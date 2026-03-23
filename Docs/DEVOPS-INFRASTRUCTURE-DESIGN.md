# The Embedinator -- DevOps Infrastructure Design

Version: 1.0
Date: 2026-03-19
Author: DevOps Architect
Status: DESIGN (not yet implemented)

---

## Table of Contents

1. [Docker Compose Decomposition](#1-docker-compose-decomposition)
2. [Ollama Service Redesign](#2-ollama-service-redesign)
3. [Dockerfile Improvements](#3-dockerfile-improvements)
4. [Volume Strategy](#4-volume-strategy)
5. [Health Check Architecture](#5-health-check-architecture)
6. [Environment Management](#6-environment-management)
7. [Cross-Platform Docker Considerations](#7-cross-platform-docker-considerations)
8. [Launcher Script Design](#8-launcher-script-design)

---

## 1. Docker Compose Decomposition

### 1.1 Decision: Overlay Files Over Profiles

**Recommendation: Use file-based composition (`-f` stacking), not Compose profiles.**

Rationale:

- Profiles require every developer to remember `--profile gpu` flags. Forgetting
  silently omits services rather than erroring.
- File overlays are explicit: the launcher script selects exactly which files to
  compose. The user never needs to know the flag.
- File overlays allow the GPU block to be a pure additive merge. With profiles,
  the GPU reservation would live inside the base file gated by a profile label,
  meaning the base file still references NVIDIA driver config even on machines
  without GPUs -- Docker Desktop on macOS will emit warnings.
- `docker compose config` on the merged result produces a single resolved YAML
  that is trivially debuggable.

### 1.2 File Layout

```
project-root/
  docker-compose.yml              # Base: all 4 services, no GPU, no dev mounts
  docker-compose.gpu-nvidia.yml   # Overlay: adds deploy.resources to ollama
  docker-compose.dev.yml          # Overlay: bind mounts + hot reload for backend/frontend
```

### 1.3 docker-compose.yml (Base)

This file replaces the current `docker-compose.yml`. Key changes from current state:

- **Remove** the entire `deploy.resources.reservations.devices` block from ollama.
  The base file must be loadable on any machine, including macOS (no NVIDIA driver)
  and CI runners (no GPU).
- **Remove** the inline `entrypoint` model-pull from ollama. Model pulling moves to
  a dedicated init script (see Section 2).
- **Add** a healthcheck to the frontend service.
- **Change** ollama entrypoint to just `ollama serve` (the default).
- **Add** SELinux `:z` suffix to all bind-mount volumes (see Section 4).
- **Keep** the `depends_on` chain as-is: backend depends on qdrant(healthy) +
  ollama(healthy); frontend depends on backend(healthy).

Service definitions:

**qdrant**
- image: qdrant/qdrant:v1.14.0 (pin to a specific version, not :latest)
- ports: 6333:6333, 6334:6334
- volumes: qdrant_data:/qdrant/storage (named volume, NOT bind mount -- see Section 4.2)
- healthcheck: unchanged (TCP probe on 6333)
- restart: unless-stopped

**ollama**
- image: ollama/ollama:latest (latest is acceptable here -- Ollama images are backward-compatible)
- ports: 11434:11434
- volumes: ollama_models:/root/.ollama (named volume, kept as-is)
- entrypoint: REMOVE the current inline entrypoint entirely. Do not set entrypoint
  at all -- let the default `ollama serve` from the image run.
- healthcheck: see Section 5
- restart: unless-stopped
- NO deploy.resources block (GPU-free base)

**backend**
- build: context=., dockerfile=Dockerfile.backend
- ports: 8000:8000
- env_file: .env
- environment: same as current (QDRANT_HOST, QDRANT_PORT, OLLAMA_BASE_URL,
  SQLITE_PATH, UPLOAD_DIR, LOG_LEVEL_OVERRIDES, RUST_WORKER_PATH)
- depends_on: qdrant(service_healthy), ollama(service_healthy)
- volumes: embedinator_data:/data (named volume -- see Section 4.2)
- healthcheck: curl -f http://localhost:8000/api/health (unchanged)
- restart: unless-stopped

**frontend**
- build: context=./frontend, dockerfile=Dockerfile
- ports: 3000:3000
- depends_on: backend(service_healthy) -- CHANGE from bare depends_on to condition
- environment: NEXT_PUBLIC_API_URL=http://backend:8000
- healthcheck: NEW -- see Section 5
- restart: unless-stopped

**volumes (named)**
```
volumes:
  ollama_models:
  qdrant_data:
  embedinator_data:
```

### 1.4 docker-compose.gpu-nvidia.yml (GPU Overlay)

Minimal overlay. Contains ONLY the additive GPU reservation for ollama.

```yaml
# GPU overlay -- merged when NVIDIA GPU is detected by the launcher.
# Usage: docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml up
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

This file does nothing else. No other services are mentioned.

**Detection logic** (in the launcher): Run `docker info --format '{{.Runtimes}}'` and
check for "nvidia" in the output, OR check if `nvidia-smi` exits 0. If either
succeeds, include this overlay.

### 1.5 docker-compose.dev.yml (Dev Overlay)

Used when the launcher is invoked with `--dev`, OR when a developer calls `make dev`.

```yaml
# Dev overlay -- bind mounts for hot reload.
# Usage: docker compose -f docker-compose.yml -f docker-compose.dev.yml up
services:
  backend:
    build:
      target: dev
    volumes:
      - ./backend:/app/backend:z
      - ./requirements.txt:/app/requirements.txt:z
      - embedinator_data:/data
    command: ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
    environment:
      DEBUG: "true"

  frontend:
    build:
      target: dev
    volumes:
      - ./frontend/app:/app/app:z
      - ./frontend/components:/app/components:z
      - ./frontend/hooks:/app/hooks:z
      - ./frontend/lib:/app/lib:z
      - ./frontend/public:/app/public:z
      - ./frontend/next.config.ts:/app/next.config.ts:z
      - ./frontend/tailwind.config.ts:/app/tailwind.config.ts:z
      - ./frontend/tsconfig.json:/app/tsconfig.json:z
      # EXCLUDE node_modules and .next -- use image-built copies
    command: ["npm", "run", "dev"]
    environment:
      NODE_ENV: development
```

Key design points:

- Backend bind mounts ONLY `./backend` and `requirements.txt`. The Rust binary
  stays in the image (it does not change during frontend/backend development).
- Frontend mounts individual source directories, NOT the entire `./frontend`
  directory. This avoids overwriting the container's `node_modules/` and `.next/`
  with the host's versions (or their absence).
- The `build.target: dev` attribute references a new `dev` stage in each
  Dockerfile (see Section 3). This stage includes dev dependencies.
- The `:z` suffix on every bind mount handles SELinux relabeling.

### 1.6 Composition Matrix

The launcher assembles the correct `-f` flags:

| Scenario                      | Files composed                                           |
|-------------------------------|----------------------------------------------------------|
| Production, no GPU            | `docker-compose.yml`                                     |
| Production, NVIDIA GPU        | `docker-compose.yml` + `docker-compose.gpu-nvidia.yml`   |
| Dev mode, no GPU              | `docker-compose.yml` + `docker-compose.dev.yml`          |
| Dev mode, NVIDIA GPU          | `docker-compose.yml` + `docker-compose.gpu-nvidia.yml` + `docker-compose.dev.yml` |

### 1.7 Makefile Compatibility

The existing Makefile is preserved UNCHANGED (14 targets, as specked in spec-17).
The `make up` target currently runs `docker compose up --build -d` which loads
only `docker-compose.yml` by default. This is correct for the production-no-GPU
case. Developers who need GPU can set `COMPOSE_FILE` env var:

```
export COMPOSE_FILE=docker-compose.yml:docker-compose.gpu-nvidia.yml
make up
```

The `make dev` target (which runs `docker compose up -d qdrant ollama`) also
continues to work as-is. The dev overlay is for containerized development; `make dev`
is for local-toolchain development where only infra services are containerized.

---

## 2. Ollama Service Redesign

### 2.1 Problem Statement

The current entrypoint is:
```
/bin/sh -c "ollama serve & sleep 5 && ollama pull qwen2.5:7b && wait"
```

Issues:
1. `sleep 5` is a race condition. On cold start (no cached layers), the server
   may not be ready in 5 seconds. On fast machines, it wastes 5 seconds.
2. The `ollama pull` blocks the entrypoint. If the pull fails (network error),
   the container exits and restarts in a loop.
3. The healthcheck passes as soon as the HTTP server is up, but `depends_on:
   service_healthy` in the backend service means the backend starts before the
   model is actually available, leading to 503s on the first chat request.
4. Only `qwen2.5:7b` is pulled. The embedding model `nomic-embed-text` is not
   pulled, so ingestion fails until `make pull-models` is run manually.

### 2.2 Recommendation: External Init Script

**Decision: Pull models from the launcher script, not from the Ollama container
entrypoint.**

Rationale:
- The Ollama container's job is to serve. It should start, become healthy, and stay
  healthy. Mixing serving and pulling in the entrypoint creates fragile lifecycle
  coupling.
- The launcher script has access to the user's terminal for progress feedback. A
  container entrypoint does not (logs are buffered, not interactive).
- Model pull is a one-time operation (models are persisted in the `ollama_models`
  named volume). The entrypoint runs on every container restart.
- If the pull is interrupted (Ctrl-C), only the launcher stops. The Ollama server
  container stays healthy for any other running services.

### 2.3 Alternative Considered: scripts/ollama-init.sh as Sidecar

A `docker compose run --rm ollama-init` sidecar service that mounts the same
`ollama_models` volume and runs `ollama pull`. This was rejected because:
- It requires the Ollama server to be running (pulls go through the HTTP API).
- A sidecar adds complexity to the compose file for a one-time operation.
- The launcher script already knows the server is healthy (it polls the healthcheck)
  and can simply `docker exec` the pull.

### 2.4 Two-Phase Startup Design

**Phase 1: Server readiness (blocking -- backend waits for this)**
- Ollama container starts with default entrypoint (`ollama serve`).
- Healthcheck confirms HTTP server is listening (see Section 5).
- `depends_on: ollama: condition: service_healthy` in the backend service gates on this.

**Phase 2: Model availability (non-blocking for compose, blocking for launcher)**
- After all 4 services are healthy, the launcher runs model pulls:
  ```
  docker exec embedinator-ollama ollama pull qwen2.5:7b
  docker exec embedinator-ollama ollama pull nomic-embed-text
  ```
- The launcher displays pull progress to the user's terminal (stdout passthrough).
- If models are already present (named volume persists them), the pull is a no-op
  that completes in under 1 second.

### 2.5 Model Pull Progress Feedback

`docker exec` with an attached TTY passes Ollama's progress bar directly to the
user's terminal. The launcher should use:
```
docker exec -t embedinator-ollama ollama pull <model>
```

The `-t` flag allocates a pseudo-TTY so the progress bar renders correctly. If
stdin is not a TTY (CI/piped), omit `-t` and Ollama falls back to line-by-line
progress output.

### 2.6 Configurable Model List

The launcher reads the model list from `.env`:
```
OLLAMA_MODELS=qwen2.5:7b,nomic-embed-text
```

Default value in `.env.example`: `qwen2.5:7b,nomic-embed-text`

This allows users to swap models without editing compose files. The launcher
splits on comma and pulls each model sequentially.

New `.env.example` entry:
```
# OLLAMA_MODELS -- Comma-separated list of Ollama models to pull on first run.
# Expected: str. Default: qwen2.5:7b,nomic-embed-text.
OLLAMA_MODELS=qwen2.5:7b,nomic-embed-text
```

---

## 3. Dockerfile Improvements

### 3.1 Dockerfile.backend

#### 3.1.1 Fixed UID/GID 1000

Current state: `addgroup --system appgroup && adduser --system --ingroup appgroup
--no-create-home appuser` -- this uses dynamically assigned UID/GID.

Change to fixed UID/GID 1000:
```
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /sbin/nologin -M appuser
```

Rationale: Bind-mounted volumes (dev mode) must have matching UID between host
and container. UID 1000 is the default first user on most Linux distributions.
On macOS/WSL2, Docker Desktop handles UID mapping transparently, so 1000 is safe.

#### 3.1.2 Build Cache Optimization -- Layer Ordering

Current order:
1. apt-get install curl
2. COPY Rust binary
3. COPY requirements.txt + pip install
4. COPY backend/

This is already well-ordered. The Rust binary copy is placed before pip install
because the Rust stage produces a single static binary that changes infrequently
relative to Python dependencies.

One improvement: separate the `apt-get` layer to run before the Rust COPY so that
a Rust recompile does not invalidate the apt cache:

```
# Stage 2 -- Python runtime
FROM python:3.14-slim AS runtime

# System dependencies (cached independently)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tini && \
    rm -rf /var/lib/apt/lists/*

# Rust binary (rarely changes)
COPY --from=rust-builder /build/target/release/embedinator-worker \
    /app/ingestion-worker/target/release/embedinator-worker

# Python dependencies (changes when requirements.txt changes)
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (changes most frequently -- last layer)
COPY backend/ ./backend/

# Non-root user with fixed UID
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /sbin/nologin -M appuser

USER appuser
EXPOSE 8000

ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### 3.1.3 Add tini as PID 1 Init

Add `tini` (installed via apt-get) as the ENTRYPOINT. This ensures proper signal
forwarding to uvicorn and prevents zombie processes. The CMD becomes the argument
to tini.

#### 3.1.4 Dev Stage

Add a `dev` stage for the dev overlay:

```
# Dev stage -- includes reload-capable uvicorn, same base
FROM runtime AS dev
# No additional packages needed -- uvicorn --reload is in the standard install.
# The dev overlay bind-mounts source code and overrides CMD.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

The `dev` stage is identical to `runtime` but with a different default CMD. This
is a no-op stage that exists purely so `docker-compose.dev.yml` can reference
`build.target: dev` without error. The actual behavior change comes from the
compose override's `command:` directive.

#### 3.1.5 Build Args

Add build args for version flexibility:

```
ARG PYTHON_VERSION=3.14
ARG RUST_VERSION=1.93
FROM rust:${RUST_VERSION} AS rust-builder
...
FROM python:${PYTHON_VERSION}-slim AS runtime
```

This allows CI to test against different versions without editing the Dockerfile.

#### 3.1.6 Complete Dockerfile.backend Structure

```
ARG RUST_VERSION=1.93
ARG PYTHON_VERSION=3.14

# --- Stage 1: Rust builder ---
FROM rust:${RUST_VERSION} AS rust-builder
WORKDIR /build
COPY ingestion-worker/Cargo.toml ingestion-worker/Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -f target/release/deps/embedinator_worker*
COPY ingestion-worker/src ./src
RUN cargo build --release

# --- Stage 2: Python runtime ---
FROM python:${PYTHON_VERSION}-slim AS runtime
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl tini && \
    rm -rf /var/lib/apt/lists/*
COPY --from=rust-builder /build/target/release/embedinator-worker \
    /app/ingestion-worker/target/release/embedinator-worker
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /sbin/nologin -M appuser
USER appuser
EXPOSE 8000
ENTRYPOINT ["tini", "--"]
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

# --- Stage 3: Dev target (same image, different default CMD) ---
FROM runtime AS dev
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### 3.2 frontend/Dockerfile

#### 3.2.1 Fixed UID/GID 1000

Current state uses UID/GID 1001. Change to 1000 for consistency with the backend:

```
RUN addgroup --system --gid 1000 nodejs && \
    adduser --system --uid 1000 nextjs
```

Note: Alpine uses `addgroup`/`adduser` (busybox), not `groupadd`/`useradd`.

#### 3.2.2 Add tini

Alpine base does not include tini by default. Add it:

```
RUN apk add --no-cache tini
ENTRYPOINT ["tini", "--"]
```

#### 3.2.3 Build Args

```
ARG NODE_VERSION=lts
FROM node:${NODE_VERSION}-alpine AS base
```

#### 3.2.4 NEXT_PUBLIC_API_URL as Build Arg

The `NEXT_PUBLIC_API_URL` environment variable is baked into the Next.js bundle at
build time (all `NEXT_PUBLIC_*` vars are). The current setup sets it as a runtime
`environment` variable in docker-compose.yml, which has NO effect on the standalone
build. The next.config.ts manually bridges this via `env: { NEXT_PUBLIC_API_URL:
process.env.NEXT_PUBLIC_API_URL }`, but this only works at build time.

For the containerized production build, the API URL is always `http://backend:8000`
(internal Docker network). However, the browser needs to reach the API at
`http://localhost:8000` (or the host's IP). The current architecture uses server-side
API calls proxied through the Next.js server, so the internal URL is correct.

Keep the current approach but document it clearly. The `NEXT_PUBLIC_API_URL` in
compose is used at build time via the builder stage. Add a build arg:

```
FROM base AS builder
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
```

And in docker-compose.yml:
```yaml
frontend:
  build:
    context: ./frontend
    dockerfile: Dockerfile
    args:
      NEXT_PUBLIC_API_URL: http://backend:8000
```

#### 3.2.5 Dev Stage

```
FROM base AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# Dev mode: next dev with hot reload. Source dirs bind-mounted by compose overlay.
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

#### 3.2.6 Complete frontend/Dockerfile Structure

```
ARG NODE_VERSION=lts
FROM node:${NODE_VERSION}-alpine AS base

# --- Dependencies ---
FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci

# --- Builder ---
FROM base AS builder
WORKDIR /app
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

# --- Production runner ---
FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
RUN apk add --no-cache tini && \
    addgroup --system --gid 1000 nodejs && \
    adduser --system --uid 1000 nextjs
COPY --from=builder /app/public ./public 2>/dev/null || true
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"
ENTRYPOINT ["tini", "--"]
CMD ["node", "server.js"]

# --- Dev target ---
FROM base AS dev
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]
```

### 3.3 .dockerignore Updates

The current `.dockerignore` is comprehensive. Add the following entries:

```
# Compose overlays (not needed in build context)
docker-compose*.yml

# Launcher scripts
start.sh
start.ps1

# Frontend-specific ignores (for frontend/Dockerfile context)
# NOTE: frontend/Dockerfile uses context=./frontend, so these are relative to frontend/
# A separate frontend/.dockerignore is needed.
```

Create `frontend/.dockerignore`:
```
node_modules/
.next/
out/
.env
.env.*
!.env.example
*.log
test-results/
coverage/
.playwright/
```

---

## 4. Volume Strategy

### 4.1 Bind Mounts vs Named Volumes

| Volume | Type | Rationale |
|--------|------|-----------|
| `qdrant_data` | Named | Qdrant's internal storage format is opaque. Users never need to browse these files. Named volumes have better I/O performance on Docker Desktop (macOS/Windows). |
| `ollama_models` | Named | Model blobs are large (4-8 GB). Named volumes avoid filesystem overhead. Already named in current config. |
| `embedinator_data` | Named | **CHANGE from current bind mount `./data:/data`**. The SQLite DB and uploads directory are application-managed. Named volumes prevent accidental host-side modification and improve macOS/WSL2 performance. |
| `./backend` | Bind | Dev mode only. Required for hot reload -- host edits must reflect in container. |
| `./frontend/*` | Bind | Dev mode only. Same rationale. Selective mounts exclude node_modules. |

### 4.2 Migration: ./data Bind Mount to Named Volume

The current `./data:/data` bind mount means the SQLite DB and uploads live on the
host filesystem at `./data/`. Changing to a named volume means they live inside
Docker's volume storage.

**Migration consideration**: Existing users who have data in `./data/` will lose
access when switching to a named volume. The launcher script must handle this:

1. On first run after the change, check if `./data/embedinator.db` exists on the host.
2. If it does, print a warning: "Existing data found in ./data/. Migrating to
   Docker volume..."
3. Use `docker cp` or a temporary container to copy `./data/` contents into the
   named volume.
4. Rename `./data/` to `./data.migrated/` as a backup.

Alternatively, keep `./data:/data:z` as a bind mount for simplicity and user
transparency (users can see and backup their own data).

**FINAL DECISION: Keep ./data as a bind mount with :z suffix.**

Rationale:
- Users expect to find their SQLite DB and uploaded files in a visible directory.
- Backup is trivial: `cp -r ./data ./data-backup`.
- The performance difference is negligible for SQLite (WAL mode) and file uploads.
- Named volumes require `docker volume` commands to inspect/backup, which is
  hostile to the "only prerequisite is Docker" promise.

Updated volume definitions:

```yaml
services:
  backend:
    volumes:
      - ./data:/data:z      # Bind mount, SELinux-safe

  qdrant:
    volumes:
      - qdrant_data:/qdrant/storage   # Named, opaque internal storage

volumes:
  ollama_models:     # Named, large model blobs
  qdrant_data:       # Named, opaque vector indices
```

### 4.3 SELinux :z Suffix

On Fedora, RHEL, and CentOS (SELinux enforcing), bind mounts fail with permission
denied unless the mount is relabeled. The `:z` suffix tells Docker to relabel the
mount point with a shared SELinux context.

Apply `:z` to ALL bind mounts:
- `./data:/data:z`
- Dev overlay: all `./backend:/app/backend:z`, `./frontend/*:/app/*:z` mounts

Named volumes do NOT need `:z` -- Docker manages their SELinux labels automatically.

The `:z` suffix is harmless on non-SELinux systems (macOS, Windows, Ubuntu). It is
a no-op.

WARNING: Do NOT use `:Z` (uppercase). `:Z` applies a private unshared label, which
would prevent multiple containers from accessing the same mount. `:z` applies a
shared label, which is correct for our use case (backend writes to `./data`, and
a future debug container might read it).

### 4.4 Data Persistence Semantics

| Command | Effect on ./data (bind) | Effect on qdrant_data (named) | Effect on ollama_models (named) |
|---------|-------------------------|-------------------------------|----------------------------------|
| `docker compose down` | Preserved | Preserved | Preserved |
| `docker compose down -v` | Preserved (bind mounts are never removed by -v) | **DELETED** | **DELETED** |
| `make clean` | DELETED (rm -rf data/) | Preserved | Preserved |
| `make clean-all` | DELETED | **DELETED** (docker compose down -v) | **DELETED** |

Document this behavior in the launcher's `--help` output and in .env.example
comments.

### 4.5 Dev Mode Volume Mounts -- Exclusion Strategy

The dev overlay must NOT mount host `node_modules/` or `.next/` into the container.
These directories contain platform-specific binaries (e.g., SWC, esbuild) that
differ between the host OS and the container's Alpine Linux.

Strategy: mount individual source directories rather than the entire project root.
See Section 1.5 for the exact mount list.

For the backend, `__pycache__/` directories are harmless (Python regenerates them)
and do not need exclusion.

---

## 5. Health Check Architecture

### 5.1 Per-Service Health Checks

#### 5.1.1 Qdrant

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -q --spider http://localhost:6333/healthz || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 10s
```

Change from current: Replace the `bash -c 'echo -e ... > /dev/tcp/...'` pattern
with `wget --spider`. The Qdrant image is based on Debian and includes `wget`.
The TCP redirect trick is fragile (depends on bash, not just sh) and harder to
read. `wget --spider` is a proper HTTP health check.

Add `start_period: 10s` to give Qdrant time to initialize its index on first boot.

#### 5.1.2 Ollama

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -q --spider http://localhost:11434/api/tags || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 15s
```

Change from current: Same `bash -c` to `wget --spider` improvement. The Ollama
image includes `wget`.

IMPORTANT: This healthcheck confirms that the Ollama HTTP server is responding,
NOT that models are loaded. Model availability is checked by the launcher script
AFTER all services are healthy (see Section 2.4). This is intentional -- the
backend's health endpoint already probes Ollama and reports "degraded" if Ollama
cannot serve inference. The user sees "starting..." in the launcher until models
are ready.

`retries: 5` with `interval: 10s` gives Ollama up to 65 seconds to start
(start_period 15s + 5 retries * 10s). This is sufficient for CPU-only cold starts.

#### 5.1.3 Backend

```yaml
healthcheck:
  test: ["CMD", "curl", "-sf", "http://localhost:8000/api/health"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

Changes from current:
- Add `-s` (silent) flag to curl to suppress progress output in logs.
- Increase `retries` to 5 (from 3). The backend loads sentence-transformer models
  on startup, which takes 15-30 seconds. With 3 retries and 10s interval, the
  health check only allows 30 seconds after start_period, which is tight.
- Add `start_period: 30s`. The backend loads the reranker model (~400MB),
  embedding model (~300MB), compiles 3 LangGraph graphs, and initializes SQLite +
  Qdrant connections. On first run, sentence-transformers downloads models from
  HuggingFace, which can take 60+ seconds. The start_period prevents premature
  unhealthy marking.

NOTE: The existing `/api/health` endpoint probes SQLite, Qdrant, and Ollama. If
any is unreachable, it returns HTTP 503 ("degraded"). This means the backend
healthcheck will fail if Qdrant or Ollama are down, which is correct behavior --
a "healthy" backend that cannot reach its dependencies is not truly healthy.

#### 5.1.4 Frontend

```yaml
healthcheck:
  test: ["CMD-SHELL", "wget -q --spider http://localhost:3000 || exit 1"]
  interval: 10s
  timeout: 5s
  retries: 3
  start_period: 15s
```

NEW healthcheck (the current frontend service has none). The Next.js standalone
server responds to HTTP requests on port 3000. A simple `wget --spider` on the
root path confirms the server is listening. Alpine base includes `wget`.

### 5.2 Dependency Chain

```
qdrant (healthy) ─┐
                   ├──> backend (healthy) ──> frontend (healthy)
ollama (healthy) ──┘
```

Compose `depends_on` with `condition: service_healthy`:

```yaml
backend:
  depends_on:
    qdrant:
      condition: service_healthy
    ollama:
      condition: service_healthy

frontend:
  depends_on:
    backend:
      condition: service_healthy
```

This change upgrades the frontend's dependency from bare `depends_on: [backend]`
(which only waits for the container to start) to `condition: service_healthy`
(which waits for the backend's healthcheck to pass).

### 5.3 Launcher Health Polling

After `docker compose up -d`, the launcher polls service health:

```
Phase 1: Infrastructure services
  Poll: docker inspect --format='{{.State.Health.Status}}' embedinator-qdrant
  Poll: docker inspect --format='{{.State.Health.Status}}' embedinator-ollama
  Timeout: 120 seconds (accounts for first-run cold start)
  Display: spinner with service name and elapsed time

Phase 2: Application services
  Poll: docker inspect --format='{{.State.Health.Status}}' embedinator-backend
  Timeout: 180 seconds (accounts for model download on first run)
  Display: spinner with service name and elapsed time

  Poll: docker inspect --format='{{.State.Health.Status}}' embedinator-frontend
  Timeout: 60 seconds
  Display: spinner with service name and elapsed time

Phase 3: Model pull (see Section 2)
  docker exec embedinator-ollama ollama pull <model>
  Timeout: 600 seconds per model (large models on slow connections)
  Display: passthrough of Ollama's progress bar
```

If any service fails its timeout, the launcher prints:
1. Which service failed.
2. The last 20 lines of that service's logs (`docker logs --tail 20 <container>`).
3. A suggestion to run `docker logs <container>` for full output.

### 5.4 Timeout Strategy

| Context | Qdrant | Ollama | Backend | Frontend | Model pull (per model) |
|---------|--------|--------|---------|----------|------------------------|
| First run | 30s | 30s | 180s | 60s | 600s |
| Subsequent run | 15s | 15s | 60s | 30s | 10s (no-op pull) |

The launcher does not need to distinguish first run from subsequent runs. It uses
the "first run" timeouts always. Subsequent runs simply complete faster because
images are cached, volumes are populated, and models are already present.

---

## 6. Environment Management

### 6.1 .env File Generation

The launcher generates `.env` from `.env.example` on first run.

Algorithm:
1. Check if `.env` exists.
2. If yes, skip generation. Print "Using existing .env file."
3. If no:
   a. Copy `.env.example` to `.env`.
   b. Generate a Fernet key and inject it (see 6.2).
   c. Print "Generated .env file. Review and customize if needed."

The `.env.example` file already contains sensible defaults for all variables. The
copy-and-inject approach means the user gets a working configuration immediately.

### 6.2 Fernet Key Auto-Generation

The `EMBEDINATOR_FERNET_KEY` variable must be a valid Fernet key (44-char
URL-safe base64 string). The system architect mandates generation via a
disposable Docker container to avoid requiring Python on the host.

Command:
```bash
docker run --rm python:3.14-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This pulls the python:3.14-slim image (which will be needed anyway for the backend
build) and runs a one-shot key generation. The output is captured and injected
into `.env` via sed:
```bash
FERNET_KEY=$(docker run --rm python:3.14-slim python -c \
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
sed -i "s|^EMBEDINATOR_FERNET_KEY=.*|EMBEDINATOR_FERNET_KEY=${FERNET_KEY}|" .env
```

For `start.ps1` (PowerShell):
```powershell
$FernetKey = docker run --rm python:3.14-slim python -c `
  "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
(Get-Content .env) -replace '^EMBEDINATOR_FERNET_KEY=.*', "EMBEDINATOR_FERNET_KEY=$FernetKey" |
  Set-Content .env
```

### 6.3 Environment Variable Precedence

Docker Compose resolves environment variables in this order (highest priority first):

1. `environment:` block in docker-compose.yml (e.g., `QDRANT_HOST: qdrant`)
2. `env_file: .env` contents
3. Shell environment variables on the host (for `${VAR:-default}` interpolation)
4. Defaults in the application code (pydantic Settings defaults)

Design principle: Variables that MUST differ between host and container (like
`QDRANT_HOST=qdrant` for Docker networking vs `QDRANT_HOST=localhost` for local dev)
are set in the compose `environment:` block, which takes precedence over `.env`.
This means the `.env` file's `QDRANT_HOST=localhost` value is correctly overridden
inside containers but used correctly during local `make dev-backend` runs.

### 6.4 Secrets Handling

| Variable | Location | Rationale |
|----------|----------|-----------|
| `EMBEDINATOR_FERNET_KEY` | `.env` (auto-generated) | Per-installation secret. Must not be committed. |
| `QDRANT_HOST`, `QDRANT_PORT` | compose `environment:` | Networking config, not secret. |
| `OLLAMA_BASE_URL` | compose `environment:` | Networking config, not secret. |
| Cloud provider API keys | SQLite DB (Fernet-encrypted) | Entered via the UI, encrypted at rest. Never in .env. |
| `LOG_LEVEL`, `DEBUG`, etc. | `.env` | Tuning knobs, not secrets. |

The `.env` file is already in `.gitignore` and `.dockerignore`. The `.env.example`
file contains no real secrets (empty `EMBEDINATOR_FERNET_KEY=`).

### 6.5 New .env.example Entries

Add these entries to the existing `.env.example`:

```
# OLLAMA_MODELS -- Comma-separated Ollama models to pull on first run.
# Expected: str. Default: qwen2.5:7b,nomic-embed-text.
OLLAMA_MODELS=qwen2.5:7b,nomic-embed-text
```

---

## 7. Cross-Platform Docker Considerations

### 7.1 WSL2 Filesystem Performance

**Problem**: When the project directory is on `/mnt/c/` (Windows filesystem
accessed through WSL2), Docker bind mounts suffer severe I/O penalties. File
operations are 5-10x slower because every access crosses the 9P filesystem bridge.

**Detection** (in `start.sh`):
```
Check if running inside WSL: test -f /proc/version && grep -qi microsoft /proc/version
If WSL detected, check if $PWD starts with /mnt/
If /mnt/ detected, print WARNING (not error -- do not block execution):
  "WARNING: Project is on Windows filesystem (/mnt/c/...).
   Performance will be significantly degraded.
   For best results, clone the project to the WSL2 native filesystem:
     ~/Projects/The-Embedinator"
```

**Detection** (in `start.ps1`):
Not applicable -- PowerShell runs natively on Windows. Docker Desktop for Windows
accesses files through its own VM, which has consistent performance regardless of
filesystem location.

### 7.2 macOS Docker VM Memory

**Problem**: Docker Desktop on macOS runs in a Linux VM with a default memory
limit (typically 2 GB on older configs, 4-8 GB on newer). The Embedinator needs
at minimum 4 GB for Ollama (model inference) + backend (reranker + embedder) +
Qdrant.

**Detection** (in `start.sh`):
```
If on macOS (uname -s == Darwin):
  DOCKER_MEM=$(docker info --format '{{.MemTotal}}')
  Convert to GB.
  If < 4 GB:
    Print WARNING:
      "WARNING: Docker has only X GB memory allocated.
       The Embedinator needs at least 4 GB (8 GB recommended).
       Increase memory in Docker Desktop > Settings > Resources."
  If < 6 GB:
    Print NOTE:
      "NOTE: Docker has X GB memory. 8 GB recommended for smooth operation."
```

**Detection** (in `start.ps1`):
Same logic using `docker info` output parsing.

### 7.3 Linux Docker Socket Permissions

**Problem**: On Linux, the Docker socket (`/var/run/docker.sock`) is owned by
the `docker` group. Users not in this group get "permission denied" errors.

**Detection** (in `start.sh`):
```
If on Linux (uname -s == Linux):
  Run: docker info > /dev/null 2>&1
  If exit code != 0:
    Check if user is in docker group: groups | grep -q docker
    If not in docker group:
      Print ERROR:
        "ERROR: Cannot connect to Docker. Your user is not in the 'docker' group.
         Fix: sudo usermod -aG docker $USER && newgrp docker
         Then re-run this script."
      Exit 1.
    Else:
      Print ERROR:
        "ERROR: Cannot connect to Docker. Is the Docker daemon running?
         Fix: sudo systemctl start docker"
      Exit 1.
```

### 7.4 Port Conflict Detection

**Problem**: Ports 3000, 6333, 6334, 8000, or 11434 may already be in use by other
applications, causing Docker containers to fail to start.

**Detection** (in `start.sh`):
```
For each port in (3000 6333 6334 8000 11434):
  If Linux: ss -tlnp | grep ":$PORT "
  If macOS: lsof -iTCP:$PORT -sTCP:LISTEN
  If port is in use:
    Identify the process (if possible).
    Print WARNING:
      "WARNING: Port $PORT is already in use (by $PROCESS).
       Service $SERVICE_NAME will fail to bind.
       Stop the conflicting process or change the port in .env."
    Set a flag but do NOT exit -- let Docker report the actual error.
```

**Detection** (in `start.ps1`):
```powershell
Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
```

### 7.5 Docker Compose Version Check

**Problem**: The launcher uses `docker compose` (v2 plugin syntax). Older installs
may only have `docker-compose` (v1 standalone) or no compose at all.

**Detection**:
```
Run: docker compose version
If exit code != 0:
  Run: docker-compose version
  If exit code == 0:
    Print ERROR:
      "ERROR: Found docker-compose (v1) but not 'docker compose' (v2).
       Install the Compose plugin: https://docs.docker.com/compose/install/"
    Exit 1.
  Else:
    Print ERROR:
      "ERROR: Docker Compose is not installed.
       Install Docker Desktop or the Compose plugin."
    Exit 1.
Parse version number. If < 2.20:
  Print WARNING:
    "WARNING: Docker Compose $VERSION detected. 2.20+ recommended."
```

### 7.6 .gitattributes for Line Endings

Create `.gitattributes` in the project root to ensure consistent line endings
across platforms. Shell scripts and Dockerfiles MUST use LF, even on Windows
(Docker containers run Linux).

```gitattributes
# Default: auto-detect
* text=auto

# Force LF for files that run inside containers or are shell scripts
*.sh text eol=lf
*.ps1 text eol=crlf
Dockerfile* text eol=lf
docker-compose*.yml text eol=lf
Makefile text eol=lf
*.py text eol=lf
*.rs text eol=lf
*.toml text eol=lf
*.lock text eol=lf
*.json text eol=lf
*.ts text eol=lf
*.tsx text eol=lf
*.js text eol=lf
*.css text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
.env* text eol=lf

# Binary files -- do not modify
*.png binary
*.jpg binary
*.jpeg binary
*.gif binary
*.ico binary
*.woff binary
*.woff2 binary
*.ttf binary
*.pdf binary
```

### 7.7 Docker Engine Minimum Version

The launcher should verify Docker Engine >= 24.0 (for `docker compose` v2 plugin
and healthcheck `start_period` support).

```
DOCKER_VERSION=$(docker version --format '{{.Server.Version}}')
Parse major version. If < 24:
  Print WARNING: "Docker Engine $VERSION detected. 24.0+ recommended."
```

---

## 8. Launcher Script Design (start.sh / start.ps1)

### 8.1 Full Flow -- start.sh (Bash/Zsh for macOS + Linux)

```
start.sh [--dev] [--stop] [--restart] [--logs [service]] [--status] [--help]

MAIN FLOW (no flags, or --dev):

  1. PREFLIGHT CHECKS
     a. Verify Docker is installed and running.
        - docker info > /dev/null 2>&1 || error + exit
     b. Verify Docker Compose v2 is available.
        - docker compose version > /dev/null 2>&1 || error + exit
     c. Check Docker Compose version >= 2.20 (warn if older).
     d. On Linux: check user is in docker group.
     e. On macOS: check Docker VM memory >= 4 GB.
     f. On WSL2: warn if project is on /mnt/c/.
     g. Check for port conflicts (3000, 6333, 6334, 8000, 11434).
        - Warn but do not exit.

  2. ENVIRONMENT SETUP
     a. If .env does not exist:
        i.   Copy .env.example to .env.
        ii.  Generate Fernet key via disposable container:
             docker run --rm python:3.14-slim python -c "..."
        iii. Inject key into .env via sed.
        iv.  Print "Generated .env with encryption key."
     b. If .env exists:
        i.   Print "Using existing .env file."
     c. Source .env to read OLLAMA_MODELS (with default fallback).

  3. COMPOSE FILE SELECTION
     a. COMPOSE_FILES="-f docker-compose.yml"
     b. Detect NVIDIA GPU:
        - docker info --format '{{json .Runtimes}}' | grep -q nvidia
        - OR: command -v nvidia-smi > /dev/null && nvidia-smi > /dev/null 2>&1
        - If detected: COMPOSE_FILES+=" -f docker-compose.gpu-nvidia.yml"
        - Print "NVIDIA GPU detected. GPU acceleration enabled."
     c. If --dev flag:
        - COMPOSE_FILES+=" -f docker-compose.dev.yml"
        - Print "Dev mode: hot reload enabled."

  4. BUILD AND START
     a. Print "Building and starting services..."
     b. docker compose $COMPOSE_FILES up --build -d
     c. If exit code != 0: print error, show docker compose logs, exit 1.

  5. HEALTH POLLING
     a. Define service list: (qdrant ollama backend frontend)
     b. Define timeout per service: (120 120 180 60) seconds
     c. For each service:
        i.   Print "Waiting for $service..."
        ii.  Start timer.
        iii. Loop:
             - status=$(docker inspect --format='{{.State.Health.Status}}' embedinator-$service)
             - If "healthy": print checkmark, break.
             - If "unhealthy": print X, show last 20 log lines, exit 1.
             - If elapsed > timeout: print timeout error, show last 20 log lines, exit 1.
             - Sleep 2 seconds.
             - Update spinner.

  6. MODEL PULL (after all services healthy)
     a. Read OLLAMA_MODELS from .env (default: qwen2.5:7b,nomic-embed-text).
     b. Split on comma.
     c. For each model:
        i.   Print "Pulling model: $model..."
        ii.  If terminal is interactive (test -t 0):
               docker exec -t embedinator-ollama ollama pull "$model"
             Else:
               docker exec embedinator-ollama ollama pull "$model"
        iii. If exit code != 0: print warning (not fatal -- user can pull manually).
     d. Print "All models ready."

  7. COMPLETION
     a. Print summary:
        "The Embedinator is running!
         Frontend:  http://localhost:3000
         API:       http://localhost:8000
         API Docs:  http://localhost:8000/docs
         Qdrant UI: http://localhost:6333/dashboard"
     b. If on macOS and `open` exists: open http://localhost:3000
        If on Linux and `xdg-open` exists: xdg-open http://localhost:3000
        If neither: print "Open http://localhost:3000 in your browser."


SUBCOMMAND FLOWS:

  --stop:
    a. Determine compose files (same detection as main flow, steps 3a-3c).
    b. docker compose $COMPOSE_FILES down
    c. Print "All services stopped."

  --restart:
    a. Run --stop flow.
    b. Run main flow (steps 1-7).

  --logs [service]:
    a. If service specified: docker compose logs -f $service
    b. If no service: docker compose logs -f

  --status:
    a. For each service in (qdrant ollama backend frontend):
       - status=$(docker inspect --format='{{.State.Health.Status}}' embedinator-$service 2>/dev/null)
       - If empty/error: print "$service: not running"
       - Else: print "$service: $status"
    b. Print port bindings.

  --help:
    Print usage with all flags documented.
```

### 8.2 Error Handling Principles

1. **Fail fast on prerequisites**: Missing Docker, missing Compose, no Docker
   permissions -- these are fatal. Print a clear error with a fix suggestion and
   exit 1.

2. **Warn on soft issues**: Port conflicts, low memory, WSL2 filesystem -- these
   are warnings. Print them but continue. The actual failure will come from Docker
   with a clearer error message.

3. **Show logs on service failure**: When a service health check fails or times
   out, immediately show the last 20 lines of that service's logs. This is the
   single most useful debugging action.

4. **Non-fatal model pull**: If Ollama model pull fails (network error), warn
   the user but do not exit. The application is still accessible -- the user can
   retry via `docker exec embedinator-ollama ollama pull <model>` or the
   `make pull-models` target.

5. **Trap Ctrl-C**: Trap SIGINT so that if the user cancels during health polling,
   the script prints "Interrupted. Services are still running. Use --stop to
   shut down." rather than leaving the user uncertain about state.

### 8.3 Idempotency

The script is safe to run multiple times:

- `.env` generation is skipped if `.env` already exists.
- `docker compose up --build -d` is idempotent (rebuilds only if Dockerfile/context
  changed; restarts only if config changed; no-ops if already running and current).
- Model pulls are idempotent (Ollama checks the manifest and skips if already present).
- Fernet key generation only happens during `.env` creation, never overwrites.

Running `./start.sh` twice in a row is harmless and fast (skips build, skips pull,
services already healthy).

### 8.4 Color Output and Progress

Use ANSI color codes ONLY if stdout is a terminal (test -t 1):

```
GREEN='\033[0;32m'   # Success messages, checkmarks
YELLOW='\033[0;33m'  # Warnings
RED='\033[0;31m'     # Errors
BLUE='\033[0;34m'    # Info/progress
BOLD='\033[1m'       # Headers
NC='\033[0m'         # Reset

If ! test -t 1: set all color vars to empty string.
```

Progress indicators:
- Spinner characters: `|/-\` cycling during health check polling.
- Checkmark (unicode U+2714) on service ready.
- Cross (unicode U+2718) on service failure.
- Elapsed time in seconds shown next to each spinner.

Example output:
```
The Embedinator - Launcher
==========================

[*] Preflight checks...
    Docker Engine 27.1.2                           OK
    Docker Compose 2.29.1                          OK
    NVIDIA GPU detected                            GPU enabled
    Port 3000                                      available
    Port 6333                                      available
    Port 8000                                      available
    Port 11434                                     available

[*] Environment setup...
    Generated .env with encryption key.

[*] Starting services...
    Building images (this may take a few minutes on first run)...
    Waiting for qdrant................                healthy (12s)
    Waiting for ollama................                healthy (8s)
    Waiting for backend...............                healthy (34s)
    Waiting for frontend..............                healthy (6s)

[*] Pulling models...
    qwen2.5:7b                                     pulling manifest...
    [=============================>] 100% 4.4 GB
    nomic-embed-text                               already present

[*] Ready!
    Frontend:  http://localhost:3000
    API:       http://localhost:8000
    API Docs:  http://localhost:8000/docs
    Qdrant UI: http://localhost:6333/dashboard
```

### 8.5 start.ps1 (PowerShell for Windows)

The PowerShell script mirrors the bash script's logic with platform-appropriate
commands.

Key differences from start.sh:

| Concern | start.sh | start.ps1 |
|---------|----------|-----------|
| Shell check | `bash` or `zsh` (shebang line) | PowerShell 5.1+ or pwsh 7+ |
| GPU detection | `nvidia-smi` or `docker info` | Same (`nvidia-smi.exe` or `docker info`) |
| Fernet key sed | `sed -i` | `(Get-Content) -replace ... \| Set-Content` |
| Port check | `ss -tlnp` or `lsof` | `Get-NetTCPConnection` |
| Color output | ANSI escape codes | `Write-Host -ForegroundColor` |
| Browser open | `xdg-open` / `open` | `Start-Process` |
| WSL2 check | `/proc/version` | Not applicable (native Windows) |
| SELinux :z | Applied | Not applicable (no SELinux on Windows) |
| Line endings | LF (enforced by .gitattributes) | CRLF for .ps1 (enforced by .gitattributes) |

The `.ps1` script should have the same subcommands: `-Stop`, `-Restart`, `-Logs`,
`-Status`, `-Dev`, `-Help`.

### 8.6 Script Location and Permissions

```
project-root/
  start.sh      # chmod +x, shebang: #!/usr/bin/env bash
  start.ps1     # No chmod needed (PowerShell execution policy)
```

The shebang uses `#!/usr/bin/env bash` (not `#!/bin/bash`) for portability across
macOS (where bash may be in `/opt/homebrew/bin/`) and NixOS.

The script must be marked executable in git:
```
git update-index --chmod=+x start.sh
```

---

## Appendix A: File Inventory (New and Modified)

### New files:
| File | Purpose |
|------|---------|
| `start.sh` | Bash/Zsh launcher for macOS + Linux |
| `start.ps1` | PowerShell launcher for Windows |
| `docker-compose.gpu-nvidia.yml` | NVIDIA GPU overlay |
| `docker-compose.dev.yml` | Dev mode overlay (bind mounts + hot reload) |
| `frontend/.dockerignore` | Frontend-specific Docker build exclusions |
| `.gitattributes` | Cross-platform line ending enforcement |

### Modified files:
| File | Changes |
|------|---------|
| `docker-compose.yml` | Remove GPU block from ollama; remove inline entrypoint from ollama; add healthcheck to frontend; change frontend depends_on to service_healthy; change qdrant volume from bind to named; add :z to data bind mount; add start_period to all healthchecks; pin qdrant image version |
| `Dockerfile.backend` | Fixed UID 1000; add tini; add build args; add dev stage; reorder layers |
| `frontend/Dockerfile` | Fixed UID 1000; add tini; add build args; add NEXT_PUBLIC_API_URL as build arg; add dev stage |
| `.env.example` | Add OLLAMA_MODELS entry |
| `.dockerignore` | Add docker-compose overlay files, launcher scripts |

### Unchanged files:
| File | Reason |
|------|--------|
| `Makefile` | 14 targets preserved exactly as specified by spec-17. No changes. |
| `backend/config.py` | No changes needed. Pydantic Settings already reads from .env correctly. |
| `backend/api/health.py` | No changes needed. Health endpoint already probes all three dependencies. |
| `frontend/next.config.ts` | No changes needed. |

---

## Appendix B: Qdrant Volume Migration

The base compose file changes Qdrant's volume from a bind mount
(`./data/qdrant_db:/qdrant/storage`) to a named volume
(`qdrant_data:/qdrant/storage`).

**Migration path for existing installations:**

If `./data/qdrant_db/` exists and contains data:
1. The launcher detects this directory.
2. Prints: "Migrating Qdrant data from ./data/qdrant_db/ to Docker volume..."
3. Creates the named volume:
   `docker volume create embedinator_qdrant_data`
4. Copies data via a temporary container:
   ```
   docker run --rm \
     -v $(pwd)/data/qdrant_db:/source:ro \
     -v qdrant_data:/target \
     alpine cp -a /source/. /target/
   ```
5. Renames `./data/qdrant_db/` to `./data/qdrant_db.migrated/`.
6. Prints: "Migration complete. Old data backed up to ./data/qdrant_db.migrated/"

If `./data/qdrant_db/` does not exist, skip migration (fresh install).

---

## Appendix C: Compose File Validation

The launcher should validate the composed configuration before starting services:

```
docker compose $COMPOSE_FILES config --quiet
```

If this fails (syntax error, invalid reference), print the error and exit before
attempting to start any services. This catches common issues like YAML indentation
errors in overlay files.

---

## Appendix D: Backwards Compatibility

Users who currently run `docker compose up --build -d` directly (without the
launcher) will see two breaking changes:

1. **Ollama no longer auto-pulls models.** The inline entrypoint is removed. Users
   must either use the launcher or manually run `make pull-models`.

2. **Ollama has no GPU on base compose.** Users with NVIDIA GPUs must either use
   the launcher or manually add `-f docker-compose.gpu-nvidia.yml`.

These are acceptable trade-offs documented in the changelog. The launcher is the
intended entry point for end users. Power users who compose manually can add the
overlay files themselves.

The `make up` and `make down` targets continue to work as before (they use the
base compose file only). The Makefile is not modified.
