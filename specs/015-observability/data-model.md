# Data Model: Observability Layer

**Branch**: `015-observability` | **Date**: 2026-03-18

## Entities

### MetricsBucket (NEW — computed, not stored)

A time-bounded aggregation of query trace data, computed on-the-fly from `query_traces` table rows.

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | string (ISO8601) | Start of the bucket time window |
| `query_count` | integer | Number of queries in this bucket |
| `avg_latency_ms` | integer | Average end-to-end latency in milliseconds |
| `p95_latency_ms` | integer | 95th percentile latency in milliseconds |
| `avg_confidence` | integer | Average confidence score (0-100) |
| `meta_reasoning_count` | integer | Number of queries that triggered meta-reasoning |
| `error_count` | integer | Number of queries that produced errors |

**Lifecycle**: Ephemeral — computed per API request from `query_traces` rows within the requested time window. Not persisted.

**Identity**: Uniquely identified by `timestamp` within a single metrics response.

### CircuitBreakerSnapshot (NEW — computed, not stored)

A point-in-time snapshot of a circuit breaker's state, read from in-process globals/instance attributes.

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | `"closed"`, `"open"`, or `"unknown"` |
| `failure_count` | integer | Current consecutive failure count |

**Lifecycle**: Ephemeral — read at request time. Three instances: qdrant, inference, search.

### MetricsResponse (NEW — API response shape)

The top-level response from `GET /api/metrics`.

| Field | Type | Description |
|-------|------|-------------|
| `window` | string | Requested time window (`"1h"`, `"24h"`, `"7d"`) |
| `bucket_size` | string | Size of each bucket (`"5m"`, `"1h"`, `"1d"`) |
| `buckets` | list[MetricsBucket] | Time-ordered list of metric buckets |
| `circuit_breakers` | dict[string, CircuitBreakerSnapshot] | CB state keyed by service name |
| `active_ingestion_jobs` | integer | Count of currently processing ingestion jobs |

### LogLevelOverride (NEW — configuration, not stored)

A per-component log level setting parsed from the `LOG_LEVEL_OVERRIDES` environment variable.

| Field | Type | Description |
|-------|------|-------------|
| `module_path` | string | Dotted Python module path (e.g., `backend.retrieval.reranker`) |
| `level` | string | Log level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

**Lifecycle**: Parsed at application startup from `Settings.log_level_overrides`. Immutable during runtime.

### StageTimings (EXISTING — stored in `query_traces.stage_timings_json`)

Per-stage timing data for a single query, already stored by spec-14.

| Field | Type | Description |
|-------|------|-------------|
| `{stage_name}` | object | Key is stage name (e.g., `rewrite`, `research`, `compress`, `generate`) |
| `.duration_ms` | float | Time spent in this stage in milliseconds |
| `.failed` | boolean (optional) | Whether this stage failed |

**Frontend type**: `Record<string, { duration_ms: number; failed?: boolean }>`

## Existing Entities (Referenced, Not Modified)

### QueryTrace (EXISTING — `query_traces` table)

15 columns as documented in `15-specify.md`. No schema changes in this spec.

### HealthResponse (EXISTING — `backend/agent/schemas.py`)

`HealthResponse(status, services)` with `HealthServiceStatus(name, status, latency_ms, error_message)`.

### StatsResponse (EXISTING — `backend/agent/schemas.py`)

`StatsResponse(total_collections, total_documents, total_chunks, total_queries, avg_confidence, avg_latency_ms, meta_reasoning_rate)`.

## Relationships

```
MetricsResponse
├── buckets: list[MetricsBucket]        # computed from query_traces rows
├── circuit_breakers: dict[CB name → CircuitBreakerSnapshot]  # read from app.state
└── active_ingestion_jobs: int          # COUNT(*) from ingestion_jobs table

QueryTrace.stage_timings_json → parsed → StageTimings → rendered → StageTimingsChart (frontend)

Settings.log_level_overrides → parsed → list[LogLevelOverride] → applied → _filter_by_component processor
```

## No Schema Migrations

This spec does NOT modify the SQLite schema. All new entities are either:
- Computed on-the-fly from existing data (MetricsBucket, CircuitBreakerSnapshot)
- Configuration parsed at startup (LogLevelOverride)
- API response shapes (MetricsResponse)
