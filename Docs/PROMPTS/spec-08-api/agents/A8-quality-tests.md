# A8: Quality + Tests + Regression

**Agent type:** `quality-engineer`
**Model:** Sonnet 4.6
**Tasks:** T030, T031, T032, T033, T034
**Wave:** 5 (serial -- runs after ALL other waves complete)

---

## Assigned Tasks

### T030: Write tests/integration/test_api_integration.py
Full request cycle per endpoint group.

### T031: Write tests/integration/test_rate_limiting.py
Burst rate limit tests for all 4 categories.

### T032: Run ruff check on all modified/created files
Lint all files touched by spec-08.

### T033: Run full regression
Verify zero regressions vs spec-07 baseline (238 tests must still pass).

### T034: Write tests/integration/test_concurrent_streams.py
10 concurrent chat streams without event loss (SC-010).

---

## File Targets

| File | Action |
|------|--------|
| `tests/integration/test_api_integration.py` | Create new |
| `tests/integration/test_rate_limiting.py` | Create new |
| `tests/integration/test_concurrent_streams.py` | Create new |

---

## Prerequisites

All Waves 1-4 must have passed their checkpoint gates before starting Wave 5. Verify by reading the gate test results:

```bash
cat Docs/Tests/spec08-gate1.status   # Must be PASSED
cat Docs/Tests/spec08-gate2.status   # Must be PASSED
cat Docs/Tests/spec08-gate3.status   # Must be PASSED
cat Docs/Tests/spec08-gate4.status   # Must be PASSED
```

If any gate has not passed, do NOT proceed. Report the failure to the lead orchestrator.

---

## T030: test_api_integration.py

Full request cycle tests using FastAPI `TestClient`. These test the complete request path through the app, not individual routers.

### Setup

```python
import json
from fastapi.testclient import TestClient
from backend.main import create_app

# Create app with mocked dependencies
# Mock db, qdrant, key_manager on app.state
```

### Test Cases

**Collections (FR-002, FR-003, FR-005):**
1. `POST /api/collections` with valid name -> 201, response has id, name, document_count
2. `POST /api/collections` with duplicate name -> 409 with code `COLLECTION_NAME_CONFLICT`
3. `POST /api/collections` with invalid name (e.g., "My Docs!") -> 400 with code `COLLECTION_NAME_INVALID`
4. `DELETE /api/collections/{id}` -> 204 with cascade (verify jobs cancelled)

**Documents (FR-006, FR-012):**
5. `GET /api/documents` -> 200 with documents list
6. `GET /api/documents/{id}` -> 200 or 404 with `DOCUMENT_NOT_FOUND`
7. `DELETE /api/documents/{id}` -> 204

**Ingestion (FR-007, FR-008, FR-011):**
8. `POST /api/collections/{id}/ingest` with valid file -> 202
9. `POST /api/collections/{id}/ingest` with `.exe` file -> 400 with `FILE_FORMAT_NOT_SUPPORTED`
10. `POST /api/collections/{id}/ingest` with oversized file -> 413 with `FILE_TOO_LARGE`
11. `GET /api/collections/{id}/ingest/{job_id}` -> 200 with job status

**Chat (FR-013, FR-014, FR-015):**
12. `POST /api/chat` -> 200 with `Content-Type: application/x-ndjson`
13. Parse response lines: first is `session`, last is `done`
14. Confidence score in response is int 0-100

**Providers (FR-018, SC-005):**
15. `GET /api/providers` -> 200, verify `has_key` is bool, no `api_key` field
16. `PUT /api/providers/{name}/key` -> 200 with `{name, has_key: true}`
17. `DELETE /api/providers/{name}/key` -> 200 with `{name, has_key: false}`
18. Verify across ALL provider responses: `api_key_encrypted` never present, `api_key` never present

**Settings (FR-020):**
19. `GET /api/settings` -> 200 with all 7 fields
20. `PUT /api/settings` with `{confidence_threshold: 75}` -> 200, verify change persisted

**Traces + Stats (FR-021, FR-023):**
21. `GET /api/traces` -> 200 with traces list
22. `GET /api/traces?session_id=nonexistent` -> 200 with empty list (NOT 404)
23. `GET /api/stats` -> 200 with all 7 numeric fields

**Health (FR-022):**
24. `GET /api/health` -> 200 with services list

**Error Format (FR-026):**
25. Every error response has `error.code`, `error.message`, and `trace_id`
26. `X-Trace-ID` header present on all responses

---

## T031: test_rate_limiting.py

Test rate limit enforcement for all 4 categories.

### Test Cases

**Chat (30/min):**
1. Send 30 POST /api/chat requests in rapid succession -> all succeed
2. Send 31st request -> 429 with code `RATE_LIMIT_EXCEEDED`
3. Verify `Retry-After: 60` header on 429 response
4. Verify `trace_id` in 429 response body

**Ingestion (10/min):**
5. Send 10 POST /api/collections/{id}/ingest requests -> all succeed
6. Send 11th -> 429

**Provider key (5/min):**
7. Send 5 PUT /api/providers/{name}/key requests -> all succeed
8. Send 6th -> 429

**General (120/min):**
9. Send 120 GET /api/collections requests -> all succeed
10. Send 121st -> 429

### Implementation Notes

- Use `TestClient` with the full app (middleware included)
- Reset rate limiter state between test functions (or use separate test instances)
- The rate limiter uses `time.monotonic()` -- you may need to mock time for reliable tests
- Alternatively, test with a fresh app instance per test to avoid state leakage

---

## T032: Ruff Check

Run ruff on all files modified or created by spec-08:

```bash
ruff check backend/api/chat.py backend/api/collections.py backend/api/documents.py \
          backend/api/ingest.py backend/api/models.py backend/api/providers.py \
          backend/api/settings.py backend/api/traces.py backend/api/health.py \
          backend/middleware.py backend/main.py backend/agent/schemas.py \
          backend/config.py
```

Fix any lint errors found. Common issues:
- Unused imports
- Line length (88 chars for ruff default)
- f-string without interpolation
- Missing type annotations

---

## T033: Full Regression

Run the complete test suite to verify zero regressions:

```bash
zsh scripts/run-tests-external.sh -n spec08-full tests/
cat Docs/Tests/spec08-full.status
cat Docs/Tests/spec08-full.summary
```

### Baseline Verification

The spec-07 baseline has 238 tests passing. After spec-08, ALL 238 must still pass plus the new spec-08 tests.

If any spec-07 test fails, investigate:
1. Check if the test imports from a modified module (schemas.py, config.py, etc.)
2. Check if the test depends on a removed function (e.g., from documents.py)
3. Fix the regression -- do NOT skip tests

### Known Pre-existing Failures

These tests were failing BEFORE spec-08 and should NOT be counted as regressions:
- `test_config.py::test_default_settings` (1 failure)
- `test_app_startup` (LangGraph checkpointer type validation)

---

## T034: test_concurrent_streams.py

Test SC-010: 10 concurrent chat stream connections.

```python
import asyncio
import json
import httpx

async def test_concurrent_streams():
    """Launch 10 simultaneous chat requests and verify all complete."""
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                client.post(
                    "/api/chat",
                    json={
                        "message": f"Test query {i}",
                        "collection_ids": ["test-collection"],
                        "session_id": f"concurrent-{i}",
                    },
                    timeout=30.0,
                )
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

        for i, resp in enumerate(responses):
            assert resp.status_code == 200, f"Stream {i} returned {resp.status_code}"

            # Parse NDJSON lines
            lines = resp.text.strip().split("\n")
            events = [json.loads(line) for line in lines if line.strip()]

            # Verify no 500 errors
            for event in events:
                assert event.get("code") != "INTERNAL_ERROR", f"Stream {i} had internal error"

            # Verify last event is "done" (success) or "error" (expected failure)
            last_event = events[-1]
            assert last_event["type"] in ("done", "error", "clarification"), \
                f"Stream {i} last event was {last_event['type']}"
```

**Note**: This test requires a running server or use `httpx.ASGITransport` for in-process testing:

```python
from httpx import ASGITransport, AsyncClient
from backend.main import create_app

app = create_app()
transport = ASGITransport(app=app)

async with AsyncClient(transport=transport, base_url="http://test") as client:
    # ... run concurrent tests
```

Mock the conversation graph to return quickly (use `tests/mocks.py` patterns).

---

## Test Commands

```bash
# Integration tests
zsh scripts/run-tests-external.sh -n spec08-integration tests/integration/test_api_integration.py
cat Docs/Tests/spec08-integration.status

# Rate limiting
zsh scripts/run-tests-external.sh -n spec08-ratelimit tests/integration/test_rate_limiting.py
cat Docs/Tests/spec08-ratelimit.status

# Concurrent streams
zsh scripts/run-tests-external.sh -n spec08-concurrent tests/integration/test_concurrent_streams.py
cat Docs/Tests/spec08-concurrent.status

# Ruff (run directly, not via test runner)
ruff check backend/

# Full regression
zsh scripts/run-tests-external.sh -n spec08-full tests/
cat Docs/Tests/spec08-full.status
cat Docs/Tests/spec08-full.summary
```

---

## Key Constraints

- ALL integration tests must handle the fact that the app starts up with real lifespan management -- mock at the right level (app.state, not individual modules)
- Rate limit tests must be deterministic -- reset state between tests or use fresh app instances
- Concurrent stream tests must verify NO event loss and NO corrupted JSON
- The full regression MUST pass (238 spec-07 tests + new spec-08 tests)
- Fix ALL ruff errors -- do not leave lint warnings
- Error responses must include `error.code`, `error.message`, and `trace_id` in every case

---

## What NOT to Do

- Do NOT skip failing tests -- fix the root cause
- Do NOT modify other agents' code unless fixing a clear bug (coordinate via SendMessage if needed)
- Do NOT add `# noqa` comments to suppress lint errors -- fix the code instead
- Do NOT ignore pre-existing failures in the regression count -- document them separately
- Do NOT use `pytest.mark.skip` on new tests
- Do NOT run pytest inside Claude Code -- use the external test runner
