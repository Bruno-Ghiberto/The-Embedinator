# Tasks: Observability Layer

**Input**: Design documents from `/specs/015-observability/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/metrics-api.md

**Tests**: Included — spec defines 7 success criteria (SC-001 through SC-007) and the plan specifies 4 new test files.

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Pre-Flight Audit)

**Purpose**: Verify codebase state before any modifications. Confirm what exists and what needs to change.

- [ ] T001 Read `specs/015-observability/spec.md` fully — confirm 14 FRs, 7 SCs, 5 user stories
- [ ] T002 Read `Docs/PROMPTS/spec-15-observability/15-plan.md` fully — confirm wave structure, task assignments, research decisions
- [ ] T003 [P] Verify `backend/middleware.py` `TraceIDMiddleware.dispatch()` does NOT currently call `bind_contextvars` or `clear_contextvars`; document exact insertion points
- [ ] T004 [P] Verify `backend/main.py` `_configure_logging()` uses `merge_contextvars` processor; confirm no per-component log level logic exists
- [ ] T004a [P] Verify FR-013 (JSON Lines format): confirm `_configure_logging()` uses `structlog.processors.JSONRenderer()` as the final processor (it does — verified in research). Write a smoke assertion in `tests/unit/test_trace_context.py`: capture 5 log entries via `capsys`, assert each line is independently parseable with `json.loads()` and contains an `"event"` key. This verifies FR-013 for the test environment.
- [ ] T005 [P] Verify `backend/config.py` `Settings` has `log_level: str = "INFO"` but NO per-component override fields
- [ ] T006 [P] Verify `backend/api/traces.py` has `list_traces`, `get_trace`, `system_stats` but NO `metrics` endpoint
- [ ] T007 [P] Verify `frontend/components/StageTimingsChart.tsx` does NOT exist; verify `frontend/hooks/useMetrics.ts` does NOT exist
- [ ] T008 [P] Verify `backend/ingestion/pipeline.py` `ingest_file()` does NOT generate or bind a trace ID at entry
- [ ] T009 [P] Verify `backend/api/chat.py` — confirm `session_id` is NOT currently bound to structlog contextvars
- [ ] T010 Perform full log event inventory: search all backend files for `log.(info|warning|error|debug)(` and `logger.(info|warning|error|debug)(` patterns; document every event name per file with current name and target prefixed name

**Checkpoint**: Audit complete — all pre-FR state confirmed. Log event inventory documented for Phase 7.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Fix prerequisites that block multiple user stories.

**CRITICAL**: US3 (per-component log levels) and US5 (log naming) depend on loggers binding `component=__name__`.

**IMPORTANT — structlog limitation**: `PrintLoggerFactory` silently drops positional args from `get_logger(__name__)`, so `_logger_name` is never available in processor `event_dict`. The only reliable mechanism is `structlog.get_logger().bind(component=__name__)`, which stores the module name as a permanent key in every emitted event.

- [ ] T011 Fix `backend/middleware.py` logger: change `structlog.get_logger()` (bare) to `structlog.get_logger().bind(component=__name__)` (R1 prerequisite — `bind(component=__name__)` stores the module name in `event_dict` as `"component"` key, which the `_filter_by_component` processor reads; `get_logger(__name__)` positional arg is silently dropped by `PrintLoggerFactory` and must NOT be used for filtering)
- [ ] T012 Migrate ALL backend modules to use `structlog.get_logger().bind(component=__name__)` pattern instead of `structlog.get_logger(__name__)` or bare `structlog.get_logger()`. The `bind()` call stores `component` as a permanent context key visible to all processors. Modules to update: `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/meta_reasoning_nodes.py`, `backend/retrieval/searcher.py`, `backend/retrieval/reranker.py`, `backend/storage/sqlite_db.py`, `backend/storage/qdrant_client.py`, `backend/storage/indexing.py`, `backend/ingestion/pipeline.py`, `backend/providers/registry.py`, `backend/api/chat.py`, `backend/api/traces.py`

**Checkpoint**: Foundation ready — all loggers bind `component=__name__`. `_filter_by_component` can now match against the `"component"` key in `event_dict`. User story implementation can now begin.

---

## Phase 3: User Story 1 - End-to-End Request Tracing (Priority: P1)

**Goal**: Every log entry produced during an HTTP request or background ingestion task automatically includes a `trace_id` field. Session ID also propagates during chat requests. Context variables cleaned up after each request.

**Independent Test**: Send a chat query, capture `X-Trace-ID` header, search logs for that trace ID. Every entry from middleware, agent, storage, and retrieval must include the matching `trace_id`.

**FRs covered**: FR-001, FR-002, FR-003, FR-014
**SCs covered**: SC-001, SC-002

### Tests for User Story 1

- [ ] T013 [P] [US1] Write `tests/unit/test_trace_context.py`: test that `TraceIDMiddleware` binds `trace_id` to structlog contextvars and clears them in `finally` block (FR-001, FR-003)
- [ ] T014 [P] [US1] Write test in `tests/unit/test_trace_context.py`: test that 2 concurrent requests produce isolated trace IDs with no cross-contamination (SC-002)
- [ ] T015 [P] [US1] Write test in `tests/unit/test_trace_context.py`: test that `session_id` appears in structlog context during chat request processing (FR-002)
- [ ] T016 [P] [US1] Write test in `tests/unit/test_trace_context.py`: test that `IngestionPipeline.ingest_file()` generates and binds a fresh trace ID at entry, and clears contextvars at exit (FR-014)

### Implementation for User Story 1

- [ ] T017 [US1] In `backend/middleware.py` `TraceIDMiddleware.dispatch()`: add `structlog.contextvars.bind_contextvars(trace_id=trace_id)` after `request.state.trace_id = trace_id`; wrap `call_next` + response header in `try/finally`; add `structlog.contextvars.clear_contextvars()` in `finally` (FR-001, FR-003)
- [ ] T018 [US1] Verify `import structlog` in `backend/middleware.py` covers `structlog.contextvars` (it does — `structlog.contextvars` is a submodule accessible via import)
- [ ] T019 [US1] In `backend/api/chat.py`: at the point where `session_id` is first extracted from `ChatRequest`, add `structlog.contextvars.bind_contextvars(session_id=session_id)` (FR-002)
- [ ] T020 [US1] In `backend/ingestion/pipeline.py` `ingest_file()`: at method entry, add `import uuid` + `ingestion_trace_id = str(uuid.uuid4())` + `structlog.contextvars.bind_contextvars(trace_id=ingestion_trace_id)`; wrap entire method body in `try/finally` with `structlog.contextvars.clear_contextvars()` in `finally` (FR-014)
- [ ] T021 [US1] Run tests: `zsh scripts/run-tests-external.sh -n spec15-us1 tests/unit/test_trace_context.py` — poll status, read summary, confirm PASSED

**Checkpoint**: US1 complete — trace ID and session ID propagate automatically through all log entries. Background ingestion has its own trace ID.

---

## Phase 4: User Story 2 - Time-Series Metrics Dashboard (Priority: P2)

**Goal**: A `GET /api/metrics` endpoint returns time-bucketed trend data (latency, confidence, meta-reasoning, errors) with circuit breaker state and active ingestion job count.

**Independent Test**: Run several chat queries, then request `GET /api/metrics?window=24h` and verify response contains properly bucketed data per the metrics-api contract.

**FRs covered**: FR-005, FR-006, FR-007, FR-008
**SCs covered**: SC-003, SC-007 (empty database edge case)

### Tests for User Story 2

- [ ] T027a [US2] In `backend/agent/schemas.py`: add three Pydantic models for the metrics endpoint (constitution requires Pydantic for all API response schemas):
  - `CircuitBreakerSnapshot(BaseModel)`: fields `state: Literal["closed", "open", "unknown"]`, `failure_count: int`
  - `MetricsBucket(BaseModel)`: fields `timestamp: str`, `query_count: int`, `avg_latency_ms: int`, `p95_latency_ms: int`, `avg_confidence: int`, `meta_reasoning_count: int`, `error_count: int`
  - `MetricsResponse(BaseModel)`: fields `window: str`, `bucket_size: str`, `buckets: list[MetricsBucket]`, `circuit_breakers: dict[str, CircuitBreakerSnapshot]`, `active_ingestion_jobs: int`

- [ ] T022 [P] [US2] Write `tests/unit/api/test_metrics.py`: test `GET /api/metrics` returns 200 with valid JSON matching `MetricsResponse` schema (FR-005)
- [ ] T023 [P] [US2] Write test: `GET /api/metrics?window=1h` returns 5-minute buckets; `?window=24h` returns hourly buckets; `?window=7d` returns daily buckets (FR-006)
- [ ] T024 [P] [US2] Write test: invalid window value (e.g., `?window=30d`) returns 400 with error envelope
- [ ] T025 [P] [US2] Write test: empty database returns empty buckets with zero counts, NOT an error (SC-007 edge case)
- [ ] T026 [P] [US2] Write test: circuit breaker state is present in response with 3 keys: `qdrant`, `inference`, `search` (FR-007)
- [ ] T027 [P] [US2] Write test: `active_ingestion_jobs` count is present in response (FR-008)

### Implementation for User Story 2

- [ ] T028 [US2] In `backend/api/traces.py`: add `GET /api/metrics` route handler with signature `async def metrics(window: str = Query(default="24h"), ...)`. Valid values: `"1h"`, `"24h"`, `"7d"`. For invalid values, use the spec-12 error envelope already handled by the global exception handler in `backend/main.py`: `raise HTTPException(status_code=400, detail={"code": "VALIDATION_ERROR", "message": "Invalid window. Must be one of: 1h, 24h, 7d", "details": None})`. Return type annotation: `-> MetricsResponse` (from T027a). (FR-005, FR-006)
- [ ] T029 [US2] Implement time-bucketed aggregation in `backend/api/traces.py`: compute `start_ts` by flooring `(now - window_duration)` to nearest bucket boundary (e.g., for 5m buckets: `floor(ts / 300) * 300`); query `get_query_traces_by_timerange(start_ts, now_ts)`; group results into buckets per R2 granularity mapping; for each bucket compute `query_count`, `avg_latency_ms`, `p95_latency_ms` (sort + index `ceil(0.95 * count) - 1`), `avg_confidence` (round to nearest integer via `round(sum/count)`), `meta_reasoning_count`, `error_count`. Include `bucket_size` in the response using `bucket_size_map = {"1h": "5m", "24h": "1h", "7d": "1d"}` — this is a required field in `MetricsResponse` per the contract.
- [ ] T030 [US2] Handle empty buckets: fill missing time slots with zero-count buckets so response always has expected number of buckets per window. After filling all slots, sort the bucket list ascending by timestamp: `buckets.sort(key=lambda b: b["timestamp"])`. Contract invariant: "Buckets are ordered ascending by `timestamp`."
- [ ] T031 [US2] Add circuit breaker state to metrics response (FR-007). Contract defines exactly 3 keys: `qdrant`, `inference`, `search`. Use this helper pattern per R3 — `None` instance → `"unknown"` state:

  ```python
  def _get_cb_state(instance, open_attr="_circuit_open", count_attr="_failure_count"):
      if instance is None:
          return {"state": "unknown", "failure_count": 0}
      return {
          "state": "open" if getattr(instance, open_attr, False) else "closed",
          "failure_count": getattr(instance, count_attr, 0),
      }

  import backend.agent.nodes as nodes_module
  inf_open = getattr(nodes_module, "_inf_circuit_open", None)
  circuit_breakers = {
      "qdrant":    _get_cb_state(getattr(request.app.state, "qdrant", None)),
      "search":    _get_cb_state(getattr(request.app.state, "hybrid_searcher", None)),
      "inference": {"state": "unknown", "failure_count": 0} if inf_open is None
                   else {"state": "open" if inf_open else "closed",
                         "failure_count": getattr(nodes_module, "_inf_failure_count", 0)},
  }
  ```

  NOTE: Do NOT expose `qdrant_storage` as a 4th key — the contract mandates exactly 3. `getattr()` with `None` sentinel correctly maps to `"unknown"` (not `"closed"`).
- [ ] T032 [US2] Add active ingestion job count to response (FR-008): query `SELECT COUNT(*) FROM ingestion_jobs WHERE status = 'processing'` via `db.db.execute()` in `backend/api/traces.py`
- [ ] T033 [US2] Run tests: `zsh scripts/run-tests-external.sh -n spec15-us2 tests/unit/api/test_metrics.py` — poll status, read summary, confirm PASSED

**Checkpoint**: US2 complete — metrics endpoint returns time-bucketed trend data with circuit breaker state and ingestion job count.

---

## Phase 5: User Story 3 - Per-Component Log Level Control (Priority: P3)

**Goal**: Developers can override log level for specific modules via `LOG_LEVEL_OVERRIDES` environment variable without changing code.

**Independent Test**: Set `LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG`, start the app, send a query, and verify only the reranker produces debug-level entries.

**FRs covered**: FR-004
**SCs covered**: SC-004, SC-007 (invalid override fallback)

### Tests for User Story 3

- [ ] T034 [P] [US3] Write `tests/unit/test_component_log_levels.py`: test that with no overrides, all components use global log level
- [ ] T035 [P] [US3] Write test: with `LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG`, reranker debug logs appear while other modules at INFO do not emit debug
- [ ] T036 [P] [US3] Write test: invalid level value in override (e.g., `backend.foo=INVALID`) falls back to global level and logs a warning (SC-007)

### Implementation for User Story 3

- [ ] T037 [US3] In `backend/config.py` `Settings`: add `log_level_overrides: str = ""` field (env var: `LOG_LEVEL_OVERRIDES`); format is comma-separated `module=LEVEL` pairs per R1
- [ ] T038 [US3] In `backend/main.py` `_configure_logging()`: after `structlog.configure()`, parse `settings.log_level_overrides` string into dict `{module_name: level_int}`; for invalid level values, log a warning and skip
- [ ] T039 [US3] Implement `_filter_by_component(logger, method_name, event_dict)` processor in `backend/main.py`:
  - Get component name: `component = event_dict.get("component", "")` (key populated by T011/T012 via `.bind(component=__name__)` — NOT `_logger_name`, which is never present with `PrintLoggerFactory`)
  - Look up override: `override_level = override_map.get(component)` — if `None`, return `event_dict` unchanged (no filtering for unregistered components)
  - Compare levels: use `method_name` param (e.g., `"debug"`, `"info"`, `"warning"`, `"error"`) to get event level integer via `logging.getLevelName(method_name.upper())`; if event level < override_level, `raise structlog.DropEvent()`; otherwise return `event_dict`
  - Position: insert AFTER `structlog.contextvars.merge_contextvars` and BEFORE `structlog.processors.add_log_level` in the processor chain in `_configure_logging()`
  - Note: use `method_name` for level comparison — do NOT use `event_dict.get("level")` as `add_log_level` hasn't run yet at this position
- [ ] T040 [US3] Run tests: `zsh scripts/run-tests-external.sh -n spec15-us3 tests/unit/test_component_log_levels.py` — poll status, read summary, confirm PASSED

**Checkpoint**: US3 complete — per-component log level overrides work via environment variable.

---

## Phase 6: User Story 4 - Stage Timings Visualization (Priority: P3)

**Goal**: The trace detail view on `/observability` shows a visual breakdown of per-stage latency when stage timing data is present. Hidden gracefully for legacy traces.

**Independent Test**: Process a chat query, navigate to trace detail, verify a stage timing chart renders showing time per stage.

**FRs covered**: FR-009, FR-010
**SCs covered**: SC-005

### Implementation for User Story 4

- [ ] T041 [P] [US4] In `frontend/lib/types.ts`: add `stage_timings?: Record<string, { duration_ms: number; failed?: boolean }>` field to `QueryTraceDetail` interface
- [ ] T042 [P] [US4] Create `frontend/components/StageTimingsChart.tsx`: horizontal bar chart using recharts; props: `timings: Record<string, { duration_ms: number; failed?: boolean }>`; each bar = one stage, length proportional to `duration_ms`, failed stages in red; use dynamic import with `{ ssr: false }` for recharts; use Tailwind for layout (FR-009)
- [ ] T043 [P] [US4] Create `frontend/hooks/useMetrics.ts`: SWR hook wrapping `GET /api/metrics` with configurable `window` parameter; type response as `MetricsResponse`
- [ ] T044 [US4] In `frontend/components/TraceTable.tsx` `ExpandedRow`: after existing detail sections, conditionally render `StageTimingsChart` — render only when `detail.stage_timings` exists and is non-empty (FR-009); hide completely when absent or empty (FR-010)
- [ ] T045 [US4] In `frontend/app/observability/page.tsx`: import and render a metrics trends section using `useMetrics` hook data; display latency trend and confidence trend from time-series buckets

**Checkpoint**: US4 complete — stage timings chart renders in trace detail view; hidden for legacy traces.

---

## Phase 7: User Story 5 - Consistent Log Event Naming (Priority: P4)

**Goal**: ALL log events across the entire backend codebase follow a consistent prefix convention. Error-level log entries include exception class name.

**Independent Test**: Exercise all major code paths, capture log output, verify every `event` field starts with one of 7 prefixes. No legacy unprefixed names remain.

**FRs covered**: FR-011, FR-012, FR-013
**SCs covered**: SC-006

### Implementation for User Story 5 — Agent Modules

- [ ] T046 [P] [US5] In `backend/agent/nodes.py`: rename ALL ~30 log events to use `agent_` prefix; examples: `"init_session_failed"` → `"agent_init_session_failed"`, `"intent_classified"` → `"agent_intent_classified"`, `"verify_groundedness: disabled via settings"` → `"agent_verify_groundedness_disabled"` (replace colons/spaces with underscores)
- [ ] T047 [P] [US5] In `backend/agent/nodes.py`: for all `log.warning()` and `log.error()` calls related to exceptions, add `error=type(exc).__name__` kwarg (FR-012); do NOT add `error` field to non-exception warning logs
- [ ] T048 [P] [US5] In `backend/agent/research_nodes.py`: rename ALL ~13 log events to use `agent_` prefix; examples: `"orchestrator_no_llm"` → `"agent_orchestrator_no_llm"`, `"tool_call_failed"` → `"agent_tool_call_failed"`; add `error=type(exc).__name__` to exception-related log calls (FR-012)
- [ ] T049 [P] [US5] In `backend/agent/meta_reasoning_nodes.py`: rename ALL ~9 log events to use `agent_` prefix; examples: `"alt_queries_generated"` → `"agent_alt_queries_generated"`, `"reranker_unavailable"` → `"agent_reranker_unavailable"`; add `error=type(exc).__name__` to exception log calls (FR-012)

### Implementation for User Story 5 — Retrieval Modules

- [ ] T050 [P] [US5] In `backend/retrieval/searcher.py`: rename log events; circuit breaker events get `circuit_` prefix: `"circuit_breaker_open"` → `"circuit_searcher_open"`; search events get `retrieval_` prefix: `"search_skipped_no_embed_fn"` → `"retrieval_search_skipped_no_embed_fn"`; add `error` fields to exception logs (FR-012)
- [ ] T051 [P] [US5] In `backend/retrieval/reranker.py`: rename log events with `retrieval_` prefix: `"reranker_failed"` → `"retrieval_reranker_failed"`, `"rerank_complete"` → `"retrieval_rerank_complete"`; add `error=type(exc).__name__` to the failed call (FR-012)

### Implementation for User Story 5 — Storage Modules

- [ ] T052 [P] [US5] In `backend/storage/qdrant_client.py`: rename log events; circuit breaker events get `circuit_` prefix: `"qdrant_circuit_half_open"` → `"circuit_qdrant_half_open"`, `"qdrant_circuit_open"` → `"circuit_qdrant_open"`; connection/CRUD events get `storage_` prefix: `"qdrant_connected"` → `"storage_qdrant_connected"` (FR-011)
- [ ] T053 [P] [US5] In `backend/storage/sqlite_db.py`: rename `"sqlite_connected"` → `"storage_sqlite_connected"` (FR-011)
- [ ] T054 [P] [US5] In `backend/storage/indexing.py`: rename `"no_chunks_to_index"` → `"storage_no_chunks_to_index"`, `"chunks_indexed"` → `"storage_chunks_indexed"` (FR-011)

### Implementation for User Story 5 — Ingestion, API, Provider Modules

- [ ] T055 [P] [US5] In `backend/ingestion/pipeline.py`: rename ALL ~12 log events with `ingestion_` prefix: `"worker_invalid_json_line"` → `"ingestion_worker_invalid_json_line"`, `"job_paused_qdrant_outage"` → `"ingestion_job_paused_qdrant_outage"`; add `error=type(exc).__name__` to error-level calls (FR-011, FR-012)
- [ ] T056 [P] [US5] In `backend/api/chat.py`: rename events with `http_` prefix: `"query_trace_write_failed"` → `"http_query_trace_write_failed"`, `"circuit_open_during_chat"` → `"http_circuit_open_during_chat"`; add `error` fields where applicable (FR-011, FR-012)
- [ ] T057 [P] [US5] In `backend/middleware.py`: rename log events with `http_` prefix (FR-011)
- [ ] T058 [P] [US5] In `backend/providers/registry.py`: rename events with `provider_` prefix: `"default_provider_registered"` → `"provider_default_registered"`, `"unknown_provider_fallback"` → `"provider_unknown_fallback"` (FR-011)

### Test Assertion Updates for User Story 5

- [ ] T059 [US5] Search all test files for string assertions on old log event names (e.g., `"intent_classified"`, `"reranker_failed"`); update any matching assertions to use the new prefixed names
- [ ] T060 [US5] Run full test suite: `zsh scripts/run-tests-external.sh -n spec15-us5 tests/` — poll status, read summary, confirm PASSED with no regressions

**Checkpoint**: US5 complete — ALL log events use prefix convention. No legacy unprefixed names remain.

---

## Phase 8: Polish & Final Validation

**Purpose**: Full regression testing and success criteria verification.

- [ ] T061 Run full test suite: `zsh scripts/run-tests-external.sh -n spec15-final tests/` — poll status, confirm PASSED; pre-existing failure count must remain at 39
- [ ] T062 Verify SC-001: send an HTTP request, capture `X-Trace-ID` header, inspect log entries from at least 3 subsystems (agent, storage, retrieval) — all must contain matching `trace_id`
- [ ] T063 Verify SC-002: write/run a test sending 5 concurrent requests; confirm each request's logs contain only its own trace ID
- [ ] T064 Verify SC-003: confirm `GET /api/metrics?window=24h` responds within 500ms (may be SKIP if load environment unavailable)
- [ ] T065 Verify SC-004: test that `LOG_LEVEL_OVERRIDES=backend.retrieval.reranker=DEBUG` changes the reranker's effective log level
- [ ] T066 Verify SC-005: confirm StageTimingsChart renders for traces with timing data and is hidden for traces without
- [ ] T067 Verify SC-006: search all backend files for log events; confirm every event name starts with one of the 7 defined prefixes; no legacy unprefixed names remain
- [ ] T068 Verify SC-007: confirm empty database returns empty buckets (not errors), malformed stage timing data is skipped (not crashes), invalid log level overrides fall back with warning
- [ ] T069 Write final validation report documenting all 7 SCs with PASS/SKIP/FAIL status, total new test count, and pre-existing failure count

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 audit completion — BLOCKS US3 and US5
- **US1 (Phase 3)**: Depends on Phase 1 only — can start after audit, parallel with Phase 2
- **US2 (Phase 4)**: Depends on Phase 1 only — can start after audit, parallel with US1
- **US3 (Phase 5)**: Depends on Phase 2 (logger `__name__` fix) — cannot start until foundational is done
- **US4 (Phase 6)**: No backend dependencies — can start after Phase 1, parallel with any backend work
- **US5 (Phase 7)**: Depends on Phase 2 (logger `__name__` fix) — should run after US1-US4 to avoid merge conflicts
- **Validation (Phase 8)**: Depends on ALL user stories being complete

### User Story Dependencies

- **US1 (P1)**: Independent — can start after audit
- **US2 (P2)**: Independent — can start after audit; benefits from US1 (trace IDs in metrics) but not required
- **US3 (P3)**: Depends on Phase 2 foundational logger fix
- **US4 (P3)**: Independent — frontend-only, no backend dependencies
- **US5 (P4)**: Depends on Phase 2 foundational logger fix; should run LAST among user stories to avoid rename conflicts with other user stories modifying same files

### Within Each User Story

- Tests written first (where applicable), confirmed to fail before implementation
- Implementation tasks follow test structure
- External test run confirms PASSED before marking story complete
- Commit after each task or logical group

### Parallel Opportunities

- **Phase 1**: T003-T009 can all run in parallel (reading different files)
- **Phase 3 + Phase 4**: US1 and US2 can run in parallel (different files)
- **Phase 5 + Phase 6**: US3 (backend) and US4 (frontend) can run in parallel
- **Phase 7**: T046-T058 can ALL run in parallel (each modifies a different file)
- **Within US2**: T022-T027 (tests) can run in parallel; T028-T032 are sequential

---

## Parallel Example: User Story 5 (Log Event Naming)

```bash
# Launch all file-scoped renames in parallel (each touches a different file):
Agent A: T046 + T047  # backend/agent/nodes.py
Agent B: T048          # backend/agent/research_nodes.py
Agent C: T049          # backend/agent/meta_reasoning_nodes.py
Agent D: T050          # backend/retrieval/searcher.py
Agent E: T051          # backend/retrieval/reranker.py
Agent F: T052          # backend/storage/qdrant_client.py
Agent G: T053 + T054   # backend/storage/sqlite_db.py + indexing.py
Agent H: T055-T058     # ingestion, API, middleware, providers

# After all complete, run T059 (assertion updates) then T060 (full test suite)
```

---

## Parallel Example: US1 + US2 Concurrent

```bash
# These two user stories modify different files and can run simultaneously:
Agent A (US1): T017 → T018 → T019 → T020 → T021
  Files: middleware.py, chat.py, pipeline.py

Agent B (US2): T027a → T028 → T029 → T030 → T031 → T032 → T033
  Files: schemas.py (Pydantic models), traces.py, sqlite_db.py (different method from US1)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Audit (T001-T010)
2. Complete Phase 2: Foundational (T011-T012)
3. Complete Phase 3: US1 - Trace ID Propagation (T013-T021)
4. **STOP and VALIDATE**: Run `zsh scripts/run-tests-external.sh -n mvp tests/` — confirm trace IDs propagate
5. This alone delivers the highest-value observability improvement

### Incremental Delivery

1. Setup + Foundational → Loggers fixed
2. Add US1 (Trace propagation) → Test → Deploy (MVP!)
3. Add US2 (Metrics endpoint) → Test → Deploy
4. Add US3 + US4 in parallel (Log levels + Stage chart) → Test → Deploy
5. Add US5 (Log naming) → Full regression → Deploy
6. Each story adds value without breaking previous stories

### Agent Teams Strategy (from 15-plan.md)

With 5 waves and 8 agents:

- **Wave 1 (A1)**: Phase 1 audit — sequential
- **Wave 2 (A2 + A3)**: US1 + US2 in parallel
- **Wave 3 (A4 + A5)**: US3 + US4 in parallel
- **Wave 4 (A6 + A7)**: US5 — agent module renames + storage/API renames in parallel
- **Wave 5 (A8)**: Phase 8 validation — sequential

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- NEVER run pytest inside Claude Code — always use `zsh scripts/run-tests-external.sh`
- Pre-existing failure count must remain at 39 throughout implementation
- FR-013 (JSON Lines format) is satisfied by structlog's `JSONRenderer`; verification test added as T004a in Phase 1
- The `get_query_traces_by_timerange()` SELECT in `sqlite_db.py` may need updating to include `provider_name` and `stage_timings_json` columns if the metrics endpoint needs them (verify during T029)
