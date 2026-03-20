# Spec 19: Cross-Platform Developer Experience -- Implementation Plan

```
# MANDATORY: TMUX MULTI-PANE SPAWNING REQUIRED
# Agent Teams MUST run in tmux. Each wave agent gets its own pane.
# Use TeamCreate -> TaskCreate -> Agent(team_name=...) -> SendMessage
# NEVER spawn agents/subagents in the same pane. Each agent = separate tmux pane.
```

---

## What This Spec Does

Spec-19 transforms The Embedinator from a multi-command, toolchain-dependent setup into
a single-command, cross-platform application. Users run `./embedinator.sh` (macOS/Linux)
or `.\embedinator.ps1` (Windows) and the entire stack builds, configures, downloads AI
models, and reports readiness. Docker Desktop is the only prerequisite.

**Scope**: 56 FRs across 9 areas, 10 SCs, 7 user stories.
**Full-stack**: Docker infrastructure, backend health, frontend routing + degraded states,
launcher scripts, cross-platform hardening.

---

## Authoritative Files -- Read Order

Every agent MUST read its own instruction file FIRST, then these shared files:

| Priority | File | Contains |
|----------|------|----------|
| 1 | Agent instruction file (`Docs/PROMPTS/spec-19-cross-platform/agents/A{N}-instructions.md`) | Assigned tasks, detailed orders |
| 2 | `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` | Authoritative design decisions (13 sections) |
| 3 | `specs/019-cross-platform-dx/spec.md` | FR-001 through FR-056, SC-001 through SC-010 |
| 4 | This file (`Docs/PROMPTS/spec-19-cross-platform/19-plan.md`) | Phase structure, agent roster, stale patterns |

---

## Build Verification Protocol

```
Backend health tests:  Use external runner per MEMORY.md policy
  zsh scripts/run-tests-external.sh -n <name> --no-cov <target>
  cat Docs/Tests/<name>.status
  cat Docs/Tests/<name>.summary

Frontend tests:       cd frontend && npm run build && npm run test

Docker validation:    docker compose config > /dev/null 2>&1
                      docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null 2>&1

Launcher validation:  bash -n embedinator.sh              # syntax check only
                      pwsh -NoProfile -Command "& { $ErrorActionPreference='Stop'; . ./embedinator.ps1 -WhatIf }" 2>/dev/null || true

Health endpoint:      curl -sf http://localhost:8000/api/health/live
                      curl -sf http://localhost:8000/api/health
                      wget --spider http://localhost:3000/healthz 2>/dev/null || curl -sf http://localhost:3000/healthz
```

---

## Implementation Phases

Seven phases organized by dependency order. Each phase can be validated independently.

---

### Phase 1: Docker Infrastructure (P0 -- foundation)

**FR ownership**: FR-017, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-038, FR-039, FR-040, FR-041, FR-042, FR-053
**SC coverage**: SC-001 (partial), SC-003 (partial), SC-010
**Assigned to**: A1 (devops-architect)

Everything else depends on correct Docker Compose files. This phase must complete
first and be gate-checked before any launcher script or frontend work starts.

#### Files to CREATE

| File | Purpose |
|------|---------|
| `docker-compose.gpu-nvidia.yml` | NVIDIA GPU overlay -- adds `deploy.resources.reservations.devices` to Ollama service (FR-018) |
| `docker-compose.gpu-amd.yml` | AMD ROCm overlay -- swaps Ollama image to `ollama/ollama:rocm`, adds `/dev/kfd` + `/dev/dri` passthrough (FR-018) |
| `docker-compose.gpu-intel.yml` | Intel Arc overlay -- adds `/dev/dri` passthrough, experimental (FR-018) |
| `.gitattributes` | Enforce LF for `.sh`, `.py`, `.ts`, `.yml`, `.json`, `Dockerfile*`; enforce CRLF for `.ps1` (FR-053) |
| `frontend/.dockerignore` | Exclude `tests/`, `node_modules/`, `.next/`, `.git/`, `*.md`, `test-results/` from build context (FR-042) |

#### Files to MODIFY

| File | Current State | Required Changes |
|------|--------------|-----------------|
| `docker-compose.yml` | Lines 30-36: NVIDIA `deploy` block on Ollama. Line 24: inline model-pulling entrypoint. Lines 6-9,45,75: hardcoded ports, no SELinux `:z`. Line 79: `NEXT_PUBLIC_API_URL`. No log rotation. No frontend health check. No `stop_grace_period`. | **Remove** Ollama `deploy` block (lines 30-36). **Remove** inline model-pulling entrypoint, replace with `ollama serve`. **Add** variable interpolation for all 5 port mappings (FR-019). **Add** `:z` to all bind mounts (FR-020). **Add** `logging:` block to all services (FR-021). **Change** Qdrant volume to bind mount `./data/qdrant_db:/qdrant/storage:z` (FR-022). **Add** `depends_on: backend: condition: service_healthy` to frontend (FR-023). **Add** `stop_grace_period: 15s` to backend (FR-024). **Replace** `NEXT_PUBLIC_API_URL` with `BACKEND_URL=http://backend:8000`. **Add** frontend health check targeting `/healthz`. **Change** backend health check to target `/api/health/live` (FR-033). |
| `docker-compose.dev.yml` | Lines 18-19: mounts `./frontend/src:/app/src` which does NOT exist. Line 21: uses `NEXT_PUBLIC_API_URL`. | **Fix** frontend volume mounts to individual dirs: `app/`, `components/`, `hooks/`, `lib/`, `public/`, `next.config.ts`, `tsconfig.json`. **Add** anonymous volumes for `node_modules/` and `.next/`. **Use** `target: deps` for frontend build. **Override** command to `npx next dev --hostname 0.0.0.0`. **Replace** `NEXT_PUBLIC_API_URL` with `BACKEND_URL`. **Add** backend `--reload` to command. (FR-025) |
| `Dockerfile.backend` | Lines 32-34: dynamic UID via `addgroup --system` / `adduser --system`. No `tini`. No cross-encoder pre-download. | **Change** user creation to fixed UID/GID 1000 (FR-038). **Install** `tini` and set as ENTRYPOINT (FR-039). **Add** cross-encoder model pre-download after `pip install` with `ENV HF_HOME=/app/.cache/huggingface` (FR-040). **Create** `/data` and `/data/uploads` dirs owned by UID 1000 before `USER` directive. |
| `frontend/Dockerfile` | Line 1: uses `node:lts-alpine`. Lines 22-23: separate `addgroup`/`adduser` layers. | **Pin** to `node:22-alpine` (FR-041). **Combine** `addgroup` + `adduser` into one `RUN` layer. **Add** `BACKEND_URL` as optional build arg/env var. |

#### Verification

```
docker compose config > /dev/null                                       # base valid
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null  # nvidia overlay valid
docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml config > /dev/null     # amd overlay valid
docker compose -f docker-compose.yml -f docker-compose.gpu-intel.yml config > /dev/null    # intel overlay valid
docker compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null          # dev overlay valid
grep -q 'EMBEDINATOR_PORT_FRONTEND' docker-compose.yml                  # port interpolation present
grep -q ':z' docker-compose.yml                                         # SELinux suffix present
grep -q 'json-file' docker-compose.yml                                  # log rotation present
grep -q 'stop_grace_period' docker-compose.yml                          # grace period present
grep -c 'deploy:' docker-compose.yml                                    # must be 0 (no GPU block)
grep -q 'tini' Dockerfile.backend                                       # tini installed
grep -q '1000' Dockerfile.backend                                       # fixed UID
grep -q 'cross-encoder' Dockerfile.backend                              # model pre-download
grep -q 'node:22-alpine' frontend/Dockerfile                            # pinned node version
test -f .gitattributes                                                  # exists
test -f frontend/.dockerignore                                          # exists
# SC-010 check: Makefile unchanged
diff <(git show HEAD:Makefile) Makefile                                 # no diff
```

---

### Phase 2: Frontend API Routing Fix (P0 -- critical bug fix)

**FR ownership**: FR-026, FR-027, FR-028, FR-029, FR-030, FR-031
**SC coverage**: SC-005
**Assigned to**: A2 (frontend-architect)
**Dependencies**: None (can run in parallel with Phase 1 and Phase 3)

This fixes the #1 cross-platform bug: `NEXT_PUBLIC_API_URL` being baked into the JS
bundle with a Docker-internal hostname that browsers cannot resolve.

#### Files to CREATE

| File | Purpose |
|------|---------|
| `frontend/app/healthz/route.ts` | Next.js App Router API route. Returns `{ "status": "ok" }` with HTTP 200. Path is `/healthz` (not `/api/health`) to avoid the rewrite rule. (FR-029) |
| `frontend/app/page.tsx` | Root route redirect. `redirect("/chat")` using Next.js `next/navigation`. (FR-031) |

#### Files to MODIFY

| File | Current State | Required Changes |
|------|--------------|-----------------|
| `frontend/next.config.ts` | Lines 6-8: `env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL }`. No `rewrites`. | **Remove** the `env` block (lines 6-8). **Add** `async rewrites()` that proxies `/api/:path*` to `${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*`. (FR-027). Retain `NEXT_PUBLIC_API_URL` as an optional override check in the rewrite -- only apply rewrite if `NEXT_PUBLIC_API_URL` is not set. |
| `frontend/lib/api.ts` | Line 17: `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000"`. | **Change** to `const API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| ""`. The empty string means all fetch calls use relative paths (`/api/...`), which the Next.js rewrite proxies to the backend. (FR-028) |

#### Verification

```
cd frontend && npm run build                   # build succeeds with rewrites
cd frontend && npm run test                    # existing tests pass
grep -q 'rewrites' frontend/next.config.ts     # rewrite present
grep -q 'BACKEND_URL' frontend/next.config.ts  # server-side env var used
grep 'API_BASE' frontend/lib/api.ts            # must show empty string fallback, not http://localhost:8000
test -f frontend/app/healthz/route.ts          # health endpoint exists
test -f frontend/app/page.tsx                  # root redirect exists
```

---

### Phase 3: Backend Health Enhancement (P1)

**FR ownership**: FR-032, FR-033, FR-034, FR-035, FR-036, FR-037, FR-044, FR-045
**SC coverage**: SC-006, SC-009 (partial)
**Assigned to**: A3 (backend-architect)
**Dependencies**: None (can run in parallel with Phase 1 and Phase 2)

Adds liveness endpoint, enhances readiness with model availability, suppresses health
log noise, and ensures circuit breaker bypass for health probes.

#### Files to MODIFY

| File | Current State | Required Changes |
|------|--------------|-----------------|
| `backend/api/health.py` | Single endpoint `GET /api/health`. Status is `"healthy"` or `"degraded"`. No liveness endpoint. No model availability check. | **Add** `GET /api/health/live` returning `{"status": "alive"}` unconditionally (FR-032). **Enhance** `/api/health` to include a `models` field in the Ollama service status with list of available vs required models (FR-034). **Add** `"starting"` as a valid overall status when dependencies are initializing (FR-035). |
| `backend/agent/schemas.py` | Lines 172-181: `HealthServiceStatus` has `status: Literal["ok", "error"]`. `HealthResponse` has `status: Literal["healthy", "degraded"]`. | **Extend** `HealthResponse.status` to `Literal["healthy", "degraded", "starting"]` (FR-035). **Add** optional `models` field to `HealthServiceStatus` for Ollama model reporting: `models: dict[str, bool] \| None = None` (FR-034). |
| `backend/middleware.py` | Lines 35-54: `RequestLoggingMiddleware` logs every request including health checks. | **Add** path exclusion list: skip logging for `/api/health` and `/api/health/live` (FR-036). Insert check at top of `dispatch`: `if request.url.path in ("/api/health", "/api/health/live"): return await call_next(request)`. |
| `backend/main.py` | Lines 117-229: `lifespan()` function. No upload dir creation. No write-access test. Qdrant/Ollama are hard dependencies (backend waits for both). | **Add** upload directory creation at startup: `os.makedirs(settings.upload_dir, exist_ok=True)` (FR-044). **Add** write-access test: attempt to create and remove a temp file in the data dir, exit with clear error if fails (FR-045). **Make** Ollama a soft dependency: wrap Ollama-dependent init in try/except, set `app.state.ollama_available = False` on failure instead of crashing. |

#### Notes on FR-037 (circuit breaker bypass)

The circuit breaker lives in `backend/retrieval/searcher.py` (HybridSearcher). Health
probes do not go through HybridSearcher -- they make direct HTTP calls to Ollama via
httpx. Therefore FR-037 is already satisfied by design. A3 should verify this and
document it rather than adding code.

#### Verification

```
# Syntax check
python -c "from backend.api.health import router"

# Liveness always returns 200
curl -sf http://localhost:8000/api/health/live | python -m json.tool
# Expected: {"status": "alive"}

# Readiness reports model availability
curl -sf http://localhost:8000/api/health | python -m json.tool
# Expected: status is "healthy"|"degraded"|"starting", Ollama service includes models dict

# Health logs suppressed
# Start backend, send 5 health requests, check logs -- no http_request entries for /api/health
```

---

### GATE CHECK (Orchestrator) -- After Phases 1, 2, 3

Before proceeding to Phase 4, the orchestrator verifies:

```bash
# Phase 1 gate
docker compose config > /dev/null 2>&1 && echo "PASS: base compose valid" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null 2>&1 && echo "PASS: nvidia overlay" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml config > /dev/null 2>&1 && echo "PASS: amd overlay" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-intel.yml config > /dev/null 2>&1 && echo "PASS: intel overlay" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null 2>&1 && echo "PASS: dev overlay" || echo "FAIL"
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile unchanged" || echo "FAIL: Makefile modified"

# Phase 2 gate
cd frontend && npm run build && echo "PASS: frontend builds" || echo "FAIL"
cd frontend && npm run test && echo "PASS: frontend tests" || echo "FAIL"
test -f frontend/app/healthz/route.ts && echo "PASS: healthz exists" || echo "FAIL"
test -f frontend/app/page.tsx && echo "PASS: root redirect exists" || echo "FAIL"

# Phase 3 gate
python -c "from backend.api.health import router" && echo "PASS: health module loads" || echo "FAIL"
```

**If any check fails**: Fix issues before proceeding. Do NOT spawn Wave 2 agents on broken infrastructure.

---

### Phase 4: Launcher Scripts (P1 -- depends on Phase 1)

**FR ownership**: FR-001, FR-002, FR-003, FR-004, FR-005, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011, FR-012, FR-013, FR-014, FR-015, FR-016, FR-054, FR-055, FR-056
**SC coverage**: SC-001, SC-002, SC-003, SC-004, SC-008, SC-009
**Assigned to**: A4 (devops-architect)
**Dependencies**: Phase 1 MUST be complete (launcher constructs compose commands using the overlay files)

This is the largest single phase by FR count (19 FRs). The launcher scripts are the
user-facing entry point and must implement: preflight checks, GPU detection, .env
generation, compose orchestration, health polling, model pulling, and browser open.

#### Files to CREATE

| File | Purpose |
|------|---------|
| `embedinator.sh` | Bash/zsh launcher for macOS + Linux. ~400-500 lines. See design doc Section 8 for full specification. (FR-001 through FR-016, FR-054, FR-056) |
| `embedinator.ps1` | PowerShell launcher for Windows. Must implement identical logic with PowerShell-native syntax. (FR-001 through FR-016, FR-055) |

#### Launcher Script Structure (`embedinator.sh`)

The script MUST follow this execution order:

```
1. Parse CLI flags (--dev, --stop, --restart, --logs, --status, --open, --help, --frontend-port, --backend-port)
2. Handle --help (print usage, exit 0)
3. Handle --stop (docker compose down, exit)
4. Handle --restart (docker compose down, then fall through to start)
5. Handle --logs (docker compose logs -f [service], exit)
6. Handle --status (poll health endpoints, print status table, exit)
7. Preflight checks:
   a. Docker daemon running (docker info)
   b. Docker Compose v2 (docker compose version)
   c. Port availability for all configured ports
   d. Disk space warning if < 15GB
   e. macOS: Docker VM memory warning if < 4GB
   f. Linux: Docker group membership check (FR-054)
   g. Windows/WSL2: /mnt/c/ path warning (FR-055)
   h. macOS: GPU info message (FR-056)
8. Environment setup:
   a. Copy .env.example -> .env if not exists
   b. Generate Fernet key via disposable container
   c. Apply CLI port overrides to .env
   d. Auto-detect LAN IP, write CORS_ORIGINS
   e. Create data/ and data/uploads/ directories
9. GPU detection (NVIDIA > AMD > Intel > none; EMBEDINATOR_GPU override)
10. Idempotency check: if services already running, report status (FR-015)
11. Build & start: select compose files, export port vars, docker compose up --build -d
12. Health polling: per-service status with in-place overwrite, timeout 300s/60s
13. Model pull: check cache, pull missing models with progress
14. Browser open (only with --open flag)
15. Print ready message with URL, logs command, stop command
```

#### PowerShell Parity (`embedinator.ps1`)

PowerShell equivalents for key operations:

| bash | PowerShell |
|------|-----------|
| `docker info 2>/dev/null` | `docker info 2>$null` |
| `nvidia-smi` | `nvidia-smi` (works in WSL2) |
| `lsof -i :PORT` or `ss -tlnp` | `Test-NetConnection -Port PORT -InformationLevel Quiet` or `Get-NetTCPConnection -LocalPort PORT` |
| `open URL` / `xdg-open URL` | `Start-Process URL` |
| `uname -s` | `$env:OS` / `[Environment]::OSVersion.Platform` |
| `grep VAR .env \| cut -d= -f2` | `(Get-Content .env \| Select-String 'VAR').Line.Split('=')[1]` |
| `curl -sf URL` | `Invoke-RestMethod URL` or `Invoke-WebRequest URL` |

#### Verification

```
# Syntax validation (no execution)
bash -n embedinator.sh                          # zero exit code
pwsh -NoProfile -File embedinator.ps1 -Help     # prints usage (Windows only)

# Help output
./embedinator.sh --help                         # prints all subcommands and flags

# Preflight without Docker (expect clean error)
# (manually stop Docker, run launcher, verify error message)

# SC-008: Fernet key generation without host Python
rm -f .env
./embedinator.sh --help    # triggers .env generation if needed
grep -q 'EMBEDINATOR_FERNET_KEY=.' .env         # key is non-empty

# SC-004: custom ports
./embedinator.sh --frontend-port 4000 --backend-port 9000 --stop  # verify port override logic
```

---

### Phase 5: Frontend Degraded States (P2 -- depends on Phase 3)

**FR ownership**: FR-046, FR-047, FR-048, FR-049
**SC coverage**: SC-007
**Assigned to**: A5 (frontend-architect)
**Dependencies**: Phase 3 MUST be complete (degraded state UI depends on the enhanced `/api/health` response)

#### Files to CREATE

| File | Purpose |
|------|---------|
| `frontend/components/BackendStatusProvider.tsx` | React context that polls `/api/health` via SWR with adaptive intervals: 5s when unreachable, 10s when degraded, 30s when ready. Exports `useBackendStatus()` hook. (FR-046) |
| `frontend/components/StatusBanner.tsx` | Non-dismissible banner rendered inside `SidebarLayout` between header and content. Uses `role="status"` and `aria-live="polite"`. Contextual messages per state. (FR-047) |

#### Files to MODIFY

| File | Current State | Required Changes |
|------|--------------|-----------------|
| `frontend/app/layout.tsx` | Lines 30-33: `ThemeProvider` wraps `SidebarLayout`. No `BackendStatusProvider`. | **Wrap** `SidebarLayout` with `BackendStatusProvider` inside `ThemeProvider`. Provider order: `ThemeProvider > BackendStatusProvider > SidebarLayout`. |
| `frontend/components/SidebarLayout.tsx` | Lines 26-33: `SidebarInset` contains header + main. No status banner. | **Import** and **render** `StatusBanner` between the `<header>` and `<main>` inside `SidebarInset`. |
| `frontend/components/ChatInput.tsx` | Lines 21-22: `canSend` checks `isStreaming`, `message.trim()`, `selectedCollections.length`. Placeholder is static. | **Import** `useBackendStatus()`. **Add** backend status to `canSend` check: disabled when not `ready`. **Change** placeholder to be contextual: "Waiting for backend..." / "AI models still loading..." / "Vector database starting..." / "Select at least one collection..." / "Ask a question..." (FR-048) |
| `frontend/components/ChatPanel.tsx` | Lines 25-31: `STARTER_QUESTIONS` shown as empty state when no messages. | **Import** `useBackendStatus()` and collections state. **Add** onboarding card when zero collections exist: guided steps with "Create a collection" button linking to `/collections`, "Upload documents" info, "Ask questions" description. Show standard starter questions when collections exist. (FR-049) |
| `frontend/lib/types.ts` | No `BackendStatus` type. | **Add** `BackendStatus` type: `"unreachable" \| "degraded" \| "ready"`. **Add** `BackendHealthResponse` interface matching the enhanced `/api/health` response. |

#### Verification

```
cd frontend && npm run build                    # build succeeds
cd frontend && npm run test                     # tests pass
grep -q 'BackendStatusProvider' frontend/app/layout.tsx          # provider present
grep -q 'StatusBanner' frontend/components/SidebarLayout.tsx     # banner present
grep -q 'useBackendStatus' frontend/components/ChatInput.tsx     # status hook used
```

---

### Phase 6: Graceful Shutdown + Environment (P2)

**FR ownership**: FR-043, FR-050, FR-051, FR-052
**SC coverage**: SC-008 (partial)
**Assigned to**: A6 (backend-architect)
**Dependencies**: Can run in parallel with Phase 4 and Phase 5

#### Files to MODIFY

| File | Current State | Required Changes |
|------|--------------|-----------------|
| `backend/main.py` | Lines 224-229: Shutdown only closes `db` and `qdrant`. No `shutting_down` flag. No WAL checkpoint. No checkpointer close. | **Add** `app.state.shutting_down = False` at startup (before `yield`). **Set** `app.state.shutting_down = True` at start of shutdown. **Add** WAL checkpoint: `await db.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")` on main DB. **Add** WAL checkpoint on checkpoint DB: open connection to `checkpoint_path`, execute checkpoint, close. **Add** explicit `await checkpointer.conn.close()` (FR-052). **Ensure** shutdown order: set flag -> checkpoint DBs -> close checkpointer -> close qdrant -> close db. |
| `backend/api/chat.py` | No shutdown rejection. | **Add** early return at top of chat endpoint: if `request.app.state.shutting_down`, yield NDJSON error `{"type": "error", "code": "SHUTTING_DOWN", "message": "Server is shutting down"}` and return (FR-050). |
| `.env.example` | Current: 28 Settings fields documented (from spec-17). Missing: `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, 5x `EMBEDINATOR_PORT_*`. | **Add** new section "Docker / Launcher" before the existing "Server" section with: `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, `EMBEDINATOR_PORT_FRONTEND`, `EMBEDINATOR_PORT_BACKEND`, `EMBEDINATOR_PORT_QDRANT`, `EMBEDINATOR_PORT_QDRANT_GRPC`, `EMBEDINATOR_PORT_OLLAMA`. (FR-043). Note: these variables are read by Docker Compose interpolation and the launcher, NOT by Pydantic Settings. Include comments explaining this. |

#### Verification

```
# Schema check
python -c "
from backend.main import create_app
app = create_app()
"

# .env.example completeness
grep -q 'BACKEND_URL' .env.example
grep -q 'OLLAMA_MODELS' .env.example
grep -q 'EMBEDINATOR_GPU' .env.example
grep -q 'EMBEDINATOR_PORT_FRONTEND' .env.example
grep -q 'EMBEDINATOR_PORT_BACKEND' .env.example
grep -q 'EMBEDINATOR_PORT_QDRANT' .env.example
grep -q 'EMBEDINATOR_PORT_OLLAMA' .env.example
```

---

### Phase 7: Validation & Cross-Platform Testing (P2)

**FR ownership**: (all -- verification only)
**SC coverage**: SC-001 through SC-010
**Assigned to**: A7 (quality-engineer)
**Dependencies**: ALL previous phases MUST be complete

#### Validation Checklist

| SC | Description | Verification Method |
|----|------------|-------------------|
| SC-001 | Linux user runs `./embedinator.sh`, all 4 services healthy within 10 min | `docker compose up` + health polling |
| SC-002 | Windows user runs `.\embedinator.ps1`, same outcome | PowerShell syntax check + manual (if available) |
| SC-003 | GPU auto-detection: NVIDIA detected with toolkit, CPU fallback without | Test GPU detection function in isolation |
| SC-004 | Custom ports: `--frontend-port 4000 --backend-port 9000` works | Compose config with env vars set |
| SC-005 | Frontend `/api/*` rewrites work, zero CORS errors | `npm run build` + verify next.config.ts rewrites |
| SC-006 | Health endpoint distinguishes "models missing" vs "Ollama unreachable" | Inspect health.py response schema |
| SC-007 | Frontend status banner + chat gating on degraded state | `npm run build` + `npm run test` |
| SC-008 | First-run .env generation with Fernet key without host Python | Launcher script logic review |
| SC-009 | Subsequent launches complete health checks within 60s | Health polling timeout logic review |
| SC-010 | All 14 Makefile targets function identically | `diff <(git show HEAD:Makefile) Makefile` -- must show zero changes |

#### Additional Checks

```
# All compose overlays parse correctly
for f in docker-compose.gpu-nvidia.yml docker-compose.gpu-amd.yml docker-compose.gpu-intel.yml docker-compose.dev.yml; do
  docker compose -f docker-compose.yml -f "$f" config > /dev/null 2>&1 && echo "PASS: $f" || echo "FAIL: $f"
done

# Frontend build + tests
cd frontend && npm run build && npm run test

# Backend health module loads
python -c "from backend.api.health import router"

# No new Python test failures vs baseline
zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/
# Compare: cat Docs/Tests/spec19-final.summary

# .gitattributes present
test -f .gitattributes && echo "PASS" || echo "FAIL"

# Launcher syntax valid
bash -n embedinator.sh && echo "PASS: bash syntax" || echo "FAIL"

# Existing Makefile preserved
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile untouched" || echo "FAIL"
```

---

## Agent Team Roster

| Agent | Role | Wave | Model | Phases | Mission |
|-------|------|------|-------|--------|---------|
| A1 | devops-architect | 1 | Sonnet | Phase 1 | Docker infrastructure: compose decomposition, GPU overlays, Dockerfile improvements, .gitattributes, .dockerignore |
| A2 | frontend-architect | 1 | Sonnet | Phase 2 | Frontend API routing fix: rewrites, healthz, root redirect, api.ts change |
| A3 | backend-architect | 1 | Sonnet | Phase 3 | Backend health: liveness, readiness enhancement, model availability, log suppression, upload dir, write-access |
| -- | *GATE CHECK* | 1.5 | Orchestrator | -- | Verify compose configs, frontend build, health module |
| A4 | devops-architect | 2 | Sonnet | Phase 4 | Launcher scripts: embedinator.sh + embedinator.ps1 (19 FRs) |
| A5 | frontend-architect | 2 | Sonnet | Phase 5 | Frontend degraded states: BackendStatusProvider, StatusBanner, chat gating, onboarding |
| A6 | backend-architect | 2 | Sonnet | Phase 6 | Graceful shutdown: shutting_down flag, WAL checkpoint, checkpointer close, .env.example |
| -- | *GATE CHECK* | 2.5 | Orchestrator | -- | Verify launcher syntax, frontend build, shutdown logic |
| A7 | quality-engineer | 3 | Sonnet | Phase 7 | Full validation: all 10 SCs, cross-platform checks, regression testing |

**Total: 7 agents across 3 waves.**

---

## Wave Execution Sequence

### Wave 1 -- A1, A2, A3 PARALLEL (3 separate tmux panes)

```
1. TeamCreate("spec19-cross-platform")
2. TaskCreate(team="spec19-cross-platform", task for A1)
3. TaskCreate(team="spec19-cross-platform", task for A2)
4. TaskCreate(team="spec19-cross-platform", task for A3)
5. Spawn all 3 agents simultaneously via Agent Teams:
   A1: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A1-instructions.md FIRST, then execute all assigned tasks."
   A2: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A2-instructions.md FIRST, then execute all assigned tasks."
   A3: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A3-instructions.md FIRST, then execute all assigned tasks."
6. Wait for all 3 to complete.
```

**Parallel safety**: A1 touches Docker/infra files, A2 touches frontend routing files, A3 touches backend Python files. Zero file overlap.

### Wave 1.5 -- GATE CHECK (Orchestrator)

Run the gate check commands listed after Phase 3. All must pass before proceeding.

### Wave 2 -- A4, A5, A6 PARALLEL (3 separate tmux panes)

```
Spawn all 3 agents simultaneously:
A4: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A4-instructions.md FIRST, then execute all assigned tasks."
A5: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A5-instructions.md FIRST, then execute all assigned tasks."
A6: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A6-instructions.md FIRST, then execute all assigned tasks."
```

**Parallel safety**: A4 creates new launcher scripts (no existing file conflicts). A5 touches frontend components. A6 touches backend `main.py`, `chat.py`, `.env.example`. The only potential collision is A5 modifying `frontend/app/layout.tsx` (adding BackendStatusProvider) while A2 already modified it in Wave 1 (no, A2 does NOT modify layout.tsx -- A2 modifies `next.config.ts` and `lib/api.ts`). Safe to parallelize.

**File touch matrix (Wave 2)**:
- A4: `embedinator.sh` (new), `embedinator.ps1` (new)
- A5: `frontend/components/BackendStatusProvider.tsx` (new), `frontend/components/StatusBanner.tsx` (new), `frontend/app/layout.tsx`, `frontend/components/SidebarLayout.tsx`, `frontend/components/ChatInput.tsx`, `frontend/components/ChatPanel.tsx`, `frontend/lib/types.ts`
- A6: `backend/main.py`, `backend/api/chat.py`, `.env.example`

Zero overlap between A4, A5, A6.

### Wave 2.5 -- GATE CHECK (Orchestrator)

```bash
bash -n embedinator.sh && echo "PASS" || echo "FAIL"
cd frontend && npm run build && echo "PASS" || echo "FAIL"
cd frontend && npm run test && echo "PASS" || echo "FAIL"
python -c "from backend.main import create_app" && echo "PASS" || echo "FAIL"
```

### Wave 3 -- A7 SOLO (Sequential)

```
A7: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A7-instructions.md FIRST, then execute all assigned tasks."
```

A7 runs the full SC-001 through SC-010 validation, regression tests, and writes a
validation report.

---

## Per-Agent Instruction File Specs

These define what each agent instruction file (`Docs/PROMPTS/spec-19-cross-platform/agents/A{N}-instructions.md`) must contain.

### A1: devops-architect (Phase 1 -- Docker Infrastructure)

- **FRs owned**: FR-017, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-038, FR-039, FR-040, FR-041, FR-042, FR-053
- **Files to create**: `docker-compose.gpu-nvidia.yml`, `docker-compose.gpu-amd.yml`, `docker-compose.gpu-intel.yml`, `.gitattributes`, `frontend/.dockerignore`
- **Files to modify**: `docker-compose.yml`, `docker-compose.dev.yml`, `Dockerfile.backend`, `frontend/Dockerfile`
- **Files NEVER to touch**: `Makefile` (SC-010)
- **Must read first**: Design doc Sections 2, 3, 10, 11 (compose decomposition, ports, Dockerfiles, volumes)
- **Verification**: All 5 compose config commands pass; `grep` checks for all required attributes
- **Key gotchas**: (1) Remove the NVIDIA `deploy` block from base compose -- do NOT just comment it out. (2) The Ollama entrypoint must change from the inline model-pulling script to just `ollama serve`. (3) The `:z` suffix goes on bind mounts only, not named volumes. (4) `tini` must be installed via `apt-get` in the Dockerfile, not via a separate package manager. (5) The cross-encoder pre-download must happen AFTER `pip install` (needs sentence-transformers installed first).

### A2: frontend-architect (Phase 2 -- API Routing Fix)

- **FRs owned**: FR-026, FR-027, FR-028, FR-029, FR-030, FR-031
- **Files to create**: `frontend/app/healthz/route.ts`, `frontend/app/page.tsx`
- **Files to modify**: `frontend/next.config.ts`, `frontend/lib/api.ts`
- **Must read first**: Design doc Section 5 (frontend API routing)
- **Verification**: `npm run build` succeeds; `npm run test` passes; grep checks
- **Key gotchas**: (1) The `rewrites()` function in next.config.ts must be `async`. (2) The rewrite destination uses `BACKEND_URL` (server-side env), NOT `NEXT_PUBLIC_API_URL` (client-side). (3) The `/healthz` route must NOT be under `/api/` to avoid being caught by the rewrite. (4) The `page.tsx` root redirect should use `redirect()` from `next/navigation`, not a client-side redirect. (5) NDJSON streaming must work through the rewrite -- Next.js rewrites operate at the HTTP level and do not buffer by default, so this should work without extra configuration. (6) The `env` block in `next.config.ts` (current lines 6-8) must be REMOVED, not just modified.

### A3: backend-architect (Phase 3 -- Backend Health)

- **FRs owned**: FR-032, FR-033, FR-034, FR-035, FR-036, FR-037, FR-044, FR-045
- **Files to modify**: `backend/api/health.py`, `backend/agent/schemas.py`, `backend/middleware.py`, `backend/main.py`
- **Must read first**: Design doc Sections 6.1-6.5 (backend resilience)
- **Verification**: Health module imports; health endpoint returns correct schema
- **Key gotchas**: (1) The liveness endpoint MUST NOT probe any external service -- it only confirms the process is alive. (2) The `/api/health` Ollama probe already calls `/api/tags` which returns the model list -- parse that response to check for required models (from `settings.default_llm_model` and `settings.default_embed_model`). (3) Do NOT change the Ollama probe to a different endpoint. (4) The `"starting"` status applies when the backend process is alive but dependencies have not been probed yet (first request after startup). (5) FR-037: Health probes already bypass the circuit breaker because they use direct httpx calls, not HybridSearcher. Document this, do not add code. (6) When making Ollama a soft dependency in `main.py`, catch only the connection error during graph compilation -- do not silently swallow all exceptions.

### A4: devops-architect (Phase 4 -- Launcher Scripts)

- **FRs owned**: FR-001 through FR-016, FR-054, FR-055, FR-056
- **Files to create**: `embedinator.sh`, `embedinator.ps1`
- **Must read first**: Design doc Sections 4, 8, 9 (GPU detection, launcher design, cross-platform)
- **Verification**: `bash -n embedinator.sh` passes; `--help` prints usage; `.env` generation works
- **Key gotchas**: (1) The Fernet key generation uses a disposable container: `docker run --rm python:3.14-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. This requires Docker to be running and the python image to be pullable. (2) Port conflict detection on Linux: use `ss -tlnp 2>/dev/null | grep ":PORT "` or `lsof -i :PORT`. On macOS: `lsof -i :PORT`. (3) The `CORS_ORIGINS` auto-generation must use the CONFIGURED frontend port (from .env or CLI flag), not hardcoded 3000. (4) GPU detection priority is NVIDIA > AMD > Intel > none. macOS always returns "none" regardless of hardware. (5) The PowerShell script must handle the case where `docker compose` is not available (Docker Desktop not installed or not in PATH). (6) The launcher must be idempotent -- if `docker compose ps` shows running services, skip the build and go straight to health polling. (7) Health polling must use the CONFIGURED host ports, not hardcoded defaults.

### A5: frontend-architect (Phase 5 -- Degraded States)

- **FRs owned**: FR-046, FR-047, FR-048, FR-049
- **Files to create**: `frontend/components/BackendStatusProvider.tsx`, `frontend/components/StatusBanner.tsx`
- **Files to modify**: `frontend/app/layout.tsx`, `frontend/components/SidebarLayout.tsx`, `frontend/components/ChatInput.tsx`, `frontend/components/ChatPanel.tsx`, `frontend/lib/types.ts`
- **Must read first**: Design doc Section 7 (frontend degraded state handling)
- **Verification**: `npm run build` + `npm run test`; grep checks for provider/banner/hook usage
- **Key gotchas**: (1) SWR already exists in the project (used for other data fetching). Use the same SWR patterns. (2) The `BackendStatusProvider` must handle fetch failures gracefully -- when the backend is unreachable, `fetch("/api/health")` will throw, not return a response. Catch errors and map to `"unreachable"` status. (3) The `StatusBanner` must NOT be dismissible -- it auto-hides when status becomes ready. (4) Provider nesting order in layout.tsx: `ThemeProvider > BackendStatusProvider > SidebarLayout`. The `Toaster` and `CommandPalette` remain outside `BackendStatusProvider`. (5) The onboarding card in ChatPanel needs to know whether collections exist -- use the existing `getCollections()` API call via SWR, not a new endpoint. (6) Use existing design tokens from the Obsidian Violet system (CSS variables), not hardcoded colors.

### A6: backend-architect (Phase 6 -- Shutdown + Env)

- **FRs owned**: FR-043, FR-050, FR-051, FR-052
- **Files to modify**: `backend/main.py`, `backend/api/chat.py`, `.env.example`
- **Must read first**: Design doc Sections 6.3, 3 (graceful shutdown, configurable ports)
- **Verification**: `create_app()` imports; `.env.example` grep checks
- **Key gotchas**: (1) The `shutting_down` flag is on `app.state`, not a global variable. (2) WAL checkpoint syntax: `await db.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")`. (3) The checkpoint DB path is derived from `settings.sqlite_path.replace("embedinator.db", "checkpoints.db")` -- this is already computed in `lifespan()` at line 158. Reuse that variable. (4) The checkpointer's internal connection is accessed via `checkpointer.conn` (AsyncSqliteSaver attribute). (5) The `.env.example` additions go at the TOP of the file in a new section, because Docker Compose and launcher variables are conceptually separate from Pydantic Settings fields. (6) The NDJSON shutdown error in `chat.py` must match the existing error event format: `{"type": "error", "code": "SHUTTING_DOWN", "message": "Server is shutting down, please retry in a moment"}`.

### A7: quality-engineer (Phase 7 -- Validation)

- **FRs owned**: None (verification only)
- **Files to create**: `specs/019-cross-platform-dx/validation-report.md`
- **Must read first**: This plan (SC verification table), spec.md (all 10 SCs)
- **Verification**: All 10 SCs documented with PASS/FAIL status
- **Key gotchas**: (1) SC-010 is critical: `diff` the Makefile against the HEAD commit to confirm zero changes. (2) SC-005 cannot be fully tested without running the Docker stack, but can be verified structurally (rewrites present, API_BASE is empty string, BACKEND_URL used). (3) Run `cd frontend && npm run build && npm run test` to catch any frontend regressions. (4) Run the backend test suite via `zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/` and compare against baseline (39 pre-existing failures -- zero new failures allowed). (5) Check that no new npm/pip dependencies were added (spec says "no new packages").

---

## Critical Path and Risk Analysis

### Critical Path (longest dependency chain)

```
Phase 1 (Docker infra) -----> Gate Check 1 -----> Phase 4 (Launcher scripts) -----> Gate Check 2 -----> Phase 7 (Validation)
   ~2h                           ~15min                ~3h                             ~15min               ~1h
```

**Estimated total wall-clock time: ~7 hours** (with Phases 2/3 and 5/6 running in parallel with the critical path).

The launcher scripts (Phase 4) are the single largest work item and the biggest
serial bottleneck. They depend on Phase 1 compose files being correct.

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Launcher script complexity** | HIGH | HIGH | A4 is the sole agent for 19 FRs. Budget extra time. PowerShell parity is the hardest part -- start with bash, then translate. |
| **NDJSON streaming through Next.js rewrites** | MEDIUM | HIGH | Next.js rewrites operate at HTTP level and should not buffer. But if streaming breaks, fallback is to keep `NEXT_PUBLIC_API_URL` as an environment variable that bypasses rewrites for the chat endpoint only. A2 must test this. |
| **tini installation in Dockerfile.backend** | LOW | MEDIUM | `tini` is available via `apt-get install tini` on Debian-based images. Verify with `python:3.14-slim`. |
| **Cross-encoder pre-download image size** | LOW | LOW | Only 24MB added. Acceptable per design doc. |
| **PowerShell on non-Windows** | LOW | LOW | PowerShell is only for Windows users. Bash covers macOS + Linux. No cross-platform PowerShell requirement. |
| **Frontend test regressions from api.ts change** | MEDIUM | MEDIUM | Changing `API_BASE` from absolute URL to empty string affects every fetch mock. A2 must verify all frontend tests pass after the change. |
| **Makefile accidentally modified** | LOW | CRITICAL | SC-010 is explicit. All agents have `Makefile` in their "NEVER touch" list. Gate checks verify with `diff`. |

### What Needs Manual Testing on Non-Linux OS

| Item | OS | Why Manual |
|------|-----|-----------|
| `embedinator.ps1` full execution | Windows 10/11 | PowerShell script can be syntax-checked but not fully run on Linux |
| macOS Docker memory warning | macOS | Uses `docker info` format specific to Docker Desktop for Mac |
| WSL2 path warning | Windows (WSL2) | Requires actual WSL2 environment to test `/mnt/c/` detection |
| GPU detection (NVIDIA on Windows) | Windows (WSL2) | `nvidia-smi` works differently under WSL2 |
| Browser auto-open | macOS, Windows | `open` (macOS), `Start-Process` (Windows) |

---

## Stale Pattern Warnings -- EVERY AGENT MUST KNOW

These are verified facts about the current codebase state. Agents encountering these
must treat them as bugs from the pre-spec-19 state, not as correct behavior.

| Current State | Location | What is Wrong | Correct State After Spec-19 |
|--------------|----------|--------------|---------------------------|
| NVIDIA GPU `deploy` block in base compose | `docker-compose.yml` lines 30-36 | Crashes on macOS, non-NVIDIA Linux, Windows without NVIDIA | REMOVED from base. Moved to `docker-compose.gpu-nvidia.yml` overlay. |
| Inline model-pulling entrypoint for Ollama | `docker-compose.yml` line 24 | `ollama serve & sleep 5 && ollama pull...` -- fragile, blocks startup | Changed to just `ollama serve`. Model pulling moved to launcher script. |
| `NEXT_PUBLIC_API_URL=http://backend:8000` | `docker-compose.yml` line 79 | Docker-internal hostname baked into JS bundle, browser cannot resolve | REMOVED. Replaced with `BACKEND_URL=http://backend:8000` (server-side). |
| `./frontend/src:/app/src` volume mount | `docker-compose.dev.yml` line 19 | `frontend/src/` directory does not exist. Frontend uses `app/`, `components/`, etc. | Fixed to mount individual frontend directories. |
| `NEXT_PUBLIC_API_URL` in dev overlay | `docker-compose.dev.yml` line 21 | Same baking bug as production compose | Replaced with `BACKEND_URL`. |
| `API_BASE = process.env.NEXT_PUBLIC_API_URL \|\| "http://localhost:8000"` | `frontend/lib/api.ts` line 17 | Absolute URL does not work when frontend is behind Docker networking | Changed to `process.env.NEXT_PUBLIC_API_URL \|\| ""` (relative paths). |
| `env: { NEXT_PUBLIC_API_URL: ... }` | `frontend/next.config.ts` lines 6-8 | Bakes env var into client bundle | REMOVED. Replaced with `rewrites()`. |
| Dynamic UID in Dockerfile.backend | `Dockerfile.backend` lines 32-34 | `adduser --system` gets auto-assigned UID, may not match host user 1000 | Fixed to `--uid 1000 --gid 1000` (or equivalent). |
| `node:lts-alpine` base image | `frontend/Dockerfile` line 1 | `lts-alpine` tag rolls forward, breaking Docker cache on Node version bumps | Pinned to `node:22-alpine`. |
| No liveness endpoint | `backend/api/health.py` | Only `/api/health` (readiness). Docker HEALTHCHECK using readiness means container restarts during model downloads. | Added `/api/health/live` (liveness). HEALTHCHECK targets liveness. |
| Health requests logged | `backend/middleware.py` lines 38-54 | Every 10s health check generates a log line, flooding logs | Health paths excluded from `RequestLoggingMiddleware`. |
| Hardcoded ports `"3000:3000"`, `"8000:8000"` | `docker-compose.yml` lines 45, 75, etc. | Users with services on 3000/8000 cannot override | Variable interpolation: `"${EMBEDINATOR_PORT_FRONTEND:-3000}:3000"` |
| No SELinux `:z` on bind mounts | `docker-compose.yml` lines 8-9, 61 | Fails on Fedora/RHEL with SELinux enforcing | All bind mounts get `:z` suffix. |
| No log rotation | `docker-compose.yml` (all services) | Docker logs grow unbounded on long-running instances | `json-file` driver, `max-size: "50m"`, `max-file: "3"` per service. |
| Separate `addgroup`/`adduser` layers | `frontend/Dockerfile` lines 22-23 | Two layers instead of one | Combined into single `RUN` layer. |

---

## Testing Strategy

### Per-Phase Independent Verification

| Phase | How to Verify | Tools |
|-------|--------------|-------|
| Phase 1 | `docker compose config` for all overlay combinations | `docker compose` CLI |
| Phase 2 | `cd frontend && npm run build && npm run test` | Node.js |
| Phase 3 | `python -c "from backend.api.health import router"` + test runner | Python import + external test runner |
| Phase 4 | `bash -n embedinator.sh` + `--help` output | Bash |
| Phase 5 | `cd frontend && npm run build && npm run test` | Node.js |
| Phase 6 | `python -c "from backend.main import create_app"` + .env.example grep | Python import |
| Phase 7 | Full SC-001 through SC-010 matrix | All tools combined |

### SC-to-Phase Mapping

| SC | Primary Phase | Supporting Phases | Full Verification Requires |
|----|-------------|-------------------|---------------------------|
| SC-001 | Phase 4 (launcher) | Phase 1 (compose), Phase 3 (health) | Running Docker stack |
| SC-002 | Phase 4 (launcher) | Phase 1 (compose) | Windows environment |
| SC-003 | Phase 4 (launcher) | Phase 1 (GPU overlays) | GPU hardware or mock |
| SC-004 | Phase 4 (launcher) | Phase 1 (port interpolation) | Running Docker stack |
| SC-005 | Phase 2 (rewrites) | Phase 1 (compose BACKEND_URL) | Running Docker stack |
| SC-006 | Phase 3 (health) | -- | Backend running with/without Ollama |
| SC-007 | Phase 5 (degraded UI) | Phase 3 (health response) | Full stack running |
| SC-008 | Phase 4 (launcher) | -- | Docker running, no host Python |
| SC-009 | Phase 4 (launcher) | Phase 3 (health endpoints) | Running Docker stack (subsequent launch) |
| SC-010 | ALL | -- | `diff` Makefile against HEAD |

### Regression Testing

- **Backend**: `zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/`
  - Gate: zero new failures vs 39 pre-existing baseline
  - ONE target per invocation
- **Frontend**: `cd frontend && npm run test`
  - Gate: all tests pass (53/53 from spec-18)
- **E2E**: Manual Docker stack verification (not automated in this spec)

---

## What Does NOT Change

- **Makefile**: All 14 targets preserved EXACTLY as-is. Not one character changed. (SC-010)
- **Backend code structure**: No new Python modules (health.py is enhanced, not new). No new pip packages.
- **Frontend packages**: No new npm packages. SWR, recharts, lucide-react all already installed.
- **Database schema**: No changes to SQLite or Qdrant.
- **Existing tests**: 1487+ backend tests and 53 frontend tests unaffected.
- **Backend config.py**: No changes. The `EMBEDINATOR_PORT_*` variables are for Docker Compose interpolation, not Pydantic Settings.

---

## Appendix: Complete File Impact Map

### Files to CREATE (12)

| File | Phase | Agent | Purpose |
|------|-------|-------|---------|
| `embedinator.sh` | 4 | A4 | Bash/zsh launcher (macOS + Linux) |
| `embedinator.ps1` | 4 | A4 | PowerShell launcher (Windows) |
| `docker-compose.gpu-nvidia.yml` | 1 | A1 | NVIDIA GPU overlay |
| `docker-compose.gpu-amd.yml` | 1 | A1 | AMD ROCm GPU overlay |
| `docker-compose.gpu-intel.yml` | 1 | A1 | Intel Arc GPU overlay |
| `.gitattributes` | 1 | A1 | Line ending enforcement |
| `frontend/.dockerignore` | 1 | A1 | Build context exclusion |
| `frontend/app/healthz/route.ts` | 2 | A2 | Frontend health endpoint |
| `frontend/app/page.tsx` | 2 | A2 | Root redirect to /chat |
| `frontend/components/BackendStatusProvider.tsx` | 5 | A5 | React context for backend health |
| `frontend/components/StatusBanner.tsx` | 5 | A5 | Global degraded state banner |
| `specs/019-cross-platform-dx/validation-report.md` | 7 | A7 | SC validation report |

### Files to MODIFY (15)

| File | Phase | Agent | Summary of Changes |
|------|-------|-------|--------------------|
| `docker-compose.yml` | 1 | A1 | Remove GPU block, add health checks, SELinux `:z`, log rotation, port interpolation, `BACKEND_URL` |
| `docker-compose.dev.yml` | 1 | A1 | Fix volume mounts, `target: deps`, `BACKEND_URL` |
| `Dockerfile.backend` | 1 | A1 | Fixed UID 1000, tini, cross-encoder pre-download |
| `frontend/Dockerfile` | 1 | A1 | Pin Node 22, combine layers |
| `frontend/next.config.ts` | 2 | A2 | Remove `env` block, add `rewrites()` |
| `frontend/lib/api.ts` | 2 | A2 | Change `API_BASE` to empty string |
| `backend/api/health.py` | 3 | A3 | Add liveness, enhance readiness, model availability |
| `backend/agent/schemas.py` | 3 | A3 | Extend health response types |
| `backend/middleware.py` | 3 | A3 | Suppress health request logs |
| `backend/main.py` | 3+6 | A3, A6 | A3: upload dir, write-access, soft Ollama. A6: shutdown flag, WAL checkpoint, checkpointer close. |
| `frontend/app/layout.tsx` | 5 | A5 | Wrap with BackendStatusProvider |
| `frontend/components/SidebarLayout.tsx` | 5 | A5 | Insert StatusBanner |
| `frontend/components/ChatInput.tsx` | 5 | A5 | Backend status gating |
| `frontend/components/ChatPanel.tsx` | 5 | A5 | Onboarding card |
| `.env.example` | 6 | A6 | Add Docker/launcher variables |

### Files to PRESERVE (must not be modified)

| File | Reason |
|------|--------|
| `Makefile` | SC-010 -- all 14 targets identical |
| `frontend/lib/types.ts` | Only additive changes by A5 (new types, no removals) |
| All files in `backend/` not listed above | No new modules, no structural changes |
| All files in `tests/` | No test changes in this spec |

### Shared File Coordination (backend/main.py)

`backend/main.py` is modified by TWO agents in different waves:
- **A3 (Wave 1)**: Adds upload dir creation (FR-044), write-access test (FR-045), soft Ollama dependency. Changes happen in the startup section of `lifespan()` (before `yield`, approximately lines 120-130).
- **A6 (Wave 2)**: Adds `shutting_down` flag, WAL checkpoint, checkpointer close. Changes happen at start of `lifespan()` (flag init) and in the shutdown section (after `yield`, lines 224-229).

Because A3 runs in Wave 1 and A6 runs in Wave 2, there is no parallel conflict. A6 will see A3's changes and build on top of them.
