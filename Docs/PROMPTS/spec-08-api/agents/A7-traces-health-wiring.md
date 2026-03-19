# A7: Traces + Health + Wiring

**Agent type:** `system-architect`
**Model:** Sonnet 4.6
**Tasks:** T022, T023, T024, T025, T028, T029
**Wave:** 4 (serial -- runs after Waves 1-3 complete)

---

## Assigned Tasks

### T022: Write tests/unit/test_traces_router.py
### T023: Write tests/unit/test_health_router.py
### T024: Extend backend/api/traces.py
### T025: Rewrite backend/api/health.py
### T028: Update backend/main.py
### T029: Update backend/api/__init__.py

---

## File Targets

| File | Action |
|------|--------|
| `backend/api/traces.py` | Extend |
| `backend/api/health.py` | Rewrite |
| `backend/main.py` | Extend (register new routers) |
| `backend/api/__init__.py` | Update (export new modules) |
| `tests/unit/test_traces_router.py` | Create new |
| `tests/unit/test_health_router.py` | Create new |

---

## Implementation: backend/api/traces.py (Extend)

Read the current file first. It has:
- `GET /api/traces/{trace_id}` -- calls `db.get_trace()` (does not exist)
- `GET /api/traces` -- calls `db.list_traces()` (does not exist), missing session_id filter and offset

### Required Changes

**Problem**: The current code calls `db.get_trace()` and `db.list_traces()` which DO NOT EXIST in SQLiteDB. There are two options:

**Option A (Preferred)**: Add these methods to SQLiteDB as part of T006 (which is in Phase 2 foundational). If T006 has already been completed by another agent or the lead, use the new methods.

**Option B**: If T006 has NOT been completed, implement the queries directly in the router using raw SQL via `db.db.execute()`. This is less clean but unblocks progress.

Check whether `db.list_traces()` and `db.get_trace()` exist. If not, add them inline or request T006 completion first.

### Traces Endpoint Updates

```python
"""Trace retrieval and system statistics endpoints."""

import json
from fastapi import APIRouter, HTTPException, Query, Request

from backend.agent.schemas import QueryTraceResponse, QueryTraceDetailResponse, StatsResponse

router = APIRouter()


@router.get("/api/traces")
async def list_traces(
    request: Request,
    session_id: str | None = Query(None),
    collection_id: str | None = Query(None),
    min_confidence: int | None = Query(None, ge=0, le=100),
    max_confidence: int | None = Query(None, ge=0, le=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    """List query traces with optional filters and pagination."""
    db = request.app.state.db

    # Build query dynamically
    conditions = []
    params = []

    if session_id is not None:
        conditions.append("session_id = ?")
        params.append(session_id)
    if collection_id is not None:
        conditions.append("collections_searched LIKE ?")
        params.append(f"%{collection_id}%")
    if min_confidence is not None:
        conditions.append("confidence_score >= ?")
        params.append(min_confidence)
    if max_confidence is not None:
        conditions.append("confidence_score <= ?")
        params.append(max_confidence)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # Get total count
    count_sql = f"SELECT COUNT(*) as cnt FROM query_traces {where_clause}"
    cursor = await db.db.execute(count_sql, params)
    row = await cursor.fetchone()
    total = row["cnt"] if row else 0

    # Get page
    sql = f"""SELECT id, session_id, query, collections_searched,
                     confidence_score, latency_ms, llm_model,
                     meta_reasoning_triggered, created_at
              FROM query_traces {where_clause}
              ORDER BY created_at DESC LIMIT ? OFFSET ?"""
    cursor = await db.db.execute(sql, params + [limit, offset])
    rows = await cursor.fetchall()

    traces = []
    for r in rows:
        d = dict(r)
        # Parse collections_searched from JSON string to list
        cs = d.get("collections_searched", "[]")
        try:
            d["collections_searched"] = json.loads(cs) if cs else []
        except (json.JSONDecodeError, TypeError):
            d["collections_searched"] = []
        d["meta_reasoning_triggered"] = bool(d.get("meta_reasoning_triggered", 0))
        traces.append(d)

    return {"traces": traces, "total": total, "limit": limit, "offset": offset}


@router.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str, request: Request) -> dict:
    """Get full trace detail."""
    db = request.app.state.db

    cursor = await db.db.execute(
        """SELECT id, session_id, query, collections_searched,
                  chunks_retrieved_json, confidence_score, latency_ms,
                  llm_model, embed_model, sub_questions_json,
                  reasoning_steps_json, strategy_switches_json,
                  meta_reasoning_triggered, created_at
           FROM query_traces WHERE id = ?""",
        (trace_id,),
    )
    row = await cursor.fetchone()

    if not row:
        trace_id_req = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "TRACE_NOT_FOUND",
                "message": f"Trace '{trace_id}' not found",
                "details": {},
            },
            "trace_id": trace_id_req,
        })

    d = dict(row)

    # Parse JSON fields
    def parse_json(val, default=None):
        if default is None:
            default = []
        if not val:
            return default
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return default

    return {
        "id": d["id"],
        "session_id": d["session_id"],
        "query": d["query"],
        "collections_searched": parse_json(d.get("collections_searched"), []),
        "confidence_score": d.get("confidence_score"),
        "latency_ms": d.get("latency_ms", 0),
        "llm_model": d.get("llm_model"),
        "meta_reasoning_triggered": bool(d.get("meta_reasoning_triggered", 0)),
        "created_at": d.get("created_at", ""),
        # Detail fields
        "sub_questions": parse_json(d.get("sub_questions_json"), []),
        "chunks_retrieved": parse_json(d.get("chunks_retrieved_json"), []),
        "reasoning_steps": parse_json(d.get("reasoning_steps_json"), []),
        "strategy_switches": parse_json(d.get("strategy_switches_json"), []),
    }


@router.get("/api/stats")
async def system_stats(request: Request) -> dict:
    """Aggregate system statistics from historical query data."""
    db = request.app.state.db

    # Collection count
    collections = await db.list_collections()
    total_collections = len(collections)

    # Document + chunk counts
    total_documents = 0
    total_chunks = 0
    for c in collections:
        docs = await db.list_documents(c["id"])
        total_documents += len(docs)
        total_chunks += sum(d.get("chunk_count", 0) or 0 for d in docs)

    # Query trace aggregates
    cursor = await db.db.execute(
        """SELECT COUNT(*) as total_queries,
                  AVG(CAST(confidence_score AS FLOAT)) as avg_confidence,
                  AVG(CAST(latency_ms AS FLOAT)) as avg_latency_ms,
                  SUM(CASE WHEN meta_reasoning_triggered = 1 THEN 1 ELSE 0 END) as meta_count
           FROM query_traces"""
    )
    row = await cursor.fetchone()
    stats = dict(row) if row else {}

    total_queries = stats.get("total_queries", 0) or 0
    avg_confidence = round(stats.get("avg_confidence", 0) or 0, 1)
    avg_latency_ms = round(stats.get("avg_latency_ms", 0) or 0, 1)
    meta_count = stats.get("meta_count", 0) or 0
    meta_rate = round(meta_count / max(total_queries, 1), 3)

    return StatsResponse(
        total_collections=total_collections,
        total_documents=total_documents,
        total_chunks=total_chunks,
        total_queries=total_queries,
        avg_confidence=avg_confidence,
        avg_latency_ms=avg_latency_ms,
        meta_reasoning_rate=meta_rate,
    ).model_dump()
```

### Key Detail: Empty Filter Returns Empty List

When `session_id` filter matches no records, return `{"traces": [], "total": 0, ...}` -- NOT a 404.

---

## Implementation: backend/api/health.py (Rewrite)

```python
"""System health check endpoint with per-service latency measurements."""

import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agent.schemas import HealthResponse, HealthServiceStatus
from backend.config import settings

router = APIRouter()


@router.get("/api/health")
async def health(request: Request):
    """Probe SQLite, Qdrant, and Ollama with latency measurements."""
    services = []
    all_ok = True

    # 1. SQLite probe
    sqlite_status = await _probe_sqlite(request)
    services.append(sqlite_status)
    if sqlite_status.status == "error":
        all_ok = False

    # 2. Qdrant probe
    qdrant_status = await _probe_qdrant(request)
    services.append(qdrant_status)
    if qdrant_status.status == "error":
        all_ok = False

    # 3. Ollama probe
    ollama_status = await _probe_ollama()
    services.append(ollama_status)
    if ollama_status.status == "error":
        all_ok = False

    status = "healthy" if all_ok else "degraded"
    status_code = 200 if all_ok else 503

    response = HealthResponse(
        status=status,
        services=services,
    )

    return JSONResponse(
        content=response.model_dump(),
        status_code=status_code,
    )


async def _probe_sqlite(request: Request) -> HealthServiceStatus:
    """Probe SQLite with SELECT 1."""
    start = time.monotonic()
    try:
        db = request.app.state.db
        await db.db.execute("SELECT 1")
        latency = round((time.monotonic() - start) * 1000, 1)
        return HealthServiceStatus(name="sqlite", status="ok", latency_ms=latency)
    except Exception as e:
        return HealthServiceStatus(name="sqlite", status="error", error_message=str(e))


async def _probe_qdrant(request: Request) -> HealthServiceStatus:
    """Probe Qdrant health check."""
    start = time.monotonic()
    try:
        qdrant = request.app.state.qdrant
        is_healthy = await qdrant.health_check()
        latency = round((time.monotonic() - start) * 1000, 1)
        if is_healthy:
            return HealthServiceStatus(name="qdrant", status="ok", latency_ms=latency)
        else:
            return HealthServiceStatus(name="qdrant", status="error", error_message="Unreachable")
    except Exception as e:
        return HealthServiceStatus(name="qdrant", status="error", error_message=str(e))


async def _probe_ollama() -> HealthServiceStatus:
    """Probe Ollama via /api/tags endpoint."""
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            latency = round((time.monotonic() - start) * 1000, 1)
            if resp.status_code == 200:
                return HealthServiceStatus(name="ollama", status="ok", latency_ms=latency)
            else:
                return HealthServiceStatus(
                    name="ollama", status="error",
                    error_message=f"HTTP {resp.status_code}",
                )
    except Exception as e:
        return HealthServiceStatus(name="ollama", status="error", error_message=str(e))
```

### Key Details

- `latency_ms` is a float (e.g., 0.4, 12.3, 45.1) -- measured with `time.monotonic()`
- When a service errors, `latency_ms` is `None` and `error_message` has the reason
- Overall status: 200 `healthy` if ALL ok, 503 `degraded` if ANY error
- Performance target: respond in < 1 second (SC-008), target < 50ms per constitution

---

## Implementation: backend/main.py (Extend)

Read the current file. Add 3 new router imports and registrations.

### Changes

1. Add to imports (after existing router imports):
```python
from backend.api import collections, documents, chat, traces, providers, health, ingest, models, settings as settings_router
```

Note: `settings` name conflicts with `from backend.config import settings`. Use alias `settings_router` or import the router object directly:

```python
from backend.api import ingest as ingest_module
from backend.api import models as models_module
from backend.api import settings as settings_module
```

2. Add router registrations (after existing `app.include_router` calls):
```python
app.include_router(ingest_module.router, tags=["ingest"])
app.include_router(models_module.router, tags=["models"])
app.include_router(settings_module.router, tags=["settings"])
```

### Name Conflict Warning

The existing code has `from backend.config import settings` at the top level. The Python module `backend.api.settings` will conflict with this name. Use aliased imports:

```python
from backend.api import settings as api_settings
# ...
app.include_router(api_settings.router, tags=["settings"])
```

---

## Implementation: backend/api/__init__.py (Update)

The current file is essentially empty (1 line). Update to export new modules:

```python
"""API routers package."""
```

No explicit exports needed -- the routers are imported directly in main.py. But verify the file does not block imports.

---

## Test Specifications

### test_traces_router.py

Mock `SQLiteDB` (specifically `db.db.execute()` for raw SQL). Test:

1. **Pagination**: `limit=5, offset=0` returns first 5; `offset=5` returns next batch
2. **session_id filter**: Only traces with matching session_id returned
3. **Empty result**: Filter matching nothing returns `{"traces": [], "total": 0}` -- NOT 404
4. **GET /traces/{id}**: Returns full detail with sub_questions, chunks_retrieved, etc.
5. **GET /traces/{id} 404**: Returns `TRACE_NOT_FOUND`
6. **GET /stats**: Returns StatsResponse with all 7 numeric fields
7. **GET /stats empty**: When no traces exist, returns zeroes (not error)
8. **collections_searched**: Correctly parsed from JSON string to list

### test_health_router.py

Mock db, qdrant, and httpx (for Ollama). Test:

1. **All healthy**: 200, status="healthy", all services "ok" with latency_ms
2. **One service down**: 503, status="degraded", failed service has error_message
3. **latency_ms is float**: Not int, not None when healthy
4. **error_message is None when ok**: Only present on error
5. **Three services**: sqlite, qdrant, ollama all present in response

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-traceshealth tests/unit/test_traces_router.py tests/unit/test_health_router.py
cat Docs/Tests/spec08-traceshealth.status
cat Docs/Tests/spec08-traceshealth.summary
```

---

## Key Constraints

- Empty filter -> empty list, NOT 404 (this is explicitly called out in the spec edge cases)
- `confidence_score` is int 0-100 in the DB (INTEGER column)
- `meta_reasoning_triggered` is stored as INTEGER (0/1) in SQLite -- convert to bool
- `collections_searched` is stored as JSON string -- parse to list for API response
- `db.list_documents(collection_id)` requires collection_id -- iterate collections for total count
- Use `db.db.execute()` for raw SQL queries that SQLiteDB doesn't have methods for
- Health probes use `time.monotonic()` for accurate latency measurement
- Import aliasing needed for `settings` module to avoid name conflict with config

---

## What NOT to Do

- Do NOT return 404 when a filter matches no traces -- return empty list
- Do NOT use `db.list_query_traces()` for the paginated traces endpoint -- its signature is incompatible (requires session_id, no offset)
- Do NOT change middleware order in main.py -- it is correct as-is
- Do NOT remove existing router registrations -- only ADD the 3 new ones
- Do NOT change the lifespan function -- it is correct
- Do NOT run pytest inside Claude Code -- use the external test runner
