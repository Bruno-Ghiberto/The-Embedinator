# Spec 17: Infrastructure -- Feature Specification Context

## Feature Description

The Infrastructure specification covers the full project directory structure, Docker strategy (full deployment and dev mode), multi-stage Dockerfiles (backend: Rust-to-Python, frontend: Next.js standalone), docker-compose files, Makefile automation targets, .env configuration, the Pydantic Settings class, and all dependency versions across Python, Rust, and JavaScript. This is the foundational spec that defines how the project is built, configured, run, and deployed.

## Requirements

### Functional Requirements

1. **Two Docker Modes**: "Full Docker" (`docker compose up`) containerizes all services (Qdrant, Ollama, backend, frontend). "Dev mode" (`make dev`) runs only Qdrant and Ollama in Docker while backend and frontend run natively with hot reload.
2. **Multi-Stage Backend Dockerfile**: Stage 1 compiles the Rust ingestion worker binary. Stage 2 builds the Python runtime with the compiled binary copied in.
3. **Multi-Stage Frontend Dockerfile**: Stage 1 builds the Next.js app. Stage 2 runs the standalone production server.
4. **Makefile Automation**: Targets for setup, build-rust, dev-infra, dev-backend, dev-frontend, dev, up, down, pull-models, test, test-cov, test-frontend, clean, clean-all.
5. **Pydantic Settings Class**: Central configuration in `backend/config.py` using `pydantic-settings` with `.env` file support and typed defaults for all settings.
6. **Environment Configuration**: `.env.example` template with all configuration variables grouped by category.
7. **GPU Passthrough**: Docker Compose supports NVIDIA GPU passthrough for Ollama.
8. **Health Checks**: All Docker services have health check configurations for dependency ordering.
9. **Volume Management**: Persistent volumes for Qdrant data, Ollama models, SQLite database, and file uploads.

### Non-Functional Requirements

- Dev mode must not require Docker rebuilds on code changes.
- Full Docker deployment must work with a single `docker compose up --build` command.
- The Makefile must be self-documenting (target names are descriptive).
- The `.env.example` must contain all variables with sensible defaults and comments.
- Docker images should use layer caching effectively (dependencies before source code).

## Key Technical Details

### Full Project Directory Structure

```
the-embedinator/
  backend/
    api/
      collections.py       # Collection CRUD endpoints
      chat.py              # Chat endpoint + SSE streaming
      models.py            # Ollama model listing proxy
      settings.py          # Settings CRUD
      providers.py         # Provider management endpoints
      traces.py            # Query trace log + health + stats
    agent/
      conversation_graph.py    # Layer 1: ConversationGraph definition
      research_graph.py        # Layer 2: ResearchGraph definition
      meta_reasoning_graph.py  # Layer 3: MetaReasoningGraph definition
      nodes.py                 # All node functions (stateless, pure)
      edges.py                 # All conditional edge functions
      tools.py                 # LangChain tool definitions + implementations
      prompts.py               # All system and user prompts as constants
      schemas.py               # Pydantic models: QueryAnalysis, SubAnswer, Citation
      state.py                 # TypedDict state schemas for all three graphs
    ingestion/
      pipeline.py          # Orchestrator: spawn Rust worker, coordinate flow
      embedder.py          # Ollama embedding calls, ThreadPoolExecutor batching
      chunker.py           # Parent/child splitting, breadcrumb prepending
      incremental.py       # SHA256 hash check, change detection
    retrieval/
      searcher.py          # Qdrant hybrid search execution
      reranker.py          # Cross-encoder reranking (sentence-transformers)
      router.py            # Regex-based collection routing
      score_normalizer.py  # Per-collection min-max normalization before merge
    storage/
      qdrant_client.py     # Qdrant connection, collection init, upsert, search
      sqlite_db.py         # SQLite connection, all table operations
      parent_store.py      # Parent chunk read/write (SQLite-backed)
    providers/
      base.py             # LLMProvider ABC, EmbeddingProvider ABC
      registry.py         # ProviderRegistry: model name -> provider resolution
      ollama.py           # OllamaProvider (default, no key needed)
      openrouter.py       # OpenRouterProvider (200+ models, one key)
      openai.py           # OpenAIProvider (direct)
      anthropic.py        # AnthropicProvider (direct)
      key_manager.py      # Fernet encryption/decryption for API keys
    errors.py              # Error hierarchy (all custom exceptions)
    config.py              # Pydantic Settings: all env vars, defaults
    main.py                # FastAPI app factory, router registration, lifespan
    middleware.py          # CORS, rate limiting, trace ID injection
  ingestion-worker/
    src/
      main.rs              # CLI entry point, dispatch to parsers
      pdf.rs               # PDF extraction
      markdown.rs          # Markdown parsing and splitting
      text.rs              # Plain text chunking
      heading_tracker.rs   # Heading hierarchy state machine
      types.rs             # Chunk struct, DocType enum, serde impls
    Cargo.toml
  frontend/
    app/
      layout.tsx
      chat/
        page.tsx
      collections/
        page.tsx
      documents/
        [id]/page.tsx
      settings/
        page.tsx
      observability/
        page.tsx
    components/
      ChatPanel.tsx
      ChatInput.tsx
      ChatSidebar.tsx
      CollectionCard.tsx
      CollectionList.tsx
      CreateCollectionDialog.tsx
      DocumentUploader.tsx
      DocumentList.tsx
      ModelSelector.tsx
      CitationTooltip.tsx
      ConfidenceIndicator.tsx
      ProviderHub.tsx
      TraceTable.tsx
      LatencyChart.tsx
      ConfidenceDistribution.tsx
      HealthDashboard.tsx
      CollectionStats.tsx
      Navigation.tsx
    lib/
      api.ts               # Centralized API client
      types.ts             # Shared TypeScript interfaces
    hooks/
      useStreamChat.ts     # Custom hook for SSE chat streaming
      useCollections.ts    # SWR hook for collections
      useModels.ts         # SWR hook for model lists
      useTraces.ts         # SWR hook for traces
    next.config.ts
    package.json
    tailwind.config.ts
    tsconfig.json
  tests/                   # See Spec 16 (Testing)
  data/                    # gitignored -- runtime data
    uploads/               # temporary file storage during ingestion
    qdrant_db/             # Qdrant persistence volume
    embedinator.db         # SQLite database file
  docker-compose.yml
  docker-compose.dev.yml
  .env.example
  Makefile
  requirements.txt         # Python dependencies
  README.md
```

### Pydantic Settings Class

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
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

### All Dependency Versions

**Python 3.14:**

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | `>=0.135` | API framework |
| `uvicorn` | `>=0.34` | ASGI server |
| `langgraph` | `>=1.0.10` | Agent graph orchestration |
| `langchain` | `>=1.2.10` | LLM abstraction, tool binding |
| `langchain-community` | `>=1.2` | Ollama integration |
| `langchain-openai` | `>=1.1.10` | OpenAI / OpenRouter integration |
| `langchain-anthropic` | `>=0.3` | Anthropic integration |
| `qdrant-client` | `>=1.17.0` | Qdrant vector database client |
| `sentence-transformers` | `>=5.2.3` | Cross-encoder reranking + embeddings |
| `pydantic` | `>=2.12` | Settings, structured output schemas |
| `pydantic-settings` | `>=2.8` | Environment variable configuration |
| `aiosqlite` | `>=0.21` | Async SQLite access |
| `httpx` | `>=0.28` | Async HTTP (Ollama/provider API calls) |
| `python-multipart` | `>=0.0.20` | File upload parsing |
| `tiktoken` | `>=0.12` | Token counting |
| `tenacity` | `>=9.0` | Retry with exponential backoff + circuit breaker |
| `cryptography` | `>=44.0` | Fernet encryption for stored API keys |
| `structlog` | `>=24.0` | Structured JSON logging |

**Rust 1.93:**

| Crate | Version | Purpose |
|-------|---------|---------|
| `serde` | `1` | Serialization framework |
| `serde_json` | `1` | JSON + NDJSON output |
| `pulldown-cmark` | `0.12` | Markdown parsing |
| `pdf-extract` | `0.8` | PDF text extraction |
| `clap` | `4` | CLI argument parsing |
| `regex` | `1` | Text boundary detection |

**JavaScript / Node.js:**

| Package | Version | Purpose |
|---------|---------|---------|
| `next` | `16` | React framework, App Router, Turbopack |
| `react` | `19` | UI component library |
| `typescript` | `5.7` | Type safety |
| `tailwindcss` | `4` | Utility-first CSS |
| `recharts` | `2` | Latency charts on observability page |
| `@radix-ui/react-tooltip` | `1` | Citation tooltip primitives |
| `@radix-ui/react-dialog` | `1` | Modal dialogs |
| `@radix-ui/react-select` | `2` | Dropdown selects |
| `swr` | `2` | Data fetching with cache for API calls |
| `react-dropzone` | `14` | File drag-drop upload |

**Infrastructure:**

| Service | Version | Purpose |
|---------|---------|---------|
| `qdrant/qdrant` (Docker) | `latest` | Vector database |
| `ollama/ollama` (Docker) | `latest` | LLM and embedding inference |
| SQLite | `3.45+` | Metadata and parent chunk storage |

**Dev/Test:**

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=8.0` | Test runner |
| `pytest-asyncio` | `>=0.24` | Async test support |
| `pytest-cov` | `>=6.0` | Coverage reporting |
| `httpx` | `>=0.28` | Test HTTP client |
| `vitest` | `>=3.0` | Frontend unit tests |
| `@playwright/test` | `>=1.50` | Frontend E2E tests |
| `@testing-library/react` | `>=16.0` | Component testing |

## Dependencies

- **External**: Docker Engine 24+, Docker Compose v2, Node.js 22+, Python 3.14, Rust 1.93, NVIDIA Container Toolkit (for GPU passthrough)
- **Other specs**: All specs depend on this infrastructure spec for project structure, configuration, and build tooling.

## Acceptance Criteria

1. `docker compose up --build` starts all four services (Qdrant, Ollama, backend, frontend) and they become healthy.
2. `make dev` starts Qdrant and Ollama in Docker. `make dev-backend` and `make dev-frontend` run natively with hot reload.
3. `make setup` installs Python dependencies, npm packages, and compiles the Rust worker.
4. `make build-rust` compiles the ingestion worker binary.
5. `make clean` removes runtime data without affecting Docker volumes or model downloads.
6. `make clean-all` stops containers, removes runtime data, and deletes Ollama model volume.
7. `make pull-models` downloads the default LLM and embedding models to Ollama.
8. `make test`, `make test-cov`, and `make test-frontend` execute their respective test suites.
9. The `.env.example` file documents all configuration variables with defaults and comments.
10. `backend/config.py` Settings class validates and loads all environment variables with correct types and defaults.
11. The backend Dockerfile successfully compiles the Rust worker in Stage 1 and runs uvicorn in Stage 2.
12. The frontend Dockerfile builds with `output: 'standalone'` and runs `node server.js`.
13. Docker service health checks work: backend waits for healthy Qdrant and Ollama before starting.
14. NVIDIA GPU passthrough works for the Ollama container (on systems with NVIDIA GPU).
15. The `data/` directory is gitignored and created automatically at runtime.

## Architecture Reference

### Build Phases Roadmap

- **Phase 1 (MVP)**: Full project structure, docker-compose files, Makefile, .env configuration, requirements.txt, Python backend with FastAPI, Next.js frontend, Qdrant + Ollama in Docker.
- **Phase 2 (Performance and Resilience)**: Rust ingestion worker binary, multi-stage backend Dockerfile, structured logging configuration.
- **Phase 3 (Ecosystem and Polish)**: Docker Compose optimized for production-style deployment with volume mounts and restart policies, comprehensive test suite integration.

### Key Design Decisions

- **SQLite over PostgreSQL**: Single-file database for simplicity. WAL mode for concurrent reads.
- **Rust for PDF parsing**: 5-20x throughput improvement. NDJSON streaming interface for overlapping parsing and embedding.
- **Dev mode separation**: Infrastructure in Docker, application code native, for fast iteration without rebuilds.
