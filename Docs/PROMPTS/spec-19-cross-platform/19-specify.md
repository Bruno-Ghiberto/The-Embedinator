# Spec 19 — Cross-Platform Developer Experience: Context Prompt for `speckit.specify`

> **How to use this file**: Pass it as context to `speckit.specify`.
> The agent will generate `specs/019-cross-platform-dx/spec.md` using the description,
> constraints, and clarification targets below.

---

## Feature Title

**Spec 19 — Cross-Platform Developer Experience**

One-liner: Transform The Embedinator from a multi-command, toolchain-dependent setup into
a single-command, cross-platform application that works on Windows 10/11, macOS, and Linux
with Docker Desktop as the only prerequisite.

---

## Design Reference

The full architectural design document produced by 4 specialized architect agents
(system, devops, backend, frontend) is at:

**`Docs/DESIGN-019-CROSS-PLATFORM-DX.md`** (13 sections, ~680 lines)

This document is **authoritative** — the specify agent MUST read it fully before writing
any requirements. All architectural decisions, trade-offs, and rejected alternatives are
documented there. Do NOT contradict the design document.

---

## Problem Statement

Today, installing and running The Embedinator requires:
1. Docker Desktop (for Qdrant + Ollama containers)
2. Python 3.14+ (bleeding edge — hard to install on many systems)
3. Node.js LTS (for the frontend)
4. Rust toolchain (optional, for the ingestion worker — but confusing when mentioned)
5. `make` (not available on Windows natively)
6. Multiple terminal windows for dev mode (`make dev-infra`, `make dev-backend`, `make dev-frontend`)
7. Manual `.env` file creation with a manually generated Fernet key
8. Manual `make pull-models` to download Ollama models (~4.7 GB)
9. No feedback about when the app is ready

The current `docker-compose.yml` hard-codes NVIDIA GPU passthrough, which **crashes on macOS,
Windows without NVIDIA, and Linux without nvidia-container-toolkit**.

The frontend has a critical bug: `NEXT_PUBLIC_API_URL=http://backend:8000` is baked into
the JS bundle at build time — the browser cannot resolve the Docker-internal hostname.

**Target state**: A user on any OS runs `./start.sh` (or `.\start.ps1` on Windows) and
the entire application builds, starts, downloads models, and opens in the browser — with
Docker Desktop as the only prerequisite.

---

## Current Infrastructure Baseline (Verified State)

> Do NOT assume. These facts were verified via codebase inspection before writing this file.

### Docker Services (4)

| Service | Image | Ports | Health Check | Issues |
|---------|-------|-------|-------------|--------|
| `qdrant` | `qdrant/qdrant:latest` | 6333, 6334 | TCP bash probe | Works |
| `ollama` | `ollama/ollama:latest` | 11434 | TCP bash probe | Hard-coded NVIDIA GPU deploy block; inline model pull in entrypoint |
| `backend` | `Dockerfile.backend` (multi-stage Rust+Python) | 8000 | `curl -f /api/health` | Non-root user has dynamic UID (not 1000); no tini |
| `frontend` | `frontend/Dockerfile` (multi-stage Next.js) | 3000 | **None** | No health check; `NEXT_PUBLIC_API_URL` baked at build time |

### Makefile (14 targets — MUST be preserved unchanged)

```
help  setup  build-rust  dev-infra  dev-backend  dev-frontend  dev
up  down  pull-models  test  test-cov  test-frontend  clean  clean-all
```

### Backend Config (`backend/config.py`)

- Pydantic Settings with 40+ env vars, `.env` file support, `populate_by_name=True`
- Defaults assume `localhost` (correct for `make dev`, wrong for Docker — Compose overrides fix this)
- `cors_origins` defaults to `http://localhost:3000,http://127.0.0.1:3000`
- `api_key_encryption_secret` aliased to `EMBEDINATOR_FERNET_KEY`

### Frontend Config

- `next.config.ts`: `output: "standalone"`, uses `NEXT_PUBLIC_API_URL` env var
- `lib/api.ts`: `const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"`
- All data fetching via SWR hooks with absolute URLs to the backend

### `.env.example`

- 40+ documented env vars grouped by category
- Missing: port configuration, `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`

---

## Scope — What Changes

### Area 1: Launcher Scripts (NEW)

- `start.sh` — bash/zsh launcher for macOS + Linux
- `start.ps1` — PowerShell launcher for Windows
- Subcommands: (default start), `--dev`, `--stop`, `--restart`, `--logs`, `--status`, `--help`
- Port override flags: `--frontend-port PORT`, `--backend-port PORT`
- Flow: preflight checks → GPU detection → .env generation → compose up → health polling → model pull → browser open

### Area 2: Docker Compose Decomposition (MODIFY + NEW)

- `docker-compose.yml` — base with no GPU block, configurable ports, SELinux `:z`, log rotation
- `docker-compose.gpu-nvidia.yml` — NVIDIA deploy reservation overlay
- `docker-compose.gpu-amd.yml` — AMD ROCm image swap + device passthrough overlay
- `docker-compose.gpu-intel.yml` — Intel Arc device passthrough overlay (experimental)
- `docker-compose.dev.yml` — fix broken volume mounts (currently mounts non-existent `src/`)

### Area 3: GPU Auto-Detection

- Detection priority: NVIDIA → AMD → Intel → CPU fallback
- NVIDIA: `nvidia-smi` + `docker info` check
- AMD: `/dev/kfd` exists + `rocminfo` check (Linux only)
- Intel: `/dev/dri/renderD*` exists (Linux only, experimental)
- macOS: always CPU (Docker VM doesn't pass through Metal)
- Windows: NVIDIA only via WSL2; AMD/Intel fall back to CPU
- `EMBEDINATOR_GPU` env var for manual override

### Area 4: Configurable Ports

- 5 host ports configurable via `EMBEDINATOR_PORT_*` env vars in `.env`
- Docker Compose uses `${EMBEDINATOR_PORT_FRONTEND:-3000}:3000` interpolation
- Launcher CLI flags override `.env` values for one-time use
- CORS origins auto-adjusted to configured frontend port
- Port conflict detection with actionable error messages

### Area 5: Frontend API Routing Fix (CRITICAL)

- **Remove** `NEXT_PUBLIC_API_URL` entirely (build-time baking problem)
- **Add** Next.js `rewrites` in `next.config.ts` proxying `/api/:path*` to `BACKEND_URL`
- `BACKEND_URL` is a server-side env var (not `NEXT_PUBLIC_`), default `http://localhost:8000`
- Docker Compose sets `BACKEND_URL=http://backend:8000` (container-internal)
- Browser uses relative `/api/...` paths — zero CORS issues, LAN access works
- Keep `NEXT_PUBLIC_API_URL` as optional override for advanced deployments

### Area 6: Frontend Health & Degraded States (NEW)

- `/healthz` route at `frontend/app/healthz/route.ts` (not `/api/health` — avoids rewrite conflict)
- Docker health check: `wget --spider http://localhost:3000/healthz`
- `BackendStatusProvider` React context: polls `/api/health`, exposes `unreachable | degraded | ready`
- `StatusBanner` component: non-dismissible banner for degraded states (Ollama downloading, Qdrant starting, etc.)
- Chat input gating: disabled with contextual placeholder when backend not ready
- Root route `app/page.tsx` redirect to `/chat`

### Area 7: Backend Health Enhancement (MODIFY)

- **Add** `/api/health/live` — liveness probe (always 200 if process running)
- **Enhance** `/api/health` — per-service status with model availability, `healthy | degraded | starting`
- Docker HEALTHCHECK targets `/api/health/live` (not full readiness — prevents unnecessary restarts during model download)
- Health probes bypass circuit breaker failure counting
- Suppress health endpoint request logs (6 noise lines/minute from Docker checks)

### Area 8: Dockerfile Improvements (MODIFY)

**Backend:**
- Fixed UID/GID 1000 for bind mount compatibility
- `tini` as PID 1 for proper signal forwarding
- Pre-download cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`, 24MB) during build
- `ENV HF_HOME=/app/.cache/huggingface`
- Build args for version flexibility (`PYTHON_VERSION`, `RUST_VERSION`)

**Frontend:**
- Pin `node:22-alpine` (not `lts-alpine` — prevents cache invalidation on LTS roll)
- `NEXT_PUBLIC_API_URL` as optional build arg
- Add `frontend/.dockerignore` to exclude test files from build context

### Area 9: Environment & First-Run (MODIFY)

- Auto-generate `.env` from `.env.example` if not exists
- Auto-generate Fernet key via disposable Docker container (no local Python needed)
- Auto-detect LAN IP for CORS origins
- Create `data/` and `data/uploads/` directories
- Validate data directory write access at backend startup (clear error message)

### Area 10: Graceful Shutdown (MODIFY)

- `stop_grace_period: 15s` in Compose
- `app.state.shutting_down` flag rejects new chat requests
- Explicit `PRAGMA wal_checkpoint(TRUNCATE)` on SQLite + checkpoints DB
- Explicit close of LangGraph checkpointer connection

### Area 11: Cross-Platform Hardening (NEW + MODIFY)

- `.gitattributes` — enforce LF for shell scripts, CRLF for `.ps1`
- SELinux `:z` suffix on all bind mounts (no-op on non-SELinux systems)
- WSL2 filesystem warning (project on `/mnt/c/`)
- macOS Docker VM memory check (warn if < 4GB)
- Linux Docker socket permission detection
- Docker Compose v2 verification
- Disk space warning (< 15GB)

---

## Non-Goals / Out of Scope

- **No new Python packages** — all backend changes use existing dependencies
- **No new frontend npm packages** — all frontend changes use existing packages
- **No database schema changes** — no SQLite or Qdrant schema migrations
- **No Makefile changes** — all 14 existing targets preserved unchanged
- **No authentication** — the app remains a trusted local network tool
- **No CI/CD pipeline** — that belongs in a separate spec
- **No Kubernetes / cloud deployment** — Docker Compose on a single machine only
- **No Ollama model selection UI** — `OLLAMA_MODELS` env var is sufficient for now
- **No Windows native (non-Docker) support** — WSL2 + Docker Desktop is the path
- **No first-run onboarding wizard in the UI** — the launcher script handles first-run setup;
  the frontend first-run onboarding (welcome card, "Create a collection" CTA) is a P3 nice-to-have,
  not a hard requirement

---

## Key Constraints

- **Docker Desktop = sole prerequisite** for end-users. The launcher scripts must not require
  Python, Node.js, Rust, `make`, `just`, or any other tool installed locally.
- **Existing Makefile preserved** — no targets added, removed, or renamed. The Makefile is for
  developers with local toolchains; the launcher is for end-users.
- **Next.js rewrites approach** for API routing — the design doc evaluated 5 options (build-time URL,
  API route proxy, runtime env injection, rewrites, nginx) and selected rewrites. Do NOT propose alternatives.
- **Compose overlay files** for GPU — the design doc evaluated profiles vs overlays and selected overlays.
- **`/healthz` path** for frontend health (not `/api/health`) — avoids rewrite conflict.
- **tini as PID 1** in both Dockerfiles — required for proper signal handling.
- **Fixed UID 1000** in backend Dockerfile — required for bind mount compatibility on Linux.
- **Cross-encoder pre-download in Dockerfile** — the design doc evaluated 3 options (build-time,
  named volume, bind mount) and selected build-time. 24MB cost is negligible.
- **No `RUNTIME_MODE` env var** — the design doc explicitly rejected this. Docker Compose `environment:`
  overrides are sufficient and idiomatic.

---

## MCP Usage Instructions

Use the following MCP servers throughout this specification task. Each has a defined
role — do not skip the mandatory ones.

### Mandatory (always use)

**serena** — Use for all codebase exploration before writing any requirement.
- `get_symbols_overview` to inspect current Docker, Makefile, and config files
- `find_symbol` to verify the exact current state of health endpoints, config fields,
  Dockerfile instructions, and compose services before writing FRs
- Do NOT describe current behavior from memory — always verify with serena first

**sequential-thinking** — Use to structure your reasoning before writing each major section.
- Activate before drafting User Stories, Functional Requirements, and Success Criteria
- Use to work through the dependency chain: which requirements must be implemented first?
- Use when a requirement spans multiple areas (e.g., port configuration affects compose,
  launcher, CORS, health polling, and browser open)

### Contextual (use when the task calls for it)

**context7** — Use when writing requirements that depend on framework-specific capabilities.
- Resolve Next.js 16 `rewrites` API before writing the API routing FR
- Verify Docker Compose variable interpolation syntax
- Confirm `next-themes` behavior with the new `BACKEND_URL` pattern

**gitnexus** — Use to understand impact of backend changes.
- `gitnexus_impact` on `health.py`, `main.py`, `config.py` before writing backend FRs
- `gitnexus_context` on the health endpoint to understand all consumers

---

## Instructions for `speckit.specify` Agent

### Mandatory: Read the design document first

Before writing ANY requirement, you MUST:
1. Read `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` in full (all 13 sections)
2. Read `docker-compose.yml`, `Dockerfile.backend`, `frontend/Dockerfile`
3. Read `backend/config.py` and `backend/api/health.py`
4. Read `frontend/next.config.ts` and `frontend/lib/api.ts`

### Mandatory clarification questions (ask before writing FRs)

1. **Launcher script name**: The design doc uses `start.sh` / `start.ps1`. Should these
   be named differently? (e.g., `embedinator.sh`, `run.sh`, `launch.sh`)

2. **Qdrant volume strategy**: The design doc proposes moving Qdrant from bind mount
   (`./data/qdrant_db:/qdrant/storage`) to a named volume (`qdrant_data`). This means
   Qdrant data is no longer visible on the host filesystem and is lost on `docker compose down -v`.
   Is this acceptable, or should Qdrant stay as a bind mount?

3. **Frontend first-run onboarding**: The design doc includes a P3 (low priority) welcome card
   with "Create a collection" CTA on first visit (zero collections). Should this be in scope
   for spec-19, or deferred to a future spec?

4. **Model pull strategy**: Two options from the design doc:
   a) Ollama entrypoint runs `ollama serve` only; the launcher script pulls models after
      Ollama is healthy (progress visible to user)
   b) A mounted `scripts/ollama-init.sh` handles both serve and pull inside the container
   Which approach? (Design doc recommends option A.)

5. **Browser auto-open behavior**: Should the launcher auto-open the browser on every start,
   only on first run, or require an explicit `--open` flag?

### Sections to generate in spec.md

1. **Overview** — 2-3 paragraphs: what, why, key outcomes
2. **User Stories** (5-7): personas include first-time user on each OS, returning user,
   developer contributor, user with port conflicts, user with non-NVIDIA GPU
   - Must include: first-time install on all 3 OS, daily start/stop, dev mode, port customization, GPU detection
3. **Functional Requirements** (25-40): organized by area
   - Area 1: Launcher Scripts (`start.sh` / `start.ps1`) — preflight, GPU detection, .env generation,
     compose up, health polling, model pull, browser open, subcommands, port flags
   - Area 2: Docker Compose — base decomposition, GPU overlays (NVIDIA/AMD/Intel), dev overlay fix,
     configurable ports, SELinux, log rotation, health checks, dependency ordering
   - Area 3: Frontend API Routing — Next.js rewrites, `BACKEND_URL`, remove `NEXT_PUBLIC_API_URL`,
     relative fetch paths, `/healthz` endpoint
   - Area 4: Backend Health — `/api/health/live`, enhanced `/api/health`, model availability,
     health log suppression, circuit breaker bypass for probes
   - Area 5: Dockerfiles — backend UID 1000, tini, cross-encoder pre-download, HF_HOME;
     frontend Node pin, .dockerignore, build arg
   - Area 6: Environment & First-Run — `.env` generation, Fernet key, LAN IP CORS, data dir
     creation, write-access test
   - Area 7: Frontend Degraded States — `BackendStatusProvider`, `StatusBanner`, chat input gating,
     SWR error retry behavior
   - Area 8: Graceful Shutdown — stop_grace_period, shutting_down flag, WAL checkpoint,
     checkpointer close
   - Area 9: Cross-Platform Hardening — `.gitattributes`, WSL2 warning, macOS memory check,
     Linux socket permissions, disk space, Compose v2 check
4. **Non-Functional Requirements** (3-5): cross-platform (works on all 3 OS),
   idempotency (safe to run launcher multiple times), startup time (< 60s subsequent runs),
   zero local toolchain requirement
5. **Success Criteria** (8-10): verifiable, binary pass/fail
   - Must include:
     - `./start.sh` runs successfully on Linux without any local toolchain except Docker
     - `.\start.ps1` runs successfully on Windows with Docker Desktop
     - GPU auto-detection selects correct profile on NVIDIA Linux
     - GPU auto-detection falls back to CPU on macOS
     - Custom ports work: `./start.sh --frontend-port 4000 --backend-port 9000`
     - Frontend serves API requests via rewrites (no CORS errors, no hostname resolution failures)
     - Backend health endpoint reports model availability
     - First-run auto-generates `.env` with Fernet key without local Python
6. **Out of Scope** — bullet list (from Non-Goals above)
7. **File Impact Map** — table: file → action (CREATE/MODIFY/PRESERVE) → purpose

### Writing quality standards

- Every FR must be verifiable: "The launcher MUST check port availability for all configured
  ports and exit with an error message if any port is in use" — not "The launcher should
  handle port conflicts"
- Use RFC 2119 keywords (MUST, SHOULD, MAY) consistently
- Keep FRs atomic: one observable behavior per requirement
- Reference the design document section for complex requirements:
  "Per DESIGN-019 Section 3.3, Docker Compose MUST use variable interpolation for ports"
- Mark each FR with its area tag: `[LAUNCHER]`, `[COMPOSE]`, `[FRONTEND]`, `[BACKEND]`,
  `[DOCKERFILE]`, `[ENV]`, `[SHUTDOWN]`, `[CROSS-PLATFORM]`
- For FRs that affect multiple files, list all affected files explicitly
