# Contract: GET /api/metrics

**Branch**: `015-observability` | **Date**: 2026-03-18

## Endpoint

```
GET /api/metrics?window={window}
```

## Request

### Query Parameters

| Parameter | Type | Required | Default | Valid Values | Description |
|-----------|------|----------|---------|-------------|-------------|
| `window` | string | No | `"24h"` | `"1h"`, `"24h"`, `"7d"` | Time window for metrics aggregation |

### Error Responses

| Condition | Status | Body |
|-----------|--------|------|
| Invalid window value | 400 | `{"error": {"code": "VALIDATION_ERROR", "message": "Invalid window. Must be one of: 1h, 24h, 7d", "details": null}, "trace_id": "..."}` |

## Response

### Success (200 OK)

```json
{
  "window": "24h",
  "bucket_size": "1h",
  "buckets": [
    {
      "timestamp": "2026-03-18T00:00:00Z",
      "query_count": 12,
      "avg_latency_ms": 1450,
      "p95_latency_ms": 3200,
      "avg_confidence": 72,
      "meta_reasoning_count": 3,
      "error_count": 1
    },
    {
      "timestamp": "2026-03-18T01:00:00Z",
      "query_count": 0,
      "avg_latency_ms": 0,
      "p95_latency_ms": 0,
      "avg_confidence": 0,
      "meta_reasoning_count": 0,
      "error_count": 0
    }
  ],
  "circuit_breakers": {
    "qdrant": {"state": "closed", "failure_count": 0},
    "inference": {"state": "closed", "failure_count": 0},
    "search": {"state": "closed", "failure_count": 0}
  },
  "active_ingestion_jobs": 0
}
```

### Response Schema

| Field | Type | Description |
|-------|------|-------------|
| `window` | string | Echo of requested window |
| `bucket_size` | string | Size of each bucket: `"5m"` for 1h, `"1h"` for 24h, `"1d"` for 7d |
| `buckets` | array | Time-ordered list of metric buckets |
| `buckets[].timestamp` | string (ISO8601) | Start of bucket time window |
| `buckets[].query_count` | integer | Queries in this bucket |
| `buckets[].avg_latency_ms` | integer | Average latency (0 if no queries) |
| `buckets[].p95_latency_ms` | integer | 95th percentile latency (0 if no queries) |
| `buckets[].avg_confidence` | integer | Average confidence 0-100 (0 if no queries) |
| `buckets[].meta_reasoning_count` | integer | Meta-reasoning triggers (0 if no queries) |
| `buckets[].error_count` | integer | Errors in this bucket |
| `circuit_breakers` | object | CB state keyed by service name |
| `circuit_breakers.{name}.state` | string | `"closed"`, `"open"`, or `"unknown"` |
| `circuit_breakers.{name}.failure_count` | integer | Current consecutive failure count |
| `active_ingestion_jobs` | integer | Currently processing ingestion jobs |

### Invariants

- Empty buckets have `query_count: 0` and all numeric fields as `0` — NOT omitted from the array
- Buckets are ordered ascending by `timestamp`
- `circuit_breakers` always has exactly 3 keys: `qdrant`, `inference`, `search`
- If a circuit breaker instance is unavailable, state is `"unknown"` with `failure_count: 0`
- Windows larger than `7d` return HTTP 400

### Window-to-Bucket Mapping

| Window | Bucket Size | Max Buckets |
|--------|-------------|-------------|
| `1h` | 5 minutes | 12 |
| `24h` | 1 hour | 24 |
| `7d` | 1 day | 7 |

## Performance

- Target: < 500ms response time for 24h window with 10,000 stored traces (SC-003)
- Implementation: fetch all traces in window, group by bucket in Python, compute aggregates
- No caching — data is always fresh from SQLite
