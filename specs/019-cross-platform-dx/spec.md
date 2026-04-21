# Feature Specification: Cross-Platform Developer Experience

**Feature Branch**: `019-cross-platform-dx`
**Created**: 2026-03-19
**Status**: Draft
**Input**: Transform The Embedinator from a multi-command, toolchain-dependent setup into a single-command, cross-platform application that works on Windows 10/11, macOS, and Linux with Docker Desktop as the only prerequisite.

## Overview

The Embedinator is a sophisticated 3-layer agentic RAG platform with a Python backend, Rust ingestion worker, Next.js frontend, Qdrant vector database, and Ollama LLM server. Despite its technical depth, the installation experience is fragmented: users must install Python 3.14+, Node.js, optionally Rust, and `make`, then run multiple commands across multiple terminal windows, manually create an `.env` file, generate a Fernet encryption key, and separately download AI models. The Docker Compose file hard-codes NVIDIA GPU passthrough, which crashes on macOS, Windows without NVIDIA, and Linux without the NVIDIA Container Toolkit. The frontend has a critical API routing bug where a Docker-internal hostname is baked into the JavaScript bundle at build time.

This specification defines a zero-toolchain, single-command startup experience. Users run `./embedinator.sh` (macOS/Linux) or `.\embedinator.ps1` (Windows) and the entire application builds, configures itself, downloads AI models with visible progress, and reports readiness. Docker Desktop is the only prerequisite. GPU acceleration is auto-detected for NVIDIA, AMD, and Intel hardware. All service ports are configurable for users with existing services on default ports. The frontend API routing is fixed to work across Docker networking, localhost, and LAN access. The backend reports granular health status including AI model availability, and the frontend gracefully handles degraded states during startup.

The outcome is an application that can be confidently shared with non-developer users, open-source contributors on any operating system, and teammates who want to evaluate the tool without setting up a development environment.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — First-Time Launch on Any OS (Priority: P1)

A new user clones The Embedinator repository on their machine (Windows, macOS, or Linux), runs a single launcher script, and has the application fully operational in their browser — without installing Python, Node.js, Rust, or any build tools. The only prerequisite they need is Docker Desktop.

**Why this priority**: This is the core value proposition of the entire spec. If a user cannot go from `git clone` to a working application in one command, every other improvement is moot. This story covers the end-to-end first-run experience: prerequisite validation, environment generation, service orchestration, model downloading, and readiness feedback.

**Independent Test**: Can be tested on a clean machine with only Docker Desktop installed. Clone the repo, run the launcher, and verify all services are healthy and the browser shows the application.

**Acceptance Scenarios**:

1. **Given** a freshly cloned repository on Linux with only Docker Engine + Compose v2 installed, **When** the user runs `./embedinator.sh`, **Then** the script validates Docker is running, detects the GPU profile, generates `.env` with a Fernet key, starts all 4 services, downloads AI models with visible progress, and prints a ready message with the application URL.
2. **Given** a freshly cloned repository on macOS with Docker Desktop, **When** the user runs `./embedinator.sh`, **Then** GPU detection correctly identifies "no GPU in Docker" (CPU mode), and the Ollama container runs without GPU passthrough.
3. **Given** a freshly cloned repository on Windows with Docker Desktop (WSL2 backend), **When** the user runs `.\embedinator.ps1`, **Then** the same first-run flow completes successfully using PowerShell-native equivalents for all operations.
4. **Given** no `.env` file exists, **When** the launcher runs for the first time, **Then** it copies `.env.example` to `.env` and generates a valid Fernet encryption key using a disposable Docker container (no local Python required).
5. **Given** all services are started, **When** the Ollama models have not yet been downloaded, **Then** the launcher pulls the configured models (default: `qwen2.5:7b` and `nomic-embed-text`) with progress output visible in the terminal, and waits until pulling completes before reporting readiness.

---

### User Story 2 — Daily Start, Stop, and Status (Priority: P2)

A returning user starts and stops The Embedinator as part of their daily workflow. Subsequent launches are fast because Docker images are cached and AI models are already downloaded. The user can check service status, view logs, and stop all services through launcher subcommands.

**Why this priority**: After the first-run experience, the daily start/stop cycle is the most frequent interaction with the launcher. Fast subsequent starts and convenient subcommands are essential for adoption.

**Independent Test**: After a successful first run, stop all services, then start again. Verify that startup is significantly faster (cached images, existing models) and that all subcommands work correctly.

**Acceptance Scenarios**:

1. **Given** services were previously started and stopped, **When** the user runs `./embedinator.sh` again, **Then** services start within 60 seconds (no image rebuilds, no model downloads) and the launcher skips the `.env` generation and model pull steps.
2. **Given** services are running, **When** the user runs `./embedinator.sh --stop`, **Then** all Docker Compose services are stopped gracefully.
3. **Given** services are running, **When** the user runs `./embedinator.sh --status`, **Then** the launcher prints the health status of each service (qdrant, ollama, backend, frontend) using their configured ports.
4. **Given** services are running, **When** the user runs `./embedinator.sh --logs backend`, **Then** the launcher streams the backend container's logs to the terminal.
5. **Given** services are running, **When** the user runs `./embedinator.sh --restart`, **Then** all services are stopped and started again cleanly.

---

### User Story 3 — GPU Auto-Detection (Priority: P2)

A user with a GPU (NVIDIA, AMD, or Intel) starts The Embedinator and automatically gets GPU-accelerated AI inference without any manual configuration. A user without a compatible GPU gets CPU-based inference that works correctly, albeit more slowly.

**Why this priority**: GPU acceleration dramatically improves inference speed. Auto-detection removes the #1 cause of startup failures: the current hard-coded NVIDIA GPU block crashes on non-NVIDIA systems. This must work on the first attempt without user intervention.

**Independent Test**: Run the launcher on systems with different GPU hardware and verify the correct Docker Compose overlay is selected. On a system without any GPU, verify CPU fallback works.

**Acceptance Scenarios**:

1. **Given** a Linux machine with an NVIDIA GPU and nvidia-container-toolkit, **When** the launcher runs GPU detection, **Then** it selects the NVIDIA overlay and the Ollama container runs with GPU access.
2. **Given** a Linux machine with an AMD GPU and ROCm drivers, **When** the launcher runs GPU detection, **Then** it selects the AMD overlay (which swaps the Ollama image to `ollama/ollama:rocm` and passes through `/dev/kfd` and `/dev/dri`).
3. **Given** a Linux machine with an Intel Arc GPU, **When** the launcher runs GPU detection, **Then** it selects the Intel overlay (experimental, passes through `/dev/dri`).
4. **Given** a macOS machine (any hardware), **When** the launcher runs GPU detection, **Then** it selects CPU mode and prints an informational message about native Ollama for Metal GPU acceleration.
5. **Given** the user sets `EMBEDINATOR_GPU=none`, **When** the launcher runs, **Then** it forces CPU mode regardless of detected hardware.
6. **Given** the user sets `EMBEDINATOR_GPU=amd`, **When** the launcher runs on a machine without `rocminfo`, **Then** it forces the AMD overlay regardless of detection results.

---

### User Story 4 — Custom Port Configuration (Priority: P3)

A user who already has services running on ports 3000 and 8000 configures The Embedinator to use different ports, either persistently via `.env` or via one-time CLI flags.

**Why this priority**: Port conflicts are the most common "it doesn't work" report for Docker-based applications. Configurable ports remove this friction entirely.

**Independent Test**: Start the application with custom ports via CLI flags and verify all services are accessible on the custom ports, including health polling and CORS configuration.

**Acceptance Scenarios**:

1. **Given** the user runs `./embedinator.sh --frontend-port 4000 --backend-port 9000`, **When** services start, **Then** the frontend is accessible on port 4000, the backend on port 9000, and the ready message shows `http://localhost:4000`.
2. **Given** the user sets `EMBEDINATOR_PORT_FRONTEND=4000` in `.env`, **When** the launcher runs without CLI flags, **Then** the frontend is accessible on port 4000 persistently across restarts.
3. **Given** port 8000 is occupied by another process, **When** the launcher runs with default ports, **Then** it detects the conflict and exits with an error message suggesting `--backend-port 9000`.
4. **Given** the frontend runs on a custom port, **When** the backend receives a request, **Then** CORS headers include the custom frontend port (auto-adjusted by the launcher).

---

### User Story 5 — Developer Mode with Hot Reload (Priority: P3)

A developer contributing to The Embedinator starts the application in development mode, where code changes to the backend and frontend are reflected immediately without rebuilding Docker images.

**Why this priority**: Contributors need a fast feedback loop. The current dev overlay is broken (mounts non-existent directories). Fixing it and making it accessible via the launcher lowers the contribution barrier.

**Independent Test**: Start with `--dev`, edit a frontend component file, and verify the change appears in the browser without restarting.

**Acceptance Scenarios**:

1. **Given** the user runs `./embedinator.sh --dev`, **When** the dev overlay mounts source directories, **Then** the frontend runs with Hot Module Replacement and the backend runs with auto-reload, both with source code mounted from the host.
2. **Given** dev mode is running, **When** the user edits a frontend component file, **Then** the browser reflects the change within seconds via HMR.
3. **Given** dev mode is running, **When** the user edits a backend Python file, **Then** the backend auto-reloads and the API reflects the change.
4. **Given** dev mode is running, **When** the user checks `node_modules` and `.next` inside the frontend container, **Then** they are isolated via anonymous volumes and do not conflict with host directories.

---

### User Story 6 — Graceful Degraded Startup (Priority: P3)

A user starts The Embedinator and opens the browser before AI models have finished downloading. The frontend shows clear, informative status messages about what is still loading, rather than cryptic error messages or broken pages.

**Why this priority**: The first-run model download takes 5-30 minutes on slow connections. Users will inevitably open the browser before it finishes. The frontend must gracefully communicate what is happening.

**Independent Test**: Start the application, immediately navigate to the chat page, and verify the status banner appears with contextual information. Verify the chat input is disabled with an explanatory message.

**Acceptance Scenarios**:

1. **Given** the frontend is running but Ollama models are still downloading, **When** the user visits the chat page, **Then** a status banner appears saying "AI models are being downloaded. Chat will be available shortly."
2. **Given** the backend is running but Qdrant is not yet healthy, **When** the user visits the collections page, **Then** a status banner says "Vector database is starting up."
3. **Given** the backend is completely unreachable, **When** the user visits any page, **Then** a status banner says "Connecting to backend..." with a loading indicator.
4. **Given** the chat page is in a degraded state, **When** the user inspects the chat input, **Then** it is disabled with a contextual placeholder explaining why.
5. **Given** all services become healthy, **When** the status transitions to ready, **Then** the status banner disappears and the chat input becomes enabled.

---

### User Story 7 — First-Run Onboarding (Priority: P3)

A user opens The Embedinator for the first time after all services are healthy. Since no collections or documents exist, the chat page shows a guided onboarding experience instead of an empty interface.

**Why this priority**: A blank chat page with no collections is confusing for new users. A simple onboarding flow bridges the gap between "app is running" and "app is useful."

**Independent Test**: Start the application with no existing data, navigate to chat, and verify the onboarding card appears with guided steps.

**Acceptance Scenarios**:

1. **Given** no collections exist, **When** the user visits the chat page, **Then** a welcome card replaces the normal empty state with steps: "Create a collection", "Upload documents", "Ask questions."
2. **Given** the onboarding card is displayed, **When** the user clicks "Create a collection", **Then** they are navigated to `/collections` or the create dialog opens.
3. **Given** at least one collection exists, **When** the user visits the chat page, **Then** the standard empty state with starter questions is shown (not the onboarding card).

---

### Edge Cases

- What happens when Docker is installed but not running? The launcher MUST detect this and print "Please start Docker Desktop" with exit code 1.
- What happens when Docker Compose v1 (`docker-compose`) is installed instead of v2 (`docker compose`)? The launcher MUST detect this and print an error recommending the upgrade.
- What happens when the user runs the launcher from `/mnt/c/...` inside WSL2? The launcher MUST print a performance warning recommending the WSL2 home directory.
- What happens when macOS Docker Desktop has less than 4GB RAM allocated? The launcher MUST warn about insufficient memory for AI inference.
- What happens when available disk space is less than 15GB? The launcher MUST warn before proceeding.
- What happens when Fernet key generation fails (Docker cannot pull the Python image)? The launcher MUST exit with an actionable error.
- What happens when model downloads are interrupted? Subsequent runs MUST re-attempt the download for incomplete models.
- What happens when the launcher is run multiple times? It MUST be idempotent — if services are already running, it SHOULD report their status rather than failing.

## Requirements *(mandatory)*

### Functional Requirements

#### Area 1: Launcher Scripts

- **FR-001** `[LAUNCHER]`: The project MUST include `embedinator.sh` (bash/zsh, for macOS and Linux) and `embedinator.ps1` (PowerShell, for Windows) at the repository root. Both scripts MUST implement identical logic with platform-appropriate syntax.
- **FR-002** `[LAUNCHER]`: The launcher MUST accept the following subcommands: (no flag) for default start, `--dev` for dev mode, `--stop` to stop all services, `--restart` to stop and start, `--logs [service]` to stream logs, `--status` to show service health, `--open` to open the browser, and `--help` to show usage.
- **FR-003** `[LAUNCHER]`: The launcher MUST accept `--frontend-port PORT` and `--backend-port PORT` flags that override the configured host ports for that run. CLI flags MUST take precedence over `.env` values.
- **FR-004** `[LAUNCHER]`: On startup, the launcher MUST run preflight checks in order: (1) Docker daemon running, (2) Docker Compose v2 available, (3) port availability for all configured ports, (4) disk space warning if below 15GB, (5) Docker VM memory warning on macOS if below 4GB, (6) WSL2 filesystem path warning on Windows.
- **FR-005** `[LAUNCHER]`: The launcher MUST detect GPU hardware in priority order: NVIDIA (via `nvidia-smi` + Docker runtime check), AMD (via `/dev/kfd` + `rocminfo`), Intel (via `/dev/dri/renderD*`), CPU fallback. Only the first match MUST be used.
- **FR-006** `[LAUNCHER]`: The `EMBEDINATOR_GPU` environment variable MUST override auto-detection when set. Valid values: `nvidia`, `amd`, `intel`, `none`.
- **FR-007** `[LAUNCHER]`: On macOS, the launcher MUST always select CPU mode and print an informational message about native Ollama for Metal GPU acceleration.
- **FR-008** `[LAUNCHER]`: If `.env` does not exist, the launcher MUST copy `.env.example` to `.env` and generate a valid Fernet encryption key using a disposable Docker container. The launcher MUST NOT require Python installed on the host.
- **FR-009** `[LAUNCHER]`: The launcher MUST auto-detect the machine's LAN IP and write `CORS_ORIGINS` in `.env` including `http://localhost:{frontend_port}`, `http://127.0.0.1:{frontend_port}`, and `http://{lan_ip}:{frontend_port}`.
- **FR-010** `[LAUNCHER]`: The launcher MUST create `data/` and `data/uploads/` directories before starting Docker Compose, to prevent Docker from creating them as root-owned.
- **FR-011** `[LAUNCHER]`: After services start, the launcher MUST poll health endpoints using the configured host ports, printing a per-service status line that updates in place. Timeout: 300 seconds for first run, 60 seconds for subsequent runs.
- **FR-012** `[LAUNCHER]`: After all services are healthy, the launcher MUST check if required AI models are already downloaded. For any missing model, it MUST pull with progress output visible in the terminal.
- **FR-013** `[LAUNCHER]`: The `OLLAMA_MODELS` environment variable MUST configure which models to download. Default: `qwen2.5:7b,nomic-embed-text`.
- **FR-014** `[LAUNCHER]`: When the `--open` flag is provided, the launcher MUST open the application URL in the default browser after all health checks pass. The URL MUST use the configured frontend port.
- **FR-015** `[LAUNCHER]`: The launcher MUST be idempotent. If services are already running, it MUST detect this and report their status rather than attempting to start duplicate containers.
- **FR-016** `[LAUNCHER]`: Port conflict detection MUST identify the conflicting process (if possible) and suggest the `--frontend-port` or `--backend-port` flag as a resolution.

#### Area 2: Docker Compose

- **FR-017** `[COMPOSE]`: The base `docker-compose.yml` MUST NOT contain any GPU-specific deploy blocks. The Ollama service MUST use `ollama serve` as its entrypoint without inline model pulling.
- **FR-018** `[COMPOSE]`: Three GPU overlay files MUST be created: `docker-compose.gpu-nvidia.yml` (NVIDIA deploy reservation), `docker-compose.gpu-amd.yml` (image swap to `ollama/ollama:rocm` + `/dev/kfd` + `/dev/dri` passthrough), and `docker-compose.gpu-intel.yml` (`/dev/dri` passthrough, experimental).
- **FR-019** `[COMPOSE]`: All service port mappings in `docker-compose.yml` MUST use variable interpolation with defaults: `"${EMBEDINATOR_PORT_FRONTEND:-3000}:3000"` for all 5 ports.
- **FR-020** `[COMPOSE]`: All bind mount volumes MUST include the `:z` SELinux suffix.
- **FR-021** `[COMPOSE]`: All services MUST include log rotation: `json-file` driver, `max-size: "50m"`, `max-file: "3"`.
- **FR-022** `[COMPOSE]`: The Qdrant service MUST use a bind mount at `./data/qdrant_db:/qdrant/storage:z`. The Ollama model volume MUST remain a named volume (`ollama_models`).
- **FR-023** `[COMPOSE]`: The frontend service MUST include `depends_on: backend: condition: service_healthy`.
- **FR-024** `[COMPOSE]`: The backend service MUST include `stop_grace_period: 15s`.
- **FR-025** `[COMPOSE]`: The `docker-compose.dev.yml` MUST be fixed to mount correct frontend directories (`app/`, `components/`, `hooks/`, `lib/`, `public/`, `next.config.ts`, `tsconfig.json`), use anonymous volumes for `node_modules/` and `.next/`, use `target: deps` for the frontend build, and override the command to run the dev server.

#### Area 3: Frontend API Routing

- **FR-026** `[FRONTEND]`: The `NEXT_PUBLIC_API_URL` environment variable MUST be removed from `docker-compose.yml` and replaced with a server-side-only `BACKEND_URL` environment variable (default: `http://localhost:8000`).
- **FR-027** `[FRONTEND]`: `next.config.ts` MUST add a `rewrites()` configuration that proxies `/api/:path*` requests to the backend using the `BACKEND_URL` server-side env var.
- **FR-028** `[FRONTEND]`: `lib/api.ts` MUST change `API_BASE` from `process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"` to `process.env.NEXT_PUBLIC_API_URL || ""` (empty string for relative paths). The `NEXT_PUBLIC_API_URL` override MUST be retained for advanced deployment scenarios.
- **FR-029** `[FRONTEND]`: A health endpoint MUST be added at `frontend/app/healthz/route.ts` returning `{"status": "ok"}` with HTTP 200. Path MUST be `/healthz` (not `/api/health`) to avoid the rewrite rule.
- **FR-030** `[FRONTEND]`: The frontend Docker health check MUST use `wget --spider http://localhost:3000/healthz` with `interval: 10s`, `timeout: 5s`, `retries: 3`, `start_period: 30s`.
- **FR-031** `[FRONTEND]`: A root route at `frontend/app/page.tsx` MUST redirect to `/chat`.

#### Area 4: Backend Health

- **FR-032** `[BACKEND]`: A liveness endpoint MUST be added at `GET /api/health/live` that always returns `{"status": "alive"}` with HTTP 200. It MUST NOT probe any external dependencies.
- **FR-033** `[BACKEND]`: The Docker HEALTHCHECK for the backend MUST target `/api/health/live` (not `/api/health`), to prevent restarts during model download windows.
- **FR-034** `[BACKEND]`: The `/api/health` readiness endpoint MUST be enhanced to report Ollama model availability — whether the configured models are present in the Ollama model list.
- **FR-035** `[BACKEND]`: The health response MUST support three overall statuses: `"healthy"`, `"degraded"`, and `"starting"`.
- **FR-036** `[BACKEND]`: Health endpoint requests (`/api/health`, `/api/health/live`) MUST be excluded from request logging middleware.
- **FR-037** `[BACKEND]`: Health probes MUST NOT count against circuit breaker failure thresholds.

#### Area 5: Dockerfiles

- **FR-038** `[DOCKERFILE]`: `Dockerfile.backend` MUST create the application user with fixed UID/GID 1000.
- **FR-039** `[DOCKERFILE]`: `Dockerfile.backend` MUST install `tini` and use it as the entrypoint for proper signal forwarding.
- **FR-040** `[DOCKERFILE]`: `Dockerfile.backend` MUST pre-download the cross-encoder model during build. `HF_HOME` MUST be set to `/app/.cache/huggingface`.
- **FR-041** `[DOCKERFILE]`: `frontend/Dockerfile` MUST pin the base image to `node:22-alpine` (not `lts-alpine`).
- **FR-042** `[DOCKERFILE]`: A `frontend/.dockerignore` MUST be created excluding test files, `node_modules`, `.next`, `.git`, and documentation.

#### Area 6: Environment & First-Run

- **FR-043** `[ENV]`: `.env.example` MUST include documentation for `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, and all 5 `EMBEDINATOR_PORT_*` variables.
- **FR-044** `[ENV]`: The backend startup MUST create the upload directory if it does not exist.
- **FR-045** `[ENV]`: The backend startup MUST test write access to the data directory and exit with a clear error message if write fails.

#### Area 7: Frontend Degraded States

- **FR-046** `[FRONTEND]`: A `BackendStatusProvider` React context MUST poll `/api/health` via SWR with adaptive intervals: 5s (unreachable), 10s (degraded), 30s (ready).
- **FR-047** `[FRONTEND]`: A `StatusBanner` component MUST render inside `SidebarLayout` with contextual messages for each degraded state. It MUST use `role="status"` and `aria-live="polite"` for accessibility.
- **FR-048** `[FRONTEND]`: The chat input MUST be disabled with a contextual placeholder when the backend is not fully ready.
- **FR-049** `[FRONTEND]`: When zero collections exist, the chat page MUST display an onboarding card with guided steps: create a collection, upload documents, ask questions.

#### Area 8: Graceful Shutdown

- **FR-050** `[SHUTDOWN]`: On shutdown, the backend MUST set a `shutting_down` flag and reject new chat requests with an NDJSON error event (`"code": "SHUTTING_DOWN"`).
- **FR-051** `[SHUTDOWN]`: On shutdown, the backend MUST execute `PRAGMA wal_checkpoint(TRUNCATE)` on both SQLite databases before closing connections.
- **FR-052** `[SHUTDOWN]`: On shutdown, the backend MUST explicitly close the LangGraph checkpointer connection.

#### Area 9: Cross-Platform Hardening

- **FR-053** `[CROSS-PLATFORM]`: A `.gitattributes` file MUST enforce LF line endings for shell scripts, Dockerfiles, YAML, Python, TypeScript, and JSON files. CRLF MUST be enforced for `.ps1` files.
- **FR-054** `[CROSS-PLATFORM]`: On Linux, if the Docker daemon is not accessible, the launcher MUST check `docker` group membership and print remediation instructions.
- **FR-055** `[CROSS-PLATFORM]`: On Windows (WSL2), the launcher MUST warn about `/mnt/c/...` filesystem performance.
- **FR-056** `[CROSS-PLATFORM]`: On macOS, the launcher MUST warn if Docker Desktop has less than 4GB RAM allocated.

### Key Entities

- **Launcher Script**: The `embedinator.sh` / `embedinator.ps1` entry point managing the full lifecycle: preflight, GPU detection, environment setup, compose orchestration, health polling, model management, and browser open.
- **GPU Profile**: One of `nvidia`, `amd`, `intel`, or `none`. Determined by auto-detection or `EMBEDINATOR_GPU` override. Maps to a Docker Compose overlay file (or no overlay for `none`).
- **Port Configuration**: Five configurable host ports (`EMBEDINATOR_PORT_*`) that map to fixed container-internal ports. Set via `.env` (persistent) or CLI flags (one-time override).
- **Backend Health State**: One of `healthy`, `degraded`, or `starting`. Derived from per-service probes including model availability.
- **Frontend Backend Status**: One of `unreachable`, `degraded`, or `ready`. Drives UI behavior: status banner visibility, chat input gating, polling frequency.

### Non-Functional Requirements

Non-functional requirements for this spec are captured as measurable Success Criteria (SC-001 through SC-010) below. Key NFR themes: cross-platform compatibility (all 3 OS), idempotent launcher (safe to run multiple times), subsequent startup < 60 seconds, zero local toolchain requirement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user on Linux with only Docker Engine and Compose v2 installed can run `./embedinator.sh` and have all 4 services healthy and the application usable within 10 minutes on a first run (including model downloads on typical broadband).
- **SC-002**: A user on Windows 10/11 with Docker Desktop can run `.\embedinator.ps1` and achieve the same outcome as SC-001.
- **SC-003**: On a system with an NVIDIA GPU and nvidia-container-toolkit, the launcher auto-detects the GPU and Ollama runs GPU-accelerated. On macOS or a system without a supported GPU, the launcher falls back to CPU mode without errors.
- **SC-004**: Custom ports work: `./embedinator.sh --frontend-port 4000 --backend-port 9000` results in the frontend accessible at `http://localhost:4000` with all API calls succeeding without CORS errors.
- **SC-005**: The frontend serves all `/api/*` requests via server-side rewrites with zero browser console errors related to hostname resolution or CORS, whether accessed from `localhost` or a LAN IP.
- **SC-006**: The backend health endpoint distinguishes between "Ollama reachable but models missing" and "Ollama unreachable" in its response.
- **SC-007**: When the backend is degraded, the frontend displays a status banner and disables the chat input. When the backend becomes healthy, both recover without page refresh.
- **SC-008**: First-run generates a valid `.env` with Fernet key without Python on the host.
- **SC-009**: Subsequent launches complete health checks within 60 seconds.
- **SC-010**: All 14 existing Makefile targets function identically to before this spec.

## Assumptions

- Docker Desktop (Windows/macOS) or Docker Engine + Compose v2 (Linux) is the industry-standard way to run multi-service applications on developer machines.
- Ports 3000 and 8000 are the most likely to conflict. Qdrant (6333/6334) and Ollama (11434) are less likely.
- The `python:3.14-slim` Docker image is available for Fernet key generation. Any Python 3.x slim image can be substituted if needed.
- Users with AMD or Intel GPUs on Windows will accept CPU-only Docker mode, as WSL2 does not support non-NVIDIA GPU passthrough.
- The cross-encoder model (24MB) is small enough to bake into the Docker image without significant impact.

## Out of Scope

- No new Python packages — all backend changes use existing dependencies
- No new frontend npm packages — all frontend changes use existing packages
- No database schema changes — no SQLite or Qdrant schema migrations
- No Makefile changes — all 14 existing targets preserved unchanged
- No authentication — the app remains a trusted local network tool
- No CI/CD pipeline — belongs in a separate spec
- No Kubernetes or cloud deployment — Docker Compose on a single machine only
- No Ollama model selection UI — `OLLAMA_MODELS` env var is sufficient
- No Windows native (non-Docker) support — WSL2 + Docker Desktop is the path

## File Impact Map

| File | Action | Purpose |
|------|--------|---------|
| `embedinator.sh` | CREATE | Bash/zsh launcher for macOS and Linux |
| `embedinator.ps1` | CREATE | PowerShell launcher for Windows |
| `docker-compose.gpu-nvidia.yml` | CREATE | NVIDIA GPU overlay |
| `docker-compose.gpu-amd.yml` | CREATE | AMD ROCm GPU overlay |
| `docker-compose.gpu-intel.yml` | CREATE | Intel Arc GPU overlay (experimental) |
| `.gitattributes` | CREATE | Line ending enforcement |
| `frontend/.dockerignore` | CREATE | Exclude test files from build context |
| `frontend/app/healthz/route.ts` | CREATE | Frontend health endpoint |
| `frontend/app/page.tsx` | CREATE | Root route redirect to /chat |
| `frontend/components/BackendStatusProvider.tsx` | CREATE | React context for backend health state |
| `frontend/components/StatusBanner.tsx` | CREATE | Global degraded state banner |
| `docker-compose.yml` | MODIFY | Remove GPU block, add health checks, SELinux `:z`, log rotation, configurable ports, `BACKEND_URL` |
| `docker-compose.dev.yml` | MODIFY | Fix broken volume mounts, correct frontend dirs |
| `Dockerfile.backend` | MODIFY | Fixed UID 1000, tini, cross-encoder pre-download |
| `frontend/Dockerfile` | MODIFY | Pin Node 22, build arg, combine layers |
| `frontend/next.config.ts` | MODIFY | Add `rewrites()` for API proxy |
| `frontend/lib/api.ts` | MODIFY | Change `API_BASE` to empty string |
| `frontend/app/layout.tsx` | MODIFY | Wrap with `BackendStatusProvider` |
| `frontend/components/SidebarLayout.tsx` | MODIFY | Insert `StatusBanner` |
| `frontend/components/ChatInput.tsx` | MODIFY | Backend status gating |
| `frontend/components/ChatPanel.tsx` | MODIFY | First-run onboarding card |
| `backend/api/health.py` | MODIFY | Add `/api/health/live`, model availability |
| `backend/main.py` | MODIFY | Graceful shutdown, upload dir, write-access test |
| `.env.example` | MODIFY | Add port, GPU, model, and backend URL vars |
| `Makefile` | PRESERVE | All 14 targets unchanged |
