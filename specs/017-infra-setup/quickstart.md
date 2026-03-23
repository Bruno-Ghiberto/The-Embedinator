# Quickstart: The Embedinator

**Spec**: 017-infra-setup

---

## Prerequisites

- Docker Engine 24+ and Docker Compose v2
- Python 3.14+
- Node.js 22+
- Rust 1.93+ (for native ingestion worker compilation)
- NVIDIA Container Toolkit (optional — for GPU-accelerated Ollama)

---

## First-Time Setup

```bash
# 1. Clone and enter
git clone <repo-url> the-embedinator
cd the-embedinator

# 2. Copy config template
cp .env.example .env
# Edit .env — at minimum set EMBEDINATOR_FERNET_KEY if you plan to use cloud providers

# 3. Install all dependencies (Python + Node + Rust binary)
make setup
```

---

## Development Mode (recommended for code changes)

```bash
# Start Qdrant + Ollama in Docker (infrastructure only)
make dev-infra

# In a separate terminal: start backend with hot reload
make dev-backend

# In a separate terminal: start frontend with hot reload
make dev-frontend

# Or start everything at once:
make dev
```

Backend: http://localhost:8000
Frontend: http://localhost:3000

Code changes reflect in under 3 seconds — no rebuilds needed.

---

## Production Mode (full Docker deployment)

```bash
# Build all images and start all 4 services
make up

# Check logs
docker compose logs -f

# Stop everything
make down
```

All 4 services (Qdrant, Ollama, backend, frontend) start with health checks.
Backend waits for healthy Qdrant and Ollama before accepting requests.

---

## Download Models

```bash
# Pull default LLM and embedding models
make pull-models
```

Requires Ollama to be running (`make dev-infra` or `make up`).

---

## Running Tests

```bash
# Backend tests (no coverage threshold)
make test

# Backend tests with ≥80% coverage gate
make test-cov

# Frontend tests
make test-frontend
```

> **Note for Claude Code agents**: Never run `pytest` directly. Always use:
> ```bash
> zsh scripts/run-tests-external.sh -n <run-name> <target>
> ```

---

## Cleanup

```bash
# Remove runtime data (data/ directory)
make clean

# Remove everything including Docker volumes and build outputs
make clean-all
```

---

## Configuration Reference

All configuration is via environment variables. See `.env.example` for the complete list with descriptions and defaults.

Key variables:
- `EMBEDINATOR_FERNET_KEY` — Required for cloud provider key storage (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `DEFAULT_LLM_MODEL` — Default: `qwen2.5:7b`
- `DEFAULT_EMBED_MODEL` — Default: `nomic-embed-text`
- `CONFIDENCE_THRESHOLD` — Default: `60` (integer 0–100 scale)

---

## Available Make Targets

```bash
make help    # Show all available targets with descriptions
```
