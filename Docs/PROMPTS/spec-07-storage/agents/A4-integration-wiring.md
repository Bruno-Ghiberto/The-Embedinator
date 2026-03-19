# Agent A4: Integration Wiring & Cross-Store Validation

**Spec**: 007 (Storage Architecture) | **Wave**: 3 (sequential) | **subagent_type**: system-architect | **Model**: Sonnet 4.6

## Mission

Wire all components together: SQLiteDB + QdrantStorage + KeyManager + ParentStore. Update `__init__.py` exports, extend ParentStore with convenience methods, update `main.py` lifespan, and create comprehensive integration tests validating cross-store consistency, WAL concurrency, provider encryption, and performance targets.

## Assigned Tasks

T058-T097 from `specs/007-storage-architecture/tasks.md`:

- T058-T061: ParentStore wrapper extension
- T164: ParentStore unit tests
- T062: `backend/storage/__init__.py` exports
- T063: `backend/main.py` lifespan updates
- T064-T071: Integration tests (parent-child linking, dedup, performance, concurrency, schema)
- T072-T076: Search retrieval workflow tests (US2)
- T077-T081: Query trace recording tests (US3)
- T082-T086: Provider encryption integration tests (US4)
- T087-T097: Cross-store consistency, error recovery, constraint validation, performance

## Critical Constraints

1. **Depends on Waves 1 and 2**: A1, A2, A3 must all be complete and tested
2. **Read all three contracts**: sqlite-contract.md, qdrant-contract.md, key-manager-contract.md
3. **NEVER run pytest inside Claude Code**. Use: `zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/`
4. **Integration tests use REAL services** -- Qdrant must be running (`docker compose up qdrant -d`)
5. **Use `unique_collection_name()` helper** in tests to avoid 409 conflicts on re-runs
6. **ParentStore uses SQL column aliases** (`id AS parent_id`, `collection_id AS collection`) -- do NOT modify the `ParentChunk` Pydantic model in `schemas.py`
7. **`EMBEDINATOR_FERNET_KEY`** is the env var for KeyManager (Constitution V)
8. **`confidence_score` is INTEGER (0-100)** in query traces
9. **`query_traces` includes `reasoning_steps_json` and `strategy_switches_json`**
10. **Both `QdrantClientWrapper` and `QdrantStorage` coexist** in qdrant_client.py -- do NOT remove QdrantClientWrapper
11. **Do NOT modify A1/A2/A3 deliverables** unless fixing a confirmed bug (coordinate via SendMessage)

## Deliverables

### 1. backend/storage/parent_store.py (EXTEND)

The existing ParentStore already has `get_by_ids()`. Add:

```python
async def get_all_by_collection(self, collection_id: str) -> list[ParentChunk]:
    """Retrieve all parent chunks for a collection."""
```

Ensure `get_by_ids()` uses the column alias pattern:
```sql
SELECT id AS parent_id, text, source_file, page, breadcrumb, collection_id AS collection
FROM parent_chunks WHERE id IN (...)
```

### 2. tests/unit/test_parent_store.py

- `test_get_by_ids_returns_aliases` -- verify parent_id and collection fields
- `test_get_all_by_collection` -- verify all parents returned
- `test_get_by_ids_empty_list` -- returns empty list
- `test_get_by_ids_missing_ids` -- missing IDs silently skipped
- `test_error_handling` -- SQLiteError raised on DB failure

### 3. backend/storage/__init__.py

```python
from .sqlite_db import SQLiteDB
from .qdrant_client import QdrantStorage
from .parent_store import ParentStore

__all__ = ["SQLiteDB", "QdrantStorage", "ParentStore"]
```

Note: KeyManager is in `backend/providers/`, not `backend/storage/`.

### 4. backend/main.py (MODIFY lifespan)

Add QdrantStorage and KeyManager initialization to the lifespan function. Add AFTER the existing QdrantClientWrapper init:

```python
# Spec 07: QdrantStorage (full-featured, coexists with QdrantClientWrapper)
from backend.storage.qdrant_client import QdrantStorage
qdrant_storage = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
app.state.qdrant_storage = qdrant_storage
logger.info("qdrant_storage_initialized")

# Spec 07: KeyManager (optional -- graceful degradation if env var missing)
from backend.providers.key_manager import KeyManager
try:
    key_manager = KeyManager()
    app.state.key_manager = key_manager
    logger.info("key_manager_initialized")
except ValueError as e:
    logger.warning("key_manager_skipped", reason=str(e))
    app.state.key_manager = None
```

### 5. Integration Test Suite

#### tests/integration/test_storage_integration.py

**Parent-child linking** (US1):
- `test_parent_chunk_to_qdrant_linking` -- create parent in SQLite, child in Qdrant, verify parent_id payload resolves
- `test_duplicate_document_detection` -- re-ingest same file_hash, verify marked duplicate
- `test_batch_parent_retrieval_performance` -- 100 parents < 10ms

**Search retrieval** (US2):
- `test_search_returns_parent_id` -- Qdrant search includes parent_id payload
- `test_search_parent_retrieval_workflow` -- search + parent lookup end-to-end
- `test_collection_isolation` -- documents/vectors isolated by collection
- `test_parent_id_mismatch_detection` -- orphaned Qdrant vector detected

**Query traces** (US3):
- `test_create_query_trace_full_flow` -- trace with all fields including reasoning_steps_json, strategy_switches_json, confidence_score (integer 0-100)
- `test_query_trace_latency_accuracy` -- latency_ms reflects actual time
- `test_trace_json_field_validation` -- JSON fields parseable
- `test_list_traces_by_session` -- filtering + ordering correct

**Provider encryption** (US4):
- `test_create_provider_with_encrypted_key` -- encrypt, store, retrieve, decrypt, verify
- `test_provider_update_changes_key` -- re-encrypt on update
- `test_provider_key_isolation` -- multiple providers decrypt independently
- `test_plaintext_never_logged` -- mock logger, verify no plaintext

**Error recovery**:
- `test_document_delete_cascades` -- FK CASCADE works
- `test_qdrant_unavailable_batch_fails` -- simulate timeout
- `test_idempotent_retry_on_failure` -- retry with UUID5, no duplicates
- `test_document_status_transitions` -- pending -> ingesting -> completed/failed

**Constraint validation**:
- `test_foreign_key_constraints_enforced` -- FK violation raises IntegrityError
- `test_unique_constraints_enforced` -- duplicate collections/documents rejected

#### tests/integration/test_concurrent_reads.py

- `test_concurrent_reads_no_blocking` -- 10 async readers, all succeed
- `test_writer_during_reads` -- writer + readers simultaneous, readers don't block
- `test_wal_checkpoint_during_reads` -- reads continue across checkpoint

#### tests/integration/test_schema_validation.py

- `test_all_tables_exist` -- verify 7 tables
- `test_all_indexes_present` -- verify expected indexes
- `test_fk_cascades_working` -- CASCADE delete verified
- `test_wal_mode_persisted` -- PRAGMA returns "wal"
- `test_foreign_keys_enforced` -- PRAGMA returns 1

#### tests/integration/test_performance.py

- `test_parent_retrieval_latency_target` -- get_parent_chunks_batch(100) < 10ms
- `test_search_latency_target` -- hybrid search on test data < 100ms

### Test Utilities

Include these helpers in test files:

```python
def unique_collection_name() -> str:
    """Generate unique collection name to avoid 409 conflicts on re-runs."""
    return f"test_{uuid.uuid4().hex[:8]}"

async def setup_test_data(db, qdrant, collection_name):
    """Create test collection, documents, parent chunks, and Qdrant vectors."""

async def cleanup_test_data(db, qdrant, collection_name):
    """Delete test artifacts from both stores."""
```

## Acceptance Criteria

- ParentStore extended with `get_all_by_collection()`
- `__init__.py` exports SQLiteDB, QdrantStorage, ParentStore
- main.py lifespan initializes QdrantStorage and KeyManager
- Parent-child linking verified across SQLite and Qdrant
- Concurrent WAL reads verified (no blocking)
- Provider encryption round-trip verified
- Query traces include reasoning_steps_json, strategy_switches_json, confidence_score (int)
- Performance targets met (< 10ms parent retrieval)
- All integration tests passing
- `ruff check backend/storage/ backend/providers/` passes

## Testing Protocol

```bash
docker compose up qdrant -d
zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/test_storage_integration.py
zsh scripts/run-tests-external.sh -n spec07-concurrent tests/integration/test_concurrent_reads.py
zsh scripts/run-tests-external.sh -n spec07-schema tests/integration/test_schema_validation.py
zsh scripts/run-tests-external.sh -n spec07-parent tests/unit/test_parent_store.py
cat Docs/Tests/spec07-wave3.status
cat Docs/Tests/spec07-wave3.summary
```

## Key References

- All Contracts: `specs/007-storage-architecture/contracts/`
- Data Model: `specs/007-storage-architecture/data-model.md`
- Spec (all FRs and SCs): `specs/007-storage-architecture/spec.md`
- Existing main.py: `backend/main.py` (lifespan pattern)
- Existing ParentStore: `backend/storage/parent_store.py`

## Execution Flow

1. Wait for A2 + A3 gate (both must pass)
2. Read this instruction file
3. Read all three contracts
4. Read existing `backend/main.py` and `backend/storage/parent_store.py`
5. Extend ParentStore
6. Create `backend/storage/__init__.py`
7. Update `backend/main.py` lifespan
8. Create all integration test files
9. Start Qdrant: `docker compose up qdrant -d`
10. Run external test runners
11. Fix failures iteratively
12. Signal completion

**Wave 3 Gate**: All integration tests must pass before Wave 4 (A5) begins.
