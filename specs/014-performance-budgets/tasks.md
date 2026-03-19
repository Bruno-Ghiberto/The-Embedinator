# Tasks: Performance Budgets and Pipeline Instrumentation

**Input**: Design documents from `/specs/014-performance-budgets/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Agent Teams**: This spec uses 3 waves with 4 agents. Read `Docs/PROMPTS/spec-14-performance/14-plan.md`
for the full orchestration protocol before spawning any agents.

**Testing**: ALL tests use the external runner — NEVER run pytest directly inside Claude Code:
```bash
zsh scripts/run-tests-external.sh -n <name> <target>
cat Docs/Tests/<name>.status    # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/<name>.summary   # ~20 lines, token-efficient
```

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete-task dependencies)
- **[Story]**: User story this task belongs to (US1–US4)
- All file paths are repository-relative

---

## Phase 1: Setup

**Purpose**: No new project structure needed. This phase verifies tooling and confirms the
pre-implementation state of all target files before any modification.

- [X] T001 Read `Docs/PROMPTS/spec-14-performance/14-plan.md` — confirm Agent Teams protocol, wave structure, and all 35 agent tasks before spawning any agent
- [X] T002 Read `specs/014-performance-budgets/spec.md` — confirm 8 FRs and 8 SCs; note that FR-005 and FR-008 are the only production code changes
- [X] T003 Confirm `tests/integration/test_performance.py` exists and contains exactly 2 passing tests (`test_parent_retrieval_latency_target`, `test_search_latency_target`) before any modification

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pre-flight audit verifying the exact pre-implementation state of all 5 target
production files. No code is written in this phase. This audit report is the Wave 1 gate
condition — Wave 2 cannot start until it is complete.

**⚠️ CRITICAL**: The schema migration (adding `stage_timings_json TEXT` to `query_traces`) is
the key foundational change. It must happen before storage tests can be written or run.
The A1 audit (T004–T010) must complete before A2 and A3 (Wave 2) spawn.

- [X] T004 Spawn Wave 1 agent: `Agent(subagent_type="quality-engineer", model="opus", prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A1-audit.md FIRST, then execute all assigned tasks")`
- [X] T005 Wait for `Docs/Tests/spec14-a1-audit.md` to exist — poll `cat Docs/Tests/spec14-a1-audit.md` until the file appears (non-zero exit means not yet written)
- [X] T006 Read `Docs/Tests/spec14-a1-audit.md` — confirm overall verdict is PASS; confirm `stage_timings_json` column absent, `ConversationState` has no `stage_timings` field, `create_query_trace()` has 15 parameters, `get_trace()` SELECT has no `stage_timings_json`
- [X] T007 [P] Skip if A1 audit report shows all insertion points — A1 already documented these. If A1's report is incomplete or shows discrepancies, read `backend/agent/state.py` to confirm exact line number of `iteration_count` (A2's insertion point)
- [X] T008 [P] Skip if A1 audit report is complete — only read `backend/storage/sqlite_db.py` lines 429–461 if A1 reported a discrepancy in the `create_query_trace()` signature
- [X] T009 [P] Skip if A1 audit report is complete — only read `backend/api/chat.py` lines 130–200 if A1 reported a discrepancy in the `final_state` / `create_query_trace()` lines
- [X] T010 [P] Skip if A1 audit report is complete — only read `backend/api/traces.py` lines 75–130 if A1 reported a discrepancy in the SELECT or response dict structure

**Checkpoint**: Audit report exists and shows PASS. All insertion points documented. Wave 2 may now spawn.

---

## Phase 3: User Story 1 — Query Response Time Verification (Priority: P1) 🎯 MVP

**Goal**: Verify the system's existing configuration already meets the defined latency budgets for
simple factoid queries (< 1.5 s first token) and complex analytical queries (< 6 s first token).
No production code changes required — this phase adds benchmark tests only.

**Independent Test**: Run `zsh scripts/run-tests-external.sh -n spec14-us1 tests/integration/test_performance.py`
and confirm new SC-001 and SC-002 benchmark tests pass (or are marked `@pytest.mark.skip` with the
verification procedure documented if live inference is unavailable in the test environment).

### Implementation for User Story 1

- [ ] T011 [US1] In `tests/integration/test_performance.py`: add `test_simple_query_first_token_latency()` — submits a factoid query against a pre-loaded collection, measures time to first NDJSON chunk event, asserts < 1500 ms (SC-001); mark `@pytest.mark.integration` with a comment explaining reference-hardware-only requirement
- [ ] T012 [US1] In `tests/integration/test_performance.py`: add `test_complex_query_first_token_latency()` — submits an analytical multi-sub-question query, measures time to first NDJSON chunk event, asserts < 6000 ms (SC-002); mark `@pytest.mark.integration`
- [ ] T013 [US1] Read `backend/config.py` — verify performance-critical defaults are set: `top_k_retrieval`, `reranker_top_k`, `embed_batch_size`; if any are absent, do NOT add them (config is complete from spec-06); document the verified values in a comment in the test file

**Checkpoint**: SC-001 and SC-002 have corresponding benchmark tests. Tests pass on reference hardware or are marked skip with documented verification procedure.

---

## Phase 4: User Story 2 — Per-Stage Timing Visibility (Priority: P2) 🔑 Primary Engineering

**Goal**: Every chat query trace record contains a per-stage timing breakdown in `stage_timings_json`,
covering at minimum 5 always-present stages plus any conditional stages that executed. The data is
accessible via `GET /api/traces/{id}` without requiring direct database access.

**Independent Test**: Run a query, fetch the trace via `GET /api/traces/{trace-id}`, and assert that
`response["stage_timings"]` is a dict with at least 5 keys (`intent_classification`, `embedding`,
`retrieval`, `ranking`, `answer_generation`), each containing a numeric `duration_ms`. Legacy traces
must still return `"stage_timings": {}`.

### Wave 2 Parallel Spawn (A2 + A3)

- [X] T014 [P] [US2] Spawn Wave 2 Agent A2: `Agent(subagent_type="python-expert", model="sonnet", prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A2-state-nodes.md FIRST, then execute all assigned tasks")`
- [X] T015 [P] [US2] Spawn Wave 2 Agent A3: `Agent(subagent_type="python-expert", model="sonnet", prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A3-storage-api.md FIRST, then execute all assigned tasks")`

### A2 Implementation — State and Nodes (backend/agent/)

- [X] T016 [P] [US2] In `backend/agent/state.py`: add `stage_timings: dict` as the last field of `ConversationState` TypedDict, after `iteration_count`; add inline comment `# FR-005: per-stage timing data accumulated by nodes`
- [X] T017 [P] [US2] In `backend/agent/nodes.py` `classify_intent()`: add `_t0 = time.perf_counter()` at function entry; after LLM call, merge `state.get("stage_timings", {})` and add `"intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)}`; wrap in try/except to add `"failed": True` on exception before re-raise
- [X] T018 [US2] In `backend/agent/nodes.py`: identify the correct node for the embedding call (read code to locate `HybridSearcher` invocation or query embedding); add timing for `"embedding"` stage using same pattern as T017
- [X] T019 [US2] In `backend/agent/nodes.py`: instrument the retrieval stage (`HybridSearcher.search()` call); record as `"retrieval"` stage
- [X] T020 [US2] In `backend/agent/nodes.py`: instrument the ranking stage (cross-encoder reranker call); record as `"ranking"` stage
- [X] T021 [US2] In `backend/agent/nodes.py`: instrument the answer generation stage (LLM call producing `final_response`); record as `"answer_generation"` stage
- [X] T022 [US2] In `backend/agent/nodes.py` `verify_groundedness()`: add timing for `"grounded_verification"` stage — this is conditional and only records when the node executes; no special "skip" logic needed
- [X] T022a [US2] Locate the MetaReasoningGraph invocation (read `backend/agent/research_graph.py` and/or `backend/agent/nodes.py` to find the call site); add timing for `"meta_reasoning"` conditional stage using the same spread pattern — this stage records only when MetaReasoningGraph is triggered by low confidence; if the call site is in `research_graph.py`, instrument it there (overrides the "not to touch" guidance specifically for this one timing point)
- [X] T023 [US2] Write `tests/unit/test_stage_timings.py` — test cases: (1) `stage_timings` field exists in `ConversationState` TypedDict; (2) after a mock node run, `stage_timings["intent_classification"]` contains numeric `duration_ms`; (3) a simulated error results in `{"duration_ms": X, "failed": True}`; (4) conditional stage key is absent when node did not execute
- [X] T024 [US2] Run external tests: `zsh scripts/run-tests-external.sh -n spec14-a2 tests/unit/` — poll until complete; read summary; confirm PASSED with no new failures

### A3 Implementation — Storage and API Layer (backend/storage/ + backend/api/)

- [X] T025 [P] [US2] In `backend/storage/sqlite_db.py` `_migrate()` (or equivalent migration method): add idempotent `ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT` wrapped in `try/except aiosqlite.OperationalError` to handle re-runs
- [X] T026 [P] [US2] In `backend/storage/sqlite_db.py` `create_query_trace()`: add `stage_timings_json: str | None = None` parameter after `provider_name`; add `stage_timings_json` to INSERT column list and VALUES tuple (column count: 15 → 16; INSERT string and tuple must stay in sync)
- [X] T027 [US2] In `backend/api/chat.py` inside `generate()`: after `final_state = graph.get_state(config).values` and `latency_ms = ...`, extract `stage_timings = final_state.get("stage_timings", {})`; pass `stage_timings_json=json.dumps(stage_timings) if stage_timings else None` to `create_query_trace()`
- [X] T028 [US2] In `backend/api/traces.py` `get_trace()`: add `stage_timings_json` to SELECT column list; add `"stage_timings": parse_json(d.get("stage_timings_json"), {})` to response dict — default is `{}` (empty dict, NOT `[]`)
- [X] T029 [US2] Write `tests/unit/test_stage_timings_db.py` — test cases: (1) `create_query_trace()` accepts `stage_timings_json` parameter; (2) trace written with stage data round-trips correctly (insert → select returns same JSON); (3) trace written without `stage_timings_json` (None) returns `{}` from `get_trace()` response
- [X] T030 [US2] Write `tests/unit/api/test_traces_stage_timings.py` — test cases: (1) `GET /api/traces/{id}` response includes `"stage_timings"` key; (2) populated `stage_timings_json` in DB is parsed to dict in response (not raw string); (3) NULL `stage_timings_json` returns `"stage_timings": {}`; (4) legacy trace (NULL column) remains readable without error
- [X] T031 [US2] Run external tests: `zsh scripts/run-tests-external.sh -n spec14-a3 tests/unit/` — poll until complete; read summary; confirm PASSED with no new failures

### Wave 2 Gate Verification

- [X] T032 [US2] Confirm `Docs/Tests/spec14-a2.status = PASSED` AND `Docs/Tests/spec14-a3.status = PASSED`; confirm no new failures in pre-existing sqlite_db, chat, or traces tests; confirm pre-existing failure count has not increased beyond 39

### Stage Timings Integration Tests (added to existing test_performance.py)

- [X] T033 [US2] In `tests/integration/test_performance.py`: add `test_stage_timings_present()` — runs real query, fetches trace via API, asserts `stage_timings` dict contains at minimum 5 keys (`intent_classification`, `embedding`, `retrieval`, `ranking`, `answer_generation`), each with numeric `duration_ms` (SC-007)
- [X] T034 [US2] In `tests/integration/test_performance.py`: add `test_stage_timings_sum_consistent_with_total()` — fetches completed trace, sums `duration_ms` values, asserts sum is ≤ 150% of `latency_ms` (SC-007 consistency check)
- [X] T035 [US2] In `tests/integration/test_performance.py`: add `test_legacy_trace_readable()` — inserts `query_traces` row with `stage_timings_json = NULL`, fetches via API, asserts valid response with `"stage_timings": {}`

**Checkpoint**: All 3 unit test files pass. Stage timings present in all new traces. Legacy traces return `{}`. `GET /api/traces/{id}` includes `"stage_timings"` field.

---

## Phase 5: User Story 3 — Document Ingestion Throughput Verification (Priority: P2)

**Goal**: Confirm the existing Rust ingestion worker and Python embedding pipeline meet the defined
throughput targets: 10-page PDF < 3 s, 200-page PDF < 15 s, 50 KB Markdown < 5 s.

**Independent Test**: Run `zsh scripts/run-tests-external.sh -n spec14-us3 tests/integration/test_performance.py`
and confirm ingestion benchmark tests pass or are marked skip with documented verification procedure.

### Implementation for User Story 3

- [ ] T036 [P] [US3] In `tests/integration/test_performance.py`: add `test_small_pdf_ingestion_latency()` — submits a pre-prepared 10-page test PDF, polls until ingestion job completes, asserts searchable within 3000 ms (SC-003); mark `@pytest.mark.integration`
- [ ] T037 [P] [US3] In `tests/integration/test_performance.py`: add `test_large_pdf_ingestion_latency()` — submits a 200-page test PDF, polls until ingestion completes, asserts searchable within 15000 ms (SC-004); mark `@pytest.mark.integration`
- [ ] T038 [P] [US3] In `tests/integration/test_performance.py`: add `test_markdown_ingestion_latency()` — submits a 50 KB Markdown file, asserts searchable within 5000 ms; mark `@pytest.mark.integration`

**Checkpoint**: SC-003 and SC-004 have corresponding benchmark tests. Tests pass on reference hardware or are marked skip with documented verification procedure.

---

## Phase 6: User Story 4 — Concurrent Query Handling (Priority: P3)

**Goal**: Verify the system handles 3 simultaneous chat queries from independent sessions without
errors, data corruption, or one query blocking another.

**Independent Test**: Run `zsh scripts/run-tests-external.sh -n spec14-us4 tests/integration/test_performance.py`
and confirm the concurrent queries test passes.

### Implementation for User Story 4

- [X] T039 [US4] In `tests/integration/test_performance.py`: add `test_concurrent_queries_no_errors()` — sends 3 simultaneous queries from independent sessions using `asyncio.gather()`; asserts all 3 return HTTP 200 and complete without error within 30 s (SC-006); mark `@pytest.mark.integration`

**Checkpoint**: SC-006 has a corresponding automated test that passes.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression validation, acceptance report, and final gate checks.

- [X] T039a In `backend/main.py` lifespan startup handler: add a `structlog.get_logger().warning()` call that emits a WARNING-level log event estimating process memory footprint based on known loaded model sizes; include known model names and sizes in the log context; this satisfies FR-003's "observable warning" requirement without any new runtime dependency (no `psutil`)
- [X] T040 [P] Spawn Wave 3 agent A4: `Agent(subagent_type="quality-engineer", model="sonnet", prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A4-validation.md FIRST, then execute all assigned tasks")`
- [X] T041 Run full test suite: `zsh scripts/run-tests-external.sh -n spec14-a4-full tests/` — poll until complete; read summary
- [X] T042 Confirm `Docs/Tests/spec14-a4-full.status = PASSED`; confirm pre-existing failure count is still 39 (any increase is a regression — investigate before proceeding)
- [X] T043 Run benchmark-only test: `zsh scripts/run-tests-external.sh -n spec14-a4-bench tests/integration/test_performance.py` — confirm new tests pass or are appropriately marked skip
- [X] T044 [P] Verify all 8 success criteria from `specs/014-performance-budgets/spec.md`:
  - SC-001 / SC-002: latency benchmark tests exist, pass or skip with documented procedure
  - SC-003 / SC-004: ingestion benchmark tests exist, pass or skip
  - SC-005: backend idle memory < 600 MB — document measurement procedure in final report
  - SC-006: concurrent queries test passes (must be automated, not skip)
  - SC-007: stage timings present test passes (must be automated, not skip)
  - SC-008: streaming rate — document measurement procedure in final report
- [X] T045 Write final report `Docs/Tests/spec14-a4-final.md` — one row per SC with PASS/SKIP/FAIL, total new test count, pre-existing failure count, explicit confirmation that `stage_timings_json` round-trips through DB → API correctly

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user story phases
- **US1 (Phase 3)**: Can begin after Foundational; independent of US2 engineering (benchmark tests only)
- **US2 (Phase 4)**: Depends on Foundational; T014+T015 (Wave 2 spawn) requires Foundational gate PASS; T033–T035 depends on T024+T031 (Wave 2 complete)
- **US3 (Phase 5)**: Can begin after Foundational; independent of US2 (ingestion benchmark only)
- **US4 (Phase 6)**: Can begin after Foundational; independent of US2 (concurrency test only)
- **Polish (Phase 7)**: Depends on all user story phases complete; T040 (Wave 3) requires all Wave 2 gates PASS

### User Story Dependencies

- **US1 (P1)**: After Foundational gate passes — no dependency on other stories
- **US2 (P2)**: After Foundational gate passes — Wave 2 agents run in parallel; Wave 3 gate depends on Wave 2 complete
- **US3 (P2)**: After Foundational gate passes — no dependency on US1 or US2
- **US4 (P3)**: After Foundational gate passes — no dependency on other stories

### Within Phase 4 (US2)

- T014 and T015 (Wave 2 spawn): Parallel — A2 and A3 are independent
- T016–T024 (A2 tasks): Sequential within A2 — each node must be instrumented before tests
- T025–T031 (A3 tasks): Sequential within A3 — migration before param, param before chat.py, chat.py before traces.py
- T033–T035: After T032 (Wave 2 gate) — require both A2 and A3 complete

### Parallel Opportunities

Within Phase 4 (US2), A2 and A3 work on entirely different files simultaneously:
- A2 files: `backend/agent/state.py`, `backend/agent/nodes.py`, `tests/unit/test_stage_timings.py`
- A3 files: `backend/storage/sqlite_db.py`, `backend/api/chat.py`, `backend/api/traces.py`, `tests/unit/test_stage_timings_db.py`, `tests/unit/api/test_traces_stage_timings.py`

Within Phase 3 (US1) and Phase 5 (US3): all tasks are parallel [P] (separate test functions in same file):
```bash
# Phase 3 + Phase 5 can run concurrently after Foundational:
T011 test_simple_query_first_token_latency
T012 test_complex_query_first_token_latency  # parallel with T011
T036 test_small_pdf_ingestion_latency        # parallel with T011/T012
T037 test_large_pdf_ingestion_latency        # parallel with others
T038 test_markdown_ingestion_latency         # parallel with others
```

---

## Parallel Example: User Story 2 (Wave 2)

```text
After T013 (Foundational gate) PASSES:

  tmux pane 1 (A2 — state/nodes):
    T016 Add stage_timings field to state.py
    T017 Instrument classify_intent in nodes.py
    T018 Instrument embedding stage
    T019 Instrument retrieval stage
    T020 Instrument ranking stage
    T021 Instrument answer_generation stage
    T022 Instrument grounded_verification stage
    T023 Write tests/unit/test_stage_timings.py
    T024 Run: zsh scripts/run-tests-external.sh -n spec14-a2 tests/unit/

  tmux pane 2 (A3 — storage/api): [runs simultaneously with pane 1]
    T025 Schema migration in sqlite_db.py
    T026 create_query_trace() param extension in sqlite_db.py
    T027 stage_timings extraction in chat.py
    T028 traces.py GET /api/traces/{id} extension
    T029 Write tests/unit/test_stage_timings_db.py
    T030 Write tests/unit/api/test_traces_stage_timings.py
    T031 Run: zsh scripts/run-tests-external.sh -n spec14-a3 tests/unit/

After BOTH complete → T032 gate check → T033–T035 (integration tests)
```

---

## Implementation Strategy

### MVP (User Story 2 Only — Core Engineering)

1. Complete Phase 1: Setup (verify tooling)
2. Complete Phase 2: Foundational (pre-flight audit — CRITICAL gate)
3. Complete Phase 4: User Story 2 (state + nodes + storage + API + tests)
4. **STOP and VALIDATE**: Fetch a real trace, confirm `stage_timings` dict is populated with 5+ stages
5. SC-007 is now satisfiable

### Incremental Delivery

1. Setup + Foundational → pre-implementation state verified
2. Add US2 (Phase 4) → core engineering complete; SC-007 met → **demo: stage timings in trace**
3. Add US1 benchmarks (Phase 3) → latency budgets verified → SC-001, SC-002 met
4. Add US3 benchmarks (Phase 5) → ingestion throughput verified → SC-003, SC-004 met
5. Add US4 test (Phase 6) → concurrency verified → SC-006 met
6. Polish (Phase 7) → full regression + final report

### Agent Teams Strategy (3 Waves)

Wave 1 (A1, opus): Read-only audit of 5 target files → write `Docs/Tests/spec14-a1-audit.md`

Wave 2 (A2 + A3, sonnet, parallel):
- A2: `state.py` + `nodes.py` + unit tests
- A3: `sqlite_db.py` + `chat.py` + `traces.py` + unit tests

Wave 3 (A4, sonnet): Full test suite + benchmarks + SC verification + final report

---

## Notes

- [P] tasks can run in parallel — different files, no incomplete-task dependencies
- [USN] label maps task to user story from spec.md for traceability
- ALL testing via `zsh scripts/run-tests-external.sh` — never pytest directly inside Claude Code
- Polling: `cat Docs/Tests/<name>.status` until status is not `RUNNING`
- Each Wave gate must pass before the next Wave spawns
- Schema migration (T025) MUST be idempotent — wrap in `try/except aiosqlite.OperationalError`
- `stage_timings` default is `{}` (empty dict), NOT `[]` — critical distinction from other JSON fields
- Absent key in `stage_timings_json` = "did not run" — NEVER insert `{"duration_ms": 0}`
- LangGraph node timing: read `state.get("stage_timings", {})` and spread before adding new entry
- Pre-existing failure baseline: 39 failures (from spec-13); any increase is a regression
