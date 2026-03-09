# Spec 15: Observability -- Implementation Plan Context

## Component Overview

The Observability layer provides full-stack visibility into The Embedinator's RAG pipeline. It spans three areas: structured logging with trace ID correlation (backend), query trace persistence in SQLite (backend), and a dashboard page with charts and health indicators (frontend). The goal is to enable systematic improvement of retrieval quality after deployment by capturing every query's performance and quality data.

## Technical Approach

### Structured Logging

- Configure `structlog` as a JSON Lines renderer for all backend logging.
- Bind `trace_id` and `session_id` to the structlog context at the start of each request via middleware.
- Each component uses `structlog.get_logger(__name__)` for automatic logger name inclusion.
- Log levels are configurable per component via environment variables or the global `LOG_LEVEL` setting.

### Trace ID Propagation

- Use Python `contextvars.ContextVar` for thread-safe trace ID storage.
- Generate UUID4 in `TraceMiddleware` and set it in the context var.
- All downstream code accesses the trace ID via `trace_id_var.get()`.
- The trace ID is returned to the client via `X-Trace-ID` response header.

### Query Traces Storage

- After each chat query completes (including SSE streaming), write a row to the `query_traces` table with performance and quality data.
- The write happens asynchronously after the response is sent (using a background task or after the SSE generator finishes).
- The trace includes: trace_id, session_id, query_text, collections_searched, latency_ms, confidence_score, meta_reasoning_triggered, retrieved_chunks (JSON), created_at.

### Health Check Endpoint

- `GET /api/health` pings Qdrant (HTTP to healthz), Ollama (HTTP to root), and SQLite (simple query).
- Returns a JSON object with per-service status and an aggregate `healthy` boolean.
- Returns HTTP 200 if all services are healthy, HTTP 503 if any are down.

### Observability Frontend Page

- Use `recharts` for latency histogram and confidence distribution charts.
- Use SWR for data fetching with auto-refresh intervals.
- The trace table supports pagination and expandable rows showing tool calls, chunks retrieved, and per-stage latencies.

## File Structure

```
backend/
  middleware.py                  # TraceMiddleware, structlog configuration
  api/
    traces.py                    # GET /api/traces, GET /api/health, GET /api/stats
  storage/
    sqlite_db.py                 # query_traces table CRUD operations
  logging_config.py              # structlog configuration (NEW FILE)

frontend/
  app/
    observability/
      page.tsx                   # Observability dashboard page
  components/
    TraceTable.tsx               # Paginated trace log
    LatencyChart.tsx             # Latency histogram chart
    ConfidenceDistribution.tsx   # Confidence score chart
    HealthDashboard.tsx          # Service health indicators
    CollectionStats.tsx          # Collection document/chunk counts
  hooks/
    useTraces.ts                 # SWR hook for traces API
```

## Implementation Steps

1. **Create `backend/logging_config.py`**: Configure structlog with JSON Lines renderer, timestamp processor, log level filtering, and context variable binding for trace_id.
2. **Implement `TraceMiddleware`**: In `backend/middleware.py`, create middleware that generates UUID4 trace IDs, sets them in `contextvars`, attaches to `request.state`, and adds `X-Trace-ID` response header.
3. **Add structlog initialization**: Call the structlog configuration function in the application lifespan handler (`main.py`).
4. **Add `query_traces` table operations**: In `sqlite_db.py`, add methods for inserting trace records and querying them with pagination, time filtering, and aggregation.
5. **Create health check endpoint**: In `backend/api/traces.py`, implement `GET /api/health` that pings Qdrant, Ollama, and SQLite and returns structured health status.
6. **Create traces endpoint**: In `backend/api/traces.py`, implement `GET /api/traces` with pagination and `GET /api/stats` for aggregated metrics (average latency, meta-reasoning rate, etc.).
7. **Wire trace writing into chat flow**: After the SSE streaming generator completes in `backend/api/chat.py`, write the accumulated trace data to `query_traces`.
8. **Build frontend observability page**: Create `frontend/app/observability/page.tsx` composing the dashboard components.
9. **Build chart components**: Implement `LatencyChart.tsx` and `ConfidenceDistribution.tsx` using `recharts`.
10. **Build trace table**: Implement `TraceTable.tsx` with pagination and expandable detail rows.
11. **Build health dashboard**: Implement `HealthDashboard.tsx` that polls `GET /api/health` and displays colored status indicators.
12. **Build collection stats**: Implement `CollectionStats.tsx` that displays per-collection document counts and total chunks.
13. **Create `useTraces` SWR hook**: Fetch traces with auto-refresh for the observability page.

## Integration Points

- **Performance (Spec 14)**: Timer instrumentation provides the latency data that feeds the trace table and charts.
- **Agent (Spec 3)**: LangGraph node execution provides confidence scores, meta-reasoning trigger events, and per-stage timings.
- **Storage (Spec 4)**: The `query_traces` table schema is defined in the storage spec. Observability reads and writes to this table.
- **Frontend (Spec 12)**: The observability page is a Next.js route that uses the same component library (Radix UI, Tailwind CSS) as the rest of the frontend.
- **Security (Spec 13)**: Trace IDs are included in security-related log entries (rate limit rejections, validation failures).

## Key Code Patterns

### structlog Configuration

```python
import structlog
import logging

def configure_logging(log_level: str = "INFO"):
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )
```

### Health Check Response Shape

```json
{
  "healthy": true,
  "services": {
    "qdrant": {"status": "ok", "latency_ms": 5},
    "ollama": {"status": "ok", "latency_ms": 12},
    "sqlite": {"status": "ok", "latency_ms": 1}
  }
}
```

### Trace Record Structure (for query_traces table)

```python
trace_record = {
    "trace_id": "req-abc-123",
    "session_id": "sess-xyz-789",
    "query_text": "What is WSAA authentication?",
    "collections_searched": '["wsaa-docs"]',
    "latency_ms": 1250,
    "confidence_score": 0.82,
    "meta_reasoning_triggered": False,
    "chunks_retrieved": '[{"id": "...", "score": 0.91, "text": "..."}]',
    "created_at": "2026-03-03T10:32:15.123Z",
}
```

## Phase Assignment

- **Phase 1 (MVP)**: Basic structlog configuration (JSON Lines output), TraceMiddleware (trace ID generation), `query_traces` table created but not fully populated, health check endpoint.
- **Phase 2 (Performance and Resilience)**: Full `query_traces` population on every chat request, structured logging with trace ID propagation throughout all components, `/observability` page with latency histogram, confidence distribution, recent trace log.
- **Phase 3 (Ecosystem and Polish)**: Collection stats, meta-reasoning rate chart, trace detail expansion, export traces to file, log level per-component configuration UI.
