# Spec 07: Storage Architecture -- Feature Specification Context

## Feature Description

The storage layer provides persistent data management for The Embedinator through two complementary systems:

1. **Qdrant** -- Vector database storing child chunk embeddings with hybrid retrieval support (dense + BM25 sparse vectors). Each user-defined collection maps to one Qdrant collection. Child chunks are the searchable unit.

2. **SQLite** -- Metadata and relational data store. Stores collection definitions, document tracking, ingestion job status, parent chunk text (the large-context counterpart to child vectors), query traces for observability, provider configurations with encrypted API keys, and system settings.

The architecture deliberately chooses SQLite over PostgreSQL for zero-config self-hosted deployment. WAL journal mode enables concurrent readers with a single writer. The entire database is a single file (`data/embedinator.db`) that can be backed up with a simple file copy.

The relationship between the two stores is: Qdrant holds child vectors with a `parent_id` payload field that references `parent_chunks.id` in SQLite. Parent chunks hold the full context text that the LLM uses for answer generation, while child chunks are the smaller retrieval units.

## Requirements

### Functional Requirements

- **Qdrant Collection Schema**: Each collection has `dense` vectors (from embedding model, e.g., 768 dims for nomic-embed-text, cosine distance) and `sparse` vectors (BM25 with IDF modifier). Both are searched in a single call with configurable fusion weights.
- **Qdrant Payload Schema**: Each child chunk point carries: `text`, `parent_id`, `breadcrumb`, `source_file`, `page`, `chunk_index`, `doc_type`, `chunk_hash`, `embedding_model`, `collection_name`, `ingested_at`.
- **SQLite Tables**: `collections`, `documents`, `ingestion_jobs`, `parent_chunks`, `query_traces`, `settings`, `providers` -- all with proper foreign keys, indexes, and constraints.
- **WAL Mode**: SQLite must run with `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` for concurrent read performance and referential integrity.
- **Parent Chunk Store**: Parent chunks are stored in SQLite with metadata JSON containing page, section, breadcrumb, and source_file. The `parent_chunks.id` is a deterministic UUID5 matching the parent's content identity.
- **Provider Key Encryption**: API keys in the `providers` table are encrypted with Fernet before storage. Ollama has no key (NULL).
- **Qdrant-SQLite Relationship**: Child chunk point in Qdrant references parent_chunks.id via the `parent_id` payload field. Parent chunk references documents.id. Documents reference collections.id. Collections store the `qdrant_collection_name` used to locate child vectors.

### Non-Functional Requirements

- SQLite writes are serialized (single writer) but reads are concurrent (WAL mode). This is acceptable for a single-user local deployment.
- Qdrant upserts are batched (batch_size=50) for throughput.
- All SQLite schema changes must be idempotent (CREATE TABLE IF NOT EXISTS pattern) for safe startup.
- Foreign key enforcement must be enabled at connection time.

## Key Technical Details

### Qdrant Vector Payload Schema (per child chunk point)

```json
{
  "text": "The raw child chunk text (without breadcrumb prefix)",
  "parent_id": "550e8400-e29b-41d4-a716-446655440000",
  "breadcrumb": "Chapter 2 > 2.3 Authentication",
  "source_file": "arca_api_spec_v2.pdf",
  "page": 3,
  "chunk_index": 7,
  "doc_type": "prose",
  "chunk_hash": "a3f5c2d8...",
  "embedding_model": "nomic-embed-text",
  "collection_name": "arca-specs",
  "ingested_at": "2026-03-03T10:00:00Z"
}
```

### Qdrant Collection Initialization

```python
from qdrant_client.models import (
    VectorParams, SparseVectorParams, Distance,
    SparseIndexParams, BM25Modifier,
)

async def create_qdrant_collection(
    client: QdrantClient,
    collection_name: str,
    dense_dim: int,
) -> None:
    await client.create_collection(
        collection_name=collection_name,
        vectors_config={
            "dense": VectorParams(
                size=dense_dim,
                distance=Distance.COSINE,
            ),
        },
        sparse_vectors_config={
            "sparse": SparseVectorParams(
                modifier=BM25Modifier.IDF,
            ),
        },
    )
```

### Complete SQLite Schema

```sql
-- Collection registry
CREATE TABLE collections (
    id          TEXT PRIMARY KEY,   -- UUID4
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    embedding_model     TEXT NOT NULL DEFAULT 'nomic-embed-text',
    chunk_profile       TEXT NOT NULL DEFAULT 'default',
    qdrant_collection_name  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL       -- ISO8601
);

-- Document tracking
CREATE TABLE documents (
    id              TEXT PRIMARY KEY,   -- UUID4
    collection_id   TEXT NOT NULL REFERENCES collections(id),
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,      -- SHA256 hex
    status          TEXT NOT NULL,      -- pending|ingesting|completed|failed|duplicate
    chunk_count     INTEGER DEFAULT 0,
    ingested_at     TEXT,               -- ISO8601, set on completion
    UNIQUE(collection_id, file_hash)
);

-- Ingestion job tracking
CREATE TABLE ingestion_jobs (
    id              TEXT PRIMARY KEY,   -- UUID4
    document_id     TEXT NOT NULL REFERENCES documents(id),
    status          TEXT NOT NULL,      -- started|streaming|embedding|completed|failed|paused
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_msg       TEXT,
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped  INTEGER DEFAULT 0
);

-- Parent chunk store (replaces JSON file store)
CREATE TABLE parent_chunks (
    id              TEXT PRIMARY KEY,   -- UUID5 deterministic
    collection_id   TEXT NOT NULL REFERENCES collections(id),
    document_id     TEXT NOT NULL REFERENCES documents(id),
    text            TEXT NOT NULL,
    metadata_json   TEXT NOT NULL,      -- JSON: page, section, breadcrumb, source_file
    created_at      TEXT NOT NULL
);
CREATE INDEX idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX idx_parent_chunks_document ON parent_chunks(document_id);

-- Query trace log (observability)
CREATE TABLE query_traces (
    id                      TEXT PRIMARY KEY,
    session_id              TEXT NOT NULL,
    query                   TEXT NOT NULL,
    sub_questions_json      TEXT,       -- JSON array of decomposed questions
    collections_searched    TEXT,       -- JSON array of collection names
    chunks_retrieved_json   TEXT,       -- JSON array of {chunk_id, score, collection}
    meta_reasoning_triggered INTEGER DEFAULT 0,  -- boolean
    latency_ms              INTEGER,
    llm_model               TEXT,
    embed_model             TEXT,
    confidence_score        REAL,
    created_at              TEXT NOT NULL
);
CREATE INDEX idx_traces_session ON query_traces(session_id);
CREATE INDEX idx_traces_created ON query_traces(created_at);

-- System settings key-value store
CREATE TABLE settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

-- Provider registry
CREATE TABLE providers (
    name       TEXT PRIMARY KEY,     -- 'ollama', 'openrouter', 'openai', 'anthropic', 'google'
    api_key_encrypted TEXT,          -- Fernet-encrypted API key (NULL for Ollama)
    base_url   TEXT,                 -- Override URL (e.g., Ollama non-default endpoint)
    is_active  INTEGER DEFAULT 0,   -- 1 if provider is configured and reachable
    created_at TEXT DEFAULT (datetime('now'))
);

-- Pragma for concurrent read performance
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

### ER Diagram Relationships

```
collections ||--o{ documents : "contains"
documents ||--o{ ingestion_jobs : "tracked by"
collections ||--o{ parent_chunks : "stores"
documents ||--o{ parent_chunks : "sourced from"
query_traces }o--|| collections : "searches"
```

### Qdrant-to-SQLite Cross-Reference

- Qdrant child chunk point has `parent_id` payload field -> matches `parent_chunks.id` in SQLite
- `parent_chunks.document_id` -> `documents.id`
- `documents.collection_id` -> `collections.id`
- `collections.qdrant_collection_name` -> Qdrant collection name

## Dependencies

- **Internal**: spec-06 (ingestion writes to documents, ingestion_jobs, parent_chunks, and Qdrant), spec-08 (API reads/writes all tables), spec-05 (circuit breaker on Qdrant client), spec-10 (providers table for API key management)
- **Libraries**: `qdrant-client >=1.17.0` (Qdrant vector database client with sparse vector support), `aiosqlite >=0.21` (async SQLite access), `cryptography >=44.0` (Fernet encryption for provider API keys)
- **Infrastructure**: Qdrant Docker container, SQLite 3.45+ (WAL mode support)

## Acceptance Criteria

1. Qdrant collection initialization creates both dense and sparse vector configurations.
2. All seven SQLite tables are created with correct columns, types, constraints, and foreign keys.
3. WAL journal mode is enabled. Foreign keys are enforced.
4. Indexes exist on `parent_chunks(collection_id)`, `parent_chunks(document_id)`, `query_traces(session_id)`, `query_traces(created_at)`.
5. `documents` table enforces UNIQUE(collection_id, file_hash).
6. Provider API keys are Fernet-encrypted before storage and decrypted on retrieval.
7. Parent chunk IDs are deterministic UUID5 values.
8. Qdrant payload contains all required fields: text, parent_id, breadcrumb, source_file, page, chunk_index, doc_type, chunk_hash, embedding_model, collection_name, ingested_at.
9. The Qdrant-SQLite cross-reference is consistent: every parent_id in Qdrant resolves to a row in parent_chunks.

## Architecture Reference

- **Qdrant client**: `backend/storage/qdrant_client.py` -- connection, collection init, upsert, search
- **SQLite DB**: `backend/storage/sqlite_db.py` -- connection, all table operations
- **Parent store**: `backend/storage/parent_store.py` -- parent chunk read/write (SQLite-backed)
- **Database file**: `data/embedinator.db`
- **Configuration**: `backend/config.py` -- `qdrant_host`, `qdrant_port`, `sqlite_path`
