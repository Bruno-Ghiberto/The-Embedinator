# Agent A1: SQLiteDB Foundation & Schema

**Spec**: 007 (Storage Architecture) | **Wave**: 1 (sequential) | **subagent_type**: python-expert | **Model**: Opus 4.6

## Mission

Implement the foundational SQLiteDB class with all 7 database tables, full CRUD methods, async context management, WAL mode, FK enforcement, and comprehensive unit tests. All other agents depend on this work being correct.

## Assigned Tasks

T001-T027 from `specs/007-storage-architecture/tasks.md`:

- T001-T006: Project structure setup (directories, `__init__.py`, dependencies)
- T007-T008: SQLiteDB `__init__`, `connect()`, `_init_schema()` with WAL + FK PRAGMAs
- T009: Collections CRUD
- T010: Documents CRUD (UNIQUE(collection_id, file_hash))
- T011: IngestionJobs CRUD (status lifecycle)
- T012: ParentChunks CRUD (UUID5 deterministic IDs, indexes)
- T013: QueryTraces CRUD (append-only, indexes on session_id + created_at)
- T014: Settings CRUD (key-value upsert)
- T015: Providers CRUD (encrypted API key field, NULL allowed for Ollama)
- T016: Error handling (IntegrityError, OperationalError)
- T017-T026: Unit tests for all tables, constraints, performance
- T027: Run external test runner and verify all pass

## Critical Constraints

1. **Read the SQLite contract FIRST**: `specs/007-storage-architecture/contracts/sqlite-contract.md`
2. **NEVER run pytest inside Claude Code**. Use: `zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py`
3. **`confidence_score` is INTEGER (0-100)** in query_traces, NOT REAL/float
4. **`query_traces` MUST include `reasoning_steps_json TEXT` and `strategy_switches_json TEXT`** (FR-005)
5. **Foreign keys use `ON DELETE CASCADE`** on all FK references
6. **Use `aiosqlite`** with async/await throughout
7. **Use `:memory:` SQLite** for test isolation (each test gets a fresh database)
8. **structlog** for logging, never `print()`
9. **Do NOT create integration tests** -- those belong to A4 (Wave 3)
10. **Do NOT create or modify QdrantStorage, KeyManager, or ParentStore** -- those belong to A2, A3, A4

## Deliverables

### 1. backend/storage/sqlite_db.py

The SQLiteDB class with:

**Schema (all 7 tables)**:
```sql
-- collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers
-- See 07-implement.md for complete SQL
```

**PRAGMA configuration**:
- `journal_mode=WAL`
- `foreign_keys=ON`
- `synchronous=NORMAL`

**Public methods** (match contract signatures exactly):

| Group | Methods |
|-------|---------|
| Lifecycle | `__aenter__`, `__aexit__`, `connect()`, `close()`, `_init_schema()` |
| Collections | `create_collection`, `get_collection`, `get_collection_by_name`, `list_collections`, `update_collection`, `delete_collection` |
| Documents | `create_document`, `get_document`, `get_document_by_hash`, `list_documents`, `update_document`, `delete_document` |
| IngestionJobs | `create_ingestion_job`, `get_ingestion_job`, `list_ingestion_jobs`, `update_ingestion_job` |
| ParentChunks | `create_parent_chunk`, `get_parent_chunk`, `get_parent_chunks_batch`, `list_parent_chunks`, `delete_parent_chunks` |
| QueryTraces | `create_query_trace`, `list_query_traces`, `get_query_traces_by_timerange` |
| Settings | `get_setting`, `set_setting`, `list_settings`, `delete_setting` |
| Providers | `create_provider`, `get_provider`, `list_providers`, `update_provider`, `delete_provider` |

### 2. tests/unit/test_sqlite_db.py

Comprehensive unit tests:

- **Schema**: `test_init_schema_creates_all_tables`, `test_wal_mode_enabled`, `test_foreign_keys_enabled`, `test_schema_idempotent`
- **Collections**: create, duplicate name, get, get_by_name, list, update, delete
- **Documents**: create, duplicate hash, get_by_hash, list, update status, delete
- **IngestionJobs**: create, update status, list by document
- **ParentChunks**: create UUID5, batch retrieval <10ms, duplicate UUID5 rejected
- **QueryTraces**: create (with reasoning_steps_json, strategy_switches_json, confidence_score as int), list by session, timerange
- **Settings**: set/get upsert, list, delete
- **Providers**: create, null api_key (Ollama), list
- **Constraints**: FK violation, UNIQUE violation, CASCADE delete
- **Performance**: batch retrieval latency for 100 chunks < 10ms

### 3. Directory structure

Ensure these directories exist with `__init__.py`:
- `backend/storage/`
- `backend/providers/`
- `tests/unit/`
- `tests/integration/`
- `data/`

## Acceptance Criteria

- All 7 tables created with correct columns, types, and constraints
- WAL mode enabled (PRAGMA returns "wal")
- Foreign keys enforced (PRAGMA returns 1)
- `ON DELETE CASCADE` works for collections -> documents -> parent_chunks
- All CRUD methods match contract signatures
- `confidence_score` is INTEGER in query_traces
- `reasoning_steps_json` and `strategy_switches_json` columns exist in query_traces
- Batch retrieval < 10ms for 100 parent chunks
- All unit tests passing via external runner
- `ruff check backend/storage/sqlite_db.py` passes
- No sensitive data logged

## Testing Protocol

```bash
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py
cat Docs/Tests/spec07-wave1.status    # RUNNING|PASSED|FAILED|ERROR
cat Docs/Tests/spec07-wave1.summary   # ~20 lines
```

## Key References

- SQLite Contract: `specs/007-storage-architecture/contracts/sqlite-contract.md`
- Data Model: `specs/007-storage-architecture/data-model.md`
- Spec: `specs/007-storage-architecture/spec.md` (FR-001 through FR-009)
- 07-implement.md: `Docs/PROMPTS/spec-07-storage/07-implement.md` (schema SQL)

## Execution Flow

1. Read this instruction file
2. Read `specs/007-storage-architecture/contracts/sqlite-contract.md`
3. Read the schema SQL in `Docs/PROMPTS/spec-07-storage/07-implement.md`
4. Create directory structure with `__init__.py` files
5. Create `backend/storage/sqlite_db.py` with SQLiteDB class
6. Create `tests/unit/test_sqlite_db.py` with comprehensive tests
7. Run external test runner
8. Fix failures iteratively
9. Run `ruff check backend/storage/sqlite_db.py`
10. Signal wave completion

**Wave 1 Gate**: All tests must pass before Wave 2 (A2 + A3) begins.
