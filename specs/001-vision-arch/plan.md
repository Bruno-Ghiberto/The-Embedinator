# Implementation Plan: Vision & System Architecture

**Branch**: `001-vision-arch` | **Date**: 2026-03-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-vision-arch/spec.md`

---

## Summary

The Embedinator is a self-hosted agentic RAG system that lets users privately embed, index, and intelligently query their own documents via a browser UI — with zero mandatory cloud dependencies. The technical approach is a three-layer LangGraph agent (ConversationGraph → ResearchGraph → MetaReasoningGraph) backed by hybrid dense+BM25 Qdrant retrieval with cross-encoder reranking, parent/child chunking with breadcrumbs, NDJSON streaming chat, Fernet-encrypted provider key storage, and a single `docker compose up` deployment.

**Phase 1 MVP status**: COMPLETE — 75/75 tasks done, 61 tests passing, Docker stack validated. This plan documents the settled design, serves as the canonical architecture reference for Phase 2+, and provides the contract and data-model artifacts required by speckit.tasks.

---

## Technical Context

**Language/Version**: Python 3.14+, TypeScript 5.7, Rust 1.93.1 (Phase 2 ingestion worker)
**Primary Dependencies**: FastAPI >= 0.135, LangGraph >= 1.0.10, LangChain >= 1.2.10, Qdrant Client >= 1.17.0, sentence-transformers >= 5.2.3, Pydantic v2 >= 2.12, aiosqlite >= 0.21, cryptography (Fernet) >= 44.0, structlog >= 24.0, tenacity >= 9.0 | Next.js 16, React 19, Tailwind CSS 4, SWR 2, recharts 2
**Storage**: SQLite WAL mode (`data/embedinator.db`) — metadata, parent chunks, traces, provider keys; Qdrant (`data/qdrant_db/`) — dense vectors + BM25
**Testing**: pytest + pytest-asyncio + pytest-cov (backend unit + integration); vitest + @testing-library/react (frontend unit); Playwright (E2E, Phase 3)
**Target Platform**: Linux server (Docker Compose), browser client (any modern browser on local network)
**Project Type**: Web service with React SPA frontend + Python AI backend + embedded vector + relational DBs
**Performance Goals**: First token < 500ms; simple query < 5s; complex query < 15s; ingestion >= 10 pages/sec (Python), >= 50 pages/sec (Rust, Phase 2); Qdrant search < 100ms at 100K vectors
**Constraints**: Zero outbound network calls in default Ollama configuration; no user authentication (trusted local network); 100 MB file upload limit; SQLite single-writer (WAL concurrency for reads); 1–5 concurrent users
**Scale/Scope**: Up to 100 collections, up to 10,000 documents/collection, up to 10M total vectors

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Source: `PROMPTS/speckit-constitution-context.md`

| Gate | Requirement | Status |
|---|---|---|
| C-01 | Zero mandatory cloud dependencies — Ollama is default, cloud is opt-in | ✅ PASS — Ollama default; OpenRouter/OpenAI/Anthropic opt-in via settings UI |
| C-02 | Three-layer LangGraph agent scaffold preserved | ✅ PASS — ConversationGraph + ResearchGraph in Phase 1; MetaReasoningGraph scaffold present, activated Phase 2 |
| C-03 | SQLite WAL mode — no PostgreSQL or additional DB service | ✅ PASS — SQLite WAL via aiosqlite; no 5th container |
| C-04 | Parent/child chunking with breadcrumbs | ✅ PASS — child ~500 chars in Qdrant; parent 2000-4000 chars in SQLite; breadcrumb prepended before embedding |
| C-05 | Cross-encoder reranking on top-20 candidates | ✅ PASS — ms-marco-MiniLM-L-6-v2; applied post-hybrid-retrieval |
| C-06 | Fernet encryption for all API keys at rest | ✅ PASS — `cryptography` Fernet; key from `EMBEDINATOR_FERNET_KEY` env var |
| C-07 | NDJSON streaming chat (`application/x-ndjson`) | ✅ PASS — `{"type":"chunk","text":"..."}` + `{"type":"metadata",...}` final frame |
| C-08 | Query trace recorded for every query | ✅ PASS — QueryTrace written to SQLite on every chat request |
| C-09 | Single `docker compose up` deployment | ✅ PASS — 4 services (Qdrant, Ollama, backend, frontend) with health-check ordering |
| C-10 | Backend test coverage >= 80%, frontend >= 70% | ✅ PASS — 61 tests passing; coverage targets enforced via pytest-cov |
| C-11 | No authentication on web interface | ✅ PASS — trusted local network by design; spec clarification confirmed |
| C-12 | API keys never logged or returned in API responses | ✅ PASS — structlog processors strip sensitive fields; provider endpoints return status only |

**Gate result**: ALL PASS — no violations, no Complexity Tracking entries required.

---

## Project Structure

### Documentation (this feature)

```text
specs/001-vision-arch/
├── plan.md              # This file
├── research.md          # Phase 0: settled decisions + rationale
├── data-model.md        # Phase 1: entity model + SQLite + Qdrant schemas
├── quickstart.md        # Phase 1: developer onboarding
├── contracts/
│   ├── rest-api.md      # Phase 1: REST endpoint contracts
│   └── streaming.md     # Phase 1: NDJSON streaming contract
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── main.py               # App factory (create_app) + lifespan context manager
├── config.py             # Pydantic Settings — all env vars
├── errors.py             # Custom error hierarchy
├── middleware.py         # Rate limiting, structlog, trace ID injection
├── api/
│   ├── chat.py           # POST /api/chat (NDJSON streaming)
│   ├── collections.py    # CRUD /api/collections
│   ├── documents.py      # Upload/delete /api/documents
│   ├── health.py         # GET /api/health
│   ├── providers.py      # Provider Hub CRUD + key management
│   └── traces.py         # GET /api/traces
├── agent/
│   ├── state.py          # LangGraph state definitions
│   ├── schemas.py        # Pydantic models for agent I/O
│   ├── prompts.py        # System + user prompt templates
│   ├── retrieval.py      # Hybrid search + parent-chunk fetch
│   ├── citations.py      # Citation construction + dedup
│   ├── confidence.py     # Evidence-based confidence computation
│   └── answer_generator.py  # LLM streaming answer node
├── storage/
│   ├── sqlite_db.py      # SQLiteDB client (aiosqlite, WAL)
│   ├── qdrant_client.py  # QdrantStorage client (hybrid search, circuit breaker)
│   ├── chunker.py        # Parent/child chunking + breadcrumbs
│   ├── document_parser.py # PDF/MD/TXT text extraction
│   └── indexing.py       # Ingestion pipeline orchestration
└── providers/
    ├── base.py           # LLMProvider ABC
    ├── registry.py       # Provider registry (resolve model → instance)
    ├── ollama.py         # Ollama adapter
    ├── openrouter.py     # OpenRouter adapter
    ├── openai.py         # OpenAI adapter
    └── anthropic.py      # Anthropic adapter

frontend/
└── src/
    ├── api/              # Typed API client (fetch wrappers)
    ├── components/       # React components (ChatWindow, CollectionCard, etc.)
    ├── hooks/            # useStreamChat and other custom hooks
    ├── pages/            # Next.js Pages Router (/chat, /collections, /settings, /observability)
    ├── styles/           # Tailwind global styles
    └── types/            # Shared TypeScript types

tests/
├── unit/                 # Fast, mocked — no Docker required
└── integration/          # Real services — requires Docker (Qdrant + Ollama)

data/                     # Runtime data — gitignored
├── embedinator.db        # SQLite WAL database
└── qdrant_db/            # Qdrant persistence volume
```

**Structure Decision**: Web application layout (Option 2 pattern). Python backend is flat module layout (not `src/`); frontend uses Next.js Pages Router under `frontend/src/`. No separate `ingestion/` package — ingestion modules live in `backend/storage/` alongside the storage clients they depend on.

---

## Complexity Tracking

> No constitution violations — section not applicable.

---

## Phase 0: Research

See [research.md](research.md) — all NEEDS CLARIFICATION items resolved via 8 accepted ADRs and completed Phase 1 implementation.

---

## Phase 1: Design

### Data Model

See [data-model.md](data-model.md) — 6 core SQLite entities + Qdrant point schema.

### API Contracts

See [contracts/rest-api.md](contracts/rest-api.md) — all REST endpoints with request/response shapes.
See [contracts/streaming.md](contracts/streaming.md) — NDJSON streaming protocol contract.

### Developer Quickstart

See [quickstart.md](quickstart.md) — environment setup, run commands, test commands.
