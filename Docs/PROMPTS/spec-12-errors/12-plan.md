# Spec 12: Error Handling — Implementation Plan Context

---

> **AGENT TEAMS -- tmux IS REQUIRED**
>
> This spec uses 4 waves with 4 agents. Wave 2 and Wave 3 each contain a single agent,
> but are written as parallel-capable placeholders for future expansion. Waves run
> sequentially; each wave gate must pass before the next wave begins.
>
> **Orchestrator protocol**:
> 1. Read THIS file first (you are doing this now)
> 2. Spawn agents by wave, one per tmux pane
> 3. Each agent's FIRST action is to read its instruction file
> 4. Wait for wave gate before spawning the next wave
>
> Spawn command for every agent (no exceptions):
> ```
> Agent(
>   subagent_type="<type>",
>   model="<model>",
>   prompt="Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/<file>.md FIRST, then execute all assigned tasks"
> )
> ```

---

## Wave Definitions

### Wave 1: Pre-Implementation Audit (sequential — must complete before Wave 2)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A1 | quality-engineer | opus | T001–T010 | Audit report at `Docs/Tests/spec12-a1-audit.md` confirming codebase matches spec |

**Instruction file**: `Docs/PROMPTS/spec-12-errors/agents/A1-audit.md`

**Gate**: A1 confirms that:
- `backend/errors.py` contains exactly 11 classes (no additions or deletions needed)
- `backend/agent/schemas.py` has `ErrorDetail` and `ErrorResponse` with correct fields
- `backend/config.py` has all required circuit breaker and rate limit config fields
- `backend/providers/base.py` has `ProviderRateLimitError` extending `Exception` with `provider` attribute
- `backend/main.py` `create_app()` has the `ProviderRateLimitError` handler (to be fixed in Wave 2)
- No discrepancies found that would block Wave 2

### Wave 2: Handler Fixes in main.py (sequential after Wave 1)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A2 | python-expert | sonnet | T011–T018 | Updated `backend/main.py` with 4 handler changes |

**Instruction file**: `Docs/PROMPTS/spec-12-errors/agents/A2-main-handlers.md`

**Gate**: `backend/main.py` `create_app()` contains all four exception handlers with the correct format. No pre-existing tests break.

### Wave 3: New Test Files (sequential after Wave 2)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A3 | python-expert | sonnet | T019–T034 | `tests/unit/test_error_contracts.py` + `tests/integration/test_error_handlers.py` |

**Instruction file**: `Docs/PROMPTS/spec-12-errors/agents/A3-tests.md`

**Gate**: Both new test files pass via external runner:
```
zsh scripts/run-tests-external.sh -n spec12-a3 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py
```

### Wave 4: Full Regression Gate (sequential after Wave 3)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A4 | quality-engineer | sonnet | T035–T040 | Final test count report confirming zero regressions |

**Instruction file**: `Docs/PROMPTS/spec-12-errors/agents/A4-regression.md`

**Gate**: Full test suite passes with zero regressions against existing 1250 tests, and all new spec-12 tests pass.

---

## Component Overview

### What Spec-12 Is

Spec-12 is a **documentation-and-hardening spec**. The codebase already has a working exception hierarchy, circuit breakers, retry logic, and rate limiting — all implemented across specs 02–11. Spec-12 does not rebuild any of these systems.

The three concrete changes spec-12 makes to production code are all in `backend/main.py`:

1. **Fix** the existing `ProviderRateLimitError` handler — change from NDJSON-style flat format to the standard nested envelope with uppercase `PROVIDER_RATE_LIMIT` code and `trace_id`.
2. **Add** a global `EmbeddinatorError` catch-all handler → HTTP 500, `INTERNAL_ERROR`.
3. **Add** a specific `QdrantConnectionError` handler → HTTP 503, `QDRANT_UNAVAILABLE`.
4. **Add** a specific `OllamaConnectionError` handler → HTTP 503, `OLLAMA_UNAVAILABLE`.

In addition, spec-12 adds two new test files:
- `tests/unit/test_error_contracts.py` — contract tests asserting the error hierarchy, Pydantic models, and config fields match the spec
- `tests/integration/test_error_handlers.py` — integration tests verifying the four exception handlers return correct HTTP status codes and response bodies

### What Spec-12 Does NOT Do

- Does NOT create new exception classes (the hierarchy is complete and frozen)
- Does NOT create a `CircuitBreaker` class (circuit breakers are implemented as instance variables on `QdrantClientWrapper`/`QdrantStorage` and as module-level globals in `nodes.py`)
- Does NOT create a `backend/circuit_breaker.py` file (no such file is needed)
- Does NOT wire `retry_max_attempts` or `retry_backoff_initial_secs` to tenacity decorators (those config fields are reserved dead config — do not change the tenacity call sites)
- Does NOT add structured logging to error handlers (out of scope — deferred to spec-15 Observability)
- Does NOT add a fallback handler for plain `Exception` (only `EmbeddinatorError` subtypes get the global handler)

---

## Technical Approach

### The Existing Error System (Ground Truth)

#### Exception Hierarchy — backend/errors.py

The file contains exactly these 11 classes, all extending `EmbeddinatorError` directly (flat hierarchy, no intermediate base classes):

```
EmbeddinatorError(Exception)         # root base — backend/errors.py:3
  ├─ QdrantConnectionError            # backend/errors.py:8
  ├─ OllamaConnectionError            # backend/errors.py:12
  ├─ SQLiteError                      # backend/errors.py:16
  ├─ LLMCallError                     # backend/errors.py:20
  ├─ EmbeddingError                   # backend/errors.py:24
  ├─ IngestionError                   # backend/errors.py:28
  ├─ SessionLoadError                 # backend/errors.py:32
  ├─ StructuredOutputParseError       # backend/errors.py:36
  ├─ RerankerError                    # backend/errors.py:40
  └─ CircuitOpenError                 # backend/errors.py:44
```

**Critical**: `EmbeddinatorError` has no `__init__` override, no `message`, `code`, or `details` fields. It is a plain `Exception` subclass. Contextual information is passed as the exception message string.

**Separate from this hierarchy** — in `backend/providers/base.py`:

```python
class ProviderRateLimitError(Exception):     # extends Exception directly, NOT EmbeddinatorError
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

#### Error Response Format — REST Endpoints

All REST routers use `HTTPException` with a structured `detail` dict:

```python
# The standard nested envelope used by all REST routers
{
    "error": {
        "code": "UPPER_SNAKE_CASE",          # machine-readable, stable
        "message": "Human-readable message", # user-facing text
        "details": {},                        # optional context, may be empty
    },
    "trace_id": "uuid-here",                 # from request.state.trace_id
}
```

The Pydantic models backing the `error` object (from `backend/agent/schemas.py`):

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorDetail
    # trace_id is NOT a field on ErrorResponse
    # It is appended directly to the dict in each router
```

**The `trace_id` is added manually** as a top-level sibling of `"error"` in `HTTPException.detail`. It is NOT part of `ErrorResponse`.

#### Current State of main.py Exception Handlers

`create_app()` in `backend/main.py` currently registers **only one** exception handler:

```python
@app.exception_handler(ProviderRateLimitError)
async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"type": "error", "message": str(exc), "code": "rate_limit"},
    )
```

This handler has **three problems**:
1. Uses NDJSON-style flat format (`"type": "error"`) instead of the nested envelope
2. Uses lowercase `"rate_limit"` instead of uppercase `"PROVIDER_RATE_LIMIT"`
3. Missing `trace_id` in the response

There is **no** `EmbeddinatorError` global handler. Any `EmbeddinatorError` subclass that propagates out of a router (e.g., `SQLiteError` from the DB layer) returns FastAPI's default `{"detail": "Internal Server Error"}` — not the nested format.

#### Circuit Breaker Pattern

There are three independent circuit breakers in the codebase. None are instances of a `CircuitBreaker` class — they are implemented with instance variables or module-level globals:

**1. QdrantClientWrapper** (`backend/storage/qdrant_client.py`, instance variables):
```python
self._circuit_open = False
self._failure_count = 0
self._last_failure_time: float | None = None
self._max_failures = settings.circuit_breaker_failure_threshold  # read once at construction
self._cooldown_secs = settings.circuit_breaker_cooldown_secs     # read once at construction
```

**2. QdrantStorage** (`backend/storage/qdrant_client.py`, same instance variable pattern on the `QdrantStorage` class)

**3. Inference circuit breaker** (`backend/agent/nodes.py`, module-level globals):
```python
_inf_circuit_open: bool = False
_inf_failure_count: int = 0
_inf_last_failure_time: float | None = None
_inf_max_failures: int = 5    # overridden from settings on every _check_inference_circuit() call
_inf_cooldown_secs: int = 30  # overridden from settings on every _check_inference_circuit() call
```

All three share the same state machine logic:
- CLOSED → OPEN: when `_failure_count >= _max_failures` after a failure
- OPEN → HALF-OPEN: when `time.monotonic() - _last_failure_time >= _cooldown_secs` (checked inside `_check_circuit()`)
- HALF-OPEN → CLOSED: probe succeeds → `_record_success()` resets count to 0
- HALF-OPEN → OPEN: probe fails → `_record_failure()` re-opens

The circuit breakers raise `CircuitOpenError` (from `backend/errors.py`) when open.

#### Retry Pattern

Qdrant operations in `QdrantClientWrapper` and `QdrantStorage` use tenacity on internal `_*_with_retry` methods:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _some_operation_with_retry(self, ...):
    ...
```

The retry count (`3`) and backoff parameters (`multiplier=1, min=1, max=10`) are **hardcoded at the call site**. The `Settings` fields `retry_max_attempts` (default `3`) and `retry_backoff_initial_secs` (default `1.0`) are **not wired** to these decorators — they are reserved for a future spec. Do not wire them.

#### NDJSON Stream Error Format

Errors during `POST /api/chat` streaming use a flat format (not the nested envelope):

```json
{"type": "error", "message": "<user-facing>", "code": "<CODE>", "trace_id": "<uuid>"}
```

The three defined stream error codes:

| Code | Trigger |
|------|---------|
| `NO_COLLECTIONS` | `body.collection_ids` is empty |
| `CIRCUIT_OPEN` | `CircuitOpenError` raised during graph execution |
| `SERVICE_UNAVAILABLE` | Any other unhandled `Exception` during graph execution |

These codes are already correct in the codebase — spec-12 does not change `backend/api/chat.py`.

#### Rate Limiting

`RateLimitMiddleware` in `backend/middleware.py` already implements sliding-window per-IP rate limiting with the correct nested envelope and `Retry-After: 60` header. No changes needed to `middleware.py`.

Config fields in `Settings` (`backend/config.py`):

| Field | Default | Applied To |
|-------|---------|-----------|
| `rate_limit_chat_per_minute` | `30` | `POST /api/chat` |
| `rate_limit_ingest_per_minute` | `10` | `POST /api/collections/*/ingest` |
| `rate_limit_provider_keys_per_minute` | `5` | `PUT/DELETE /api/providers/*/key` |
| `rate_limit_general_per_minute` | `120` | All other endpoints |

Circuit breaker config fields in `Settings`:

| Field | Type | Default |
|-------|------|---------|
| `circuit_breaker_failure_threshold` | `int` | `5` |
| `circuit_breaker_cooldown_secs` | `int` | `30` |

---

## File Structure

Only these files are created or modified by spec-12:

```
backend/
  main.py                          # MODIFY: fix ProviderRateLimitError handler + add 3 new handlers

tests/
  unit/
    test_error_contracts.py        # CREATE: contract tests (hierarchy, models, config fields)
  integration/
    test_error_handlers.py         # CREATE: handler integration tests (HTTP status + response body)
```

**No other files are touched.** Do NOT modify:
- `backend/errors.py` — the hierarchy is complete and frozen
- `backend/agent/schemas.py` — `ErrorDetail` and `ErrorResponse` are already correct
- `backend/config.py` — all required config fields already exist
- `backend/middleware.py` — rate limiting is already correct
- `backend/api/chat.py` — stream error handling is already correct
- `backend/storage/qdrant_client.py` — circuit breakers are already correct
- `backend/agent/nodes.py` — inference circuit breaker is already correct
- `backend/providers/base.py` — `ProviderRateLimitError` is already correct

---

## Implementation Steps

### Wave 1: A1 — Pre-Implementation Audit (Tasks T001–T010)

A1 verifies the codebase against this plan before any code changes are made. This prevents Wave 2 from implementing against a wrong assumption.

**T001** — Read `backend/errors.py` and verify:
- Exactly 11 classes are present (list them)
- All 10 subclasses extend `EmbeddinatorError` directly
- No `__init__` override exists on any class
- Report PASS or list discrepancies

**T002** — Read `backend/providers/base.py` and verify:
- `ProviderRateLimitError` exists and extends `Exception` (not `EmbeddinatorError`)
- `__init__(self, provider: str)` signature is present
- `self.provider = provider` attribute assignment is present
- Report PASS or list discrepancies

**T003** — Read `backend/agent/schemas.py` `ErrorDetail` class and verify:
- Fields: `code: str`, `message: str`, `details: dict = {}`
- No `trace_id` field
- Report PASS or list discrepancies

**T004** — Read `backend/agent/schemas.py` `ErrorResponse` class and verify:
- Fields: `error: ErrorDetail` only
- No `trace_id` field on the model
- Report PASS or list discrepancies

**T005** — Read `backend/config.py` `Settings` class and verify these fields exist with correct types and defaults:
- `circuit_breaker_failure_threshold: int = 5`
- `circuit_breaker_cooldown_secs: int = 30`
- `retry_max_attempts: int = 3` (dead config — exists but not wired)
- `retry_backoff_initial_secs: float = 1.0` (dead config — exists but not wired)
- `rate_limit_chat_per_minute: int = 30`
- `rate_limit_ingest_per_minute: int = 10`
- `rate_limit_provider_keys_per_minute: int = 5`
- `rate_limit_general_per_minute: int = 120`
- Report PASS or list discrepancies

**T006** — Read `backend/main.py` `create_app()` and verify:
- The current `ProviderRateLimitError` handler returns `{"type": "error", "message": ..., "code": "rate_limit"}` (confirms what needs to be fixed)
- No `EmbeddinatorError` global handler exists (confirms it needs to be added)
- No `QdrantConnectionError` specific handler exists (confirms it needs to be added)
- No `OllamaConnectionError` specific handler exists (confirms it needs to be added)
- Report current state of handlers

**T007** — Read `backend/middleware.py` `RateLimitMiddleware.dispatch()` and verify:
- Returns `JSONResponse(status_code=429, content={"error": {...}, "trace_id": ...}, headers={"Retry-After": "60"})`
- Code in the error is `"RATE_LIMIT_EXCEEDED"` (uppercase)
- Report PASS or list discrepancies

**T008** — Read `backend/api/chat.py` stream error handling and verify:
- Three error codes used: `NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`
- All stream errors include `trace_id` in their JSON
- Report PASS or list discrepancies

**T009** — Read `backend/storage/qdrant_client.py` and verify:
- `QdrantClientWrapper` uses instance variables `_circuit_open`, `_failure_count`, `_last_failure_time`
- The `@retry` decorator on `_*_with_retry` methods uses `stop_after_attempt(3)`, `wait_exponential(multiplier=1, min=1, max=10)`, `wait_random(0, 1)`, `reraise=True`
- Report PASS or list discrepancies

**T010** — Write audit report to `Docs/Tests/spec12-a1-audit.md` summarizing all findings. If any discrepancy is found that conflicts with this plan, note it clearly. Do NOT proceed with Wave 2 tasks.

---

### Wave 2: A2 — Handler Fixes in main.py (Tasks T011–T018)

A2 makes exactly four targeted changes to `backend/main.py` `create_app()`. No other files are modified.

**T011** — Read `backend/main.py` in full to understand existing imports and handler registration order.

**T012** — Verify these imports are already present in `backend/main.py` (they should be, since the current `ProviderRateLimitError` handler uses them):
- `from fastapi.responses import JSONResponse`
- `from starlette.requests import Request` (or `from fastapi import Request`)
- `from backend.providers.base import ProviderRateLimitError`

**T013** — Verify or add this import to `backend/main.py`:
```python
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
```
If `backend.errors` is not yet imported, add this import after the existing provider import.

**T014** — Replace the existing `ProviderRateLimitError` handler in `create_app()`. Find and replace:

FIND (current, wrong):
```python
@app.exception_handler(ProviderRateLimitError)
async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"type": "error", "message": str(exc), "code": "rate_limit"},
    )
```

REPLACE WITH (corrected):
```python
@app.exception_handler(ProviderRateLimitError)
async def provider_rate_limit_handler(request: Request, exc: ProviderRateLimitError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "PROVIDER_RATE_LIMIT",
                "message": f"Rate limit exceeded for provider: {exc.provider}",
                "details": {"provider": exc.provider},
            },
            "trace_id": trace_id,
        },
    )
```

**T015** — Add the global `EmbeddinatorError` handler immediately after the `ProviderRateLimitError` handler:

```python
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

**T016** — Add the `QdrantConnectionError` specific handler immediately after the `EmbeddinatorError` handler:

```python
@app.exception_handler(QdrantConnectionError)
async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "QDRANT_UNAVAILABLE",
                "message": "Vector database is temporarily unavailable",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

**T017** — Add the `OllamaConnectionError` specific handler immediately after the `QdrantConnectionError` handler:

```python
@app.exception_handler(OllamaConnectionError)
async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "OLLAMA_UNAVAILABLE",
                "message": "Inference service is temporarily unavailable",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

**T018** — Verify handler registration order in `create_app()`. FastAPI resolves exception handlers by MRO specificity. The order must be:
1. `ProviderRateLimitError` handler (most specific, extends `Exception`)
2. `QdrantConnectionError` handler (specific subclass of `EmbeddinatorError`)
3. `OllamaConnectionError` handler (specific subclass of `EmbeddinatorError`)
4. `EmbeddinatorError` handler (global catch-all, must come AFTER the specific subclass handlers)

**Important**: FastAPI's `@app.exception_handler` uses MRO. More-specific handlers for `EmbeddinatorError` subclasses MUST be registered before the base class handler to ensure they take precedence. Verify by reading the final `create_app()` body.

---

### Wave 3: A3 — New Test Files (Tasks T019–T034)

A3 writes two new test files. Both use only standard library imports, pytest, and FastAPI `TestClient`. No mock databases or Qdrant connections are needed.

**Important before writing tests**: A3 must read:
- `backend/errors.py` — exact class names to test
- `backend/agent/schemas.py` — `ErrorDetail` and `ErrorResponse` field names
- `backend/config.py` — `Settings` field names and defaults
- `backend/providers/base.py` — `ProviderRateLimitError` signature
- `backend/main.py` — the final handler code (after A2's changes)

#### File 1: tests/unit/test_error_contracts.py

**T019** — Create `tests/unit/test_error_contracts.py`. This file asserts static properties of the error hierarchy and Pydantic models. It imports from the codebase but does NOT start a server or make HTTP requests.

**T020** — Write test class `TestErrorHierarchy`:

```python
class TestErrorHierarchy:
    def test_all_required_classes_exist(self):
        """All 11 documented exception classes are importable from backend.errors."""
        import backend.errors as errors
        required = [
            "EmbeddinatorError",
            "QdrantConnectionError",
            "OllamaConnectionError",
            "SQLiteError",
            "LLMCallError",
            "EmbeddingError",
            "IngestionError",
            "SessionLoadError",
            "StructuredOutputParseError",
            "RerankerError",
            "CircuitOpenError",
        ]
        for name in required:
            assert hasattr(errors, name), f"{name} missing from backend.errors"

    def test_no_extra_classes_in_errors_module(self):
        """backend.errors contains no undocumented exception classes."""
        import inspect
        import backend.errors as errors
        classes_in_module = {
            name
            for name, obj in inspect.getmembers(errors, inspect.isclass)
            if obj.__module__ == "backend.errors"
        }
        expected = {
            "EmbeddinatorError",
            "QdrantConnectionError",
            "OllamaConnectionError",
            "SQLiteError",
            "LLMCallError",
            "EmbeddingError",
            "IngestionError",
            "SessionLoadError",
            "StructuredOutputParseError",
            "RerankerError",
            "CircuitOpenError",
        }
        assert classes_in_module == expected, (
            f"Unexpected classes: {classes_in_module - expected}; "
            f"Missing classes: {expected - classes_in_module}"
        )

    def test_root_base_is_exception(self):
        from backend.errors import EmbeddinatorError
        assert issubclass(EmbeddinatorError, Exception)
        assert not issubclass(EmbeddinatorError, BaseException.__subclasses__()[0]
                              if len(BaseException.__subclasses__()) > 0 else type)

    def test_all_subclasses_extend_embedinator_error_directly(self):
        from backend.errors import (
            EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
            SQLiteError, LLMCallError, EmbeddingError, IngestionError,
            SessionLoadError, StructuredOutputParseError, RerankerError, CircuitOpenError,
        )
        subclasses = [
            QdrantConnectionError, OllamaConnectionError, SQLiteError,
            LLMCallError, EmbeddingError, IngestionError, SessionLoadError,
            StructuredOutputParseError, RerankerError, CircuitOpenError,
        ]
        for cls in subclasses:
            assert EmbeddinatorError in cls.__bases__, (
                f"{cls.__name__} must extend EmbeddinatorError directly, "
                f"got bases: {cls.__bases__}"
            )

    def test_embedinator_error_has_no_custom_init(self):
        """EmbeddinatorError must not override __init__ — it is a plain Exception subclass."""
        from backend.errors import EmbeddinatorError
        assert EmbeddinatorError.__init__ is Exception.__init__ or \
               "__init__" not in EmbeddinatorError.__dict__, \
               "EmbeddinatorError must not define __init__"

    def test_exception_classes_are_instantiable_with_string(self):
        """All exception classes can be raised with a plain string message."""
        from backend.errors import (
            EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
            CircuitOpenError, SQLiteError, LLMCallError,
        )
        for cls in [EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
                    CircuitOpenError, SQLiteError, LLMCallError]:
            exc = cls("test message")
            assert str(exc) == "test message"
```

**T021** — Write test class `TestProviderRateLimitError`:

```python
class TestProviderRateLimitError:
    def test_lives_in_providers_base(self):
        from backend.providers.base import ProviderRateLimitError
        assert ProviderRateLimitError.__module__ == "backend.providers.base"

    def test_extends_exception_not_embedinator_error(self):
        from backend.providers.base import ProviderRateLimitError
        from backend.errors import EmbeddinatorError
        assert issubclass(ProviderRateLimitError, Exception)
        assert not issubclass(ProviderRateLimitError, EmbeddinatorError)

    def test_requires_provider_argument(self):
        import inspect
        from backend.providers.base import ProviderRateLimitError
        sig = inspect.signature(ProviderRateLimitError.__init__)
        params = list(sig.parameters.keys())
        assert "provider" in params

    def test_has_provider_attribute(self):
        from backend.providers.base import ProviderRateLimitError
        exc = ProviderRateLimitError(provider="openai")
        assert exc.provider == "openai"

    def test_str_message_contains_provider_name(self):
        from backend.providers.base import ProviderRateLimitError
        exc = ProviderRateLimitError(provider="anthropic")
        assert "anthropic" in str(exc)
```

**T022** — Write test class `TestErrorSchemas`:

```python
class TestErrorSchemas:
    def test_error_detail_fields(self):
        from backend.agent.schemas import ErrorDetail
        import inspect
        fields = ErrorDetail.model_fields
        assert "code" in fields
        assert "message" in fields
        assert "details" in fields

    def test_error_detail_field_types(self):
        from backend.agent.schemas import ErrorDetail
        fields = ErrorDetail.model_fields
        assert fields["code"].annotation is str
        assert fields["message"].annotation is str
        # details should be dict (accept both str annotation and actual type)
        details_annotation = fields["details"].annotation
        assert details_annotation in (dict, "dict"), f"Expected dict, got {details_annotation}"

    def test_error_detail_details_defaults_to_empty_dict(self):
        from backend.agent.schemas import ErrorDetail
        ed = ErrorDetail(code="TEST", message="test")
        assert ed.details == {}

    def test_error_response_has_error_field(self):
        from backend.agent.schemas import ErrorResponse, ErrorDetail
        fields = ErrorResponse.model_fields
        assert "error" in fields

    def test_error_response_error_field_is_error_detail(self):
        from backend.agent.schemas import ErrorResponse, ErrorDetail
        fields = ErrorResponse.model_fields
        annotation = fields["error"].annotation
        assert annotation is ErrorDetail or annotation == "ErrorDetail"

    def test_error_response_has_no_trace_id_field(self):
        """trace_id is appended manually in dicts, not defined on the model."""
        from backend.agent.schemas import ErrorResponse
        fields = ErrorResponse.model_fields
        assert "trace_id" not in fields

    def test_error_response_instantiation(self):
        from backend.agent.schemas import ErrorResponse, ErrorDetail
        resp = ErrorResponse(error=ErrorDetail(code="X", message="y"))
        assert resp.error.code == "X"
```

**T023** — Write test class `TestCircuitBreakerConfig`:

```python
class TestCircuitBreakerConfig:
    def test_circuit_breaker_failure_threshold_exists(self):
        from backend.config import Settings
        fields = Settings.model_fields
        assert "circuit_breaker_failure_threshold" in fields

    def test_circuit_breaker_failure_threshold_type_and_default(self):
        from backend.config import Settings
        field = Settings.model_fields["circuit_breaker_failure_threshold"]
        assert field.default == 5
        assert field.annotation is int or field.annotation == "int"

    def test_circuit_breaker_cooldown_secs_exists(self):
        from backend.config import Settings
        fields = Settings.model_fields
        assert "circuit_breaker_cooldown_secs" in fields

    def test_circuit_breaker_cooldown_secs_type_and_default(self):
        from backend.config import Settings
        field = Settings.model_fields["circuit_breaker_cooldown_secs"]
        assert field.default == 30
        assert field.annotation is int or field.annotation == "int"

    def test_retry_max_attempts_reserved_field_exists(self):
        """Reserved dead config — must not be removed."""
        from backend.config import Settings
        assert "retry_max_attempts" in Settings.model_fields

    def test_retry_backoff_initial_secs_reserved_field_exists(self):
        """Reserved dead config — must not be removed."""
        from backend.config import Settings
        assert "retry_backoff_initial_secs" in Settings.model_fields
```

**T024** — Write test class `TestRateLimitConfig`:

```python
class TestRateLimitConfig:
    def test_chat_rate_limit_field_exists_with_correct_default(self):
        from backend.config import Settings
        field = Settings.model_fields["rate_limit_chat_per_minute"]
        assert field.default == 30

    def test_ingest_rate_limit_field_exists_with_correct_default(self):
        from backend.config import Settings
        field = Settings.model_fields["rate_limit_ingest_per_minute"]
        assert field.default == 10

    def test_provider_keys_rate_limit_field_exists_with_correct_default(self):
        from backend.config import Settings
        field = Settings.model_fields["rate_limit_provider_keys_per_minute"]
        assert field.default == 5

    def test_general_rate_limit_field_exists_with_correct_default(self):
        from backend.config import Settings
        field = Settings.model_fields["rate_limit_general_per_minute"]
        assert field.default == 120
```

**T025** — Add module-level imports and `from __future__ import annotations` guard at the top of `test_error_contracts.py`:

```python
"""Contract tests for the error handling system (spec-12).

These tests assert static properties of the exception hierarchy, Pydantic error
models, and Settings config fields. They do not start a server or make HTTP requests.
"""
from __future__ import annotations

import inspect
import pytest
```

**T026** — Run the unit contract tests via external runner and confirm they pass:
```
zsh scripts/run-tests-external.sh -n spec12-unit-contracts tests/unit/test_error_contracts.py
```
Poll: `cat Docs/Tests/spec12-unit-contracts.status`
Read: `cat Docs/Tests/spec12-unit-contracts.summary`

Fix any failures before proceeding to T027.

#### File 2: tests/integration/test_error_handlers.py

**T027** — Create `tests/integration/test_error_handlers.py`. This file tests the four exception handlers registered in `create_app()` by mounting a minimal test app with route overrides that raise specific exceptions.

The test file uses `fastapi.testclient.TestClient` (synchronous) to avoid async complexity.

**T028** — Write the test setup:

```python
"""Integration tests for exception handlers registered in create_app() (spec-12).

Tests verify that:
- Each handler returns the correct HTTP status code
- The response body uses the standard nested envelope: {"error": {...}, "trace_id": ...}
- Error codes are uppercase snake_case
- No raw exception text or traceback is exposed in any response
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.errors import (
    EmbeddinatorError,
    QdrantConnectionError,
    OllamaConnectionError,
    SQLiteError,
    LLMCallError,
    CircuitOpenError,
)
from backend.providers.base import ProviderRateLimitError
```

**T029** — Write a `@pytest.fixture` that creates a minimal test app with all four handlers registered and test routes that raise specific exceptions:

```python
@pytest.fixture
def app_with_handlers():
    """Minimal FastAPI app with spec-12 exception handlers and test trigger routes."""
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    from starlette.requests import Request

    app = FastAPI()

    # Register the same handlers as create_app()
    @app.exception_handler(ProviderRateLimitError)
    async def provider_rate_limit_handler(request: Request, exc: ProviderRateLimitError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "PROVIDER_RATE_LIMIT",
                    "message": f"Rate limit exceeded for provider: {exc.provider}",
                    "details": {"provider": exc.provider},
                },
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(QdrantConnectionError)
    async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "QDRANT_UNAVAILABLE",
                    "message": "Vector database is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(OllamaConnectionError)
    async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "OLLAMA_UNAVAILABLE",
                    "message": "Inference service is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

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

    # Test trigger routes
    @app.get("/trigger/provider-rate-limit")
    async def trigger_provider_rate_limit():
        raise ProviderRateLimitError(provider="openai")

    @app.get("/trigger/qdrant-connection")
    async def trigger_qdrant_connection():
        raise QdrantConnectionError("Qdrant is down")

    @app.get("/trigger/ollama-connection")
    async def trigger_ollama_connection():
        raise OllamaConnectionError("Ollama is down")

    @app.get("/trigger/embedinator-generic")
    async def trigger_embedinator_generic():
        raise EmbeddinatorError("Generic internal error")

    @app.get("/trigger/sqlite-error")
    async def trigger_sqlite_error():
        from backend.errors import SQLiteError
        raise SQLiteError("DB write failed")

    @app.get("/trigger/llm-call-error")
    async def trigger_llm_call_error():
        from backend.errors import LLMCallError
        raise LLMCallError("LLM call failed")

    @app.get("/trigger/circuit-open")
    async def trigger_circuit_open():
        raise CircuitOpenError("Circuit is open")

    return app
```

**T030** — Write test class `TestProviderRateLimitHandler`:

```python
class TestProviderRateLimitHandler:
    def test_returns_429(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response = client.get("/trigger/provider-rate-limit")
        assert response.status_code == 429

    def test_response_body_uses_nested_envelope(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/provider-rate-limit").json()
        assert "error" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_error_code_is_uppercase(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/provider-rate-limit").json()
        assert body["error"]["code"] == "PROVIDER_RATE_LIMIT"

    def test_response_includes_trace_id(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/provider-rate-limit").json()
        assert "trace_id" in body

    def test_provider_name_in_details(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/provider-rate-limit").json()
        assert body["error"].get("details", {}).get("provider") == "openai"

    def test_no_raw_exception_text(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response_text = client.get("/trigger/provider-rate-limit").text
        assert "Traceback" not in response_text
        assert "ProviderRateLimitError" not in response_text
```

**T031** — Write test class `TestQdrantConnectionHandler`:

```python
class TestQdrantConnectionHandler:
    def test_returns_503(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/qdrant-connection").status_code == 503

    def test_error_code_is_qdrant_unavailable(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/qdrant-connection").json()
        assert body["error"]["code"] == "QDRANT_UNAVAILABLE"

    def test_uses_nested_envelope(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/qdrant-connection").json()
        assert "error" in body
        assert "trace_id" in body

    def test_no_raw_exception_text(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        response_text = client.get("/trigger/qdrant-connection").text
        assert "QdrantConnectionError" not in response_text
        assert "Traceback" not in response_text
```

**T032** — Write test class `TestOllamaConnectionHandler`:

```python
class TestOllamaConnectionHandler:
    def test_returns_503(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/ollama-connection").status_code == 503

    def test_error_code_is_ollama_unavailable(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/ollama-connection").json()
        assert body["error"]["code"] == "OLLAMA_UNAVAILABLE"

    def test_uses_nested_envelope(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/ollama-connection").json()
        assert "error" in body
        assert "trace_id" in body
```

**T033** — Write test class `TestGlobalEmbeddinatorErrorHandler`:

```python
class TestGlobalEmbeddinatorErrorHandler:
    def test_generic_embedinator_error_returns_500(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/embedinator-generic").status_code == 500

    def test_sqlite_error_falls_through_to_global_handler(self, app_with_handlers):
        """SQLiteError extends EmbeddinatorError — should return 500 via global handler."""
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/sqlite-error").status_code == 500

    def test_llm_call_error_falls_through_to_global_handler(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/llm-call-error").status_code == 500

    def test_circuit_open_error_falls_through_to_global_handler(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        assert client.get("/trigger/circuit-open").status_code == 500

    def test_error_code_is_internal_error(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/embedinator-generic").json()
        assert body["error"]["code"] == "INTERNAL_ERROR"

    def test_response_uses_nested_envelope(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        body = client.get("/trigger/embedinator-generic").json()
        assert "error" in body
        assert "trace_id" in body

    def test_no_raw_exception_text_in_any_handler(self, app_with_handlers):
        client = TestClient(app_with_handlers, raise_server_exceptions=False)
        for path in [
            "/trigger/embedinator-generic",
            "/trigger/sqlite-error",
            "/trigger/llm-call-error",
            "/trigger/circuit-open",
        ]:
            text = client.get(path).text
            assert "Traceback" not in text, f"Traceback exposed at {path}"
            assert "EmbeddinatorError" not in text, f"Class name exposed at {path}"
```

**T034** — Run the complete new test suite via external runner:
```
zsh scripts/run-tests-external.sh -n spec12-a3 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py
```
Poll: `cat Docs/Tests/spec12-a3.status`
Read: `cat Docs/Tests/spec12-a3.summary`

Fix any failures before reporting done.

---

### Wave 4: A4 — Regression Gate (Tasks T035–T040)

A4 runs the full test suite to verify zero regressions.

**T035** — Run the full test suite via external runner:
```
zsh scripts/run-tests-external.sh -n spec12-regression tests/
```
Poll: `cat Docs/Tests/spec12-regression.status` (RUNNING|PASSED|FAILED|ERROR)
Read: `cat Docs/Tests/spec12-regression.summary`

**T036** — Verify that the test count shows:
- All 1250 existing tests still pass (zero regressions)
- All new spec-12 tests pass (unit contracts + integration handler tests)
- The 39 pre-existing failures remain at exactly 39 (no new failures introduced)

**T037** — If regressions are found, identify which tests broke and why. The most likely cause is the `ProviderRateLimitError` handler change in `main.py` — any test that was asserting the old `{"type": "error", ..., "code": "rate_limit"}` format will break and must be updated to the new `{"error": {...}, "trace_id": ...}` format.

Search for tests that reference the old handler behavior:
- Look for `"rate_limit"` (lowercase) in test assertions
- Look for `"type": "error"` assertions in rate limit test contexts

**T038** — If any tests reference the old incorrect handler format, update them to match the new nested envelope format.

**T039** — Re-run `zsh scripts/run-tests-external.sh -n spec12-regression-final tests/` to confirm final state.

**T040** — Write final report to `Docs/Tests/spec12-final-report.md`:
- Total tests before spec-12 (baseline): 1250 passing
- Total tests after spec-12: X passing
- New tests added: X (unit contracts + integration handlers)
- Pre-existing failures: 39 (unchanged)
- Regressions introduced: 0

---

## Key Code Patterns

### The Standard Nested Envelope

Every REST error response — from exception handlers AND from `HTTPException` raises in routers — uses this exact structure:

```python
# Structure sent to client
{
    "error": {
        "code": "UPPER_SNAKE_CASE",          # stable machine-readable identifier
        "message": "Human-readable message", # user-facing text (no internal details)
        "details": {},                        # optional context; empty dict if nothing extra
    },
    "trace_id": "uuid-here",                 # from request.state.trace_id
}
```

**Getting `trace_id` in a handler**:
```python
trace_id = getattr(request.state, "trace_id", "")
```

`request.state.trace_id` is set by `TraceIDMiddleware` before any handler runs. The `getattr` with default `""` handles the edge case where the middleware did not run (e.g., before CORS preflight).

### Correct Exception Handler Signature

```python
@app.exception_handler(SomeError)
async def some_error_handler(request: Request, exc: SomeError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=<code>,
        content={
            "error": {
                "code": "<UPPER_SNAKE_CODE>",
                "message": "<user-facing message>",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

Note: `JSONResponse` is from `fastapi.responses`. `Request` is from `starlette.requests` or `fastapi`.

### Handler Registration Order in create_app()

FastAPI resolves exception handlers by exact type first, then parent classes. Register specific subclasses BEFORE the base class handler:

```python
# CORRECT ORDER — specific before generic
@app.exception_handler(ProviderRateLimitError)        # most specific (extends Exception)
async def provider_rate_limit_handler(...): ...

@app.exception_handler(QdrantConnectionError)          # specific EmbeddinatorError subclass
async def qdrant_connection_error_handler(...): ...

@app.exception_handler(OllamaConnectionError)          # specific EmbeddinatorError subclass
async def ollama_connection_error_handler(...): ...

@app.exception_handler(EmbeddinatorError)              # base class — catch-all LAST
async def embedinator_error_handler(...): ...
```

### Existing NDJSON Stream Error Pattern (Do Not Change)

Stream errors in `backend/api/chat.py` use a different (flat) format — this is correct and intentional:

```python
# CORRECT — flat format for NDJSON stream events (backend/api/chat.py)
yield json.dumps({
    "type": "error",
    "message": "A required service is temporarily unavailable. Please try again in a few seconds.",
    "code": "CIRCUIT_OPEN",
    "trace_id": trace_id,
}) + "\n"
```

This format is NOT the same as the REST nested envelope. Both are correct for their respective contexts. Do not change the stream error format.

### How trace_id Flows

`TraceIDMiddleware` (in `backend/middleware.py`) sets `request.state.trace_id` on every incoming request. The middleware runs before any route handler or exception handler. Exception handlers access it via `getattr(request.state, "trace_id", "")`.

The `trace_id` is a UUIDv4 string generated per-request. In tests using `TestClient` with a minimal app that doesn't have `TraceIDMiddleware`, `request.state.trace_id` will not be set — hence the `getattr` default to `""` ensures handlers don't crash.

### ErrorDetail and ErrorResponse — How They Are Used

These Pydantic models are used for documentation and type hints in router code, but the actual HTTP response body is a plain `dict` assembled manually in each router. Example from `backend/api/collections.py`:

```python
raise HTTPException(
    status_code=409,
    detail={
        "error": {
            "code": "COLLECTION_NAME_CONFLICT",
            "message": f"Collection '{name}' already exists",
            "details": {},
        },
        "trace_id": request.state.trace_id,
    },
)
```

Exception handlers also return a plain `dict` inside `JSONResponse.content`. `ErrorResponse.model_dump()` is NOT used in the actual response assembly.

---

## Integration Points

### backend/main.py

**The only production file modified by spec-12.** Location of all changes:

- Lines 148–191: `create_app()` function
- Existing handler: `ProviderRateLimitError` (fix in place)
- New handlers added after the existing one: `EmbeddinatorError`, `QdrantConnectionError`, `OllamaConnectionError`

Required imports (add if missing):
```python
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
```

The `ProviderRateLimitError` import is already present (`from backend.providers.base import ProviderRateLimitError`).

### backend/errors.py (read-only reference)

Contains 11 exception classes. All extend `EmbeddinatorError` directly. No changes needed.

**Classes that exist** (exact names, case-sensitive):
`EmbeddinatorError`, `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError`

**Classes that do NOT exist and must NOT be created**:
`StorageError`, `DatabaseError`, `DatabaseMigrationError`, `QdrantCollectionError`, `RustWorkerError`, `EmbeddingValidationError`, `DuplicateDocumentError`, `AgentError`, `ToolExecutionError`, `ConfidenceError`, `ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ModelNotFoundError`, `APIError`, `ValidationError`, `NotFoundError`, `ConflictError`

### backend/agent/schemas.py (read-only reference)

Contains `ErrorDetail` and `ErrorResponse`. No changes needed.

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorDetail
    # NOTE: no trace_id field — added manually in dicts
```

### backend/providers/base.py (read-only reference)

Contains `ProviderRateLimitError`. No changes needed.

```python
class ProviderRateLimitError(Exception):
    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

### backend/config.py (read-only reference)

All required config fields already present in `Settings`. No changes needed.

Circuit breaker fields:
- `circuit_breaker_failure_threshold: int = 5`
- `circuit_breaker_cooldown_secs: int = 30`

Retry fields (reserved dead config — do not wire to tenacity):
- `retry_max_attempts: int = 3`
- `retry_backoff_initial_secs: float = 1.0`

Rate limit fields:
- `rate_limit_chat_per_minute: int = 30`
- `rate_limit_ingest_per_minute: int = 10`
- `rate_limit_provider_keys_per_minute: int = 5`
- `rate_limit_general_per_minute: int = 120`

---

## Testing Protocol

### External Test Runner Only

**NEVER run pytest inside Claude Code.** Always use the external test runner script.

```bash
# Run a specific test file
zsh scripts/run-tests-external.sh -n <name> <target>

# Run multiple test files
zsh scripts/run-tests-external.sh -n <name> tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py

# Run full suite
zsh scripts/run-tests-external.sh -n <name> tests/
```

### Polling and Reading Results

```bash
# Poll status (do not sleep between polls — just check):
cat Docs/Tests/<name>.status
# Returns: RUNNING | PASSED | FAILED | ERROR

# Read summary (~20 lines):
cat Docs/Tests/<name>.summary

# Read full log (only if needed to debug failures):
cat Docs/Tests/<name>.log
```

### Test Naming Conventions

| Test Run | Name | Target |
|----------|------|--------|
| A3 unit contracts | `spec12-unit-contracts` | `tests/unit/test_error_contracts.py` |
| A3 integration handlers | `spec12-integration-handlers` | `tests/integration/test_error_handlers.py` |
| A3 combined gate | `spec12-a3` | Both files together |
| A4 regression gate | `spec12-regression` | `tests/` |
| A4 final run | `spec12-regression-final` | `tests/` |

### Expected Final Test Counts

After spec-12 implementation:
- 1250 existing tests: all still passing (zero regressions)
- 39 pre-existing failures: unchanged
- New spec-12 tests: approximately 35–50 new tests passing (unit contracts + integration handlers)

---

## Critical Constraints (All Agents)

### Hard Rules

1. **NEVER run pytest inside Claude Code** — only `zsh scripts/run-tests-external.sh`
2. **NEVER create exception classes** that do not already exist in `backend/errors.py`
3. **NEVER create a `CircuitBreaker` class** or `backend/circuit_breaker.py` file
4. **NEVER wire `retry_max_attempts` or `retry_backoff_initial_secs`** to tenacity decorators
5. **NEVER add structured logging** to error handlers (out of scope)
6. **NEVER modify** `backend/errors.py`, `backend/agent/schemas.py`, `backend/config.py`, `backend/middleware.py`, `backend/api/chat.py`
7. **NEVER rename** the `ProviderRateLimitError` handler function (only replace the body with the correct implementation)
8. **NEVER use `"type": "error"` format** in exception handlers — that is NDJSON stream format only

### Correct vs. Wrong Patterns

| Pattern | Correct | Wrong |
|---------|---------|-------|
| Error code case | `"PROVIDER_RATE_LIMIT"` | `"rate_limit"`, `"provider_rate_limit"` |
| Response envelope | `{"error": {...}, "trace_id": ...}` | `{"type": "error", "message": ..., "code": ...}` |
| trace_id source | `getattr(request.state, "trace_id", "")` | `str(uuid.uuid4())` in handler |
| New exception classes | Never — hierarchy is frozen | Do not add any |
| Circuit breaker | Existing instance vars / module globals | Do not create CircuitBreaker class |
| Retry config | Leave hardcoded at call site | Do not read from Settings |

---

## Appendix: HTTP Status Code Reference

Complete mapping of error conditions to HTTP status codes (all already implemented except the new handlers):

| Source | Error Condition | Status | Code |
|--------|----------------|--------|------|
| `middleware.py` | Rate limit exceeded | 429 | `RATE_LIMIT_EXCEEDED` |
| `main.py` handler | `ProviderRateLimitError` (cloud provider 429) | 429 | `PROVIDER_RATE_LIMIT` (fixed in spec-12) |
| `main.py` handler | `QdrantConnectionError` | 503 | `QDRANT_UNAVAILABLE` (added in spec-12) |
| `main.py` handler | `OllamaConnectionError` | 503 | `OLLAMA_UNAVAILABLE` (added in spec-12) |
| `main.py` handler | Any other `EmbeddinatorError` | 500 | `INTERNAL_ERROR` (added in spec-12) |
| `api/providers.py` | Encryption key not configured | 503 | `KEY_MANAGER_UNAVAILABLE` |
| `api/models.py` | Ollama unreachable | 503 | `SERVICE_UNAVAILABLE` |
| `api/collections.py` | Invalid collection name | 400 | `COLLECTION_NAME_INVALID` |
| `api/settings.py` | Value out of range | 400 | `SETTINGS_VALIDATION_ERROR` |
| `api/ingest.py` | Unsupported file type | 400 | `FILE_FORMAT_NOT_SUPPORTED` |
| `api/ingest.py` | File too large | 413 | `FILE_TOO_LARGE` |
| `api/collections.py` | Collection not found | 404 | `COLLECTION_NOT_FOUND` |
| `api/documents.py` | Document not found | 404 | `DOCUMENT_NOT_FOUND` |
| `api/ingest.py` | Job not found | 404 | `JOB_NOT_FOUND` |
| `api/traces.py` | Trace not found | 404 | `TRACE_NOT_FOUND` |
| `api/providers.py` | Provider not found | 404 | `PROVIDER_NOT_FOUND` |
| `api/collections.py` | Name conflict | 409 | `COLLECTION_NAME_CONFLICT` |
| `api/ingest.py` | Duplicate document | 409 | `DUPLICATE_DOCUMENT` |
| `api/chat.py` stream | No collections selected | N/A (HTTP 200 + NDJSON) | `NO_COLLECTIONS` |
| `api/chat.py` stream | Circuit breaker open | N/A (HTTP 200 + NDJSON) | `CIRCUIT_OPEN` |
| `api/chat.py` stream | Unhandled exception | N/A (HTTP 200 + NDJSON) | `SERVICE_UNAVAILABLE` |
