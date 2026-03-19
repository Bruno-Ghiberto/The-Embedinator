# Agent A5: Quality Engineer

## Agent: quality-engineer | Model: claude-sonnet-4-5 | Wave: 4

## Role

You are the Wave 4 testing agent for spec-10. You write all new tests, run the final gate
check, and verify the implementation is correct end-to-end. You do NOT modify any
implementation files — only test files. Wave 3 must be complete (gate passed) before you start.

---

## Assigned Tasks

**T026** — Write unit tests for retry-once behavior and HTTP 429 in `tests/unit/test_providers.py`:
- 5xx response triggers one retry; second failure re-raises
- HTTP 429 raises `ProviderRateLimitError` immediately (no retry)
- Applies to `generate()` and `generate_stream()` for all three cloud providers

**T027** — Write unit tests for model-agnostic embedding in `tests/unit/test_providers.py`:
- `OllamaEmbeddingProvider.embed(texts)` (no model arg) uses `self.model` in API payload
- `OllamaEmbeddingProvider.embed(texts, model="override")` uses `"override"` in API payload
- Same for `embed_single()`

**T028** — Write unit tests for `SQLiteDB` migration and `create_query_trace()` in
`tests/unit/test_sqlite_db.py`:
- After `connect()`, `PRAGMA table_info(query_traces)` includes a `provider_name` column
- `create_query_trace(..., provider_name="openrouter")` persists the value; query confirms
- `create_query_trace(...)` without `provider_name` succeeds (backward compatible, NULL stored)
- Running migration twice on same DB does not raise (idempotency)

**T029** — Write unit tests for `GET /api/providers/health` in
`tests/unit/test_providers_router.py`:
- Ollama reachable: `health_check()` returns `True` → `reachable: True` in response
- Cloud provider with no key stored: response includes `reachable: False` without calling `health_check()`
- Cloud provider `health_check()` raises exception → `reachable: False` (no 500)
- Response is always HTTP 200

**T030** — Write unit tests for enriched `GET /api/models/llm` in
`tests/unit/test_providers_router.py`:
- Cloud provider with `api_key_encrypted` non-null: its model appears in response
- Cloud provider with no key (null `api_key_encrypted`): its model does NOT appear
- Ollama models still appear regardless

**T031** — Write integration test for `ProviderRegistry` flow in
`tests/integration/test_providers_integration.py` (new file):
- `initialize()` → `get_active_llm(db)` returns an `OllamaLLMProvider` by default
- `set_active_provider(db, "openrouter", config)` → `get_active_llm(db)` returns `OpenRouterLLMProvider`
- Provider name from `db.get_active_provider()` matches `"openrouter"` after switch

**T032** — Write integration test for `BatchEmbedder` with injected provider in
`tests/integration/test_providers_integration.py`:
- Construct `BatchEmbedder(embedding_provider=mock_provider)`
- Call `embed_chunks(chunks)` — verify `mock_provider.embed()` is called, not a hard-coded class
- Verify returned embeddings are non-empty

**T033** — Run `gitnexus_detect_changes({scope: "all", repo: "The-Embedinator"})` — confirm
changed symbols match expected scope (providers/, storage/sqlite_db.py, ingestion/embedder.py,
agent/nodes.py, api/chat.py, api/models.py, api/providers.py). Report any unexpected changes
to the Orchestrator.

**T034** — Run the final gate and verify all done criteria are met.

---

## File Scope

You touch ONLY these test files:
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/tests/unit/test_providers.py` (extend)
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/tests/unit/test_sqlite_db.py` (extend)
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/tests/unit/test_providers_router.py` (extend)
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/tests/integration/test_providers_integration.py` (new)

Do NOT modify any implementation files.

---

## Testing Guidance

### Mocking httpx for cloud provider tests (T026, T027)

Use `unittest.mock.AsyncMock` and `unittest.mock.patch` to mock `httpx.AsyncClient`.
For retry tests, configure the mock to raise `httpx.HTTPStatusError` on the first call and
succeed on the second. Use `respx` or `pytest-httpx` if already in requirements.txt.

Example structure for retry test:
```python
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

async def test_openrouter_retries_on_503():
    mock_response_503 = MagicMock()
    mock_response_503.status_code = 503
    mock_response_200 = MagicMock()
    mock_response_200.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

    with patch("httpx.AsyncClient") as mock_client:
        instance = mock_client.return_value.__aenter__.return_value
        instance.post.side_effect = [
            httpx.HTTPStatusError("503", request=MagicMock(), response=mock_response_503),
            mock_response_200,
        ]
        mock_response_200.raise_for_status = lambda: None
        result = await provider.generate("test")
        assert result == "ok"
        assert instance.post.call_count == 2  # called twice (retry)
```

### SQLiteDB migration test pattern (T028)

Use an in-memory SQLite database (`:memory:`) for isolation:
```python
import pytest
from backend.storage.sqlite_db import SQLiteDB

@pytest.mark.asyncio
async def test_provider_name_column_exists():
    db = SQLiteDB(":memory:")
    await db.connect()
    cursor = await db.db.execute("PRAGMA table_info(query_traces)")
    columns = {row[1] for row in await cursor.fetchall()}
    assert "provider_name" in columns
    await db.close()
```

### FastAPI test client for router tests (T029, T030)

Use `httpx.AsyncClient` with the FastAPI `app` from `backend.main`. Mock `app.state.db`
and `app.state.registry` to avoid real Qdrant/Ollama dependencies.

### Integration tests (T031, T032)

Use real SQLite in-memory DB for `ProviderRegistry` tests. Mock cloud provider HTTP calls.
For `BatchEmbedder` tests, use a mock `EmbeddingProvider` with a configured `embed()` return value.
Do NOT require running Ollama or Qdrant for integration tests — use mocks.

---

## Critical Constraints

- Do NOT modify implementation files — tests only
- Test the ACTUAL behavior described in the spec, not assumed behavior
- Use `pytest.mark.asyncio` for all async tests
- Read existing test files before adding to them — follow their patterns (fixtures, naming, class structure)
- Check `requirements.txt` for available testing libraries before introducing new imports

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## Gate Check

After completing T026-T033, run the final gate:

```bash
zsh scripts/run-tests-external.sh -n spec10-gate-final tests/
```

Poll `Docs/Tests/spec10-gate-final.status` until `PASSED` or `FAILED`.

Pass criteria:
- 0 new failures vs spec-09 baseline (946 passing, 39 known pre-existing failures)
- All new spec-10 tests pass
- `gitnexus_detect_changes` confirms expected scope only

If `FAILED`, read the summary and log. Fix any test failures that are caused by bugs in YOUR
test code. If an implementation bug is found, report it to the Orchestrator rather than
fixing implementation yourself (you are tests-only).

When the gate passes, notify the Orchestrator that Wave 4 is complete and spec-10 is done.
