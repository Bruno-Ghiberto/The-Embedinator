# SQLite Storage Layer Contract

**Feature**: Storage Architecture | **Date**: 2026-03-13 | **Version**: 1.0

## Overview

Internal contract defining the SQLiteDB class interface. This is the synchronous-facing, async-wrapped SQLite persistence layer used by the ingestion pipeline and chat retrieval paths.

## Class: SQLiteDB

**Module**: `backend.storage.sqlite_db`

**Responsibility**: Schema initialization, CRUD operations on all 7 tables (Collections, Documents, IngestionJobs, ParentChunks, QueryTraces, Settings, Providers), connection management, constraint enforcement.

### Public Methods

#### Initialization & Lifecycle

```python
class SQLiteDB:
    async def __aenter__(self) -> SQLiteDB
    async def __aexit__(exc_type, exc_val, exc_tb) -> None
```

**Contract**:
- Context manager for async SQLite connection lifecycle
- On enter: Opens connection, runs schema initialization (idempotent)
- On exit: Closes connection, ensures WAL checkpoint

---

#### Schema Management

```python
async def init_schema() -> None
```

**Contract**:
- Creates all 7 tables if not present
- Enables PRAGMA foreign_keys=ON
- Enables PRAGMA journal_mode=WAL
- Idempotent: Safe to call multiple times (IF NOT EXISTS checks)
- Raises: aiosqlite.DatabaseError if schema conflict detected

**Tables Created**:
- collections
- documents
- ingestion_jobs
- parent_chunks
- query_traces
- settings
- providers

---

#### Collections CRUD

```python
async def create_collection(
    id: str,  # UUID4
    name: str,
    description: str | None,
    embedding_model: str,
    chunk_profile: str,
    qdrant_collection_name: str
) -> None

async def get_collection(collection_id: str) -> dict | None

async def get_collection_by_name(name: str) -> dict | None

async def list_collections() -> list[dict]

async def update_collection(collection_id: str, **kwargs) -> None

async def delete_collection(collection_id: str) -> None
```

**Contract**:
- create_collection: Raises IntegrityError if name/qdrant_collection_name already exists
- get_collection: Returns {id, name, description, embedding_model, chunk_profile, qdrant_collection_name, created_at} or None
- list_collections: Returns list of all collection dicts
- update_collection: Partial updates, passes any field to UPDATE SET
- delete_collection: Cascades to documents, ingestion_jobs, parent_chunks, query_traces

**Raises**:
- sqlite3.IntegrityError: Unique constraint violation (name, qdrant_collection_name)
- sqlite3.OperationalError: Schema issue or connection problem

---

#### Documents CRUD

```python
async def create_document(
    id: str,  # UUID4
    collection_id: str,
    filename: str,
    file_path: str | None,
    file_hash: str,
    status: str = "pending"
) -> None

async def get_document(doc_id: str) -> dict | None

async def get_document_by_hash(collection_id: str, file_hash: str) -> dict | None

async def list_documents(collection_id: str) -> list[dict]

async def update_document(doc_id: str, **kwargs) -> None

async def delete_document(doc_id: str) -> None
```

**Contract**:
- create_document: Raises IntegrityError if (collection_id, file_hash) already exists
- get_document_by_hash: Used for duplicate detection; returns None if not found
- list_documents: Returns docs for given collection, ordered by created_at
- status field: "pending" | "ingesting" | "completed" | "failed" | "duplicate"
- Raises: sqlite3.IntegrityError on FK violation (collection_id must exist)

---

#### Ingestion Jobs CRUD

```python
async def create_ingestion_job(
    id: str,  # UUID4
    document_id: str,
    status: str = "started"
) -> None

async def get_ingestion_job(job_id: str) -> dict | None

async def list_ingestion_jobs(document_id: str) -> list[dict]

async def update_ingestion_job(
    job_id: str,
    status: str | None = None,
    chunks_processed: int | None = None,
    chunks_skipped: int | None = None,
    finished_at: str | None = None,
    error_msg: str | None = None
) -> None
```

**Contract**:
- create_ingestion_job: Creates job with started_at = CURRENT_TIMESTAMP
- get_ingestion_job: Returns {id, document_id, status, started_at, finished_at, error_msg, chunks_processed, chunks_skipped}
- update_ingestion_job: Partial updates; multiple fields can be updated in one call
- status values: "started" | "streaming" | "embedding" | "completed" | "failed" | "paused"
- Raises: sqlite3.IntegrityError if document_id doesn't exist

**Idempotent Resume Pattern**:
- Job marked failed; orchestrator can resume by creating new job or updating status
- UUID5 parent chunk IDs prevent duplicate storage

---

#### Parent Chunks CRUD

```python
async def create_parent_chunk(
    id: str,  # UUID5 deterministic
    collection_id: str,
    document_id: str,
    text: str,
    metadata_json: str | None = None
) -> None

async def get_parent_chunk(parent_id: str) -> dict | None

async def get_parent_chunks_batch(parent_ids: list[str]) -> list[dict]

async def list_parent_chunks(collection_id: str, document_id: str | None = None) -> list[dict]

async def delete_parent_chunks(document_id: str) -> None
```

**Contract**:
- create_parent_chunk: UUID5 id must be deterministic; raises IntegrityError if id already exists (safe upsert via retry)
- get_parent_chunk: Returns {id, collection_id, document_id, text, metadata_json, created_at}
- get_parent_chunks_batch: Batch retrieval optimized for search hit processing; target <10ms for 100 chunks
- Column aliases: Returns id AS parent_id, collection_id AS collection (schema flexibility for consumers)
- Raises: sqlite3.IntegrityError on FK violation or duplicate UUID5 id

**Performance**:
- Indexed on (collection_id, document_id) for fast document-scoped lookups
- Batch queries use IN (id1, id2, ...) for efficient retrieval

---

#### Query Traces CRUD

```python
async def create_query_trace(
    id: str,  # UUID4
    session_id: str,
    query: str,
    collections_searched: str,  # JSON array
    chunks_retrieved_json: str,  # JSON array
    latency_ms: int,
    llm_model: str | None = None,
    embed_model: str | None = None,
    confidence_score: float | None = None,
    sub_questions_json: str | None = None,
    meta_reasoning_triggered: bool = False
) -> None

async def list_query_traces(session_id: str, limit: int = 100) -> list[dict]

async def get_query_traces_by_timerange(
    start_ts: str,
    end_ts: str,
    limit: int = 1000
) -> list[dict]
```

**Contract**:
- create_query_trace: Append-only; inserts with created_at = CURRENT_TIMESTAMP
- list_query_traces: Returns traces for session, ordered by created_at DESC
- Indexed on (session_id, created_at) for dashboard queries
- JSON fields validated at insertion (app responsibility)
- confidence_score: Float 0.0–1.0 (5-signal aggregation from retrieval)
- Raises: None expected (append-only operation)

---

#### Settings CRUD

```python
async def get_setting(key: str) -> str | None

async def set_setting(key: str, value: str) -> None

async def list_settings() -> dict[str, str]

async def delete_setting(key: str) -> None
```

**Contract**:
- get_setting: Returns value or None if key not found
- set_setting: Upserts (INSERT OR REPLACE)
- list_settings: Returns dict of all key-value pairs
- Keys: Alphanumeric + underscore, 1–256 chars
- Values: Any JSON-serializable string

---

#### Providers CRUD (Encrypted Keys)

```python
async def create_provider(
    name: str,
    api_key_encrypted: str | None = None,
    base_url: str | None = None,
    is_active: bool = True
) -> None

async def get_provider(name: str) -> dict | None

async def list_providers() -> list[dict]

async def update_provider(
    name: str,
    is_active: bool | None = None,
    api_key_encrypted: str | None = None,
    base_url: str | None = None
) -> None

async def delete_provider(name: str) -> None
```

**Contract**:
- create_provider: name is PRIMARY KEY (provider identifier)
- get_provider: Returns {name, api_key_encrypted, base_url, is_active, created_at}
- api_key_encrypted: Fernet ciphertext or NULL (for Ollama with local base_url)
- Raises: sqlite3.IntegrityError if name already exists

---

## Error Handling

### Expected Exceptions

| Exception | Scenario | Recovery |
|-----------|----------|----------|
| sqlite3.IntegrityError | Unique/FK constraint violation | Retry with different key, or handle duplicate gracefully |
| sqlite3.OperationalError | Database locked, no space, corrupt | Log error, raise to orchestrator for retry |
| asyncio.TimeoutError | Query exceeds timeout (app-level) | Retry with circuit breaker (app responsibility) |

### Transaction Semantics

- **Auto-commit by default**: Each INSERT/UPDATE/DELETE auto-commits
- **Read consistency**: WAL mode guarantees consistent snapshot reads
- **Write serialization**: Single-threaded orchestrator (no explicit locking needed)

---

## Performance Characteristics

| Operation | Target | Notes |
|-----------|--------|-------|
| init_schema() | <100ms | Idempotent, runs once on startup |
| create_collection() | <5ms | Unique constraint check on name |
| create_document() | <5ms | Unique constraint check on (collection_id, file_hash) |
| get_parent_chunks_batch(100 ids) | <10ms | Index on (collection_id, document_id) |
| list_query_traces(session_id) | <20ms | Index on (session_id, created_at) |
| create_query_trace() | <1ms | Append-only, no blocking reads |

---

## Usage Example

```python
# In ingestion pipeline
async with SQLiteDB("data/embedinator.db") as db:
    # Create collection
    await db.create_collection(
        id=collection_id,
        name="my-research",
        embedding_model="all-MiniLM-L6-v2",
        chunk_profile="default",
        qdrant_collection_name="my_research_qdrant"
    )

    # Create document
    await db.create_document(
        id=doc_id,
        collection_id=collection_id,
        filename="report.pdf",
        file_hash=sha256_hash,
        status="ingesting"
    )

    # Create parent chunks (idempotent)
    await db.create_parent_chunk(
        id=uuid5_deterministic_id,
        collection_id=collection_id,
        document_id=doc_id,
        text=chunk_text,
        metadata_json=json.dumps({...})
    )

# In chat retrieval
async with SQLiteDB("data/embedinator.db") as db:
    # Get parent chunks by ID list from Qdrant search
    parents = await db.get_parent_chunks_batch(parent_ids)
    # Returns [{"parent_id": "...", "collection": "...", "text": "..."}, ...]

# Record query trace
await db.create_query_trace(
    id=trace_id,
    session_id=session_id,
    query=user_query,
    collections_searched=json.dumps([coll1_id, coll2_id]),
    chunks_retrieved_json=json.dumps([...]),
    latency_ms=125,
    confidence_score=0.87
)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-13 | Initial contract definition for Storage Architecture |
