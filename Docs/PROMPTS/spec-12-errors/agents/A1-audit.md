# A1: Pre-Implementation Audit -- Spec 12 Error Handling

**Wave**: 1 of 4 | **Branch**: `012-error-handling`

---

## This Is Your Briefing File

Your orchestrator spawned you with the prompt:
> "Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/A1-audit.md FIRST, then await further instructions."

After you finish reading this file in full, signal readiness to the orchestrator by posting:

```
A1 ready -- briefing complete
```

The orchestrator will then send you specific task assignments via `SendMessage`. Execute each task as it arrives, using the MCP tools and task details in this file as your reference.

---

## Agent Configuration

| Field | Value |
|-------|-------|
| **subagent_type** | `quality-engineer` |
| **model** | `claude-opus-4-6` |
| **rationale** | Needs deep codebase understanding to audit 8 files accurately and identify discrepancies with plan assumptions |

---

## MCP Tools Available

Use these tools to verify codebase facts. Do not guess — look up the actual code.

| Tool | When to use |
|------|-------------|
| `mcp__serena__find_symbol` | Look up specific classes (EmbeddinatorError, ProviderRateLimitError, ErrorDetail, Settings) |
| `mcp__serena__get_symbols_overview` | Get all classes/functions in a file at a glance |
| `mcp__gitnexus__context` | Get 360-degree view of a symbol (callers, callees, file location) |
| `mcp__gitnexus__impact` | Check blast radius before flagging risky discrepancies |
| `mcp__gitnexus__query` | Find execution flows related to error handling or rate limiting |

If any MCP tool call fails, fall back to reading the file directly with the Read tool.

---

## Mission

Verify every assumption in `specs/012-error-handling/plan.md` against the live codebase before any code is changed. Your output is a gate report. If any critical discrepancy exists between the plan and the codebase, STOP and document it. Wave 2 (A2) cannot start until your report is written and contains no critical discrepancies.

**NEVER modify any production file. Read only.**

---

## Critical Rules

- **NEVER run pytest or any test commands inside Claude Code.** Testing is done via the external runner only (Wave 4).
- **NEVER modify `backend/errors.py`** -- the exception hierarchy is frozen.
- **NEVER create `CircuitBreaker` class or `backend/circuit_breaker.py`** -- already implemented in qdrant_client.py and nodes.py.
- **NEVER wire `retry_max_attempts` or `retry_backoff_initial_secs` to tenacity** -- these are dead config fields reserved for a future spec.
- If a serena/gitnexus tool call fails, fall back to reading the file directly with the Read tool.

---

## What You Are Checking

Spec-12 makes exactly 4 changes to `backend/main.py`:

1. **Fix** the existing `ProviderRateLimitError` handler -- it currently returns `{"type": "error", "code": "rate_limit"}` (wrong format, lowercase code, missing trace_id)
2. **Add** global `EmbeddinatorError` handler → HTTP 500, code `INTERNAL_ERROR`
3. **Add** `QdrantConnectionError` handler → HTTP 503, code `QDRANT_UNAVAILABLE`
4. **Add** `OllamaConnectionError` handler → HTTP 503, code `OLLAMA_UNAVAILABLE`

No other production files are touched. 2 new test files are created later (Wave 3).

---

## Tasks (T001-T009)

Run T001-T008 in parallel -- each reads a different file.

### T001: Verify exception hierarchy in `backend/errors.py`

Use `mcp__serena__get_symbols_overview` on `backend/errors.py` with `depth=1` to list all classes. Confirm exactly these 10 subclasses exist and all extend `EmbeddinatorError` directly (no intermediate base classes):

```
QdrantConnectionError
OllamaConnectionError
SQLiteError
LLMCallError
EmbeddingError
IngestionError
SessionLoadError
StructuredOutputParseError
RerankerError
CircuitOpenError
```

Then use `mcp__serena__find_symbol` with `name_path_pattern="EmbeddinatorError"` and `depth=0` to confirm the base class has no `__init__` override.

**Discrepancy**: If any of the 18 classes from the OLD `12-implement.md` are present (e.g., `StorageError`, `AgentError`, `ProviderError`, `RustWorkerError`, `EmbeddingValidationError`, `DatabaseMigrationError`, etc.) that is a **CRITICAL DISCREPANCY** -- stop immediately.

### T002: Verify `ProviderRateLimitError` in `backend/providers/base.py`

Use `mcp__serena__find_symbol` with `name_path_pattern="ProviderRateLimitError"` and `relative_path="backend/providers/base.py"`, `depth=1`. Verify:
- `ProviderRateLimitError` extends `Exception` directly (NOT `EmbeddinatorError`)
- Constructor: `__init__(self, provider: str)`
- Has `self.provider` attribute
- `str(exc)` returns `f"Rate limit exceeded for provider: {provider}"` (or equivalent)

Record the exact class definition in your audit.

### T003: Verify Pydantic models in `backend/agent/schemas.py`

Use serena to find `ErrorDetail` and `ErrorResponse` in `backend/agent/schemas.py`. Verify:
- `ErrorDetail` has fields: `code: str`, `message: str`, `details: dict = {}`
- `ErrorResponse` has field: `error: ErrorDetail`
- `ErrorResponse` has **NO** `trace_id` field (trace_id is added as a plain dict key in handlers, NOT as a Pydantic field)

**Discrepancy**: If `ErrorResponse` has a `trace_id` field → MINOR discrepancy, note it. The handler pattern `{"error": {...}, "trace_id": trace_id}` uses a plain dict, not the Pydantic model.

### T004: Verify config fields in `backend/config.py`

Use serena to find the `Settings` class in `backend/config.py`. Verify all 8 required fields exist with their defaults:

```python
circuit_breaker_failure_threshold: int = 5
circuit_breaker_cooldown_secs: int = 30
retry_max_attempts: int = 3           # dead config -- DO NOT wire to tenacity
retry_backoff_initial_secs: float = 1.0  # dead config -- DO NOT wire to tenacity
rate_limit_chat_per_minute: int = 30
rate_limit_ingest_per_minute: int = 10
rate_limit_provider_keys_per_minute: int = 5
rate_limit_general_per_minute: int = 120
```

Record exact field names and defaults found.

### T005: Verify current state of `backend/main.py` exception handlers

Read `backend/main.py`. Find `create_app()` (starts at line 149) and locate all `@app.exception_handler(...)` decorators. Confirm:

a. The existing `ProviderRateLimitError` handler exists at approximately lines 173-179 and currently returns the OLD wrong format (something like `{"type": "error", "message": ..., "code": "rate_limit"}`). Record the exact current body.

b. There is **NO** `EmbeddinatorError` exception handler (this is the missing handler we need to add).

c. There is **NO** `QdrantConnectionError` exception handler (missing -- need to add).

d. There is **NO** `OllamaConnectionError` exception handler (missing -- need to add).

Record exact line numbers for where `create_app()` starts, where the existing `ProviderRateLimitError` handler is, and where new handlers should be inserted (before the `app.include_router(...)` calls).

### T006: Verify `RateLimitMiddleware` in `backend/middleware.py`

Read `backend/middleware.py`. Find `RateLimitMiddleware.dispatch()`. Verify:
- Returns `JSONResponse(status_code=429, ...)`
- Response body uses nested envelope: `{"error": {"code": "RATE_LIMIT_EXCEEDED", ...}, "trace_id": ...}`
- Response includes `Retry-After: 60` header

This handler is ALREADY CORRECT and should NOT be modified.

### T007: Verify stream error codes in `backend/api/chat.py`

Read `backend/api/chat.py`. Find all places where error events are emitted in the NDJSON stream. Verify exactly three stream error codes are used: `NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`. The stream format is:

```json
{"type": "error", "message": "...", "code": "...", "trace_id": "..."}
```

This is intentionally different from the REST envelope. Do NOT change this file.

### T008: Verify tenacity retry pattern in `backend/storage/qdrant_client.py`

Read `backend/storage/qdrant_client.py`. Find the `@retry(...)` decorator(s). Verify the pattern uses:
- `stop_after_attempt(3)` (hardcoded, not reading from config)
- `wait_exponential(multiplier=1, min=1, max=10)` + `wait_random(0, 1)` (jitter, random exceptions)
- `reraise=True`

Confirm `retry_max_attempts` and `retry_backoff_initial_secs` from Settings are NOT being read here. These are dead config -- intentionally not wired.

### T009: Write audit report

Write a gate report to `Docs/Tests/spec12-a1-audit.md` using the following structure:

```markdown
# Spec 12 -- Pre-Implementation Audit Report
**Date**: 2026-03-17  |  **Agent**: A1  |  **Branch**: 012-error-handling

## T001 -- Exception Hierarchy
[findings]

## T002 -- ProviderRateLimitError
[exact class definition found]

## T003 -- Pydantic Models
[ErrorDetail fields, ErrorResponse fields, trace_id note]

## T004 -- Config Fields
[exact field names and defaults found]

## T005 -- main.py Handler State
[current handlers found, line numbers, exact body of existing ProviderRateLimitError handler]

## T006 -- RateLimitMiddleware
[status: ALREADY CORRECT / discrepancy]

## T007 -- Stream Error Codes
[codes found in chat.py]

## T008 -- Tenacity Retry Pattern
[pattern found, confirm retry_max_attempts not used]

## Summary
- Critical discrepancies: [list or NONE]
- Minor discrepancies: [list or NONE]
- Gate status: PASS / FAIL

## A2 instructions
[Any notes for A2 about exact line numbers, import locations, or other findings that differ from plan.md]
```

**If gate status is FAIL** (critical discrepancy found): Stop. Do not proceed. The user must resolve the discrepancy before Wave 2.

**If gate status is PASS**: Write the report and stop. The orchestrator will then send instructions to start Wave 2 (A2).

---

## Files to Read (by task)

| Task | File |
|------|------|
| T001 | `backend/errors.py` |
| T002 | `backend/providers/base.py` |
| T003 | `backend/agent/schemas.py` |
| T004 | `backend/config.py` |
| T005 | `backend/main.py` |
| T006 | `backend/middleware.py` |
| T007 | `backend/api/chat.py` |
| T008 | `backend/storage/qdrant_client.py` |
| T009 | Write to `Docs/Tests/spec12-a1-audit.md` |

---

## Reference Documents

- Authoritative spec: `specs/012-error-handling/spec.md`
- Implementation plan: `specs/012-error-handling/plan.md`
- Data model + error codes: `specs/012-error-handling/data-model.md`
- Contract: `specs/012-error-handling/contracts/error-response.md`
- Quickstart (step-by-step): `specs/012-error-handling/quickstart.md`
- Tasks: `specs/012-error-handling/tasks.md`
