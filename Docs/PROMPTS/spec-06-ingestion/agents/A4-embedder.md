# Agent: A4-embedder

**subagent_type**: performance-engineer | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the `BatchEmbedder` class for parallel batch embedding via Ollama and the `validate_embedding` function that checks every vector before storage. Write comprehensive unit tests covering parallel batching and all 4 validation checks.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-009 (parallel embedding), FR-010 (validate embeddings), FR-020 (resource limits)
3. `specs/006-ingestion-pipeline/data-model.md` -- embedding validation rules table
4. `specs/006-ingestion-pipeline/research.md` -- R6: embed_max_workers concurrency management
5. `specs/006-ingestion-pipeline/tasks.md` -- T022, T027
6. `backend/config.py` -- `settings.embed_max_workers` (4), `settings.embed_batch_size` (16), `settings.default_embed_model`, `settings.ollama_base_url`

## Assigned Tasks

- T022: [P] [US1] Implement `BatchEmbedder` class in `backend/ingestion/embedder.py`:
  - `embed_chunks(texts: list[str]) -> list[list[float]]`: split texts into batches of `settings.embed_batch_size`, use `ThreadPoolExecutor(max_workers=settings.embed_max_workers)` to call `_embed_batch` in parallel, collect and return results in order.
  - `_embed_batch(batch: list[str]) -> list[list[float]]`: synchronous call to Ollama `/api/embed` endpoint via httpx. Return list of embedding vectors.
  - `validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]`: 4 checks per data-model.md validation rules. Returns `(True, "")` on success or `(False, "reason string")` on failure.
- T027: [P] [US1] Write unit tests for BatchEmbedder in `tests/unit/test_embedder.py`:
  - Parallel batching splits correctly (e.g., 100 texts with batch_size=16 produces 7 batches)
  - `validate_embedding` passes valid vectors (correct dim, normal values)
  - `validate_embedding` catches wrong dimensions with reason `"wrong dimensions: got X, expected Y"`
  - `validate_embedding` catches NaN values with reason `"contains NaN values"`
  - `validate_embedding` catches zero vector with reason `"zero vector"`
  - `validate_embedding` catches low magnitude with reason matching `"magnitude below threshold"`
  - Return type is `tuple[bool, str]` in all cases

## Files to Create/Modify

### Create
- `backend/ingestion/embedder.py`

### Modify
- `tests/unit/test_embedder.py` (fill in test implementations in scaffold created by A1)

## Key Patterns

- **validate_embedding signature**: `def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]` -- module-level function, NOT a method on BatchEmbedder. Must be importable as `from backend.ingestion.embedder import validate_embedding`.
- **Reason strings**: The second element of the tuple is the reason for failure. Empty string `""` on success.
- **ThreadPoolExecutor**: Use `concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)`. Submit `_embed_batch` calls for each batch. Use `executor.map()` or `futures.as_completed()` to collect results in order.
- **Ollama /api/embed endpoint**: POST to `{base_url}/api/embed` with JSON body `{"model": model, "input": [texts...]}`. Response contains `{"embeddings": [[floats...], ...]}`.
- **httpx**: Use `httpx.Client` (synchronous, since `_embed_batch` runs in threads). Create a session for connection reuse.
- **structlog**: `logger = structlog.get_logger(__name__)`
- **Settings access**: `from backend.config import settings`
- **Test mocking**: Mock the httpx calls, not Ollama itself. Use `unittest.mock.patch` on `httpx.Client.post`.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n spec06-embedder tests/unit/test_embedder.py`
- NEVER modify files outside your assignment (only `embedder.py` and `test_embedder.py`)
- `validate_embedding` returns `tuple[bool, str]`, NOT just `bool`
- Do NOT implement skip-and-continue behavior in `embed_chunks` -- A8 adds that in Wave 4. For now, if a single embedding fails, let the exception propagate.
- The `embed_chunks` method is `async` (called from the async pipeline) but uses ThreadPoolExecutor internally for CPU-bound parallelism. Use `asyncio.get_event_loop().run_in_executor()` or `asyncio.to_thread()`.
- The `_embed_batch` method is synchronous (runs inside ThreadPoolExecutor threads).

## Checkpoint

Embedder importable, validate_embedding works, tests pass:

```bash
python -c "from backend.ingestion.embedder import BatchEmbedder, validate_embedding; v, r = validate_embedding([0.1]*384, 384); print('valid:', v, 'reason:', repr(r))"
python -c "from backend.ingestion.embedder import validate_embedding; v, r = validate_embedding([0.0]*384, 384); print('zero:', v, 'reason:', r)"
ruff check backend/ingestion/embedder.py
zsh scripts/run-tests-external.sh -n spec06-embedder tests/unit/test_embedder.py
cat Docs/Tests/spec06-embedder.status
cat Docs/Tests/spec06-embedder.summary
```
