# Data Model: Ingestion Pipeline

**Branch**: `006-ingestion-pipeline` | **Date**: 2026-03-13 | **Plan**: [plan.md](plan.md)

## Entity Relationship Overview

```
Collection (existing)
  │
  ├── 1:N ── Document
  │              │
  │              ├── 1:N ── IngestionJob
  │              │
  │              ├── 1:N ── ParentChunk (SQLite)
  │              │              │
  │              │              └── 1:N ── ChildChunk (Qdrant vector)
  │              │
  │              └── file_hash unique per collection
  │
  └── Qdrant collection (vectors)
```

---

## Entities

### Document (SQLite — `documents` table)

Tracks an uploaded file within a collection. Migrated from Phase 1 schema.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID4 identifier |
| `collection_id` | TEXT | NOT NULL, FK → collections(id) | Single collection membership |
| `filename` | TEXT | NOT NULL | Original filename |
| `file_hash` | TEXT | NOT NULL | SHA256 hex digest of file content |
| `status` | TEXT | NOT NULL | Current ingestion status |
| `chunk_count` | INTEGER | DEFAULT 0 | Count of child chunks indexed |
| `created_at` | TEXT | NOT NULL | ISO8601 upload timestamp |
| `ingested_at` | TEXT | | ISO8601 completion timestamp |

**Unique constraint**: `(collection_id, file_hash)` — prevents duplicate files per collection.

**Status values**: `pending` | `ingesting` | `completed` | `failed` | `duplicate`

**State transitions**:

```
                    ┌──────────┐
  Upload ──────────►│  pending  │
                    └────┬─────┘
                         │ pipeline starts
                         ▼
                    ┌──────────┐
                    │ ingesting │◄──── re-ingest (failed doc)
                    └────┬─────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         ┌─────────┐ ┌────────┐ ┌──────────┐
         │completed │ │ failed │ │duplicate │
         └─────────┘ └────────┘ └──────────┘
              │                      ▲
              │   same hash,         │
              │   same collection    │
              └──────────────────────┘
```

**Migration from Phase 1**:

| Phase 1 Column | Phase 2 Column | Mapping |
|---------------|---------------|---------|
| `name` | `filename` | Direct rename |
| `collection_ids` (JSON array) | `collection_id` (TEXT) | Extract first element |
| — | `file_hash` | Set to `''` for legacy rows |
| — | `chunk_count` | Set to `0` for legacy rows |
| `indexed` status | `completed` | Value mapping |
| `uploaded`/`parsing`/`indexing` | `pending` | Value mapping |
| `upload_date` | `created_at` | Direct rename |
| — | `ingested_at` | Set to NULL for legacy rows |

---

### IngestionJob (SQLite — `ingestion_jobs` table)

Tracks the lifecycle of processing a single document through the ingestion pipeline.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID4 job identifier |
| `document_id` | TEXT | NOT NULL, FK → documents(id) | Associated document |
| `status` | TEXT | NOT NULL | Current job status |
| `started_at` | TEXT | NOT NULL | ISO8601 start timestamp |
| `finished_at` | TEXT | | ISO8601 completion timestamp |
| `error_msg` | TEXT | | Error details if failed |
| `chunks_processed` | INTEGER | DEFAULT 0 | Child chunks successfully embedded and upserted |
| `chunks_skipped` | INTEGER | DEFAULT 0 | Chunks skipped due to validation failure |

**Status values**: `started` | `streaming` | `embedding` | `completed` | `failed` | `paused`

**State transitions**:

```
         ┌─────────┐
  Create ►│ started │
         └────┬────┘
              │ worker spawned
              ▼
         ┌───────────┐
         │ streaming  │ ◄── worker sending NDJSON
         └────┬──────┘
              │ all chunks received
              ▼
         ┌───────────┐
         │ embedding  │ ◄── parallel batch embedding
         └────┬──────┘
              │
    ┌─────────┼─────────┬──────────┐
    ▼         ▼         ▼          ▼
┌─────────┐ ┌────────┐ ┌────────┐
│completed│ │ failed │ │ paused │
└─────────┘ └────────┘ └───┬────┘
                            │ service recovers
                            ▼
                       (resume from embedding)
```

**Pause triggers**:
- Qdrant unreachable AND upsert buffer full (1,000 points)
- Ollama embedding service unreachable (circuit breaker open)

**Resume**: Automatic when the service recovers (connection/circuit breaker probe succeeds).

---

### ParentChunk (SQLite — `parent_chunks` table)

Large text segment (~2000-4000 chars) representing approximately one page of a document. Read by the ResearchGraph via `ParentStore.get_by_ids()` to provide full context for LLM answer generation.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID5 deterministic ID |
| `collection_id` | TEXT | NOT NULL, FK → collections(id) | Collection membership |
| `document_id` | TEXT | NOT NULL, FK → documents(id) | Source document |
| `text` | TEXT | NOT NULL | Full parent chunk text |
| `source_file` | TEXT | NOT NULL | Original filename |
| `page` | INTEGER | | Page number (1-indexed for PDF, section index for others) |
| `breadcrumb` | TEXT | | Heading hierarchy path (e.g., "Chapter 2 > 2.3 Auth") |
| `created_at` | TEXT | NOT NULL | ISO8601 creation timestamp |

**Indexes**:
- `idx_parent_chunks_collection` on `collection_id`
- `idx_parent_chunks_document` on `document_id`

**ParentStore compatibility**: The existing `ParentStore.get_by_ids()` queries flat columns (`parent_id`, `text`, `source_file`, `page`, `breadcrumb`, `collection`). After migration, the column names change to `id`, `text`, `source_file`, `page`, `breadcrumb`, `collection_id`. The query in `parent_store.py` must be updated to match.

---

### ChildChunk (Qdrant — vector points)

Small text segment (~500 chars) derived from a parent chunk, with a breadcrumb prefix. Stored as a vector point in Qdrant for dense + BM25 hybrid retrieval.

| Field | Storage | Description |
|-------|---------|-------------|
| Point ID | Qdrant point ID | UUID5: `uuid5(namespace, "source_file:page:chunk_index")` |
| Vector | Qdrant vector | Embedding of breadcrumb-prefixed child text |
| `parent_id` | Qdrant payload | UUID5 of the parent chunk (links to SQLite) |
| `source_file` | Qdrant payload | Original filename |
| `page` | Qdrant payload | Page number |
| `chunk_index` | Qdrant payload | Position within the page |
| `breadcrumb` | Qdrant payload | Heading hierarchy path |
| `text` | Qdrant payload | Raw child text (without breadcrumb prefix) |
| `collection_id` | Qdrant payload | Collection identifier |
| `document_id` | Qdrant payload | Document identifier |

**Deterministic ID formula**: `uuid5(EMBEDINATOR_NAMESPACE, f"{source_file}:{page}:{chunk_index}")`

**Idempotent upserts**: Same source_file + page + chunk_index always produces the same point ID. Re-ingesting a file with unchanged pages overwrites in place without creating duplicates.

---

### NativeWorkerOutput (Transient — not persisted)

Structured text chunk produced by the Rust ingestion worker, streamed as NDJSON via stdout. Consumed by the Python pipeline and transformed into parent/child chunks.

| Field | Type | Description |
|-------|------|-------------|
| `text` | String | Raw extracted text content |
| `page` | Integer | Page number (1-indexed) |
| `section` | String | Current section heading |
| `heading_path` | String[] | Full heading hierarchy from root |
| `doc_type` | String | `"prose"` or `"code"` |
| `chunk_profile` | String | `"default"` (reserved for future profiles) |
| `chunk_index` | Integer | Global chunk index within the document |

---

## Validation Rules

### Document Upload Validation

| Rule | Check | Error |
|------|-------|-------|
| Supported file type | Extension in allowlist (12 types) | HTTP 400 `INVALID_FILE` |
| File size limit | ≤ 100MB | HTTP 413 |
| MIME type (PDF only) | `application/pdf` | HTTP 400 `INVALID_FILE` |
| Duplicate detection | SHA256 hash + collection_id + status=completed | HTTP 409 `DUPLICATE_DOCUMENT` |

### Embedding Validation

| Rule | Check | Error Action |
|------|-------|-------------|
| Correct dimensions | `len(vector) == expected_dim` | Skip chunk, log reason |
| No NaN values | `not any(isnan(v) for v in vector)` | Skip chunk, log reason |
| Non-zero vector | `not all(v == 0 for v in vector)` | Skip chunk, log reason |
| Minimum magnitude | `sqrt(sum(v² for v)) >= 1e-6` | Skip chunk, log reason |

### Chunking Validation

| Rule | Target |
|------|--------|
| Parent chunk size | 2000-4000 characters |
| Child chunk size | ~500 characters |
| Breadcrumb prefix | `[heading > path]` format, adds ~50 chars |

---

## Cascade Behavior

| Event | Effect |
|-------|--------|
| Collection deleted | Documents cascade delete → IngestionJobs cascade delete → ParentChunks cascade delete. Qdrant collection deleted (all child vectors removed). |
| Document deleted | IngestionJobs cascade delete → ParentChunks cascade delete. Qdrant points filtered by `document_id` and deleted. |
| Document re-ingested (changed hash) | Old Qdrant points deleted by `source_file` filter. Old parent chunks deleted by `document_id`. New chunks created with potentially same UUID5 IDs (idempotent overwrite for unchanged content). |
