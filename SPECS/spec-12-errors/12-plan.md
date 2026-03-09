# Spec 12: Error Handling Specification -- Implementation Plan Context

## Component Overview

The error handling system provides a structured exception hierarchy, standardized error responses, retry logic with exponential backoff, and circuit breaker protection for The Embedinator. It ensures that all errors are caught, categorized, and presented to users with meaningful messages while preserving internal diagnostic details for developers. The circuit breaker prevents cascading failures when external services (Qdrant, Ollama) are down.

## Technical Approach

### Exception Hierarchy Design
- Single `EmbdinatorError` base class with `message`, `code`, and `details` fields
- Four domain subtrees: Storage, Ingestion, Agent, Provider (plus API for route-level errors)
- Each exception class has a default `code` value matching the HTTP error code mapping
- All exceptions are picklable for potential future task queue use

### FastAPI Integration
- Register a global exception handler for `EmbdinatorError` that maps exception type to HTTP status
- Register a fallback handler for unhandled `Exception` that returns 500 with `INTERNAL_ERROR`
- Use `request.state.trace_id` for error response correlation
- Strip `internal` details from `ErrorResponse` unless `DEBUG_MODE=true`

### Retry and Circuit Breaker
- Use `tenacity` library for retry with exponential backoff
- Implement a custom `CircuitBreaker` class (in-memory, no external dependencies)
- Apply circuit breaker to Qdrant operations and Ollama/provider API calls
- Circuit breaker wraps individual service calls, not entire request handlers

## File Structure

```
backend/
  errors.py              # Exception hierarchy (all custom exceptions)
  middleware.py           # CORS, rate limiting, trace ID injection, error handlers
  circuit_breaker.py      # CircuitBreaker class with state machine
```

## Implementation Steps

### Step 1: Exception Hierarchy (`backend/errors.py`)
1. Define `EmbdinatorError(Exception)` base with `message: str`, `code: str`, `details: Optional[dict]`
2. Define Storage errors: `StorageError`, `QdrantConnectionError`, `QdrantCollectionError`, `DatabaseError`, `DatabaseMigrationError`
3. Define Ingestion errors: `IngestionError`, `RustWorkerError`, `FileValidationError`, `EmbeddingError`, `EmbeddingValidationError`, `DuplicateDocumentError`
4. Define Agent errors: `AgentError`, `LLMCallError`, `StructuredOutputParseError`, `RerankerError`, `ToolExecutionError`, `ConfidenceError`
5. Define Provider errors: `ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ProviderRateLimitError`, `ModelNotFoundError`
6. Define API errors: `APIError`, `ValidationError`, `NotFoundError`, `ConflictError`
7. Define `ErrorResponse(BaseModel)` with `detail`, `code`, `trace_id`, `internal`

### Step 2: HTTP Status Code Mapping
1. Create a mapping dict: `EXCEPTION_STATUS_MAP: dict[type[EmbdinatorError], int]`
2. Map each exception class to its HTTP status code
3. Register as FastAPI exception handler in `backend/main.py`

### Step 3: Global Exception Handler (`backend/middleware.py`)
1. Create `embedinator_exception_handler(request, exc)` function
2. Look up HTTP status from `EXCEPTION_STATUS_MAP`
3. Build `ErrorResponse` with user-facing `detail`, error `code`, and `trace_id` from request state
4. Conditionally include `internal` details (stack trace, raw error) only when `DEBUG_MODE=true`
5. Create `generic_exception_handler(request, exc)` for unhandled exceptions
6. Return 500 with `INTERNAL_ERROR` code and generic message
7. Log the full exception with structlog for debugging

### Step 4: Circuit Breaker (`backend/circuit_breaker.py`)
1. Define `CircuitBreakerState` enum: `CLOSED`, `OPEN`, `HALF_OPEN`
2. Create `CircuitBreaker` class with configurable `failure_threshold`, `window_duration`, `cooldown_secs`
3. Implement `call(func, *args, **kwargs)` method:
   - If CLOSED: execute normally, track failures
   - If OPEN: raise `ServiceUnavailableError` immediately (with last error info)
   - If HALF_OPEN: allow one probe call; on success -> CLOSED, on failure -> OPEN
4. Implement `record_success()` and `record_failure()` methods
5. Implement `_should_trip()` check: N consecutive failures within window
6. Thread-safe via `asyncio.Lock` for async contexts

### Step 5: Retry Decorators
1. Create retry wrapper functions using `tenacity`:
   - `retry_qdrant`: Retry on `QdrantConnectionError`, 3 attempts, exponential backoff
   - `retry_llm`: Retry on `LLMCallError`, 3 attempts, exponential backoff
   - `retry_embedding`: Retry on `EmbeddingError`, 3 attempts, exponential backoff
2. Create a generic `with_retry(retry_on, max_attempts, initial_backoff)` factory

### Step 6: SSE Error Handling
1. Define `format_sse_error(error: EmbdinatorError) -> str` function
2. Format error as SSE event: `data: {"type": "error", "message": "...", "code": "..."}`
3. Use in chat streaming endpoint to send errors mid-stream

### Step 7: Rate Limiter
1. Create `RateLimiter` class with in-memory sliding window counter
2. Configure per-endpoint limits:
   - `POST /api/chat`: 30/min
   - `POST /api/collections/{id}/ingest`: 10/min
   - `PUT /api/providers/{name}/key`: 5/min
   - All others: 120/min
3. Implement as FastAPI dependency injection

### Step 8: Testing
1. Unit tests for exception hierarchy: verify inheritance, code/message fields
2. Unit tests for circuit breaker: state transitions (closed -> open -> half-open -> closed)
3. Unit tests for retry: verify retry count, backoff timing
4. Integration tests for exception handler: verify HTTP status codes for each exception type
5. Test that `internal` details are stripped in production mode

## Integration Points

- **All backend modules** use exception classes from `backend/errors.py`
- **Storage layer** (`spec-07`): Wraps raw Qdrant/SQLite errors into `StorageError` subtypes
- **Ingestion layer** (`spec-06`): Catches storage errors, wraps into `IngestionError` subtypes
- **Agent layer** (`spec-02/03/04`): Catches LLM/tool errors, uses node-specific fallback
- **Provider layer** (`spec-10`): Raises `ProviderError` subtypes for auth, rate limiting
- **API layer** (`spec-08`): Global exception handler maps to HTTP responses
- **Frontend** (`spec-09`): Consumes `ErrorResponse` format and displays `detail` messages

## Key Code Patterns

### Exception Handler Pattern
```python
@app.exception_handler(EmbdinatorError)
async def embedinator_exception_handler(request: Request, exc: EmbdinatorError):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    response = ErrorResponse(
        detail=exc.message,
        code=exc.code,
        trace_id=getattr(request.state, "trace_id", None),
    )
    if settings.DEBUG_MODE:
        response.internal = {"traceback": traceback.format_exc(), "details": exc.details}
    return JSONResponse(status_code=status_code, content=response.model_dump(exclude_none=True))
```

### Circuit Breaker Usage Pattern
```python
qdrant_breaker = CircuitBreaker(failure_threshold=5, cooldown_secs=30)

async def search_qdrant(query, collection):
    return await qdrant_breaker.call(qdrant_client.hybrid_search, query, collection)
```

### Retry Usage Pattern
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1.0, max=10),
    retry=retry_if_exception_type(QdrantConnectionError),
)
async def upsert_with_retry(collection, points):
    await qdrant.upsert_batch(collection, points)
```

### Error Wrapping Pattern
```python
# Storage layer wraps raw errors
async def hybrid_search(self, ...):
    try:
        result = await self.client.search(...)
    except Exception as e:
        raise QdrantConnectionError(
            message="Failed to execute search query",
            code="QDRANT_UNAVAILABLE",
            details={"original_error": str(e), "collection": collection_name},
        ) from e
```

## Phase Assignment

- **Phase 1 (MVP)**: Full exception hierarchy in `backend/errors.py`. Global exception handler with HTTP status mapping. Circuit breaker + retry on Qdrant and Ollama calls. `ErrorResponse` model. Rate limiting on key endpoints.
- **Phase 2**: SSE error event formatting for mid-stream errors. Enhanced structured logging of errors with trace ID propagation.
- **Phase 3**: Production hardening -- ensure `internal` details are stripped, error monitoring integration points.
