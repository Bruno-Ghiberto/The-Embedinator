# Spec 01: Vision & System Architecture -- Implementation Plan Context

## Overview & User Stories

This spec establishes the foundational infrastructure **and delivers a complete end-to-end user-facing MVP** that satisfies all 5 user stories from the spec:

- **US1 (P1)**: Private Document Q&A — Upload docs, query them, get cited answers (local only)
- **US2 (P2)**: One-Command Start — Single command to launch all services
- **US3 (P3)**: Streamed Real-Time Answers — Streaming responses word-by-word
- **US4 (P4)**: Observability — Full trace view showing sources and reasoning
- **US5 (P5)**: Optional Cloud Provider — Switch between Ollama and cloud APIs

**Success Criteria (SC-001 to SC-008)**: New user should upload a document and receive a correct, cited answer within 5 minutes. All three services (backend, frontend, Ollama) must start from one command with no manual configuration.

## Technical Stack

- **Backend**: FastAPI with async/await, SQLite (WAL mode), Qdrant, Ollama (default provider)
- **Frontend**: Next.js 16 + React 19 with TypeScript; chat UI, collections browser, trace viewer
- **Orchestration**: Docker Compose (4 services: Qdrant, Ollama, FastAPI, Next.js)
- **Infrastructure**: Configuration via environment variables, structured JSON logging with trace IDs, middleware for CORS and rate limiting
- **Configuration**: Pydantic Settings from `.env` file with sensible local-first defaults

## File Structure (Complete MVP)

```
the-embedinator/
  backend/
    __init__.py
    main.py                # FastAPI app factory, lifespan (startup/shutdown resources)
    config.py              # Settings: all env vars, defaults, validation
    errors.py              # Error hierarchy (EmbeddinatorError base + all custom exceptions)
    middleware.py          # CORS, rate limiting, trace ID injection
    api/
      __init__.py
      collections.py       # Collection CRUD (create, list, delete) — User Story 1 (upload to collection)
      documents.py         # Document upload, parsing, deletion — User Story 1 (US1)
      chat.py              # Chat endpoint with SSE streaming — User Story 3 (US3)
      traces.py            # Query trace view (sources, retrieval scores, reasoning) — User Story 4 (US4)
      providers.py         # List available providers, set active provider — User Story 5 (US5)
      health.py            # System health check (all services up?)
    agent/
      __init__.py
      state.py             # TypedDict state schemas for all three LangGraph layers
      schemas.py           # Pydantic models: QueryAnalysis, SubAnswer, Citation, Trace, GroundednessResult, ConfidenceScore
      prompts.py           # All system and user prompts as constants
    storage/
      __init__.py
      sqlite_db.py         # SQLiteDB class: table creation (collections, documents, queries, traces, providers), WAL mode
      qdrant_client.py     # Qdrant wrapper: health check, vector search interface
    providers/
      __init__.py
      base.py              # Abstract base: LLMProvider, EmbeddingProvider
      registry.py          # ProviderRegistry: provider name -> instance resolution
      ollama.py            # OllamaProvider (default, local)
  frontend/
    src/
      pages/
        index.tsx          # Collections browser & document upload (US1: upload to collection)
        chat/[id].tsx      # Chat interface for a collection (US1: ask questions)
        traces/[id].tsx    # Query trace viewer (US4: observability)
        settings.tsx       # Provider selection & API key management (US5)
      components/
        CollectionsList.tsx
        ChatBox.tsx        # Streaming response display (US3)
        TraceViewer.tsx
        ConfidenceIndicator.tsx  # 0–100% scale (clarified requirement)
      api/
        client.ts          # API client (fetch wrappers)
      types/
        index.ts           # TypeScript interfaces (collection, document, query, answer, trace)
      styles/
        global.css
    package.json
    next.config.js
    tsconfig.json
  data/                    # gitignored — runtime data
    uploads/               # User-uploaded documents
    qdrant_db/             # Vector store persistence
  docker-compose.yml       # Services: qdrant, ollama, backend (FastAPI), frontend (Next.js)
  docker-compose.dev.yml   # Dev overrides (hot reload, verbose logging)
  .env.example             # Template with all vars and docs
  Makefile                 # Targets: make dev, make build, make test, make docker-up/down
  requirements.txt         # Python dependencies (FastAPI, aiosqlite, pydantic-settings, structlog, etc.)
  package.json             # Node.js dependencies (already in frontend/ but may want at root)
  .gitignore
```

## Implementation Steps

### Backend Infrastructure (Foundations)

1. **`backend/config.py`**: Define `Settings` class with environment variables and defaults. Include: SQLite path, Qdrant URL, Ollama URL, API port, default model names, logging level. Load from `.env`; use sensible local defaults (e.g., `http://localhost:6333` for Qdrant).

2. **`backend/errors.py`**: Custom exception hierarchy:
   - `EmbeddinatorError` (base)
   - `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`

3. **`backend/storage/sqlite_db.py`**: Async SQLiteDB class with table schemas:
   - `collections` (id, name, created_at, updated_at)
   - `documents` (id, name, collection_ids_json, upload_date, file_path, status) — *supports many-to-many via JSON list*
   - `parent_chunks` (id, document_id, text, embedding_id)
   - `query_traces` (id, query_text, collections_searched, passages_retrieved, confidence, created_at)
   - `providers` (name, type, config_json, is_active)
   - `sessions` (id, created_at, last_activity_at, user_agent)

4. **`backend/storage/qdrant_client.py`**: Qdrant wrapper with health check and circuit breaker. Initialize collection on startup.

5. **`backend/providers/base.py`**: Abstract base classes `LLMProvider` and `EmbeddingProvider` with methods for generating responses and embeddings.

6. **`backend/providers/registry.py`**: `ProviderRegistry` to resolve provider name to instance. Default to Ollama.

7. **`backend/providers/ollama.py`**: `OllamaProvider` implementation calling Ollama HTTP API.

8. **`backend/middleware.py`**: CORS (allow local network), rate limiting, trace ID injection.

9. **`backend/agent/state.py`**: TypedDict schemas for ConversationState, ResearchState, MetaReasoningState (from architecture doc).

10. **`backend/agent/schemas.py`**: Pydantic models for QueryAnalysis, SubAnswer, Citation, GroundednessResult, ConfidenceScore (0–100 scale). All used across agent layers and API responses.

11. **`backend/main.py`**: FastAPI app factory with lifespan context manager:
    - **Startup**: Initialize SQLiteDB, QdrantClient, ProviderRegistry, Ollama health check
    - **Registration**: Mount routers for collections, documents, chat, traces, providers, health
    - **Shutdown**: Close DB and Qdrant connections
    - Set CORS middleware for local network access

### API Endpoints (Fulfill User Stories)

12. **`backend/api/collections.py`** (User Story 1):
    - `GET /api/collections` — List all collections
    - `POST /api/collections` — Create collection (name)
    - `DELETE /api/collections/{id}` — Delete collection

13. **`backend/api/documents.py`** (User Story 1):
    - `POST /api/documents` — Upload document (file, collection_id; supports PDF/MD/TXT)
    - `DELETE /api/documents/{id}` — Delete document (marks as deleted, traces retain text)
    - `GET /api/documents?collection_id=X` — List documents in collection

14. **`backend/api/chat.py`** (User Story 1 + 3):
    - `POST /api/chat` (request body: query, collection_ids, model_name) → SSE stream with streamed response text + final metadata (citations, confidence, trace_id)
    - Implement streaming via `StreamingResponse` with `async for` over response chunks
    - First words appear within 1 second (**SC-002**)

15. **`backend/api/traces.py`** (User Story 4):
    - `GET /api/traces/{trace_id}` — Full trace details (query, sources searched, passages retrieved with scores, reasoning steps)
    - Include confidence score 0–100% and passage links

16. **`backend/api/providers.py`** (User Story 5):
    - `GET /api/providers` — List available providers (Ollama, OpenRouter, etc.) with config status
    - `POST /api/providers/{name}/activate` — Switch active provider
    - `POST /api/providers/{name}/config` — Set API key (encrypted storage)

17. **`backend/api/health.py`**:
    - `GET /api/health` — Return status of Ollama, Qdrant, SQLite connections

### Frontend (Complete User-Facing UI)

18. **`frontend/src/pages/index.tsx`** (User Story 1 + 2):
    - Display list of collections (with counts)
    - Upload document button → file chooser → POST to `/api/documents` with collection_id (**SC-001**: user uploads and queries within 5 min)
    - Link to create new collection
    - Link to each collection's chat page

19. **`frontend/src/pages/chat/[id].tsx`** (User Story 1 + 3):
    - Display collection name and document list
    - Chat input field + send button
    - Message history (user queries + system answers)
    - **Stream responses** word-by-word as they arrive from `/api/chat` endpoint (**SC-002**: first words within 1s)
    - Display confidence indicator (0–100% scale) below each answer (**FR-008a clarification**)
    - Show citations as clickable links to source passages

20. **`frontend/src/pages/traces/[id].tsx`** (User Story 4):
    - Show trace details: query, collections searched, passages retrieved (with relevance scores)
    - Link to source documents
    - Show reasoning steps and fallback attempts
    - Display confidence score

21. **`frontend/src/pages/settings.tsx`** (User Story 5):
    - Provider selector dropdown (Ollama, OpenRouter, etc.)
    - API key input for cloud providers (masked)
    - Save button → POST to `/api/providers/{name}/config`
    - Display "unsecured local mode" if using Ollama only

22. **`frontend/src/components/ConfidenceIndicator.tsx`**:
    - Display confidence as 0–100% badge/bar (e.g., "87% confident")
    - Color code: green 80–100%, yellow 50–79%, red 0–49%

23. **`frontend/src/types/index.ts`**: TypeScript interfaces for Collection, Document, Query, Answer, Trace, ConfidenceScore.

### Deployment & Configuration

24. **`docker-compose.yml`**:
    - Service `qdrant` (port 6333, volume for persistence)
    - Service `ollama` (port 11434, volume for models)
    - Service `backend` (FastAPI, port 8000, depends_on qdrant + ollama)
    - Service `frontend` (Next.js, port 3000, depends_on backend)
    - Health checks for each service

25. **`.env.example`**: Template documenting all variables (SQLITE_PATH, QDRANT_HOST, OLLAMA_BASE_URL, API_PORT, DEFAULT_LLM_MODEL, DEFAULT_EMBED_MODEL, LOG_LEVEL, etc.)

26. **`Makefile`**:
    - `make dev` — Start Docker Compose in dev mode with hot reload
    - `make build` — Build all images
    - `make test` — Run test suite
    - `make docker-up / docker-down` — Manual Docker control

27. **`requirements.txt`**: All Python dependencies with pinned versions:
    - `fastapi>=0.135`, `aiosqlite>=0.20`, `pydantic>=2.0`, `pydantic-settings>=2.0`
    - `qdrant-client>=1.17.0`, `structlog>=24.0`
    - `httpx>=0.27` (for Ollama/provider HTTP calls)
    - No LangGraph yet (added in spec-02)

## Validation Against Spec

| Success Criterion | How This Plan Delivers |
|-------------------|------------------------|
| **SC-001**: New user uploads doc & gets cited answer within 5 min | Frontend: upload UI (step 18), chat interface (step 19), backend ingestion + query (steps 12–14) |
| **SC-002**: First words in browser within 1s | SSE streaming endpoint (step 14), React component consuming stream (step 19) |
| **SC-003**: No data leaves machine in local-only mode | Config: default Ollama provider, no external calls (step 1) |
| **SC-004**: System starts from one command | Docker Compose + Makefile (steps 24–26): `make dev` starts all 4 services |
| **SC-005**: Trace back each statement to source passage | Trace endpoint (step 15) returns passages; frontend links them (step 20) |
| **SC-006**: Fallback on low confidence | Deferred to spec-03 (LangGraph logic); placeholder in schemas (step 10) |
| **SC-007**: Switch providers without restart | Settings endpoint (step 16) updates active provider in DB; no restart needed |
| **SC-008**: Decline to answer 95% of off-topic queries | Deferred to spec-03 (retrieval + grounding logic); framework in place |

## Clarified Requirements Reflected

- ✅ **Confidence scale 0–100%**: Schemas (step 10), ConfidenceIndicator component (step 22), FR-008a update (step 15)
- ✅ **Many-to-many document↔collection**: SQLite schema with JSON array in documents table (step 3)
- ✅ **Multiple concurrent sessions**: FastAPI naturally supports; sessions table for tracking (step 3)
- ✅ **Streamed responses**: SSE streaming endpoint + React consumer (steps 14, 19)
- ✅ **No authentication**: No auth middleware; assumes local network trust (step 8, Docker Compose)

## Phase Assignment

**Phase 1: Minimum Viable Product** — All 27 steps are Phase 1. This delivers a complete, working system that satisfies all 5 user stories and 8 success criteria. Users can:
1. Start the system with one command
2. Upload documents to collections
3. Ask questions and get streamed answers with citations
4. View traces of reasoning
5. Optionally switch to a cloud provider

Later phases (2–17) add sophistication: Rust ingestion worker, LangGraph reasoning, performance tuning, additional providers, security hardening, observability.
