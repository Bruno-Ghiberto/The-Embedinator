# Feature Specification: Error Handling

**Feature Branch**: `012-error-handling`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "Read @Docs/PROMPTS/spec-12-errors/12-specify.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Consistent, Actionable Error Responses (Priority: P1)

A frontend developer integrates with the Embedinator API. When a request fails, they receive a predictable, structured error response every time — same shape, same field names, same code conventions — regardless of which endpoint failed or what internal component caused the error. They can write one error-handling routine in the frontend that handles all API errors uniformly.

**Why this priority**: Inconsistent error formats break the frontend's ability to display errors correctly and make debugging harder. This is the most foundational requirement — it affects all other interactions.

**Independent Test**: Submit a request that triggers each category of error (validation, not found, conflict, rate limit, service unavailable). Verify all responses share the same envelope shape.

**Acceptance Scenarios**:

1. **Given** a request with an invalid field value, **When** the API rejects it, **Then** the response contains a machine-readable code, a human-readable message, and a request trace identifier — all in the same nested structure as every other error.
2. **Given** a resource that does not exist, **When** the API is asked for it, **Then** the 404 response uses the same envelope as a 400 validation error.
3. **Given** an unexpected internal failure, **When** it reaches the API boundary, **Then** the response returns a generic error message with no internal details (stack trace, file paths, class names) exposed to the caller.

---

### User Story 2 - Transparent Streaming Errors (Priority: P2)

A user is chatting with the Embedinator. The system starts streaming a response, then an internal service becomes temporarily unavailable mid-stream. Instead of the stream silently hanging or producing garbled output, the user receives a clear, human-readable error message that explains the service is temporarily unavailable and they can try again. The frontend knows the stream has ended.

**Why this priority**: The chat stream begins before the system knows if it will succeed. If errors during streaming are not surfaced as structured events, the user sees a broken experience. This is the primary user-facing failure scenario.

**Independent Test**: Trigger a service outage condition during an active chat stream. Verify the stream terminates cleanly with an error event that the frontend can display.

**Acceptance Scenarios**:

1. **Given** an active chat stream, **When** the internal circuit breaker trips, **Then** an error event is emitted in the stream with a code and user-friendly message, and the stream ends.
2. **Given** a chat request with no collections selected, **When** the stream begins, **Then** an error event is immediately emitted explaining that at least one collection must be selected.
3. **Given** an unexpected failure during graph execution, **When** the exception is caught, **Then** the stream emits an error event and terminates without exposing internal exception text.

---

### User Story 3 - Automatic Recovery from Transient Failures (Priority: P3)

An operator runs the Embedinator. The vector database temporarily hiccups (network glitch, restart). The system automatically retries failed operations with short delays before giving up, and trips a circuit breaker after repeated failures to prevent the entire system from stalling on timeouts. When the database recovers, the circuit breaker resets automatically and normal operation resumes — no manual restart required.

**Why this priority**: Transient failures are unavoidable in production. Automatic recovery reduces operator burden and improves uptime.

**Independent Test**: Simulate a temporary service outage, verify requests fail fast during the outage (circuit open), then restore the service and verify normal requests succeed again (circuit reset).

**Acceptance Scenarios**:

1. **Given** a transient service error, **When** an operation fails, **Then** the system automatically retries up to a configured number of times with increasing delays before surfacing the failure.
2. **Given** repeated consecutive failures, **When** the failure threshold is reached, **Then** the circuit opens and subsequent calls fail immediately without waiting for a timeout.
3. **Given** an open circuit, **When** the cooldown period elapses, **Then** the next call is allowed through as a probe; if it succeeds, normal operation resumes.

---

### User Story 4 - Rate Limit Protection (Priority: P4)

A malicious actor or runaway script floods the Embedinator API with requests. The system rate-limits incoming traffic per IP address, returning a clear 429 response with a retry-after indicator. Legitimate users on different IPs are unaffected.

**Why this priority**: Without rate limiting, abuse can exhaust system resources and degrade service for all users.

**Independent Test**: Send requests exceeding the configured rate limit from a single IP. Verify 429 responses with retry guidance are returned and requests from other IPs succeed normally.

**Acceptance Scenarios**:

1. **Given** a single IP sending more than the allowed chat requests per minute, **When** the limit is exceeded, **Then** the API returns a 429 response with a machine-readable code and a header indicating when to retry.
2. **Given** rate limits are exceeded on one endpoint, **When** the same IP calls a different endpoint, **Then** the rate limit is applied independently per endpoint type.
3. **Given** a rate-limited IP waits the indicated retry period, **When** it sends a new request, **Then** the request succeeds normally.

---

### User Story 5 - Encrypted Provider Key Errors (Priority: P5)

An administrator configures a cloud provider API key. If the encryption key is not configured in the system environment, any attempt to store or retrieve provider keys returns a clear 503 error explaining the service is unavailable — not a cryptic internal exception.

**Why this priority**: Misconfigured encryption keys must fail safely and visibly, not silently or with confusing error messages.

**Independent Test**: Remove the encryption key from the environment. Verify that provider key endpoints return 503 with a meaningful error code.

**Acceptance Scenarios**:

1. **Given** the encryption key is not configured, **When** a provider key is requested, **Then** the API returns 503 with a service-unavailable code and no internal details.

---

### Edge Cases

- What happens when a circuit breaker is open and a rate limit is hit simultaneously?
- How does the system behave when the trace identifier is unavailable (e.g., before middleware runs)?
- What happens when the database itself is unavailable during error handling?
- How are errors in background ingestion jobs surfaced — not via HTTP, but via job status polling?
- What happens when a streaming error occurs before any content chunk has been sent?
- What happens when the system receives a provider rate-limit error and returns a 429 — does the frontend see the same format as a rate-limit from the middleware?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST define a single root error category from which all application errors descend, so every caught application exception can be identified and handled programmatically.

- **FR-002**: The system MUST define specific named error categories for storage failures (vector database connection, SQLite), inference failures, embedding failures, ingestion pipeline failures, session load failures, and circuit breaker trips. Each category carries a distinct identity.

- **FR-003**: One provider-specific rate-limit error category MUST exist separately from the main error hierarchy. It MUST preserve the attribute `provider` (the provider name that triggered the limit). It MUST NOT be merged into the main hierarchy.

- **FR-004**: All REST API error responses MUST use a single, consistent nested envelope with an outer object containing an `error` field (with machine-readable code, human-readable message, and optional structured details) and a `trace_id` field (unique request identifier).

- **FR-005**: All error codes in REST responses MUST be stable, uppercase snake_case strings. Renaming an existing code is a breaking change and is not permitted.

- **FR-006**: Errors during an active chat stream MUST be emitted as structured stream events (not HTTP error status codes). Each event MUST include a code and a user-facing message. Three stream error codes are defined: one for no collections selected, one for circuit breaker open, one for any other unhandled failure.

- **FR-007**: A global catch-all handler MUST be registered for the root application error category. It MUST return HTTP 500 with the standard nested envelope and the stable code `INTERNAL_ERROR`. Two additional specific handlers MUST also be registered: `QdrantConnectionError` → HTTP 503 with code `QDRANT_UNAVAILABLE`, and `OllamaConnectionError` → HTTP 503 with code `OLLAMA_UNAVAILABLE`. These specific handlers take precedence over the global 500 catch-all. All other application error subtypes fall through to the global 500 handler.

- **FR-008**: The provider rate-limit exception handler MUST use the standard nested envelope with an uppercase code consistent with all other error codes, and MUST include the trace identifier.

- **FR-009**: The system MUST maintain circuit breakers for the vector database layer and the inference layer. Each circuit breaker MUST open after a configurable number of consecutive failures, stay open for a configurable cooldown period, and allow exactly one probe request to test recovery. Both parameters MUST be configurable via environment variables.

- **FR-010**: Vector database operations MUST be retried on transient failure using exponential backoff with random jitter, up to a fixed number of attempts (hardcoded at the call site; the `retry_max_attempts` and `retry_backoff_initial_secs` settings fields are reserved for a future spec and MUST NOT be removed). The circuit breaker records outcomes after all retry attempts are exhausted.

- **FR-011**: The ingestion pipeline MUST retry embedding failures using a custom loop with exponential backoff (5 s initial, 60 s maximum), pausing the job record between attempts. This is a separate retry strategy from the vector database retry.

- **FR-012**: In-memory per-IP rate limiting MUST be applied to all API endpoints using a sliding-window algorithm. Limits MUST be independently configurable for the chat endpoint, the ingestion endpoint, provider key management endpoints, and all other endpoints. All rate-limited responses MUST include a `Retry-After` header.

- **FR-013**: Internal error details (exception text, file paths, line numbers, class names) MUST NOT appear in any response to external callers.

- **FR-014**: Contract tests MUST validate that all required error categories exist, extend the correct base, carry the expected attributes, and that the error response Pydantic models have the correct fields.

### Key Entities

- **Error Category**: A named application exception type with a defined identity, parent class, and contextual message. Not a data record — a code-level artifact.
- **Error Response Envelope**: The JSON structure returned to callers on failure — outer fields `error` (with `code`, `message`, `details`) and `trace_id`.
- **Stream Error Event**: A structured line emitted during a chat stream on failure — fields `type`, `message`, `code`, `trace_id`.
- **Circuit Breaker**: An in-memory state machine per protected service that tracks consecutive failures and temporarily halts calls to a failing service.
- **Rate Limit Bucket**: A per-IP, per-endpoint-type counter enforcing request frequency limits within a sliding time window.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every error response from any REST endpoint uses the same nested envelope shape — zero exceptions. A single frontend error-handling routine handles all API errors without special-casing per endpoint.

- **SC-002**: Every error code string in all error responses is a stable uppercase snake_case identifier. No lowercase codes or plain HTTP status phrases appear in any error response body.

- **SC-003**: When an internal service fails transiently, the system resumes normal operation automatically within the configured cooldown period (default: 30 seconds after the outage resolves), without operator intervention.

- **SC-004**: Rate-limited responses are returned in under 5 ms at the middleware layer (pure in-memory check, no I/O). All rate-limited responses include a `Retry-After` header.

- **SC-005**: No stack traces, exception class names, file paths, or module paths appear in any response to external callers under normal operating conditions.

- **SC-006**: Contract tests cover all defined error categories (existence, parent class, attributes) and the error response data models. Removal of any error category is immediately caught by the test suite.

- **SC-007**: The chat stream always terminates cleanly with either a success terminal event or an error event. A stream MUST NOT hang indefinitely or terminate without emitting a terminal event.

## Clarifications

### Session 2026-03-17

- Q: Should spec-12 add specific HTTP status handlers for individual error subtypes beyond the global 500 catch-all? → A: Add specific 503 handlers for `QdrantConnectionError` and `OllamaConnectionError`; all other application errors remain 500.
- Q: Should spec-12 wire the `retry_max_attempts` and `retry_backoff_initial_secs` settings fields to the retry decorators? → A: No — leave as reserved dead config; retry attempt counts remain hardcoded at the call site in this spec.
- Q: Should SC-004 ("immediately") be replaced with a measurable latency target for rate-limit decisions? → A: Yes — under 5 ms per rate-limit decision at the middleware layer.
- Q: Should spec-12 define structured logging requirements for error events? → A: Out of scope — defer to existing per-layer structlog usage; formal log schema belongs in the Observability spec.

## Assumptions

- Structured error logging (log fields, log schemas, log levels per error type) is **out of scope** for spec-12. Each layer already logs via structlog; a formal log schema is deferred to the Observability spec (spec-15).
- Error categories that were described in earlier drafts of this spec but do not exist in the current codebase (e.g., `StorageError`, `AgentError`, `NotFoundError`, `ConflictError`, and related sub-types) MUST NOT be created by this spec. The authoritative list is the 11 categories currently in the errors module plus the provider rate-limit exception in the provider base module.
- The circuit breaker counts consecutive failures with no time decay window. A "60-second failure window" does not exist and is not being added.
- Retry configuration fields for maximum attempts and initial backoff exist in the settings object but are not currently wired to the retry decorators. They are reserved for future use and MUST NOT be removed.
- Ingestion errors surface via job status polling, not via HTTP error responses. The API returns success once a job is accepted; the job status record reflects failure.
- The `debug` configuration flag currently has no effect on error response content. It is reserved for future conditional detail exposure and MUST NOT be removed.
