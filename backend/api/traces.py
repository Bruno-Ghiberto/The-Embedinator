"""Trace retrieval and system statistics endpoints."""

import json
import math
import time
from collections import defaultdict
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, Query, Request

from backend.agent.schemas import (
    CircuitBreakerSnapshot,
    MetricsBucket,
    MetricsResponse,
    StatsResponse,
)

logger = structlog.get_logger().bind(component=__name__)

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
    count_sql = f"SELECT COUNT(*) as cnt FROM query_traces {where_clause}"  # noqa: S608
    cursor = await db.db.execute(count_sql, params)
    row = await cursor.fetchone()
    total = row["cnt"] if row else 0

    # Get page
    sql = (
        f"SELECT id, session_id, query, collections_searched,"  # noqa: S608
        f" confidence_score, latency_ms, llm_model,"
        f" meta_reasoning_triggered, created_at"
        f" FROM query_traces {where_clause}"
        f" ORDER BY created_at DESC LIMIT ? OFFSET ?"
    )
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
                  meta_reasoning_triggered, created_at,
                  stage_timings_json
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
        "stage_timings": parse_json(d.get("stage_timings_json"), {}),
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


@router.get("/api/metrics", response_model=MetricsResponse)
async def metrics(
    window: str = Query(default="24h"),
    request: Request = ...,
) -> MetricsResponse:
    """Return time-bucketed query metrics for the requested time window."""
    if window not in ("1h", "24h", "7d"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": "Invalid window. Must be one of: 1h, 24h, 7d",
                "details": None,
            },
        )

    db = request.app.state.db

    # ── Bucket config ────────────────────────────────────────────────────────
    bucket_size_map = {"1h": "5m", "24h": "1h", "7d": "1d"}
    bucket_seconds_map = {"1h": 300, "24h": 3600, "7d": 86400}
    window_seconds_map = {"1h": 3600, "24h": 86400, "7d": 604800}

    bucket_size = bucket_size_map[window]
    bucket_secs = bucket_seconds_map[window]
    window_secs = window_seconds_map[window]

    now_ts = int(time.time())
    # Floor start_ts to the nearest bucket boundary
    start_ts = ((now_ts - window_secs) // bucket_secs) * bucket_secs

    start_iso = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
    now_iso = datetime.fromtimestamp(now_ts, tz=timezone.utc).isoformat()

    traces = await db.get_query_traces_by_timerange(start_iso, now_iso)

    # ── Group traces into bucket slots ───────────────────────────────────────
    bucket_data: dict[int, list] = defaultdict(list)
    for trace in traces:
        created_at = trace.get("created_at") or ""
        if isinstance(created_at, str) and created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                ts = int(dt.timestamp())
            except (ValueError, OSError):
                continue
        else:
            ts = int(created_at) if created_at else 0
        bucket_key = (ts // bucket_secs) * bucket_secs
        bucket_data[bucket_key].append(trace)

    # ── Fill all expected bucket slots (including empty ones) ────────────────
    max_buckets = window_secs // bucket_secs
    all_bucket_keys = [start_ts + i * bucket_secs for i in range(max_buckets)]

    buckets = []
    for bk in all_bucket_keys:
        data = bucket_data.get(bk, [])
        if not data:
            buckets.append(MetricsBucket(
                timestamp=datetime.fromtimestamp(bk, tz=timezone.utc).isoformat(),
                query_count=0,
                avg_latency_ms=0,
                p95_latency_ms=0,
                avg_confidence=0,
                meta_reasoning_count=0,
                error_count=0,
            ))
        else:
            latencies = sorted([t.get("latency_ms", 0) or 0 for t in data])
            p95_idx = max(0, math.ceil(0.95 * len(latencies)) - 1)
            confidences = [t.get("confidence_score", 0) or 0 for t in data]
            buckets.append(MetricsBucket(
                timestamp=datetime.fromtimestamp(bk, tz=timezone.utc).isoformat(),
                query_count=len(data),
                avg_latency_ms=int(sum(latencies) / len(latencies)),
                p95_latency_ms=latencies[p95_idx],
                avg_confidence=round(sum(confidences) / len(confidences)),
                meta_reasoning_count=sum(
                    1 for t in data if t.get("meta_reasoning_triggered")
                ),
                error_count=sum(1 for t in data if t.get("error_type")),
            ))

    # Sort ascending by timestamp
    buckets.sort(key=lambda b: b.timestamp)

    # ── Circuit breaker states ────────────────────────────────────────────────
    def _get_cb_state(instance) -> CircuitBreakerSnapshot:
        if instance is None:
            return CircuitBreakerSnapshot(state="unknown", failure_count=0)
        return CircuitBreakerSnapshot(
            state="open" if getattr(instance, "_circuit_open", False) else "closed",
            failure_count=getattr(instance, "_failure_count", 0),
        )

    import backend.agent.nodes as nodes_module  # noqa: PLC0415

    inf_open = getattr(nodes_module, "_inf_circuit_open", None)
    circuit_breakers = {
        "qdrant": _get_cb_state(getattr(request.app.state, "qdrant", None)),
        "search": _get_cb_state(getattr(request.app.state, "hybrid_searcher", None)),
        "inference": (
            CircuitBreakerSnapshot(state="unknown", failure_count=0)
            if inf_open is None
            else CircuitBreakerSnapshot(
                state="open" if inf_open else "closed",
                failure_count=getattr(nodes_module, "_inf_failure_count", 0),
            )
        ),
    }

    # ── Active ingestion jobs ─────────────────────────────────────────────────
    try:
        cursor = await db.db.execute(
            "SELECT COUNT(*) FROM ingestion_jobs WHERE status = ?",
            ("processing",),
        )
        row = await cursor.fetchone()
        active_ingestion_jobs = row[0] if row else 0
    except Exception:
        active_ingestion_jobs = 0

    return MetricsResponse(
        window=window,
        bucket_size=bucket_size,
        buckets=buckets,
        circuit_breakers=circuit_breakers,
        active_ingestion_jobs=active_ingestion_jobs,
    )
