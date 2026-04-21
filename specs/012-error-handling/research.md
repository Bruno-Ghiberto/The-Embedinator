# Research: Error Handling (spec-12)

**Date**: 2026-03-17 | **Branch**: `012-error-handling`

## Overview

No significant unknowns exist at plan time. The codebase (specs 01–11) is fully implemented and the 12-specify.md context document contains accurate ground truth. This document records the four research decisions made during planning to resolve edge cases.

---

## R1: FastAPI Exception Handler Resolution Order

**Decision**: Register specific subclass handlers before the base class handler, but both will work regardless of registration order.

**Rationale**: FastAPI (via Starlette's `ExceptionMiddleware`) stores exception handlers in a dict keyed by exception type. When an exception escapes a route, the middleware iterates the exception's MRO to find a matching handler. The lookup is by type identity, not registration order. This means:

- `QdrantConnectionError` (subclass) → matched before `EmbeddinatorError` (base) automatically
- Registration order does not affect which handler fires
- Convention: register specific before generic for readability

**Alternatives considered**:
- A single `EmbeddinatorError` handler with internal `isinstance` branching → rejected (requires update for each new subclass, hides logic from FastAPI's dispatch)
- A `EXCEPTION_STATUS_MAP` dict approach (original spec-12 draft) → rejected (re-implements what FastAPI already handles; requires maintaining a separate dict)

**Verification**: Starlette source `ExceptionMiddleware.__call__` iterates `type(exc).__mro__` to find a handler.

---

## R2: Old ProviderRateLimitError Handler — Test Impact Assessment

**Decision**: Fix the handler body freely. No test files assert the old response format.

**Finding**: `grep -rn '"rate_limit"\|"type": "error"' tests/` (excluding the NDJSON stream tests) returns no hits against the `ProviderRateLimitError` handler. Existing test files that mention `rate_limit` only assert:
- `Settings.rate_limit_chat_per_minute == 30` (config default)
- `Settings.rate_limit_provider_keys_per_minute == 5` (config default)
- `RateLimitMiddleware` returns 429 with `RATE_LIMIT_EXCEEDED` (middleware, not exception handler)

None of these assert the `{"type": "error", "code": "rate_limit"}` format of the exception handler.

**Risk**: Low — the existing handler is called only when a cloud provider returns HTTP 429. In test environments, this path is rarely exercised.

---

## R3: trace_id in Exception Handlers

**Decision**: `getattr(request.state, "trace_id", "")` is the correct pattern for all handlers.

**Rationale**:
- `TraceIDMiddleware` sets `request.state.trace_id` (a UUID4 string) on every incoming request before any route runs
- Exception handlers receive the same `Request` object, so `request.state.trace_id` is always populated in production
- In integration tests using `TestClient` with a minimal app (no `TraceIDMiddleware`), `request.state.trace_id` would raise `AttributeError` without the `getattr` fallback
- Default of `""` is preferable to `None` for JSON serialization (no `null` in the response)

**Alternative**: `str(uuid.uuid4())` in each handler — rejected (generates a different UUID than the one used for the actual request trace; breaks correlation with logs)

---

## R4: debug Config Flag

**Decision**: No change to debug behavior in spec-12.

**Finding**: `Settings.debug: bool = False` exists in `backend/config.py`. No production code currently reads it in error response construction. The original spec-12 draft proposed stripping `internal` details when `debug=False`, but the actual codebase never implemented `internal` details on error responses. There is nothing to strip.

**Status**: Field reserved for spec-15 (Observability) or a future spec that adds conditional detail exposure. Must not be removed.

---

## Summary Table

| Decision | Chosen | Rejected | Impact |
|----------|--------|----------|--------|
| Handler registration order | Specific before generic (convention) | Generic before specific | None — MRO lookup is order-independent |
| Old handler test impact | Fix freely, no test updates needed | Update existing tests | Low risk — no assertions on old format |
| trace_id source | `getattr(request.state, "trace_id", "")` | `str(uuid.uuid4())` | Correct correlation with request trace |
| debug flag | No change (reserved) | Implement conditional details | Scope control — deferred to spec-15 |
