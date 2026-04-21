# Implementation Plan: Ingestion Pipeline

**Branch**: `006-ingestion-pipeline` | **Date**: 2026-03-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-ingestion-pipeline/spec.md`

## Summary

Implement the production ingestion pipeline that transforms uploaded documents (PDF, Markdown, plain text, 9 code file types) into searchable vector embeddings. The pipeline consists of a Rust binary (`embedinator-worker`) for fast document parsing with NDJSON streaming output, and a Python orchestrator (`backend/ingestion/`) that coordinates chunking, embedding, validation, and storage. Includes schema migration from Phase 1, SHA256-based deduplication, parent/child chunking with breadcrumbs, deterministic UUID5 point IDs, parallel batch embedding, embedding validation (deferred from spec-05), upsert buffering with pause/resume on infrastructure outage (deferred from spec-05), and full ingestion job lifecycle tracking.

## Technical Context

**Language/Version**: Python 3.14+ (pipeline orchestrator) + Rust 1.93.1 (ingestion worker binary)
**Primary Dependencies**: FastAPI >= 0.135, Pydantic v2 >= 2.12, aiosqlite >= 0.21, httpx >= 0.28, tenacity >= 9.0, structlog >= 24.0 (Python); serde 1, serde_json 1, pulldown-cmark 0.12, pdf-extract 0.8, clap 4, regex 1 (Rust)
**Storage**: SQLite WAL mode (`data/embedinator.db`) for documents/jobs/parent chunks + Qdrant for child chunk vectors
**Testing**: pytest (via external runner `scripts/run-tests-external.sh` — NEVER inside Claude Code) + `cargo test` (Rust)
**Target Platform**: Linux server (Docker Compose: 4 services — qdrant, ollama, backend, frontend)
**Project Type**: Web service (backend ingestion subsystem)
**Performance Goals**: 200-page PDF ingested in <20 seconds; Rust parsing 2-5s for 200 pages; parallel embedding ~2s for 1200 chunks
**Constraints**: Max file size 100MB; 12 supported file types; upsert buffer cap 1,000 points; 1-5 concurrent users
**Scale/Scope**: Single-user to small-team usage; parallel ingestion across collections with configurable resource limits

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | ✅ PASS | Ollama is default embedding provider. Rust worker is a local subprocess. No mandatory cloud calls. |
| II | Three-Layer Agent Architecture | ✅ PASS | Not modifying agent layers. ParentStore read path preserved (FR-019) for ResearchGraph compatibility. |
| III | Retrieval Pipeline Integrity | ✅ PASS | Parent/child chunking with breadcrumbs (FR-007), ~500 char children in Qdrant, 2000-4000 char parents in SQLite, deterministic UUID5 IDs (FR-008), Rust worker for Phase 2 parsing (FR-006) — all aligned. |
| IV | Observability from Day One | ✅ PASS | `ingestion_jobs` table tracks full lifecycle with status transitions, chunk counts, error messages, and timestamps. structlog logging throughout with trace IDs. |
| V | Secure by Design | ✅ PASS | Parameterized SQL for all new tables. File validation: extension allowlist (12 types, extended from Phase 1's 3), 100MB size limit. MIME check for PDF; extension-only for code files (see R2 in research.md). Rate limits respected on ingest endpoint. |
| VI | NDJSON Streaming Contract | ✅ PASS | Chat streaming unaffected. Rust worker uses NDJSON for subprocess output, consistent with project convention. |
| VII | Simplicity by Default | ✅ PASS | SQLite for all relational storage. Rust worker is a subprocess spawned by Python backend, NOT a separate Docker service — still exactly 4 services. This IS Phase 2, making the Rust worker the correct implementation per ADR-003. |

**Gate result**: ALL PASS. No violations. One extension noted (file type allowlist expanded from 3→12 for Phase 2; see Complexity Tracking).

## Project Structure

### Documentation (this feature)

```text
specs/006-ingestion-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0: research decisions
├── data-model.md        # Phase 1: entity schemas and state machines
├── quickstart.md        # Phase 1: developer setup guide
├── contracts/
│   ├── ingest-api.md    # POST /api/collections/{id}/ingest contract
│   └── worker-ndjson.md # Rust worker subprocess NDJSON schema
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── ingestion/
│   ├── __init__.py          # Package init
│   ├── pipeline.py          # IngestionPipeline orchestrator
│   ├── chunker.py           # ChunkSplitter: parent/child + breadcrumbs + UUID5
│   ├── embedder.py          # BatchEmbedder: parallel embedding + validation
│   └── incremental.py       # IncrementalChecker: SHA256 dedup + change detection
├── storage/
│   ├── sqlite_db.py         # MODIFY: migrate documents, add ingestion_jobs + parent_chunks
│   └── parent_store.py      # MODIFY: update get_by_ids() for new schema
├── api/
│   └── documents.py         # MODIFY: add ingest endpoint, extend SUPPORTED_FORMATS
└── config.py                # MODIFY: add 3 new settings fields (5 ingestion fields already exist)

ingestion-worker/
├── Cargo.toml
└── src/
    ├── main.rs              # CLI (clap), file type dispatch, NDJSON serialization
    ├── pdf.rs               # PDF extraction (pdf-extract)
    ├── markdown.rs          # Markdown parsing (pulldown-cmark)
    ├── text.rs              # Plain text paragraph/sentence splitting
    ├── code.rs              # Code files (9 extensions), doc_type "code"
    ├── heading_tracker.rs   # HeadingTracker: heading hierarchy
    └── types.rs             # Chunk struct, DocType enum, serde

tests/
├── unit/
│   ├── test_chunker.py
│   ├── test_embedder.py
│   ├── test_incremental.py
│   ├── test_ingestion_pipeline.py
│   ├── test_ingestion_api.py
│   └── test_schema_migration.py
└── integration/
    └── test_ingestion_pipeline.py
```

**Structure Decision**: Follows the existing web application structure (backend/ + frontend/). New `backend/ingestion/` package for all pipeline modules. Rust worker in a separate `ingestion-worker/` Cargo workspace at repo root. This mirrors the architecture established in Phase 1 where backend modules are organized by domain concern.

## Complexity Tracking

| Extension | Why Needed | Constitution Alignment |
|-----------|------------|----------------------|
| File type allowlist expanded from 3 to 12 | Rust worker supports code files (.py, .js, .ts, .rs, .go, .java, .c, .cpp, .h) in addition to PDF/MD/TXT — required for code-aware RAG | Principle V intent (validate uploads) preserved. Extension-based validation + MIME check for PDF. No violation — Phase 2 naturally expands supported types. |

## Constitution Re-Check (Post-Design)

*Re-evaluated after Phase 1 design artifacts (data-model.md, contracts/, quickstart.md) were produced.*

| # | Principle | Status | Post-Design Notes |
|---|-----------|--------|-------------------|
| I | Local-First Privacy | ✅ PASS | Confirmed: no cloud dependencies in data model or contracts. Ollama embedding calls are local. |
| II | Three-Layer Agent Architecture | ✅ PASS | Confirmed: data model preserves `parent_chunks` read path via `ParentStore.get_by_ids()`. ResearchGraph integration unaffected. |
| III | Retrieval Pipeline Integrity | ✅ PASS | Confirmed: data model defines parent (2000-4000 chars) and child (~500 chars) entities. UUID5 deterministic IDs. Breadcrumb fields in both ParentChunk and ChildChunk. Rust worker NDJSON contract specifies `heading_path` for breadcrumb generation. |
| IV | Observability from Day One | ✅ PASS | Confirmed: `ingestion_jobs` entity tracks full lifecycle with `status`, `chunks_processed`, `chunks_skipped`, `error_msg`, timestamps. State machine documented. |
| V | Secure by Design | ✅ PASS | Confirmed: ingest-api contract specifies validation order (extension → size → collection → MIME → duplicate). Parameterized SQL in all DDL. Rate limit noted (10 uploads/min). |
| VI | NDJSON Streaming Contract | ✅ PASS | Confirmed: worker-ndjson contract defines complete schema with invariants. Chat NDJSON contract unchanged. |
| VII | Simplicity by Default | ✅ PASS | Confirmed: SQLite for all relational storage (3 tables). No new Docker services. Rust worker is subprocess, not service. |

**Post-design gate result**: ALL PASS. Design artifacts are constitution-compliant. Ready for `/speckit.tasks`.

## Generated Artifacts

| Artifact | Path | Description |
|----------|------|-------------|
| Plan | `specs/006-ingestion-pipeline/plan.md` | This file — technical context, constitution check, project structure |
| Research | `specs/006-ingestion-pipeline/research.md` | 6 research decisions (R1-R6): PDF crate, MIME validation, migration strategy, partial output, file type extension, resource management |
| Data Model | `specs/006-ingestion-pipeline/data-model.md` | 5 entities (Document, IngestionJob, ParentChunk, ChildChunk, NativeWorkerOutput), state machines, validation rules, cascade behavior |
| API Contract | `specs/006-ingestion-pipeline/contracts/ingest-api.md` | POST /api/collections/{id}/ingest — request/response schemas, validation flow, error codes |
| Worker Contract | `specs/006-ingestion-pipeline/contracts/worker-ndjson.md` | Rust worker subprocess protocol — CLI interface, NDJSON schema, exit codes, invariants |
| Quickstart | `specs/006-ingestion-pipeline/quickstart.md` | Developer setup guide — prerequisites, build steps, test commands, smoke tests |
