╔══════════════════════════════════════════════════════════════╗
║  AGENT TEAMS REQUIRE TMUX — NON-NEGOTIABLE                  ║
║  Run: tmux new-session -s spec15                             ║
║  Each agent spawns in its own pane automatically            ║
╚══════════════════════════════════════════════════════════════╝

# Spec 15: Observability Layer — Implementation Guide

**Branch**: `015-observability` | **Date**: 2026-03-18
**Spec**: `specs/015-observability/spec.md` | **Tasks**: `specs/015-observability/tasks.md`

---

## Implementation Overview

Spec-15 closes remaining observability gaps across the full stack. It does NOT recreate
existing MVP components (`logging_config.py`, `TraceMiddleware`, `LatencyChart.tsx`,
etc.) — those are already implemented. This spec extends the existing foundation with:

| User Story | Priority | What Changes |
|------------|----------|--------------|
| US1: End-to-End Request Tracing | P1 | `bind_contextvars(trace_id=...)` in middleware + session_id in chat + ingestion trace |
| US2: Time-Series Metrics Dashboard | P2 | `GET /api/metrics` endpoint with bucketed trend data |
| US3: Per-Component Log Level Control | P3 | `LOG_LEVEL_OVERRIDES` env var + `_filter_by_component` processor |
| US4: Stage Timings Visualization | P3 | `StageTimingsChart.tsx` + `useMetrics.ts` frontend components |
| US5: Consistent Log Event Naming | P4 | Full codebase-wide rename across 12 backend modules |

**Scope**: ~17 files modified (14 backend + 3 frontend), 2 new frontend files, 4 new test
files. No new dependencies. No schema migrations. No new Docker services.

**Pre-existing test failures**: 39 — this count must not increase.

---

## Wave Execution Plan

```
Wave 1 ─── A1 (Opus) ─── Audit + Foundation ────────────── BLOCKING
             |
             └── Gate: ALL modules use .bind(component=__name__)
                        Log event inventory complete

Wave 2 ─── A2 (Sonnet) ─ US1: End-to-End Tracing ┐── parallel
       └── A3 (Sonnet) ─ US2: Metrics Endpoint   ┘
             |
             └── Gate: test_trace_context.py PASSED
                        test_metrics.py PASSED

Wave 3 ─── A4 (Sonnet) ─ US3: Per-Component Log Levels ┐── parallel
       └── A5 (Sonnet) ─ US4: Stage Timings Chart      ┘
             |
             └── Gate: test_component_log_levels.py PASSED
                        StageTimingsChart renders + hidden for legacy

Wave 4 ─── A6 (Opus)   ─ US5: Agent + Retrieval renames ┐── parallel
       └── A7 (Sonnet) ─ US5: Storage + API renames     ┘
             |
             └── Gate: full test suite passes, ≤39 pre-existing failures

Wave 5 ─── A8 (Sonnet) ─ Phase 8: Final Validation ──── sequential
```

**Gate discipline**: No wave may start until ALL agents in the preceding wave have reported
completion AND the gate condition is verified. The Orchestrator is responsible for polling
and confirming gates.

---

## File Modification Map

| Agent | Wave | Files Modified | Files Created |
|-------|------|----------------|---------------|
| A1 | 1 | `backend/middleware.py` (logger), `backend/agent/nodes.py` (logger), `backend/agent/research_nodes.py` (logger), `backend/agent/meta_reasoning_nodes.py` (logger), `backend/retrieval/searcher.py` (logger), `backend/retrieval/reranker.py` (logger), `backend/storage/sqlite_db.py` (logger), `backend/storage/qdrant_client.py` (logger), `backend/storage/indexing.py` (logger), `backend/ingestion/pipeline.py` (logger), `backend/providers/registry.py` (logger), `backend/api/chat.py` (logger), `backend/api/traces.py` (logger) | `tests/unit/test_trace_context.py` (T004a smoke only) |
| A2 | 2 | `backend/middleware.py`, `backend/api/chat.py`, `backend/ingestion/pipeline.py` | `tests/unit/test_trace_context.py` (full) |
| A3 | 2 | `backend/agent/schemas.py`, `backend/api/traces.py` | `tests/unit/api/test_metrics.py` |
| A4 | 3 | `backend/config.py`, `backend/main.py` | `tests/unit/test_component_log_levels.py` |
| A5 | 3 | `frontend/lib/types.ts`, `frontend/components/TraceTable.tsx`, `frontend/app/observability/page.tsx` | `frontend/components/StageTimingsChart.tsx`, `frontend/hooks/useMetrics.ts` |
| A6 | 4 | `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/meta_reasoning_nodes.py`, `backend/retrieval/searcher.py`, `backend/retrieval/reranker.py` | — |
| A7 | 4 | `backend/storage/qdrant_client.py`, `backend/storage/sqlite_db.py`, `backend/storage/indexing.py`, `backend/ingestion/pipeline.py`, `backend/api/chat.py`, `backend/middleware.py`, `backend/providers/registry.py` | — |
| A8 | 5 | — | — |

**Note**: `middleware.py`, `chat.py`, and `pipeline.py` are touched by multiple agents across
different waves. This is safe because A1 (logger fix) runs first, A2 (tracing) runs second,
and A7 (event renames) runs fourth. No two agents in the same wave touch the same file.

---

## Critical Implementation Rules

### C1: Pydantic Schema First (A3)
Add three models to `backend/agent/schemas.py` BEFORE implementing the endpoint:
`CircuitBreakerSnapshot`, `MetricsBucket`, `MetricsResponse`. These are required
as the return type annotation on the handler. See A3.md for exact field definitions.

### C2: structlog Component Binding (A1, BLOCKING)
`PrintLoggerFactory` silently drops positional args. `get_logger(__name__)` does NOT
populate `_logger_name` in `event_dict`. The ONLY working pattern is:

```python
# WRONG:
log = structlog.get_logger(__name__)

# CORRECT:
log = structlog.get_logger().bind(component=__name__)
```

The `_filter_by_component` processor (A4) reads `event_dict.get("component", "")`.
If A1 does not complete this migration, US3 will not work correctly.

### C3: Circuit Breaker "unknown" State (A3)
Three keys exactly: `qdrant`, `inference`, `search`. None instance MUST map to
`"unknown"` state, not `"closed"`. Using `getattr(..., False)` on None returns False
(interpreted as "closed") — this is the bug to avoid. Always check for None first.

### U1: bucket_size Field Required (A3)
`MetricsResponse` MUST include a `bucket_size: str` field. The contract specifies:
`"5m"` for 1h window, `"1h"` for 24h window, `"1d"` for 7d window. This field
is a top-level response field, not inside buckets.

### U2: Ascending Bucket Sort (A3)
Buckets MUST be sorted ascending by timestamp. After filling zero-count slots,
call `buckets.sort(key=lambda b: b.timestamp)` before building the response.

### U3: Spec-12 Error Envelope (A3)
Invalid window values return HTTP 400 with the spec-12 envelope format:
```python
raise HTTPException(status_code=400, detail={
    "code": "VALIDATION_ERROR",
    "message": "Invalid window. Must be one of: 1h, 24h, 7d",
    "details": None
})
```

### Verified Current State (do not re-audit)
- `_configure_logging()` processor chain: `merge_contextvars` → `add_log_level` →
  `TimeStamper` → `StackInfoRenderer` → `format_exc_info` → `_strip_sensitive_fields` →
  `JSONRenderer`. No per-component filter exists yet.
- `TraceIDMiddleware.dispatch()`: uuid → `request.state.trace_id` → `call_next` →
  response header. No `bind_contextvars`. No `try/finally`. Lines 22-27.
- `backend/api/traces.py`: `list_traces`, `get_trace`, `system_stats` — no `metrics`.
- `backend/agent/schemas.py`: no `MetricsResponse`, `MetricsBucket`, `CircuitBreakerSnapshot`.

---

## Agent Instruction Files

| Agent | File | Role | Model |
|-------|------|------|-------|
| A1 | `Docs/PROMPTS/spec-15-observability/agents/A1.md` | quality-engineer | Opus 4.6 |
| A2 | `Docs/PROMPTS/spec-15-observability/agents/A2.md` | python-expert | Sonnet 4.6 |
| A3 | `Docs/PROMPTS/spec-15-observability/agents/A3.md` | python-expert | Sonnet 4.6 |
| A4 | `Docs/PROMPTS/spec-15-observability/agents/A4.md` | python-expert | Sonnet 4.6 |
| A5 | `Docs/PROMPTS/spec-15-observability/agents/A5.md` | frontend-architect | Sonnet 4.6 |
| A6 | `Docs/PROMPTS/spec-15-observability/agents/A6.md` | python-expert | Opus 4.6 |
| A7 | `Docs/PROMPTS/spec-15-observability/agents/A7.md` | python-expert | Sonnet 4.6 |
| A8 | `Docs/PROMPTS/spec-15-observability/agents/A8.md` | quality-engineer | Sonnet 4.6 |

---

## Orchestrator Script

```bash
# PREREQUISITE: Must be inside a tmux session
# tmux new-session -s spec15

# === WAVE 1 ===
claude --agent quality-engineer --model claude-opus-4-6-20251001 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A1.md FIRST, then execute all assigned tasks."
# Wait for A1 completion message. Verify gate: all modules use .bind(component=__name__)

# === WAVE 2 (spawn in parallel) ===
claude --agent python-expert --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A2.md FIRST, then execute all assigned tasks." &

claude --agent python-expert --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A3.md FIRST, then execute all assigned tasks." &

wait  # Wait for both A2 and A3 to complete
# Verify gate: test_trace_context.py PASSED, test_metrics.py PASSED

# === WAVE 3 (spawn in parallel) ===
claude --agent python-expert --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A4.md FIRST, then execute all assigned tasks." &

claude --agent frontend-architect --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A5.md FIRST, then execute all assigned tasks." &

wait  # Wait for both A4 and A5 to complete
# Verify gate: test_component_log_levels.py PASSED, StageTimingsChart exists

# === WAVE 4 (spawn in parallel) ===
claude --agent python-expert --model claude-opus-4-6-20251001 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A6.md FIRST, then execute all assigned tasks." &

claude --agent python-expert --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A7.md FIRST, then execute all assigned tasks." &

wait  # Wait for both A6 and A7 to complete
# Verify gate: full test suite passes, ≤39 pre-existing failures

# === WAVE 5 ===
claude --agent quality-engineer --model claude-sonnet-4-6 \
  "Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/A8.md FIRST, then execute all assigned tasks."
```

---

## Test Runner Reference

**NEVER run pytest directly inside Claude Code.** Always use the external test runner:

```bash
# Run a specific test file:
zsh scripts/run-tests-external.sh -n <run-name> <target-path>

# Example for a single file:
zsh scripts/run-tests-external.sh -n spec15-us1 tests/unit/test_trace_context.py

# Example for full suite:
zsh scripts/run-tests-external.sh -n spec15-final tests/

# Poll for results (non-blocking):
zsh scripts/run-tests-external.sh -s <run-name>

# Pre-existing baseline: 39 failures — must not increase
```

The test runner accepts ONE target path per invocation. For multiple files, run separate
invocations. Each agent should run their own user-story-scoped test before reporting
completion.

---

## Commit Conventions

Use conventional commits after each logical group:

```
feat: add bind_contextvars to TraceIDMiddleware for automatic trace propagation
feat: add GET /api/metrics endpoint with time-bucketed trend data
feat: add per-component log level overrides via LOG_LEVEL_OVERRIDES env var
feat: add StageTimingsChart component for pipeline stage visualization
refactor: rename all backend log events to follow prefix convention
fix: add try/finally to TraceIDMiddleware to clear contextvars on error
test: add trace context propagation and isolation tests
```

Commit after each wave completes and passes its gate condition, not after every individual task.

---

## Authoritative References

- Spec: `specs/015-observability/spec.md`
- Plan: `specs/015-observability/plan.md`
- Tasks: `specs/015-observability/tasks.md`
- Research: `specs/015-observability/research.md`
- Metrics API contract: `specs/015-observability/contracts/metrics-api.md`
