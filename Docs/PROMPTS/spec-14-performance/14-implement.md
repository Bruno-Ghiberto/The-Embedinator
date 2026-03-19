# Spec 14: Performance Budgets and Pipeline Instrumentation — Implementation Context

> **AGENT TEAMS — tmux IS MANDATORY**
>
> This spec uses Claude Code Agent Teams with 3 waves and 4 agents.
> tmux MUST be running before spawning any agent.
> Each agent runs in its own tmux pane.
> Wave 2 runs A2 and A3 simultaneously in parallel panes.
> Waves are sequential — each wave gate must pass before the next wave spawns.
>
> ORCHESTRATOR PROTOCOL:
> 1. Verify tmux is running (`tmux ls`)
> 2. Read THIS file completely before doing anything else
> 3. Spawn agents by wave using the exact `Agent()` commands below
> 4. Each agent's FIRST action is to read its own instruction file
> 5. Wait for the wave gate to pass before spawning the next wave
>
> DO NOT attempt to implement this spec without Agent Teams in tmux.
> DO NOT spawn Wave 2 before the Wave 1 audit report is written and verified.
> DO NOT spawn Wave 3 before both `spec14-a2.status = PASSED` and `spec14-a3.status = PASSED`.

---

## What This Spec Does

Spec-14 adds one engineering change and one set of verification benchmarks. The engineering
change is per-stage timing instrumentation: a new `stage_timings_json` column is added to the
`query_traces` table and populated on every chat query across 5 always-present pipeline stages.
The verification work confirms that existing configuration defaults already satisfy the latency,
throughput, and concurrency budgets defined in the spec's 8 success criteria.

Total scope: approximately 60–80 lines of new production code across 5 existing files, plus new
unit and integration tests. No new modules, no new pip dependencies.

---

## Wave Structure

| Wave | Agent | Type | Model | Tasks | Files |
|------|-------|------|-------|-------|-------|
| 1 (sequential) | A1 | `quality-engineer` | **opus** | T001–T008 | Read-only audit → writes `Docs/Tests/spec14-a1-audit.md` |
| 2A (parallel) | A2 | `python-expert` | **sonnet** | T009–T016 (tasks.md T016–T024) | `backend/agent/state.py`, `backend/agent/nodes.py`, `tests/unit/test_stage_timings.py` |
| 2B (parallel) | A3 | `python-expert` | **sonnet** | T017–T025 (tasks.md T025–T031) | `backend/storage/sqlite_db.py`, `backend/api/chat.py`, `backend/api/traces.py`, 2 test files |
| 3 (sequential) | A4 | `quality-engineer` | **sonnet** | T026–T035 (tasks.md T040–T045) | Extends `tests/integration/test_performance.py`, writes `Docs/Tests/spec14-a4-final.md` |

---

## Agent Spawn Commands

Copy these exactly. Each agent reads its instruction file before doing any work.

### Wave 1 — Spawn A1 (Pre-Flight Audit)

```python
Agent(
  subagent_type="quality-engineer",
  model="opus",
  prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A1-audit.md FIRST, then execute all assigned tasks"
)
```

**Wave 1 gate**: Do not proceed until `Docs/Tests/spec14-a1-audit.md` exists and its overall
verdict is PASS. Verify all 5 target files are in pre-FR state (no `stage_timings` field,
no `stage_timings_json` column or parameter).

### Wave 2 — Spawn A2 and A3 in parallel panes

Spawn both simultaneously, each in its own tmux pane:

```python
# Pane 1 — A2 (state + nodes)
Agent(
  subagent_type="python-expert",
  model="sonnet",
  prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A2-state-nodes.md FIRST, then execute all assigned tasks"
)

# Pane 2 — A3 (storage + API) — spawn at the same time as A2
Agent(
  subagent_type="python-expert",
  model="sonnet",
  prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A3-storage-api.md FIRST, then execute all assigned tasks"
)
```

**Wave 2 gate**: Both `Docs/Tests/spec14-a2.status = PASSED` AND
`Docs/Tests/spec14-a3.status = PASSED`. Pre-existing failure count must not exceed 39.

### Wave 3 — Spawn A4 (Benchmarks and Final Validation)

```python
Agent(
  subagent_type="quality-engineer",
  model="sonnet",
  prompt="Read your instruction file at Docs/PROMPTS/spec-14-performance/agents/A4-validation.md FIRST, then execute all assigned tasks"
)
```

**Final gate**: `Docs/Tests/spec14-a4-full.status = PASSED`. SC-006 and SC-007 verified by
passing automated tests. Pre-existing failure count = 39. Final report written.

---

## Files Modified (Production)

| File | FR | Change Type |
|------|----|-------------|
| `backend/agent/state.py` | FR-005 | Add `stage_timings: dict` field to `ConversationState` TypedDict (last field, after `iteration_count`) |
| `backend/agent/nodes.py` | FR-005 | Add inline `time.perf_counter()` timing to 6–7 node functions; record into `state["stage_timings"]` |
| `backend/storage/sqlite_db.py` | FR-005 | Schema migration + `stage_timings_json` parameter in `create_query_trace()` + column in `get_trace()` SELECT |
| `backend/api/chat.py` | FR-005 | Extract `stage_timings` from `final_state`; pass as `stage_timings_json` to `create_query_trace()` |
| `backend/api/traces.py` | FR-008 | Add `stage_timings_json` to SELECT; add parsed `"stage_timings"` key (default `{}`) to response dict |

---

## Files Added (Tests)

| File | Agent | Purpose |
|------|-------|---------|
| `tests/unit/test_stage_timings.py` | A2 | TypedDict field presence; timing entry structure; state merge; failed stage; absent conditional stage |
| `tests/unit/test_stage_timings_db.py` | A3 | `create_query_trace()` signature; round-trip through SQLite; NULL returns `{}` |
| `tests/unit/api/test_traces_stage_timings.py` | A3 | `GET /api/traces/{id}` includes `"stage_timings"` key; parsed to dict; NULL returns `{}`; legacy trace readable |
| `tests/integration/test_performance.py` | A4 | EXTENDS existing file — adds 4+ new benchmark tests (SC-006, SC-007); preserves 2 existing spec-07 tests |

---

## Files NOT to Touch

| File | Reason |
|------|--------|
| `backend/ingestion/embedder.py` | ThreadPoolExecutor batch embedding already implemented in spec-06 |
| `backend/retrieval/reranker.py` | Singleton cross-encoder loading already in `main.py` lifespan (spec-06) |
| `backend/retrieval/searcher.py` | No changes needed for spec-14 |
| `backend/middleware.py` | Rate limiting complete from spec-08 |
| `backend/agent/edges.py` | Routing logic not involved in timing |
| `backend/agent/conversation_graph.py` | Read-only — confirms node names to map to stage names |
| `backend/config.py` | Read-only — confirms performance defaults already set; no changes needed |
| `backend/main.py` | Read-only except for FR-003's memory warning log (T039a — add structlog WARNING at startup; see tasks.md) |
| `tests/integration/test_performance.py` | The 2 existing spec-07 tests must remain UNTOUCHED — A4 only appends new tests |

Note on `backend/agent/research_graph.py`: The "not to touch" guideline has one override — if
the MetaReasoningGraph invocation lives there (not in `nodes.py`), A2 must add the
`"meta_reasoning"` conditional stage timing at that call site only. The broader routing
logic in `research_graph.py` must remain unchanged.

---

## Key Constraints

### Inline Timing — No Timer Class

Use `time.perf_counter()` inline per node. Do NOT create a shared `Timer` context manager or
any utility module. Do NOT create `backend/timing.py`. This keeps each node self-contained:

```python
_t0 = time.perf_counter()
try:
    # ... existing node logic, UNCHANGED ...
    result["stage_timings"] = {
        **state.get("stage_timings", {}),
        "stage_name": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
    }
    return result
except Exception:
    raise  # re-raise after timing; LangGraph handles the error
```

### LangGraph State Merge — MUST Spread Prior Timings

LangGraph uses "last value wins" for TypedDict fields. Each node MUST read the accumulated
dict from state and spread it before adding its own entry, or prior stages are lost:

```python
result["stage_timings"] = {
    **state.get("stage_timings", {}),   # preserve all prior stage entries
    "intent_classification": {"duration_ms": round((time.perf_counter() - _t0) * 1000, 1)},
}
```

Do NOT return just `{"stage_timings": {"intent_classification": {...}}}` — this would overwrite
all previously recorded stages.

### stage_timings Default Is `{}` — Not `[]`

The `stage_timings` field in `ConversationState` defaults to an empty dict `{}`. In `traces.py`
the `parse_json()` default must be `{}` (not `[]`). Legacy traces with NULL `stage_timings_json`
must return `"stage_timings": {}` in the API response.

### Conditional Stages — Absent Key Means Did Not Run

Do NOT insert `{"duration_ms": 0}` for stages that did not execute. An absent key in
`stage_timings_json` is the signal that the stage was skipped. The two conditional stages are:
- `grounded_verification` — only when `verify_groundedness()` node executes
- `meta_reasoning` — only when MetaReasoningGraph is triggered

### 6 Always-Present + 2 Conditional Stages

| Stage Name | Presence | Node |
|------------|----------|------|
| `intent_classification` | always | `classify_intent()` |
| `embedding` | always | query embedding call |
| `retrieval` | always | `HybridSearcher.search()` |
| `ranking` | always | cross-encoder reranker call |
| `answer_generation` | always | LLM call producing `final_response` |
| `grounded_verification` | conditional | `verify_groundedness()` |
| `meta_reasoning` | conditional | MetaReasoningGraph invocation |

### Failed Stage Format

When a node raises an exception, record duration up to the failure with `"failed": True` and
then re-raise. Do not suppress the original exception:

```json
{"duration_ms": 45.2, "failed": true}
```

### Schema Migration Is Idempotent

Wrap `ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT` in
`try/except aiosqlite.OperationalError` — SQLite raises `OperationalError` on duplicate column
name. This is the same pattern used for the `provider_name` column migration in spec-10.

### Chat Endpoint Is NDJSON — Not SSE

`Content-Type: application/x-ndjson`. There is no `text/event-stream`, no `data:` prefix, no
SSE. Tests consume the stream with `aiter_lines()`. Do not reference SSE anywhere in spec-14
code or tests.

### pathlib.Path for Test Fixtures

Use `tmp_path / "test.db"` (not `str(tmp_path) + "/test.db"`). The existing tests follow this
convention (Constitution Principle VIII).

---

## Exact Insertion Points

These code snippets were verified against the current codebase using Serena on branch
`013-security-hardening`. All file states confirmed as pre-FR-005.

### 1. state.py — Add `stage_timings` field

`ConversationState` currently ends at (body lines 28–29 in the class):

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

Note: `ConversationState` currently has 13 fields (session_id, messages, query_analysis,
sub_answers, selected_collections, llm_model, embed_model, intent, final_response, citations,
groundedness_result, confidence_score, iteration_count). After this change it has 14.

### 2. sqlite_db.py — create_query_trace() signature tail

Current (lines 444–446 of the method signature):

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

The INSERT column list and VALUES tuple must also be extended. Current INSERT (verified):

```sql
INSERT INTO query_traces
   (id, session_id, query, sub_questions_json, collections_searched,
    chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
    meta_reasoning_triggered, latency_ms, llm_model, embed_model,
    confidence_score, provider_name, created_at)
   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

After change — add `stage_timings_json` before `created_at` in the column list, and add
`stage_timings_json` before `now` in the VALUES tuple. Column count: 15 → 16.

### 3. sqlite_db.py — Schema migration

Add after the last existing `ALTER TABLE` migration block (the one for `provider_name`):

```python
try:
    await self.db.execute(
        "ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT"
    )
    await self.db.commit()
except aiosqlite.OperationalError:
    pass  # column already exists (idempotent re-run)
```

A1 will identify the exact migration method name and line number in the audit report.

### 4. traces.py — SELECT and response dict

Current SELECT (verified at lines 82–88 of `get_trace()`):

```sql
SELECT id, session_id, query, collections_searched,
          chunks_retrieved_json, confidence_score, latency_ms,
          llm_model, embed_model, sub_questions_json,
          reasoning_steps_json, strategy_switches_json,
          meta_reasoning_triggered, created_at
   FROM query_traces WHERE id = ?
```

After change — add `stage_timings_json`:

```sql
SELECT id, session_id, query, collections_searched,
          chunks_retrieved_json, confidence_score, latency_ms,
          llm_model, embed_model, sub_questions_json,
          reasoning_steps_json, strategy_switches_json,
          meta_reasoning_triggered, created_at,
          stage_timings_json
   FROM query_traces WHERE id = ?
```

Current response dict tail (verified — last two entries):

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

### 5. chat.py — Extract and pass stage_timings

Current code after graph stream completes (verified at the `# 3. Get final state` comment):

```python
            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
```

After change — add one line to extract stage_timings:

```python
            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
            stage_timings = final_state.get("stage_timings", {})  # FR-005
```

Current `create_query_trace()` call tail (verified — last two keyword arguments before the
closing paren):

```python
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
                )
```

After change — add `stage_timings_json`:

```python
                    meta_reasoning_triggered=bool(attempted),
                    provider_name=provider_name,
                    stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
                )
```

`json` is already imported in `chat.py`. Do not add a new import.

Also note: `chat.py`'s `initial_state` dict does NOT currently include a `stage_timings` key.
This is correct — LangGraph initializes the TypedDict field to its declared default. Since
`stage_timings: dict` has no explicit default in a TypedDict, A2 must verify that LangGraph
either uses `{}` or that `initial_state` explicitly sets `"stage_timings": {}`. If needed,
add `"stage_timings": {}` to `initial_state` in `chat.py` (A3's responsibility since it falls
in the chat.py scope).

---

## Wave Gates

| Gate | Condition | Blocks |
|------|-----------|--------|
| Wave 1 → Wave 2 | `Docs/Tests/spec14-a1-audit.md` exists; overall verdict PASS; all 5 target files confirmed in pre-FR state; `stage_timings_json` column absent; `ConversationState` has no `stage_timings` field; `create_query_trace()` has 15 parameters | Wave 2 spawn |
| Wave 2 → Wave 3 | `spec14-a2.status = PASSED` AND `spec14-a3.status = PASSED`; no new failures above 39 baseline | Wave 3 spawn |
| Final | `spec14-a4-full.status = PASSED`; SC-006 automated test passes; SC-007 automated test passes; pre-existing failure count = 39; `Docs/Tests/spec14-a4-final.md` written | Spec-14 complete |

---

## Testing Protocol

NEVER run pytest directly inside Claude Code. All testing uses the external runner.

```bash
# Trigger a run
zsh scripts/run-tests-external.sh -n <name> <target>

# Poll status
cat Docs/Tests/<name>.status        # RUNNING | PASSED | FAILED | ERROR

# Read results (token-efficient)
cat Docs/Tests/<name>.summary       # ~20 lines

# Full output if needed
cat Docs/Tests/<name>.log
```

### External Test Run Schedule

| Agent | Run name | Target | When |
|-------|----------|--------|------|
| A2 | `spec14-a2` | `tests/unit/` | After T016 (test file written) |
| A3 | `spec14-a3` | `tests/unit/` | After all 3 test files written |
| A4 | `spec14-a4-full` | `tests/` | Wave 3 start (before adding new benchmarks) |
| A4 | `spec14-a4-bench` | `tests/integration/test_performance.py` | After T031 (new benchmark tests written) |

### New Test File Locations

```
tests/
  unit/
    test_stage_timings.py               # A2 — FR-005 state field + timing structure
    test_stage_timings_db.py            # A3 — FR-005 storage round-trip
    api/
      test_traces_stage_timings.py      # A3 — FR-008 API exposure
  integration/
    test_performance.py                 # A4 — EXTENDS existing; adds SC-006, SC-007 benchmarks
```

---

## Acceptance Criteria Reference (8 Success Criteria)

A4 verifies all 8 in T033. SC-006 and SC-007 must have passing automated tests and cannot
be marked skip. SC-001 through SC-005 and SC-008 may be marked skip in CI if they require
reference hardware or a live inference model; they must document the verification procedure.

| SC | Description | CI Requirement |
|----|-------------|----------------|
| SC-001 | Simple factoid queries: first token < 1.5 s on reference hardware | Skip allowed (document procedure) |
| SC-002 | Complex analytical queries: first token < 6 s on reference hardware | Skip allowed (document procedure) |
| SC-003 | 10-page PDF fully indexed and searchable < 3 s | Skip allowed (document procedure) |
| SC-004 | 200-page PDF fully indexed and searchable < 15 s | Skip allowed (document procedure) |
| SC-005 | Backend idle memory < 600 MB (excluding inference engine) | Skip allowed (document measurement) |
| SC-006 | 3 simultaneous queries from independent sessions complete without error | **MUST pass — automated test required** |
| SC-007 | Every trace contains per-stage breakdown with ≥5 always-present named stages, accessible via `GET /api/traces/{id}` | **MUST pass — automated test required** |
| SC-008 | Response token streaming ≥50 output events per second | Skip allowed (document measurement) |

---

## What Is Already Built — Do Not Reimplement

| Component | Spec | Location |
|-----------|------|----------|
| SQLite WAL mode | spec-07 | `backend/storage/sqlite_db.py` PRAGMA in init |
| Singleton cross-encoder loading | spec-06/07 | `backend/main.py` lifespan handler |
| ThreadPoolExecutor batch embedding | spec-06 | `backend/ingestion/embedder.py` |
| Rust ingestion worker | spec-06 | `ingestion-worker/` |
| Qdrant batch upserts + UpsertBuffer | spec-06 | `backend/ingestion/embedder.py` |
| NDJSON streaming for chat | spec-08/09 | `Content-Type: application/x-ndjson` |
| `time.monotonic()` for total `latency_ms` | spec-08 | `backend/api/chat.py` (keep as-is) |
| `latency_ms` column in `query_traces` | spec-07/08 | `backend/storage/sqlite_db.py` |
| `reasoning_steps_json` column | spec-07 | `query_traces` table |
| `strategy_switches_json` column | spec-07 | `query_traces` table |
| Rate limiting, CORS middleware | spec-08 | `backend/middleware.py` |
| Security sanitization | spec-13 | `backend/api/chat.py`, `backend/api/ingest.py` |
| Circuit breakers + retry | spec-05 | `backend/agent/nodes.py`, `backend/retrieval/searcher.py` |
| 2 existing performance tests | spec-07 | `tests/integration/test_performance.py` |

---

## Source Documents (Reading Order for Agents)

Agents read their own instruction file first. The instruction files reference these for context:

1. `Docs/PROMPTS/spec-14-performance/14-plan.md` — orchestration protocol and Appendix
2. `specs/014-performance-budgets/spec.md` — 8 FRs, 8 SCs
3. `specs/014-performance-budgets/data-model.md` — schema changes, ConversationState lifecycle
4. `specs/014-performance-budgets/contracts/trace-detail-api.md` — FR-008 API contract
5. `specs/014-performance-budgets/research.md` — R-001 through R-007 design decisions
6. `specs/014-performance-budgets/tasks.md` — full 48-task list across 7 phases
