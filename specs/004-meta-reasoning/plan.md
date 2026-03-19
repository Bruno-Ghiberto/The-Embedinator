# Implementation Plan: MetaReasoningGraph

**Branch**: `004-meta-reasoning` | **Date**: 2026-03-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-meta-reasoning/spec.md`

## Summary

The MetaReasoningGraph is Layer 3 of the three-layer LangGraph agent architecture. When the ResearchGraph exhausts its iteration/tool budget without reaching confidence threshold, the MetaReasoningGraph diagnoses the failure using quantitative cross-encoder scoring (via the project's `Reranker` class), selects a recovery strategy, modifies state, and re-enters the ResearchGraph. If recovery fails after the configured maximum attempts, it generates an honest uncertainty report with actionable user guidance. Implementation uses the established config DI pattern, separate node/edge/graph files, SSE status events, structlog observability, and configurable thresholds.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: LangGraph >= 1.0.10, LangChain >= 1.2.10, sentence-transformers >= 5.2.3, structlog >= 24.0, tenacity >= 9.0
**Storage**: SQLite WAL mode (existing), Qdrant (existing) — no new storage for this feature
**Testing**: pytest via external runner (`scripts/run-tests-external.sh`) — NEVER inside Claude Code
**Target Platform**: Linux server (Docker Compose)
**Project Type**: Web service (backend agent layer)
**Performance Goals**: < 10s per meta-reasoning attempt, < 20s total for 2-attempt cycle (SC-004)
**Constraints**: Max 2 meta-reasoning attempts (configurable via `settings.meta_reasoning_max_attempts`), cross-encoder scoring must not use LLM self-assessment
**Scale/Scope**: 1–5 concurrent users, single Reranker instance shared with ResearchGraph

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | PASS | No new outbound calls. Uses existing Ollama (default) or opt-in cloud LLM. No new services. |
| II | Three-Layer Agent Architecture | PASS | This IS Layer 3 (MetaReasoningGraph). Completes the three-layer scaffold mandated by ADR-002. |
| III | Retrieval Pipeline Integrity | PASS | Uses existing Reranker (cross-encoder/ms-marco-MiniLM-L-6-v2), hybrid search, parent/child chunks. No pipeline modifications. |
| IV | Observability from Day One | PASS | FR-016: structlog per node with session/trace ID. SSE events for user-facing progress. Meta-reasoning events captured in query traces. |
| V | Secure by Design | PASS | No new endpoints, no new credential handling, no new user input paths. Uses existing parameterized queries. |
| VI | NDJSON Streaming Contract | PASS | FR-014: Emits `{"type": "meta_reasoning", ...}` events via existing NDJSON protocol. Extends the type vocabulary without changing the protocol. |
| VII | Simplicity by Default | PASS | No new services (still 4 Docker services). No new databases. Reuses existing Reranker + LLM. Separate files follow established spec-03 pattern. |

**Gate result**: ALL PASS. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/004-meta-reasoning/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
  agent/
    meta_reasoning_graph.py   # StateGraph definition + compile (NEW)
    meta_reasoning_nodes.py   # 4 node functions (NEW)
    meta_reasoning_edges.py   # Conditional edge functions (NEW)
    prompts.py                # Add 2 prompt constants (MODIFY)
    state.py                  # Add attempted_strategies field (MODIFY)
    research_edges.py         # Update "exhausted" routing (MODIFY)
    research_graph.py         # Wire meta_reasoning subgraph (MODIFY)
  config.py                   # Add 2 threshold settings (MODIFY)
  main.py                     # Build MetaReasoningGraph in lifespan (MODIFY)
tests/
  unit/
    test_meta_reasoning_nodes.py   # Node unit tests (NEW)
    test_meta_reasoning_edges.py   # Edge unit tests (NEW)
  integration/
    test_meta_reasoning_graph.py   # Full graph tests (NEW)
```

**Structure Decision**: Follows the spec-03 (ResearchGraph) pattern exactly — separate `_nodes.py`, `_edges.py`, `_graph.py` files per graph layer. All prompts in central `prompts.py`. All settings in central `config.py`.

## Phase 0: Research

All unknowns resolved during `/speckit.clarify`. See [research.md](research.md) for 8 decisions:

| # | Decision | Choice |
|---|----------|--------|
| R1 | Quality evaluation method | Reranker class (not raw CrossEncoder or LLM) |
| R2 | Score variance signal | `statistics.stdev(chunk_relevance_scores)` |
| R3 | Strategy deduplication | `attempted_strategies: set[str]` field |
| R4 | Configurable thresholds | `meta_relevance_threshold`, `meta_variance_threshold` in Settings |
| R5 | SSE status events | NDJSON `{"type": "meta_reasoning", ...}` extension |
| R6 | Node interface contract | Config DI pattern (`config: RunnableConfig = None`) |
| R7 | Graph structure | Subgraph compiled and invoked from ResearchGraph node |
| R8 | Retry failure handling | Direct to `report_uncertainty` on infrastructure errors |

## Phase 1: Design

See [data-model.md](data-model.md) for entity definitions. See [quickstart.md](quickstart.md) for implementation guide.

### Key Design Decisions

1. **State update**: Add `attempted_strategies: set[str]` to `MetaReasoningState` in `state.py` (only new field needed — all other fields scaffolded in spec-01's state.py, exercised for the first time in spec-04)
2. **Config additions**: `meta_relevance_threshold: float = 0.2` and `meta_variance_threshold: float = 0.15` in `Settings`
3. **Prompts**: 2 new constants in `prompts.py` — `GENERATE_ALT_QUERIES_SYSTEM`, `REPORT_UNCERTAINTY_SYSTEM`
4. **No contracts directory**: No new external interfaces exposed — MetaReasoningGraph is internal to the agent layer, invoked only via ResearchGraph subgraph wiring

### Node Contracts

| Node | Reads | Writes | Side Effects |
|------|-------|--------|-------------|
| `generate_alternative_queries` | `sub_question`, `retrieved_chunks` | `alternative_queries` | LLM call, SSE event |
| `evaluate_retrieval_quality` | `sub_question`, `retrieved_chunks` | `mean_relevance_score`, `chunk_relevance_scores` | Reranker inference, SSE event |
| `decide_strategy` | `mean_relevance_score`, `chunk_relevance_scores`, `retrieved_chunks`, `meta_attempt_count`, `attempted_strategies` | `recovery_strategy`, `modified_state`, `meta_attempt_count`, `attempted_strategies` | structlog event |
| `report_uncertainty` | `sub_question`, `retrieved_chunks`, `mean_relevance_score`, `meta_attempt_count`, `alternative_queries` | `answer`, `uncertainty_reason` | LLM call, SSE event |

### Strategy Decision Logic

```text
mean < meta_relevance_threshold AND chunk_count < 3     → WIDEN_SEARCH
mean < meta_relevance_threshold AND chunk_count >= 3    → CHANGE_COLLECTION
mean >= meta_relevance_threshold AND variance > meta_variance_threshold → RELAX_FILTERS
mean >= meta_relevance_threshold AND variance <= meta_variance_threshold → report_uncertainty
    (handles: decent individual chunks but insufficient aggregate confidence — no search-parameter change will help; the content gap is genuine)
meta_attempt_count >= meta_reasoning_max_attempts       → report_uncertainty (forced)
candidate in attempted_strategies                       → next untried strategy or report_uncertainty
```

### Graph Flow

```text
START → generate_alternative_queries → evaluate_retrieval_quality → decide_strategy
  decide_strategy --[recovery_strategy set]--> END (modified_state ready for ResearchGraph retry)
  decide_strategy --[recovery_strategy None]--> report_uncertainty → END
```

### Integration Points

- `should_continue_loop` in `research_edges.py`: already returns `"exhausted"` string — no change needed to the edge function itself
- `build_research_graph` in `research_graph.py`: **already accepts** `meta_reasoning_graph: Any = None` and conditionally routes `"exhausted"` → `meta_reasoning` when provided. The only new work is adding the ResearchState↔MetaReasoningState mapper node inside the `meta_reasoning` wrapper.
- `main.py` lifespan: builds inside-out — `meta_reasoning_graph → research_graph → conversation_graph`
- Guard: `settings.meta_reasoning_max_attempts == 0` → skip meta-reasoning, keep `fallback_response` (FR-011)

## Subagent Teams Strategy

Implementation uses Claude Code subagents with 5 waves. Each wave has a checkpoint gate — the next wave does NOT start until the previous wave's tests pass.

### Wave 1: Foundation (1 agent)

- **Agent A1**: Prompts + State + Config
  - Add prompt constants to `prompts.py`
  - Add `attempted_strategies` field to `MetaReasoningState` in `state.py`
  - Add `meta_relevance_threshold`, `meta_variance_threshold` to `Settings` in `config.py`
- **Checkpoint**: `python -c "from backend.agent.state import MetaReasoningState; print('OK')"` + `ruff check .`

### Wave 2: Nodes (2 agents, parallel)

- **Agent A2**: `evaluate_retrieval_quality` + `decide_strategy` in `meta_reasoning_nodes.py`
  - Scoring logic, strategy selection, variance computation, strategy dedup, structlog
- **Agent A3**: `generate_alternative_queries` + `report_uncertainty` in `meta_reasoning_nodes.py`
  - LLM-dependent nodes, SSE events, graceful degradation, no-fabrication guardrail
- **Checkpoint**: All 4 node functions importable + `ruff check .`

### Wave 3: Edges + Graph Builder (1 agent)

- **Agent A4**: Edge functions + `build_meta_reasoning_graph()`
  - `route_after_strategy` edge in `meta_reasoning_edges.py`
  - Graph definition in `meta_reasoning_graph.py`
- **Checkpoint**: `build_meta_reasoning_graph()` returns compiled graph

### Wave 4: Integration (1 agent)

- **Agent A5**: ResearchGraph routing + main.py wiring
  - Update `should_continue_loop`: `"exhausted"` → `meta_reasoning`
  - Guard for `max_attempts == 0` (FR-011)
  - Update `build_research_graph` to wire subgraph
  - Update `main.py` lifespan
- **Checkpoint**: Full graph chain compiles

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

## Testing Protocol

**CRITICAL: NEVER run pytest inside Claude Code.** All test execution uses the external runner.

```bash
# Unit tests:
zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py

# Integration tests:
zsh scripts/run-tests-external.sh -n spec04-integration tests/integration/test_meta_reasoning_graph.py

# Regression (all specs):
zsh scripts/run-tests-external.sh -n spec04-regression tests/

# Check status:
cat Docs/Tests/spec04-unit.status    # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec04-unit.summary   # ~20 lines summary
```

### Checkpoint Gate Protocol

After each wave:
```bash
zsh scripts/run-tests-external.sh -n spec04-wave-N tests/
cat Docs/Tests/spec04-wave-N.status  # Must be PASSED before next wave
```

## Constitution Re-Check (Post-Design)

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | PASS | No changes from pre-design check |
| II | Three-Layer Agent Architecture | PASS | Design confirms Layer 3 completion |
| III | Retrieval Pipeline Integrity | PASS | Uses Reranker as-is, no pipeline changes |
| IV | Observability from Day One | PASS | structlog + SSE events confirmed in node contracts |
| V | Secure by Design | PASS | No new attack surface |
| VI | NDJSON Streaming Contract | PASS | Type extension only |
| VII | Simplicity by Default | PASS | 3 new files, 5 modified — minimal footprint |

**Post-design gate**: ALL PASS. Design consistent with constitution.

## Dependencies

| Dependency | Type | Status | Required By |
|-----------|------|--------|-------------|
| Spec-01 (state.py, schemas.py, config.py) | Internal | Complete | Wave 1 |
| Spec-02 (ConversationGraph) | Internal | Complete | Wave 4 |
| Spec-03 (ResearchGraph, Reranker, research_edges.py) | Internal | Complete | Wave 2, 4 |
| LangGraph >= 1.0.10 | External | In requirements.txt | Wave 3 |
| sentence-transformers >= 5.2.3 | External | In requirements.txt | Wave 2 |
| structlog >= 24.0 | External | In requirements.txt | All waves |
| statistics (stdlib) | External | Built-in | Wave 2 |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Cross-encoder threshold defaults don't match deployment model | Medium | Medium | Configurable via env vars (R4) |
| Subgraph state mapping loses fields | Low | High | Explicit field mapping in integration node |
| Second attempt repeats same strategy | Low | Medium | `attempted_strategies` dedup (R3, FR-015) |
| Meta-reasoning adds >20s latency | Low | Medium | Performance target SC-004, bounded by max 2 attempts |
