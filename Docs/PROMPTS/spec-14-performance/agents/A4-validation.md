# A4: Benchmarks and Final Validation

**Agent type**: `quality-engineer`
**Model**: **Sonnet 4.6** (`model="sonnet"`)

You are the final quality gate for spec-14. You run the full regression suite, add benchmark
tests for all 8 success criteria, verify the implementation end-to-end, and write the final
acceptance report.

## Assigned Tasks

T026–T035 from `Docs/PROMPTS/spec-14-performance/14-plan.md` (Wave 3 — Benchmarks and Final Validation).

| Task | Description |
|------|-------------|
| T026 | Run full test suite `spec14-a4-full tests/` — confirm no regressions |
| T027 | Verify the 2 existing performance tests still pass |
| T028 | Add `test_stage_timings_present()` to `test_performance.py` (SC-007) |
| T029 | Add `test_stage_timings_sum_consistent_with_total()` to `test_performance.py` |
| T030 | Add `test_legacy_trace_readable()` to `test_performance.py` |
| T031 | Add `test_concurrent_queries_no_errors()` to `test_performance.py` (SC-006) |
| T032 | Run `spec14-a4-bench tests/integration/test_performance.py` — confirm new tests pass |
| T033 | Verify all 8 success criteria from spec.md |
| T034 | Confirm pre-existing failure count is 39 |
| T035 | Write final report `Docs/Tests/spec14-a4-final.md` |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-14-performance/14-plan.md` — full orchestration protocol and acceptance criteria
2. `Docs/Tests/spec14-a1-audit.md` — A1's pre-flight audit (confirms target file states)
3. `Docs/Tests/spec14-a2.summary` — A2's unit test results
4. `Docs/Tests/spec14-a3.summary` — A3's unit test results
5. `specs/014-performance-budgets/spec.md` — 8 SCs to verify
6. `specs/014-performance-budgets/quickstart.md` — verification procedures and CI skip guidance

## T026 — Full Regression Suite

```bash
zsh scripts/run-tests-external.sh -n spec14-a4-full tests/
```

Poll until complete:
```bash
cat Docs/Tests/spec14-a4-full.status
```

Read results:
```bash
cat Docs/Tests/spec14-a4-full.summary
```

**Expected**: `PASSED`. All new spec-14 tests pass. Pre-existing failure count = 39 (no increase).

If the pre-existing failure count has increased, investigate: read `Docs/Tests/spec14-a4-full.log`
to identify the new failures. Determine if they stem from A2 or A3's changes. Fix regressions
before proceeding to T028.

## T027 — Verify Existing Performance Tests

Read `tests/integration/test_performance.py`. Confirm:
- `test_parent_retrieval_latency_target` is present and unchanged
- `test_search_latency_target` is present and unchanged
- Both pass in the T026 run results (or are marked skip — check their status in the summary)

These two tests must NOT be modified by spec-14. If they are now failing in a way they were
not failing before, A2 or A3 introduced a regression — investigate.

## T028 — test_stage_timings_present() (SC-007)

Add to `tests/integration/test_performance.py` — this is NOT marked skip; it must produce a
passing automated test. It runs against a real database and real API.

```python
@pytest.mark.asyncio
async def test_stage_timings_present():
    """SC-007: Every trace produced after spec-14 has stage_timings with ≥5 stages.

    Requires: running FastAPI server + SQLite DB (starts within test using app factory).
    This test must be automated (not skipped) — it is a required SC-006/SC-007 gate.
    """
    import uuid
    from httpx import AsyncClient, ASGITransport
    from backend.main import create_app  # adjust import to match actual app factory

    app = create_app()
    # Pre-condition: a collection must exist for the query to search
    # Use an existing collection or create a minimal one if none exists

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        # Submit a chat query
        session_id = str(uuid.uuid4())
        resp = await client.post(
            "/api/chat",
            json={"session_id": session_id, "message": "What is this system?"},
        )
        # Collect the NDJSON stream
        chunks = []
        async for line in resp.aiter_lines():
            if line.strip():
                import json as _json
                chunks.append(_json.loads(line))

        # Find the done event which contains the trace_id
        done_events = [c for c in chunks if c.get("type") == "done"]
        assert done_events, "Stream did not produce a 'done' event"
        trace_id = done_events[-1].get("trace_id") or done_events[-1].get("data", {}).get("trace_id")
        assert trace_id, "done event does not contain trace_id"

        # Fetch the trace
        trace_resp = await client.get(f"/api/traces/{trace_id}")
        assert trace_resp.status_code == 200
        trace = trace_resp.json()

        # SC-007 assertion: stage_timings has ≥5 always-present stages
        assert "stage_timings" in trace
        timings = trace["stage_timings"]
        required_stages = {
            "intent_classification", "embedding", "retrieval", "ranking", "answer_generation"
        }
        present = set(timings.keys())
        assert required_stages.issubset(present), (
            f"Missing required stages: {required_stages - present}. "
            f"Present: {present}"
        )
        for stage, entry in timings.items():
            assert isinstance(entry.get("duration_ms"), (int, float)), (
                f"Stage {stage!r} has non-numeric duration_ms: {entry!r}"
            )
```

**Implementation note**: Read the existing conftest.py and the two passing spec-07 tests to
understand how the test app is instantiated. Adapt to match that pattern. If the app requires
a running Qdrant and Ollama instance, this test may need to be marked `@pytest.mark.integration`
(with a note) but it must NOT be marked `@pytest.mark.skip` — it needs to run in CI when live
services are available.

## T029 — test_stage_timings_sum_consistent_with_total()

Add to `tests/integration/test_performance.py`:

```python
@pytest.mark.asyncio
async def test_stage_timings_sum_consistent_with_total():
    """SC-007 consistency: sum of stage duration_ms ≤ 150% of total latency_ms.

    Accounts for LangGraph overhead, routing, and serialization not attributed to a stage.
    """
    # Fetch a trace that was just produced (reuse the trace from the previous test
    # or run another query). Assert sum(duration_ms) <= latency_ms * 1.5
    # ...
    pass  # implement using same app factory pattern as T028
```

The key assertion: `sum(entry["duration_ms"] for entry in timings.values()) <= trace["latency_ms"] * 1.5`

## T030 — test_legacy_trace_readable()

Add to `tests/integration/test_performance.py` — this test does NOT require live services:

```python
@pytest.mark.asyncio
async def test_legacy_trace_readable():
    """Legacy trace (stage_timings_json = NULL) returns stage_timings: {} without error.

    Simulates a trace produced before spec-14 was deployed. Does not require live services.
    """
    import uuid
    import aiosqlite
    from pathlib import Path
    from httpx import AsyncClient, ASGITransport
    from backend.main import create_app
    from backend.config import Settings

    settings = Settings()
    db_path = Path(settings.db_path)  # adjust to actual config field name

    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())

    # Insert a row with stage_timings_json = NULL directly into SQLite
    async with aiosqlite.connect(str(db_path)) as db:
        await db.execute(
            """INSERT INTO query_traces
               (id, session_id, query, collections_searched,
                confidence_score, latency_ms, meta_reasoning_triggered, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
            (trace_id, session_id, "legacy query", "[]", 50, 200, 0),
        )
        await db.commit()

    # Now fetch via API — should return 200 with stage_timings: {}
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        resp = await client.get(f"/api/traces/{trace_id}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["stage_timings"] == {}, (
        f"Expected stage_timings: {{}} for legacy trace, got: {data['stage_timings']!r}"
    )
```

Adjust `settings.db_path` to match the actual Settings field name (read `backend/config.py` or
check A1's audit if it noted the field name).

## T031 — test_concurrent_queries_no_errors() (SC-006)

Add to `tests/integration/test_performance.py`:

```python
@pytest.mark.asyncio
async def test_concurrent_queries_no_errors():
    """SC-006: 3 simultaneous queries from independent sessions all complete without error.

    Sends 3 queries concurrently using asyncio.gather(). All must return HTTP 200
    and complete within 30 seconds. Requires live services (Qdrant, Ollama).
    """
    import asyncio
    import uuid
    from httpx import AsyncClient, ASGITransport
    from backend.main import create_app

    app = create_app()

    async def run_query(client: AsyncClient, session_id: str) -> int:
        """Submit a query and collect the full NDJSON stream. Returns HTTP status code."""
        resp = await client.post(
            "/api/chat",
            json={"session_id": session_id, "message": "Describe the key concepts."},
            timeout=30.0,
        )
        # Drain the stream
        async for _ in resp.aiter_lines():
            pass
        return resp.status_code

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as client:
        session_ids = [str(uuid.uuid4()) for _ in range(3)]
        results = await asyncio.gather(
            *[run_query(client, sid) for sid in session_ids],
            return_exceptions=True,
        )

    for i, result in enumerate(results):
        assert not isinstance(result, Exception), (
            f"Query {i} raised an exception: {result}"
        )
        assert result == 200, f"Query {i} returned status {result}, expected 200"
```

Mark with `@pytest.mark.integration` since this requires live Qdrant + Ollama. Unlike SC-001
through SC-005, SC-006 must produce a passing automated test — it MUST NOT be marked skip.

## T032 — Run Benchmark Tests

```bash
zsh scripts/run-tests-external.sh -n spec14-a4-bench tests/integration/test_performance.py
```

Poll until complete:
```bash
cat Docs/Tests/spec14-a4-bench.status
```

Read results:
```bash
cat Docs/Tests/spec14-a4-bench.summary
```

**Expected**: `PASSED`. The new tests (T028–T031) pass. The 2 existing spec-07 tests are
unchanged. Tests requiring live inference that are not available in CI should be marked
`@pytest.mark.integration` (they will still run in environments with live services).

## T033 — Verify All 8 Success Criteria

Read `specs/014-performance-budgets/spec.md` for the exact SC definitions. Verify each:

| SC | Description | Verification Method | CI status |
|----|-------------|---------------------|-----------|
| SC-001 | Simple query first token < 1.5 s | Benchmark test or config inspection | Skip if no live inference |
| SC-002 | Complex query first token < 6 s | Benchmark test or config inspection | Skip if no live inference |
| SC-003 | 10-page PDF indexable < 3 s | Benchmark test | Skip if no live services |
| SC-004 | 200-page PDF indexable < 15 s | Benchmark test | Skip if no live services |
| SC-005 | Backend idle < 600 MB (excl. inference) | Document measurement procedure | Skip in CI |
| SC-006 | 3 concurrent queries without error | `test_concurrent_queries_no_errors` PASSES | Must pass |
| SC-007 | Stage timings in every trace with ≥5 stages | `test_stage_timings_present` PASSES | Must pass |
| SC-008 | Streaming ≥50 events/sec | Document measurement procedure | Skip in CI |

For SC-005: Read `backend/main.py` and note all models loaded at startup (cross-encoder, etc.).
Estimate memory footprint from model sizes. Document the measurement procedure (how to measure
with `ps aux` or `psutil`) in the final report.

For SC-008: Describe how to measure streaming token rate using the NDJSON endpoint with a
high-throughput Ollama model. Document the procedure but do not require automation.

## T034 — Confirm Pre-Existing Failure Count

Read `Docs/Tests/spec14-a4-full.summary` (from T026). Confirm the pre-existing failure count
is exactly 39. This was established in spec-13's baseline.

If the count is greater than 39, investigate whether the new failures are:
1. Caused by A2 or A3 changes (regression — must be fixed)
2. Pre-existing failures that were previously silently failing but are now reported differently
3. Environmental issues unrelated to the code changes

Document your findings in the final report. Do NOT proceed to T035 with PASS verdict if there
are new regressions.

## T035 — Write Final Report

Write `Docs/Tests/spec14-a4-final.md` using this structure:

```markdown
# Spec-14 Final Acceptance Report
Date: [today]
Branch: 014-performance-budgets

## Regression Results
- Full suite run: spec14-a4-full
- Total tests: [N]
- Passed: [N]
- Failed (pre-existing): 39
- Failed (new): 0
- Pre-existing failure count unchanged: YES / NO

## Success Criteria Verification

| SC | Description | Status | Evidence |
|----|-------------|--------|----------|
| SC-001 | Simple query < 1.5 s | PASS / SKIP | [test name or config inspection note] |
| SC-002 | Complex query < 6 s | PASS / SKIP | [test name or config inspection note] |
| SC-003 | 10-page PDF < 3 s | PASS / SKIP | [test name or skip note] |
| SC-004 | 200-page PDF < 15 s | PASS / SKIP | [test name or skip note] |
| SC-005 | Idle < 600 MB | SKIP | [measurement procedure] |
| SC-006 | 3 concurrent queries | PASS | test_concurrent_queries_no_errors |
| SC-007 | Stage timings present | PASS | test_stage_timings_present |
| SC-008 | Streaming ≥50 events/s | SKIP | [measurement procedure] |

## stage_timings_json Round-Trip Verification
- Schema migration applied: YES
- create_query_trace() accepts stage_timings_json: YES
- chat.py extracts and passes stage_timings: YES
- traces.py returns "stage_timings" in response: YES
- Legacy trace (NULL) returns {}: VERIFIED by test_legacy_trace_readable

## New Test Summary
- New tests added: [N]
- Test files:
  - tests/unit/test_stage_timings.py (A2)
  - tests/unit/test_stage_timings_db.py (A3)
  - tests/unit/api/test_traces_stage_timings.py (A3)
  - tests/integration/test_performance.py (+[N] new tests from A4)

## Overall Verdict
PASS / FAIL

[Explanation if FAIL]
```

## Key Constraints

- **NEVER run pytest directly** — use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **SC-006 and SC-007 MUST be automated tests** (not skip) — these are the only two SCs that
  must produce passing automated gate tests in every run
- **Do NOT modify the 2 existing spec-07 tests** — `test_parent_retrieval_latency_target` and
  `test_search_latency_target` must remain exactly as they are
- **NDJSON stream**: The chat endpoint returns `application/x-ndjson`; consume with `aiter_lines()`
  not SSE handling
- **Pre-existing failures: 39** — any increase is a regression; investigate and fix before PASS
- **Use Serena MCP** for code reading when verifying implementation details

## Success Criteria

- `Docs/Tests/spec14-a4-full.status` is `PASSED`
- Pre-existing failure count remains at exactly 39
- SC-006 verified by `test_concurrent_queries_no_errors` (passing automated test)
- SC-007 verified by `test_stage_timings_present` (passing automated test)
- `stage_timings_json` round-trip confirmed end-to-end in the report
- Final report written to `Docs/Tests/spec14-a4-final.md`
- Overall verdict is PASS

## After Completing All Tasks

Report completion to the orchestrator with the path to `Docs/Tests/spec14-a4-final.md` and
the overall PASS/FAIL verdict. The orchestrator will read the final report and close the
spec-14 implementation.
