# Spec 02: ConversationGraph -- Implementation Context

## Implementation Scope

### Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/agent/conversation_graph.py` | Create | StateGraph definition, node/edge wiring, compile |
| `backend/agent/nodes.py` | Create | All node function implementations (ConversationGraph, ResearchGraph, MetaReasoningGraph) |
| `backend/agent/edges.py` | Create | All conditional edge functions |
| `backend/agent/prompts.py` | Modify (add prompts) | Add all ConversationGraph prompt constants |
| `backend/api/chat.py` | Modify (replace stub) | Full chat endpoint with SSE streaming |

## Code Specifications

### backend/agent/conversation_graph.py

```python
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from backend.agent.state import ConversationState
from backend.agent.nodes import (
    init_session, classify_intent, rewrite_query,
    request_clarification, fan_out, aggregate_answers,
    verify_groundedness, validate_citations, format_response,
)
from backend.agent.edges import route_intent, should_clarify


def build_conversation_graph(research_graph_compiled):
    """Build and compile the ConversationGraph.

    Args:
        research_graph_compiled: The compiled ResearchGraph to use as a subgraph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(ConversationState)

    # Add nodes
    graph.add_node("init_session", init_session)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("fan_out", fan_out)
    graph.add_node("research", research_graph_compiled)
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("verify_groundedness", verify_groundedness)
    graph.add_node("validate_citations", validate_citations)
    graph.add_node("format_response", format_response)

    # Edges
    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "classify_intent")
    graph.add_conditional_edges("classify_intent", route_intent, {
        "rag_query": "rewrite_query",
        "ambiguous": "request_clarification",
    })
    graph.add_edge("request_clarification", "classify_intent")
    graph.add_conditional_edges("rewrite_query", should_clarify, {
        True: "request_clarification",
        False: "fan_out",
    })
    graph.add_edge("fan_out", "research")
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile()
```

### backend/agent/nodes.py -- ConversationGraph Nodes

```python
import json
import structlog
from typing import List, Optional
from langgraph.types import Send, interrupt
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from sentence_transformers import CrossEncoder

from backend.agent.state import ConversationState, ResearchState
from backend.agent.schemas import (
    QueryAnalysis, SubAnswer, Citation, GroundednessResult,
    ClaimVerification, RetrievedChunk,
)
from backend.agent.prompts import (
    CLASSIFY_INTENT_SYSTEM, CLASSIFY_INTENT_USER,
    REWRITE_QUERY_SYSTEM, REWRITE_QUERY_USER,
    VERIFY_GROUNDEDNESS_SYSTEM, FORMAT_RESPONSE_SYSTEM,
)
from backend.errors import SessionLoadError, LLMCallError, StructuredOutputParseError
from backend.config import Settings

logger = structlog.get_logger()


async def init_session(state: ConversationState, *, db) -> ConversationState:
    """Load or create session. Restores message history from SQLite.
    Reads: state["session_id"]
    Writes: state["messages"], state["selected_collections"]
    On failure: Create fresh session, log warning.
    """
    ...


async def classify_intent(state: ConversationState, *, llm) -> dict:
    """Classify user intent as rag_query, collection_mgmt, or ambiguous.
    Reads: state["messages"]
    Returns: {"intent": Literal["rag_query", "collection_mgmt", "ambiguous"]}
    On failure: Defaults to "rag_query".
    """
    ...


async def rewrite_query(state: ConversationState, *, llm) -> ConversationState:
    """Decompose query into sub-questions with Pydantic structured output.
    Reads: state["messages"], state["selected_collections"]
    Writes: state["query_analysis"]
    On failure: Retry once, then single-question fallback.
    Uses: llm.with_structured_output(QueryAnalysis)
    """
    ...


async def request_clarification(state: ConversationState) -> None:
    """LangGraph interrupt -- pause graph, yield clarification questions.
    Reads: state["query_analysis"]
    Effect: interrupt() call, graph checkpoint serialized to SQLite.
    """
    clarification = state["query_analysis"].clarification_needed
    interrupt({"clarification_needed": clarification})


async def fan_out(state: ConversationState) -> List[Send]:
    """Spawn one ResearchGraph per sub-question via LangGraph Send().
    Reads: state["query_analysis"], state["selected_collections"],
           state["llm_model"], state["embed_model"]
    Returns: List[Send] -- one per sub-question.
    Fallback: If no sub-questions, use original query as sole sub-question.
    """
    qa = state["query_analysis"]
    sub_questions = qa.sub_questions if qa and qa.sub_questions else [
        state["messages"][-1].content  # fallback to original query
    ]
    collections = (qa.collections_hint if qa and qa.collections_hint
                   else state["selected_collections"])

    sends = []
    for sub_q in sub_questions:
        sends.append(Send("research", {
            "sub_question": sub_q,
            "session_id": state["session_id"],
            "selected_collections": collections,
            "llm_model": state["llm_model"],
            "embed_model": state["embed_model"],
            "retrieved_chunks": [],
            "retrieval_keys": set(),
            "tool_call_count": 0,
            "iteration_count": 0,
            "confidence_score": 0.0,
            "answer": None,
            "citations": [],
            "context_compressed": False,
        }))
    return sends


async def aggregate_answers(state: ConversationState) -> ConversationState:
    """Merge parallel ResearchGraph results, deduplicate citations, rank.
    Reads: state["sub_answers"]
    Writes: state["final_response"] (draft), state["citations"]
    Handles: Partial failures (some ResearchGraphs may have failed).
    """
    ...


async def verify_groundedness(state: ConversationState, *, llm) -> ConversationState:
    """NLI-based claim-by-claim verification against retrieved chunks.
    Reads: state["final_response"], state["citations"], state["sub_answers"]
    Writes: state["groundedness_result"], state["confidence_score"]
    On failure: Sets groundedness_result=None, logs warning.
    Uses: llm with VERIFY_GROUNDEDNESS_SYSTEM prompt, structured output -> GroundednessResult
    """
    ...


async def validate_citations(
    state: ConversationState, *, reranker: CrossEncoder
) -> ConversationState:
    """Cross-encoder alignment check for each inline citation.
    Reads: state["final_response"], state["citations"]
    Writes: state["citations"] (corrected)
    On failure: Pass citations through unvalidated.

    For each citation:
    1. Score (claim_text, chunk_text) with cross-encoder
    2. If score >= CITATION_ALIGNMENT_THRESHOLD (0.3): keep
    3. If score < threshold: try to remap to best-matching chunk from all sub_answers
    4. If best remap score < threshold: drop citation entirely
    """
    corrected_citations: List[Citation] = []
    CITATION_ALIGNMENT_THRESHOLD = 0.3

    for citation in state["citations"]:
        claim_text = citation.claim_text
        chunk_text = citation.chunk.text

        score = reranker.predict([(claim_text, chunk_text)])[0]

        if score >= CITATION_ALIGNMENT_THRESHOLD:
            corrected_citations.append(citation)
        else:
            all_chunks = [sa.chunks for sa in state["sub_answers"]]
            flat_chunks = [c for sublist in all_chunks for c in sublist]
            pairs = [(claim_text, c.text) for c in flat_chunks]
            scores = reranker.predict(pairs)
            best_idx = int(scores.argmax())
            best_score = scores[best_idx]

            if best_score >= CITATION_ALIGNMENT_THRESHOLD:
                citation.chunk = flat_chunks[best_idx]
                corrected_citations.append(citation)

    return {**state, "citations": corrected_citations}


async def format_response(state: ConversationState) -> ConversationState:
    """Apply citation annotations, confidence indicator, SSE formatting.
    Reads: state["final_response"], state["citations"],
           state["groundedness_result"], state["confidence_score"]
    Writes: state["final_response"] (formatted)

    Rules:
    - Insert [1], [2] markers where claims are supported
    - Annotate unsupported claims with [unverified]
    - Remove contradicted claims, note contradiction
    - Add confidence summary if confidence < 0.7
    """
    ...
```

### backend/agent/edges.py

```python
from backend.agent.state import ConversationState


def route_intent(state: ConversationState) -> str:
    """Route based on classified intent.
    Returns node name: 'rewrite_query', 'collection_mgmt', or 'request_clarification'.
    """
    intent = state.get("intent", "rag_query")
    if intent == "rag_query":
        return "rewrite_query"
    elif intent == "collection_mgmt":
        return "collection_mgmt"
    else:
        return "request_clarification"


def should_clarify(state: ConversationState) -> bool:
    """Check if query needs clarification.
    Returns True if query_analysis.is_clear == False and clarification_needed is set.
    """
    qa = state.get("query_analysis")
    if qa and not qa.is_clear and qa.clarification_needed:
        return True
    return False
```

### backend/agent/prompts.py (ConversationGraph additions)

```python
# --- ConversationGraph prompts ---

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

### backend/api/chat.py

```python
import json
import time
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    collection_ids: List[str]
    llm_model: Optional[str] = None
    embed_model: Optional[str] = None
    session_id: Optional[str] = None


@router.post("/chat")
async def chat(request: Request, body: ChatRequest):
    """Chat endpoint with SSE streaming.

    1. Build initial ConversationState from request
    2. Invoke compiled ConversationGraph via astream_events()
    3. Stream tokens, citations, and done event via SSE
    4. Write query_trace record to SQLite
    """
    app = request.app
    graph = app.state.conversation_graph
    db = app.state.db
    settings = app.state.settings

    session_id = body.session_id or generate_session_id()
    llm_model = body.llm_model or settings.default_llm_model
    embed_model = body.embed_model or settings.default_embed_model

    initial_state = {
        "session_id": session_id,
        "messages": [HumanMessage(content=body.message)],
        "query_analysis": None,
        "sub_answers": [],
        "selected_collections": body.collection_ids,
        "llm_model": llm_model,
        "embed_model": embed_model,
        "final_response": None,
        "citations": [],
        "groundedness_result": None,
        "confidence_score": 0.0,
        "iteration_count": 0,
    }

    start_time = time.monotonic()

    async def event_stream():
        async for event in graph.astream_events(initial_state, version="v2"):
            if event["event"] == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                if token:
                    yield f'data: {json.dumps({"type": "token", "content": token})}\n\n'

        latency_ms = int((time.monotonic() - start_time) * 1000)
        yield f'data: {json.dumps({"type": "done", "latency_ms": latency_ms})}\n\n'

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

## Configuration

Relevant settings from `backend/config.py`:
- `max_iterations: int = 10` -- Max tool loop iterations in ResearchGraph
- `max_tool_calls: int = 8` -- Max tool calls in ResearchGraph
- `confidence_threshold: float = 0.6` -- Triggers MetaReasoningGraph below this
- `groundedness_check_enabled: bool = True` -- Toggle GAV on/off
- `citation_alignment_threshold: float = 0.3` -- Cross-encoder score floor for valid citations
- `reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"` -- Model for citation validation

## Error Handling

| Node | Error | Recovery |
|------|-------|----------|
| `init_session` | `SessionLoadError` from SQLite | Create fresh session, log warning, continue |
| `classify_intent` | `LLMCallError` | Default to `{"intent": "rag_query"}`, log warning |
| `rewrite_query` | `StructuredOutputParseError` | Retry once with simplified prompt; if fails again, create single-question `QueryAnalysis` using original message |
| `fan_out` | Empty `sub_questions` list | Use original user message as sole sub-question |
| `aggregate_answers` | Some `sub_answers` are None/failed | Aggregate only successful answers, log which sub-questions failed |
| `verify_groundedness` | `LLMCallError` | Set `groundedness_result = None`, do not adjust confidence, log warning |
| `validate_citations` | `RerankerError` (cross-encoder failure) | Pass all citations through unvalidated, log warning |

## Testing Requirements

### Unit Tests
- `test_classify_intent`: Mock LLM, verify correct routing for each intent type
- `test_classify_intent_fallback`: Mock LLM failure, verify defaults to `rag_query`
- `test_rewrite_query`: Mock LLM with structured output, verify `QueryAnalysis` is produced correctly
- `test_rewrite_query_fallback`: Mock parse failure, verify single-question fallback
- `test_fan_out`: Given a `QueryAnalysis` with 3 sub-questions, verify 3 `Send` objects produced
- `test_aggregate_answers`: Given 3 `SubAnswer` objects, verify deduplication and merge
- `test_validate_citations_keeps_valid`: Mock cross-encoder with score > 0.3, verify citation kept
- `test_validate_citations_remaps_invalid`: Mock cross-encoder with low score for original chunk but high for alternative, verify remap
- `test_validate_citations_drops_invalid`: Mock cross-encoder with all low scores, verify citation dropped
- `test_format_response`: Verify citation markers inserted, unverified annotations added

### Integration Tests
- `test_conversation_graph_end_to_end`: Run full graph with mocked LLM and Qdrant, verify SSE event stream
- `test_clarification_interrupt`: Verify graph pauses when `is_clear == False` and resumes with user response

## Done Criteria

- [ ] `backend/agent/conversation_graph.py` defines and compiles a valid LangGraph StateGraph
- [ ] All node functions implemented in `backend/agent/nodes.py` with proper error handling
- [ ] All edge functions implemented in `backend/agent/edges.py`
- [ ] All prompt templates defined in `backend/agent/prompts.py`
- [ ] `backend/api/chat.py` implements SSE streaming endpoint
- [ ] `fan_out` correctly produces `Send()` calls for parallel ResearchGraph dispatch
- [ ] `verify_groundedness` produces `GroundednessResult` with per-claim verdicts
- [ ] `validate_citations` correctly keeps, remaps, or drops citations based on cross-encoder score
- [ ] `format_response` produces properly formatted output with citation markers
- [ ] All error recovery paths work as specified (LLM failures, parse failures, etc.)
- [ ] Unit tests pass for all node functions
- [ ] Integration test for full graph execution passes with mocked dependencies
