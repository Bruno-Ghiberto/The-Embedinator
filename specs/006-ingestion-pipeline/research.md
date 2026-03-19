# Research: Ingestion Pipeline

**Branch**: `006-ingestion-pipeline` | **Date**: 2026-03-13 | **Plan**: [plan.md](plan.md)

## R1: PDF Parsing Crate Selection

**Decision**: Use `pdf-extract` (version 0.8) as the PDF parsing crate.

**Rationale**: `pdf-extract` is a pure-Rust crate with no system dependencies. The architecture blueprint notes that `pdfium-render` produces higher-quality output if pdfium is bundled, but bundling pdfium adds ~25MB to the binary and requires managing a platform-specific shared library (`.so` on Linux, `.dylib` on macOS). For a Docker-deployed tool, the extra complexity is not justified at this stage.

**Alternatives considered**:
- `pdfium-render`: Better output quality, especially for complex layouts. Requires bundling the pdfium binary (~25MB). Would be the upgrade path if users report parsing quality issues with `pdf-extract`.
- `lopdf` + custom extraction: More control over text flow, but significantly more implementation effort. Not justified for MVP.

**Migration path**: If parsing quality is insufficient, swap `pdf-extract` for `pdfium-render` in `pdf.rs`. The interface (page-by-page text extraction) remains identical. The `Chunk` output schema is unchanged.

---

## R2: MIME Content-Type Validation for Extended File Types

**Decision**: Apply MIME content-type validation only for PDF files (`application/pdf`). For Markdown, text, and code files, rely on extension-based validation only.

**Rationale**: Code files have unreliable MIME types across operating systems and upload clients:

| Extension | Expected MIME | Commonly Reported |
|-----------|--------------|-------------------|
| `.py` | `text/x-python` | `text/plain`, `application/octet-stream` |
| `.rs` | N/A | `text/plain`, `application/octet-stream` |
| `.ts` | `application/typescript` | `video/mp2t` (conflict with MPEG transport stream!) |
| `.go` | N/A | `text/plain`, `application/octet-stream` |
| `.h` | `text/x-c` | `text/plain` |

Rejecting `.ts` files with MIME `video/mp2t` would be a false negative. Since the Rust worker handles the actual parsing and will produce a clear error if the file content doesn't match expectations, extension validation is sufficient for non-PDF types.

**Implementation**:
- `.pdf` → validate MIME is `application/pdf`
- `.md`, `.txt` → accept any `text/*` MIME (don't reject)
- Code files → extension-only validation (ignore MIME)

**Alternatives considered**:
- Full MIME validation for all types: Rejected due to MIME unreliability for code files.
- Magic byte detection: Over-engineered for this use case. Code files don't have reliable magic bytes.

---

## R3: Documents Table Migration Strategy

**Decision**: Use create-copy-drop-rename pattern within `SQLiteDB._create_tables()`.

**Rationale**: SQLite's `ALTER TABLE` is limited — it cannot rename columns (before SQLite 3.25), change column types, or add constraints like UNIQUE. The safest approach is:

1. Create `documents_new` with the production schema
2. Copy existing rows with column mapping (e.g., `name` → `filename`, first element of `collection_ids` JSON → `collection_id`)
3. Drop `documents` (old)
4. Rename `documents_new` → `documents`
5. Recreate indexes and FK constraints

This preserves all existing Phase 1 data while achieving the target schema cleanly.

**Phase 1 data handling**:
- Existing document records are preserved with mapped columns
- `file_hash` is set to empty string (`''`) for legacy records (they weren't hashed)
- `chunk_count` is set to `0` for legacy records
- Status values are mapped: `indexed` → `completed`, `uploaded`/`parsing`/`indexing` → `pending`
- Legacy vector points (uuid4 IDs) in Qdrant remain as orphans until the user manually re-ingests

**Alternatives considered**:
- ALTER TABLE approach: SQLite 3.25+ supports RENAME COLUMN, but cannot add UNIQUE constraints or change FK relationships. Insufficient.
- Versioned table (`documents_v2`): Requires updating all code referencing `documents`. More invasive than rename.
- Database migration framework (Alembic): Over-engineered for a single-file SQLite database with 1-5 users.

---

## R4: Rust Worker Partial Output Handling

**Decision**: Process all successfully streamed chunks from the worker, even on non-zero exit.

**Rationale**: The NDJSON streaming architecture naturally handles this. Python reads chunks line-by-line as the Rust worker emits them. If the worker crashes at chunk 450 of 600, Python has already received and can process chunks 0-449. The pipeline should:

1. Process all received chunks (embed, validate, upsert)
2. Set `ingestion_jobs.status` to `failed`
3. Set `ingestion_jobs.error_msg` to the worker's stderr output
4. Set `documents.status` to `failed`
5. Record `chunks_processed` as the count of successfully processed chunks

This provides partial value — a partially indexed document is searchable (for the pages that were parsed) and the user gets clear feedback about the failure.

**Alternatives considered**:
- Discard all chunks on worker failure: Wastes work already done and provides no partial value.
- Retry the worker automatically: Over-complex for Phase 2. If parsing fails, the file likely has a structural issue that retrying won't fix.

---

## R5: Constitution File Type Allowlist Extension

**Decision**: Extend the upload allowlist from 3 types (Phase 1: pdf, md, txt) to 12 types (Phase 2: add .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h) without a new ADR.

**Rationale**: Constitution Principle V states file uploads "MUST be validated: extension allowlist (pdf, md, txt), 100 MB size limit, MIME content-type check." The parenthetical list is the Phase 1 scope. The intent of the principle is to validate uploads (prevent arbitrary file types), not to permanently limit to 3 types. Phase 2 introduces a Rust worker that natively supports code file parsing — extending the allowlist is the natural evolution.

The validation intent is fully preserved:
- Extension allowlist: expanded from 3 to 12, still enforced
- Size limit: 100MB, unchanged
- MIME check: applied where reliable (PDF); extension-only for code files (see R2)

**No ADR needed**: This is an extension of scope, not a violation of principle. The constitution's file type list was descriptive of Phase 1, not prescriptive of all phases.

---

## R6: Concurrent Ingestion Resource Management

**Decision**: Use configurable `embed_max_workers` (default 4) to limit ThreadPoolExecutor concurrency across all active ingestion jobs. No per-job resource quotas in Phase 2.

**Rationale**: The system targets 1-5 concurrent users. Multiple simultaneous ingestion jobs share:
- CPU: Rust worker processes (one per job, OS-scheduled)
- GPU/VRAM: Ollama embedding inference (single Ollama instance handles concurrency internally)
- ThreadPoolExecutor: shared pool size limits total parallel embedding threads

For 1-5 users, a shared thread pool with `max_workers=4` provides sufficient parallelism without resource exhaustion. If two jobs run simultaneously, each effectively gets ~2 workers. The Rust worker is CPU-bound but short-lived (2-5s per document), so OS scheduling is adequate.

**Future considerations** (not for Phase 2):
- Per-job resource quotas if user count grows
- Queue-based job scheduling with configurable concurrency limit
- Priority-based scheduling (small files before large)

**Alternatives considered**:
- Global job queue with semaphore: Over-engineered for 1-5 users.
- Per-job thread pool: Wastes resources when only one job is active.
