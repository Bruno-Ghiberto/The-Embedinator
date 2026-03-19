# Spec 14: Performance — Feature Specification Context

## Feature Description

The Performance specification defines concrete latency budgets, memory budgets, throughput targets, and resource allocation constraints for The Embedinator. These are not aspirational goals but measurable thresholds that guide implementation choices, configuration defaults, and monitoring alerts. The system is designed for a single developer workstation with specific hardware (Intel i7-12700K, 64 GB RAM, RTX 4070 Ti with 12 GB VRAM, NVMe SSD).

---

## Already Implemented — Do NOT Reimplement

The following components are fully built and must not be re-implemented by spec-14 agents. Spec-14 concerns itself with measurement, budgeting, and instrumentation only.

### Rust Ingestion Worker — `ingestion-worker/` (spec-06)

The Rust binary is fully implemented: PDF parsing via `pdf-extract`, Markdown parsing via `pulldown-cmark`, NDJSON output to stdout. It provides 5-20x throughput improvement over Python for CPU-bound PDF parsing, and overlaps CPU parsing with network I/O via its NDJSON streaming interface. **Do not rewrite any part of this binary.**

### Storage Layer — `backend/storage/` (spec-07)

`SQLiteDB` is fully implemented with WAL mode enabled, all 7 tables created, and full CRUD. The `query_traces` table already includes a `latency_ms` column storing total end-to-end latency per query. `QdrantStorage` is fully implemented with hybrid dense+BM25 search via `client.query_points()`. **Do not add new tables or columns without explicit instruction.**

### FastAPI Routing Layer — `backend/api/` (spec-08)

All API endpoints are fully implemented: `backend/api/chat.py`, `backend/api/ingest.py`, `backend/api/documents.py`, `backend/api/collections.py`, `backend/api/providers.py`, `backend/api/models.py`, `backend/api/settings.py`. **Do not add new endpoints unless explicitly required by a functional requirement in this spec.**

### NDJSON Streaming — `backend/api/chat.py` (spec-08)

The chat endpoint streams responses using NDJSON (newline-delimited JSON), not SSE (Server-Sent Events). Each line is a JSON object followed by `\n`. The 10 event types (`thinking`, `chunk`, `citations`, `confidence`, `done`, `error`, `clarification`, `rewriting`, `researching`, `meta_reasoning`) are already implemented. **Do not convert to SSE. Do not add new event types without explicit instruction.**

### Next.js Frontend — `frontend/` (spec-09)

All UI components are fully implemented: chat interface, document upload, collection management, settings, provider configuration, trace viewer. **Do not modify frontend components unless explicitly required.**

### Circuit Breaker and Retry — `backend/` (spec-05)

Circuit breakers and `tenacity` retry decorators already wrap all external calls to Ollama and Qdrant. These are the primary mechanisms preventing runaway latency from infrastructure failures. **Do not add additional retry layers.**

---

## Functional Requirements (Spec-14 Scope Only)

### FR-001: Latency Budget Enforcement

Each component in the chat query pipeline must operate within its assigned latency budget (see Factoid and Analytical Tier tables below). The total first-token latency for a factoid query (Phase 2, with Groundedness and Attribution Verification) must not exceed approximately 1.2 seconds on target hardware.

This FR is a **design constraint and configuration target**, not a runtime enforcement mechanism. Implementation means choosing configuration defaults (see Architecture Reference) that keep each component within budget.

### FR-002: Ingestion Throughput Targets

Document ingestion must meet throughput targets (see Ingestion Throughput Targets table below). The Rust worker (Phase 2) handles PDF parsing throughput; the Python pipeline handles embedding throughput via `BatchEmbedder` with `embed_batch_size=16` and `embed_max_workers=4`.

### FR-003: Memory Budget Compliance

Each service must operate within its assigned memory budget during normal use (see Memory Budgets table below). Memory budgets are guidelines, not hard limits enforced at runtime. Exceeding a budget triggers monitoring warnings in Spec 15.

### FR-004: Concurrent Query Support

The system must handle 3–5 concurrent chat queries without crashing or timing out. Concurrency is limited by Ollama's sequential inference model. The FastAPI async event loop and LangGraph state isolation ensure concurrent queries do not corrupt each other's state.

### FR-005: Performance Monitoring (Per-Stage Instrumentation)

**Scoping note — what already exists vs. what is new work:**

- **EXISTING** (`backend/storage/sqlite_db.py`, spec-07): `query_traces.latency_ms` stores total end-to-end latency (wall clock from request receipt to final NDJSON `done` event). This is already implemented and must not be changed.
- **NEW WORK (spec-14)**: Add per-stage timing instrumentation to LangGraph nodes in `backend/agent/` (conversation, research, meta-reasoning). Record timing breakdowns as a structured JSON object and store it alongside the existing `latency_ms` total. The storage field for per-stage data is `query_traces.reasoning_steps_json` (already exists as a column, currently stores reasoning steps — spec-14 must decide whether to extend this column or add a new `stage_timings_json` column).

Per-stage measurements must cover at minimum: intent classification, query rewriting, embedding, Qdrant search, reranking, parent chunk retrieval, answer generation, GAV (if executed).

---

## Non-Functional Requirements

- Budgets are defined for the primary target hardware; performance on lesser hardware degrades gracefully.
- Ollama is the primary bottleneck. The system architecture must ensure non-LLM components do not add unnecessary latency.
- Memory budgets are guidelines, not hard limits enforced at runtime. Exceeding them triggers monitoring warnings (Spec 15).
- NDJSON token streaming must deliver 50–100 events per second for smooth UI rendering.
- No new pip dependencies are required for performance instrumentation. Use Python stdlib `time.perf_counter()` for timing.

---

## Key Technical Details

### Target Hardware

| Component | Specification |
|-----------|---------------|
| CPU | Intel Core i7-12700K (12 cores, 20 threads) |
| RAM | 64 GB DDR5 |
| GPU | NVIDIA RTX 4070 Ti (12 GB VRAM) |
| Storage | NVMe SSD |
| OS | Windows 11 Pro / macOS 13+ / Linux |

### Minimum Requirements (for running the system at all)

| Component | Minimum | Notes |
|-----------|---------|-------|
| RAM | 8 GB | Ollama with 7B model; no GPU offload |
| CPU | 4 cores | Cross-encoder reranking is CPU-bound |
| Disk | 10 GB free | Qdrant data + SQLite + Ollama models |
| GPU | Optional | Ollama can run on CPU (slower) |

---

### End-to-End Latency Budgets — Factoid Tier

The factoid tier covers simple single-hop questions handled by the ConversationGraph without triggering ResearchGraph or MetaReasoningGraph.

#### Phase 1 (no GAV — for reference only, already superseded)

| Component | Budget | Notes |
|-----------|--------|-------|
| FastAPI routing + session load | 20 ms | SQLite read |
| Intent classification (LLM) | 200 ms | Ollama, 7B model |
| Query rewriting (LLM) | 300 ms | Structured output |
| Embedding (query) | 50 ms | Ollama nomic-embed-text |
| Qdrant hybrid search | 30 ms | Dense + BM25 + RRF |
| Cross-encoder reranking (top-20) | 150 ms | CPU, ms-marco-MiniLM |
| Parent chunk retrieval | 10 ms | SQLite indexed read |
| Answer generation (LLM) | 500 ms | First token; streaming |
| **Total first-token latency** | **~800 ms** | No GAV |
| **Total full response** | **~1.5-2 seconds** | |

#### Phase 2 (with GAV — current implementation)

| Component | Budget | Notes |
|-----------|--------|-------|
| FastAPI routing + session load | 20 ms | SQLite read |
| Intent classification (LLM) | 200 ms | Ollama, 7B model |
| Query rewriting (LLM) | 300 ms | Structured output |
| Embedding (query) | 50 ms | Ollama nomic-embed-text |
| Qdrant hybrid search | 30 ms | Dense + BM25 + RRF |
| Cross-encoder reranking (top-20) | 150 ms | CPU, ms-marco-MiniLM |
| Parent chunk retrieval | 10 ms | SQLite indexed read |
| Answer generation (LLM) | 500 ms | First token; streaming |
| Groundedness verification (LLM) | 400 ms | Separate LLM call |
| Citation validation (cross-encoder) | 50 ms | 5 citation pairs |
| **Total first-token latency** | **~1.2 seconds** | With GAV |
| **Total full response** | **~2-3 seconds** | |

---

### End-to-End Latency Budgets — Analytical Tier

| Component | Budget | Notes |
|-----------|--------|-------|
| Query decomposition | 400 ms | 3-5 sub-questions |
| ResearchGraph per sub-question | 1-3 seconds | Multiple tool call iterations |
| MetaReasoningGraph (if triggered) | 1-2 seconds | Cross-encoder + strategy switch |
| Aggregation + verification | 600 ms | Merge + GAV |
| **Total first-token latency** | **~3-5 seconds** | |
| **Total full response** | **~5-10 seconds** | |

---

### API Endpoint Latency Targets

| Endpoint | Target | Notes |
|----------|--------|-------|
| `GET /api/health` | < 50 ms | Ping all services |
| `GET /api/collections` | < 100 ms | SQLite read |
| `POST /api/collections` | < 200 ms | SQLite write + Qdrant create |
| `DELETE /api/collections/{id}` | < 500 ms | Qdrant collection delete |
| `GET /api/settings` | < 50 ms | SQLite read |
| `GET /api/traces` | < 200 ms | SQLite read with filters |

---

### UI Performance Targets

| Interaction | Target | Notes |
|-------------|--------|-------|
| Chat page initial load | < 2 s | Cold load including JS bundle |
| Collection list render | < 500 ms | SWR cache hit |
| Document upload feedback | < 200 ms | Drag-drop zone acknowledgment |
| Token rendering (streaming) | No visible lag | Progressive DOM update |
| Navigation between pages | < 300 ms | Next.js client-side routing |

---

### Ingestion Throughput Targets (Phase 1 Python Pipeline)

| Document Type | Size | Target Time | Bottleneck |
|--------------|------|-------------|------------|
| PDF, 10 pages | ~30 KB | < 3 seconds | Embedding API calls |
| PDF, 50 pages | ~150 KB | < 8 seconds | Embedding API calls |
| PDF, 200 pages | ~600 KB | < 15 seconds | Embedding API calls |
| Markdown, 50 KB | ~50 KB | < 5 seconds | Embedding API calls |
| Code file, 10 KB | ~10 KB | < 2 seconds | Embedding API calls |

### Ingestion Throughput Targets (Phase 2 Rust Worker)

| Metric | Target | Notes |
|--------|--------|-------|
| PDF parsing throughput | >= 50 pages/sec | Rust worker, no GIL |
| Overall ingestion throughput | >= 10 pages/sec | Includes embedding bottleneck |
| Embedding throughput | >= 50 chunks/sec | Ollama nomic-embed-text |

---

### Memory Budgets

| Service | Budget | Notes |
|---------|--------|-------|
| FastAPI backend (idle) | 200-400 MB | Python runtime + loaded models |
| Cross-encoder model | ~200 MB | ms-marco-MiniLM loaded in CPU RAM |
| Per ingestion job | +100-300 MB | Chunk buffer + embedding batches |
| Per chat query | +50-100 MB | LangGraph state + retrieved chunks |
| Qdrant | 500 MB - 2 GB | Depends on total chunk count |
| Ollama (7B model) | 5-8 GB VRAM | GPU offloaded |
| Ollama (embedding model) | 1-2 GB VRAM | Can share with LLM |
| Next.js frontend | 100-200 MB | Node.js runtime |
| **Total (during query)** | **~8-12 GB** | Including Ollama model |

### Memory Scaling by Corpus Size (Qdrant)

| Corpus Size | Qdrant Memory | Notes |
|-------------|---------------|-------|
| 10,000 chunks | ~500 MB | Small corpus |
| 100,000 chunks | ~1-2 GB | Medium corpus |
| 1,000,000 chunks | ~5-10 GB | Large corpus, may need tuning |
| 10,000,000 chunks | ~20-50 GB | At host RAM limits |

---

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent chat queries | 3-5 | Limited by Ollama (sequential inference) |
| Ingestion jobs | 1 at a time | Serial by design (single Rust worker) |
| Qdrant queries/second | 100+ | Limited by CPU for cross-encoder |
| NDJSON events/second | 50-100 | Token streaming rate |
| SQLite writes/second | 1,000+ | WAL mode, batched transactions |

---

### Benchmarking Methodology

Performance claims in this spec must be verified against target hardware using the following benchmark procedures.

#### Chat Latency Benchmark

1. Warm up the system: send 5 chat queries and discard results (ensures Ollama model is loaded, SQLite WAL is active, Qdrant index is warm).
2. Send 20 factoid-tier queries against a collection containing at least 1,000 chunks.
3. Measure time from HTTP request send to receipt of the first NDJSON `chunk` event.
4. Report P50, P90, P99 latency.
5. Pass condition: P90 <= 1.5 seconds.

#### Ingestion Benchmark

1. Prepare a 10-page PDF and a 200-page PDF.
2. POST each to `/api/collections/{id}/ingest` and poll `/api/documents/{id}` until `status = "completed"`.
3. Measure wall-clock time from POST to `status = "completed"`.
4. Pass condition: 10-page PDF < 3 seconds, 200-page PDF < 15 seconds.

#### Concurrent Load Test

1. Use `asyncio.gather` or `httpx.AsyncClient` to send 3 chat queries simultaneously.
2. Measure that all 3 complete without HTTP 500 or timeout.
3. Pass condition: all 3 queries return a `done` NDJSON event within 30 seconds.

---

### Optimization Levers

| Lever | Phase | Impact | Effort |
|-------|-------|--------|--------|
| Reduce `top_k_retrieval` (20 → 10) | Phase 1 | -75 ms reranking | Low |
| Enable GPU cross-encoder (`device="cuda"`) | Phase 1/2 | -100 ms reranking | Medium |
| Increase `embed_batch_size` (16 → 32) | Phase 2 | +20% embedding throughput | Low |
| Add Qdrant on-disk payload index | Phase 2 | -5 ms search | Medium |
| Use quantized Ollama model (Q4_K_M) | Any | -1-2 GB VRAM, slight quality loss | Low |
| Enable SQLite `PRAGMA cache_size` | Any | -2 ms SQLite reads | Low |
| Add Redis for session cache | Phase 3 | -20 ms per query | High |

---

## Dependencies

- **Internal**:
  - Spec 15 (Observability — `backend/observability/` — latency metrics collection and alerting)
  - Spec 02 (Conversation Graph — `backend/agent/conversation_graph.py` — FastAPI routing overhead and LangGraph node timing)
  - Spec 03 (Research Graph — `backend/agent/research_graph.py` — multi-hop query latency)
  - Spec 06 (Ingestion Pipeline — `backend/ingestion/pipeline.py`, `ingestion-worker/` — Rust worker throughput)
  - Spec 07 (Storage — `backend/storage/sqlite_db.py`, `backend/storage/qdrant.py` — search and reranking timing)
  - Spec 08 (API Reference — `backend/api/chat.py` — NDJSON streaming and FastAPI routing)
- **Infrastructure**: Ollama (LLM/embedding inference), Qdrant (vector search), SQLite with WAL mode
- **Libraries**: `sentence-transformers>=5.2.3` (cross-encoder model loading), `tenacity>=9.0` (retry logic that affects latency)

---

## Acceptance Criteria

1. A factoid-tier chat query returns its first NDJSON `chunk` token within 1.5 seconds on target hardware (allowing 25% margin over the 1.2-second Phase 2 budget).
2. An analytical-tier chat query returns its first NDJSON `chunk` token within 6 seconds on target hardware.
3. Ingesting a 10-page PDF completes (status = "completed") in under 3 seconds (Phase 2 with Rust worker).
4. Ingesting a 200-page PDF completes (status = "completed") in under 15 seconds (Phase 2 with Rust worker).
5. The backend process uses less than 600 MB RAM at idle (including cross-encoder model, excluding Ollama).
6. NDJSON token streaming delivers at least 50 events/second during answer generation.
7. SQLite writes during ingestion sustain 1,000+ rows/second with WAL mode enabled.
8. The system handles 3 concurrent chat queries without crashing or timing out.
9. Total end-to-end latency per query is recorded in `query_traces.latency_ms` (already implemented — verify it is populated on each query).
10. Per-stage timing breakdowns (intent classification, embedding, search, reranking, answer generation, GAV) are stored as structured JSON in `query_traces` for each query.

---

## Architecture Reference

Performance budgets influence configuration defaults in `backend/config.py`:

```python
# Retrieval -- tuned for latency budget
top_k_retrieval: int = 20          # Limits cross-encoder reranking to 20 candidates
top_k_rerank: int = 5              # Final top-5 after reranking
reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Chosen for CPU speed

# Ingestion -- tuned for throughput
embed_batch_size: int = 16         # Ollama embedding batch size
embed_max_workers: int = 4         # ThreadPoolExecutor parallelism
qdrant_upsert_batch_size: int = 50 # Qdrant batch upsert size

# Agent -- iteration limits prevent runaway latency
max_iterations: int = 10
max_tool_calls: int = 8
```

The Rust ingestion worker (Phase 2) provides 5-20x throughput improvement over Python for CPU-bound PDF parsing. The NDJSON streaming interface allows Python to begin embedding chunk N while Rust extracts chunk N+5, overlapping CPU parsing and network I/O.

Relevant files for this spec:

| File | Role in spec-14 |
|------|-----------------|
| `backend/config.py` | Configuration defaults tuned for latency and throughput budgets |
| `backend/agent/conversation_graph.py` | FR-005: add per-stage timing instrumentation |
| `backend/agent/research_graph.py` | FR-005: add per-stage timing instrumentation |
| `backend/agent/nodes.py` | FR-005: add `time.perf_counter()` calls around LLM invocations |
| `backend/storage/sqlite_db.py` | FR-005: `query_traces.latency_ms` already exists; per-stage storage TBD |
| `backend/retrieval/searcher.py` | Reference only — search latency already within budget |
| `backend/retrieval/reranker.py` | Reference only — reranking latency already within budget |
| `ingestion-worker/` | Reference only — Rust worker throughput already implemented |

## Out of Scope for Spec-14

- Runtime latency enforcement (hard timeouts per pipeline stage) — these would require significant LangGraph instrumentation and are deferred to a future spec.
- Horizontal scaling, load balancing, or distributed deployment — this is a single-node developer system.
- GPU cross-encoder inference — the reranker uses CPU by design (`ms-marco-MiniLM-L-6-v2` is fast enough on CPU).
- Redis or external caching layers — SQLite WAL mode is sufficient for the target query volume.
- Profiling or flame graph tooling integration — use Python's stdlib `time.perf_counter()` for instrumentation.
- Frontend bundle size optimization — Next.js build defaults are sufficient for the target use case.
