# A3 — Unit Tests: Errors + Storage Indexing (Wave 2)

**Agent type**: `python-expert`
**Model**: `claude-sonnet-4-6`
**Wave**: 2 (parallel with A2)
**Gate requirement**: `Docs/Tests/spec16-scaffold.status` must equal `PASSED` before starting.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | File to Create |
|------|----------------|
| T015 | `tests/unit/test_storage_indexing.py` |
| T016 | `tests/unit/test_errors.py` |
| T018 | Gate run (see below) |

---

## Pre-Task Check

Before writing any file, verify the gate:
```bash
cat Docs/Tests/spec16-scaffold.status   # must be PASSED
```

Verify production symbols:
```bash
python -c "from backend.storage.indexing import index_chunks; print('OK')"
python -c "from backend.errors import EmbeddinatorError; print('OK')"
```

---

## T015 — tests/unit/test_storage_indexing.py

**Import**: `from backend.storage.indexing import index_chunks`
**Symbol**: async function with signature `index_chunks(app, doc_id: str, chunks: list[dict])`.

Mock `app.state.qdrant` and `app.state.registry` — do NOT require a running Qdrant or embedding model.

Required test cases (minimum 5):
1. Empty `chunks` list returns without error (early return guard).
2. `app.state.qdrant.upsert()` is called with the correct collection name.
3. Each chunk's `"text"` key is passed to the embed provider.
4. Storage errors from Qdrant are propagated (mock `qdrant.upsert` to raise, assert exception).
5. The `doc_id` argument appears in the Qdrant payload for each point.

The actual payload keys stored are `document_id`, `text`, `chunk_index`, `start_offset`, `end_offset`. Use this in assertions.

---

## T016 — tests/unit/test_errors.py

**Import**: `from backend.errors import EmbeddinatorError` (plus the 10 subclasses).

The 11 classes in `backend/errors.py` (verified):
1. `EmbeddinatorError`
2. `QdrantConnectionError`
3. `OllamaConnectionError`
4. `SQLiteError`
5. `LLMCallError`
6. `EmbeddingError`
7. `IngestionError`
8. `SessionLoadError`
9. `StructuredOutputParseError`
10. `RerankerError`
11. `CircuitOpenError`

Do NOT test `ProviderRateLimitError` here — it lives in `backend/providers/base.py`, not `backend/errors.py`. Importing it from `backend.errors` raises `ImportError`.

Required test cases (minimum 6):
1. `EmbeddinatorError` is a subclass of `Exception`.
2. All 10 subclasses are subclasses of `EmbeddinatorError`.
3. Each subclass can be raised and caught as `EmbeddinatorError` (test catch-as-base).
4. Each exception has a meaningful string representation when a message is provided.
5. `CircuitOpenError` can be raised without arguments (no required message).
6. All classes are importable from `backend.errors` in a single `from ... import` statement.

---

## T018 — Gate Run

After creating both test files, run the gate:

```bash
zsh scripts/run-tests-external.sh -n spec16-a3 --no-cov tests/unit/test_storage_indexing.py tests/unit/test_errors.py
```

Verify:
```bash
cat Docs/Tests/spec16-a3.status   # must be PASSED
```

Also confirm no regressions in the full unit suite:
```bash
zsh scripts/run-tests-external.sh -n spec16-a3-regression --no-cov tests/unit/
cat Docs/Tests/spec16-a3-regression.status   # must be PASSED
```

Report `spec16-a3.status` result to the orchestrator when complete.

---

## Critical Gotchas

- `ProviderRateLimitError` is in `backend.providers.base`, NOT `backend.errors`. Do NOT import it from `backend.errors`.
- `index_chunks` accesses `app.state.registry.get_embedding_provider()` — mock `app` as a `MagicMock` with `app.state.qdrant` and `app.state.registry` configured as `AsyncMock`/`MagicMock`.
- `index_chunks` is an `async` function — test functions that call it must be `async def` and the fixture must be configured for asyncio (already handled by `pytest.ini asyncio_mode = auto`).
- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
- Use `--no-cov` for all development gate runs.
