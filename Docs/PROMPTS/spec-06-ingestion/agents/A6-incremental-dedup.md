# Agent: A6-incremental-dedup

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 3

## Mission

Implement the `IncrementalChecker` class for SHA256-based duplicate detection and change detection during re-ingestion. Wire duplicate checking into the pipeline and API endpoint. Implement old vector point deletion on re-ingestion of changed files. Write comprehensive unit and integration tests.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full code specifications (the authoritative reference)
2. `specs/006-ingestion-pipeline/spec.md` -- FR-003 (SHA256 dedup), FR-004 (failed re-ingestion), FR-005 (changed hash re-ingest)
3. `specs/006-ingestion-pipeline/contracts/ingest-api.md` -- HTTP 409 DUPLICATE_DOCUMENT response
4. `specs/006-ingestion-pipeline/data-model.md` -- Document entity, UNIQUE constraint, status transitions
5. `specs/006-ingestion-pipeline/tasks.md` -- T031-T036
6. `backend/storage/sqlite_db.py` -- `find_document_by_hash()` method (added by A1)
7. `backend/ingestion/pipeline.py` -- IngestionPipeline (created by A2)
8. `backend/api/documents.py` -- ingest endpoint (created by A2)
9. `backend/storage/qdrant_client.py` -- QdrantClientWrapper for point deletion

## Assigned Tasks

- T031: [US2] Implement `IncrementalChecker` class in `backend/ingestion/incremental.py`:
  - `compute_file_hash(file_path: str) -> str`: SHA256 hex digest of file content, reading in 8KB blocks.
  - `check_duplicate(collection_id: str, file_hash: str) -> tuple[bool, str | None]`: query documents table for matching hash with status `completed`. Return `(True, existing_doc_id)` if duplicate, `(False, None)` otherwise. A document with status `failed` is NOT a duplicate (FR-004).
  - `check_change(collection_id: str, filename: str, new_hash: str) -> tuple[bool, str | None]`: find a document with the same filename but different hash. Return `(True, old_doc_id)` if changed, `(False, None)` otherwise.
- T032: [US2] Wire `IncrementalChecker` into `IngestionPipeline.ingest_file()` in `backend/ingestion/pipeline.py`: call `compute_file_hash` at pipeline entry, pass hash to downstream callers.
- T033: [US2] Implement old vector point deletion on re-ingestion in `backend/ingestion/pipeline.py`: when change detected, delete old Qdrant points by `source_file` payload filter and old parent_chunks by `document_id` before re-ingesting.
- T034: [US2] Wire duplicate/change detection into API endpoint in `backend/api/documents.py`: return HTTP 409 `DUPLICATE_DOCUMENT` for same hash + completed status, allow re-ingestion for failed status (FR-004), trigger point deletion + re-ingest for changed hash (FR-005).
- T035: [US2] Write unit tests for `IncrementalChecker` in `tests/unit/test_incremental.py`:
  - SHA256 hash correctness (known input -> known hash)
  - Duplicate detection: same hash + completed status -> True
  - Failed document re-ingestion: same hash + failed status -> False (allowed)
  - Change detection: different hash -> returns old doc ID
  - Per-collection scoping: same hash in different collections -> not duplicate
- T036: [US2] Write integration test: upload file -> re-upload same -> 409; modify file -> re-upload -> verify old Qdrant points deleted and new chunks indexed with correct UUID5 IDs -- in `tests/integration/test_ingestion_pipeline.py`.

## Files to Create/Modify

### Create
- `backend/ingestion/incremental.py`

### Modify
- `backend/ingestion/pipeline.py` (wire IncrementalChecker, add vector deletion)
- `backend/api/documents.py` (wire duplicate detection, 409 response)
- `tests/unit/test_incremental.py` (fill in tests)
- `tests/integration/test_ingestion_pipeline.py` (add dedup integration test)

## Key Patterns

- **SHA256 in blocks**: Read file in 8KB blocks for memory efficiency (`for block in iter(lambda: f.read(8192), b"")`).
- **Duplicate check query**: `SELECT id, status FROM documents WHERE collection_id = ? AND file_hash = ?` -- only return True if status is `completed`.
- **Change check query**: `SELECT id, file_hash FROM documents WHERE collection_id = ? AND filename = ? AND file_hash != ?` -- returns old doc ID if hash differs.
- **Qdrant point deletion**: Use `QdrantClientWrapper` to delete points by payload filter `{"source_file": filename}` in the target collection. The exact delete method depends on what `QdrantClientWrapper` exposes -- you may need to call `self.qdrant.client.delete()` directly on the underlying qdrant_client.
- **Parent chunk deletion**: Use `db.delete_parent_chunks_by_document(old_doc_id)` method added by A1.
- **structlog**: `logger = structlog.get_logger(__name__)`
- **Constructor DI**: `IncrementalChecker.__init__(self, db: SQLiteDB)` -- takes SQLiteDB instance.
- **Test mocking**: Mock SQLiteDB.find_document_by_hash() to return test data. Use real SHA256 computation for hash tests.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n spec06-dedup tests/unit/test_incremental.py`
- NEVER modify `backend/config.py`, `backend/storage/sqlite_db.py`, `backend/storage/parent_store.py`
- NEVER modify Rust files
- When modifying `pipeline.py` and `documents.py`, only add dedup-related code. Do not change the core pipeline flow or other endpoint logic.
- The UNIQUE constraint `(collection_id, file_hash)` already exists in the database schema (added by A1). Your duplicate detection is an application-level check that provides friendly error messages.

## Checkpoint

IncrementalChecker importable, dedup wired, tests pass:

```bash
python -c "from backend.ingestion.incremental import IncrementalChecker; print('IncrementalChecker OK')"
ruff check backend/ingestion/incremental.py backend/ingestion/pipeline.py backend/api/documents.py
zsh scripts/run-tests-external.sh -n spec06-dedup tests/unit/test_incremental.py
cat Docs/Tests/spec06-dedup.status
cat Docs/Tests/spec06-dedup.summary
```
