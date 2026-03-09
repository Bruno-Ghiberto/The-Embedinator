# Spec 14: Performance -- Implementation Context

## Implementation Scope

Performance is a cross-cutting concern. Rather than creating new files, the implementation involves adding instrumentation and tuning to existing files.

### Files to Create

- `backend/timing.py` -- Timer context manager and timing utilities
- `tests/integration/test_performance.py` -- Performance benchmark tests

### Files to Modify

- `backend/config.py` -- Performance-tuned default values (already specified in architecture)
- `backend/storage/sqlite_db.py` -- WAL mode, busy timeout, slow query warnings
- `backend/middleware.py` -- Request-level timing (end-to-end latency capture)
- `backend/ingestion/embedder.py` -- ThreadPoolExecutor with configurable max_workers
- `backend/ingestion/pipeline.py` -- Ingestion timing, batch upsert coordination
- `backend/retrieval/reranker.py` -- Singleton model loading, inference timing
- `backend/retrieval/searcher.py` -- Search timing instrumentation
- `backend/agent/nodes.py` -- Per-node timing instrumentation
- `backend/api/chat.py` -- End-to-end query timing, query_traces population
- `backend/main.py` -- Lifespan: load cross-encoder model once at startup

## Code Specifications

### backend/timing.py

```python
"""Performance timing utilities for pipeline instrumentation."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class StageTimings:
    """Accumulates per-stage latency measurements for a single query."""

    routing_ms: float = 0
    intent_classification_ms: float = 0
    query_rewriting_ms: float = 0
    embedding_ms: float = 0
    qdrant_search_ms: float = 0
    reranking_ms: float = 0
    parent_retrieval_ms: float = 0
    answer_generation_ms: float = 0
    groundedness_ms: float = 0
    citation_validation_ms: float = 0
    total_ms: float = 0


class Timer:
    """Context manager for measuring elapsed time in milliseconds."""

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


@contextmanager
def timed(name: str, trace_id: str = ""):
    """Convenience context manager that yields a Timer."""
    timer = Timer(name, trace_id)
    with timer:
        yield timer
```

### SQLite WAL Mode and Slow Query Warning (in sqlite_db.py)

```python
async def initialize(self):
    """Initialize database connection with performance settings."""
    self.connection = await aiosqlite.connect(self.db_path)
    # WAL mode: unlimited concurrent readers, serialized writer
    await self.connection.execute("PRAGMA journal_mode=WAL")
    # 5-second timeout when database is locked by writer
    await self.connection.execute("PRAGMA busy_timeout=5000")
    # Enable memory-mapped I/O for read performance
    await self.connection.execute("PRAGMA mmap_size=268435456")  # 256 MB
    await self._run_migrations()
```

### Cross-Encoder Singleton Loading (in main.py lifespan)

```python
from contextlib import asynccontextmanager
from sentence_transformers import CrossEncoder

@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    # Load cross-encoder model once (~200 MB in CPU RAM)
    app.state.reranker = CrossEncoder(settings.reranker_model)

    # Initialize SQLite with WAL mode
    app.state.db = SQLiteDB(settings.sqlite_path)
    await app.state.db.initialize()

    # Auto-generate encryption secret if needed
    generate_secret_if_missing()

    yield

    # Cleanup
    await app.state.db.close()
```

### Request Timing Middleware (in middleware.py)

```python
class RequestTimingMiddleware:
    """Measures end-to-end request latency and logs it."""

    async def __call__(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            elapsed_ms=round(elapsed_ms, 1),
            trace_id=getattr(request.state, "trace_id", "no-trace"),
        )
        return response
```

### Performance-Tuned Config Defaults (in config.py)

```python
class Settings(BaseSettings):
    # Retrieval -- tuned for latency budgets
    top_k_retrieval: int = 20           # Cross-encoder processes at most 20 candidates
    top_k_rerank: int = 5               # Final top-5 passed to LLM
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # Fast CPU model

    # Ingestion -- tuned for throughput
    embed_batch_size: int = 16          # Texts per Ollama embedding call
    embed_max_workers: int = 4          # Parallel embedding threads
    qdrant_upsert_batch_size: int = 50  # Points per Qdrant upsert

    # Agent -- iteration caps prevent runaway latency
    max_iterations: int = 10
    max_tool_calls: int = 8
    confidence_threshold: float = 0.6
    meta_reasoning_max_attempts: int = 2
```

## Configuration

Performance budgets are enforced through configuration defaults. No separate performance-specific environment variables are needed beyond what is already in the Settings class. The defaults are tuned for the target hardware.

Key settings that affect performance:

| Setting | Value | Performance Impact |
|---------|-------|--------------------|
| `top_k_retrieval` | 20 | Limits cross-encoder to 20 candidates (~150 ms) |
| `top_k_rerank` | 5 | Reduces LLM context size |
| `embed_batch_size` | 16 | Balances Ollama throughput vs. memory |
| `embed_max_workers` | 4 | Parallel embedding threads |
| `qdrant_upsert_batch_size` | 50 | Reduces Qdrant HTTP round-trips |
| `max_iterations` | 10 | Caps agent loop to prevent runaway latency |
| `max_tool_calls` | 8 | Caps tool calls per iteration |

## Error Handling

- **Slow query detection**: SQLite queries exceeding 100 ms trigger a WARNING log with the query text and elapsed time.
- **Timeout on LLM calls**: If Ollama does not respond within the expected budget (e.g., 2x the budget), the circuit breaker (from Spec 8) trips and returns a degraded response.
- **Memory pressure**: If the process exceeds expected memory usage, log a WARNING. No automatic mitigation (single-user system; user can restart).
- **Ingestion timeout**: If a single document ingestion exceeds 60 seconds, log a WARNING and continue (do not abort).

## Testing Requirements

### Performance Benchmark Tests (tests/integration/test_performance.py)

These tests require a running Qdrant and Ollama instance and are marked with `@pytest.mark.slow`.

1. `test_factoid_query_first_token_latency` -- End-to-end chat query with a pre-indexed collection. Assert first SSE token arrives within 3 seconds (relaxed threshold for CI).
2. `test_qdrant_search_latency` -- Execute 100 vector searches against a test collection. Assert p95 latency is under 50 ms.
3. `test_cross_encoder_reranking_latency` -- Rerank 20 candidates. Assert latency is under 300 ms (2x budget for CI margin).
4. `test_sqlite_wal_concurrent_reads` -- Execute 10 concurrent read queries while a write is in progress. Assert no `database is locked` errors.
5. `test_ingestion_throughput` -- Ingest a 3-page test PDF. Assert completion within 5 seconds.
6. `test_sse_streaming_rate` -- Mock an LLM response and verify SSE events are delivered at >= 30 events/second.

### Unit Tests

1. `test_timer_measures_elapsed` -- Timer context manager correctly reports elapsed milliseconds.
2. `test_stage_timings_dataclass` -- StageTimings accumulates values correctly.

## Done Criteria

- [ ] SQLite WAL mode is enabled on database initialization
- [ ] `Timer` context manager is implemented and used to instrument all major pipeline stages
- [ ] Cross-encoder model is loaded once at application startup via lifespan handler
- [ ] Per-stage latencies are stored in `query_traces` table after each chat query
- [ ] Slow SQLite queries (>100 ms) generate WARNING log entries
- [ ] `ThreadPoolExecutor` is used for parallel embedding batches with configurable worker count
- [ ] Qdrant upserts use batch mode (50 points per call)
- [ ] SSE streaming delivers tokens without artificial buffering delays
- [ ] Configuration defaults match the performance budget targets
- [ ] Performance benchmark tests exist and pass on target hardware
