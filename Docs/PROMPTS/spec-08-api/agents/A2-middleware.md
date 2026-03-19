# A2: Middleware

**Agent type:** `backend-architect`
**Model:** Sonnet 4.6
**Tasks:** T005
**Wave:** 1 (parallel with A1)

---

## Assigned Task

### T005: Extend backend/middleware.py

Update `RateLimitMiddleware` to add a 4th rate limit category (provider key management), fix the general limit, read all limits from config, and include `trace_id` in 429 response bodies.

---

## File Targets

| File | Action |
|------|--------|
| `backend/middleware.py` | Extend (modify RateLimitMiddleware) |

---

## Current State

Read `backend/middleware.py` first. The current `RateLimitMiddleware` has:
- 3 categories: upload (POST /api/documents -> 10/min), chat (POST /api/chat -> 30/min), general (100/min)
- Hardcoded limits in `_get_limit()`
- No `trace_id` in 429 response body
- Bucket keys: `upload:{ip}`, `chat:{ip}`, `general:{ip}`

## Required Changes

### 1. Add 4th Rate Limit Category

Add `provider_key` category for PUT or DELETE requests to provider key endpoints.

Match condition: method is `PUT` or `DELETE` AND path matches `/api/providers/*/key` pattern.

```python
# Check if path matches /api/providers/{name}/key
import re
_PROVIDER_KEY_PATTERN = re.compile(r"^/api/providers/[^/]+/key$")
```

### 2. Update _get_limit() Method

Read limits from the app's settings (via `backend.config.settings`), not hardcoded values:

```python
from backend.config import settings

def _get_limit(self, path: str, method: str) -> int:
    if method in ("PUT", "DELETE") and _PROVIDER_KEY_PATTERN.match(path):
        return settings.rate_limit_provider_keys_per_minute  # 5
    if method == "POST" and path == "/api/chat":
        return settings.rate_limit_chat_per_minute  # 30
    if method == "POST" and "/ingest" in path:
        return settings.rate_limit_ingest_per_minute  # 10
    return settings.rate_limit_general_per_minute  # 120
```

### 3. Update _get_bucket() Method

```python
def _get_bucket(self, path: str, method: str, client_ip: str) -> str:
    if method in ("PUT", "DELETE") and _PROVIDER_KEY_PATTERN.match(path):
        return f"provider_key:{client_ip}"
    if method == "POST" and path == "/api/chat":
        return f"chat:{client_ip}"
    if method == "POST" and "/ingest" in path:
        return f"ingest:{client_ip}"
    return f"general:{client_ip}"
```

### 4. Add trace_id to 429 Response Body

The `TraceIDMiddleware` runs before `RateLimitMiddleware` (middleware order in main.py: RateLimit is outermost, then RequestLogging, then TraceID -- but Starlette processes them inside-out, so TraceID runs first on request). Use `getattr(request.state, "trace_id", "unknown")` to safely access it:

```python
trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
return JSONResponse(
    status_code=429,
    content={
        "error": {
            "code": "RATE_LIMIT_EXCEEDED",
            "message": f"Rate limit exceeded: {limit} requests per minute",
            "details": {"retry_after_seconds": 60},
        },
        "trace_id": trace_id,
    },
    headers={"Retry-After": "60"},
)
```

### 5. Fix Ingest Path Detection

Current code checks `path.startswith("/api/documents")` which is wrong. The ingest endpoint is `POST /api/collections/{id}/ingest`. Update to check for `/ingest` in the path:

```python
if method == "POST" and "/ingest" in path:
```

### Summary of Rate Limit Categories

| Category | Limit | Match | Bucket |
|----------|-------|-------|--------|
| Provider key | 5/min | PUT or DELETE `/api/providers/*/key` | `provider_key:{ip}` |
| Chat | 30/min | POST `/api/chat` | `chat:{ip}` |
| Ingestion | 10/min | POST `*/ingest` | `ingest:{ip}` |
| General | 120/min | everything else | `general:{ip}` |

---

## Key Constraints

- The `_PROVIDER_KEY_PATTERN` regex must match paths like `/api/providers/openai/key` and `/api/providers/anthropic/key`
- Provider key check MUST come before the general fallback in both `_get_limit()` and `_get_bucket()`
- Do NOT change `TraceIDMiddleware` or `RequestLoggingMiddleware` -- they are correct
- Import `settings` from `backend.config` at module level (it is already a singleton)
- Keep the existing sliding window implementation -- only change limit values and category detection
- The `uuid` import is already available in the file

---

## Dependencies

- **Depends on T004** (A1 adds `rate_limit_provider_keys_per_minute` and `rate_limit_general_per_minute` to config.py)
- If A1 has not finished yet, you can still implement with hardcoded values and a TODO comment, but the final version MUST read from settings

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-middleware tests/unit/test_middleware_rate_limit.py
cat Docs/Tests/spec08-middleware.status
cat Docs/Tests/spec08-middleware.summary
```

If `test_middleware_rate_limit.py` does not exist, create it with tests verifying:
- POST /api/chat -> chat bucket, limit 30
- POST /api/collections/xxx/ingest -> ingest bucket, limit 10
- PUT /api/providers/openai/key -> provider_key bucket, limit 5
- DELETE /api/providers/openai/key -> provider_key bucket, limit 5
- GET /api/collections -> general bucket, limit 120
- 429 response body contains `trace_id` and `error.code` = "RATE_LIMIT_EXCEEDED"
- `Retry-After` header is present on 429 responses

---

## What NOT to Do

- Do NOT change TraceIDMiddleware or RequestLoggingMiddleware
- Do NOT add any new middleware classes
- Do NOT change the middleware registration order in main.py (that is A7's task)
- Do NOT use `request.app.state.settings` -- use `from backend.config import settings` (it is a module-level singleton)
- Do NOT run pytest inside Claude Code -- use the external test runner
