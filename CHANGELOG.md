# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.2.0] - Unreleased

### Added

**Agent Architecture**
- Three-layer agentic RAG pipeline: ConversationGraph (Layer 1), ResearchGraph (Layer 2), and MetaReasoningGraph (Layer 3)
- Intelligent query routing that classifies messages as document questions, collection commands, or ambiguous inputs
- Complex query decomposition that breaks multi-topic questions into focused sub-questions researched in parallel
- Conversation continuity with session management and history compression for multi-turn follow-ups
- Iterative search refinement with query rephrasing, metadata filtering, and cross-collection search
- Search budget enforcement to prevent runaway resource consumption
- Automatic recovery from poor retrieval results via strategy selection (widen search, change collection, relax filters)
- Honest uncertainty reporting when the system genuinely cannot find relevant information

**Accuracy & Trust**
- Grounded answer verification that checks every claim against retrieved evidence, marking unsupported claims as `[unverified]`
- Citation-chunk alignment validation ensuring inline citations actually point to supporting passages
- 5-signal confidence scoring based on evidence quality, not just relevance scores
- Tier-based query classification (factoid, lookup, analytical, comparative) with tuned retrieval parameters per tier
- Circuit breaker pattern for graceful degradation when external services are unavailable

**Retrieval Pipeline**
- Hybrid dense + BM25 vector search via Qdrant for better recall across query types
- Cross-encoder reranking for precision improvement on top-k results
- Per-collection score normalization for fair cross-collection ranking
- Parent chunk context retrieval linking child search results to their broader document context

**Ingestion**
- Rust-based ingestion worker for high-performance document parsing (PDF, Markdown, plain text, code)
- Parent/child chunking strategy (parent: 2000-4000 chars, child: ~500 chars) with structural breadcrumbs
- Incremental re-ingestion with SHA256 hash-based duplicate detection
- Deterministic UUID5 point IDs for idempotent re-ingestion
- Parallel batch embedding with configurable concurrency
- Embedding validation and fault tolerance with automatic retry on transient failures

**Storage**
- Dual storage architecture: SQLite (WAL mode) for metadata and Qdrant for vector search
- Fernet-encrypted API key storage for cloud provider credentials
- Parent chunk store in SQLite linking child vectors to full document context
- Collection-scoped document management with job tracking and status transitions

**API**
- Complete REST API with 15+ endpoints for chat, collections, documents, providers, settings, traces, and health
- NDJSON streaming for real-time chat responses with structured event types (session, status, chunk, citation, confidence, groundedness, done)
- Rate limiting middleware (sliding window: 10 uploads/min, 30 chat/min, 100 general/min)
- Trace ID middleware for request correlation across the full pipeline
- Structured JSON error responses with consistent envelope format across all endpoints

**Frontend**
- Complete Next.js 16 application with shadcn/ui component library and "Obsidian Violet" design system
- Dark and light mode with manual toggle and system preference detection
- Collapsible sidebar navigation with icon-only mode and keyboard shortcut (Cmd+K) command palette
- Chat page with streaming response rendering, inline citation tooltips, and confidence indicators
- Collection management with card grid, create/delete, and document count display
- Document upload with drag-and-drop, progress tracking, and ingestion status polling
- Settings page with provider hub for managing LLM providers and API keys
- Observability dashboard with latency histogram, trace table, confidence distribution, and health status
- Responsive layout adapting to desktop and mobile viewports

**Providers**
- Multi-provider LLM support with pluggable adapter pattern
- Built-in providers: Ollama (local), OpenRouter, OpenAI, and Anthropic
- Automatic fallback to Ollama when cloud providers are unavailable
- Provider health checks visible in the observability dashboard
- Secure API key management with encrypted storage and masked display

**Quality & Reliability**
- Component interface contracts with automated signature verification tests
- Consistent error handling with custom error hierarchy and structured error responses
- Security hardening: input truncation, filename sanitization, magic-byte file validation, log scrubbing
- Performance budgets with per-stage timing instrumentation and configurable latency thresholds
- Full-stack observability with structured logging, trace ID propagation, and time-series metrics
- Comprehensive test suite: 1500+ backend tests across unit, integration, and E2E tiers with 85% coverage

**Infrastructure**
- Docker Compose setup with 4 services (Qdrant, Ollama, backend, frontend) and health checks
- Cross-platform launcher scripts (`embedinator.sh` / `embedinator.ps1`) for single-command startup
- Automatic GPU detection for NVIDIA, AMD, and Intel with appropriate Docker configuration
- Auto-generation of `.env` with Fernet encryption key on first run
- AI model auto-download with visible progress during startup
- Configurable service ports for conflict-free deployment
- 14-target Makefile for development workflow (setup, build, test, deploy, clean)
- Multi-stage Dockerfiles with non-root user execution

### Changed
- Frontend API routing now uses Next.js rewrites instead of build-time environment variables, fixing Docker networking issues
- Chat responses upgraded from simple text streaming to structured NDJSON events with metadata
- Confidence scoring upgraded from simple relevance average to 5-signal evidence-based computation
- Docker Compose healthchecks now probe `/api/health/live` instead of `/api/health`. The latter is a readiness probe gated on model availability, so a missing model would hold the backend container unhealthy and prevent the frontend from starting at all — leaving no UI instead of a UI reporting the problem
- Backend status polling uses a single 5s interval in every state, replacing an adaptive schedule that slowed to 30s while healthy
- The Next.js proxy's idle timeout (`proxyTimeout`) is raised from its 30s default to 600s, and its request body cap (`proxyClientMaxBodySize`) from 10 MiB to 100 MiB. `proxyTimeout` is a socket-inactivity timer, not a total-duration one: a cold model taking ~31s to produce its first token is 31s of silence on the wire, which the default cut off. The body cap now matches the backend's upload limit (BUG-054, BUG-040)
- Upload size limit in the UI raised from 50 MB to 100 MB, matching what the backend has always enforced (BUG-040)
- The chat client now watches a stream for silence (`STREAM_IDLE_TIMEOUT_MS`, 120s). A stream that goes quiet ends with an error message and a Retry button instead of spinning forever, using the new client error codes `STREAM_STALLED` and `STREAM_TRUNCATED`; Retry is disabled while a turn is streaming, so one turn has one owner (BUG-074, BUG-119)
- Every in-flight LLM call on a chat turn is bounded by a wall-clock deadline via the new `llm_call_timeout_seconds` setting (default 90s, environment variable `LLM_CALL_TIMEOUT_SECONDS`). On expiry the turn ends with an NDJSON `error` frame carrying the new code `LLM_TIMEOUT` (BUG-088)
- Health polling keeps its 5s cadence while the backend is unreachable. Recovery is no longer governed by SWR's exponential backoff, which grew with the length of the outage (BUG-124)
- A message the intent classifier scores as ambiguous now ends the turn with an answer instead of sending its own fallback answer back to be re-classified (BUG-082)

### Fixed

**Health & status reporting**
- Aggregate health no longer reports `healthy` while a required Ollama model is missing, so a system that cannot actually serve a query no longer advertises itself as ready (BUG-026)
- Model availability checks now normalize Ollama's `:latest` tag suffix. A correctly installed default stack was previously reported as missing its embedding model on every start (BUG-025)
- The status banner now reflects backend degradation within one ~5s polling cycle instead of up to 30s. Health requests are also bounded by a 3s timeout, so a hung backend can no longer hold the UI on stale green indefinitely. Because backend status also gates the chat input, this previously allowed users to submit into a backend that could not serve them (BUG-034)
- The UI now leaves its unreachable state within one 5s poll interval of the backend coming back. Recovery was previously scheduled by SWR's exponential backoff, so the longer the outage, the longer users stayed locked out of a backend that was already healthy — 197s measured on a 190s outage, against a filed estimate of 31-60s (BUG-124)

**Observability**
- The trace-detail stage-timings chart now plots every recorded stage. Research orchestrator and tool timings were stored as bare numbers and rendered as empty bars, so on a 26s turn the chart showed a 1.9s stage as dominant while hiding the real 18.1s bottleneck (BUG-102)
- Query Analytics latency and confidence distributions are now computed across all queries via `/api/stats` instead of re-slicing the visible 20-row page. The panel previously read high-confidence while the true average across all traces was low, and paging the table silently changed the "analytics" (BUG-112)

**Streaming & deadlines**
- A chat stream that ends without a terminal event no longer leaves the UI streaming forever. Both halves of the defect are fixed: a stream that goes silent is ended by a client-side idle watchdog after 120s, and a stream whose connection closes without a `done` or `error` event now reports one. Both were needed, because the proxy does not deliver a connection close to the browser at all (BUG-074)
- A permanently dead conversation is now visibly distinct from one that is still being worked on, and no longer accepts further input through a Retry button while a turn is in flight. The health banner recovering after an outage no longer implies that an in-flight conversation survived it (BUG-119)
- A single in-flight LLM call can no longer run unbounded. Neither the provider's own request timeout nor the research loop's wall-clock cap could interrupt a call already awaiting a frozen socket; one such call was observed running 553s. The turn now ends at the deadline with an error the user can act on, and releases its concurrency slot (BUG-088)
- An ambiguous message no longer loops between intent classification and clarification until the request dies. The turn ends with the clarification answer, and a step bound keeps any remaining cycle away from the graph's recursion limit (BUG-082)
- A chat stream whose backend dies mid-answer now ends in the browser instead of spinning indefinitely. The Next.js proxy's behaviour is unchanged — it still never signals the browser that the connection is gone — so it is the client-side idle watchdog that ends the dead stream, 120s after the last piece of the answer arrived, leaving an error state and a Retry (BUG-123)

**Uploads & proxy**
- Chat requests are no longer cut off after ~30s of silence by the Next.js proxy. The first chat after startup — when the model is still loading — waits ~31s for its first token and was being killed by the proxy's default idle timeout, with no error that named the cause (BUG-054)
- The three size limits that disagreed (UI 50 MB, proxy 10 MiB, backend 100 MB) now agree at 100 MB, so the UI no longer rejects a file the backend accepts (BUG-040)

---

## [0.1.0] - 2026-03-10

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
