# Implementation Plan: Error Handling

**Branch**: `012-error-handling` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/012-error-handling/spec.md`
**Context**: Implementation plan context at `Docs/PROMPTS/spec-12-errors/12-plan.md`

## Summary

Spec-12 is a hardening spec. The exception hierarchy, circuit breakers, retry logic, and rate limiting are already implemented and working across specs 02–11. The three concrete production changes are all in `backend/main.py`:

1. Fix the existing `ProviderRateLimitError` handler — change from flat NDJSON-style format (`{"type": "error", "code": "rate_limit"}`) to the standard nested REST envelope with uppercase `PROVIDER_RATE_LIMIT` code and `trace_id`.
2. Add a global `EmbeddinatorError` catch-all handler → HTTP 500, `INTERNAL_ERROR`.
3. Add a specific `QdrantConnectionError` handler → HTTP 503, `QDRANT_UNAVAILABLE`.
4. Add a specific `OllamaConnectionError` handler → HTTP 503, `OLLAMA_UNAVAILABLE`.

In addition, spec-12 adds two new test files: `tests/unit/test_error_contracts.py` (contract tests for the error hierarchy, Pydantic models, and config fields) and `tests/integration/test_error_handlers.py` (integration tests verifying the four exception handlers return correct HTTP status codes and response bodies).

**Scope**: 1 production file modified, 2 test files created, ~35–50 new tests.

---

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: FastAPI >= 0.135, Pydantic v2 >= 2.12, pytest (testing only)
**Storage**: N/A — no database schema changes
**Testing**: pytest via `zsh scripts/run-tests-external.sh` (NEVER inside Claude Code)
**Target Platform**: Linux server (Docker container, Python service)
**Project Type**: Web service — backend hardening
**Performance Goals**: Rate limit decisions under 5 ms; exception handler overhead < 1 ms per request
**Constraints**: Zero new production dependencies; only `backend/main.py` modified in production code
**Scale/Scope**: Minimal — 4 exception handler changes, 2 new test files

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Assessment |
|-----------|--------|------------|
| I. Local-First Privacy | ✅ PASS | Spec-12 adds only exception handlers. No outbound network calls, no auth, no cloud dependencies introduced. |
| II. Three-Layer Agent Architecture | ✅ PASS | No changes to ConversationGraph, ResearchGraph, or MetaReasoningGraph. |
| III. Retrieval Pipeline Integrity | ✅ PASS | No retrieval pipeline modifications. |
| IV. Observability from Day One | ✅ PASS | All new exception handlers include `trace_id` in the response from `request.state.trace_id`. Trace ID is preserved across the error boundary. Structured log schemas deferred to spec-15 (explicitly out of scope per clarification Q4). |
| V. Secure by Design | ✅ PASS | Spec-12 hardens security: no stack traces or class names leak in error responses (FR-013). `ProviderRateLimitError` handler fixed to use standard envelope. Global handler catches `EmbeddinatorError` subtypes that would otherwise return FastAPI's default `{"detail": "Internal Server Error"}` with no trace_id. Rate limiting already enforced by middleware — spec-12 adds contract tests for config fields. |
| VI. NDJSON Streaming Contract | ✅ PASS | NDJSON stream error format (`{"type": "error", "message": ..., "code": ...}`) is explicitly preserved unchanged. REST error handlers use the nested envelope — a different (correct) format for a different context. No changes to `backend/api/chat.py`. |
| VII. Simplicity by Default | ✅ PASS | Minimal change: 4 handler additions/fixes in one file. No new abstractions, no new files in production code, no new dependencies. YAGNI applied — no `CircuitBreaker` class extracted, retry config fields left as dead config. |

**Constitution gate: PASS. No violations. Proceed to Phase 0.**

---

## Project Structure

### Documentation (this feature)

```text
specs/012-error-handling/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/
│   └── error-response.md    # Phase 1 output — REST and NDJSON error schemas
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
  main.py                          # MODIFY: fix + add 4 exception handlers in create_app()

tests/
  unit/
    test_error_contracts.py        # CREATE: contract tests (hierarchy, models, config fields)
  integration/
    test_error_handlers.py         # CREATE: handler integration tests (HTTP status + body)

Docs/PROMPTS/spec-12-errors/
  agents/
    A1-audit.md                    # CREATE: Wave 1 agent instructions
    A2-main-handlers.md            # CREATE: Wave 2 agent instructions
    A3-tests.md                    # CREATE: Wave 3 agent instructions
    A4-regression.md               # CREATE: Wave 4 agent instructions
```

**No other source files are created or modified.**

---

## Phase 0: Research

*See [research.md](research.md) for full findings. Summary below.*

### R1: FastAPI Exception Handler Resolution Order

**Decision**: Register all handlers (specific and base class) in `create_app()`. Registration order does not affect resolution — FastAPI/Starlette checks exact type match first, then walks MRO. Both approaches work; order chosen for readability (specific before generic).

**Rationale**: Starlette's `ExceptionMiddleware` uses a dict keyed by exception type. On each exception, it iterates MRO to find a registered handler. Registering `QdrantConnectionError` before `EmbeddinatorError` has no functional difference, but clarifies intent to readers.

**Alternatives**: A single handler for `EmbeddinatorError` with `isinstance` checks inside was rejected — it would require updating the handler for every new subclass and adds conditional logic where FastAPI's dispatch mechanism handles it naturally.

### R2: Old `ProviderRateLimitError` Handler — No Existing Test Assertions

**Decision**: Fix the handler freely. No test updates required from the old format.

**Rationale**: `grep` across all test files confirms no test asserts `{"type": "error", ..., "code": "rate_limit"}`. Existing tests for rate limiting only check `Settings` config field defaults and `RateLimitMiddleware` behavior — neither touches the `ProviderRateLimitError` exception handler.

**Risk**: Low. Only `backend/main.py` lines 174–178 need to change.

### R3: `trace_id` Availability in Exception Handlers

**Decision**: Use `getattr(request.state, "trace_id", "")` in all four handlers.

**Rationale**: `TraceIDMiddleware` runs before routes and sets `request.state.trace_id`. Exception handlers receive the same `request` object, so the trace_id is always available on production requests. The `getattr` fallback to `""` handles the edge case of test clients that mount the app without `TraceIDMiddleware`.

### R4: `debug` Config Flag — No Change

**Decision**: The `Settings.debug` field has no effect on error responses in spec-12. It remains as reserved infrastructure for future conditional detail exposure (spec-15 or later).

**Rationale**: Spec clarification Q4 — structured logging and debug detail exposure are explicitly out of scope for spec-12.

---

## Phase 1: Design

### Data Model

*See [data-model.md](data-model.md) for full details.*

Spec-12 introduces no new database tables or persistent data. The relevant "data model" is the in-memory state and JSON schemas:

- **Error Category** (code artifact): flat hierarchy of 11 `EmbeddinatorError` subclasses + `ProviderRateLimitError` (separate base)
- **REST Error Envelope** (JSON schema): `{error: {code, message, details}, trace_id}`
- **NDJSON Stream Error Event** (JSON line): `{type: "error", message, code, trace_id}`
- **Circuit Breaker State** (in-memory per instance): `{_circuit_open, _failure_count, _last_failure_time}`
- **Rate Limit Bucket** (in-memory per IP): sliding window counter keyed by `"{bucket_type}:{client_ip}"`

### Interface Contracts

*See [contracts/error-response.md](contracts/error-response.md) for full JSON schema.*

Two stable contracts exposed to external callers:

1. **REST Error Envelope** — returned by all REST routers and the four exception handlers
2. **NDJSON Stream Error Event** — returned by `POST /api/chat` on stream-level failures

Both are stable public contracts — renaming a `code` value is a breaking change.

### Quickstart

*See [quickstart.md](quickstart.md).*

---

## Implementation Design

### Handler Registration Pattern

All four handlers follow the same pattern. Handlers are added inside `create_app()` in `backend/main.py`:

```python
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
from backend.providers.base import ProviderRateLimitError  # already imported

@app.exception_handler(ProviderRateLimitError)   # FIX: replace body of existing handler
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

@app.exception_handler(EmbeddinatorError)         # NEW: global catch-all
async def embedinator_error_handler(request: Request, exc: EmbeddinatorError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=500,
        content={
            "error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred", "details": {}},
            "trace_id": trace_id,
        },
    )

@app.exception_handler(QdrantConnectionError)     # NEW: 503 for Qdrant
async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {"code": "QDRANT_UNAVAILABLE", "message": "Vector database is temporarily unavailable", "details": {}},
            "trace_id": trace_id,
        },
    )

@app.exception_handler(OllamaConnectionError)     # NEW: 503 for Ollama
async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {"code": "OLLAMA_UNAVAILABLE", "message": "Inference service is temporarily unavailable", "details": {}},
            "trace_id": trace_id,
        },
    )
```

### Agent Teams Orchestration

Spec-12 uses 4 waves (A1→A2→A3→A4). Full agent instruction files live in `Docs/PROMPTS/spec-12-errors/agents/`.

| Wave | Agent | Type | Model | Primary Output |
|------|-------|------|-------|----------------|
| 1 | A1 | quality-engineer | Opus | Audit report — confirms codebase matches plan assumptions |
| 2 | A2 | python-expert | Sonnet | `backend/main.py` with 4 handler changes |
| 3 | A3 | python-expert | Sonnet | `test_error_contracts.py` + `test_error_handlers.py` |
| 4 | A4 | quality-engineer | Sonnet | Full regression gate, final test count report |

---

## Complexity Tracking

| Decision | Complexity Added | Justification |
|----------|-----------------|---------------|
| 3 new exception handlers | Minimal — 4 handler functions in `main.py` | Required by FR-007, FR-008, and clarification Q1 |
| Fix `ProviderRateLimitError` handler | Near-zero — body replacement only | Existing handler has 3 known bugs (format, code case, missing trace_id) |
| No `CircuitBreaker` class extraction | Zero (defer) | Constitution §VII YAGNI — existing globals work; refactoring adds risk with no user-facing value in spec-12 scope |
| Retry config not wired to tenacity | Zero (status quo preserved) | Clarification Q2 — dead config reserved for future spec |

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** Use the external runner exclusively.

```bash
# Agent test gates:
zsh scripts/run-tests-external.sh -n spec12-unit-contracts tests/unit/test_error_contracts.py
zsh scripts/run-tests-external.sh -n spec12-integration-handlers tests/integration/test_error_handlers.py
zsh scripts/run-tests-external.sh -n spec12-a3 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py
zsh scripts/run-tests-external.sh -n spec12-regression tests/

# Poll:   cat Docs/Tests/<name>.status
# Read:   cat Docs/Tests/<name>.summary
```

**Expected final counts**: 1250 existing + ~35–50 new spec-12 tests passing. 39 pre-existing failures unchanged. 0 regressions.
