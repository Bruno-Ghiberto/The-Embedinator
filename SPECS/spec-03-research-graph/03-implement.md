# Spec 03: ResearchGraph -- Implementation Context

## Implementation Scope

### Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/agent/research_graph.py` | Create | StateGraph definition for ResearchGraph |
| `backend/agent/tools.py` | Create | LangChain @tool definitions for all six tools |
| `backend/agent/nodes.py` | Modify | Add ResearchGraph node functions |
| `backend/agent/edges.py` | Modify | Add ResearchGraph edge functions |
| `backend/agent/prompts.py` | Modify | Add orchestrator prompt templates |
| `backend/retrieval/__init__.py` | Create | Package marker |
| `backend/retrieval/searcher.py` | Create | Qdrant hybrid search execution |
| `backend/retrieval/reranker.py` | Create | Cross-encoder reranking |
| `backend/retrieval/router.py` | Create | Regex-based collection routing |
| `backend/retrieval/score_normalizer.py` | Create | Per-collection min-max normalization |
| `backend/storage/parent_store.py` | Create | Parent chunk read from SQLite |

## Code Specifications

### backend/agent/research_graph.py

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import ResearchState
from backend.agent.nodes import (
    orchestrator, tools_node, should_compress_context_node,
    compress_context, collect_answer, fallback_response,
)
from backend.agent.edges import should_continue_loop, route_after_compress_check


def build_research_graph(meta_reasoning_graph=None):
    """Build and compile the ResearchGraph.

    Args:
        meta_reasoning_graph: Optional compiled MetaReasoningGraph.
            If None, budget exhaustion routes to fallback_response.
            If provided, budget exhaustion routes to meta_reasoning.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(ResearchState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("tools", tools_node)
    graph.add_node("should_compress_context", should_compress_context_node)
    graph.add_node("compress_context", compress_context)
    graph.add_node("collect_answer", collect_answer)
    graph.add_node("fallback_response", fallback_response)

    if meta_reasoning_graph:
        graph.add_node("meta_reasoning", meta_reasoning_graph)

    graph.add_edge(START, "orchestrator")

    exhausted_target = "meta_reasoning" if meta_reasoning_graph else "fallback_response"
    graph.add_conditional_edges("orchestrator", should_continue_loop, {
        "continue": "tools",
        "sufficient": "collect_answer",
        "exhausted": exhausted_target,
    })

    graph.add_edge("tools", "should_compress_context")
    graph.add_conditional_edges(
        "should_compress_context", route_after_compress_check, {
            "compress": "compress_context",
            "continue": "orchestrator",
        }
    )
    graph.add_edge("compress_context", "orchestrator")
    graph.add_edge("collect_answer", END)
    graph.add_edge("fallback_response", END)

    if meta_reasoning_graph:
        graph.add_edge("meta_reasoning", "orchestrator")

    return graph.compile()
```

### backend/agent/tools.py

```python
from typing import List, Optional
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
    """Hybrid dense+BM25 search in Qdrant on child chunk collection,
    followed by cross-encoder reranking.

    Args:
        query: The search query text.
        collection: Name of the Qdrant collection to search.
        top_k: Number of results to return after reranking.
        filters: Optional Qdrant payload filters (doc_type, page range, source_file).

    Returns:
        List of RetrievedChunk objects sorted by rerank score descending.

    Raises:
        QdrantConnectionError: If Qdrant is unreachable.
        EmbeddingError: If embedding generation fails.
    """
    ...


@tool
async def retrieve_parent_chunks(
    parent_ids: List[str],
) -> List[ParentChunk]:
    """Fetch parent chunks from SQLite by parent_id list.
    Parent chunks contain the full surrounding context for child chunks.

    Args:
        parent_ids: List of parent chunk IDs to retrieve.

    Returns:
        List of ParentChunk objects.

    Raises:
        SQLiteError: If database read fails.
    """
    ...


@tool
async def cross_encoder_rerank(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """Score (query, chunk) pairs with cross-encoder and return top-k ranked results.

    Args:
        query: The search query text.
        chunks: List of chunks to rerank.
        top_k: Number of top results to return.

    Returns:
        List of RetrievedChunk objects sorted by cross-encoder score descending.

    Raises:
        RerankerError: If cross-encoder inference fails.
    """
    ...


@tool
async def filter_by_collection(
    collection_name: str,
) -> dict:
    """Constrain subsequent searches to a specific named collection.

    Args:
        collection_name: The collection to constrain to.

    Returns:
        State modification dict with updated collection filter.
    """
    ...


@tool
async def filter_by_metadata(
    filters: dict,
) -> dict:
    """Apply Qdrant payload filter to narrow search results.
    Supported filter keys: doc_type, page_range, source_file, breadcrumb.

    Args:
        filters: Dictionary of payload filter conditions.

    Returns:
        State modification dict with updated metadata filters.
    """
    ...


@tool
async def semantic_search_all_collections(
    query: str,
    top_k: int = 20,
) -> List[RetrievedChunk]:
    """Fan-out search across all enabled collections simultaneously.
    Results are normalized per-collection (min-max) before merging.

    Args:
        query: The search query text.
        top_k: Number of results to return after merge.

    Returns:
        List of RetrievedChunk objects merged from all collections.

    Raises:
        QdrantConnectionError: If Qdrant is unreachable.
        EmbeddingError: If embedding generation fails.
    """
    ...
```

### backend/agent/nodes.py -- ResearchGraph Nodes

```python
import structlog
from typing import List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from backend.agent.state import ResearchState
from backend.agent.schemas import RetrievedChunk, Citation, SubAnswer
from backend.agent.prompts import ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER
from backend.config import Settings

logger = structlog.get_logger()

# --- ResearchGraph nodes ---

async def orchestrator(state: ResearchState, *, llm) -> ResearchState:
    """Decide which tools to call based on current context.

    Binds all available tools to the LLM and invokes with the orchestrator prompt.
    Parses tool calls from the response. Increments iteration_count.

    Reads: state["sub_question"], state["retrieved_chunks"],
           state["tool_call_count"], state["iteration_count"]
    Writes: internal tool_call decisions, state["iteration_count"]
    Raises: LLMCallError (triggers fallback_response via edge function)
    """
    ...


async def tools_node(state: ResearchState) -> ResearchState:
    """Execute pending tool calls from orchestrator.

    For each tool call:
    1. Execute the tool function
    2. Deduplicate results against retrieval_keys
    3. Merge new chunks into retrieved_chunks
    4. Increment tool_call_count

    Deduplication key: f"{normalize_query(query)}:{parent_id}"

    Reads: pending tool calls, state["retrieval_keys"]
    Writes: state["retrieved_chunks"], state["retrieval_keys"], state["tool_call_count"]
    """
    ...


async def should_compress_context_node(state: ResearchState) -> ResearchState:
    """Check token count against model context window.

    Uses tiktoken approximation for token counting.
    This is a routing node -- actual routing is done by the edge function.

    Reads: state["retrieved_chunks"], state["llm_model"]
    Writes: nothing (routing decision is in edge function)
    """
    ...


async def compress_context(state: ResearchState, *, llm) -> ResearchState:
    """Summarize retrieved chunks when context window is approached.

    Concatenates all chunk texts, summarizes via LLM call,
    replaces retrieved_chunks with compressed versions.

    Reads: state["retrieved_chunks"], state["llm_model"]
    Writes: state["retrieved_chunks"] (compressed), state["context_compressed"] = True
    """
    ...


async def collect_answer(state: ResearchState, *, llm) -> ResearchState:
    """Generate answer from retrieved chunks, compute confidence, build citations.

    1. Build prompt with sub_question + retrieved chunks
    2. LLM generates answer with inline references
    3. Build Citation objects mapping references to chunks
    4. Compute confidence_score from cross-encoder relevance scores

    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"], state["citations"], state["confidence_score"]
    """
    ...


async def fallback_response(state: ResearchState) -> ResearchState:
    """Generate graceful insufficient-information response.

    Does NOT hallucinate. States what was searched, what was found (if anything),
    and why results were insufficient.

    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"]
    """
    ...
```

### backend/agent/edges.py -- ResearchGraph Edges

```python
from backend.agent.state import ResearchState
from backend.config import Settings

settings = Settings()


def should_continue_loop(state: ResearchState) -> str:
    """Determine whether the orchestrator loop should continue.

    Returns:
        "continue": More iterations available and tool calls available
        "sufficient": Confidence >= threshold, proceed to collect_answer
        "exhausted": Budget exhausted with low confidence, route to meta-reasoning or fallback
    """
    if state["confidence_score"] >= settings.confidence_threshold:
        return "sufficient"

    if (state["iteration_count"] >= settings.max_iterations or
        state["tool_call_count"] >= settings.max_tool_calls):
        return "exhausted"

    # Check if orchestrator produced no new tool calls (tool exhaustion)
    # This is detected by checking if the last orchestrator response had zero tool calls
    # Implementation detail: set a flag in orchestrator node
    if state.get("_no_new_tools", False):
        return "exhausted"

    return "continue"


def route_after_compress_check(state: ResearchState) -> str:
    """Route after context size check.

    Returns:
        "compress": Token count exceeds budget, compress before continuing
        "continue": Token count within budget, continue to orchestrator
    """
    # Check if total token count of retrieved_chunks exceeds threshold
    # Threshold is ~75% of model context window
    # Implementation uses tiktoken approximation
    if state.get("_needs_compression", False):
        return "compress"
    return "continue"
```

### backend/agent/prompts.py -- ResearchGraph Additions

```python
# --- ResearchGraph prompts ---

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

### backend/retrieval/searcher.py

```python
from typing import List, Optional
from qdrant_client import QdrantClient
from backend.agent.schemas import RetrievedChunk
from backend.config import Settings


class HybridSearcher:
    """Executes hybrid dense + BM25 search against Qdrant."""

    def __init__(self, qdrant_client: QdrantClient, settings: Settings):
        self.client = qdrant_client
        self.dense_weight = settings.hybrid_dense_weight    # 0.7
        self.sparse_weight = settings.hybrid_sparse_weight  # 0.3
        self.default_top_k = settings.top_k_retrieval       # 20

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 20,
        filters: Optional[dict] = None,
        embed_fn=None,
    ) -> List[RetrievedChunk]:
        """Execute hybrid search.

        1. Generate dense embedding for query via embed_fn
        2. Execute Qdrant query with dense + BM25 (sparse) fusion
        3. Apply payload filters if provided
        4. Return top_k results as RetrievedChunk objects
        """
        ...
```

### backend/retrieval/reranker.py

```python
from typing import List
from sentence_transformers import CrossEncoder
from backend.agent.schemas import RetrievedChunk
from backend.config import Settings


class Reranker:
    """Cross-encoder reranking for retrieved chunks."""

    def __init__(self, settings: Settings):
        self.model = CrossEncoder(settings.reranker_model)
        self.default_top_k = settings.top_k_rerank  # 5

    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """Score (query, chunk) pairs and return top-k sorted by score.

        1. Build pairs: [(query, chunk.text) for chunk in chunks]
        2. Predict scores via cross-encoder
        3. Sort by score descending
        4. Return top_k with rerank_score populated
        """
        pairs = [(query, chunk.text) for chunk in chunks]
        scores = self.model.predict(pairs)

        for chunk, score in zip(chunks, scores):
            chunk.rerank_score = float(score)

        ranked = sorted(chunks, key=lambda c: c.rerank_score or 0, reverse=True)
        return ranked[:top_k]
```

### backend/retrieval/score_normalizer.py

```python
from typing import List
from backend.agent.schemas import RetrievedChunk


def normalize_scores(chunks: List[RetrievedChunk]) -> List[RetrievedChunk]:
    """Per-collection min-max normalization of dense_score.

    Groups chunks by collection, applies min-max normalization within each group,
    then returns all chunks with normalized scores.
    """
    ...
```

### backend/storage/parent_store.py

```python
from typing import List
from backend.agent.schemas import ParentChunk


class ParentStore:
    """Read parent chunks from SQLite parent_chunks table."""

    def __init__(self, db):
        self.db = db

    async def get_by_ids(self, parent_ids: List[str]) -> List[ParentChunk]:
        """Fetch parent chunks by ID list.

        Args:
            parent_ids: List of parent chunk UUIDs.

        Returns:
            List of ParentChunk objects. Missing IDs are silently skipped.
        """
        ...
```

## Configuration

Relevant settings from `backend/config.py`:
- `max_iterations: int = 10` -- Orchestrator loop limit
- `max_tool_calls: int = 8` -- Total tool call limit
- `confidence_threshold: float = 0.6` -- MetaReasoningGraph trigger
- `hybrid_dense_weight: float = 0.7` -- Dense vector weight in hybrid search
- `hybrid_sparse_weight: float = 0.3` -- BM25 weight in hybrid search
- `top_k_retrieval: int = 20` -- Initial retrieval count
- `top_k_rerank: int = 5` -- Post-reranking count
- `reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"` -- Cross-encoder model

## Error Handling

| Component | Error | Recovery |
|-----------|-------|----------|
| `orchestrator` | `LLMCallError` | Route to `fallback_response` via edge function |
| `search_child_chunks` | `QdrantConnectionError` | Retry with tenacity (3 attempts, exponential backoff). If all fail, tool returns empty list, orchestrator continues. |
| `search_child_chunks` | `EmbeddingError` | Retry once. If fails, tool returns empty list. |
| `retrieve_parent_chunks` | `SQLiteError` | Return empty list, log warning. |
| `cross_encoder_rerank` | `RerankerError` | Return chunks unsorted, log warning. |
| `compress_context` | `LLMCallError` | Skip compression, continue with uncompressed chunks, log warning. |
| `semantic_search_all_collections` | Partial collection failure | Return results from successful collections only. |

## Testing Requirements

### Unit Tests
- `test_orchestrator_binds_tools`: Verify LLM receives all six tools
- `test_orchestrator_increments_iteration`: Verify iteration_count increments each loop
- `test_deduplication`: Given duplicate (query, parent_id) pairs, verify only first is kept
- `test_loop_terminates_on_max_iterations`: Verify loop stops at iteration 10
- `test_loop_terminates_on_max_tool_calls`: Verify loop stops at 8 tool calls
- `test_loop_terminates_on_confidence`: Verify loop stops when confidence >= 0.6
- `test_loop_terminates_on_tool_exhaustion`: Verify loop stops when no new tool calls
- `test_context_compression_triggers`: Verify compression activates when token count exceeds threshold
- `test_fallback_response_content`: Verify graceful messaging without hallucination
- `test_collect_answer_builds_citations`: Verify Citation objects are correctly constructed

### Integration Tests
- `test_research_graph_with_mock_qdrant`: Full loop with mocked Qdrant returning predefined chunks
- `test_research_graph_meta_reasoning_trigger`: Verify routing to MetaReasoningGraph on low confidence

## Done Criteria

- [ ] `backend/agent/research_graph.py` defines and compiles a valid LangGraph StateGraph
- [ ] All six tools defined in `backend/agent/tools.py` with correct signatures and docstrings
- [ ] `orchestrator` node binds tools to LLM and parses tool calls
- [ ] `tools_node` executes tool calls with deduplication
- [ ] Deduplication prevents redundant (query, parent_id) retrievals
- [ ] Loop respects MAX_ITERATIONS (10) and MAX_TOOL_CALLS (8) limits
- [ ] Context compression triggers when approaching model context window
- [ ] `collect_answer` produces SubAnswer with answer, citations, confidence_score
- [ ] `fallback_response` produces graceful non-hallucinated response
- [ ] `backend/retrieval/searcher.py` executes hybrid search against Qdrant
- [ ] `backend/retrieval/reranker.py` performs cross-encoder reranking
- [ ] `backend/storage/parent_store.py` reads parent chunks from SQLite
- [ ] MetaReasoningGraph trigger edge routes correctly on low confidence
- [ ] All error recovery paths work as specified
- [ ] Unit tests pass for orchestrator loop control
- [ ] Integration test with mocked Qdrant completes successfully
