# Quickstart: Ingestion Pipeline Development

**Branch**: `006-ingestion-pipeline` | **Date**: 2026-03-13

## Prerequisites

- Python 3.14+ with venv
- Rust 1.93.1+ with Cargo
- Docker (for Qdrant and Ollama)
- tmux (for Agent Teams orchestration)

## Setup

### 1. Start Infrastructure Services

```bash
docker compose up -d qdrant ollama
```

Wait for Qdrant health check:
```bash
curl -s http://localhost:6333/healthz  # expect: {"title":"qdrant - vectorass engine","version":"..."}
```

### 2. Build the Rust Ingestion Worker

```bash
cd ingestion-worker
cargo build --release
cd ..
```

The binary will be at `ingestion-worker/target/release/embedinator-worker`.

### 3. Install Python Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 4. Start the Backend

```bash
cd backend
python -m uvicorn main:create_app --factory --reload --host 0.0.0.0 --port 8000
```

## Testing

### IMPORTANT: External Test Runner

**NEVER run pytest inside Claude Code.** Use the external test runner:

```bash
# Run all ingestion tests:
zsh scripts/run-tests-external.sh -n spec06 --no-cov tests/unit/test_chunker.py tests/unit/test_embedder.py tests/unit/test_incremental.py tests/unit/test_ingestion_pipeline.py

# Check status:
cat Docs/Tests/spec06.status

# Read summary:
cat Docs/Tests/spec06.summary

# Full regression:
zsh scripts/run-tests-external.sh -n spec06-full tests/
```

### Rust Worker Tests

```bash
cd ingestion-worker
cargo test
```

## Manual Smoke Test

### Upload a file

```bash
# Create a test collection first (assuming spec-08 API exists):
COLLECTION_ID="test-collection-id"

# Upload a text file:
curl -X POST \
  -F "file=@README.md" \
  http://localhost:8000/api/collections/$COLLECTION_ID/ingest

# Expected: 202 with document_id and job_id
```

### Test the Rust worker directly

```bash
# Create a test file:
echo "# Hello World\n\nThis is a test document.\n\n## Section 2\n\nMore content here." > /tmp/test.md

# Run the worker:
./ingestion-worker/target/release/embedinator-worker --file /tmp/test.md --type markdown

# Expected: NDJSON output to stdout
```

### Verify ingestion

```bash
# Check document status in SQLite:
sqlite3 data/embedinator.db "SELECT id, filename, status, chunk_count FROM documents;"

# Check ingestion job:
sqlite3 data/embedinator.db "SELECT id, status, chunks_processed, chunks_skipped FROM ingestion_jobs;"

# Check parent chunks:
sqlite3 data/embedinator.db "SELECT id, source_file, page, breadcrumb FROM parent_chunks LIMIT 5;"

# Check Qdrant point count:
curl -s http://localhost:6333/collections/$COLLECTION_ID | jq '.result.points_count'
```

## Key Configuration

Settings in `backend/config.py` (via environment variables):

| Setting | Env Var | Default | Description |
|---------|---------|---------|-------------|
| `rust_worker_path` | `RUST_WORKER_PATH` | `ingestion-worker/target/release/embedinator-worker` | Path to Rust binary |
| `embed_max_workers` | `EMBED_MAX_WORKERS` | `4` | Parallel embedding threads |
| `embed_batch_size` | `EMBED_BATCH_SIZE` | `16` | Chunks per Ollama call |
| `qdrant_upsert_batch_size` | `QDRANT_UPSERT_BATCH_SIZE` | `50` | Points per Qdrant upsert |
| `parent_chunk_size` | `PARENT_CHUNK_SIZE` | `3000` | Parent chunk target chars |
| `child_chunk_size` | `CHILD_CHUNK_SIZE` | `500` | Child chunk target chars |
| `max_upload_size_mb` | `MAX_UPLOAD_SIZE_MB` | `100` | Max file size in MB |

## Architecture Summary

```
User uploads file
       │
       ▼
  API Endpoint (documents.py)
       │ validate type/size/duplicate
       ▼
  IngestionPipeline.ingest_file()
       │
       ├── Spawn Rust Worker (subprocess)
       │        │
       │        ▼ NDJSON stdout
       │
       ├── ChunkSplitter (parent/child + breadcrumbs + UUID5)
       │
       ├── BatchEmbedder (ThreadPoolExecutor + validate_embedding)
       │
       ├── QdrantClientWrapper.upsert() (batched, buffered)
       │
       └── SQLiteDB (documents + ingestion_jobs + parent_chunks)
```
