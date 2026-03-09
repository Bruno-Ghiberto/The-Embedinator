# Spec 14: Performance -- Feature Specification Context

## Feature Description

The Performance specification defines concrete latency budgets, memory budgets, throughput targets, and resource allocation constraints for The Embedinator. These are not aspirational goals but measurable thresholds that guide implementation choices, configuration defaults, and monitoring alerts. The system is designed for a single developer workstation with specific hardware (Intel i7-12700K, 64 GB RAM, RTX 4070 Ti with 12 GB VRAM, NVMe SSD).

## Requirements

### Functional Requirements

1. **Latency Budget Enforcement**: Each component in the chat query pipeline must operate within its assigned latency budget. The total first-token latency for a factoid query must be approximately 1.2 seconds.
2. **Ingestion Throughput**: Document ingestion must meet throughput targets (e.g., 10-page PDF in under 3 seconds, 200-page PDF in under 15 seconds).
3. **Memory Budget Compliance**: Each service must stay within its assigned memory budget during normal operation.
4. **Concurrent Query Support**: The system must support 3-5 concurrent chat queries, limited by Ollama sequential inference.
5. **Performance Monitoring**: Latency measurements must be collected at each pipeline stage and stored in `query_traces` for observability.

### Non-Functional Requirements

- Budgets are defined for the target hardware specification; performance on lesser hardware degrades gracefully.
- Ollama is the primary bottleneck; the system architecture must ensure non-LLM components do not add unnecessary latency.
- Memory budgets are guidelines, not hard limits; exceeding them triggers monitoring warnings.
- SSE token streaming must deliver 50-100 events per second for smooth UI rendering.

## Key Technical Details

### Target Hardware

| Component | Specification |
|-----------|-------------|
| CPU | Intel Core i7-12700K (12 cores, 20 threads) |
| RAM | 64 GB DDR5 |
| GPU | NVIDIA RTX 4070 Ti (12 GB VRAM) |
| Storage | NVMe SSD |
| OS | Windows 11 Pro |

### End-to-End Latency Budgets -- Factoid Tier

| Component | Budget | Notes |
|-----------|--------|-------|
| FastAPI routing + session load | 20 ms | SQLite read |
| Intent classification (LLM) | 200 ms | Ollama, 8B model |
| Query rewriting (LLM) | 300 ms | Structured output |
| Embedding (query) | 50 ms | Ollama nomic-embed-text |
| Qdrant hybrid search | 30 ms | Dense + BM25 + RRF |
| Cross-encoder reranking (top-20) | 150 ms | CPU, ms-marco-MiniLM |
| Parent chunk retrieval | 10 ms | SQLite indexed read |
| Answer generation (LLM) | 500 ms | First token; streaming |
| Groundedness verification (LLM) | 400 ms | Separate LLM call |
| Citation validation (cross-encoder) | 50 ms | 5 citation pairs |
| **Total first-token latency** | **~1.2 seconds** | |
| **Total full response** | **~2-3 seconds** | |

### End-to-End Latency Budgets -- Analytical Tier

| Component | Budget | Notes |
|-----------|--------|-------|
| Query decomposition | 400 ms | 3-5 sub-questions |
| ResearchGraph per sub-question | 1-3 seconds | Multiple tool call iterations |
| MetaReasoningGraph (if triggered) | 1-2 seconds | Cross-encoder + strategy switch |
| Aggregation + verification | 600 ms | Merge + GAV |
| **Total first-token latency** | **~3-5 seconds** | |
| **Total full response** | **~5-10 seconds** | |

### Ingestion Throughput Targets

| Document Type | Size | Target Time | Bottleneck |
|--------------|------|-------------|-----------|
| PDF, 10 pages | ~30 KB | < 3 seconds | Embedding API calls |
| PDF, 50 pages | ~150 KB | < 8 seconds | Embedding API calls |
| PDF, 200 pages | ~600 KB | < 15 seconds | Embedding API calls |
| Markdown, 50 KB | ~50 KB | < 5 seconds | Embedding API calls |
| Code file, 10 KB | ~10 KB | < 2 seconds | Embedding API calls |

### Memory Budgets

| Service | Budget | Notes |
|---------|--------|-------|
| FastAPI backend (idle) | 200-400 MB | Python runtime + loaded models |
| Cross-encoder model | ~200 MB | ms-marco-MiniLM loaded in CPU RAM |
| Per ingestion job | +100-300 MB | Chunk buffer + embedding batches |
| Per chat query | +50-100 MB | LangGraph state + retrieved chunks |
| Qdrant | 500 MB - 2 GB | Depends on total chunk count |
| Ollama (8B model) | 5-8 GB VRAM | GPU offloaded |
| Ollama (embedding model) | 1-2 GB VRAM | Can share with LLM |
| Next.js frontend | 100-200 MB | Node.js runtime |
| **Total (during query)** | **~8-12 GB** | Excluding Ollama model |

### Throughput Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent chat queries | 3-5 | Limited by Ollama (sequential inference) |
| Ingestion jobs | 1 at a time | Serial by design (single Rust worker) |
| Qdrant queries/second | 100+ | Limited by CPU for cross-encoder |
| SSE events/second | 50-100 | Token streaming rate |
| SQLite writes/second | 1,000+ | WAL mode, batched transactions |

## Dependencies

- **Internal**: Spec 15 (Observability -- latency metrics collection and storage), Spec 2 (API Layer -- FastAPI routing overhead), Spec 3 (Agent -- LangGraph node timing), Spec 5 (Ingestion -- Rust worker throughput), Spec 7 (Retrieval -- search and reranking timing)
- **Infrastructure**: Ollama (LLM/embedding inference), Qdrant (vector search), SQLite with WAL mode
- **Libraries**: `sentence-transformers>=5.2.3` (cross-encoder model loading), `tenacity>=9.0` (retry logic that affects latency)

## Acceptance Criteria

1. A factoid-tier chat query returns its first SSE token within 1.5 seconds on target hardware (allowing 25% margin over the 1.2-second budget).
2. An analytical-tier chat query returns its first SSE token within 6 seconds on target hardware.
3. Ingesting a 10-page PDF completes in under 3 seconds (Phase 2 with Rust worker).
4. Ingesting a 200-page PDF completes in under 15 seconds (Phase 2 with Rust worker).
5. The backend process uses less than 600 MB RAM at idle (including cross-encoder model).
6. SSE token streaming delivers at least 50 events/second during answer generation.
7. SQLite writes during ingestion sustain 1,000+ rows/second with WAL mode enabled.
8. The system handles 3 concurrent chat queries without crashing or timing out.
9. Each pipeline stage's latency is recorded in the `query_traces` table for monitoring.

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
