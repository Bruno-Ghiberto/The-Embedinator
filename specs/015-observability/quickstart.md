# Quickstart: Observability Layer

**Branch**: `015-observability` | **Date**: 2026-03-18

## What This Spec Does

Closes remaining observability gaps by:
1. Making trace IDs propagate automatically to ALL log entries (not just middleware logs)
2. Adding a time-series metrics endpoint (`GET /api/metrics`)
3. Enabling per-component log level overrides via environment variable
4. Adding a stage timings chart to the observability dashboard
5. Renaming all log events to follow a consistent prefix convention

## What Already Exists (Do NOT Rebuild)

- `TraceIDMiddleware` in `backend/middleware.py` — generates UUID4, sets `X-Trace-ID` header
- `_configure_logging()` in `backend/main.py` — structlog JSON Lines with `merge_contextvars`
- `GET /api/health`, `GET /api/traces`, `GET /api/stats` — all endpoints exist
- `query_traces` table with 15 columns including `stage_timings_json`
- Frontend observability page with 5 dashboard components
- Three circuit breakers (qdrant, search, inference)
- Error hierarchy in `backend/errors.py`

## Key Technical Decisions

| Decision | Choice | Why |
|----------|--------|-----|
| Per-component log levels | Custom structlog processor with `DropEvent` | `PrintLoggerFactory` bypasses standard `logging` module |
| Metrics bucketing | Fixed window→bucket mapping | Predictable response format, no client negotiation |
| Circuit breaker exposure | Direct `getattr()` on `app.state` | Simplest; 4 instances don't justify a registry |
| P95 computation | Python-side sort after fetching traces | SQLite lacks `PERCENTILE_CONT`; 10K traces is fast |
| Ingestion trace ID | New UUID per `ingest_file()` call | HTTP request's trace ID is stale after 202 response |

## Testing

**NEVER run pytest inside Claude Code.** Always use:

```bash
zsh scripts/run-tests-external.sh -n <name> <target>
cat Docs/Tests/<name>.status    # RUNNING | PASSED | FAILED
cat Docs/Tests/<name>.summary   # ~20 lines
```

## Files At a Glance

**Backend — 14 files modified** (no new backend files):
- `middleware.py` — add `bind_contextvars`/`clear_contextvars`
- `config.py` — add `log_level_overrides` setting
- `main.py` — per-component filtering in `_configure_logging()`
- `traces.py` — new `GET /api/metrics` endpoint
- `chat.py` — bind `session_id` to contextvars
- `pipeline.py` — bind trace ID at `ingest_file()` entry
- 8 files — log event name renames (FR-011)

**Frontend — 3 modified, 2 new**:
- `StageTimingsChart.tsx` (NEW) — horizontal bar chart for stage timings
- `useMetrics.ts` (NEW) — SWR hook for metrics endpoint
- `types.ts`, `TraceTable.tsx`, `page.tsx` — modifications

**Tests — 3-4 new files**: trace context, component log levels, metrics endpoint
