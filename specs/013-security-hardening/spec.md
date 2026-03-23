# Feature Specification: Security Hardening

**Feature Branch**: `013-security-hardening`
**Created**: 2026-03-17
**Status**: Draft
**Input**: Harden defense-in-depth security: input truncation, filter key whitelisting, file upload content validation, and logging security

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Safe Document Ingestion (Priority: P1)

An operator uploads documents through the ingestion interface. The system protects against malicious filenames (path traversal attacks) and rejects forged files (e.g., a non-PDF file renamed with a `.pdf` extension). Existing extension and size checks remain intact.

**Why this priority**: File upload is the primary external input vector. Path traversal in filenames and forged file types are common attack patterns that can compromise the host filesystem or cause downstream parsing failures.

**Independent Test**: Upload a file with a malicious filename (e.g., `../../etc/passwd.txt`) and a forged PDF (random bytes with `.pdf` extension) — both must be handled safely without affecting other features.

**Acceptance Scenarios**:

1. **Given** a file named `../../etc/passwd.txt`, **When** the operator uploads it, **Then** the system sanitizes the filename (removes path traversal components) and stores the file safely with a clean name.
2. **Given** a file with `.pdf` extension but non-PDF content (first bytes are not `%PDF`), **When** the operator uploads it, **Then** the system rejects the upload with a clear error message indicating content mismatch.
3. **Given** a valid `.md` file, **When** the operator uploads it, **Then** the upload succeeds without content sniffing (plain-text types have no magic bytes to verify).
4. **Given** a valid PDF file (first bytes are `%PDF`), **When** the operator uploads it, **Then** the upload succeeds normally.
5. **Given** a file with an unsupported extension (e.g., `.exe`), **When** the operator uploads it, **Then** the existing extension check rejects it (existing behavior preserved).

---

### User Story 2 - Protected Chat Input (Priority: P1)

A user submits a chat query through the interface. The system guards against excessively long messages that could abuse the language model's context window or inflate storage costs. Truncation is silent — users experience no error.

**Why this priority**: The chat endpoint is the most frequently used input surface. Without length enforcement, a single oversized message can degrade response quality and inflate processing costs.

**Independent Test**: Submit a 15,000-character message and verify it is processed successfully with only the first 10,000 characters stored and sent to the language model.

**Acceptance Scenarios**:

1. **Given** a chat message of 15,000 characters, **When** the user submits it, **Then** the system processes the first 10,000 characters without error.
2. **Given** a chat message of 15,000 characters, **When** the query trace is recorded, **Then** the stored query text is exactly 10,000 characters.
3. **Given** a chat message of 5,000 characters (under the limit), **When** the user submits it, **Then** the full message is preserved without truncation.

---

### User Story 3 - Restricted Search Filters (Priority: P2)

A user (or client application) submits a search query with payload filters. The system only accepts known, safe filter keys and silently ignores any unknown or potentially malicious keys. This prevents arbitrary access to internal payload fields in the vector database.

**Why this priority**: Filter injection is a less common but real risk. Restricting filter keys to a known set prevents data leakage from unexpected payload fields.

**Independent Test**: Submit a search query with an unknown filter key and verify it is silently ignored while known filter keys work correctly.

**Acceptance Scenarios**:

1. **Given** a search query with filter `{"doc_type": "Prose"}`, **When** the system processes it, **Then** the filter is applied normally.
2. **Given** a search query with filter `{"arbitrary_field": "value"}`, **When** the system processes it, **Then** the unknown key is silently ignored and results are returned without filtering on that key.
3. **Given** a search query with mixed filters `{"doc_type": "Prose", "evil_key": "attack"}`, **When** the system processes it, **Then** only `doc_type` is applied; `evil_key` is silently dropped.

---

### User Story 4 - Sensitive Data Redaction in Logs (Priority: P2)

An operator reviews application logs for debugging or incident response. The system ensures that sensitive values (API keys, passwords, tokens) are never present in log output, even if application code accidentally passes them to the logging system.

**Why this priority**: Log files are often stored in less-secured locations than databases. Sensitive data in logs creates a secondary exposure surface that persists beyond the original request.

**Independent Test**: Trigger a log event that includes an `api_key` field and verify the JSON log output shows `[REDACTED]` instead of the actual value.

**Acceptance Scenarios**:

1. **Given** an application log event that includes a field named `api_key`, **When** the log is written, **Then** the value is replaced with `[REDACTED]`.
2. **Given** an application log event that includes a field named `password`, `secret`, `token`, or `authorization`, **When** the log is written, **Then** each sensitive field value is replaced with `[REDACTED]`.
3. **Given** a provider listing endpoint response, **When** the operator requests provider details, **Then** the response includes a presence indicator (e.g., `has_key: true/false`) and never the encrypted key value.

---

### Edge Cases

- What happens when a filename consists entirely of path traversal characters (e.g., `../../../`)? The system must produce a safe fallback name (not an empty string).
- What happens when a PDF file is exactly 3 bytes (fewer than the 4-byte magic check)? The system must reject it as content mismatch rather than crashing on a short read.
- What happens when a chat message is exactly 10,000 characters? It must be preserved in full (no off-by-one truncation).
- What happens when all filter keys in a search query are unknown? The system must return unfiltered results (not an error).
- What happens when the logging redaction processor encounters a nested dict containing a `password` key? The redaction applies to top-level log record keys only (nested values are not scanned, to avoid performance overhead).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST silently truncate chat messages to a maximum of 10,000 characters before processing and before storing the query in the trace log.
- **FR-002**: System MUST restrict search filter keys to a known allowlist (`doc_type`, `source_file`, `page`, `chunk_index`). Unknown keys MUST be silently ignored.
- **FR-003**: System MUST sanitize uploaded filenames by removing path traversal sequences and restricting characters to alphanumeric, dots, hyphens, and underscores. If the sanitized name is empty, the system MUST use a safe fallback name.
- **FR-004**: System MUST verify that files uploaded with a `.pdf` extension begin with the magic bytes `%PDF`. Files that fail this check MUST be rejected with a clear error message.
- **FR-005**: System MUST NOT perform magic byte verification on non-PDF file types (plain-text file types have no reliable magic bytes).
- **FR-006**: System MUST redact sensitive field values in all log output. Fields matching `api_key`, `password`, `secret`, `token`, and `authorization` (case-insensitive) MUST be replaced with `[REDACTED]`.
- **FR-007**: System MUST NOT return encrypted key values in any provider listing or detail endpoint response. A boolean presence indicator MUST be used instead.
- **FR-008**: All existing security behaviors (extension allowlist, file size limit, rate limiting, CORS, collection name validation) MUST continue to function identically after this spec is implemented.

### Key Entities

- **Chat Message**: User-submitted query text, subject to length truncation before processing and storage.
- **Search Filter**: Key-value pairs used to narrow vector search results, restricted to a known key set.
- **Uploaded File**: Document submitted for ingestion, subject to filename sanitization and content type verification.
- **Log Record**: Structured log event, subject to sensitive field redaction before output.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of uploaded filenames containing path traversal sequences are sanitized before reaching disk or database storage.
- **SC-002**: 100% of forged PDF files (wrong magic bytes) are rejected at upload time with a descriptive error.
- **SC-003**: Chat messages exceeding 10,000 characters are truncated; the stored trace query length never exceeds 10,000 characters.
- **SC-004**: 100% of search queries with unknown filter keys produce results without error (unknown keys silently dropped).
- **SC-005**: Zero instances of plaintext API keys, passwords, secrets, tokens, or authorization headers appear in log output.
- **SC-006**: All existing security tests (rate limiting, CORS, extension allowlist, file size, collection name validation) continue to pass without modification.
- **SC-007**: No new external dependencies are introduced by this feature.

## Assumptions

- The system is a self-hosted, single-user application. There is no multi-tenant isolation or per-user access control in scope.
- The existing encryption key (`EMBEDINATOR_FERNET_KEY`) and its lifecycle (ValueError on absence, graceful degradation to `None`) are stable and must not be altered.
- Magic byte checking for PDF is sufficient for the MVP. Comprehensive MIME type verification (e.g., via `python-magic` / `libmagic`) is out of scope to avoid adding system dependencies.
- Log redaction applies to top-level log record keys only. Deep inspection of nested structures is out of scope to avoid performance overhead.
- The allowed filter key set (`doc_type`, `source_file`, `page`, `chunk_index`) is fixed for this spec. Future extensions would require a spec amendment.
- The 10,000-character chat truncation limit is chosen to match the security blueprint. It is not configurable in this spec.

## Out of Scope

- Authentication or authorization (single-user system, no auth layer)
- TLS termination (handled by reverse proxy in production)
- Virus scanning (noted in blueprint as post-MVP ClamAV hook)
- Comprehensive MIME type verification via external libraries
- Fernet key rotation
- Multi-tenant security isolation
- Nested/deep log field redaction
