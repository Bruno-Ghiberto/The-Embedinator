# Spec 17: Infrastructure -- Implementation Context

## Implementation Scope

### Files to Create

- `docker-compose.yml` -- Full containerized deployment
- `docker-compose.dev.yml` -- Dev mode (infrastructure only)
- `backend/Dockerfile` -- Multi-stage Rust + Python build
- `frontend/Dockerfile` -- Multi-stage Next.js build
- `Makefile` -- Build automation targets
- `.env.example` -- Environment variable template
- `.gitignore` -- Git exclusion rules
- `backend/config.py` -- Pydantic Settings class
- `requirements.txt` -- Python production dependencies
- `requirements-dev.txt` -- Python dev/test dependencies
- All `__init__.py` files for Python packages
- Backend module placeholder files (with docstring stubs)

### Files to Modify

- `frontend/next.config.ts` -- Add `output: 'standalone'` for Docker deployment

## Code Specifications

### docker-compose.yml (Full -- all services)

```yaml
# docker-compose.yml -- Full containerized deployment
# Requires: Docker Engine 24+, Docker Compose v2 (no 'version:' field needed)

services:

  # -- Vector database --------------------------------------------------------
  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    ports:
      - "6333:6333"   # HTTP API
      - "6334:6334"   # gRPC (optional)
    volumes:
      - ./data/qdrant_db:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  # -- LLM + Embedding inference ----------------------------------------------
  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    # GPU passthrough -- remove this block if no NVIDIA GPU
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/"]
      interval: 15s
      timeout: 5s
      retries: 5
      start_period: 20s

  # -- Python backend (FastAPI + LangGraph) -----------------------------------
  # Multi-stage build: Stage 1 compiles the Rust worker, Stage 2 is Python runtime
  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data          # SQLite db, uploads, Qdrant db (if local)
    env_file:
      - .env
    environment:
      # These override .env for Docker networking (service names, not localhost)
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - OLLAMA_BASE_URL=http://ollama:11434
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 15s

  # -- Next.js frontend -------------------------------------------------------
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "3000:3000"
    environment:
      # NEXT_PUBLIC_* vars are inlined at build time -- set to host-facing URL
      # so the browser (outside Docker) can reach the backend.
      - NEXT_PUBLIC_API_URL=http://localhost:8000
      # Server-side Next.js calls (SSR/API routes) use the Docker service name
      - INTERNAL_API_URL=http://backend:8000
    depends_on:
      backend:
        condition: service_healthy

volumes:
  ollama_models:     # persists downloaded Ollama models across container restarts
```

### docker-compose.dev.yml (Dev mode -- infrastructure only)

```yaml
# docker-compose.dev.yml
# Run with: docker compose -f docker-compose.dev.yml up
# Then start backend and frontend natively with: make dev

services:

  qdrant:
    image: qdrant/qdrant:latest
    restart: unless-stopped
    ports:
      - "6333:6333"
    volumes:
      - ./data/qdrant_db:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

  ollama:
    image: ollama/ollama:latest
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

volumes:
  ollama_models:
```

### backend/Dockerfile (Multi-stage: Rust to Python)

```dockerfile
# -- Stage 1: Compile the Rust ingestion worker --------------------------------
FROM rust:1.93-slim AS rust-builder

WORKDIR /build

# Cache Cargo dependencies before copying source
COPY ingestion-worker/Cargo.toml ingestion-worker/Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs
RUN cargo build --release
RUN rm -f target/release/deps/embedinator_worker*

# Now copy real source and build
COPY ingestion-worker/src ./src
RUN cargo build --release

# -- Stage 2: Python runtime --------------------------------------------------
FROM python:3.14-slim AS runtime

WORKDIR /app

# System deps: curl (healthcheck), libssl (requests), build tools for some Python pkgs
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled Rust binary from Stage 1
COPY --from=rust-builder /build/target/release/embedinator-worker /usr/local/bin/embedinator-worker
RUN chmod +x /usr/local/bin/embedinator-worker

# Install Python dependencies first (layer cached unless requirements.txt changes)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Runtime data directory (mounted as volume in compose)
RUN mkdir -p /app/data/uploads

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### frontend/Dockerfile

```dockerfile
# -- Stage 1: Build Next.js app -----------------------------------------------
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Build-time env vars must be provided here (NEXT_PUBLIC_* baked into bundle)
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# -- Stage 2: Minimal production runner ---------------------------------------
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

# Only copy what's needed to run
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
```

**Note**: The frontend Dockerfile requires `output: 'standalone'` in `next.config.ts`.

### Makefile

```makefile
.PHONY: setup build-rust dev-infra dev-backend dev-frontend dev up down clean test

# First-time setup: install all toolchain dependencies
setup:
	python -m venv .venv && .venv/bin/pip install -r backend/requirements.txt
	.venv/bin/pip install -r requirements-dev.txt
	cd frontend && npm install
	cargo build --release --manifest-path ingestion-worker/Cargo.toml
	cp .env.example .env

# Compile Rust ingestion worker (native, for dev mode)
build-rust:
	cargo build --release --manifest-path ingestion-worker/Cargo.toml

# Dev mode: start only Qdrant + Ollama in Docker (infrastructure)
dev-infra:
	docker compose -f docker-compose.dev.yml up -d
	@echo "Qdrant: http://localhost:6333  |  Ollama: http://localhost:11434"

# Start Python backend with hot reload
dev-backend:
	PYTHONPATH=backend .venv/bin/uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Start Next.js frontend with hot reload
dev-frontend:
	cd frontend && npm run dev

# Full dev mode: infra in Docker, backend + frontend natively (3 terminals)
dev: dev-infra
	@echo "Run in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-frontend"

# Full Docker deployment: build and start all services
up:
	docker compose up --build

# Stop all Docker services
down:
	docker compose down

# Pull default Ollama models after first start
pull-models:
	curl http://localhost:11434/api/pull -d '{"name":"llama3.2"}'
	curl http://localhost:11434/api/pull -d '{"name":"nomic-embed-text"}'

# Run backend tests
test:
	.venv/bin/pytest tests/ -q --tb=short --no-header

# Run backend tests with coverage
test-cov:
	.venv/bin/pytest tests/ --cov=backend --cov-report=term-missing -q --tb=short

# Run frontend tests
test-frontend:
	cd frontend && npm run test

# Wipe runtime data (keeps model volumes)
clean:
	rm -rf data/uploads/* data/embedinator.db
	find . -name "__pycache__" -type d -exec rm -rf {} +

# Full teardown including Docker volumes (removes downloaded Ollama models)
clean-all: down clean
	docker volume rm the-embedinator_ollama_models || true
```

### .env.example

```bash
# ── Ollama ──────────────────────────────────────────────
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_MODEL=llama3.2
DEFAULT_EMBED_MODEL=nomic-embed-text

# ── Qdrant ──────────────────────────────────────────────
QDRANT_HOST=localhost
QDRANT_PORT=6333

# ── Backend ─────────────────────────────────────────────
HOST=0.0.0.0
PORT=8000
SQLITE_PATH=data/embedinator.db
LOG_LEVEL=INFO
DEBUG=false

# ── Security ────────────────────────────────────────────
# Auto-generated on first run if empty. Keep this value secret.
API_KEY_ENCRYPTION_SECRET=

# ── Agent Limits ────────────────────────────────────────
MAX_ITERATIONS=10
MAX_TOOL_CALLS=8
CONFIDENCE_THRESHOLD=0.6

# ── Retrieval ───────────────────────────────────────────
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
TOP_K_RETRIEVAL=20
TOP_K_RERANK=5

# ── CORS (comma-separated origins) ─────────────────────
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### backend/config.py

```python
"""Central configuration using Pydantic Settings with .env file support."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration with typed defaults.

    Values are loaded from environment variables, with .env file as fallback.
    Every setting has a sensible default for local development.
    """

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Providers
    ollama_base_url: str = "http://localhost:11434"
    default_provider: str = "ollama"
    default_llm_model: str = "llama3.2"
    default_embed_model: str = "nomic-embed-text"
    api_key_encryption_secret: str = ""

    # SQLite
    sqlite_path: str = "data/embedinator.db"

    # Ingestion
    rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 100
    parent_chunk_size: int = 3000
    child_chunk_size: int = 500
    embed_batch_size: int = 16
    embed_max_workers: int = 4
    qdrant_upsert_batch_size: int = 50

    # Agent
    max_iterations: int = 10
    max_tool_calls: int = 8
    confidence_threshold: float = 0.6
    meta_reasoning_max_attempts: int = 2

    # Retrieval
    hybrid_dense_weight: float = 0.7
    hybrid_sparse_weight: float = 0.3
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Accuracy & Robustness
    groundedness_check_enabled: bool = True
    citation_alignment_threshold: float = 0.3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_secs: int = 30
    retry_max_attempts: int = 3
    retry_backoff_initial_secs: float = 1.0

    # Rate Limiting
    rate_limit_chat_per_minute: int = 30
    rate_limit_ingest_per_minute: int = 10
    rate_limit_default_per_minute: int = 120

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env")
```

### requirements.txt

```
fastapi>=0.135
uvicorn>=0.34
langgraph>=1.0.10
langchain>=1.2.10
langchain-community>=1.2
langchain-openai>=1.1.10
langchain-anthropic>=0.3
qdrant-client>=1.17.0
sentence-transformers>=5.2.3
pydantic>=2.12
pydantic-settings>=2.8
aiosqlite>=0.21
httpx>=0.28
python-multipart>=0.0.20
tiktoken>=0.12
tenacity>=9.0
cryptography>=44.0
structlog>=24.0
```

### requirements-dev.txt

```
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=6.0
httpx>=0.28
testcontainers[qdrant]>=4.0
```

### .gitignore

```
# Runtime data
data/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# Rust
ingestion-worker/target/

# Node.js
node_modules/
.next/

# Environment
.env

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
```

## Configuration

All configuration is managed through the Settings class and `.env` file. See the full Settings class above for all variables, types, and defaults.

Key Docker Compose environment overrides for container networking:

| Variable | Dev Mode Value | Docker Mode Value |
|----------|---------------|-------------------|
| `QDRANT_HOST` | `localhost` | `qdrant` |
| `QDRANT_PORT` | `6333` | `6333` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | `http://ollama:11434` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | `http://localhost:8000` |
| `INTERNAL_API_URL` | N/A | `http://backend:8000` |

## Error Handling

- **Missing `.env` file**: Settings class falls back to defaults. The application runs with default configuration (localhost Qdrant and Ollama).
- **Docker build failures**: The multi-stage Dockerfile uses Cargo dependency caching (dummy `main.rs` trick) to avoid full recompilation on source changes.
- **GPU not available**: If the NVIDIA GPU block in docker-compose causes errors, users should remove the `deploy.resources.reservations` block from the Ollama service.
- **Port conflicts**: If ports 6333, 8000, or 3000 are in use, users can override via Docker Compose port mapping or `.env` variables.

## Testing Requirements

1. `make setup` completes without errors on a clean machine with Python 3.14, Node.js 22, and Rust 1.93 installed.
2. `backend/config.py` can be imported and instantiated with no environment variables set (all defaults work).
3. Settings class correctly loads values from a `.env` file.
4. Settings class correctly overrides defaults with environment variables.
5. Docker Compose files are valid YAML (`docker compose config` succeeds).
6. The `.gitignore` excludes all specified patterns.

## Done Criteria

- [ ] Full project directory structure exists with all directories and `__init__.py` files
- [ ] `backend/config.py` Settings class is complete with all fields and defaults
- [ ] `docker-compose.yml` defines all four services with health checks and GPU passthrough
- [ ] `docker-compose.dev.yml` defines Qdrant and Ollama only
- [ ] `backend/Dockerfile` is a multi-stage build (Rust Stage 1, Python Stage 2)
- [ ] `frontend/Dockerfile` is a multi-stage build (Next.js build, standalone runner)
- [ ] `Makefile` includes all targets: setup, build-rust, dev-infra, dev-backend, dev-frontend, dev, up, down, pull-models, test, test-cov, test-frontend, clean, clean-all
- [ ] `.env.example` documents all configuration variables with defaults and comments
- [ ] `requirements.txt` lists all Python production dependencies with version constraints
- [ ] `requirements-dev.txt` lists all Python test dependencies
- [ ] `.gitignore` excludes data/, __pycache__/, .venv/, node_modules/, .next/, target/, .env
- [ ] `docker compose config` validates both compose files without errors
- [ ] `Settings()` can be instantiated with no environment variables (all defaults work)
- [ ] The `data/` directory is not tracked by git
