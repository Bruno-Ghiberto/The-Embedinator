# Research: Observability Layer

**Branch**: `015-observability` | **Date**: 2026-03-18
**Source**: Technical context from `Docs/PROMPTS/spec-15-observability/15-plan.md` and codebase verification via serena

## R1: Per-Component Log Levels with structlog

**Decision**: Custom structlog processor with `DropEvent` filtering.

**Rationale**: The current structlog configuration uses `PrintLoggerFactory()` which bypasses Python's standard `logging` module entirely. Therefore, calling `logging.getLogger(name).setLevel(level)` has no effect on structlog output. The correct approach is a custom processor inserted into the structlog chain that checks the logger name against an override map and raises `structlog.DropEvent` for events below the configured level.

**Implementation**:
- Add `log_level_overrides: str = ""` to `Settings` in `backend/config.py` (env var: `LOG_LEVEL_OVERRIDES`)
- Format: comma-separated `module.path=LEVEL` pairs (e.g., `backend.retrieval.reranker=DEBUG,backend.storage.sqlite_db=WARNING`)
- Add `_filter_by_component(logger, method_name, event_dict)` processor to `_configure_logging()` in `backend/main.py`
- Processor position: AFTER `merge_contextvars` and BEFORE `add_log_level` in the chain
- Invalid level values log a warning at startup and fall back to global default

**Alternatives considered**:
- Standard `logging` module integration: Rejected — `PrintLoggerFactory` bypasses it entirely
- Separate structlog instances per module: Rejected — structlog is designed as a singleton configuration
- Environment variable per module (e.g., `LOG_LEVEL_RERANKER`): Rejected — too many env vars, hard to manage

**Prerequisite**: All modules must use `structlog.get_logger(__name__)` (not bare `structlog.get_logger()`) for the processor to match logger names. `backend/middleware.py` currently uses bare `structlog.get_logger()` — this must be fixed.

## R2: Metrics Bucket Granularity Strategy

**Decision**: Fixed mapping from window to bucket size.

**Rationale**: A fixed mapping provides predictable bucket counts and eliminates the need for client-side granularity negotiation. Three windows cover the common use cases: real-time monitoring (1h), daily review (24h), and weekly trends (7d).

**Implementation**:

| Window | Bucket Size | Max Buckets | SQLite strftime Format |
|--------|-------------|-------------|----------------------|
| `1h` | 5 minutes | 12 | `strftime('%Y-%m-%dT%H:%M', created_at)` truncated to 5-min |
| `24h` | 1 hour | 24 | `strftime('%Y-%m-%dT%H:00:00Z', created_at)` |
| `7d` | 1 day | 7 | `strftime('%Y-%m-%d', created_at)` |

For the 5-minute bucketing in the 1h window, truncate minutes to nearest 5: `(CAST(strftime('%M', created_at) AS INTEGER) / 5) * 5`.

**P95 latency computation**: SQLite lacks `PERCENTILE_CONT`. Fetch all `latency_ms` values in the window, group by bucket in Python, sort per bucket, and take index `ceil(0.95 * count) - 1`. This is efficient for up to 10,000 traces (SC-003 target).

**Alternatives considered**:
- Dynamic granularity based on data density: Rejected — unpredictable response format complicates frontend
- SQL-only aggregation with `MAX()` as P95 proxy: Rejected — inaccurate upper bound, not true P95
- Pre-aggregated materialized table: Rejected — adds schema complexity for marginal benefit at 1-5 user scale

## R3: Circuit Breaker State Exposure Pattern

**Decision**: Direct attribute access via `request.app.state` with `getattr()` fallback.

**Rationale**: Circuit breakers are instance-level attributes on objects stored in `app.state`. There is no centralized registry. Direct access is the simplest approach and aligns with Constitution VII (Simplicity by Default).

**Implementation**:
- Qdrant CB: `getattr(request.app.state, "qdrant", None)` → `._circuit_open`, `._failure_count`
- Qdrant Storage CB: `getattr(request.app.state, "qdrant_storage", None)` → `._circuit_open`, `._failure_count`
- Search CB: `getattr(request.app.state, "hybrid_searcher", None)` → `._circuit_open`, `._failure_count`
- Inference CB: `import backend.agent.nodes as nodes_module` → `nodes_module._inf_circuit_open`, `nodes_module._inf_failure_count`

If any instance is `None` or missing, return `{"state": "unknown", "failure_count": 0}`.

**Alternatives considered**:
- Circuit breaker observer interface: Rejected — over-engineering for 4 instances; violates YAGNI
- Centralized CB registry singleton: Rejected — requires refactoring existing CB code across 4 modules
- Health endpoint extension: Rejected — health endpoint serves a different purpose (service reachability, not CB state)

## R4: Log Event Naming Audit Approach

**Decision**: Static analysis pre/post rename with verification test.

**Rationale**: A codebase-wide rename across 12+ modules requires systematic tracking. Static analysis via `search_for_pattern` (serena) or `grep` provides a complete inventory before and after the rename, ensuring nothing is missed.

**Implementation**:
1. **Pre-rename audit (Wave 1, A1)**: Search all backend files for `log\.(info|warning|error|debug)\(` and `logger\.(info|warning|error|debug)\(` patterns. Document every current event name per file.
2. **Rename (Wave 4, A6+A7)**: Apply prefix convention to all events. Replace colons/spaces with underscores.
3. **Post-rename verification (Wave 5, A8)**: Re-run the search and confirm every event name starts with one of 7 valid prefixes.
4. **Verification test**: A test that exercises key code paths, captures log output, and asserts every `event` field starts with a valid prefix.

**Prefix-to-module mapping**:

| Prefix | Modules |
|--------|---------|
| `http_` | `backend/api/chat.py`, `backend/api/ingest.py`, `backend/middleware.py` |
| `agent_` | `backend/agent/nodes.py`, `backend/agent/research_nodes.py`, `backend/agent/meta_reasoning_nodes.py` |
| `retrieval_` | `backend/retrieval/searcher.py` (non-CB), `backend/retrieval/reranker.py` |
| `storage_` | `backend/storage/sqlite_db.py`, `backend/storage/qdrant_client.py` (non-CB), `backend/storage/indexing.py` |
| `ingestion_` | `backend/ingestion/pipeline.py` |
| `provider_` | `backend/providers/registry.py`, `backend/providers/ollama.py` |
| `circuit_` | CB events in `searcher.py`, `qdrant_client.py`, `nodes.py` |

**Test assertion updates**: Some existing tests assert on specific event name strings. These assertions must be updated after the rename (Wave 4 agents handle this).

## R5: Background Ingestion Trace ID Generation

**Decision**: Generate a NEW trace ID at `ingest_file()` entry, distinct from the HTTP request trace ID.

**Rationale**:
- The HTTP request returns 202 immediately; the background task may run for minutes
- The ingestion trace represents a distinct operation from the upload request
- The upload request's trace ID is already recorded in the 202 response's `X-Trace-ID` header
- Python `asyncio.create_task()` copies the parent's context, but the middleware clears it after the HTTP response completes — the background task's copy would be stale

**Implementation**:
```python
async def ingest_file(self, file_path, filename, collection_id, document_id, job_id, file_hash=None):
    ingestion_trace_id = str(uuid.uuid4())
    structlog.contextvars.bind_contextvars(trace_id=ingestion_trace_id)
    try:
        # ... existing method body ...
    finally:
        structlog.contextvars.clear_contextvars()
```

**Alternatives considered**:
- Inherit HTTP request trace ID: Rejected — stale after middleware cleanup; conflates two distinct operations
- Log the HTTP trace ID as a `parent_trace_id` field: Considered but deferred — adds complexity without clear user need in MVP
- Pass trace ID as parameter to `ingest_file()`: Rejected — would require signature change and caller updates; contextvars is simpler
