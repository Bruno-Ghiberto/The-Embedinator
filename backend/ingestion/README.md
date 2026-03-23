# backend/ingestion/

Document ingestion pipeline that processes uploaded files into searchable
vector embeddings.

## Pipeline Flow

```
File Upload --> Rust Worker (parse) --> Chunking --> Embedding --> Qdrant Upsert
                                           |
                                     SQLite (parent chunks, job tracking)
```

1. **File upload** -- `api/ingest.py` receives the file via multipart upload,
   validates the extension and size, and creates an ingestion job record.
2. **Rust worker** -- `pipeline.py` spawns the `embedinator-worker` binary as
   a subprocess. The worker reads the file, extracts text with structure
   (headings, code blocks), and outputs JSON chunks to stdout.
3. **Chunking** -- Parent chunks (default 3,000 tokens) are stored in SQLite.
   Child chunks (default 500 tokens) are created for embedding.
4. **Embedding** -- `embedder.py` generates vector embeddings in batches using
   the configured embedding model (default: nomic-embed-text via Ollama).
5. **Upsert** -- `UpsertBuffer` batches child chunks and upserts them to Qdrant
   with both dense vectors and BM25 sparse vectors for hybrid search.

## Key Classes

| Class                | File             | Purpose                           |
|----------------------|------------------|-----------------------------------|
| `IngestionPipeline`  | `pipeline.py`    | Orchestrates the full pipeline    |
| `UpsertBuffer`       | `pipeline.py`    | Batched Qdrant upsert with flush  |
| `IngestionResult`    | `pipeline.py`    | Result dataclass (chunks, timing) |

## Incremental Processing

`incremental.py` handles deduplication. When re-ingesting a file, the system:

1. Computes a content hash of the uploaded file
2. Checks if a document with the same hash already exists
3. If unchanged, skips processing (returns existing document)
4. If changed, deletes old chunks and re-processes

## Configuration

| Variable               | Default | Description                       |
|------------------------|---------|-----------------------------------|
| `RUST_WORKER_PATH`     | `ingestion-worker/target/release/embedinator-worker` | Path to Rust binary |
| `PARENT_CHUNK_SIZE`    | 3000    | Parent chunk size in tokens       |
| `CHILD_CHUNK_SIZE`     | 500     | Child chunk size in tokens        |
| `EMBED_BATCH_SIZE`     | 16      | Chunks per embedding batch        |
| `EMBED_MAX_WORKERS`    | 4       | Thread pool size for embeddings   |
| `QDRANT_UPSERT_BATCH_SIZE` | 50 | Points per Qdrant upsert call     |
| `MAX_UPLOAD_SIZE_MB`   | 100     | Maximum file upload size          |

## Supported Formats

- **PDF** -- Parsed by the Rust worker using `pdf-extract`
- **Markdown** -- Parsed with `pulldown-cmark`, preserving heading structure
- **Plain text** -- Direct text extraction with line-based chunking
