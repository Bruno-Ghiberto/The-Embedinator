# Agent: A1-foundation-schema

**subagent_type**: backend-architect | **Model**: Sonnet 4.6 | **Wave**: 1

## Mission

Create the package scaffolding, add new config fields, migrate the Phase 1 database schema to the production schema, create the `ingestion_jobs` and `parent_chunks` tables, update `ParentStore.get_by_ids()` for the new column names, fix existing document CRUD operations, and create test file scaffolding for all subsequent agents. This is the foundational wave -- all other agents depend on your output.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-06-ingestion/06-implement.md` -- full implementation context (the authoritative reference)
2. `specs/006-ingestion-pipeline/data-model.md` -- entity schemas, state machines, migration mapping table
3. `specs/006-ingestion-pipeline/research.md` -- R3: create-copy-drop-rename migration strategy
4. `specs/006-ingestion-pipeline/tasks.md` -- task definitions T001-T011
5. `backend/config.py` -- Settings class (verify existing fields at lines 30-34, add 3 new)
6. `backend/storage/sqlite_db.py` -- Phase 1 schema (_create_tables at line 30), document CRUD methods
7. `backend/storage/parent_store.py` -- get_by_ids() SQL query (lines 26-68)
8. `backend/agent/schemas.py` -- ParentChunk model (lines 38-44) -- DO NOT MODIFY
9. `backend/api/documents.py` -- existing document endpoints (verify they work after migration)

## Assigned Tasks

- T001: Create `backend/ingestion/` package with `__init__.py`
- T002: [P] Initialize `ingestion-worker/` Cargo workspace: create `Cargo.toml` with dependencies and empty `src/` module files (main.rs, pdf.rs, markdown.rs, text.rs, code.rs, heading_tracker.rs, types.rs). The Rust source files should contain only minimal stubs (e.g., empty modules or `// TODO` comments) -- A5 fills in implementations.
- T003: [P] Create unit test scaffolding files: `tests/unit/test_chunker.py`, `tests/unit/test_embedder.py`, `tests/unit/test_incremental.py`, `tests/unit/test_ingestion_pipeline.py`, `tests/unit/test_ingestion_api.py` -- with imports and empty test class stubs
- T004: [P] Create integration test scaffolding: `tests/integration/test_ingestion_pipeline.py` -- with imports and fixtures
- T005: [US6] Add 3 new config fields to `backend/config.py`: `rust_worker_path`, `embed_max_workers`, `qdrant_upsert_batch_size`. Note: `max_upload_size_mb`, `parent_chunk_size`, `child_chunk_size`, `embed_batch_size` already exist at lines 31-34 -- do NOT re-add them.
- T006: [US6] Implement `documents` table migration using create-copy-drop-rename pattern in `backend/storage/sqlite_db.py` per R3. Map columns per data-model.md migration table. Add UNIQUE constraint `(collection_id, file_hash)` where `file_hash != ''`.
- T007: [P] [US6] Add `ingestion_jobs` table DDL to `_create_tables()` in `backend/storage/sqlite_db.py` per data-model.md
- T008: [P] [US6] Add `parent_chunks` table DDL with indexes to `_create_tables()` in `backend/storage/sqlite_db.py` per data-model.md
- T009: [US6] Update `ParentStore.get_by_ids()` SQL: use `id AS parent_id` and `collection_id AS collection` column aliases so the existing ParentChunk Pydantic model (which uses `parent_id` and `collection` fields) continues to work. Do NOT modify `schemas.py`.
- T010: [US6] Update existing document CRUD operations (`create_document`, `update_document_status`, `list_documents`) in `sqlite_db.py` to use new column names. Add new methods: `create_ingestion_job`, `update_ingestion_job`, `insert_parent_chunk`, `delete_parent_chunks_by_document`, `find_document_by_hash`.
- T011: [US6] Write unit tests for schema migration in `tests/unit/test_schema_migration.py`

## Files to Create/Modify

### Create
- `backend/ingestion/__init__.py`
- `ingestion-worker/Cargo.toml`
- `ingestion-worker/src/main.rs` (empty stub)
- `ingestion-worker/src/types.rs` (empty stub)
- `ingestion-worker/src/heading_tracker.rs` (empty stub)
- `ingestion-worker/src/text.rs` (empty stub)
- `ingestion-worker/src/code.rs` (empty stub)
- `ingestion-worker/src/markdown.rs` (empty stub)
- `ingestion-worker/src/pdf.rs` (empty stub)
- `tests/unit/test_chunker.py` (scaffold)
- `tests/unit/test_embedder.py` (scaffold)
- `tests/unit/test_incremental.py` (scaffold)
- `tests/unit/test_ingestion_pipeline.py` (scaffold)
- `tests/unit/test_ingestion_api.py` (scaffold)
- `tests/unit/test_schema_migration.py` (full tests)
- `tests/integration/test_ingestion_pipeline.py` (scaffold)

### Modify
- `backend/config.py` -- add 3 settings fields
- `backend/storage/sqlite_db.py` -- migration + new tables + new CRUD methods
- `backend/storage/parent_store.py` -- SQL column aliases in get_by_ids()

## Key Patterns

- **Migration pattern** (R3): Check for `collection_ids` column via `PRAGMA table_info(documents)`. If found, run create-copy-drop-rename. Must be idempotent -- if migration already happened, the check returns False and migration is skipped.
- **Column aliases**: Use `SELECT id AS parent_id, ..., collection_id AS collection FROM parent_chunks` so `row["parent_id"]` and `row["collection"]` still work with the existing ParentChunk model.
- **Config**: Settings uses Pydantic `BaseSettings`. Add fields in the Ingestion section after line 34.
- **Test scaffolding**: Each test file should have imports and empty test class stubs with `pass` bodies. Wave 2-4 agents fill in the actual test implementations.
- **Rust stubs**: The `Cargo.toml` must be valid (`cargo check` should succeed). Rust source files should have minimal stubs that compile (e.g., `pub mod types;` in main.rs, empty struct/enum placeholders in types.rs).
- **structlog**: Use `logger = structlog.get_logger(__name__)` in any modified Python file.
- **UNIQUE index**: Use partial index `WHERE file_hash != ''` so legacy rows with empty hash don't conflict.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `backend/agent/schemas.py` -- the ParentChunk model field names (`parent_id`, `collection`) stay as-is. Use SQL aliases instead.
- NEVER modify `backend/agent/conversation_graph.py`, `research_graph.py`, `nodes.py`, `confidence.py`
- NEVER modify `backend/errors.py` -- `IngestionError` and `CircuitOpenError` already exist
- NEVER modify `backend/main.py` -- ingestion pipeline is launched from the API endpoint, not lifespan
- The 4 existing config fields (`max_upload_size_mb`, `parent_chunk_size`, `child_chunk_size`, `embed_batch_size`) must NOT be re-added or duplicated
- Test scaffolding files should have empty test methods or `pass` bodies -- Wave 2+ agents fill them in
- The existing `upload_document` endpoint (`POST /api/documents`) must NOT be removed -- it is the Phase 1 endpoint that continues to work

## Checkpoint

All files created, migration implemented, config updated. Running all of these succeeds:

```bash
python -c "from backend.config import settings; print('rust_worker_path:', settings.rust_worker_path, 'embed_max_workers:', settings.embed_max_workers, 'upsert_batch:', settings.qdrant_upsert_batch_size)"
python -c "import backend.ingestion; print('ingestion package OK')"
python -c "import tests.unit.test_schema_migration; print('migration tests OK')"
python -c "import tests.unit.test_chunker; import tests.unit.test_embedder; import tests.unit.test_incremental; import tests.unit.test_ingestion_pipeline; import tests.unit.test_ingestion_api; print('test scaffolding OK')"
python -c "import tests.integration.test_ingestion_pipeline; print('integration scaffold OK')"
ruff check backend/config.py backend/storage/sqlite_db.py backend/storage/parent_store.py
zsh scripts/run-tests-external.sh -n spec06-us6 tests/unit/test_schema_migration.py
cat Docs/Tests/spec06-us6.status
cat Docs/Tests/spec06-us6.summary
```
