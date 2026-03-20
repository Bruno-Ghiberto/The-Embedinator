# Spec 19: Cross-Platform Developer Experience — Implementation Context

```
# MANDATORY: TMUX MULTI-PANE SPAWNING REQUIRED
# Agent Teams MUST run in tmux. Each wave agent gets its own pane.
# Use TeamCreate → TaskCreate → Agent(team_name=...) → SendMessage
# NEVER spawn agents/subagents in the same pane. Each agent = separate tmux pane.
```

---

## What This Spec Does

Spec-19 transforms The Embedinator from a multi-command, toolchain-dependent setup into
a single-command, cross-platform application. Users run `./embedinator.sh` (macOS/Linux)
or `.\embedinator.ps1` (Windows) and the entire stack builds, configures, downloads AI
models, and reports readiness. Docker Desktop is the only prerequisite.

**Scope**: 88 tasks (T001–T089, T007 merged into T005), 56 FRs across 9 areas, 10 SCs.
**Full-stack**: Docker infrastructure, backend health, frontend routing + degraded states,
launcher scripts, cross-platform hardening, graceful shutdown.

---

## Authoritative Files — Read Order

Every agent MUST read its own instruction file FIRST, then these shared files:

| Priority | File | Contains |
|----------|------|----------|
| 1 | Agent instruction file (`Docs/PROMPTS/spec-19-cross-platform/agents/A{N}-instructions.md`) | Assigned tasks, detailed orders |
| 2 | `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` | Authoritative design decisions (13 sections, 700 lines) |
| 3 | `specs/019-cross-platform-dx/spec.md` | FR-001 through FR-056, SC-001 through SC-010 |
| 4 | `specs/019-cross-platform-dx/tasks.md` | Canonical task list (T001–T089) |
| 5 | This file (`Docs/PROMPTS/spec-19-cross-platform/19-implement.md`) | Wave structure, stale patterns, gotchas |
| 6 | `specs/019-cross-platform-dx/data-model.md` | Key entities, state machines, env var contracts |

---

## Build Verification Protocol

```
Backend health tests:  Use external runner per MEMORY.md policy — NEVER run pytest directly
  zsh scripts/run-tests-external.sh -n <name> --no-cov <target>
  cat Docs/Tests/<name>.status
  cat Docs/Tests/<name>.summary

Frontend tests:       cd frontend && npm run build && npm run test

Docker validation:    docker compose config > /dev/null 2>&1
                      docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null 2>&1
                      docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml config > /dev/null 2>&1
                      docker compose -f docker-compose.yml -f docker-compose.gpu-intel.yml config > /dev/null 2>&1
                      docker compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null 2>&1

Launcher validation:  bash -n embedinator.sh              # syntax check only (no execution)
                      pwsh -NoProfile -Command "& { Get-Help ./embedinator.ps1 }" 2>/dev/null || true

Health endpoint:      curl -sf http://localhost:8000/api/health/live
                      curl -sf http://localhost:8000/api/health
                      wget --spider http://localhost:3000/healthz 2>/dev/null || curl -sf http://localhost:3000/healthz

Makefile unchanged:   diff <(git show HEAD:Makefile) Makefile  # MUST show zero diff (SC-010)
```

---

## Stale Pattern Warnings — EVERY AGENT MUST KNOW

These are verified facts about the current codebase. Agents encountering these
must treat them as bugs from the pre-spec-19 state, not as correct behavior.

| Current State | Location | What's Wrong | Correct After Spec-19 |
|--------------|----------|-------------|----------------------|
| NVIDIA `deploy` block in base compose | `docker-compose.yml` lines 30-36 | Crashes on macOS, non-NVIDIA Linux/Windows | REMOVED from base. Moved to `docker-compose.gpu-nvidia.yml` |
| Inline model-pulling entrypoint | `docker-compose.yml` line 24 | `ollama serve & sleep 5 && ollama pull...` — fragile | Changed to `entrypoint: ["ollama", "serve"]`. Models pulled by launcher |
| `NEXT_PUBLIC_API_URL=http://backend:8000` | `docker-compose.yml` line 79 | Docker hostname baked into JS bundle | REMOVED. Replaced with `BACKEND_URL=http://backend:8000` |
| `./frontend/src:/app/src` volume mount | `docker-compose.dev.yml` line 19 | `frontend/src/` doesn't exist | Fixed to mount individual frontend dirs |
| `NEXT_PUBLIC_API_URL` in dev overlay | `docker-compose.dev.yml` line 21 | Same baking bug | Replaced with `BACKEND_URL` |
| `API_BASE = ...NEXT_PUBLIC_API_URL... \|\| "http://localhost:8000"` | `frontend/lib/api.ts` line 17 | Absolute URL doesn't work behind Docker | Changed to `...NEXT_PUBLIC_API_URL \|\| ""` (relative paths) |
| `env: { NEXT_PUBLIC_API_URL: ... }` | `frontend/next.config.ts` lines 6-8 | Bakes env var into client bundle | REMOVED. Replaced with `async rewrites()` |
| Dynamic UID in Dockerfile | `Dockerfile.backend` lines 32-34 | Auto-assigned UID may not be 1000 | Fixed to `--uid 1000 --gid 1000` |
| `node:lts-alpine` base image | `frontend/Dockerfile` line 1 | Rolling tag breaks Docker cache | Pinned to `node:22-alpine` |
| No liveness endpoint | `backend/api/health.py` | Only `/api/health` (readiness). Docker restarts container during model downloads | Added `/api/health/live` (liveness). HEALTHCHECK targets liveness |
| Health requests logged | `backend/middleware.py` | Every 10s health check floods logs | Health paths excluded from `RequestLoggingMiddleware` |
| Hardcoded ports | `docker-compose.yml` | Users can't override 3000/8000/6333/6334/11434 | Variable interpolation: `${EMBEDINATOR_PORT_*:-default}:internal` |
| No SELinux `:z` on bind mounts | `docker-compose.yml` | Fails on Fedora/RHEL with SELinux | All bind mounts get `:z` suffix |
| No log rotation | `docker-compose.yml` | Logs grow unbounded | `json-file` driver, `max-size: "50m"`, `max-file: "3"` |
| Separate `addgroup`/`adduser` layers | `frontend/Dockerfile` lines 22-23 | Two layers instead of one | Combined into single `RUN` |
| No `tini` in backend Dockerfile | `Dockerfile.backend` | No proper PID 1 signal forwarding | `tini` installed and set as ENTRYPOINT |

---

## Agent Team Roster

| Agent | Role | Wave | Model | Phase | Tasks | Mission |
|-------|------|------|-------|-------|-------|---------|
| A1 | devops-architect | 1 | Sonnet | 1+Setup | T001–T021 | Docker infra: compose decomposition, GPU overlays, Dockerfiles, .gitattributes, .dockerignore |
| A2 | frontend-architect | 1 | Sonnet | 2 | T022–T026 | Frontend API routing: rewrites, healthz, root redirect, api.ts change |
| A3 | backend-architect | 1 | Sonnet | 3 | T027–T035 | Backend health: liveness, readiness, model availability, log suppression, upload dir, write-access |
| — | *GATE CHECK 1* | 1.5 | Orchestrator | — | T036 | Verify compose configs, frontend build, health module, Makefile unchanged |
| A4 | devops-architect | 2 | Sonnet | 4 | T037–T060 | Launcher scripts: embedinator.sh + embedinator.ps1 (19 FRs, largest work item) |
| A5 | frontend-architect | 2 | Sonnet | 5 | T061–T068 | Frontend degraded states: BackendStatusProvider, StatusBanner, chat gating, onboarding |
| A6 | backend-architect | 2 | Sonnet | 6 | T069–T074 | Graceful shutdown: shutting_down flag, WAL checkpoint, checkpointer close, .env.example |
| — | *GATE CHECK 2* | 2.5 | Orchestrator | — | T075 | Verify launcher syntax, frontend build+test, main.py import, Makefile unchanged |
| A7 | quality-engineer | 3 | Sonnet | 7 | T076–T089 | Full validation: all 10 SCs, regression tests, validation report |

**Total: 7 agents across 3 waves + 2 gate checks.**

---

## Wave Execution Sequence

### Wave 1 — A1, A2, A3 PARALLEL (3 separate tmux panes)

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

**Parallel safety — file touch matrix (Wave 1)**:
- A1: `docker-compose.yml`, `docker-compose.dev.yml`, `docker-compose.gpu-*.yml` (3 new), `Dockerfile.backend`, `frontend/Dockerfile`, `.gitattributes`, `frontend/.dockerignore`
- A2: `frontend/next.config.ts`, `frontend/lib/api.ts`, `frontend/app/healthz/route.ts` (new), `frontend/app/page.tsx` (new)
- A3: `backend/api/health.py`, `backend/agent/schemas.py`, `backend/middleware.py`, `backend/main.py`

**Zero file overlap between A1, A2, A3.**

### Wave 1.5 — GATE CHECK 1 (Orchestrator)

After all 3 agents complete, the orchestrator runs:

```bash
# Phase 1: Docker infrastructure
docker compose config > /dev/null 2>&1 && echo "PASS: base compose" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null 2>&1 && echo "PASS: nvidia" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml config > /dev/null 2>&1 && echo "PASS: amd" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-intel.yml config > /dev/null 2>&1 && echo "PASS: intel" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null 2>&1 && echo "PASS: dev" || echo "FAIL"
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile unchanged" || echo "FAIL: Makefile modified!"

# Phase 2: Frontend routing
cd frontend && npm run build && echo "PASS: frontend build" || echo "FAIL"
cd frontend && npm run test && echo "PASS: frontend tests" || echo "FAIL"
test -f frontend/app/healthz/route.ts && echo "PASS: healthz exists" || echo "FAIL"
test -f frontend/app/page.tsx && echo "PASS: root redirect exists" || echo "FAIL"

# Phase 3: Backend health
python -c "from backend.api.health import router" && echo "PASS: health module" || echo "FAIL"
```

**If any check fails**: Fix issues before proceeding. Do NOT spawn Wave 2 on broken infrastructure.

### Wave 2 — A4, A5, A6 PARALLEL (3 separate tmux panes)

```
Spawn all 3 agents simultaneously:
A4: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A4-instructions.md FIRST, then execute all assigned tasks."
A5: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A5-instructions.md FIRST, then execute all assigned tasks."
A6: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A6-instructions.md FIRST, then execute all assigned tasks."
```

**Parallel safety — file touch matrix (Wave 2)**:
- A4: `embedinator.sh` (new), `embedinator.ps1` (new)
- A5: `frontend/components/BackendStatusProvider.tsx` (new), `frontend/components/StatusBanner.tsx` (new), `frontend/app/layout.tsx`, `frontend/components/SidebarLayout.tsx`, `frontend/components/ChatInput.tsx`, `frontend/components/ChatPanel.tsx`, `frontend/lib/types.ts`
- A6: `backend/main.py`, `backend/api/chat.py`, `.env.example`

**Zero file overlap between A4, A5, A6.**

**Note on `backend/main.py`**: A3 modified it in Wave 1 (startup: upload dir + write-access). A6 modifies it in Wave 2 (shutdown: flag + WAL checkpoint + checkpointer). No conflict — different sections of `lifespan()`.

### Wave 2.5 — GATE CHECK 2 (Orchestrator)

```bash
bash -n embedinator.sh && echo "PASS: launcher syntax" || echo "FAIL"
cd frontend && npm run build && echo "PASS: frontend build" || echo "FAIL"
cd frontend && npm run test && echo "PASS: frontend tests" || echo "FAIL"
python -c "from backend.main import create_app" && echo "PASS: main.py loads" || echo "FAIL"
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile unchanged" || echo "FAIL"
```

### Wave 3 — A7 SOLO (Sequential)

```
A7: "Read Docs/PROMPTS/spec-19-cross-platform/agents/A7-instructions.md FIRST, then execute all assigned tasks."
```

A7 runs the full SC-001 through SC-010 validation matrix, backend + frontend regression tests, and writes `specs/019-cross-platform-dx/validation-report.md`.

---

## Risk Gotchas — EVERY AGENT MUST KNOW

1. **Makefile is SACRED** — SC-010 requires zero changes. `diff <(git show HEAD:Makefile) Makefile` is checked at every gate. If an agent accidentally modifies it, the gate fails.

2. **NDJSON streaming through rewrites** — Next.js rewrites operate at HTTP level and should NOT buffer. But if streaming breaks in testing, the fallback is to keep `NEXT_PUBLIC_API_URL` as an environment variable that bypasses rewrites for the streaming endpoint. A2 must verify this works.

3. **`tini` installation** — Must use `apt-get install -y --no-install-recommends tini` in the `python:3.14-slim` based Dockerfile. Verify the package is available in that base image.

4. **Cross-encoder pre-download ordering** — The `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('...')"` line MUST come AFTER `pip install -r requirements.txt`. If placed before, it fails because `sentence-transformers` isn't installed yet.

5. **PowerShell parity** — `embedinator.ps1` is the hardest deliverable. A4 should implement `embedinator.sh` FIRST (bash is the primary target), then translate to PowerShell. Port detection, GPU detection, and health polling all need PowerShell-native equivalents.

6. **`backend/main.py` multi-touch** — A3 modifies startup (Wave 1, before `yield` in `lifespan()`). A6 modifies shutdown (Wave 2, after `yield`). These are in different waves so no parallel conflict. A6 will see A3's changes.

7. **Frontend test mocks** — After changing `API_BASE` to empty string, existing frontend tests that mock API calls may need their mock URLs updated. A2 must verify all 53 frontend tests pass after the change.

8. **No new packages** — The spec explicitly forbids new pip or npm packages. All changes use existing dependencies (SWR for polling, existing fetch for health, etc.).

9. **`.env.example` append only** — A6 adds a new "Docker / Launcher" section at the TOP. The existing 28 Settings fields below MUST NOT be modified. Docker Compose reads `EMBEDINATOR_PORT_*` from `.env` — these are NOT Pydantic Settings fields.

10. **SELinux `:z` on bind mounts only** — The `:z` suffix goes on bind-mounted directories (`./data:/data:z`), NOT on named volumes (`ollama_models:/root/.ollama`). Named volumes don't need SELinux relabeling.

---

## Files to Create vs Modify vs Preserve

### CREATE (12 files)

| File | Agent | Wave | FR |
|------|-------|------|----|
| `docker-compose.gpu-nvidia.yml` | A1 | 1 | FR-018 |
| `docker-compose.gpu-amd.yml` | A1 | 1 | FR-018 |
| `docker-compose.gpu-intel.yml` | A1 | 1 | FR-018 |
| `.gitattributes` | A1 | 1 | FR-053 |
| `frontend/.dockerignore` | A1 | 1 | FR-042 |
| `frontend/app/healthz/route.ts` | A2 | 1 | FR-029 |
| `frontend/app/page.tsx` | A2 | 1 | FR-031 |
| `embedinator.sh` | A4 | 2 | FR-001–FR-016 |
| `embedinator.ps1` | A4 | 2 | FR-001–FR-016 |
| `frontend/components/BackendStatusProvider.tsx` | A5 | 2 | FR-046 |
| `frontend/components/StatusBanner.tsx` | A5 | 2 | FR-047 |
| `specs/019-cross-platform-dx/validation-report.md` | A7 | 3 | — |

### MODIFY (16 files)

| File | Agent(s) | Wave(s) | Summary |
|------|----------|---------|---------|
| `docker-compose.yml` | A1 | 1 | Remove GPU block, `ollama serve`, port interpolation, SELinux `:z`, log rotation, health checks, `BACKEND_URL`, `depends_on`, `stop_grace_period` |
| `docker-compose.dev.yml` | A1 | 1 | Fix volume mounts, `target: deps`, `BACKEND_URL` |
| `Dockerfile.backend` | A1 | 1 | UID 1000, tini, cross-encoder pre-download, HF_HOME |
| `frontend/Dockerfile` | A1 | 1 | Pin Node 22, combine addgroup/adduser layers |
| `frontend/next.config.ts` | A2 | 1 | Remove `env` block, add `async rewrites()` |
| `frontend/lib/api.ts` | A2 | 1 | Change `API_BASE` to empty string |
| `backend/api/health.py` | A3 | 1 | Add `/api/health/live`, enhance readiness, model availability |
| `backend/agent/schemas.py` | A3 | 1 | Extend health types (`starting`, `models` field) |
| `backend/middleware.py` | A3 | 1 | Suppress health request logs |
| `backend/main.py` | A3, A6 | 1, 2 | A3: upload dir + write-access (startup). A6: shutdown flag + WAL checkpoint + checkpointer close |
| `frontend/app/layout.tsx` | A5 | 2 | Wrap with `BackendStatusProvider` |
| `frontend/components/SidebarLayout.tsx` | A5 | 2 | Insert `StatusBanner` |
| `frontend/components/ChatInput.tsx` | A5 | 2 | Backend status gating |
| `frontend/components/ChatPanel.tsx` | A5 | 2 | First-run onboarding card |
| `frontend/lib/types.ts` | A5 | 2 | Add `BackendStatus` types |
| `backend/api/chat.py` | A6 | 2 | Shutdown rejection NDJSON error |
| `.env.example` | A6 | 2 | Add Docker/launcher vars at top |

### PRESERVE (must NOT be modified by any agent)

| File | Reason |
|------|--------|
| `Makefile` | SC-010 — all 14 targets unchanged. Verified at every gate check. |
| `backend/config.py` | No Settings changes. `EMBEDINATOR_PORT_*` vars are for Compose, not Pydantic. |
| `requirements.txt` | No new Python packages. |
| `frontend/package.json` | No new npm packages. |
| All `tests/**` files | No test modifications in this spec. |

---

## Success Criteria Verification (Final — A7)

| SC | Check | Phase |
|----|-------|-------|
| SC-001 | `docker compose config` valid for base + all overlays; 4 services defined | 1, 4 |
| SC-002 | `embedinator.ps1` syntax valid; `-Help` prints usage | 4 |
| SC-003 | GPU detection: NVIDIA path returns `nvidia`, macOS returns `none` | 4 |
| SC-004 | `EMBEDINATOR_PORT_FRONTEND=4000 docker compose config` shows `4000:3000` | 1, 4 |
| SC-005 | `next.config.ts` has `rewrites()`, `api.ts` has empty-string `API_BASE` | 2 |
| SC-006 | Health endpoint Ollama probe includes `models` dict in response | 3 |
| SC-007 | `BackendStatusProvider` + `StatusBanner` + chat gating wired in layout/components | 5 |
| SC-008 | Launcher generates `.env` with Fernet key via Docker (no host Python) | 4 |
| SC-009 | Health polling timeout: 300s first-run, 60s subsequent in launcher code | 4 |
| SC-010 | `diff <(git show HEAD:Makefile) Makefile` returns zero diff | ALL |

All 10 must PASS. A7 writes `specs/019-cross-platform-dx/validation-report.md` with PASS/FAIL per SC.

---

## Pre-existing Test Failures

39 pre-existing backend test failures (documented, not regressions). Gate checks compare against this baseline — acceptance criterion is **zero new failures**, not zero total.

53 frontend tests (spec-18 baseline) — all must pass after spec-19 changes.

---

## Agent Instruction File Checklist

Each agent instruction file at `Docs/PROMPTS/spec-19-cross-platform/agents/A{N}-instructions.md` MUST contain:

1. **Role and mission** — one-sentence summary
2. **FR ownership** — exact FR numbers from spec.md
3. **Task ownership** — exact task numbers from tasks.md
4. **Files to create** — with exact paths
5. **Files to modify** — with exact paths and what changes
6. **Files NEVER to touch** — always includes `Makefile`
7. **Must-read documents** — from the Authoritative Files table
8. **Design doc sections** — which sections of `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` to read
9. **Key gotchas** — agent-specific from the Risk Gotchas section
10. **Verification commands** — how to confirm success

The orchestrator creates these files BEFORE spawning agents. Agents read them FIRST.
