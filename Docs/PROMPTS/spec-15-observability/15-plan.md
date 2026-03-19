# Spec 15: Observability Layer -- Implementation Plan Context

> **AGENT TEAMS -- tmux IS REQUIRED**
>
> This spec uses 5 waves with 8 agents. Waves run sequentially; each wave gate
> must pass before the next wave begins. Waves 2, 3, and 4 run agents in parallel.
>
> **Orchestrator protocol**:
> 1. Read THIS file first (you are doing this now)
> 2. Spawn agents by wave, one per tmux pane
> 3. Each agent's FIRST action is to read its instruction file
> 4. Wait for wave gate before spawning the next wave
>
> Spawn command for every agent (no exceptions):
> ```
> Agent(
>   subagent_type="<type>",
>   model="<model>",
>   prompt="Read your instruction file at Docs/PROMPTS/spec-15-observability/agents/<file>.md FIRST, then execute all assigned tasks"
> )
> ```

---

## Component Overview

### What Spec-15 Adds

Spec-15 closes the remaining observability gaps identified in earlier specs. It has four
distinct engineering workstreams:

1. **Trace ID context propagation** -- Bind the existing `TraceIDMiddleware`-generated trace ID
   to structlog contextvars so ALL downstream log entries (agent, storage, retrieval, ingestion)
   automatically include `trace_id` without explicit kwarg passing. Also bind `session_id`
   during chat requests. Also generate and bind trace IDs for background ingestion tasks.

2. **Metrics aggregation endpoint** -- A new `GET /api/metrics` endpoint that returns
   time-bucketed trend data (latency percentiles, confidence averages, meta-reasoning rates,
   error counts) from the existing `query_traces` table, plus circuit breaker state and
   active ingestion job count.

3. **Per-component log levels + stage timings visualization** -- Add per-module log level
   overrides to `Settings` and apply them in `_configure_logging()`. Add a `StageTimingsChart`
   frontend component to visualize the `stage_timings_json` data that spec-14 already stores.

4. **Log event naming convention** -- Rename ALL existing log events across the entire codebase
   to use consistent category prefixes (`http_`, `agent_`, `retrieval_`, `storage_`,
   `ingestion_`, `provider_`, `circuit_`). Add `error` field with exception class name
   to all error-level log entries.

| FR | Primary File(s) | Change |
|----|-----------------|--------|
| FR-001 | `backend/middleware.py` | Add `structlog.contextvars.bind_contextvars(trace_id=trace_id)` in `TraceIDMiddleware.dispatch()` |
| FR-002 | `backend/api/chat.py` | Bind `session_id` to structlog contextvars at chat request entry |
| FR-003 | `backend/middleware.py` | Add `structlog.contextvars.clear_contextvars()` in `finally` block of `TraceIDMiddleware.dispatch()` |
| FR-004 | `backend/config.py`, `backend/main.py` | Add per-component log level settings; update `_configure_logging()` |
| FR-005 | `backend/api/traces.py` | New `GET /api/metrics` endpoint with time-bucketed query |
| FR-006 | `backend/api/traces.py` | Configurable time windows (1h, 24h, 7d) with appropriate bucket granularity |
| FR-007 | `backend/api/traces.py` | Include circuit breaker state in metrics response |
| FR-008 | `backend/api/traces.py` | Include active ingestion job count in metrics response |
| FR-009 | `frontend/components/StageTimingsChart.tsx` (new) | Horizontal bar chart for per-stage timing data |
| FR-010 | `frontend/components/TraceTable.tsx` | Conditionally render StageTimingsChart in ExpandedRow |
| FR-011 | 12 backend files | Rename ALL log events to use category prefixes |
| FR-012 | 12 backend files | Add `error` field with exception class name to error-level log entries |
| FR-013 | N/A (already satisfied) | Verify all logs are JSON Lines via structlog's `JSONRenderer` |
| FR-014 | `backend/ingestion/pipeline.py` | Generate and bind trace ID at start of `ingest_file()` |

Total scope: ~200-300 lines of new/modified production code across ~15 files, plus ~150 lines
of new tests.

### What Is Already Built -- Do NOT Reimplement

The following were completed in earlier specs. Agents must not touch these as new work:

| Component | Spec | Location |
|-----------|------|----------|
| `TraceIDMiddleware` class | spec-13 | `backend/middleware.py` lines 19-27 |
| `RequestLoggingMiddleware` class | spec-13 | `backend/middleware.py` |
| `RateLimitMiddleware` class | spec-13 | `backend/middleware.py` |
| `_configure_logging()` function | spec-13 | `backend/main.py` lines 39-57 |
| `_strip_sensitive_fields` processor | spec-13 | `backend/main.py` |
| `structlog.contextvars.merge_contextvars` in processor chain | spec-13 | `backend/main.py` line 43 |
| `GET /api/health` endpoint | spec-08 | `backend/api/health.py` |
| `GET /api/traces` endpoint | spec-08 | `backend/api/traces.py` |
| `GET /api/traces/{trace_id}` endpoint | spec-08 | `backend/api/traces.py` |
| `GET /api/stats` endpoint | spec-08 | `backend/api/traces.py` lines 134-176 |
| `query_traces` table with 15 columns | spec-07/10/14 | `backend/storage/sqlite_db.py` |
| `stage_timings_json` column | spec-14 | `backend/storage/sqlite_db.py` |
| `Settings.log_level` field | spec-13 | `backend/config.py` line 9 |
| Frontend observability page | spec-09 | `frontend/app/observability/page.tsx` |
| All 5 dashboard components | spec-09 | `frontend/components/` |
| `useTraces` SWR hook | spec-09 | `frontend/hooks/useTraces.ts` |
| NDJSON streaming for chat | spec-08/09 | `Content-Type: application/x-ndjson` |
| Three circuit breakers | spec-05/07 | `qdrant_client.py`, `searcher.py`, `nodes.py` |
| Error hierarchy | spec-12 | `backend/errors.py` |
| Stage timing instrumentation | spec-14 | `backend/agent/nodes.py` |
| `get_query_traces_by_timerange()` | spec-07 | `backend/storage/sqlite_db.py` lines 544-560 |

---

## Research Decisions

These key implementation choices must be resolved by the audit agent (A1) or the implementing
agent. Each includes the recommended approach.

### R1: Per-Component Log Levels with structlog

**Question**: How to implement per-component log levels when structlog uses a single global
`make_filtering_bound_logger()` call?

**Recommended approach**: Use Python's standard `logging` module integration. After
`structlog.configure()`, iterate over per-component overrides and call
`logging.getLogger(component_name).setLevel(level)` for each. Since structlog's
`PrintLoggerFactory` routes through standard logging when configured properly, this
applies module-level filtering.

However, structlog with `PrintLoggerFactory` bypasses standard logging. The alternative
is to add a custom structlog processor that checks the logger name against the override
map and drops events below the configured level. This processor must be inserted BEFORE
`JSONRenderer` in the chain.

**Agent A4 must verify** which approach works with the current `PrintLoggerFactory(file=sys.stdout)`
configuration and implement accordingly.

### R2: Metrics Bucket Granularity Strategy

**Question**: How to determine appropriate bucket sizes for different time windows?

**Recommended approach**: Fixed mapping:

| Window | Bucket Size | Max Buckets |
|--------|-------------|-------------|
| `1h` | 5 minutes | 12 |
| `24h` | 1 hour | 24 |
| `7d` | 1 day | 7 |

The SQL query uses `strftime()` for bucketing since SQLite stores `created_at` as ISO8601
text. Example: `strftime('%Y-%m-%dT%H:00:00', created_at)` for hourly buckets.

### R3: Circuit Breaker State Exposure Pattern

**Question**: How to read circuit breaker state from the metrics endpoint when the circuit
breakers are instance attributes (not centralized)?

**Recommended approach**: The metrics endpoint handler receives `request: Request`, which
gives access to `request.app.state`. Circuit breakers are reachable as:
- `request.app.state.qdrant._circuit_open` and `._failure_count` (QdrantClientWrapper)
- `request.app.state.qdrant_storage._circuit_open` (QdrantStorage -- if separate instance)
- `request.app.state.hybrid_searcher._circuit_open` (HybridSearcher)
- Module-level `backend.agent.nodes._inf_circuit_open` (inference)

The endpoint imports `nodes` module and reads the globals directly. For app.state instances,
it uses `getattr(request.app.state, "qdrant", None)` with graceful fallback.

### R4: Log Event Naming Audit Approach

**Question**: How to ensure ALL log events are renamed and none are missed?

**Recommended approach**: Static analysis via `search_for_pattern`. Before and after the
rename, run a search for log calls across all backend files. The audit verifies:
1. Pre-rename: document all current event names per file
2. Post-rename: verify every event name starts with a valid prefix
3. Regression: run full test suite to ensure renamed events do not break assertions

A verification test can also exercise key code paths and capture log output, asserting
every `event` field starts with one of the 7 prefixes.

### R5: Background Ingestion Trace ID Generation

**Question**: Should the background ingestion task inherit the HTTP request's trace ID or
generate a new one?

**Recommended approach**: Generate a NEW trace ID at the start of `ingest_file()`. Rationale:
- The HTTP request returns 202 immediately; the background task may run for minutes
- The ingestion trace represents a distinct operation from the upload request
- The request's trace ID is already recorded in the 202 response header

Implementation: At the top of `IngestionPipeline.ingest_file()`, generate `trace_id = str(uuid.uuid4())`
and call `structlog.contextvars.bind_contextvars(trace_id=trace_id)`. Clean up in a `finally`
block with `structlog.contextvars.clear_contextvars()`.

---

## Wave Definitions

### Wave 1 -- Pre-Flight Audit (Sequential)

| Field | Value |
|-------|-------|
| Agent | A1 |
| Type | quality-engineer |
| Model | claude-opus-4-5 |
| Tasks | T001-T010 |
| Output | `Docs/Tests/spec15-a1-audit.md` |

**Gate condition**: Audit report exists AND confirms:
- `TraceIDMiddleware.dispatch()` does NOT currently call `bind_contextvars` or `clear_contextvars`
- `Settings` does NOT have per-component log level fields
- No `GET /api/metrics` endpoint exists in `traces.py`
- `StageTimingsChart.tsx` does NOT exist in `frontend/components/`
- `useMetrics.ts` does NOT exist in `frontend/hooks/`
- `QueryTraceDetail` type in `frontend/lib/types.ts` does NOT include `stage_timings`
- `IngestionPipeline.ingest_file()` does NOT bind a trace ID
- Full inventory of current log event names across all backend modules (for FR-011 baseline)
- All target files identified with line-level insertion points documented

Do not spawn Wave 2 until the audit report is written and conditions above are met.

---

### Wave 2 -- Trace ID Propagation + Metrics Endpoint (Parallel)

Both A2 and A3 run simultaneously. They modify different files and do not conflict.

#### A2 -- Trace ID and Session ID Context Propagation

| Field | Value |
|-------|-------|
| Agent | A2 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T011-T019 |
| Files modified | `backend/middleware.py`, `backend/api/chat.py`, `backend/ingestion/pipeline.py` |
| New test files | `tests/unit/test_trace_context.py` |

#### A3 -- Metrics Aggregation Endpoint

| Field | Value |
|-------|-------|
| Agent | A3 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T020-T028 |
| Files modified | `backend/api/traces.py`, `backend/storage/sqlite_db.py` |
| New test files | `tests/unit/api/test_metrics.py` |

**Wave 2 gate condition**: Both A2 and A3 complete all assigned tasks. Each agent's external
test run returns `PASSED`. The pre-existing failure count does not increase.

---

### Wave 3 -- Per-Component Log Levels + Frontend (Parallel)

Both A4 and A5 run simultaneously. A4 modifies backend config/main; A5 modifies frontend files.

#### A4 -- Per-Component Log Level Configuration

| Field | Value |
|-------|-------|
| Agent | A4 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T029-T034 |
| Files modified | `backend/config.py`, `backend/main.py` |
| New test files | `tests/unit/test_component_log_levels.py` |

#### A5 -- Stage Timings Visualization

| Field | Value |
|-------|-------|
| Agent | A5 |
| Type | frontend-architect |
| Model | claude-sonnet-4-5 |
| Tasks | T035-T041 |
| Files modified | `frontend/lib/types.ts`, `frontend/components/TraceTable.tsx`, `frontend/app/observability/page.tsx` |
| New files created | `frontend/components/StageTimingsChart.tsx`, `frontend/hooks/useMetrics.ts` |

**Wave 3 gate condition**: Both A4 and A5 complete all assigned tasks. A4's external test run
returns `PASSED`. A5's vitest run returns `PASSED`.

---

### Wave 4 -- Log Event Naming Convention (Parallel)

Both A6 and A7 run simultaneously. They modify different files and do not conflict.

#### A6 -- Agent Module Log Event Renames

| Field | Value |
|-------|-------|
| Agent | A6 |
| Type | python-expert |
| Model | claude-opus-4-5 |
| Tasks | T042-T047 |
| Files modified | `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/meta_reasoning_nodes.py` |

**Why Opus**: `nodes.py` has ~30 log events and is the largest file. Many event names embed
diagnostic context (e.g., `"verify_groundedness: disabled via settings"`). The rename requires
careful judgment about which prefix and event name to use, and must also add `error` fields
to error-level log entries (FR-012).

#### A7 -- Storage/Retrieval/Ingestion/API Log Event Renames

| Field | Value |
|-------|-------|
| Agent | A7 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T048-T054 |
| Files modified | `backend/retrieval/searcher.py`, `backend/retrieval/reranker.py`, `backend/storage/qdrant_client.py`, `backend/storage/sqlite_db.py`, `backend/storage/indexing.py`, `backend/ingestion/pipeline.py`, `backend/api/chat.py`, `backend/middleware.py`, `backend/providers/registry.py` |

**Wave 4 gate condition**: Both A6 and A7 complete. External test run of full `tests/` suite
returns `PASSED`. Pre-existing failure count does not increase. A8 will verify no unprefixed
event names remain.

---

### Wave 5 -- Final Validation (Sequential)

| Field | Value |
|-------|-------|
| Agent | A8 |
| Type | quality-engineer |
| Model | claude-sonnet-4-5 |
| Tasks | T055-T062 |
| Output | `Docs/Tests/spec15-a8-final.md` |

**Wave 5 gate condition (final)**: All 7 success criteria verified. Pre-existing failure
count remains at 39. Final report written.

---

## Task Table

| Task | Agent | Description |
|------|-------|-------------|
| T001 | A1 | Read `specs/015-observability/spec.md` fully -- confirm 14 FRs, 7 SCs, 5 user stories |
| T002 | A1 | Read `backend/middleware.py` lines 19-27 -- confirm `TraceIDMiddleware.dispatch()` does NOT call `bind_contextvars` or `clear_contextvars`; document exact insertion points |
| T003 | A1 | Read `backend/main.py` lines 39-57 -- confirm `_configure_logging()` uses `merge_contextvars` processor (position 1); confirm no per-component log level logic exists |
| T004 | A1 | Read `backend/config.py` -- confirm `Settings` has `log_level: str = "INFO"` but NO per-component override fields |
| T005 | A1 | Read `backend/api/traces.py` -- confirm `list_traces`, `get_trace`, and `system_stats` exist but NO `metrics` endpoint; document route structure |
| T006 | A1 | Read `frontend/lib/types.ts` -- confirm `QueryTraceDetail` does NOT include `stage_timings`; confirm `frontend/components/StageTimingsChart.tsx` does NOT exist; confirm `frontend/hooks/useMetrics.ts` does NOT exist |
| T007 | A1 | Read `backend/ingestion/pipeline.py` lines 88-100 -- confirm `ingest_file()` does NOT generate or bind a trace ID at entry |
| T008 | A1 | Perform full log event inventory: search all backend files for `log\.(info\|warning\|error\|debug)\(` and `logger\.(info\|warning\|error\|debug)\(` patterns; document every event name per file with its current name, the target prefixed name, and the target prefix category |
| T009 | A1 | Read `backend/api/chat.py` -- confirm `session_id` is NOT currently bound to structlog contextvars; document the exact location where session_id is first available |
| T010 | A1 | Write audit report `Docs/Tests/spec15-a1-audit.md` -- one section per wave with insertion points, one section for log event inventory, overall PASS/FAIL verdict for pre-FR state |
| T011 | A2 | In `backend/middleware.py` `TraceIDMiddleware.dispatch()`: add `structlog.contextvars.bind_contextvars(trace_id=trace_id)` after `request.state.trace_id = trace_id`; wrap `call_next` + response header in `try/finally` block; add `structlog.contextvars.clear_contextvars()` in the `finally` block (FR-001, FR-003) |
| T012 | A2 | Add `import structlog` to `backend/middleware.py` if not already present (it imports `structlog.get_logger()` so verify the import covers `structlog.contextvars`) |
| T013 | A2 | In `backend/api/chat.py`: at the start of the `generate()` inner function (or wherever `session_id` is first extracted from `ChatRequest`), add `structlog.contextvars.bind_contextvars(session_id=session_id)` (FR-002) |
| T014 | A2 | Verify that `structlog.contextvars.clear_contextvars()` in the middleware `finally` block also clears `session_id` -- it does because `clear_contextvars()` clears ALL bound vars |
| T015 | A2 | In `backend/ingestion/pipeline.py` `ingest_file()`: at method entry (before any other logic), add `import uuid` + `trace_id = str(uuid.uuid4())` + `structlog.contextvars.bind_contextvars(trace_id=trace_id)` (FR-014); wrap the entire method body in `try/finally` with `structlog.contextvars.clear_contextvars()` in `finally` |
| T016 | A2 | Write `tests/unit/test_trace_context.py`: (1) send a request through TraceIDMiddleware, capture the response `X-Trace-ID` header, verify log entries contain matching `trace_id`; (2) send two concurrent requests, verify no trace ID cross-contamination; (3) verify contextvars are cleared after request completes; (4) verify session_id appears in log entries during chat processing |
| T017 | A2 | Write a test for FR-014: verify that `IngestionPipeline.ingest_file()` binds a trace ID to structlog contextvars at entry and clears it at exit |
| T018 | A2 | Run external tests: `zsh scripts/run-tests-external.sh -n spec15-a2 tests/unit/test_trace_context.py` -- poll until status is not `RUNNING`; read summary |
| T019 | A2 | Confirm `Docs/Tests/spec15-a2.status` is `PASSED`; report completion to orchestrator |
| T020 | A3 | In `backend/storage/sqlite_db.py`: update `get_query_traces_by_timerange()` SELECT to include `provider_name` and `stage_timings_json` columns (currently missing from the SELECT); these are needed for metrics aggregation |
| T021 | A3 | In `backend/api/traces.py`: add `GET /api/metrics` route handler that accepts `window` query param (values: `1h`, `24h`, `7d`, default `24h`); validate the window value and return 400 for invalid windows |
| T022 | A3 | Implement time-bucketed aggregation: compute `start_ts` from current time minus window duration; query `get_query_traces_by_timerange(start_ts, now_ts)`; group results into buckets using R2 granularity mapping; for each bucket compute: `query_count`, `avg_latency_ms`, `p95_latency_ms`, `avg_confidence`, `meta_reasoning_count`, `error_count` |
| T023 | A3 | For P95 latency calculation: sort `latency_ms` values per bucket, take the value at index `ceil(0.95 * count) - 1`; handle edge case of empty buckets (return 0 for all numeric fields) |
| T024 | A3 | Add circuit breaker state to metrics response (FR-007): import `backend.agent.nodes` for inference CB globals; read `request.app.state.qdrant._circuit_open` and `._failure_count` for Qdrant CB; read `request.app.state.hybrid_searcher._circuit_open` for search CB; use `getattr()` with defaults for graceful fallback if instances are missing |
| T025 | A3 | Add active ingestion job count to metrics response (FR-008): query `SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'processing'` via `db.db.execute()` |
| T026 | A3 | Write `tests/unit/api/test_metrics.py`: (1) `GET /api/metrics` returns 200 with valid JSON; (2) `GET /api/metrics?window=1h` returns 5-minute buckets; (3) `GET /api/metrics?window=24h` returns hourly buckets; (4) `GET /api/metrics?window=7d` returns daily buckets; (5) invalid window returns 400; (6) empty database returns empty buckets with zero counts (not error); (7) circuit breaker state is present in response; (8) active ingestion job count is present |
| T027 | A3 | Run external tests: `zsh scripts/run-tests-external.sh -n spec15-a3 tests/unit/api/test_metrics.py` -- poll until status is not `RUNNING`; read summary |
| T028 | A3 | Confirm `Docs/Tests/spec15-a3.status` is `PASSED`; report completion to orchestrator |
| T029 | A4 | In `backend/config.py` `Settings`: add `log_level_overrides: str = ""` field (env var: `LOG_LEVEL_OVERRIDES`); format is comma-separated `module=LEVEL` pairs, e.g. `backend.retrieval.reranker=DEBUG,backend.storage.sqlite_db=WARNING` |
| T030 | A4 | In `backend/main.py` `_configure_logging()`: after `structlog.configure()`, parse `settings.log_level_overrides` string into a dict of `{module_name: level}`; for invalid level values, log a warning and skip (fall back to global); store the parsed overrides for use by the filtering processor |
| T031 | A4 | Implement per-component filtering: add a custom structlog processor function `_filter_by_component(logger, method_name, event_dict)` that checks `event_dict.get("_logger_name", "")` against the override map; if the logger's effective level is higher than the event's level, raise `structlog.DropEvent`; insert this processor AFTER `merge_contextvars` and BEFORE `add_log_level` in the chain |
| T032 | A4 | Ensure all backend modules that use `structlog.get_logger()` pass `__name__` as the logger name: verify `nodes.py` uses `log = structlog.get_logger(__name__)`, `middleware.py` uses `logger = structlog.get_logger(__name__)` (currently uses `structlog.get_logger()` without `__name__` -- fix this) |
| T033 | A4 | Write `tests/unit/test_component_log_levels.py`: (1) with no overrides, all components use global level; (2) with `LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG`, reranker debug logs appear while others at INFO do not emit debug; (3) invalid level value in override falls back to global with warning |
| T034 | A4 | Run external tests: `zsh scripts/run-tests-external.sh -n spec15-a4 tests/unit/test_component_log_levels.py` -- poll until done; confirm PASSED |
| T035 | A5 | In `frontend/lib/types.ts`: add `stage_timings?: Record<string, { duration_ms: number; failed?: boolean }>` field to `QueryTraceDetail` interface |
| T036 | A5 | Create `frontend/components/StageTimingsChart.tsx`: a horizontal bar chart using recharts showing per-stage latency breakdown; props: `timings: Record<string, { duration_ms: number; failed?: boolean }>` |
| T037 | A5 | StageTimingsChart design: each bar represents a stage (rewrite, research, compression, generation, etc.); bar length proportional to `duration_ms`; failed stages shown in red; use Tailwind for layout; use dynamic import with `{ ssr: false }` for recharts components |
| T038 | A5 | In `frontend/components/TraceTable.tsx` `ExpandedRow`: after the existing detail sections, add conditional rendering of `StageTimingsChart` -- render only when `detail.stage_timings` exists and is a non-empty object (FR-009); hide completely when absent or empty (FR-010, handles legacy traces) |
| T039 | A5 | Create `frontend/hooks/useMetrics.ts`: SWR hook wrapping `GET /api/metrics` with configurable `window` parameter; type the response as `MetricsResponse` (define in `types.ts` or inline) |
| T040 | A5 | In `frontend/app/observability/page.tsx`: import and render a metrics trends section using `useMetrics` hook data -- this can be a placeholder section that renders the time-series data in a simple format (e.g., latency trend line chart) |
| T041 | A5 | Run vitest: verify StageTimingsChart renders with sample data, renders nothing when timings is empty/undefined; verify TraceTable integration |
| T042 | A6 | In `backend/agent/nodes.py`: rename ALL log events to use `agent_` prefix; example renames: `"init_session_failed"` -> `"agent_init_session_failed"`, `"intent_classified"` -> `"agent_intent_classified"`, `"verify_groundedness: disabled via settings"` -> `"agent_verify_groundedness_disabled"` (replace colons and spaces with underscores) |
| T043 | A6 | In `backend/agent/nodes.py`: for all `log.warning()` and `log.error()` calls that relate to exceptions, add `error=type(exc).__name__` kwarg (FR-012); do NOT add `error` field to non-exception warning logs |
| T044 | A6 | In `backend/agent/research_nodes.py`: rename ALL log events to use `agent_` prefix; example: `"orchestrator_no_llm"` -> `"agent_orchestrator_no_llm"`, `"tool_call_failed"` -> `"agent_tool_call_failed"`, `"compress_context_start"` -> `"agent_compress_context_start"`; add `error=type(exc).__name__` to exception-related log calls |
| T045 | A6 | In `backend/agent/meta_reasoning_nodes.py`: rename ALL log events to use `agent_` prefix; example: `"alt_queries_generated"` -> `"agent_alt_queries_generated"`, `"reranker_unavailable"` -> `"agent_reranker_unavailable"`, `"max_attempts_reached"` -> `"agent_max_attempts_reached"`; add `error=type(exc).__name__` to exception log calls |
| T046 | A6 | Run external tests: `zsh scripts/run-tests-external.sh -n spec15-a6 tests/unit/` -- poll until done; confirm no regressions in agent-related tests (test event name strings in assertions may need updating) |
| T047 | A6 | If any tests assert on specific event name strings (e.g., `"intent_classified"` in test assertions), update those assertions to match the new prefixed names |
| T048 | A7 | In `backend/retrieval/searcher.py`: rename log events; circuit breaker events get `circuit_` prefix: `"circuit_breaker_open"` -> `"circuit_searcher_open"`, `"circuit_breaker_opened"` -> `"circuit_searcher_opened"`; search events get `retrieval_` prefix: `"search_skipped_no_embed_fn"` -> `"retrieval_search_skipped_no_embed_fn"` |
| T049 | A7 | In `backend/retrieval/reranker.py`: rename log events with `retrieval_` prefix: `"reranker_failed"` -> `"retrieval_reranker_failed"`, `"rerank_complete"` -> `"retrieval_rerank_complete"`; add `error=type(exc).__name__` to the `reranker_failed` call |
| T050 | A7 | In `backend/storage/qdrant_client.py`: rename log events; circuit breaker events get `circuit_` prefix: `"qdrant_circuit_half_open"` -> `"circuit_qdrant_half_open"`, `"qdrant_circuit_open"` -> `"circuit_qdrant_open"`, `"qdrant_circuit_opened"` -> `"circuit_qdrant_opened"`; connection/CRUD events get `storage_` prefix: `"qdrant_connected"` -> `"storage_qdrant_connected"`, `"qdrant_collection_created"` -> `"storage_qdrant_collection_created"` |
| T051 | A7 | In `backend/storage/sqlite_db.py`: rename `"sqlite_connected"` -> `"storage_sqlite_connected"`; In `backend/storage/indexing.py`: rename `"no_chunks_to_index"` -> `"storage_no_chunks_to_index"`, `"chunks_indexed"` -> `"storage_chunks_indexed"` |
| T052 | A7 | In `backend/ingestion/pipeline.py`: rename ALL log events with `ingestion_` prefix: `"worker_invalid_json_line"` -> `"ingestion_worker_invalid_json_line"`, `"job_paused_qdrant_outage"` -> `"ingestion_job_paused_qdrant_outage"`, `"job_resumed_qdrant_recovered"` -> `"ingestion_job_resumed_qdrant_recovered"`; add `error=type(exc).__name__` to error-level calls |
| T053 | A7 | In `backend/api/chat.py`: rename events with `http_` prefix: `"query_trace_write_failed"` -> `"http_query_trace_write_failed"`, `"circuit_open_during_chat"` -> `"http_circuit_open_during_chat"`, `"chat_stream_error"` -> `"http_chat_stream_error"`; In `backend/middleware.py`: rename events with `http_` prefix; In `backend/providers/registry.py`: rename events with `provider_` prefix: `"default_provider_registered"` -> `"provider_default_registered"`, `"unknown_provider_fallback"` -> `"provider_unknown_fallback"`, `"provider_activated"` -> `"provider_activated"` (already has prefix) |
| T054 | A7 | Run external tests: `zsh scripts/run-tests-external.sh -n spec15-a7 tests/` -- poll until done; confirm no regressions; if test assertions reference old event names, update them |
| T055 | A8 | Run full test suite: `zsh scripts/run-tests-external.sh -n spec15-a8-full tests/` -- poll until complete; read summary |
| T056 | A8 | Verify SC-001: send an HTTP request, capture `X-Trace-ID` header, inspect log entries from at least 3 subsystems (agent, storage, retrieval) -- all must contain matching `trace_id` |
| T057 | A8 | Verify SC-002: write a test that sends 5 concurrent requests and confirms each request's logs contain only its own trace ID (no cross-contamination) |
| T058 | A8 | Verify SC-003: if feasible in CI, confirm `GET /api/metrics?window=24h` responds within 500ms |
| T059 | A8 | Verify SC-004: test that setting `LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG` changes the reranker's effective log level without restart (environment variable takes effect at startup) |
| T060 | A8 | Verify SC-005: confirm StageTimingsChart renders for traces with timing data and is hidden for traces without |
| T061 | A8 | Verify SC-006: search all backend files for log events; confirm every event name starts with one of the 7 defined prefixes (`http_`, `agent_`, `retrieval_`, `storage_`, `ingestion_`, `provider_`, `circuit_`); no legacy unprefixed names remain |
| T062 | A8 | Write final report `Docs/Tests/spec15-a8-final.md` -- one row per success criterion with PASS/SKIP/FAIL; total new test count; pre-existing failure count (must remain 39); explicit confirmation of all 14 FRs |

---

## Acceptance Criteria Reference

These 7 success criteria from `specs/015-observability/spec.md` are what A8 must verify:

1. **SC-001**: 100% of log entries produced during an HTTP request or background ingestion task contain a matching `trace_id` field, verified by log inspection across at least 3 subsystems.
2. **SC-002**: Zero trace ID leakage between concurrent requests -- verified by sending 5 concurrent requests and confirming each request's logs contain only its own trace ID.
3. **SC-003**: Metrics endpoint returns time-bucketed data within 500ms for a 24-hour window with up to 10,000 stored traces.
4. **SC-004**: Per-component log level overrides take effect without requiring application restart or code changes -- verified by setting an environment variable and confirming changed verbosity.
5. **SC-005**: Stage timings chart renders correctly for traces with timing data and is hidden for traces without -- verified on at least 3 traces of each type.
6. **SC-006**: ALL log event names across the entire codebase follow the defined prefix convention -- verified by exercising all major code paths and confirming every emitted log entry's event name starts with one of the 7 defined prefixes. No legacy unprefixed event names remain.
7. **SC-007**: The system handles edge cases gracefully: empty trace database returns empty buckets (not errors), malformed stage timing data is skipped (not crashes), invalid log level overrides fall back to global default with a warning.

SC-003 may be marked SKIP if the test environment cannot support the 10,000-trace load. All
other SCs must produce passing automated tests or documented verification.

---

## Integration Points

### Files Modified (Backend -- 14 files)

| File | FR(s) | Change Type |
|------|-------|-------------|
| `backend/middleware.py` | FR-001, FR-003, FR-011 | Add `bind_contextvars`/`clear_contextvars` in dispatch; rename log events |
| `backend/api/chat.py` | FR-002, FR-011 | Bind `session_id` to contextvars; rename log events |
| `backend/api/traces.py` | FR-005-FR-008 | Add `GET /api/metrics` endpoint |
| `backend/config.py` | FR-004 | Add `log_level_overrides` setting |
| `backend/main.py` | FR-004 | Update `_configure_logging()` with per-component filtering |
| `backend/ingestion/pipeline.py` | FR-014, FR-011 | Bind trace ID at `ingest_file()` entry; rename log events |
| `backend/storage/sqlite_db.py` | FR-005, FR-011 | Update `get_query_traces_by_timerange()` SELECT; rename log events |
| `backend/agent/nodes.py` | FR-011, FR-012 | Rename all ~30 log events; add error field to exception logs |
| `backend/agent/research_nodes.py` | FR-011, FR-012 | Rename all ~13 log events; add error field |
| `backend/agent/meta_reasoning_nodes.py` | FR-011, FR-012 | Rename all ~9 log events; add error field |
| `backend/retrieval/searcher.py` | FR-011, FR-012 | Rename log events; split circuit_/retrieval_ prefixes |
| `backend/retrieval/reranker.py` | FR-011, FR-012 | Rename log events with retrieval_ prefix |
| `backend/storage/qdrant_client.py` | FR-011, FR-012 | Rename log events; split circuit_/storage_ prefixes |
| `backend/storage/indexing.py` | FR-011 | Rename log events with storage_ prefix |
| `backend/providers/registry.py` | FR-011 | Rename log events with provider_ prefix |

### Files Created (Frontend -- 2 new files)

| File | FR(s) | Description |
|------|-------|-------------|
| `frontend/components/StageTimingsChart.tsx` | FR-009, FR-010 | Horizontal bar chart for stage timing data |
| `frontend/hooks/useMetrics.ts` | FR-005 | SWR hook for `GET /api/metrics` endpoint |

### Files Modified (Frontend -- 3 files)

| File | FR(s) | Change Type |
|------|-------|-------------|
| `frontend/lib/types.ts` | FR-009 | Add `stage_timings` to `QueryTraceDetail` interface |
| `frontend/components/TraceTable.tsx` | FR-009, FR-010 | Render `StageTimingsChart` in `ExpandedRow` |
| `frontend/app/observability/page.tsx` | FR-005 | Add metrics trends section |

### New Test Files (4 files)

| File | Agent | Tests |
|------|-------|-------|
| `tests/unit/test_trace_context.py` | A2 | Trace ID propagation, session ID binding, concurrent isolation, ingestion trace ID |
| `tests/unit/api/test_metrics.py` | A3 | Metrics endpoint windows, buckets, circuit breakers, edge cases |
| `tests/unit/test_component_log_levels.py` | A4 | Per-component level overrides, fallback behavior |
| Frontend vitest files (if needed) | A5 | StageTimingsChart rendering, TraceTable integration |

### Files Verified But NOT Modified

| File | Why Read | Action |
|------|----------|--------|
| `backend/api/health.py` | Confirm health endpoint already complete | Read-only |
| `backend/errors.py` | Reference error hierarchy for metrics classification | Read-only |
| `backend/agent/conversation_graph.py` | Confirm node names for stage timing stages | Read-only |
| `frontend/components/LatencyChart.tsx` | Reference existing recharts pattern | Read-only |
| `frontend/components/ConfidenceDistribution.tsx` | Reference existing dynamic import pattern | Read-only |

### Files Explicitly NOT to Touch

| File | Reason |
|------|--------|
| `backend/agent/state.py` | `stage_timings: dict` already added by spec-14 |
| `backend/agent/edges.py` | Routing logic not involved in observability |
| `backend/agent/research_edges.py` | Has logger but no log calls -- nothing to rename |
| `backend/agent/research_graph.py` | Has logger but no log calls -- nothing to rename |
| `backend/ingestion/chunker.py` | No log calls exist |
| `backend/ingestion/embedder.py` | No log calls exist |
| `backend/ingestion/incremental.py` | No log calls exist |

---

## Key Constraints

### TraceIDMiddleware -- Target Implementation

Current implementation (`backend/middleware.py` lines 19-27):
```python
class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique trace ID into every request/response for observability."""

    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

Target implementation:
```python
class TraceIDMiddleware(BaseHTTPMiddleware):
    """Inject a unique trace ID into every request/response for observability."""

    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()
```

Because `_configure_logging()` already includes `structlog.contextvars.merge_contextvars` as
the FIRST processor in the chain, binding `trace_id` to contextvars will cause it to appear
automatically in every log entry produced during that request -- no changes needed to
individual log call sites.

### Session ID Binding in chat.py

The `session_id` is available from `ChatRequest.session_id`. At the point where the chat
endpoint begins processing, bind it:

```python
structlog.contextvars.bind_contextvars(session_id=session_id)
```

This is cleared automatically when the middleware's `finally` block runs `clear_contextvars()`.

### Background Ingestion Trace ID (FR-014)

Background ingestion runs via `asyncio.create_task(pipeline.ingest_file(...))` in
`backend/api/ingest.py` line 147. The task inherits a copy of the request's context at
creation time, but after the HTTP response completes, the middleware clears the request
context. The background task's copy persists but may be stale.

Target implementation at `IngestionPipeline.ingest_file()` entry:

```python
async def ingest_file(self, file_path, filename, collection_id, document_id, job_id, file_hash=None):
    ingestion_trace_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(trace_id=ingestion_trace_id)
    try:
        # ... existing method body ...
    finally:
        structlog.contextvars.clear_contextvars()
```

This generates a fresh trace ID distinct from the HTTP request's trace ID. All log entries
from `pipeline.py`, `chunker.py`, `embedder.py`, `sqlite_db.py`, and `qdrant_client.py`
called during ingestion will automatically include this `trace_id` via the contextvar
processor.

### Metrics Endpoint Response Format

```json
{
  "window": "24h",
  "bucket_size": "1h",
  "buckets": [
    {
      "timestamp": "2026-03-18T00:00:00Z",
      "query_count": 12,
      "avg_latency_ms": 1450,
      "p95_latency_ms": 3200,
      "avg_confidence": 72,
      "meta_reasoning_count": 3,
      "error_count": 1
    }
  ],
  "circuit_breakers": {
    "qdrant": {"state": "closed", "failure_count": 0},
    "inference": {"state": "closed", "failure_count": 0},
    "search": {"state": "closed", "failure_count": 0}
  },
  "active_ingestion_jobs": 0
}
```

Rules:
- Empty buckets return `query_count: 0` and all other numeric fields as `0` -- NOT omitted
- `p95_latency_ms` is `0` when `query_count` is `0`
- `circuit_breakers` uses `getattr` fallback: if a circuit breaker instance is unavailable,
  return `{"state": "unknown", "failure_count": 0}`
- Time window capped: reject windows larger than `7d` with HTTP 400

### Per-Component Log Level Configuration Format

Environment variable: `LOG_LEVEL_OVERRIDES`
Format: comma-separated `module.path=LEVEL` pairs

```
LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG,backend.storage.sqlite_db=WARNING
```

Settings field:
```python
log_level_overrides: str = ""  # Comma-separated module=LEVEL pairs
```

The parsed override map is used by a custom structlog processor that filters events by
logger name. When a module has an override, its events below the configured level are
dropped via `raise structlog.DropEvent`.

Invalid level values (e.g., `backend.foo=INVALID`) are logged as a warning at startup
and skipped -- the module uses the global default instead.

### Log Event Naming Convention

Every log event MUST start with one of these 7 prefixes:

| Prefix | Applies to |
|--------|-----------|
| `http_` | `backend/api/chat.py`, `backend/api/ingest.py`, `backend/middleware.py` |
| `agent_` | `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/meta_reasoning_nodes.py` |
| `retrieval_` | `backend/retrieval/searcher.py` (non-CB events), `backend/retrieval/reranker.py` |
| `storage_` | `backend/storage/sqlite_db.py`, `backend/storage/qdrant_client.py` (non-CB events), `backend/storage/indexing.py`, `backend/storage/parent_store.py` |
| `ingestion_` | `backend/ingestion/pipeline.py`, `backend/ingestion/chunker.py`, `backend/ingestion/embedder.py` |
| `provider_` | `backend/providers/registry.py`, `backend/providers/ollama.py` |
| `circuit_` | Circuit breaker events in `searcher.py`, `qdrant_client.py`, `nodes.py` |

Rules for naming:
- Replace colons and spaces in event names with underscores: `"verify_groundedness: disabled"` -> `"agent_verify_groundedness_disabled"`
- Circuit breaker events include the service name: `"circuit_qdrant_open"`, `"circuit_searcher_open"`, `"circuit_inference_open"`
- Error-level log entries MUST include `error=type(exc).__name__` when an exception variable is in scope (FR-012)
- Non-exception warnings do NOT get an `error` field

### Current Log Event Inventory (Verified via Serena)

**backend/agent/nodes.py** (~30 events, uses `log`):
- `init_session_failed`, `invalid_intent_value`, `intent_classified`, `classify_intent_failed`
- `rewrite_query_first_attempt_failed`, `rewrite_query_fallback`, `query_analysis_fallback_used`
- `interrupting_for_clarification`, `clarification_received`
- `aggregate_answers: no valid sub-answers found`
- `verify_groundedness: disabled via settings`, `verify_groundedness: no final_response, skipping`
- `verify_groundedness: no sub_answers, skipping`, `verify_groundedness: empty context from chunks, skipping`
- `verify_groundedness: failed, graceful degradation`
- `citation_remapped`, `citation_stripped`, `validate_citations_failed`
- `summarize_history_failed`, `format_response: empty final_response, returning as-is`
- `format_response: groundedness annotations (Phase 2 -- not yet implemented)`
- Plus additional info-level events for stage completions

**backend/agent/research_nodes.py** (~13 events, uses `log`):
- `orchestrator_no_llm`, `orchestrator_llm_failed`
- `tools_node_no_messages`, `unknown_tool`, `tool_call_failed`, `tool_call_failed_after_retry`
- `dedup_filtered`, `tool_call_complete`
- `compress_context_start`, `compress_context_no_llm`, `compress_context_failed`
- `collect_answer_llm_failed`, `fallback_triggered`

**backend/agent/meta_reasoning_nodes.py** (~9 events, uses `log`):
- `alt_queries_generated`, `alt_queries_failed`
- `eval_quality_empty_chunks`, `reranker_unavailable`, `reranker_no_scores`, `reranker_failed`
- `max_attempts_reached`, `no_viable_strategy`, `uncertainty_llm_failed`

**backend/retrieval/searcher.py** (~10 events, uses `logger`):
- `circuit_breaker_open`, `circuit_breaker_opened` (CB events -> `circuit_` prefix)
- `search_skipped_no_embed_fn`, `search_all_skipped_no_embed_fn`
- `list_collections_failed`, `search_all_no_collections`
- Plus additional search completion events

**backend/retrieval/reranker.py** (~2 events, uses `logger`):
- `reranker_failed`, `rerank_complete`

**backend/storage/qdrant_client.py** (~9 events, uses `logger`):
- `qdrant_circuit_half_open`, `qdrant_circuit_open`, `qdrant_circuit_opened` (CB -> `circuit_`)
- `qdrant_connected`, `qdrant_connection_failed`
- `qdrant_collection_created`
- `qdrant_storage_circuit_half_open` (CB -> `circuit_`)
- `qdrant_storage_collection_created`, `qdrant_storage_collection_deleted`

**backend/storage/sqlite_db.py** (1 event, uses `logger`):
- `sqlite_connected`

**backend/storage/indexing.py** (2 events, uses `logger`):
- `no_chunks_to_index`, `chunks_indexed`

**backend/ingestion/pipeline.py** (~12 events, uses `logger`):
- `worker_invalid_json_line`, `job_paused_qdrant_outage`, `job_resumed_qdrant_recovered`
- Plus additional job status events

**backend/api/chat.py** (3 events, uses `logger`):
- `query_trace_write_failed`, `circuit_open_during_chat`, `chat_stream_error`

**backend/middleware.py** (2 events, uses `logger`):
- Request logging event, rate limit event

**backend/providers/registry.py** (3 events, uses `logger`):
- `default_provider_registered`, `unknown_provider_fallback`, `provider_activated`

### Logger Variable Naming

Some modules use `log`, others use `logger`. Both are valid structlog bound loggers. The
FR-011 rename does NOT require changing the variable name -- only the event string parameter.

One fix required: `backend/middleware.py` uses `logger = structlog.get_logger()` WITHOUT
`__name__`. This must be changed to `logger = structlog.get_logger(__name__)` for per-component
log level filtering to work (FR-004 depends on logger name matching).

### JSON Lines Format (FR-013)

Already satisfied by `structlog.processors.JSONRenderer()` in the processor chain. No code
changes needed. Verification: capture log output from a running instance and pipe through
`jq .` -- every line must parse as valid JSON.

### Chat Endpoint Uses NDJSON -- Not SSE

The chat endpoint uses `Content-Type: application/x-ndjson` and returns
`StreamingResponse(..., media_type="application/x-ndjson")`. There is no SSE, no
`text/event-stream`, and no `data:` prefix on events. Do not introduce any SSE
references in spec-15 code or tests.

### pathlib.Path Rule

Any new file path construction in Python code MUST use `pathlib.Path`, not `os.path.join`
or string concatenation. This applies to test fixtures (e.g., `tmp_path / "test.db"`).

### timed_app Fixture Pattern (from spec-14 memory)

When creating test fixtures that use `TestClient`, patch `backend.main.SQLiteDB` via
`main_module.settings.sqlite_path = tmp_path / "test.db"` to avoid old-schema real DB.
Also mock QdrantStorage + Reranker + HybridSearcher. This avoids
`sqlite3.OperationalError: no such column: description` from the real `data/embedinator.db`.

---

## Testing Protocol

**NEVER run pytest directly inside Claude Code.** All testing uses the external runner:

```bash
# Run a target
zsh scripts/run-tests-external.sh -n <name> <target>

# Check status (poll)
cat Docs/Tests/<name>.status        # RUNNING | PASSED | FAILED | ERROR

# Read results
cat Docs/Tests/<name>.summary       # ~20 lines, token-efficient
cat Docs/Tests/<name>.log           # full pytest output if needed
```

The script accepts ONE target -- run parallel invocations for multi-file gate checks.

### External Test Run Schedule

| Agent | Run name | Target | When |
|-------|----------|--------|------|
| A2 | `spec15-a2` | `tests/unit/test_trace_context.py` | After T016-T017 |
| A3 | `spec15-a3` | `tests/unit/api/test_metrics.py` | After T026 |
| A4 | `spec15-a4` | `tests/unit/test_component_log_levels.py` | After T033 |
| A5 | N/A | vitest (frontend) | After T041 |
| A6 | `spec15-a6` | `tests/unit/` | After T046 |
| A7 | `spec15-a7` | `tests/` | After T054 |
| A8 | `spec15-a8-full` | `tests/` | Wave 5 start (T055) |

### Wave Gates Summary

| Gate | Condition |
|------|-----------|
| Wave 1 -> Wave 2 | `Docs/Tests/spec15-a1-audit.md` exists; all target files confirmed in pre-FR state; log event inventory complete |
| Wave 2 -> Wave 3 | `spec15-a2.status = PASSED` AND `spec15-a3.status = PASSED`; no new failures |
| Wave 3 -> Wave 4 | `spec15-a4.status = PASSED` AND A5 vitest passes; no new failures |
| Wave 4 -> Wave 5 | `spec15-a6.status = PASSED` AND `spec15-a7.status = PASSED`; no new failures |
| Final | `spec15-a8-full.status = PASSED`; all 7 SCs verified; pre-existing failure count = 39 |

### New Test File Locations

```
tests/
  unit/
    test_trace_context.py              # A2 -- FR-001, FR-002, FR-003, FR-014
    test_component_log_levels.py       # A4 -- FR-004
    api/
      test_metrics.py                  # A3 -- FR-005, FR-006, FR-007, FR-008
  integration/
    (no new integration tests -- SC verification done by A8 in final report)
```

---

## Dependencies

### Libraries (all already installed -- no new dependencies)

- `structlog >= 24.0` -- structured JSON logging with contextvars support
- `recharts` (frontend) -- already used for LatencyChart and ConfidenceDistribution

### Spec Dependencies

| Spec | What This Spec Uses From It |
|------|-----------------------------|
| Spec 7 (Storage Architecture) | `query_traces` table schema, `SQLiteDB` class, `get_query_traces_by_timerange()` |
| Spec 8 (API Reference) | Health endpoint, traces API, REST route structure |
| Spec 9 (Next.js Frontend) | Observability page, dashboard components, recharts patterns |
| Spec 12 (Error Handling) | Error hierarchy for error classification in metrics and FR-012 |
| Spec 13 (Security Hardening) | Middleware layer, `_strip_sensitive_fields` processor, `_configure_logging()` |
| Spec 14 (Performance Budgets) | `stage_timings_json` column, `ConversationState.stage_timings` field |

---

## Appendix: get_query_traces_by_timerange() Current State

The existing method SELECT does NOT include `provider_name` or `stage_timings_json`:

```python
async def get_query_traces_by_timerange(self, start_ts, end_ts, limit=1000):
    cursor = await self.db.execute(
        """SELECT id, session_id, query, sub_questions_json, collections_searched,
                  chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
                  meta_reasoning_triggered, latency_ms, llm_model, embed_model,
                  confidence_score, created_at
           FROM query_traces WHERE created_at >= ? AND created_at <= ?
           ORDER BY created_at DESC LIMIT ?""",
        (start_ts, end_ts, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]
```

A3 must update this SELECT to include `provider_name, stage_timings_json` so the metrics
endpoint can use this method. Alternatively, A3 can write a dedicated aggregation SQL query
for the metrics endpoint. The dedicated query approach is preferred for performance since it
avoids fetching all rows into Python:

```sql
SELECT
    strftime('%Y-%m-%dT%H:00:00Z', created_at) AS bucket,
    COUNT(*) AS query_count,
    AVG(latency_ms) AS avg_latency_ms,
    AVG(confidence_score) AS avg_confidence,
    SUM(CASE WHEN meta_reasoning_triggered = 1 THEN 1 ELSE 0 END) AS meta_reasoning_count
FROM query_traces
WHERE created_at >= ? AND created_at <= ?
GROUP BY bucket
ORDER BY bucket ASC
```

Note: P95 latency cannot be computed in SQLite directly (no `PERCENTILE_CONT`). Options:
1. Fetch all `latency_ms` values per bucket and compute in Python
2. Use an approximation: `MAX(latency_ms)` as upper bound
3. Fetch all traces in the window (up to `limit`), group and compute in Python

Option 3 is recommended for correctness and simplicity, since SC-003 allows up to 10,000
traces and Python can sort/compute P95 efficiently for that volume.
