# Spec 06: Ingestion Pipeline -- Implementation Context

## Implementation Scope

### Files to Create
- `backend/ingestion/pipeline.py` -- Main orchestrator
- `backend/ingestion/chunker.py` -- Parent/child splitting and breadcrumb prepending
- `backend/ingestion/embedder.py` -- Ollama embedding with parallel batching and validation
- `backend/ingestion/incremental.py` -- SHA256 hash-based change detection
- `ingestion-worker/Cargo.toml` -- Rust project configuration
- `ingestion-worker/src/main.rs` -- CLI entry point and NDJSON output
- `ingestion-worker/src/pdf.rs` -- PDF text extraction
- `ingestion-worker/src/markdown.rs` -- Markdown parsing
- `ingestion-worker/src/text.rs` -- Plain text chunking
- `ingestion-worker/src/heading_tracker.rs` -- Heading hierarchy tracking
- `ingestion-worker/src/types.rs` -- Chunk struct and DocType enum

### Files to Modify
- `backend/config.py` -- Add ingestion-related configuration fields

## Code Specifications

### Pipeline Orchestrator (backend/ingestion/pipeline.py)

```python
import asyncio
import json
import subprocess
import uuid
from typing import Optional

from backend.config import get_settings
from backend.ingestion.chunker import chunk_document, prepend_breadcrumb
from backend.ingestion.embedder import embed_chunks_parallel, validate_embedding
from backend.ingestion.incremental import check_duplicate, compute_file_hash
from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import QdrantStorage

settings = get_settings()

async def ingest_document(
    db: SQLiteDB,
    qdrant: QdrantStorage,
    collection_id: str,
    collection_name: str,
    file_path: str,
    filename: str,
    embedding_model: str,
    dense_dim: int,
) -> dict:
    """Main ingestion orchestrator. Returns {job_id, document_id, status}."""

    # 1. Compute SHA256
    file_hash = compute_file_hash(file_path)

    # 2. Check for duplicates
    dup_result = await check_duplicate(db, collection_id, file_hash)
    if dup_result == "duplicate":
        doc_id = await db.create_document(collection_id, filename, file_path, file_hash, status="duplicate")
        return {"job_id": None, "document_id": doc_id, "status": "duplicate"}
    elif dup_result == "changed":
        # Delete old Qdrant points by source_file filter
        await qdrant.delete_by_source(collection_name, filename)
        await db.delete_document_chunks(collection_id, filename)

    # 3. Create document and job records
    doc_id = str(uuid.uuid4())
    job_id = str(uuid.uuid4())
    await db.create_document(collection_id, filename, file_path, file_hash, status="ingesting", doc_id=doc_id)
    await db.create_ingestion_job(job_id, doc_id, status="started")

    try:
        # 4. Spawn Rust worker (or Python fallback)
        await db.update_ingestion_job(job_id, status="streaming")
        raw_chunks = []
        async for chunk in run_rust_worker(file_path):
            raw_chunks.append(chunk)

        # 5. Parent/child splitting
        parents, children = chunk_document(
            raw_chunks,
            parent_size=settings.parent_chunk_size,
            child_size=settings.child_chunk_size,
            source_file=filename,
        )

        # 6. Embed children
        await db.update_ingestion_job(job_id, status="embedding")
        child_texts = [c["text_with_breadcrumb"] for c in children]
        embeddings = await embed_chunks_parallel(
            child_texts,
            model=embedding_model,
            batch_size=settings.embed_batch_size,
            max_workers=settings.embed_max_workers,
        )

        # 7. Validate and upsert
        valid_children = []
        skipped = 0
        for child, embedding in zip(children, embeddings):
            if validate_embedding(embedding, dense_dim):
                child["embedding"] = embedding
                valid_children.append(child)
            else:
                skipped += 1

        # 8. Batch upsert to Qdrant
        await qdrant.batch_upsert(
            collection_name,
            valid_children,
            batch_size=settings.qdrant_upsert_batch_size,
        )

        # 9. Store parent chunks in SQLite
        await db.insert_parent_chunks(collection_id, doc_id, parents)

        # 10. Update status
        chunk_count = len(valid_children)
        await db.update_document(doc_id, status="completed", chunk_count=chunk_count)
        await db.update_ingestion_job(
            job_id, status="completed",
            chunks_processed=chunk_count,
            chunks_skipped=skipped,
        )

        return {"job_id": job_id, "document_id": doc_id, "status": "completed"}

    except Exception as e:
        await db.update_document(doc_id, status="failed")
        await db.update_ingestion_job(job_id, status="failed", error_msg=str(e))
        raise
```

### Chunker (backend/ingestion/chunker.py)

```python
import uuid
from typing import List, Tuple

EMBEDINATOR_NAMESPACE = uuid.UUID("d7e8f9a0-b1c2-3d4e-5f6a-7b8c9d0e1f2a")

def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
    key = f"{source_file}:{page}:{chunk_index}"
    return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))

def prepend_breadcrumb(text: str, heading_path: list[str]) -> str:
    if not heading_path:
        return text
    breadcrumb = " > ".join(heading_path)
    return f"[{breadcrumb}] {text}"

def chunk_document(
    raw_chunks: list[dict],
    parent_size: int = 3000,
    child_size: int = 500,
    source_file: str = "",
) -> Tuple[list[dict], list[dict]]:
    """Split raw chunks into parent and child chunks.

    Returns (parents, children) where each child has:
      - point_id: deterministic UUID5
      - text: raw child text
      - text_with_breadcrumb: text with heading path prepended
      - parent_id: UUID5 of the parent chunk
      - page, chunk_index, breadcrumb, source_file
    """
    parents = []
    children = []
    # ... accumulate raw text into parents of parent_size chars,
    # split each parent into children of child_size chars,
    # assign point_id via compute_point_id()
    return parents, children
```

### Embedder (backend/ingestion/embedder.py)

```python
import math
from concurrent.futures import ThreadPoolExecutor
from typing import List

from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5),
    reraise=True,
)
def embed_batch_sync(texts: List[str], model: str) -> List[List[float]]:
    """Synchronous embedding call to Ollama for a batch of texts."""
    # POST to Ollama /api/embed with batch of texts
    ...

async def embed_chunks_parallel(
    texts: List[str],
    model: str,
    batch_size: int = 16,
    max_workers: int = 4,
) -> List[List[float]]:
    """Embed chunks in parallel batches using ThreadPoolExecutor."""
    batches = [texts[i:i + batch_size] for i in range(0, len(texts), batch_size)]
    all_embeddings: List[List[float]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(embed_batch_sync, batch, model) for batch in batches]
        for future in futures:
            batch_result = future.result()
            all_embeddings.extend(batch_result)

    return all_embeddings

def validate_embedding(embedding: List[float], expected_dim: int) -> bool:
    if len(embedding) != expected_dim:
        return False
    if any(math.isnan(x) for x in embedding):
        return False
    if all(x == 0.0 for x in embedding):
        return False
    magnitude = math.sqrt(sum(x * x for x in embedding))
    if magnitude < 1e-6:
        return False
    return True
```

### Incremental Ingestion (backend/ingestion/incremental.py)

```python
import hashlib

def compute_file_hash(file_path: str) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            sha256.update(block)
    return sha256.hexdigest()

async def check_duplicate(db, collection_id: str, file_hash: str) -> str:
    """Returns 'duplicate', 'changed', or 'new'."""
    existing = await db.get_document_by_hash(collection_id, file_hash)
    if existing:
        if existing["status"] == "completed":
            return "duplicate"
        elif existing["status"] == "failed":
            return "new"  # allow retry
    # Check if same filename exists with different hash (changed file)
    existing_by_name = await db.get_document_by_filename(collection_id, existing_filename)
    if existing_by_name and existing_by_name["file_hash"] != file_hash:
        return "changed"
    return "new"
```

### Rust Worker Types (ingestion-worker/src/types.rs)

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize)]
pub struct Chunk {
    pub text: String,
    pub page: u32,
    pub section: String,
    pub heading_path: Vec<String>,
    pub doc_type: DocType,
    pub chunk_profile: String,
    pub chunk_index: u32,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum DocType {
    Prose,
    Code,
    Table,
    Mixed,
}
```

### Rust Worker Main (ingestion-worker/src/main.rs)

```rust
use clap::Parser;
use std::path::PathBuf;

mod pdf;
mod markdown;
mod text;
mod heading_tracker;
mod types;

use types::{Chunk, DocType};

#[derive(Parser)]
#[command(name = "embedinator-worker")]
#[command(about = "Document parser for The Embedinator")]
struct Cli {
    #[arg(long)]
    file: PathBuf,

    #[arg(long)]
    r#type: Option<String>,
}

fn main() {
    let cli = Cli::parse();

    let file_type = cli.r#type.unwrap_or_else(|| {
        detect_type_from_extension(&cli.file)
    });

    let chunks: Vec<Chunk> = match file_type.as_str() {
        "pdf" => pdf::extract(&cli.file),
        "markdown" => markdown::extract(&cli.file),
        "text" | "code" => text::extract(&cli.file),
        _ => {
            eprintln!("Unsupported file type: {}", file_type);
            std::process::exit(1);
        }
    };

    for chunk in chunks {
        let json = serde_json::to_string(&chunk).unwrap();
        println!("{}", json);
    }
}

fn detect_type_from_extension(path: &PathBuf) -> String {
    match path.extension().and_then(|e| e.to_str()) {
        Some("pdf") => "pdf".to_string(),
        Some("md") | Some("markdown") => "markdown".to_string(),
        Some("txt") => "text".to_string(),
        Some("py") | Some("js") | Some("ts") | Some("rs") | Some("go") | Some("java") => "code".to_string(),
        _ => "text".to_string(),
    }
}
```

### Rust Cargo.toml

```toml
[package]
name = "embedinator-worker"
version = "0.1.0"
edition = "2021"

[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
pulldown-cmark = "0.12"
pdf-extract = "0.8"
clap = { version = "4", features = ["derive"] }
regex = "1"
```

## Configuration

Add to `backend/config.py` `Settings` class:

```python
# Ingestion
rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
upload_dir: str = "data/uploads"
max_upload_size_mb: int = 100
parent_chunk_size: int = 3000     # chars
child_chunk_size: int = 500       # chars
embed_batch_size: int = 16
embed_max_workers: int = 4
qdrant_upsert_batch_size: int = 50
```

## Error Handling

- **Rust worker crash** (non-zero exit code): Read stderr, log the error message, set ingestion_job status to "failed" with error_msg containing the stderr output. All chunks successfully streamed before the crash are still processed.
- **Rust worker not found** (missing binary): In Phase 1, fall back to Python-only text extraction. In Phase 2, return HTTP 500 with message "Ingestion worker binary not found at {path}".
- **Ollama embedding failure**: Retry 3 times with exponential backoff (from spec-05). If all retries fail, pause the ingestion job (status=paused). Log the error.
- **Qdrant upsert failure**: Retry 3 times. If circuit breaker opens, buffer up to 1000 points in memory, flush when connection recovers. If buffer overflows, set job status to "failed".
- **Invalid embedding**: Log to ingestion_job, increment chunks_skipped, continue with next chunk.
- **Unsupported file type**: Return HTTP 400 before starting pipeline. Allowed types: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`.
- **File too large**: Return HTTP 413 if file exceeds `max_upload_size_mb` (default 100MB).
- **SHA256 computation failure**: Should not happen on valid files. If it does, log and return HTTP 500.

## Testing Requirements

### Unit Tests
- `test_compute_file_hash`: Verify SHA256 of a known file.
- `test_compute_point_id`: Verify deterministic UUID5 for known inputs.
- `test_prepend_breadcrumb`: Verify breadcrumb formatting.
- `test_chunk_document`: Verify parent/child splitting produces correct sizes and counts.
- `test_validate_embedding`: Test all four failure modes and valid case.
- `test_check_duplicate`: Test duplicate, changed, new, and failed-retry scenarios.

### Integration Tests
- `test_ingest_small_pdf`: Upload a 5-page test PDF, verify documents/ingestion_jobs rows, Qdrant points, and parent_chunks.
- `test_ingest_markdown`: Upload a markdown file, verify heading_path extraction and breadcrumb prepending.
- `test_ingest_duplicate`: Upload same file twice, verify second returns status=duplicate.
- `test_ingest_changed_file`: Upload file, modify, re-upload, verify old points deleted and new points created.

### Rust Unit Tests
- `test_pdf_extraction`: Parse a sample PDF, verify chunk count and text content.
- `test_markdown_extraction`: Parse a sample markdown, verify heading_path correctness.
- `test_heading_tracker`: Verify H1/H2/H3 hierarchy tracking across multiple sections.

## Done Criteria

- [ ] `pipeline.py` orchestrates the full ingestion flow from file upload to completed status
- [ ] `chunker.py` produces parent chunks of 2000-4000 chars and child chunks of ~500 chars
- [ ] Breadcrumbs are prepended to every child chunk
- [ ] Point IDs are deterministic UUID5 values
- [ ] `embedder.py` embeds chunks in parallel using ThreadPoolExecutor
- [ ] `validate_embedding()` rejects invalid vectors
- [ ] `incremental.py` detects duplicates and changed files correctly
- [ ] Rust worker binary compiles and parses PDF, Markdown, and plain text files
- [ ] Rust worker streams NDJSON to stdout with correct schema
- [ ] Ingestion job status transitions through started -> streaming -> embedding -> completed
- [ ] Failed chunks are logged and skipped without aborting the batch
- [ ] A 200-page PDF ingests in under 20 seconds
