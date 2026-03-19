# Spec 17: Infrastructure — Implementation Plan

## Component Overview

Spec 17 audits and completes the project infrastructure layer. All primary infrastructure files already exist — the goal is to verify conformance with the 15 functional requirements (FR-001 through FR-015) and 8 success criteria (SC-001 through SC-008), then remediate any gaps. No production application logic is changed. All work targets the following infrastructure files:

- `backend/config.py` — Settings class (FR-009)
- `.env.example` — configuration template (FR-010)
- `Dockerfile.backend` — multi-stage Rust + Python build at project root (FR-004, FR-015)
- `frontend/Dockerfile` — multi-stage standalone Next.js build (FR-005, FR-015)
- `docker-compose.yml` — full 4-service production deployment (FR-006, FR-007, FR-008, FR-014)
- `docker-compose.dev.yml` — 2-service infrastructure-only dev mode (FR-002)
- `Makefile` — 14 named automation targets (FR-011, FR-012)
- `ingestion-worker/Cargo.toml` — Rust dependency definitions (FR-003)
- `requirements.txt` — Python production dependencies (FR-001)

**Out of scope**: CI/CD pipeline files (GitHub Actions, GitLab CI, etc.). The Makefile targets (`make test`, `make test-cov`, `make build-rust`) are the integration hooks any external pipeline can call.

---

## What Already Exists — Verify, Do Not Recreate Blindly

All of the following files exist. Agents MUST read each file before editing it. Edits are only made to bring a file into conformance with a specific FR or SC that it currently fails.

```
Dockerfile.backend              # root-level, multi-stage
frontend/Dockerfile             # multi-stage standalone
docker-compose.yml
docker-compose.dev.yml
docker-compose.prod.yml         # exists; relationship to docker-compose.yml must be clarified
.env.example
.gitignore
Makefile
requirements.txt
ingestion-worker/Cargo.toml
backend/config.py               # Settings class
```

---

## Technical Approach

### Configuration Management (FR-009, FR-010)

`backend/config.py` uses `pydantic-settings` `BaseSettings` with `SettingsConfigDict(env_file=".env")`. All settings have typed defaults. The current Settings class is largely correct but must be verified against the full field list. `.env.example` must document every field from Settings — one variable per line with a comment explaining its purpose, expected type/range, and working default.

**Critical type constraint**: `confidence_threshold` MUST be `int = 60` (0–100 scale). The research graph edge divides by 100 when comparing against the 0.0–1.0 output of the confidence scoring function. Any `float` default (e.g., `0.6`) is a bug.

**Current verified Settings fields** (from `backend/config.py` as of spec-16):

```python
# Server
host: str = "0.0.0.0"
port: int = 8000
log_level: str = "INFO"
debug: bool = False
log_level_overrides: str = Field(default="", alias="LOG_LEVEL_OVERRIDES")  # spec-15

# Frontend
frontend_port: int = 3000

# Qdrant
qdrant_host: str = "localhost"
qdrant_port: int = 6333

# Providers
ollama_base_url: str = "http://localhost:11434"
default_provider: str = "ollama"
default_llm_model: str = "qwen2.5:7b"     # NOT llama3.2
default_embed_model: str = "nomic-embed-text"
api_key_encryption_secret: str = ""

# SQLite
sqlite_path: str = "data/embedinator.db"

# Ingestion
upload_dir: str = "data/uploads"
max_upload_size_mb: int = 100
parent_chunk_size: int = 3000
child_chunk_size: int = 500
embed_batch_size: int = 16
rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
embed_max_workers: int = 4
qdrant_upsert_batch_size: int = 50

# Agent
max_iterations: int = 10
max_tool_calls: int = 8
confidence_threshold: int = 60             # int 0-100, NOT float
compression_threshold: float = 0.75
meta_reasoning_max_attempts: int = 2
meta_relevance_threshold: float = 0.2      # spec-04
meta_variance_threshold: float = 0.15      # spec-04

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
rate_limit_provider_keys_per_minute: int = 5
rate_limit_general_per_minute: int = 120   # NOT rate_limit_default_per_minute

# CORS
cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
```

### Docker Strategy (FR-002 through FR-008, FR-014, FR-015)

**Full mode** (`docker-compose.yml`): Four services — Qdrant, Ollama, backend, frontend. Backend uses `Dockerfile.backend` (multi-stage: Rust compilation then Python runtime). Frontend uses `frontend/Dockerfile` (multi-stage: Next.js build then standalone runner). Health checks on all services with `depends_on: condition: service_healthy`. NVIDIA GPU passthrough for Ollama via `deploy.resources.reservations.devices`. Named volumes for all persistent data. Restart policies (`unless-stopped` or `on-failure`) on all services.

**Dev mode** (`docker-compose.dev.yml`): Two services only — Qdrant and Ollama. Backend and frontend run natively with `uvicorn --reload` and `next dev` respectively. This provides sub-3-second code reload (SC-002).

**Non-root users (FR-015)**: Both `Dockerfile.backend` and `frontend/Dockerfile` MUST create a non-root system user and switch to it before the `CMD`/`ENTRYPOINT`. Example pattern:
```dockerfile
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
```

**Note on `docker-compose.prod.yml`**: This file exists in the repository but was not specified in the spec. Agents must inspect it and reconcile with `docker-compose.yml` — either consolidate or document its relationship clearly.

### Build Automation (FR-011, FR-012)

The Makefile must declare exactly these 14 named targets (FR-011):

| Target | Purpose |
|--------|---------|
| `setup` | Install all dependencies (Python pip, Node npm, build-rust) |
| `build-rust` | Compile the ingestion worker binary from source |
| `dev-infra` | Start Qdrant + Ollama in Docker only |
| `dev-backend` | Run backend natively with hot reload |
| `dev-frontend` | Run frontend natively with hot reload |
| `dev` | Start dev-infra then dev-backend + dev-frontend |
| `up` | Build and start all 4 services in production mode |
| `down` | Stop all services |
| `pull-models` | Download required models via Ollama |
| `test` | Run backend test suite (no coverage enforcement) |
| `test-cov` | Run backend tests with ≥80% coverage gate (FR-012) |
| `test-frontend` | Run frontend vitest tests |
| `clean` | Remove runtime data (data/) |
| `clean-all` | Remove all generated artifacts including volumes and build outputs |

`make test-cov` must invoke `pytest` with `--cov=backend --cov-fail-under=80` (or use `scripts/run-tests-external.sh`) and exit non-zero when coverage < 80% (SC-006).

### Python Dependencies (FR-001)

`requirements.txt` must include all packages used across all 16 prior specs. Correct package names:

```
# Core framework
fastapi>=0.135
uvicorn[standard]
pydantic>=2.12
pydantic-settings

# LangGraph / LangChain
langgraph>=1.0.10
langgraph-checkpoint-sqlite>=2.0          # NOT langgraph-checkpoint (old name)
langchain-core>=1.2.10                    # NOT "langchain" (that is a meta-package)
langchain-ollama                          # spec-10 — NOT langchain-community
langchain-openai
langchain-anthropic

# Storage
aiosqlite>=0.21
qdrant-client>=1.17.0

# ML
sentence-transformers>=5.2.3

# HTTP
httpx>=0.28

# Observability
structlog>=24.0

# Security
cryptography>=44.0

# Testing (may be in same file or requirements-dev.txt if it is created)
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=6.0
```

Note: `tenacity` is NOT in `requirements.txt` per codebase state. Do not add it unless specifically absent from the file and required by production code.

---

## File Structure (Corrected)

This reflects the actual codebase as of spec-16. Agents must not recreate existing files or add files not in this list.

```
the-embedinator/
  backend/
    __init__.py
    api/
      __init__.py
      chat.py
      collections.py
      documents.py
      health.py
      ingest.py
      models.py
      providers.py
      settings.py
      traces.py
    agent/
      __init__.py
      answer_generator.py
      citations.py
      confidence.py
      conversation_graph.py
      edges.py
      meta_reasoning_edges.py
      meta_reasoning_graph.py
      meta_reasoning_nodes.py
      nodes.py
      prompts.py
      research_edges.py
      research_graph.py
      research_nodes.py
      retrieval.py
      schemas.py
      state.py
      tools.py
    ingestion/
      __init__.py
      chunker.py
      embedder.py
      incremental.py
      pipeline.py
    retrieval/
      __init__.py
      reranker.py
      score_normalizer.py
      searcher.py
      # NO router.py — routing logic lives inside searcher.py
    storage/
      __init__.py
      chunker.py
      document_parser.py
      indexing.py
      parent_store.py
      qdrant_client.py
      sqlite_db.py
    providers/
      __init__.py
      base.py
      registry.py
      ollama.py
      openrouter.py
      openai.py
      anthropic.py
      key_manager.py
    config.py
    errors.py
    main.py
    middleware.py
    # NO logging_config.py — logging configured inline in main.py
    # NO timing.py — stage timings live in state.py + nodes.py
    # NO validators.py — validation is in Pydantic models
  ingestion-worker/
    src/
      main.rs
      pdf.rs
      markdown.rs
      text.rs
      heading_tracker.rs
      types.rs
    Cargo.toml
  frontend/
    app/ (page components)
    components/ (18 component files)
    lib/
      api.ts
      types.ts
    hooks/ (4 hook files)
    next.config.ts
    package.json
    tsconfig.json
    Dockerfile
    # NO tailwind.config.ts — Tailwind v4 does not use a separate config file
  tests/ (see Spec 16)
  data/ (gitignored, created at runtime)
  Dockerfile.backend           # root-level multi-stage (NOT backend/Dockerfile)
  docker-compose.yml
  docker-compose.dev.yml
  docker-compose.prod.yml      # inspect and reconcile with docker-compose.yml
  .env.example
  .gitignore
  Makefile
  requirements.txt             # single file (NO requirements-dev.txt)
  README.md
```

---

## Testing Protocol

> These rules are absolute. Every agent in every wave must follow them.

**NEVER run pytest directly inside Claude Code.**

Wrong:
```bash
pytest tests/
python -m pytest tests/
.venv/bin/pytest tests/
```

Correct:
```bash
zsh scripts/run-tests-external.sh -n <run-name> <target>
```

The script:
- Runs pytest in a background process
- Writes results to `Docs/Tests/<run-name>.{status,summary,log}`
- Returns immediately; poll with: `cat Docs/Tests/<run-name>.status`
- Read results with: `cat Docs/Tests/<run-name>.summary`
- Debug failures with: `grep "FAILED" Docs/Tests/<run-name>.log`

For spec-17 validation (no new test files — only verifying existing suite passes):
```bash
zsh scripts/run-tests-external.sh -n spec17-validate tests/
```

For fast gate checks without coverage overhead:
```bash
zsh scripts/run-tests-external.sh -n spec17-quick --no-cov tests/unit/
```

The script accepts ONE target. For multi-file verification, run separate invocations.

---

## Agent Teams Wave Structure

Implementation uses 4 waves with 5 agents following the pattern from specs 07–16.

Instruction files are stored at: `Docs/PROMPTS/spec-17-infra/agents/`

Spawn pattern:
```
Read your instruction file at Docs/PROMPTS/spec-17-infra/agents/A{N}-{role}.md FIRST, then execute all assigned tasks.
```

### Wave 1 — A1 (infrastructure-engineer, Sonnet)

**Goal**: Audit all existing infrastructure files against spec requirements. Create instruction files for all downstream agents. Establish baseline test count.

**Tasks**:
1. Run baseline suite to confirm 1487 tests passing (post-spec-16 baseline):
   ```bash
   zsh scripts/run-tests-external.sh -n spec17-baseline --no-cov tests/
   ```
   Record the exact test count and any pre-existing failures in the A5 instruction file.
2. Read and audit these files against all 15 FRs:
   - `Dockerfile.backend` — check FR-004 (multi-stage) and FR-015 (non-root user)
   - `frontend/Dockerfile` — check FR-005 (multi-stage standalone) and FR-015 (non-root user)
   - `docker-compose.yml` — check FR-006 (health checks), FR-007 (volumes), FR-008 (GPU), FR-014 (restart policies)
   - `docker-compose.dev.yml` — check FR-002 (2-service dev mode only)
   - `Makefile` — count targets, verify all 14 from FR-011 are present; check FR-012 (coverage gate)
   - `requirements.txt` — check for correct package names (langchain-core not langchain, langchain-ollama not langchain-community, langgraph-checkpoint-sqlite)
   - `.env.example` — check FR-010 (every Settings field documented with comment and default)
   - `backend/config.py` — check all required fields are present with correct types and defaults
3. Produce a gap report: list every FR that is not yet satisfied, with the specific file and line that needs changing.
4. Create `Docs/PROMPTS/spec-17-infra/agents/` directory.
5. Write instruction files `a2-instructions.md` through `a5-instructions.md` with the specific gaps each agent must remediate.

**Gate before Wave 2**: `spec17-baseline.status` must be PASSED. Gap report must be complete.

### Wave 2 — A2 + A3 (python-expert, Sonnet, parallel)

**Goal**: Remediate configuration and container image gaps. A2 and A3 work on non-overlapping files.

**A2 — Configuration (backend/config.py + .env.example)**:
1. Verify `backend/config.py` contains all fields listed in the Technical Approach section with correct types and defaults. Pay special attention to:
   - `confidence_threshold: int = 60` (must be int, not float)
   - `default_llm_model: str = "qwen2.5:7b"` (not llama3.2)
   - `log_level_overrides: str = Field(default="", alias="LOG_LEVEL_OVERRIDES")`
   - `rate_limit_general_per_minute: int = 120` (not rate_limit_default_per_minute)
   - `rate_limit_provider_keys_per_minute: int = 5`
2. Add any missing fields; correct any wrong types or defaults.
3. Audit `.env.example` — every variable in Settings must appear in `.env.example` with a comment. Add any missing entries. Format:
   ```
   # Description of what this setting controls. Expected: string. Default: "value".
   VARIABLE_NAME=value
   ```
4. Run gate after changes:
   ```bash
   zsh scripts/run-tests-external.sh -n spec17-a2 --no-cov tests/unit/test_config.py
   ```
   All config tests must pass.

**A3 — Container images (Dockerfile.backend + frontend/Dockerfile)**:
1. Audit `Dockerfile.backend` for FR-004 (multi-stage: Stage 1 compiles Rust, Stage 2 is Python runtime with binary copied in) and FR-015 (non-root user before CMD).
2. Audit `frontend/Dockerfile` for FR-005 (multi-stage: Stage 1 builds Next.js with `output: "standalone"`, Stage 2 runs standalone server) and FR-015 (non-root user before CMD).
3. Apply the non-root user pattern to any Dockerfile missing it:
   ```dockerfile
   RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
   USER appuser
   ```
4. Verify frontend Dockerfile does NOT reference `tailwind.config.ts` (Tailwind v4 has no config file).
5. Verify `next.config.ts` sets `output: "standalone"` for FR-013.

**Gate before Wave 3**: Both A2 and A3 must signal completion. A2's config test run must be PASSED.

### Wave 3 — A4 (backend-architect, Sonnet)

**Goal**: Remediate Compose and Makefile gaps identified by A1.

**Tasks**:
1. Audit and update `docker-compose.yml`:
   - FR-006: All 4 services must have `healthcheck` sections with appropriate `test`, `interval`, `timeout`, `retries`.
   - FR-007: Qdrant data, SQLite database, and uploaded files MUST use named volumes or bind mounts that survive restarts.
   - FR-008: Ollama service must include GPU passthrough block (with CPU fallback — the block is safe to include on CPU-only machines; Docker simply ignores it when no GPU is available):
     ```yaml
     deploy:
       resources:
         reservations:
           devices:
             - driver: nvidia
               count: all
               capabilities: [gpu]
     ```
   - FR-014: All services must have `restart: unless-stopped` (or `on-failure`).
   - Backend and frontend services must set Docker networking env vars: `QDRANT_HOST=qdrant`, `OLLAMA_BASE_URL=http://ollama:11434`.
2. Audit and update `docker-compose.dev.yml`:
   - Must contain only 2 services: Qdrant and Ollama.
   - Must NOT start backend or frontend containers (those run natively in dev mode).
3. Reconcile `docker-compose.prod.yml` with `docker-compose.yml` — if they are duplicates, consolidate. Document the decision.
4. Audit and update `Makefile`:
   - Verify all 14 targets from FR-011 are present (see table in Technical Approach).
   - Verify `test-cov` target includes `--cov-fail-under=80` (FR-012).
   - Every target must have a brief `@echo` describing what it does (SC-008 self-documenting requirement).
   - `make help` or the default `make` target should list all targets with descriptions.

**Gate before Wave 4**: A4 signals completion. No gate test required (infrastructure files; tested by A5).

### Wave 4 — A5 (quality-engineer, Sonnet)

**Goal**: Full suite validation. Confirm all 8 SCs pass. Zero regressions from spec baseline.

**Tasks**:
1. Run complete suite:
   ```bash
   zsh scripts/run-tests-external.sh -n spec17-final tests/
   ```
2. Confirm total passing tests >= 1487 (the post-spec-16 baseline from A1's run).
3. Confirm 0 new failures vs. the pre-existing failure baseline recorded by A1.
4. Verify SC-005 (`.env.example` completeness): Count Settings fields in `backend/config.py` and count documented variables in `.env.example`. They must match.
5. Verify SC-006 (coverage gate): Confirm `pytest.ini` or `Makefile`'s `test-cov` target has `--cov-fail-under=80`.
6. Verify SC-008 (self-documenting Makefile): Read the Makefile and confirm each of the 14 FR-011 targets has a description comment or `@echo` message.
7. Verify FR-015: Read `Dockerfile.backend` and `frontend/Dockerfile` and confirm both contain `USER <non-root-user>` before the final `CMD` or `ENTRYPOINT`.
8. Write a validation report to `specs/017-infra-setup/validation-report.md` with:
   - Final test count and coverage %
   - Per-FR status (PASS / FAIL / N/A for infra-only FRs)
   - Per-SC status

---

## Integration Points

- **All specs**: Every spec depends on `backend/config.py` Settings for configuration. Field names must exactly match what modules import (e.g., `settings.rate_limit_general_per_minute`, not `settings.rate_limit_default_per_minute`).
- **Spec 13 (Security)**: `api_key_encryption_secret` in Settings maps to `EMBEDINATOR_FERNET_KEY` env var. `.env.example` must document this. Containers must not run as root (FR-015 reinforces spec-13 security hardening).
- **Spec 15 (Observability)**: `log_level_overrides` uses `LOG_LEVEL_OVERRIDES` env var alias. Docker Compose must forward this env var to the backend container.
- **Spec 16 (Testing)**: `make test-cov` must invoke the same 80% threshold as `pytest.ini`'s `--cov-fail-under=80`.
- **Spec 06 (Ingestion)**: `rust_worker_path` in Settings points to the compiled Rust binary. `Dockerfile.backend` must build the binary in Stage 1 and place it at this exact path in Stage 2.
- **Spec 10 (Providers)**: `langchain-ollama` (not `langchain-community`) must be in `requirements.txt`. LangGraph checkpoint package must be `langgraph-checkpoint-sqlite>=2.0`.

---

## Key Code Patterns

### Docker Networking Override

```yaml
# In docker-compose.yml, backend service overrides localhost references:
environment:
  QDRANT_HOST: qdrant              # Docker service name, not "localhost"
  OLLAMA_BASE_URL: http://ollama:11434
  SQLITE_PATH: /data/embedinator.db
  UPLOAD_DIR: /data/uploads
```

### Non-Root User Pattern (FR-015)

```dockerfile
# In both Dockerfile.backend and frontend/Dockerfile, before CMD:
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --no-create-home appuser
USER appuser
```

### Multi-Stage Dockerfile.backend

```dockerfile
# Stage 1 — Rust compiler
FROM rust:1.93 AS rust-builder
WORKDIR /build
COPY ingestion-worker/ .
RUN cargo build --release

# Stage 2 — Python runtime
FROM python:3.14-slim
WORKDIR /app
COPY --from=rust-builder /build/target/release/embedinator-worker \
     /app/ingestion-worker/target/release/embedinator-worker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Health Check Pattern (FR-006)

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 10s
  timeout: 5s
  retries: 5
  start_period: 30s
```

### Makefile Self-Documentation Pattern (SC-008)

```makefile
.PHONY: help
help:           ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup:          ## Install all dependencies (Python, Node, Rust binary)
	pip install -r requirements.txt
	cd frontend && npm install
	$(MAKE) build-rust

test-cov:       ## Run backend tests with ≥80% coverage gate (exits non-zero if below threshold)
	pytest --cov=backend --cov-report=term-missing --cov-fail-under=80 tests/
```

---

## Success Criteria Mapping

| SC | Criterion | FR | Verified by | Verification Method |
|----|-----------|-----|-------------|---------------------|
| SC-001 | Single setup command, zero manual steps | FR-001, FR-011 | A5 | `make setup` completes without error |
| SC-002 | Code changes in dev mode reflected in <3s | FR-002 | Manual | `uvicorn --reload` + `next dev` hot reload |
| SC-003 | Single-command production deploy | FR-002, FR-011 | A5 | `make up` reaches healthy state |
| SC-004 | All 4 services healthy within 120s | FR-006 | A5 | Verify `healthcheck` on all compose services |
| SC-005 | `.env.example` documents 100% of settings | FR-010 | A5 | Count Settings fields vs. `.env.example` entries |
| SC-006 | ≥80% coverage gate auto-enforced | FR-012 | A5 | `pytest.ini` has `--cov-fail-under=80` |
| SC-007 | Zero data loss across full restart | FR-007 | A5 | Verify named volumes on all data paths |
| SC-008 | Self-documenting Makefile targets | FR-011 | A5 | Each of 14 targets has a `##` comment |

---

## Corrections Applied

The following errors in the original `17-plan.md` are corrected in this version:

1. **`backend/retrieval/router.py` removed**: This file does not exist. Routing logic lives inside `backend/retrieval/searcher.py`. Added to the file structure with an explicit comment.

2. **`backend/Dockerfile` → `Dockerfile.backend` at project root**: The original plan listed `backend/Dockerfile` as a path. The actual file is `Dockerfile.backend` at the repo root (confirmed by Serena). All Dockerfile references updated.

3. **`frontend/tailwind.config.ts` removed**: Tailwind v4 does not use a separate config file. Confirmed absent from `frontend/`. Removed from file structure and `make setup` instructions.

4. **`backend/logging_config.py`, `timing.py`, `validators.py` removed**: None of these files exist. Logging is configured inline in `backend/main.py`; stage timings live in `state.py`; validation uses Pydantic models. All removed from the file structure.

5. **`requirements-dev.txt` removed**: Only `requirements.txt` exists (confirmed by Serena). References to a separate dev requirements file are removed.

6. **Agent Teams added**: The original plan had no Agent Teams structure. This version defines 4 waves with 5 agents following the pattern from specs 07–16.

7. **External test runner enforced**: The original plan had no mention of `scripts/run-tests-external.sh`. A dedicated Testing Protocol section now mandates it and prohibits direct `pytest` calls.

8. **CI/CD explicitly excluded**: Phase 3 in the original plan mentioned "CI/CD pipeline configuration." This is now explicitly out of scope per spec clarification.

9. **FR-015 (non-root containers) added**: The original plan made no mention of non-root container users. FR-015 is now addressed in the Docker Strategy section, the A3 agent tasks, and the Non-Root User Pattern code example.

10. **Settings field corrections**:
    - `confidence_threshold: int = 60` — correctly documented as `int` (not `float = 0.6`)
    - `default_llm_model: str = "qwen2.5:7b"` — corrected from `llama3.2`
    - `log_level_overrides: str = Field(alias="LOG_LEVEL_OVERRIDES")` — spec-15 field added
    - `rate_limit_general_per_minute` — correct name (not `rate_limit_default_per_minute`)
    - `rate_limit_provider_keys_per_minute = 5` — spec-10 field added
    - `meta_relevance_threshold = 0.2`, `meta_variance_threshold = 0.15` — spec-04 fields added
    - `frontend_port: int = 3000` — spec-15 field added

11. **Python dependency corrections**:
    - `langchain-core` (not `langchain`)
    - `langchain-ollama` (not `langchain-community`) — from spec-10
    - `langgraph-checkpoint-sqlite>=2.0` (not the old name)

12. **Agent file structure corrected**: Added `backend/api/documents.py`, `backend/api/health.py`, `backend/agent/answer_generator.py`, `backend/agent/citations.py`, `backend/agent/retrieval.py`, `backend/agent/meta_reasoning_*.py`, `backend/storage/chunker.py`, `backend/storage/document_parser.py`, `backend/storage/indexing.py` — all of which exist in the actual codebase.

13. **"Create" → "Audit and update" framing**: All infrastructure files already exist. The plan now correctly frames agent work as auditing existing files against FRs and remediating gaps, not creating from scratch.
