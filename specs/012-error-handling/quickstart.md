# Quickstart: Error Handling (spec-12)

**Date**: 2026-03-17 | **Branch**: `012-error-handling`

## What This Spec Does

Spec-12 makes four targeted changes to `backend/main.py` and adds two test files. The exception hierarchy, circuit breakers, retry logic, and rate limiting are already working — this spec ensures their error responses are consistent.

## Implementation Checklist

### Step 1: Add imports to `backend/main.py`

Verify or add:
```python
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
```

The `ProviderRateLimitError` import is already present.

### Step 2: Fix the existing handler

Find (lines ~174–178) and replace the body of `rate_limit_handler`:

```python
# OLD (wrong)
content={"type": "error", "message": str(exc), "code": "rate_limit"}

# NEW (correct)
content={
    "error": {
        "code": "PROVIDER_RATE_LIMIT",
        "message": f"Rate limit exceeded for provider: {exc.provider}",
        "details": {"provider": exc.provider},
    },
    "trace_id": getattr(request.state, "trace_id", ""),
}
```

### Step 3: Add three new handlers

After the fixed `ProviderRateLimitError` handler, add:

1. `@app.exception_handler(EmbeddinatorError)` → 500, `INTERNAL_ERROR`
2. `@app.exception_handler(QdrantConnectionError)` → 503, `QDRANT_UNAVAILABLE`
3. `@app.exception_handler(OllamaConnectionError)` → 503, `OLLAMA_UNAVAILABLE`

See `Docs/PROMPTS/spec-12-errors/12-plan.md` Wave 2 for exact code.

### Step 4: Create test files

- `tests/unit/test_error_contracts.py` — static contract tests (no server needed)
- `tests/integration/test_error_handlers.py` — handler tests via `TestClient`

See `Docs/PROMPTS/spec-12-errors/12-plan.md` Wave 3 for full test code.

### Step 5: Run tests via external runner

```bash
# Unit contracts
zsh scripts/run-tests-external.sh -n spec12-unit-contracts tests/unit/test_error_contracts.py
cat Docs/Tests/spec12-unit-contracts.status  # poll until PASSED/FAILED

# Integration handlers
zsh scripts/run-tests-external.sh -n spec12-integration-handlers tests/integration/test_error_handlers.py
cat Docs/Tests/spec12-integration-handlers.status

# Full regression
zsh scripts/run-tests-external.sh -n spec12-regression tests/
cat Docs/Tests/spec12-regression.status
cat Docs/Tests/spec12-regression.summary
```

**NEVER run pytest directly inside Claude Code.**

## Do NOT

- Create any new exception classes in `backend/errors.py` (hierarchy is frozen)
- Create a `CircuitBreaker` class or `backend/circuit_breaker.py`
- Wire `retry_max_attempts` or `retry_backoff_initial_secs` to tenacity decorators
- Modify `backend/api/chat.py` (stream error codes are already correct)
- Add structured logging to error handlers (deferred to spec-15)
- Use `{"type": "error", ...}` format in REST exception handlers (that's NDJSON stream format)

## Verification

After implementation, verify:

```bash
# Manual smoke check (with server running):
curl -s http://localhost:8000/api/collections/does-not-exist | python3 -m json.tool
# Should return: {"error": {"code": "COLLECTION_NOT_FOUND", ...}, "trace_id": "..."}
```

All error responses should use the nested `{"error": {...}, "trace_id": "..."}` envelope.
