# Data Model: Storage Architecture

**Date**: 2026-03-13 | **Phase**: Phase 1 Design | **Spec**: [spec.md](spec.md)

## Entity Relationship Diagram

```
Collections (1)
    └── (1:N) Documents
            └── (1:N) IngestionJobs
            └── (1:N) ParentChunks
                    └── (1:N) ChildChunks in Qdrant [via parent_id payload]
    └── (1:N) QueryTraces

ParentChunks
    └── (1:N) QueryTraces [via chunks_retrieved_json]

Providers (isolated, no FK)
Settings (isolated, no FK)
```

## Entities

### 1. Collection

**Purpose**: User-defined grouping of documents within embedinator.db. Maps to one Qdrant collection.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| id | UUID4 | PRIMARY KEY | Auto-generated |
| name | TEXT | UNIQUE, NOT NULL | Human-readable collection name |
| description | TEXT | Optional | Markdown-friendly description |
| embedding_model | TEXT | NOT NULL | e.g., "all-MiniLM-L6-v2" |
| chunk_profile | TEXT | NOT NULL | Configuration profile (e.g., "default", "code-heavy") |
| qdrant_collection_name | TEXT | UNIQUE, NOT NULL | Qdrant collection identifier |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |

**Validation Rules**:
- name must be alphanumeric + underscore, 1–256 chars
- embedding_model must match one of supported sentence-transformers models
- qdrant_collection_name must match Qdrant naming rules (alphanumeric + underscore)

**State Lifecycle**:
- Created → Active (default) → Optional future: Archived (if archival feature added)

---

### 2. Document

**Purpose**: Single ingested file within a collection. Tracks filename, file_hash, ingestion status, and chunk count.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| id | UUID4 | PRIMARY KEY | Auto-generated |
| collection_id | UUID4 | FOREIGN KEY → Collection.id | NOT NULL |
| filename | TEXT | NOT NULL | Original filename (e.g., "report.pdf") |
| file_path | TEXT | Optional | Path used during ingestion |
| file_hash | TEXT | NOT NULL | SHA256 hash for deduplication |
| status | TEXT | Enum: pending\|ingesting\|completed\|failed\|duplicate | Default: pending |
| chunk_count | INTEGER | Default: 0 | Number of parent chunks extracted |
| ingested_at | TIMESTAMP | Optional | Completion timestamp |
| UNIQUE | (collection_id, file_hash) | Compound | Prevent duplicates per collection |

**Validation Rules**:
- file_hash must be SHA256 (64 hex chars)
- chunk_count >= 0
- status transitions: pending → (ingesting|failed|duplicate) → (completed|failed)

**State Lifecycle**:
- pending (initial) → ingesting (processing) → completed (success) | failed (error) | duplicate (already present)

**Duplicate Detection**:
- If re-ingesting file with same file_hash in same collection_id, mark as duplicate
- File can exist in multiple collections (different collection_id, same file_hash is allowed)

---

### 3. IngestionJob

**Purpose**: Tracks status of ingesting a single document. Records started_at, finished_at, error messages, and chunk counts.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| id | UUID4 | PRIMARY KEY | Auto-generated |
| document_id | UUID4 | FOREIGN KEY → Document.id | NOT NULL |
| status | TEXT | Enum: started\|streaming\|embedding\|completed\|failed\|paused | Default: started |
| started_at | TIMESTAMP | NOT NULL | Job start time |
| finished_at | TIMESTAMP | Optional | Job completion time |
| error_msg | TEXT | Optional | Error message if failed |
| chunks_processed | INTEGER | Default: 0 | Count of successfully processed chunks |
| chunks_skipped | INTEGER | Default: 0 | Count of skipped chunks (e.g., empty, duplicates) |

**Validation Rules**:
- started_at must be before finished_at (if finished_at present)
- chunks_processed >= 0, chunks_skipped >= 0
- error_msg required if status=failed

**State Lifecycle**:
- started → (streaming → embedding → completed) | (streaming → failed) | paused
- Resumable: Job marked as paused or failed; orchestrator can resume without rollback (idempotent via UUID5)

**Idempotent Resume**:
- Job failure persists partial data
- UUID5 determinism ensures safe re-run: duplicate Qdrant vectors skipped (upsert), duplicate parent chunks detected (UUID5 uniqueness constraint)
- Orchestrator retries failed batch when ready

---

### 4. ParentChunk

**Purpose**: Full-context text segment (2000–4000 chars) stored in SQLite. Links to Document and Collection. Retrieved by UUID5 ID during search.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| id | UUID5 | PRIMARY KEY | Deterministic, content-based |
| collection_id | UUID4 | FOREIGN KEY → Collection.id | NOT NULL |
| document_id | UUID4 | FOREIGN KEY → Document.id | NOT NULL |
| text | TEXT | NOT NULL | Full-context text (2000–4000 chars) |
| metadata_json | JSON | Optional | {page: int, section: str, breadcrumb: str, source_file: str} |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation time |
| INDEX | (collection_id, document_id) | Compound | Fast lookup by collection/doc |

**Validation Rules**:
- id must be UUID5 (deterministic from content hash)
- text length 2000–4000 chars
- metadata_json must be valid JSON if present
- collection_id and document_id must exist

**UUID5 Determinism**:
- ID computed from hash of (collection_id || document_id || text_content)
- Same content always produces same UUID5 → idempotent upserts
- Duplicate insert rejected by PRIMARY KEY constraint (safe for resume)

**Relationship to Child Chunks**:
- Child chunks stored in Qdrant with parent_id payload field
- Payload points to this ParentChunk.id
- Search retrieval: Qdrant returns child vector + parent_id → SQLite lookup via id

---

### 5. QueryTrace

**Purpose**: Observability record for every chat query. Captures query text, collections searched, chunks retrieved, confidence score, and latency.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| id | UUID4 | PRIMARY KEY | Auto-generated |
| session_id | TEXT | NOT NULL | User session identifier |
| query | TEXT | NOT NULL | Original user query text |
| sub_questions_json | JSON | Optional | Array of decomposed sub-questions |
| collections_searched | JSON | NOT NULL | Array of collection IDs searched |
| chunks_retrieved_json | JSON | NOT NULL | Array of {parent_id, chunk_text, score, breadcrumb} |
| meta_reasoning_triggered | BOOLEAN | Default: FALSE | Whether meta-reasoning strategy ran |
| latency_ms | INTEGER | NOT NULL | Total query latency in milliseconds |
| llm_model | TEXT | Optional | LLM model used for answer generation |
| embed_model | TEXT | Optional | Embedding model used for search |
| confidence_score | FLOAT | Range: 0.0–1.0 | Search confidence (5-signal aggregation) |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Query timestamp |
| INDEX | (session_id, created_at) | Compound | Fast filtering by session + time |

**Validation Rules**:
- session_id must be non-empty
- query must be non-empty
- collections_searched valid JSON array
- chunks_retrieved_json valid JSON array
- latency_ms >= 0
- confidence_score 0.0–1.0

**Data Retention**:
- No automatic archival in scope (P2 priority deferred)
- Users manage cleanup via external SQL dumps or cron
- Schema supports future retention policies without changes

**Observability Use Cases**:
- Dashboard: Average latency by collection, success rate by time window
- Debugging: Full query context for support requests
- Analytics: Confidence score distribution, meta-reasoning frequency

---

### 6. Settings

**Purpose**: Key-value configuration store for system and user preferences.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| key | TEXT | PRIMARY KEY | Configuration key (e.g., "max_ingestion_batch_size") |
| value | TEXT | NOT NULL | Configuration value (JSON-serializable) |

**Validation Rules**:
- key must be alphanumeric + underscore, 1–256 chars
- value must be valid for the key's type (string, int, JSON, etc.)

**Common Keys** (examples, not exhaustive):
- `max_ingestion_batch_size`: Integer (default: 100)
- `qdrant_timeout_ms`: Integer (default: 5000)
- `confidence_threshold`: Integer 0–100 (default: 60)
- `meta_reasoning_enabled`: Boolean (default: true)

**Lifecycle**:
- Insert on first use, update as needed
- No deletion required (deactivate by setting value to disabled/false)

---

### 7. Provider

**Purpose**: Encrypted storage for LLM provider API keys and configuration.

| Field | Type | Constraints | Notes |
|-------|------|-----------|-------|
| name | TEXT | PRIMARY KEY | Provider identifier (e.g., "openai", "ollama") |
| api_key_encrypted | TEXT | Optional | Fernet-encrypted API key (NULL for Ollama) |
| base_url | TEXT | Optional | Custom base URL (e.g., for self-hosted Ollama) |
| is_active | BOOLEAN | Default: TRUE | Whether provider is enabled for use |
| created_at | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Configuration creation time |

**Validation Rules**:
- name must be alphanumeric + underscore (provider identifier)
- api_key_encrypted must be valid Fernet ciphertext if not NULL
- base_url must be valid HTTPS URL if provided
- is_active boolean

**Encryption**:
- API keys encrypted with Fernet (symmetric key from environment)
- Decrypted only in memory when making requests
- Never stored plaintext or logged
- Failed decrypt returns error; request aborted

**Supported Providers** (examples):
- ollama (base_url = "http://localhost:11434", no api_key)
- openai (api_key_encrypted required)
- openrouter (api_key_encrypted required)
- anthropic (api_key_encrypted required)
- google (api_key_encrypted required)

**Lifecycle**:
- Created on user configuration
- is_active toggled to disable temporarily
- Deleted when user removes provider (hard delete, no archival)

---

## Schema Constraints

### Foreign Keys (enforced via PRAGMA foreign_keys=ON)

- Document.collection_id → Collection.id (CASCADE on delete)
- IngestionJob.document_id → Document.id (CASCADE on delete)
- ParentChunk.collection_id → Collection.id (CASCADE on delete)
- ParentChunk.document_id → Document.id (CASCADE on delete)

### Indexes (for performance)

- Collection(qdrant_collection_name) — unique constraint
- Document(collection_id, file_hash) — compound unique
- Document(collection_id) — fast filter by collection
- ParentChunk(collection_id, document_id) — fast lookup within document
- ParentChunk(id) — PRIMARY KEY (automatic)
- QueryTrace(session_id, created_at) — fast filtering by session + time
- QueryTrace(created_at) — optional, for archival/cleanup queries

### SQLite Configuration

- PRAGMA journal_mode=WAL — concurrent readers, single serialized writer
- PRAGMA foreign_keys=ON — referential integrity enforcement
- PRAGMA synchronous=NORMAL — balance durability and performance

---

## Qdrant Vector Schema (Parallel Storage)

Each Qdrant point (child chunk) carries payload linking back to SQLite:

```json
{
  "id": "qdrant_point_id",
  "vector": [0.123, 0.456, ...],  // dense embedding (768 dims)
  "payload": {
    "text": "child chunk text (~300 chars)",
    "parent_id": "uuid5_of_parent_chunk",
    "breadcrumb": "Collection > Document > Section",
    "source_file": "report.pdf",
    "page": 3,
    "chunk_index": 5,
    "doc_type": "Prose|Code",
    "chunk_hash": "sha256_of_chunk_text",
    "embedding_model": "all-MiniLM-L6-v2",
    "collection_name": "qdrant_collection_name",
    "ingested_at": "2026-03-13T10:00:00Z"
  }
}
```

**Qdrant Collection Creation**:
- Dense vectors: 768 dimensions, cosine distance
- Sparse vectors: BM25 with IDF modifier for keyword search
- Hybrid search combines both via rank fusion

---

## Data Consistency

### Idempotency via UUID5

- ParentChunk.id = UUID5(collection_id || document_id || text_content)
- Same content → same ID → duplicate insert rejected
- Safe to retry failed ingestion jobs: duplicate chunks skipped, existing vectors replaced

### Dual-Store Consistency

- Qdrant child chunks link via parent_id payload
- SQLite parent_chunks table is source of truth for text
- Search flow: Qdrant → parent_ids → SQLite lookup
- All parent_ids in Qdrant must resolve to parent_chunks rows (verified in tests)

### Sequential Writes

- Single-threaded orchestrator processes one document at a time
- Multiple Query Trace inserts allowed (read-only operation for queries)
- Concurrent reads safe via WAL mode

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Parent chunk retrieval by ID list | <10ms per 100 chunks | SQLite indexed on (collection_id, document_id, id) |
| Qdrant hybrid search | <100ms for 100K vectors | Dense + sparse rank fusion |
| Duplicate detection | <5ms | File_hash lookup, indexed |
| Document ingestion (single) | Depends on content size | Sequential queuing, no parallelization |
| Concurrent readers | Unlimited | SQLite WAL mode, no lock contention |
| Query trace insert | <1ms | Append-only, indexed on (session_id, created_at) |

---

## Phase 1 Completion Status

✅ All 7 entities defined with fields, constraints, validation rules, and relationships
✅ UUID5 determinism and idempotency documented
✅ Dual-store architecture (SQLite ↔ Qdrant) clarified
✅ Performance targets specified
✅ Schema constraints and indexes documented
✅ Data consistency guarantees articulated

**Ready for Phase 1b (Contract Definitions) and Phase 2 (Implementation Tasks)**
