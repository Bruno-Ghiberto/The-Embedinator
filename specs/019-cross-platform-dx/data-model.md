# Data Model: Cross-Platform Developer Experience

**Feature**: 019-cross-platform-dx
**Date**: 2026-03-19

## Note

This spec introduces no new database tables or schema changes. The "data model" for this feature consists of configuration entities, state machines, and environment variable contracts. No SQLite or Qdrant schema migrations are needed.

---

## Key Entities

### 1. GPU Profile

Determines which Docker Compose overlay file (if any) is applied to the Ollama service.

**Values**: `nvidia` | `amd` | `intel` | `none`

**Detection priority** (first match wins):
1. `EMBEDINATOR_GPU` env var override (if set)
2. NVIDIA: `nvidia-smi` succeeds AND `docker info` contains "nvidia"
3. AMD: `/dev/kfd` exists AND `rocminfo` succeeds (Linux only)
4. Intel: `/dev/dri/renderD*` exists (Linux only, experimental)
5. Fallback: `none` (CPU)

**Maps to**:
| Profile | Compose Overlay | Ollama Image |
|---------|----------------|--------------|
| `nvidia` | `docker-compose.gpu-nvidia.yml` | `ollama/ollama:latest` |
| `amd` | `docker-compose.gpu-amd.yml` | `ollama/ollama:rocm` |
| `intel` | `docker-compose.gpu-intel.yml` | `ollama/ollama:latest` |
| `none` | (no overlay) | `ollama/ollama:latest` |

### 2. Port Configuration

Five configurable host ports mapping to fixed container-internal ports.

| Environment Variable | Default | Container Port | Service |
|---------------------|---------|:---:|---------|
| `EMBEDINATOR_PORT_FRONTEND` | 3000 | 3000 | Frontend (Next.js) |
| `EMBEDINATOR_PORT_BACKEND` | 8000 | 8000 | Backend (FastAPI) |
| `EMBEDINATOR_PORT_QDRANT` | 6333 | 6333 | Qdrant HTTP |
| `EMBEDINATOR_PORT_QDRANT_GRPC` | 6334 | 6334 | Qdrant gRPC |
| `EMBEDINATOR_PORT_OLLAMA` | 11434 | 11434 | Ollama |

**Precedence**: CLI flag > `.env` value > default

**Side effects when ports change**:
- `CORS_ORIGINS` in `.env` must include the configured frontend port
- Launcher health polling must use configured host ports
- Browser open URL must use configured frontend port
- Docker Compose variable interpolation handles the mapping automatically

### 3. Backend Health State

Represents the overall readiness of the backend service.

**Values**: `healthy` | `degraded` | `starting`

**State transitions**:
```
┌──────────┐   all probes OK   ┌──────────┐
│ starting │ ────────────────> │ healthy  │
└──────────┘                   └──────────┘
     │                              │
     │  some probes fail            │  a probe fails
     v                              v
┌──────────┐   all probes OK   ┌──────────┐
│ degraded │ ────────────────> │ healthy  │
└──────────┘                   └──────────┘
```

**Per-service probe results** (embedded in health response):

| Service | Probe | Status | Extra Data |
|---------|-------|--------|-----------|
| sqlite | `SELECT 1` | `ok` / `error` | `latency_ms` |
| qdrant | HTTP health check | `ok` / `error` | `latency_ms` |
| ollama | `GET /api/tags` | `ok` / `error` | `latency_ms`, `models: {model_name: present}` |

**Overall status logic**:
- `healthy`: all services `ok` AND all required models present
- `degraded`: at least one service `error` OR required models missing
- `starting`: first probe after startup, dependencies not yet checked

### 4. Frontend Backend Status

Client-side representation of backend health, derived from polling `/api/health`.

**Values**: `unreachable` | `degraded` | `ready`

**Derivation**:
| Condition | Frontend Status |
|-----------|----------------|
| `fetch()` throws (network error) | `unreachable` |
| Backend returns HTTP 503 | `degraded` |
| Backend returns HTTP 200 with `status: "starting"` | `degraded` |
| Backend returns HTTP 200 with `status: "degraded"` | `degraded` |
| Backend returns HTTP 200 with `status: "healthy"` | `ready` |

**Polling intervals** (adaptive):
| Status | Interval |
|--------|----------|
| `unreachable` | 5 seconds |
| `degraded` | 10 seconds |
| `ready` | 30 seconds |

**UI effects**:
| Status | Banner | Chat Input |
|--------|--------|-----------|
| `unreachable` | "Connecting to backend..." | Disabled: "Waiting for backend to start..." |
| `degraded` (Ollama) | "AI models are being downloaded..." | Disabled: "AI models are still loading..." |
| `degraded` (Qdrant) | "Vector database is starting up." | Disabled: "Vector database is starting..." |
| `ready` | Hidden | Enabled (subject to collection selection) |

### 5. Launcher Subcommands

The launcher script accepts exactly one primary action.

| Subcommand | Action | Exits After |
|------------|--------|-------------|
| (none) | Default start flow | No (prints ready message) |
| `--dev` | Start with dev overlay | No |
| `--stop` | `docker compose down` | Yes |
| `--restart` | Stop then start | No |
| `--logs [service]` | Stream container logs | Yes (Ctrl-C) |
| `--status` | Print health status | Yes |
| `--open` | Open browser after health checks | Modifier (combined with start) |
| `--help` | Print usage | Yes |
| `--frontend-port PORT` | Override frontend host port | Modifier |
| `--backend-port PORT` | Override backend host port | Modifier |

---

## Environment Variable Contracts

### New variables added to `.env.example`

| Variable | Read By | Default | Purpose |
|----------|---------|---------|---------|
| `BACKEND_URL` | Docker Compose → Next.js server | `http://localhost:8000` | Server-side rewrite destination |
| `OLLAMA_MODELS` | Launcher script | `qwen2.5:7b,nomic-embed-text` | Models to auto-download |
| `EMBEDINATOR_GPU` | Launcher script | (auto-detect) | Force GPU profile |
| `EMBEDINATOR_PORT_FRONTEND` | Docker Compose interpolation | `3000` | Frontend host port |
| `EMBEDINATOR_PORT_BACKEND` | Docker Compose interpolation | `8000` | Backend host port |
| `EMBEDINATOR_PORT_QDRANT` | Docker Compose interpolation | `6333` | Qdrant HTTP host port |
| `EMBEDINATOR_PORT_QDRANT_GRPC` | Docker Compose interpolation | `6334` | Qdrant gRPC host port |
| `EMBEDINATOR_PORT_OLLAMA` | Docker Compose interpolation | `11434` | Ollama host port |

**Important**: These variables are NOT read by Pydantic Settings (`backend/config.py`). They are consumed by Docker Compose variable interpolation and the launcher script only. `backend/config.py` is not modified.
