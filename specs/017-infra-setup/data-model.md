# Data Model: Spec 17 — Infrastructure

**Date**: 2026-03-19
**Branch**: `017-infra-setup`

---

## Overview

Spec 17 has one primary data structure: the `Settings` class. It is the single source of truth for all runtime configuration across all 17 specs. All other infrastructure artifacts (Dockerfiles, Compose files, Makefile, `.env.example`) derive from or reference this class.

---

## Settings Class

**Location**: `backend/config.py`
**Type**: Pydantic `BaseSettings` — loaded from environment variables and `.env` file

### Server Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `host` | `str` | `"0.0.0.0"` | `HOST` | Bind address for uvicorn |
| `port` | `int` | `8000` | `PORT` | Bind port for uvicorn |
| `log_level` | `str` | `"INFO"` | `LOG_LEVEL` | Root log level (DEBUG/INFO/WARNING/ERROR) |
| `debug` | `bool` | `False` | `DEBUG` | Enable FastAPI debug mode |
| `log_level_overrides` | `str` | `""` | `LOG_LEVEL_OVERRIDES` | Per-component overrides (spec-15, US3) |
| `frontend_port` | `int` | `3000` | `FRONTEND_PORT` | Frontend dev server port |

### Qdrant Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `qdrant_host` | `str` | `"localhost"` | `QDRANT_HOST` | Overridden to `qdrant` in Docker |
| `qdrant_port` | `int` | `6333` | `QDRANT_PORT` | Qdrant HTTP port |

### Provider Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `ollama_base_url` | `str` | `"http://localhost:11434"` | `OLLAMA_BASE_URL` | Overridden to `http://ollama:11434` in Docker |
| `default_provider` | `str` | `"ollama"` | `DEFAULT_PROVIDER` | Default LLM provider name |
| `default_llm_model` | `str` | `"qwen2.5:7b"` | `DEFAULT_LLM_MODEL` | Default chat model |
| `default_embed_model` | `str` | `"nomic-embed-text"` | `DEFAULT_EMBED_MODEL` | Default embedding model |
| `api_key_encryption_secret` | `str` | `""` | `EMBEDINATOR_FERNET_KEY` | **Fernet key for API key encryption — alias required** |

> **Critical**: `api_key_encryption_secret` MUST use `Field(default="", alias="EMBEDINATOR_FERNET_KEY")`. Constitution V specifies this env var name. Without the alias, pydantic-settings reads `API_KEY_ENCRYPTION_SECRET` instead.

### SQLite Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `sqlite_path` | `str` | `"data/embedinator.db"` | `SQLITE_PATH` | Path to main SQLite database |

### Ingestion Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `rust_worker_path` | `str` | `"ingestion-worker/target/release/embedinator-worker"` | `RUST_WORKER_PATH` | Path to compiled Rust binary |
| `upload_dir` | `str` | `"data/uploads"` | `UPLOAD_DIR` | Temporary upload storage |
| `max_upload_size_mb` | `int` | `100` | `MAX_UPLOAD_SIZE_MB` | Max file size per upload |
| `parent_chunk_size` | `int` | `3000` | `PARENT_CHUNK_SIZE` | Parent chunk character size |
| `child_chunk_size` | `int` | `500` | `CHILD_CHUNK_SIZE` | Child chunk character size |
| `embed_batch_size` | `int` | `16` | `EMBED_BATCH_SIZE` | Embedding batch size |
| `embed_max_workers` | `int` | `4` | `EMBED_MAX_WORKERS` | ThreadPoolExecutor workers |
| `qdrant_upsert_batch_size` | `int` | `50` | `QDRANT_UPSERT_BATCH_SIZE` | Qdrant upsert batch size |

### Agent Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `max_iterations` | `int` | `10` | `MAX_ITERATIONS` | Max research graph iterations |
| `max_tool_calls` | `int` | `8` | `MAX_TOOL_CALLS` | Max tool calls per iteration |
| `confidence_threshold` | `int` | `60` | `CONFIDENCE_THRESHOLD` | **INTEGER 0–100 scale. Edge divides by 100 when comparing against float.** |
| `compression_threshold` | `float` | `0.75` | `COMPRESSION_THRESHOLD` | Message history compression trigger |
| `meta_reasoning_max_attempts` | `int` | `2` | `META_REASONING_MAX_ATTEMPTS` | Max meta-reasoning retries (Constitution II) |
| `meta_relevance_threshold` | `float` | `0.2` | `META_RELEVANCE_THRESHOLD` | Cross-encoder mean score threshold (spec-04) |
| `meta_variance_threshold` | `float` | `0.15` | `META_VARIANCE_THRESHOLD` | Score stdev threshold (spec-04) |

### Retrieval Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `hybrid_dense_weight` | `float` | `0.7` | `HYBRID_DENSE_WEIGHT` | Dense vector weight in hybrid search |
| `hybrid_sparse_weight` | `float` | `0.3` | `HYBRID_SPARSE_WEIGHT` | BM25 sparse weight in hybrid search |
| `top_k_retrieval` | `int` | `20` | `TOP_K_RETRIEVAL` | Candidates before reranking |
| `top_k_rerank` | `int` | `5` | `TOP_K_RERANK` | Final chunks after reranking |
| `reranker_model` | `str` | `"cross-encoder/ms-marco-MiniLM-L-6-v2"` | `RERANKER_MODEL` | Cross-encoder model name |

### Accuracy & Robustness Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `groundedness_check_enabled` | `bool` | `True` | `GROUNDEDNESS_CHECK_ENABLED` | Enable citation grounding check |
| `citation_alignment_threshold` | `float` | `0.3` | `CITATION_ALIGNMENT_THRESHOLD` | Min score for citation acceptance |
| `circuit_breaker_failure_threshold` | `int` | `5` | `CIRCUIT_BREAKER_FAILURE_THRESHOLD` | Consecutive failures to open CB |
| `circuit_breaker_cooldown_secs` | `int` | `30` | `CIRCUIT_BREAKER_COOLDOWN_SECS` | CB cooldown period |
| `retry_max_attempts` | `int` | `3` | `RETRY_MAX_ATTEMPTS` | Max retry attempts |
| `retry_backoff_initial_secs` | `float` | `1.0` | `RETRY_BACKOFF_INITIAL_SECS` | Initial retry backoff |

### Rate Limiting Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `rate_limit_chat_per_minute` | `int` | `30` | `RATE_LIMIT_CHAT_PER_MINUTE` | Chat endpoint rate limit |
| `rate_limit_ingest_per_minute` | `int` | `10` | `RATE_LIMIT_INGEST_PER_MINUTE` | Ingest endpoint rate limit |
| `rate_limit_provider_keys_per_minute` | `int` | `5` | `RATE_LIMIT_PROVIDER_KEYS_PER_MINUTE` | Provider key mgmt rate limit |
| `rate_limit_general_per_minute` | `int` | `120` | `RATE_LIMIT_GENERAL_PER_MINUTE` | Default rate limit |

### CORS Settings

| Field | Type | Default | Env Var | Description |
|-------|------|---------|---------|-------------|
| `cors_origins` | `str` | `"http://localhost:3000,http://127.0.0.1:3000"` | `CORS_ORIGINS` | Comma-separated allowed origins |

---

## Service Volume Map

| Volume Name | Mount Path | Content |
|------------|-----------|---------|
| `qdrant_data` | `/qdrant/storage` | Qdrant vector indices |
| `ollama_data` | `/root/.ollama` | Ollama model weights |
| `sqlite_data` | `/data/embedinator.db` | SQLite main database |
| `uploads_data` | `/data/uploads` | Temporary ingestion uploads |

---

## Docker Service Dependency Graph

```
frontend ──► backend ──► qdrant
                    └──► ollama
```

`depends_on: condition: service_healthy` enforces this ordering.

---

## Makefile Target Contract

14 required targets (FR-011):

| Target | Depends On | Side Effects |
|--------|-----------|--------------|
| `setup` | Python, Node, Rust | Installs all deps; safe to run multiple times |
| `build-rust` | Rust toolchain | Produces `ingestion-worker/target/release/embedinator-worker` |
| `dev-infra` | Docker | Starts Qdrant + Ollama containers |
| `dev-backend` | venv | Starts uvicorn with `--reload` |
| `dev-frontend` | node_modules | Starts `next dev` |
| `dev` | dev-infra | Starts dev-infra, then backend + frontend in parallel |
| `up` | Docker | Builds and starts all 4 production containers |
| `down` | Docker | Stops all containers |
| `pull-models` | Ollama running | Downloads `qwen2.5:7b` and `nomic-embed-text` |
| `test` | venv | Runs pytest without coverage enforcement |
| `test-cov` | venv | Runs pytest with `--cov-fail-under=80` (SC-006) |
| `test-frontend` | node_modules | Runs `vitest run` |
| `clean` | — | Removes `data/` directory contents |
| `clean-all` | Docker | Runs `down`, removes volumes, `data/`, build outputs |
