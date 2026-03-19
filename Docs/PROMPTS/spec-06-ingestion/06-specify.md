# Spec 06: Ingestion Pipeline -- Feature Specification Context

## Feature Description

The ingestion pipeline is the data path through which documents (PDF, Markdown, plain text, code files) are parsed, chunked, embedded, and stored in Qdrant and SQLite. It consists of two major components:

1. **Python Ingestion Pipeline** (`backend/ingestion/pipeline.py`) -- The orchestrator that coordinates file upload handling, SHA256 hash-based change detection, spawning the Rust worker, reading NDJSON output, parent/child chunk splitting, breadcrumb prepending, deterministic UUID5 point ID generation, parallel batch embedding via Ollama, embedding validation, and Qdrant batch upsert.

2. **Rust Ingestion Worker** (`ingestion-worker/` Cargo workspace) -- A standalone binary (`embedinator-worker`) that handles CPU-intensive document parsing. It reads a file and streams parsed text chunks to stdout as NDJSON (one JSON object per line). Supports PDF, Markdown, plain text, and code files. The Python pipeline spawns this binary as a subprocess and reads its stdout line-by-line.

The pipeline is designed for incremental ingestion: files are tracked by SHA256 hash, and re-uploading an identical file is rejected with HTTP 409 `DUPLICATE_DOCUMENT` immediately (per API reference). Changed files trigger full re-ingestion with deterministic point IDs ensuring unchanged chunks overwrite in place.

> **Important — Existing Code Migration**: The Phase 1 MVP implemented a simplified ingestion path in `backend/storage/` and `backend/api/documents.py` that this spec **supersedes**. See the [Existing Code Migration](#existing-code-migration) section for details.

## Requirements

### Functional Requirements

- **File Upload**: Accept multipart file uploads via `POST /api/collections/{collection_id}/ingest` (migrates from the existing `POST /api/documents` endpoint). Validate file type (allowed: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`) and file size (max 100MB). Unsupported types return HTTP 400 `INVALID_FILE`; oversized files return HTTP 413.
- **Document & Job Tracking**: On upload, create a `documents` row (status=`pending`) and an `ingestion_jobs` row (status=`started`) in SQLite. Document statuses: `pending` | `ingesting` | `completed` | `failed` | `duplicate` (per API reference). Job statuses: `started` | `streaming` | `embedding` | `completed` | `failed` | `paused`.
- **Incremental Ingestion**: Compute SHA256 of the uploaded file. If hash matches an existing completed document in the same collection, reject with HTTP 409 `DUPLICATE_DOCUMENT` (per API reference). If hash matches a failed document, allow re-ingestion. If hash differs from an existing document (file changed), delete old Qdrant points by `source_file` filter and re-ingest.
- **Rust Worker Subprocess**: Spawn `embedinator-worker --file <path> [--type <type>]`. Read stdout line-by-line as NDJSON. Capture stderr for error logging.
- **Parent/Child Chunking**: Split raw text from the Rust worker into parent chunks (2000-4000 chars) and child chunks (~500 chars). Each child gets a breadcrumb prefix: `[Chapter > Section > Subsection] text`.
- **Deterministic Point IDs**: Each child chunk gets a UUID5 point ID computed as `uuid5(namespace, source_file:page:chunk_index)`. This ensures idempotent upserts. Note: the existing `backend/storage/indexing.py` uses `uuid4()` (random IDs); all new ingestion must use UUID5. Existing indexed data with random IDs will be orphaned and should be re-ingested.
- **Parallel Batch Embedding**: Embed child chunk text (with breadcrumb) via Ollama using a `ThreadPoolExecutor` with configurable worker count (default 4). Batch size default 16 chunks per Ollama API call.
- **Embedding Validation (FR-014/FR-015 from spec-05)**: Every embedding vector is validated before upsert using the interface contract deferred by spec-05 ADR-002. Function signature: `validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]` returning `(is_valid, reason)`. Four checks: correct dimension count, no NaN values, non-zero vector, magnitude above threshold. Failed chunks are logged with the reason string to `ingestion_jobs.error_log` and skipped (FR-015: one bad embedding must not abort the batch).
- **Qdrant Batch Upsert**: Upsert child chunk vectors to Qdrant via `QdrantClientWrapper` (the actual class name in `backend/storage/qdrant_client.py`) in batches of 50 points. Parent chunk text is stored in SQLite `parent_chunks` table.
- **Upsert Buffering & Job Pause/Resume (FR-020 from spec-05)**: When Qdrant is unreachable during ingestion, buffer pending upserts in-memory (up to 1,000 points) and flush when connection recovers. When the buffer reaches capacity and Qdrant is still unreachable, pause the ingestion job (set `ingestion_jobs.status = 'paused'`) rather than dropping items; resume and flush automatically once the connection recovers. When Ollama is down during ingestion, pause the job and set `status = 'paused'`; retry automatically when the circuit breaker closes (leveraging spec-05's `QdrantClientWrapper` circuit breaker pattern).
- **Status Updates**: Update `ingestion_jobs.status` through the lifecycle: `started` -> `streaming` -> `embedding` -> `completed` (or `failed`/`paused`). Update `documents.chunk_count` and `documents.status` on completion (set to `completed`) or failure (set to `failed`).

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
| `pdf.rs` | PDF text extraction using `pdf-extract` crate (blueprint prefers `pdfium-render` if pdfium is bundled; `pdf-extract` is the fallback — see `architecture-design.md:1138`); page-by-page iteration |
| `markdown.rs` | Markdown parsing with `pulldown-cmark`; heading-boundary chunk splitting at H1/H2/H3 |
| `text.rs` | Plain text chunking; paragraph and sentence boundary detection |
| `code.rs` | Code file handling (`.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`); routes through paragraph-boundary chunking similar to `text.rs` but with `doc_type: "code"` annotation |
| `heading_tracker.rs` | Stateful `HeadingTracker` struct; maintains Chapter > Section > Subsection hierarchy |
| `types.rs` | `Chunk` struct, `DocType` enum (`prose` | `code`), serde serialization |

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

- **Internal — spec-05**: Circuit breaker pattern on `QdrantClientWrapper` (`backend/storage/qdrant_client.py`), `CircuitOpenError` in `backend/errors.py`. FR-014/FR-015 (embedding validation) and FR-020 (upsert buffer + pause/resume) were **deferred to this spec** by spec-05 ADR-002 — see `specs/005-accuracy-robustness/tasks.md:144` for the interface contract.
- **Internal — spec-08**: API endpoint `POST /api/collections/{collection_id}/ingest`. NOTE: this spec creates the ingestion pipeline logic; spec-08 creates the API route that calls it. If implementing before spec-08, a temporary route in `backend/api/documents.py` can be used.
- **Schema Prerequisites (replaces spec-07 dependency)**: This spec **must create** the `documents`, `ingestion_jobs`, and `parent_chunks` tables itself (via `SQLiteDB._create_tables` or a migration), because spec-07 has not been implemented and the existing `documents` table schema diverges significantly from the blueprint. See [Schema Prerequisites](#schema-prerequisites) section below.
- **Python Libraries**: `httpx >=0.27` (Ollama API calls; already in requirements.txt), `python-multipart >=0.0.18` (file upload parsing; already in requirements.txt), `tenacity >=9.0` (retry; **ADD to requirements.txt**), `aiosqlite >=0.20` (SQLite writes; already in requirements.txt)
- **Rust Crates**: `serde 1`, `serde_json 1`, `pulldown-cmark 0.12`, `pdf-extract 0.8`, `clap 4`, `regex 1`
- **Infrastructure**: Ollama (embedding inference), Qdrant (vector storage)

## Acceptance Criteria

1. Multipart file upload to `/api/collections/{collection_id}/ingest` triggers the full ingestion pipeline.
2. Unsupported file types are rejected with HTTP 400 `INVALID_FILE`. Files exceeding 100MB are rejected with HTTP 413.
3. Duplicate files (same SHA256 in same collection with status=completed) are rejected with HTTP 409 `DUPLICATE_DOCUMENT` without re-processing.
4. Changed files trigger deletion of old Qdrant points and full re-ingestion.
5. Rust worker binary parses PDF, Markdown, plain text, and code files and streams NDJSON to stdout.
6. Parent/child chunking produces parents of 2000-4000 chars and children of ~500 chars.
7. Breadcrumbs are prepended to each child chunk text.
8. Point IDs are deterministic (same source_file + page + chunk_index always produces the same UUID5).
9. Embedding is parallelized via ThreadPoolExecutor.
10. Failed embeddings are logged with reason and skipped, not fatal (FR-014/FR-015).
11. Ingestion job status transitions: started -> streaming -> embedding -> completed (or failed/paused).
12. A 200-page PDF ingests in under 20 seconds.
13. When Qdrant is unreachable, upserts are buffered in-memory (up to 1,000 points) and flushed on recovery; when the buffer is full, the job is paused (not aborted) and resumes automatically (FR-020).
14. When Ollama is down during ingestion, the job is paused and retries when the circuit breaker closes.
15. The `documents` table schema matches the blueprint (single `collection_id` FK, `file_hash`, `chunk_count`, status enum: `pending|ingesting|completed|failed|duplicate`).
16. The `ingestion_jobs` and `parent_chunks` tables are created as part of this spec.

## Schema Prerequisites

This spec must create or migrate the following SQLite tables to match `data-model.md`. The existing `_create_tables()` in `backend/storage/sqlite_db.py` does NOT include `ingestion_jobs` or `parent_chunks`, and the existing `documents` table diverges significantly from the blueprint.

### `documents` table — MIGRATION REQUIRED

The existing schema (Phase 1 MVP) diverges from the blueprint:

| Aspect | Existing (`sqlite_db.py:39-48`) | Blueprint (`data-model.md:109-122`) |
|--------|--------------------------------|-------------------------------------|
| Collection FK | `collection_ids JSON` (multi-collection) | `collection_id TEXT NOT NULL FK` (single) |
| Name column | `name TEXT` | `filename TEXT` |
| Hash column | ❌ missing | `file_hash TEXT NOT NULL` (SHA256 hex) |
| Chunk count | ❌ missing | `chunk_count INTEGER DEFAULT 0` |
| Status values | `uploaded/parsing/indexing/indexed/failed` | `pending/ingesting/completed/failed/duplicate` |
| Completion timestamp | `upload_date` | `ingested_at` |
| Unique constraint | none | `(collection_id, file_hash)` — prevents duplicate uploads per collection |

**Action**: Recreate the `documents` table to match the blueprint schema. Update `SQLiteDB._create_tables()` and add migration logic for any existing data.

### `ingestion_jobs` table — NEW

```sql
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,       -- started|streaming|embedding|completed|failed|paused
    started_at TEXT NOT NULL,   -- ISO8601
    finished_at TEXT,           -- ISO8601, set on completion/failure
    error_msg TEXT,             -- Error details if failed
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped INTEGER DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

### `parent_chunks` table — NEW

> **Schema decision needed**: The existing `ParentStore.get_by_ids()` in `backend/storage/parent_store.py` queries flat columns (`parent_id, text, source_file, page, breadcrumb, collection`). The blueprint (`data-model.md:137-150`) specifies a JSON column approach (`id, collection_id, document_id, text, metadata_json, created_at`). This spec must pick ONE schema and update `ParentStore` to match. Recommendation: use the flat-column schema already in use by `ParentStore` for consistency with the existing read path, and update column names to match (`parent_id` → `id`, `collection` → `collection_id`, add `document_id` and `created_at`).

```sql
CREATE TABLE IF NOT EXISTS parent_chunks (
    id TEXT PRIMARY KEY,           -- UUID5 deterministic
    collection_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    text TEXT NOT NULL,
    source_file TEXT NOT NULL,
    page INTEGER,
    breadcrumb TEXT,
    created_at TEXT NOT NULL,       -- ISO8601
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);
```

## Existing Code Migration

The Phase 1 MVP implemented a simplified ingestion path that this spec **supersedes**. The following modules must be addressed:

| Existing Module | Function | Action |
|----------------|----------|--------|
| `backend/storage/chunker.py` | `chunk_text()` — simple overlapping chunks, no parent/child, no breadcrumbs | **SUPERSEDED** by `backend/ingestion/chunker.py` (parent/child + breadcrumbs). Delete or deprecate. |
| `backend/storage/document_parser.py` | `parse_document()` — Python-based PDF/MD/TXT parsing (only 3 file types) | **SUPERSEDED** by the Rust ingestion worker (12 file types). Delete or deprecate. |
| `backend/storage/indexing.py` | `index_chunks()` — uuid4 random IDs, no validation, single batch, no parent/child | **SUPERSEDED** by `backend/ingestion/pipeline.py` + `embedder.py` (UUID5, validation, parallel batching). Delete or deprecate. |
| `backend/api/documents.py` | `upload_document()` at `POST /api/documents` + `_process_document()` orchestrator | **SUPERSEDED** by `POST /api/collections/{collection_id}/ingest` + `IngestionPipeline.ingest_file()`. Migrate endpoint path. Keep `list_documents`, `get_document`, `delete_document` routes. |
| `backend/api/documents.py:14` | `SUPPORTED_FORMATS = {".pdf", ".md", ".txt"}` | **EXTEND** to include all 12 file types: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h` |

> **Note on `backend/storage/parent_store.py`**: This module is used by the ResearchGraph (spec-03) for **reading** parent chunks. It must NOT be deleted. Its `get_by_ids()` query must be updated to match whichever `parent_chunks` table schema is chosen above.

## Architecture Reference

- **Python pipeline**: `backend/ingestion/pipeline.py` -- `IngestionPipeline` class (see `architecture-design.md:2421-2461` for the blueprint class skeleton with `ingest_file()`, `check_duplicate()`, and `IngestionResult` model)
- **Chunker**: `backend/ingestion/chunker.py` -- `ChunkSplitter` class; parent/child splitting, breadcrumb prepending
- **Embedder**: `backend/ingestion/embedder.py` -- `BatchEmbedder` class with `embed_batch()` and `validate_embedding(vector, expected_dim) -> tuple[bool, str]` (see `architecture-design.md:2463-2498` for the blueprint class skeleton)
- **Incremental**: `backend/ingestion/incremental.py` -- `IncrementalChecker` class; SHA256 hash check, change detection
- **Rust worker**: `ingestion-worker/` -- Cargo workspace with `src/main.rs`, `pdf.rs`, `markdown.rs`, `text.rs`, `code.rs`, `heading_tracker.rs`, `types.rs`
- **Configuration**: `backend/config.py` -- The following fields already exist: `upload_dir` (default `"data/uploads"`), `max_upload_size_mb` (default `100`), `parent_chunk_size` (default `3000`), `child_chunk_size` (default `500`), `embed_batch_size` (default `16`). The following fields must be **ADDED** to `Settings`: `rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"`, `embed_max_workers: int = 4`, `qdrant_upsert_batch_size: int = 50`
- **Qdrant client**: `backend/storage/qdrant_client.py` -- `QdrantClientWrapper` class (NOT `QdrantStorage` as named in the blueprint; the actual class was renamed during implementation). The circuit breaker and retry logic from spec-05 are already wired in.
