# Spec 03: ResearchGraph -- Implementation Plan Context

## Component Overview

The ResearchGraph is the per-sub-question worker in the three-layer agent. It runs an LLM-driven orchestrator loop that decides which retrieval tools to call, executes them, deduplicates results, optionally compresses context, and terminates when confidence is sufficient or budget is exhausted. On exhaustion with low confidence, it delegates to the MetaReasoningGraph (spec-04). It is spawned by ConversationGraph's `fan_out` node and returns a `SubAnswer` with citations.

## Technical Approach

- **LangGraph StateGraph**: Define `ResearchGraph` using `StateGraph(ResearchState)` with a conditional loop between `orchestrator` -> `tools` -> `should_compress_context` -> `orchestrator`.
- **LangChain Tool Binding**: Bind tools to the orchestrator LLM via `.bind_tools()`. The orchestrator's response contains tool calls that are executed by the `tools` node.
- **LangChain @tool Decorator**: All tool functions are defined with `@tool` and proper docstrings for automatic schema generation.
- **Deduplication via Set**: `retrieval_keys: Set[str]` tracks `f"{query_normalized}:{parent_id}"` to skip seen results.
- **Token Counting**: Use `tiktoken` for approximate token counts. For non-GPT models, use the closest available encoding or the model's tokenizer endpoint.
- **Circuit Breaker**: Wrap Qdrant and Ollama calls with `tenacity` retry + circuit breaker pattern.

## File Structure

```
backend/
  agent/
    research_graph.py        # StateGraph definition for ResearchGraph
    nodes.py                 # Add ResearchGraph node functions
    edges.py                 # Add ResearchGraph edge functions
    tools.py                 # LangChain @tool definitions
    prompts.py               # Add orchestrator prompts
  retrieval/
    searcher.py              # Qdrant hybrid search execution
    reranker.py              # Cross-encoder reranking
    router.py                # Collection routing
    score_normalizer.py      # Per-collection min-max normalization
  storage/
    parent_store.py          # Parent chunk read from SQLite
```

## Implementation Steps

1. **Implement retrieval layer (`backend/retrieval/`)**:
   - `searcher.py`: `HybridSearcher` class with `search(query, collection, top_k, filters)` method. Executes hybrid dense + BM25 search against Qdrant. Uses `hybrid_dense_weight` (0.7) and `hybrid_sparse_weight` (0.3) from config.
   - `reranker.py`: `Reranker` class wrapping `sentence-transformers` `CrossEncoder`. `rerank(query, chunks, top_k)` method scores pairs and returns sorted results.
   - `score_normalizer.py`: Per-collection min-max normalization before cross-collection merge.
   - `router.py`: Regex-based collection routing (inherited from GRAVITEA).

2. **Implement parent store (`backend/storage/parent_store.py`)**:
   - `ParentStore` class with `get_by_ids(parent_ids: List[str]) -> List[ParentChunk]`.
   - Reads from SQLite `parent_chunks` table.

3. **Define tools in `backend/agent/tools.py`**:
   - `search_child_chunks`: Calls `HybridSearcher.search()` then `Reranker.rerank()`.
   - `retrieve_parent_chunks`: Calls `ParentStore.get_by_ids()`.
   - `cross_encoder_rerank`: Calls `Reranker.rerank()` directly.
   - `filter_by_collection`: Returns state modification dict.
   - `filter_by_metadata`: Returns state modification dict.
   - `semantic_search_all_collections`: Fan-out across collections, normalize, merge.

4. **Add orchestrator prompts to `backend/agent/prompts.py`**:
   - `ORCHESTRATOR_SYSTEM` and `ORCHESTRATOR_USER` templates.

5. **Implement ResearchGraph node functions in `backend/agent/nodes.py`**:
   - `orchestrator(state, *, llm)`: Bind tools to LLM, invoke with prompt, parse tool calls.
   - `tools(state)`: Execute pending tool calls, merge results, update dedup keys.
   - `should_compress_context(state)`: Token counting check, return routing decision.
   - `compress_context(state, *, llm)`: Summarize chunks, return compressed state.
   - `collect_answer(state, *, llm)`: Generate answer from chunks, compute confidence, build citations.
   - `fallback_response(state)`: Generate graceful "insufficient information" response.

6. **Implement ResearchGraph edge functions in `backend/agent/edges.py`**:
   - `should_continue_loop(state)`: Check iteration/tool limits, confidence, tool exhaustion.
   - `route_after_compress_check(state)`: Route to `compress_context` or back to `orchestrator`.

7. **Define the graph in `backend/agent/research_graph.py`**:
   - Create `StateGraph(ResearchState)`
   - Add orchestrator loop: `orchestrator` -> `tools` -> `should_compress_context` -> (compress or orchestrator)
   - Add terminal nodes: `collect_answer`, `fallback_response`
   - Add MetaReasoningGraph trigger edge
   - Compile

## Integration Points

- **ConversationGraph (spec-02)**: Spawns ResearchGraph via `Send()`. ResearchGraph receives `ResearchState` as initial state. Returns completed state with `answer`, `citations`, `confidence_score`.
- **MetaReasoningGraph (spec-04)**: ResearchGraph routes to MetaReasoningGraph when `confidence_score < CONFIDENCE_THRESHOLD` and iteration/tool budget is exhausted. MetaReasoningGraph modifies state and re-enters ResearchGraph.
- **Qdrant**: `search_child_chunks` and `semantic_search_all_collections` make HTTP calls to Qdrant for hybrid search.
- **SQLite**: `retrieve_parent_chunks` reads from `parent_chunks` table.
- **Ollama / Cloud LLM**: Orchestrator decisions, context compression, answer generation.
- **Cross-Encoder Model**: Reranking in `search_child_chunks` and `cross_encoder_rerank` tools.

## Key Code Patterns

### ResearchGraph Loop Structure

```python
from langgraph.graph import StateGraph, START, END

def build_research_graph(meta_reasoning_graph=None):
    graph = StateGraph(ResearchState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("tools", tools)
    graph.add_node("should_compress_context", should_compress_context)
    graph.add_node("compress_context", compress_context)
    graph.add_node("collect_answer", collect_answer)
    graph.add_node("fallback_response", fallback_response)

    if meta_reasoning_graph:
        graph.add_node("meta_reasoning", meta_reasoning_graph)

    graph.add_edge(START, "orchestrator")
    graph.add_conditional_edges("orchestrator", should_continue_loop, {
        "continue": "tools",
        "sufficient": "collect_answer",
        "exhausted": "fallback_response" if not meta_reasoning_graph else "meta_reasoning",
    })
    graph.add_edge("tools", "should_compress_context")
    graph.add_conditional_edges("should_compress_context", route_after_compress_check, {
        "compress": "compress_context",
        "continue": "orchestrator",
    })
    graph.add_edge("compress_context", "orchestrator")
    graph.add_edge("collect_answer", END)
    graph.add_edge("fallback_response", END)

    if meta_reasoning_graph:
        graph.add_edge("meta_reasoning", "orchestrator")  # retry loop

    return graph.compile()
```

### Deduplication Pattern

```python
def normalize_query(query: str) -> str:
    return " ".join(query.lower().strip().split())

def dedup_key(query: str, parent_id: str) -> str:
    return f"{normalize_query(query)}:{parent_id}"

# In tools node:
new_chunks = []
for chunk in raw_results:
    key = dedup_key(query, chunk.parent_id)
    if key not in state["retrieval_keys"]:
        state["retrieval_keys"].add(key)
        new_chunks.append(chunk)
```

### Tool Binding Pattern

```python
# In orchestrator node:
tools_list = [search_child_chunks, retrieve_parent_chunks,
              cross_encoder_rerank, filter_by_collection,
              filter_by_metadata, semantic_search_all_collections]

llm_with_tools = llm.bind_tools(tools_list)
response = await llm_with_tools.ainvoke([system_msg, user_msg])
```

## Phase Assignment

- **Phase 1 (MVP)**: ResearchGraph with all six tools, orchestrator loop, deduplication, context compression, fallback_response. MetaReasoningGraph trigger is wired but MetaReasoningGraph itself is a stub that routes directly to fallback_response.
- **Phase 2 (Performance & Resilience)**: MetaReasoningGraph fully implemented (spec-04). Computed confidence scoring replaces placeholder.
