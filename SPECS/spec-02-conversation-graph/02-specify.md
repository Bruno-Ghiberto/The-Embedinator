# Spec 02: ConversationGraph -- Feature Specification Context

## Feature Description

The ConversationGraph is Layer 1 of the three-layer LangGraph agent architecture. It is the outermost graph and the entry point for every chat request. It manages the full conversation lifecycle: session initialization, intent classification, query decomposition into sub-questions, parallel dispatch to ResearchGraph instances via LangGraph `Send()`, answer aggregation, grounded answer verification, citation validation, and final response formatting for SSE streaming.

**File**: `backend/agent/conversation_graph.py`

The ConversationGraph is session-scoped (no max duration). It receives a chat message from the FastAPI chat endpoint, processes it through a series of nodes, and returns a formatted response with inline citations, confidence indicators, and groundedness annotations.

## Requirements

### Functional Requirements

1. **Session Management**: Load or create session state from SQLite on each chat request. Restore conversation history. If SQLite read fails, create a fresh session and log a warning.
2. **Intent Classification**: Classify each user message as `rag_query`, `collection_mgmt`, or `ambiguous` using an LLM call. Default to `rag_query` on LLM failure.
3. **Query Decomposition**: Use Pydantic structured output to decompose complex queries into 1-5 focused sub-questions. Classify complexity tier (`factoid`, `lookup`, `comparison`, `analytical`, `multi_hop`). If structured output parsing fails, retry once with simplified prompt then fall back to single-question mode.
4. **Clarification Interrupts**: If `QueryAnalysis.is_clear == False`, use LangGraph interrupt to pause the graph and yield clarification questions to the UI. Serialize graph state to SQLite.
5. **Parallel Sub-Question Dispatch**: Spawn one ResearchGraph per sub-question using LangGraph `Send()` API. All instances run concurrently.
6. **Answer Aggregation**: Merge parallel ResearchGraph results, deduplicate citations, rank by relevance.
7. **Grounded Answer Verification (GAV)**: Run NLI-based claim-by-claim verification of the draft answer against retrieved chunks. Mark claims as SUPPORTED, UNSUPPORTED, or CONTRADICTED. If >50% of claims are unsupported, flag the answer.
8. **Citation-Chunk Alignment Validation**: Use cross-encoder to verify each inline citation points to a chunk that actually supports the claim. Remap or remove invalid citations.
9. **Response Formatting**: Apply citation annotations `[1]`, `[2]`, etc. Add confidence indicators. Annotate unverified claims with `[unverified]`. Remove contradicted claims. Format for SSE delivery.
10. **History Summarization**: Compress conversation history when token budget is approached to prevent context overflow.

### Non-Functional Requirements

1. The graph must be defined using LangGraph's `StateGraph` API with `ConversationState` as the state type.
2. All node functions must be stateless and pure -- state is passed in and returned.
3. Node functions are defined in `backend/agent/nodes.py`, not inline in the graph definition file.
4. Edge functions (routing logic) are defined in `backend/agent/edges.py`.
5. Prompt templates are defined as constants in `backend/agent/prompts.py`.
6. Dependencies (LLM, reranker, DB) are injected, not imported globally.

## Key Technical Details

### Nodes

| Node | Responsibility | Reads from State | Writes to State | Side Effects |
|------|---------------|------------------|-----------------|-------------|
| `init_session` | Load or create session state, restore conversation history from SQLite | `session_id` | `messages`, `selected_collections` | SQLite read |
| `classify_intent` | Determine if message is RAG query, collection command, or ambiguous | `messages` | `intent` (internal) | LLM call |
| `rewrite_query` | Decompose query into sub-questions with Pydantic structured output | `messages`, `selected_collections` | `query_analysis` | LLM call (structured output) |
| `request_clarification` | LangGraph interrupt -- pause graph, yield clarification questions to UI | `query_analysis` | N/A (interrupt) | Graph checkpoint to SQLite |
| `route_intent` | Branch: send to RAG path, collection management, or clarification | `intent` | N/A (routing) | None |
| `fan_out` | Spawn one ResearchGraph per sub-question using `Send()` | `query_analysis`, `selected_collections`, `llm_model`, `embed_model` | N/A (spawns subgraphs) | None |
| `aggregate_answers` | Merge parallel ResearchGraph results, deduplicate citations, rank by relevance | `sub_answers` | `final_response` (draft), `citations` | None |
| `verify_groundedness` | NLI-based claim verification against retrieved context | `final_response`, `citations`, `sub_answers` | `groundedness_result`, `confidence_score` | LLM call |
| `validate_citations` | Cross-encoder alignment check for each inline citation | `final_response`, `citations` | `citations` (corrected) | Cross-encoder inference |
| `summarize_history` | Compress conversation history when token budget is approached | `messages` | `messages` (compressed) | LLM call |
| `format_response` | Apply citation annotations, confidence indicator, stream-format for SSE | `final_response`, `citations`, `groundedness_result`, `confidence_score` | `final_response` (formatted) | None |

### Node Error Handling

| Node | Failure Mode | Recovery |
|------|-------------|----------|
| `init_session` | SQLite read failure | Create fresh session, log warning |
| `classify_intent` | LLM call failure | Default to `rag_query` intent |
| `rewrite_query` | Structured output parse failure | Retry once with simplified prompt; fall back to single-question mode |
| `fan_out` | No sub-questions generated | Use original query as sole sub-question |
| `aggregate_answers` | One or more ResearchGraphs failed | Aggregate available answers, note gaps |
| `verify_groundedness` | LLM call failure | Skip verification, set `groundedness_result = None`, log warning |
| `validate_citations` | Cross-encoder failure | Pass citations through unvalidated |

### Structured Output: QueryAnalysis

```python
class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str]              # max 5 decomposed sub-questions
    clarification_needed: Optional[str]   # human-readable clarification prompt
    collections_hint: List[str]           # suggested collection names to search
    complexity_tier: Literal[
        "factoid", "lookup", "comparison", "analytical", "multi_hop"
    ]
```

### State Schema

```python
class ConversationState(TypedDict):
    session_id: str
    messages: List[BaseMessage]
    query_analysis: Optional[QueryAnalysis]
    sub_answers: List[SubAnswer]
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    final_response: Optional[str]
    citations: List[Citation]
    groundedness_result: Optional[GroundednessResult]
    confidence_score: float
    iteration_count: int
```

### Groundedness Result Schema

```python
class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str]
    explanation: str

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool             # True if >50% claims supported
    confidence_adjustment: float       # modifier applied to confidence score
```

## Dependencies

- **Spec 01 (Vision)**: State schemas, Pydantic models, config, errors, SQLite DB, Qdrant client
- **Spec 03 (ResearchGraph)**: ConversationGraph spawns ResearchGraph via `Send()` -- ResearchGraph must be defined as a subgraph
- **Libraries**: `langgraph >= 1.0.10`, `langchain >= 1.2.10`, `pydantic >= 2.12`, `sentence-transformers >= 5.2.3`, `aiosqlite >= 0.21`
- **Services**: Ollama or cloud LLM provider for classify_intent, rewrite_query, verify_groundedness; Cross-encoder model for validate_citations

## Acceptance Criteria

1. ConversationGraph is a valid LangGraph `StateGraph` that compiles without errors.
2. `init_session` loads session history from SQLite and recovers gracefully on failure.
3. `classify_intent` returns one of three valid intents; defaults to `rag_query` on LLM failure.
4. `rewrite_query` produces a valid `QueryAnalysis` object via Pydantic structured output.
5. `fan_out` produces a `List[Send]` with one entry per sub-question.
6. `aggregate_answers` merges sub-answers and deduplicates citations correctly.
7. `verify_groundedness` produces a `GroundednessResult` with per-claim verdicts.
8. `validate_citations` removes or remaps citations where cross-encoder score is below `CITATION_ALIGNMENT_THRESHOLD` (0.3).
9. `format_response` produces a properly formatted answer with inline citation markers and confidence summary.
10. Graph routes correctly: RAG queries go to rewrite_query, ambiguous goes to request_clarification, collection commands go to collection_mgmt handler.

## Architecture Reference

### Prompt Templates

**classify_intent system prompt:**
```python
CLASSIFY_INTENT_SYSTEM = """You are an intent classifier for a RAG system.
Given the user's message and conversation history, classify the intent as one of:
- "rag_query": The user is asking a question that requires searching documents
- "collection_mgmt": The user wants to manage collections (create, delete, list)
- "ambiguous": The intent is unclear and needs clarification

Respond with a JSON object: {"intent": "rag_query"|"collection_mgmt"|"ambiguous", "reason": "..."}
"""

CLASSIFY_INTENT_USER = """Conversation history:
{history}

User message: {message}
Selected collections: {collections}
"""
```

**rewrite_query system prompt:**
```python
REWRITE_QUERY_SYSTEM = """You are a query analyzer for a document retrieval system.
Given the user's question and available collections, produce a structured analysis.

Rules:
1. Decompose complex questions into 1-5 focused sub-questions
2. Each sub-question should be answerable from a single document section
3. Identify which collections are most likely to contain relevant information
4. Classify the complexity tier to optimize retrieval depth
5. If the question is ambiguous or requires clarification, set is_clear=false

Complexity tiers:
- factoid: Single fact retrieval ("What port does X use?")
- lookup: Specific document section ("How do I configure X?")
- comparison: Cross-document comparison ("Compare X and Y approaches")
- analytical: Deep analysis requiring synthesis ("Why does X fail when Y?")
- multi_hop: Chained reasoning across multiple evidence steps
"""

REWRITE_QUERY_USER = """User question: {question}
Available collections: {collections}
Conversation context: {context}
"""
```

**verify_groundedness system prompt:**
```python
VERIFY_GROUNDEDNESS_SYSTEM = """Given ONLY the retrieved context below, evaluate each claim
in the proposed answer. For each claim, respond with:
- SUPPORTED: the context contains evidence for this claim
- UNSUPPORTED: no evidence found in the retrieved context
- CONTRADICTED: the context contradicts this claim

Be strict. If the context merely discusses a related topic but does not
explicitly support the specific claim, mark it UNSUPPORTED.

Retrieved Context:
{context}

Proposed Answer:
{answer}
"""
```

**format_response system prompt:**
```python
FORMAT_RESPONSE_SYSTEM = """Format the answer for the user with inline citations.

Rules:
1. Insert citation markers [1], [2], etc. where claims are supported by specific chunks
2. Each citation must reference a real chunk from the provided list
3. If the groundedness check flagged unsupported claims, annotate them with [unverified]
4. If the groundedness check flagged contradicted claims, remove them and note the contradiction
5. End with a confidence summary if confidence < 0.7

Chunks available for citation:
{chunks_with_ids}

Groundedness result:
{groundedness_result}
"""
```

### Citation Validation Implementation

```python
async def validate_citations(
    state: ConversationState,
    reranker: CrossEncoder,
) -> ConversationState:
    """Verify each citation points to a chunk that supports the claim."""
    corrected_citations: List[Citation] = []

    for citation in state["citations"]:
        claim_text = citation.claim_text
        chunk_text = citation.chunk.text

        score = reranker.predict([(claim_text, chunk_text)])[0]

        if score >= CITATION_ALIGNMENT_THRESHOLD:
            corrected_citations.append(citation)
        else:
            # Try to remap to the best matching chunk
            all_chunks = [sa.chunks for sa in state["sub_answers"]]
            flat_chunks = [c for sublist in all_chunks for c in sublist]
            pairs = [(claim_text, c.text) for c in flat_chunks]
            scores = reranker.predict(pairs)
            best_idx = int(scores.argmax())
            best_score = scores[best_idx]

            if best_score >= CITATION_ALIGNMENT_THRESHOLD:
                citation.chunk = flat_chunks[best_idx]
                corrected_citations.append(citation)
            # else: citation is dropped entirely

    return {**state, "citations": corrected_citations}
```

### SSE Event Format

```
data: {"type": "token", "content": "..."}
data: {"type": "citation", "index": 1, "chunkId": "...", "source": "...", "page": 5}
data: {"type": "done", "latency_ms": 1240}
```

### Full Chat Query Sequence (from browser to response)

1. Browser submits query to Next.js
2. Next.js sends `POST /api/chat {message, collection_ids, llm_model, session_id}` to FastAPI
3. FastAPI loads session history from SQLite
4. FastAPI invokes ConversationGraph
5. `init_session` -> `classify_intent` -> `route_intent` -> `rewrite_query` -> `fan_out`
6. `fan_out` spawns N ResearchGraph instances via `Send()` (parallel)
7. Each ResearchGraph returns `SubAnswer + citations`
8. `aggregate_answers` -> `verify_groundedness` -> `validate_citations` -> `format_response`
9. Formatted response streamed via SSE to Next.js to Browser
10. FastAPI writes `query_trace` record to SQLite
