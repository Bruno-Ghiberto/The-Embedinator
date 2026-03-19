# Agent: A2-pipeline-orchestrator

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 2

## Mission

Implement the `IngestionPipeline` orchestrator class that coordinates the full ingestion flow: spawn Rust worker, read NDJSON output, chunk, embed, batch upsert to Qdrant, store parent chunks in SQLite, and track job lifecycle. Also implement the new `POST /api/collections/{collection_id}/ingest` endpoint and extend `SUPPORTED_FORMATS` to 12 file types. Write associated unit tests.

This is the most complex component in the spec -- subprocess management, status state machine, batch upsert logic, multiple failure domains, and DI wiring.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-001, FR-006, FR-009, FR-011, FR-014, FR-015
3. `specs/006-ingestion-pipeline/contracts/ingest-api.md` -- POST /ingest contract (request/response/errors)
4. `specs/006-ingestion-pipeline/contracts/worker-ndjson.md` -- Rust worker NDJSON schema and spawn pattern
5. `specs/006-ingestion-pipeline/data-model.md` -- IngestionJob state machine, Document status transitions
6. `specs/006-ingestion-pipeline/research.md` -- R4: partial output handling, R6: resource management
7. `specs/006-ingestion-pipeline/tasks.md` -- T023-T025, T028-T030
8. `backend/ingestion/chunker.py` -- ChunkSplitter (created by A3 in parallel)
9. `backend/ingestion/embedder.py` -- BatchEmbedder, validate_embedding (created by A4 in parallel)
10. `backend/storage/sqlite_db.py` -- SQLiteDB with new CRUD methods (modified by A1)
11. `backend/storage/qdrant_client.py` -- QdrantClientWrapper.upsert() signature
12. `backend/api/documents.py` -- existing endpoints (add new ingest endpoint)
13. `backend/config.py` -- settings fields for worker path, batch sizes

## Assigned Tasks

- T023: [US1] Implement `IngestionPipeline` class in `backend/ingestion/pipeline.py`: full orchestration flow with 9 steps (see 06-implement.md). Accept `db: SQLiteDB`, `qdrant: QdrantClientWrapper` via constructor DI.
- T024: [US1] Implement `POST /api/collections/{collection_id}/ingest` endpoint in `backend/api/documents.py` per ingest-api.md contract: multipart upload, validate extension + size + collection, save file, create document + job records, launch pipeline as background task, return 202.
- T025: [US1] Extend `SUPPORTED_FORMATS` from `{".pdf", ".md", ".txt"}` to 12 types in `backend/api/documents.py`.
- T028: [US1] Write unit tests for IngestionPipeline in `tests/unit/test_ingestion_pipeline.py`: happy path with mocked worker (mock subprocess outputting NDJSON lines), mock QdrantClientWrapper, verify status transitions (started -> streaming -> embedding -> completed), verify document chunk_count updated.
- T029: [US1] Write unit tests for ingest API endpoint in `tests/unit/test_ingestion_api.py`: valid file accepted (202), unsupported extension rejected (400 INVALID_FILE), oversized file rejected (413), missing collection rejected (404), response body matches contract schema.
- T030: [US1] Write integration test scaffold in `tests/integration/test_ingestion_pipeline.py`: upload a small PDF via ingest endpoint, wait for completion, verify document status=completed, child chunks exist in Qdrant, parent chunks exist in SQLite.

## Files to Create/Modify

### Create
- `backend/ingestion/pipeline.py`

### Modify
- `backend/api/documents.py` (add ingest endpoint, extend SUPPORTED_FORMATS)
- `tests/unit/test_ingestion_pipeline.py` (add pipeline tests to scaffold)
- `tests/unit/test_ingestion_api.py` (add API tests to scaffold)
- `tests/integration/test_ingestion_pipeline.py` (add integration test)

## Key Patterns

- **Constructor DI**: `IngestionPipeline.__init__(self, db: SQLiteDB, qdrant: QdrantClientWrapper)` -- no global state.
- **Subprocess spawn**: Use `subprocess.Popen` with `stdout=PIPE, stderr=PIPE, text=True` per worker-ndjson.md spawn pattern. Read stdout line-by-line for streaming NDJSON.
- **Status state machine**: `started -> streaming -> embedding -> completed` (or `failed`). Update via `db.update_ingestion_job()`.
- **Partial output (R4)**: If worker exits non-zero, process ALL received chunks before setting status=failed. Read stderr for error details.
- **Batch upsert**: Iterate points in slices of `settings.qdrant_upsert_batch_size`. Call `self.qdrant.upsert(collection_id, batch)` per batch.
- **Background task**: Use `asyncio.create_task()` in the endpoint to launch pipeline asynchronously.
- **QdrantClientWrapper** (NOT `QdrantStorage`): Use `self.qdrant.upsert(collection_name, points)`.
- **Import at runtime**: Since A3 and A4 run in parallel, their modules may not exist yet when you write your code. Use the imports at module level -- they will resolve once all Wave 2 agents complete.
- **structlog**: `logger = structlog.get_logger(__name__)`
- **Test mocking**: Mock subprocess via `unittest.mock.patch("subprocess.Popen")`. Mock Popen's stdout to yield NDJSON lines. Mock QdrantClientWrapper and SQLiteDB.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify files outside your assignment (no touching chunker.py, embedder.py, config.py, sqlite_db.py, parent_store.py)
- NEVER delete the existing `upload_document` endpoint (POST /api/documents) -- it stays as-is
- NEVER import or reference `QdrantStorage` -- the class is `QdrantClientWrapper`
- The new ingest endpoint is SEPARATE from the old upload endpoint -- different route, different logic
- Do NOT implement fault tolerance (UpsertBuffer, pause/resume) -- A8 adds that in Wave 4
- Do NOT implement duplicate detection -- A6 adds that in Wave 3
- Do NOT implement MIME validation -- A7 adds that in Wave 3

## Checkpoint

Pipeline importable, endpoint accessible, tests written:

```bash
python -c "from backend.ingestion.pipeline import IngestionPipeline; print('Pipeline OK')"
python -c "from backend.api.documents import ingest_document; print('Ingest endpoint OK')"
ruff check backend/ingestion/pipeline.py backend/api/documents.py
```
