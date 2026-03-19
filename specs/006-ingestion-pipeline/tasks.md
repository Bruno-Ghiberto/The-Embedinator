# Tasks: Ingestion Pipeline

**Input**: Design documents from `/specs/006-ingestion-pipeline/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — each user story has associated unit and integration tests.

**Organization**: Tasks are grouped by user story. US6 (Schema Migration) is foundational. US1 (Core Pipeline) and US4 (Rust Worker) are combined in Phase 3 because the pipeline requires the worker to function.

**Testing**: ALL test execution via `zsh scripts/run-tests-external.sh`. NEVER run pytest inside Claude Code.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US4, US6)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create package structure and scaffolding for all new modules

- [x] T001 Create `backend/ingestion/` package with `__init__.py`
- [x] T002 [P] Initialize `ingestion-worker/` Cargo workspace: create `Cargo.toml` with dependencies (serde, serde_json, pulldown-cmark 0.12, pdf-extract 0.8, clap 4, regex 1) and empty `src/` module files (main.rs, pdf.rs, markdown.rs, text.rs, code.rs, heading_tracker.rs, types.rs)
- [x] T003 [P] Create unit test scaffolding files: `tests/unit/test_chunker.py`, `tests/unit/test_embedder.py`, `tests/unit/test_incremental.py`, `tests/unit/test_ingestion_pipeline.py`, `tests/unit/test_ingestion_api.py`
- [x] T004 [P] Create integration test scaffolding: `tests/integration/test_ingestion_pipeline.py`

**Checkpoint**: Package directories exist, Cargo.toml valid (`cargo check` succeeds), all test files importable

---

## Phase 2: Foundational — User Story 6 — Database Schema Migration from Phase 1 (Priority: P1)

**Goal**: Migrate existing Phase 1 database schema to production schema required by the ingestion pipeline. Create `ingestion_jobs` and `parent_chunks` tables. Preserve existing data and backward compatibility.

**Independent Test**: Run migration on existing database with Phase 1 data. Verify collections, documents, and queries still function. Verify new tables exist and accept records.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Implementation for User Story 6

- [x] T005 [US6] Add 3 new config fields to `backend/config.py`: `rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"`, `embed_max_workers: int = 4`, `qdrant_upsert_batch_size: int = 50`. NOTE: `upload_dir`, `max_upload_size_mb`, `parent_chunk_size`, `child_chunk_size`, `embed_batch_size` already exist in config.py — do NOT re-add them.
- [x] T006 [US6] Implement `documents` table migration using create-copy-drop-rename pattern in `backend/storage/sqlite_db.py` per R3 from research.md. Map columns: `name`→`filename`, `collection_ids` JSON→`collection_id` TEXT (extract first), add `file_hash` (empty for legacy), `chunk_count` (0 for legacy), map statuses (`indexed`→`completed`, `uploaded`/`parsing`/`indexing`→`pending`), rename `upload_date`→`created_at`, add `ingested_at`. Add UNIQUE constraint `(collection_id, file_hash)`.
- [x] T007 [P] [US6] Add `ingestion_jobs` table DDL to `_create_tables()` in `backend/storage/sqlite_db.py` per data-model.md: id, document_id FK, status, started_at, finished_at, error_msg, chunks_processed, chunks_skipped
- [x] T008 [P] [US6] Add `parent_chunks` table DDL with indexes to `_create_tables()` in `backend/storage/sqlite_db.py` per data-model.md: id, collection_id FK, document_id FK, text, source_file, page, breadcrumb, created_at. Create `idx_parent_chunks_collection` and `idx_parent_chunks_document`
- [x] T009 [US6] Update `ParentStore.get_by_ids()` SQL query in `backend/storage/parent_store.py`: change `parent_id`→`id`, `collection`→`collection_id` to match new `parent_chunks` schema. Verify return type compatibility with ResearchGraph (FR-019)
- [x] T010 [US6] Verify existing document CRUD operations (`list_documents`, `get_document`, `delete_document`) still work after migration — adjust SQL queries in `backend/api/documents.py` if column names changed (`name`→`filename`, `upload_date`→`created_at`)
- [x] T011 [US6] Write unit tests for schema migration in `tests/unit/test_schema_migration.py`: (1) fresh DB creates all 3 tables, (2) migration preserves Phase 1 data with correct column mapping, (3) ParentStore.get_by_ids() works with new schema, (4) UNIQUE constraint prevents duplicate (collection_id, file_hash)

**Checkpoint**: `python -c "from backend.config import settings; print(settings.rust_worker_path, settings.embed_max_workers, settings.qdrant_upsert_batch_size)"` succeeds. `ruff check backend/storage/sqlite_db.py backend/config.py backend/storage/parent_store.py` passes. Schema tests pass via `zsh scripts/run-tests-external.sh -n spec06-us6 tests/unit/test_schema_migration.py`

---

## Phase 3: User Story 1 — Upload and Ingest a Document (P1) + User Story 4 — High-Performance Parsing via Native Worker (P2) 🎯 MVP

**Goal**: Implement the complete end-to-end ingestion pipeline: user uploads a document, Rust worker parses it, Python pipeline chunks/embeds/stores it, document becomes searchable. This combines US1 (pipeline) and US4 (worker) because the pipeline requires the worker to function.

**Independent Test**: Upload a small PDF to a collection and verify that the document appears as `completed`, child chunks are searchable in Qdrant, and parent chunks are retrievable from SQLite.

### Rust Worker (US4) — can run fully in parallel with Python tasks below

- [x] T012 [P] [US4] Implement `types.rs` in `ingestion-worker/src/types.rs`: `Chunk` struct with fields (text, page, section, heading_path, doc_type, chunk_profile, chunk_index), `DocType` enum (`Prose`, `Code`), serde Serialize/Deserialize derives per worker-ndjson.md contract
- [x] T013 [P] [US4] Implement `heading_tracker.rs` in `ingestion-worker/src/heading_tracker.rs`: `HeadingTracker` struct maintaining Chapter > Section > Subsection hierarchy, `push(level, text)` method to update, `path()` method returning `Vec<String>` of current heading path
- [x] T014 [US4] Implement `text.rs` in `ingestion-worker/src/text.rs`: plain text chunking with paragraph boundary detection (split on double newlines), sentence boundary fallback within paragraphs, emit `Chunk` structs with `doc_type: Prose`
- [x] T015 [P] [US4] Implement `code.rs` in `ingestion-worker/src/code.rs`: code file handling for 9 extensions (.py, .js, .ts, .rs, .go, .java, .c, .cpp, .h), paragraph-boundary chunking similar to text.rs but emit with `doc_type: Code`
- [x] T016 [US4] Implement `markdown.rs` in `ingestion-worker/src/markdown.rs`: parse with pulldown-cmark, split at H1/H2/H3 heading boundaries, use HeadingTracker to maintain heading hierarchy, emit chunks with correct `heading_path`
- [x] T017 [US4] Implement `pdf.rs` in `ingestion-worker/src/pdf.rs`: PDF text extraction using `pdf-extract` crate (R1 decision), page-by-page iteration, emit one or more chunks per page, skip image-only pages (warn to stderr)
- [x] T018 [US4] Implement `main.rs` in `ingestion-worker/src/main.rs`: clap CLI (`--file <path>`, `--type <pdf|markdown|text|code>`), auto-detect type from extension per worker-ndjson.md contract, dispatch to parser module, serialize each Chunk as NDJSON line to stdout, write errors to stderr, exit codes (0=success, 1=file error, 2=parse error)
- [x] T019 [US4] Write Rust tests in `ingestion-worker/src/` (inline #[cfg(test)] modules): test NDJSON output schema for each parser, test heading_tracker hierarchy, test type auto-detection, test partial output on parse error. Run: `cd ingestion-worker && cargo test`
- [x] T020 [US4] Build release binary and smoke test: `cargo build --release --manifest-path ingestion-worker/Cargo.toml`. Verify: `echo "test" > /tmp/test.txt && ./ingestion-worker/target/release/embedinator-worker --file /tmp/test.txt --type text` produces valid NDJSON

### Python Pipeline (US1) — can run fully in parallel with Rust tasks above

- [x] T021 [P] [US1] Implement `ChunkSplitter` class in `backend/ingestion/chunker.py`: `split_into_parents(raw_chunks: list[dict]) -> list[ParentChunk]` accumulating to 2000-4000 chars, `split_parent_into_children(parent_text: str, target_size: int = 500) -> list[str]` splitting on sentence boundaries, `prepend_breadcrumb(text: str, heading_path: list[str]) -> str` producing `[A > B] text`, `compute_point_id(source_file: str, page: int, chunk_index: int) -> str` using `uuid5(EMBEDINATOR_NAMESPACE, key)` per data-model.md
- [x] T022 [P] [US1] Implement `BatchEmbedder` class in `backend/ingestion/embedder.py`: `embed_chunks(texts: list[str]) -> list[list[float]]` using ThreadPoolExecutor (settings.embed_max_workers workers, settings.embed_batch_size per call), `_embed_batch(batch: list[str]) -> list[list[float]]` calling Ollama API via httpx, `validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]` with 4 checks (dimensions, NaN, zero, magnitude) per data-model.md validation rules
- [x] T023 [US1] Implement `IngestionPipeline` class in `backend/ingestion/pipeline.py`: `ingest_file(file_path: str, filename: str, collection_id: str, document_id: str, job_id: str) -> IngestionResult` orchestrating: (1) update job status `started`, (2) spawn Rust worker subprocess, (3) read NDJSON stdout line-by-line, update status `streaming`, (4) pass raw chunks to ChunkSplitter, (5) embed children via BatchEmbedder, update status `embedding`, (6) batch upsert to Qdrant (settings.qdrant_upsert_batch_size points per call), (7) store parents in SQLite parent_chunks table, (8) update document chunk_count and status `completed`, (9) update job status `completed` with chunks_processed count. Accept `db: SQLiteDB`, `qdrant: QdrantClientWrapper` via constructor DI.
- [x] T024 [US1] Implement `POST /api/collections/{collection_id}/ingest` endpoint in `backend/api/documents.py` per ingest-api.md contract: accept multipart file upload, validate extension against SUPPORTED_FORMATS, validate size ≤ 100MB, validate collection exists, save file to upload_dir, create document record (status=pending), create ingestion_jobs record (status=started), launch pipeline as background task, return 202 with document_id + job_id
- [x] T025 [US1] Extend `SUPPORTED_FORMATS` from `{".pdf", ".md", ".txt"}` to include 12 types (add `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`) in `backend/api/documents.py`
- [x] T026 [P] [US1] Write unit tests for ChunkSplitter in `tests/unit/test_chunker.py`: parent chunks within 2000-4000 chars, child chunks ~500 chars, breadcrumb prefix format `[A > B] text`, UUID5 determinism (same input → same ID), UUID5 uniqueness (different input → different ID)
- [x] T027 [P] [US1] Write unit tests for BatchEmbedder in `tests/unit/test_embedder.py`: parallel batching splits correctly, validate_embedding passes valid vectors, validate_embedding catches wrong dimensions/NaN/zero/low magnitude with correct reason strings
- [x] T028 [US1] Write unit tests for IngestionPipeline in `tests/unit/test_ingestion_pipeline.py`: happy path with mocked worker (mock subprocess outputting NDJSON lines), mock QdrantClientWrapper, verify status transitions (started→streaming→embedding→completed), verify document chunk_count updated
- [x] T029 [US1] Write unit tests for ingest API endpoint in `tests/unit/test_ingestion_api.py`: valid file accepted (202), unsupported extension rejected (400 INVALID_FILE), oversized file rejected (413), missing collection rejected (404), response body matches contract schema
- [x] T030 [US1] Write integration test: upload a small PDF via ingest endpoint, wait for completion, verify document status=completed, child chunks exist in Qdrant, parent chunks exist in SQLite parent_chunks table — in `tests/integration/test_ingestion_pipeline.py`

**Checkpoint**: `python -c "from backend.ingestion.pipeline import IngestionPipeline; print('Pipeline OK')"` and `python -c "from backend.ingestion.chunker import ChunkSplitter; print('Chunker OK')"` and `python -c "from backend.ingestion.embedder import BatchEmbedder, validate_embedding; print('Embedder OK')"` succeed. `cargo build --release --manifest-path ingestion-worker/Cargo.toml` succeeds. `ruff check backend/ingestion/` passes. Unit tests: `zsh scripts/run-tests-external.sh -n spec06-us1 tests/unit/test_chunker.py tests/unit/test_embedder.py tests/unit/test_ingestion_pipeline.py tests/unit/test_ingestion_api.py`. Integration: `zsh scripts/run-tests-external.sh -n spec06-integration tests/integration/test_ingestion_pipeline.py`

---

## Phase 4: User Story 2 — Incremental Re-Ingestion and Duplicate Detection (Priority: P1)

**Goal**: Prevent duplicate document uploads and support efficient re-ingestion when files change, using SHA256 hash-based change detection and deterministic UUID5 IDs for idempotent upserts.

**Independent Test**: Upload a file, re-upload same file (verify 409 rejection). Modify file, re-upload (verify old data replaced, new chunks indexed).

### Implementation for User Story 2

- [x] T031 [US2] Implement `IncrementalChecker` class in `backend/ingestion/incremental.py`: `compute_file_hash(file_path: str) -> str` computing SHA256 hex digest, `check_duplicate(collection_id: str, file_hash: str) -> tuple[bool, str | None]` querying documents table (returns (is_dup, existing_doc_id)), `check_change(collection_id: str, filename: str, new_hash: str) -> tuple[bool, str | None]` detecting modified re-uploads. Accept `db: SQLiteDB` via constructor.
- [x] T032 [US2] Wire `IncrementalChecker` into `IngestionPipeline.ingest_file()` in `backend/ingestion/pipeline.py`: call check_duplicate before spawning worker, compute hash at pipeline entry
- [x] T033 [US2] Implement old vector point deletion on re-ingestion in `backend/ingestion/pipeline.py`: when change detected, delete old Qdrant points by `source_file` filter and old parent_chunks by `document_id` before re-ingesting
- [x] T034 [US2] Wire duplicate/change detection into API endpoint in `backend/api/documents.py`: return HTTP 409 `DUPLICATE_DOCUMENT` for same hash + completed status, allow re-ingestion for failed status (FR-004), trigger point deletion + re-ingest for changed hash (FR-005)
- [x] T035 [US2] Write unit tests for `IncrementalChecker` in `tests/unit/test_incremental.py`: SHA256 hash correctness, duplicate detection (same hash + completed → True), failed document re-ingestion allowed (same hash + failed → False), change detection (different hash → old doc ID returned), per-collection scoping (same hash in different collections → not duplicate)
- [x] T036 [US2] Write integration test: upload file → re-upload same → 409; modify file → re-upload → verify old Qdrant points deleted and new chunks indexed with correct UUID5 IDs — in `tests/integration/test_ingestion_pipeline.py`

**Checkpoint**: `python -c "from backend.ingestion.incremental import IncrementalChecker; print('IncrementalChecker OK')"` succeeds. Tests: `zsh scripts/run-tests-external.sh -n spec06-us2 tests/unit/test_incremental.py`

---

## Phase 5: User Story 3 — Embedding Validation and Fault Tolerance (Priority: P2)

**Goal**: Ensure the pipeline gracefully handles embedding failures, infrastructure outages, and worker crashes without losing progress. Invalid embeddings are skipped (not fatal). Qdrant/Ollama outages trigger pause/resume.

**Independent Test**: Inject a simulated embedding failure and verify batch continues. Simulate Qdrant unavailability and verify job pauses and resumes.

### Implementation for User Story 3

- [x] T037 [US3] Add skip-and-continue behavior to `BatchEmbedder.embed_chunks()` in `backend/ingestion/embedder.py`: when `validate_embedding()` fails for a chunk, log reason via structlog, increment a skipped counter, continue with remaining chunks in batch. Return both valid embeddings and skip count.
- [x] T038 [US3] Implement `UpsertBuffer` class in `backend/ingestion/pipeline.py`: `_buffer: list` with `MAX_CAPACITY = 1000`, `add(points) -> bool` (returns False at capacity), `flush(qdrant, collection) -> int` (batch upsert and clear), `pending_count` property
- [x] T039 [US3] Wire upsert buffering into `IngestionPipeline`: attempt Qdrant upsert → on failure, add to UpsertBuffer → if buffer full, set job status=`paused` → poll for recovery → flush buffer → resume embedding → update status back to `embedding` in `backend/ingestion/pipeline.py`
- [x] T040 [US3] Implement Ollama outage handling in `backend/ingestion/pipeline.py`: detect embedding failures (CircuitOpenError or connection error), set job status=`paused`, implement retry loop with backoff, resume when circuit breaker closes or connection recovers
- [x] T041 [US3] Implement worker crash handling in `backend/ingestion/pipeline.py`: if worker exits non-zero, process all successfully streamed chunks (per R4 from research.md), log stderr output, set job status=`failed`, set document status=`failed`, record chunks_processed count
- [x] T042 [US3] Write unit tests for fault tolerance in `tests/unit/test_ingestion_pipeline.py`: (1) validation failure skips chunk, rest of batch succeeds, chunks_skipped incremented, (2) UpsertBuffer add/flush mechanics, (3) buffer full triggers pause, (4) Ollama outage triggers pause, (5) worker crash processes received chunks and sets status=failed
- [x] T043 [US3] Write integration test for fault tolerance in `tests/integration/test_ingestion_pipeline.py`: mock Qdrant to be temporarily unreachable → verify job pauses → restore → verify job completes with all points flushed

**Checkpoint**: Tests: `zsh scripts/run-tests-external.sh -n spec06-us3 tests/unit/test_ingestion_pipeline.py tests/unit/test_embedder.py`

---

## Phase 6: User Story 5 — File Type Validation and Upload Constraints (Priority: P3)

**Goal**: Enforce strict validation on uploaded files. Reject unsupported formats and oversized files with clear error messages before any processing begins. Add MIME check for PDF uploads.

**Independent Test**: Upload files of unsupported types and verify rejection with appropriate error codes. Upload a file exceeding 100MB and verify rejection.

### Implementation for User Story 5

- [x] T044 [US5] Add MIME content-type validation for PDF uploads in `backend/api/documents.py`: check `file.content_type == "application/pdf"` for `.pdf` files per R2 from research.md. For code files, skip MIME check (extension-only validation).
- [x] T045 [US5] Write comprehensive file validation tests in `tests/unit/test_ingestion_api.py`: (1) all 12 supported types accepted, (2) unsupported types rejected (.exe, .zip, .docx, .xlsx → 400 INVALID_FILE), (3) file > 100MB rejected (413), (4) PDF with wrong MIME rejected (400), (5) .ts file with MIME video/mp2t accepted (extension-only for code)
- [x] T046 [US5] Write edge case tests in `tests/unit/test_ingestion_api.py`: (1) zero-content PDF produces completed with chunk_count=0, (2) missing worker binary returns clear error, (3) concurrent upload of same file to same collection — second rejected by UNIQUE constraint

**Checkpoint**: Tests: `zsh scripts/run-tests-external.sh -n spec06-us5 tests/unit/test_ingestion_api.py`

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Full regression, code quality, and final validation across all stories

- [x] T047 Run full unit test suite: `zsh scripts/run-tests-external.sh -n spec06-units tests/unit/`
- [x] T048 Run full integration test suite: `zsh scripts/run-tests-external.sh -n spec06-integ tests/integration/`
- [x] T049 [P] Run `ruff check` on all modified/created Python files: `ruff check backend/ingestion/ backend/storage/sqlite_db.py backend/storage/parent_store.py backend/api/documents.py backend/config.py tests/`
- [x] T050 [P] Run Rust quality checks: `cd ingestion-worker && cargo test && cargo clippy -- -D warnings`
- [x] T051 Run full regression suite (all specs): `zsh scripts/run-tests-external.sh -n spec06-full tests/` — verify 0 regressions from spec-05 baseline (SC-009)
- [x] T052 Verify all done criteria: schema migration (US6), pipeline happy path (US1), Rust worker builds and parses all 4 doc types (US4), dedup works (US2), fault tolerance (US3), file validation (US5). Run quickstart.md smoke test.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational / US6 (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US1 + US4 (Phase 3)**: Depends on US6. US4 (Rust) and US1 (Python) can run in parallel within this phase
- **US2 (Phase 4)**: Depends on US1 (needs pipeline to add dedup to)
- **US3 (Phase 5)**: Depends on US1 (adds fault tolerance to existing pipeline)
- **US5 (Phase 6)**: Depends on US1 (adds validation to existing API endpoint)
- **Polish (Phase 7)**: Depends on all stories being complete

### User Story Dependencies

```
US6 (Schema) ──────────┐
                        ├──► US1 + US4 (Pipeline + Worker) ──► US2 (Dedup)
                        │                                  ──► US3 (Fault Tolerance)
                        │                                  ──► US5 (File Validation)
                        └──────────────────────────────────────► Polish
```

- **US6**: FOUNDATIONAL — must complete before any other story
- **US1 + US4**: Can be developed in parallel (Rust worker + Python pipeline are separate codebases)
- **US2**: Requires US1 pipeline to exist (adds IncrementalChecker to pipeline flow)
- **US3**: Requires US1 pipeline to exist (adds UpsertBuffer, pause/resume, crash handling)
- **US5**: Requires US1 API endpoint to exist (adds MIME validation, edge case handling)
- **US2, US3, US5**: Independent of each other — can run in parallel after US1

### Within Each User Story

- Models/types before services
- Core logic before API wiring
- Implementation before tests
- Unit tests before integration tests

### Agent Teams Wave Mapping

| Wave | Phase | Agents | Notes |
|------|-------|--------|-------|
| 1 | Phase 1 + 2 | A1 (Sonnet) | Setup + Schema Migration |
| 2 | Phase 3 | A2 (Opus) + A3 (Sonnet) + A4 (Sonnet) + A5 (Sonnet) | Pipeline + Chunker + Embedder + Rust Worker (parallel) |
| 3 | Phase 4 + 6 | A6 (Sonnet) + A7 (Sonnet) | Incremental + API/File Validation |
| 4 | Phase 5 + integration | A8 (Sonnet) | Fault Tolerance + Integration Tests |
| 5 | Phase 7 | Lead | Polish + Full Regression |

### Parallel Opportunities

**Phase 3 (highest parallelism):**
```
Parallel Stream A (Rust — A5):     T012, T013 → T014, T015 → T016, T017 → T018 → T019 → T020
Parallel Stream B (Chunker — A3):  T021 → T026
Parallel Stream C (Embedder — A4): T022 → T027
Parallel Stream D (Pipeline — A2): T023 → T024, T025 → T028, T029 → T030
```

**Phase 4-6 (after Phase 3):**
```
US2 (A6): T031 → T032, T033 → T034 → T035 → T036
US5 (A7): T044 → T045, T046     (can run parallel with US2)
US3 (A8): T037 → T038 → T039, T040 → T041 → T042 → T043
```

---

## Parallel Example: Phase 3 (US1 + US4)

```bash
# These 4 streams run fully in parallel (different codebases/files):

# Stream A — Rust Worker (A5):
Task: "Implement types.rs in ingestion-worker/src/types.rs"
Task: "Implement heading_tracker.rs in ingestion-worker/src/heading_tracker.rs"

# Stream B — Chunker (A3):
Task: "Implement ChunkSplitter in backend/ingestion/chunker.py"

# Stream C — Embedder (A4):
Task: "Implement BatchEmbedder in backend/ingestion/embedder.py"

# Stream D — Pipeline (A2):
Task: "Implement IngestionPipeline in backend/ingestion/pipeline.py"  # after chunker + embedder
```

---

## Implementation Strategy

### MVP First (US6 + US1 + US4 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: US6 Schema Migration (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 + US4 Core Pipeline + Rust Worker
4. **STOP and VALIDATE**: Upload a PDF, verify it's parsed, chunked, embedded, and searchable
5. This is the minimum viable ingestion pipeline

### Incremental Delivery

1. Setup + US6 → Schema ready
2. US1 + US4 → Core pipeline working → **MVP!**
3. US2 → Duplicate detection prevents wasted work
4. US3 → Fault tolerance for production reliability
5. US5 → Comprehensive file validation
6. Polish → Full regression, quality gates

### Agent Teams Strategy

With 8 agents across 5 waves:

1. **Wave 1 (A1)**: Setup + US6 foundation — single agent, sequential
2. **Wave 2 (A2+A3+A4+A5)**: Core pipeline — 4 agents in parallel, maximum throughput
3. **Wave 3 (A6+A7)**: Dedup + File Validation — 2 agents in parallel
4. **Wave 4 (A8)**: Fault Tolerance + Integration — 1 agent, depends on everything
5. **Wave 5 (Lead)**: Polish + Regression — lead runs directly

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- US4 (Rust Worker) tasks are fully parallel with US1 (Python Pipeline) tasks — different codebases
- A2 (Pipeline orchestrator) uses Opus model — most complex component
- All other agents use Sonnet model for cost efficiency
- **NEVER run pytest inside Claude Code** — always use `zsh scripts/run-tests-external.sh`
- Rust tests run via `cargo test` (not pytest)
- Agent instruction files at `Docs/PROMPTS/spec-06-ingestion/agents/A{N}-name.md`
