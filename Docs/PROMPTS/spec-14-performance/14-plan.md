# Spec 14: Performance Budgets and Pipeline Instrumentation — Implementation Plan Context

> **AGENT TEAMS -- tmux IS REQUIRED**
>
> This spec uses 3 waves with 4 agents. Waves run sequentially; each wave gate
> must pass before the next wave begins. Wave 2 runs agents in parallel.
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
>   prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/<file>.md FIRST, then execute all assigned tasks"
> )
> ```

---

## Component Overview

### What Spec-14 Adds

Spec-14 has one primary engineering change and one set of verification benchmarks. The primary
change is per-stage timing instrumentation: adding a new `stage_timings_json` column to the
`query_traces` table and populating it on every chat query. The verification work confirms that
existing configuration defaults already satisfy the latency, throughput, and concurrency budgets
defined in the spec.

| FR | File | Change |
|----|------|--------|
| FR-005 | `backend/agent/state.py` | Add `stage_timings: dict` field to `ConversationState` |
| FR-005 | `backend/agent/nodes.py` | Instrument each pipeline node with `time.perf_counter()` timing; record into `state["stage_timings"]` |
| FR-005 | `backend/storage/sqlite_db.py` | Schema migration: `ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT`; add `stage_timings_json` parameter to `create_query_trace()`; add column to SELECT in `get_trace()` raw query |
| FR-005 | `backend/api/chat.py` | Extract `stage_timings` from `final_state` after graph completes; serialize and pass `stage_timings_json=json.dumps(stage_timings)` to `create_query_trace()` |
| FR-008 | `backend/api/traces.py` | Add `stage_timings_json` to SELECT in `get_trace()`; parse and expose as `"stage_timings"` in the response dict |
| FR-001–FR-004, FR-006–FR-007 | `tests/integration/test_performance.py` | Extend existing file with new benchmark tests asserting against spec time budgets |

Total scope: ~60–80 lines of new production code across 5 existing files, plus new tests.

### What Is Already Built — Do NOT Reimplement

The following were completed in earlier specs. Agents must not touch these as new work:

| Component | Spec | Location |
|-----------|------|----------|
| SQLite WAL mode | spec-07 | `backend/storage/sqlite_db.py` (PRAGMA journal_mode=WAL in init) |
| Singleton cross-encoder loading | spec-07 / spec-06 | `backend/main.py` lifespan handler |
| ThreadPoolExecutor batch embedding | spec-06 | `backend/ingestion/embedder.py` |
| Rust ingestion worker | spec-06 | `ingestion-worker/` |
| Qdrant batch upserts | spec-06 | `backend/ingestion/embedder.py` UpsertBuffer |
| NDJSON streaming for chat | spec-08 / spec-09 | `Content-Type: application/x-ndjson` (NOT SSE) |
| `time.monotonic()` for total latency | spec-08 | `backend/api/chat.py` line 60 |
| `latency_ms` stored in `query_traces` | spec-07 / spec-08 | `backend/storage/sqlite_db.py` |
| `reasoning_steps_json` column | spec-07 | `query_traces` table |
| `strategy_switches_json` column | spec-07 | `query_traces` table |
| Rate limiting, CORS middleware | spec-08 | `backend/middleware.py`, `backend/main.py` |
| Security sanitization | spec-13 | `backend/api/chat.py`, `backend/api/ingest.py` |
| Circuit breakers + retry | spec-05 | `backend/agent/nodes.py`, `backend/retrieval/searcher.py` |
| Spec-07 storage performance tests | spec-07 | `tests/integration/test_performance.py` (first two tests) |

The `tests/integration/test_performance.py` file already exists with two passing tests
(`test_parent_retrieval_latency_target`, `test_search_latency_target`). Spec-14 adds new
benchmark tests to this same file without modifying the existing tests.

---

## Wave Definitions

### Wave 1 — Pre-Flight Audit (Sequential)

| Field | Value |
|-------|-------|
| Agent | A1 |
| Type | quality-engineer |
| Model | claude-opus-4-5 |
| Tasks | T001–T008 |
| Output | `Docs/Tests/spec14-a1-audit.md` |

**Gate condition**: Audit report exists AND confirms:
- `query_traces` table does NOT yet have a `stage_timings_json` column
- `ConversationState` does NOT yet have a `stage_timings` field
- `create_query_trace()` signature does NOT yet include `stage_timings_json` parameter
- `get_trace()` SELECT does NOT yet include `stage_timings_json`
- All 5 target production files are identified with line-level insertion points documented
- `tests/integration/test_performance.py` exists with 2 existing tests; spec-14 adds to it

Do not spawn Wave 2 until the audit report is written and conditions above are met.

---

### Wave 2 — Implementation (Parallel)

Both A2 and A3 run simultaneously in separate tmux panes. They modify different files and do not conflict.

#### A2 — State and Nodes Instrumentation

| Field | Value |
|-------|-------|
| Agent | A2 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T009–T016 |
| Files modified | `backend/agent/state.py`, `backend/agent/nodes.py` |
| New test files | `tests/unit/test_stage_timings.py` |

#### A3 — Storage and API Layer

| Field | Value |
|-------|-------|
| Agent | A3 |
| Type | python-expert |
| Model | claude-sonnet-4-5 |
| Tasks | T017–T025 |
| Files modified | `backend/storage/sqlite_db.py`, `backend/api/chat.py`, `backend/api/traces.py` |
| New test files | `tests/unit/test_stage_timings_db.py`, `tests/unit/api/test_traces_stage_timings.py` |

**Wave 2 gate condition**: Both A2 and A3 complete all assigned tasks. Each agent's external
test run of `tests/unit/` returns `PASSED`. The pre-existing failure count does not increase.

---

### Wave 3 — Benchmarks and Final Validation (Sequential)

| Field | Value |
|-------|-------|
| Agent | A4 |
| Type | quality-engineer |
| Model | claude-sonnet-4-5 |
| Tasks | T026–T035 |
| Output | `Docs/Tests/spec14-a4-final.md` |

**Wave 3 gate condition (final)**: All 8 success criteria verified. Pre-existing failure
count remains at 39. Final report written.

---

## Task Table

| Task | Agent | Description |
|------|-------|-------------|
| T001 | A1 | Read `specs/014-performance-budgets/spec.md` fully — confirm 8 FRs, 8 SCs, primary new work is `stage_timings_json` column (FR-005 and FR-008) |
| T002 | A1 | Read `backend/agent/state.py` — confirm `ConversationState` has 13 fields (session_id through iteration_count); confirm `stage_timings: dict` does NOT exist |
| T003 | A1 | Read `backend/agent/nodes.py` — identify the 7 instrumentation target nodes: `classify_intent`, `rewrite_query`, the ResearchGraph call site in ConversationGraph (embedding occurs here), the searcher invocation (retrieval), `validate_citations` (ranking), the LLM generation call (answer_generation), `verify_groundedness` (conditional grounded_verification) |
| T004 | A1 | Read `backend/storage/sqlite_db.py` lines 429–461 — confirm `create_query_trace()` has 15 parameters (id through provider_name); confirm `stage_timings_json` parameter is absent; note the INSERT column list |
| T005 | A1 | Read `backend/api/chat.py` lines 46–228 — confirm `time.monotonic()` already used for `latency_ms`; confirm `stage_timings` is NOT extracted from `final_state`; note exact line where `create_query_trace()` call begins |
| T006 | A1 | Read `backend/api/traces.py` lines 75–130 — confirm SELECT does NOT include `stage_timings_json`; note the `parse_json()` helper that already exists; confirm `stage_timings` key is absent from the response dict |
| T007 | A1 | Read `tests/integration/test_performance.py` — confirm 2 existing tests (`test_parent_retrieval_latency_target`, `test_search_latency_target`) are present and must NOT be modified; document the file structure for A4 |
| T008 | A1 | Write audit report `Docs/Tests/spec14-a1-audit.md` — one section per target file with line-level insertion points, one section for "do not touch" files, overall PASS/FAIL verdict for pre-FR state |
| T009 | A2 | In `backend/agent/state.py`: add `stage_timings: dict` field to `ConversationState` after `iteration_count`; the field accumulates per-node timing data as the pipeline runs |
| T010 | A2 | In `backend/agent/nodes.py` `classify_intent()`: add `t0 = time.perf_counter()` at function entry; after the LLM call completes, compute elapsed and write `state["stage_timings"]["intent_classification"] = {"duration_ms": round((time.perf_counter() - t0) * 1000, 1)}`; wrap in try/except so a timing failure never masks a node error — on exception include `"failed": true` |
| T011 | A2 | In `backend/agent/nodes.py`: add timing for the embedding stage. The embedding call occurs inside `rewrite_query()` or the node that invokes `HybridSearcher` — identify the correct node by reading the code; instrument it as `state["stage_timings"]["embedding"] = {"duration_ms": ...}` |
| T012 | A2 | In `backend/agent/nodes.py`: instrument the retrieval stage (the `HybridSearcher.search()` call path); record as `state["stage_timings"]["retrieval"] = {"duration_ms": ...}` |
| T013 | A2 | In `backend/agent/nodes.py`: instrument the ranking stage (`validate_citations()` or the cross-encoder reranker call); record as `state["stage_timings"]["ranking"] = {"duration_ms": ...}` |
| T014 | A2 | In `backend/agent/nodes.py`: instrument the answer generation stage (the LLM call that produces `final_response`); record as `state["stage_timings"]["answer_generation"] = {"duration_ms": ...}` |
| T015 | A2 | In `backend/agent/nodes.py` `verify_groundedness()`: instrument as `state["stage_timings"]["grounded_verification"] = {"duration_ms": ...}` — this stage is conditional; only records when the node actually executes (which is correct since absent key = "did not run") |
| T016 | A2 | Write `tests/unit/test_stage_timings.py` — test cases: (1) `stage_timings` key exists in `ConversationState` TypedDict; (2) after a node runs, `stage_timings["intent_classification"]` contains `duration_ms` as a number; (3) a simulated node error results in `{"duration_ms": X, "failed": true}` for that stage; (4) conditional stage key is absent when the node did not execute; then run `zsh scripts/run-tests-external.sh -n spec14-a2 tests/unit/` and confirm PASSED |
| T017 | A3 | In `backend/storage/sqlite_db.py`: run schema migration by adding `stage_timings_json TEXT` column — add `await self.db.execute("ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT")` inside the `_migrate()` method or equivalent migration path used by existing column additions; verify by reading how `reasoning_steps_json` was added |
| T018 | A3 | In `backend/storage/sqlite_db.py` `create_query_trace()`: add `stage_timings_json: str \| None = None` parameter (after `provider_name`); add `stage_timings_json` to the INSERT column list and VALUES tuple |
| T019 | A3 | In `backend/api/chat.py` inside `generate()`, after `final_state = graph.get_state(config).values` and before the `create_query_trace()` call: extract `stage_timings = final_state.get("stage_timings", {})`; then pass `stage_timings_json=json.dumps(stage_timings) if stage_timings else None` to `create_query_trace()` |
| T020 | A3 | In `backend/api/traces.py` `get_trace()`: add `stage_timings_json` to the SELECT column list; add `"stage_timings": parse_json(d.get("stage_timings_json"), {})` to the response dict — use `{}` as the default (not `[]`) so consumers can distinguish "no stages recorded" from "stages is a list" |
| T021 | A3 | Write `tests/unit/test_stage_timings_db.py` — test cases: (1) `create_query_trace()` accepts `stage_timings_json` parameter without error; (2) a trace written with stage data round-trips correctly through SQLite (insert then select returns the same JSON); (3) a trace written without `stage_timings_json` (None) returns `{}` from `get_trace()` response |
| T022 | A3 | Write `tests/unit/api/test_traces_stage_timings.py` — test cases: (1) `GET /api/traces/{id}` response includes `"stage_timings"` key; (2) when `stage_timings_json` is populated in DB, the response parses it to a dict (not a raw string); (3) when `stage_timings_json` is NULL in DB, response returns `"stage_timings": {}`; (4) legacy trace records (NULL column) remain readable without error |
| T023 | A3 | Run external tests: `zsh scripts/run-tests-external.sh -n spec14-a3 tests/unit/` — poll until status is not `RUNNING`; read summary |
| T024 | A3 | Confirm `Docs/Tests/spec14-a3.status` is `PASSED`; confirm no new failures in pre-existing sqlite_db, chat, or traces tests |
| T025 | A3 | Report completion to orchestrator via task update |
| T026 | A4 | Run full test suite: `zsh scripts/run-tests-external.sh -n spec14-a4-full tests/` — poll until complete; read summary |
| T027 | A4 | Verify the 2 existing performance tests in `test_performance.py` still pass (`test_parent_retrieval_latency_target`, `test_search_latency_target`) |
| T028 | A4 | In `tests/integration/test_performance.py`: add `test_stage_timings_present()` — runs a real query through the graph, fetches the trace via the API, asserts that `stage_timings` dict contains at minimum the 5 always-present keys (`intent_classification`, `embedding`, `retrieval`, `ranking`, `answer_generation`), each with a numeric `duration_ms` value |
| T029 | A4 | In `tests/integration/test_performance.py`: add `test_stage_timings_sum_consistent_with_total()` — fetches a completed trace, sums the `duration_ms` values of all stage entries, asserts the sum is within 150% of `latency_ms` (accounting for overhead and conditional stages that contribute to total but not necessarily to the sum) |
| T030 | A4 | In `tests/integration/test_performance.py`: add `test_legacy_trace_readable()` — directly inserts a `query_traces` row with `stage_timings_json = NULL` (simulating a pre-spec-14 trace), then fetches it via the API and asserts the response is valid with `"stage_timings": {}` |
| T031 | A4 | In `tests/integration/test_performance.py`: add `test_concurrent_queries_no_errors()` — send 3 simultaneous queries from independent sessions using `asyncio.gather()`; assert all 3 return status 200 and complete without error (SC-006) |
| T032 | A4 | Run external tests again after adding new benchmark tests: `zsh scripts/run-tests-external.sh -n spec14-a4-bench tests/integration/test_performance.py` — confirm new tests pass or are appropriately marked `pytest.mark.skip` if they require live services (Qdrant, Ollama) not available in CI |
| T033 | A4 | Verify all 8 success criteria from `specs/014-performance-budgets/spec.md` — SC-001 through SC-008 — document each as PASS (verified by test or configuration inspection) or SKIP (requires reference hardware, noted as such) |
| T034 | A4 | Confirm pre-existing failure count is still 39 (established in spec-13 baseline) — any increase is a regression that must be investigated and fixed before final report |
| T035 | A4 | Write final report `Docs/Tests/spec14-a4-final.md` — one row per success criterion with PASS/SKIP/FAIL, total new test count, pre-existing failure count, and explicit confirmation that `stage_timings_json` round-trips through DB → API correctly |

---

## Acceptance Criteria Reference

These 8 success criteria from `specs/014-performance-budgets/spec.md` are what A4 must verify in T033:

1. **SC-001**: Simple factoid queries return their first visible response token within 1.5 seconds on reference hardware. (Benchmark test or configuration inspection.)
2. **SC-002**: Complex analytical queries return their first visible response token within 6 seconds on reference hardware.
3. **SC-003**: A 10-page PDF is fully indexed and searchable within 3 seconds.
4. **SC-004**: A 200-page PDF is fully indexed and searchable within 15 seconds.
5. **SC-005**: The system backend consumes less than 600 MB of memory at idle, including all loaded models except the inference engine.
6. **SC-006**: Three simultaneous chat queries from independent sessions all return complete, valid answers without errors or timeouts within 30 seconds.
7. **SC-007**: Every query trace record produced after spec-14 contains a per-stage timing breakdown with at least 5 always-present named stages. Conditional stages appear only when executed. Breakdown is accessible via `GET /api/traces/{id}`.
8. **SC-008**: Response token streaming sustains at least 50 output events per second during answer generation.

SC-001 through SC-005 and SC-008 may be marked SKIP in CI if they require reference hardware or a live inference model. They must be documented with the verification procedure. SC-006 and SC-007 must produce passing automated tests.

---

## Integration Points

### Files Modified (5 total)

| File | FR | Change Type |
|------|----|-------------|
| `backend/agent/state.py` | FR-005 | Add `stage_timings: dict` field to `ConversationState` TypedDict |
| `backend/agent/nodes.py` | FR-005 | Add inline `time.perf_counter()` timing to 6–7 node functions |
| `backend/storage/sqlite_db.py` | FR-005 | Schema migration + `stage_timings_json` parameter in `create_query_trace()` + column in SELECT |
| `backend/api/chat.py` | FR-005 | Extract `stage_timings` from `final_state` and pass to `create_query_trace()` |
| `backend/api/traces.py` | FR-008 | Add `stage_timings_json` to SELECT; add parsed `"stage_timings"` key to response dict |

### Files Extended (1 total — do NOT delete existing tests)

| File | Change |
|------|--------|
| `tests/integration/test_performance.py` | Append new benchmark tests; leave the 2 existing spec-07 tests untouched |

### Files Verified But NOT Modified

| File | Why Read | Action |
|------|----------|--------|
| `backend/agent/conversation_graph.py` | Confirm node names to map to stage names | Read-only |
| `backend/config.py` | Confirm performance-related defaults (top_k, embed_batch_size, etc.) already set | Read-only; no changes needed |

### Files Explicitly NOT to Touch

| File | Reason |
|------|--------|
| `backend/ingestion/embedder.py` | ThreadPoolExecutor already implemented in spec-06 |
| `backend/retrieval/reranker.py` | Singleton cross-encoder already loaded in main.py lifespan |
| `backend/retrieval/searcher.py` | No changes needed for spec-14 |
| `backend/middleware.py` | Rate limiting complete from spec-08 |
| `backend/agent/edges.py` | Routing logic not involved in timing |
| `backend/agent/research_graph.py` | Sub-graph timing rolls up into parent node timing |

---

## Key Constraints

### stage_timings_json Data Format

The canonical JSON format for `stage_timings_json` is:

```json
{
  "intent_classification": {"duration_ms": 180},
  "embedding": {"duration_ms": 45},
  "retrieval": {"duration_ms": 28},
  "ranking": {"duration_ms": 142},
  "answer_generation": {"duration_ms": 487},
  "grounded_verification": {"duration_ms": 390}
}
```

Rules:
- `duration_ms` is a float rounded to 1 decimal place (use `round(..., 1)`)
- `duration_ms` is always present for every stage that executed
- `meta_reasoning` key is included only when the MetaReasoningGraph was triggered
- `grounded_verification` key is included only when `verify_groundedness` node executed

### Conditional Stage Rules

An absent key means "did not run." Do NOT insert a stage entry with `duration_ms: 0` for a
skipped stage. This distinction is specified in the spec and relied upon by SC-007.

### Failed Stage Rules

If a node raises an exception that is caught by the timing wrapper, the stage entry MUST
still be written to `stage_timings` with the measured duration up to the point of failure:

```json
{"duration_ms": 45.2, "failed": true}
```

Subsequent stages that did not execute because of the failure are simply absent (no key).
A timing failure itself (e.g., `time.perf_counter()` error) must never mask the underlying
node error — use `try/except` around timing code only, not around the node logic.

### Inline Timing Pattern (No Timer Class)

Use inline `time.perf_counter()` in each node. Do NOT create a shared `Timer` context
manager class. This keeps each node self-contained and avoids import coupling:

```python
async def classify_intent(state: ConversationState, *, llm: Any) -> dict:
    _t0 = time.perf_counter()
    try:
        # ... existing node logic ...
        result = {"intent": intent}
        result.setdefault("stage_timings", state.get("stage_timings", {}))
        result["stage_timings"] = {
            **result["stage_timings"],
            "intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
        }
        return result
    except Exception:
        timings = {
            **state.get("stage_timings", {}),
            "intent_classification": {
                "duration_ms": round((time.perf_counter() - _t0) * 1000, 1),
                "failed": True,
            },
        }
        raise  # re-raise after recording; LangGraph handles the error
```

Note: LangGraph node functions return partial state dicts. The timing update must merge into
the existing `stage_timings` dict from state rather than replacing it. The pattern above uses
`state.get("stage_timings", {})` as the base and spreads existing timings before adding the
new stage entry.

### chat.py — Extracting stage_timings from final_state

After `final_state = graph.get_state(config).values`, add:

```python
stage_timings = final_state.get("stage_timings", {})
```

Then pass to `create_query_trace()`:

```python
stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
```

This must be added in the same `try` block as the other `create_query_trace()` arguments,
after the existing `strategy_switches_json` and `provider_name` arguments.

### traces.py — Response Default for NULL stage_timings_json

When `stage_timings_json` is NULL (legacy traces), `parse_json(val, {})` returns `{}` — NOT
`[]`. This is important: the default for `stage_timings` uses an empty dict, unlike
`sub_questions`, `chunks_retrieved`, and other fields which default to `[]`.

### pathlib.Path Rule (Constitution Principle VIII)

Any new file path construction in Python code MUST use `pathlib.Path`, not `os.path.join`
or string concatenation with hardcoded separators. This applies to any path used in test
fixtures (e.g., `tmp_path / "test.db"`). The existing tests already follow this pattern.

### Chat Endpoint Uses NDJSON — Not SSE

The chat endpoint uses `Content-Type: application/x-ndjson` and returns
`StreamingResponse(..., media_type="application/x-ndjson")`. There is no SSE, no
`text/event-stream`, and no `data:` prefix on events. Do not introduce any SSE
references anywhere in spec-14 code or tests.

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

### External Test Run Schedule

| Agent | Run name | Target | When |
|-------|----------|--------|------|
| A2 | `spec14-a2` | `tests/unit/` | After T016 (test file written) |
| A3 | `spec14-a3` | `tests/unit/` | After T022–T023 complete |
| A4 | `spec14-a4-full` | `tests/` | Wave 3 start (T026) |
| A4 | `spec14-a4-bench` | `tests/integration/test_performance.py` | After T031 (new benchmarks written) |

### Wave Gates Summary

| Gate | Condition |
|------|-----------|
| Wave 1 → Wave 2 | `Docs/Tests/spec14-a1-audit.md` exists; all 5 target files confirmed in pre-FR state; `stage_timings_json` column confirmed absent |
| Wave 2 → Wave 3 | `spec14-a2.status = PASSED` AND `spec14-a3.status = PASSED`; no new failures in pre-existing tests |
| Final | `spec14-a4-full.status = PASSED`; SC-006 and SC-007 verified by passing tests; pre-existing failure count = 39 |

### New Test File Locations

All new test files follow the existing project test layout:

```
tests/
  unit/
    test_stage_timings.py               # A2 — FR-005 state + nodes
    test_stage_timings_db.py            # A3 — FR-005 storage round-trip
    api/
      test_traces_stage_timings.py      # A3 — FR-008 API exposure
  integration/
    test_performance.py                 # A4 — EXTENDS existing file; adds FR-005, SC-006, SC-007 benchmarks
```

---

## Appendix: Exact Insertion Points

This section gives agents the precise code context for each change so edits are unambiguous.

### FR-005 — state.py: Add stage_timings field

Current `ConversationState` tail (lines 29–31):
```python
    confidence_score: int  # 0–100 scale (user-facing)
    iteration_count: int
```

After change — add `stage_timings` as the last field:
```python
    confidence_score: int  # 0–100 scale (user-facing)
    iteration_count: int
    stage_timings: dict  # FR-005: per-stage timing data accumulated by nodes
```

### FR-005 — sqlite_db.py: create_query_trace() parameter

Current method signature tail (lines 444–446):
```python
        meta_reasoning_triggered: bool = False,
        provider_name: str | None = None,
    ) -> None:
```

After change:
```python
        meta_reasoning_triggered: bool = False,
        provider_name: str | None = None,
        stage_timings_json: str | None = None,
    ) -> None:
```

The INSERT statement must also gain `stage_timings_json` in both the column name list and
the VALUES tuple. The column count increases from 15 to 16; the INSERT string and tuple
must stay in sync.

### FR-005 — sqlite_db.py: Schema migration

The `stage_timings_json` column must be added to `query_traces` via a migration. Read the
existing migration code (look for how `provider_name` or `reasoning_steps_json` were added
as columns) and add `stage_timings_json TEXT` following the same pattern. The migration
must be idempotent (use `ALTER TABLE ... ADD COLUMN` only if column does not exist, or wrap
in a try/except that ignores `OperationalError: duplicate column name`).

### FR-008 — traces.py: SELECT and response dict

Current SELECT statement (lines 82–88):
```python
        """SELECT id, session_id, query, collections_searched,
                  chunks_retrieved_json, confidence_score, latency_ms,
                  llm_model, embed_model, sub_questions_json,
                  reasoning_steps_json, strategy_switches_json,
                  meta_reasoning_triggered, created_at
           FROM query_traces WHERE id = ?"""
```

After change — add `stage_timings_json`:
```python
        """SELECT id, session_id, query, collections_searched,
                  chunks_retrieved_json, confidence_score, latency_ms,
                  llm_model, embed_model, sub_questions_json,
                  reasoning_steps_json, strategy_switches_json,
                  meta_reasoning_triggered, created_at,
                  stage_timings_json
           FROM query_traces WHERE id = ?"""
```

Current response dict tail (lines 128–130):
```python
        "reasoning_steps": parse_json(d.get("reasoning_steps_json"), []),
        "strategy_switches": parse_json(d.get("strategy_switches_json"), []),
    }
```

After change — add `stage_timings` with `{}` as default:
```python
        "reasoning_steps": parse_json(d.get("reasoning_steps_json"), []),
        "strategy_switches": parse_json(d.get("strategy_switches_json"), []),
        "stage_timings": parse_json(d.get("stage_timings_json"), {}),
    }
```

### FR-005 — chat.py: Extract and pass stage_timings

Current code (lines 137–139, after graph stream completes):
```python
            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
```

After change — extract stage_timings immediately after final_state:
```python
            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
            stage_timings = final_state.get("stage_timings", {})  # FR-005
```

Current `create_query_trace()` call tail (lines 193–197):
```python
                    strategy_switches_json=json.dumps(
                        list(attempted)
                    ) if attempted else None,
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
```

After change — add `stage_timings_json`:
```python
                    strategy_switches_json=json.dumps(
                        list(attempted)
                    ) if attempted else None,
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
                    stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
```
