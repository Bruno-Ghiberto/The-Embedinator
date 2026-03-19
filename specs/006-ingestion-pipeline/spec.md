# Feature Specification: Ingestion Pipeline

**Feature Branch**: `006-ingestion-pipeline`
**Created**: 2026-03-13
**Status**: Draft
**Input**: Ingestion pipeline: document parsing, chunking, embedding, and storage via Python orchestrator and Rust worker

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Upload and Ingest a Document (Priority: P1)

A user uploads a document (PDF, Markdown, plain text, or code file) into a collection. The system parses the document, splits it into searchable chunks with structural breadcrumbs, generates embedding vectors, validates each vector, and stores everything for later retrieval. The user can track the progress of the ingestion job through status updates.

**Why this priority**: This is the core data path — without document ingestion, there is nothing to search or ask questions about. Every other feature depends on documents being parsed, chunked, embedded, and stored.

**Independent Test**: Upload a small PDF to a collection and verify that the document appears as `completed`, child chunks are searchable in the vector store, and parent chunks are retrievable for answer generation.

**Acceptance Scenarios**:

1. **Given** a collection exists, **When** the user uploads a supported file (PDF, Markdown, text, or code) under 100MB, **Then** the system creates a document record (status `pending`) and an ingestion job record (status `started`), and begins processing.
2. **Given** ingestion has started, **When** the document is parsed, **Then** the job status transitions through `started` -> `streaming` -> `embedding` -> `completed` and the document status is set to `completed` with an accurate `chunk_count`.
3. **Given** a 200-page PDF is uploaded, **When** ingestion completes, **Then** parent chunks are 2000-4000 characters each, child chunks are approximately 500 characters each, and each child chunk has a breadcrumb prefix reflecting its position in the document hierarchy.
4. **Given** ingestion is complete, **When** the user queries the collection, **Then** the embedded child chunks are retrievable via vector search and their parent chunks provide full context for answer generation.

---

### User Story 2 - Incremental Re-Ingestion and Duplicate Detection (Priority: P1)

A user re-uploads a document that already exists in a collection. If the file is identical (same SHA256 hash), the system rejects it immediately to avoid redundant work. If the file has changed, the system re-ingests it while ensuring deterministic chunk IDs prevent duplicate entries.

**Why this priority**: Without duplicate detection and incremental re-ingestion, users would accumulate duplicate data, waste processing resources, and get degraded search results. This is essential for any production workflow.

**Independent Test**: Upload a file, then upload the same file again and verify rejection. Modify the file, re-upload, and verify that old data is replaced and new chunks are indexed with the same deterministic IDs for unchanged content.

**Acceptance Scenarios**:

1. **Given** a document with hash H is already `completed` in a collection, **When** the user uploads the same file (hash H), **Then** the system rejects it with a `DUPLICATE_DOCUMENT` error without re-processing.
2. **Given** a document with hash H1 was previously ingested, **When** the user uploads a modified version (hash H2), **Then** the system deletes the old vector points, re-parses the entire document, and re-embeds all chunks. Unchanged chunks produce the same deterministic UUID5 point IDs and overwrite in place.
3. **Given** a document previously failed ingestion, **When** the user re-uploads the same file, **Then** the system allows re-ingestion (retry semantics).
4. **Given** two different collections exist, **When** the user uploads the same file to both, **Then** each collection independently tracks its own document and deduplication is scoped per collection.

---

### User Story 3 - Embedding Validation and Fault Tolerance (Priority: P2)

The system validates every embedding vector before storing it and gracefully handles failures in individual chunks, the parsing worker, or infrastructure services (vector store, embedding service) without losing progress.

**Why this priority**: A single corrupt embedding can degrade search quality for an entire collection. Infrastructure outages during long ingestion jobs must not lose all progress. This story ensures data integrity and operational reliability.

**Independent Test**: Inject a simulated embedding failure for one chunk in a batch and verify the rest of the batch completes successfully. Simulate vector store unavailability during upsert and verify that the job pauses and resumes when connectivity is restored.

**Acceptance Scenarios**:

1. **Given** a batch of chunks is being embedded, **When** one embedding fails validation (wrong dimensions, NaN values, zero vector, or below-threshold magnitude), **Then** the failed chunk is logged with a reason string and skipped, the rest of the batch continues, and the `chunks_skipped` count is incremented.
2. **Given** the parsing worker process crashes mid-document, **When** the pipeline detects the crash, **Then** all successfully parsed chunks are still processed, the job status is set to `failed`, and the error is logged.
3. **Given** the vector store becomes unreachable during ingestion, **When** upserts fail, **Then** the system buffers pending upserts in memory (up to 1,000 points) and flushes them when the connection recovers. If the buffer fills, the job is paused (not aborted) and resumes automatically once connectivity is restored.
4. **Given** the embedding service becomes unreachable during ingestion, **When** embedding calls fail, **Then** the job is paused and retries automatically when the service recovers.

---

### User Story 4 - High-Performance Document Parsing via Native Worker (Priority: P2)

Large documents (100+ pages) are parsed by a native binary worker that streams results incrementally, allowing the pipeline to begin embedding chunks while parsing is still in progress. This overlapping of CPU-bound parsing with network-bound embedding achieves high throughput.

**Why this priority**: Without the native parsing worker, large document ingestion would be bottlenecked by sequential processing. The streaming architecture is essential to meet the throughput targets.

**Independent Test**: Ingest a 200-page PDF and verify that total ingestion time is under 20 seconds, with parsing completing in 2-5 seconds and the pipeline processing chunks concurrently.

**Acceptance Scenarios**:

1. **Given** a 200-page PDF is uploaded, **When** the native worker parses it, **Then** it produces approximately 600 structured text chunks streamed incrementally to the pipeline.
2. **Given** a Markdown file with hierarchical headings, **When** the native worker parses it, **Then** each chunk includes the correct heading hierarchy path for breadcrumb generation.
3. **Given** a code file (e.g., `.py`, `.rs`, `.java`), **When** the native worker parses it, **Then** the chunks are annotated with document type `code` and processed with paragraph-boundary detection.
4. **Given** the file type is not explicitly specified, **When** the native worker receives the file, **Then** it auto-detects the document type from the file extension.

---

### User Story 5 - File Type Validation and Upload Constraints (Priority: P3)

The system enforces strict validation on uploaded files, rejecting unsupported formats and oversized files with clear error messages before any processing begins.

**Why this priority**: Input validation prevents wasted resources and provides immediate feedback. While important, it is a gate before the core pipeline and simpler to implement.

**Independent Test**: Upload files of unsupported types and verify rejection with appropriate error codes. Upload a file exceeding 100MB and verify rejection.

**Acceptance Scenarios**:

1. **Given** a user attempts to upload an unsupported file type (e.g., `.exe`, `.zip`), **When** the upload is received, **Then** the system rejects it with an `INVALID_FILE` error before any processing.
2. **Given** a user attempts to upload a file larger than 100MB, **When** the upload is received, **Then** the system rejects it with a file-too-large error.
3. **Given** a user uploads any of the 12 supported file types (`.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`), **When** the upload is received, **Then** it is accepted and ingestion begins.

---

### User Story 6 - Database Schema Migration from Phase 1 (Priority: P1)

The system migrates the existing simplified database schema from Phase 1 to the production schema required by the ingestion pipeline, including new tables for ingestion job tracking and parent chunk storage. Existing functionality (search, retrieval, document listing) continues to work without regression.

**Why this priority**: The existing database schema is incompatible with the ingestion pipeline requirements. Without migration, no other user stories can function. This is a foundational prerequisite.

**Independent Test**: Run the migration on an existing database with Phase 1 data and verify that collections, documents, and queries still function. Verify that new `ingestion_jobs` and `parent_chunks` tables exist and accept records.

**Acceptance Scenarios**:

1. **Given** an existing database with Phase 1 `documents` table, **When** the application starts, **Then** the `documents` table is migrated to the production schema (single collection foreign key, file hash, chunk count, standardized status values, completion timestamp).
2. **Given** a fresh database, **When** the application starts, **Then** `ingestion_jobs` and `parent_chunks` tables are created automatically alongside the existing tables.
3. **Given** the research graph uses the parent chunk read path, **When** the `parent_chunks` table is created with the new schema, **Then** the existing parent chunk lookup continues to function correctly.
4. **Given** the Phase 1 upload endpoint at a different path, **When** the migration is complete, **Then** the ingestion endpoint is available at the new collection-scoped path and existing document operations (list, get, delete) remain functional.

---

### Edge Cases

- What happens when the native worker binary is not found or not compiled? The system should return a clear error indicating the worker path is misconfigured.
- What happens when a file has zero extractable text (e.g., image-only PDF)? The worker produces zero chunks, the pipeline completes with `chunk_count = 0`, and the document is marked `completed` (not `failed`).
- What happens when the same file is uploaded concurrently to the same collection? The unique constraint on collection + file hash prevents duplicate records; the second upload should be rejected.
- What happens when multiple files are uploaded simultaneously to different collections? All jobs run in parallel, sharing embedding worker threads and native worker processes. Resource limits (configurable max concurrent workers) prevent exhaustion.
- What happens when embedding dimensions change between ingestion runs (e.g., user switches embedding model)? Each collection is tied to an embedding model; validation catches dimension mismatches and skips those chunks.
- What happens when the in-memory upsert buffer (1,000 points) fills and the vector store remains down for an extended period? The job is paused, not aborted. No data is lost. The job resumes automatically when connectivity is restored.
- What happens when a previously ingested document's collection is deleted? Vector points are deleted as part of collection deletion; database foreign keys cascade the delete.
- What happens to Phase 1 documents after schema migration? Their records are preserved in the migrated table. Their vector points (random UUID4 IDs) remain in the vector store as orphans until the user manually re-ingests or deletes those documents.

## Clarifications

### Session 2026-03-13

- Q: Can multiple ingestion jobs run simultaneously? → A: Yes — parallel ingestion with shared resource limits.
- Q: What happens to Phase 1 data during schema migration? → A: Preserve as-is; orphaned vector points remain until manually cleaned.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept multipart file uploads at the collection-scoped ingestion endpoint for 12 supported file types: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`.
- **FR-002**: System MUST reject unsupported file types with a clear `INVALID_FILE` error and files exceeding 100MB with a file-too-large error, before any processing begins.
- **FR-003**: System MUST compute a SHA256 hash of each uploaded file and reject duplicates (same hash in same collection with `completed` status) with a `DUPLICATE_DOCUMENT` error.
- **FR-004**: System MUST allow re-ingestion of previously failed documents (same hash, `failed` status).
- **FR-005**: System MUST delete old vector points and fully re-ingest when a document with a changed hash is re-uploaded to the same collection.
- **FR-006**: System MUST parse documents using a native binary worker that streams structured text chunks incrementally, supporting PDF, Markdown, plain text, and code file types.
- **FR-007**: System MUST split parsed text into parent chunks (2000-4000 characters) and child chunks (~500 characters), prepending a structural breadcrumb prefix to each child chunk reflecting its position in the document hierarchy.
- **FR-008**: System MUST generate deterministic point IDs for each child chunk using a namespace-based identifier scheme keyed on source file, page, and chunk index, ensuring idempotent upserts.
- **FR-009**: System MUST embed child chunks in parallel using configurable worker count (default 4) and batch size (default 16).
- **FR-010**: System MUST validate every embedding vector before storage, checking: correct dimension count, no NaN values, non-zero vector, and magnitude above threshold. Failed chunks MUST be logged with a reason and skipped without aborting the batch.
- **FR-011**: System MUST upsert child chunk vectors to the vector store in configurable batches (default 50 points) and store parent chunk text in the relational database.
- **FR-012**: System MUST buffer pending vector upserts in memory (up to 1,000 points) when the vector store is unreachable, and flush when connectivity recovers. When the buffer is full, the ingestion job MUST be paused (not aborted) and MUST resume automatically on recovery.
- **FR-013**: System MUST pause ingestion jobs when the embedding service is unreachable and retry automatically when the service recovers.
- **FR-014**: System MUST track ingestion job status through the lifecycle: `started` -> `streaming` -> `embedding` -> `completed` (or `failed`/`paused`).
- **FR-015**: System MUST update document status and chunk count on ingestion completion or failure.
- **FR-016**: System MUST handle native worker process crashes gracefully by processing all successfully parsed chunks, logging the error, and setting the job status to `failed`.
- **FR-017**: System MUST migrate the existing Phase 1 `documents` table to the production schema (single collection foreign key, file hash, chunk count, standardized statuses, completion timestamp). Phase 1 document records and their orphaned vector points (indexed with random UUIDs) MUST be preserved as-is; no automatic cleanup or re-ingestion is performed during migration.
- **FR-018**: System MUST create ingestion job tracking and parent chunk storage tables as part of application initialization.
- **FR-019**: System MUST preserve compatibility with the existing parent chunk read path used by the research graph after schema migration.
- **FR-020**: System MUST support parallel ingestion — multiple jobs MAY run simultaneously across different collections, sharing CPU (native worker), GPU/VRAM (embedding service), and vector store resources. The system MUST enforce configurable resource limits (e.g., maximum concurrent embedding workers) to prevent resource exhaustion.

### Key Entities

- **Document**: A file uploaded by a user into a collection. Tracked by content hash for deduplication. Key attributes: filename, collection membership, content hash, ingestion status, chunk count.
- **Ingestion Job**: A record tracking the lifecycle of processing a single document. Progresses through defined status stages and records processed/skipped chunk counts and any error details.
- **Parent Chunk**: A large text segment (2000-4000 chars) representing approximately one page of a document. Stored in the relational database. Linked to its source document and collection.
- **Child Chunk**: A smaller text segment (~500 chars) derived from a parent chunk, with a breadcrumb prefix. Embedded as a vector and stored in the vector store. Linked to its parent chunk via deterministic identifier.
- **Native Worker Output**: A structured text chunk produced by the native parsing binary, containing text content, page number, section heading, heading hierarchy path, document type, and chunk index.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can upload a 200-page PDF and have it fully ingested (parsed, chunked, embedded, and searchable) in under 20 seconds.
- **SC-002**: 100% of uploaded files with valid types and sizes are successfully ingested or produce a clear, actionable error within 30 seconds.
- **SC-003**: 0% of invalid embedding vectors are stored — every vector is validated before storage, and failures are logged with reasons without aborting the batch.
- **SC-004**: Duplicate file uploads (same content, same collection) are detected and rejected in under 1 second without any re-processing.
- **SC-005**: Re-ingestion of a modified document completes without leaving orphaned or duplicate data in the vector store, verified by point count matching the new chunk count.
- **SC-006**: An ingestion job survives a temporary infrastructure outage (vector store or embedding service down for up to 5 minutes) without data loss — the job pauses and completes successfully after recovery.
- **SC-007**: The native parsing worker processes documents at least 5x faster than the previous parser for documents over 50 pages.
- **SC-008**: All 12 supported file types can be uploaded, parsed, and ingested end-to-end without errors.
- **SC-009**: Existing search and retrieval functionality (parent chunk lookups, document listing, collection queries) continues to work without regression after schema migration.
