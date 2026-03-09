# Spec 15: Observability -- Feature Specification Context

## Feature Description

The Observability layer for The Embedinator provides full-stack visibility into the RAG pipeline through structured logging, trace ID propagation, metrics collection, and a dedicated `/observability` page in the frontend. Every HTTP request generates a UUID4 trace ID that propagates through all backend function calls, enabling end-to-end correlation of logs and stored query traces. The `query_traces` SQLite table captures per-query performance and quality data that feeds the observability dashboard.

## Requirements

### Functional Requirements

1. **Structured Logging**: All backend logs must use JSON Lines format via `structlog`. Each log entry includes `timestamp`, `level`, `logger`, `message`, `trace_id`, `session_id`, and a `data` object with context-specific fields.
2. **Trace ID Propagation**: Every HTTP request generates a UUID4 trace ID in FastAPI middleware. This ID propagates through all downstream function calls via Python `contextvars` and is returned in the `X-Trace-ID` response header.
3. **Query Traces Table**: The `query_traces` SQLite table stores per-query data: trace ID, session ID, query text, collections searched, latency, confidence score, meta-reasoning trigger flag, chunks retrieved with scores, and timestamps.
4. **Metrics Collection**: The system must collect histogram metrics (query latency, ingestion latency, embedding latency, search latency, reranker latency, LLM latency, confidence scores), counters (meta-reasoning triggers, errors by type), and gauges (circuit breaker state, active ingestion jobs, cache hit rate).
5. **Health Check Endpoint**: `GET /api/health` must ping Qdrant, Ollama, and SQLite and return aggregate health status.
6. **Observability Page**: The frontend `/observability` page displays latency histogram, confidence distribution chart, meta-reasoning rate, service health status, collection statistics, and a paginated trace log with expandable detail.

### Non-Functional Requirements

- Logging overhead must be negligible (microseconds per log entry).
- Trace ID generation and propagation must add less than 1 ms to request latency.
- The `query_traces` write must not block the response to the user (can be done after SSE completes or asynchronously).
- Log level is configurable per component via environment variables.
- Debug-level logging must not be enabled by default in production (it includes full prompt text and LLM raw responses).

## Key Technical Details

### Structured Log Format (JSON Lines)

```json
{
  "timestamp": "2026-03-03T10:32:15.123Z",
  "level": "INFO",
  "logger": "backend.agent.nodes",
  "message": "Groundedness verification completed",
  "trace_id": "req-abc-123",
  "session_id": "sess-xyz-789",
  "data": {
    "supported_claims": 4,
    "unsupported_claims": 1,
    "contradicted_claims": 0,
    "elapsed_ms": 380
  }
}
```

### Log Levels by Component

| Component | Default Level | Debug Level Enables |
|-----------|--------------|-------------------|
| `backend.api.*` | INFO | Request/response bodies, headers |
| `backend.agent.nodes` | INFO | Full prompt text, LLM raw responses |
| `backend.agent.tools` | INFO | Qdrant query details, chunk text snippets |
| `backend.ingestion.pipeline` | INFO | Per-chunk processing, Rust worker stderr |
| `backend.ingestion.embedder` | INFO | Embedding batch timing, validation failures |
| `backend.retrieval.searcher` | INFO | Search query vectors, score distributions |
| `backend.retrieval.reranker` | WARNING | Per-pair scores (very verbose at INFO) |
| `backend.storage.qdrant_client` | WARNING | Connection events, retry attempts |
| `backend.storage.sqlite_db` | WARNING | Slow query warnings (>100ms) |
| `backend.providers.registry` | INFO | Provider selection, key decryption events |

### Trace ID Propagation

```python
import contextvars

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="no-trace")

class TraceMiddleware:
    async def __call__(self, request, call_next):
        trace_id = str(uuid4())
        trace_id_var.set(trace_id)
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

Trace ID flows through: HTTP Request -> FastAPI Middleware -> API Route -> Agent Nodes -> Storage Ops / Qdrant Calls / Ollama Calls -> query_traces table.

### Metrics to Collect

| Metric | Type | Source | Purpose |
|--------|------|--------|---------|
| `query_latency_ms` | Histogram | API middleware | End-to-end query time |
| `ingestion_latency_ms` | Histogram | Ingestion pipeline | Document processing time |
| `embedding_latency_ms` | Histogram | Embedder | Per-batch embedding time |
| `qdrant_search_latency_ms` | Histogram | Qdrant client | Per-search latency |
| `reranker_latency_ms` | Histogram | Reranker | Cross-encoder inference time |
| `llm_latency_ms` | Histogram | Provider calls | Per-LLM-call latency |
| `confidence_score` | Histogram | Agent nodes | Distribution of confidence scores |
| `meta_reasoning_triggered` | Counter | Agent nodes | Rate of meta-reasoning activation |
| `circuit_breaker_state` | Gauge | Circuit breaker | Current state per service |
| `active_ingestion_jobs` | Gauge | Pipeline | Concurrent ingestion tracking |
| `error_count` | Counter | Error handler | Errors by type and component |
| `cache_hit_rate` | Gauge | SWR/query cache | Frontend cache effectiveness |

### `/observability` Page Data Sources

| Dashboard Element | Data Source | Query |
|-------------------|------------|-------|
| Latency histogram | `query_traces.latency_ms` | `SELECT latency_ms FROM query_traces WHERE created_at > ? ORDER BY created_at DESC LIMIT 1000` |
| Confidence distribution | `query_traces.confidence_score` | `SELECT confidence_score FROM query_traces WHERE confidence_score IS NOT NULL` |
| Meta-reasoning rate | `query_traces.meta_reasoning_triggered` | `SELECT AVG(meta_reasoning_triggered) FROM query_traces WHERE created_at > ?` |
| Service health | `/api/health` endpoint | Real-time ping to Qdrant + Ollama + SQLite |
| Collection stats | `collections` + `documents` | `SELECT c.name, COUNT(d.id), SUM(d.chunk_count) FROM collections c LEFT JOIN documents d ...` |
| Recent traces | `query_traces` | Paginated query with expandable detail |

## Dependencies

- **Libraries**: `structlog>=24.0` (structured JSON logging)
- **Internal**: `backend/config.py` (log_level setting), `backend/storage/sqlite_db.py` (query_traces table), `backend/middleware.py` (TraceMiddleware)
- **Other specs**: Spec 4 (Storage -- query_traces table schema), Spec 14 (Performance -- latency instrumentation feeds observability), Spec 2 (API Layer -- health endpoint), Spec 12 (Frontend -- observability page components)

## Acceptance Criteria

1. All backend log output is valid JSON Lines parseable by `jq` or any JSON parser.
2. Every log entry includes a `trace_id` field that matches the `X-Trace-ID` response header.
3. `GET /api/health` returns status for Qdrant, Ollama, and SQLite with a `200` status when all are healthy and `503` when any are down.
4. After running 5 chat queries, the `/observability` page displays at least 5 entries in the trace table.
5. The latency histogram chart renders with data from `query_traces`.
6. The confidence distribution chart renders with data from `query_traces`.
7. Collection stats display document count and total chunk count per collection.
8. Setting `LOG_LEVEL=DEBUG` enables verbose logging including prompt text (verified by log inspection).
9. The `query_traces` table contains per-stage latency data for each query.
10. Trace IDs are consistent across all log entries for a single request.

## Architecture Reference

Frontend components for the observability page:

- `frontend/components/TraceTable.tsx` -- Paginated trace log with expandable detail
- `frontend/components/LatencyChart.tsx` -- Latency histogram (uses `recharts`)
- `frontend/components/ConfidenceDistribution.tsx` -- Confidence score distribution chart
- `frontend/components/HealthDashboard.tsx` -- Service health status indicators
- `frontend/components/CollectionStats.tsx` -- Per-collection document and chunk counts
- `frontend/hooks/useTraces.ts` -- SWR hook for fetching trace data

Backend files:

- `backend/middleware.py` -- TraceMiddleware (trace ID generation and propagation)
- `backend/api/traces.py` -- Query trace log + health + stats endpoints
- `backend/storage/sqlite_db.py` -- query_traces table operations
