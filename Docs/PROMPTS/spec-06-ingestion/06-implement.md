# Spec 06: Ingestion Pipeline -- Implementation Context

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

### Agent Team Composition

| Agent | Role | subagent_type | Model | Wave | Tasks |
|-------|------|---------------|-------|------|-------|
| A1 | Foundation: Setup + Schema Migration (US6) | backend-architect | Sonnet 4.6 | 1 | T001-T011 |
| A2 | Pipeline Orchestrator (US1 core) | python-expert | **Opus 4.6** | 2 | T023, T024, T025, T028, T029, T030 |
| A3 | Chunker (US1 chunking) | python-expert | Sonnet 4.6 | 2 | T021, T026 |
| A4 | Embedder + Validation (US1 embedding) | performance-engineer | Sonnet 4.6 | 2 | T022, T027 |
| A5 | Rust Worker (US4) | system-architect | Sonnet 4.6 | 2 | T012-T020 |
| A6 | Incremental/Dedup (US2) | python-expert | Sonnet 4.6 | 3 | T031-T036 |
| A7 | API + File Validation (US5) | security-engineer | Sonnet 4.6 | 3 | T044-T046 |
| A8 | Fault Tolerance + Integration (US3) | quality-engineer | Sonnet 4.6 | 4 | T037-T043 |
| Lead | Polish + Regression | (orchestrator) | -- | 5 | T047-T052 |

**Rationale for Opus on A2**: Pipeline orchestrator is the most complex component -- subprocess management, status state machine, upsert buffering, pause/resume, multiple failure domains, DI wiring.

### Wave Execution Order

```
Wave 1 (A1):                Foundation + Schema Migration   -> Checkpoint Gate
Wave 2 (A2+A3+A4+A5):      Pipeline + Chunker + Embedder + Rust Worker (parallel) -> Checkpoint Gate
Wave 3 (A6+A7):             Incremental Dedup + API Validation (parallel) -> Checkpoint Gate
Wave 4 (A8):                Fault Tolerance + Integration Tests -> Checkpoint Gate
Wave 5 (Lead):              Polish + Full Regression          -> Done
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

Wave 1 -- Foundation + Schema Migration:
- T001-T011: Package setup, config fields, schema migration, parent_store update, test scaffolding (assign to A1)

Wave 2 -- Pipeline + Chunker + Embedder + Rust Worker (parallel, after Wave 1 completes):
- T023, T024, T025, T028, T029, T030: IngestionPipeline, ingest endpoint, SUPPORTED_FORMATS, pipeline tests (assign to A2, depends on Wave 1)
- T021, T026: ChunkSplitter + chunker tests (assign to A3, depends on Wave 1)
- T022, T027: BatchEmbedder + embedder tests (assign to A4, depends on Wave 1)
- T012-T020: Rust worker types, parsers, CLI, tests, build (assign to A5, depends on Wave 1)

Wave 3 -- Incremental Dedup + API Validation (parallel, after Wave 2 completes):
- T031-T036: IncrementalChecker + dedup wiring + tests (assign to A6, depends on Wave 2)
- T044-T046: MIME validation + file validation tests + edge cases (assign to A7, depends on Wave 2)

Wave 4 -- Fault Tolerance + Integration (after Wave 3 completes):
- T037-T043: Skip-and-continue, UpsertBuffer, pause/resume, Ollama outage, worker crash, tests (assign to A8, depends on Wave 3)

Wave 5 -- Polish (after Wave 4 completes):
- T047-T052: Full regression, ruff, cargo clippy, done criteria validation (lead)
```

### Step 3: Spawn Teammates per Wave

**Wave 1 -- Spawn A1 (Foundation + Schema Migration):**
```
Spawn a teammate named "A1-foundation-schema" with subagent_type "backend-architect" and model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A1-foundation-schema.md FIRST, then execute all assigned tasks."
```

Wait for A1 to complete. Run checkpoint gate (see below). Then proceed to Wave 2.

**Wave 2 -- Spawn A2 + A3 + A4 + A5 (parallel, each in own tmux pane):**
```
Spawn four teammates in parallel:

1. Teammate "A2-pipeline-orchestrator" with subagent_type "python-expert" and model Opus:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A2-pipeline-orchestrator.md FIRST, then execute all assigned tasks."

2. Teammate "A3-chunker" with subagent_type "python-expert" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A3-chunker.md FIRST, then execute all assigned tasks."

3. Teammate "A4-embedder" with subagent_type "performance-engineer" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A4-embedder.md FIRST, then execute all assigned tasks."

4. Teammate "A5-rust-worker" with subagent_type "system-architect" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A5-rust-worker.md FIRST, then execute all assigned tasks."
```

Wait for all four to complete. Run checkpoint gate. Then proceed to Wave 3.

**Wave 3 -- Spawn A6 + A7 (parallel):**
```
Spawn two teammates in parallel:

1. Teammate "A6-incremental-dedup" with subagent_type "python-expert" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A6-incremental-dedup.md FIRST, then execute all assigned tasks."

2. Teammate "A7-api-validation" with subagent_type "security-engineer" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A7-api-validation.md FIRST, then execute all assigned tasks."
```

Wait for both A6 and A7. Run checkpoint gate. Then proceed to Wave 4.

**Wave 4 -- Spawn A8 (Fault Tolerance + Integration):**
```
Spawn a teammate named "A8-fault-tolerance" with subagent_type "quality-engineer" and model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-06-ingestion/agents/A8-fault-tolerance.md FIRST, then execute all assigned tasks."
```

Wait for A8. Run checkpoint gate. Then proceed to Wave 5.

**Wave 5 -- Lead (Polish + Regression):**

The lead runs T047-T052 directly. No teammate spawned.

### Step 4: Checkpoint Gates (Lead Runs After Each Wave)

The lead runs these verification commands after each wave completes. If a gate fails, message the relevant teammate to fix it before proceeding.

```bash
# Wave 1: Foundation + Schema Migration ready
python -c "from backend.config import settings; print('rust_worker_path:', settings.rust_worker_path, 'embed_max_workers:', settings.embed_max_workers, 'qdrant_upsert_batch_size:', settings.qdrant_upsert_batch_size)"
python -c "import aiosqlite; import asyncio; asyncio.run((lambda: None)())"  # aiosqlite importable
python -c "import tests.unit.test_schema_migration; print('schema migration tests OK')"
python -c "import tests.unit.test_chunker; import tests.unit.test_embedder; import tests.unit.test_incremental; import tests.unit.test_ingestion_pipeline; import tests.unit.test_ingestion_api; print('test scaffolding OK')"
python -c "import tests.integration.test_ingestion_pipeline; print('integration test scaffold OK')"
ruff check backend/config.py backend/storage/sqlite_db.py backend/storage/parent_store.py

# Wave 2: Pipeline + Chunker + Embedder importable, Rust worker builds
python -c "from backend.ingestion.pipeline import IngestionPipeline; print('Pipeline OK')"
python -c "from backend.ingestion.chunker import ChunkSplitter; print('Chunker OK')"
python -c "from backend.ingestion.embedder import BatchEmbedder, validate_embedding; print('Embedder OK')"
ruff check backend/ingestion/ backend/api/documents.py
cargo build --release --manifest-path ingestion-worker/Cargo.toml
echo "test" > /tmp/_embedinator_test.txt && ./ingestion-worker/target/release/embedinator-worker --file /tmp/_embedinator_test.txt --type text && rm /tmp/_embedinator_test.txt

# Wave 3: Incremental + API validation
python -c "from backend.ingestion.incremental import IncrementalChecker; print('IncrementalChecker OK')"
ruff check backend/ingestion/incremental.py backend/api/documents.py

# Wave 4: Fault tolerance + integration
ruff check backend/ingestion/pipeline.py backend/ingestion/embedder.py
zsh scripts/run-tests-external.sh -n spec06-wave4 tests/unit/test_ingestion_pipeline.py tests/unit/test_embedder.py
cat Docs/Tests/spec06-wave4.status
cat Docs/Tests/spec06-wave4.summary

# Wave 5: Full test suite (lead runs directly)
zsh scripts/run-tests-external.sh -n spec06-units tests/unit/
zsh scripts/run-tests-external.sh -n spec06-integ tests/integration/
zsh scripts/run-tests-external.sh -n spec06-full tests/
cd ingestion-worker && cargo test && cargo clippy -- -D warnings && cd ..
cat Docs/Tests/spec06-full.status
cat Docs/Tests/spec06-full.summary
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
3. **Parallel waves share files safely** -- Wave 2 agents each create different files in `backend/ingestion/`. A5 works entirely in `ingestion-worker/`. A2 is the only agent modifying `documents.py` in Wave 2. No merge conflicts if agents stay in their assigned regions.
4. **Teammate prompts are minimal** -- just point to the instruction file. All context lives in the instruction files and CLAUDE.md.
5. **Model selection** -- A2 (pipeline orchestrator, complex subprocess + state machine + DI wiring) uses Opus. All others use Sonnet for cost efficiency.
6. **Monitor via tmux** -- click into any teammate's pane to see their progress.
7. **If a teammate fails** -- shut it down and spawn a replacement with the same instruction file. The task list tracks which tasks are done.
8. **Never inline spec content in spawn prompts** -- agents MUST read their instruction file FIRST. All authoritative context lives in the instruction files and spec artifacts.
9. **Wave 2 file ownership** -- A2 owns `pipeline.py` and `documents.py`. A3 owns `chunker.py`. A4 owns `embedder.py`. A5 owns all `ingestion-worker/` files. No overlap.
10. **Rust tests use cargo** -- A5 runs `cargo test`, not pytest. All Python tests use the external runner.

---

## Implementation Scope

### Files to Create

| File | Agent | Purpose |
|------|-------|---------|
| `backend/ingestion/__init__.py` | A1 | Package init |
| `backend/ingestion/pipeline.py` | A2 | IngestionPipeline orchestrator |
| `backend/ingestion/chunker.py` | A3 | ChunkSplitter: parent/child + breadcrumbs + UUID5 |
| `backend/ingestion/embedder.py` | A4 | BatchEmbedder: parallel embedding + validation |
| `backend/ingestion/incremental.py` | A6 | IncrementalChecker: SHA256 dedup + change detection |
| `ingestion-worker/Cargo.toml` | A5 | Rust project config |
| `ingestion-worker/src/main.rs` | A5 | CLI entry, type dispatch, NDJSON serialization |
| `ingestion-worker/src/types.rs` | A5 | Chunk struct, DocType enum (Prose, Code) |
| `ingestion-worker/src/heading_tracker.rs` | A5 | HeadingTracker: heading hierarchy |
| `ingestion-worker/src/text.rs` | A5 | Plain text paragraph/sentence chunking |
| `ingestion-worker/src/code.rs` | A5 | Code files (9 extensions), doc_type Code |
| `ingestion-worker/src/markdown.rs` | A5 | Markdown parsing (pulldown-cmark) |
| `ingestion-worker/src/pdf.rs` | A5 | PDF extraction (pdf-extract) |
| `tests/unit/test_chunker.py` | A1 (scaffold), A3 (tests) | ChunkSplitter unit tests |
| `tests/unit/test_embedder.py` | A1 (scaffold), A4 (tests) | BatchEmbedder unit tests |
| `tests/unit/test_incremental.py` | A1 (scaffold), A6 (tests) | IncrementalChecker unit tests |
| `tests/unit/test_ingestion_pipeline.py` | A1 (scaffold), A2+A8 (tests) | Pipeline unit tests |
| `tests/unit/test_ingestion_api.py` | A1 (scaffold), A2+A7 (tests) | API endpoint tests |
| `tests/unit/test_schema_migration.py` | A1 | Schema migration unit tests |
| `tests/integration/test_ingestion_pipeline.py` | A1 (scaffold), A2+A6+A8 (tests) | End-to-end integration tests |

### Files to Modify

| File | Agent | What Changes |
|------|-------|--------------|
| `backend/config.py` | A1 | Add 3 new settings: `rust_worker_path`, `embed_max_workers`, `qdrant_upsert_batch_size` |
| `backend/storage/sqlite_db.py` | A1 | Migrate documents table, add ingestion_jobs + parent_chunks tables |
| `backend/storage/parent_store.py` | A1 | Update get_by_ids() SQL: `parent_id`->`id`, `collection`->`collection_id` |
| `backend/api/documents.py` | A2, A6, A7 | A2: new ingest endpoint + extend SUPPORTED_FORMATS. A6: wire 409 duplicate. A7: MIME check |
| `backend/ingestion/pipeline.py` | A6, A8 | A6: wire IncrementalChecker. A8: UpsertBuffer, pause/resume, crash handling |
| `backend/ingestion/embedder.py` | A8 | Add skip-and-continue on validation failure |

### Files That Exist and Are NOT Modified (Verified via Serena)

- `backend/errors.py` -- `IngestionError` (line 27-28) and `CircuitOpenError` (line 43-44) already exist. DO NOT MODIFY.
- `backend/agent/schemas.py` -- `ParentChunk` model (line 38-44) with `parent_id`, `collection` fields. DO NOT MODIFY -- the `ParentStore.get_by_ids()` update handles the column mapping without changing the Pydantic model.
- `backend/agent/conversation_graph.py` -- Graph definition. DO NOT TOUCH.
- `backend/agent/research_graph.py` -- ResearchGraph. DO NOT TOUCH.
- `backend/agent/nodes.py` -- Conversation nodes. DO NOT TOUCH.
- `backend/agent/confidence.py` -- 5-signal confidence formula. DO NOT TOUCH.
- `backend/retrieval/searcher.py` -- HybridSearcher. DO NOT TOUCH.
- `backend/retrieval/reranker.py` -- Reranker. DO NOT TOUCH.
- `backend/main.py` -- Lifespan function. NOT modified in this spec (ingestion pipeline is launched as a background task from the API endpoint, not wired into lifespan).

### FR-to-Task-to-Agent Mapping

| FR | Description | Tasks | Agent(s) |
|----|-------------|-------|----------|
| FR-001 | Accept multipart upload, 12 file types | T024, T025 | A2 |
| FR-002 | Reject unsupported types + oversized files | T024, T044, T045 | A2, A7 |
| FR-003 | SHA256 hash dedup (completed status) | T031, T034 | A6 |
| FR-004 | Allow re-ingestion of failed documents | T031, T034 | A6 |
| FR-005 | Delete old vectors on changed-hash re-upload | T033, T034 | A6 |
| FR-006 | Native binary worker, NDJSON streaming | T012-T018 | A5 |
| FR-007 | Parent/child chunking + breadcrumbs | T021 | A3 |
| FR-008 | Deterministic UUID5 point IDs | T021 | A3 |
| FR-009 | Parallel embedding (configurable workers) | T022 | A4 |
| FR-010 | Validate embeddings, skip failures | T022, T037 | A4, A8 |
| FR-011 | Batch upsert to Qdrant | T023 | A2 |
| FR-012 | Upsert buffer + pause/resume on outage | T038, T039 | A8 |
| FR-013 | Pause on embedding service outage | T040 | A8 |
| FR-014 | Job status lifecycle tracking | T023 | A2 |
| FR-015 | Update document status + chunk count | T023 | A2 |
| FR-016 | Worker crash: process received chunks | T041 | A8 |
| FR-017 | Migrate documents table (Phase 1 -> 2) | T006 | A1 |
| FR-018 | Create ingestion_jobs + parent_chunks | T007, T008 | A1 |
| FR-019 | Preserve parent chunk read path | T009 | A1 |
| FR-020 | Parallel ingestion, resource limits | T022 | A4 |

---

## Codebase Verification (Verified via Serena MCP)

These facts were verified against the live codebase. Agents MUST respect them.

1. **Settings class** at `config.py:5-67`: ALREADY has `upload_dir` (line 30), `max_upload_size_mb: int = 100` (line 31), `parent_chunk_size: int = 3000` (line 32), `child_chunk_size: int = 500` (line 33), `embed_batch_size: int = 16` (line 34). These 5 fields exist -- DO NOT re-add them. Only 3 fields need to be ADDED: `rust_worker_path`, `embed_max_workers`, `qdrant_upsert_batch_size`.
2. **Phase 1 `documents` table** at `sqlite_db.py:39-47`: columns `id TEXT PRIMARY KEY`, `name TEXT NOT NULL`, `collection_ids JSON NOT NULL`, `file_path TEXT NOT NULL`, `status TEXT DEFAULT 'uploaded'`, `upload_date DATETIME`, `file_size_bytes INT`, `parse_error TEXT`. MISSING for spec-06: `file_hash`, `chunk_count`, `ingested_at`, single `collection_id`.
3. **`_create_tables()`** at `sqlite_db.py:30-90`: Creates 6 tables (collections, documents, queries, answers, traces, providers). NO `ingestion_jobs` or `parent_chunks` tables.
4. **ParentStore.get_by_ids()** at `parent_store.py:26-68`: SQL selects `parent_id, text, source_file, page, breadcrumb, collection FROM parent_chunks WHERE parent_id IN (?)`. Constructs `ParentChunk(parent_id=row["parent_id"], ..., collection=row["collection"])`. After migration, column names change: `parent_id`->`id`, `collection`->`collection_id`. The SQL and row access must be updated.
5. **ParentChunk model** at `schemas.py:38-44`: `parent_id: str`, `text: str`, `source_file: str`, `page: int | None = None`, `breadcrumb: str`, `collection: str`. This Pydantic model is used throughout the research graph. DO NOT change field names -- instead, use SQL column aliases in `get_by_ids()`: `SELECT id AS parent_id, ..., collection_id AS collection`.
6. **SUPPORTED_FORMATS** at `documents.py:13-14`: `{".pdf", ".md", ".txt"}` -- needs extension to 12 types.
7. **upload_document** at `documents.py:16-88`: `POST /api/documents` endpoint. Phase 1 pattern with `collection_ids` as JSON form field. The NEW ingest endpoint is `POST /api/collections/{collection_id}/ingest` per the API contract -- this is a SEPARATE route, not a modification of the existing one.
8. **_process_document** at `documents.py:91-112`: Phase 1 background task importing `backend.storage.document_parser`, `backend.storage.chunker`, `backend.storage.indexing`. These modules will be superseded by `backend.ingestion.*` but the old code is NOT removed in this spec.
9. **create_document** at `sqlite_db.py:157-174`: Inserts with columns `id, name, collection_ids, file_path, status, upload_date, file_size_bytes`. After migration, this method MUST be updated for the new schema columns.
10. **update_document_status** at `sqlite_db.py:176-181`: `UPDATE documents SET status = ?, parse_error = ? WHERE id = ?`. After migration, the `parse_error` column is removed (error tracking moves to `ingestion_jobs.error_msg`). This method needs updating.
11. **list_documents** at `sqlite_db.py:183-203`: Selects `id, name, collection_ids, status, upload_date`. After migration, column names change. Must be updated.
12. **delete_document** at `sqlite_db.py:222-227`: Soft-delete via status='deleted'. No column name changes needed, but status value mapping applies.
13. **QdrantClientWrapper** at `qdrant_client.py:21-31`: Class name is `QdrantClientWrapper` (NOT `QdrantStorage`). Has full circuit breaker with `_check_circuit`, `_record_success`, `_record_failure`, half-open + cooldown. Has `upsert(collection_name: str, points: list[dict])` method.
14. **lifespan** at `main.py:42-124`: Initializes SQLiteDB, QdrantClientWrapper, ProviderRegistry, AsyncSqliteSaver, HybridSearcher, Reranker, ParentStore, research_tools, conversation_graph. Does NOT initialize ingestion components. The ingestion pipeline is instantiated per-request in the API endpoint, not in lifespan.
15. **IngestionError** at `errors.py:27-28`: Already exists. Use for pipeline failures.
16. **CircuitOpenError** at `errors.py:43-44`: Already exists. Used by QdrantClientWrapper and inference CB.
17. **backend/ingestion/** directory: DOES NOT EXIST. A1 creates it.
18. **ingestion-worker/** directory: DOES NOT EXIST. A5 creates it.

---

## Code Specifications

### Critical Patterns (ALL Agents MUST Follow)

```python
# Import settings at function/method level for testability
from backend.config import settings

# structlog pattern
import structlog
logger = structlog.get_logger(__name__)

# Use QdrantClientWrapper (NEVER QdrantStorage)
from backend.storage.qdrant_client import QdrantClientWrapper

# Constructor DI pattern for ingestion modules
class IngestionPipeline:
    def __init__(self, db: SQLiteDB, qdrant: QdrantClientWrapper):
        self.db = db
        self.qdrant = qdrant

# Return type for validate_embedding
def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]:
    """Returns (is_valid, reason). reason is empty string on success."""

# DocType enum in Rust has ONLY two variants
# "prose" for PDF/MD/text, "code" for code files
# NO "table" or "mixed" variants
```

> **IMPORTANT**: The class name is `QdrantClientWrapper`, NOT `QdrantStorage`. Any reference
> to `QdrantStorage` is a bug from an older draft. The codebase has always used `QdrantClientWrapper`.

---

### backend/config.py (MODIFY -- A1)

Add 3 NEW settings fields to the `Settings` class. The other 4 ingestion-related fields already exist and MUST NOT be re-added.

```python
# --- Add these 3 fields to the Ingestion section (after embed_batch_size, around line 34) ---

    # Ingestion (add below existing fields)
    rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
    embed_max_workers: int = 4
    qdrant_upsert_batch_size: int = 50
```

**Already existing** (DO NOT re-add):
- `upload_dir: str = "data/uploads"` (line 30)
- `max_upload_size_mb: int = 100` (line 31)
- `parent_chunk_size: int = 3000` (line 32)
- `child_chunk_size: int = 500` (line 33)
- `embed_batch_size: int = 16` (line 34)

---

### backend/storage/sqlite_db.py (MODIFY -- A1)

#### Schema Migration: documents table (FR-017)

Use the create-copy-drop-rename pattern (R3 from research.md) inside `_create_tables()`. The migration must be idempotent -- it runs only if the old schema is detected (check for `collection_ids` column in `documents`).

```python
async def _create_tables(self):
    # Check if migration is needed (old schema has collection_ids JSON column)
    try:
        cursor = await self.db.execute("PRAGMA table_info(documents)")
        columns = await cursor.fetchall()
        col_names = [col[1] for col in columns] if columns else []
        needs_migration = "collection_ids" in col_names
    except Exception:
        needs_migration = False

    if needs_migration:
        await self._migrate_documents_table()

    # Create tables (idempotent with IF NOT EXISTS)
    await self.db.executescript("""
        CREATE TABLE IF NOT EXISTS collections (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            chunk_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ingested_at DATETIME,
            FOREIGN KEY (collection_id) REFERENCES collections(id)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_collection_hash
            ON documents(collection_id, file_hash)
            WHERE file_hash != '';
        CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

        -- ... (queries, answers, traces, providers tables unchanged) ...

        CREATE TABLE IF NOT EXISTS ingestion_jobs (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'started',
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            error_msg TEXT,
            chunks_processed INTEGER DEFAULT 0,
            chunks_skipped INTEGER DEFAULT 0,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS parent_chunks (
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            document_id TEXT NOT NULL,
            text TEXT NOT NULL,
            source_file TEXT NOT NULL,
            page INTEGER,
            breadcrumb TEXT,
            created_at DATETIME NOT NULL,
            FOREIGN KEY (collection_id) REFERENCES collections(id),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
        CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);
    """)
    await self.db.commit()
```

#### Migration method (R3 pattern)

```python
async def _migrate_documents_table(self):
    """Migrate Phase 1 documents table to Phase 2 schema (R3: create-copy-drop-rename)."""
    logger.info("documents_table_migration_starting")

    await self.db.executescript("""
        CREATE TABLE IF NOT EXISTS documents_new (
            id TEXT PRIMARY KEY,
            collection_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_hash TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'pending',
            chunk_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            ingested_at DATETIME
        );

        INSERT OR IGNORE INTO documents_new (id, collection_id, filename, file_path, file_hash, status, chunk_count, created_at)
        SELECT
            id,
            COALESCE(
                json_extract(collection_ids, '$[0]'),
                'unknown'
            ),
            name,
            file_path,
            '',
            CASE status
                WHEN 'indexed' THEN 'completed'
                WHEN 'uploaded' THEN 'pending'
                WHEN 'parsing' THEN 'pending'
                WHEN 'indexing' THEN 'pending'
                WHEN 'deleted' THEN 'failed'
                ELSE status
            END,
            0,
            COALESCE(upload_date, CURRENT_TIMESTAMP)
        FROM documents;

        DROP TABLE documents;
        ALTER TABLE documents_new RENAME TO documents;
    """)
    await self.db.commit()
    logger.info("documents_table_migration_complete")
```

#### New CRUD methods for ingestion

A1 must also add these methods to `SQLiteDB`:

```python
async def create_ingestion_job(self, job_id: str, document_id: str) -> dict:
    """Create a new ingestion job record."""

async def update_ingestion_job(self, job_id: str, *, status: str | None = None,
                                error_msg: str | None = None,
                                chunks_processed: int | None = None,
                                chunks_skipped: int | None = None) -> None:
    """Update ingestion job fields."""

async def insert_parent_chunk(self, chunk_id: str, collection_id: str, document_id: str,
                               text: str, source_file: str, page: int | None,
                               breadcrumb: str | None) -> None:
    """Insert a parent chunk record."""

async def delete_parent_chunks_by_document(self, document_id: str) -> int:
    """Delete all parent chunks for a document. Returns count deleted."""

async def find_document_by_hash(self, collection_id: str, file_hash: str) -> dict | None:
    """Find a document in collection by content hash."""
```

Also update existing methods to match new column names:
- `create_document`: use `collection_id`, `filename`, `created_at` columns
- `update_document_status`: remove `parse_error` parameter (errors in ingestion_jobs now)
- `list_documents`: select new columns (`filename`, `collection_id`, `created_at`)

---

### backend/storage/parent_store.py (MODIFY -- A1)

Update the SQL query to use column aliases that match the existing `ParentChunk` model field names. This preserves backward compatibility with the research graph without changing the Pydantic model.

```python
async def get_by_ids(self, parent_ids: list[str]) -> list[ParentChunk]:
    # ...
    cursor = await self.db.db.execute(
        f"SELECT id AS parent_id, text, source_file, page, breadcrumb, collection_id AS collection "
        f"FROM parent_chunks WHERE id IN ({placeholders})",
        parent_ids,
    )
    # ... rest unchanged -- row["parent_id"] and row["collection"] still work
```

> **CRITICAL**: Use `id AS parent_id` and `collection_id AS collection` aliases. The ParentChunk
> Pydantic model in `schemas.py` uses `parent_id` and `collection` field names. Do NOT change the
> model -- change the SQL to alias the new column names to the old field names.

---

### backend/ingestion/chunker.py (CREATE -- A3)

```python
import uuid
from dataclasses import dataclass

import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)

# Deterministic namespace for UUID5 point IDs (FR-008)
EMBEDINATOR_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


@dataclass
class ParentChunkData:
    """Internal representation of a parent chunk before DB storage."""
    chunk_id: str
    text: str
    source_file: str
    page: int | None
    breadcrumb: str | None
    children: list[dict]  # list of {text: str, point_id: str, chunk_index: int}


class ChunkSplitter:
    """Splits raw worker output into parent/child chunks with breadcrumbs and UUID5 IDs."""

    def __init__(self, parent_size: int | None = None, child_size: int | None = None):
        self.parent_size = parent_size or settings.parent_chunk_size
        self.child_size = child_size or settings.child_chunk_size

    def split_into_parents(self, raw_chunks: list[dict], source_file: str) -> list[ParentChunkData]:
        """Accumulate raw worker chunks into parent chunks (2000-4000 chars).

        Each raw_chunk has: text, page, section, heading_path, doc_type, chunk_index.
        """

    def split_parent_into_children(self, parent_text: str, target_size: int | None = None) -> list[str]:
        """Split a parent chunk into child chunks (~500 chars) on sentence boundaries."""

    @staticmethod
    def prepend_breadcrumb(text: str, heading_path: list[str]) -> str:
        """Prepend breadcrumb prefix: '[A > B > C] text'"""
        if not heading_path:
            return text
        prefix = " > ".join(heading_path)
        return f"[{prefix}] {text}"

    @staticmethod
    def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
        """Deterministic UUID5 for idempotent upserts (FR-008)."""
        key = f"{source_file}:{page}:{chunk_index}"
        return str(uuid.uuid5(EMBEDINATOR_NAMESPACE, key))
```

---

### backend/ingestion/embedder.py (CREATE -- A4)

```python
import math
from concurrent.futures import ThreadPoolExecutor

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger(__name__)


def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]:
    """Validate an embedding vector. Returns (is_valid, reason).

    Checks (per data-model.md validation rules):
    1. Correct dimension count
    2. No NaN values
    3. Non-zero vector
    4. Magnitude above threshold (1e-6)
    """
    if len(vector) != expected_dim:
        return False, f"wrong dimensions: got {len(vector)}, expected {expected_dim}"
    if any(math.isnan(v) for v in vector):
        return False, "contains NaN values"
    if all(v == 0.0 for v in vector):
        return False, "zero vector"
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude < 1e-6:
        return False, f"magnitude below threshold: {magnitude}"
    return True, ""


class BatchEmbedder:
    """Parallel batch embedding via Ollama API.

    Uses ThreadPoolExecutor with configurable max_workers (settings.embed_max_workers)
    and batch_size (settings.embed_batch_size) per Ollama call.
    """

    def __init__(self, model: str | None = None, max_workers: int | None = None,
                 batch_size: int | None = None):
        self.model = model or settings.default_embed_model
        self.max_workers = max_workers or settings.embed_max_workers
        self.batch_size = batch_size or settings.embed_batch_size
        self.base_url = settings.ollama_base_url

    async def embed_chunks(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of texts in parallel batches.

        Returns list of embedding vectors (same order as input).
        Delegates to ThreadPoolExecutor for parallel Ollama calls.
        """

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Synchronous: embed a single batch via Ollama /api/embed endpoint.

        Called from ThreadPoolExecutor threads.
        """
```

---

### backend/ingestion/pipeline.py (CREATE -- A2)

```python
import asyncio
import json
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from backend.config import settings
from backend.ingestion.chunker import ChunkSplitter
from backend.ingestion.embedder import BatchEmbedder, validate_embedding
from backend.storage.qdrant_client import QdrantClientWrapper
from backend.storage.sqlite_db import SQLiteDB

logger = structlog.get_logger(__name__)


@dataclass
class IngestionResult:
    """Result of a completed ingestion job."""
    document_id: str
    job_id: str
    status: str
    chunks_processed: int = 0
    chunks_skipped: int = 0
    error: str | None = None


class IngestionPipeline:
    """Orchestrates the full ingestion flow: parse -> chunk -> embed -> store.

    Accepts db and qdrant via constructor DI.
    """

    def __init__(self, db: SQLiteDB, qdrant: QdrantClientWrapper):
        self.db = db
        self.qdrant = qdrant
        self.chunker = ChunkSplitter()
        self.embedder = BatchEmbedder()

    async def ingest_file(
        self, file_path: str, filename: str, collection_id: str,
        document_id: str, job_id: str,
    ) -> IngestionResult:
        """Full ingestion pipeline for a single document.

        Steps:
        1. Update job status -> started
        2. Spawn Rust worker subprocess
        3. Read NDJSON stdout line-by-line, update status -> streaming
        4. Pass raw chunks to ChunkSplitter (parent/child + breadcrumbs + UUID5)
        5. Embed children via BatchEmbedder, update status -> embedding
        6. Batch upsert to Qdrant (settings.qdrant_upsert_batch_size per call)
        7. Store parents in SQLite parent_chunks table
        8. Update document chunk_count and status -> completed
        9. Update job status -> completed with chunks_processed count
        """

    async def _spawn_worker(self, file_path: str) -> subprocess.Popen:
        """Spawn Rust worker subprocess per worker-ndjson.md contract."""
        proc = subprocess.Popen(
            [settings.rust_worker_path, "--file", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        return proc

    async def _read_worker_output(self, proc: subprocess.Popen) -> list[dict]:
        """Read NDJSON lines from worker stdout. Handles partial output (R4)."""
        raw_chunks = []
        for line in proc.stdout:
            line = line.strip()
            if line:
                try:
                    chunk = json.loads(line)
                    raw_chunks.append(chunk)
                except json.JSONDecodeError:
                    logger.warning("worker_invalid_json_line", line=line[:100])
        return raw_chunks

    async def _batch_upsert(
        self, collection_id: str, points: list[dict],
    ) -> int:
        """Upsert points in batches of settings.qdrant_upsert_batch_size."""
        batch_size = settings.qdrant_upsert_batch_size
        upserted = 0
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            await self.qdrant.upsert(collection_id, batch)
            upserted += len(batch)
        return upserted
```

> **NOTE**: A2 must also handle the subprocess lifecycle -- check `proc.returncode` after
> `proc.wait()`, read stderr, and implement the partial output guarantee per R4 in research.md.
> If worker exits non-zero, process all received chunks, then set status=failed.

---

### backend/ingestion/incremental.py (CREATE -- A6)

```python
import hashlib

import structlog

from backend.storage.sqlite_db import SQLiteDB

logger = structlog.get_logger(__name__)


class IncrementalChecker:
    """SHA256-based duplicate detection and change detection for re-ingestion."""

    def __init__(self, db: SQLiteDB):
        self.db = db

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """Compute SHA256 hex digest of file content."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(8192), b""):
                sha256.update(block)
        return sha256.hexdigest()

    async def check_duplicate(self, collection_id: str, file_hash: str) -> tuple[bool, str | None]:
        """Check if a document with this hash already exists (completed) in the collection.

        Returns (is_duplicate, existing_document_id).
        A document with status 'failed' is NOT a duplicate (allows re-ingestion per FR-004).
        """

    async def check_change(self, collection_id: str, filename: str, new_hash: str) -> tuple[bool, str | None]:
        """Check if a document with the same filename but different hash exists.

        Returns (is_changed, old_document_id).
        If changed, the caller should delete old vectors and re-ingest (FR-005).
        """
```

---

### backend/api/documents.py (MODIFY -- A2 for endpoint + SUPPORTED_FORMATS, A6 for dedup wiring, A7 for MIME check)

#### SUPPORTED_FORMATS extension (A2)

```python
# Replace line 13-14
SUPPORTED_FORMATS = {
    ".pdf", ".md", ".txt",
    ".py", ".js", ".ts", ".rs", ".go", ".java",
    ".c", ".cpp", ".h",
}
```

#### New ingest endpoint (A2)

```python
@router.post("/api/collections/{collection_id}/ingest", status_code=202)
async def ingest_document(
    request: Request,
    collection_id: str,
    file: UploadFile = File(...),
):
    """Ingest a document into a collection. Processing is async.

    Per ingest-api.md contract:
    1. Validate file extension
    2. Validate file size <= 100MB
    3. Validate collection exists
    4. (A7 adds) Validate MIME type for PDF
    5. (A6 adds) Compute hash, check duplicate
    6. Save file
    7. Create document + job records
    8. Launch pipeline as background task
    9. Return 202 with document_id + job_id
    """
```

> **IMPORTANT**: The existing `upload_document` endpoint (`POST /api/documents`) is PRESERVED
> as-is. The new `ingest_document` endpoint is ADDED alongside it. Do not delete the old endpoint.

#### MIME validation (A7 adds to ingest endpoint)

```python
# Inside ingest_document, after extension check:
if suffix == ".pdf":
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail={
            "error": "INVALID_FILE",
            "message": f"PDF file has invalid content type: {file.content_type}",
        })
```

#### Duplicate detection (A6 adds to ingest endpoint)

```python
# Inside ingest_document, after file save:
from backend.ingestion.incremental import IncrementalChecker
checker = IncrementalChecker(db)
file_hash = checker.compute_file_hash(str(file_path))

is_dup, existing_id = await checker.check_duplicate(collection_id, file_hash)
if is_dup:
    file_path.unlink(missing_ok=True)
    raise HTTPException(status_code=409, detail={
        "error": "DUPLICATE_DOCUMENT",
        "message": f"File with hash {file_hash} already exists in collection {collection_id} with status 'completed'",
    })
```

---

### Rust Worker (ingestion-worker/) -- A5

All Rust files follow the worker-ndjson.md contract. Key specifications:

#### types.rs

```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct Chunk {
    pub text: String,
    pub page: usize,
    pub section: String,
    pub heading_path: Vec<String>,
    pub doc_type: DocType,
    pub chunk_profile: String,
    pub chunk_index: usize,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
#[serde(rename_all = "lowercase")]
pub enum DocType {
    Prose,
    Code,
}
```

> **IMPORTANT**: `DocType` has exactly 2 variants: `Prose` and `Code`. No `Table` or `Mixed`.
> The `#[serde(rename_all = "lowercase")]` ensures JSON serialization produces `"prose"` and `"code"`.

#### heading_tracker.rs

```rust
pub struct HeadingTracker {
    levels: Vec<(usize, String)>,
}

impl HeadingTracker {
    pub fn new() -> Self { ... }
    pub fn push(&mut self, level: usize, text: String) { ... }
    pub fn path(&self) -> Vec<String> { ... }
}
```

`push(level, text)`: Remove all entries at same or deeper level, then push new entry. This maintains the correct hierarchy (e.g., pushing H2 removes the old H2 and any H3).

#### main.rs

```rust
use clap::Parser;

#[derive(Parser)]
struct Args {
    #[arg(long)]
    file: String,
    #[arg(long)]
    r#type: Option<String>,
}

fn detect_type_from_extension(path: &str) -> &str {
    // .pdf -> "pdf"
    // .md -> "markdown"
    // .txt -> "text"
    // .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h -> "code"
}
```

Exit codes: 0=success, 1=file error, 2=parse error. NDJSON to stdout, diagnostics to stderr.

#### Parser modules

- `pdf.rs`: Use `pdf-extract` crate. Page-by-page extraction. Skip image-only pages (warn to stderr). Emit `Chunk` with `doc_type: Prose`.
- `markdown.rs`: Use `pulldown-cmark`. Split at heading boundaries (H1/H2/H3). Use `HeadingTracker` for hierarchy. Emit `Chunk` with `doc_type: Prose`.
- `text.rs`: Split on double newlines (paragraph boundaries). Sentence boundary fallback within paragraphs. Emit `Chunk` with `doc_type: Prose`.
- `code.rs`: Handle 9 extensions (`.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`). Paragraph-boundary chunking. Emit `Chunk` with `doc_type: Code`.

#### Cargo.toml

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

---

## Error Handling

| Location | Error | Recovery |
|----------|-------|----------|
| `IngestionPipeline.ingest_file` | Worker exits non-zero | Process all received chunks, set job status=`failed`, log stderr (R4) |
| `IngestionPipeline.ingest_file` | Worker binary not found | Raise `IngestionError`, set job status=`failed` |
| `BatchEmbedder.embed_chunks` | Single embedding fails validation | Skip chunk, log reason with structlog, increment chunks_skipped (FR-010) |
| `BatchEmbedder._embed_batch` | Ollama unreachable | A8 adds: pause job, retry with backoff (FR-013) |
| `IngestionPipeline._batch_upsert` | Qdrant unreachable | A8 adds: buffer in UpsertBuffer (up to 1000 points), pause job if full (FR-012) |
| `IngestionPipeline._batch_upsert` | UpsertBuffer full | Pause job (NOT abort), resume on recovery (FR-012) |
| `validate_embedding` | Wrong dims/NaN/zero/low magnitude | Return `(False, reason_string)`, caller skips chunk |
| `ingest_document` endpoint | Unsupported file type | HTTP 400 `INVALID_FILE` |
| `ingest_document` endpoint | File too large | HTTP 413 `FILE_TOO_LARGE` |
| `ingest_document` endpoint | Collection not found | HTTP 404 `COLLECTION_NOT_FOUND` |
| `ingest_document` endpoint | Duplicate document | HTTP 409 `DUPLICATE_DOCUMENT` |
| `ingest_document` endpoint | PDF wrong MIME | HTTP 400 `INVALID_FILE` |
| `ingest_document` endpoint | Pipeline crash | HTTP 500 `INGESTION_ERROR` |
| Rust worker | File not found | Exit code 1, stderr message |
| Rust worker | Parse error | Exit code 2, partial output on stdout, error on stderr |
| Schema migration | Old table detected | Run create-copy-drop-rename, idempotent |

---

## Testing Requirements

**NEVER run pytest inside Claude Code.** All test execution uses the external runner.

**Rust tests run via `cargo test`** (not pytest).

### Per-Agent Test Responsibilities

| Agent | Test File(s) | What to Test |
|-------|-------------|--------------|
| A1 | `tests/unit/test_schema_migration.py` | Fresh DB creates 3 tables; migration preserves Phase 1 data; ParentStore.get_by_ids() with new schema; UNIQUE constraint |
| A2 | `tests/unit/test_ingestion_pipeline.py`, `tests/unit/test_ingestion_api.py` | Happy path with mocked worker; status transitions; endpoint 202/400/413/404 responses |
| A3 | `tests/unit/test_chunker.py` | Parent 2000-4000 chars; child ~500 chars; breadcrumb format; UUID5 determinism+uniqueness |
| A4 | `tests/unit/test_embedder.py` | Parallel batching; validate_embedding passes/fails with correct reasons |
| A5 | Inline `#[cfg(test)]` in Rust | NDJSON schema; heading_tracker; type auto-detection; partial output on error |
| A6 | `tests/unit/test_incremental.py` | SHA256 correctness; duplicate detection; failed re-ingestion; change detection; per-collection scoping |
| A7 | `tests/unit/test_ingestion_api.py` | 12 supported types; unsupported rejected; PDF MIME check; zero-content PDF; missing worker |
| A8 | `tests/unit/test_ingestion_pipeline.py`, `tests/integration/test_ingestion_pipeline.py` | Validation skip; UpsertBuffer; buffer-full pause; Ollama outage pause; worker crash; integration: mock Qdrant outage -> pause -> resume |

### Test Runner Commands

```bash
# Schema migration (A1):
zsh scripts/run-tests-external.sh -n spec06-us6 tests/unit/test_schema_migration.py

# Chunker (A3):
zsh scripts/run-tests-external.sh -n spec06-chunker tests/unit/test_chunker.py

# Embedder (A4):
zsh scripts/run-tests-external.sh -n spec06-embedder tests/unit/test_embedder.py

# Pipeline (A2):
zsh scripts/run-tests-external.sh -n spec06-pipeline tests/unit/test_ingestion_pipeline.py tests/unit/test_ingestion_api.py

# Rust worker (A5):
cd ingestion-worker && cargo test

# Incremental (A6):
zsh scripts/run-tests-external.sh -n spec06-dedup tests/unit/test_incremental.py

# API validation (A7):
zsh scripts/run-tests-external.sh -n spec06-api tests/unit/test_ingestion_api.py

# Fault tolerance (A8):
zsh scripts/run-tests-external.sh -n spec06-fault tests/unit/test_ingestion_pipeline.py tests/unit/test_embedder.py

# Full unit suite:
zsh scripts/run-tests-external.sh -n spec06-units tests/unit/

# Integration:
zsh scripts/run-tests-external.sh -n spec06-integ tests/integration/test_ingestion_pipeline.py

# Full regression (all specs):
zsh scripts/run-tests-external.sh -n spec06-full tests/

# Check status:
cat Docs/Tests/<name>.status       # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/<name>.summary      # ~20 lines summary
```

---

## Done Criteria

### User Story 6 -- Schema Migration
- [ ] documents table migrated: `collection_ids` JSON -> `collection_id` TEXT, `name` -> `filename`, `upload_date` -> `created_at`, new columns `file_hash`, `chunk_count`, `ingested_at`
- [ ] Phase 1 data preserved with correct status mapping (`indexed` -> `completed`, `uploaded`/`parsing`/`indexing` -> `pending`)
- [ ] UNIQUE constraint `(collection_id, file_hash)` prevents duplicates
- [ ] `ingestion_jobs` table created with correct schema
- [ ] `parent_chunks` table created with indexes
- [ ] `ParentStore.get_by_ids()` works with new schema (column aliases)
- [ ] Existing document CRUD operations work after migration
- [ ] 3 new config fields added: `rust_worker_path`, `embed_max_workers`, `qdrant_upsert_batch_size`

### User Story 1 -- Core Pipeline
- [ ] `IngestionPipeline.ingest_file()` orchestrates full flow: parse -> chunk -> embed -> store
- [ ] Rust worker spawned as subprocess, NDJSON read line-by-line
- [ ] Job status transitions: started -> streaming -> embedding -> completed
- [ ] `ChunkSplitter` produces parent chunks (2000-4000 chars) and child chunks (~500 chars)
- [ ] Breadcrumb prefix format: `[A > B > C] text`
- [ ] UUID5 deterministic point IDs from `source_file:page:chunk_index`
- [ ] `BatchEmbedder` uses ThreadPoolExecutor with configurable workers/batch size
- [ ] `validate_embedding` returns `tuple[bool, str]` with 4 checks
- [ ] Batch upsert to Qdrant at `settings.qdrant_upsert_batch_size` points per call
- [ ] Parent chunks stored in SQLite `parent_chunks` table
- [ ] Document `chunk_count` and `status` updated on completion
- [ ] `POST /api/collections/{collection_id}/ingest` endpoint returns 202

### User Story 4 -- Rust Worker
- [ ] `embedinator-worker` binary builds with `cargo build --release`
- [ ] CLI: `--file <path>`, `--type <pdf|markdown|text|code>` (auto-detect if omitted)
- [ ] NDJSON output per worker-ndjson.md contract
- [ ] `DocType` enum: `Prose` and `Code` only (NO `Table` or `Mixed`)
- [ ] PDF parser via `pdf-extract`, page-by-page
- [ ] Markdown parser via `pulldown-cmark`, heading boundaries, HeadingTracker
- [ ] Text parser: paragraph + sentence boundaries
- [ ] Code parser: 9 extensions (`.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`)
- [ ] Exit codes: 0=success, 1=file error, 2=parse error
- [ ] `cargo test` passes, `cargo clippy -- -D warnings` clean

### User Story 2 -- Incremental/Dedup
- [ ] SHA256 hash computed for every uploaded file
- [ ] Duplicate detection: same hash + completed status -> HTTP 409
- [ ] Failed document re-ingestion allowed (FR-004)
- [ ] Changed file: old Qdrant points deleted, full re-ingestion (FR-005)
- [ ] Dedup scoped per collection (same file in different collections OK)

### User Story 3 -- Fault Tolerance
- [ ] Invalid embedding skipped, batch continues, `chunks_skipped` incremented
- [ ] `UpsertBuffer` with MAX_CAPACITY=1000 points
- [ ] Qdrant outage: buffer pending upserts, pause job if buffer full
- [ ] Ollama outage: pause job, retry with backoff
- [ ] Worker crash: process received chunks, set status=failed, log stderr
- [ ] Paused jobs resume automatically on service recovery

### User Story 5 -- File Validation
- [ ] 12 file types accepted (`.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`)
- [ ] Unsupported types rejected with HTTP 400 `INVALID_FILE`
- [ ] Files > 100MB rejected with HTTP 413
- [ ] PDF MIME check: must be `application/pdf`
- [ ] Code files: extension-only validation (MIME ignored per R2)

### Cross-Cutting
- [ ] `SUPPORTED_FORMATS` extended to 12 types
- [ ] `ruff check .` passes on all modified/created Python files
- [ ] `cargo clippy -- -D warnings` clean
- [ ] Full regression suite passes with 0 regressions from spec-05 baseline (SC-009)
- [ ] `QdrantClientWrapper` used everywhere (never `QdrantStorage`)
