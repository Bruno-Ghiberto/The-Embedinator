# The Embedinator — Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Planned — Phase 2
- Rust ingestion worker for high-performance PDF parsing
- MetaReasoningGraph (Layer 3) for retrieval failure recovery
- Grounded Answer Verification (GAV) with NLI-based claim checking
- Citation-Chunk Alignment validation via cross-encoder
- Computed confidence scoring (evidence-based)
- `/observability` page: latency histogram, trace table, confidence distribution, health dashboard
- Incremental ingestion with SHA256 hash-based change detection
- Parallel batch embedding with ThreadPoolExecutor

### Planned — Phase 3
- Additional direct providers: OpenAI, Anthropic, Google AI
- Per-document-type chunk profiles (code vs prose)
- LRU cache for identical queries within session window
- Citation highlighting mapped to PDF page coordinates
- `/documents/[id]` page enhancements
- Comprehensive E2E test suite with Playwright

---

## [0.1.0] — 2026-03-10 — Phase 1 MVP

### Added

**Backend**
- FastAPI application with app factory pattern and lifespan management
- Collection CRUD endpoints (`POST/GET/DELETE /api/collections`)
- Document upload with multipart file handling (`POST /api/collections/{id}/ingest`)
- Chat endpoint with NDJSON streaming (`POST /api/chat`)
- Provider management with Fernet-encrypted API key storage
- Health check endpoint aggregating Qdrant, Ollama, and SQLite status
- Trace recording for every query (SQLite `query_traces` table)
- Settings CRUD endpoint
- Model listing endpoint (LLM and embedding models)
- SQLite storage with WAL mode: collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers
- Qdrant client wrapper with collection CRUD and hybrid search support
- Provider registry with pluggable adapters: Ollama, OpenRouter, OpenAI, Anthropic
- Rate limiting middleware (sliding window: 10 uploads/min, 30 chat/min, 100 general/min)
- Request logging middleware with structured JSON output (structlog)
- Trace ID middleware for request correlation
- CORS configuration (configurable origins)
- Pydantic Settings centralized configuration (`backend/config.py`)
- Custom error hierarchy (`backend/errors.py`)

**Agent Architecture**
- Retrieval module: Qdrant search with collection filtering and top_k ranking
- Citation builder: document deduplication, text truncation, prompt formatting
- Confidence scorer: weighted average of passage relevance scores (0-100)
- Answer generator: streaming LLM wrapper with async iteration

**Ingestion Pipeline**
- PDF parsing via pypdf (Python-only, Rust worker deferred to Phase 2)
- Parent/child chunking (parent: 2000-4000 chars, child: ~500 chars)
- Breadcrumb prepending from document heading hierarchy
- Embedding via Ollama (nomic-embed-text default)
- Deterministic UUID5 point IDs for idempotent re-ingestion
- File validation: extension allowlist, size limits

**Frontend**
- Next.js 16 application with App Router and TypeScript
- Chat page with streaming response rendering
- Collection management page with create/delete
- Document upload with drag-drop (react-dropzone)
- Model selector component (LLM and embedding)
- Settings page stub
- Sidebar navigation
- Tailwind CSS styling

**Infrastructure**
- Docker Compose with 4 services: Qdrant, Ollama, backend, frontend
- Health checks using bash `/dev/tcp` (no curl dependency)
- Auto-pull of default LLM model (qwen2.5:7b) on first start
- Production compose override (`docker-compose.prod.yml`) with TLS proxy stubs
- `.env.example` with all configuration options documented

**Testing**
- 61 passing tests (unit + integration)
- Unit tests: retrieval, confidence, citations, answer generator
- Integration tests: app startup, US1 e2e flow, US3 streaming, US4 traces
- Test isolation: unique collection names via UUID suffix, monkeypatch for env vars
- In-memory SQLite fixtures for fast unit tests

---

*For detailed architecture, see `docs/architecture-design.md`. For API reference, see `docs/api-reference.md`.*
