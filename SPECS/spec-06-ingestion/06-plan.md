# Spec 06: Ingestion Pipeline -- Implementation Plan Context

## Component Overview

The ingestion pipeline is the data path that transforms uploaded documents into searchable vector embeddings. It has two halves: a Rust binary that handles fast CPU-bound document parsing, and a Python pipeline that orchestrates chunking, embedding, validation, and storage. The pipeline supports incremental ingestion via SHA256 hashing, ensuring idempotent re-uploads and efficient change detection.

This is a critical path component: every document that users can search over must pass through this pipeline. Reliability, observability (job status tracking), and performance (parallel embedding, batch upserts) are key design concerns.

## Technical Approach

### Python Pipeline (backend/ingestion/)

The Python pipeline is the orchestrator. It does not parse documents directly (that is the Rust worker's job). Its responsibilities are:

1. **Receive file upload** from the API layer
2. **Check for duplicates** via SHA256 hash comparison in SQLite
3. **Spawn Rust worker** as a subprocess, passing the file path
4. **Read NDJSON stream** from the worker's stdout, line by line
5. **Split into parent/child chunks** using `chunker.py`
6. **Prepend breadcrumbs** to each child chunk
7. **Generate deterministic UUID5 point IDs** for each child chunk
8. **Embed child chunks** in parallel batches via Ollama
9. **Validate each embedding** before upsert
10. **Batch upsert** to Qdrant (children as vectors) and SQLite (parents as text)
11. **Update job status** in SQLite throughout the process

### Rust Worker (ingestion-worker/)

A standalone Cargo binary. Receives a file path and optional type hint via CLI args. Parses the document and streams structured chunks to stdout as NDJSON. Each line is a self-contained JSON object with text, page number, section heading, heading path, doc type, and chunk index. The binary is stateless and produces no side effects beyond stdout/stderr output.

### Key Design Decisions

- **Streaming decoupling**: Python begins embedding chunk N while Rust is still parsing chunk N+5. No need to wait for the entire document to be parsed.
- **Deterministic IDs**: UUID5(namespace, source:page:chunk_index) ensures idempotent upserts. Re-ingesting the same content overwrites in place.
- **Full re-parse on change**: Simpler than page-level diffing. Rust parsing is fast enough (2-5s for 200 pages) that the complexity of incremental page diffing is not justified.
- **Parent/child split**: Parents provide context for the LLM (large windows). Children are the unit of vector retrieval (small, focused chunks). Parent text lives in SQLite; child vectors live in Qdrant.

## File Structure

```
backend/
  ingestion/
    pipeline.py          # Orchestrator: spawn Rust worker, coordinate full flow
    embedder.py          # Ollama embedding calls, ThreadPoolExecutor batching, validate_embedding()
    chunker.py           # Parent/child splitting, breadcrumb prepending
    incremental.py       # SHA256 hash check, change detection logic

ingestion-worker/
  src/
    main.rs              # CLI entry point (clap), file type dispatch, stdout NDJSON serialization
    pdf.rs               # PDF text extraction using pdf-extract crate; page-by-page iteration
    markdown.rs          # Markdown parsing with pulldown-cmark; heading-boundary splitting at H1/H2/H3
    text.rs              # Plain text chunking; paragraph and sentence boundary detection
    heading_tracker.rs   # Stateful HeadingTracker struct; Chapter > Section > Subsection hierarchy
    types.rs             # Chunk struct, DocType enum, serde serialization
  Cargo.toml
```

## Implementation Steps

### Phase 1 (MVP): Python-Only Ingestion

1. **Create `backend/ingestion/chunker.py`**: Implement parent/child splitting logic. Parent target: 2000-4000 chars. Child target: ~500 chars. Implement breadcrumb prepending using heading_path from raw chunks. Implement deterministic UUID5 point ID generation.

2. **Create `backend/ingestion/embedder.py`**: Implement Ollama embedding call function with `@retry` decorator (from spec-05). Implement `ThreadPoolExecutor`-based parallel batch embedding. Implement `validate_embedding()` (from spec-05). Batch size: 16 chunks per API call. Max workers: 4.

3. **Create `backend/ingestion/incremental.py`**: Implement SHA256 file hashing. Implement duplicate detection logic (query documents table by collection_id + file_hash). Implement change detection (hash differs -> delete old points, re-ingest).

4. **Create `backend/ingestion/pipeline.py`**: Wire together all components. In Phase 1, implement a Python-only text extraction fallback (simple page splitting) since the Rust worker comes in Phase 2. Handle file upload, duplicate check, chunking, embedding, validation, upsert, status updates.

5. **Wire into API**: Connect pipeline to `POST /api/collections/{id}/ingest` endpoint.

### Phase 2 (Performance): Rust Worker + Pipeline Update

6. **Create Rust worker** (`ingestion-worker/`): Set up Cargo workspace. Implement `types.rs` with `Chunk` struct and `DocType` enum. Implement `heading_tracker.rs` with `HeadingTracker`. Implement `pdf.rs` using `pdf-extract`. Implement `markdown.rs` using `pulldown-cmark`. Implement `text.rs` for plain text. Implement `main.rs` with clap CLI, file type dispatch, NDJSON serialization.

7. **Update `pipeline.py`**: Replace Python text extraction with subprocess spawn of Rust worker. Read NDJSON from worker stdout line-by-line. Handle worker process errors (non-zero exit, stderr messages).

8. **Add parallel batch embedding**: Update `embedder.py` to use `ThreadPoolExecutor` with configurable worker count.

9. **Add incremental ingestion**: Wire `incremental.py` into the pipeline. On re-upload, delete old Qdrant points by source_file filter before re-ingesting.

10. **Write tests**: Unit tests for chunker, embedder, incremental. Integration test for full pipeline with a small PDF.

## Integration Points

- **API** (spec-08): `POST /api/collections/{id}/ingest` calls `pipeline.py`. `GET /api/collections/{id}/ingest/{job_id}` reads job status from SQLite.
- **Storage** (spec-07): Pipeline writes to `documents`, `ingestion_jobs`, `parent_chunks` SQLite tables. Pipeline upserts child vectors to Qdrant collections.
- **Accuracy** (spec-05): Embedding validation and circuit breaker protect the ingestion path.
- **Retrieval** (spec-11): Stored child vectors in Qdrant and parent text in SQLite are the data source for search queries.

## Key Code Patterns

### Subprocess Spawn + NDJSON Read

```python
import subprocess
import json

async def run_rust_worker(file_path: str, file_type: str | None = None) -> AsyncIterator[dict]:
    cmd = [settings.rust_worker_path, "--file", file_path]
    if file_type:
        cmd.extend(["--type", file_type])

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    for line in proc.stdout:
        line = line.strip()
        if line:
            yield json.loads(line)

    proc.wait()
    if proc.returncode != 0:
        stderr = proc.stderr.read()
        raise IngestionWorkerError(f"Worker exited with code {proc.returncode}: {stderr}")
```

### Parent/Child Split Pattern

```python
def split_into_children(parent_text: str, target_size: int = 500) -> List[str]:
    # Split on sentence boundaries, accumulate until target_size
    ...

def prepend_breadcrumb(child_text: str, heading_path: List[str]) -> str:
    breadcrumb = " > ".join(heading_path)
    return f"[{breadcrumb}] {child_text}"
```

### Deterministic Point ID

```python
import uuid

EMBEDINATOR_NAMESPACE = uuid.UUID("d7e8f9a0-b1c2-3d4e-5f6a-7b8c9d0e1f2a")

def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
    key = f"{source_file}:{page}:{chunk_index}"
    return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))
```

### Parallel Batch Embedding

```python
from concurrent.futures import ThreadPoolExecutor

async def embed_chunks(chunks: List[str], model: str, batch_size: int = 16, max_workers: int = 4) -> List[List[float]]:
    batches = [chunks[i:i+batch_size] for i in range(0, len(chunks), batch_size)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(embed_batch, batch, model) for batch in batches]
        results = [f.result() for f in futures]

    return [vec for batch_result in results for vec in batch_result]
```

## Phase Assignment

- **Phase 1 (MVP)**: Python ingestion pipeline with Python-only text extraction fallback. Parent/child chunking, breadcrumb prepending, embedding, validation, Qdrant upsert. SQLite document/job tracking.
- **Phase 2 (Performance and Resilience)**: Rust ingestion worker binary. Pipeline updated to spawn worker subprocess and read NDJSON. Parallel batch embedding with ThreadPoolExecutor. Incremental ingestion via SHA256 hash check.
