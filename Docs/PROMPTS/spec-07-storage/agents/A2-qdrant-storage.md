# Agent A2: QdrantStorage Implementation

**Spec**: 007 (Storage Architecture) | **Wave**: 2 (parallel with A3) | **subagent_type**: backend-architect | **Model**: Sonnet 4.6

## Mission

Implement the QdrantStorage class for vector management: collection creation with hybrid dense+sparse config, batch upsert with full payload validation, hybrid search with rank fusion, and point deletion. This is a NEW class that coexists with the existing `QdrantClientWrapper` in the same file.

## Assigned Tasks

T028-T045 from `specs/007-storage-architecture/tasks.md`:

- T028: `QdrantStorage.__init__()` with async Qdrant client
- T029: `health_check()` returning True/False
- T030: `create_collection()` with dense 768d cosine + sparse BM25 IDF
- T031: `collection_exists()`, `delete_collection()`, `get_collection_info()`
- T032: `batch_upsert()` with QdrantPoint class and idempotent semantics
- T033: `search_hybrid()` with weighted rank fusion
- T034: `delete_points()` and `delete_points_by_filter()`
- T035: `get_point()`, `get_points_by_ids()`, `scroll_points()`
- T036: Payload validation (11 required fields)
- T037: Error handling with tenacity retry
- T038-T044: Unit tests (mocked Qdrant, no real service)
- T045: Run external test runner

## Critical Constraints

1. **Read the Qdrant contract FIRST**: `specs/007-storage-architecture/contracts/qdrant-contract.md`
2. **NEVER run pytest inside Claude Code**. Use: `zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py`
3. **This is a NEW class `QdrantStorage`**, NOT a rename of `QdrantClientWrapper`. Both coexist in `backend/storage/qdrant_client.py`. DO NOT modify the existing `QdrantClientWrapper`.
4. **All unit tests use mocked Qdrant** -- no real Qdrant service. Use `unittest.mock.AsyncMock`.
5. **Payload has exactly 11 required fields** (FR-011): text, parent_id, breadcrumb, source_file, page, chunk_index, doc_type, chunk_hash, embedding_model, collection_name, ingested_at
6. **`doc_type` is "Prose" or "Code" only** -- no "Table" or "Mixed"
7. **Child chunks are ~500 chars** (Constitution III), not ~300
8. **Fail entire batch** on Qdrant timeout (not partial tracking)
9. **Do NOT create integration tests** -- those belong to A4 (Wave 3)
10. **Do NOT modify any other files** -- you own ONLY `qdrant_client.py` (new QdrantStorage class) and `test_qdrant_storage.py`

## Deliverables

### 1. backend/storage/qdrant_client.py (ADD QdrantStorage class)

Add the QdrantStorage class BELOW the existing QdrantClientWrapper class. Do NOT modify QdrantClientWrapper.

**Public methods** (from contract):

| Method | Purpose |
|--------|---------|
| `__init__(host, port)` | Initialize async Qdrant client |
| `health_check()` | Returns True/False for circuit breaker |
| `create_collection(name, vector_size=768, distance="cosine")` | Dense + sparse config |
| `collection_exists(name)` | Returns True/False |
| `delete_collection(name)` | Removes collection + all points |
| `get_collection_info(name)` | Returns metadata dict |
| `batch_upsert(name, points)` | Idempotent upsert, returns count |
| `search_hybrid(name, dense_vector, sparse_vector, top_k, weights, threshold)` | Rank fusion |
| `delete_points(name, point_ids)` | Delete by ID list |
| `delete_points_by_filter(name, filter)` | Delete by payload filter |
| `get_point(name, point_id)` | Single point retrieval |
| `get_points_by_ids(name, ids)` | Batch retrieval |
| `scroll_points(name, limit, offset)` | Cursor-based iteration |

**Vector configuration**:
- Dense: 768 dims, cosine distance, HNSW index
- Sparse: BM25 with IDF modifier (on-disk index)

**Error handling**:
- Tenacity retry with exponential backoff + jitter on transient failures
- Circuit breaker pattern (use existing `_check_circuit` / `_record_success` / `_record_failure` approach from QdrantClientWrapper)

**Data classes** to define:

```python
@dataclass
class QdrantPoint:
    id: int | str
    vector: list[float]
    sparse_vector: SparseVector | None
    payload: dict

class SearchResult:
    id: int | str
    score: float
    payload: dict
```

### 2. tests/unit/test_qdrant_storage.py

Comprehensive mocked unit tests:

- **Collection**: create (dense+sparse config), exists, info, delete, idempotent create
- **Batch upsert**: points stored, payload validated, idempotent (same ID replaces), timeout fails batch
- **Hybrid search**: dense-only, sparse-only, balanced weights, top-k, score threshold
- **Point deletion**: by ID list, by filter, nonexistent gracefully handled
- **Point retrieval**: get single, batch, scroll pagination
- **Payload validation**: all 11 fields present, parent_id UUID format, doc_type enum
- **Error handling**: connection error, timeout, dimension mismatch, retry behavior

## Acceptance Criteria

- QdrantStorage class added to `qdrant_client.py` without breaking `QdrantClientWrapper`
- Dense 768d cosine + sparse BM25 IDF config in `create_collection`
- Batch upsert validates all 11 payload fields
- Hybrid search with tunable weights (default 0.6 dense + 0.4 sparse)
- Tenacity retry on transient failures
- Circuit breaker pattern implemented
- All unit tests passing (mocked, no real Qdrant)
- `ruff check backend/storage/qdrant_client.py` passes

## Testing Protocol

```bash
zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
cat Docs/Tests/spec07-wave2-qdrant.status
cat Docs/Tests/spec07-wave2-qdrant.summary
```

## Key References

- Qdrant Contract: `specs/007-storage-architecture/contracts/qdrant-contract.md`
- Data Model (payload): `specs/007-storage-architecture/data-model.md`
- Spec (FR-010, FR-011): `specs/007-storage-architecture/spec.md`
- Existing QdrantClientWrapper: `backend/storage/qdrant_client.py` (lines 21-183)

## Execution Flow

1. Wait for A1 gate (Wave 1 tests must pass)
2. Read this instruction file
3. Read `specs/007-storage-architecture/contracts/qdrant-contract.md`
4. Read existing `backend/storage/qdrant_client.py` to understand QdrantClientWrapper patterns
5. Add `QdrantStorage` class BELOW the existing `QdrantClientWrapper`
6. Create `tests/unit/test_qdrant_storage.py`
7. Run external test runner
8. Fix failures iteratively
9. Run `ruff check backend/storage/qdrant_client.py`
10. Signal completion (orchestrator waits for both A2 + A3)

**Wave 2 Gate**: Both A2 and A3 tests must pass before Wave 3 (A4) begins.
