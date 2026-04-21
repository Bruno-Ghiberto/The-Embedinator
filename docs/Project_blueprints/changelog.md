# The Embedinator — Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Planned
- Comprehensive E2E test suite with Playwright (spec-23 design complete, implementation pending)
- Per-document-type chunk profiles (code vs prose)
- LRU cache for identical queries within session window
- Citation highlighting mapped to PDF page coordinates
- `/documents/[id]` page enhancements
- Google AI direct provider integration

---

## [0.3.0] — 2026-04-20 — Hardening & Performance

### Added

**CI/CD Pipeline (spec-27)**
- Reusable `_ci-core.yml` workflow gating all publish/release jobs
- Shape X 9-check required-status roster on `main` and `develop` (strict enforcement)
- Backend image signed with cosign v3.0.5 keyless (Fulcio + Rekor) at every publish
- SPDX SBOM attestation via syft + sigstore bundle verification
- Trivy image scanning (CRITICAL/HIGH block) + CodeQL Go analysis
- `ci-rust.yml` for Rust ingestion-worker CI (was unguarded since spec-06)
- `govulncheck` gate for Go TUI installer
- Pre-commit parity hook (`.pre-commit-config.yaml` enforced in CI)
- PR title lint (conventional commits), `codecov.yml` coverage targets

**Performance (spec-26)**
- Research-loop instrumentation: per-stage timing stored in `stage_timings_json` column
- `checkpoint_max_threads` cap: prunes oldest LangGraph checkpoints on startup (DISK-001 fix)
- `embed_max_workers` raised to 12 (CPU-002 audit — matches 20-thread host headroom)
- `circuit_breaker_cooldown_secs` raised to 60s (prevents aggressive lockout on single-user host)
- `groundedness_check_enabled` defaults to `false` (opt-in — saves 3–8s per turn)
- `default_llm_model` reverted to `qwen2.5:7b` (thinking models unsupported — see `docs/performance.md`)
- Warm factoid p50 latency: 30.6s → 19.5s (−36%); analytical: 33.5s → 16.0s (−52%)

**Frontend (spec-22)**
- Complete UI overhaul: dark-mode design system, shadcn/ui components, Tailwind v4 tokens
- Markdown rendering in chat (react-markdown + remark-gfm + rehype-highlight)
- `field-sizing-content` auto-resize textarea; removed legacy `ChatSidebar.tsx`, `CitationTooltip.tsx`

### Fixed

**Chat & Streaming (spec-24)**
- Graph stall bug: ResearchGraph fan-out no longer blocks on empty sub-questions
- Token-by-token streaming restored with LangGraph v2 + subgraph architecture
- Citation display: `CitationEvent` correctly serialized and rendered in UI

**Reliability (spec-21 / spec-25)**
- 22 confirmed bugs resolved: circuit-breaker false trips, checkpoint serialization errors,
  NDJSON framing on partial tool calls, BUG-007/008/015 session-continuity issues
- Ollama enforced Docker-only (no host-side fallback); health endpoint uses `/api/health/live`
- `_chat_semaphore(5)` cap prevents resource exhaustion under concurrent requests (BUG-015)

---

## [0.2.0] — 2026-03-20 — Full-Stack Feature Release

### Added

**Provider Architecture (spec-10)**
- Pluggable provider registry: Ollama, OpenRouter, OpenAI, Anthropic
- Fernet-encrypted API key storage (`EMBEDINATOR_FERNET_KEY` via `api_key_encryption_secret`)
- Provider health endpoint (`GET /api/providers/{name}/health`)

**Component Interfaces (spec-11)**
- Formal interface contracts for all major components (`backend/interfaces/`)
- Pytest contract tests introspecting signatures at CI time

**Error Handling (spec-12)**
- Custom error hierarchy in `backend/errors.py`: `EmbeddinatorError`, `CircuitOpenError`, etc.
- Structured `ErrorResponse` envelope on all API error paths (spec-12)

**Security Hardening (spec-13)**
- Input sanitization middleware: regex blocklist for prompt injection patterns
- Rate limiting refined: `rate_limit_provider_keys_per_minute = 5` (brute-force guard)
- CORS locked to configurable `cors_origins` list

**Performance Budgets (spec-14)**
- Stage-timing instrumentation across all agent nodes
- `stage_timings` field added to `query_traces` table via idempotent `ALTER TABLE`
- Budget-aware alerts logged when node exceeds configured thresholds

**Observability (spec-15)**
- `/observability` page: latency histogram, trace table, confidence distribution, health dashboard
- `GET /api/metrics` endpoint with per-bucket aggregates and circuit breaker snapshots
- structlog JSON renderer with trace ID propagation via `contextvars`

**Testing (spec-16)**
- 82 new tests: 56 unit + 15 E2E + 11 integration (total: 1487 passing, 87% coverage)
- `pytest.ini` with `--cov-fail-under=80`; `@pytest.mark.require_docker` for Qdrant tests
- `tests/conftest.py` with 4 shared fixtures; `tests/fixtures/` with sample PDF/MD/TXT

**Infrastructure (spec-17)**
- Multi-stage `Dockerfile.backend` with non-root user (`appuser`)
- `docker-compose.yml` with GPU overlay support (NVIDIA, AMD `rocm`, Intel `/dev/dri`)
- 14-target Makefile with `up`, `down`, `logs`, `test`, `build`, `lint` targets
- `.env.example` covering all 40+ configuration options

**UX/UI Redesign (spec-18)**
- shadcn/ui v4 component library replacing raw Tailwind components
- Dark-mode first design; zero hard-coded gray classes; `next-themes` provider
- Sidebar navigation, collection selector, model picker, settings page fully implemented

**Cross-Platform DX (spec-19)**
- `embedinator.sh` / `embedinator.ps1` branded launcher scripts
- GPU auto-detection with Ollama `rocm` image swap for AMD
- Next.js `rewrites()` replacing `NEXT_PUBLIC_API_URL` (browser uses relative paths)
- `--open` flag for explicit browser launch

**Open-Source Launch (spec-20)**
- Apache 2.0 license
- GitHub Actions CI (`ci.yml`, `docker-publish.yml`, `release.yml`) with quality gates
- pre-commit hooks: ruff, mypy, prettier, markdownlint
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`
- Repository visibility flipped public at `2026-03-20`; `v0.2.0` tag created

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
