# Research: ResearchGraph

**Feature**: 003-research-graph | **Date**: 2026-03-11

## Research Questions & Decisions

### R1: LangGraph Tool Binding Pattern

**Question**: How to bind LangChain tools to the orchestrator LLM and execute tool calls in a StateGraph?

**Decision**: Use `llm.bind_tools(tools_list)` to create a tool-aware LLM. The orchestrator node invokes it and inspects `AIMessage.tool_calls` for structured tool call objects. The `tools_node` then dispatches each call.

**Rationale**: This is the standard LangGraph pattern for tool-calling agents. The LLM returns structured `tool_calls` (not raw text parsing), and LangChain provides `ToolMessage` for returning results.

**Pattern**:
```python
from langchain_core.messages import AIMessage, ToolMessage

# In orchestrator node:
llm_with_tools = llm.bind_tools(tools_list)
response: AIMessage = await llm_with_tools.ainvoke([system_msg, user_msg])

# response.tool_calls is a list of dicts:
# [{"name": "search_child_chunks", "args": {"query": "...", "collection": "..."}, "id": "call_abc123"}]

# In tools_node:
for tool_call in response.tool_calls:
    tool_fn = tool_map[tool_call["name"]]
    result = await tool_fn.ainvoke(tool_call["args"])
    # Create ToolMessage for the result
    tool_msg = ToolMessage(content=str(result), tool_call_id=tool_call["id"])
```

**Important details from research**:
- `tool_calls` format is model-provider agnostic — same structure for OpenAI, Anthropic, Ollama
- `ToolMessage` MUST include `tool_call_id` matching the original `tool_call["id"]` — this is how the LLM associates results with requests
- When the LLM does NOT want to call tools, `tool_calls` is empty and `content` has the text answer
- LangGraph ships a prebuilt `ToolNode` class, but the manual approach gives more control over deduplication and retry logic

**Alternatives considered**:
- Manual JSON parsing of LLM output → Fragile, model-dependent
- LangGraph prebuilt `ToolNode` → Less control over deduplication and retry logic

---

### R2: Send() Payload Delivery

**Question**: How does `Send("research", payload)` deliver state to the ResearchGraph?

**Decision**: The `Send()` payload IS the initial state of the target node/subgraph. When the ConversationGraph's `route_fan_out()` returns `[Send("research", payload)]`, each payload becomes the `ResearchState` for a separate ResearchGraph invocation. Multiple `Send()` objects create concurrent executions.

**Rationale**: This is confirmed by the existing `route_fan_out()` implementation in `backend/agent/edges.py:87-101` which constructs a full `ResearchState` TypedDict as the payload.

**Pattern**:
```python
# In edges.py (existing):
sends.append(Send("research", payload))  # payload is ResearchState TypedDict

# In conversation_graph.py (existing):
graph.add_node("research", research_graph)  # compiled ResearchGraph
graph.add_conditional_edges("rewrite_query", route_after_rewrite,
                           ["request_clarification", "research"])
graph.add_edge("research", "aggregate_answers")
```

**Key insight**: The ResearchGraph must be a COMPILED graph (via `.compile()`), passed to `add_node()`. It receives the Send() payload as its state.

---

### R3: Token Counting for Compression

**Question**: How to count tokens for the 75% compression threshold without adding tiktoken?

**Decision**: Use `count_tokens_approximately` from `langchain_core.messages.utils`. This is a lightweight approximation that divides character count by ~4 (roughly 1 token per 4 chars for English). For the compression threshold decision, this approximation is sufficient — we only need to know "are we near 75%?" not exact counts.

**Rationale**: Spec explicitly forbids tiktoken. The existing `get_context_budget()` in `nodes.py` already returns `int(window * 0.75)` which is the threshold we compare against.

**Pattern**:
```python
from langchain_core.messages.utils import count_tokens_approximately
from backend.agent.nodes import get_context_budget

# In should_compress_context:
budget = get_context_budget(state["llm_model"])  # 75% of context window
total_text = " ".join(chunk.text for chunk in state["retrieved_chunks"])
token_count = count_tokens_approximately([HumanMessage(content=total_text)])
needs_compression = token_count >= budget
```

**Full signature from research**:
```python
def count_tokens_approximately(
    messages: Iterable[MessageLikeRepresentation],
    *,
    chars_per_token: float = 4.0,           # ~4 chars/token for English
    extra_tokens_per_message: float = 3.0,  # BOS/EOS overhead
    count_name: bool = True,
    tokens_per_image: int = 85,
    use_usage_metadata_scaling: bool = False,
    tools: list[BaseTool | dict] | None = None,
) -> int
```
Available since `langchain-core >= 0.3.46`.

**Alternatives considered**:
- tiktoken → Explicitly forbidden by spec
- Custom character-based estimation → Reinventing the wheel, langchain_core already has this
- Model-specific tokenizer endpoints → Added latency per check, overkill for threshold decision

---

### R4: Qdrant Hybrid Search Implementation

**Question**: How to execute hybrid dense + BM25 search with qdrant-client >= 1.17.0?

**Decision**: Use Qdrant's `query_points` API with `prefetch` for multi-stage retrieval. Dense and sparse vectors are stored in the same collection using named vectors. The `prefetch` parameter runs both searches, and `fusion` combines results using Reciprocal Rank Fusion (RRF).

**Rationale**: Qdrant >= 1.7 supports native hybrid search with prefetch + fusion, which is more efficient than separate queries + manual merging.

**Pattern**:
```python
from qdrant_client import QdrantClient, models

# Collection must have both dense and sparse named vectors
# (set up during ingestion — spec-06)

# Hybrid search with prefetch + fusion:
results = client.query_points(
    collection_name=collection,
    prefetch=[
        models.Prefetch(
            query=dense_vector,        # from embedding model
            using="dense",             # named vector
            limit=top_k,
        ),
        models.Prefetch(
            query=models.SparseVector(
                indices=sparse_indices,
                values=sparse_values,
            ),
            using="sparse",            # named sparse vector (BM25)
            limit=top_k,
        ),
    ],
    query=models.FusionQuery(
        fusion=models.Fusion.RRF,      # Reciprocal Rank Fusion
    ),
    limit=top_k,
    with_payload=True,
    query_filter=models.Filter(         # optional metadata filter
        must=[
            models.FieldCondition(
                key="doc_type",
                match=models.MatchValue(value="pdf"),
            ),
        ],
    ) if filters else None,
)
```

**Important details from research**:
- Collection must have `sparse_vectors_config` with `Modifier.IDF` — Qdrant computes IDF server-side for the `Qdrant/bm25` sparse model
- Weighted RRF (`models.RrfQuery(rrf=models.Rrf(weights=[3.0, 1.0]))`) available in >= 1.17.0 — allows biasing dense vs sparse
- Cross-collection fan-out requires client-side `asyncio.gather` — Qdrant `query_batch_points` only works within a single collection
- **Existing `backend/storage/qdrant_client.py:61` uses the deprecated `client.search()` API** — the new `HybridSearcher` should use `client.query_points()` (current unified API)

**Alternatives considered**:
- Separate dense + sparse queries merged manually → More round trips, no native RRF
- Only dense search → Loses keyword-match precision (violates Constitution III)

---

### R5: Cross-Encoder Reranking

**Question**: How to load and use sentence-transformers CrossEncoder for reranking?

**Decision**: Load `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` at startup (in lifespan), use `model.rank(query, documents)` for batch scoring. Return sorted results by score descending.

**Rationale**: Constitution III mandates cross-encoder reranking with ms-marco-MiniLM-L-6-v2 on top-20 candidates. The `rank()` method is the efficient way to score query-document pairs in batch.

**Pattern**:
```python
from sentence_transformers import CrossEncoder

# Load once at startup:
reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

# In Reranker.rerank():
documents = [chunk.text for chunk in chunks]
rankings = reranker_model.rank(query, documents, top_k=top_k, return_documents=False)
# rankings is a list of dicts: [{"corpus_id": int, "score": float}, ...]

# Map back to chunks with rerank_score:
reranked = []
for r in rankings:
    chunk = chunks[r["corpus_id"]]
    chunk.rerank_score = r["score"]
    reranked.append(chunk)
```

**Alternatives considered**:
- LLM-based reranking → Too slow, not a retrieval signal
- BM25 score alone → Insufficient ranking quality (Constitution III)
- Other cross-encoder models → Constitution specifies ms-marco-MiniLM-L-6-v2

---

### R6: Dependency Injection in @tool Functions

**Question**: How do @tool-decorated functions access services like HybridSearcher, Reranker, ParentStore?

**Decision**: Use closure-based injection. Define tools inside a factory function that captures service instances. The factory is called at graph build time with the initialized services.

**Rationale**: LangChain @tool functions must have simple signatures for schema generation (the LLM sees the function signature). Service dependencies cannot be function parameters. Closures capture them cleanly without global state.

**Pattern**:
```python
from langchain_core.tools import tool

def create_research_tools(searcher, reranker, parent_store):
    @tool
    async def search_child_chunks(
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[dict]:
        """Hybrid dense+BM25 search with cross-encoder reranking."""
        raw = await searcher.search(query, collection, top_k, filters)
        return await reranker.rerank(query, raw, top_k=top_k)

    @tool
    async def retrieve_parent_chunks(parent_ids: list[str]) -> list[dict]:
        """Fetch parent chunks from storage by ID list."""
        return await parent_store.get_by_ids(parent_ids)

    # ... more tools ...

    return [search_child_chunks, retrieve_parent_chunks, ...]
```

**Alternatives considered**:
- Global singletons → Testability nightmare, against project patterns
- RunnableConfig injection → More complex, LangGraph-specific coupling
- Class-based tools → Heavier, less idiomatic for LangChain

---

### R7: Retry-Once Policy Implementation (FR-016)

**Question**: How to implement retry-once for failed tool calls while counting both attempts against the budget?

**Decision**: Wrap individual tool executions with `tenacity` using `stop_after_attempt(2)`. Count the original attempt immediately. If it fails and retries, the retry is a separate tool call that also counts.

**Rationale**: FR-016 specifies exactly one retry. Using tenacity is consistent with the existing circuit breaker pattern in `backend/storage/qdrant_client.py`. Counting both attempts prevents a single tool from consuming the entire budget on retries.

**Pattern**:
```python
from tenacity import retry, stop_after_attempt, retry_if_exception_type

async def execute_tool_call(tool_fn, args, state):
    state["tool_call_count"] += 1  # count original attempt
    try:
        return await tool_fn.ainvoke(args)
    except (QdrantConnectionError, EmbeddingError) as e:
        state["tool_call_count"] += 1  # count retry attempt
        logger.warning("tool_call_retrying", tool=tool_fn.name, error=str(e))
        try:
            return await tool_fn.ainvoke(args)  # one retry
        except Exception:
            logger.error("tool_call_failed_after_retry", tool=tool_fn.name)
            return None  # skip this tool call
```

**Alternatives considered**:
- tenacity with automatic retry → Harder to count attempts explicitly
- No retry (fail-fast) → Rejected by clarification Q1 (user chose Option B)
- Unlimited retries → Budget could be exhausted on a single failing tool

---

### R8: Signal-Based Confidence Scoring (FR-009)

**Question**: How to compute confidence from retrieval signals instead of LLM self-assessment?

**Decision**: Weighted combination of 5 measurable signals from the retrieved chunks. The formula produces a float 0.0–1.0, converted to int 0–100 for SubAnswer.

**Rationale**: FR-009 and Constitution IV both require confidence from retrieval signals, not LLM self-assessment. The existing `compute_confidence()` in `confidence.py` is a Phase 1 placeholder that only uses relevance scores — spec-03 replaces it with a richer signal set.

**Formula**:
```python
def compute_confidence(
    chunks: list[RetrievedChunk],
    target_collections: list[str],
    expected_chunks: int = 5,
) -> float:
    if not chunks:
        return 0.0

    reranked = [c for c in chunks if c.rerank_score is not None]
    if not reranked:
        return 0.1  # minimal confidence without reranking

    scores = [c.rerank_score for c in reranked]

    # Signal 1: Mean rerank score (weight 0.4)
    mean_score = sum(scores) / len(scores)

    # Signal 2: Chunk count factor (weight 0.2)
    count_factor = min(1.0, len(reranked) / expected_chunks)

    # Signal 3: Top score quality (weight 0.2)
    top_score = max(scores)

    # Signal 4: Score consistency — low variance = higher confidence (weight 0.1)
    if len(scores) > 1:
        variance = sum((s - mean_score) ** 2 for s in scores) / len(scores)
        consistency = max(0.0, 1.0 - variance)  # lower variance → higher score
    else:
        consistency = 0.5

    # Signal 5: Collection coverage (weight 0.1)
    collections_hit = len(set(c.collection for c in reranked))
    coverage = min(1.0, collections_hit / max(1, len(target_collections)))

    confidence = (
        0.4 * mean_score +
        0.2 * count_factor +
        0.2 * top_score +
        0.1 * consistency +
        0.1 * coverage
    )
    return max(0.0, min(1.0, confidence))
```

**Alternatives considered**:
- LLM self-assessment ("How confident are you?") → Explicitly forbidden by FR-009 and Constitution IV
- Single-signal (just mean score) → Insufficient; doesn't capture coverage or diversity
- Learned calibration model → YAGNI (Constitution VII); can be added later if needed
