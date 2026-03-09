# Spec 12: Error Handling Specification -- Implementation Context

## Implementation Scope

### Files to Create
```
backend/
  errors.py              # Exception hierarchy + ErrorResponse model
  circuit_breaker.py     # CircuitBreaker class
```

### Files to Modify
```
backend/
  middleware.py           # Add exception handlers, rate limiter
  main.py                # Register exception handlers
  config.py              # Add error/retry configuration settings
```

## Code Specifications

### Exception Hierarchy (`backend/errors.py`)

```python
from typing import Optional
from pydantic import BaseModel


class EmbdinatorError(Exception):
    """Base exception for all Embedinator errors."""

    def __init__(
        self,
        message: str,
        code: str,
        details: Optional[dict] = None,
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


# ========================================
# Storage layer errors
# ========================================

class StorageError(EmbdinatorError):
    """Base for all storage-related errors."""
    pass


class QdrantConnectionError(StorageError):
    """Qdrant server is unreachable or returned an unexpected error."""

    def __init__(self, message: str = "Vector database unavailable", details: Optional[dict] = None):
        super().__init__(message=message, code="QDRANT_UNAVAILABLE", details=details)


class QdrantCollectionError(StorageError):
    """Qdrant collection operation failed (create/delete/not found)."""

    def __init__(self, message: str, code: str = "QDRANT_COLLECTION_ERROR", details: Optional[dict] = None):
        super().__init__(message=message, code=code, details=details)


class DatabaseError(StorageError):
    """SQLite operation failed."""

    def __init__(self, message: str = "Database operation failed", details: Optional[dict] = None):
        super().__init__(message=message, code="DATABASE_ERROR", details=details)


class DatabaseMigrationError(StorageError):
    """SQLite schema migration failed."""

    def __init__(self, message: str = "Database migration failed", details: Optional[dict] = None):
        super().__init__(message=message, code="MIGRATION_ERROR", details=details)


# ========================================
# Ingestion layer errors
# ========================================

class IngestionError(EmbdinatorError):
    """Base for all ingestion-related errors."""
    pass


class RustWorkerError(IngestionError):
    """Rust ingestion worker binary failed or produced invalid output."""

    def __init__(self, message: str = "Document parsing failed", details: Optional[dict] = None):
        super().__init__(message=message, code="RUST_WORKER_ERROR", details=details)


class FileValidationError(IngestionError):
    """Uploaded file failed validation (type, size, content)."""

    def __init__(self, message: str = "Invalid file", details: Optional[dict] = None):
        super().__init__(message=message, code="INVALID_FILE", details=details)


class EmbeddingError(IngestionError):
    """Embedding generation failed after retries."""

    def __init__(self, message: str = "Embedding service unavailable", details: Optional[dict] = None):
        super().__init__(message=message, code="EMBEDDING_UNAVAILABLE", details=details)


class EmbeddingValidationError(IngestionError):
    """Generated embedding failed validation (NaN, zero-vector, dimension mismatch)."""

    def __init__(self, message: str = "Embedding validation failed", details: Optional[dict] = None):
        super().__init__(message=message, code="EMBEDDING_VALIDATION_ERROR", details=details)


class DuplicateDocumentError(IngestionError):
    """Document with same hash already exists in the collection."""

    def __init__(self, message: str = "Document already ingested", details: Optional[dict] = None):
        super().__init__(message=message, code="DUPLICATE_DOCUMENT", details=details)


# ========================================
# Agent layer errors
# ========================================

class AgentError(EmbdinatorError):
    """Base for all agent-related errors."""
    pass


class LLMCallError(AgentError):
    """LLM inference call failed (timeout, connection, invalid response)."""

    def __init__(self, message: str = "Inference service unavailable", details: Optional[dict] = None):
        super().__init__(message=message, code="LLM_UNAVAILABLE", details=details)


class StructuredOutputParseError(AgentError):
    """LLM produced output that could not be parsed into the expected schema."""

    def __init__(self, message: str = "Failed to parse structured output", details: Optional[dict] = None):
        super().__init__(message=message, code="STRUCTURED_OUTPUT_ERROR", details=details)


class RerankerError(AgentError):
    """Cross-encoder reranking failed."""

    def __init__(self, message: str = "Reranking failed", details: Optional[dict] = None):
        super().__init__(message=message, code="RERANKER_ERROR", details=details)


class ToolExecutionError(AgentError):
    """Agent tool execution failed."""

    def __init__(self, message: str = "Tool execution failed", details: Optional[dict] = None):
        super().__init__(message=message, code="TOOL_EXECUTION_ERROR", details=details)


class ConfidenceError(AgentError):
    """Confidence computation failed."""

    def __init__(self, message: str = "Confidence computation failed", details: Optional[dict] = None):
        super().__init__(message=message, code="CONFIDENCE_ERROR", details=details)


# ========================================
# Provider layer errors
# ========================================

class ProviderError(EmbdinatorError):
    """Base for all provider-related errors."""
    pass


class ProviderNotConfiguredError(ProviderError):
    """Provider API key is not configured."""

    def __init__(self, message: str = "Provider not configured", details: Optional[dict] = None):
        super().__init__(message=message, code="PROVIDER_NOT_CONFIGURED", details=details)


class ProviderAuthError(ProviderError):
    """Provider rejected the API key or key decryption failed."""

    def __init__(self, message: str = "Invalid API key for provider", details: Optional[dict] = None):
        super().__init__(message=message, code="PROVIDER_AUTH_ERROR", details=details)


class ProviderRateLimitError(ProviderError):
    """Provider returned 429 Too Many Requests."""

    def __init__(self, message: str = "Provider rate limit reached, try again later", details: Optional[dict] = None):
        super().__init__(message=message, code="RATE_LIMITED", details=details)


class ModelNotFoundError(ProviderError):
    """Requested model is not available from any configured provider."""

    def __init__(self, message: str = "Model not found", details: Optional[dict] = None):
        super().__init__(message=message, code="MODEL_NOT_FOUND", details=details)


# ========================================
# API layer errors
# ========================================

class APIError(EmbdinatorError):
    """Base for all API-level errors."""
    pass


class ValidationError(APIError):
    """Request validation failed (field constraints, missing required fields)."""

    def __init__(self, message: str = "Validation error", details: Optional[dict] = None):
        super().__init__(message=message, code="VALIDATION_ERROR", details=details)


class NotFoundError(APIError):
    """Requested resource does not exist."""

    def __init__(self, message: str = "Resource not found", details: Optional[dict] = None):
        super().__init__(message=message, code="NOT_FOUND", details=details)


class ConflictError(APIError):
    """Resource already exists or state conflict."""

    def __init__(self, message: str = "Resource already exists", details: Optional[dict] = None):
        super().__init__(message=message, code="CONFLICT", details=details)


# ========================================
# Error Response Model
# ========================================

class ErrorResponse(BaseModel):
    """Standardized error response body for all API errors."""
    detail: str          # user-facing message
    code: str            # machine-readable error code
    trace_id: Optional[str] = None  # request trace ID for debugging
    internal: Optional[dict] = None  # stack trace, raw error (dev mode only)


# ========================================
# HTTP Status Code Mapping
# ========================================

EXCEPTION_STATUS_MAP: dict[type, int] = {
    ValidationError: 400,
    FileValidationError: 400,
    ProviderAuthError: 401,
    NotFoundError: 404,
    ModelNotFoundError: 404,
    ConflictError: 409,
    DuplicateDocumentError: 409,
    ProviderRateLimitError: 429,
    QdrantConnectionError: 503,
    LLMCallError: 503,
    EmbeddingError: 503,
    ProviderNotConfiguredError: 400,
}
```

### Circuit Breaker (`backend/circuit_breaker.py`)

```python
import asyncio
import time
from enum import Enum
from typing import Callable, TypeVar, Any
import structlog

logger = structlog.get_logger()

T = TypeVar("T")


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open and blocking calls."""

    def __init__(self, last_error: Exception, cooldown_remaining: float):
        self.last_error = last_error
        self.cooldown_remaining = cooldown_remaining
        super().__init__(f"Circuit breaker open. Cooldown: {cooldown_remaining:.1f}s")


class CircuitBreaker:
    """In-memory circuit breaker for external service calls.

    State transitions:
      CLOSED -> OPEN: After `failure_threshold` consecutive failures within `window_duration`
      OPEN -> HALF_OPEN: After `cooldown_secs` have elapsed
      HALF_OPEN -> CLOSED: Probe call succeeds
      HALF_OPEN -> OPEN: Probe call fails
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        window_duration: float = 60.0,
        cooldown_secs: float = 30.0,
        name: str = "default",
    ):
        self.failure_threshold = failure_threshold
        self.window_duration = window_duration
        self.cooldown_secs = cooldown_secs
        self.name = name

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._failure_timestamps: list[float] = []
        self._last_failure_time = 0.0
        self._last_error: Exception | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        return self._state

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute func through the circuit breaker."""
        async with self._lock:
            now = time.monotonic()

            if self._state == CircuitBreakerState.OPEN:
                elapsed = now - self._last_failure_time
                if elapsed >= self.cooldown_secs:
                    self._state = CircuitBreakerState.HALF_OPEN
                    logger.info("circuit_breaker.half_open", name=self.name)
                else:
                    remaining = self.cooldown_secs - elapsed
                    raise CircuitBreakerOpen(self._last_error, remaining)

        try:
            result = await func(*args, **kwargs)
            await self._record_success()
            return result
        except Exception as e:
            await self._record_failure(e)
            raise

    async def _record_success(self) -> None:
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                logger.info("circuit_breaker.closed", name=self.name, reason="probe_succeeded")
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
            self._failure_timestamps.clear()

    async def _record_failure(self, error: Exception) -> None:
        async with self._lock:
            now = time.monotonic()
            self._last_error = error
            self._last_failure_time = now

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                logger.warning("circuit_breaker.open", name=self.name, reason="probe_failed")
                return

            # Prune old timestamps outside the window
            cutoff = now - self.window_duration
            self._failure_timestamps = [t for t in self._failure_timestamps if t > cutoff]
            self._failure_timestamps.append(now)

            if len(self._failure_timestamps) >= self.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    "circuit_breaker.open",
                    name=self.name,
                    reason="threshold_reached",
                    failures=len(self._failure_timestamps),
                )
```

### Exception Handler Registration (`backend/main.py` additions)

```python
import traceback
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from backend.errors import (
    EmbdinatorError, ErrorResponse, EXCEPTION_STATUS_MAP,
)
from backend.config import settings

async def embedinator_exception_handler(request: Request, exc: EmbdinatorError):
    status_code = EXCEPTION_STATUS_MAP.get(type(exc), 500)
    response = ErrorResponse(
        detail=exc.message,
        code=exc.code,
        trace_id=getattr(request.state, "trace_id", None),
    )
    if settings.DEBUG_MODE:
        response.internal = {
            "traceback": traceback.format_exc(),
            "details": exc.details,
            "exception_type": type(exc).__name__,
        }
    return JSONResponse(
        status_code=status_code,
        content=response.model_dump(exclude_none=True),
    )


async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(
        "unhandled_exception",
        error=str(exc),
        traceback=traceback.format_exc(),
        trace_id=getattr(request.state, "trace_id", None),
    )
    response = ErrorResponse(
        detail="An internal error occurred",
        code="INTERNAL_ERROR",
        trace_id=getattr(request.state, "trace_id", None),
    )
    return JSONResponse(status_code=500, content=response.model_dump(exclude_none=True))


# In app factory:
app.add_exception_handler(EmbdinatorError, embedinator_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)
```

### Retry Decorators

```python
# backend/retry.py (or inline where needed)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
import structlog

logger = structlog.get_logger()


def retry_on_transient(
    retry_on: tuple[type[Exception], ...] = (QdrantConnectionError, EmbeddingError, LLMCallError),
    max_attempts: int = 3,
    initial_backoff: float = 1.0,
    max_backoff: float = 10.0,
):
    """Factory for retry decorators on transient failures."""
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=initial_backoff, max=max_backoff),
        retry=retry_if_exception_type(retry_on),
        before_sleep=before_sleep_log(logger, structlog.stdlib.log_level),
    )
```

### Rate Limiter

```python
# backend/rate_limiter.py
import time
from collections import defaultdict
from fastapi import Request, HTTPException


class RateLimiter:
    """In-memory sliding window rate limiter."""

    def __init__(self):
        self._windows: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window_secs: int = 60) -> None:
        now = time.monotonic()
        cutoff = now - window_secs
        self._windows[key] = [t for t in self._windows[key] if t > cutoff]

        if len(self._windows[key]) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later.",
            )
        self._windows[key].append(now)
```

### SSE Error Formatting

```python
# Used in chat streaming endpoint
import json

def format_sse_error(error: EmbdinatorError) -> str:
    """Format an error as an SSE event for mid-stream error delivery."""
    event = {
        "type": "error",
        "message": error.message,
        "code": error.code,
    }
    return f"data: {json.dumps(event)}\n\n"
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG_MODE` | `false` | Include internal error details in API responses |
| `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | `5` | Consecutive failures before circuit opens |
| `CIRCUIT_BREAKER_COOLDOWN_SECS` | `30` | Seconds to wait before half-open probe |
| `RETRY_MAX_ATTEMPTS` | `3` | Maximum retry attempts per call |
| `RETRY_BACKOFF_INITIAL_SECS` | `1.0` | Initial backoff delay in seconds |

### Configuration in `backend/config.py`

```python
class Settings(BaseSettings):
    # ... existing settings ...
    debug_mode: bool = False
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_secs: int = 30
    retry_max_attempts: int = 3
    retry_backoff_initial_secs: float = 1.0
```

## Error Handling

This module IS the error handling system. Key self-referential behaviors:

- The circuit breaker itself raises `CircuitBreakerOpen` when tripped, which should be caught and wrapped into the appropriate domain error (e.g., `QdrantConnectionError` for Qdrant calls)
- The rate limiter raises `HTTPException(429)` directly (FastAPI built-in)
- The exception handler itself must never raise -- it must always return a valid `JSONResponse`
- The generic exception handler must log the full traceback before returning the sanitized response

## Testing Requirements

### Unit Tests

**Exception Hierarchy:**
- Verify `EmbdinatorError` base fields: `message`, `code`, `details`
- Verify all subclasses inherit correctly and can be instantiated
- Verify default `code` values for each exception class
- Verify `EXCEPTION_STATUS_MAP` contains entries for all exception classes that need HTTP mapping

**Circuit Breaker:**
- Test CLOSED state: calls execute normally, failures are tracked
- Test CLOSED -> OPEN transition: after `failure_threshold` consecutive failures
- Test OPEN state: calls fail immediately with `CircuitBreakerOpen`
- Test OPEN -> HALF_OPEN transition: after cooldown expires
- Test HALF_OPEN -> CLOSED: probe success
- Test HALF_OPEN -> OPEN: probe failure
- Test window pruning: old failures outside window do not count
- Test concurrent access: multiple async calls do not corrupt state

**Retry:**
- Test successful call: no retry needed
- Test transient failure then success: verify retry count
- Test all retries exhausted: verify final exception is raised
- Test backoff timing: verify exponential increase

**Error Response:**
- Test `ErrorResponse` model serialization with all fields
- Test `ErrorResponse` with `internal=None` (production mode)
- Test `ErrorResponse` with `internal` populated (debug mode)

**Rate Limiter:**
- Test under limit: calls succeed
- Test at limit: next call raises 429
- Test window expiry: old requests fall off

### Integration Tests

**Exception Handler:**
- Verify each exception type returns correct HTTP status code
- Verify `trace_id` is included in error response
- Verify `internal` details appear only when `DEBUG_MODE=true`
- Verify unhandled exceptions return 500 with `INTERNAL_ERROR`
- Verify error response body matches `ErrorResponse` schema

## Done Criteria

1. `backend/errors.py` defines all 20+ exception classes in the hierarchy with correct inheritance
2. Every exception carries `message`, `code`, and `details` fields
3. `EXCEPTION_STATUS_MAP` maps every relevant exception to its HTTP status code
4. `ErrorResponse` Pydantic model is defined with `detail`, `code`, `trace_id`, `internal`
5. FastAPI global exception handler returns correct status codes for all exception types
6. Unhandled exceptions return 500 with `INTERNAL_ERROR` and no internal details in production
7. `CircuitBreaker` correctly implements CLOSED -> OPEN -> HALF_OPEN -> CLOSED state machine
8. Circuit breaker trips after 5 consecutive failures within 60 seconds (configurable)
9. Circuit breaker allows probe after 30-second cooldown (configurable)
10. `retry_on_transient` decorator retries up to 3 times with exponential backoff
11. Rate limiter enforces per-endpoint limits with sliding window
12. SSE error formatter produces valid SSE event data
13. All unit tests pass for exception hierarchy, circuit breaker, retry, and rate limiter
14. Internal details (stack traces) only appear when `DEBUG_MODE=true`
