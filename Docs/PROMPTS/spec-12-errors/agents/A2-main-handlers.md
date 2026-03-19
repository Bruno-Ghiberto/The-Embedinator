# A2: backend/main.py Handler Changes -- Spec 12 Error Handling

**Wave**: 2 of 4 | **Branch**: `012-error-handling`

---

## This Is Your Briefing File

Your orchestrator spawned you with the prompt:
> "Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/A2-main-handlers.md FIRST, then await further instructions."

After you finish reading this file in full, signal readiness to the orchestrator by posting:

```
A2 ready -- briefing complete
```

The orchestrator will then send you specific task assignments via `SendMessage`. Execute each task as it arrives, using the MCP tools and task details in this file as your reference.

---

## Agent Configuration

| Field | Value |
|-------|-------|
| **subagent_type** | `python-expert` |
| **model** | `claude-sonnet-4-6` |
| **rationale** | Focused Python editing task -- replacing/adding 4 handler functions in a single file; Sonnet is sufficient |

---

## MCP Tools Available

Use these tools before and after editing to verify your changes.

| Tool | When to use |
|------|-------------|
| `mcp__serena__find_symbol` | Verify `create_app` function boundaries and `rate_limit_handler` location before editing |
| `mcp__serena__get_symbols_overview` | Confirm all symbols in `backend/main.py` before and after edits |
| `mcp__gitnexus__context` | Use `context({name: "create_app"})` to confirm callers and verify no signature change is needed |
| `mcp__gitnexus__impact` | Run `impact({target: "create_app", direction: "upstream", repo: "The-Embedinator"})` before editing |

---

## Prerequisite

**Read `Docs/Tests/spec12-a1-audit.md` first.** This is A1's gate report. If it says "Gate status: FAIL", stop immediately and notify the orchestrator. If PASS, proceed with the tasks below. The audit report also contains exact line numbers and the current body of the `ProviderRateLimitError` handler -- use that information instead of guessing line numbers.

---

## Mission

Make exactly 4 changes to `backend/main.py` within `create_app()`:

1. **Fix** the body of the existing `ProviderRateLimitError` handler
2. **Add** a new `QdrantConnectionError` handler → HTTP 503
3. **Add** a new `OllamaConnectionError` handler → HTTP 503
4. **Add** a new global `EmbeddinatorError` handler → HTTP 500

Then run a smoke test via the external runner to confirm no pre-existing tests break.

---

## Critical Rules

- **NEVER run pytest inside Claude Code.** Use `zsh scripts/run-tests-external.sh` only.
- **NEVER modify `backend/errors.py`** -- hierarchy is frozen.
- **NEVER create `CircuitBreaker` class or `backend/circuit_breaker.py`**.
- **NEVER modify `backend/api/chat.py`** -- stream error codes are already correct.
- **NEVER add `"type": "error"` format** to REST exception handlers -- that's the NDJSON stream format.
- **NEVER modify `backend/middleware.py`** -- `RateLimitMiddleware` is already correct.
- Before editing `backend/main.py`, run `mcp__gitnexus__impact({target: "create_app", direction: "upstream", repo: "The-Embedinator"})` and confirm impact level. Proceed only if impact is LOW or MEDIUM.
- Only modify `backend/main.py`. No other production files.

---

## Impact Analysis (Run Before Editing)

Run this before making any edits:

```
mcp__gitnexus__impact({target: "create_app", direction: "upstream", repo: "The-Embedinator"})
```

**Known result** (pre-verified): `create_app` is called by 5 test fixtures/functions and by `backend/main.py` at module level (`app = create_app()`). Adding handlers inside the function body does NOT change its signature or return type. Expected risk level: **LOW**.

If the tool returns HIGH or CRITICAL, stop and consult the orchestrator.

---

## Tasks (T010-T018)

### T010: Read `backend/main.py` in full

Read the entire file. Understand:
- Current import block -- where is `ProviderRateLimitError` imported? (it should already be imported from `backend.providers.base`)
- Where is `create_app()` defined? (line 149)
- What are the exact line numbers of the existing `ProviderRateLimitError` handler? (cross-check with A1 audit report -- approximately lines 173-179)
- What imports from `backend.errors` are currently present? (likely none -- this is what T011 adds)
- What is the exact current body of the `ProviderRateLimitError` handler? (the wrong format to be replaced)

### T011: Add missing imports

If `from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError` is not already present, add it after the existing `from backend.providers.base import ProviderRateLimitError` import line.

Use the Edit tool with a precise old_string/new_string that includes enough surrounding context to be unambiguous.

Do NOT add `ProviderRateLimitError` to this import -- it's already imported from `backend.providers.base`.

### T012: Fix the `ProviderRateLimitError` handler

Replace the BODY of the existing `rate_limit_handler` (keep the decorator and function signature, replace only the body).

**Current (wrong) body** -- confirmed by A1 audit:
```python
return JSONResponse(
    status_code=429,
    content={"type": "error", "message": str(exc), "code": "rate_limit"},
)
```

**New (correct) body**:
```python
async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
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

Use the exact current body from the A1 audit report as the `old_string` in your Edit call. Keep the `@app.exception_handler(ProviderRateLimitError)` decorator as-is.

### T013: Add `EmbeddinatorError` handler (global catch-all)

After the fixed `ProviderRateLimitError` handler, add:

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

### T014: Add `QdrantConnectionError` handler

After the `EmbeddinatorError` handler, add:

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

**Note**: Registration order does NOT affect resolution (FastAPI uses MRO lookup). Specific handlers before the base class handler is convention only.

### T015: Add `OllamaConnectionError` handler

After the `QdrantConnectionError` handler, add:

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

### T016: Verify handler registration order

After all edits, read `backend/main.py` again and confirm the handlers appear in this order within `create_app()`:

1. `@app.exception_handler(ProviderRateLimitError)` -- fixed body
2. `@app.exception_handler(EmbeddinatorError)` -- new, HTTP 500
3. `@app.exception_handler(QdrantConnectionError)` -- new, HTTP 503
4. `@app.exception_handler(OllamaConnectionError)` -- new, HTTP 503

All 4 handlers must use `getattr(request.state, "trace_id", "")` and return `JSONResponse` with the nested `{"error": {...}, "trace_id": trace_id}` envelope.

### T017: Run smoke test via external runner

```bash
zsh scripts/run-tests-external.sh -n spec12-a2-smoke tests/unit/test_schemas_api.py tests/unit/test_middleware_rate_limit.py
```

Poll until complete:
```bash
cat Docs/Tests/spec12-a2-smoke.status
```

If PASSED: proceed to T018.
If FAILED: read `Docs/Tests/spec12-a2-smoke.summary` and `Docs/Tests/spec12-a2-smoke.log`. Fix the issue in `backend/main.py` (and ONLY `backend/main.py`). Re-run.

**Note**: The smoke test targets `test_schemas_api.py` and `test_middleware_rate_limit.py`. If those files don't exist, try `tests/unit/` as the target. Do NOT run the full suite here -- that's A4's job.

### T018: Confirm no regressions from handler changes

Read `Docs/Tests/spec12-a2-smoke.summary`. Confirm all tests that were passing before still pass. If any failures are related to the handler changes, investigate and fix in `backend/main.py`.

**Gate**: Notify the orchestrator that Wave 2 is complete. A3 may only proceed after T018 confirms PASSED.

---

## Handler Pattern Reference

All four handlers follow this exact structure:

```python
@app.exception_handler(SomeError)
async def some_error_handler(request: Request, exc: SomeError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=XXX,
        content={
            "error": {
                "code": "UPPER_SNAKE_CASE_CODE",
                "message": "User-facing message. No class names or stack traces.",
                "details": {},  # or {"key": "value"} for extra context
            },
            "trace_id": trace_id,
        },
    )
```

**Key invariants**:
- `code` MUST be `UPPER_SNAKE_CASE`
- `message` MUST NOT expose exception class names, file paths, or internal details
- `details` MUST be a dict (empty `{}` is fine)
- `trace_id` MUST use `getattr(request.state, "trace_id", "")` -- never generate a new UUID
- `JSONResponse` not `Response` (auto-serializes dict to JSON)

---

## Error Code Reference (spec-12 handlers only)

| Handler | HTTP | Code |
|---------|------|------|
| `ProviderRateLimitError` | 429 | `PROVIDER_RATE_LIMIT` |
| `EmbeddinatorError` | 500 | `INTERNAL_ERROR` |
| `QdrantConnectionError` | 503 | `QDRANT_UNAVAILABLE` |
| `OllamaConnectionError` | 503 | `OLLAMA_UNAVAILABLE` |

---

## Reference Documents

- A1 audit report (REQUIRED): `Docs/Tests/spec12-a1-audit.md`
- Plan (handlers section): `specs/012-error-handling/plan.md` -- "Implementation Design"
- Quickstart (steps 1-4): `specs/012-error-handling/quickstart.md`
- Tasks: `specs/012-error-handling/tasks.md` -- Phase 2
- Contract: `specs/012-error-handling/contracts/error-response.md`
