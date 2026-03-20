# Spec-019-Prep: Cross-Platform Developer Experience Architecture

**Date:** 2026-03-19
**Status:** DESIGN COMPLETE — Ready for speckit pipeline
**Architects:** System, DevOps, Backend, Frontend (sequential analysis)
**Branch context:** `018-ux-redesign` (spec-18 complete, uncommitted)

---

## Executive Summary

Transform The Embedinator from a developer-oriented multi-command setup into a **single-command, cross-platform application** that works on Windows 10/11, macOS, and Linux with **Docker Desktop as the only prerequisite**.

### Core Design Decisions

| Decision | Recommendation | Rationale |
|----------|---------------|-----------|
| **Prerequisites** | Docker Desktop only | Rust, Python, Node all run in containers. Zero toolchain install. |
| **Launcher** | `embedinator.sh` + `embedinator.ps1` pair | Zero dependencies beyond OS shell. Full control over GPU detection, env setup, health polling. |
| **GPU handling** | Compose overlay files | Base compose is always safe (CPU). NVIDIA/AMD/Intel overlays added when detected. macOS always CPU in Docker. |
| **API routing** | Next.js `rewrites` (no `NEXT_PUBLIC_API_URL`) | Browser uses relative `/api/*` paths. Server-side `BACKEND_URL` env var for Docker networking. Zero CORS issues, LAN access works. |
| **First-run** | Fully automated | `.env` generation, Fernet key, model downloads, health polling. Browser open via `--open` flag. |
| **Dev vs Prod** | `--dev` flag on launcher OR `make dev` | Two paths: Docker-dev for contributors, local-dev for core developers. |
| **Port config** | All 5 host ports configurable via `.env` or CLI flags | Defaults: 3000/8000/6333/6334/11434. Users likely have services on 3000/8000. |

---

## 1. System Architecture

### 1.1 File Structure (new/modified files)

```
project root/
  embedinator.sh                          # NEW — bash/zsh launcher (macOS + Linux)
  embedinator.ps1                         # NEW — PowerShell launcher (Windows)
  docker-compose.yml                # MODIFY — remove NVIDIA deploy block, add health checks
  docker-compose.gpu-nvidia.yml     # NEW — NVIDIA GPU overlay for Ollama
  docker-compose.gpu-amd.yml        # NEW — AMD ROCm GPU overlay (swaps image + device passthrough)
  docker-compose.gpu-intel.yml      # NEW — Intel Arc GPU overlay (device passthrough)
  docker-compose.dev.yml            # MODIFY — fix broken volume mounts
  .gitattributes                    # NEW — enforce LF/CRLF per file type
  frontend/.dockerignore            # NEW — exclude test files from build context
  frontend/app/healthz/route.ts     # NEW — frontend health endpoint
  frontend/app/page.tsx             # NEW — root redirect to /chat
  frontend/components/BackendStatusProvider.tsx  # NEW — backend health context
  frontend/components/StatusBanner.tsx           # NEW — global degraded state banner
  scripts/ollama-init.sh            # NEW — robust Ollama model pull with retries (optional)
  Makefile                          # PRESERVE — no changes to existing 14 targets
  Dockerfile.backend                # MODIFY — fixed UID 1000, pre-download cross-encoder, tini
  frontend/Dockerfile               # MODIFY — pin Node 22, build arg for API URL
```

### 1.2 Prerequisite Strategy

| Platform | Only Requirement | Notes |
|----------|-----------------|-------|
| **Windows 10/11** | Docker Desktop (WSL2 backend) | Installer enables WSL2 automatically |
| **macOS** | Docker Desktop for Mac | Apple Silicon + Intel both supported natively |
| **Linux** | Docker Engine + Compose v2 plugin | Most distros package this; Docker Desktop for Linux also works |

**Rejected alternatives:** Python CLI (requires Python pre-installed), Go/Rust wrapper (6+ binary targets to distribute), `just`/`task` runner (adds a prerequisite).

### 1.3 User Experience Flow

```
$ ./embedinator.sh
[1/6] Checking Docker.............. OK (Docker Desktop 4.38.0, Compose v2.32)
[2/6] Detecting GPU................ AMD ROCm detected, using GPU acceleration
[3/6] Generating environment....... Created .env with Fernet key
[4/6] Building services............ First run — this takes 3-5 minutes
      qdrant:   healthy
      ollama:   healthy
      backend:  healthy  (port 8000)
      frontend: healthy  (port 3000)
[5/6] Downloading AI models........ qwen2.5:7b (4.4 GB)
      ████████████████░░░░░░░░░░ 67% | 2.9 GB / 4.4 GB
      nomic-embed-text (274 MB)... done
[6/6] Ready!

  Open:   http://localhost:3000
  Logs:   docker compose logs -f
  Stop:   ./embedinator.sh --stop
  Help:   ./embedinator.sh --help

# With custom ports:
$ ./embedinator.sh --frontend-port 4000 --backend-port 9000
  ...
  Open:   http://localhost:4000
```

---

## 2. Docker Compose Decomposition

### 2.1 Base Compose (always loaded, no GPU)

**Key changes from current:**
- Remove `deploy.resources.reservations.devices` from Ollama (breaks on non-NVIDIA)
- Change Ollama entrypoint from model-pulling inline script to simple `ollama serve`
- Add frontend health check (`/healthz`)
- Change backend health check to `/api/health/live` (liveness, not readiness)
- Add `stop_grace_period: 15s` to backend
- Add SELinux `:z` suffix to bind mounts
- Add Docker log rotation (`json-file`, 50m x 3 files)
- Change Qdrant from bind mount to named volume
- Replace frontend `NEXT_PUBLIC_API_URL` with server-side `BACKEND_URL`
- Add frontend `depends_on: backend: condition: service_healthy`

### 2.2 GPU Overlay Files

Three GPU-specific overlays, each selected automatically by the launcher script based on hardware detection:

#### NVIDIA (`docker-compose.gpu-nvidia.yml`)

Additive overlay — adds GPU reservation to the base Ollama service (same `ollama/ollama:latest` image):

```yaml
services:
  ollama:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

#### AMD ROCm (`docker-compose.gpu-amd.yml`)

**Swaps the Ollama image** to the ROCm variant and adds AMD GPU device passthrough:

```yaml
services:
  ollama:
    image: ollama/ollama:rocm
    devices:
      - /dev/kfd:/dev/kfd
      - /dev/dri:/dev/dri
```

**Key difference from NVIDIA:** AMD requires a different Docker image (`ollama/ollama:rocm`), not just a `deploy` block. The ROCm image includes the AMD GPU compute stack. The `/dev/kfd` (Kernel Fusion Driver) and `/dev/dri` (Direct Rendering Infrastructure) devices must be passed through for GPU access.

**Platform support:** Linux only. AMD ROCm is not supported in Docker on Windows (WSL2 does not pass through AMD GPUs) or macOS.

#### Intel Arc (`docker-compose.gpu-intel.yml`)

Additive overlay — passes through the Intel GPU render device (same `ollama/ollama:latest` image, Intel oneAPI/SYCL support is built-in):

```yaml
services:
  ollama:
    devices:
      - /dev/dri:/dev/dri
```

**Platform support:** Linux only (experimental). Intel Arc GPU support in Ollama is experimental. Docker on Windows (WSL2) does not pass through Intel GPUs. macOS does not use Intel Arc.

### 2.3 Dev Overlay (`docker-compose.dev.yml`)

**Key changes from current (currently broken — mounts non-existent `src/` dir):**
- Mount individual frontend directories: `app/`, `components/`, `hooks/`, `lib/`, `public/`
- Anonymous volumes for `node_modules/` and `.next/`
- Use `target: deps` to stop at dependency install stage
- Override command to `npx next dev --hostname 0.0.0.0`
- Backend: mount `./backend:/app/backend` with `uvicorn --reload`

### 2.4 Composition Logic

```bash
# GPU_PROFILE is one of: nvidia, amd, intel, none
# When "none", no GPU overlay is appended — base compose is sufficient (CPU mode)

# Production (default)
if [ "$GPU_PROFILE" = "none" ]; then
    docker compose -f docker-compose.yml up --build -d
else
    docker compose -f docker-compose.yml -f docker-compose.gpu-${GPU_PROFILE}.yml up --build -d
fi

# Development (same pattern, appends dev overlay)
if [ "$GPU_PROFILE" = "none" ]; then
    docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
else
    docker compose -f docker-compose.yml -f docker-compose.gpu-${GPU_PROFILE}.yml -f docker-compose.dev.yml up --build
fi
```

---

## 3. Configurable Ports

### 3.1 Problem

Ports 3000 (frontend) and 8000 (backend) are extremely common defaults — Next.js, React dev servers, FastAPI, Django, and many other frameworks use them. Users very likely have other services occupying these ports. Qdrant (6333/6334) and Ollama (11434) are less likely to conflict but should still be configurable.

### 3.2 Design: Host Ports vs Container Ports

Docker maps **host ports** (what the user's machine exposes) to **container ports** (what the process inside the container listens on). Only host ports need to be configurable — container-internal ports stay fixed:

| Service | Container Port (fixed) | Host Port (configurable) | Default |
|---------|:---:|:---:|:---:|
| Frontend | 3000 | `EMBEDINATOR_PORT_FRONTEND` | 3000 |
| Backend | 8000 | `EMBEDINATOR_PORT_BACKEND` | 8000 |
| Qdrant HTTP | 6333 | `EMBEDINATOR_PORT_QDRANT` | 6333 |
| Qdrant gRPC | 6334 | `EMBEDINATOR_PORT_QDRANT_GRPC` | 6334 |
| Ollama | 11434 | `EMBEDINATOR_PORT_OLLAMA` | 11434 |

### 3.3 Docker Compose Variable Interpolation

The base `docker-compose.yml` uses env var interpolation with defaults:

```yaml
services:
  frontend:
    ports:
      - "${EMBEDINATOR_PORT_FRONTEND:-3000}:3000"
  backend:
    ports:
      - "${EMBEDINATOR_PORT_BACKEND:-8000}:8000"
  qdrant:
    ports:
      - "${EMBEDINATOR_PORT_QDRANT:-6333}:6333"
      - "${EMBEDINATOR_PORT_QDRANT_GRPC:-6334}:6334"
  ollama:
    ports:
      - "${EMBEDINATOR_PORT_OLLAMA:-11434}:11434"
```

Docker Compose reads these from `.env` automatically (same file the backend uses). No code changes inside the containers — they always listen on their fixed internal ports.

### 3.4 How Ports Flow Through the System

When the user sets custom ports, several things must adapt:

**CORS origins** — The backend's `CORS_ORIGINS` must include the custom frontend port:
```
# .env with custom ports
EMBEDINATOR_PORT_FRONTEND=4000
CORS_ORIGINS=http://localhost:4000,http://127.0.0.1:4000
```
The launcher script handles this automatically: it reads `EMBEDINATOR_PORT_FRONTEND` from `.env` and writes the correct `CORS_ORIGINS` value.

**Next.js rewrites** — The `BACKEND_URL` env var in `docker-compose.yml` always points to `http://backend:8000` (the container-internal address). This does NOT change when the host backend port changes, because the frontend container talks to the backend container over Docker's internal network, not through the host port mapping. No impact.

**Browser auto-open** — The launcher reads `EMBEDINATOR_PORT_FRONTEND` and opens `http://localhost:${port}`:
```bash
FRONTEND_PORT=$(grep EMBEDINATOR_PORT_FRONTEND .env 2>/dev/null | cut -d= -f2)
FRONTEND_PORT=${FRONTEND_PORT:-3000}
open "http://localhost:${FRONTEND_PORT}"
```

**Health polling** — The launcher polls health endpoints using the configured host ports:
```bash
curl -sf "http://localhost:${BACKEND_PORT}/api/health/live"
wget --spider "http://localhost:${FRONTEND_PORT}/healthz"
```

**Makefile `dev-backend` / `dev-frontend`** — These targets run locally (not in Docker), so they use the Settings defaults from `config.py` (`port: int = 8000`, `frontend_port: int = 3000`). If the user wants custom ports in local dev mode, they set `PORT=9000` in `.env` which Pydantic Settings reads automatically. No Makefile changes needed.

### 3.5 Launcher CLI Flags

Users can set ports via `.env` (persistent) or via CLI flags (one-time override):

```bash
# Via .env (persistent across restarts)
echo "EMBEDINATOR_PORT_FRONTEND=4000" >> .env
echo "EMBEDINATOR_PORT_BACKEND=9000" >> .env
./embedinator.sh

# Via CLI flags (one-time, overrides .env for this run)
./embedinator.sh --frontend-port 4000 --backend-port 9000

# PowerShell equivalent
.\embedinator.ps1 -FrontendPort 4000 -BackendPort 9000
```

CLI flags take precedence over `.env` values. The launcher exports them as environment variables before calling `docker compose`, so the compose interpolation picks them up.

### 3.6 Port Conflict Detection

The launcher checks ALL configured ports before starting:

```
[1/6] Checking Docker.............. OK
      Checking ports...............
        3000 (frontend): available
        8000 (backend):  IN USE (pid 12345: node)

  ERROR: Port 8000 is already in use.
  Fix:   ./embedinator.sh --backend-port 9000
         or stop the conflicting process
```

On conflict, the launcher suggests the `--backend-port` / `--frontend-port` flag with an alternative port, rather than silently failing.

### 3.7 `.env.example` Port Documentation

```bash
# ── Ports ──────────────────────────────────────────────────────────────────
# Host ports for Docker port mapping. Change these if the defaults conflict
# with other services on your machine. Container-internal ports stay fixed.

# EMBEDINATOR_PORT_FRONTEND — Frontend (Next.js). Default: 3000.
EMBEDINATOR_PORT_FRONTEND=3000

# EMBEDINATOR_PORT_BACKEND — Backend API (FastAPI). Default: 8000.
EMBEDINATOR_PORT_BACKEND=8000

# EMBEDINATOR_PORT_QDRANT — Qdrant HTTP API. Default: 6333.
EMBEDINATOR_PORT_QDRANT=6333

# EMBEDINATOR_PORT_QDRANT_GRPC — Qdrant gRPC API. Default: 6334.
EMBEDINATOR_PORT_QDRANT_GRPC=6334

# EMBEDINATOR_PORT_OLLAMA — Ollama API. Default: 11434.
EMBEDINATOR_PORT_OLLAMA=11434
```

---

## 4. GPU Auto-Detection

### 4.1 Detection Logic

The launcher script detects GPUs in priority order (NVIDIA > AMD > Intel > CPU fallback):

```
GPU_PROFILE="none"

1. Check NVIDIA:  nvidia-smi succeeds + docker info contains "nvidia"  → "nvidia"
2. Check AMD:     /dev/kfd exists + rocminfo succeeds                  → "amd"
3. Check Intel:   /dev/dri/renderD* exists + (sycl-ls or intel_gpu_top)→ "intel"
4. Fallback:      none of the above                                    → "none" (CPU)
```

Only the first match is used. If a system has both NVIDIA and Intel GPUs, NVIDIA wins (it has the most mature Ollama support).

### 4.2 Detection Matrix

| Platform | GPU | Detection Method | Compose Overlay | Ollama Image |
|----------|-----|-----------------|-----------------|--------------|
| Linux + NVIDIA + nvidia-container-toolkit | NVIDIA | `nvidia-smi` + `docker info` | `gpu-nvidia.yml` | `ollama/ollama:latest` |
| Linux + AMD + ROCm drivers | AMD | `/dev/kfd` + `rocminfo` | `gpu-amd.yml` | `ollama/ollama:rocm` |
| Linux + Intel Arc + oneAPI | Intel | `/dev/dri/renderD*` + `sycl-ls` | `gpu-intel.yml` | `ollama/ollama:latest` |
| Linux without GPU | CPU | All checks fail | (base only) | `ollama/ollama:latest` |
| macOS (any) | None in Docker | `uname -s == Darwin` | (base only) | `ollama/ollama:latest` |
| Windows + NVIDIA + Docker WSL2 GPU | NVIDIA | `nvidia-smi` + `docker info` | `gpu-nvidia.yml` | `ollama/ollama:latest` |
| Windows + AMD | CPU | WSL2 doesn't pass AMD GPUs | (base only) | `ollama/ollama:latest` |
| Windows + Intel Arc | CPU | WSL2 doesn't pass Intel GPUs | (base only) | `ollama/ollama:latest` |
| Windows without GPU | CPU | All checks fail | (base only) | `ollama/ollama:latest` |

### 4.3 macOS GPU Note

Docker Desktop for Mac runs containers in a Linux VM — Metal/GPU is NOT passed through. Ollama runs on CPU inside the container. For GPU acceleration, users can install Ollama natively (`brew install ollama`) and set `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env`. This is a documented advanced option.

### 4.4 Windows AMD/Intel GPU Note

WSL2 (Docker Desktop's backend on Windows) only supports GPU passthrough for NVIDIA via the CUDA driver bridge. AMD ROCm and Intel oneAPI are not available in WSL2 containers. Users with AMD or Intel GPUs on Windows fall back to CPU mode in Docker. For GPU acceleration, they can install Ollama natively on Windows and set `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `.env` (same pattern as macOS).

### 4.5 GPU Override

Users can force a specific GPU profile by setting `EMBEDINATOR_GPU` in their environment:

```bash
EMBEDINATOR_GPU=amd ./embedinator.sh      # Force AMD even if detection fails
EMBEDINATOR_GPU=none ./embedinator.sh     # Force CPU mode even with GPU present
```

This is useful when auto-detection fails (e.g., `rocminfo` not installed but AMD GPU present) or for testing.

---

## 5. Frontend API Routing (Critical Design)

### 5.1 Problem

`NEXT_PUBLIC_API_URL` is baked into the JS bundle at build time. Setting it to `http://backend:8000` (Docker internal DNS) means the browser cannot resolve it. This is the #1 cross-platform bug.

### 5.2 Solution: Next.js Rewrites

Remove `NEXT_PUBLIC_API_URL` entirely. Use a server-side `BACKEND_URL` env var with Next.js `rewrites` in `next.config.ts`:

```
Browser → http://localhost:3000/api/chat → [Next.js rewrite] → http://backend:8000/api/chat
```

**Benefits:**
- Zero CORS issues (same-origin requests)
- LAN access works (`http://192.168.1.50:3000/api/...` goes through the same rewrite)
- No build-time baking
- NDJSON streaming works (rewrites operate at HTTP level, no buffering)

**Changes required:**
1. `next.config.ts` — add `rewrites()` pointing `/api/:path*` to `${BACKEND_URL}/api/:path*`
2. `lib/api.ts` — change `API_BASE` to empty string (relative paths)
3. `docker-compose.yml` — replace `NEXT_PUBLIC_API_URL` with `BACKEND_URL=http://backend:8000`
4. Keep `NEXT_PUBLIC_API_URL` as optional override for advanced deployments

### 5.3 Frontend Health Endpoint

Add `/healthz` route (not `/api/health` to avoid rewrite conflict) at `frontend/app/healthz/route.ts`. Returns `{"status": "ok"}`. Docker health check uses `wget --spider http://localhost:3000/healthz`.

---

## 6. Backend Resilience

### 6.1 Startup Strategy

- **Ollama = soft dependency**: Backend starts without it, reports "degraded" status
- **Two health endpoints**:
  - `/api/health/live` — liveness (Docker HEALTHCHECK, always 200 if process alive)
  - `/api/health` — readiness (launcher script, frontend status)
- **Enhanced health response**: Per-service status with model availability, `"healthy" | "degraded" | "starting"` states
- **Circuit breaker**: Health probes bypass circuit breaker failure counting

### 6.2 Cross-Encoder Model

**Pre-download in Dockerfile** (Option A — recommended):
- 24MB addition to image (~2% of total size)
- Eliminates runtime internet dependency
- Deterministic builds
- Add `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` after `pip install`
- Set `ENV HF_HOME=/app/.cache/huggingface`

### 6.3 Graceful Shutdown

- `stop_grace_period: 15s` (vs default 10s)
- `app.state.shutting_down` flag rejects new chat requests
- In-flight NDJSON streams drain during grace period
- Explicit `PRAGMA wal_checkpoint(TRUNCATE)` on both SQLite databases
- Explicit close of LangGraph checkpointer connection

### 6.4 Database Initialization

- `lifespan()` creates `data/uploads/` directory on startup
- Write-access test at startup with clear error message if `data/` is not writable
- Fixed UID 1000 in Dockerfile.backend aligns with host user

### 6.5 Logging

- Suppress health endpoint request logs (`/api/health`, `/api/health/live`)
- Docker log rotation: `json-file`, 50m x 3 files per service
- Add `service`, `version`, `runtime` fields to structlog context
- No file logging inside containers

---

## 7. Frontend Degraded State Handling

### 7.1 BackendStatusProvider

React context wrapping the app. Polls `/api/health` via SWR:
- `unreachable` → 5s polling
- `degraded` → 10s polling
- `ready` → 30s polling

### 7.2 Global Status Banner

Non-dismissible banner in `SidebarLayout` between header and content:

| State | Banner Message |
|-------|---------------|
| Unreachable | "Connecting to backend..." + spinner |
| Starting | "Backend is starting up..." + spinner |
| Ollama downloading | "AI models are being downloaded. Chat will be available shortly." + progress bar |
| Qdrant down | "Vector database is starting up." |

### 7.3 Chat Input Gating

| Backend State | Chat Input Behavior |
|--------------|-------------------|
| Unreachable | Disabled, placeholder: "Waiting for backend to start..." |
| Degraded (Ollama) | Disabled, placeholder: "AI models are still loading..." |
| Degraded (Qdrant) | Disabled, placeholder: "Vector database is starting..." |
| Ready, no collections | Disabled, placeholder: "Select at least one collection..." |
| Ready, collections selected | Enabled, placeholder: "Ask a question..." |

### 7.4 First-Run Onboarding

When zero collections exist, replace chat empty state with guided onboarding:
1. "Create a collection" — button to `/collections`
2. "Upload documents" — supported formats info
3. "Ask questions" — how the chat works

### 7.5 Root Route

Add `app/page.tsx` that redirects to `/chat` (the primary interface).

---

## 8. Launcher Script Design (`embedinator.sh` / `embedinator.ps1`)

### 8.1 Subcommands

| Command | Action |
|---------|--------|
| `./embedinator.sh` | Start in production mode (default) |
| `./embedinator.sh --dev` | Start with dev overlay (hot reload) |
| `./embedinator.sh --stop` | `docker compose down` |
| `./embedinator.sh --restart` | Stop + start |
| `./embedinator.sh --logs [service]` | `docker compose logs -f [service]` |
| `./embedinator.sh --status` | Show service health status |
| `./embedinator.sh --frontend-port PORT` | Override frontend host port (default: 3000) |
| `./embedinator.sh --backend-port PORT` | Override backend host port (default: 8000) |
| `./embedinator.sh --help` | Show usage |

Flags can be combined: `./embedinator.sh --dev --frontend-port 4000 --backend-port 9000`

PowerShell equivalents: `.\embedinator.ps1 -Dev -FrontendPort 4000 -BackendPort 9000`

### 8.2 Preflight Checks

1. Docker running (`docker info`)
2. Docker Compose v2 available (`docker compose version`)
3. Port availability — check all **configured** ports (not hardcoded defaults). Read from `.env` + CLI flag overrides
4. Disk space (warn if < 15GB)
5. Docker memory (macOS: warn if < 4GB allocated)
6. WSL2 filesystem warning (Windows: warn if project on `/mnt/c/`)

### 8.3 Environment Setup

1. Copy `.env.example` → `.env` if not exists
2. Generate Fernet key via disposable container:
   ```
   docker run --rm python:3.14-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
3. Apply CLI port overrides to `.env` (write `EMBEDINATOR_PORT_FRONTEND` / `EMBEDINATOR_PORT_BACKEND` if flags provided)
4. Auto-detect LAN IP, write `CORS_ORIGINS` using the configured frontend port
5. Create `data/` and `data/uploads/` directories

### 8.4 Build & Start

1. Select compose files based on GPU detection + `--dev` flag
2. Export port env vars so Docker Compose interpolation picks them up
3. `docker compose -f ... up --build -d`
4. Print first-build timing estimate

### 8.5 Health Polling

1. Poll Qdrant, Ollama, backend, frontend health endpoints **using configured host ports**
2. Print status line with per-service indicators (overwrite in place)
3. Timeout: 300s for first run (model downloads), 60s for subsequent

### 8.6 Model Pull

1. Check if models already cached (`docker compose exec ollama ollama list`)
2. Pull missing models with progress passthrough
3. `OLLAMA_MODELS` env var configures model list (default: `qwen2.5:7b,nomic-embed-text`)

### 8.7 Browser Open

Uses the configured frontend port:

```bash
FRONTEND_PORT=${EMBEDINATOR_PORT_FRONTEND:-3000}
case "$(uname -s)" in
    Darwin)  open "http://localhost:${FRONTEND_PORT}" ;;
    Linux)   xdg-open "http://localhost:${FRONTEND_PORT}" 2>/dev/null || true ;;
esac
# PowerShell: Start-Process "http://localhost:$FrontendPort"
```

---

## 9. Cross-Platform Considerations

### 9.1 Windows (WSL2 + Docker Desktop)

| Issue | Mitigation |
|-------|-----------|
| `/mnt/c/` filesystem slow | Launcher warns; docs recommend cloning into WSL2 `~/` |
| Line endings (CRLF) | `.gitattributes` enforces LF for shell scripts |
| Port conflicts | Launcher checks configured ports; `--frontend-port` / `--backend-port` flags to override |
| No `make` available | Users use `embedinator.ps1` instead; `make` only for developers |
| AMD/Intel GPUs not available in WSL2 | CPU fallback; docs explain native Ollama for GPU acceleration |

### 9.2 macOS (Docker Desktop)

| Issue | Mitigation |
|-------|-----------|
| No GPU in Docker (Metal not passed through) | CPU-only; docs explain native Ollama (`brew install ollama`) for Metal acceleration |
| Docker VM memory (default 2GB) | Launcher warns if < 4GB |
| VirtioFS vs legacy osxfs | Docs recommend VirtioFS for dev mode |

### 9.3 Linux

| Issue | Mitigation |
|-------|-----------|
| Docker socket permissions | Launcher detects and prints `usermod -aG docker` instructions |
| SELinux (Fedora/RHEL) | All bind mounts get `:z` suffix |
| UID mismatch on bind mounts | Backend Dockerfile uses fixed UID 1000 |
| Rootless Docker | Fixed UID 1000 aligns with typical user |
| AMD GPU: ROCm drivers required | Launcher checks `/dev/kfd`; prints install instructions if missing |
| Intel Arc GPU: oneAPI drivers required | Launcher checks `/dev/dri/renderD*`; experimental support noted |

### 9.4 Universal

| Issue | Mitigation |
|-------|-----------|
| Docker Compose v1 vs v2 | Launcher requires `docker compose` (v2) |
| Disk space (~15GB total) | Launcher warns if insufficient |
| First-run downloads (~8GB) | Launcher shows progress, estimates sizes |
| `.gitattributes` | Enforce line endings per file type |

---

## 10. Dockerfile Improvements

### 10.1 Backend (`Dockerfile.backend`)

| Change | Rationale |
|--------|-----------|
| Fixed UID/GID 1000 | Bind mount compatibility with host user |
| `tini` as PID 1 | Proper signal forwarding to uvicorn |
| Pre-download cross-encoder model | Eliminate runtime HuggingFace download (24MB) |
| `ENV HF_HOME=/app/.cache/huggingface` | Stable model cache path |
| Build args (`PYTHON_VERSION`, `RUST_VERSION`) | Version flexibility |

### 10.2 Frontend (`frontend/Dockerfile`)

| Change | Rationale |
|--------|-----------|
| Pin `node:22-alpine` (not `lts-alpine`) | Prevent cache invalidation on LTS roll |
| `NEXT_PUBLIC_API_URL` as optional build arg | Advanced deployment override |
| Add `.dockerignore` | Exclude test files, reduce build context |
| Combine `addgroup`/`adduser` into one layer | Minor image optimization |

---

## 11. Volume Strategy

| Volume | Type | Survives `down` | Survives `down -v` | Purpose |
|--------|------|:---:|:---:|---------|
| `./data:/data:z` | Bind mount | Yes | Yes | SQLite DB, uploads (user-visible) |
| `qdrant_data` | Named volume | Yes | No | Qdrant internal storage |
| `ollama_models` | Named volume | Yes | No | Ollama model cache (~5GB) |
| `/app/node_modules` (dev) | Anonymous | No | No | Container deps isolation |
| `/app/.next` (dev) | Anonymous | No | No | Container build cache isolation |

---

## 12. Implementation Priority

| Phase | Items | Effort |
|-------|-------|--------|
| **P0 — Critical** | Compose decomposition, GPU overlay, frontend rewrites, `/healthz` endpoint, `embedinator.sh`/`embedinator.ps1` | High |
| **P1 — High** | Backend health enhancement (`/api/health/live`), Dockerfile improvements (UID 1000, tini, cross-encoder), dev overlay fix, `.gitattributes` | Medium |
| **P2 — Medium** | `BackendStatusProvider`, `StatusBanner`, chat input gating, graceful shutdown, log rotation | Medium |
| **P3 — Low** | First-run onboarding, root redirect, `.dockerignore`, build arg flexibility, connection retry | Low |

---

## 13. What Does NOT Change

- **Makefile**: All 14 targets preserved unchanged. `make dev`, `make up`, `make down` continue to work for developers with local toolchains.
- **Backend code structure**: No new Python modules (except health endpoint enhancement). No new dependencies.
- **Frontend pages/components**: Existing 5 pages, 20+ components unchanged. Only additions (StatusBanner, BackendStatusProvider, /healthz route, root redirect).
- **Database schema**: No changes to SQLite or Qdrant.
- **Testing**: Existing 1487+ tests unaffected.

---

## Appendix A: Files to Create

| File | Purpose |
|------|---------|
| `embedinator.sh` | Bash/zsh launcher (macOS + Linux) |
| `embedinator.ps1` | PowerShell launcher (Windows) |
| `docker-compose.gpu-nvidia.yml` | NVIDIA GPU overlay (deploy reservations) |
| `docker-compose.gpu-amd.yml` | AMD ROCm GPU overlay (image swap + /dev/kfd,/dev/dri) |
| `docker-compose.gpu-intel.yml` | Intel Arc GPU overlay (/dev/dri passthrough, experimental) |
| `.gitattributes` | Line ending enforcement |
| `frontend/.dockerignore` | Build context exclusion |
| `frontend/app/healthz/route.ts` | Frontend health endpoint |
| `frontend/app/page.tsx` | Root redirect to /chat |
| `frontend/components/BackendStatusProvider.tsx` | Backend health context |
| `frontend/components/StatusBanner.tsx` | Global degraded state banner |
| `scripts/ollama-init.sh` | Optional: robust model pull script |

## Appendix B: Files to Modify

| File | Changes |
|------|---------|
| `docker-compose.yml` | Remove GPU block, add health checks, SELinux `:z`, log rotation, frontend `BACKEND_URL` |
| `docker-compose.dev.yml` | Fix volume mounts, `target: deps`, correct env vars |
| `Dockerfile.backend` | Fixed UID 1000, tini, cross-encoder pre-download, HF_HOME |
| `frontend/Dockerfile` | Pin Node 22, build arg, combine layers |
| `frontend/next.config.ts` | Add `rewrites()` for API proxy |
| `frontend/lib/api.ts` | Change `API_BASE` to empty string |
| `frontend/app/layout.tsx` | Wrap with `BackendStatusProvider` |
| `frontend/components/SidebarLayout.tsx` | Insert `StatusBanner` |
| `frontend/components/ChatInput.tsx` | Backend status gating |
| `frontend/components/ChatPanel.tsx` | First-run onboarding |
| `backend/api/health.py` | Add `/api/health/live`, enhance readiness response |
| `backend/main.py` | Graceful shutdown, upload dir creation, write-access test |
| `.env.example` | Add `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, `EMBEDINATOR_PORT_*` documentation |
