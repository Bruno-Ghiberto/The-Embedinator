# Spec 06: Ingestion Pipeline -- Implementation Plan Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## Agent Team Orchestration Protocol

> **MANDATORY**: Agent Teams is REQUIRED for this spec. You MUST be running
> inside tmux. Agent Teams auto-detects tmux and spawns each teammate in its
> own split pane (the default `"auto"` teammateMode).
>
> **Enable**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`:
> ```json
> {
>   "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
> }
> ```
>
> **tmux multi-pane spawning is REQUIRED.** Each agent gets its own tmux pane
> for real-time visibility. Do NOT run agents sequentially in a single pane.

### Architecture

The **lead session** (you, the orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list with dependency tracking -- teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Wave Execution Order

```
Wave 1 (A1):                Foundation + Schema           -> Checkpoint Gate
Wave 2 (A2 + A3 + A4 + A5): Pipeline + Chunker + Embedder + Rust Worker (parallel) -> Checkpoint Gate
Wave 3 (A6 + A7):           Incremental + API Wiring (parallel) -> Checkpoint Gate
Wave 4 (A8):                Integration Tests             -> Checkpoint Gate
Wave 5 (Lead):              Polish + Full Regression      -> Done
```

### Step 1: Create the Team

```
Create an agent team called "spec06-ingestion" to implement the Ingestion
Pipeline feature.
```

The lead creates the team. All teammates will appear in their own tmux panes automatically.

### Step 2: Create Tasks with Dependencies

Create tasks in the shared task list so teammates can self-claim. Tasks encode the wave dependency chain:

```
Create the following tasks for the team:

Wave 1 -- Foundation:
- Schema migration (documents table), ingestion_jobs DDL, parent_chunks DDL (assign to A1)
- Config additions: rust_worker_path, embed_max_workers, qdrant_upsert_batch_size (assign to A1)
- ParentStore.get_by_ids() update for new parent_chunks schema (assign to A1)
- Test file scaffolding: create empty test modules (assign to A1)

Wave 2 -- Components (parallel, after Wave 1 completes):
- pipeline.py: IngestionPipeline class, worker spawn, NDJSON read, status tracking, upsert buffering, pause/resume (assign to A2, depends on Wave 1)
- chunker.py: ChunkSplitter, parent/child split, breadcrumbs, UUID5 IDs + unit tests (assign to A3, depends on Wave 1)
- embedder.py: BatchEmbedder, validate_embedding, ThreadPoolExecutor + unit tests (assign to A4, depends on Wave 1)
- Rust worker: full Cargo workspace (main.rs, pdf.rs, markdown.rs, text.rs, code.rs, heading_tracker.rs, types.rs) (assign to A5, depends on Wave 1)

Wave 3 -- Wiring (parallel, after Wave 2 completes):
- incremental.py: IncrementalChecker, SHA256 hashing, duplicate detection, change detection + unit tests (assign to A6, depends on Wave 2)
- API endpoint: POST /api/collections/{id}/ingest, file validation, existing code migration + unit tests (assign to A7, depends on Wave 2)

Wave 4 -- Integration (after Wave 3 completes):
- Integration tests: full pipeline, schema migration, fault tolerance, Rust worker build verification (assign to A8, depends on Wave 3)

Wave 5 -- Polish (after Wave 4 completes):
- Full regression, ruff check, done criteria validation (Lead)
```

### Step 3: Spawn Teammates per Wave

**Wave 1 -- Spawn A1 (Foundation):**
```
Spawn a teammate named "A1-foundation-schema" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A1-foundation-schema.md FIRST, then execute all assigned tasks."
```

Wait for A1 to complete. Run checkpoint gate (see below). Then proceed to Wave 2.

**Wave 2 -- Spawn A2 + A3 + A4 + A5 (parallel, each in own tmux pane):**
```
Spawn four teammates in parallel:

1. Teammate "A2-pipeline-orchestrator" with model Opus:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A2-pipeline-orchestrator.md FIRST, then execute all assigned tasks."

2. Teammate "A3-chunker-breadcrumbs" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A3-chunker-breadcrumbs.md FIRST, then execute all assigned tasks."

3. Teammate "A4-embedder-validation" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A4-embedder-validation.md FIRST, then execute all assigned tasks."

4. Teammate "A5-rust-worker" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A5-rust-worker.md FIRST, then execute all assigned tasks."
```

Wait for all four to complete. Run checkpoint gate. Then proceed to Wave 3.

**Wave 3 -- Spawn A6 + A7 (parallel):**
```
Spawn two teammates in parallel:

1. Teammate "A6-incremental-dedup" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A6-incremental-dedup.md FIRST, then execute all assigned tasks."

2. Teammate "A7-api-migration" with model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A7-api-migration.md FIRST, then execute all assigned tasks."
```

Wait for both to complete. Run checkpoint gate. Then proceed to Wave 4.

**Wave 4 -- Spawn A8 (Integration Tests):**
```
Spawn a teammate named "A8-integration-tests" with model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A8-integration-tests.md FIRST, then execute all assigned tasks."
```

Wait for A8 to complete. Run checkpoint gate. Then proceed to Wave 5.

**Wave 5 -- Lead (Polish):**
The lead runs the final polish directly (no teammate needed).

### Step 4: Checkpoint Gates (Lead Runs After Each Wave)

The lead runs these verification commands after each wave completes. If a gate fails, message the relevant teammate to fix it before proceeding.

```bash
# Wave 1: Foundation ready
python -c "from backend.storage.sqlite_db import SQLiteDB; print('SQLiteDB importable')"
python -c "from backend.config import settings; print('worker:', settings.rust_worker_path, 'workers:', settings.embed_max_workers, 'upsert_batch:', settings.qdrant_upsert_batch_size)"
python -c "from backend.storage.parent_store import ParentStore; print('ParentStore importable')"
ruff check backend/storage/sqlite_db.py backend/config.py backend/storage/parent_store.py

# Wave 2: All components importable + Rust builds
python -c "from backend.ingestion.pipeline import IngestionPipeline; print('Pipeline OK')"
python -c "from backend.ingestion.chunker import ChunkSplitter; print('ChunkSplitter OK')"
python -c "from backend.ingestion.embedder import BatchEmbedder, validate_embedding; print('Embedder OK')"
cargo build --release --manifest-path ingestion-worker/Cargo.toml
ruff check backend/ingestion/
zsh scripts/run-tests-external.sh -n spec06-w2 --no-cov tests/unit/
cat Docs/Tests/spec06-w2.status
cat Docs/Tests/spec06-w2.summary

# Wave 3: Incremental + API wiring
python -c "from backend.ingestion.incremental import IncrementalChecker; print('IncrementalChecker OK')"
python -c "from backend.api.documents import router; print('API router OK')"
ruff check backend/ingestion/incremental.py backend/api/documents.py
zsh scripts/run-tests-external.sh -n spec06-w3 --no-cov tests/unit/
cat Docs/Tests/spec06-w3.status
cat Docs/Tests/spec06-w3.summary

# Wave 4: Integration tests pass
zsh scripts/run-tests-external.sh -n spec06-integration tests/integration/test_ingestion_pipeline.py
cat Docs/Tests/spec06-integration.status
cat Docs/Tests/spec06-integration.summary

# Wave 5: Full regression (all specs)
zsh scripts/run-tests-external.sh -n spec06-full tests/
cat Docs/Tests/spec06-full.status
cat Docs/Tests/spec06-full.summary
ruff check .
```

### Step 5: Shutdown and Cleanup

After all waves complete and checkpoint gates pass:

```
Ask all teammates to shut down, then clean up the team.
```

This removes the shared team resources. Always shut down teammates before cleanup.

### Orchestration Rules

1. **Never skip checkpoint gates** -- a failed gate means the next wave's teammates will build on broken code.
2. **Use SendMessage for steering** -- if a teammate is going off-track, message them directly in their tmux pane or via the lead's messaging system.
3. **Parallel waves share files safely** -- A2, A3, A4 each create different files in `backend/ingestion/`. A5 works in an entirely separate `ingestion-worker/` directory. No merge conflicts if agents stay in their assigned regions.
4. **Teammate prompts are minimal** -- just point to the instruction file. All context lives in the instruction files and CLAUDE.md.
5. **Model selection** -- A2 (IngestionPipeline, complex orchestrator with subprocess management, status state machine, upsert buffering, pause/resume) uses Opus. All others use Sonnet for cost efficiency.
6. **Monitor via tmux** -- click into any teammate's pane to see their progress.
7. **If a teammate fails** -- shut it down and spawn a replacement with the same instruction file. The task list tracks which tasks are done.
8. **Never inline spec content in spawn prompts** -- agents MUST read their instruction file FIRST. All authoritative context lives in the instruction files and spec artifacts.
9. **NEVER run pytest inside Claude Code** -- all test execution goes through the external runner: `zsh scripts/run-tests-external.sh`. See [Testing Protocol](#testing-protocol).
10. **Rust worker is fully independent** -- A5 works in `ingestion-worker/` with zero dependency on Python code. It only needs to match the NDJSON output schema defined in its instruction file.

---

## Implementation Scope

### Files to Create

| File | Agent | Purpose |
|------|-------|---------|
| `backend/ingestion/__init__.py` | A1 | Package init |
| `backend/ingestion/pipeline.py` | A2 | IngestionPipeline orchestrator: worker spawn, NDJSON read, status tracking, upsert buffering, pause/resume |
| `backend/ingestion/chunker.py` | A3 | ChunkSplitter: parent/child split, breadcrumbs, deterministic UUID5 point IDs |
| `backend/ingestion/embedder.py` | A4 | BatchEmbedder: ThreadPoolExecutor parallel embedding, validate_embedding() |
| `backend/ingestion/incremental.py` | A6 | IncrementalChecker: SHA256 hashing, duplicate detection, change detection |
| `ingestion-worker/Cargo.toml` | A5 | Rust workspace manifest |
| `ingestion-worker/src/main.rs` | A5 | CLI entry point (clap), file type dispatch, stdout NDJSON serialization |
| `ingestion-worker/src/pdf.rs` | A5 | PDF text extraction via pdf-extract; page-by-page |
| `ingestion-worker/src/markdown.rs` | A5 | Markdown parsing via pulldown-cmark; heading-boundary splitting |
| `ingestion-worker/src/text.rs` | A5 | Plain text chunking; paragraph/sentence boundary detection |
| `ingestion-worker/src/code.rs` | A5 | Code file handling (9 extensions); doc_type "code" annotation |
| `ingestion-worker/src/heading_tracker.rs` | A5 | Stateful HeadingTracker: Chapter > Section > Subsection |
| `ingestion-worker/src/types.rs` | A5 | Chunk struct, DocType enum, serde serialization |
| `tests/unit/test_chunker.py` | A3 | Chunker unit tests |
| `tests/unit/test_embedder.py` | A4 | Embedder + validate_embedding unit tests |
| `tests/unit/test_incremental.py` | A6 | Incremental checker unit tests |
| `tests/unit/test_ingestion_pipeline.py` | A2 | Pipeline unit tests |
| `tests/unit/test_ingestion_api.py` | A7 | API endpoint unit tests |
| `tests/integration/test_ingestion_pipeline.py` | A8 | Full pipeline integration tests |
| `Docs/PROMPTS/spec-06-ingestion/agents/A1-foundation-schema.md` | Lead | A1 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A2-pipeline-orchestrator.md` | Lead | A2 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A3-chunker-breadcrumbs.md` | Lead | A3 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A4-embedder-validation.md` | Lead | A4 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A5-rust-worker.md` | Lead | A5 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A6-incremental-dedup.md` | Lead | A6 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A7-api-migration.md` | Lead | A7 instruction file |
| `Docs/PROMPTS/spec-06-ingestion/agents/A8-integration-tests.md` | Lead | A8 instruction file |

### Files to Modify

| File | Agent | Purpose |
|------|-------|---------|
| `backend/storage/sqlite_db.py` | A1 | Migrate documents table, add ingestion_jobs + parent_chunks DDL to `_create_tables()` |
| `backend/config.py` | A1 | Add `rust_worker_path`, `embed_max_workers`, `qdrant_upsert_batch_size` settings |
| `backend/storage/parent_store.py` | A1 | Update `get_by_ids()` query to match new parent_chunks schema |
| `backend/api/documents.py` | A7 | Add `POST /api/collections/{id}/ingest` route, extend `SUPPORTED_FORMATS` to 12 types, migrate existing upload endpoint |
| `requirements.txt` | A1 | Ensure `tenacity>=9.0` is present |

### Files That Exist and Are NOT Modified

- `backend/storage/qdrant_client.py` -- `QdrantClientWrapper` with circuit breaker from spec-05. Pipeline uses it via dependency injection. DO NOT MODIFY.
- `backend/agent/nodes.py` -- Conversation/research nodes. Unrelated to ingestion. DO NOT MODIFY.
- `backend/agent/confidence.py` -- Spec-03 R8 5-signal formula. DO NOT TOUCH.
- `backend/errors.py` -- Has `IngestionError`, `CircuitOpenError`. May need new error subclasses but verify first.
- `backend/main.py` -- App factory. A7 may need to register the new ingestion route here.

---

## Component Overview

The ingestion pipeline transforms uploaded documents into searchable vector embeddings. It has two halves:

1. **Rust Ingestion Worker** (`ingestion-worker/`) -- A standalone Cargo binary (`embedinator-worker`) that handles CPU-intensive document parsing. Reads a file, streams parsed text chunks to stdout as NDJSON (one JSON object per line). Supports PDF, Markdown, plain text, and 9 code file types. Stateless -- produces no side effects beyond stdout/stderr.

2. **Python Ingestion Pipeline** (`backend/ingestion/`) -- The orchestrator that coordinates the full flow: file upload handling, SHA256 duplicate detection, Rust worker subprocess spawn, NDJSON stream reading, parent/child chunk splitting with breadcrumbs, deterministic UUID5 point IDs, parallel batch embedding via Ollama, embedding validation, Qdrant batch upsert with buffering, and SQLite job/document status tracking.

### Key Design Decisions

- **Streaming decoupling**: Python begins embedding chunk N while Rust is still parsing chunk N+5. No need to wait for the entire document to be parsed.
- **Deterministic IDs**: `UUID5(namespace, source_file:page:chunk_index)` ensures idempotent upserts. Re-ingesting the same content overwrites in place.
- **Full re-parse on change**: Simpler than page-level diffing. Rust parsing is fast enough (2-5s for 200 pages) that incremental page diffing is not justified.
- **Parent/child split**: Parents provide context for the LLM (large windows, stored in SQLite). Children are the unit of vector retrieval (small, focused chunks, stored in Qdrant).
- **Upsert buffering**: When Qdrant is unreachable, buffer up to 1,000 points in-memory and flush on recovery. When buffer is full, pause the job (not abort). Resume automatically. (FR-012/FR-013 from spec)
- **Parallel ingestion**: Multiple jobs MAY run simultaneously across different collections. Configurable resource limits (embed_max_workers) prevent exhaustion. (FR-020 from spec)

---

## Schema Prerequisites

This spec must create or migrate the following SQLite tables. The existing `_create_tables()` in `backend/storage/sqlite_db.py` does NOT include `ingestion_jobs` or `parent_chunks`, and the existing `documents` table diverges from the blueprint.

### `documents` table -- MIGRATION REQUIRED

| Aspect | Existing (`sqlite_db.py`) | Required (spec) |
|--------|--------------------------|-----------------|
| Collection FK | `collection_ids JSON` (multi-collection) | `collection_id TEXT NOT NULL FK` (single) |
| Name column | `name TEXT` | `filename TEXT` |
| Hash column | missing | `file_hash TEXT NOT NULL` (SHA256 hex) |
| Chunk count | missing | `chunk_count INTEGER DEFAULT 0` |
| Status values | `uploaded/parsing/indexing/indexed/failed` | `pending/ingesting/completed/failed/duplicate` |
| Completion timestamp | `upload_date` | `ingested_at` |
| Unique constraint | none | `(collection_id, file_hash)` |

### `ingestion_jobs` table -- NEW

```sql
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    status TEXT NOT NULL,       -- started|streaming|embedding|completed|failed|paused
    started_at TEXT NOT NULL,   -- ISO8601
    finished_at TEXT,           -- ISO8601
    error_msg TEXT,
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped INTEGER DEFAULT 0,
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
```

### `parent_chunks` table -- NEW

Uses flat-column schema (consistent with existing `ParentStore.get_by_ids()` read path):

```sql
CREATE TABLE IF NOT EXISTS parent_chunks (
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    text TEXT NOT NULL,
    source_file TEXT NOT NULL,
    page INTEGER,
    breadcrumb TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    FOREIGN KEY (document_id) REFERENCES documents(id)
);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);
```

---

## Existing Code Migration

The Phase 1 MVP implemented a simplified ingestion path that this spec **supersedes**:

| Existing Module | Status | Action |
|----------------|--------|--------|
| `backend/storage/chunker.py` | SUPERSEDED | Delete or deprecate. Replaced by `backend/ingestion/chunker.py` (parent/child + breadcrumbs). |
| `backend/storage/document_parser.py` | SUPERSEDED | Delete or deprecate. Replaced by Rust ingestion worker (12 file types). |
| `backend/storage/indexing.py` | SUPERSEDED | Delete or deprecate. Replaced by `pipeline.py` + `embedder.py` (UUID5, validation, parallel). |
| `backend/api/documents.py` — `upload_document()` | SUPERSEDED | Replace with `POST /api/collections/{id}/ingest`. Keep `list_documents`, `get_document`, `delete_document`. |
| `backend/api/documents.py` — `SUPPORTED_FORMATS` | EXTEND | From 3 types to 12: add `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`. |
| `backend/storage/parent_store.py` | PRESERVE | Used by ResearchGraph (spec-03). Update `get_by_ids()` query for new schema. DO NOT DELETE. |

---

## File Structure

```
backend/
  ingestion/
    __init__.py
    pipeline.py          # IngestionPipeline: spawn worker, NDJSON read, status tracking, upsert buffer, pause/resume
    chunker.py           # ChunkSplitter: parent/child splitting, breadcrumbs, UUID5 IDs
    embedder.py          # BatchEmbedder: ThreadPoolExecutor parallel embedding, validate_embedding()
    incremental.py       # IncrementalChecker: SHA256 hash, duplicate detection, change detection
  storage/
    sqlite_db.py         # MODIFY: migrate documents, add ingestion_jobs + parent_chunks DDL
    parent_store.py      # MODIFY: update get_by_ids() for new parent_chunks schema
  api/
    documents.py         # MODIFY: add ingest endpoint, extend SUPPORTED_FORMATS, migrate upload
  config.py              # MODIFY: add rust_worker_path, embed_max_workers, qdrant_upsert_batch_size

ingestion-worker/
  Cargo.toml
  src/
    main.rs              # CLI (clap), file type dispatch, stdout NDJSON
    pdf.rs               # PDF extraction (pdf-extract), page-by-page
    markdown.rs          # Markdown (pulldown-cmark), heading-boundary splitting
    text.rs              # Plain text, paragraph/sentence boundaries
    code.rs              # Code files (.py/.js/.ts/.rs/.go/.java/.c/.cpp/.h), doc_type "code"
    heading_tracker.rs   # HeadingTracker: Chapter > Section > Subsection
    types.rs             # Chunk struct, DocType enum, serde

tests/
  unit/
    test_chunker.py
    test_embedder.py
    test_incremental.py
    test_ingestion_pipeline.py
    test_ingestion_api.py
  integration/
    test_ingestion_pipeline.py
```

---

## Key Code Patterns

### Subprocess Spawn + NDJSON Read (pipeline.py)

```python
import subprocess
import json
from backend.config import settings

async def _run_worker(file_path: str, file_type: str | None = None) -> AsyncIterator[dict]:
    """Spawn Rust worker and stream NDJSON chunks."""
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
        raise IngestionError(f"Worker exited {proc.returncode}: {stderr}")
```

### Parent/Child Split + Breadcrumbs (chunker.py)

```python
import uuid

EMBEDINATOR_NAMESPACE = uuid.UUID("d7e8f9a0-b1c2-3d4e-5f6a-7b8c9d0e1f2a")

def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
    key = f"{source_file}:{page}:{chunk_index}"
    return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))

def prepend_breadcrumb(text: str, heading_path: list[str]) -> str:
    breadcrumb = " > ".join(heading_path)
    return f"[{breadcrumb}] {text}"
```

### Embedding Validation (embedder.py)

```python
import math

def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]:
    """Validate embedding vector. Returns (is_valid, reason)."""
    if len(vector) != expected_dim:
        return False, f"dimension mismatch: got {len(vector)}, expected {expected_dim}"
    if any(math.isnan(v) for v in vector):
        return False, "contains NaN values"
    if all(v == 0.0 for v in vector):
        return False, "zero vector"
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude < 1e-6:
        return False, f"magnitude below threshold: {magnitude}"
    return True, "ok"
```

### Parallel Batch Embedding (embedder.py)

```python
from concurrent.futures import ThreadPoolExecutor
from backend.config import settings

async def embed_chunks(
    chunks: list[str], model: str,
    batch_size: int | None = None, max_workers: int | None = None
) -> list[list[float]]:
    batch_size = batch_size or settings.embed_batch_size
    max_workers = max_workers or settings.embed_max_workers
    batches = [chunks[i:i+batch_size] for i in range(0, len(chunks), batch_size)]

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_embed_batch, batch, model) for batch in batches]
        results = [f.result() for f in futures]

    return [vec for batch_result in results for vec in batch_result]
```

### Upsert Buffering + Pause/Resume (pipeline.py)

```python
class UpsertBuffer:
    """Buffer pending Qdrant upserts. Pause job when buffer full."""
    MAX_CAPACITY = 1000

    def __init__(self):
        self._buffer: list = []

    def add(self, points: list) -> bool:
        """Add points. Returns False if buffer is at capacity."""
        self._buffer.extend(points)
        return len(self._buffer) < self.MAX_CAPACITY

    async def flush(self, qdrant: QdrantClientWrapper, collection: str) -> int:
        """Flush buffer to Qdrant. Returns count flushed."""
        if not self._buffer:
            return 0
        batch_size = settings.qdrant_upsert_batch_size
        flushed = 0
        for i in range(0, len(self._buffer), batch_size):
            batch = self._buffer[i:i+batch_size]
            await qdrant.upsert(collection, batch)
            flushed += len(batch)
        self._buffer.clear()
        return flushed
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

### Rust Worker Cargo Dependencies

```toml
[dependencies]
serde = { version = "1", features = ["derive"] }
serde_json = "1"
pulldown-cmark = "0.12"
pdf-extract = "0.8"
clap = { version = "4", features = ["derive"] }
regex = "1"
```

---

## Integration Points

- **spec-05 (Accuracy/Robustness)**: Circuit breaker on `QdrantClientWrapper` (`backend/storage/qdrant_client.py`), `CircuitOpenError` in `backend/errors.py`. FR-014/FR-015 (embedding validation) and FR-020 (upsert buffer + pause/resume) were **deferred to this spec** by spec-05 ADR-002.
- **spec-03 (ResearchGraph)**: Uses `ParentStore.get_by_ids()` to read parent chunks during answer generation. Schema change must preserve this read path (FR-019).
- **spec-08 (API)**: `POST /api/collections/{collection_id}/ingest` endpoint. If implementing before spec-08, a temporary route in `documents.py` is acceptable.
- **spec-11 (Interfaces)**: Stored child vectors in Qdrant and parent text in SQLite are the data source for search queries.

---

## Spec-to-Agent Mapping

| Spec Requirement | Agent | Component |
|-----------------|-------|-----------|
| FR-001 (file upload, 12 types) | A7 | API endpoint |
| FR-002 (reject invalid) | A7 | File validation |
| FR-003 (SHA256 duplicate) | A6 | IncrementalChecker |
| FR-004 (re-ingest failed) | A6 | IncrementalChecker |
| FR-005 (delete old + re-ingest) | A6 | IncrementalChecker |
| FR-006 (native worker streaming) | A5 + A2 | Rust worker + pipeline spawn |
| FR-007 (parent/child + breadcrumbs) | A3 | ChunkSplitter |
| FR-008 (deterministic UUID5) | A3 | ChunkSplitter |
| FR-009 (parallel embedding) | A4 | BatchEmbedder |
| FR-010 (embedding validation) | A4 | validate_embedding() |
| FR-011 (batch upsert + parent storage) | A2 | IngestionPipeline |
| FR-012 (upsert buffering 1000 pts) | A2 | UpsertBuffer |
| FR-013 (Ollama pause/resume) | A2 | IngestionPipeline |
| FR-014 (job status lifecycle) | A2 + A1 | Pipeline + schema |
| FR-015 (document status update) | A2 + A1 | Pipeline + schema |
| FR-016 (worker crash handling) | A2 | IngestionPipeline |
| FR-017 (schema migration) | A1 | SQLiteDB._create_tables() |
| FR-018 (create tables) | A1 | SQLiteDB._create_tables() |
| FR-019 (ParentStore compat) | A1 | ParentStore.get_by_ids() |
| FR-020 (parallel ingestion) | A2 | Configurable resource limits |

---

## Configuration

### Existing Fields (DO NOT ADD -- already in `backend/config.py`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `upload_dir` | `str` | `"data/uploads"` | Upload directory |
| `max_upload_size_mb` | `int` | `100` | Max file size |
| `parent_chunk_size` | `int` | `3000` | Parent chunk target chars |
| `child_chunk_size` | `int` | `500` | Child chunk target chars |
| `embed_batch_size` | `int` | `16` | Chunks per Ollama API call |

### New Fields (A1 MUST ADD to `backend/config.py`)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `rust_worker_path` | `str` | `"ingestion-worker/target/release/embedinator-worker"` | Path to Rust binary |
| `embed_max_workers` | `int` | `4` | ThreadPoolExecutor worker count |
| `qdrant_upsert_batch_size` | `int` | `50` | Points per Qdrant upsert call |

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** All test execution uses the external runner script.

```bash
# Launch tests (returns immediately, runs in background):
zsh scripts/run-tests-external.sh -n <run-name> [--no-cov] [--fail-fast] <test-target>

# Poll status (~5 tokens):
cat Docs/Tests/<run-name>.status       # RUNNING | PASSED | FAILED | ERROR | NO_TESTS

# Read summary when done (~20 lines, ~100 tokens):
cat Docs/Tests/<run-name>.summary

# Debug specific failures (NEVER read full .log):
grep "FAILED" Docs/Tests/<run-name>.log
grep -A5 "test_specific_name" Docs/Tests/<run-name>.log
```

### Per-Wave Test Commands

```bash
# Wave 2 unit tests:
zsh scripts/run-tests-external.sh -n spec06-w2 --no-cov tests/unit/test_chunker.py tests/unit/test_embedder.py tests/unit/test_ingestion_pipeline.py

# Wave 3 unit tests:
zsh scripts/run-tests-external.sh -n spec06-w3 --no-cov tests/unit/test_incremental.py tests/unit/test_ingestion_api.py

# Wave 4 integration tests:
zsh scripts/run-tests-external.sh -n spec06-integration tests/integration/test_ingestion_pipeline.py

# Wave 5 full regression (all specs):
zsh scripts/run-tests-external.sh -n spec06-full tests/
```

### Rust Worker Tests

```bash
# Run Rust tests directly (not pytest):
cd ingestion-worker && cargo test

# Build release binary:
cargo build --release --manifest-path ingestion-worker/Cargo.toml

# Smoke test with a sample file:
echo "Hello world" > /tmp/test.txt
./ingestion-worker/target/release/embedinator-worker --file /tmp/test.txt --type text
```

---

## Done Criteria

### Schema & Foundation (Wave 1)
- [ ] `documents` table migrated to production schema (single collection FK, file_hash, chunk_count, status enum)
- [ ] `ingestion_jobs` table created with all columns and FK
- [ ] `parent_chunks` table created with flat-column schema + indexes
- [ ] `ParentStore.get_by_ids()` updated for new schema (spec-03 read path preserved)
- [ ] 3 new config fields added to `backend/config.py`
- [ ] Test scaffolding files created

### Python Pipeline (Wave 2)
- [ ] `IngestionPipeline.ingest_file()` orchestrates full flow: spawn worker, read NDJSON, chunk, embed, validate, upsert, track status
- [ ] Job status transitions: `started` -> `streaming` -> `embedding` -> `completed` (or `failed`/`paused`)
- [ ] Upsert buffer (1,000 point capacity) with pause/resume on Qdrant outage
- [ ] Ollama outage triggers job pause; auto-resume on circuit breaker close
- [ ] Worker crash handling: process remaining chunks, log error, set status=`failed`
- [ ] `ChunkSplitter`: parent chunks 2000-4000 chars, child chunks ~500 chars
- [ ] Breadcrumb prefix: `[heading > path]` prepended to each child chunk
- [ ] Deterministic UUID5 point IDs: `uuid5(namespace, source_file:page:chunk_index)`
- [ ] `BatchEmbedder`: ThreadPoolExecutor with configurable workers and batch size
- [ ] `validate_embedding()`: 4 checks (dimensions, NaN, zero, magnitude), returns `(bool, str)`
- [ ] Failed embeddings logged with reason and skipped (not fatal)

### Rust Worker (Wave 2)
- [ ] `embedinator-worker` binary builds with `cargo build --release`
- [ ] CLI: `--file <path>` (required) + `--type <pdf|markdown|text|code>` (optional, auto-detect)
- [ ] PDF parsing via pdf-extract, page-by-page
- [ ] Markdown parsing via pulldown-cmark, heading-boundary splitting
- [ ] Plain text: paragraph/sentence boundary detection
- [ ] Code files: 9 extensions supported, `doc_type: "code"` annotation
- [ ] HeadingTracker maintains heading hierarchy for breadcrumbs
- [ ] NDJSON output: one JSON line per chunk with all required fields
- [ ] Partial output on parse failure: stream what was parsed, exit non-zero
- [ ] `cargo test` passes

### Incremental & API (Wave 3)
- [ ] SHA256 hash computed for every uploaded file
- [ ] Duplicate detection: same hash + same collection + status=completed -> HTTP 409
- [ ] Failed document re-ingestion allowed (same hash + status=failed)
- [ ] Changed file: delete old Qdrant points, full re-ingest
- [ ] `POST /api/collections/{id}/ingest` endpoint functional
- [ ] 12 file types accepted; unsupported -> HTTP 400 `INVALID_FILE`; >100MB -> HTTP 413
- [ ] Existing `list_documents`, `get_document`, `delete_document` routes preserved
- [ ] `SUPPORTED_FORMATS` extended from 3 to 12

### Integration & Regression (Wave 4-5)
- [ ] Full pipeline integration test: upload PDF, verify chunks in Qdrant + parents in SQLite
- [ ] Schema migration test: existing data preserved, new tables functional
- [ ] Fault tolerance test: simulated Qdrant/Ollama outage triggers pause, not abort
- [ ] Duplicate detection test: same file rejected, modified file re-ingested
- [ ] 200-page PDF ingests in under 20 seconds (SC-001)
- [ ] `ruff check .` passes on all modified/created files
- [ ] Full regression: 0 regressions from spec-05 baseline
- [ ] `cargo test` passes for Rust worker
