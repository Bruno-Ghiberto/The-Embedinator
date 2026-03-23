# Implementation Plan: Observability Layer

**Branch**: `015-observability` | **Date**: 2026-03-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/015-observability/spec.md`

## Summary

Close remaining observability gaps in The Embedinator by: (1) binding trace ID and session ID to structlog context variables so ALL downstream log entries automatically include them, (2) adding a `GET /api/metrics` endpoint for time-bucketed trend data, (3) introducing per-component log level overrides, (4) adding a stage timings visualization chart to the frontend, and (5) renaming ALL existing log events across the codebase to follow a consistent prefix convention. Background ingestion tasks also get trace ID generation.

Scope: ~200-300 lines of new/modified production code across ~17 files (14 backend + 3 frontend), 2 new frontend files, 4 new test files. No new dependencies. No schema migrations.

## Technical Context

**Language/Version**: Python 3.14+ (backend), TypeScript 5.7 (frontend)
**Primary Dependencies**: structlog >= 24.0 (contextvars, JSONRenderer), FastAPI >= 0.135, recharts 2 (frontend charts), SWR 2 (data fetching) — all already installed
**Storage**: SQLite WAL mode (`data/embedinator.db`) — existing `query_traces` table with 15 columns, no schema changes
**Testing**: pytest (backend, via `scripts/run-tests-external.sh`), vitest (frontend)
**Target Platform**: Docker Compose (Linux, macOS, Windows via WSL)
**Project Type**: Web application (Python backend + Next.js frontend)
**Performance Goals**: Metrics endpoint < 500ms for 24h window with up to 10,000 traces (SC-003)
**Constraints**: No new dependencies, no new Docker services, no database migrations
**Scale/Scope**: 14 FRs, 7 SCs, 5 user stories, ~17 files modified, 2 new files created

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First Privacy | PASS | No cloud dependencies introduced. No authentication added. |
| II. Three-Layer Agent Architecture | PASS | Agent graph structure not modified. Only log event names change within existing nodes. |
| III. Retrieval Pipeline Integrity | PASS | Retrieval pipeline not modified. Only log event names change within searcher/reranker. |
| IV. Observability from Day One | PASS | **Directly aligned.** This spec completes the observability story: automatic trace ID propagation, metrics, per-component log levels. Constitution V already requires `bind_contextvars(trace_id=...)` at middleware boundary — FR-001 implements this. |
| V. Secure by Design | PASS | `_strip_sensitive_fields` processor already in structlog chain. FR-001 uses `bind_contextvars` as Constitution V requires. No credentials exposed in metrics endpoint. |
| VI. NDJSON Streaming Contract | PASS | No streaming changes. Plan correctly references NDJSON, not SSE. |
| VII. Simplicity by Default | PASS | No new services, no new databases. Metrics computed from existing SQLite data. Per-component log levels use env vars (simplest config). |
| VIII. Cross-Platform Compatibility | PASS | No platform-specific code. `pathlib.Path` used for any file path construction. |

**Result**: All 8 principles PASS. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/015-observability/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── metrics-api.md   # GET /api/metrics contract
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── middleware.py                  # MODIFY: bind/clear contextvars in TraceIDMiddleware
├── config.py                      # MODIFY: add log_level_overrides setting
├── main.py                        # MODIFY: update _configure_logging() with per-component filtering
├── api/
│   ├── chat.py                    # MODIFY: bind session_id to contextvars; rename log events
│   └── traces.py                  # MODIFY: add GET /api/metrics endpoint
├── agent/
│   ├── nodes.py                   # MODIFY: rename ~30 log events, add error fields
│   ├── research_nodes.py          # MODIFY: rename ~13 log events, add error fields
│   └── meta_reasoning_nodes.py    # MODIFY: rename ~9 log events, add error fields
├── retrieval/
│   ├── searcher.py                # MODIFY: rename log events (retrieval_ + circuit_ prefixes)
│   └── reranker.py                # MODIFY: rename log events with retrieval_ prefix
├── storage/
│   ├── sqlite_db.py               # MODIFY: rename log events; update get_query_traces_by_timerange()
│   ├── qdrant_client.py           # MODIFY: rename log events (storage_ + circuit_ prefixes)
│   └── indexing.py                # MODIFY: rename log events with storage_ prefix
├── ingestion/
│   └── pipeline.py                # MODIFY: bind trace ID at ingest_file() entry; rename log events
└── providers/
    └── registry.py                # MODIFY: rename log events with provider_ prefix

frontend/
├── lib/
│   └── types.ts                   # MODIFY: add stage_timings to QueryTraceDetail
├── components/
│   ├── StageTimingsChart.tsx       # NEW: horizontal bar chart for stage timings
│   └── TraceTable.tsx             # MODIFY: render StageTimingsChart in ExpandedRow
├── hooks/
│   └── useMetrics.ts              # NEW: SWR hook for GET /api/metrics
└── app/
    └── observability/
        └── page.tsx               # MODIFY: add metrics trends section

tests/
├── unit/
│   ├── test_trace_context.py      # NEW: FR-001, FR-002, FR-003, FR-014 tests
│   ├── test_component_log_levels.py  # NEW: FR-004 tests
│   └── api/
│       └── test_metrics.py        # NEW: FR-005 through FR-008 tests
└── (frontend vitest files)
```

**Structure Decision**: Web application with separate backend (Python/FastAPI) and frontend (Next.js/React). All modifications are to existing files except 2 new frontend components and 3-4 new test files.

## Complexity Tracking

No constitution violations to justify.
