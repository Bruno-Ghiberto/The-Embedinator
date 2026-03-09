# Spec 03: ResearchGraph -- Feature Specification Context

## Feature Description

The ResearchGraph is Layer 2 of the three-layer LangGraph agent architecture. One ResearchGraph instance is spawned per sub-question via LangGraph `Send()` from the ConversationGraph's `fan_out` node. Multiple instances run concurrently. Each instance manages its own tool-call loop with deduplication, safety limits, context compression, and confidence tracking.

**File**: `backend/agent/research_graph.py`

The ResearchGraph is the "worker" layer -- it takes a single sub-question, searches Qdrant collections using hybrid retrieval, cross-encoder reranks results, tracks deduplication to avoid redundant searches, and iterates until it either reaches sufficient confidence or exhausts its tool budget. On budget exhaustion with low confidence, it routes to the MetaReasoningGraph for failure recovery.

## Requirements

### Functional Requirements

1. **Orchestrator Loop**: An LLM-driven orchestrator decides which tool(s) to call next based on the current sub-question, retrieved chunks, iteration count, and tool call count.
2. **Tool Execution**: Execute tool calls decided by the orchestrator. Tools include `search_child_chunks`, `retrieve_parent_chunks`, `cross_encoder_rerank`, `filter_by_collection`, `filter_by_metadata`, and `semantic_search_all_collections`.
3. **Deduplication**: Maintain a `retrieval_keys: Set[str]` where the key is `f"{query_normalized}:{parent_id}"`. Skip any (query, parent chunk) pair already seen in this instance.
4. **Context Compression**: When retrieved chunks approach the model's context window limit, summarize them via an LLM call before continuing.
5. **Loop Termination**: Stop when any of these conditions is met:
   - `MAX_ITERATIONS = 10` total loop iterations reached
   - `MAX_TOOL_CALLS = 8` total tool calls reached
   - Orchestrator determines answer is sufficient (confidence above threshold)
   - No new tool calls are generated (tool exhaustion)
6. **Confidence Routing**: If the loop ends with `confidence_score < CONFIDENCE_THRESHOLD` and budget is exhausted, route to MetaReasoningGraph for recovery.
7. **Fallback Response**: If tools are exhausted and MetaReasoningGraph is not triggered (or is not available in Phase 1), generate a graceful "insufficient information" response.
8. **Answer Collection**: Package the final answer with citations and confidence score for return to ConversationGraph.

### Non-Functional Requirements

1. Tokenizer selection must use the appropriate tokenizer for the active model. For Ollama models, use `tiktoken` approximation or the model's own tokenizer endpoint -- not `cl100k_base` (which is GPT-specific).
2. All node functions are stateless and pure.
3. Tool definitions use LangChain's `@tool` decorator.

## Key Technical Details

### Nodes

| Node | Responsibility | Reads from State | Writes to State | Side Effects |
|------|---------------|------------------|-----------------|-------------|
| `orchestrator` | Decide which tool(s) to call next based on current retrieved context | `sub_question`, `retrieved_chunks`, `tool_call_count`, `iteration_count` | `pending_tool_calls` (internal) | LLM call |
| `tools` | Execute the chosen tool call(s), update state with results | `pending_tool_calls`, `retrieval_keys` | `retrieved_chunks`, `retrieval_keys`, `tool_call_count` | Qdrant search, cross-encoder |
| `should_compress_context` | Check token count against model-appropriate tokenizer | `retrieved_chunks`, `llm_model` | N/A (routing decision) | Token counting |
| `compress_context` | Summarize retrieved chunks when context window is approached | `retrieved_chunks` | `retrieved_chunks` (compressed), `context_compressed` | LLM call |
| `fallback_response` | Generate graceful "insufficient information" response when tools exhausted | `sub_question`, `retrieved_chunks` | `answer` | None |
| `collect_answer` | Package final answer + citations for return to ConversationGraph | `sub_question`, `retrieved_chunks`, `answer` | `answer`, `citations`, `confidence_score` | None |

### Available Tools

| Tool | Description | Input | Output | Side Effects |
|------|-------------|-------|--------|-------------|
| `search_child_chunks` | Hybrid dense+BM25 search in Qdrant on child chunk collection | `query: str, collection: str, top_k: int, filters: Optional[dict]` | `List[RetrievedChunk]` | Qdrant search + cross-encoder rerank |
| `retrieve_parent_chunks` | Fetch parent chunks from SQLite by parent_id list | `parent_ids: List[str]` | `List[ParentChunk]` | SQLite read |
| `cross_encoder_rerank` | Score (query, chunk) pairs with cross-encoder, return ranked list | `query: str, chunks: List[RetrievedChunk], top_k: int` | `List[RetrievedChunk]` (reranked) | Cross-encoder inference |
| `filter_by_collection` | Constrain search to a named collection | `collection_name: str` | State modification | None |
| `filter_by_metadata` | Apply Qdrant payload filter (doc_type, page range, source_file) | `filters: dict` | State modification | None |
| `semantic_search_all_collections` | Fan-out search across all enabled collections simultaneously | `query: str, top_k: int` | `List[RetrievedChunk]` (merged, normalized) | Qdrant multi-collection search |

### Loop Control Constants

```python
MAX_ITERATIONS = 10    # total loop iterations
MAX_TOOL_CALLS = 8     # total tool calls
CONFIDENCE_THRESHOLD = 0.6  # from Settings
```

### Deduplication Key

```python
key = f"{query_normalized}:{parent_id}"
# Added to retrieval_keys: Set[str] after each retrieval
# Any (query, parent chunk) pair already seen is skipped
```

### State Schema

```python
class ResearchState(TypedDict):
    sub_question: str
    session_id: str
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    retrieved_chunks: List[RetrievedChunk]
    retrieval_keys: Set[str]
    tool_call_count: int
    iteration_count: int
    confidence_score: float
    answer: Optional[str]
    citations: List[Citation]
    context_compressed: bool
```

### Orchestrator Prompt Template

```python
ORCHESTRATOR_SYSTEM = """You are a research orchestrator for a RAG system. Your goal is to
find the best evidence to answer the given sub-question.

Available tools:
{tool_descriptions}

Already retrieved chunks (count: {chunk_count}):
{chunk_summaries}

Rules:
1. Call search_child_chunks first with the sub-question as the query
2. If initial results are insufficient, try rephrasing the query
3. Use filter_by_metadata to narrow results if you get too many irrelevant chunks
4. Use retrieve_parent_chunks to get full context for promising child chunks
5. Stop when you have enough evidence OR when you've exhausted useful search angles
6. Never repeat the same search query + collection combination

Iteration: {iteration} / {max_iterations}
Tool calls used: {tool_call_count} / {max_tool_calls}
"""

ORCHESTRATOR_USER = """Sub-question: {sub_question}
Target collections: {collections}
Current confidence: {confidence_score}
"""
```

## Dependencies

- **Spec 01 (Vision)**: State schemas (`ResearchState`), Pydantic models (`RetrievedChunk`, `ParentChunk`, `Citation`, `SubAnswer`), config (`Settings`), errors
- **Spec 02 (ConversationGraph)**: Spawns ResearchGraph via `Send()` -- ResearchGraph must conform to the state interface expected by `fan_out`
- **Spec 04 (MetaReasoningGraph)**: ResearchGraph routes to MetaReasoningGraph on low confidence + budget exhaustion
- **Libraries**: `langgraph >= 1.0.10`, `langchain >= 1.2.10`, `qdrant-client >= 1.17.0`, `sentence-transformers >= 5.2.3`, `tiktoken >= 0.12`
- **Services**: Qdrant (hybrid search), Ollama/cloud LLM (orchestrator decisions, context compression), cross-encoder model (reranking)

## Acceptance Criteria

1. ResearchGraph is a valid LangGraph `StateGraph` that compiles without errors.
2. Orchestrator loop respects `MAX_ITERATIONS` (10) and `MAX_TOOL_CALLS` (8) limits.
3. Deduplication prevents redundant (query, parent_id) searches.
4. Context compression triggers when token count approaches model context window.
5. When confidence >= threshold, loop terminates and `collect_answer` is reached.
6. When confidence < threshold and budget exhausted, graph routes to MetaReasoningGraph.
7. When tools are exhausted (no new tool calls generated), `fallback_response` is reached.
8. All six tools are properly defined with LangChain `@tool` decorator and correct signatures.
9. Tool results are correctly merged into `retrieved_chunks` with deduplication.
10. `collect_answer` produces a `SubAnswer` with answer text, citations, retrieved chunks, and confidence score.

## Architecture Reference

### Tool Implementation Signatures

```python
from langchain_core.tools import tool
from backend.retrieval.searcher import HybridSearcher
from backend.retrieval.reranker import Reranker
from backend.storage.parent_store import ParentStore
from backend.agent.schemas import RetrievedChunk, ParentChunk

@tool
async def search_child_chunks(
    query: str,
    collection: str,
    top_k: int = 20,
    filters: Optional[dict] = None,
) -> List[RetrievedChunk]:
    """Hybrid dense+BM25 search with cross-encoder reranking.
    Raises: QdrantConnectionError, EmbeddingError
    """
    ...

@tool
async def retrieve_parent_chunks(
    parent_ids: List[str],
) -> List[ParentChunk]:
    """Fetch parent chunks from SQLite by parent_id list.
    Raises: SQLiteError
    """
    ...

@tool
async def cross_encoder_rerank(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """Score (query, chunk) pairs with cross-encoder.
    Raises: RerankerError
    """
    ...

@tool
async def filter_by_collection(
    collection_name: str,
) -> dict:
    """Constrain search to a named collection."""
    ...

@tool
async def filter_by_metadata(
    filters: dict,
) -> dict:
    """Apply Qdrant payload filter (doc_type, page range, source_file)."""
    ...

@tool
async def semantic_search_all_collections(
    query: str,
    top_k: int = 20,
) -> List[RetrievedChunk]:
    """Fan-out search across all enabled collections.
    Results are merged and normalized per-collection before merging.
    Raises: QdrantConnectionError, EmbeddingError
    """
    ...
```

### MetaReasoningGraph Trigger Condition

```python
if (state["iteration_count"] >= MAX_ITERATIONS or
    state["tool_call_count"] >= MAX_TOOL_CALLS) and \
   state["confidence_score"] < CONFIDENCE_THRESHOLD:
    # Route to MetaReasoningGraph
```

### Node Interface Contracts

```python
async def orchestrator(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Decide which tools to call based on current context.
    Reads: state["sub_question"], state["retrieved_chunks"],
           state["tool_call_count"], state["iteration_count"]
    Writes: internal tool_call decisions
    Raises: LLMCallError (triggers fallback_response)
    """

async def collect_answer(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Generate answer from retrieved chunks, compute confidence.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"], state["citations"], state["confidence_score"]
    """

async def compress_context(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Summarize retrieved chunks when context window is approached.
    Reads: state["retrieved_chunks"], state["llm_model"]
    Writes: state["retrieved_chunks"] (compressed), state["context_compressed"]
    """

async def fallback_response(
    state: ResearchState,
) -> ResearchState:
    """Generate graceful insufficient-information response.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"]
    """
```
