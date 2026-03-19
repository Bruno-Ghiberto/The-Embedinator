# Contract: Error Response (spec-12)

**Date**: 2026-03-17 | **Branch**: `012-error-handling`
**Stability**: Stable — all `code` values are breaking changes to rename

---

## REST Error Envelope

### Usage

Returned by all REST API routers (`/api/*`) and by the four exception handlers in `create_app()` for errors that escape routers.

### Schema

```
Content-Type: application/json

{
  "error": {
    "code":    string  // REQUIRED — stable UPPER_SNAKE_CASE identifier
    "message": string  // REQUIRED — user-facing text; no internal details
    "details": object  // OPTIONAL — structured context; empty object if unused
  }
  "trace_id": string   // REQUIRED — UUID4 from request.state.trace_id
}
```

### Constraints

- `code` MUST be `UPPER_SNAKE_CASE`. Lowercase codes are a bug.
- `message` MUST be user-facing. No exception class names, file paths, or stack traces.
- `details` MAY contain structured context (e.g., `{"provider": "openai"}`). MAY be `{}`.
- `trace_id` MUST be the UUID4 injected by `TraceIDMiddleware` for the current request.

### Examples

```json
// HTTP 429 — cloud provider rate limit
{
  "error": {
    "code": "PROVIDER_RATE_LIMIT",
    "message": "Rate limit exceeded for provider: openai",
    "details": {"provider": "openai"}
  },
  "trace_id": "a3f1b2c4-d5e6-7890-abcd-ef1234567890"
}

// HTTP 500 — unhandled EmbeddinatorError
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An internal error occurred",
    "details": {}
  },
  "trace_id": "b4c2d3e5-f6a7-8901-bcde-fa2345678901"
}

// HTTP 503 — Qdrant unreachable
{
  "error": {
    "code": "QDRANT_UNAVAILABLE",
    "message": "Vector database is temporarily unavailable",
    "details": {}
  },
  "trace_id": "c5d3e4f6-a7b8-9012-cdef-ab3456789012"
}

// HTTP 429 — middleware rate limit
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded: 30 requests per minute",
    "details": {"retry_after_seconds": 60}
  },
  "trace_id": "d6e4f5a7-b8c9-0123-defa-bc4567890123"
}
```

---

## NDJSON Stream Error Event

### Usage

Emitted as a line in the NDJSON stream from `POST /api/chat` when an error occurs after the HTTP 200 response has started. This format is **intentionally different** from the REST envelope — it uses the flat NDJSON event schema.

### Schema

```
Content-Type: application/x-ndjson (line in streaming response)

{"type": "error", "message": string, "code": string, "trace_id": string}
```

### Constraints

- `type` MUST be `"error"` (lowercase).
- `code` MUST be one of the three defined stream codes: `NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`.
- `message` MUST be user-facing.
- After emitting an error event, the stream MUST terminate (no `done` event follows).

### Examples

```json
{"type": "error", "message": "Please select at least one collection before searching.", "code": "NO_COLLECTIONS", "trace_id": "abc123"}

{"type": "error", "message": "A required service is temporarily unavailable. Please try again in a few seconds.", "code": "CIRCUIT_OPEN", "trace_id": "def456"}

{"type": "error", "message": "Unable to process your request. Please retry.", "code": "SERVICE_UNAVAILABLE", "trace_id": "ghi789"}
```

---

## Rate Limit Response Headers

When the middleware returns HTTP 429, the response MUST include:

```
Retry-After: 60
```

This header is always 60 seconds regardless of remaining window time.

---

## Frontend Consumption Rules

1. Check `response.status` for HTTP status code first — 429 means rate limited, 503 means service unavailable, 500 means internal error.
2. Parse `response.json()` to get `error.code` for programmatic error routing.
3. Display `error.message` to the user (safe, no internal details).
4. Log `trace_id` for support diagnostics.
5. For streaming: check each NDJSON line for `{"type": "error"}` and release `isStreaming` state on error, done, OR clarification events.
