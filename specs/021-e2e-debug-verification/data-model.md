# Data Model: End-to-End Debug & Verification

**Phase 1 output** — No new database entities. Spec-21 uses existing schema only.

---

## Existing Entities (Used, Not Modified)

### Service (runtime concept, not persisted)

A containerized component of the application.

| Field | Type | Description |
|-------|------|-------------|
| name | string | Service identifier (qdrant, ollama, backend, frontend) |
| health_status | enum | healthy, unhealthy, starting, stopped |
| port | int | Host port mapping (6333, 11434, 8000, 3000) |
| depends_on | list[string] | Services that must be healthy before this one starts |

**Relationships**: Frontend depends_on Backend; Backend depends_on Qdrant + Ollama.
**Used by**: FR-001 (startup), FR-002 (health verification), SC-001 (all healthy <5 min).

### Collection (SQLite: `collections` table)

A named group of documents for search.

| Field | Type | Description |
|-------|------|-------------|
| id | int (PK) | Auto-increment |
| name | string | User-provided name |
| description | string | Optional description |
| embedding_model | string | Model used for embeddings |
| chunk_profile | string | Chunking configuration |
| qdrant_collection_name | string | Corresponding Qdrant collection |
| created_at | datetime | Creation timestamp |

**Relationships**: Has many Documents. Has many ParentChunks.
**Used by**: FR-009 (create collections), FR-010 (upload documents), seed_data.py.

### Document (SQLite: `documents` table)

An uploaded file processed into searchable chunks.

| Field | Type | Description |
|-------|------|-------------|
| id | int (PK) | Auto-increment |
| collection_id | int (FK → collections) | Parent collection |
| filename | string | Original filename |
| file_hash | string | SHA-256 hash for dedup |
| status | enum | pending, processing, complete, failed |
| chunk_count | int | Number of child chunks indexed |
| created_at | datetime | Upload timestamp |

**Relationships**: Belongs to Collection. Has many IngestionJobs. Has many ParentChunks.
**Used by**: FR-010 (upload), FR-011 (dedup), FR-012 (progress), SC-003 (ingestion <3 min).
**State transitions**: pending → processing → complete/failed.

---

## New Concepts (Not Persisted in Database)

### Smoke Check (runtime — output of smoke_test.py)

An individual verification step in the smoke test suite.

| Field | Type | Description |
|-------|------|-------------|
| number | int | Sequential check number (1-13) |
| name | string | Human-readable check name |
| result | enum | PASS, FAIL |
| elapsed_seconds | float | Time taken for this check |
| error_message | string? | Error details if FAIL |

**Used by**: FR-022 (smoke test), FR-023 (exit codes), FR-024 (check results).
**Not persisted**: Printed to stdout; only the aggregate exit code matters for automation.

### Fix Entry (persisted in docs/fixes-log.md)

A record of a bug found and resolved during spec-21.

| Field | Type | Description |
|-------|------|-------------|
| title | string | Short fix title |
| symptom | string | What the developer observed |
| root_cause | string | Why it happened |
| fix_applied | string | What was changed |
| files_modified | list[string] | Files changed |
| phase | string | Which implementation phase |

**Used by**: FR-025 (all fixes documented), SC-008 (fixes log complete).
**Persisted as**: Markdown in `docs/fixes-log.md`, not database records.

---

## Schema Changes

**None.** Spec-21 does not modify any database tables, columns, or indices.
All 7 existing SQLite tables remain unchanged:
- `collections`, `documents`, `ingestion_jobs`, `parent_chunks`
- `query_traces`, `settings`, `providers`
