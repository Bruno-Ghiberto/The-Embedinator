# Feature Specification: API Reference — HTTP Interface Layer

**Feature Branch**: `008-api-reference`
**Created**: 2026-03-14
**Status**: Draft
**Input**: User description: "Read @Docs/PROMPTS/spec-08-api/08-specify.md"

## Clarifications

### Session 2026-03-14

- Q: Should endpoint paths include an API version prefix (e.g., `/api/v1/`)? → A: No version prefix — paths use `/api/` directly (e.g., `/api/collections`, `/api/chat`). API versioning is out of scope for this feature.
- Q: What is the enforcement unit for rate limiting (no user authentication present)? → A: Per client IP address — each IP gets its own independent counter per endpoint category.
- Q: What happens to in-progress ingestion jobs when a collection is deleted? → A: Cancel active jobs immediately — any in-progress jobs are cancelled and transition to `failed` status before the collection is removed.
- Q: When do settings updates take effect? → A: New sessions only — active chat sessions continue with the settings in effect when they started; changes apply to sessions initiated after the update.
- Q: How long are query traces retained? → A: Indefinitely — traces are kept until explicitly cleared; no automatic time-based or count-based purging.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Ask Questions and Receive Streamed Answers (Priority: P1)

A user opens the chat interface, selects one or more document collections, types a question, and immediately begins receiving an answer that streams token by token. Along with the answer, the user sees source citations, a confidence score, and a groundedness indicator. If the system needs clarification before answering, it interrupts and asks a targeted question. The user can resume across multiple turns using the same session.

**Why this priority**: Chat is the primary product capability. Everything else — collections, ingestion, providers — exists to support this interaction. Without a working chat endpoint, the system has no user-facing value.

**Independent Test**: Can be tested end-to-end by sending a POST request with a message and at least one collection ID and verifying that a stream of structured events is returned, ending with a `done` event.

**Acceptance Scenarios**:

1. **Given** a collection with indexed documents, **When** a user sends a message via the chat endpoint, **Then** a stream of events is returned starting with a `session` event, followed by `status`, `chunk` (repeated), `citation`, `confidence`, `groundedness`, and `done` events — in newline-delimited JSON format with no buffering.
2. **Given** a chat session already in progress, **When** the user sends a follow-up message with the same session ID, **Then** the system continues the conversation with full prior context preserved.
3. **Given** an ambiguous query, **When** the agent cannot determine intent, **Then** a `clarification` event is returned with a targeted question before the answer stream begins.
4. **Given** the inference service is unavailable, **When** a chat request is submitted, **Then** an `error` event is returned with a human-readable message and a structured error code.
5. **Given** a user sends more than 30 chat requests per minute, **When** the 31st request arrives, **Then** the system rejects it with a rate-limit response.

---

### User Story 2 — Manage Collections and Upload Documents (Priority: P2)

A user creates a document collection, gives it a name, and uploads documents to it (PDF, Markdown, code files, etc.). The system accepts the upload, triggers background processing, and lets the user poll for ingestion status. The user can list all documents in a collection and delete documents they no longer need. When a collection is no longer needed, the user can delete it entirely.

**Why this priority**: Collections and document ingestion are prerequisites for meaningful chat. A user must be able to organize and populate collections before asking questions. This is the primary data-management workflow.

**Independent Test**: Can be tested by creating a collection, uploading a document, polling the job status until completion, listing documents, and then deleting the document — all via the HTTP interface.

**Acceptance Scenarios**:

1. **Given** no existing collections, **When** a user creates a collection with a valid name, **Then** the collection is created and returned with a unique ID and creation timestamp.
2. **Given** a collection already exists with a given name, **When** a user tries to create another with the same name, **Then** the system returns a conflict error (409).
3. **Given** a collection name with uppercase letters, spaces, or special characters (other than hyphens and underscores), **When** a user submits it, **Then** the system rejects it with a validation error.
4. **Given** a valid collection, **When** a user uploads a supported file (PDF, Markdown, Python, etc.) under 100 MB, **Then** the system accepts the file, returns a job ID, and begins ingestion in the background.
5. **Given** a file over 100 MB or with an unsupported extension (e.g., `.exe`), **When** uploaded, **Then** the system rejects it with a descriptive error explaining the limit or allowed types.
6. **Given** an active ingestion job, **When** the user polls the job status endpoint, **Then** the current status is returned (started, streaming, embedding, completed, failed, paused) along with progress counts.
7. **Given** a duplicate file (same content as an already-ingested document), **When** uploaded, **Then** the system detects the duplicate and returns a `duplicate` status without re-processing.
8. **Given** a collection with documents, **When** a user deletes a document, **Then** the document is removed and no longer appears in listings.
9. **Given** an existing collection, **When** a user deletes the collection, **Then** it and all associated data are removed.

---

### User Story 3 — Configure AI Providers and Browse Available Models (Priority: P3)

A user browses the list of configured AI providers (local and cloud), saves an API key for a cloud provider, and lists the models available from each provider. API keys are stored securely and never returned in responses — only a flag indicating whether a key is configured. The user can delete a key when it is no longer needed. The user can also list all available language and embedding models across providers.

**Why this priority**: Provider configuration unlocks cloud model access. Without it, the system is limited to local models. This is a one-time configuration step that unblocks the full model selection.

**Independent Test**: Can be tested by listing providers, saving an API key for one, verifying `has_key: true` appears in the response (but no key value), then deleting the key and verifying `has_key: false`.

**Acceptance Scenarios**:

1. **Given** the system has providers configured, **When** a user lists providers, **Then** each provider shows its name, active status, whether a key is configured, and model count — but never the key value itself.
2. **Given** a provider that accepts API keys, **When** a user submits a valid key, **Then** it is stored securely and `has_key: true` is returned.
3. **Given** a provider with a stored key, **When** a user deletes the key, **Then** `has_key: false` is returned and the key is permanently removed.
4. **Given** a configured provider, **When** a user lists its models, **Then** available model names with metadata (size, quantization, context length) are returned.
5. **Given** a provider is unreachable, **When** model listing is requested, **Then** a service-unavailable error is returned with a human-readable explanation.

---

### User Story 4 — Monitor System Health and Browse Query History (Priority: P4)

An operator checks the health of the system by calling the health endpoint, which reports the status of each connected service (vector database, inference service, relational database) along with latency measurements. They can also view a paginated list of past queries with response metrics, drill into a specific query to see retrieved chunks, sub-questions, and strategy decisions, and review aggregate system statistics (total queries, average confidence, meta-reasoning rate).

**Why this priority**: Observability is essential for operating the system reliably. Health checks enable automated monitoring; query traces enable debugging and quality assessment.

**Independent Test**: Can be tested independently by calling the health, stats, and traces endpoints and verifying structured responses with expected fields.

**Acceptance Scenarios**:

1. **Given** all services are running, **When** the health endpoint is called, **Then** each service (vector database, inference, relational database) shows `ok` with a latency measurement in milliseconds.
2. **Given** one service is down, **When** the health endpoint is called, **Then** that service shows `error` while healthy services remain `ok`.
3. **Given** past queries exist, **When** the traces list is called, **Then** a paginated list is returned with query text, confidence score, latency, and model used.
4. **Given** a specific trace ID, **When** the trace detail endpoint is called, **Then** the full detail is returned including sub-questions, retrieved chunks with scores, reasoning steps, and strategy switches.
5. **Given** queries have been processed, **When** the stats endpoint is called, **Then** aggregate counts (collections, documents, chunks, queries) and averages (latency, confidence, meta-reasoning rate) are returned.

---

### User Story 5 — Adjust System-Wide Settings (Priority: P5)

An administrator views the current system configuration (default model, chunk sizes, confidence threshold, etc.) and applies partial updates. Only changed fields need to be submitted. The system validates the update and returns the full updated configuration.

**Why this priority**: Settings allow tuning the system without code changes. It is a lower-priority administrative capability that does not block core workflows.

**Independent Test**: Can be tested by fetching settings (verifying defaults), submitting a partial update with one changed field, then fetching again to verify the change persisted.

**Acceptance Scenarios**:

1. **Given** no prior customization, **When** settings are fetched, **Then** the current defaults are returned (default model, chunk sizes, confidence threshold as integer 0–100, etc.).
2. **Given** current settings, **When** a partial update is submitted with only one field changed, **Then** only that field is updated and all others retain their values.
3. **Given** an invalid value (e.g., confidence threshold outside 0–100), **When** submitted, **Then** a validation error is returned.

---

### Edge Cases

- What happens when a collection ID referenced in a chat request does not exist? → 404 with descriptive error.
- What happens when `collection_ids` is empty in a chat request? → 400 validation error.
- What happens when a file upload is interrupted mid-stream? → Job status transitions to `failed` with an error message.
- What happens when the same document is uploaded while an ingestion job for it is already running? → System detects duplicate by content hash and returns `duplicate` status immediately.
- What happens when a provider's model endpoint returns unexpected data? → System returns a service-unavailable error; it does not crash or expose raw error details.
- What happens when traces are queried with a session filter that matches no records? → Empty paginated list is returned (not 404).
- What happens when a rate limit is exceeded? → The request is rejected with a rate-limit response immediately.
- What happens when CORS is not configured for a requesting origin? → The request is blocked by the browser with no partial data exposed.
- What happens when a collection is deleted while ingestion jobs are active? → Active jobs are cancelled immediately and transition to `failed` status before deletion completes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST expose a unified HTTP interface at a single base URL (no API version prefix) that serves all six endpoint groups: collections, documents, chat, models, providers, and observability. API versioning is out of scope.
- **FR-002**: The system MUST allow users to create named collections with lowercase-alphanumeric names (hyphens and underscores permitted) and reject names that violate this pattern.
- **FR-003**: The system MUST prevent duplicate collection names and return a conflict response when a name already exists.
- **FR-004**: The system MUST allow users to list all collections, each showing document count and creation date.
- **FR-005**: The system MUST allow users to delete a collection, immediately cancelling any active ingestion jobs (transitioning them to `failed`) and then removing the collection and all associated data.
- **FR-006**: The system MUST allow users to list all documents within a collection, including ingestion status and file metadata.
- **FR-007**: The system MUST accept file uploads for supported types (.pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h) up to 100 MB in size.
- **FR-008**: The system MUST reject uploads with unsupported file types or files exceeding 100 MB, returning a descriptive error identifying the specific violation.
- **FR-009**: The system MUST trigger background ingestion upon successful upload and return a job ID that can be used to poll status.
- **FR-010**: The system MUST expose an ingestion job status endpoint returning the current phase (started, streaming, embedding, completed, failed, paused), timestamps, error details if failed, and chunk progress counts.
- **FR-011**: The system MUST detect duplicate documents by content and return a `duplicate` status without re-processing.
- **FR-012**: The system MUST allow users to delete a document from a collection.
- **FR-013**: The system MUST stream chat responses in newline-delimited JSON format with no buffering — delivering tokens as generated.
- **FR-014**: The chat stream MUST produce these event types where applicable: `session`, `status`, `chunk`, `citation`, `meta_reasoning`, `confidence`, `groundedness`, `done`, `clarification`, `error`.
- **FR-015**: Confidence scores in all responses MUST be integers on a 0–100 scale.
- **FR-016**: The system MUST support multi-turn chat sessions identified by a session ID, preserving conversation context across turns.
- **FR-017**: The system MUST expose listings of available language models and embedding models from configured providers.
- **FR-018**: The system MUST allow users to save an encrypted API key for a cloud provider and MUST NEVER return the key value in any response — only a boolean `has_key` indicator.
- **FR-019**: The system MUST allow users to delete a stored provider API key.
- **FR-020**: The system MUST allow reading and partially updating system-wide configuration settings, validating all values before applying. Updated settings MUST take effect for new chat sessions only; active sessions continue with the settings in effect at session start.
- **FR-021**: The system MUST expose a paginated query trace listing with optional filtering by session ID, and a detail view showing sub-questions, retrieved chunks, reasoning steps, and strategy switches. Traces are retained indefinitely and are never automatically purged.
- **FR-022**: The system MUST expose a health endpoint that probes each connected service independently and reports per-service status with latency measurements.
- **FR-023**: The system MUST expose a system statistics endpoint computing aggregate counts and averages from historical query data.
- **FR-024**: The system MUST enforce rate limits per client IP address, per endpoint category: chat (30 requests/minute), ingestion (10 requests/minute), provider key management (5 requests/minute), all other endpoints (120 requests/minute).
- **FR-025**: The system MUST support configurable cross-origin request policies to allow the frontend to communicate with the API.
- **FR-026**: All error responses MUST include a human-readable description, a machine-readable error code, and a request trace ID.

### Key Entities

- **Collection**: A named grouping of documents that maps to a searchable knowledge space. Has a name, description, default embedding model preference, chunk profile, and document count.
- **Document**: A file within a collection. Has a filename, content hash (for duplicate detection), ingestion status, chunk count, and ingestion timestamp.
- **IngestionJob**: A background processing record for a document upload. Tracks phases (started → streaming → embedding → completed/failed/paused), progress counts, timestamps, and error messages.
- **ChatSession**: A stateful conversation identified by a session ID. Preserves multi-turn context and links to query traces.
- **QueryTrace**: A record of a completed chat query capturing the query text, collections searched, model used, confidence score, latency, sub-questions, retrieved chunks, and reasoning/strategy decisions.
- **Provider**: A configured AI service (local or cloud). Has a name, active status, optional encrypted API key, base URL, and a list of available models.
- **ModelInfo**: Metadata about an available model: name, provider, size, quantization, context length, and embedding dimensions (for embedding models).
- **SystemSettings**: Configurable system-wide parameters: default language and embedding models, chunk sizes, confidence threshold, groundedness check toggle, citation alignment threshold.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All documented endpoints respond with correct HTTP status codes and structured payloads for both success and error conditions, with zero endpoints returning unstructured or missing error bodies.
- **SC-002**: Chat answer tokens reach the client within 500 ms of the first token being generated — no buffering or batch delivery permitted.
- **SC-003**: A complete chat query-to-final-event round trip (excluding model inference time) completes in under 2 seconds for a single-collection query.
- **SC-004**: Rate limits are enforced accurately — a burst of 31 chat requests within 60 seconds results in exactly 1 rejected request with a rate-limit response.
- **SC-005**: Provider API keys are never returned in any response under any condition — 100% of provider listing responses return only `has_key: true/false`, never the key value.
- **SC-006**: File type and size validation rejects 100% of uploads with unsupported extensions or files over 100 MB, with a descriptive error identifying the specific violation.
- **SC-007**: Duplicate document detection prevents re-ingestion for 100% of re-uploaded files with identical content.
- **SC-008**: The health endpoint responds in under 1 second and correctly reflects the live status of each service — verified by intentionally stopping a service and confirming the response changes.
- **SC-009**: All error responses include a human-readable description, a machine-readable code, and a request trace ID — 0 error responses omit any of these fields.
- **SC-010**: The system handles at least 10 concurrent chat stream connections without dropping events or corrupting newline-delimited JSON payloads.
