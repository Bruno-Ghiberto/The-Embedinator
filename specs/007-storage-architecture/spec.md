# Feature Specification: Storage Architecture

**Feature Branch**: `007-storage-architecture`
**Created**: 2026-03-13
**Status**: Ready
**Input**: Implement the storage architecture with Qdrant for vector search and SQLite for metadata management

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Ingestion Pipeline Stores Documents and Chunks (Priority: P1)

The ingestion worker processes documents, extracts parent chunks, computes embeddings for child chunks, and stores metadata in SQLite while uploading vectors to Qdrant. The storage layer must track document state, prevent duplicates, and link child vectors to parent context via deterministic IDs.

**Why this priority**: Core to the entire RAG system. Without reliable storage, documents cannot be ingested or retrieved.

**Independent Test**: Can be fully tested by: (1) Upload a document to a collection, (2) Verify documents table has the record with correct file_hash and status, (3) Verify parent_chunks table has parent text with UUID5 ID, (4) Verify Qdrant has child vectors with parent_id payload linking back to SQLite.

**Acceptance Scenarios**:

1. **Given** an empty collection, **When** ingesting a 5-page PDF, **Then** documents table has 1 record, ingestion_jobs table tracks the job status, parent_chunks table has 10-20 parent records, and Qdrant has 50-100 child vectors, all linked via parent_id.
2. **Given** a document already ingested, **When** re-ingesting the same file (same file_hash), **Then** the document is marked as duplicate and not re-processed.

---

### User Story 2 - Chat/Search Retrieves Parent Chunks and Metadata (Priority: P1)

When answering a user query, the chat system retrieves child vectors from Qdrant, looks up parent chunk text from SQLite, and includes breadcrumb/source metadata. The parent-child relationship must be reliable and fast.

**Why this priority**: Equally critical as ingestion. Search retrieval is the primary read path for end users.

**Independent Test**: Can be fully tested by: (1) Upload a document with known content, (2) Query with terms matching that content, (3) Verify Qdrant returns child vectors with parent_id payloads, (4) Verify parent_store retrieves full parent text from SQLite by parent_id, (5) Verify answer generation has full context.

**Acceptance Scenarios**:

1. **Given** a collection with indexed documents, **When** searching for a query, **Then** Qdrant returns top-k child chunks with parent_id in payload.
2. **Given** child chunk results, **When** fetching parent chunks from SQLite, **Then** parent_store.get_by_ids() returns parent text and metadata in < 10ms per request.

---

### User Story 3 - Query Observability Traces All Searches (Priority: P2)

Every chat query generates a trace record in SQLite, capturing the query text, sub-questions, collections searched, chunks retrieved, confidence score, and latency. This enables observability dashboards and debugging.

**Why this priority**: Observability is secondary to core functionality but required for production monitoring and user support.

**Independent Test**: Can be fully tested by: (1) Execute a chat query, (2) Verify query_traces table has a new record with all fields populated, (3) Verify timestamps and latency_ms are accurate, (4) Verify confidence_score reflects retrieval quality.

**Acceptance Scenarios**:

1. **Given** a completed query, **When** checking query_traces table, **Then** a new record exists with query text, session_id, collections_searched (JSON), chunks_retrieved_json, confidence_score, and latency_ms.
2. **Given** multiple queries in a session, **When** filtering traces by session_id, **Then** all queries are returned in chronological order.

---

### User Story 4 - Multi-Provider LLM Support with Encrypted Keys (Priority: P2)

The system supports multiple LLM providers (Ollama, OpenRouter, OpenAI, Anthropic, Google). API keys are encrypted at rest in the providers table and decrypted only in memory when making requests.

**Why this priority**: Enables flexible LLM switching and security best practice. Secondary to core RAG but required for production security.

**Independent Test**: Can be fully tested by: (1) Store an API key via settings UI, (2) Verify it's encrypted in providers table (not plaintext), (3) Verify backend can decrypt and use the key, (4) Verify deleted keys cannot be recovered.

**Acceptance Scenarios**:

1. **Given** a new provider configuration, **When** storing an API key, **Then** the providers table stores api_key_encrypted (not plaintext), and is_active reflects reachability.
2. **Given** an encrypted key, **When** backend loads it, **Then** it's decrypted in memory only (never stored decrypted in logs or cache).

### Edge Cases

- What happens when a document's file_hash already exists in a different collection? → Must allow (same file can be in multiple collections; unique constraint is on collection_id + file_hash).
- How does the system handle Qdrant being unavailable during search? → Should return error to user; SQLite metadata is still readable for fallback behavior. During ingestion batch upsert, if Qdrant fails (even mid-batch), entire batch is marked failed; orchestrator retries full batch when Qdrant recovers (safe via UUID5 idempotent upserts).
- What if an ingestion job fails halfway through? → Partial data persists; job marked as failed in ingestion_jobs; orchestrator can resume. UUID5 determinism ensures safe re-runs: duplicate vectors skipped (Qdrant upsert replaces), duplicate parent chunks detected by uniqueness. See Clarifications for recovery strategy.
- How are query traces archived? → Traces grow indefinitely; optional cleanup policy can be configured (not in scope of initial feature, but schema must support it).

## Requirements *(mandatory)*

<!--
  ACTION REQUIRED: The content in this section represents placeholders.
  Fill them out with the right functional requirements.
-->

### Functional Requirements

- **FR-001**: System MUST create a `collections` table tracking user-defined collections with fields: id (UUID4), name (unique), description, embedding_model, chunk_profile, qdrant_collection_name (unique), created_at.

- **FR-002**: System MUST create a `documents` table tracking ingested files with fields: id (UUID4), collection_id (FK), filename, file_path, file_hash (SHA256), status (pending|ingesting|completed|failed|duplicate), chunk_count, ingested_at, and UNIQUE(collection_id, file_hash) constraint.

- **FR-003**: System MUST create an `ingestion_jobs` table tracking job status with fields: id (UUID4), document_id (FK), status (started|streaming|embedding|completed|failed|paused), started_at, finished_at, error_msg, chunks_processed, chunks_skipped.

- **FR-004**: System MUST create a `parent_chunks` table storing full-context text with fields: id (UUID5 deterministic), collection_id (FK), document_id (FK), text (2000-4000 chars), metadata_json (page, section, breadcrumb, source_file), created_at, and indexes on (collection_id, document_id).

- **FR-005**: System MUST create a `query_traces` table for observability with fields: id (UUID4), session_id, query, sub_questions_json, collections_searched (JSON), chunks_retrieved_json, reasoning_steps_json (JSON), strategy_switches_json (JSON), meta_reasoning_triggered, latency_ms, llm_model, embed_model, confidence_score (0–100 integer), created_at, and indexes on (session_id, created_at).

- **FR-006**: System MUST create a `settings` table for key-value configuration: key (TEXT PRIMARY KEY), value (TEXT).

- **FR-007**: System MUST create a `providers` table for encrypted API key storage with fields: name (PRIMARY KEY), api_key_encrypted (Fernet-encrypted or NULL for Ollama), base_url, is_active, created_at.

- **FR-008**: SQLite MUST run with PRAGMA journal_mode=WAL to enable concurrent readers with a single serialized writer.

- **FR-009**: SQLite MUST run with PRAGMA foreign_keys=ON to enforce referential integrity across all tables.

- **FR-010**: Qdrant collection initialization MUST create both `dense` vector config (e.g., 768 dims, cosine distance) and `sparse` vector config (BM25 with IDF modifier) for hybrid search.

- **FR-011**: Each Qdrant point (child chunk) MUST carry payload with: text, parent_id (linking to SQLite parent_chunks.id), breadcrumb, source_file, page, chunk_index, doc_type (Prose or Code), chunk_hash, embedding_model, collection_name, ingested_at.

- **FR-012**: System MUST generate deterministic UUID5 IDs for parent_chunks based on content identity to enable idempotent upserts.

- **FR-013**: System MUST encrypt API keys using Fernet symmetric encryption before storage in the providers table.

- **FR-014**: System MUST support querying parent chunks by ID list from SQLite with column aliases for schema flexibility (id AS parent_id, collection_id AS collection).

- **FR-015**: Concurrent ingestion jobs MUST be processed sequentially via a memory queue at the orchestrator level. If one job fails, it MUST be logged but MUST NOT block subsequent jobs in the queue. *(Queue implementation owned by spec-06 ingestion pipeline orchestrator; spec-07 storage layer supports this via `ingestion_jobs` status tracking.)*

- **FR-016**: Ingestion jobs MUST be resumable: UUID5 deterministic parent IDs enable idempotent re-runs. Duplicate Qdrant vectors are skipped (upsert replaces), and duplicate SQLite parent chunks are detected by UUID5 uniqueness constraint. Failed jobs marked in ingestion_jobs table; orchestrator can resume without explicit rollback.

### Key Entities

- **Collection**: A user-defined grouping of documents. Contains metadata (name, description, embedding model, Qdrant collection name). Maps to one Qdrant collection.

- **Document**: A single ingested file. Tracks filename, file_hash (for deduplication), ingestion status, and chunk count. Links to collection via collection_id.

- **Parent Chunk**: A 2000-4000 character segment of a document. Stored in SQLite for full-context LLM retrieval. ID is UUID5 deterministic based on content. Carries metadata (page, breadcrumb, source_file) in JSON.

- **Child Chunk**: A smaller segment of a parent chunk (~300 chars). Stored as a vector in Qdrant. Carries parent_id payload field linking back to SQLite parent_chunks.id.

- **Ingestion Job**: Tracks the state of ingesting a single document. Logs start time, completion time, error messages, and counts of chunks processed/skipped.

- **Query Trace**: Records metadata about every chat query for observability. Captures query text, sub-questions, collections searched, chunks retrieved, confidence score, and latency.

- **Provider**: Configuration for a single LLM provider (Ollama, OpenRouter, OpenAI, Anthropic, Google). Stores provider name, encrypted API key, optional base_url override, and active status.

## Success Criteria *(mandatory)*

<!--
  ACTION REQUIRED: Define measurable success criteria.
  These must be technology-agnostic and measurable.
-->

### Measurable Outcomes

- **SC-001**: All seven SQLite tables (collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers) are created with correct column types, constraints, and indexes.

- **SC-002**: SQLite WAL mode is enabled and foreign key enforcement is active (verified via PRAGMA queries).

- **SC-003**: Parent chunk UUID5 IDs are deterministic and reproducible—identical content always generates the same ID.

- **SC-004**: Qdrant collection initialization creates both dense and sparse vector configurations with correct parameters (dense: 768 dims, cosine; sparse: BM25).

- **SC-005**: Child chunks in Qdrant carry all required payload fields (text, parent_id, breadcrumb, source_file, page, chunk_index, doc_type, chunk_hash, embedding_model, collection_name, ingested_at).

- **SC-006**: Parent chunk retrieval from SQLite by ID list completes in under 10ms for lists of up to 100 chunks.

- **SC-007**: Document ingestion prevents duplicates—re-ingesting a file with the same file_hash marks it as duplicate in documents table.

- **SC-008**: Concurrent reads to SQLite proceed without blocking (WAL mode concurrency verified).

- **SC-009**: API keys are encrypted in providers table and decrypted only in memory; no plaintext keys appear in logs or database exports.

- **SC-010**: Query traces are recorded for every chat query with all fields populated (query, session_id, confidence_score (0–100 integer), latency_ms, collections_searched, chunks_retrieved_json, reasoning_steps_json, strategy_switches_json).

- **SC-011**: Qdrant-SQLite cross-references are consistent—every parent_id in Qdrant resolves to a row in parent_chunks; every document_id in parent_chunks resolves to a row in documents.

## Clarifications

### Session 2026-03-13

- Q: What are the target deployment scales—how many documents/chunks per collection, and expected monthly growth? → A: Medium scale: 1K-10K documents per collection, <1K chunks per document. This scale supports research depth while keeping SQLite WAL performance acceptable; aligns with "self-hosted single-user system" model.

- Q: If two ingestion jobs try to write simultaneously, should they queue sequentially, fail fast, or use optimistic locking? → A: Sequential Queue. Jobs are queued in memory by the ingestion orchestrator; system processes one document at a time. Failed jobs are logged but do not block subsequent jobs. Aligns with typical document pipeline architecture.

- Q: If an ingestion job fails after writing some chunks to Qdrant, should it rollback, resume from checkpoint, or require manual cleanup? → A: Idempotent Resume. UUID5 deterministic parent IDs enable safe re-runs: duplicate Qdrant vectors are skipped (upsert replaces), duplicate SQLite parent chunks detected by UUID5 uniqueness. Failed jobs persist partial data; orchestrator can resume without explicit rollback.

- Q: If Qdrant fails mid-batch upsert (e.g., 30 of 50 vectors uploaded, then timeout), should the job fail entirely, retry only failed vectors, or use circuit breaker fallback? → A: Fail Entire Batch. Batch failure is simplest strategy; UUID5 idempotent upserts make retry safe (duplicates skipped). Per-vector tracking adds complexity; circuit breaker is app-level concern (Spec 05). Batch retry allows orchestrator to resume when Qdrant recovers.

- Q: Should query trace archival be fully out-of-scope, define baseline retention policy, or include archival interface placeholder? → A: Fully Out-of-Scope. Traces stored for observability (P2 priority); users manage archival externally via SQL dumps/cron. Medium-scale deployment won't hit storage constraints; deferring archival avoids over-engineering. Schema supports external archival; future retention policies can be added without schema changes.

## Assumptions

- **Data Scale**: Medium deployment (1K-10K documents per collection, <1K chunks per document). See Clarifications for scale rationale.
- SQLite 3.45+ is available in the deployment environment (supports WAL mode).
- Qdrant is configured externally (Docker container or remote service); this spec defines client-side schema only.
- API key encryption uses Fernet (symmetric key derived from environment).
- Parent chunk size is 2000-4000 characters (per ADR-005); child chunks are ~500 characters for vector embedding (per Constitution Principle III).
- File hashing uses SHA256 for duplicate detection.
- Document types are limited to Prose and Code (not mixed or tables).
- Single-user / small-team deployment (SQLite write serialization is acceptable).
- Query trace cleanup/archival is out of scope; traces grow indefinitely but can be archived by external processes.

## Dependencies

**Internal specs**:
- Spec 02 (ConversationGraph): Requires separate checkpoints.db via LangGraph checkpointer.
- Spec 03 (ResearchGraph): Requires parent chunk retrieval and breadcrumb metadata.
- Spec 04 (MetaReasoningGraph): Requires confidence_score and strategy tracking in query context.
- Spec 05 (Accuracy/Robustness): Requires circuit breaker support (application-level; no schema changes).
- Spec 06 (Ingestion Pipeline): Writes to documents, ingestion_jobs, parent_chunks, and Qdrant.

**External libraries**:
- `qdrant-client >=1.17.0`: Vector database client with sparse vector support.
- `aiosqlite >=0.21`: Async SQLite access.
- `cryptography >=44.0`: Fernet encryption for API keys.
