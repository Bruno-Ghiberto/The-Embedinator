# backend/storage/

Dual storage layer using SQLite for structured metadata and Qdrant for
vector embeddings.

## Storage Architecture

```
                    +------------------+
                    |   Storage Layer  |
                    +--------+---------+
                             |
              +--------------+--------------+
              |                             |
    +---------v----------+       +----------v---------+
    |      SQLite        |       |       Qdrant       |
    |   (WAL mode)       |       |  (vector search)   |
    +--------------------+       +--------------------+
    | collections        |       | dense vectors      |
    | documents          |       | BM25 sparse vectors|
    | parent_chunks      |       | payload metadata   |
    | ingestion_jobs     |       +--------------------+
    | query_traces       |
    | providers          |
    | settings           |
    +--------------------+
```

## Key Components

### SQLiteDB (`sqlite_db.py`)

Async SQLite wrapper with 40+ methods organized by entity:

- **Collections** -- CRUD for document collections
- **Documents** -- CRUD with content hash for deduplication
- **Parent chunks** -- Large text chunks for LLM context (batch read support)
- **Ingestion jobs** -- Job tracking with status updates
- **Query traces** -- Per-query audit trail with timing and confidence
- **Providers** -- LLM provider configuration and active provider tracking
- **Settings** -- Key-value runtime settings

The database uses WAL (Write-Ahead Logging) mode for concurrent read access.
Schema initialization and migrations run automatically on `connect()`.

### QdrantClientWrapper (`qdrant_client.py`)

Low-level Qdrant operations with circuit breaker and retry:

- `ensure_collection(name, vector_size)` -- Create collection if not exists
- `search(collection, vector, top_k)` -- Dense vector search
- `upsert(collection, points)` -- Batch point insertion

### QdrantStorage (`qdrant_client.py`)

Higher-level Qdrant interface for the ingestion pipeline:

- `create_collection(name, dense_size, sparse_enabled)` -- Full collection setup
- `batch_upsert(collection, points)` -- Batch upsert with `QdrantPoint` objects
- `search_hybrid(collection, dense_vector, sparse_vector, top_k)` -- Hybrid search
- `delete_points_by_filter(collection, filter)` -- Filtered deletion
- `scroll_points(collection, filter, limit)` -- Paginated point retrieval
- Built-in circuit breaker and retry logic

### ParentStore (`parent_store.py`)

Reads parent chunks from SQLite for the research graph. When the reranker
selects child chunks, the parent store retrieves the full parent text to
provide richer context to the LLM.

### Other Files

| File                 | Purpose                                         |
|----------------------|-------------------------------------------------|
| `chunker.py`         | Text chunking with token-based splitting        |
| `document_parser.py` | File format detection and routing               |
| `indexing.py`        | Collection indexing and management               |

## Encryption

Cloud provider API keys are encrypted with Fernet (AES-128-CBC) before
storage in the `providers` table. The encryption key is read from
`EMBEDINATOR_FERNET_KEY`. See [`../providers/README.md`](../providers/README.md)
for details.

## Database Location

Default path: `data/embedinator.db` (configurable via `SQLITE_PATH`).
The checkpoint database for LangGraph session state is stored separately
at `data/checkpoints.db`.
