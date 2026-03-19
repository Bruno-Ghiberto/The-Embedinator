# Spec 03: ResearchGraph -- Implementation Plan Context

## Component Overview

The ResearchGraph is the per-sub-question worker in the three-layer agent. It runs an LLM-driven orchestrator loop that decides which retrieval tools to call, executes them, deduplicates results, optionally compresses context, and terminates when confidence is sufficient or budget is exhausted. On exhaustion with low confidence, it delegates to the MetaReasoningGraph (spec-04). It is spawned by ConversationGraph's `route_fan_out()` edge function (called via `route_after_rewrite()` in `backend/agent/edges.py`) using `Send("research", payload)` and returns a `SubAnswer` with citations.

## Existing Code to Build On

These files already exist from specs 01-02 and MUST be used — do NOT recreate:

| File | What exists | Relevant for |
|------|-------------|--------------|
| `backend/agent/state.py` | `ResearchState(TypedDict)` with all fields (sub_question, retrieval_keys, tool_call_count, iteration_count, confidence_score, context_compressed, etc.) | Graph state — use as-is |
| `backend/agent/state.py` | `MetaReasoningState(TypedDict)` | Future integration |
| `backend/agent/schemas.py` | `RetrievedChunk`, `ParentChunk`, `Citation`, `SubAnswer` Pydantic models | Tool return types, answer packaging |
| `backend/agent/nodes.py` | `get_context_budget(model_name)` → returns `int(window * 0.75)`, `MODEL_CONTEXT_WINDOWS` dict | 75% compression threshold (FR-010) |
| `backend/agent/nodes.py` | structlog import, `logger = structlog.get_logger(__name__)` | Logging pattern (FR-017) |
| `backend/agent/edges.py` | `route_fan_out(state)` builds `Send("research", payload)` with full `ResearchState` | How ResearchGraph is spawned |
| `backend/agent/conversation_graph.py` | `graph.add_node("research", research_graph)` — expects compiled research graph | Integration point |
| `backend/agent/confidence.py` | `compute_confidence(passages, top_k=5)` — weighted average of relevance scores → int 0-100 | Extend for FR-009 (retrieval signal-based) |
| `backend/agent/answer_generator.py` | `generate_answer(llm, prompt)` and `generate_answer_stream(llm, prompt)` | Answer generation in collect_answer |
| `backend/agent/prompts.py` | 7 existing prompt constants (spec-02) | Add orchestrator prompts alongside |

## Technical Approach

- **LangGraph StateGraph**: Define `ResearchGraph` using `StateGraph(ResearchState)` with a conditional loop between `orchestrator` → `tools` → `should_compress_context` → `orchestrator`.
- **LangChain Tool Binding**: Bind tools to the orchestrator LLM via `.bind_tools()`. The orchestrator's response contains tool calls that are executed by the `tools` node.
- **LangChain @tool Decorator**: All tool functions are defined with `@tool` and proper docstrings for automatic schema generation.
- **Deduplication via Set**: `retrieval_keys: set[str]` tracks `f"{query_normalized}:{parent_id}"` to skip seen results.
- **Token Counting**: Use `count_tokens_approximately` from `langchain_core.messages.utils` (zero new dependencies — already used in spec-02). Do NOT add `tiktoken`.
- **Compression Threshold**: Trigger context compression when accumulated tokens reach 75% of model context window. Use existing `get_context_budget()` from `backend/agent/nodes.py`.
- **Retry-Once Policy (FR-016)**: Each failed tool call is retried exactly once. Both the original attempt and the retry count against the 8-call budget. Use `tenacity` with `stop=stop_after_attempt(2)` on individual tool executions.
- **Structured Logging (FR-017)**: Use `structlog` (already in codebase) to emit JSON log events at: loop start/end, each tool call (with result status), context compression events, confidence score changes, and fallback triggers. Follow the existing `logger = structlog.get_logger(__name__)` pattern.
- **Confidence Scoring (FR-009)**: Extend `backend/agent/confidence.py` to compute confidence from measurable retrieval signals: rerank scores, chunk count, coverage ratio. NOT from LLM self-assessment. The existing `compute_confidence()` is a Phase 1 placeholder — spec-03 replaces it with signal-based computation. Output is float 0.0–1.0 internally, converted to int 0–100 for `SubAnswer`.
- **Circuit Breaker**: Wrap Qdrant calls with `tenacity` retry + existing circuit breaker pattern from `backend/storage/qdrant_client.py`.

## File Structure

```
backend/
  agent/
    research_graph.py        # NEW: StateGraph definition for ResearchGraph
    research_nodes.py        # NEW: ResearchGraph-specific node functions
    research_edges.py        # NEW: ResearchGraph-specific edge functions
    tools.py                 # NEW: LangChain @tool definitions
    prompts.py               # MODIFY: Add orchestrator prompts
    confidence.py            # MODIFY: Replace placeholder with signal-based scoring
    state.py                 # EXISTS: ResearchState already defined
    schemas.py               # EXISTS: RetrievedChunk, ParentChunk, Citation, SubAnswer
    nodes.py                 # EXISTS: get_context_budget(), MODEL_CONTEXT_WINDOWS
  retrieval/
    __init__.py              # NEW
    searcher.py              # NEW: Qdrant hybrid search execution
    reranker.py              # NEW: Cross-encoder reranking
    score_normalizer.py      # NEW: Per-collection min-max normalization
  storage/
    parent_store.py          # NEW: Parent chunk read from SQLite
```

**Note**: ResearchGraph nodes and edges go in separate files (`research_nodes.py`, `research_edges.py`) to avoid bloating the existing `nodes.py` / `edges.py` which belong to ConversationGraph.

## Implementation Steps

### Step 1: Retrieval Layer (`backend/retrieval/`)

- `searcher.py`: `HybridSearcher` class with `async search(query, collection, top_k, filters)` method. Executes hybrid dense + BM25 search against Qdrant. Uses `hybrid_dense_weight` (0.7) and `hybrid_sparse_weight` (0.3) from config. Wraps calls with retry-once per FR-016.
- `reranker.py`: `Reranker` class wrapping `sentence-transformers` `CrossEncoder`. `async rerank(query, chunks, top_k)` method scores pairs and returns sorted `list[RetrievedChunk]`.
- `score_normalizer.py`: `normalize_scores(chunks_by_collection)` — per-collection min-max normalization before cross-collection merge.

### Step 2: Parent Store (`backend/storage/parent_store.py`)

- `ParentStore` class with `async get_by_ids(parent_ids: list[str]) -> list[ParentChunk]`.
- Reads from SQLite `parent_chunks` table via existing `backend/storage/sqlite_db.py` patterns.

### Step 3: Tool Definitions (`backend/agent/tools.py`)

- `search_child_chunks(query, collection, top_k=20, filters=None)`: Calls `HybridSearcher.search()` then `Reranker.rerank()`.
- `retrieve_parent_chunks(parent_ids)`: Calls `ParentStore.get_by_ids()`.
- `cross_encoder_rerank(query, chunks, top_k=5)`: Calls `Reranker.rerank()` directly.
- `filter_by_collection(collection_name)`: Returns state modification dict.
- `filter_by_metadata(filters)`: Returns state modification dict.
- `semantic_search_all_collections(query, top_k=20)`: Fan-out across collections, normalize via `score_normalizer`, merge.

All tools use `@tool` decorator with proper docstrings.

### Step 4: Orchestrator Prompts (`backend/agent/prompts.py`)

- Add `ORCHESTRATOR_SYSTEM` and `ORCHESTRATOR_USER` templates.
- Add `COMPRESS_CONTEXT_SYSTEM` prompt for context compression.
- Add `COLLECT_ANSWER_SYSTEM` prompt for answer generation from chunks.

### Step 5: Node Functions (`backend/agent/research_nodes.py`)

All follow the pattern: `async def node_name(state: ResearchState, *, llm: Any) -> dict`

- `orchestrator(state, *, llm)`: Bind tools to LLM via `.bind_tools()`, invoke with orchestrator prompt, parse tool calls from response. Log decision via structlog.
- `tools_node(state)`: Execute pending tool calls with retry-once (FR-016). Merge results into `retrieved_chunks` with deduplication via `retrieval_keys`. Increment `tool_call_count`. Log each tool call result.
- `should_compress_context(state)`: Use `count_tokens_approximately` to check token count against `get_context_budget(state["llm_model"])`. Return routing decision (not a state mutation).
- `compress_context(state, *, llm)`: Summarize `retrieved_chunks` via LLM call. Preserve citation references (FR-011). Set `context_compressed = True`. Log compression event.
- `collect_answer(state, *, llm)`: Generate answer from retrieved chunks. Compute confidence from retrieval signals via updated `compute_confidence()`. Convert float→int: `int(confidence_score * 100)`. Build citations. Log final confidence.
- `fallback_response(state)`: Generate graceful "insufficient information" response. Log fallback trigger.

### Step 6: Edge Functions (`backend/agent/research_edges.py`)

- `should_continue_loop(state)`: Returns `"continue"` | `"sufficient"` | `"exhausted"`:
  - `"sufficient"` if confidence_score >= CONFIDENCE_THRESHOLD
  - `"exhausted"` if iteration_count >= MAX_ITERATIONS or tool_call_count >= MAX_TOOL_CALLS or no pending tool calls
  - `"continue"` otherwise
- `route_after_compress_check(state)`: Returns `"compress"` | `"continue"` based on `should_compress_context` output.

### Step 7: Graph Definition (`backend/agent/research_graph.py`)

- Create `StateGraph(ResearchState)`
- Wire orchestrator loop: `orchestrator` → `tools` → `should_compress_context` → (compress or orchestrator)
- Wire terminal nodes: `collect_answer`, `fallback_response`
- Wire MetaReasoningGraph trigger edge (stub to `fallback_response` in Phase 1)
- Compile

### Step 8: Integration

- Update `backend/agent/conversation_graph.py`: pass compiled research graph to `build_conversation_graph(research_graph=...)` instead of mock
- Update `backend/main.py` lifespan: build research graph, inject into conversation graph
- Update `tests/mocks.py`: create `build_mock_research_graph()` that returns a simple compiled graph for unit tests

### Step 9: Confidence Scoring Upgrade (`backend/agent/confidence.py`)

- Replace Phase 1 placeholder with signal-based computation:
  - Inputs: rerank scores, chunk count, coverage ratio, number of collections searched
  - Formula: weighted combination of signals, NOT LLM self-assessment
  - Output: float 0.0–1.0 (converted to int 0–100 in collect_answer)

## Subagent Team Design

Implementation uses Claude Code subagents organized in 5 waves. Each agent reads its instruction file first, then executes assigned tasks.

### Wave 1 — Scaffold (1 agent)

| Agent | subagent_type | Model | Tasks |
|-------|---------------|-------|-------|
| agent-scaffold | python-expert | opus | Create all new files with stubs, add orchestrator prompts to prompts.py, verify all imports |

**Checkpoint**: All new modules importable, stubs have correct signatures.

### Wave 2 — Core Implementation (3 parallel agents)

| Agent | subagent_type | Model | Tasks |
|-------|---------------|-------|-------|
| agent-retrieval | python-expert | opus | HybridSearcher, Reranker, ScoreNormalizer full implementations |
| agent-tools | python-expert | opus | All 6 @tool definitions using retrieval layer interfaces |
| agent-nodes | python-expert | sonnet | All 6 research node functions + 2 edge functions |

**Checkpoint**: Each module has full implementations. Agents code against stub interfaces from Wave 1.

### Wave 3 — Integration (1 agent)

| Agent | subagent_type | Model | Tasks |
|-------|---------------|-------|-------|
| agent-integration | backend-architect | opus | Wire research_graph.py, update conversation_graph.py, update main.py lifespan, update mocks.py |

**Checkpoint**: `build_research_graph()` compiles without error, ConversationGraph uses real research graph.

### Wave 4 — Tests (2 parallel agents)

| Agent | subagent_type | Model | Tasks |
|-------|---------------|-------|-------|
| agent-unit-tests | quality-engineer | sonnet | Unit tests for retrieval, tools, nodes, edges, confidence |
| agent-integration-tests | quality-engineer | opus | Integration tests for full research_graph execution flows |

**Checkpoint**: All tests pass via external runner (`scripts/run-tests-external.sh`).

### Wave 5 — Polish (1 agent)

| Agent | subagent_type | Model | Tasks |
|-------|---------------|-------|-------|
| agent-polish | self-review | opus | Fix broken tests, verify structured logging (FR-017), verify retry behavior (FR-016), update CLAUDE.md |

**Checkpoint**: All tests green, CLAUDE.md updated.

### Test Execution Policy

**NEVER run pytest inside Claude Code.** All test execution uses the external runner:
```bash
zsh scripts/run-tests-external.sh -n <name> <target>
# Output: Docs/Tests/{name}.{status,summary,log}
# Poll: cat Docs/Tests/<name>.status → RUNNING|PASSED|FAILED|ERROR
# Read: cat Docs/Tests/<name>.summary (~20 lines, token-efficient)
```

## Integration Points

- **ConversationGraph (spec-02)**: Spawns ResearchGraph via `Send("research", payload)` from `route_fan_out()` edge function. ResearchGraph receives `ResearchState` as initial state (see `backend/agent/edges.py:87-101` for exact payload). Returns completed state with `answer`, `citations`, `confidence_score`.
- **MetaReasoningGraph (spec-04)**: ResearchGraph routes to MetaReasoningGraph when `confidence_score < CONFIDENCE_THRESHOLD` and iteration/tool budget is exhausted. In Phase 1, this routes to `fallback_response` instead (stub).
- **Qdrant**: `search_child_chunks` and `semantic_search_all_collections` make HTTP calls to Qdrant via `backend/storage/qdrant_client.py` for hybrid search.
- **SQLite**: `retrieve_parent_chunks` reads from `parent_chunks` table via `backend/storage/sqlite_db.py`.
- **Ollama / Cloud LLM**: Orchestrator decisions, context compression, answer generation — via provider registry in `backend/providers/`.
- **Cross-Encoder Model**: Reranking in `search_child_chunks` and `cross_encoder_rerank` tools.

## Key Code Patterns

### ResearchGraph Loop Structure

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import ResearchState

def build_research_graph(meta_reasoning_graph=None):
    graph = StateGraph(ResearchState)

    graph.add_node("orchestrator", orchestrator)
    graph.add_node("tools", tools_node)
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

# In tools_node:
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
from backend.agent.tools import (
    search_child_chunks, retrieve_parent_chunks,
    cross_encoder_rerank, filter_by_collection,
    filter_by_metadata, semantic_search_all_collections,
)

tools_list = [search_child_chunks, retrieve_parent_chunks,
              cross_encoder_rerank, filter_by_collection,
              filter_by_metadata, semantic_search_all_collections]

llm_with_tools = llm.bind_tools(tools_list)
response = await llm_with_tools.ainvoke([system_msg, user_msg])
```

### Retry-Once Pattern (FR-016)

```python
from tenacity import retry, stop_after_attempt, retry_if_exception_type

@retry(stop=stop_after_attempt(2), retry=retry_if_exception_type(QdrantConnectionError))
async def _execute_tool_with_retry(tool_fn, **kwargs):
    return await tool_fn(**kwargs)

# In tools_node: count both attempts against budget
state["tool_call_count"] += 1  # original attempt
try:
    result = await _execute_tool_with_retry(tool_fn, **kwargs)
except Exception:
    state["tool_call_count"] += 1  # retry also counts
    logger.warning("tool_call_failed_after_retry", tool=tool_name)
    continue
```

### Structured Logging Pattern (FR-017)

```python
import structlog
logger = structlog.get_logger(__name__)

# In orchestrator:
logger.info("research_loop_start", sub_question=state["sub_question"],
            session_id=state["session_id"])

# In tools_node:
logger.info("tool_call", tool=tool_name, status="success",
            new_chunks=len(new_chunks), tool_call_count=state["tool_call_count"])

# In collect_answer:
logger.info("research_loop_end", confidence=confidence_score,
            total_chunks=len(state["retrieved_chunks"]),
            iterations=state["iteration_count"])
```

## Phase Assignment

- **Phase 1 (MVP)**: ResearchGraph with all six tools, orchestrator loop, deduplication, context compression, signal-based confidence scoring (FR-009), retry-once (FR-016), structured logging (FR-017), fallback_response. MetaReasoningGraph trigger is wired but MetaReasoningGraph itself is a stub that routes directly to fallback_response.
- **Phase 2 (MetaReasoning)**: MetaReasoningGraph fully implemented (spec-04), replacing the stub.
