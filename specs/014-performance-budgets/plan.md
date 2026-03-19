# Implementation Plan: Performance Budgets and Pipeline Instrumentation

**Branch**: `014-performance-budgets` | **Date**: 2026-03-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/014-performance-budgets/spec.md`

## Summary

Spec-14 has one primary engineering change and one set of verification benchmarks. The primary
change is per-stage timing instrumentation: adding a `stage_timings_json TEXT` column to the
existing `query_traces` SQLite table, accumulating per-node timing data in `ConversationState`
as each pipeline stage executes, and exposing the parsed data via the existing `GET /api/traces/{id}`
endpoint. The verification work confirms that existing configuration defaults already satisfy the
latency, throughput, and concurrency budgets defined in the spec.

Total scope: ~60–80 lines of new production code across 5 existing files, plus 3 new unit test
files and 4 new integration benchmark tests (extending an existing file).

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: LangGraph >= 1.0.10, FastAPI >= 0.135, aiosqlite >= 0.21, structlog >= 24.0
**Storage**: SQLite WAL mode (`data/embedinator.db`) — schema migration adds `stage_timings_json TEXT` column to `query_traces` via idempotent `ALTER TABLE`
**Testing**: pytest via external runner (`scripts/run-tests-external.sh`) — NEVER run pytest directly inside Claude Code
**Target Platform**: Linux / macOS 13+ / Windows 11+ via Docker Compose
**Project Type**: Backend service (Python FastAPI + LangGraph agent)
**Performance Goals**: `time.perf_counter()` instrumentation adds < 1 ms overhead per node (negligible relative to LLM call latency); benchmarks verify 1.5 s simple query, 6 s complex query, 3 s/15 s ingestion targets
**Constraints**: No new pip dependencies; inline timing only (no Timer class); idempotent schema migration; `pathlib.Path` for all new file paths (Constitution VIII)
**Scale/Scope**: 5 modified production files, 3 new unit test files, 1 extended integration file; 35 agent tasks across 3 waves

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Local-First Privacy** | ✅ PASS | No new network calls; no authentication changes; all changes are internal instrumentation only |
| **II. Three-Layer Agent Architecture** | ✅ PASS | Timing instrumentation added to existing nodes only; `ConversationGraph → ResearchGraph → MetaReasoningGraph` structure is untouched |
| **III. Retrieval Pipeline Integrity** | ✅ PASS | No changes to retrieval components (searcher, reranker, chunking); timing is purely observational |
| **IV. Observability from Day One** | ✅ PASS | This spec explicitly extends observability: `stage_timings_json` enriches the mandatory `query_traces` record already required by this principle |
| **V. Secure by Design** | ✅ PASS | `stage_timings_json` contains only numeric timing data (no credentials, no PII); parameterized SQL maintained; no new credentials introduced |
| **VI. NDJSON Streaming Contract** | ✅ PASS | No changes to streaming protocol; `stage_timings` data is stored in trace record only, not added to the NDJSON stream; metadata frame is unchanged |
| **VII. Simplicity by Default** | ✅ PASS | No new services; no new dependencies; inline `time.perf_counter()` avoids Timer class abstraction; YAGNI respected |
| **VIII. Cross-Platform Compatibility** | ✅ PASS | All changes are pure Python; no file paths in production code; test fixtures use `tmp_path / "test.db"` (pathlib.Path); no platform-specific calls |

**GATE RESULT: PASS** — No violations detected. Complexity Tracking table not required.

## Project Structure

### Documentation (this feature)

```text
specs/014-performance-budgets/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── trace-detail-api.md
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (modified files only)

```text
backend/
  agent/
    state.py                     # Add stage_timings: dict field to ConversationState
    nodes.py                     # Add time.perf_counter() timing to 6-7 node functions
  storage/
    sqlite_db.py                 # Schema migration + create_query_trace() param + SELECT
  api/
    chat.py                      # Extract stage_timings from final_state; pass to create_query_trace()
    traces.py                    # Add stage_timings_json to SELECT; expose as "stage_timings" in response

tests/
  unit/
    test_stage_timings.py        # NEW — FR-005 state + nodes (A2)
    test_stage_timings_db.py     # NEW — FR-005 storage round-trip (A3)
    api/
      test_traces_stage_timings.py  # NEW — FR-008 API exposure (A3)
  integration/
    test_performance.py          # EXTENDED — adds 4 new benchmarks; 2 existing tests preserved
```

**Structure Decision**: Single backend project (existing layout). No new files at the module level — all changes are additions to existing files. Three new test files follow the existing `tests/unit/` and `tests/unit/api/` layout established in prior specs.
