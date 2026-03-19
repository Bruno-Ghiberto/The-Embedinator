# A4 — Backend E2E Tests (Wave 3)

**Agent type**: `python-expert`
**Model**: `claude-sonnet-4-6`
**Wave**: 3 (parallel with A5)
**Gate requirement**: `Docs/Tests/spec16-scaffold.status` must equal `PASSED` before starting. Confirm with orchestrator that Wave 2 gates also passed.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | File to Create |
|------|----------------|
| T019 | `tests/e2e/__init__.py` (empty) |
| T020 | `tests/e2e/test_ingest_e2e.py` |
| T021 | `tests/e2e/test_chat_e2e.py` |
| T022 | `tests/e2e/test_collection_e2e.py` |
| T022b | `tests/e2e/test_observability_e2e.py` |
| T023 | Gate runs (see below) |

`tests/e2e/` already exists as an empty directory.

---

## E2E Test Architecture

**All tests use `httpx.AsyncClient(app=app, base_url="http://test")` — in-process ASGI only.** There is NO live server, NO browser, NO Playwright `.spec.ts` files. These are standard Python pytest files.

**All tests must be marked `@pytest.mark.e2e`.**

**All client fixtures must use `try/finally` teardown** to guarantee cleanup even when assertions fail (FR-006a).

Standard client fixture pattern:
```python
import pytest
import pytest_asyncio
import httpx
from backend.main import app

@pytest_asyncio.fixture
async def client(self):
    async with httpx.AsyncClient(app=app, base_url="http://test") as c:
        yield c
    # OR use try/finally if explicit teardown is needed for state cleanup
```

---

## T020 — test_ingest_e2e.py

Scenario: POST a document to `/api/ingest`, poll job status, verify the document appears in `/api/documents`.

- Mock the embedding provider so no Qdrant or Ollama is required.
- Poll `/api/jobs/{job_id}` until status is `"completed"` or `"failed"` (with a timeout).
- Assert the document appears in the collection via `GET /api/documents`.
- Use `try/finally` teardown to delete the collection and document after the test.

---

## T021 — test_chat_e2e.py

Scenario: POST to `/api/chat`, collect NDJSON stream lines, assert event types appear in order.

- Mock the LLM and Qdrant so no real services are needed.
- Use `client.stream("POST", "/api/chat", json={...})` to collect NDJSON lines.
- Assert that event types `retrieval_complete`, `answer_chunk`, and `done` all appear (in that order).
- The stream endpoint uses `Content-Type: application/x-ndjson` — parse each line as JSON.

```python
lines = []
async with client.stream("POST", "/api/chat", json={"message": "test", "collection": "test"}) as resp:
    async for line in resp.aiter_lines():
        if line.strip():
            lines.append(json.loads(line))
event_types = [l["event"] for l in lines]
assert "retrieval_complete" in event_types
assert "answer_chunk" in event_types
assert "done" in event_types
```

---

## T022 — test_collection_e2e.py

Scenario: POST creates collection, GET returns it, DELETE removes it, subsequent GET returns 404.

- Use unique collection names to avoid conflicts with other test runs (generate via `uuid.uuid4().hex[:8]`).
- `try/finally` teardown must delete the collection even if assertions fail.

---

## T022b — test_observability_e2e.py

Scenario: Pre-seed a trace, then assert `/api/traces` and `/api/metrics` return populated data.

- Mock LLM and Qdrant to avoid real service calls.
- After streaming a chat request, assert `GET /api/traces` returns a list with at least 1 entry.
- Assert `GET /api/metrics` returns a response containing `circuit_breaker` and `latency_p99` fields.
- `try/finally` teardown.

---

## T023 — Gate Runs

After creating all 4 E2E test files, run:

```bash
# Primary gate: E2E tests pass
zsh scripts/run-tests-external.sh -n spec16-a4 --no-cov -m "e2e" tests/e2e/
cat Docs/Tests/spec16-a4.status   # must be PASSED

# Regression check: existing unit tests unaffected
zsh scripts/run-tests-external.sh -n spec16-no-regression-a4 --no-cov tests/unit/
cat Docs/Tests/spec16-no-regression-a4.status   # must be PASSED
```

Report `spec16-a4.status` to the orchestrator when complete.

---

## Critical Gotchas

- E2E tests are Python pytest `.py` files. Do NOT create `.spec.ts`, `playwright.config.ts`, or any TypeScript files.
- The `@pytest.mark.e2e` marker must appear on every test class or function.
- `try/finally` teardown is MANDATORY (FR-006a) — cleanup always runs even on assertion failure.
- Mock all external dependencies (LLM, Qdrant, embedder) so E2E tests run without real services.
- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
- `asyncio_mode = auto` in `pytest.ini` means you do NOT need `@pytest.mark.asyncio` on async tests.
