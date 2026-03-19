# Spec 17: Infrastructure — Implementation Context

```
# ⚠️ MANDATORY: TMUX MULTI-PANE SPAWNING REQUIRED
# Agent Teams MUST run in tmux. Each wave agent gets its own pane.
# See: https://docs.anthropic.com/en/docs/claude-code/agent-teams
```

---

## What This Spec Does

Spec-17 is an **audit and remediation** spec. It does NOT create infrastructure from scratch — all files already exist at post-spec-16 state. The goal is to close gaps identified in an audit of 15 functional requirements (FR-001–FR-015) against the current repository state.

Do not write new files unless a gap explicitly requires one. Every agent task is a targeted fix or verification against an existing file.

---

## Gap Summary (from research.md)

Five primary gaps were found in the audit:

1. **`Dockerfile.backend`** — single-stage Python-only build. Needs a Rust compile stage (FR-004) and a non-root user (FR-015).
2. **`Makefile`** — only 7 of the 14 required named targets present. Needs 9 additions/renames (FR-011, SC-008).
3. **`backend/config.py`** — `api_key_encryption_secret` missing `alias="EMBEDINATOR_FERNET_KEY"` (Constitution V). Also missing `model_config` `populate_by_name=True` which is required when aliased fields are present.
4. **`docker-compose.yml`** — GPU passthrough block needs verification (FR-008); missing `LOG_LEVEL_OVERRIDES` and `RUST_WORKER_PATH` environment variable overrides in the backend service (FR-009, FR-010).
5. **`.env.example`** — missing entries for specs 04, 10, and 15 fields; uses wrong key name `API_KEY_ENCRYPTION_SECRET` instead of `EMBEDINATOR_FERNET_KEY`; uses wrong defaults (`llama3.2`, `CONFIDENCE_THRESHOLD=0.6`).

---

## ⚠️ CONSTITUTION V — SECURE BY DEFAULT

```
api_key_encryption_secret MUST use Field(default="", alias="EMBEDINATOR_FERNET_KEY")

Without the alias, pydantic-settings reads the env var API_KEY_ENCRYPTION_SECRET (wrong).
The correct env var name is EMBEDINATOR_FERNET_KEY — used by all upstream specs since spec-07.

.env.example MUST document EMBEDINATOR_FERNET_KEY= (not API_KEY_ENCRYPTION_SECRET=).
model_config MUST include populate_by_name=True when alias fields are present.
```

---

## Testing Protocol — MANDATORY

```
NEVER run pytest directly. Always use:
  zsh scripts/run-tests-external.sh -n <run-name> <target>

The script runs pytest in the background, writing results to:
  Docs/Tests/<run-name>.status    — poll this (values: running / done / error)
  Docs/Tests/<run-name>.summary   — human-readable result (pass/fail counts, coverage)
  Docs/Tests/<run-name>.log       — full pytest output

Polling:
  cat Docs/Tests/<run-name>.status
  cat Docs/Tests/<run-name>.summary

ONE target per invocation. Run separate invocations for multi-file checks.
Add --no-cov to skip coverage threshold enforcement for gate checks.
```

---

## Agent Teams Wave Structure

### Wave 1 — A1 (devops-architect, Sonnet) — runs alone

Runs the baseline test suite, performs a full gap audit of all infrastructure files against each FR, and writes A2–A5 instruction files. Gates Wave 2 on baseline completion.

### Wave 2 — A2 + A3 (python-expert, Sonnet) — PARALLEL after Wave 1

- A2: `backend/config.py` + `.env.example` (T030–T035)
- A3: `Dockerfile.backend` rewrite (T019–T021)

Both run simultaneously in separate tmux panes after Wave 1 gate passes.

### Wave 3 — A4 (backend-architect, Sonnet) — after Wave 2

`requirements.txt`, `.gitignore`, `ingestion-worker/Cargo.toml`, `Makefile` targets, `docker-compose.yml` env overrides, `docker-compose.prod.yml` comment header, and testing targets (T008–T018, T022–T029, T036–T039).

### Wave 4 — A5 (quality-engineer, Sonnet) — after Wave 3

Makefile `help` target + `##` comments, final test run, validation report (T040–T044).

### Spawn Pattern

```
Read your instruction file at Docs/PROMPTS/spec-17-infra/agents/A{N}-instructions.md FIRST,
then await orchestrator instructions.
```

---

## Files to Modify vs Verify

```
MODIFY (targeted gap fixes):
  Dockerfile.backend              — multi-stage Rust+Python + non-root user (FR-004, FR-015)
  backend/config.py               — EMBEDINATOR_FERNET_KEY alias + populate_by_name=True (Constitution V)
  .env.example                    — all 28 Settings fields; correct key names and defaults
  Makefile                        — 9 missing targets + ## self-doc comments + help target
  docker-compose.yml              — LOG_LEVEL_OVERRIDES + RUST_WORKER_PATH overrides

VERIFY ONLY (no changes expected unless audit reveals a gap):
  frontend/Dockerfile             — already compliant (USER nextjs present, multi-stage)
  docker-compose.dev.yml          — already has exactly 2 services
  docker-compose.prod.yml         — add comment header explaining production override purpose
  .gitignore                      — verify all required patterns present
  requirements.txt                — verify correct package names (langchain-core, not langchain)
  ingestion-worker/Cargo.toml     — verify Rust deps present
```

---

## Correct Code Specifications

Use the code blocks below as the authoritative reference for every change. Do not infer from the stale 17-implement.md content that preceded this file.

### `backend/config.py` — complete correct form

Key differences from the current file (as of post-spec-16):
- Line 31: `api_key_encryption_secret: str = ""` must become `Field(default="", alias="EMBEDINATOR_FERNET_KEY")`
- Line 79: `SettingsConfigDict(env_file=".env")` must become `SettingsConfigDict(env_file=".env", populate_by_name=True)`

All other fields shown below are already correct — verify but do not change unless a discrepancy exists.

```python
"""Application configuration via environment variables with sensible local-first defaults."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False
    log_level_overrides: str = Field(default="", alias="LOG_LEVEL_OVERRIDES")  # spec-15

    # Frontend
    frontend_port: int = 3000  # spec-09

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Providers
    ollama_base_url: str = "http://localhost:11434"
    default_provider: str = "ollama"
    default_llm_model: str = "qwen2.5:7b"           # NOT llama3.2
    default_embed_model: str = "nomic-embed-text"
    api_key_encryption_secret: str = Field(default="", alias="EMBEDINATOR_FERNET_KEY")  # Constitution V

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
    confidence_threshold: int = 60   # INTEGER 0–100; edge divides by 100 when comparing to float score
    compression_threshold: float = 0.75
    meta_reasoning_max_attempts: int = 2
    meta_relevance_threshold: float = 0.2   # spec-04
    meta_variance_threshold: float = 0.15   # spec-04

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
    rate_limit_provider_keys_per_minute: int = 5    # spec-10
    rate_limit_general_per_minute: int = 120        # NOT rate_limit_default_per_minute

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)


settings = Settings()
```

### `Dockerfile.backend` — multi-stage Rust + Python

The binary destination path `/app/ingestion-worker/target/release/embedinator-worker` must match the `rust_worker_path` default in Settings exactly.

```dockerfile
# Stage 1 — Compile Rust ingestion worker
FROM rust:1.93 AS rust-builder
WORKDIR /build

# Cache Cargo dependencies before copying source (dummy main.rs trick)
COPY ingestion-worker/Cargo.toml ingestion-worker/Cargo.lock ./
RUN mkdir src && echo "fn main() {}" > src/main.rs && \
    cargo build --release && \
    rm -f target/release/deps/embedinator_worker*

# Copy real source and rebuild
COPY ingestion-worker/src ./src
RUN cargo build --release

# Stage 2 — Python runtime
FROM python:3.14-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Copy compiled Rust binary — path must match rust_worker_path default in Settings
COPY --from=rust-builder /build/target/release/embedinator-worker \
    /app/ingestion-worker/target/release/embedinator-worker

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

# Non-root user (FR-015)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup --no-create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### `docker-compose.yml` — backend service environment block

Add or update the `environment` block of the `backend` service. The `LOG_LEVEL_OVERRIDES` and `RUST_WORKER_PATH` entries are the new additions.

```yaml
environment:
  QDRANT_HOST: qdrant
  OLLAMA_BASE_URL: http://ollama:11434
  SQLITE_PATH: /data/embedinator.db
  UPLOAD_DIR: /data/uploads
  LOG_LEVEL_OVERRIDES: ${LOG_LEVEL_OVERRIDES:-}
  RUST_WORKER_PATH: /app/ingestion-worker/target/release/embedinator-worker
```

### `Makefile` — 14 required targets with `##` self-doc comments

FR-011 requires exactly 14 named targets. SC-008 requires every target to carry a `## Short description` comment. The `help` target reads those comments to generate its output.

Existing targets in the current Makefile that conflict with the required set:
- `docker-up` → rename to `up`
- `docker-down` → rename to `down`
- `build`, `test-unit`, `test-integration`, `lint`, `format`, `docker-clean`, `logs`, `logs-backend`, `logs-frontend` are not in the required 14 — remove or leave as undocumented extras

The 14 required targets are: `help`, `setup`, `build-rust`, `dev-infra`, `dev-backend`, `dev-frontend`, `dev`, `up`, `down`, `pull-models`, `test`, `test-cov`, `test-frontend`, `clean`, `clean-all`.

Wait — that is 15. The `.PHONY` list in the task spec counts 14. Treat `help` as required (SC-008) and included in the 14 count alongside the others. The exact set per FR-011 is:

```
help setup build-rust dev-infra dev-backend dev-frontend dev
up down pull-models test test-cov test-frontend clean clean-all
```

Complete Makefile:

```makefile
.PHONY: help setup build-rust dev-infra dev-backend dev-frontend dev up down pull-models test test-cov test-frontend clean clean-all

help:  ## Show all available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup:  ## Install all dependencies (Python pip, Node npm, Rust binary)
	pip install -r requirements.txt
	cd frontend && npm install
	$(MAKE) build-rust

build-rust:  ## Compile the Rust ingestion worker binary
	cd ingestion-worker && cargo build --release

dev-infra:  ## Start Qdrant + Ollama in Docker (infrastructure only, for dev mode)
	docker compose -f docker-compose.dev.yml up -d

dev-backend:  ## Start Python backend with hot reload (uvicorn --reload)
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## Start Next.js frontend with hot reload (next dev)
	cd frontend && npm run dev

dev: dev-infra  ## Start dev-infra then print instructions for backend + frontend
	@echo "Run in separate terminals: make dev-backend  /  make dev-frontend"

up:  ## Build and start all 4 production Docker services
	docker compose up --build -d

down:  ## Stop all Docker services
	docker compose down

pull-models:  ## Pull default Ollama models (qwen2.5:7b + nomic-embed-text)
	docker exec $$(docker compose ps -q ollama) ollama pull qwen2.5:7b
	docker exec $$(docker compose ps -q ollama) ollama pull nomic-embed-text

test:  ## Run backend tests (no coverage threshold)
	zsh scripts/run-tests-external.sh -n make-test --no-cov tests/

test-cov:  ## Run backend tests with >=80% coverage gate (exits non-zero if below threshold)
	zsh scripts/run-tests-external.sh -n make-test-cov tests/

test-frontend:  ## Run frontend tests (vitest)
	cd frontend && npm run test

clean:  ## Remove runtime data (data/ directory contents)
	rm -rf data/

clean-all: down  ## Full teardown: stop containers, remove volumes and build outputs
	docker compose down -v
	rm -rf data/ ingestion-worker/target/ frontend/.next/
```

Note: `make test` and `make test-cov` delegate to `run-tests-external.sh`. Agents must never call pytest directly, including from Makefile targets.

### `.env.example` — all 28 Settings fields

Every Settings field must appear with the correct env var name, its type annotation in a comment, and its default value. Critical corrections:
- `EMBEDINATOR_FERNET_KEY=` (not `API_KEY_ENCRYPTION_SECRET=`)
- `CONFIDENCE_THRESHOLD=60` (not `0.6`)
- `DEFAULT_LLM_MODEL=qwen2.5:7b` (not `llama3.2`)
- `RATE_LIMIT_GENERAL_PER_MINUTE=120` (not `RATE_LIMIT_DEFAULT_PER_MINUTE=120`)

```bash
# The Embedinator — Environment Variable Reference
# Copy this file to .env and fill in secrets before running.
# All values shown are the defaults used when a variable is absent.

# ── Server ───────────────────────────────────────────────────────────────────
# HOST — Bind address for uvicorn. Expected: str. Default: 0.0.0.0.
HOST=0.0.0.0

# PORT — Listen port for uvicorn. Expected: int. Default: 8000.
PORT=8000

# LOG_LEVEL — Root log level. Expected: DEBUG|INFO|WARNING|ERROR. Default: INFO.
LOG_LEVEL=INFO

# DEBUG — Enable debug mode (verbose errors). Expected: bool. Default: false.
DEBUG=false

# LOG_LEVEL_OVERRIDES — Per-component log level overrides (spec-15, FR-004).
# Format: comma-separated module.path=LEVEL pairs.
# Example: backend.retrieval.reranker=DEBUG,backend.storage.sqlite_db=WARNING
# Expected: str. Default: (empty string — no overrides).
LOG_LEVEL_OVERRIDES=

# FRONTEND_PORT — Port the Next.js frontend listens on. Expected: int. Default: 3000.
FRONTEND_PORT=3000

# ── Qdrant ───────────────────────────────────────────────────────────────────
# QDRANT_HOST — Hostname of the Qdrant service. Expected: str. Default: localhost.
QDRANT_HOST=localhost

# QDRANT_PORT — Port of the Qdrant HTTP API. Expected: int. Default: 6333.
QDRANT_PORT=6333

# ── Providers ────────────────────────────────────────────────────────────────
# OLLAMA_BASE_URL — Base URL for the Ollama API. Expected: str. Default: http://localhost:11434.
OLLAMA_BASE_URL=http://localhost:11434

# DEFAULT_PROVIDER — Active LLM provider name. Expected: str. Default: ollama.
DEFAULT_PROVIDER=ollama

# DEFAULT_LLM_MODEL — Default Ollama chat model. Expected: str. Default: qwen2.5:7b.
DEFAULT_LLM_MODEL=qwen2.5:7b

# DEFAULT_EMBED_MODEL — Default embedding model name. Expected: str. Default: nomic-embed-text.
DEFAULT_EMBED_MODEL=nomic-embed-text

# EMBEDINATOR_FERNET_KEY — Fernet key for cloud provider API key encryption (spec-07, Constitution V).
# Generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Expected: str (URL-safe base64, 44 chars). Default: (empty — cloud providers disabled until set).
EMBEDINATOR_FERNET_KEY=

# ── SQLite ────────────────────────────────────────────────────────────────────
# SQLITE_PATH — Path to the main SQLite database file. Expected: str. Default: data/embedinator.db.
SQLITE_PATH=data/embedinator.db

# ── Ingestion ─────────────────────────────────────────────────────────────────
# RUST_WORKER_PATH — Path to the compiled Rust ingestion worker binary.
# Expected: str. Default: ingestion-worker/target/release/embedinator-worker.
RUST_WORKER_PATH=ingestion-worker/target/release/embedinator-worker

# UPLOAD_DIR — Directory for uploaded files. Expected: str. Default: data/uploads.
UPLOAD_DIR=data/uploads

# MAX_UPLOAD_SIZE_MB — Maximum file upload size in megabytes. Expected: int. Default: 100.
MAX_UPLOAD_SIZE_MB=100

# PARENT_CHUNK_SIZE — Token size of parent chunks for retrieval. Expected: int. Default: 3000.
PARENT_CHUNK_SIZE=3000

# CHILD_CHUNK_SIZE — Token size of child chunks stored in Qdrant. Expected: int. Default: 500.
CHILD_CHUNK_SIZE=500

# EMBED_BATCH_SIZE — Number of chunks per embedding batch. Expected: int. Default: 16.
EMBED_BATCH_SIZE=16

# EMBED_MAX_WORKERS — Thread pool size for embedding workers. Expected: int. Default: 4.
EMBED_MAX_WORKERS=4

# QDRANT_UPSERT_BATCH_SIZE — Number of points per Qdrant upsert call. Expected: int. Default: 50.
QDRANT_UPSERT_BATCH_SIZE=50

# ── Agent ─────────────────────────────────────────────────────────────────────
# MAX_ITERATIONS — Maximum LangGraph research loop iterations. Expected: int. Default: 10.
MAX_ITERATIONS=10

# MAX_TOOL_CALLS — Maximum tool calls per research turn. Expected: int. Default: 8.
MAX_TOOL_CALLS=8

# CONFIDENCE_THRESHOLD — Minimum confidence score to accept an answer (0–100 integer scale).
# Expected: int. Default: 60. NOTE: do not use 0.6 — the scale is 0–100, not 0.0–1.0.
CONFIDENCE_THRESHOLD=60

# COMPRESSION_THRESHOLD — Cosine similarity threshold for context compression. Expected: float. Default: 0.75.
COMPRESSION_THRESHOLD=0.75

# META_REASONING_MAX_ATTEMPTS — Max meta-reasoning retry attempts. Expected: int. Default: 2.
META_REASONING_MAX_ATTEMPTS=2

# META_RELEVANCE_THRESHOLD — Mean cross-encoder score threshold for meta-reasoning (spec-04).
# Expected: float. Default: 0.2.
META_RELEVANCE_THRESHOLD=0.2

# META_VARIANCE_THRESHOLD — Stdev threshold for noisy result detection in meta-reasoning (spec-04).
# Expected: float. Default: 0.15.
META_VARIANCE_THRESHOLD=0.15

# ── Retrieval ─────────────────────────────────────────────────────────────────
# HYBRID_DENSE_WEIGHT — Weight for dense vector scores in hybrid search. Expected: float. Default: 0.7.
HYBRID_DENSE_WEIGHT=0.7

# HYBRID_SPARSE_WEIGHT — Weight for BM25 sparse scores in hybrid search. Expected: float. Default: 0.3.
HYBRID_SPARSE_WEIGHT=0.3

# TOP_K_RETRIEVAL — Number of candidates retrieved from Qdrant. Expected: int. Default: 20.
TOP_K_RETRIEVAL=20

# TOP_K_RERANK — Number of results kept after cross-encoder reranking. Expected: int. Default: 5.
TOP_K_RERANK=5

# RERANKER_MODEL — HuggingFace cross-encoder model name. Expected: str.
# Default: cross-encoder/ms-marco-MiniLM-L-6-v2.
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# ── Accuracy & Robustness ─────────────────────────────────────────────────────
# GROUNDEDNESS_CHECK_ENABLED — Enable groundedness verification node. Expected: bool. Default: true.
GROUNDEDNESS_CHECK_ENABLED=true

# CITATION_ALIGNMENT_THRESHOLD — Minimum score for citation validity. Expected: float. Default: 0.3.
CITATION_ALIGNMENT_THRESHOLD=0.3

# CIRCUIT_BREAKER_FAILURE_THRESHOLD — Failures before circuit opens. Expected: int. Default: 5.
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5

# CIRCUIT_BREAKER_COOLDOWN_SECS — Seconds before circuit half-opens. Expected: int. Default: 30.
CIRCUIT_BREAKER_COOLDOWN_SECS=30

# RETRY_MAX_ATTEMPTS — Maximum retry attempts for transient failures. Expected: int. Default: 3.
RETRY_MAX_ATTEMPTS=3

# RETRY_BACKOFF_INITIAL_SECS — Initial backoff interval in seconds. Expected: float. Default: 1.0.
RETRY_BACKOFF_INITIAL_SECS=1.0

# ── Rate Limiting ─────────────────────────────────────────────────────────────
# RATE_LIMIT_CHAT_PER_MINUTE — Max chat requests per IP per minute. Expected: int. Default: 30.
RATE_LIMIT_CHAT_PER_MINUTE=30

# RATE_LIMIT_INGEST_PER_MINUTE — Max ingest requests per IP per minute. Expected: int. Default: 10.
RATE_LIMIT_INGEST_PER_MINUTE=10

# RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE — Max provider key requests per IP per minute (spec-10).
# Expected: int. Default: 5.
RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE=5

# RATE_LIMIT_GENERAL_PER_MINUTE — Default rate limit for unlisted endpoints. Expected: int. Default: 120.
RATE_LIMIT_GENERAL_PER_MINUTE=120

# ── CORS ──────────────────────────────────────────────────────────────────────
# CORS_ORIGINS — Comma-separated list of allowed CORS origins.
# Expected: str. Default: http://localhost:3000,http://127.0.0.1:3000.
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

### `requirements.txt` — correct package names

```
fastapi>=0.135
uvicorn>=0.34
langgraph>=1.0.10
langchain-core>=1.2.10
langchain-ollama>=0.3
langchain-openai>=1.1.10
langchain-anthropic>=0.3
langgraph-checkpoint-sqlite>=2.0
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

Key corrections from the stale version:
- `langchain-core>=1.2.10` not `langchain>=1.2.10` (the `langchain` meta-package is not used)
- `langchain-ollama>=0.3` not `langchain-community>=1.2`
- `langgraph-checkpoint-sqlite>=2.0` added (required for checkpointing, was missing)

---

## Pre-existing Test Failures

39 pre-existing failures exist in the test suite. These are documented and not regressions from spec-17 work. The baseline run in T001 records the exact count. All subsequent gate checks compare against that baseline count — the acceptance criterion is "0 new failures", not "0 total failures".

One known pre-existing failure is in `tests/unit/test_config.py`. A gate check on that file (T035) is acceptable if it does not exceed 1 failure.

---

## Success Criteria (from spec.md SC-001–SC-008)

| SC | Criterion | Verification |
|----|-----------|-------------|
| SC-001 | `docker compose config` exits 0 | `docker compose config > /dev/null` |
| SC-002 | `Settings()` instantiates with no env vars | `python -c "from backend.config import Settings; Settings()"` |
| SC-003 | `Settings(EMBEDINATOR_FERNET_KEY='x')` sets `api_key_encryption_secret='x'` | Python assertion |
| SC-004 | `Dockerfile.backend` `FROM` lines include `rust:1.93` | `grep -c "^FROM" Dockerfile.backend` returns 2 |
| SC-005 | `make help` prints all 14 target names with descriptions | `make help` output |
| SC-006 | `.env.example` contains `EMBEDINATOR_FERNET_KEY=` | `grep EMBEDINATOR_FERNET_KEY .env.example` |
| SC-007 | No new test failures vs baseline | Compare `spec17-final.summary` to `spec17-baseline.summary` |
| SC-008 | All Makefile targets have `## description` comment | `grep -c "##" Makefile` |

Validation report path: `specs/017-infra-setup/validation-report.md`

---

## Stale Content Prohibited

The following identifiers appeared in the original 17-implement.md and are incorrect. Any agent that encounters them in a file should treat them as a bug to fix:

| Stale identifier | Correct replacement |
|-----------------|-------------------|
| `requirements-dev.txt` | Does not exist; dev deps are in `requirements.txt` |
| `rate_limit_default_per_minute` | `rate_limit_general_per_minute` |
| `llama3.2` | `qwen2.5:7b` |
| `confidence_threshold: float = 0.6` | `confidence_threshold: int = 60` |
| `API_KEY_ENCRYPTION_SECRET` | `EMBEDINATOR_FERNET_KEY` |
| `langchain-community` | `langchain-ollama` |
| `backend/Dockerfile` | `Dockerfile.backend` (at repo root) |
| `langchain>=1.2.10` | `langchain-core>=1.2.10` |
| `SettingsConfigDict(env_file=".env")` | `SettingsConfigDict(env_file=".env", populate_by_name=True)` |
