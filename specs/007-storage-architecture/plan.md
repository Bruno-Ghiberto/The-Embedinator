# Implementation Plan: Storage Architecture

**Branch**: `007-storage-architecture` | **Date**: 2026-03-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/007-storage-architecture/spec.md`

## Summary

Implement a dual-store persistence layer for The Embedinator: SQLite (relational metadata, parent chunks, observability traces) + Qdrant (vector search with hybrid dense+BM25). The two stores link via parent_id relationships enabling idempotent, resumable ingestion with fail-entire-batch recovery. Support encrypted API key storage and concurrent read performance via WAL mode.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: aiosqlite (>=0.21), qdrant-client (>=1.17.0), cryptography (>=44.0), tenacity (>=9.0)
**Storage**: SQLite WAL mode (embedinator.db) + Qdrant (external Docker container)
**Testing**: pytest with external test runner (scripts/run-tests-external.sh)
**Target Platform**: Linux self-hosted single-user deployment
**Project Type**: Backend infrastructure (storage layer for RAG system)
**Performance Goals**: Parent retrieval <10ms per batch, Qdrant search <100ms for 100K vectors, concurrent WAL reads without blocking
**Constraints**: Single writer (serialized ingestion), 1K-10K documents per collection, idempotent re-runs on failure
**Scale/Scope**: Medium deployment (self-hosted, 1–5 concurrent users, SQLite acceptable for write serialization)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Requirement | Status |
|-----------|-------------|--------|
| I. Local-First Privacy | All data in SQLite local file; no mandatory outbound calls | ✅ PASS |
| II. Three-Layer Agent Arch | Storage layer used by ResearchGraph; metadata stored per ADR-006 | ✅ PASS |
| III. Retrieval Pipeline Integrity | Parent/child chunking (UUID5 IDs), hybrid search, parent chunks in SQLite, breadcrumbs in JSON | ✅ PASS |
| IV. Observability from Day One | query_traces table captures all chat requests; FK relationship to document/collection | ✅ PASS |
| V. Secure by Design | Fernet encryption for API keys; parameterized SQL (no injection); trace ID propagation | ✅ PASS |
| VI. NDJSON Streaming Contract | Storage layer invisible to streaming; query_traces record metadata for metadata frame | ✅ PASS |
| VII. Simplicity by Default | SQLite (not PostgreSQL); embedded Qdrant client; no auth needed; YAGNI on caching/pooling | ✅ PASS |

**All gates PASS — no violations or justifications needed.**

## Project Structure

### Documentation (this feature)

```text
specs/007-storage-architecture/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output (no unknowns; empty)
├── data-model.md        # Phase 1 output (7 entities: Collections, Documents, IngestionJobs, ParentChunks, QueryTraces, Settings, Providers)
├── quickstart.md        # Phase 1 output (developer guide for storage layer)
├── contracts/           # Phase 1 output (storage layer internal contract schema)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code

```text
backend/
  storage/
    __init__.py
    sqlite_db.py          # SQLiteDB class: async context, schema init, all table CRUD
    qdrant_client.py      # QdrantStorage: collection creation, batch_upsert, hybrid search, delete
    parent_store.py       # ParentStore: parent chunk convenience layer (wrapper over SQLiteDB)
  providers/
    key_manager.py        # KeyManager: Fernet encryption/decryption for API keys
  main.py                 # Updated: storage layer initialization in lifespan

data/
  embedinator.db          # SQLite database (gitignored, created at runtime)
  qdrant_db/              # Qdrant persistence volume (gitignored)

tests/
  unit/
    test_sqlite_db.py                  # SQLiteDB CRUD, schema, constraints, indexes
    test_qdrant_storage.py             # QdrantStorage collection init, search, delete
    test_key_manager.py                # KeyManager encrypt/decrypt
    test_parent_store.py               # ParentStore batch operations
  integration/
    test_storage_integration.py        # Parent-child linking, Qdrant-SQLite cross-ref
    test_concurrent_reads.py           # WAL mode concurrent reader validation
    test_performance.py                # Parent retrieval latency < 10ms
    test_schema_validation.py          # Foreign keys, indexes, constraints, WAL
```

**Structure Decision**: Backend infrastructure (no frontend components). Storage layer is internal to backend, exposed via REST API (spec-08). SQLite as single file (embedinator.db), Qdrant as external service. Tests follow constitution standards: unit tests (no external services), integration tests (with Qdrant).

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| *(none)* | — | No complexity violations — all Constitution checks PASS. |
