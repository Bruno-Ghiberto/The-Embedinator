# Spec 12: Error Handling — Feature Specification Context

## Feature Description

The Error Handling spec defines a formal, machine-readable specification for the exception hierarchy, HTTP status code mapping, error response format, retry policies, and circuit breaker configuration already present in The Embedinator codebase. The goal of this spec is to codify the real, implemented patterns consistently across all layers, fill gaps where handling is ad-hoc, and produce comprehensive contract tests that lock in the behaviour for future development.

The system's current state (after specs 01–11) has a flat exception hierarchy rooted at `EmbeddinatorError` in `backend/errors.py`, with one provider-layer exception (`ProviderRateLimitError`) living in `backend/providers/base.py`. Circuit breakers are implemented independently in `QdrantClientWrapper`, `QdrantStorage`, and the inference layer of `backend/agent/nodes.py`. Retry logic is applied as a `tenacity` decorator pattern on internal `_*_with_retry` methods. HTTP error responses follow a nested `{"error": {...}, "trace_id": ...}` shape in all REST routers, while NDJSON streaming errors follow a `{"type": "error", "message": ..., "code": ..., "trace_id": ...}` shape.

Spec 12 does **not** change the working exception hierarchy or circuit breaker behaviour — it documents the ground truth, adds missing error codes, and defines contract tests to prevent regressions.

---

## Requirements

### Functional Requirements

1. **FR-001 Exception Hierarchy**: All application exceptions extend `EmbeddinatorError` (note: two 'd's — `backend/errors.py`). The existing flat hierarchy is the authoritative shape; sub-grouping is by naming convention only, not by intermediate base classes.

2. **FR-002 Provider Rate-Limit Exception**: `ProviderRateLimitError` is defined in `backend/providers/base.py` and extends `Exception` directly (not `EmbeddinatorError`). It is the only application exception that lives outside `backend/errors.py`. This is a deliberate design choice from spec-10 and must not be changed.

3. **FR-003 Error Response Format**: All REST API error responses use a consistent two-level nested JSON body. The outer envelope contains `"error"` (an object) and `"trace_id"` (a string). The inner error object contains `"code"`, `"message"`, and `"details"` (an object, may be empty).

4. **FR-004 NDJSON Stream Error Format**: Errors during chat streaming (after the HTTP 200 response has started) are emitted as NDJSON lines: `{"type": "error", "message": "<user-facing>", "code": "<UPPER_SNAKE>", "trace_id": "<uuid>"}`.

5. **FR-005 HTTP Status Code Mapping**: Each error condition maps to a specific HTTP status code. The mapping is documented in the HTTP Status Code Mapping section of this spec.

6. **FR-006 Error Code Stability**: All `code` strings used in production responses are stable, uppercase snake_case identifiers. Frontend consumers may depend on these codes for routing and display decisions. Renaming a code is a breaking change.

7. **FR-007 Rate Limiting**: The `RateLimitMiddleware` implements a sliding-window in-memory per-IP rate limiter. When the limit is exceeded, it returns HTTP 429 with `{"error": {"code": "RATE_LIMIT_EXCEEDED", ...}, "trace_id": ...}` and a `Retry-After: 60` response header. Limit thresholds are configured in `backend/config.py` via four `Settings` fields (see Rate Limiting section).

8. **FR-008 Circuit Breaker — Qdrant**: `QdrantClientWrapper` and `QdrantStorage` each maintain independent in-memory circuit breakers. The circuit opens after `circuit_breaker_failure_threshold` consecutive failures (counted by `_record_failure()`). After the circuit opens, all calls immediately raise `CircuitOpenError`. The circuit transitions to half-open after `circuit_breaker_cooldown_secs` seconds; a single probe request is allowed through; success closes the circuit (resets failure count), failure re-opens it.

9. **FR-009 Circuit Breaker — Inference**: `backend/agent/nodes.py` maintains a module-level inference circuit breaker (`_inf_circuit_open`, `_inf_failure_count`, `_inf_last_failure_time`). Thresholds are read from `settings.circuit_breaker_failure_threshold` and `settings.circuit_breaker_cooldown_secs` on every call to `_check_inference_circuit()`. When open, it raises `CircuitOpenError("Inference service circuit breaker is open")`.

10. **FR-010 Retry Policy — Qdrant Operations**: Internal `_*_with_retry` methods on both `QdrantClientWrapper` and `QdrantStorage` are decorated with `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1), retry=retry_if_exception_type(Exception), reraise=True)`. This retries on any exception, up to 3 attempts, with jittered exponential backoff (1–10 seconds). The retry is applied to the inner method only; circuit-breaker recording happens in the outer public method after retries are exhausted.

11. **FR-011 Retry Policy — Ingestion Embed**: `IngestionPipeline._embed_with_retry()` uses a custom while-loop with exponential backoff (5s initial, 60s max), not the `@retry` decorator. It retries on `CircuitOpenError` and `httpx.ConnectError`/`ConnectTimeout`, pausing the job in the DB between attempts.

12. **FR-012 Cloud Provider Retry**: Cloud provider adapters (`openai.py`, `openrouter.py`, `anthropic.py`) retry once on 5xx or timeout, and raise `ProviderRateLimitError` on HTTP 429. This is handled inside the provider class, not with `tenacity`.

13. **FR-013 Internal Error Suppression**: Unhandled exceptions in the chat stream (`except Exception`) are caught and returned as `{"type": "error", "code": "SERVICE_UNAVAILABLE", ...}`. No stack trace or raw exception message is exposed to the client.

14. **FR-014 Debug Mode**: The `Settings.debug` field (boolean, default `False`) may be used in future development to conditionally include internal error details. Currently it is not used in error responses. Error codes and messages are the same in debug and production mode.

15. **FR-015 Structured Error Pydantic Models**: `ErrorDetail` and `ErrorResponse` are defined in `backend/agent/schemas.py`. They represent the nested inner structure used in REST error responses. These models are not used in NDJSON stream errors or the `ProviderRateLimitError` exception handler.

### Non-Functional Requirements

- **NFR-001**: Error handling overhead must add less than 1ms per request. Circuit breaker checks are O(1) in-memory comparisons. Rate limiter bucket cleanup is O(n) per request where n is the number of recent requests in the window (bounded by the limit value).
- **NFR-002**: Circuit breaker state is maintained in-memory per-process. It does not survive process restart or cross instances. This is a documented limitation, not a bug.
- **NFR-003**: No raw exception messages, module paths, or line numbers are exposed to external callers in production.
- **NFR-004**: All error codes are stable identifiers. New error conditions require new codes; existing codes must not be renamed or repurposed.
- **NFR-005**: The `Retry-After: 60` header must be present on all HTTP 429 responses from the `RateLimitMiddleware`.

---

## Key Technical Details

### Exception Hierarchy

The actual `backend/errors.py` as implemented through spec-11:

```python
# backend/errors.py
# All classes extend EmbeddinatorError directly (flat hierarchy, no domain subtrees).

class EmbeddinatorError(Exception):
    """Base exception for all Embedinator errors."""
    # NOTE: No __init__ override. No message/code/details fields on the base class.
    # Contextual information is passed as the exception message string.


# --- Storage layer (by convention) ---

class QdrantConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Qdrant."""

class OllamaConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Ollama."""

class SQLiteError(EmbeddinatorError):
    """SQLite operation failed."""


# --- Inference/LLM layer ---

class LLMCallError(EmbeddinatorError):
    """LLM inference call failed."""

class StructuredOutputParseError(EmbeddinatorError):
    """Failed to parse structured output from LLM."""

class RerankerError(EmbeddinatorError):
    """Cross-encoder reranking failed."""


# --- Ingestion layer ---

class EmbeddingError(EmbeddinatorError):
    """Embedding generation failed."""

class IngestionError(EmbeddinatorError):
    """Document ingestion pipeline failed."""


# --- Session layer ---

class SessionLoadError(EmbeddinatorError):
    """Failed to load session from SQLite."""


# --- Cross-cutting ---

class CircuitOpenError(EmbeddinatorError):
    """Raised when a circuit breaker is open (Qdrant or inference)."""
```

The provider-layer exception is separate from this hierarchy:

```python
# backend/providers/base.py
# Extends Exception directly, NOT EmbeddinatorError.

class ProviderRateLimitError(Exception):
    """Raised by cloud providers on HTTP 429 rate limit responses."""
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

**Classes from the original spec-12 draft that do NOT exist in the codebase** (and must not be created by spec-12 implementation agents):
- `StorageError`, `DatabaseError`, `DatabaseMigrationError`, `QdrantCollectionError`
- `RustWorkerError`, `EmbeddingValidationError`, `DuplicateDocumentError`
- `AgentError`, `ToolExecutionError`, `ConfidenceError`
- `ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ModelNotFoundError`
- `APIError`, `ValidationError`, `NotFoundError`, `ConflictError`

### HTTP Status Code Mapping

HTTP errors in REST routers are raised as `fastapi.HTTPException`. There is no global `EmbeddinatorError`-to-HTTP mapping in `main.py` (except for `ProviderRateLimitError`). Each router raises `HTTPException` directly with the appropriate status and a structured `detail` body.

| Error Condition | HTTP Status | Error Code | Router / Source |
|----------------|-------------|------------|----------------|
| Collection name fails regex | 400 | `COLLECTION_NAME_INVALID` | `api/collections.py` |
| Settings value out of range | 400 | `SETTINGS_VALIDATION_ERROR` | `api/settings.py` |
| Unsupported file type | 400 | `FILE_FORMAT_NOT_SUPPORTED` | `api/ingest.py` |
| Rate limit exceeded (middleware) | 429 | `RATE_LIMIT_EXCEEDED` | `middleware.py` |
| Provider rate limit (cloud) | 429 | `rate_limit` (lowercase) | `main.py` exception handler |
| Collection not found | 404 | `COLLECTION_NOT_FOUND` | `api/collections.py`, `api/ingest.py` |
| Document not found | 404 | `DOCUMENT_NOT_FOUND` | `api/documents.py` |
| Ingestion job not found | 404 | `JOB_NOT_FOUND` | `api/ingest.py` |
| Trace not found | 404 | `TRACE_NOT_FOUND` | `api/traces.py` |
| Provider not found | 404 | `PROVIDER_NOT_FOUND` | `api/providers.py` |
| Collection name conflict | 409 | `COLLECTION_NAME_CONFLICT` | `api/collections.py` |
| Duplicate document (same hash) | 409 | `DUPLICATE_DOCUMENT` | `api/ingest.py` |
| File too large (> max_upload_size_mb) | 413 | `FILE_TOO_LARGE` | `api/ingest.py` |
| Encryption key not configured | 503 | `KEY_MANAGER_UNAVAILABLE` | `api/providers.py` |
| Ollama unreachable (models endpoint) | 503 | `SERVICE_UNAVAILABLE` | `api/models.py` |
| Unhandled exception (fallback) | 500 | (default FastAPI detail) | FastAPI default handler |

**Note**: There is no registered global `EmbeddinatorError` exception handler in `main.py`. Storage and ingestion errors that propagate to FastAPI's default handler will return HTTP 500 with FastAPI's default error format (`{"detail": "Internal Server Error"}`), not the nested `{"error": {...}}` format. Spec-12 should add a global `EmbeddinatorError` exception handler to ensure consistent formatting.

**Note on `ProviderRateLimitError` code**: The exception handler in `main.py` currently uses `"code": "rate_limit"` (lowercase, inconsistent with the `UPPER_SNAKE_CASE` convention). This is a code inconsistency that spec-12 should correct to `"PROVIDER_RATE_LIMIT"`.

### Error Response Format

#### REST API Error Response

All REST routers (collections, documents, ingest, traces, providers, settings, models) use the following structure for `HTTPException.detail`:

```python
{
    "error": {
        "code": "UPPER_SNAKE_CASE_CODE",     # machine-readable, stable identifier
        "message": "Human-readable message", # user-facing text
        "details": {                          # optional structured context, may be {}
            "field": "value",
        },
    },
    "trace_id": "req-uuid-here",             # from request.state.trace_id
}
```

The Pydantic models backing this shape (in `backend/agent/schemas.py`):

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorDetail
    # Note: trace_id is added directly in the dict, NOT via this model
```

**The `trace_id` is not part of `ErrorResponse`** — it is appended manually in each router as a top-level sibling of `"error"` in the `HTTPException.detail` dict.

#### Rate Limit Response (middleware)

```python
# HTTP 429 from RateLimitMiddleware
{
    "error": {
        "code": "RATE_LIMIT_EXCEEDED",
        "message": "Rate limit exceeded: {limit} requests per minute",
        "details": {"retry_after_seconds": 60},
    },
    "trace_id": "req-uuid-here",
}
# Header: Retry-After: 60
```

#### ProviderRateLimitError Response (exception handler)

```python
# HTTP 429 from main.py exception_handler(ProviderRateLimitError)
# CURRENT (inconsistent): uses lowercase "rate_limit" code and "type" field
{
    "type": "error",
    "message": "Rate limit exceeded for provider: {provider_name}",
    "code": "rate_limit",   # ISSUE: should be PROVIDER_RATE_LIMIT per convention
}
# Note: no trace_id, no nested "error" object — inconsistent with REST format
```

Spec-12 should standardise this to:

```python
# TARGET for spec-12:
{
    "error": {
        "code": "PROVIDER_RATE_LIMIT",
        "message": "Rate limit exceeded for provider: {provider_name}",
        "details": {"provider": "{provider_name}"},
    },
    "trace_id": "req-uuid-here",  # from request.state.trace_id
}
```

#### NDJSON Stream Error Events

Streaming errors (from `backend/api/chat.py`) are emitted as NDJSON lines on the already-started HTTP 200 response body:

```json
{"type": "error", "message": "<user-facing message>", "code": "<CODE>", "trace_id": "<uuid>"}
```

The full set of error NDJSON codes and their trigger conditions:

| Code | Trigger Condition | Message |
|------|------------------|---------|
| `NO_COLLECTIONS` | `body.collection_ids` is empty or missing | "Please select at least one collection before searching." |
| `CIRCUIT_OPEN` | `CircuitOpenError` raised during graph execution | "A required service is temporarily unavailable. Please try again in a few seconds." |
| `SERVICE_UNAVAILABLE` | Any other unhandled `Exception` during graph execution | "Unable to process your request. Please retry." |

**Important**: The spec's original draft listed `OLLAMA_UNAVAILABLE` as a stream error code. This code does not exist anywhere in the implementation. The actual codes are `CIRCUIT_OPEN` and `SERVICE_UNAVAILABLE`.

### Error Propagation Rules

| Layer | Errors Raised | Propagation Behaviour | Notes |
|-------|--------------|----------------------|-------|
| `storage/qdrant_client.py` (`QdrantClientWrapper`) | `CircuitOpenError` | Propagates up | Raw Qdrant `Exception` wrapped after retries |
| `storage/qdrant_client.py` (`QdrantStorage`) | `CircuitOpenError`, raw `Exception` from Qdrant | Propagates up | Same pattern as QdrantClientWrapper |
| `storage/sqlite_db.py` | `SQLiteError` | Propagates up | Wraps `aiosqlite.Error` |
| `storage/parent_store.py` | `SQLiteError` | Propagates up | Wraps raw DB exceptions |
| `storage/document_parser.py` | `IngestionError` | Propagates up | File-not-found, unsupported format, no text extracted |
| `providers/ollama.py` | `OllamaConnectionError`, `LLMCallError`, `EmbeddingError` | Propagates up | httpx connection errors → OllamaConnectionError; others → LLMCallError or EmbeddingError |
| `providers/openai.py`, `openrouter.py`, `anthropic.py` | `ProviderRateLimitError`, raw `httpx` exceptions | Propagates up | 429 → ProviderRateLimitError; one retry on 5xx before re-raise |
| `agent/nodes.py` | `CircuitOpenError` | Propagates to chat.py | Inference circuit breaker checks; node-level failures mostly swallowed with fallback behaviour |
| `retrieval/searcher.py` | `QdrantConnectionError` | Propagates up | Circuit breaker open → QdrantConnectionError |
| `ingestion/pipeline.py` | `IngestionError` (indirectly via document_parser) | Writes to job record, returns `IngestionResult(status="failed")` | Does NOT re-raise; failure is surfaced via job status polling |
| `api/*` routers | `HTTPException` | HTTP error response | Each router raises directly with nested `detail` body |
| `api/chat.py` | NDJSON error event | Stream error line | CircuitOpenError and Exception both caught |

### Circuit Breaker Configuration

The circuit breaker parameters are configured via `backend/config.py` `Settings` fields:

| Config Field | Settings Attribute | Default | Env Var |
|-------------|-------------------|---------|---------|
| Failure threshold (consecutive) | `circuit_breaker_failure_threshold` | `5` | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| Cooldown duration | `circuit_breaker_cooldown_secs` | `30` | `CIRCUIT_BREAKER_COOLDOWN_SECS` |

There is no window duration (the original spec's "60-second window" does not exist in the implementation). The circuit breaker counts **consecutive** failures with no time decay. Failures are only reset by a successful call (`_record_success()`).

There are **three independent circuit breakers** in the codebase:

1. `QdrantClientWrapper._circuit_open` — in `backend/storage/qdrant_client.py`
2. `QdrantStorage._circuit_open` — in `backend/storage/qdrant_client.py`
3. Inference circuit breaker (`_inf_circuit_open`) — module-level globals in `backend/agent/nodes.py`

All three read their thresholds from `settings.circuit_breaker_failure_threshold` and `settings.circuit_breaker_cooldown_secs`. The inference circuit breaker reads these on every call (allowing runtime config changes), while the Qdrant circuit breakers read them once at construction time.

### Circuit Breaker State Machine

```
CLOSED (normal operation)
  |
  |-- consecutive failure count reaches circuit_breaker_failure_threshold -->
  v
OPEN (all calls raise CircuitOpenError immediately)
  |
  |-- time.monotonic() - _last_failure_time >= circuit_breaker_cooldown_secs -->
  v
HALF-OPEN (one probe request is allowed through; circuit_open flag set to False)
  |
  |-- probe succeeds --> _record_success() --> CLOSED (failure count reset to 0)
  |-- probe fails    --> _record_failure() --> OPEN (if count >= threshold again)
```

Key implementation notes:
- The transition from OPEN to HALF-OPEN happens inside `_check_circuit()`, not in a background task. The circuit is only checked when a caller invokes a protected method.
- `_record_failure()` increments `_failure_count` and sets `_last_failure_time`. It only sets `_circuit_open = True` when `_failure_count >= _max_failures`.
- `_record_success()` resets `_failure_count = 0` and `_circuit_open = False`.
- There is no explicit HALF-OPEN state flag — it is implicit: `_circuit_open` is set to `False` inside `_check_circuit()` when the cooldown has elapsed.

### Retry Policy

All Qdrant operations use the `@retry` decorator from `tenacity` applied to internal `_*_with_retry` methods:

```python
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
    retry=retry_if_exception_type(Exception),  # retries on ANY exception
    reraise=True,
)
async def _some_operation_with_retry(self, ...):
    ...
```

Key points:
- The `multiplier=1, min=1, max=10` parameters mean backoff starts at 1 second and caps at 10 seconds.
- `wait_random(0, 1)` adds up to 1 second of jitter to prevent thundering herd.
- `reraise=True` means the last exception is re-raised after all attempts are exhausted.
- The retry decorator is on the **inner** method. The outer public method calls the inner method, records circuit-breaker outcomes, and does not use tenacity itself.
- The `retry_max_attempts` and `retry_backoff_initial_secs` config fields in `Settings` are **not** used by the tenacity decorators (they are hardcoded at `3` and `multiplier=1`). Those config fields are available for future use.

Ingestion embed retry (pipeline.py) uses a custom loop, **not** tenacity:

```python
backoff = 5.0    # initial backoff in seconds
max_backoff = 60.0

while True:
    try:
        return await self.embedder.embed_chunks(texts)
    except (CircuitOpenError, httpx.ConnectError, httpx.ConnectTimeout):
        await self.db.update_ingestion_job(job_id, status="paused")
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)
```

---

## Dependencies

### Spec Dependencies

| Spec | Dependency Reason |
|------|------------------|
| spec-02-conversation-graph | `CircuitOpenError` caught in `chat.py` stream handler |
| spec-03-research-graph | `QdrantConnectionError` raised in `retrieval/searcher.py` |
| spec-04-meta-reasoning | `CircuitOpenError` may be raised during meta-reasoning node LLM calls |
| spec-05-accuracy | Inference circuit breaker implemented in `agent/nodes.py`; `verify_groundedness` error fallback |
| spec-06-ingestion | `IngestionError`, `EmbeddingError` raised in `ingestion/` modules |
| spec-07-storage | `SQLiteError`, `QdrantConnectionError`, `CircuitOpenError` raised in `storage/` modules |
| spec-08-api | All REST routers use the `HTTPException` + nested `detail` pattern |
| spec-10-providers | `ProviderRateLimitError` in `providers/base.py`; exception handler in `main.py` |
| spec-11-interfaces | Contract tests reference error types for expected raise conditions |

### Package Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `tenacity` | `>=9.0` | Retry with exponential backoff + jitter on Qdrant operations |
| `pydantic` | `>=2.12` | `ErrorDetail`, `ErrorResponse` models in `backend/agent/schemas.py` |
| `structlog` | `>=24.0` | Structured JSON error logging in all layers |
| `fastapi` | `>=0.135` | `HTTPException`, `Request`, `JSONResponse` for error responses |

---

## Acceptance Criteria

1. `backend/errors.py` contains exactly these classes: `EmbeddinatorError`, `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError`. All extend `EmbeddinatorError` directly. No other classes are present.

2. `ProviderRateLimitError` is defined in `backend/providers/base.py` and extends `Exception` directly. It has `provider: str` attribute and a `__init__(self, provider: str)` signature.

3. All REST API error responses from the `backend/api/` routers use the `{"error": {"code": ..., "message": ..., "details": {...}}, "trace_id": ...}` nested format.

4. The `ProviderRateLimitError` exception handler in `backend/main.py` uses the same nested format and returns `code: "PROVIDER_RATE_LIMIT"` (uppercase, consistent with convention).

5. NDJSON streaming error events from `backend/api/chat.py` use the `{"type": "error", "message": ..., "code": ..., "trace_id": ...}` flat format. The defined codes are: `NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`.

6. `RateLimitMiddleware` returns HTTP 429 with `code: "RATE_LIMIT_EXCEEDED"` and `Retry-After: 60` header.

7. A global `EmbeddinatorError` exception handler is registered in `create_app()` in `backend/main.py` that maps any unhandled `EmbeddinatorError` to HTTP 500 with the standard nested error format and `code: "INTERNAL_ERROR"`.

8. Circuit breaker opens after `settings.circuit_breaker_failure_threshold` consecutive failures (default 5). It allows one probe after `settings.circuit_breaker_cooldown_secs` seconds (default 30). It closes on probe success.

9. Qdrant `_*_with_retry` methods use `stop_after_attempt(3)` with `wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1)`. The tenacity config hardcodes 3 attempts at the call site.

10. `ErrorDetail` and `ErrorResponse` Pydantic models exist in `backend/agent/schemas.py` with the documented fields. `trace_id` is NOT a field on `ErrorResponse`.

11. Contract tests in `tests/unit/test_error_contracts.py` verify:
    - All required exception classes exist in `backend/errors.py`
    - All required classes extend `EmbeddinatorError`
    - `ProviderRateLimitError` is in `backend/providers/base.py` and extends `Exception`
    - `ErrorDetail` has `code: str`, `message: str`, `details: dict` fields
    - `ErrorResponse` has `error: ErrorDetail` field
    - Circuit breaker config fields exist in `Settings` with correct types and defaults
    - Rate limiting config fields exist in `Settings` with correct types and defaults

12. No raw Python exception messages, module paths, or traceback text is present in any error response sent to clients under normal (non-debug) operation.

---

## Architecture Reference

### All NDJSON Event Types (Chat Stream)

For reference, the full set of NDJSON event types emitted by `POST /api/chat`:

| Event Type | Fields | When Emitted |
|------------|--------|-------------|
| `session` | `session_id` | Before graph execution starts |
| `status` | `node` | On each LangGraph node transition |
| `chunk` | `text` | For each AI message chunk |
| `clarification` | `question` | When graph requests clarification (stream ends here) |
| `citation` | `citations` (list) | After graph completes, if citations exist |
| `meta_reasoning` | `strategies_attempted` (list) | If meta-reasoning strategies were attempted |
| `confidence` | `score` (int 0–100) | Always emitted after graph completes |
| `groundedness` | `overall_grounded`, `supported`, `unsupported`, `contradicted` | If groundedness check ran and has result |
| `done` | `latency_ms`, `trace_id` | Last event on success |
| `error` | `message`, `code`, `trace_id` | On error (replaces `done`) |

**Note**: `clarification` ends the stream without `done`. This is intentional per spec-09 — the frontend must release `isStreaming` on `done`, `error`, OR `clarification`.

### Per-Node Error Behaviour

| Node | Error Condition | Behaviour |
|------|----------------|-----------|
| `init_session` | Any DB exception | Catches exception, returns empty messages with state defaults (does NOT raise) |
| `classify_intent` | Any exception (LLM error, JSON parse, invalid intent) | Catches exception, defaults to `"rag_query"` (does NOT raise) |
| `rewrite_query` | First attempt fails (ValidationError or any) | Retries once with simplified prompt; on second failure uses safe fallback `QueryAnalysis` |
| `fan_out` | Called | Raises `NotImplementedError` — this is a dead stub, routing bypasses it |
| `aggregate_answers` | No valid sub-answers | Returns fallback response text with `confidence_score: 0` (does NOT raise) |
| `verify_groundedness` | Inference circuit open | `_check_inference_circuit()` raises `CircuitOpenError`; caught by `chat.py` |
| `verify_groundedness` | LLM call fails | Caught; returns `groundedness_result: None` (does NOT raise) |
| `validate_citations` | Any exception | Caught; passes citations through unvalidated (does NOT raise) |
| `generate_answer` | Inference circuit open | `_check_inference_circuit()` raises `CircuitOpenError`; propagates to `chat.py` |
| `generate_answer` | LLM failure | Raises `LLMCallError`; propagates to `chat.py` as generic stream error |
| `orchestrator` (research) | Any exception | Caught; triggers `fallback_response` path |

### Rate Limiting Configuration

Rate limits are configured in `Settings` and enforced by `RateLimitMiddleware` (sliding-window per-IP, 60-second window):

| `Settings` Field | Default | Env Var | Applied To |
|-----------------|---------|---------|-----------|
| `rate_limit_chat_per_minute` | `30` | `RATE_LIMIT_CHAT_PER_MINUTE` | `POST /api/chat` |
| `rate_limit_ingest_per_minute` | `10` | `RATE_LIMIT_INGEST_PER_MINUTE` | `POST /api/collections/*/ingest` |
| `rate_limit_provider_keys_per_minute` | `5` | `RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE` | `PUT /api/providers/*/key` and `DELETE /api/providers/*/key` |
| `rate_limit_general_per_minute` | `120` | `RATE_LIMIT_GENERAL_PER_MINUTE` | All other endpoints |

The middleware uses path matching:
- `PUT` or `DELETE` on a path matching `^/api/providers/[^/]+/key$` → provider key bucket
- `POST /api/chat` → chat bucket
- `POST` on a path containing `/ingest` → ingest bucket
- All other requests → general bucket

Rate limit buckets are keyed by `"{bucket_type}:{client_ip}"`. The `client_ip` is taken from `request.client.host` (defaulting to `"unknown"` if unavailable).

### Global Exception Handler (Spec-12 Addition)

Spec-12 adds the following global handler to `create_app()` in `backend/main.py`:

```python
from backend.errors import EmbeddinatorError

@app.exception_handler(EmbeddinatorError)
async def embedinator_error_handler(request: Request, exc: EmbeddinatorError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

This ensures that any `EmbeddinatorError` that propagates out of a router (e.g., `SQLiteError`, `QdrantConnectionError`) returns the standard nested error format rather than FastAPI's default `{"detail": "Internal Server Error"}`.

**Subclass specificity**: FastAPI's exception handler resolution uses MRO order. More specific subclasses can be registered with their own handlers. For example, a future `QdrantConnectionError` handler could return 503 instead of 500. The `EmbeddinatorError` handler acts as the catch-all fallback.

### Known Code Inconsistencies (To Be Fixed in Spec-12)

1. **`ProviderRateLimitError` handler in `main.py`** uses `"code": "rate_limit"` (lowercase) and `"type": "error"` (NDJSON-style) in a REST context. Target: `"code": "PROVIDER_RATE_LIMIT"` with the standard nested error format.

2. **No global `EmbeddinatorError` handler**: Storage errors that propagate out of routers return FastAPI's default 500 format, not the nested format. Target: register the global handler shown above.

3. **Retry config fields unused by tenacity**: `settings.retry_max_attempts` and `settings.retry_backoff_initial_secs` exist in `Settings` but the tenacity decorators hardcode `stop_after_attempt(3)` and `wait_exponential(multiplier=1, min=1, max=10)`. Spec-12 may wire these up, or document that the config fields are reserved for future use.

4. **Inference circuit breaker globals in `nodes.py`**: The three module-level globals (`_inf_circuit_open`, `_inf_failure_count`, `_inf_last_failure_time`) could be extracted into a reusable `CircuitBreaker` class shared with `QdrantClientWrapper` and `QdrantStorage`. This is a refactoring opportunity, not a bug.
