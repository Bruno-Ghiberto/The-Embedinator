# Spec 15: Observability -- Implementation Context

## Implementation Scope

### Files to Create

- `backend/logging_config.py` -- structlog JSON Lines configuration
- `frontend/components/TraceTable.tsx` -- Paginated trace log with expandable detail
- `frontend/components/LatencyChart.tsx` -- Latency histogram using recharts
- `frontend/components/ConfidenceDistribution.tsx` -- Confidence score distribution chart
- `frontend/components/HealthDashboard.tsx` -- Service health status indicators
- `frontend/components/CollectionStats.tsx` -- Per-collection document and chunk counts
- `frontend/hooks/useTraces.ts` -- SWR hook for traces API

### Files to Modify

- `backend/middleware.py` -- Add TraceMiddleware with contextvars-based trace ID propagation
- `backend/api/traces.py` -- Health check, traces, and stats endpoints
- `backend/storage/sqlite_db.py` -- query_traces CRUD operations
- `backend/main.py` -- Wire structlog configuration and TraceMiddleware
- `backend/api/chat.py` -- Write trace record after SSE streaming completes
- `frontend/app/observability/page.tsx` -- Compose dashboard from components

## Code Specifications

### backend/logging_config.py

```python
"""Structured logging configuration using structlog with JSON Lines output."""

import logging
import structlog


def configure_logging(log_level: str = "INFO"):
    """Configure structlog for JSON Lines output with trace ID binding.

    Call this once during application startup.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
```

### TraceMiddleware (in backend/middleware.py)

```python
import contextvars
from uuid import uuid4
import time
import structlog

logger = structlog.get_logger(__name__)

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "trace_id", default="no-trace"
)


class TraceMiddleware:
    """Generates a UUID4 trace ID for every HTTP request and propagates it
    via contextvars. Returns the trace ID in the X-Trace-ID response header."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        trace_id = str(uuid4())
        trace_id_var.set(trace_id)

        # Bind trace_id to structlog context for all downstream logging
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)

        start_time = time.perf_counter()

        async def send_with_trace(message):
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-trace-id", trace_id.encode()))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_trace)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "Request completed",
            elapsed_ms=round(elapsed_ms, 1),
            trace_id=trace_id,
        )
```

### Health Check Endpoint (in backend/api/traces.py)

```python
import time
import httpx
import structlog
from fastapi import APIRouter, Depends

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api")


@router.get("/health")
async def health_check(db=Depends(get_db), settings=Depends(get_settings)):
    """Ping Qdrant, Ollama, and SQLite. Returns aggregate health status."""
    services = {}

    # Check Qdrant
    try:
        start = time.perf_counter()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"http://{settings.qdrant_host}:{settings.qdrant_port}/healthz",
                timeout=5.0,
            )
        latency = (time.perf_counter() - start) * 1000
        services["qdrant"] = {
            "status": "ok" if resp.status_code == 200 else "error",
            "latency_ms": round(latency, 1),
        }
    except Exception as e:
        services["qdrant"] = {"status": "error", "error": str(e)}

    # Check Ollama
    try:
        start = time.perf_counter()
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{settings.ollama_base_url}/",
                timeout=5.0,
            )
        latency = (time.perf_counter() - start) * 1000
        services["ollama"] = {
            "status": "ok" if resp.status_code == 200 else "error",
            "latency_ms": round(latency, 1),
        }
    except Exception as e:
        services["ollama"] = {"status": "error", "error": str(e)}

    # Check SQLite
    try:
        start = time.perf_counter()
        await db.execute("SELECT 1")
        latency = (time.perf_counter() - start) * 1000
        services["sqlite"] = {"status": "ok", "latency_ms": round(latency, 1)}
    except Exception as e:
        services["sqlite"] = {"status": "error", "error": str(e)}

    all_healthy = all(s.get("status") == "ok" for s in services.values())
    status_code = 200 if all_healthy else 503

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"healthy": all_healthy, "services": services},
        status_code=status_code,
    )


@router.get("/traces")
async def get_traces(
    limit: int = 50,
    offset: int = 0,
    db=Depends(get_db),
):
    """Return paginated query traces for the observability page."""
    traces = await db.get_query_traces(limit=limit, offset=offset)
    total = await db.count_query_traces()
    return {"traces": traces, "total": total, "limit": limit, "offset": offset}


@router.get("/stats")
async def get_stats(db=Depends(get_db)):
    """Return aggregated observability statistics."""
    return {
        "avg_latency_ms": await db.get_avg_latency(),
        "meta_reasoning_rate": await db.get_meta_reasoning_rate(),
        "total_queries": await db.count_query_traces(),
        "collection_stats": await db.get_collection_stats(),
    }
```

### query_traces SQL Operations (additions to sqlite_db.py)

```python
async def insert_query_trace(self, trace: dict) -> None:
    """Insert a query trace record."""
    await self.connection.execute(
        """INSERT INTO query_traces
           (trace_id, session_id, query_text, collections_searched,
            latency_ms, confidence_score, meta_reasoning_triggered,
            chunks_retrieved, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            trace["trace_id"],
            trace["session_id"],
            trace["query_text"],
            trace["collections_searched"],
            trace["latency_ms"],
            trace.get("confidence_score"),
            trace.get("meta_reasoning_triggered", False),
            trace.get("chunks_retrieved", "[]"),
            trace["created_at"],
        ),
    )
    await self.connection.commit()

async def get_query_traces(self, limit: int = 50, offset: int = 0) -> list[dict]:
    """Return paginated query traces, most recent first."""
    cursor = await self.connection.execute(
        """SELECT * FROM query_traces
           ORDER BY created_at DESC LIMIT ? OFFSET ?""",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in rows]

async def count_query_traces(self) -> int:
    cursor = await self.connection.execute("SELECT COUNT(*) FROM query_traces")
    row = await cursor.fetchone()
    return row[0]

async def get_avg_latency(self) -> float | None:
    cursor = await self.connection.execute(
        "SELECT AVG(latency_ms) FROM query_traces"
    )
    row = await cursor.fetchone()
    return row[0]

async def get_meta_reasoning_rate(self) -> float | None:
    cursor = await self.connection.execute(
        "SELECT AVG(CAST(meta_reasoning_triggered AS REAL)) FROM query_traces"
    )
    row = await cursor.fetchone()
    return row[0]

async def get_collection_stats(self) -> list[dict]:
    cursor = await self.connection.execute(
        """SELECT c.name, COUNT(d.id) as doc_count,
                  COALESCE(SUM(d.chunk_count), 0) as total_chunks
           FROM collections c
           LEFT JOIN documents d ON c.id = d.collection_id
           GROUP BY c.id, c.name"""
    )
    rows = await cursor.fetchall()
    return [{"name": r[0], "doc_count": r[1], "total_chunks": r[2]} for r in rows]
```

### Frontend: LatencyChart.tsx Pattern

```tsx
// Uses recharts for histogram rendering
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

interface LatencyChartProps {
  data: { bucket: string; count: number }[];
}

export function LatencyChart({ data }: LatencyChartProps) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="bucket" label={{ value: "Latency (ms)", position: "bottom" }} />
        <YAxis label={{ value: "Count", angle: -90, position: "insideLeft" }} />
        <Tooltip />
        <Bar dataKey="count" fill="#3b82f6" />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Global log level for structlog |
| `DEBUG` | `false` | When true, enables debug-level logging for all components |

Per-component log levels can be configured via standard Python logging configuration if needed, but the default approach uses a single global level.

## Error Handling

- **Health check failures**: If a service ping fails, the health endpoint returns `"status": "error"` for that service with the exception message. The aggregate status is `503`. The error is logged at WARNING level.
- **Trace write failures**: If inserting a trace into SQLite fails, log the error at ERROR level but do not fail the chat response. The trace is lost but the user's query succeeds.
- **structlog configuration errors**: If structlog configuration fails at startup, fall back to standard Python logging with a WARNING.
- **Frontend data fetch failures**: The SWR hooks display an error state in the UI components. The observability page remains accessible even if some data sources fail.

## Testing Requirements

### Backend Unit Tests

1. `test_trace_middleware_generates_uuid` -- Verify TraceMiddleware produces a valid UUID4 in the X-Trace-ID header.
2. `test_trace_id_propagates_to_logs` -- Verify structlog entries include the trace_id set by middleware.
3. `test_health_check_all_healthy` -- Mock all services as reachable; assert 200 response with all "ok".
4. `test_health_check_qdrant_down` -- Mock Qdrant as unreachable; assert 503 response with Qdrant "error".
5. `test_insert_query_trace` -- Insert a trace record and read it back; verify all fields match.
6. `test_get_traces_pagination` -- Insert 10 traces, request page of 5; verify correct count and offset.
7. `test_get_collection_stats` -- Create collections with documents; verify stats aggregation.

### Frontend Unit Tests (vitest)

1. `test_latency_chart_renders` -- Render LatencyChart with sample data; verify bars appear.
2. `test_health_dashboard_green` -- Render with all-healthy data; verify green indicators.
3. `test_health_dashboard_red` -- Render with one unhealthy service; verify red indicator.
4. `test_trace_table_pagination` -- Render with paginated data; verify page controls work.

## Done Criteria

- [ ] structlog is configured for JSON Lines output with timestamp, level, logger, and trace_id
- [ ] TraceMiddleware generates UUID4 trace IDs and propagates via contextvars
- [ ] X-Trace-ID response header is set on every HTTP response
- [ ] All log entries within a request share the same trace_id
- [ ] `GET /api/health` pings Qdrant, Ollama, and SQLite; returns 200 or 503
- [ ] `GET /api/traces` returns paginated query traces
- [ ] `GET /api/stats` returns aggregated metrics (avg latency, meta-reasoning rate, collection stats)
- [ ] query_traces table is populated after each chat query
- [ ] Frontend observability page displays latency histogram, confidence distribution, trace table, health status, and collection stats
- [ ] Charts render correctly with real data from the API
- [ ] Per-component log levels are configurable (at minimum via global LOG_LEVEL)
- [ ] All observability unit tests pass
