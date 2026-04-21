# Research: End-to-End Debug & Verification

**Phase 0 output** — All unknowns resolved, no NEEDS CLARIFICATION remaining.

---

## Decision 1: Frontend BACKEND_URL — Runtime vs Build-Time

**Question**: Does `BACKEND_URL` in `next.config.ts` rewrites need to be available at build
time (via Docker build args) or at runtime (via container environment)?

**Research**:
- `frontend/next.config.ts` defines rewrites as an `async rewrites()` function
- In Next.js, `rewrites()` is evaluated when the server starts, not during `next build`
- The function reads `process.env.BACKEND_URL` at **server startup time**
- `docker-compose.yml` passes `BACKEND_URL=http://backend:8000` as a runtime environment variable
- The frontend Dockerfile has NO `ARG BACKEND_URL` — this is **correct behavior**

**Decision**: BACKEND_URL is a **runtime** environment variable. No Dockerfile build args needed.

**Rationale**: Next.js evaluates the `async rewrites()` function when the server process starts,
not during the build step. The runtime env var from docker-compose.yml is sufficient.

**Alternatives considered**:
- Build-time ARG/ENV in Dockerfile — **rejected** (unnecessary, rewrites are runtime)
- Middleware-based proxying — **rejected** (overkill, rewrites already work)

**Implication for plan**: Root Cause #1 ("BACKEND_URL not passed at build time") is
**partially incorrect**. The rewrite mechanism is runtime, not build-time. The actual cause of
frontend exit code 1 must be investigated separately — it may be a build failure (missing
dep, TypeScript error), a runtime crash (missing env var for something else), or a startup
timing issue. A1 must diagnose the actual crash from `docker compose logs frontend`.

---

## Decision 2: Health Endpoint /api/health/live — Path Registration

**Question**: Why does `/api/health/live` return 404 when it's defined in the code?

**Research**:
- `backend/api/health.py:17` — `router = APIRouter()` (no prefix)
- `backend/api/health.py:25` — `@router.get("/api/health/live")` (full path in decorator)
- `backend/api/health.py:31` — `@router.get("/api/health")` (full path in decorator)
- `backend/main.py:359` — `app.include_router(health.router, tags=["health"])` (no prefix)

**Decision**: The endpoint paths are hardcoded as full paths with no router prefix.
Both `/api/health` and `/api/health/live` **should** be registered correctly.

**Rationale**: FastAPI registers the exact decorator path when no prefix is used in
`include_router()`. The 404 reported in spec-20 may have been:
1. A transient issue during that session (container not fully started)
2. A code state that was later fixed
3. An issue with how the endpoint was tested (wrong URL, wrong method)

**Implication for plan**: A2 must **verify** both endpoints are registered by listing all
routes programmatically. If `/api/health/live` truly returns 404 in the current code, A2
investigates the root cause (middleware, exception in handler, import error). If it works,
A2 documents the finding and moves on.

---

## Decision 3: Data Seeding Approach

**Question**: How should the application be seeded with demo data for E2E testing?

**Research**:
- No built-in seeding mechanism exists
- Test fixtures exist: `tests/fixtures/sample.md`, `sample.pdf`, `sample.txt`
- Backend API exposes `POST /api/collections` and `POST /api/collections/{id}/ingest`
- Ingestion is async: returns job_id, must poll for completion
- `httpx` is already a dependency (used by backend and tests)

**Decision**: Create `scripts/seed_data.py` using httpx to call the backend API.

**Rationale**: Using the public API ensures the full pipeline is tested (API → chunking →
embedding → Qdrant upsert). Direct database manipulation would bypass the ingestion pipeline
and miss bugs. httpx is already installed.

**Alternatives considered**:
- Direct SQLite + Qdrant insertion — **rejected** (bypasses pipeline, misses bugs)
- Django-style fixtures/migrations — **rejected** (not applicable to this stack)
- Docker entrypoint seed command — **rejected** (couples seeding to container lifecycle)

**Design**:
```
seed_data.py
├── Check if "Sample Knowledge Base" collection exists (GET /api/collections)
├── If not: create it (POST /api/collections)
├── Upload tests/fixtures/sample.md (POST /api/collections/{id}/ingest)
├── Poll job status until complete (GET /api/collections/{id}/ingest/{job_id})
├── Report: collection name, document count, chunk count
└── Exit 0 on success, 1 on failure
```

---

## Decision 4: Smoke Test Architecture

**Question**: What approach for the automated smoke test suite?

**Research**:
- FR-022: Single command covering health, API, basic workflows
- FR-023: Exit 0 on success, non-zero on failure
- FR-024: Individual check results with pass/fail and timing
- Must test against running Docker services (not in-process)
- httpx already available for HTTP calls

**Decision**: Create `scripts/smoke_test.py` — a standalone Python script using httpx.

**Rationale**: Python with httpx provides clean async HTTP testing with good error handling.
A standalone script (not pytest) is simpler for CI/CD integration and matches the "single
command" requirement. No new dependencies needed.

**Alternatives considered**:
- Bash script with curl — **rejected** (harder to parse NDJSON, poor error handling)
- pytest-based E2E — **rejected** (confuses smoke tests with unit tests, different lifecycle)
- Playwright browser tests — **rejected** (heavier than needed for API-level smoke test)

**Design**: 13 sequential checks, each with timing and pass/fail. See
`contracts/smoke-test.md` for the full contract.

---

## Decision 5: Frontend Integration Testing Strategy

**Question**: How should we verify all 5 frontend pages work with real backend data?

**Research**:
- MCP tools available: Playwright, Chrome DevTools, Browser Tools
- Frontend uses SWR for data fetching (handles loading/error states)
- Pages: Chat, Collections, Settings, Observability, Documents
- Main concern: pages crash when receiving real API data shapes vs expected shapes

**Decision**: Orchestrator uses Playwright MCP for browser verification at gate checks.
A3 fixes any page crashes by reading code and matching to real API response shapes.

**Rationale**: Playwright provides programmatic access to page snapshots, console messages,
and network requests — exactly what's needed to verify frontend integration. A3 can test
pages by curling from the host to check HTTP 200, but deep verification (console errors,
rendering) requires browser tools.

**Alternatives considered**:
- Manual browser testing only — **rejected** (not repeatable)
- New Playwright test files — **rejected** (adds complexity, NFR-001)
- Frontend unit tests with mocked API — **rejected** (already exist, don't test real integration)

---

## Decision 6: Makefile Verification Strategy

**Question**: How to ensure Makefile is never accidentally modified (SC-009)?

**Decision**: `git diff -- Makefile | wc -l` at every gate check. Must output 0.

**Rationale**: Byte-level git diff is the most reliable check. md5sum would also work
but adds unnecessary complexity.

**Additional safeguard**: Every agent instruction file lists Makefile under "NEVER touch".
