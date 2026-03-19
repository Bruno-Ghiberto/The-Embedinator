# Spec 04: MetaReasoningGraph -- Implementation Plan Context

## Component Overview

The MetaReasoningGraph is Layer 3 of the three-layer agent architecture and the primary differentiator of The Embedinator. It diagnoses retrieval failures using quantitative cross-encoder scoring (via the project's `Reranker` class, NOT LLM self-assessment), selects a recovery strategy based on measurable failure signals, modifies state, and re-enters the ResearchGraph for another attempt. It prevents silent failures, gives the system a second chance to find relevant evidence, and provides honest, actionable uncertainty reports when recovery fails.

**Spec reference**: `specs/004-meta-reasoning/spec.md` — 6 user stories, 17 FRs, 7 edge cases, 6 success criteria

## Technical Approach

- **LangGraph StateGraph**: Define `MetaReasoningGraph` using `StateGraph(MetaReasoningState)` with a linear flow through evaluation and decision nodes, plus conditional routing to strategy-specific state modification or uncertainty reporting.
- **Reranker for Scoring**: Use the project's `Reranker` class from `backend/retrieval/reranker.py` (wraps `sentence_transformers.CrossEncoder`) for quantitative retrieval quality evaluation. Call `reranker.rerank(query, chunks, top_k=len(chunks))` to score ALL chunks — not just the default top-5.
- **Strategy Pattern with Dedup**: Each recovery strategy (WIDEN_SEARCH, CHANGE_COLLECTION, RELAX_FILTERS) produces a `modified_state` dict that overwrites specific ResearchState fields before re-entry. Previously attempted strategies are tracked in `attempted_strategies: set[str]` and excluded on subsequent attempts (FR-015).
- **Configurable Thresholds**: Decision thresholds come from Settings — `meta_relevance_threshold` (default 0.2) and `meta_variance_threshold` (default 0.15) — tunable per environment (FR-004 clarification).
- **Score Variance**: The RELAX_FILTERS strategy uses `statistics.stdev(chunk_relevance_scores) > settings.meta_variance_threshold` instead of the undefined `answer_coherence` from the blueprint.
- **Attempt Counter**: `meta_attempt_count` is incremented each time. At `>= settings.meta_reasoning_max_attempts` (default 2), `report_uncertainty` is forced.
- **LLM via Config DI**: LLM resolved from `config["configurable"]["llm"]`, Reranker from `config["configurable"]["reranker"]` — following the established spec-03 pattern.
- **SSE Status Events**: Emit lightweight NDJSON events during meta-reasoning for user feedback (FR-014): `{"type": "meta_reasoning", "data": {"status": "...", "attempt": N}}`.
- **Structured Logging**: Every node emits structlog JSON events with session/trace ID (FR-016), consistent with spec-02/03 patterns.

## File Structure

```
backend/
  agent/
    meta_reasoning_graph.py   # StateGraph definition + compile (NEW)
    meta_reasoning_nodes.py   # 4 node function implementations (NEW)
    meta_reasoning_edges.py   # Conditional edge functions (NEW)
    prompts.py                # Add GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM
    state.py                  # Update MetaReasoningState: add attempted_strategies field
    research_edges.py         # Update should_continue_loop: "exhausted" → meta_reasoning
    research_graph.py         # Update build_research_graph: accept + wire meta_reasoning subgraph
  retrieval/
    reranker.py               # Existing — used by evaluate_retrieval_quality (no changes)
  config.py                   # Add meta_relevance_threshold, meta_variance_threshold settings
  main.py                     # Build MetaReasoningGraph in lifespan, pass to ResearchGraph builder
tests/
  unit/
    test_meta_reasoning_nodes.py   # Node unit tests (NEW)
    test_meta_reasoning_edges.py   # Edge unit tests (NEW)
  integration/
    test_meta_reasoning_graph.py   # Full graph compilation + execution tests (NEW)
```

## Implementation Steps

### Phase 1: Foundation (Wave 1)

1. **Add meta-reasoning prompts to `backend/agent/prompts.py`**:
   - `GENERATE_ALT_QUERIES_SYSTEM` template (with `{sub_question}` and `{chunk_summaries}` placeholders)
   - `REPORT_UNCERTAINTY_SYSTEM` template (with collections searched, findings, suggestions structure)

2. **Update `MetaReasoningState` in `backend/agent/state.py`**:
   - Add `attempted_strategies: set[str]` field for strategy deduplication (FR-015)

3. **Add settings to `backend/config.py`**:
   - `meta_relevance_threshold: float = 0.2`
   - `meta_variance_threshold: float = 0.15`

### Phase 2: Nodes (Wave 2 — parallel agents)

4. **`generate_alternative_queries`** in `meta_reasoning_nodes.py`:
   - Signature: `async def generate_alternative_queries(state: MetaReasoningState, config: RunnableConfig = None) -> dict`
   - LLM from `config["configurable"]["llm"]`
   - Produce exactly 3 alternative formulations
   - Emit SSE event: `{"type": "meta_reasoning", "data": {"status": "Generating alternative queries...", "attempt": N}}`
   - Emit structlog: `log.info("alt_queries_generated", count=3, session_id=...)`
   - Graceful degradation: if LLM call fails, return `{"alternative_queries": [state["sub_question"]]}` (edge case)

5. **`evaluate_retrieval_quality`** in `meta_reasoning_nodes.py`:
   - Signature: `async def evaluate_retrieval_quality(state: MetaReasoningState, config: RunnableConfig = None) -> dict`
   - Reranker from `config["configurable"]["reranker"]`
   - Call `reranker.rerank(state["sub_question"], chunks, top_k=len(chunks))` to score ALL chunks
   - Extract `chunk.rerank_score` for each chunk → `chunk_relevance_scores`
   - Compute `mean_relevance_score = sum(scores) / len(scores)`
   - Guard: empty chunks → `{"mean_relevance_score": 0.0, "chunk_relevance_scores": []}` (FR-013)
   - Guard: Reranker unavailable (circuit breaker open) → route to report_uncertainty (FR-012)
   - Emit SSE event + structlog

6. **`decide_strategy`** in `meta_reasoning_nodes.py`:
   - Signature: `async def decide_strategy(state: MetaReasoningState) -> dict`
   - Read thresholds from `settings.meta_relevance_threshold`, `settings.meta_variance_threshold`
   - Compute `score_variance = statistics.stdev(chunk_relevance_scores)` (guard for < 2 scores)
   - Check `meta_attempt_count >= settings.meta_reasoning_max_attempts` → force report_uncertainty
   - Check `attempted_strategies` set → exclude already-tried strategies (FR-015)
   - Strategy selection: mean_score, chunk_count, score_variance → WIDEN_SEARCH / CHANGE_COLLECTION / RELAX_FILTERS
   - If selected strategy already attempted AND no untried strategies match → force report_uncertainty
   - Return partial dict: `{"recovery_strategy": str, "modified_state": dict, "meta_attempt_count": N+1, "attempted_strategies": updated_set}`
   - Emit structlog: `log.info("strategy_selected", strategy=..., mean_score=..., variance=..., attempt=...)`

7. **`report_uncertainty`** in `meta_reasoning_nodes.py`:
   - Signature: `async def report_uncertainty(state: MetaReasoningState, config: RunnableConfig = None) -> dict`
   - LLM from config. Build prompt with collections searched, chunks found, alternative queries tried
   - MUST NOT fabricate answers (FR-008)
   - Return: `{"answer": str, "uncertainty_reason": str}`
   - Emit SSE event: `{"type": "meta_reasoning", "data": {"status": "Could not find sufficient evidence", "attempt": N}}`

### Phase 3: Edges + Graph (Wave 3)

8. **Edge functions in `meta_reasoning_edges.py`**:
   - `route_after_strategy(state) -> str`: Returns `"retry"` if recovery_strategy is set, `"report"` if None (forced uncertainty)
   - `should_retry_or_report(state) -> str`: Check meta_attempt_count vs settings limit

9. **Graph builder in `meta_reasoning_graph.py`**:
   - `build_meta_reasoning_graph() -> CompiledGraph`
   - Linear flow: START → generate_alternative_queries → evaluate_retrieval_quality → decide_strategy
   - Conditional edge from decide_strategy via `route_after_strategy`: `"retry"` → END (modified_state ready), `"report"` → report_uncertainty → END

### Phase 4: Integration (Wave 4)

10. **Update `should_continue_loop` in `research_edges.py`**:
    - Change `"exhausted"` route from `fallback_response` to `meta_reasoning` node
    - Add guard: if `settings.meta_reasoning_max_attempts == 0`, keep routing to `fallback_response` (FR-011)

11. **Update `build_research_graph` in `research_graph.py`**:
    - Accept `meta_reasoning_graph: CompiledGraph | None` parameter
    - Add `meta_reasoning` node that wraps the compiled subgraph
    - Map ResearchState fields ↔ MetaReasoningState fields
    - On recovery (modified_state returned): apply overrides to ResearchState, re-enter orchestrator loop
    - On uncertainty (answer returned): set answer + confidence_score=0.0, route to END

12. **Wire up in `backend/main.py` lifespan**:
    ```python
    # Build graphs inside-out:
    meta_reasoning_graph = build_meta_reasoning_graph()
    research_graph = build_research_graph(
        meta_reasoning_graph=meta_reasoning_graph,
        reranker=reranker,
        ...
    )
    conversation_graph = build_conversation_graph(research_graph_compiled=research_graph)
    ```

### Phase 5: Tests (Wave 5 — parallel agents)

13. **Unit tests** in `test_meta_reasoning_nodes.py`:
    - `generate_alternative_queries`: produces exactly 3 alternatives, graceful LLM failure
    - `evaluate_retrieval_quality`: scores all chunks, handles empty list, handles Reranker unavailability
    - `decide_strategy`: all 3 strategies + forced uncertainty + strategy dedup + configurable thresholds
    - `report_uncertainty`: no fabrication, includes collections/suggestions

14. **Edge tests** in `test_meta_reasoning_edges.py`:
    - `route_after_strategy`: retry vs report routing
    - Integration with `should_continue_loop` updated routing

15. **Integration tests** in `test_meta_reasoning_graph.py`:
    - Full graph compilation
    - End-to-end: trigger → strategy → retry → success
    - End-to-end: trigger → max attempts → report_uncertainty
    - Strategy dedup across attempts
    - max_attempts=0 bypass

## Integration Points

- **ResearchGraph (spec-03)**: MetaReasoningGraph is invoked as a subgraph node in ResearchGraph. The `should_continue_loop` edge's `"exhausted"` route is updated from `fallback_response` to `meta_reasoning`. MetaReasoningGraph receives ResearchState context, produces `modified_state` for retry or `answer`+`uncertainty_reason` for termination.
- **Reranker (shared)**: The same `Reranker` instance (from `backend/retrieval/reranker.py`) used by ResearchGraph's tool nodes is passed via `config["configurable"]["reranker"]` to `evaluate_retrieval_quality`. Uses `reranker.rerank()` (not raw `CrossEncoder.predict()`).
- **LLM (shared)**: Same LLM provider as ResearchGraph, resolved from `config["configurable"]["llm"]` for alternative query generation and uncertainty reporting.
- **SSE Streaming**: Emits `{"type": "meta_reasoning", ...}` events via the existing NDJSON streaming protocol in `backend/api/chat.py`. User sees progress during the extra latency (up to 20s for 2 attempts).
- **ConversationGraph (spec-02)**: Not directly connected. ConversationGraph receives the final SubAnswer from ResearchGraph regardless of whether MetaReasoningGraph was involved.

## Key Code Patterns

### Node Signature Convention

All nodes follow the spec-03 established pattern:

```python
from langchain_core.runnables import RunnableConfig
from backend.agent.state import MetaReasoningState
from backend.config import settings
import structlog

logger = structlog.get_logger()

async def node_name(
    state: MetaReasoningState,
    config: RunnableConfig = None,  # NOT RunnableConfig | None (LangGraph quirk)
) -> dict:  # Return partial state update, NOT full MetaReasoningState
    """Docstring with Reads/Writes."""
    configurable = (config or {}).get("configurable", {})
    llm = configurable.get("llm")
    reranker = configurable.get("reranker")
    # ... node logic ...
    return {"field": value}  # partial dict, NOT {**state, "field": value}
```

### Reranker Quality Evaluation

```python
async def evaluate_retrieval_quality(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    log = logger.bind(session_id=state.get("session_id", ""))
    sub_q = state["sub_question"]
    chunks = state["retrieved_chunks"]

    if not chunks:
        log.info("eval_quality_empty_chunks")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    configurable = (config or {}).get("configurable", {})
    reranker = configurable.get("reranker")

    if reranker is None:
        log.warning("eval_quality_no_reranker")
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    try:
        # Score ALL chunks, not just top-k
        scored_chunks = reranker.rerank(sub_q, chunks, top_k=len(chunks))
    except Exception as exc:
        log.warning("eval_quality_reranker_failed", error=str(exc))
        return {"mean_relevance_score": 0.0, "chunk_relevance_scores": []}

    scores = [c.rerank_score for c in scored_chunks]
    mean_score = sum(scores) / len(scores)

    log.info("eval_quality_complete", mean_score=f"{mean_score:.3f}",
             chunk_count=len(scores))

    return {
        "mean_relevance_score": mean_score,
        "chunk_relevance_scores": scores,
    }
```

### Strategy Decision with Variance + Dedup

```python
import statistics

async def decide_strategy(state: MetaReasoningState) -> dict:
    log = logger.bind(session_id=state.get("session_id", ""))
    mean_score = state["mean_relevance_score"]
    chunks = state["retrieved_chunks"]
    chunk_count = len(chunks)
    scores = state["chunk_relevance_scores"]
    attempt_count = state["meta_attempt_count"]
    attempted = state.get("attempted_strategies", set())

    # Guard: max attempts reached (FR-006)
    if attempt_count >= settings.meta_reasoning_max_attempts:
        log.info("strategy_max_attempts", attempt=attempt_count)
        return {"recovery_strategy": None}

    # Compute score variance (guard for < 2 scores)
    score_variance = statistics.stdev(scores) if len(scores) >= 2 else 0.0

    # Determine candidate strategy
    relevance_thresh = settings.meta_relevance_threshold   # default 0.2
    variance_thresh = settings.meta_variance_threshold     # default 0.15

    candidate = None
    if mean_score < relevance_thresh and chunk_count < 3:
        candidate = "WIDEN_SEARCH"
    elif mean_score < relevance_thresh and chunk_count >= 3:
        candidate = "CHANGE_COLLECTION"
    elif mean_score >= relevance_thresh and score_variance > variance_thresh:
        candidate = "RELAX_FILTERS"
    # else: decent relevance + low variance → report_uncertainty

    # Strategy dedup (FR-015): skip if already attempted
    if candidate and candidate in attempted:
        # Try next best alternative
        fallback_order = ["WIDEN_SEARCH", "CHANGE_COLLECTION", "RELAX_FILTERS"]
        candidate = next((s for s in fallback_order if s not in attempted), None)

    if candidate is None:
        log.info("strategy_none_available", attempted=list(attempted))
        return {"recovery_strategy": None}

    # Build modified_state per strategy
    modified = _build_modified_state(candidate, state)

    log.info("strategy_selected", strategy=candidate, mean_score=f"{mean_score:.3f}",
             variance=f"{score_variance:.3f}", chunk_count=chunk_count,
             attempt=attempt_count + 1)

    return {
        "recovery_strategy": candidate,
        "modified_state": modified,
        "meta_attempt_count": attempt_count + 1,
        "attempted_strategies": attempted | {candidate},
    }
```

### MetaReasoningGraph Definition

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import MetaReasoningState
from backend.agent.meta_reasoning_nodes import (
    generate_alternative_queries, evaluate_retrieval_quality,
    decide_strategy, report_uncertainty,
)
from backend.agent.meta_reasoning_edges import route_after_strategy


def build_meta_reasoning_graph():
    graph = StateGraph(MetaReasoningState)

    graph.add_node("generate_alternative_queries", generate_alternative_queries)
    graph.add_node("evaluate_retrieval_quality", evaluate_retrieval_quality)
    graph.add_node("decide_strategy", decide_strategy)
    graph.add_node("report_uncertainty", report_uncertainty)

    graph.add_edge(START, "generate_alternative_queries")
    graph.add_edge("generate_alternative_queries", "evaluate_retrieval_quality")
    graph.add_edge("evaluate_retrieval_quality", "decide_strategy")
    graph.add_conditional_edges("decide_strategy", route_after_strategy, {
        "retry": END,              # modified_state ready for ResearchGraph re-entry
        "report": "report_uncertainty",
    })
    graph.add_edge("report_uncertainty", END)

    return graph.compile()
```

### Graph Assembly Order (backend/main.py)

```python
# Build graphs inside-out in lifespan:
meta_reasoning_graph = build_meta_reasoning_graph()
research_graph = build_research_graph(meta_reasoning_graph=meta_reasoning_graph)
conversation_graph = build_conversation_graph(research_graph_compiled=research_graph)

app.state.conversation_graph = conversation_graph
```

## Subagent Teams Strategy

Implementation uses Claude Code Agent Teams (experimental) with 5 waves. Each wave has a checkpoint gate — the next wave does NOT start until the previous wave's tests pass.

### Wave 1: Foundation (1 agent)
- **Agent A1**: Prompts + State + Config
  - Add prompt constants to `prompts.py`
  - Add `attempted_strategies` field to `MetaReasoningState` in `state.py`
  - Add `meta_relevance_threshold`, `meta_variance_threshold` to `Settings` in `config.py`
- **Checkpoint**: Verify no import errors, `ruff check .` passes

### Wave 2: Nodes (2 agents, parallel)
- **Agent A2**: `evaluate_retrieval_quality` + `decide_strategy`
  - Implements the scoring and strategy decision nodes in `meta_reasoning_nodes.py`
  - Follows config DI pattern, uses `Reranker`, `statistics.stdev`, strategy dedup, structlog
- **Agent A3**: `generate_alternative_queries` + `report_uncertainty`
  - Implements the LLM-dependent nodes in `meta_reasoning_nodes.py`
  - Follows config DI pattern, SSE events, graceful degradation, no-fabrication guardrail
- **Checkpoint**: All 4 node functions importable, `ruff check .` passes

### Wave 3: Edges + Graph Builder (1 agent)
- **Agent A4**: Edge functions + `build_meta_reasoning_graph()`
  - `route_after_strategy` edge in `meta_reasoning_edges.py`
  - Graph definition in `meta_reasoning_graph.py`
  - Verify graph compiles without error
- **Checkpoint**: `build_meta_reasoning_graph()` returns compiled graph

### Wave 4: Integration (1 agent)
- **Agent A5**: ResearchGraph routing + main.py wiring
  - Update `should_continue_loop` in `research_edges.py`: `"exhausted"` → `meta_reasoning`
  - Guard: `settings.meta_reasoning_max_attempts == 0` → keep `fallback_response` (FR-011)
  - Update `build_research_graph` to accept + wire meta_reasoning subgraph
  - Update `main.py` lifespan to build MetaReasoningGraph first
- **Checkpoint**: Full graph chain compiles (conversation → research → meta_reasoning)

### Wave 5: Tests (2 agents, parallel)
- **Agent A6**: Unit tests (`test_meta_reasoning_nodes.py` + `test_meta_reasoning_edges.py`)
- **Agent A7**: Integration tests (`test_meta_reasoning_graph.py`)
- **Checkpoint**: All tests pass via external runner

### Agent Instruction Files

Store at `Docs/PROMPTS/spec-04-meta-reasoning/agents/`:
- `agent-a1-foundation.md`
- `agent-a2-eval-strategy-nodes.md`
- `agent-a3-query-uncertainty-nodes.md`
- `agent-a4-edges-graph.md`
- `agent-a5-integration.md`
- `agent-a6-unit-tests.md`
- `agent-a7-integration-tests.md`

Each agent reads its instruction file FIRST. Spawn prompt: "Read your instruction file at `<path>` FIRST, then execute all assigned tasks."

## Testing Protocol

**CRITICAL: NEVER run pytest inside Claude Code.** All test execution MUST use the external test runner.

### Test Runner Usage

```bash
# Launch tests (returns immediately, runs in background):
zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py

# Poll status (1 line, ~5 tokens):
cat Docs/Tests/spec04-unit.status
# → RUNNING | PASSED | FAILED | ERROR

# Read summary when done (~20 lines):
cat Docs/Tests/spec04-unit.summary

# Debug specific failure only if needed:
grep -A5 "test_specific_name" Docs/Tests/spec04-unit.log
```

### Test Run Names
- `spec04-unit` — Node + edge unit tests
- `spec04-integration` — Full graph compilation + execution tests
- `spec04-regression` — Full test suite (all specs) to check for regressions

### Checkpoint Gate Protocol
After each wave, the orchestrator runs:
```bash
zsh scripts/run-tests-external.sh -n spec04-wave-N tests/
cat Docs/Tests/spec04-wave-N.status  # Must be PASSED before next wave
```

## Phase Assignment

- **Phase 2 (Performance & Resilience)**: MetaReasoningGraph is a Phase 2 feature. In Phase 1, the ResearchGraph routes budget exhaustion to `fallback_response` directly. In Phase 2, MetaReasoningGraph is built and wired in.
  - Phase 2 includes: All four nodes, strategy decision logic with configurable thresholds, cross-encoder quality evaluation via Reranker, strategy deduplication, retry loop with attempt counter, SSE status events, structured logging, report_uncertainty, ResearchGraph routing update, main.py wiring.
  - Phase 2 depends on: Spec-01 (state.py, schemas.py, config.py), Spec-02 (ConversationGraph), Spec-03 (ResearchGraph, Reranker, research_edges.py).
