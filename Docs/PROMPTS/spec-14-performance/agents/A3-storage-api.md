# A3: Storage and API Layer

**Agent type**: `python-expert`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You implement the storage and API changes for spec-14's `stage_timings_json` column. This includes:
the schema migration in SQLite, the `create_query_trace()` parameter extension, extracting
`stage_timings` from the chat pipeline's final state, and exposing it via the traces API.

You run in parallel with A2 — you modify the storage and API layer, A2 modifies the agent layer.
Do NOT touch `backend/agent/`, `backend/retrieval/`, or any files outside your scope.

## Assigned Tasks

T017–T025 from `Docs/PROMPTS/spec-14-performance/14-plan.md` (Wave 2 — A3 Implementation).

| Task | File | Description |
|------|------|-------------|
| T017 | `backend/storage/sqlite_db.py` | Schema migration: add `stage_timings_json TEXT` column to `query_traces` |
| T018 | `backend/storage/sqlite_db.py` | Add `stage_timings_json: str \| None = None` parameter to `create_query_trace()` |
| T019 | `backend/api/chat.py` | Extract `stage_timings` from `final_state`; pass to `create_query_trace()` |
| T020 | `backend/api/traces.py` | Add `stage_timings_json` to SELECT; add parsed `"stage_timings"` to response dict |
| T021 | `tests/unit/test_stage_timings_db.py` | Write unit tests for storage round-trip |
| T022 | `tests/unit/api/test_traces_stage_timings.py` | Write unit tests for API exposure |
| T023 | (run) | Run `spec14-a3 tests/unit/` via external runner |
| T024 | (verify) | Confirm PASSED; confirm no new failures in pre-existing tests |
| T025 | (report) | Report completion to orchestrator |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-14-performance/14-plan.md` — full orchestration protocol; read "Key Constraints"
   and "Appendix: Exact Insertion Points" sections carefully
2. `Docs/Tests/spec14-a1-audit.md` — A1's audit report; confirms exact line numbers and insertion points
3. `specs/014-performance-budgets/spec.md` — 8 FRs (focus on FR-005 and FR-008)
4. `specs/014-performance-budgets/data-model.md` — full `query_traces` schema and invariants
5. `specs/014-performance-budgets/contracts/trace-detail-api.md` — FR-008 API contract
6. `specs/014-performance-budgets/research.md` — R-003 (migration idempotency) and R-004 (`{}` default)

## T017 — Schema Migration (backend/storage/sqlite_db.py)

Use `find_symbol` with name_path `SQLiteDB/_migrate` (or search for the migration method) to read
the current migration code. Compare against how `provider_name` or `reasoning_steps_json` columns
were added to understand the existing pattern.

**Change**: Add the following migration step using the same idempotent pattern:

```python
try:
    await self.db.execute(
        "ALTER TABLE query_traces ADD COLUMN stage_timings_json TEXT"
    )
    await self.db.commit()
except aiosqlite.OperationalError:
    pass  # column already exists (idempotent re-run)
```

Place this block immediately after the existing `provider_name` column migration (the last `ALTER
TABLE` block). The `try/except aiosqlite.OperationalError` pattern is required — SQLite raises
`OperationalError: duplicate column name` on `ALTER TABLE ADD COLUMN` re-runs.

## T018 — create_query_trace() Parameter Extension (backend/storage/sqlite_db.py)

Use `find_symbol` with name_path `SQLiteDB/create_query_trace`, `include_body=true` to read the
full method body.

**Change 1 — Add parameter** (after `provider_name: str | None = None`):

```python
        meta_reasoning_triggered: bool = False,
        provider_name: str | None = None,
        stage_timings_json: str | None = None,
    ) -> None:
```

**Change 2 — Update INSERT**: Add `stage_timings_json` to both the column name list and the
VALUES tuple. The column count increases from 15 to 16. Both the column string and the values
tuple MUST stay in sync — an off-by-one here will cause a runtime error.

Read A1's audit for the exact INSERT structure, then extend it. The final entry in the VALUES
tuple changes from:

```python
    ...,
    provider_name,
)
```

To:

```python
    ...,
    provider_name,
    stage_timings_json,
)
```

## T019 — Extract stage_timings in chat.py (backend/api/chat.py)

Use `find_symbol` with name_path `generate`, `include_body=true` to read the current `generate()`
function body.

**Change 1** — After `final_state = graph.get_state(config).values` and `latency_ms = ...`,
add one line to extract stage timings from the graph's completed state:

```python
            # 3. Get final state after stream completes
            final_state = graph.get_state(config).values
            latency_ms = int((time.monotonic() - start_time) * 1000)
            stage_timings = final_state.get("stage_timings", {})  # FR-005
```

**Change 2** — In the `create_query_trace()` call, add `stage_timings_json` as the last keyword
argument (after `provider_name`). Read A1's audit for the exact call site. The addition is:

```python
                    provider_name=provider_name,
                    stage_timings_json=json.dumps(stage_timings) if stage_timings else None,
```

Note: `json` is already imported in `chat.py` (used for `json.dumps` elsewhere). Do NOT add a
new import. Verify with `find_symbol` if unsure.

## T020 — Extend traces.py Response (backend/api/traces.py)

Use `find_symbol` with name_path `get_trace`, `include_body=true`. Read A1's audit for the
exact SELECT statement and response dict structure.

**Change 1 — SELECT**: Add `stage_timings_json` as the last selected column:

```sql
SELECT id, session_id, query, collections_searched,
       chunks_retrieved_json, confidence_score, latency_ms,
       llm_model, embed_model, sub_questions_json,
       reasoning_steps_json, strategy_switches_json,
       meta_reasoning_triggered, created_at,
       stage_timings_json
FROM query_traces WHERE id = ?
```

**Change 2 — Response dict**: Add `"stage_timings"` as the last key in the response dict.
Use `{}` (empty dict) as the default — NOT `[]` (empty list). This is critical:

```python
        "reasoning_steps": parse_json(d.get("reasoning_steps_json"), []),
        "strategy_switches": parse_json(d.get("strategy_switches_json"), []),
        "stage_timings": parse_json(d.get("stage_timings_json"), {}),
    }
```

**Why `{}`**: `stage_timings` is a key→entry mapping (dict), not a sequence. Returning `{}`
for legacy traces (NULL `stage_timings_json`) allows consumers to distinguish "no stages recorded"
from "stages is a list." The `parse_json(val, {})` call already supports custom defaults.

## T021 — Write Storage Unit Tests

Write `tests/unit/test_stage_timings_db.py`:

```python
"""Unit tests for stage_timings_json storage round-trip (FR-005)."""
import json
import pytest
import aiosqlite
from pathlib import Path


@pytest.fixture
async def db(tmp_path):
    """Create an in-memory SQLite DB with the query_traces schema for testing."""
    # Use SQLiteDB from backend.storage.sqlite_db or create a minimal table directly
    from backend.storage.sqlite_db import SQLiteDB
    db = SQLiteDB(db_path=str(tmp_path / "test.db"))
    await db.initialize()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_create_query_trace_accepts_stage_timings_json(db):
    """create_query_trace() accepts stage_timings_json without error."""
    import inspect
    from backend.storage.sqlite_db import SQLiteDB
    sig = inspect.signature(SQLiteDB.create_query_trace)
    assert "stage_timings_json" in sig.parameters


@pytest.mark.asyncio
async def test_stage_timings_round_trips_through_sqlite(db):
    """stage_timings written as JSON is returned correctly from get_trace()."""
    import uuid
    timings = {
        "intent_classification": {"duration_ms": 180.4},
        "embedding": {"duration_ms": 45.1},
    }
    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    await db.create_query_trace(
        id=trace_id,
        session_id=session_id,
        query="test query",
        collections_searched=json.dumps(["col1"]),
        confidence_score=72,
        latency_ms=500,
        stage_timings_json=json.dumps(timings),
    )
    trace = await db.get_trace(trace_id)
    assert trace is not None
    assert trace["stage_timings"] == timings


@pytest.mark.asyncio
async def test_null_stage_timings_returns_empty_dict(db):
    """A trace written without stage_timings_json (None) returns stage_timings: {} from get_trace()."""
    import uuid
    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    await db.create_query_trace(
        id=trace_id,
        session_id=session_id,
        query="legacy query",
        collections_searched=json.dumps([]),
        confidence_score=50,
        latency_ms=200,
        # stage_timings_json not passed (defaults to None)
    )
    trace = await db.get_trace(trace_id)
    assert trace is not None
    assert trace["stage_timings"] == {}
```

Adjust imports and fixture construction to match the actual `SQLiteDB` constructor signature
(read `backend/storage/sqlite_db.py` for the exact parameters). If `get_trace()` is not on
`SQLiteDB`, locate the correct method name from A1's audit.

## T022 — Write API Unit Tests

Write `tests/unit/api/test_traces_stage_timings.py`:

```python
"""Unit tests for GET /api/traces/{id} stage_timings extension (FR-008)."""
import json
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_trace_response_includes_stage_timings_key(app_with_trace):
    """GET /api/traces/{id} always includes stage_timings key in response."""
    async with AsyncClient(transport=ASGITransport(app=app_with_trace.app),
                           base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{app_with_trace.trace_id}")
    assert resp.status_code == 200
    assert "stage_timings" in resp.json()


@pytest.mark.asyncio
async def test_populated_stage_timings_parsed_to_dict(app_with_stage_timings):
    """Populated stage_timings_json in DB is returned as dict, not raw string."""
    async with AsyncClient(transport=ASGITransport(app=app_with_stage_timings.app),
                           base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{app_with_stage_timings.trace_id}")
    data = resp.json()
    assert isinstance(data["stage_timings"], dict)
    assert "intent_classification" in data["stage_timings"]


@pytest.mark.asyncio
async def test_null_stage_timings_json_returns_empty_dict(app_with_legacy_trace):
    """NULL stage_timings_json in DB returns stage_timings: {} (not null, not [])."""
    async with AsyncClient(transport=ASGITransport(app=app_with_legacy_trace.app),
                           base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{app_with_legacy_trace.trace_id}")
    data = resp.json()
    assert data["stage_timings"] == {}


@pytest.mark.asyncio
async def test_legacy_trace_is_readable_without_error(app_with_legacy_trace):
    """Legacy trace (NULL stage_timings_json) does not raise 500."""
    async with AsyncClient(transport=ASGITransport(app=app_with_legacy_trace.app),
                           base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{app_with_legacy_trace.trace_id}")
    assert resp.status_code == 200
```

**Test setup approach**: Look at existing tests in `tests/unit/api/` (e.g., existing trace tests
from spec-08) to understand the fixture pattern used for creating test app instances. Reuse
existing conftest fixtures wherever possible. If the existing test fixtures don't support inserting
stage_timings_json directly, use `aiosqlite` to insert a row directly with `NULL` or a JSON value
and then call the API.

## T023 — Run External Tests

```bash
zsh scripts/run-tests-external.sh -n spec14-a3 tests/unit/
```

Poll until complete:
```bash
cat Docs/Tests/spec14-a3.status
```

Read results:
```bash
cat Docs/Tests/spec14-a3.summary
```

## T024 — Confirm PASSED

Verify:
- `Docs/Tests/spec14-a3.status` is `PASSED`
- No new failures in pre-existing `sqlite_db`, `chat`, or `traces` tests
- Pre-existing failure count has not increased beyond 39

If failures exist in your new test files, fix them before reporting completion.
If pre-existing tests that were passing before your changes now fail, investigate and fix the
regression before reporting.

## T025 — Report Completion

Report completion to the orchestrator with:
- `spec14-a3.status = PASSED`
- Count of new tests added
- Any unexpected findings (e.g., if A1's insertion points were incorrect)

## Key Constraints

- **NEVER run pytest directly** — use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **`stage_timings` default is `{}`** (empty dict) — NOT `[]` — this is a dict-typed field, not a list
- **Schema migration MUST be idempotent** — wrap in `try/except aiosqlite.OperationalError`
- **`json` already imported in chat.py** — do NOT add a new import
- **INSERT column count sync** — both the column name list and VALUES tuple in `create_query_trace()`
  must be extended together; mismatched counts cause runtime errors
- **NDJSON only** — the chat endpoint is `application/x-ndjson`, not SSE
- **Do NOT touch**: `backend/agent/`, `backend/retrieval/`, `backend/config.py`, `backend/main.py`
- **Pre-existing failures: 39** — any increase is a regression; investigate before reporting
- **pathlib.Path for test fixtures** — use `tmp_path / "test.db"`, not string concatenation

## Files Modified

| File | Change |
|------|--------|
| `backend/storage/sqlite_db.py` | Migration + `create_query_trace()` parameter + `get_trace()` SELECT |
| `backend/api/chat.py` | Extract `stage_timings` from `final_state`; pass to `create_query_trace()` |
| `backend/api/traces.py` | Add `stage_timings_json` to SELECT; add `"stage_timings"` to response |

## New Files Created

| File | Purpose |
|------|---------|
| `tests/unit/test_stage_timings_db.py` | Storage round-trip unit tests |
| `tests/unit/api/test_traces_stage_timings.py` | API exposure unit tests |

## Success Criteria

- `stage_timings_json TEXT` column migration is present and idempotent in `sqlite_db.py`
- `create_query_trace()` accepts `stage_timings_json: str | None = None` as 16th parameter
- `chat.py` extracts `stage_timings` from `final_state` and passes it as `stage_timings_json`
- `traces.py` selects `stage_timings_json` and returns `"stage_timings": {}` for NULL
- Both test files exist with passing tests
- `Docs/Tests/spec14-a3.status` is `PASSED`
- No new failures in pre-existing unit tests

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will verify both `spec14-a2.status = PASSED`
and `spec14-a3.status = PASSED` before proceeding to Wave 3 (A4).
