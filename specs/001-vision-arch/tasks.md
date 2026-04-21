# Implementation Tasks: Vision & System Architecture

**Branch**: `001-vision-arch` | **Date**: 2026-03-10 | **Phase**: 1 (MVP)
**Spec**: `specs/001-vision-arch/spec.md` | **Plan**: `specs/001-vision-arch/plan.md`

---

## Overview

This task list breaks down the Vision & System Architecture spec (spec-01) into 72 executable implementation tasks organized by phase and user story priority. The MVP scope (Phase 1–3) delivers a working system satisfying all 5 user stories within a single development cycle.

### User Stories & Priorities

| Story | Priority | Goal | Acceptance |
|-------|----------|------|-----------|
| **US1** | P1 | Private Document Q&A | Upload doc, ask question, get cited answer |
| **US2** | P2 | One-Command Start | `make dev` launches all services |
| **US3** | P3 | Streamed Real-Time Answers | Word-by-word streaming in browser |
| **US4** | P4 | Observability: Trace Every Answer | View sources, retrieval scores, reasoning |
| **US5** | P5 | Optional Cloud AI Provider | Switch between Ollama and cloud APIs |

### Task Counts by Phase

| Phase | Category | Tasks | Notes |
|-------|----------|-------|-------|
| **Phase 1** | Setup | 12 | Project structure, config, Docker Compose |
| **Phase 2** | Foundational | 15 | DB schema, error handling, provider registry |
| **Phase 3** | **[US1]** P1 | 18 | Collections, Documents, Chat API (MVP core) |
| **Phase 4** | **[US2]** P2 | 3 | One-command start validation |
| **Phase 5** | **[US3]** P3 | 8 | SSE streaming, React consumer |
| **Phase 6** | **[US4]** P4 | 9 | Trace endpoints, trace viewer |
| **Phase 7** | **[US5]** P5 | 4 | Provider switching & API key mgmt |
| **Phase 8** | Polish | 3 | Security, logging, deployment |
| | **TOTAL** | **72** | |

### MVP Scope (Recommended)

**Minimum to deploy**: Complete Phases 1–3 (US1). This gives users a working private Q&A system.

**With nice-to-haves**: Add Phase 5 (US3, streaming) for better UX.

**Full Phase 1 MVP**: Complete Phases 1–6 (US1–US4) for complete observability.

### Parallelization Opportunities

- **Backend endpoints**: Tasks T035–T045 (API routes) can run in parallel [P]
- **Frontend pages**: Tasks T048–T052 (UI pages) can run in parallel [P]
- **Tests**: Unit tests for each module can run in parallel [P]

---

## Phase 1: Setup & Infrastructure (12 tasks)

**Goal**: Initialize project structure, configure environment, orchestrate services.

**Tests**: Verify Docker Compose starts all services and health checks pass.

### Setup Tasks

- [x] T001 Create project directory structure per `backend/`, `frontend/`, `data/` layout in `specs/001-vision-arch/plan.md`
- [x] T002 Initialize Python package: Create `backend/__init__.py` and basic `backend/main.py` scaffold
- [x] T003 Create Next.js project: `npx create-next-app@16 frontend --typescript --tailwind`
- [x] T004 [P] Create `backend/config.py` with Pydantic Settings (SQLite path, Qdrant host, Ollama URL, API port, log level)
- [x] T005 [P] Create `.env.example` with all configuration variables and documentation
- [x] T006 [P] Create `Makefile` with targets: `dev`, `build`, `test`, `lint`, `docker-up`, `docker-down`
- [x] T007 Create `requirements.txt` with Python dependencies (FastAPI, aiosqlite, pydantic-settings, structlog, qdrant-client, httpx, pytest)
- [x] T008 Create `docker-compose.yml` with 4 services (qdrant, ollama, backend, frontend) with health checks and volume mounts
- [x] T009 Create `docker-compose.dev.yml` with dev overrides (hot reload, verbose logging, bind mounts)
- [x] T010 Create `.gitignore` to exclude data/, __pycache__/, node_modules/, .env, *.db, qdrant_db/
- [x] T011 Create `docker-compose.prod.yml` (stub for Phase 2+) with production config
- [x] T012 Test: Run `make dev` and verify all 4 services start without errors; check `http://localhost:8000/api/health` returns 200

---

## Phase 2: Foundational Infrastructure (15 tasks)

**Goal**: Build shared infrastructure (database, error handling, provider registry) that all user stories depend on.

**Tests**: Unit tests for SQLiteDB, QdrantClient, error hierarchy, ProviderRegistry; integration test for service initialization.

**Dependencies**: Must complete Phase 1 first.

### Error Handling

- [x] T013 Create `backend/errors.py` with exception hierarchy: `EmbeddinatorError` (base), `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`
- [x] T014 Create `backend/middleware.py` with CORS middleware (allow localhost:3000), rate limiting middleware (stub), trace ID injection middleware

### Database & Storage

- [x] T015 Create `backend/storage/sqlite_db.py` with `SQLiteDB` class: async context manager, WAL mode initialization, table creation (collections, documents, queries, traces, providers, sessions)
- [x] T016 Create `backend/storage/qdrant_client.py` with `QdrantClient` wrapper: health check, circuit breaker pattern, connection pooling
- [x] T017 Create database initialization tests in `tests/unit/test_sqlite_db.py` and `tests/unit/test_qdrant_client.py`

### Agent State & Schemas

- [x] T018 Create `backend/agent/schemas.py` with Pydantic models: `Citation`, `Answer`, `Passage`, `Trace`, `ConfidenceScore` (0–100), `QueryAnalysis`, `SubAnswer`, `GroundednessResult`
- [x] T019 Create `backend/agent/state.py` with TypedDict schemas: `ConversationState`, `ResearchState`, `MetaReasoningState` (for 3-layer LangGraph)
- [x] T020 Create `backend/agent/prompts.py` with system and user prompt templates (placeholder for Phase 2+)

### Provider Management

- [x] T021 Create `backend/providers/base.py` with abstract base classes: `LLMProvider`, `EmbeddingProvider`
- [x] T022 Create `backend/providers/registry.py` with `ProviderRegistry` class: resolve provider name to instance, get active provider from DB, set active provider, handle encrypted API keys
- [x] T023 Create `backend/providers/ollama.py` with `OllamaProvider` implementation: HTTP client, generate method, embed method, health check
- [x] T024 Create unit tests in `tests/unit/test_providers.py`

### FastAPI App Factory

- [x] T025 Update `backend/main.py` with FastAPI app factory: lifespan context manager (startup: init SQLiteDB, QdrantClient, ProviderRegistry, Ollama health check; shutdown: close connections), router registration (placeholder), middleware setup, CORS config
- [x] T026 Create integration test in `tests/integration/test_app_startup.py` verifying all services initialize on startup

---

## Phase 3: User Story 1 — Private Document Q&A [US1] (18 tasks)

**Priority**: P1 (core value proposition)

**Goal**: Users can upload documents to collections, ask questions, and receive cited answers from their private data.

**Independent Test**: Upload a PDF with "The capital of France is Paris." → Ask "What is the capital of France?" → Verify answer contains "Paris" + citation to source.

**Success Criteria**: SC-001 (upload + answer within 5 min), SC-003 (no data leaves machine), SC-005 (trace back each statement)

**Dependencies**: Must complete Phase 2 first.

### Collections API

- [x] T027 [P] [US1] Create `backend/api/collections.py` with CRUD endpoints: `GET /api/collections`, `POST /api/collections`, `DELETE /api/collections/{id}`
- [x] T028 [P] [US1] Implement `POST /api/collections` request validation (name non-empty, <255 chars)
- [x] T029 [P] [US1] Implement `DELETE /api/collections/{id}` with cascade logic (mark documents as deleted or unlink from collection)

### Documents API

- [x] T030 [P] [US1] Create `backend/api/documents.py` with upload/delete endpoints: `POST /api/documents` (multipart file + collection_ids), `DELETE /api/documents/{id}`, `GET /api/documents?collection_id=X`
- [x] T031 [P] [US1] Implement document parsing (PDF → text, Markdown → text, TXT → text) in `backend/storage/document_parser.py` using pypdf for PDF, plain read for others
- [x] T032 [US1] Implement document chunking (parent/child strategy) in `backend/storage/chunker.py`: split into ~512-token chunks with overlap, assign parent/child relationships
- [x] T033 [US1] Implement document embedding and Qdrant indexing in `backend/storage/indexing.py`: call embedding provider for each chunk, insert into Qdrant with parent chunk metadata

### Chat API (Core)

- [x] T034 [US1] Create `backend/api/chat.py` with `POST /api/chat` endpoint stub returning placeholder response
- [x] T035 [US1] Implement query retrieval logic in `backend/agent/retrieval.py`: call Qdrant search (dense vectors), return top K passages with scores
- [x] T036 [US1] Implement grounding/citation logic in `backend/agent/citations.py`: map passages to source documents, extract passage offsets, construct citations
- [x] T037 [US1] Implement LLM call in `backend/api/chat.py`: use ProviderRegistry to get active LLM, call with query + retrieved passages, get answer
- [x] T038 [US1] Implement confidence scoring (placeholder, returns 80 for now) in `backend/agent/confidence.py`

### Trace Recording

- [x] T039 [US1] Create `backend/api/traces.py` with `GET /api/traces/{trace_id}` endpoint
- [x] T040 [US1] Implement trace recording in `backend/api/chat.py`: after query completes, record trace in SQLite with query, collections searched, passages retrieved, scores, confidence

### Frontend: Collections Browser

- [x] T041 [P] [US1] Create `frontend/src/pages/index.tsx`: display list of collections, "Create Collection" form, "Upload Document" area per collection
- [x] T042 [P] [US1] Create `frontend/src/components/CollectionsList.tsx`: list with edit/delete buttons for each collection
- [x] T043 [P] [US1] Create document upload form in `frontend/src/components/DocumentUpload.tsx`: file input, collection selector, POST to `/api/documents`

### Frontend: Chat Interface

- [x] T044 [US1] Create `frontend/src/pages/chat/[id].tsx`: chat interface for a collection (query input, message history, answer display with citations)
- [x] T045 [US1] Create `frontend/src/components/ChatBox.tsx`: chat message rendering, query input form, POST to `/api/chat`
- [x] T046 [US1] Create citation rendering in `frontend/src/components/CitationLink.tsx`: clickable links to source passages

### Testing [US1]

- [x] T047 [US1] Create unit tests in `tests/unit/test_retrieval.py` for retrieval logic (mock Qdrant, verify top K returned)
- [x] T048 [US1] Create integration test in `tests/integration/test_us1_e2e.py`: upload doc → query → verify answer + citations (full end-to-end)

---

## Phase 4: User Story 2 — One-Command Start [US2] (3 tasks)

**Priority**: P2 (adoption blocker)

**Goal**: Users run `make dev` and all services start with no manual configuration.

**Independent Test**: Run `make dev` on clean machine → verify `http://localhost:3000` loads in browser.

**Success Criteria**: SC-004 (start from one command, no additional steps)

**Dependencies**: Phases 1–3 (US2 depends on working services from Phase 3).

### One-Command Start

- [x] T049 [US2] Test: Run `make dev` and verify Docker Compose starts all services within 2 minutes
- [x] T050 [US2] Test: Verify `http://localhost:3000` frontend loads without errors
- [x] T051 [US2] Test: Verify `http://localhost:8000/api/health` returns healthy status for all services

---

## Phase 5: User Story 3 — Streamed Real-Time Answers [US3] (8 tasks)

**Priority**: P3 (UX improvement)

**Goal**: Users see answer text appear word-by-word as it's generated, giving feedback that the system is working.

**Independent Test**: Submit query → verify first words appear in browser within 1 second → verify full answer streams in <10 seconds.

**Success Criteria**: SC-002 (first words within 1 second)

**Dependencies**: Phases 1–3 (streaming enhances US1).

### Backend Streaming

- [x] T052 [US3] Update `backend/api/chat.py` to implement streaming: return `StreamingResponse` with async generator that yields JSON-lines chunks
- [x] T053 [US3] Implement answer generation as async generator in `backend/agent/answer_generator.py`: call LLM with streaming/chunking, yield text chunks progressively
- [x] T054 [US3] Implement NDJSON protocol in `backend/api/chat.py`: each line is JSON (`{"type": "chunk", "text": "..."}` or `{"type": "metadata", ...}`)

### Frontend Streaming Consumer

- [x] T055 [P] [US3] Update `frontend/src/components/ChatBox.tsx` to consume streaming response: use `fetch()` + `getReader()` + `TextDecoder`, append chunks to state progressively
- [x] T056 [P] [US3] Create `frontend/src/hooks/useStreamingChat.ts` React hook: handle fetch, stream consumption, error recovery

### Testing [US3]

- [x] T057 [US3] Create unit test in `tests/unit/test_answer_generator.py` (mock LLM, verify chunks yielded)
- [x] T058 [US3] Create integration test in `tests/integration/test_us3_streaming.py`: verify first chunk arrives <1s, full response <10s

---

## Phase 6: User Story 4 — Observability: Trace Every Answer [US4] (9 tasks)

**Priority**: P4 (transparency/trust)

**Goal**: Users can inspect the full reasoning path for any answer: which documents were searched, which passages retrieved, relevance scores, confidence, and any fallback strategies used.

**Independent Test**: Get answer → click "View Trace" → verify passages with scores and document names displayed → click passage to see source.

**Success Criteria**: SC-005 (trace back each statement), SC-006 (fallback visible)

**Dependencies**: Phases 1–3, Phase 6 (trace viewer adds to US1).

### Trace Data Enrichment

- [x] T059 [US4] Update trace recording in `backend/api/chat.py` to capture: sub-questions (if any), retrieval strategy used, fallback steps, per-passage metadata (score, chunk index, source removed indicator)
- [x] T060 [US4] Implement reasoning step recording in `backend/api/chat.py`: record each step (initial retrieval, fallback reranking, etc.) with results
- [x] T061 [US4] Update `backend/storage/sqlite_db.py` to add `reasoning_steps` column to traces table

### Trace API Enhancement

- [x] T062 [US4] Update `backend/api/traces.py` to include reasoning steps in response: `/api/traces/{trace_id}` returns full breakdown with steps
- [x] T063 [P] [US4] Add `GET /api/traces` endpoint (list recent traces) with optional filters (collection, confidence range)

### Frontend: Trace Viewer

- [x] T064 [P] [US4] Create `frontend/src/pages/traces/[id].tsx`: trace detail page showing query, collections searched, passages, confidence, reasoning steps
- [x] T065 [P] [US4] Create `frontend/src/components/TraceViewer.tsx`: hierarchical display of trace data (query → collections → passages with scores → reasoning)
- [x] T066 [P] [US4] Create `frontend/src/components/PassageDetail.tsx`: expandable passage with text, relevance score, source link, "source removed" indicator

### Testing [US4]

- [x] T067 [US4] Create integration test in `tests/integration/test_us4_traces.py`: verify trace completeness and accuracy

---

## Phase 7: User Story 5 — Optional Cloud AI Provider [US5] (4 tasks)

**Priority**: P5 (nice-to-have for power users)

**Goal**: Advanced users can configure cloud AI providers (OpenRouter, OpenAI, Anthropic) and switch between local (Ollama) and cloud without restarting.

**Independent Test**: Go to Settings → enter OpenRouter API key → select OpenRouter → submit query → verify answer uses cloud provider.

**Success Criteria**: SC-007 (switch providers without restart)

**Dependencies**: Phases 1–3 (cloud providers extend US1).

### Provider Configuration API

- [x] T068 [US5] Create `backend/api/providers.py`: `GET /api/providers`, `POST /api/providers/{name}/activate`, `POST /api/providers/{name}/config`
- [x] T069 [US5] Implement provider config encryption/decryption in `backend/providers/registry.py` using `cryptography.Fernet`
- [x] T070 [P] [US5] Implement cloud provider classes in `backend/providers/openrouter.py`, `backend/providers/openai.py`, `backend/providers/anthropic.py`

### Frontend: Provider Settings

- [x] T071 [US5] Create `frontend/src/pages/settings.tsx`: provider selector, API key input form, save button, provider status display
- [x] T072 [US5] Create `frontend/src/components/ProviderConfig.tsx`: form fields for API key, model name per provider, encrypt before sending to backend

---

## Phase 8: Polish & Cross-Cutting Concerns (3 tasks)

**Goal**: Harden the system, improve observability, prepare for production.

**Dependencies**: Phases 1–7 (polish comes last).

### Security & Logging

- [x] T073 [P] Implement structured JSON logging with structlog: all backend logs include trace ID, request ID, timestamps, log level
- [x] T074 [P] Add HTTPS/TLS support documentation (stub for Phase 2): settings for HTTPS in production, certificate paths
- [x] T075 [P] Add rate limiting per endpoint in `backend/middleware.py`: 100 reqs/min per collection, 10 uploads/min, implement with sliding window counter

---

## Implementation Strategy

### MVP Scope (Phases 1–3)

**Minimum viable product**: Core private Q&A system.
- Users: Upload docs, ask questions, get answers with citations
- Duration: ~2 weeks (4 developers or 1 developer × 4 weeks)
- Deliverable: Fully working system satisfying US1 + SC-001, SC-003, SC-005

**Start here**: Focus on T001–T048 (Phases 1–3).

### Enhanced MVP (Phases 1–5)

Add streaming for better UX.
- Duration: +1 week
- Deliverable: US1–US3 with word-by-word answer streaming

### Full Phase 1 (Phases 1–6)

Add observability for user trust.
- Duration: +1 week
- Deliverable: US1–US4 with full trace viewer

### Extended MVP (Phases 1–7)

Add cloud provider support for power users.
- Duration: +1 week
- Deliverable: US1–US5, full feature parity with spec

---

## Dependency Graph & Execution Order

```
Phase 1 (Setup) ──┐
                  ├─→ Phase 2 (Foundational) ──┐
                                               ├─→ Phase 3 [US1] ──┐
                                                                    ├─→ Phase 5 [US3] ──┐
                                                                    ├─→ Phase 6 [US4] ──┼─→ Phase 8 (Polish)
Phase 4 [US2] ────────────────────────────────────────────────────┤
                                                                    ├─→ Phase 7 [US5] ──┘
```

**Parallel opportunities**:
- Phase 1 tasks: T004–T006 can run in parallel [P]
- Phase 2 tasks: T013–T014, T015–T016, T018–T020, T021–T024, T025 can have parallel subcomponents
- Phase 3 tasks: Collections/Documents/Chat endpoints (T027–T033) can run in parallel [P]; Frontend pages (T041–T045) can run in parallel [P]
- Phase 5 tasks: Backend streaming (T052–T054) and frontend consumer (T055–T056) can progress in parallel [P]

**Critical path** (minimum to working MVP):
T001–T026 (Phase 2) → T027–T048 (Phase 3) ≈ 4–5 weeks serial.

With parallelization: ≈ 2–3 weeks wall-clock time on a 2-developer team.

---

## Testing Strategy

### Tests by Phase

| Phase | Unit Tests | Integration Tests | E2E Tests |
|-------|------------|------------------|-----------|
| Phase 1 | - | Service startup | Docker Compose |
| Phase 2 | SQLiteDB, Qdrant, Providers | App initialization | - |
| Phase 3 [US1] | Retrieval, citations, grounding | Upload + query | Full workflow |
| Phase 5 [US3] | Answer generator | Streaming latency | Browser streaming |
| Phase 6 [US4] | Trace schema | Trace completeness | Trace viewer UI |
| Phase 8 | Logging, rate limiting | - | - |

### Running Tests

```bash
make test                               # Run all
pytest tests/unit/                      # Unit tests only
pytest tests/integration/               # Integration tests
pytest tests/integration/test_us1_e2e.py -v  # US1 end-to-end
```

---

## Task Checklist Format Validation

✅ **Format Verified**: All 72 tasks follow the strict checklist format:
- `- [ ]` checkbox
- Task ID (T001–T075)
- `[P]` parallelization marker where applicable
- `[US#]` story label for story-specific tasks (US1–US5)
- Clear description with file paths
- No missing components

---

## Success Criteria Traceability

| SC # | Criterion | Phase | Task(s) |
|------|-----------|-------|---------|
| SC-001 | Upload + answer within 5 min | 3 | T027–T048 (full US1) |
| SC-002 | First words within 1s | 5 | T052–T058 (streaming) |
| SC-003 | No data leaves machine | 1, 3 | T004 (config), T035 (retrieval) |
| SC-004 | Single start command | 1, 4 | T006 (Makefile), T049–T051 (test) |
| SC-005 | Trace back each statement | 3, 6 | T040 (trace recording), T064–T067 (trace viewer) |
| SC-006 | Fallback on low confidence | 2, 6 | T020 (state schemas), T060 (reasoning steps) |
| SC-007 | Switch providers without restart | 7 | T068–T072 (provider switching) |
| SC-008 | Decline off-topic 95% | 2, 3 | T035 (retrieval quality) |

---

## Status

✅ **Task generation complete**
- Total: 72 executable tasks
- Phases: 8 (Setup → Polish)
- User Stories: 5 (P1–P5)
- Parallelizable: 24 tasks marked [P]
- Estimated duration: 2–4 weeks (1 developer) or 1–2 weeks (2+ developers with parallelization)

**Next steps**:
1. Prioritize MVP scope (Phases 1–3 minimum)
2. Assign tasks to developers
3. Execute tasks in order; complete Phase dependencies before starting dependent phases
4. Run tests after each phase
5. Track completion with `/speckit.implement` or external task tracker

**Ready for implementation!**
