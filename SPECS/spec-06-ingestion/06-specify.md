# Spec 06: Ingestion Pipeline -- Feature Specification Context

## Feature Description

The ingestion pipeline is the data path through which documents (PDF, Markdown, plain text, code files) are parsed, chunked, embedded, and stored in Qdrant and SQLite. It consists of two major components:

1. **Python Ingestion Pipeline** (`backend/ingestion/pipeline.py`) -- The orchestrator that coordinates file upload handling, SHA256 hash-based change detection, spawning the Rust worker, reading NDJSON output, parent/child chunk splitting, breadcrumb prepending, deterministic UUID5 point ID generation, parallel batch embedding via Ollama, embedding validation, and Qdrant batch upsert.

2. **Rust Ingestion Worker** (`ingestion-worker/` Cargo workspace) -- A standalone binary (`embedinator-worker`) that handles CPU-intensive document parsing. It reads a file and streams parsed text chunks to stdout as NDJSON (one JSON object per line). Supports PDF, Markdown, plain text, and code files. The Python pipeline spawns this binary as a subprocess and reads its stdout line-by-line.

The pipeline is designed for incremental ingestion: files are tracked by SHA256 hash, and re-uploading an identical file returns `status=duplicate` immediately. Changed files trigger full re-ingestion with deterministic point IDs ensuring unchanged chunks overwrite in place.

## Requirements

### Functional Requirements

- **File Upload**: Accept multipart file uploads via `POST /api/collections/{id}/ingest`. Validate file type (allowed: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`) and file size (max 100MB).
- **Document & Job Tracking**: On upload, create a `documents` row (status=pending) and an `ingestion_jobs` row (status=started) in SQLite.
- **Incremental Ingestion**: Compute SHA256 of the uploaded file. If hash matches an existing completed document in the same collection, return `status=duplicate`. If hash matches a failed document, allow re-ingestion. If hash differs from an existing document (file changed), delete old Qdrant points by `source_file` filter and re-ingest.
- **Rust Worker Subprocess**: Spawn `embedinator-worker --file <path> [--type <type>]`. Read stdout line-by-line as NDJSON. Capture stderr for error logging.
- **Parent/Child Chunking**: Split raw text from the Rust worker into parent chunks (2000-4000 chars) and child chunks (~500 chars). Each child gets a breadcrumb prefix: `[Chapter > Section > Subsection] text`.
- **Deterministic Point IDs**: Each child chunk gets a UUID5 point ID computed as `uuid5(namespace, source_file:page:chunk_index)`. This ensures idempotent upserts.
- **Parallel Batch Embedding**: Embed child chunk text (with breadcrumb) via Ollama using a `ThreadPoolExecutor` with configurable worker count (default 4). Batch size default 16 chunks per Ollama API call.
- **Embedding Validation**: Every embedding vector is validated before upsert (dimension check, NaN check, zero-vector check, magnitude check). Failed chunks are logged and skipped.
- **Qdrant Batch Upsert**: Upsert child chunk vectors to Qdrant in batches of 50 points. Parent chunk text is stored in SQLite `parent_chunks` table.
- **Status Updates**: Update `ingestion_jobs.status` through the lifecycle: started -> streaming -> embedding -> completed (or failed/paused). Update `documents.chunk_count` and `documents.status` on completion.

### Non-Functional Requirements

- 200-page PDF should ingest in ~10-15 seconds total.
- Rust worker parsing: 2-5 seconds for 200 pages.
- Embedding with ThreadPoolExecutor (4 workers): ~2 seconds for 1200 chunks.
- Qdrant upsert: ~0.5 seconds for 1200 points.
- One bad embedding must not abort the entire batch.
- Pipeline must handle worker process crashes gracefully (log error, set status=failed).

## Key Technical Details

### Rust Worker CLI Interface

```
embedinator-worker --file <path> [--type <pdf|markdown|text|code>]

Options:
  --file   Path to the input file (required)
  --type   Document type (optional; auto-detected from extension if omitted)

Output:
  NDJSON stream to stdout, one chunk per line.
  Errors and diagnostics to stderr.
  Exit code 0 on success, non-zero on failure.
```

### Rust Worker NDJSON Output Schema (per line)

```json
{
  "text": "The chunk text content...",
  "page": 3,
  "section": "2.3 Authentication",
  "heading_path": ["Chapter 2: API Reference", "2.3 Authentication"],
  "doc_type": "prose",
  "chunk_profile": "default",
  "chunk_index": 7
}
```

### Rust Worker Module Structure

| File | Responsibility |
|------|---------------|
| `main.rs` | CLI argument parsing (clap), file type dispatch, stdout NDJSON serialization |
| `pdf.rs` | PDF text extraction using `pdf-extract` crate; page-by-page iteration |
| `markdown.rs` | Markdown parsing with `pulldown-cmark`; heading-boundary chunk splitting at H1/H2/H3 |
| `text.rs` | Plain text chunking; paragraph and sentence boundary detection |
| `heading_tracker.rs` | Stateful `HeadingTracker` struct; maintains Chapter > Section > Subsection hierarchy |
| `types.rs` | `Chunk` struct, `DocType` enum, serde serialization |

### Rust Cargo.toml Dependencies

```toml
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
pulldown-cmark = "0.12"
pdf-extract = "0.8"
clap = { version = "4", features = ["derive"] }
regex = "1"
```

### Rust Worker Error Handling

- **stderr**: Human-readable error messages (parsing failures, file not found)
- **Exit code**: 0 on success, 1 on file error, 2 on parse error
- **Partial output**: If parsing fails mid-document, all successfully parsed chunks are still streamed. The Python pipeline reads what it can and logs the error.

### Parent/Child Chunking Parameters

- Parent chunk target: 2000-4000 chars (approximately one page of a typical document)
- Child chunk target: ~500 chars
- Breadcrumb prefix: `[Chapter > Section > Subsection] ` prepended to each child chunk text (adds ~50 chars)
- Average ratio: ~6 child chunks per parent chunk

### Deterministic Point ID

```python
import uuid

EMBEDINATOR_NAMESPACE = uuid.UUID("some-fixed-namespace-uuid")

def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
    key = f"{source_file}:{page}:{chunk_index}"
    return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))
```

### Worked Example: 200-Page PDF

| Step | Input | Output | Time |
|------|-------|--------|------|
| Rust worker parsing | 200-page PDF | ~600 NDJSON lines | 2-5s |
| Parent/child splitting | 600 raw chunks | ~200 parents, ~1200 children | <1s |
| Embedding (Ollama) | 1200 children, batch=16, workers=4 | 1200 vectors | ~2s |
| Qdrant upsert | 1200 points, batch=50 | 24 API calls | ~0.5s |
| SQLite writes | 200 parent INSERTs | 200 rows | <0.1s |
| **Total** | | | **~10-15s** |

### Incremental Re-Ingestion

When the same PDF is re-uploaded with modifications:
1. SHA256 hash differs -> triggers re-ingestion
2. Old Qdrant points deleted via `source_file` filter
3. Full re-parse and re-embed (Rust worker cannot diff pages)
4. Deterministic UUID5 point IDs -> unchanged chunks get same IDs -> Qdrant upserts overwrite in place
5. Net result: only changed pages produce genuinely new vectors

## Dependencies

- **Internal**: spec-05 (embedding validation, circuit breaker on Ollama/Qdrant calls), spec-07 (SQLite tables: documents, ingestion_jobs, parent_chunks), spec-08 (API endpoint POST /api/collections/{id}/ingest)
- **Python Libraries**: `httpx >=0.28` (Ollama API calls), `python-multipart >=0.0.20` (file upload parsing), `tenacity >=9.0` (retry), `aiosqlite >=0.21` (SQLite writes)
- **Rust Crates**: `serde 1`, `serde_json 1`, `pulldown-cmark 0.12`, `pdf-extract 0.8`, `clap 4`, `regex 1`
- **Infrastructure**: Ollama (embedding inference), Qdrant (vector storage)

## Acceptance Criteria

1. Multipart file upload to `/api/collections/{id}/ingest` triggers the full ingestion pipeline.
2. Unsupported file types are rejected with HTTP 400. Files exceeding 100MB are rejected with HTTP 413.
3. Duplicate files (same SHA256 in same collection with status=completed) return `status=duplicate` without re-processing.
4. Changed files trigger deletion of old Qdrant points and full re-ingestion.
5. Rust worker binary parses PDF, Markdown, and plain text files and streams NDJSON to stdout.
6. Parent/child chunking produces parents of 2000-4000 chars and children of ~500 chars.
7. Breadcrumbs are prepended to each child chunk text.
8. Point IDs are deterministic (same source_file + page + chunk_index always produces the same UUID5).
9. Embedding is parallelized via ThreadPoolExecutor.
10. Failed embeddings are logged and skipped, not fatal.
11. Ingestion job status transitions: started -> streaming -> embedding -> completed.
12. A 200-page PDF ingests in under 20 seconds.

## Architecture Reference

- **Python pipeline**: `backend/ingestion/pipeline.py` -- orchestrator
- **Chunker**: `backend/ingestion/chunker.py` -- parent/child splitting, breadcrumb prepending
- **Embedder**: `backend/ingestion/embedder.py` -- Ollama embedding calls, ThreadPoolExecutor batching
- **Incremental**: `backend/ingestion/incremental.py` -- SHA256 hash check, change detection
- **Rust worker**: `ingestion-worker/` -- Cargo workspace with src/main.rs, pdf.rs, markdown.rs, text.rs, heading_tracker.rs, types.rs
- **Configuration**: `backend/config.py` -- `rust_worker_path`, `upload_dir`, `max_upload_size_mb`, `parent_chunk_size`, `child_chunk_size`, `embed_batch_size`, `embed_max_workers`, `qdrant_upsert_batch_size`
