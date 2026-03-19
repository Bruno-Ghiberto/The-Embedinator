# Spec 15: Observability -- Feature Specification Context

## Feature Description

The Observability layer for The Embedinator provides full-stack visibility into the RAG pipeline through structured logging, trace ID propagation, metrics collection, and a dedicated `/observability` page in the frontend. Every HTTP request generates a UUID4 trace ID in FastAPI middleware that propagates through all backend function calls, enabling end-to-end correlation of logs and stored query traces. The `query_traces` SQLite table captures per-query performance and quality data that feeds the observability dashboard.

Significant foundational work for observability was completed across previous specs. This spec focuses on closing remaining gaps: ensuring trace IDs propagate automatically to all structlog entries via `contextvars`, introducing per-component log level configuration, adding in-process metrics aggregation endpoints, and enhancing the existing observability dashboard with stage timing visualization.

## What Already Exists

The following components were implemented in earlier specs. This spec builds upon and enhances them -- it does NOT recreate them.

### Middleware Layer (Spec 13: Security Hardening)

- **`backend/middleware.py`** -- Three middleware classes already registered in `backend/main.py`:
  - `TraceIDMiddleware` -- Generates UUID4 trace ID, sets `request.state.trace_id`, returns `X-Trace-ID` response header
  - `RequestLoggingMiddleware` -- Logs every request with `method`, `path`, `status`, `duration_ms`, `trace_id`, `client`
  - `RateLimitMiddleware` -- Sliding-window per-IP rate limiting (30 chat/min, 10 ingest/min, 5 provider key ops/min, 120 general/min)

### Structured Logging (Spec 13: Security Hardening)

- **`backend/main.py` `_configure_logging()`** -- structlog JSON Lines configuration with these processors:
  1. `structlog.contextvars.merge_contextvars` -- merges context variables into log entries
  2. `structlog.processors.add_log_level`
  3. `structlog.processors.TimeStamper(fmt="iso")`
  4. `structlog.processors.StackInfoRenderer()`
  5. `structlog.processors.format_exc_info`
  6. `_strip_sensitive_fields` -- redacts fields matching `api_key`, `password`, `secret`, `token`, `authorization`
  7. `structlog.processors.JSONRenderer()`

- **Global log level**: `Settings.log_level: str = "INFO"` in `backend/config.py`, passed to `structlog.make_filtering_bound_logger()`

### Health Check Endpoint (Spec 8: API Reference)

- **`backend/api/health.py`** -- `GET /api/health` probes SQLite, Qdrant, and Ollama with per-service latency measurements
- Returns `HealthResponse(status="healthy"|"degraded", services=[HealthServiceStatus(...)])` with HTTP 200 (healthy) or 503 (degraded)
- `HealthServiceStatus` schema: `name: str`, `status: "ok"|"error"`, `latency_ms: float|None`, `error_message: str|None`

### Query Traces API (Spec 8: API Reference)

- **`backend/api/traces.py`** -- Three endpoints already implemented:
  - `GET /api/traces` -- Paginated trace list with optional filters (`session_id`, `collection_id`, `min_confidence`, `max_confidence`, `limit`, `offset`)
  - `GET /api/traces/{trace_id}` -- Full trace detail with parsed JSON fields (sub_questions, chunks_retrieved, reasoning_steps, strategy_switches, stage_timings)
  - `GET /api/stats` -- Aggregate system statistics (`StatsResponse`: total_collections, total_documents, total_chunks, total_queries, avg_confidence, avg_latency_ms, meta_reasoning_rate)

### Query Traces Table (Spec 7: Storage Architecture + migrations from Specs 10, 14)

The `query_traces` SQLite table has these columns (verified from `backend/storage/sqlite_db.py`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID4 trace ID |
| `session_id` | TEXT NOT NULL | Chat session identifier |
| `query` | TEXT NOT NULL | User's query text |
| `sub_questions_json` | TEXT | JSON array of decomposed sub-questions |
| `collections_searched` | TEXT | JSON array of collection names |
| `chunks_retrieved_json` | TEXT | JSON array of `{chunk_id, score, collection}` |
| `reasoning_steps_json` | TEXT | JSON array of agent reasoning steps |
| `strategy_switches_json` | TEXT | JSON array of meta-reasoning strategy switches |
| `meta_reasoning_triggered` | INTEGER DEFAULT 0 | Boolean: 1 if MetaReasoningGraph activated |
| `latency_ms` | INTEGER | End-to-end query time in milliseconds |
| `llm_model` | TEXT | LLM model used for generation |
| `embed_model` | TEXT | Embedding model used for query |
| `confidence_score` | INTEGER | Computed confidence on 0--100 scale |
| `provider_name` | TEXT | LLM provider name (added via Spec 10 migration) |
| `stage_timings_json` | TEXT | JSON dict of per-stage latency data (added via Spec 14 migration) |
| `created_at` | TEXT NOT NULL | ISO8601 timestamp |

Indexes: `idx_traces_session` on `(session_id)`, `idx_traces_created` on `(created_at)`.

### Frontend Observability Page (Spec 9: Next.js Frontend)

- **`frontend/app/observability/page.tsx`** -- Fully implemented page with 5 sections:
  1. `HealthDashboard` component (self-fetching via `/api/health`)
  2. `LatencyChart` component (recharts histogram, dynamic import with SSR disabled)
  3. `ConfidenceDistribution` component (recharts chart, dynamic import with SSR disabled)
  4. `TraceTable` component (paginated with session filter)
  5. `CollectionStats` component (self-fetching)
- **`frontend/hooks/useTraces.ts`** -- SWR hook wrapping `GET /api/traces` with filter params
- **`frontend/components/`** -- All five components exist: `TraceTable.tsx`, `LatencyChart.tsx`, `ConfidenceDistribution.tsx`, `HealthDashboard.tsx`, `CollectionStats.tsx`

### Circuit Breaker State (Specs 5, 7)

Three independent circuit breaker implementations exist in the codebase:
1. `backend/storage/qdrant_client.py` -- `QdrantClientWrapper._circuit_open` and `QdrantStorage._circuit_open` (Qdrant calls)
2. `backend/retrieval/searcher.py` -- `HybridSearcher._circuit_open` (search calls)
3. `backend/agent/nodes.py` -- Module-level `_inf_circuit_open` (inference/LLM calls)

All use the same pattern: failure counter, max threshold (`circuit_breaker_failure_threshold=5`), cooldown (`circuit_breaker_cooldown_secs=30`).

### Error Hierarchy (Spec 12: Error Handling)

**`backend/errors.py`** -- 10 subclasses of `EmbeddinatorError`:
`QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError`

**`backend/providers/base.py`** -- `ProviderRateLimitError(Exception)` (separate hierarchy, not a subclass of `EmbeddinatorError`). Raised on HTTP 429 from cloud providers.

### Existing structlog Usage Across Codebase

All backend modules already import and use structlog: `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/research_edges.py`, `backend/agent/meta_reasoning_nodes.py`, `backend/agent/research_graph.py`, `backend/retrieval/searcher.py`, `backend/retrieval/reranker.py`, `backend/storage/sqlite_db.py`, `backend/storage/qdrant_client.py`, `backend/storage/parent_store.py`, `backend/storage/indexing.py`, `backend/ingestion/pipeline.py`, `backend/ingestion/chunker.py`, `backend/ingestion/embedder.py`, `backend/ingestion/incremental.py`, `backend/providers/registry.py`, `backend/providers/ollama.py`, `backend/api/chat.py`, `backend/middleware.py`.

---

## Requirements

### Functional Requirements

1. **Trace ID Context Propagation**: `TraceIDMiddleware` must bind the generated `trace_id` to structlog context variables using `structlog.contextvars.bind_contextvars(trace_id=trace_id)` so that ALL downstream log entries (agent nodes, storage ops, retrieval, ingestion) automatically include `trace_id` without explicit kwarg passing. Currently, only `RequestLoggingMiddleware` explicitly passes `trace_id` -- other modules do not include it in their log calls.

2. **Session ID Context Binding**: When a chat request is processed, `session_id` must be bound to structlog context variables so that all log entries within that request scope include the session identifier.

3. **Per-Component Log Level Configuration**: Introduce per-module log level overrides in `backend/config.py`. The global `log_level` remains the default, but specific modules can have stricter or more verbose levels. This enables debug-level logging for a single component (e.g., `backend.retrieval.searcher`) without flooding the entire log stream.

4. **Metrics Aggregation Endpoint**: Extend `backend/api/traces.py` with a `GET /api/metrics` endpoint that returns time-bucketed histogram data for latency distributions, confidence score distributions, and meta-reasoning trigger rates. Unlike `GET /api/stats` (which returns aggregate totals), this endpoint returns time-series data suitable for charting trends over configurable windows (1h, 24h, 7d).

5. **Stage Timings Visualization**: Add a per-stage latency breakdown view to the trace detail on the `/observability` page. The `stage_timings_json` column (from Spec 14) already stores per-stage timing data -- this needs to be rendered as a horizontal bar chart or waterfall diagram showing time spent in each pipeline stage (rewrite, research, compression, generation, etc.).

6. **Log Completeness Audit**: Ensure all significant operations log a structured event with consistent field names. Each log entry must use one of the following categories as its event name prefix: `http_`, `agent_`, `retrieval_`, `storage_`, `ingestion_`, `provider_`, `circuit_`. Log entries for error conditions must include an `error` field with the exception class name.

### Non-Functional Requirements

- Logging overhead must be negligible (microseconds per log entry).
- Trace ID generation and propagation must add less than 1 ms to request latency.
- The `query_traces` write must not block the response to the user (can be done after the NDJSON stream completes or asynchronously).
- Log level is configurable via environment variable (`LOG_LEVEL` for global default).
- Debug-level logging must not be enabled by default in production (it may include full prompt text and LLM raw responses).
- Context variable cleanup must happen after each request to prevent trace ID leakage between requests.

## Key Technical Details

### Trace ID Propagation (Current State vs. Target)

**Current implementation** (`TraceIDMiddleware` in `backend/middleware.py`):

```python
class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        response: Response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

The trace ID is available via `request.state.trace_id` in API route handlers, which pass it explicitly to log calls. However, deeper layers (agent nodes, storage operations, retrieval modules) do not have access to the request object and therefore do not include `trace_id` in their log entries.

**Target implementation** -- add structlog contextvars binding:

```python
import structlog

class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Trace-ID"] = trace_id
            return response
        finally:
            structlog.contextvars.clear_contextvars()
```

Because `_configure_logging()` already includes `structlog.contextvars.merge_contextvars` in the processor chain, binding the trace ID to contextvars will cause it to appear automatically in every log entry produced during that request -- no changes needed to individual log call sites across the codebase.

### Structured Log Format (JSON Lines)

All backend logs use JSON Lines format via structlog's `JSONRenderer`. Fields are flat key-value pairs (not nested). A typical log entry after trace ID propagation will look like:

```json
{
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "event": "retrieval_search_completed",
  "level": "info",
  "timestamp": "2026-03-03T10:32:15.123456Z",
  "collection": "tech-docs",
  "results_count": 8,
  "elapsed_ms": 42.3
}
```

Note: structlog uses `event` as the message field name, not `message`. The `logger` field is not included by default -- it is available if modules use `structlog.get_logger(__name__)`.

### Per-Component Log Levels

| Component | Default Level | Debug Level Enables |
|-----------|--------------|-------------------|
| `backend.api` | INFO | Request/response bodies, headers |
| `backend.agent.nodes` | INFO | Full prompt text, LLM raw responses |
| `backend.agent.research_nodes` | INFO | Tool call parameters, chunk text snippets |
| `backend.agent.meta_reasoning_nodes` | INFO | Strategy selection reasoning, reranker scores |
| `backend.ingestion.pipeline` | INFO | Per-chunk processing, Rust worker stderr |
| `backend.ingestion.embedder` | INFO | Embedding batch timing, validation failures |
| `backend.retrieval.searcher` | INFO | Search query vectors, score distributions |
| `backend.retrieval.reranker` | WARNING | Per-pair cross-encoder scores (very verbose at INFO) |
| `backend.storage.qdrant_client` | WARNING | Connection events, retry attempts |
| `backend.storage.sqlite_db` | WARNING | Slow query warnings (>100ms) |
| `backend.providers.registry` | INFO | Provider selection, key decryption events |
| `backend.providers.ollama` | INFO | Model listing, health check results |
| `backend.middleware` | INFO | Rate limit events, request durations |

The global `Settings.log_level` (default `"INFO"`) applies to all modules unless overridden. Per-component overrides are applied via Python's standard `logging` module level settings or structlog filtering, keyed by logger name.

### Metrics to Collect

Metrics are derived from the `query_traces` table and in-process counters. No external metrics library (e.g., Prometheus client) is introduced -- all metrics are served via REST endpoints.

| Metric | Type | Source | Purpose |
|--------|------|--------|---------|
| `query_latency_ms` | Histogram | `query_traces.latency_ms` | End-to-end query time distribution |
| `confidence_score` | Histogram | `query_traces.confidence_score` | Distribution of confidence scores (0--100) |
| `meta_reasoning_triggered` | Counter | `query_traces.meta_reasoning_triggered` | Rate of meta-reasoning activation |
| `stage_timings` | Breakdown | `query_traces.stage_timings_json` | Per-stage latency (rewrite, research, compress, generate) |
| `circuit_breaker_state` | Gauge | In-process globals | Current state per service (qdrant, inference, search) |
| `active_ingestion_jobs` | Gauge | `ingestion_jobs WHERE status='processing'` | Concurrent ingestion tracking |
| `error_count` | Counter | Error handler middleware | Errors by type (EmbeddinatorError subclass or ProviderRateLimitError) |

Note: `cache_hit_rate` from the architecture blueprint is a frontend-side metric (SWR cache) and is not collected by the backend.

### `/observability` Page Data Sources (Existing)

| Dashboard Element | Data Source | API Endpoint |
|-------------------|------------|--------------|
| Latency histogram | `query_traces.latency_ms` | `GET /api/traces` (returns `latency_ms` per trace) |
| Confidence distribution | `query_traces.confidence_score` | `GET /api/traces` (returns `confidence_score` per trace) |
| Meta-reasoning rate | Aggregate from `query_traces` | `GET /api/stats` (returns `meta_reasoning_rate`) |
| Service health | Live probes to Qdrant + Ollama + SQLite | `GET /api/health` |
| Collection stats | `collections` + `documents` tables | `GET /api/stats` (returns totals) |
| Recent traces | `query_traces` (paginated) | `GET /api/traces?limit=20&offset=0` |
| Trace detail | Single `query_traces` row | `GET /api/traces/{trace_id}` |

### New: `/api/metrics` Endpoint

Returns time-bucketed data for trend analysis:

```json
{
  "window": "24h",
  "buckets": [
    {
      "timestamp": "2026-03-18T00:00:00Z",
      "query_count": 12,
      "avg_latency_ms": 1450,
      "p95_latency_ms": 3200,
      "avg_confidence": 72,
      "meta_reasoning_count": 3,
      "error_count": 1
    }
  ],
  "circuit_breakers": {
    "qdrant": {"state": "closed", "failure_count": 0},
    "inference": {"state": "closed", "failure_count": 0},
    "search": {"state": "closed", "failure_count": 0}
  }
}
```

## Dependencies

- **Libraries**: `structlog>=24.0` (already installed -- structured JSON logging with contextvars support)
- **Internal (existing, not modified)**:
  - `backend/middleware.py` -- `TraceIDMiddleware`, `RequestLoggingMiddleware`, `RateLimitMiddleware`
  - `backend/api/traces.py` -- `list_traces`, `get_trace`, `system_stats` endpoints
  - `backend/api/health.py` -- `GET /api/health` endpoint
  - `backend/storage/sqlite_db.py` -- `query_traces` table operations (`create_query_trace`, `list_traces`, `get_trace`, `get_query_traces_by_timerange`)
  - `backend/agent/schemas.py` -- `HealthResponse`, `HealthServiceStatus`, `StatsResponse`
  - `frontend/app/observability/page.tsx` -- Observability page with all 5 dashboard sections
  - `frontend/components/{TraceTable,LatencyChart,ConfidenceDistribution,HealthDashboard,CollectionStats}.tsx`
  - `frontend/hooks/useTraces.ts` -- SWR hook for trace data
- **Internal (to be modified)**:
  - `backend/middleware.py` -- Add `structlog.contextvars.bind_contextvars()` call in `TraceIDMiddleware`
  - `backend/config.py` -- Add per-component log level settings
  - `backend/main.py` -- Update `_configure_logging()` to apply per-component levels
  - `backend/api/traces.py` -- Add `GET /api/metrics` endpoint
  - `backend/api/chat.py` -- Bind `session_id` to structlog context variables during chat streaming
- **Other specs this depends on**:
  - Spec 7 (Storage Architecture -- `query_traces` table schema, `SQLiteDB` class)
  - Spec 8 (API Reference -- health endpoint, traces API, REST route structure)
  - Spec 9 (Next.js Frontend -- observability page and components)
  - Spec 12 (Error Handling -- error hierarchy for error classification in metrics)
  - Spec 13 (Security Hardening -- middleware layer, `_strip_sensitive_fields` log processor)
  - Spec 14 (Performance Budgets -- `stage_timings` in `ConversationState`, `stage_timings_json` column migration)

## Acceptance Criteria

1. All backend log output is valid JSON Lines parseable by `jq` or any JSON parser.
2. Every log entry produced during an HTTP request includes a `trace_id` field that matches the `X-Trace-ID` response header -- verified by checking logs from agent nodes, storage ops, and retrieval modules (not just middleware logs).
3. `GET /api/health` returns status for Qdrant, Ollama, and SQLite with `200` when all are healthy and `503` when any are degraded. (Already implemented -- verified, not rebuilt.)
4. After running 5 chat queries, the `/observability` page displays at least 5 entries in the trace table. (Already implemented -- verified, not rebuilt.)
5. The latency histogram chart renders with data from `query_traces`. (Already implemented -- verified, not rebuilt.)
6. The confidence distribution chart renders with data from `query_traces`. (Already implemented -- verified, not rebuilt.)
7. Collection stats display document count and total chunk count per collection. (Already implemented via `GET /api/stats` -- verified, not rebuilt.)
8. Setting `LOG_LEVEL=DEBUG` enables verbose logging including prompt text (verified by log inspection).
9. The `query_traces` table contains per-stage latency data (`stage_timings_json`) for each query. (Already implemented by Spec 14 -- verified, not rebuilt.)
10. Trace IDs are consistent across ALL log entries for a single request, including those emitted by `backend/agent/nodes.py`, `backend/retrieval/searcher.py`, and `backend/storage/sqlite_db.py`.
11. `GET /api/metrics?window=24h` returns time-bucketed histogram data with latency percentiles, confidence averages, and meta-reasoning counts.
12. The trace detail view on `/observability` includes a stage timings visualization (bar chart or waterfall) when `stage_timings` data is present.
13. Per-component log level overrides work: setting `LOG_LEVEL_RETRIEVAL_RERANKER=DEBUG` enables debug logs for the reranker while other components remain at their default levels.
14. Context variables are cleaned up after each request -- no trace ID leakage between concurrent requests.

## Architecture Reference

### Backend Files (Existing -- Enhancements Only)

- `backend/middleware.py` -- Add contextvars binding in `TraceIDMiddleware.dispatch()`
- `backend/main.py` -- Update `_configure_logging()` for per-component levels
- `backend/config.py` -- Add per-component log level settings to `Settings`
- `backend/api/traces.py` -- Add `GET /api/metrics` endpoint with time-bucketed aggregation

### Frontend Files (Existing -- Enhancements Only)

- `frontend/app/observability/page.tsx` -- Add stage timings visualization section
- `frontend/components/TraceTable.tsx` -- Existing (no changes unless detail expansion is enhanced)
- `frontend/components/LatencyChart.tsx` -- Existing (recharts histogram)
- `frontend/components/ConfidenceDistribution.tsx` -- Existing (recharts distribution chart)
- `frontend/components/HealthDashboard.tsx` -- Existing (service health indicators)
- `frontend/components/CollectionStats.tsx` -- Existing (per-collection stats)
- `frontend/hooks/useTraces.ts` -- Existing (SWR hook for `/api/traces`)

### New Frontend Files

- `frontend/components/StageTimingsChart.tsx` -- Horizontal bar chart showing per-stage latency breakdown
- `frontend/hooks/useMetrics.ts` -- SWR hook for `GET /api/metrics` (time-series data)

### Error Types for Metrics Classification

The `error_count` metric should classify errors by these types:

| Error Class | Module | Trigger |
|-------------|--------|---------|
| `QdrantConnectionError` | `backend/errors.py` | Qdrant unreachable |
| `OllamaConnectionError` | `backend/errors.py` | Ollama unreachable |
| `SQLiteError` | `backend/errors.py` | SQLite operation failure |
| `LLMCallError` | `backend/errors.py` | LLM inference failure |
| `EmbeddingError` | `backend/errors.py` | Embedding generation failure |
| `IngestionError` | `backend/errors.py` | Pipeline processing failure |
| `SessionLoadError` | `backend/errors.py` | Session checkpoint load failure |
| `StructuredOutputParseError` | `backend/errors.py` | LLM output parsing failure |
| `RerankerError` | `backend/errors.py` | Cross-encoder failure |
| `CircuitOpenError` | `backend/errors.py` | Circuit breaker open |
| `ProviderRateLimitError` | `backend/providers/base.py` | Cloud provider HTTP 429 (separate hierarchy) |

### Circuit Breaker Observability

Three circuit breaker instances exist. For the metrics endpoint, their state can be read from:

| Circuit Breaker | Location | State Variables |
|----------------|----------|-----------------|
| Qdrant (wrapper) | `QdrantClientWrapper._circuit_open`, `._failure_count` | Instance on `app.state.qdrant` |
| Qdrant (storage) | `QdrantStorage._circuit_open`, `._failure_count` | Instance on `app.state.qdrant_storage` |
| Search | `HybridSearcher._circuit_open`, `._failure_count` | Instance on `app.state.hybrid_searcher` |
| Inference | `nodes._inf_circuit_open`, `nodes._inf_failure_count` | Module-level globals in `backend/agent/nodes.py` |
