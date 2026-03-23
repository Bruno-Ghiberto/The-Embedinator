# Tasks: Cross-Platform Developer Experience

**Input**: Design documents from `/specs/019-cross-platform-dx/`
**Prerequisites**: plan.md, spec.md, data-model.md, research.md, quickstart.md
**Implementation plan**: `Docs/PROMPTS/spec-19-cross-platform/19-plan.md`

**Organization**: Tasks follow the 7-phase implementation plan structure. User stories are mapped to phases via [US*] labels. Foundational phases (2-4) are blocking prerequisites that enable all user stories.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1-US7)
- Exact file paths included in all descriptions

---

## Phase 1: Setup

**Purpose**: Cross-platform hardening files that must exist before any other work

- [X] T001 Create `.gitattributes` at repository root enforcing LF for `*.sh`, `*.py`, `*.ts`, `*.tsx`, `*.json`, `*.yaml`, `*.yml`, `Makefile`, `Dockerfile*`, `docker-compose*.yml` and CRLF for `*.ps1` (FR-053)
- [X] T002 [P] Create `frontend/.dockerignore` excluding `node_modules`, `.next`, `test-results`, `tests`, `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`, `.git`, `README.md` (FR-042)

---

## Phase 2: Foundational — Docker Infrastructure (A1)

**Purpose**: Compose decomposition, GPU overlays, Dockerfile improvements — foundation everything depends on

**FR ownership**: FR-017 through FR-025, FR-038 through FR-042

### Compose Files

- [X] T003 Modify `docker-compose.yml`: remove NVIDIA `deploy.resources.reservations.devices` block (lines 30-36) from the Ollama service. Replace inline model-pulling entrypoint with `entrypoint: ["ollama", "serve"]` (FR-017)
- [X] T004 Modify `docker-compose.yml`: replace all hardcoded port mappings with Docker Compose variable interpolation — `"${EMBEDINATOR_PORT_FRONTEND:-3000}:3000"` for frontend, `"${EMBEDINATOR_PORT_BACKEND:-8000}:8000"` for backend, `"${EMBEDINATOR_PORT_QDRANT:-6333}:6333"` and `"${EMBEDINATOR_PORT_QDRANT_GRPC:-6334}:6334"` for Qdrant, `"${EMBEDINATOR_PORT_OLLAMA:-11434}:11434"` for Ollama (FR-019)
- [X] T005 Modify `docker-compose.yml`: add `:z` SELinux suffix to all bind mount volumes — `./data:/data:z`, `./data/qdrant_db:/qdrant/storage:z`. Ensure Qdrant uses bind mount (not named volume) per user decision (FR-020, FR-022)
- [X] T006 Modify `docker-compose.yml`: add `logging:` block to ALL 4 services with `driver: "json-file"`, `options: { max-size: "50m", max-file: "3" }` (FR-021)
- [X] T008 Modify `docker-compose.yml`: add `depends_on: backend: condition: service_healthy` to the frontend service (FR-023)
- [X] T009 Modify `docker-compose.yml`: add `stop_grace_period: 15s` to the backend service (FR-024)
- [X] T010 Modify `docker-compose.yml`: replace frontend environment `NEXT_PUBLIC_API_URL=http://backend:8000` with `BACKEND_URL=http://backend:8000` (FR-026)
- [X] T011 Modify `docker-compose.yml`: add frontend health check — `test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/healthz"]`, `interval: 10s`, `timeout: 5s`, `retries: 3`, `start_period: 30s` (FR-030)
- [X] T012 Modify `docker-compose.yml`: change backend health check from `curl -f http://localhost:8000/api/health` to `curl -f http://localhost:8000/api/health/live` (FR-033)

### GPU Overlay Files

- [X] T013 [P] Create `docker-compose.gpu-nvidia.yml` with Ollama service `deploy.resources.reservations.devices` block for NVIDIA GPU (FR-018)
- [X] T014 [P] Create `docker-compose.gpu-amd.yml` swapping Ollama image to `ollama/ollama:rocm` and adding `devices: ["/dev/kfd:/dev/kfd", "/dev/dri:/dev/dri"]` (FR-018)
- [X] T015 [P] Create `docker-compose.gpu-intel.yml` adding `devices: ["/dev/dri:/dev/dri"]` to Ollama service (FR-018)

### Dev Overlay Fix

- [X] T016 [US5] Modify `docker-compose.dev.yml`: fix broken frontend volume mounts — replace `./frontend/src:/app/src` with individual mounts for `app/`, `components/`, `hooks/`, `lib/`, `public/`, `next.config.ts`, `tsconfig.json`. Add anonymous volumes for `/app/node_modules` and `/app/.next`. Use `target: deps` for frontend build. Override frontend command to `npx next dev --hostname 0.0.0.0`. Replace `NEXT_PUBLIC_API_URL` with `BACKEND_URL=http://backend:8000` (FR-025)

### Dockerfile Improvements

- [X] T017 [P] Modify `Dockerfile.backend`: change user creation from dynamic UID to fixed UID/GID 1000 — `RUN addgroup --system --gid 1000 appgroup && adduser --system --uid 1000 --gid 1000 --no-create-home appuser` (FR-038)
- [X] T018 [P] Modify `Dockerfile.backend`: install `tini` via `apt-get install -y --no-install-recommends tini`, change `ENTRYPOINT ["tini", "--"]`, keep `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]` (FR-039)
- [X] T019 Modify `Dockerfile.backend`: add `ENV HF_HOME=/app/.cache/huggingface` and `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` AFTER the `pip install` step to pre-download the cross-encoder model (FR-040)
- [X] T020 [P] Modify `frontend/Dockerfile`: change base image from `node:lts-alpine` to `node:22-alpine`. Combine separate `addgroup`/`adduser` RUN commands into a single layer (FR-041)

### Phase 2 Verification

- [X] T021 Verify all compose overlay combinations parse: `docker compose config`, `docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config`, AMD overlay, Intel overlay, dev overlay. Verify Makefile is unchanged via `diff <(git show HEAD:Makefile) Makefile`

**Checkpoint**: Docker infrastructure ready. All compose configs valid. Dockerfiles improved. Makefile untouched (SC-010).

---

## Phase 3: Foundational — Frontend API Routing Fix (A2)

**Purpose**: Fix the #1 cross-platform bug — `NEXT_PUBLIC_API_URL` build-time baking

**FR ownership**: FR-026 through FR-031
**Can run in parallel with Phase 2 and Phase 4** (zero file overlap)

- [X] T022 [P] Modify `frontend/next.config.ts`: remove the `env: { NEXT_PUBLIC_API_URL: ... }` block (lines 6-8). Add `async rewrites()` returning `[{ source: "/api/:path*", destination: "${process.env.BACKEND_URL || "http://localhost:8000"}/api/:path*" }]` (FR-027)
- [X] T023 [P] Modify `frontend/lib/api.ts`: change line 17 from `const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` to `const API_BASE = process.env.NEXT_PUBLIC_API_URL || ""` (FR-028)
- [X] T024 [P] Create `frontend/app/healthz/route.ts`: Next.js App Router route handler returning `NextResponse.json({ status: "ok" })` with HTTP 200 (FR-029)
- [X] T025 [P] Create `frontend/app/page.tsx`: server component that calls `redirect("/chat")` from `next/navigation` (FR-031)
- [X] T026 Verify frontend builds and tests pass: `cd frontend && npm run build && npm run test`. Verify `grep -q 'rewrites' frontend/next.config.ts` and `grep -q 'BACKEND_URL' frontend/next.config.ts` (SC-005)

**Checkpoint**: Frontend API routing fixed. Browser uses relative paths. Rewrites proxy to backend. Health endpoint exists.

---

## Phase 4: Foundational — Backend Health Enhancement (A3)

**Purpose**: Liveness/readiness separation, model availability, log suppression, startup resilience

**FR ownership**: FR-032 through FR-037, FR-044, FR-045
**Can run in parallel with Phase 2 and Phase 3** (zero file overlap)

- [X] T027 [P] Modify `backend/agent/schemas.py`: extend `HealthResponse.status` to `Literal["healthy", "degraded", "starting"]`. Add optional `models: dict[str, bool] | None = None` field to `HealthServiceStatus` for Ollama model reporting (FR-034, FR-035)
- [X] T028 Modify `backend/api/health.py`: add `GET /api/health/live` endpoint returning `{"status": "alive"}` unconditionally with HTTP 200 — no dependency probes (FR-032)
- [X] T029 Modify `backend/api/health.py`: enhance `_probe_ollama()` to parse the `/api/tags` response body, check whether `settings.default_llm_model` and `settings.default_embed_model` are present in the model list, and include a `models` dict in the Ollama service status (FR-034)
- [X] T030 Modify `backend/api/health.py`: add `"starting"` status logic — return `starting` when it's the first probe after backend startup (before any dependency has been checked) (FR-035)
- [X] T031 [P] Modify `backend/middleware.py`: add path exclusion set `{"/api/health", "/api/health/live"}` at the top of `RequestLoggingMiddleware.dispatch()` — skip logging for these paths (FR-036)
- [X] T032 Modify `backend/main.py`: add `Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)` in `lifespan()` startup, before the SQLite init (FR-044)
- [X] T033 Modify `backend/main.py`: add write-access test after upload dir creation — create and remove a temp file in the data dir, exit with `SystemExit(1)` and a clear log message if `PermissionError` (FR-045)
- [X] T034 Document FR-037 (circuit breaker bypass): verify that health probes in `health.py` use direct `httpx` calls and do NOT go through `HybridSearcher` circuit breaker. Add a code comment in `health.py` noting this design choice (FR-037)
- [X] T035 Verify: `python -c "from backend.api.health import router"` succeeds. Verify health module has both endpoints registered

**Checkpoint**: Backend has liveness + enhanced readiness endpoints. Model availability reported. Health logs suppressed. Upload dir created. Write-access tested.

---

## GATE CHECK 1 (Orchestrator)

**All three foundational phases (2, 3, 4) must pass before proceeding.**

- [ ] T036 Run Gate Check 1: (1) `docker compose config > /dev/null` for all overlay combos, (2) `cd frontend && npm run build && npm run test`, (3) `python -c "from backend.api.health import router"`, (4) `diff <(git show HEAD:Makefile) Makefile` shows zero changes

---

## Phase 5: US1+US2+US3+US4+US5 — Launcher Scripts (A4)

**Goal**: Create the `embedinator.sh` and `embedinator.ps1` launcher scripts — the single-command entry point for all user stories

**Independent Test**: Run `./embedinator.sh --help` and verify it prints usage. Run `bash -n embedinator.sh` for syntax validation.

**FR ownership**: FR-001 through FR-016, FR-054, FR-055, FR-056
**SC coverage**: SC-001, SC-002, SC-003, SC-004, SC-008, SC-009
**Depends on**: Phase 2 (compose files must be correct)

### embedinator.sh (bash/zsh)

- [X] T037 [US1] Create `embedinator.sh`: implement CLI argument parsing for all subcommands — `--dev`, `--stop`, `--restart`, `--logs [service]`, `--status`, `--open`, `--help`, `--frontend-port PORT`, `--backend-port PORT` (FR-001, FR-002, FR-003)
- [X] T038 [US1] Implement `--help` subcommand in `embedinator.sh`: print usage with all flags and examples (FR-002)
- [X] T039 [US2] Implement `--stop` subcommand: run `docker compose down` with the correct `-f` flags for the detected compose files (FR-002)
- [X] T040 [US2] Implement `--restart` subcommand: stop then fall through to the start flow (FR-002)
- [X] T041 [US2] Implement `--logs [service]` subcommand: run `docker compose logs -f [service]` (FR-002)
- [X] T042 [US2] Implement `--status` subcommand: poll health endpoints using configured ports, print per-service status table (FR-002)
- [X] T043 [US1] Implement preflight checks in `embedinator.sh`: (1) Docker daemon via `docker info`, (2) Docker Compose v2 via `docker compose version`, (3) port availability for all configured ports, (4) disk space warning < 15GB, (5) macOS Docker VM memory warning < 4GB, (6) Linux Docker group check (FR-054), (7) WSL2 `/mnt/c/` warning (FR-055), (8) macOS GPU info message (FR-056) (FR-004)
- [X] T044 [US3] Implement GPU detection in `embedinator.sh`: priority order NVIDIA (`nvidia-smi` + `docker info | grep nvidia`) > AMD (`/dev/kfd` + `rocminfo`) > Intel (`/dev/dri/renderD*`) > CPU. `EMBEDINATOR_GPU` env var override. macOS always CPU with info message (FR-005, FR-006, FR-007)
- [X] T045 [US1] Implement `.env` generation in `embedinator.sh`: copy `.env.example` to `.env` if not exists, generate Fernet key via `docker run --rm python:3.14-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, inject into `.env` (FR-008)
- [X] T046 [US4] Implement port override logic in `embedinator.sh`: apply CLI `--frontend-port` / `--backend-port` flags to env vars, export for Docker Compose interpolation (FR-003)
- [X] T047 [US1] Implement CORS auto-detection in `embedinator.sh`: detect LAN IP, write `CORS_ORIGINS=http://localhost:{port},http://127.0.0.1:{port},http://{lan_ip}:{port}` to `.env` (FR-009)
- [X] T048 [US1] Implement data directory creation in `embedinator.sh`: `mkdir -p data/uploads data/qdrant_db` before compose up (FR-010)
- [X] T049 [US1] Implement idempotency check in `embedinator.sh`: if `docker compose ps` shows running services, skip build and report status (FR-015)
- [X] T050 [US1] Implement compose orchestration in `embedinator.sh`: select compose files based on GPU profile + `--dev` flag, run `docker compose -f ... up --build -d` (FR-001)
- [X] T051 [US1] Implement health polling in `embedinator.sh`: poll Qdrant, Ollama, backend, frontend health endpoints using configured host ports. Print per-service status line with in-place overwrite. Timeout 300s first run, 60s subsequent (FR-011)
- [X] T052 [US1] Implement model pull in `embedinator.sh`: after health checks pass, check `docker compose exec ollama ollama list` for each model in `OLLAMA_MODELS`. Pull missing models with progress passthrough (FR-012, FR-013)
- [X] T053 [US1] Implement browser open in `embedinator.sh`: when `--open` flag is set, open `http://localhost:${FRONTEND_PORT}` via `open` (macOS) / `xdg-open` (Linux) (FR-014)
- [X] T054 [US4] Implement port conflict detection in `embedinator.sh`: check configured ports before starting, identify conflicting process if possible, suggest `--frontend-port` / `--backend-port` as resolution (FR-016)
- [X] T055 [US1] Implement ready message in `embedinator.sh`: print URL, `--logs` command, `--stop` command after all health checks and model pulls complete

### embedinator.ps1 (PowerShell)

- [X] T056 [US1] Create `embedinator.ps1`: implement identical logic to `embedinator.sh` with PowerShell-native syntax — `param()` block for CLI flags, `docker info 2>$null` for Docker check, `Test-NetConnection` for port checks, `Invoke-RestMethod` for health polling, `Start-Process` for browser open (FR-001)
- [X] T057 [US1] Implement all subcommands in `embedinator.ps1`: `-Help`, `-Stop`, `-Restart`, `-Logs [service]`, `-Status`, `-Open`, `-Dev`, `-FrontendPort PORT`, `-BackendPort PORT` (FR-002, FR-003)
- [X] T058 [US3] Implement GPU detection in `embedinator.ps1`: NVIDIA only via `nvidia-smi` in WSL2; AMD/Intel always fall back to CPU on Windows (FR-005, FR-006)
- [X] T059 [US1] Implement `.env` generation, CORS auto-detection, data dir creation, health polling, model pull, and ready message in `embedinator.ps1` — same logic as bash script with PowerShell equivalents (FR-008 through FR-016)

### Phase 5 Verification

- [X] T060 Verify `bash -n embedinator.sh` passes (syntax check). Verify `./embedinator.sh --help` prints usage with all documented flags and subcommands

**Checkpoint**: Launcher scripts complete. First-time launch (US1), daily operations (US2), GPU detection (US3), custom ports (US4), and dev mode (US5) all functional.

---

## Phase 6: US6 — Frontend Degraded States (A5)

**Goal**: Show informative status when the backend is starting up or models are still downloading

**Independent Test**: Start services, immediately open browser, verify status banner appears. Wait for healthy, verify banner disappears and chat input enables.

**FR ownership**: FR-046, FR-047, FR-048, FR-049
**SC coverage**: SC-007
**Depends on**: Phase 4 (enhanced `/api/health` response)

- [X] T061 [P] [US6] Add `BackendStatus` type to `frontend/lib/types.ts`: `type BackendStatus = "unreachable" | "degraded" | "ready"` and `BackendHealthResponse` interface matching the enhanced `/api/health` response (FR-046)
- [X] T062 [US6] Create `frontend/components/BackendStatusProvider.tsx`: React context using SWR to poll `/api/health` with adaptive intervals (5s unreachable, 10s degraded, 30s ready). Export `useBackendStatus()` hook returning `{ state, services }`. Handle fetch errors as `unreachable` (FR-046)
- [X] T063 [US6] Create `frontend/components/StatusBanner.tsx`: non-dismissible banner with contextual messages per degraded state. Use `role="status"` and `aria-live="polite"`. Use existing design tokens (CSS variables), not hardcoded colors. Auto-hide when status becomes `ready` (FR-047)
- [X] T064 [US6] Modify `frontend/app/layout.tsx`: wrap `SidebarLayout` with `BackendStatusProvider` inside `ThemeProvider`. Provider order: `ThemeProvider > BackendStatusProvider > SidebarLayout` (FR-046)
- [X] T065 [US6] Modify `frontend/components/SidebarLayout.tsx`: import and render `StatusBanner` between the `<header>` and `<main>` inside `SidebarInset` (FR-047)
- [X] T066 [US6] Modify `frontend/components/ChatInput.tsx`: import `useBackendStatus()`, add backend status to `canSend` check (disabled when not `ready`), change placeholder to contextual: "Waiting for backend to start..." / "AI models are still loading..." / "Vector database is starting..." / current placeholder when ready (FR-048)

### First-Run Onboarding (US7)

- [X] T067 [US7] Modify `frontend/components/ChatPanel.tsx`: when zero collections exist (check via existing SWR collections hook), replace the standard empty state with an onboarding card showing: (1) "Create a collection" button linking to `/collections`, (2) "Upload documents" with supported formats, (3) "Ask questions" explanation. When collections exist, show standard starter questions (FR-049)

### Phase 6 Verification

- [X] T068 Verify `cd frontend && npm run build && npm run test` passes. Verify `BackendStatusProvider` is in `layout.tsx`, `StatusBanner` is in `SidebarLayout.tsx`, `useBackendStatus` is in `ChatInput.tsx`

**Checkpoint**: Frontend shows informative degraded-state banners (US6). First-run onboarding guides new users (US7).

---

## Phase 7: Cross-Cutting — Graceful Shutdown + Environment (A6)

**Purpose**: Shutdown resilience and `.env.example` documentation

**FR ownership**: FR-043, FR-050, FR-051, FR-052
**Can run in parallel with Phases 5 and 6** (zero file overlap)

- [X] T069 Modify `backend/main.py`: add `app.state.shutting_down = False` at the start of `lifespan()` (before `yield`). Set `app.state.shutting_down = True` at start of the shutdown section (after `yield`) (FR-050)
- [X] T070 Modify `backend/api/chat.py`: add early return at the top of the chat endpoint — if `request.app.state.shutting_down`, yield NDJSON error `{"type": "error", "code": "SHUTTING_DOWN", "message": "Server is shutting down. Please retry in a moment."}` and return (FR-050)
- [X] T071 Modify `backend/main.py`: in the shutdown section, add `await db.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")` for the main SQLite database BEFORE `await db.close()` (FR-051)
- [X] T072 Modify `backend/main.py`: in the shutdown section, open the checkpoints DB, execute `PRAGMA wal_checkpoint(TRUNCATE)`, close connection. Then explicitly close the LangGraph checkpointer connection via `checkpointer.conn.close()` (FR-051, FR-052)
- [X] T073 Modify `.env.example`: add a new `Docker / Launcher` section at the TOP of the file with documented entries for `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, and all 5 `EMBEDINATOR_PORT_*` variables with defaults and descriptions. Include comment explaining these are NOT read by Pydantic Settings (FR-043)

### Phase 7 Verification

- [X] T074 Verify `python -c "from backend.main import create_app"` succeeds. Verify `.env.example` contains all 8 new variables via grep

**Checkpoint**: Graceful shutdown protects in-flight requests and database integrity. `.env.example` documents all new configuration.

---

## GATE CHECK 2 (Orchestrator)

**Phases 5, 6, 7 must all pass before validation.**

- [ ] T075 Run Gate Check 2: (1) `bash -n embedinator.sh` passes, (2) `cd frontend && npm run build && npm run test`, (3) `python -c "from backend.main import create_app"`, (4) `diff <(git show HEAD:Makefile) Makefile` zero changes

---

## Phase 8: Validation & Cross-Platform Testing (A7)

**Purpose**: Verify all 10 success criteria pass. Write validation report.

- [X] T076 Validate SC-001: verify `docker compose config` parses for base and all overlays. Verify all 4 service definitions present with correct health checks
- [X] T077 Validate SC-002: verify `embedinator.ps1` syntax with `pwsh -NoProfile -Command "& { Get-Help ./embedinator.ps1 }"` (or syntax check if pwsh not available)
- [X] T078 Validate SC-003: verify GPU detection logic in `embedinator.sh` — trace the NVIDIA/AMD/Intel/CPU code paths. Verify macOS always returns `none`
- [X] T079 Validate SC-004: verify Docker Compose variable interpolation — `EMBEDINATOR_PORT_FRONTEND=4000 docker compose config` shows `4000:3000` port mapping
- [X] T080 Validate SC-005: verify `frontend/next.config.ts` contains `rewrites()`, `frontend/lib/api.ts` has empty-string `API_BASE`, no `NEXT_PUBLIC_API_URL` in `docker-compose.yml`
- [X] T081 Validate SC-006: verify `backend/api/health.py` Ollama probe parses model list and reports availability in response
- [X] T082 Validate SC-007: verify `BackendStatusProvider`, `StatusBanner`, and chat input gating are wired up — check imports in `layout.tsx`, `SidebarLayout.tsx`, `ChatInput.tsx`
- [X] T083 Validate SC-008: verify `embedinator.sh` generates Fernet key via Docker container without local Python — trace the key generation code path
- [X] T084 Validate SC-009: verify health polling timeout logic — 300s first run, 60s subsequent — in `embedinator.sh`
- [X] T085 Validate SC-010: `diff <(git show HEAD:Makefile) Makefile` MUST show zero changes
- [X] T086 Run frontend regression: `cd frontend && npm run build && npm run test` — all tests must pass (53/53 from spec-18 baseline)
- [X] T087 Run backend regression: `zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/` — zero new failures vs 39 pre-existing baseline
- [X] T088 Verify no new npm/pip packages added: compare `frontend/package.json` and `requirements.txt` against HEAD
- [X] T089 Create `specs/019-cross-platform-dx/validation-report.md` documenting all 10 SC results with PASS/FAIL status

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup ──────────────> (no deps)
Phase 2: Docker Infra ───────> depends on Phase 1
Phase 3: Frontend Routing ───> depends on Phase 1 (can parallel with Phase 2)
Phase 4: Backend Health ─────> depends on Phase 1 (can parallel with Phase 2, 3)
GATE CHECK 1 ────────────────> depends on Phases 2, 3, 4
Phase 5: Launcher Scripts ───> depends on GATE CHECK 1 (needs correct compose files)
Phase 6: Frontend Degraded ──> depends on GATE CHECK 1 (needs enhanced health endpoint)
Phase 7: Shutdown + Env ─────> depends on GATE CHECK 1 (can parallel with Phases 5, 6)
GATE CHECK 2 ────────────────> depends on Phases 5, 6, 7
Phase 8: Validation ─────────> depends on GATE CHECK 2
```

### User Story Dependencies

| Story | Primary Phase | Can Start After |
|-------|--------------|----------------|
| **US1** (First-Time Launch) | Phase 5 (launcher) | Gate Check 1 |
| **US2** (Daily Start/Stop) | Phase 5 (launcher) | Gate Check 1 |
| **US3** (GPU Detection) | Phase 2 (overlays) + Phase 5 (detection) | Gate Check 1 for detection |
| **US4** (Custom Ports) | Phase 2 (interpolation) + Phase 5 (flags) | Gate Check 1 for flags |
| **US5** (Dev Mode) | Phase 2 (dev overlay) + Phase 5 (--dev) | Gate Check 1 for --dev |
| **US6** (Degraded Startup) | Phase 6 (frontend) | Gate Check 1 |
| **US7** (Onboarding) | Phase 6 (frontend) | Gate Check 1 |

### Parallel Opportunities

**Wave 1** (after Phase 1 setup):
- Phase 2 (A1: Docker) + Phase 3 (A2: Frontend routing) + Phase 4 (A3: Backend health) — **3 agents in parallel, zero file overlap**

**Wave 2** (after Gate Check 1):
- Phase 5 (A4: Launcher) + Phase 6 (A5: Frontend degraded) + Phase 7 (A6: Shutdown) — **3 agents in parallel, zero file overlap**

**Wave 3** (after Gate Check 2):
- Phase 8 (A7: Validation) — solo

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phases 2-4: Foundational (parallel)
3. Gate Check 1
4. Complete Phase 5: Launcher Scripts (embedinator.sh only — skip .ps1 for MVP)
5. **STOP and VALIDATE**: `./embedinator.sh` works end-to-end on Linux

### Incremental Delivery

1. Setup + Foundational (Phases 1-4) → Docker infra correct, routing fixed, health enhanced
2. Launcher (Phase 5) → US1-US5 all functional → **Core delivery**
3. Frontend degraded states (Phase 6) → US6+US7 → **Polish delivery**
4. Shutdown + env (Phase 7) → Cross-cutting resilience
5. Validation (Phase 8) → All 10 SCs documented

### Agent Teams Execution

See `Docs/PROMPTS/spec-19-cross-platform/19-plan.md` for the full 7-agent, 3-wave execution plan with per-agent instruction file specs.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [US*] label maps task to specific user story for traceability
- **Makefile is NEVER modified** — SC-010 verified at every gate check
- **No new packages** — spec explicitly prohibits new pip/npm dependencies
- **`backend/main.py` shared**: A3 modifies startup (Wave 1), A6 modifies shutdown (Wave 2) — no parallel conflict
- Total: **88 tasks** across 8 phases + 2 gate checks (T007 merged into T005)
