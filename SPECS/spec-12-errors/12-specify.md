# Spec 12: Error Handling Specification -- Feature Specification Context

## Feature Description

The Error Handling Specification defines a structured exception hierarchy, standardized error response format, per-layer error propagation rules, retry policies with exponential backoff, and circuit breaker configuration for The Embedinator. Every exception in the system extends a base `EmbdinatorError` class and carries a machine-readable error code, a user-facing message, and optional diagnostic details. The API layer maps exceptions to HTTP status codes and returns a consistent JSON error response format.

The system uses `tenacity` for retry with exponential backoff on transient failures (Qdrant, Ollama), and implements a circuit breaker pattern that trips after consecutive failures to prevent cascading timeouts.

## Requirements

### Functional Requirements

1. **Exception Hierarchy**: A single base class `EmbdinatorError` with four domain-specific subtrees: Storage, Ingestion, Agent, Provider, and API errors
2. **Error Response Format**: Standardized `ErrorResponse` Pydantic model with `detail` (user-facing), `code` (machine-readable), `trace_id` (debugging), and optional `internal` details (dev mode only)
3. **HTTP Status Code Mapping**: Each exception class maps to a specific HTTP status code (400, 401, 404, 409, 413, 429, 500, 503)
4. **Error Propagation Rules**: Each architectural layer (storage, ingestion, agent, API) has defined rules for which errors it catches, which it wraps, and which it bubbles up
5. **Retry Policy**: Configurable retry with exponential backoff on transient failures. Default: 3 attempts, 1.0s initial backoff, 10s max backoff
6. **Circuit Breaker**: State machine (closed -> open -> half-open) that trips after 5 consecutive failures within a 60-second window, cools down for 30 seconds before allowing a probe request
7. **User-Facing Error Messages**: Predefined human-readable messages for every error type -- no internal details leaked to users in production mode

### Non-Functional Requirements

- Error handling must add less than 1ms overhead per request (no heavy logging in the hot path)
- Circuit breaker state must be maintained in-memory (no external dependency)
- Internal error details (stack traces, raw exceptions) must only appear when `DEBUG_MODE=true`
- Error codes must be stable across versions for frontend consumption

## Key Technical Details

### Exception Hierarchy

```python
# backend/errors.py

class EmbdinatorError(Exception):
    """Base exception for all Embedinator errors."""
    def __init__(self, message: str, code: str, details: Optional[dict] = None):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)

# --- Storage layer ---
class StorageError(EmbdinatorError): ...
class QdrantConnectionError(StorageError): ...
class QdrantCollectionError(StorageError): ...
class DatabaseError(StorageError): ...
class DatabaseMigrationError(StorageError): ...

# --- Ingestion layer ---
class IngestionError(EmbdinatorError): ...
class RustWorkerError(IngestionError): ...
class FileValidationError(IngestionError): ...
class EmbeddingError(IngestionError): ...
class EmbeddingValidationError(IngestionError): ...
class DuplicateDocumentError(IngestionError): ...

# --- Agent layer ---
class AgentError(EmbdinatorError): ...
class LLMCallError(AgentError): ...
class StructuredOutputParseError(AgentError): ...
class RerankerError(AgentError): ...
class ToolExecutionError(AgentError): ...
class ConfidenceError(AgentError): ...

# --- Provider layer ---
class ProviderError(EmbdinatorError): ...
class ProviderNotConfiguredError(ProviderError): ...
class ProviderAuthError(ProviderError): ...
class ProviderRateLimitError(ProviderError): ...
class ModelNotFoundError(ProviderError): ...

# --- API layer ---
class APIError(EmbdinatorError): ...
class ValidationError(APIError): ...
class NotFoundError(APIError): ...
class ConflictError(APIError): ...
```

### HTTP Status Code Mapping

| Exception Class | HTTP Status | Error Code | User Message |
|----------------|-------------|------------|-------------|
| `ValidationError` | 400 | `VALIDATION_ERROR` | Field-specific error messages |
| `FileValidationError` | 400 | `INVALID_FILE` | "Unsupported file type" / "File too large" |
| `NotFoundError` | 404 | `NOT_FOUND` | "Resource not found" |
| `ConflictError` | 409 | `CONFLICT` | "Resource already exists" |
| `DuplicateDocumentError` | 409 | `DUPLICATE_DOCUMENT` | "Document already ingested" |
| `ProviderAuthError` | 401 | `PROVIDER_AUTH_ERROR` | "Invalid API key for provider" |
| `ProviderRateLimitError` | 429 | `RATE_LIMITED` | "Provider rate limit reached, try again later" |
| `QdrantConnectionError` | 503 | `QDRANT_UNAVAILABLE` | "Vector database unavailable" |
| `LLMCallError` | 503 | `LLM_UNAVAILABLE` | "Inference service unavailable" |
| `EmbeddingError` | 503 | `EMBEDDING_UNAVAILABLE` | "Embedding service unavailable" |
| Unhandled `Exception` | 500 | `INTERNAL_ERROR` | "An internal error occurred" |

### Error Response Format

```python
class ErrorResponse(BaseModel):
    detail: str          # user-facing message
    code: str            # machine-readable error code
    trace_id: Optional[str] = None  # request trace ID for debugging
    # Internal details (only in dev mode, stripped in production):
    internal: Optional[dict] = None  # stack trace, raw error, etc.
```

### Error Propagation Rules

| Layer | Catches | Bubbles Up | Notes |
|-------|---------|-----------|-------|
| Storage (`qdrant_client`, `sqlite_db`) | Raw HTTP/DB errors | `QdrantConnectionError`, `DatabaseError` | Wraps raw exceptions with context |
| Ingestion (`pipeline`, `embedder`) | Storage errors, Rust worker errors | `IngestionError` subtypes | Logs per-chunk failures, continues batch |
| Agent (`nodes`, `tools`) | LLM errors, tool errors | `AgentError` subtypes | Node-specific fallback before bubbling |
| API (`routes`) | All `EmbdinatorError` subtypes | HTTP error responses | Maps to status codes, logs internally |

### Circuit Breaker Configuration

| Parameter | Value | Configurable Via |
|-----------|-------|-----------------|
| Failure threshold (consecutive) | 5 | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` |
| Window duration | 60 seconds | -- |
| Cooldown (open -> half-open) | 30 seconds | `CIRCUIT_BREAKER_COOLDOWN_SECS` |
| Retry attempts per call | 3 | `RETRY_MAX_ATTEMPTS` |
| Retry backoff initial | 1.0 seconds | `RETRY_BACKOFF_INITIAL_SECS` |
| Retry backoff max | 10 seconds | -- |

### Circuit Breaker State Machine

```
CLOSED (normal operation)
  |
  |-- failure count reaches threshold -->
  |
OPEN (all calls fail immediately with cached error)
  |
  |-- cooldown timer expires -->
  |
HALF-OPEN (allow one probe request)
  |
  |-- probe succeeds --> CLOSED (reset failure count)
  |-- probe fails --> OPEN (reset cooldown timer)
```

### Retry Policy

Implemented using `tenacity` library:

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, max=10),
    retry=retry_if_exception_type((QdrantConnectionError, EmbeddingError, LLMCallError)),
)
async def call_with_retry(func, *args, **kwargs):
    return await func(*args, **kwargs)
```

## Dependencies

### Spec Dependencies
- **spec-07-storage**: Storage errors originate from Qdrant and SQLite operations
- **spec-06-ingestion**: Ingestion errors wrap storage and Rust worker failures
- **spec-02/03/04-agent**: Agent errors wrap LLM, tool, and reranker failures
- **spec-10-providers**: Provider errors for auth, rate limiting, and missing config
- **spec-08-api**: API routes consume the error hierarchy for HTTP response mapping
- **spec-11-interfaces**: All interface contracts reference these error types

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `tenacity` | `>=9.0` | Retry with exponential backoff + circuit breaker |
| `pydantic` | `>=2.12` | `ErrorResponse` model |
| `structlog` | `>=24.0` | Structured error logging |

## Acceptance Criteria

1. All exception classes are defined in `backend/errors.py` extending `EmbdinatorError`
2. Every exception carries `message`, `code`, and `details` fields
3. FastAPI exception handler maps every `EmbdinatorError` subclass to the correct HTTP status code
4. Unhandled exceptions return 500 with `INTERNAL_ERROR` code and no internal details in production
5. `ErrorResponse` model is used for all error responses
6. Internal details (`stack trace`, `raw error`) only appear when `DEBUG_MODE=true`
7. Circuit breaker trips after 5 consecutive failures within 60 seconds
8. Circuit breaker recovers via half-open probe after 30-second cooldown
9. Retry policy retries transient errors (503-class) up to 3 times with exponential backoff
10. Error propagation follows the documented layer rules -- no raw exceptions leak across layer boundaries
11. All error codes are stable strings consumable by the frontend

## Architecture Reference

### SSE Error Events

Errors during chat streaming are sent as SSE events (not HTTP error responses, since the stream has already begun):

```
data: {"type": "error", "message": "Inference service unavailable", "code": "OLLAMA_UNAVAILABLE"}
```

### Per-Node Error Behavior

Key agent node error behaviors (documented in spec-11 contracts):

| Node | Error | Behavior |
|------|-------|----------|
| `classify_intent` | `LLMCallError` | Caught, defaults to `"rag_query"` |
| `rewrite_query` | `StructuredOutputParseError` | Retry once, then single-question fallback |
| `verify_groundedness` | `LLMCallError` | Caught, sets `groundedness_result=None` |
| `validate_citations` | `RerankerError` | Caught, passes citations through unvalidated |
| `orchestrator` | `LLMCallError` | Triggers `fallback_response` |

### Rate Limiting Configuration

| Endpoint | Limit | Window | Purpose |
|----------|-------|--------|---------|
| `POST /api/chat` | 30 requests | per minute | Prevent runaway query loops |
| `POST /api/collections/{id}/ingest` | 10 requests | per minute | Prevent ingestion flooding |
| `PUT /api/providers/{name}/key` | 5 requests | per minute | Prevent brute-force key testing |
| All other endpoints | 120 requests | per minute | General protection |
