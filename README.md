# The Embedinator

**Self-hosted agentic RAG system for private document intelligence.**

![CI](https://github.com/Bruno-Ghiberto/The-Embedinator/actions/workflows/ci.yml/badge.svg)
![Coverage](https://img.shields.io/badge/coverage-87%25-brightgreen)
![License](https://img.shields.io/badge/license-Apache%202.0-blue)
![Python](https://img.shields.io/badge/python-3.14%2B-blue)

---

## What Is This?

The Embedinator is a self-hosted retrieval-augmented generation (RAG) system
that turns your private documents into a conversational knowledge base. Upload
PDFs, Markdown, or plain text files, and the system ingests, chunks, embeds,
and indexes them so you can ask natural-language questions and receive grounded,
citation-backed answers.

Unlike simple "chat with your docs" tools, The Embedinator uses a **three-layer
agentic architecture** powered by LangGraph. A conversation layer manages
sessions and intent. A research layer performs multi-step retrieval with hybrid
search, reranking, and tool use. A meta-reasoning layer detects low-quality
results and applies recovery strategies. The result is higher accuracy,
transparent confidence scoring, and verifiable citations.

The entire stack runs locally: Python backend, Rust ingestion worker, Next.js
frontend, Qdrant vector database, and Ollama for local LLM inference. Cloud
providers (OpenAI, Anthropic, OpenRouter) are supported as optional
alternatives.


## Screenshots

![Chat Interface](docs/images/chat-light.png)

![Dark Mode](docs/images/chat-dark.png)

![Collections](docs/images/collections.png)

![Observability Dashboard](docs/images/observability.png)


## Why The Embedinator?

Most RAG tools do a single vector lookup and pass the results to an LLM. The Embedinator goes further:

- **3-layer agent architecture** — ConversationGraph manages sessions and intent, ResearchGraph performs multi-step retrieval with six tools, and MetaReasoningGraph detects failures and applies recovery strategies. This is not a single-shot pipeline; it is an iterative, self-correcting agent system.
- **Meta-reasoning recovery** — When initial retrieval produces poor results (low relevance, high variance, poor coverage), the system automatically tries alternative strategies: query reformulation, broader collection search, or question decomposition.
- **Grounded answer verification** — Every claim in the generated answer is checked against the retrieved evidence. Unsupported claims are marked `[unverified]` so you know exactly what is backed by your documents.
- **5-signal confidence scoring** — Confidence is computed from retrieval quality, reranker agreement, coverage breadth, coherence, and source diversity — not just raw similarity scores.
- **Hybrid search with cross-encoder reranking** — Dense vector search and BM25 sparse retrieval run in parallel via Qdrant, then a cross-encoder reranker re-orders the top results for precision.
- **Parent/child chunking with breadcrumbs** — Small child chunks are used for precise retrieval, while their parent chunks provide the LLM with broader document context. Structural breadcrumbs (heading hierarchy) are prepended so the model knows where each chunk lives in the original document.


## Key Features

- **3-layer agentic RAG** -- ConversationGraph, ResearchGraph, and MetaReasoningGraph orchestrated by LangGraph
- **Hybrid search** -- dense vector + BM25 sparse retrieval with Qdrant, followed by cross-encoder reranking
- **Parent/child chunking** -- small chunks for precise retrieval, parent chunks for rich LLM context
- **NDJSON streaming** -- real-time streamed answers with 10 event types (status, chunk, citation, confidence, and more)
- **Grounded answers** -- claim-level groundedness verification with citation alignment scoring
- **5-signal confidence scoring** -- composite score from retrieval quality, reranker agreement, coverage, coherence, and source diversity
- **Meta-reasoning recovery** -- automatic strategy switching (query rewrite, broader search, decomposition) when results are poor
- **Multi-provider LLM support** -- Ollama (local), OpenAI, Anthropic, and OpenRouter with encrypted API key storage
- **Rust ingestion worker** -- high-performance document parsing for PDF, Markdown, and plain text
- **Full observability** -- structured JSON logging, per-query traces, stage timing, latency charts, and a metrics dashboard
- **Rate limiting and security** -- per-endpoint rate limits, input sanitization, CORS, and circuit breakers


## Performance

See [docs/performance.md](docs/performance.md) for measured performance numbers on reference
hardware and behavior on weaker machines.

**Headline numbers (reference hardware, warm-state p50)**:
- Factoid query: 19,528 ms
- Analytical query: 15,963 ms
- Supported models: `qwen2.5:7b` (default), `llama3.1:8b`, `mistral:7b`

Thinking models (`gemma4`, `qwen3-thinking`, `deepseek-r1`) are not supported in the current
release — the backend refuses to start with them configured. See
[Supported Models](docs/performance.md#supported-models) for rationale.

> **Note**: GPU launch is required to reach the benchmark numbers above. Use `./embedinator.sh`
> (which auto-detects GPU and merges the correct Docker Compose overlay) rather than plain
> `docker compose up -d`.


## Architecture Overview

```
                        +-------------------+
                        |   Next.js 16 UI   |
                        |   (React 19)      |
                        +--------+----------+
                                 | NDJSON / REST
                                 v
                        +-------------------+
                        | FastAPI Backend    |
                        | (Python 3.14)     |
                        +--------+----------+
                                 |
              +------------------+------------------+
              |                  |                  |
   +----------v---+   +---------v------+   +-------v--------+
   | Layer 1       |   | Layer 2        |   | Layer 3         |
   | Conversation  |   | Research       |   | Meta-Reasoning  |
   | Graph         |-->| Graph          |-->| Graph           |
   | (session,     |   | (tools, hybrid |   | (strategy       |
   |  intent,      |   |  search,       |   |  recovery,      |
   |  history)     |   |  reranking)    |   |  retry logic)   |
   +---------------+   +-------+--------+   +-----------------+
                                |
                    +-----------+-----------+
                    |                       |
             +------v------+        +------v------+
             |   Qdrant    |        |   SQLite    |
             |  (vectors)  |        |  (metadata) |
             +-------------+        +-------------+
```

**Layer 1 -- ConversationGraph:** Manages sessions, classifies intent (RAG
query, clarification, collection management), rewrites queries, compresses
history, and formats final responses.

**Layer 2 -- ResearchGraph:** Executes multi-step research using six tools
(hybrid search, reranker, parent chunk lookup, sub-question decomposition,
broader search, focused search). Loops until confidence exceeds the threshold or
the iteration limit is reached.

**Layer 3 -- MetaReasoningGraph:** Activates when research produces low-quality
results. Analyzes failure signals (low relevance scores, high variance, poor
coverage) and applies recovery strategies such as query reformulation, broader
collection search, or question decomposition.


## Tech Stack

| Layer          | Technology                                           |
|----------------|------------------------------------------------------|
| Frontend       | Next.js 16, React 19, TypeScript 5.7, Tailwind CSS 4 |
| Backend        | Python 3.14, FastAPI, LangGraph, LangChain           |
| Ingestion      | Rust 1.93 (PDF, Markdown, plain text parsing)        |
| Vector DB      | Qdrant (dense + BM25 hybrid search)                  |
| Metadata DB    | SQLite (WAL mode)                                    |
| Local LLM      | Ollama (default: qwen2.5:7b)                         |
| Embeddings     | nomic-embed-text (via Ollama)                        |
| Reranking      | cross-encoder/ms-marco-MiniLM-L-6-v2                |
| Cloud providers| OpenAI, Anthropic, OpenRouter (optional)             |


## Quick Start

The only prerequisite is [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
# 1. Clone the repository
git clone https://github.com/Bruno-Ghiberto/The-Embedinator.git
cd The-Embedinator

# 2. Launch everything
./embedinator.sh          # macOS / Linux
# .\embedinator.ps1       # Windows (PowerShell)
```

The launcher script will:

1. Check that Docker is running
2. Generate a `.env` file with a Fernet encryption key (first run only)
3. Detect GPU availability (NVIDIA, AMD, Intel) and configure Docker accordingly
4. Build and start all four services (Qdrant, Ollama, backend, frontend)
5. Pull the default AI models (~4 GB on first run: qwen2.5:7b + nomic-embed-text)
6. Open the application in your browser at `http://localhost:3000`

The backend API is available at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.


## Development Setup

For contributors who want to work on individual components with hot reload.

**Prerequisites:** Python 3.14+, Node.js 22+, Docker, Git

```bash
# Install all dependencies (Python, Node, Rust)
make setup

# Start infrastructure (Qdrant + Ollama in Docker)
make dev-infra

# In separate terminals:
make dev-backend    # Python backend with hot reload on :8000
make dev-frontend   # Next.js frontend with hot reload on :3000
```

### Backend (Python)

```bash
# Create and activate a virtual environment
python3.14 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start infrastructure services
make dev-infra

# Run the backend with hot reload
make dev-backend
# Backend is available at http://localhost:8000
```

### Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
# Frontend is available at http://localhost:3000
```

### Rust Ingestion Worker

```bash
cd ingestion-worker
cargo build --release
# Binary output: target/release/embedinator-worker
```

The ingestion worker is a CLI binary invoked by the Python backend during
document processing. It reads a file path from its arguments and outputs
structured JSON chunks to stdout.


## Makefile Targets

| Target           | Description                                              |
|------------------|----------------------------------------------------------|
| `help`           | Show all available targets with descriptions              |
| `setup`          | Install Python, Node, and Rust dependencies               |
| `build-rust`     | Compile the Rust ingestion worker binary                  |
| `dev-infra`      | Start Qdrant + Ollama in Docker (infrastructure only)     |
| `dev-backend`    | Start Python backend with uvicorn hot reload              |
| `dev-frontend`   | Start Next.js frontend with hot reload                    |
| `dev`            | Start dev-infra, then print instructions for backend/frontend |
| `up`             | Build and start all 4 production Docker services          |
| `down`           | Stop all Docker services                                  |
| `pull-models`    | Pull default Ollama models (qwen2.5:7b + nomic-embed-text) |
| `test`           | Run backend tests without coverage threshold              |
| `test-cov`       | Run backend tests with 80% coverage gate                  |
| `test-frontend`  | Run frontend tests (vitest)                               |
| `clean`          | Remove runtime data (data/ directory)                     |
| `clean-all`      | Full teardown: stop containers, remove volumes and builds |


## Configuration

All configuration is managed through environment variables. Copy `.env.example`
to `.env` and adjust as needed. The file is organized into sections:

| Section          | Key variables                                          |
|------------------|--------------------------------------------------------|
| Server           | `HOST`, `PORT`, `LOG_LEVEL`, `DEBUG`                   |
| Qdrant           | `QDRANT_HOST`, `QDRANT_PORT`                           |
| Providers        | `DEFAULT_PROVIDER`, `DEFAULT_LLM_MODEL`, `OLLAMA_BASE_URL` |
| Encryption       | `EMBEDINATOR_FERNET_KEY` (required for cloud providers) |
| SQLite           | `SQLITE_PATH`                                          |
| Ingestion        | `RUST_WORKER_PATH`, `UPLOAD_DIR`, `MAX_UPLOAD_SIZE_MB` |
| Agent            | `MAX_ITERATIONS`, `CONFIDENCE_THRESHOLD`, `COMPRESSION_THRESHOLD` |
| Retrieval        | `HYBRID_DENSE_WEIGHT`, `TOP_K_RETRIEVAL`, `TOP_K_RERANK` |
| Rate limiting    | `RATE_LIMIT_CHAT_PER_MINUTE`, `RATE_LIMIT_INGEST_PER_MINUTE` |
| CORS             | `CORS_ORIGINS`                                         |

See [`.env.example`](.env.example) for the complete reference with defaults and
descriptions for every variable.

To enable cloud LLM providers, generate a Fernet key and set
`EMBEDINATOR_FERNET_KEY`:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```


## API Endpoints

All endpoints are prefixed with `/api`. The backend serves interactive API
documentation at `/docs` (Swagger UI) and `/redoc`.

### Chat

| Method | Path          | Description                              |
|--------|---------------|------------------------------------------|
| POST   | `/api/chat`   | Stream an answer as NDJSON events        |

### Collections

| Method | Path                          | Description                  |
|--------|-------------------------------|------------------------------|
| GET    | `/api/collections`            | List all collections         |
| POST   | `/api/collections`            | Create a new collection      |
| DELETE | `/api/collections/{id}`       | Delete a collection          |

### Documents

| Method | Path                     | Description                     |
|--------|--------------------------|---------------------------------|
| GET    | `/api/documents`         | List documents (with filters)   |
| GET    | `/api/documents/{id}`    | Get a single document           |
| DELETE | `/api/documents/{id}`    | Delete a document               |

### Ingestion

| Method | Path                                        | Description                  |
|--------|---------------------------------------------|------------------------------|
| POST   | `/api/collections/{id}/ingest`              | Upload a file for ingestion  |
| GET    | `/api/collections/{id}/ingest/{job_id}`     | Check ingestion job status   |

### Observability

| Method | Path                   | Description                          |
|--------|------------------------|--------------------------------------|
| GET    | `/api/traces`          | List query traces                    |
| GET    | `/api/traces/{id}`     | Get detailed trace with stage timings|
| GET    | `/api/stats`           | System-wide statistics               |
| GET    | `/api/metrics`         | Time-series metrics for dashboards   |
| GET    | `/api/health`          | Health check (SQLite, Qdrant, Ollama)|

### Providers

| Method | Path                          | Description                      |
|--------|-------------------------------|----------------------------------|
| GET    | `/api/providers`              | List configured LLM providers    |
| PUT    | `/api/providers/{name}/key`   | Save an encrypted API key        |
| GET    | `/api/providers/health`       | Check provider connectivity      |
| DELETE | `/api/providers/{name}/key`   | Remove a provider API key        |

### Models

| Method | Path                 | Description                           |
|--------|----------------------|---------------------------------------|
| GET    | `/api/models/llm`    | List available LLM models             |
| GET    | `/api/models/embed`  | List available embedding models       |

### Settings

| Method | Path              | Description                              |
|--------|-------------------|------------------------------------------|
| GET    | `/api/settings`   | Read current application settings        |
| PUT    | `/api/settings`   | Update application settings at runtime   |


## Project Structure

```
The-Embedinator/
|-- backend/                    # Python backend (FastAPI + LangGraph)
|   |-- agent/                  # 3-layer LangGraph agent system
|   |   |-- conversation_graph.py  # Layer 1: session & intent management
|   |   |-- research_graph.py      # Layer 2: multi-step research
|   |   |-- meta_reasoning_graph.py # Layer 3: strategy recovery
|   |   |-- nodes.py               # 17 conversation node functions
|   |   |-- research_nodes.py      # 6 research node functions
|   |   |-- meta_reasoning_nodes.py # meta-reasoning node functions
|   |   |-- edges.py               # conversation edge routing
|   |   |-- research_edges.py      # research edge routing
|   |   |-- meta_reasoning_edges.py # meta-reasoning edge routing
|   |   |-- state.py               # TypedDict state definitions
|   |   |-- schemas.py             # Pydantic request/response models
|   |   |-- tools.py               # 6 research tools (closure factory)
|   |   |-- confidence.py          # 5-signal confidence scoring
|   |   |-- prompts.py             # Prompt templates for all nodes
|   |   |-- citations.py           # Citation extraction and validation
|   |   |-- answer_generator.py    # Final answer formatting
|   |   +-- retrieval.py           # Retrieval orchestration
|   |-- api/                    # FastAPI route handlers
|   |   |-- chat.py                # NDJSON streaming endpoint
|   |   |-- collections.py        # Collection CRUD
|   |   |-- documents.py          # Document CRUD
|   |   |-- ingest.py             # File upload + ingestion jobs
|   |   |-- traces.py             # Query traces + stats + metrics
|   |   |-- providers.py          # LLM provider key management
|   |   |-- models.py             # Model listing (LLM + embedding)
|   |   |-- settings.py           # Runtime settings
|   |   +-- health.py             # Service health probes
|   |-- storage/                # Data persistence layer
|   |   |-- sqlite_db.py          # SQLite async wrapper (40+ methods)
|   |   |-- qdrant_client.py      # Qdrant wrapper + QdrantStorage
|   |   |-- parent_store.py       # Parent chunk reader
|   |   |-- chunker.py            # Text chunking logic
|   |   |-- document_parser.py    # Document format detection
|   |   +-- indexing.py           # Collection indexing
|   |-- providers/              # Pluggable LLM provider system
|   |   |-- registry.py           # Provider registry + model resolution
|   |   |-- base.py               # Abstract provider interface
|   |   |-- ollama.py             # Ollama adapter
|   |   |-- openai.py             # OpenAI adapter
|   |   |-- anthropic.py          # Anthropic adapter
|   |   |-- openrouter.py         # OpenRouter adapter
|   |   +-- key_manager.py        # Fernet-encrypted key storage
|   |-- retrieval/              # Search and ranking
|   |   |-- searcher.py           # HybridSearcher (dense + BM25)
|   |   |-- reranker.py           # Cross-encoder reranking
|   |   +-- score_normalizer.py   # Per-collection score normalization
|   |-- ingestion/              # Document processing pipeline
|   |   |-- pipeline.py           # IngestionPipeline orchestrator
|   |   |-- embedder.py           # Embedding generation
|   |   |-- chunker.py            # Ingestion-specific chunking
|   |   +-- incremental.py        # Deduplication logic
|   |-- main.py                 # App factory + lifespan management
|   |-- config.py               # Pydantic Settings (all env vars)
|   |-- errors.py               # Custom exception hierarchy
|   +-- middleware.py           # Rate limiting, logging, trace IDs
|-- frontend/                   # Next.js 16 frontend
|   |-- app/                    # App Router pages
|   |   |-- chat/                  # Chat interface
|   |   |-- collections/           # Collection management
|   |   |-- documents/             # Document browser
|   |   |-- settings/              # Application settings
|   |   +-- observability/         # Traces, metrics, health dashboard
|   |-- components/             # Application components
|   |   |-- ui/                    # shadcn/ui primitives (20+ components)
|   |   |-- ChatPanel.tsx          # Chat message rendering
|   |   |-- CollectionCard.tsx     # Collection card display
|   |   |-- DocumentUploader.tsx   # Drag-and-drop upload
|   |   |-- ProviderHub.tsx        # LLM provider management
|   |   |-- CommandPalette.tsx     # Cmd+K command palette
|   |   |-- ThemeToggle.tsx        # Dark/light mode toggle
|   |   +-- SidebarLayout.tsx      # Collapsible sidebar navigation
|   |-- hooks/                  # Custom React hooks (SWR-based)
|   |   |-- useStreamChat.ts       # Streaming chat hook
|   |   |-- useCollections.ts      # Collection data fetching
|   |   |-- useTraces.ts           # Trace data fetching
|   |   +-- useMetrics.ts          # Metrics data fetching
|   +-- lib/                    # API client + shared types
|-- ingestion-worker/           # Rust document parser
|   +-- src/
|       |-- main.rs                # CLI entry point
|       |-- pdf.rs                 # PDF extraction
|       |-- markdown.rs            # Markdown parsing (pulldown-cmark)
|       |-- text.rs                # Plain text handling
|       |-- heading_tracker.rs     # Heading/breadcrumb extraction
|       |-- code.rs                # Code block handling
|       +-- types.rs               # Shared type definitions
|-- tests/                      # Test suite (1487 tests, 87% coverage)
|   |-- unit/                   # Unit tests (~60 files)
|   |-- integration/            # Integration tests (~20 files)
|   |-- e2e/                    # End-to-end tests (4 files)
|   |-- regression/             # Regression test suite
|   +-- fixtures/               # Sample PDF, Markdown, text files
|-- docs/                       # Project documentation
|   |-- adr/                       # 8 Architecture Decision Records
|   |-- architecture-design.md     # System architecture overview
|   |-- api-reference.md           # API endpoint documentation
|   |-- data-model.md              # Database schema reference
|   |-- security-model.md          # Security architecture
|   |-- performance-budget.md      # Performance targets
|   |-- testing-strategy.md        # Testing approach and coverage
|   +-- runbook.md                 # Operations runbook
|-- .github/                    # GitHub configuration
|   |-- workflows/                 # CI, release, security workflows
|   |-- ISSUE_TEMPLATE/            # Bug report and feature request forms
|   +-- PULL_REQUEST_TEMPLATE.md   # PR template
|-- scripts/                    # Development and test scripts
|-- specs/                      # Feature specifications (001-019)
|-- docker-compose.yml          # Production: 4 services
|-- docker-compose.dev.yml      # Development overrides
|-- docker-compose.prod.yml     # Production overrides
|-- Dockerfile.backend          # Multi-stage: Rust build + Python runtime
|-- Makefile                    # 15 development targets
|-- embedinator.sh              # Cross-platform launcher (macOS/Linux)
|-- embedinator.ps1             # Cross-platform launcher (Windows)
|-- requirements.txt            # Python dependencies
|-- .env.example                # Environment variable reference
+-- pytest.ini                  # Test configuration
```


## Testing

The project has **1,487 tests** across unit, integration, E2E, and regression
suites with **87% code coverage**.

### Backend Tests (pytest)

```bash
# Run all backend tests (no coverage gate)
make test

# Run with 80% coverage threshold
make test-cov

# Run specific test files directly
pytest tests/unit/test_config.py
pytest tests/integration/ -v
pytest tests/e2e/ -v
```

### Frontend Tests (vitest)

```bash
make test-frontend
# Or directly:
cd frontend && npm run test
```

### Test Markers

```ini
# pytest.ini markers:
e2e          # Backend E2E tests (in-process ASGI via httpx)
require_docker  # Tests requiring Qdrant on localhost:6333
```


## Specifications

The project is built from 19 detailed specifications covering every subsystem.
Each spec lives in [`specs/`](specs/) and includes user stories,
functional requirements, success criteria, and implementation tasks.

| Spec | Name                    | Status     |
|------|-------------------------|------------|
| 001  | Vision & Architecture   | Complete   |
| 002  | Conversation Graph      | Complete   |
| 003  | Research Graph          | Complete   |
| 004  | Meta-Reasoning          | Complete   |
| 005  | Accuracy & Robustness   | Complete   |
| 006  | Ingestion Pipeline      | Complete   |
| 007  | Storage Architecture    | Complete   |
| 008  | API Reference           | Complete   |
| 009  | Next.js Frontend        | Complete   |
| 010  | Provider Architecture   | Complete   |
| 011  | Component Interfaces    | Complete   |
| 012  | Error Handling          | Complete   |
| 013  | Security Hardening      | Complete   |
| 014  | Performance Budgets     | Complete   |
| 015  | Observability           | Complete   |
| 016  | Testing Strategy        | Complete   |
| 017  | Infrastructure Setup    | Complete   |
| 018  | UX/UI Redesign          | Complete   |
| 019  | Cross-Platform DX       | Complete   |


## Docker Services

The `docker-compose.yml` defines four services:

| Service    | Image                  | Port  | Purpose                        |
|------------|------------------------|-------|--------------------------------|
| `qdrant`   | qdrant/qdrant:latest   | 6333  | Vector database                |
| `ollama`   | ollama/ollama:latest   | 11434 | Local LLM inference            |
| `backend`  | Custom (Dockerfile.backend) | 8000 | FastAPI application        |
| `frontend` | Custom (frontend/Dockerfile) | 3000 | Next.js web interface     |

The backend Dockerfile uses a multi-stage build: stage 1 compiles the Rust
ingestion worker, stage 2 sets up the Python runtime with the compiled binary
and runs as a non-root user.


## License

This project is licensed under the [Apache License 2.0](LICENSE).


## Contributing

Contributions are welcome! Please read the [Contributing Guide](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md) before submitting a pull request.

<!-- spec-27 Gate 2 smoke test marker: 2026-04-17T22:44:26Z -->

