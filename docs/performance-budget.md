# The Embedinator — Performance Budget

**Version**: 1.0
**Date**: 2026-03-10
**Source**: `docs/architecture-design.md` Section 17 (Performance Targets & Budgets)

---

## Target Hardware

The Embedinator is designed for and tested on this baseline developer workstation:

| Component | Specification |
|---|---|
| CPU | Intel Core i7-12700K (12 cores, 20 threads) |
| RAM | 64 GB DDR5 |
| GPU | NVIDIA RTX 4070 Ti (12 GB VRAM) |
| Storage | NVMe SSD |
| OS | Windows 11 Pro / macOS 13+ / Linux |

### Minimum Requirements

| Component | Minimum | Notes |
|---|---|---|
| RAM | 8 GB | Ollama with 7B model; no GPU offload |
| CPU | 4 cores | Cross-encoder reranking is CPU-bound |
| Disk | 10 GB free | Qdrant data + SQLite + Ollama models |
| GPU | Optional | Ollama can run on CPU (slower) |

---

## End-to-End Latency Budgets

### Chat Query — Factoid Tier (Simple Question)

| Component | Budget | Notes |
|---|---|---|
| FastAPI routing + session load | 20 ms | SQLite read |
| Intent classification (LLM) | 200 ms | Ollama, 8B model |
| Query rewriting (LLM) | 300 ms | Structured output |
| Embedding (query) | 50 ms | Ollama nomic-embed-text |
| Qdrant hybrid search | 30 ms | Dense + BM25 + RRF |
| Cross-encoder reranking (top-20) | 150 ms | CPU, ms-marco-MiniLM |
| Parent chunk retrieval | 10 ms | SQLite indexed read |
| Answer generation (LLM) | 500 ms | First token; streaming |
| Groundedness verification (LLM) | 400 ms | Separate LLM call (Phase 2) |
| Citation validation (cross-encoder) | 50 ms | 5 citation pairs (Phase 2) |
| **Total first-token latency** | **~800 ms** | Phase 1 (no GAV) |
| **Total first-token latency** | **~1.2 seconds** | Phase 2 (with GAV) |
| **Total full response** | **~2-3 seconds** | |

### Chat Query — Analytical Tier (Complex Question)

| Component | Budget | Notes |
|---|---|---|
| Query decomposition | 400 ms | 3-5 sub-questions |
| ResearchGraph per sub-question | 1-3 seconds | Multiple tool call iterations |
| MetaReasoningGraph (if triggered) | 1-2 seconds | Cross-encoder + strategy switch |
| Aggregation + verification | 600 ms | Merge + GAV |
| **Total first-token latency** | **~3-5 seconds** | |
| **Total full response** | **~5-10 seconds** | |

### API Endpoint Latency

| Endpoint | Target | Notes |
|---|---|---|
| `GET /api/health` | < 50 ms | Ping all services |
| `GET /api/collections` | < 100 ms | SQLite read |
| `POST /api/collections` | < 200 ms | SQLite write + Qdrant create |
| `DELETE /api/collections/{id}` | < 500 ms | Qdrant collection delete |
| `GET /api/settings` | < 50 ms | SQLite read |
| `GET /api/traces` | < 200 ms | SQLite read with filters |

---

## Ingestion Throughput Targets

### Phase 1 (Python Parsing)

| Document Type | Size | Target Time | Bottleneck |
|---|---|---|---|
| PDF, 10 pages | ~30 KB | < 3 seconds | Embedding API calls |
| PDF, 50 pages | ~150 KB | < 8 seconds | Embedding API calls |
| PDF, 200 pages | ~600 KB | < 15 seconds | Embedding API calls |
| Markdown, 50 KB | ~50 KB | < 5 seconds | Embedding API calls |
| Code file, 10 KB | ~10 KB | < 2 seconds | Embedding API calls |

### Phase 2 (Rust Worker)

| Metric | Target | Notes |
|---|---|---|
| PDF parsing throughput | >= 50 pages/sec | Rust worker, no GIL |
| Overall ingestion throughput | >= 10 pages/sec | Includes embedding bottleneck |
| Embedding throughput | >= 50 chunks/sec | Ollama nomic-embed-text |

---

## Memory Budgets

| Service | Budget | Notes |
|---|---|---|
| FastAPI backend (idle) | 200-400 MB | Python runtime + loaded models |
| Cross-encoder model | ~200 MB | ms-marco-MiniLM in CPU RAM |
| Per ingestion job | +100-300 MB | Chunk buffer + embedding batches |
| Per chat query | +50-100 MB | LangGraph state + retrieved chunks |
| Qdrant | 500 MB - 2 GB | Depends on total chunk count |
| Ollama (7B model) | 5-8 GB VRAM | GPU offloaded |
| Ollama (embedding model) | 1-2 GB VRAM | Can share with LLM |
| Next.js frontend | 100-200 MB | Node.js runtime |
| **Total (during query)** | **~8-12 GB** | Including Ollama model |

### Memory Scaling

| Chunks in Qdrant | Estimated Qdrant RAM | Notes |
|---|---|---|
| 10,000 | ~500 MB | Small corpus |
| 100,000 | ~1-2 GB | Medium corpus |
| 1,000,000 | ~5-10 GB | Large corpus, may need tuning |
| 10,000,000 | ~20-50 GB | At host RAM limits |

---

## Throughput Targets

| Metric | Target | Notes |
|---|---|---|
| Concurrent chat queries | 3-5 | Limited by Ollama (sequential inference) |
| Ingestion jobs | 1 at a time | Serial by design |
| Qdrant queries/second | 100+ | Limited by CPU for cross-encoder |
| SSE events/second | 50-100 | Token streaming rate |
| SQLite writes/second | 1,000+ | WAL mode, batched transactions |

---

## UI Performance

| Metric | Target | Notes |
|---|---|---|
| Chat page initial load | < 2s | Cold load including JS bundle |
| Collection list render | < 500ms | SWR cache hit |
| Document upload feedback | < 200ms | Drag-drop zone acknowledgment |
| Token rendering (streaming) | No visible lag | Progressive DOM update |
| Navigation between pages | < 300ms | Next.js client-side routing |

---

## Benchmarking Methodology

### Chat Latency Benchmark

1. Pre-index a test collection with 10 known documents (50 pages total)
2. Run 20 factoid-tier queries with known answers
3. Run 10 analytical-tier queries requiring multi-collection search
4. Measure: first-token latency, full-response latency, confidence score
5. Record in `query_traces` table for analysis

### Ingestion Benchmark

1. Prepare test documents: 10-page PDF, 50-page PDF, 200-page PDF, 50 KB markdown
2. Measure end-to-end ingestion time (upload → all chunks in Qdrant)
3. Break down: parsing time, chunking time, embedding time, upsert time

### Load Test (Optional)

1. Use `locust` or `hey` to simulate concurrent queries
2. Target: 5 concurrent chat queries without degradation
3. Measure: p50, p95, p99 latency; error rate; memory usage

---

## Optimization Levers

| Lever | Phase | Impact | Effort |
|---|---|---|---|
| Rust ingestion worker | Phase 2 | 5-20x parsing speedup | High |
| Parallel batch embedding (ThreadPoolExecutor) | Phase 2 | 2-4x embedding throughput | Medium |
| LRU query cache | Phase 3 | Eliminate redundant Qdrant calls | Low |
| Qdrant HNSW tuning (m, ef_construct) | Phase 2 | Better search precision/speed tradeoff | Low |
| Smaller cross-encoder model | Phase 1 | Faster reranking at cost of precision | Low |
| GPU-accelerated cross-encoder | Phase 3 | 10x reranking speedup | Medium |
| Ollama model quantization (Q4 vs Q8) | Phase 1 | 2x inference speed at quality cost | Low |

---

*Extracted from `docs/architecture-design.md` Section 17 (Performance Targets & Budgets).*
