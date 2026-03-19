# Spec 03: ResearchGraph -- Implementation Context

## Implementation Scope

### Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/agent/research_graph.py` | Create | StateGraph definition + `build_research_graph()` |
| `backend/agent/research_nodes.py` | Create | 6 ResearchGraph node functions |
| `backend/agent/research_edges.py` | Create | 2 ResearchGraph edge functions |
| `backend/agent/tools.py` | Create | Closure-based tool factory via `create_research_tools()` |
| `backend/retrieval/__init__.py` | Create | Package marker |
| `backend/retrieval/searcher.py` | Create | `HybridSearcher` -- Qdrant hybrid dense+BM25 search |
| `backend/retrieval/reranker.py` | Create | `Reranker` -- CrossEncoder reranking |
| `backend/retrieval/score_normalizer.py` | Create | Per-collection min-max score normalization |
| `backend/storage/parent_store.py` | Create | `ParentStore` -- parent chunk reads from SQLite |
| `backend/agent/prompts.py` | Modify | Add `ORCHESTRATOR_SYSTEM`, `ORCHESTRATOR_USER`, `COMPRESS_CONTEXT_SYSTEM`, `COLLECT_ANSWER_SYSTEM` |
| `backend/agent/confidence.py` | Modify | Replace Phase 1 placeholder with 5-signal formula returning float 0.0-1.0 |
| `backend/config.py` | Modify | Add `compression_threshold: float = 0.75` |
| `backend/agent/conversation_graph.py` | Modify | Accept and wire real research graph |
| `backend/main.py` | Modify | Init HybridSearcher, Reranker, ParentStore, build graphs in lifespan |
| `tests/mocks.py` | Modify | Keep `build_mock_research_graph()` working alongside real graph |

**Files that exist and are NOT modified** (use as-is):
- `backend/agent/state.py` -- `ResearchState` TypedDict already defined (lines 33-46)
- `backend/agent/schemas.py` -- `RetrievedChunk`, `ParentChunk`, `Citation`, `SubAnswer` already defined
- `backend/agent/nodes.py` -- `get_context_budget()`, `MODEL_CONTEXT_WINDOWS` (used by research nodes)
- `backend/agent/edges.py` -- `route_fan_out()` spawns ResearchGraph via `Send()`
- `backend/errors.py` -- `QdrantConnectionError`, `LLMCallError`, `EmbeddingError`, `RerankerError`, `SQLiteError`

---

## Code Specifications

### backend/agent/research_graph.py

```python
"""ResearchGraph -- Layer 2 of the three-layer LangGraph agent.

Per-sub-question worker spawned via Send("research", payload) from
ConversationGraph's route_fan_out() edge. Runs an LLM-driven orchestrator
loop: orchestrator -> tools -> compress check -> (compress | orchestrator).
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.agent.research_edges import route_after_compress_check, should_continue_loop
from backend.agent.research_nodes import (
    collect_answer,
    compress_context,
    fallback_response,
    orchestrator,
    should_compress_context,
    tools_node,
)
from backend.agent.state import ResearchState


def build_research_graph(
    tools: list,
    meta_reasoning_graph: Any = None,
) -> Any:
    """Build and compile the ResearchGraph.

    Args:
        tools: List of LangChain tool objects returned by create_research_tools().
        meta_reasoning_graph: Optional compiled MetaReasoningGraph.
            If None, budget exhaustion routes to fallback_response.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(ResearchState)

    # Bind tools into node closures via functools.partial or config
    graph.add_node("orchestrator", orchestrator)
    graph.add_node("tools", tools_node)
    graph.add_node("should_compress_context", should_compress_context)
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

**CRITICAL**: Tools use closure-based dependency injection (R6). The factory
function `create_research_tools()` receives infrastructure objects and returns
tool instances that close over them. Tools are NOT defined at module level.

```python
"""LangChain tool definitions for ResearchGraph.

Tools are created via create_research_tools() factory which closes over
infrastructure dependencies (HybridSearcher, Reranker, ParentStore).
This avoids module-level singletons and supports testing with mocks.
"""
from __future__ import annotations

from langchain_core.tools import tool

from backend.agent.schemas import ParentChunk, RetrievedChunk
from backend.retrieval.reranker import Reranker
from backend.retrieval.score_normalizer import normalize_scores
from backend.retrieval.searcher import HybridSearcher
from backend.storage.parent_store import ParentStore


def create_research_tools(
    searcher: HybridSearcher,
    reranker: Reranker,
    parent_store: ParentStore,
) -> list:
    """Factory that creates tool instances with injected dependencies.

    Args:
        searcher: HybridSearcher for Qdrant queries.
        reranker: CrossEncoder reranker.
        parent_store: SQLite parent chunk reader.

    Returns:
        List of 6 LangChain tool objects ready for llm.bind_tools().
    """

    @tool
    async def search_child_chunks(
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Hybrid dense+BM25 search in Qdrant on child chunk collection,
        followed by cross-encoder reranking.

        Args:
            query: The search query text.
            collection: Name of the Qdrant collection to search.
            top_k: Number of results to return after reranking.
            filters: Optional Qdrant payload filters.

        Returns:
            List of RetrievedChunk objects sorted by rerank score descending.
        """
        # 1. Hybrid search via searcher (includes circuit breaker)
        raw_chunks = await searcher.search(query, collection, top_k=top_k, filters=filters)
        # 2. Rerank via cross-encoder
        if raw_chunks:
            raw_chunks = reranker.rerank(query, raw_chunks, top_k=top_k)
        return raw_chunks

    @tool
    async def retrieve_parent_chunks(
        parent_ids: list[str],
    ) -> list[ParentChunk]:
        """Fetch parent chunks from SQLite by parent_id list.
        Parent chunks contain the full surrounding context for child chunks.

        Args:
            parent_ids: List of parent chunk IDs to retrieve.

        Returns:
            List of ParentChunk objects. Missing IDs are silently skipped.
        """
        return await parent_store.get_by_ids(parent_ids)

    @tool
    async def cross_encoder_rerank(
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score (query, chunk) pairs with cross-encoder and return top-k ranked.

        Args:
            query: The search query text.
            chunks: List of chunks to rerank.
            top_k: Number of top results to return.

        Returns:
            List of RetrievedChunk objects sorted by cross-encoder score descending.
        """
        return reranker.rerank(query, chunks, top_k=top_k)

    @tool
    async def filter_by_collection(
        collection_name: str,
    ) -> dict:
        """Constrain subsequent searches to a specific named collection.

        Args:
            collection_name: The collection to constrain to.

        Returns:
            Confirmation dict with the active collection filter.
        """
        return {"active_collection_filter": collection_name}

    @tool
    async def filter_by_metadata(
        filters: dict,
    ) -> dict:
        """Apply Qdrant payload filter to narrow search results.
        Supported filter keys: doc_type, page_range, source_file, breadcrumb.

        Args:
            filters: Dictionary of payload filter conditions.

        Returns:
            Confirmation dict with the active metadata filters.
        """
        return {"active_metadata_filters": filters}

    @tool
    async def semantic_search_all_collections(
        query: str,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all enabled collections simultaneously.
        Results are normalized per-collection (min-max) before merging.

        Args:
            query: The search query text.
            top_k: Number of results to return after merge.

        Returns:
            List of RetrievedChunk objects merged from all collections.
        """
        # searcher.search_all_collections handles multi-collection fan-out
        raw_chunks = await searcher.search_all_collections(query, top_k=top_k)
        # Per-collection score normalization
        normalized = normalize_scores(raw_chunks)
        # Final rerank across merged results
        if normalized:
            normalized = reranker.rerank(query, normalized, top_k=top_k)
        return normalized

    return [
        search_child_chunks,
        retrieve_parent_chunks,
        cross_encoder_rerank,
        filter_by_collection,
        filter_by_metadata,
        semantic_search_all_collections,
    ]
```

### backend/agent/research_nodes.py

```python
"""Node functions for the ResearchGraph (Layer 2).

All node functions are async, stateless, and pure. Dependencies (LLM, tools)
are resolved from RunnableConfig at invocation time.
"""
from __future__ import annotations

from typing import Any

import structlog
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.messages.utils import count_tokens_approximately

from backend.agent.confidence import compute_confidence
from backend.agent.nodes import get_context_budget
from backend.agent.prompts import (
    COLLECT_ANSWER_SYSTEM,
    COMPRESS_CONTEXT_SYSTEM,
    ORCHESTRATOR_SYSTEM,
    ORCHESTRATOR_USER,
)
from backend.agent.schemas import Citation, RetrievedChunk
from backend.agent.state import ResearchState
from backend.config import settings
from backend.errors import LLMCallError

logger = structlog.get_logger(__name__)


def normalize_query(query: str) -> str:
    """Normalize query string for deduplication keys."""
    return " ".join(query.lower().strip().split())


def dedup_key(query: str, parent_id: str) -> str:
    """Build deduplication key from normalized query + parent_id."""
    return f"{normalize_query(query)}:{parent_id}"


async def orchestrator(state: ResearchState, config: Any = None) -> dict:
    """Decide which tools to call based on current context.

    Binds all available tools to the LLM and invokes with the orchestrator
    prompt. Parses tool calls from the AIMessage response. Increments
    iteration_count. If the LLM returns zero tool calls, sets _no_new_tools
    flag so should_continue_loop detects tool exhaustion (F4).

    Reads: sub_question, retrieved_chunks, tool_call_count, iteration_count
    Writes: iteration_count, messages (with AIMessage containing tool_calls),
            _no_new_tools flag

    The LLM and tools list are resolved from RunnableConfig (injected by
    the graph at compile/invoke time).
    """
    log = logger.bind(
        session_id=state["session_id"],
        sub_question=state["sub_question"],
        iteration=state["iteration_count"],
    )
    log.info(
        "orchestrator_start",
        tool_call_count=state["tool_call_count"],
        chunk_count=len(state["retrieved_chunks"]),
    )

    # --- Resolve LLM + tools from config ---
    # llm = config["configurable"]["llm"]
    # tools_list = config["configurable"]["tools"]
    # llm_with_tools = llm.bind_tools(tools_list)

    # --- Build prompt ---
    chunk_summaries = "\n".join(
        f"- [{c.collection}] {c.text[:120]}..." for c in state["retrieved_chunks"][:10]
    ) or "(none yet)"

    system_msg = SystemMessage(content=ORCHESTRATOR_SYSTEM.format(
        tool_descriptions="(auto-populated by bind_tools)",
        chunk_count=len(state["retrieved_chunks"]),
        chunk_summaries=chunk_summaries,
        iteration=state["iteration_count"] + 1,
        max_iterations=settings.max_iterations,
        tool_call_count=state["tool_call_count"],
        max_tool_calls=settings.max_tool_calls,
    ))

    user_msg = HumanMessage(content=ORCHESTRATOR_USER.format(
        sub_question=state["sub_question"],
        collections=", ".join(state["selected_collections"]),
        confidence_score=f"{state['confidence_score']:.2f}",
    ))

    # --- Invoke LLM with tools bound (R1) ---
    # response = await llm_with_tools.ainvoke([system_msg, user_msg])
    # tool_calls = response.tool_calls  # list[dict] from AIMessage

    # --- Detect tool exhaustion (F4) ---
    # no_new_tools = len(tool_calls) == 0

    # log.info(
    #     "orchestrator_decision",
    #     num_tool_calls=len(tool_calls),
    #     no_new_tools=no_new_tools,
    # )

    # return {
    #     "iteration_count": state["iteration_count"] + 1,
    #     "messages": [response],  # AIMessage with tool_calls
    #     "_no_new_tools": no_new_tools,
    # }
    ...


async def tools_node(state: ResearchState, config: Any = None) -> dict:
    """Execute pending tool calls from orchestrator with retry-once (FR-016).

    For each tool call from the orchestrator's AIMessage:
    1. Look up the tool function by name
    2. Execute with retry-once: try -> except -> count+1 -> retry -> count+1
       Both the original attempt and the retry count against the budget (R7)
    3. Deduplicate results against retrieval_keys
    4. Merge new chunks into retrieved_chunks
    5. Increment tool_call_count per execution (including retries)

    Deduplication key: f"{normalize_query(query)}:{parent_id}"

    Reads: messages (last AIMessage with tool_calls), retrieval_keys,
           retrieved_chunks, tool_call_count
    Writes: retrieved_chunks, retrieval_keys, tool_call_count
    """
    log = logger.bind(session_id=state["session_id"])

    # --- Resolve tools from config ---
    # tools_by_name = {t.name: t for t in config["configurable"]["tools"]}
    # last_ai_message = state["messages"][-1]  # AIMessage with tool_calls
    # tool_calls = last_ai_message.tool_calls

    new_chunks: list[RetrievedChunk] = []
    updated_keys = set(state["retrieval_keys"])
    tool_call_count = state["tool_call_count"]
    tool_messages: list[ToolMessage] = []

    # for tc in tool_calls:
    #     tool_name = tc["name"]
    #     tool_args = tc["args"]
    #     tool_fn = tools_by_name.get(tool_name)
    #
    #     if not tool_fn:
    #         log.warning("unknown_tool", tool=tool_name)
    #         continue
    #
    #     # --- Retry-once pattern (R7, FR-016) ---
    #     tool_call_count += 1  # original attempt counts
    #     result = None
    #     try:
    #         result = await tool_fn.ainvoke(tool_args)
    #     except Exception as first_err:
    #         log.warning("tool_call_failed", tool=tool_name, error=str(first_err))
    #         tool_call_count += 1  # retry also counts against budget
    #         try:
    #             result = await tool_fn.ainvoke(tool_args)
    #         except Exception as retry_err:
    #             log.warning("tool_call_failed_after_retry",
    #                         tool=tool_name, error=str(retry_err))
    #             tool_messages.append(ToolMessage(
    #                 content=f"Tool {tool_name} failed: {retry_err}",
    #                 tool_call_id=tc["id"],
    #             ))
    #             continue
    #
    #     # --- Deduplication ---
    #     if isinstance(result, list):
    #         for chunk in result:
    #             if isinstance(chunk, RetrievedChunk):
    #                 key = dedup_key(
    #                     tool_args.get("query", state["sub_question"]),
    #                     chunk.parent_id,
    #                 )
    #                 if key not in updated_keys:
    #                     updated_keys.add(key)
    #                     new_chunks.append(chunk)
    #
    #     tool_messages.append(ToolMessage(
    #         content=str(result),
    #         tool_call_id=tc["id"],
    #     ))
    #
    #     log.info("tool_call_complete", tool=tool_name,
    #              new_chunks=len(new_chunks), tool_call_count=tool_call_count)

    return {
        "retrieved_chunks": state["retrieved_chunks"] + new_chunks,
        "retrieval_keys": updated_keys,
        "tool_call_count": tool_call_count,
        # "messages": tool_messages,
    }


async def should_compress_context(state: ResearchState) -> dict:
    """Check token count against model context window.

    Uses count_tokens_approximately from langchain_core (R3 -- NOT tiktoken).
    Sets _needs_compression flag in state for route_after_compress_check
    edge to read (F3). This node does NOT do routing itself.

    Reads: retrieved_chunks, llm_model
    Writes: _needs_compression (bool flag for edge function)
    """
    log = logger.bind(session_id=state["session_id"])

    # Build messages from chunk texts for token counting
    chunk_texts = [HumanMessage(content=c.text) for c in state["retrieved_chunks"]]
    token_count = count_tokens_approximately(chunk_texts) if chunk_texts else 0
    budget = get_context_budget(state["llm_model"])
    compression_threshold = int(budget * settings.compression_threshold)

    needs_compression = token_count > compression_threshold

    log.info(
        "compress_check",
        token_count=token_count,
        budget=budget,
        threshold=compression_threshold,
        needs_compression=needs_compression,
    )

    return {"_needs_compression": needs_compression}


async def compress_context(state: ResearchState, config: Any = None) -> dict:
    """Summarize retrieved chunks when context window is approached.

    Concatenates all chunk texts, summarizes via LLM call, replaces
    retrieved_chunks with compressed versions. Preserves citation
    references (FR-011).

    On LLM failure: skip compression, continue with uncompressed chunks.

    Reads: retrieved_chunks, llm_model
    Writes: retrieved_chunks (compressed), context_compressed = True
    """
    log = logger.bind(session_id=state["session_id"])
    log.info("compress_context_start", chunk_count=len(state["retrieved_chunks"]))

    # --- Resolve LLM from config ---
    # llm = config["configurable"]["llm"]

    # chunks_text = "\n\n---\n\n".join(
    #     f"[{c.collection} | {c.source_file}] {c.text}"
    #     for c in state["retrieved_chunks"]
    # )

    # try:
    #     response = await llm.ainvoke([
    #         SystemMessage(content=COMPRESS_CONTEXT_SYSTEM),
    #         HumanMessage(content=f"Compress the following retrieved context:\n\n{chunks_text}"),
    #     ])
    #     # Build a single compressed RetrievedChunk
    #     # ... (implementation creates compressed chunk list)
    #     log.info("compress_context_done")
    #     return {"retrieved_chunks": compressed_chunks, "context_compressed": True}
    # except Exception as exc:
    #     log.warning("compress_context_failed", error=str(exc))
    #     return {}  # Skip compression on failure
    ...


async def collect_answer(state: ResearchState, config: Any = None) -> dict:
    """Generate answer from retrieved chunks, compute confidence, build citations.

    1. Build prompt with sub_question + retrieved chunks
    2. LLM generates answer with inline references
    3. Build Citation objects mapping references to chunks
    4. Compute confidence_score from retrieval signals via compute_confidence()
       -- 5-signal formula (R8), NOT LLM self-assessment

    CONFIDENCE SCALE: state["confidence_score"] is float 0.0-1.0.
    SubAnswer.confidence_score is int 0-100. Conversion: int(score * 100).

    Reads: sub_question, retrieved_chunks
    Writes: answer, citations, confidence_score (float 0.0-1.0)
    """
    log = logger.bind(session_id=state["session_id"])

    # --- Compute confidence from retrieval signals (R8) ---
    confidence = compute_confidence(state["retrieved_chunks"])

    log.info(
        "collect_answer",
        chunk_count=len(state["retrieved_chunks"]),
        confidence_score=confidence,
        sub_question=state["sub_question"],
    )

    # --- Resolve LLM from config, generate answer ---
    # llm = config["configurable"]["llm"]
    # response = await llm.ainvoke([
    #     SystemMessage(content=COLLECT_ANSWER_SYSTEM),
    #     HumanMessage(content=...),
    # ])
    # answer_text = response.content
    # citations = _build_citations(state["retrieved_chunks"], answer_text)

    return {
        "confidence_score": confidence,
        # "answer": answer_text,
        # "citations": citations,
    }


async def fallback_response(state: ResearchState) -> dict:
    """Generate graceful insufficient-information response.

    Does NOT hallucinate. States what was searched, what was found (if anything),
    and why results were insufficient.

    Reads: sub_question, retrieved_chunks
    Writes: answer, confidence_score (0.0)
    """
    log = logger.bind(session_id=state["session_id"])

    chunk_count = len(state["retrieved_chunks"])
    collections_searched = list({c.collection for c in state["retrieved_chunks"]})

    if chunk_count > 0:
        answer = (
            f"I searched {len(collections_searched)} collection(s) and found "
            f"{chunk_count} passage(s), but none were sufficiently relevant to "
            f"answer: \"{state['sub_question']}\". The documents may not cover "
            f"this specific topic in enough detail."
        )
    else:
        answer = (
            f"I could not find any relevant information to answer: "
            f"\"{state['sub_question']}\". The indexed documents may not "
            f"cover this topic."
        )

    log.info("fallback_response", chunk_count=chunk_count,
             collections_searched=collections_searched)

    return {
        "answer": answer,
        "citations": [],
        "confidence_score": 0.0,
    }
```

### backend/agent/research_edges.py

```python
"""Edge functions (routing logic) for the ResearchGraph.

Edge functions determine which node to execute next based on the current state.
These are separate from edges.py which contains ConversationGraph edges.
"""
from __future__ import annotations

import structlog

from backend.agent.state import ResearchState
from backend.config import settings

logger = structlog.get_logger(__name__)


def should_continue_loop(state: ResearchState) -> str:
    """Determine whether the orchestrator loop should continue.

    IMPORTANT (F1): Confidence is checked FIRST. If confidence >= threshold,
    route to collect_answer regardless of remaining budget. Then check budget
    exhaustion, then tool exhaustion.

    CONFIDENCE SCALE MISMATCH: config.confidence_threshold is int 0-100,
    but state["confidence_score"] is float 0.0-1.0. Convert threshold
    by dividing by 100.

    Returns:
        "sufficient": confidence >= threshold -> collect_answer
        "exhausted": budget or tools exhausted -> meta_reasoning or fallback
        "continue": keep looping
    """
    confidence = state["confidence_score"]
    threshold = settings.confidence_threshold / 100  # int 60 -> float 0.6

    # 1. Confidence check FIRST (F1)
    if confidence >= threshold:
        logger.info(
            "loop_exit_sufficient",
            confidence=confidence,
            threshold=threshold,
            session_id=state["session_id"],
        )
        return "sufficient"

    # 2. Budget exhaustion
    if (state["iteration_count"] >= settings.max_iterations or
            state["tool_call_count"] >= settings.max_tool_calls):
        logger.info(
            "loop_exit_exhausted",
            iteration_count=state["iteration_count"],
            tool_call_count=state["tool_call_count"],
            confidence=confidence,
            session_id=state["session_id"],
        )
        return "exhausted"

    # 3. Tool exhaustion -- orchestrator produced no new tool calls (F4)
    if state.get("_no_new_tools", False):
        logger.info(
            "loop_exit_tool_exhaustion",
            confidence=confidence,
            session_id=state["session_id"],
        )
        return "exhausted"

    return "continue"


def route_after_compress_check(state: ResearchState) -> str:
    """Route after context size check.

    Reads the _needs_compression flag set by should_compress_context node (F3).

    Returns:
        "compress": Token count exceeds threshold, compress before continuing
        "continue": Token count within budget, loop back to orchestrator
    """
    if state.get("_needs_compression", False):
        return "compress"
    return "continue"
```

### backend/retrieval/searcher.py

```python
"""Qdrant hybrid dense + BM25 search with circuit breaker protection.

Uses AsyncQdrantClient (R4) with prefetch (dense + sparse) and FusionQuery(Fusion.RRF).
All Qdrant calls are wrapped with the circuit breaker pattern per C1.
"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    FieldCondition,
    Filter,
    FusionQuery,
    MatchValue,
    Prefetch,
    QueryRequest,
    models,
)

from backend.agent.schemas import RetrievedChunk
from backend.config import Settings
from backend.errors import QdrantConnectionError

logger = structlog.get_logger(__name__)


class HybridSearcher:
    """Executes hybrid dense + BM25 search against Qdrant.

    Uses AsyncQdrantClient (R4). All Qdrant call sites are protected
    by the circuit breaker pattern (C1 -- Constitution requirement).
    """

    def __init__(self, client: AsyncQdrantClient, settings: Settings):
        self.client = client
        self.dense_weight = settings.hybrid_dense_weight    # 0.7
        self.sparse_weight = settings.hybrid_sparse_weight  # 0.3
        self.default_top_k = settings.top_k_retrieval       # 20

        # Circuit breaker state (C1)
        self._circuit_open = False
        self._failure_count = 0
        self._max_failures = settings.circuit_breaker_failure_threshold  # 5
        self._cooldown_secs = settings.circuit_breaker_cooldown_secs     # 30

    async def _check_circuit(self) -> None:
        """Check circuit breaker state. Raises if circuit is open."""
        if self._circuit_open:
            logger.warning("circuit_breaker_open", failure_count=self._failure_count)
            raise QdrantConnectionError("Circuit breaker is open -- Qdrant unavailable")

    def _record_success(self) -> None:
        """Reset circuit breaker on success."""
        self._failure_count = 0
        self._circuit_open = False

    def _record_failure(self) -> None:
        """Increment failure count, open circuit if threshold reached."""
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._circuit_open = True
            logger.error("circuit_breaker_opened", failure_count=self._failure_count)

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Execute hybrid search with circuit breaker (C1).

        1. Check circuit breaker state
        2. Generate dense embedding for query via embed_fn
        3. Execute Qdrant query_points with prefetch (dense + sparse) + Fusion.RRF (R4)
        4. Apply payload filters if provided
        5. Return top_k results as RetrievedChunk objects

        Args:
            query: The search query text.
            collection: Qdrant collection name.
            top_k: Number of results to return.
            filters: Optional payload filters (doc_type, page_range, source_file).
            embed_fn: Callable that returns dense vector for query text.

        Returns:
            List of RetrievedChunk objects.

        Raises:
            QdrantConnectionError: If Qdrant is unreachable or circuit is open.
        """
        await self._check_circuit()
        # Implementation: query_points with prefetch + FusionQuery(Fusion.RRF)
        ...

    async def search_all_collections(
        self,
        query: str,
        top_k: int = 20,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all available collections.

        Queries each collection in parallel, merges results.
        Circuit breaker protects each individual collection query (C1).
        Partial failures return results from successful collections only.

        Args:
            query: The search query text.
            top_k: Number of results per collection.
            embed_fn: Callable that returns dense vector for query text.

        Returns:
            Merged list of RetrievedChunk from all collections.
        """
        await self._check_circuit()
        # Implementation: asyncio.gather per collection, merge results
        ...
```

### backend/retrieval/reranker.py

```python
"""Cross-encoder reranking for retrieved chunks.

Uses model.rank() API (R5) -- NOT model.predict(). The rank() method
returns a list of dicts with corpus_id and score, which avoids manual
pair construction.
"""
from __future__ import annotations

import structlog
from sentence_transformers import CrossEncoder

from backend.agent.schemas import RetrievedChunk
from backend.config import Settings
from backend.errors import RerankerError

logger = structlog.get_logger(__name__)


class Reranker:
    """Cross-encoder reranking for retrieved chunks."""

    def __init__(self, settings: Settings):
        self.model = CrossEncoder(settings.reranker_model)
        self.default_top_k = settings.top_k_rerank  # 5

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score (query, chunk) pairs and return top-k sorted by score.

        Uses model.rank() (R5) which returns:
            [{"corpus_id": int, "score": float}, ...]

        NOT model.predict() -- rank() handles pair construction internally.

        Args:
            query: The search query text.
            chunks: List of chunks to rerank.
            top_k: Number of top results to return.

        Returns:
            List of RetrievedChunk objects sorted by cross-encoder score descending,
            with rerank_score populated.

        Raises:
            RerankerError: If cross-encoder inference fails.
        """
        if not chunks:
            return []

        documents = [c.text for c in chunks]

        try:
            # R5: model.rank() returns [{"corpus_id": int, "score": float}]
            rankings = self.model.rank(
                query, documents, top_k=top_k, return_documents=False
            )
        except Exception as exc:
            logger.warning("reranker_failed", error=str(exc))
            raise RerankerError(f"Cross-encoder reranking failed: {exc}") from exc

        ranked_chunks: list[RetrievedChunk] = []
        for entry in rankings:
            idx = entry["corpus_id"]
            chunk = chunks[idx]
            chunk.rerank_score = float(entry["score"])
            ranked_chunks.append(chunk)

        logger.info("rerank_complete", input_count=len(chunks),
                     output_count=len(ranked_chunks))
        return ranked_chunks
```

### backend/retrieval/score_normalizer.py

```python
"""Per-collection min-max normalization of dense scores.

Used when merging results from multiple Qdrant collections to ensure
scores are comparable across collections.
"""
from __future__ import annotations

from backend.agent.schemas import RetrievedChunk


def normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Per-collection min-max normalization of dense_score.

    Groups chunks by collection, applies min-max normalization within
    each group, then returns all chunks with normalized dense_score values.

    Args:
        chunks: List of RetrievedChunk from potentially multiple collections.

    Returns:
        Same list with dense_score normalized to [0.0, 1.0] per collection.
        Returns input unchanged if empty or single-chunk collections.
    """
    if not chunks:
        return chunks

    # Group by collection
    by_collection: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_collection.setdefault(chunk.collection, []).append(chunk)

    # Normalize within each collection
    for collection, group in by_collection.items():
        scores = [c.dense_score for c in group]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        if score_range > 0:
            for c in group:
                c.dense_score = (c.dense_score - min_score) / score_range

    return chunks
```

### backend/retrieval/__init__.py

```python
"""Retrieval layer: hybrid search, cross-encoder reranking, score normalization."""
```

### backend/storage/parent_store.py

```python
"""Parent chunk reads from SQLite.

Follows existing SQLiteDB patterns from backend/storage/sqlite_db.py.
Uses aiosqlite async connection from the shared DB instance.
"""
from __future__ import annotations

import structlog

from backend.agent.schemas import ParentChunk
from backend.errors import SQLiteError

logger = structlog.get_logger(__name__)


class ParentStore:
    """Read parent chunks from SQLite parent_chunks table."""

    def __init__(self, db):
        """Initialize with the shared SQLiteDB instance.

        Args:
            db: An SQLiteDB instance (backend/storage/sqlite_db.py).
        """
        self.db = db

    async def get_by_ids(self, parent_ids: list[str]) -> list[ParentChunk]:
        """Fetch parent chunks by ID list.

        Args:
            parent_ids: List of parent chunk UUIDs.

        Returns:
            List of ParentChunk objects. Missing IDs are silently skipped.

        Raises:
            SQLiteError: If database read fails.
        """
        if not parent_ids:
            return []

        try:
            placeholders = ",".join("?" for _ in parent_ids)
            cursor = await self.db.db.execute(
                f"SELECT parent_id, text, source_file, page, breadcrumb, collection "
                f"FROM parent_chunks WHERE parent_id IN ({placeholders})",
                parent_ids,
            )
            rows = await cursor.fetchall()

            results = [
                ParentChunk(
                    parent_id=row["parent_id"],
                    text=row["text"],
                    source_file=row["source_file"],
                    page=row["page"],
                    breadcrumb=row["breadcrumb"],
                    collection=row["collection"],
                )
                for row in rows
            ]

            logger.info("parent_chunks_fetched",
                        requested=len(parent_ids), found=len(results))
            return results

        except Exception as exc:
            logger.warning("parent_store_read_failed", error=str(exc))
            raise SQLiteError(f"Failed to fetch parent chunks: {exc}") from exc
```

### backend/agent/prompts.py -- Additions

Append the following 4 constants to the existing file (after `SUMMARIZE_HISTORY_SYSTEM`):

```python
# --- ResearchGraph prompt constants (Spec 03) ---

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

COMPRESS_CONTEXT_SYSTEM = """You are a context compression assistant for a RAG system.
Given a set of retrieved document passages, produce a concise summary that:
1. Preserves all factual claims and their source document references
2. Removes redundant or overlapping information
3. Maintains enough detail that specific claims can still be cited
4. Keeps passage boundaries clear so citations remain valid
5. Does NOT introduce information not present in the original passages

Format: Return a condensed version of the passages, grouped by topic,
with [Source: document_name] markers preserved inline.
"""

COLLECT_ANSWER_SYSTEM = """Generate a precise answer to the sub-question using ONLY the
retrieved passages below. For every claim, cite the source using [Source: document_name].

If the passages do not contain sufficient information, say so clearly rather than
guessing or hallucinating. Include the confidence level in your reasoning.

Passages:
{passages}
"""
```

### backend/agent/confidence.py -- Replacement

```python
"""Confidence scoring for retrieval results.

Replaces Phase 1 placeholder with 5-signal formula (R8).
Returns float 0.0-1.0 (NOT int 0-100). Conversion to int is done
in collect_answer: int(score * 100).

5-signal formula:
  score = mean_rerank(0.4) + chunk_count(0.2) + top_score(0.2)
        + variance(0.1) + coverage(0.1)

All signals are computed from measurable retrieval data, NOT LLM
self-assessment (FR-009).
"""
from __future__ import annotations

import math

from backend.agent.schemas import RetrievedChunk


def compute_confidence(
    chunks: list[RetrievedChunk],
    top_k: int = 5,
    expected_chunk_count: int = 5,
    num_collections_searched: int = 1,
    num_collections_total: int = 1,
) -> float:
    """Compute confidence score (0.0-1.0) from retrieval signals.

    5-signal weighted formula (R8):
        mean_rerank     * 0.4  -- average rerank score of top-k chunks
        chunk_count     * 0.2  -- ratio of retrieved vs expected chunks
        top_score       * 0.2  -- best single rerank score
        variance        * 0.1  -- inverse of score variance (consistency)
        coverage        * 0.1  -- ratio of collections searched vs total

    Args:
        chunks: Retrieved chunks with rerank_score populated.
        top_k: Number of top chunks to consider for scoring.
        expected_chunk_count: Expected number of useful chunks (for ratio).
        num_collections_searched: Collections actually searched.
        num_collections_total: Total available collections.

    Returns:
        Float confidence score in range [0.0, 1.0].
        Returns 0.0 if no chunks provided.
    """
    if not chunks:
        return 0.0

    # Use top-k chunks by rerank score
    scored = [c for c in chunks if c.rerank_score is not None]
    if not scored:
        # Fall back to dense_score if no rerank scores
        scores = sorted([c.dense_score for c in chunks], reverse=True)[:top_k]
    else:
        scored.sort(key=lambda c: c.rerank_score, reverse=True)
        scores = [c.rerank_score for c in scored[:top_k]]

    if not scores:
        return 0.0

    # Signal 1: Mean rerank score (weight 0.4)
    mean_rerank = sum(scores) / len(scores)
    # Clamp to [0, 1]
    mean_rerank = max(0.0, min(1.0, mean_rerank))

    # Signal 2: Chunk count ratio (weight 0.2)
    chunk_ratio = min(1.0, len(chunks) / max(1, expected_chunk_count))

    # Signal 3: Top score (weight 0.2)
    top_score = max(0.0, min(1.0, scores[0]))

    # Signal 4: Inverse variance -- consistency (weight 0.1)
    if len(scores) > 1:
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        # Low variance = high consistency = higher confidence
        inverse_variance = 1.0 / (1.0 + math.sqrt(variance))
    else:
        inverse_variance = 1.0

    # Signal 5: Collection coverage (weight 0.1)
    coverage = min(1.0, num_collections_searched / max(1, num_collections_total))

    # Weighted sum
    confidence = (
        mean_rerank * 0.4
        + chunk_ratio * 0.2
        + top_score * 0.2
        + inverse_variance * 0.1
        + coverage * 0.1
    )

    return max(0.0, min(1.0, confidence))
```

### backend/config.py -- Addition

Add the following field to the `Settings` class under the `# Agent` section:

```python
    # Agent
    max_iterations: int = 10
    max_tool_calls: int = 8
    confidence_threshold: int = 60  # 0-100 scale
    meta_reasoning_max_attempts: int = 2
    compression_threshold: float = 0.75  # NEW: fraction of context budget that triggers compression
```

### backend/main.py -- Lifespan Modifications

The lifespan function needs to initialize infrastructure objects and build the
graph chain. Add after the checkpointer setup block:

```python
    # --- Spec 03: ResearchGraph infrastructure ---
    from backend.retrieval.searcher import HybridSearcher
    from backend.retrieval.reranker import Reranker
    from backend.storage.parent_store import ParentStore
    from backend.agent.tools import create_research_tools
    from backend.agent.research_graph import build_research_graph
    from backend.agent.conversation_graph import build_conversation_graph

    hybrid_searcher = HybridSearcher(qdrant.client, settings)
    app.state.hybrid_searcher = hybrid_searcher
    logger.info("hybrid_searcher_initialized")

    reranker_instance = Reranker(settings)
    app.state.reranker = reranker_instance
    logger.info("reranker_initialized", model=settings.reranker_model)

    parent_store = ParentStore(db)
    app.state.parent_store = parent_store
    logger.info("parent_store_initialized")

    # Build tool list via closure-based factory (R6)
    research_tools = create_research_tools(hybrid_searcher, reranker_instance, parent_store)
    app.state.research_tools = research_tools
    logger.info("research_tools_created", count=len(research_tools))

    # Build graph chain: ResearchGraph -> ConversationGraph
    research_graph = build_research_graph(tools=research_tools)
    conversation_graph = build_conversation_graph(
        research_graph=research_graph,
        checkpointer=checkpointer,
    )
    app.state.conversation_graph = conversation_graph
    logger.info("graphs_compiled")
```

---

## Configuration

### New Setting

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `compression_threshold` | `float` | `0.75` | Fraction of context budget that triggers chunk compression |

### Existing Settings Used (no changes)

| Setting | Type | Value | Used By |
|---------|------|-------|---------|
| `confidence_threshold` | `int` | `60` | `should_continue_loop` (divided by 100 for comparison) |
| `max_iterations` | `int` | `10` | `should_continue_loop` |
| `max_tool_calls` | `int` | `8` | `should_continue_loop`, `tools_node` |
| `top_k_retrieval` | `int` | `20` | `HybridSearcher` |
| `top_k_rerank` | `int` | `5` | `Reranker` |
| `reranker_model` | `str` | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `Reranker` |
| `hybrid_dense_weight` | `float` | `0.7` | `HybridSearcher` |
| `hybrid_sparse_weight` | `float` | `0.3` | `HybridSearcher` |
| `circuit_breaker_failure_threshold` | `int` | `5` | `HybridSearcher` |
| `circuit_breaker_cooldown_secs` | `int` | `30` | `HybridSearcher` |
| `retry_max_attempts` | `int` | `3` | General retry config |
| `retry_backoff_initial_secs` | `float` | `1.0` | General retry config |

### Confidence Scale Mismatch

`config.confidence_threshold` = `60` (int, 0-100 scale).
`state["confidence_score"]` = float (0.0-1.0 scale).
Edge function must convert: `state["confidence_score"] >= settings.confidence_threshold / 100`.

---

## Error Handling

| Component | Error | Recovery | Budget Impact |
|-----------|-------|----------|---------------|
| `orchestrator` | `LLMCallError` | Route to `fallback_response` via edge function | N/A |
| `tools_node` (any tool) | Any exception | Retry once (FR-016). Original + retry both count against `max_tool_calls` (R7) | +2 tool calls |
| `search_child_chunks` | `QdrantConnectionError` | Circuit breaker trips after 5 failures (C1). Tool returns empty list. | +1 or +2 |
| `search_child_chunks` | `EmbeddingError` | Retry once. If fails, tool returns empty list. | +1 or +2 |
| `retrieve_parent_chunks` | `SQLiteError` | Return empty list, log warning. | +1 |
| `cross_encoder_rerank` | `RerankerError` | Return chunks unsorted, log warning. | +1 |
| `compress_context` | `LLMCallError` | Skip compression, continue with uncompressed chunks. | N/A |
| `semantic_search_all_collections` | Partial collection failure | Return results from successful collections only. | +1 |
| `HybridSearcher` (any method) | Circuit breaker open | Raise `QdrantConnectionError` immediately. | N/A |

### Retry-Once Pattern (FR-016, R7)

```
try:
    result = await tool_fn(...)      # attempt 1: tool_call_count += 1
except Exception:
    result = await tool_fn(...)      # attempt 2: tool_call_count += 1
    # If attempt 2 also fails: log, return ToolMessage with error, continue
```

Both attempts count against the `max_tool_calls` budget.

---

## Subagent Team Design

### Wave Structure

```
Wave 1: agent-scaffold       (create files, stubs, imports)
Wave 2: agent-retrieval      (HybridSearcher, Reranker, ScoreNormalizer)
         agent-tools          (tool factory + 6 tool definitions)
         agent-nodes          (6 nodes + 2 edges + confidence + prompts)
Wave 3: agent-integration    (wire graph, update main.py, conversation_graph.py)
Wave 4: agent-unit-tests     (unit tests for retrieval, tools, nodes, edges)
         agent-integration-tests  (full graph execution flow tests)
Wave 5: agent-polish         (fix failures, verify FR-016/017, update CLAUDE.md)
```

### Agent Mappings

| Agent | subagent_type | Model | Wave | Instruction File | Tasks |
|-------|---------------|-------|------|------------------|-------|
| agent-scaffold | python-expert | Opus 4.6 | 1 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-scaffold.md` | T001-T012 |
| agent-retrieval | python-expert | Opus 4.6 | 2 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-retrieval.md` | T013-T016 |
| agent-tools | python-expert | Sonnet 4.6 | 2 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-tools.md` | T018, T027-T030 |
| agent-nodes | python-expert | Sonnet 4.6 | 2 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-nodes.md` | T019-T022, T032, T034-T036, T040-T041 |
| agent-integration | backend-architect | Opus 4.6 | 3 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-integration.md` | T023-T026, T033, T037-T039, T042-T043 |
| agent-unit-tests | quality-engineer | Sonnet 4.6 | 4 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-unit-tests.md` | T044-T048 |
| agent-integration-tests | quality-engineer | Opus 4.6 | 4 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-integration-tests.md` | T049-T050 |
| agent-polish | self-review | Opus 4.6 | 5 | `Docs/PROMPTS/spec-03-research-graph/agents/agent-polish.md` | T051-T057 |

### Orchestrator Execution Protocol

**Prerequisites**: You MUST be running inside a tmux session. Claude Code Agent Teams auto-detects tmux and assigns each spawned agent its own pane for parallel visibility.

**Spawn prompt template** — Use this EXACT pattern for every agent:

```
Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/<agent-name>.md FIRST, then execute all assigned tasks.
```

Do NOT inline spec content, code snippets, or task descriptions in the spawn prompt. The instruction file is the single source of truth — the agent reads it and pulls what it needs from the authoritative files listed in its "Context Files" section.

**Wave execution sequence**:

```
WAVE 1 — Sequential (1 agent)
├── Spawn agent-scaffold (python-expert, opus)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-scaffold.md FIRST, then execute all assigned tasks."
├── CHECKPOINT: Verify all new modules are importable
│   Run: python -c "from backend.agent.research_graph import build_research_graph; from backend.retrieval.searcher import HybridSearcher"
│   If FAIL → fix before proceeding
│
WAVE 2 — Parallel (3 agents, separate tmux panes)
├── Spawn agent-retrieval (python-expert, opus)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-retrieval.md FIRST, then execute all assigned tasks."
├── Spawn agent-tools (python-expert, sonnet)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-tools.md FIRST, then execute all assigned tasks."
├── Spawn agent-nodes (python-expert, sonnet)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-nodes.md FIRST, then execute all assigned tasks."
├── WAIT for all 3 to complete
├── CHECKPOINT: Each module has full implementations
│   Run: python -c "from backend.retrieval.searcher import HybridSearcher; from backend.agent.tools import create_research_tools"
│   If FAIL → fix before proceeding
│
WAVE 3 — Sequential (1 agent)
├── Spawn agent-integration (backend-architect, opus)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-integration.md FIRST, then execute all assigned tasks."
├── CHECKPOINT: build_research_graph() compiles without error
│   Run: python -c "from backend.agent.research_graph import build_research_graph; g = build_research_graph(tools=[])"
│   If FAIL → fix before proceeding
│
WAVE 4 — Parallel (2 agents, separate tmux panes)
├── Spawn agent-unit-tests (quality-engineer, sonnet)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-unit-tests.md FIRST, then execute all assigned tasks."
├── Spawn agent-integration-tests (quality-engineer, opus)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-integration-tests.md FIRST, then execute all assigned tasks."
├── WAIT for both to complete
├── CHECKPOINT: All tests pass
│   Run: zsh scripts/run-tests-external.sh -n spec03-all tests/unit/ tests/integration/test_research_graph.py
│   Poll: cat Docs/Tests/spec03-all.status
│   If FAILED → proceed to Wave 5 (agent-polish fixes failures)
│
WAVE 5 — Sequential (1 agent)
├── Spawn agent-polish (self-review, opus)
│   Prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/agent-polish.md FIRST, then execute all assigned tasks."
├── FINAL CHECKPOINT: All tests green, CLAUDE.md updated
│   Run: zsh scripts/run-tests-external.sh -n spec03-final tests/
│   Poll: cat Docs/Tests/spec03-final.status
```

**CRITICAL rules for the orchestrator**:
- NEVER proceed to the next wave until the current wave's checkpoint passes
- NEVER run pytest directly — always use `zsh scripts/run-tests-external.sh`
- NEVER inline spec content in spawn prompts — agents read their own instruction files
- Parallel agents in the same wave MUST be spawned in a single message (multiple Agent tool calls) to maximize concurrency
- If a checkpoint fails, diagnose and fix BEFORE spawning the next wave
- Each agent's FIRST action is reading its instruction file — this is non-negotiable

---

## Testing

### Test Execution Policy

**NEVER run pytest inside Claude Code.** All test execution uses the external runner:

```bash
zsh scripts/run-tests-external.sh -n <name> <target>
# Output: Docs/Tests/{name}.{status,summary,log}
# Poll: cat Docs/Tests/<name>.status  -> RUNNING|PASSED|FAILED|ERROR
# Read: cat Docs/Tests/<name>.summary  (~20 lines, token-efficient)
```

### Unit Tests (Wave 4)

| Test | Validates |
|------|-----------|
| `test_orchestrator_binds_tools` | LLM receives all 6 tools via `bind_tools()` |
| `test_orchestrator_increments_iteration` | `iteration_count` increments each loop |
| `test_orchestrator_sets_no_new_tools_flag` | `_no_new_tools` flag set when LLM returns 0 tool calls |
| `test_deduplication` | Duplicate `(query, parent_id)` pairs are skipped |
| `test_loop_terminates_on_max_iterations` | Loop stops at iteration 10 |
| `test_loop_terminates_on_max_tool_calls` | Loop stops at 8 tool calls |
| `test_loop_terminates_on_confidence` | Loop stops when `confidence >= 0.6` |
| `test_loop_terminates_on_tool_exhaustion` | Loop stops when `_no_new_tools` is True |
| `test_confidence_first_then_budget` | Confidence checked before budget in `should_continue_loop` (F1) |
| `test_context_compression_triggers` | Compression activates when token count exceeds threshold |
| `test_compress_sets_needs_compression_flag` | `_needs_compression` flag set correctly (F3) |
| `test_fallback_response_content` | Graceful messaging without hallucination |
| `test_collect_answer_builds_citations` | Citation objects correctly constructed |
| `test_retry_once_both_count` | Both original + retry count against budget (R7) |
| `test_confidence_5_signal` | 5-signal formula returns correct float 0.0-1.0 (R8) |
| `test_confidence_scale_conversion` | `confidence_threshold / 100` comparison works |
| `test_reranker_uses_rank_not_predict` | `model.rank()` called, not `model.predict()` (R5) |
| `test_searcher_circuit_breaker` | HybridSearcher circuit breaker opens after 5 failures (C1) |
| `test_score_normalizer` | Per-collection min-max normalization |

### Integration Tests (Wave 4)

| Test | Validates |
|------|-----------|
| `test_research_graph_with_mock_qdrant` | Full loop with mocked Qdrant returning predefined chunks |
| `test_research_graph_meta_reasoning_trigger` | Routing to MetaReasoningGraph on low confidence |

---

## Done Criteria

- [ ] `backend/agent/research_graph.py` defines and compiles a valid LangGraph StateGraph
- [ ] `backend/agent/tools.py` uses closure-based factory `create_research_tools()` (R6)
- [ ] All 6 tools have correct signatures and docstrings
- [ ] `orchestrator` node binds tools to LLM and parses tool calls (R1)
- [ ] `orchestrator` sets `_no_new_tools` flag on zero tool calls (F4)
- [ ] `tools_node` executes tool calls with retry-once logic (FR-016, R7)
- [ ] `tools_node` deduplicates results via `retrieval_keys` set
- [ ] `should_continue_loop` checks confidence FIRST, then budget (F1)
- [ ] `should_continue_loop` converts `confidence_threshold / 100` for comparison
- [ ] `should_compress_context` sets `_needs_compression` flag (F3)
- [ ] `route_after_compress_check` reads `_needs_compression` flag (F3)
- [ ] Context compression triggers at `compression_threshold` (0.75) of context budget
- [ ] Token counting uses `count_tokens_approximately` (R3), NOT tiktoken
- [ ] `collect_answer` produces answer, citations, confidence_score (float 0.0-1.0)
- [ ] `confidence.py` implements 5-signal formula (R8) returning float 0.0-1.0
- [ ] `fallback_response` produces graceful non-hallucinated response
- [ ] `HybridSearcher` uses `AsyncQdrantClient` (R4) with circuit breaker (C1)
- [ ] `Reranker` uses `model.rank()` not `model.predict()` (R5)
- [ ] structlog logging at all decision points (FR-017)
- [ ] `config.py` has `compression_threshold: float = 0.75`
- [ ] `main.py` lifespan initializes HybridSearcher, Reranker, ParentStore, builds graphs
- [ ] MetaReasoningGraph trigger edge routes correctly on low confidence + exhaustion
- [ ] All error recovery paths work as specified
- [ ] Unit tests pass via external runner
- [ ] Integration tests with mocked Qdrant complete successfully
