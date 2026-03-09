# Spec 07: Storage Architecture -- Implementation Plan Context

## Component Overview

The storage layer provides the dual-store persistence foundation for The Embedinator. Qdrant handles vector storage and hybrid retrieval (dense + sparse). SQLite handles all relational metadata, parent chunk text, observability traces, provider keys, and system settings. The two stores are linked by the `parent_id` relationship: Qdrant child chunks reference SQLite parent chunks.

This is a foundational spec. Nearly every other component depends on storage: the ingestion pipeline writes to it, the retrieval system reads from it, the API layer exposes it, and the agent graphs query through it.

## Technical Approach

### SQLite Layer (backend/storage/sqlite_db.py)

- Create an `SQLiteDB` class that manages the async connection via `aiosqlite`.
- On initialization, execute the full schema DDL (CREATE TABLE IF NOT EXISTS for idempotency).
- Set PRAGMA directives (WAL, foreign_keys) at connection time.
- Provide async methods for all CRUD operations on each table.
- Use parameterized queries exclusively (no string interpolation) for SQL injection prevention.
- Transactions for batch operations (e.g., inserting 200 parent chunks).

### Qdrant Layer (backend/storage/qdrant_client.py)

- Create a `QdrantStorage` class wrapping `qdrant_client.QdrantClient`.
- Provide methods for: collection creation (dense + sparse config), batch upsert, hybrid search, point deletion by filter, collection deletion.
- All methods decorated with `@retry` and guarded by `CircuitBreaker` (from spec-05).
- Search method supports both dense and sparse vectors in a single call with configurable fusion weights.

### Parent Store (backend/storage/parent_store.py)

- Thin wrapper over `SQLiteDB` specifically for parent chunk operations.
- `get_parent_by_id(parent_id)` -- retrieves full parent text and metadata for LLM context.
- `get_parents_by_ids(parent_ids)` -- batch retrieval for multi-chunk answers.
- `insert_parents(collection_id, document_id, parents)` -- batch insert in a transaction.

### Key Manager (backend/providers/key_manager.py)

- Fernet encryption/decryption for API keys stored in the `providers` table.
- Auto-generate encryption secret on first run if not configured.
- Never return raw keys through the API (only `has_key: bool`).

## File Structure

```
backend/
  storage/
    qdrant_client.py     # QdrantStorage class: collection init, upsert, search, delete
    sqlite_db.py         # SQLiteDB class: connection, schema init, all table CRUD
    parent_store.py      # ParentStore: parent chunk read/write convenience layer
  providers/
    key_manager.py       # Fernet encryption/decryption for API keys

data/
  embedinator.db         # SQLite database file (gitignored, created at runtime)
  qdrant_db/             # Qdrant persistence volume (gitignored)
```

## Implementation Steps

1. **Create `backend/storage/sqlite_db.py`**: Implement `SQLiteDB` class with async context manager. On `__aenter__`, connect to SQLite and set PRAGMAs. Execute schema DDL. Implement CRUD methods for: collections (create, get, list, delete), documents (create, get, list by collection, update status, get by hash, delete), ingestion_jobs (create, get, update), parent_chunks (insert batch, get by id, get by ids, delete by document), query_traces (insert, list with pagination, get by id), settings (get, set), providers (get all, get by name, update key, delete key).

2. **Create `backend/storage/qdrant_client.py`**: Implement `QdrantStorage` class. Initialize with host/port from settings. Implement `create_collection()` with dense + sparse vector config. Implement `batch_upsert()` with batching logic. Implement `hybrid_search()` with dense + sparse query. Implement `delete_by_source()` for point deletion by source_file filter. Implement `delete_collection()`. Add `@retry` decorators and `CircuitBreaker` on all methods.

3. **Create `backend/storage/parent_store.py`**: Implement `ParentStore` class wrapping `SQLiteDB` for parent chunk convenience methods.

4. **Create `backend/providers/key_manager.py`**: Implement Fernet-based encryption. Auto-generate key if `api_key_encryption_secret` is empty.

5. **Add startup initialization**: In `backend/main.py` (lifespan), initialize SQLiteDB (which creates tables), initialize QdrantStorage, and verify Qdrant connectivity.

6. **Write tests**: Unit tests for SQLiteDB CRUD operations, QdrantStorage collection creation and search, parent store batch operations, key encryption/decryption.

## Integration Points

- **Ingestion Pipeline** (spec-06): Writes to `documents`, `ingestion_jobs`, `parent_chunks` tables and Qdrant collections.
- **API** (spec-08): All endpoints read/write through the storage layer. Collections CRUD, document listing, chat endpoint searches Qdrant.
- **Agent Graphs** (specs 02-04): ResearchGraph retrieves chunks from Qdrant, resolves parent text from SQLite.
- **Retrieval** (spec-11): Searcher and reranker use QdrantStorage for hybrid search.
- **Accuracy** (spec-05): Circuit breaker and retry wrap QdrantStorage methods.
- **Providers** (spec-10): Provider registry reads/writes the `providers` table for API key management.
- **Observability** (spec-15): Query traces written to `query_traces` table.

## Key Code Patterns

### SQLiteDB Initialization Pattern

```python
import aiosqlite

class SQLiteDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()

    async def _init_schema(self):
        await self.db.executescript(SCHEMA_SQL)
        await self.db.commit()
```

### QdrantStorage Search Pattern

```python
from qdrant_client import QdrantClient
from qdrant_client.models import NamedVector, NamedSparseVector, SearchRequest

class QdrantStorage:
    async def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict,  # {indices: [...], values: [...]}
        top_k: int = 20,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> list[dict]:
        # Execute hybrid search with both dense and sparse vectors
        ...
```

### Fernet Key Management Pattern

```python
from cryptography.fernet import Fernet

class KeyManager:
    def __init__(self, secret: str):
        if not secret:
            secret = Fernet.generate_key().decode()
        self.fernet = Fernet(secret.encode() if isinstance(secret, str) else secret)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

## Phase Assignment

- **Phase 1 (MVP)**: SQLite schema (collections, documents, ingestion_jobs, parent_chunks tables). Qdrant collection creation with dense + sparse vectors. SQLiteDB and QdrantStorage classes with full CRUD. Provider table with Fernet key encryption. Settings table.
- **Phase 2 (Performance and Resilience)**: query_traces table fully populated on every chat request. Structured logging with trace ID propagation.
- **Phase 3 (Ecosystem and Polish)**: Per-document chunk profiles (extend collections table). LRU cache layer over Qdrant queries.
