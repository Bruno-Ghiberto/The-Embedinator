# A3: Test Files -- Spec 12 Error Handling

**Wave**: 3 of 4 | **Branch**: `012-error-handling`

---

## This Is Your Briefing File

Your orchestrator spawned you with the prompt:
> "Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/A3-tests.md FIRST, then await further instructions."

After you finish reading this file in full, signal readiness to the orchestrator by posting:

```
A3 ready -- briefing complete
```

The orchestrator will then send you specific task assignments via `SendMessage`. Execute each task as it arrives, using the MCP tools and task details in this file as your reference.

---

## Agent Configuration

| Field | Value |
|-------|-------|
| **subagent_type** | `python-expert` |
| **model** | `claude-sonnet-4-6` |
| **rationale** | Test writing across 2 files with 7+4 test classes; Sonnet handles test authoring well |

---

## MCP Tools Available

Use these tools to verify codebase facts before writing tests.

| Tool | When to use |
|------|-------------|
| `mcp__serena__find_symbol` | Look up exact class names in `backend/errors.py`, field names in `backend/agent/schemas.py`, before hardcoding them into tests |
| `mcp__serena__get_symbols_overview` | Scan existing test files (e.g., `tests/unit/`, `tests/integration/`) for naming and import patterns to follow |
| `mcp__sequential-thinking__sequentialthinking` | Plan the structure and ordering of test classes across both files before writing any code |

---

## Prerequisites

1. **A2 gate must be PASSED** -- confirm `Docs/Tests/spec12-a2-smoke.status` contains `PASSED` before writing any test code.
2. Read `Docs/Tests/spec12-a1-audit.md` -- use A1's findings for exact class names, field names, and line numbers.
3. Read `backend/main.py` to see the 4 handlers as they actually exist after A2's work.

---

## Mission

Create two new test files:

1. `tests/unit/test_error_contracts.py` -- contract tests (static inspection, no server)
2. `tests/integration/test_error_handlers.py` -- integration tests using FastAPI `TestClient`

Then run each via the external test runner and confirm PASSED before adding more test classes.

---

## Critical Rules

- **NEVER run pytest inside Claude Code.** Use `zsh scripts/run-tests-external.sh` only.
- **NEVER import from `backend.errors` using classes that don't exist** -- check the A1 audit for the exact class list. The 18 invented classes in the OLD `12-implement.md` do NOT exist.
- **NEVER modify `backend/errors.py`, `backend/main.py`, or any production code.** This wave is tests only.
- **NEVER use `AsyncMock()` as a LangGraph checkpointer** -- use `MemorySaver()` in integration tests if needed.
- Use `from __future__ import annotations` at the top of both test files.
- Use `monkeypatch.setenv()` not `os.environ[]` in tests to avoid env variable leaks.
- All test names must be unique across the file -- do not reuse method names across test classes.

---

## Phase 3: US1 -- Create `tests/unit/test_error_contracts.py`

### T019: Create the file with header

Create `tests/unit/test_error_contracts.py`:

```python
"""
Contract tests for spec-12 error handling.

These tests perform static introspection -- they verify the error hierarchy,
Pydantic models, and config field contracts WITHOUT starting a server.
Tests must remain green after any refactor of error handling code.
"""
from __future__ import annotations
```

Do not add any test classes yet -- this establishes the file exists for subsequent tasks.

### T020: Add `TestErrorHierarchy` class

Add to `tests/unit/test_error_contracts.py`:

```python
import importlib
import inspect

import pytest

from backend.errors import EmbeddinatorError


class TestErrorHierarchy:
    """Verify the exception hierarchy matches the spec-12 contract."""

    # Use the A1 audit report for the exact list -- do NOT hardcode wrong names.
    REQUIRED_SUBCLASS_NAMES = {
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
        # Add any additional class found by A1 here
    }

    def test_all_required_classes_exist(self):
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            assert hasattr(errors_module, name), f"Missing class: {name}"

    def test_root_base_is_exception(self):
        assert issubclass(EmbeddinatorError, Exception)

    def test_all_subclasses_extend_embedinator_error_directly(self):
        """No intermediate base classes -- flat hierarchy."""
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            cls = getattr(errors_module, name)
            assert EmbeddinatorError in cls.__bases__, (
                f"{name} does not directly extend EmbeddinatorError "
                f"(bases: {cls.__bases__})"
            )

    def test_embedinator_error_has_no_custom_init(self):
        """EmbeddinatorError.__init__ must not be overridden -- no code, message fields."""
        assert EmbeddinatorError.__init__ is Exception.__init__, (
            "EmbeddinatorError must not override __init__"
        )

    def test_exception_classes_are_instantiable_with_string(self):
        """All subclasses can be created with a plain string message."""
        import backend.errors as errors_module
        for name in self.REQUIRED_SUBCLASS_NAMES:
            cls = getattr(errors_module, name)
            exc = cls("test message")
            assert str(exc) == "test message"
```

**Important**: Cross-reference the `REQUIRED_SUBCLASS_NAMES` set with the A1 audit report. If A1 found a different count or different names, update the set before writing this class.

### T021: Add `TestProviderRateLimitError` class

Add to `tests/unit/test_error_contracts.py`:

```python
from backend.providers.base import ProviderRateLimitError
from backend.errors import EmbeddinatorError


class TestProviderRateLimitError:
    """ProviderRateLimitError is separate from the EmbeddinatorError hierarchy."""

    def test_lives_in_providers_base(self):
        import backend.providers.base as providers_base
        assert hasattr(providers_base, "ProviderRateLimitError")

    def test_extends_exception_not_embedinator_error(self):
        assert issubclass(ProviderRateLimitError, Exception)
        assert not issubclass(ProviderRateLimitError, EmbeddinatorError)

    def test_requires_provider_argument(self):
        with pytest.raises(TypeError):
            ProviderRateLimitError()  # must fail without provider arg

    def test_has_provider_attribute(self):
        exc = ProviderRateLimitError("openai")
        assert exc.provider == "openai"

    def test_str_message_contains_provider_name(self):
        exc = ProviderRateLimitError("anthropic")
        assert "anthropic" in str(exc)
```

### T022: Add `TestErrorSchemas` class

Add to `tests/unit/test_error_contracts.py`:

```python
import pydantic

from backend.agent.schemas import ErrorDetail, ErrorResponse


class TestErrorSchemas:
    """Verify Pydantic model contracts for the error envelope."""

    def test_error_detail_has_required_fields(self):
        model_fields = ErrorDetail.model_fields
        assert "code" in model_fields
        assert "message" in model_fields
        assert "details" in model_fields

    def test_error_detail_details_defaults_to_empty_dict(self):
        ed = ErrorDetail(code="X", message="y")
        assert ed.details == {}

    def test_error_detail_code_is_str(self):
        field = ErrorDetail.model_fields["code"]
        # annotation may be string due to __future__ annotations
        assert field.annotation in (str, "str")

    def test_error_response_has_error_field(self):
        model_fields = ErrorResponse.model_fields
        assert "error" in model_fields

    def test_error_response_has_no_trace_id_field(self):
        """trace_id is NOT a Pydantic field -- it is added as a plain dict key in handlers."""
        model_fields = ErrorResponse.model_fields
        assert "trace_id" not in model_fields, (
            "ErrorResponse must not have a trace_id field. "
            "trace_id is appended as a plain dict key: {'error': {...}, 'trace_id': '...'}"
        )

    def test_error_response_wraps_error_detail(self):
        ed = ErrorDetail(code="TEST", message="test msg")
        er = ErrorResponse(error=ed)
        assert er.error.code == "TEST"
        assert er.error.message == "test msg"
```

### T023: Run unit contract tests via external runner

```bash
zsh scripts/run-tests-external.sh -n spec12-unit-contracts tests/unit/test_error_contracts.py
```

Poll:
```bash
cat Docs/Tests/spec12-unit-contracts.status
```

If PASSED: proceed to T024.
If FAILED: read `Docs/Tests/spec12-unit-contracts.summary` and fix. Common failures:
- Wrong class names in `REQUIRED_SUBCLASS_NAMES` → update from A1 audit
- `EmbeddinatorError.__init__` IS overridden → update test expectation to match actual code
- `ErrorResponse` field structure differs → update test assertions to match actual model

Fix until PASSED before proceeding.

---

## Phase 3 (continued): Create `tests/integration/test_error_handlers.py`

### T024: Create `test_error_handlers.py` with fixture

Create `tests/integration/test_error_handlers.py`:

```python
"""
Integration tests for spec-12 exception handlers in backend/main.py.

Uses a minimal FastAPI app with the same 4 handlers registered and
trigger routes for each exception type. Tests verify HTTP status codes
and response body shape WITHOUT needing the full app startup.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from backend.errors import (
    EmbeddinatorError,
    QdrantConnectionError,
    OllamaConnectionError,
    SQLiteError,
    LLMCallError,
    CircuitOpenError,
)
from backend.providers.base import ProviderRateLimitError


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with all 4 spec-12 handlers and trigger routes."""
    app = FastAPI()

    # Register handlers in the same order as backend/main.py
    @app.exception_handler(ProviderRateLimitError)
    async def rate_limit_handler(request, exc: ProviderRateLimitError):
        from fastapi.responses import JSONResponse
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

    @app.exception_handler(EmbeddinatorError)
    async def embedinator_error_handler(request, exc: EmbeddinatorError):
        from fastapi.responses import JSONResponse
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred", "details": {}},
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(QdrantConnectionError)
    async def qdrant_handler(request, exc: QdrantConnectionError):
        from fastapi.responses import JSONResponse
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {"code": "QDRANT_UNAVAILABLE", "message": "Vector database is temporarily unavailable", "details": {}},
                "trace_id": trace_id,
            },
        )

    @app.exception_handler(OllamaConnectionError)
    async def ollama_handler(request, exc: OllamaConnectionError):
        from fastapi.responses import JSONResponse
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {"code": "OLLAMA_UNAVAILABLE", "message": "Inference service is temporarily unavailable", "details": {}},
                "trace_id": trace_id,
            },
        )

    # Trigger routes -- each raises a specific exception
    @app.get("/trigger/rate-limit")
    async def trigger_rate_limit():
        raise ProviderRateLimitError("openai")

    @app.get("/trigger/embedinator")
    async def trigger_embedinator():
        raise EmbeddinatorError("generic error")

    @app.get("/trigger/qdrant")
    async def trigger_qdrant():
        raise QdrantConnectionError("qdrant is down")

    @app.get("/trigger/ollama")
    async def trigger_ollama():
        raise OllamaConnectionError("ollama is down")

    @app.get("/trigger/sqlite")
    async def trigger_sqlite():
        raise SQLiteError("db error")

    @app.get("/trigger/llm")
    async def trigger_llm():
        raise LLMCallError("llm failed")

    @app.get("/trigger/circuit")
    async def trigger_circuit():
        raise CircuitOpenError("circuit is open")

    return app


@pytest.fixture
def app_with_handlers():
    return _build_test_app()


@pytest.fixture
def client(app_with_handlers):
    return TestClient(app_with_handlers, raise_server_exceptions=False)
```

**Note**: The fixture re-implements the handlers inline rather than importing from `backend.main` so that tests remain isolated. The production handlers in `backend/main.py` are tested via the production app in the regression suite (Wave 4).

### T025: Add `TestProviderRateLimitHandler`

Add to `tests/integration/test_error_handlers.py`:

```python
class TestProviderRateLimitHandler:
    def test_returns_429(self, client):
        resp = client.get("/trigger/rate-limit")
        assert resp.status_code == 429

    def test_response_body_uses_nested_envelope(self, client):
        resp = client.get("/trigger/rate-limit")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body

    def test_error_code_is_uppercase(self, client):
        resp = client.get("/trigger/rate-limit")
        code = resp.json()["error"]["code"]
        assert code == code.upper(), f"code must be UPPER_SNAKE_CASE, got: {code}"
        assert code == "PROVIDER_RATE_LIMIT"

    def test_response_includes_trace_id(self, client):
        resp = client.get("/trigger/rate-limit")
        trace_id = resp.json()["trace_id"]
        assert trace_id is not None  # "" is valid (no TraceIDMiddleware in test)

    def test_provider_name_in_details(self, client):
        resp = client.get("/trigger/rate-limit")
        details = resp.json()["error"]["details"]
        assert details.get("provider") == "openai"

    def test_no_raw_exception_text(self, client):
        resp = client.get("/trigger/rate-limit")
        body_str = resp.text
        assert "ProviderRateLimitError" not in body_str
        assert "Traceback" not in body_str
```

### T026: Add `TestQdrantConnectionHandler`

```python
class TestQdrantConnectionHandler:
    def test_returns_503(self, client):
        resp = client.get("/trigger/qdrant")
        assert resp.status_code == 503

    def test_error_code_is_qdrant_unavailable(self, client):
        resp = client.get("/trigger/qdrant")
        assert resp.json()["error"]["code"] == "QDRANT_UNAVAILABLE"

    def test_uses_nested_envelope(self, client):
        resp = client.get("/trigger/qdrant")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body
        assert "code" in body["error"]
        assert "message" in body["error"]

    def test_no_raw_exception_text(self, client):
        resp = client.get("/trigger/qdrant")
        assert "QdrantConnectionError" not in resp.text
```

### T027: Add `TestOllamaConnectionHandler`

```python
class TestOllamaConnectionHandler:
    def test_returns_503(self, client):
        resp = client.get("/trigger/ollama")
        assert resp.status_code == 503

    def test_error_code_is_ollama_unavailable(self, client):
        resp = client.get("/trigger/ollama")
        assert resp.json()["error"]["code"] == "OLLAMA_UNAVAILABLE"

    def test_uses_nested_envelope(self, client):
        resp = client.get("/trigger/ollama")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body
```

### T028: Add `TestGlobalEmbeddinatorErrorHandler`

```python
class TestGlobalEmbeddinatorErrorHandler:
    def test_generic_embedinator_error_returns_500(self, client):
        resp = client.get("/trigger/embedinator")
        assert resp.status_code == 500

    def test_sqlite_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/sqlite")
        assert resp.status_code == 500

    def test_llm_call_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/llm")
        assert resp.status_code == 500

    def test_circuit_open_error_falls_through_to_global_handler(self, client):
        resp = client.get("/trigger/circuit")
        assert resp.status_code == 500

    def test_error_code_is_internal_error(self, client):
        resp = client.get("/trigger/embedinator")
        assert resp.json()["error"]["code"] == "INTERNAL_ERROR"

    def test_response_uses_nested_envelope(self, client):
        resp = client.get("/trigger/embedinator")
        body = resp.json()
        assert "error" in body
        assert "trace_id" in body
        assert "code" in body["error"]
        assert "message" in body["error"]
        assert "details" in body["error"]

    def test_no_raw_exception_text_in_any_handler(self, client):
        for route in ["/trigger/embedinator", "/trigger/qdrant", "/trigger/ollama", "/trigger/rate-limit"]:
            resp = client.get(route)
            assert "Traceback" not in resp.text
            assert "Exception" not in resp.text or resp.json()  # JSON body is fine; raw stack trace is not
```

### T029: Run integration handler tests via external runner

```bash
zsh scripts/run-tests-external.sh -n spec12-integration-handlers tests/integration/test_error_handlers.py
```

Poll:
```bash
cat Docs/Tests/spec12-integration-handlers.status
```

If FAILED: read `Docs/Tests/spec12-integration-handlers.summary`. Fix test code (not production code). Re-run.

### T030: Run combined US1 gate

```bash
zsh scripts/run-tests-external.sh -n spec12-us1 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py
```

Confirm PASSED before proceeding to Phase 4.

---

## Phase 4: US2-US4 -- Add contract test classes to `test_error_contracts.py`

### T031: Add `TestCircuitBreakerConfig`

Append to `tests/unit/test_error_contracts.py`:

```python
from backend.config import Settings


class TestCircuitBreakerConfig:
    """Verify circuit breaker config field contracts."""

    def test_circuit_breaker_failure_threshold_default(self):
        s = Settings()
        assert s.circuit_breaker_failure_threshold == 5
        assert isinstance(s.circuit_breaker_failure_threshold, int)

    def test_circuit_breaker_cooldown_secs_default(self):
        s = Settings()
        assert s.circuit_breaker_cooldown_secs == 30
        assert isinstance(s.circuit_breaker_cooldown_secs, int)

    def test_retry_max_attempts_field_exists_and_is_reserved(self):
        """retry_max_attempts is dead config -- reserved for future spec. MUST NOT be removed."""
        s = Settings()
        assert hasattr(s, "retry_max_attempts")
        assert isinstance(s.retry_max_attempts, int)

    def test_retry_backoff_initial_secs_field_exists_and_is_reserved(self):
        """retry_backoff_initial_secs is dead config -- reserved for future spec. MUST NOT be removed."""
        s = Settings()
        assert hasattr(s, "retry_backoff_initial_secs")
```

### T032: Add `TestRateLimitConfig`

Append to `tests/unit/test_error_contracts.py`:

```python
class TestRateLimitConfig:
    """Verify rate limit config field contracts."""

    def test_rate_limit_chat_per_minute(self):
        s = Settings()
        assert s.rate_limit_chat_per_minute == 30

    def test_rate_limit_ingest_per_minute(self):
        s = Settings()
        assert s.rate_limit_ingest_per_minute == 10

    def test_rate_limit_provider_keys_per_minute(self):
        s = Settings()
        assert s.rate_limit_provider_keys_per_minute == 5

    def test_rate_limit_general_per_minute(self):
        s = Settings()
        assert s.rate_limit_general_per_minute == 120
```

### T033: Add `TestStreamErrorCodes`

Append to `tests/unit/test_error_contracts.py`:

```python
import pathlib


class TestStreamErrorCodes:
    """Verify NDJSON stream error codes are present in chat.py (static code inspection).

    These tests prevent accidental renaming of stream error codes that would break
    frontend consumers. The NDJSON format {"type": "error", "code": ...} is intentionally
    different from the REST error envelope -- do NOT unify them.
    """

    _chat_source: str = ""

    @classmethod
    def setup_class(cls):
        chat_path = pathlib.Path(__file__).parent.parent.parent / "backend" / "api" / "chat.py"
        cls._chat_source = chat_path.read_text()

    def test_no_collections_code_present(self):
        assert "NO_COLLECTIONS" in self._chat_source

    def test_circuit_open_code_present(self):
        assert "CIRCUIT_OPEN" in self._chat_source

    def test_service_unavailable_code_present(self):
        assert "SERVICE_UNAVAILABLE" in self._chat_source
```

### T034: Run updated unit contract tests

```bash
zsh scripts/run-tests-external.sh -n spec12-us2-us4 tests/unit/test_error_contracts.py
```

Confirm PASSED with all new test classes.

---

## Phase 5: US5 -- Provider Key Error Codes

### T035: Add `TestProviderKeyErrorCodes`

Append to `tests/unit/test_error_contracts.py`:

```python
class TestProviderKeyErrorCodes:
    """Verify KEY_MANAGER_UNAVAILABLE code is used in providers.py (static code inspection).

    This test prevents accidental removal of the error code that protects
    provider key operations when the Fernet key manager is not configured.
    """

    _providers_source: str = ""

    @classmethod
    def setup_class(cls):
        providers_path = pathlib.Path(__file__).parent.parent.parent / "backend" / "api" / "providers.py"
        cls._providers_source = providers_path.read_text()

    def test_key_manager_unavailable_code_present(self):
        assert "KEY_MANAGER_UNAVAILABLE" in self._providers_source
```

### T036: Run final unit contract tests

```bash
zsh scripts/run-tests-external.sh -n spec12-us5-final tests/unit/test_error_contracts.py
```

Confirm all test classes pass. The full `test_error_contracts.py` should now contain:
- `TestErrorHierarchy`
- `TestProviderRateLimitError`
- `TestErrorSchemas`
- `TestCircuitBreakerConfig`
- `TestRateLimitConfig`
- `TestStreamErrorCodes`
- `TestProviderKeyErrorCodes`

**A3 is complete when T036 confirms PASSED. Notify the orchestrator so Wave 4 (A4) can begin.**

---

## Test Naming Convention

| Test naming pattern | Example |
|--------------------|---------|
| `test_<what>_<expected>` | `test_returns_429` |
| `test_<thing>_<property>` | `test_error_code_is_uppercase` |
| `test_<action>_<result>` | `test_provider_name_in_details` |
| `test_no_<bad_thing>` | `test_no_raw_exception_text` |

All test method names within a class must be unique. All class names within a file must be unique.

---

## Reference Documents

- A1 audit (REQUIRED before T020): `Docs/Tests/spec12-a1-audit.md`
- Data model (exact class names): `specs/012-error-handling/data-model.md`
- Contract (envelope schema): `specs/012-error-handling/contracts/error-response.md`
- Quickstart (steps 4-5): `specs/012-error-handling/quickstart.md`
- Tasks: `specs/012-error-handling/tasks.md` -- Phases 3-5
