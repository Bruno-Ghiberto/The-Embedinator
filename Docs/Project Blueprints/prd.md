# The Embedinator — Product Requirements Document

**Version**: 1.0
**Date**: 2026-03-10
**Status**: Draft
**Author**: Architecture Design Team
**Source**: `claudedocs/architecture-design.md` v2.0

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Target Users & Personas](#target-users--personas)
4. [Product Vision & Goals](#product-vision--goals)
5. [User Stories](#user-stories)
6. [Functional Requirements](#functional-requirements)
7. [Non-Functional Requirements](#non-functional-requirements)
8. [System Architecture Summary](#system-architecture-summary)
9. [Success Metrics & KPIs](#success-metrics--kpis)
10. [Constraints & Assumptions](#constraints--assumptions)
11. [Risks & Mitigations](#risks--mitigations)
12. [Release Phases & Roadmap](#release-phases--roadmap)
13. [Dependencies](#dependencies)
14. [Glossary](#glossary)

---

## Executive Summary

The Embedinator is a self-hosted agentic RAG (Retrieval-Augmented Generation) system that lets users embed, index, and intelligently query their own documents — entirely on their own hardware, with zero mandatory cloud dependencies. It combines a three-layer LangGraph agent architecture with hybrid dense+BM25 retrieval, cross-encoder reranking, and a Next.js frontend, all deployable with a single `docker compose up`.

The system differentiates itself through:
- **Autonomous failure recovery**: A MetaReasoningGraph diagnoses retrieval failures and switches strategies without user intervention
- **Evidence-based confidence scoring**: Confidence is computed from retrieval signals, not LLM self-assessment
- **Grounded answer verification**: NLI-based claim checking catches hallucinated or unsupported assertions
- **Multi-provider flexibility**: Defaults to fully local inference (Ollama) but supports cloud LLMs (OpenRouter, OpenAI, Anthropic) for users without GPU hardware
- **Built-in observability**: Query traces, latency charts, and confidence distributions accessible through the UI

---

## Problem Statement

### The Core Problem

Individuals and small teams with private document collections (technical specs, research papers, legal documents, internal wikis) lack a practical tool to ask natural-language questions against their documents with high accuracy, full privacy, and zero cloud lock-in.

### Why Existing Solutions Fall Short

| Solution Category | Limitation |
|---|---|
| **Cloud RAG services** (ChatGPT file upload, Perplexity) | Data leaves user's machine; subscription costs; no control over retrieval pipeline; no observability into how answers were produced |
| **Open-source RAG frameworks** (LangChain templates, LlamaIndex) | Require significant developer setup; no UI; single-loop agents fail silently on hard queries; no built-in failure recovery |
| **Local chat apps** (GPT4All, Jan.ai, LM Studio) | Chat-only — no document ingestion, no retrieval pipeline, no collection management |
| **Enterprise solutions** (Vectara, Pinecone + custom) | Over-engineered for individual use; require cloud infrastructure; expensive |

### The Gap

No existing tool combines: (a) self-hosted privacy, (b) a multi-layer agent with autonomous failure recovery, (c) a polished browser UI, (d) built-in query observability, and (e) zero-config deployment via Docker Compose.

---

## Target Users & Personas

### Primary Persona: Technical Professional

**Name**: Alex — Software Developer / Technical Lead
**Context**: Works with technical documentation (API specs, RFCs, architecture docs, vendor manuals). Needs to query across 10-50 documents quickly and accurately.
**Pain points**:
- Searching PDFs manually is slow and misses cross-document connections
- Cloud tools expose proprietary documentation to third parties
- Existing local tools can't handle multi-document queries with citations
**Success criteria**: Can upload a set of technical PDFs and get accurate, cited answers within seconds, all running locally.

### Secondary Persona: Researcher / Knowledge Worker

**Name**: Jordan — Academic Researcher / Analyst
**Context**: Works with research papers, reports, and notes. Needs to synthesize information across a corpus.
**Pain points**:
- Citation tracking across dozens of sources is manual and error-prone
- Confidence in LLM answers is opaque — no way to know if the answer is well-supported
- No budget for enterprise document intelligence tools
**Success criteria**: Can see exactly which passages support each answer, with a meaningful confidence score and full query trace.

### Tertiary Persona: Privacy-Conscious User

**Name**: Sam — Legal/Medical/Financial Professional
**Context**: Works with sensitive documents that cannot leave the local network.
**Pain points**:
- Cloud-based AI tools are prohibited by compliance requirements
- Local alternatives lack the quality of cloud-based RAG systems
**Success criteria**: Entire pipeline (embedding, inference, storage) runs on local hardware with no outbound API calls in default configuration.

---

## Product Vision & Goals

### Vision Statement

> The Embedinator is a self-hosted agentic RAG system that lets you embed, index, and intelligently query your own documents — entirely on your own hardware, with zero cloud dependencies.

### Product Goals

| ID | Goal | Measurable Target |
|---|---|---|
| G1 | **Zero-config deployment** | Single `docker compose up` from clone to working system in < 5 minutes (excluding model download) |
| G2 | **Accurate retrieval** | Top-5 retrieved passages contain the correct answer for >= 80% of queries on benchmark set |
| G3 | **Meaningful confidence** | Confidence score correlates with actual answer correctness (Pearson r >= 0.6) |
| G4 | **Low perceived latency** | First token appears in < 500ms after query submission |
| G5 | **Full observability** | Every query produces a trace showing: collections searched, passages retrieved, scores, strategy switches, and total latency |
| G6 | **Privacy by default** | Zero outbound API calls when using Ollama (default configuration) |
| G7 | **Provider flexibility** | User can switch between local and cloud LLMs without code changes or restarts |

---

## User Stories

### US1: Private Document Q&A (P1 — Must Have)

> As a technical professional, I want to upload my documents to a private collection and ask natural-language questions, so that I can get accurate, cited answers without my data leaving my machine.

**Acceptance Criteria**:
- User can create a named collection via the UI
- User can upload PDF, Markdown, and plain text files (up to 100 MB each)
- Ingestion progress is visible (polling or streaming status)
- User can ask a question and receive a streamed answer with inline citations
- Citations reference specific documents and page numbers
- Answer includes a confidence indicator (0-100%)
- All processing happens locally when using Ollama

### US2: One-Command Start (P1 — Must Have)

> As a developer, I want to start the entire system with a single `docker compose up`, so that I don't spend time on manual service configuration.

**Acceptance Criteria**:
- `docker compose up` starts all 4 services (Qdrant, Ollama, backend, frontend)
- Health checks ensure services start in correct order
- Default LLM model is auto-pulled on first start
- System is functional within 5 minutes of clone (network permitting)
- `.env.example` documents all configuration options

### US3: Streaming Responses (P1 — Must Have)

> As a user, I want to see the answer appear token-by-token as it's generated, so that I don't stare at a blank screen waiting for the full response.

**Acceptance Criteria**:
- First token appears within 500ms of query submission
- Tokens stream incrementally using NDJSON (`application/x-ndjson`)
- Stream format: `{"type": "chunk", "text": "..."}` for tokens, `{"type": "metadata", ...}` for final metadata
- Metadata includes: `trace_id`, `confidence`, `citations[]`, `latency_ms`
- UI renders tokens progressively with proper markdown formatting

### US4: Query Traces & Observability (P2 — Should Have)

> As a power user, I want to see exactly how my query was processed — which collections were searched, what passages were retrieved, and whether the agent had to retry — so that I can understand and trust the system's answers.

**Acceptance Criteria**:
- Every query generates a trace record in SQLite
- Trace includes: query text, collections searched, passages retrieved with scores, confidence, reasoning steps, total latency, whether MetaReasoningGraph was triggered
- `/observability` page displays: trace table with filters, latency histogram, confidence distribution chart, collection size stats, health dashboard
- Individual trace detail view shows step-by-step agent execution

### US5: Cloud Provider Support (P2 — Should Have)

> As a user without GPU hardware, I want to configure cloud LLM providers (OpenRouter, OpenAI, Anthropic) so that I can use powerful models without local compute requirements.

**Acceptance Criteria**:
- Settings page includes a Provider Hub section
- User enters an API key once; it is encrypted (Fernet) and stored in SQLite
- All models from a configured provider appear in the model dropdown
- User can switch between providers per conversation
- API keys are never logged or returned in API responses
- System falls back to Ollama if cloud provider is unavailable

---

## Functional Requirements

### FR1: Collection Management

| ID | Requirement | Priority |
|---|---|---|
| FR1.1 | Create collection with name and optional description | P1 |
| FR1.2 | List all collections with document count and total chunk count | P1 |
| FR1.3 | Delete collection (removes Qdrant collection + SQLite metadata) | P1 |
| FR1.4 | Get collection details (documents, chunks, last updated) | P1 |

### FR2: Document Ingestion

| ID | Requirement | Priority |
|---|---|---|
| FR2.1 | Upload files via multipart form (PDF, MD, TXT) | P1 |
| FR2.2 | Parse documents and extract text with structural metadata | P1 |
| FR2.3 | Split into parent chunks (2000-4000 chars) and child chunks (~500 chars) | P1 |
| FR2.4 | Prepend breadcrumb paths to child chunks before embedding | P1 |
| FR2.5 | Generate embeddings via configured provider (default: Ollama nomic-embed-text) | P1 |
| FR2.6 | Upsert child vectors to Qdrant with deterministic UUID5 point IDs | P1 |
| FR2.7 | Store parent chunks in SQLite with foreign key to collection/document | P1 |
| FR2.8 | Track ingestion job status (pending, processing, completed, failed) | P1 |
| FR2.9 | Incremental ingestion: detect unchanged documents via SHA256 hash | P2 |
| FR2.10 | Rust ingestion worker for high-performance PDF parsing (NDJSON streaming) | P2 |

### FR3: Chat & Retrieval

| ID | Requirement | Priority |
|---|---|---|
| FR3.1 | Accept natural-language query with collection selection | P1 |
| FR3.2 | Embed query using same model as collection's documents | P1 |
| FR3.3 | Hybrid dense + BM25 search in Qdrant | P1 |
| FR3.4 | Cross-encoder reranking of top-k results | P1 |
| FR3.5 | Parent chunk retrieval: use child match to fetch parent context | P1 |
| FR3.6 | LLM answer generation with retrieved passages as context | P1 |
| FR3.7 | NDJSON streaming response with token chunks and metadata | P1 |
| FR3.8 | Inline citation construction (document name, page, text excerpt) | P1 |
| FR3.9 | Confidence score computation (weighted average of passage relevance) | P1 |
| FR3.10 | Query trace recording (query, passages, scores, latency, confidence) | P1 |

### FR4: Agent Architecture

| ID | Requirement | Priority |
|---|---|---|
| FR4.1 | ConversationGraph: session lifecycle, intent classification, query rewriting | P1 |
| FR4.2 | ResearchGraph: tool-based retrieval loop with iteration budget | P1 |
| FR4.3 | Fan-out: decompose complex queries into sub-questions, research in parallel | P1 |
| FR4.4 | MetaReasoningGraph: failure diagnosis and strategy switching | P2 |
| FR4.5 | Grounded Answer Verification (GAV): NLI-based claim checking | P2 |
| FR4.6 | Citation-Chunk Alignment: cross-encoder validation of each citation | P2 |
| FR4.7 | Query-Adaptive Retrieval Depth: complexity classifier tunes top_k and iterations | P1 |

### FR5: Provider Management

| ID | Requirement | Priority |
|---|---|---|
| FR5.1 | Ollama as default provider (no configuration required) | P1 |
| FR5.2 | Provider registry: resolve model name to provider instance | P1 |
| FR5.3 | API key storage with Fernet encryption at rest | P1 |
| FR5.4 | OpenRouter provider support (200+ models, one key) | P1 |
| FR5.5 | OpenAI direct provider support | P2 |
| FR5.6 | Anthropic direct provider support | P2 |
| FR5.7 | Model listing endpoint (aggregates models from all active providers) | P1 |

### FR6: Observability

| ID | Requirement | Priority |
|---|---|---|
| FR6.1 | Query trace table with filters (collection, confidence range, date) | P2 |
| FR6.2 | Latency histogram (query processing time distribution) | P2 |
| FR6.3 | Confidence distribution chart | P2 |
| FR6.4 | Collection size statistics (documents, chunks, vectors) | P2 |
| FR6.5 | Health dashboard (Qdrant, Ollama, SQLite status) | P1 |

### FR7: Frontend

| ID | Requirement | Priority |
|---|---|---|
| FR7.1 | Chat page with collection selector, model selector, message history | P1 |
| FR7.2 | Chat input with streaming response rendering | P1 |
| FR7.3 | Citation tooltips with document name, page, and text excerpt | P1 |
| FR7.4 | Confidence indicator (visual bar/badge 0-100%) | P1 |
| FR7.5 | Collections page with CRUD operations | P1 |
| FR7.6 | Document upload with drag-drop and progress indicator | P1 |
| FR7.7 | Settings page with Provider Hub | P2 |
| FR7.8 | Observability page with trace table and charts | P2 |
| FR7.9 | Responsive layout with sidebar navigation | P1 |

---

## Non-Functional Requirements

### NFR1: Performance

| Metric | Target | Measurement |
|---|---|---|
| First token latency (chat) | < 500ms | Time from query submission to first streamed token |
| Full answer latency (simple query) | < 5s | End-to-end for queries hitting 1 collection |
| Full answer latency (complex query) | < 15s | End-to-end for multi-sub-question queries |
| Ingestion throughput (Python) | >= 10 pages/sec | PDF ingestion including embedding |
| Ingestion throughput (Rust worker) | >= 50 pages/sec | PDF parsing only (Phase 2) |
| Embedding throughput | >= 50 chunks/sec | nomic-embed-text via Ollama |
| Qdrant search latency | < 100ms | Single collection, 100K vectors |
| UI initial load | < 2s | Cold load of chat page |
| API response (health check) | < 50ms | GET /api/health |

### NFR2: Scalability

| Dimension | Target |
|---|---|
| Collections per instance | Up to 100 |
| Documents per collection | Up to 10,000 |
| Vectors per Qdrant instance | Up to 10M (limited by host RAM) |
| Concurrent users | 1-5 (single-user system by design) |
| SQLite concurrent reads | Unlimited (WAL mode) |
| SQLite concurrent writes | 1 (serialized — acceptable for workload) |

### NFR3: Reliability

| Requirement | Implementation |
|---|---|
| Circuit breaker on Qdrant calls | 5 failures in 30s opens circuit; half-open after cooldown |
| Circuit breaker on Ollama calls | Same pattern as Qdrant |
| Retry with exponential backoff | 3 attempts, 1s initial, 2x multiplier |
| Embedding integrity validation | Reject NaN, zero-vector, and dimension-mismatch before upsert |
| Graceful degradation | System responds with uncertainty message rather than crashing |
| Data durability | SQLite WAL mode; Qdrant data persisted to volume |

### NFR4: Security

| Requirement | Implementation |
|---|---|
| API keys encrypted at rest | Fernet symmetric encryption in SQLite |
| No credentials in logs | structlog processors strip sensitive fields |
| CORS restricted | Configurable origins (default: localhost:3000) |
| Rate limiting | Sliding window: 10 uploads/min, 30 chat/min, 100 general/min |
| File upload validation | Size limit (100 MB), file type allowlist (PDF, MD, TXT) |
| No outbound calls in default config | Ollama is local; cloud providers are opt-in |
| Trace ID propagation | Every request gets a UUID trace ID for log correlation |

### NFR5: Maintainability

| Requirement | Target |
|---|---|
| Test coverage (backend) | >= 80% line coverage |
| Test coverage (frontend) | >= 70% line coverage |
| Structured logging | JSON output via structlog, machine-parseable |
| Configuration centralization | All settings in `backend/config.py` via environment variables |
| Modular architecture | Each concern in a separate module with clear interfaces |

---

## System Architecture Summary

```
Browser <--HTTP/SSE--> Next.js :3000 <--REST/SSE--> FastAPI :8000
                                                      |
                                    +-----------------+-----------------+
                                    |                 |                 |
                              LangGraph Agent    Qdrant :6333    SQLite (WAL)
                              (3-layer graphs)   (vectors)       (metadata)
                                    |
                              Ollama :11434
                           (LLM + embedding)
```

**4 Docker services**: Qdrant, Ollama, FastAPI backend, Next.js frontend

**3-layer agent**: ConversationGraph (session) -> ResearchGraph (sub-question) -> MetaReasoningGraph (failure recovery)

**Storage**: Qdrant for vector search, SQLite for metadata/parent chunks/traces/settings/providers

See `claudedocs/architecture-design.md` for the complete system architecture specification.

---

## Success Metrics & KPIs

### Launch Criteria (Phase 1 MVP)

| Metric | Target | How to Measure |
|---|---|---|
| System starts successfully | 100% | `docker compose up` completes with all health checks passing |
| End-to-end RAG loop works | Yes | Upload PDF -> ask question -> receive cited answer |
| All 5 user stories addressed | Phase-appropriate | US1-US3 fully functional; US4-US5 partially |
| Backend test suite passes | 100% green | `pytest` with >= 60% coverage |
| Frontend renders correctly | Yes | Manual verification of all pages |

### Ongoing Quality Metrics (Post-Launch)

| Metric | Target | Frequency |
|---|---|---|
| Retrieval accuracy (top-5 hit rate) | >= 80% | Per benchmark run |
| Confidence-correctness correlation | Pearson r >= 0.6 | Per benchmark run |
| Mean query latency | < 5s (simple), < 15s (complex) | Continuous via traces |
| System uptime (self-hosted) | >= 99% during active use | Via health endpoint |
| User-reported false citations | < 5% of cited passages | Manual review |

---

## Constraints & Assumptions

### Constraints

| ID | Constraint | Rationale |
|---|---|---|
| C1 | Single-user / small-team system | SQLite write serialization; no multi-tenant isolation |
| C2 | Requires Docker and Docker Compose | Dependency management for 4 services |
| C3 | Local inference requires >= 8 GB RAM | Ollama + qwen2.5:7b minimum |
| C4 | GPU recommended but not required | Ollama runs on CPU but slower |
| C5 | Python 3.14+ for backend | Uses modern language features |
| C6 | PDF parsing limited to text-based PDFs | Scanned/image PDFs not supported in Phase 1 |
| C7 | Cross-platform: Windows 11+, macOS 13+, Linux | Docker Compose deploys identically on all 3 platforms; Rust worker must be compiled per target OS |

### Assumptions

| ID | Assumption | Risk if Wrong |
|---|---|---|
| A1 | Users have Docker installed or can install it | Blocking — no alternative deployment path in Phase 1 |
| A2 | Network available for initial model download | Blocking — Ollama needs to pull models on first start |
| A3 | Documents are primarily English text | Retrieval accuracy may degrade for non-English content |
| A4 | Qdrant REST API remains stable across minor versions | Medium — would require client updates |
| A5 | Users accept local resource usage (CPU/RAM) for privacy | Low — cloud alternative provided via US5 |

---

## Risks & Mitigations

| ID | Risk | Probability | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Ollama model download fails or is slow | Medium | High | Retry logic; clear error messaging; document minimum bandwidth |
| R2 | Qdrant OOM on large collections | Low | High | Document RAM requirements per vector count; configurable limits |
| R3 | Cross-encoder reranking too slow on CPU | Medium | Medium | Limit reranking to top-20 candidates; use small model (MiniLM-L-6) |
| R4 | SQLite write contention under concurrent ingestion | Low | Medium | WAL mode; queue ingestion jobs; serialize writes |
| R5 | LLM hallucination despite RAG context | Medium | High | GAV node (Phase 2); confidence scoring; citation validation |
| R6 | Cloud provider API changes | Low | Low | Thin adapter pattern; version-pinned SDKs |
| R7 | Docker Compose complexity for non-developers | Medium | Medium | Comprehensive README; `.env.example`; health check feedback |
| R8 | Rust worker adds build complexity | Medium | Low | Phase 1 uses Python-only; Rust is Phase 2 optimization |

---

## Release Phases & Roadmap

### Phase 1: Minimum Viable Product

**Goal**: End-to-end RAG loop in a browser, all in Python + Qdrant + Ollama.

**Scope**:
- FastAPI backend with collection, chat, document, health, and provider endpoints
- ConversationGraph + ResearchGraph (2-layer agent)
- Hybrid dense+BM25 search with cross-encoder reranking
- Parent/child chunking with breadcrumbs (Python implementation)
- SQLite metadata (collections, documents, ingestion_jobs, parent_chunks, query_traces, providers)
- Circuit breaker + retry on Qdrant/Ollama calls
- Query-adaptive retrieval depth
- Next.js frontend: /chat, /collections pages with file upload
- Ollama as default provider; OpenRouter as cloud alternative
- Fernet-encrypted API key storage
- Rate limiting and structured logging
- Docker Compose with health checks

**User Stories Covered**: US1 (full), US2 (full), US3 (full), US4 (traces created, no UI), US5 (partial — Ollama + OpenRouter)

**Status**: Implemented (spec-01 complete, 75/75 tasks done)

### Phase 2: Performance and Resilience

**Goal**: Rust ingestion worker, MetaReasoningGraph, observability UI, accuracy enhancements.

**Scope**:
- Rust ingestion worker binary (PDF, Markdown, plain text)
- NDJSON streaming from Rust to Python
- Parallel batch embedding with ThreadPoolExecutor
- Incremental ingestion (SHA256 hash-based change detection)
- MetaReasoningGraph (Layer 3): failure diagnosis, strategy switching
- Grounded Answer Verification (GAV): NLI claim checking
- Citation-Chunk Alignment validation
- Computed confidence scoring (evidence-based, not LLM self-assessment)
- /observability page: latency histogram, trace table, confidence distribution, health dashboard
- Structured logging with trace ID propagation

### Phase 3: Ecosystem and Polish

**Goal**: Additional providers, per-document chunk profiles, citation highlighting, caching.

**Scope**:
- Additional direct providers: OpenAI, Anthropic, Google AI
- Per-document-type chunk profiles (code vs prose)
- LRU cache for identical queries within session window
- Citation highlighting mapped to PDF page coordinates
- /documents/[id] enhancements (chunk count, re-ingest, history)
- Production Docker Compose optimizations
- Comprehensive test suite: unit, integration, E2E (Playwright)

---

## Dependencies

### Runtime Infrastructure

| Dependency | Version | Required | Purpose |
|---|---|---|---|
| Docker + Docker Compose | Latest | Yes | Service orchestration |
| Qdrant | Latest | Yes | Vector storage and hybrid search |
| Ollama | Latest | Yes (default) | LLM inference and embedding |
| SQLite | 3.45+ | Yes (embedded) | Metadata, parent chunks, traces |

### Backend (Python 3.14)

| Package | Version | Purpose |
|---|---|---|
| fastapi | >= 0.135 | API framework |
| uvicorn | >= 0.34 | ASGI server |
| langgraph | >= 1.0.10 | Agent graph orchestration |
| langchain | >= 1.2.10 | LLM abstraction, tool binding |
| qdrant-client | >= 1.17.0 | Qdrant client |
| sentence-transformers | >= 5.2.3 | Cross-encoder reranking |
| pydantic | >= 2.12 | Schemas and settings |
| aiosqlite | >= 0.21 | Async SQLite |
| httpx | >= 0.28 | Async HTTP client |
| cryptography | >= 44.0 | Fernet encryption |
| structlog | >= 24.0 | Structured logging |
| tenacity | >= 9.0 | Retry and circuit breaker |

### Frontend (Node.js)

| Package | Version | Purpose |
|---|---|---|
| next | 16 | React framework |
| react | 19 | UI library |
| typescript | 5.7 | Type safety |
| tailwindcss | 4 | Styling |
| recharts | 2 | Charts (observability) |
| @radix-ui/* | Latest | UI primitives |
| swr | 2 | Data fetching |

---

## Glossary

| Term | Definition |
|---|---|
| **Agentic RAG** | A RAG system where an LLM-based agent controls the retrieval loop, making decisions about which tools to call, how many retrieval rounds to perform, and when to stop |
| **BM25** | Best Matching 25 — a sparse text retrieval algorithm based on term frequency; used alongside dense vectors for hybrid search |
| **Breadcrumb** | A hierarchical path (e.g., "Chapter 2 > 2.3 Authentication > Token Formats") prepended to chunk text before embedding to encode document structure |
| **Child chunk** | A small text segment (~500 chars) embedded and stored in Qdrant for precision retrieval |
| **Circuit breaker** | A resilience pattern that stops calling a failing service after N failures, allowing it time to recover |
| **Confidence score** | A 0-100 integer computed from passage relevance scores, NOT from LLM self-assessment |
| **ConversationGraph** | Layer 1 of the agent — manages session lifecycle, intent classification, and response formatting |
| **Cross-encoder** | A model that scores (query, passage) pairs jointly for accurate relevance ranking; slower but more precise than bi-encoder matching |
| **Dense vector search** | Retrieval using embedding similarity (cosine/dot product) in a vector database |
| **Fan-out** | Decomposing a complex query into multiple sub-questions and researching them in parallel |
| **Fernet** | Symmetric encryption scheme from the `cryptography` library; used for API key storage |
| **GAV** | Grounded Answer Verification — NLI-based claim-by-claim checking of generated answers |
| **Hybrid search** | Combining dense vector retrieval with sparse BM25 retrieval using score fusion |
| **LangGraph** | A framework for building multi-step, stateful agent workflows as directed graphs |
| **MetaReasoningGraph** | Layer 3 of the agent — diagnoses retrieval failures and autonomously switches strategy |
| **NDJSON** | Newline-Delimited JSON — a streaming format where each line is a complete JSON object |
| **Parent chunk** | A larger text segment (2000-4000 chars) stored in SQLite; provides LLM context when a child chunk matches |
| **Provider** | An LLM inference service (Ollama, OpenRouter, OpenAI, Anthropic) |
| **Query trace** | A persistent record of how a query was processed: passages retrieved, scores, latency, strategy switches |
| **ResearchGraph** | Layer 2 of the agent — executes tool-based retrieval loops for individual sub-questions |
| **RRF** | Reciprocal Rank Fusion — a score combination method for merging ranked lists from different retrieval methods |
| **SSE** | Server-Sent Events — a protocol for server-to-client streaming over HTTP |
| **WAL** | Write-Ahead Logging — SQLite journal mode enabling concurrent reads with serialized writes |

---

*This PRD is derived from the system architecture design document (`claudedocs/architecture-design.md` v2.0) and the RAG analysis report (`claudedocs/rag-analysis-report.md`). For detailed technical specifications, interface contracts, and implementation guidance, refer to the architecture document.*
