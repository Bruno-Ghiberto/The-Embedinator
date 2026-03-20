# A3 — Backend Architect: Health Enhancement

## Role & Mission

You are the backend architect responsible for adding liveness/readiness health separation, model availability reporting, health log suppression, upload directory creation, and write-access testing in the backend.

## FR Ownership

FR-032, FR-033, FR-034, FR-035, FR-036, FR-037, FR-044, FR-045

## Task Ownership

T027 through T035 (Phase 4: Backend Health Enhancement)

### Tasks

- **T027** [P]: Modify `backend/agent/schemas.py`: extend `HealthResponse.status` to `Literal["healthy", "degraded", "starting"]`. Add optional `models: dict[str, bool] | None = None` field to `HealthServiceStatus` for Ollama model reporting (FR-034, FR-035)
- **T028**: Modify `backend/api/health.py`: add `GET /api/health/live` endpoint returning `{"status": "alive"}` unconditionally with HTTP 200 — no dependency probes (FR-032)
- **T029**: Modify `backend/api/health.py`: enhance `_probe_ollama()` to parse the `/api/tags` response body, check whether `settings.default_llm_model` and `settings.default_embed_model` are present in the model list, and include a `models` dict in the Ollama service status (FR-034)
- **T030**: Modify `backend/api/health.py`: add `"starting"` status logic — return `starting` when it's the first probe after backend startup (before any dependency has been checked) (FR-035)
- **T031** [P]: Modify `backend/middleware.py`: add path exclusion set `{"/api/health", "/api/health/live"}` at the top of `RequestLoggingMiddleware.dispatch()` — skip logging for these paths (FR-036)
- **T032**: Modify `backend/main.py`: add `Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)` in `lifespan()` startup, before the SQLite init (FR-044). **IMPORTANT**: You ONLY modify the startup section of `lifespan()` (before `yield`). A6 will modify the shutdown section (after `yield`) in Wave 2.
- **T033**: Modify `backend/main.py`: add write-access test after upload dir creation — create and remove a temp file in the data dir, exit with `SystemExit(1)` and a clear log message if `PermissionError` (FR-045)
- **T034**: Document FR-037 (circuit breaker bypass): verify that health probes in `health.py` use direct `httpx` calls and do NOT go through `HybridSearcher` circuit breaker. Add a code comment in `health.py` noting this design choice (FR-037)
- **T035**: Verify: `python -c "from backend.api.health import router"` succeeds. Verify health module has both `/api/health` and `/api/health/live` endpoints registered.

## Files to CREATE

None — all modifications to existing files.

## Files to MODIFY

| File | Changes |
|------|---------|
| `backend/agent/schemas.py` | Extend `HealthResponse.status` to include `"starting"`. Add `models` field to `HealthServiceStatus`. |
| `backend/api/health.py` | Add `/api/health/live` liveness endpoint. Enhance Ollama probe with model availability. Add `"starting"` status logic. Add circuit breaker bypass comment. |
| `backend/middleware.py` | Add health path exclusion set to suppress health request logs. |
| `backend/main.py` | Add upload dir creation and write-access test in `lifespan()` startup (before `yield` ONLY). |

## Files NEVER to Touch

- `Makefile` — SC-010
- `backend/config.py` — no Settings changes
- `requirements.txt` — no new Python packages
- Any `tests/**` files
- Any file owned by A1 or A2 (see 19-implement.md file touch matrix)
- `backend/api/chat.py` — owned by A6 in Wave 2
- `.env.example` — owned by A6 in Wave 2

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Section 6 (Backend Resilience)
3. `specs/019-cross-platform-dx/spec.md` — FR-032 through FR-037, FR-044, FR-045
4. `specs/019-cross-platform-dx/tasks.md` — T027 through T035
5. `specs/019-cross-platform-dx/data-model.md` — Section 3 (Backend Health State)
6. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — stale patterns, risk gotchas

## Key Gotchas

1. **`backend/main.py` multi-touch** — You ONLY modify the startup section of `lifespan()` (before `yield`). A6 modifies the shutdown section (after `yield`) in Wave 2. Do NOT touch anything after the `yield` statement.
2. **Health probes bypass circuit breaker** — Health probes in `health.py` use direct `httpx.AsyncClient` calls. They do NOT go through `HybridSearcher` circuit breaker. This is intentional — add a comment documenting this.
3. **`starting` status** — Use a module-level flag (e.g., `_first_probe = True`) that flips to `False` after the first health check completes. When `_first_probe` is `True`, return `"starting"` as the overall status.
4. **Ollama model probe** — Parse the JSON response from Ollama's `GET /api/tags` endpoint. Check if `settings.default_llm_model` and `settings.default_embed_model` are in the model list. Return `models: {"qwen2.5:7b": true/false, "nomic-embed-text": true/false}` in the Ollama service status.
5. **Upload dir** — Use `Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)`. The default `upload_dir` is configured in `backend/config.py` Settings.
6. **Write-access test** — Create a temp file, write to it, then remove it. If `PermissionError`, log clearly and raise `SystemExit(1)`.
7. **No new packages** — All changes use existing dependencies (httpx, structlog, pathlib are all already available).

## Verification Commands

```bash
# Health module imports
python -c "from backend.api.health import router" && echo "PASS: health module" || echo "FAIL"

# Both endpoints exist (check route registration)
python -c "
from backend.api.health import router
routes = [r.path for r in router.routes]
assert '/api/health/live' in routes or '/live' in routes, 'Missing /api/health/live'
print('PASS: both endpoints registered')
" || echo "FAIL"

# Middleware has health exclusion
grep -q '/api/health' backend/middleware.py && echo "PASS: health exclusion" || echo "FAIL"

# Main.py has upload dir creation
grep -q 'upload_dir' backend/main.py && echo "PASS: upload dir in main" || echo "FAIL"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
