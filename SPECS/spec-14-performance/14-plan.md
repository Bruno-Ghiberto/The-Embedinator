# Spec 14: Performance -- Implementation Plan Context

## Component Overview

The Performance specification is not a single component but a cross-cutting set of constraints that guide implementation decisions across every spec. This plan defines how to instrument the system for performance measurement, establish configuration defaults that meet latency budgets, and create performance testing infrastructure to validate compliance.

## Technical Approach

### Latency Measurement

- Instrument each pipeline stage with timing wrappers that record elapsed milliseconds.
- Use Python's `time.perf_counter()` for high-resolution timing within async functions.
- Store per-stage latencies as structured fields in the `query_traces` SQLite table.
- Use `structlog` to log per-stage timings at INFO level with trace ID correlation.

### Configuration Tuning

- Set default values in `backend/config.py` that optimize for the latency budget (e.g., `top_k_retrieval=20` to keep cross-encoder reranking under 150 ms).
- Use `ThreadPoolExecutor` with `embed_max_workers=4` for parallel embedding batches.
- Set `embed_batch_size=16` to balance Ollama throughput with memory usage.
- Enable SQLite WAL mode on database initialization to support concurrent reads.

### Resource Management

- Load the cross-encoder model once at application startup and keep it in memory (~200 MB).
- Avoid loading large models per-request; use singleton patterns for model instances.
- Ensure ingestion jobs run serially (one at a time) to prevent memory spikes.
- Use streaming responses (SSE) to deliver tokens incrementally, avoiding full-response buffering.

### Throughput Optimization for Ingestion

- Phase 1: Python-based chunking and embedding with serial pipeline.
- Phase 2: Rust worker for PDF parsing with NDJSON streaming. Python begins embedding as chunks arrive from Rust, overlapping CPU-bound parsing and network I/O embedding.
- Batch Qdrant upserts (50 points per batch) to reduce HTTP round-trips.

## File Structure

Performance concerns are distributed across the codebase. There is no single "performance" module, but the following files are most affected:

```
backend/
  config.py                      # Default values tuned for performance budgets
  middleware.py                   # Request timing (latency measurement)
  storage/
    sqlite_db.py                 # WAL mode, query_traces writes, slow query warnings
  retrieval/
    reranker.py                  # Cross-encoder model loading and inference timing
    searcher.py                  # Qdrant search timing
  ingestion/
    pipeline.py                  # Ingestion timing, batch coordination
    embedder.py                  # ThreadPoolExecutor batch embedding
  agent/
    nodes.py                     # Per-node timing
  api/
    chat.py                      # End-to-end query timing, SSE streaming rate
    traces.py                    # query_traces storage
tests/
  integration/
    test_performance.py          # Performance benchmarks (NEW FILE)
```

## Implementation Steps

1. **Enable SQLite WAL mode**: In `sqlite_db.py` initialization, execute `PRAGMA journal_mode=WAL` to support concurrent reads and high write throughput.
2. **Implement timing decorators/context managers**: Create a `Timer` context manager or decorator that uses `time.perf_counter()` and logs elapsed time to structlog with the trace ID.
3. **Instrument pipeline stages**: Wrap each major operation (embedding, search, reranking, LLM calls, parent chunk retrieval) with timing instrumentation.
4. **Store latencies in query_traces**: After each chat query completes, write a row to `query_traces` with per-stage latency fields.
5. **Configure ThreadPoolExecutor**: In `embedder.py`, use `ThreadPoolExecutor(max_workers=settings.embed_max_workers)` for parallel embedding batches.
6. **Singleton model loading**: Load the cross-encoder model in the application lifespan handler and inject it via FastAPI dependency injection. Do not load per-request.
7. **Batch Qdrant upserts**: In the ingestion pipeline, accumulate points and upsert in batches of `settings.qdrant_upsert_batch_size`.
8. **SSE streaming rate**: Ensure the chat endpoint's SSE generator yields tokens as they arrive from LangGraph's `astream_events()` without artificial buffering.
9. **Add slow query warnings**: In `sqlite_db.py`, log a WARNING for any SQLite query exceeding 100 ms.
10. **Create performance benchmarks**: Write integration tests that measure and assert against latency/throughput targets.

## Integration Points

- **Observability (Spec 15)**: Performance measurements feed directly into the observability page's latency histograms and the `query_traces` table.
- **Agent (Spec 3)**: Node timing instrumentation in `nodes.py` provides per-stage latency data.
- **Retrieval (Spec 7)**: Cross-encoder model loading strategy (singleton vs. per-request) directly impacts latency and memory.
- **Ingestion (Spec 5)**: Rust worker throughput and batch embedding parallelism determine ingestion speed.
- **Infrastructure (Spec 17)**: Docker resource allocation (GPU passthrough, memory limits) must accommodate the memory budget.

## Key Code Patterns

### Timer Context Manager

```python
import time
import structlog

logger = structlog.get_logger(__name__)

class Timer:
    """Context manager for measuring elapsed time."""

    def __init__(self, name: str, trace_id: str = ""):
        self.name = name
        self.trace_id = trace_id
        self.elapsed_ms: float = 0

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, *args):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
        logger.info(
            f"{self.name} completed",
            elapsed_ms=round(self.elapsed_ms, 1),
            trace_id=self.trace_id,
        )
```

### SQLite WAL Mode

```python
# In sqlite_db.py initialize()
await self.connection.execute("PRAGMA journal_mode=WAL")
await self.connection.execute("PRAGMA busy_timeout=5000")
```

### Singleton Cross-Encoder Loading

```python
# In main.py lifespan
from sentence_transformers import CrossEncoder

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load once at startup
    app.state.reranker = CrossEncoder(settings.reranker_model)
    yield
    # Cleanup
    del app.state.reranker
```

### Batch Embedding with ThreadPoolExecutor

```python
from concurrent.futures import ThreadPoolExecutor

class BatchEmbedder:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Split into sub-batches and process in parallel
        ...
```

## Phase Assignment

- **Phase 1 (MVP)**: Basic timing instrumentation, SQLite WAL mode, configuration defaults tuned for budgets, singleton cross-encoder loading, serial ingestion pipeline with batch embedding.
- **Phase 2 (Performance and Resilience)**: Rust worker integration (5-20x ingestion speedup), parallel batch embedding with ThreadPoolExecutor, full `query_traces` population with per-stage latencies, structured logging of all timings.
- **Phase 3 (Ecosystem and Polish)**: Performance benchmarking test suite, LRU cache for identical queries, per-document-type chunk profiles for optimized ingestion, comprehensive monitoring thresholds.
