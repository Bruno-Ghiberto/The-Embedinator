"""E2E: Observability — seed a trace, verify /api/traces and /api/metrics.

Uses real in-memory SQLiteDB so traces are actually persisted and queryable.
All tests marked @pytest.mark.e2e.
"""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from unittest.mock import AsyncMock

from backend.api import health, traces
from backend.middleware import TraceIDMiddleware
from backend.storage.sqlite_db import SQLiteDB


def _make_observability_app(db: SQLiteDB) -> "FastAPI":
    """Minimal app with traces + health routers backed by a real in-memory DB."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    app.include_router(traces.router)
    app.include_router(health.router)

    app.state.db = db
    # qdrant + hybrid_searcher set to None → circuit_breakers will report "unknown"
    app.state.qdrant = None
    app.state.hybrid_searcher = None

    return app


async def _seed_trace(db: SQLiteDB) -> str:
    """Insert one query trace directly into the DB and return its id."""
    trace_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    await db.create_query_trace(
        id=trace_id,
        session_id=session_id,
        query="What is the meaning of life?",
        collections_searched=json.dumps(["test-collection"]),
        chunks_retrieved_json=json.dumps([]),
        latency_ms=250,
        llm_model="qwen2.5:7b",
        embed_model="nomic-embed-text",
        confidence_score=72,
        meta_reasoning_triggered=False,
        provider_name="ollama",
    )
    return trace_id


@pytest.mark.e2e
class TestObservabilityE2E:
    """Traces and metrics endpoints return populated data after a chat request."""

    @pytest_asyncio.fixture
    async def db(self):
        """Isolated in-memory SQLiteDB — real trace persistence."""
        instance = SQLiteDB(":memory:")
        await instance.connect()
        yield instance
        await instance.close()

    @pytest_asyncio.fixture
    async def client_with_trace(self, db):
        """Client connected to app that already has one trace seeded."""
        # Seed a trace directly (no LLM / Qdrant needed)
        await _seed_trace(db)

        app = _make_observability_app(db)
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
                yield c
        finally:
            pass  # db fixture handles cleanup

    async def test_traces_returns_at_least_one_entry(self, client_with_trace):
        """GET /api/traces returns a list with at least 1 entry after seeding."""
        try:
            resp = await client_with_trace.get("/api/traces")
            assert resp.status_code == 200, f"Unexpected status: {resp.status_code} — {resp.text}"
            data = resp.json()
            assert "traces" in data, f"Response missing 'traces' key: {data}"
            assert len(data["traces"]) >= 1, f"Expected at least 1 trace, got {len(data['traces'])}"
        finally:
            pass

    async def test_traces_response_has_expected_fields(self, client_with_trace):
        """Each trace entry contains the standard observation fields."""
        try:
            resp = await client_with_trace.get("/api/traces")
            assert resp.status_code == 200
            traces_list = resp.json()["traces"]
            assert traces_list, "No traces returned"
            trace = traces_list[0]
            for field in ("id", "session_id", "query", "confidence_score", "latency_ms", "created_at"):
                assert field in trace, f"Trace entry missing field '{field}': {trace}"
        finally:
            pass

    async def test_metrics_returns_circuit_breaker_and_buckets(self, client_with_trace):
        """GET /api/metrics returns circuit_breakers dict and buckets list."""
        try:
            resp = await client_with_trace.get("/api/metrics")
            assert resp.status_code == 200, f"Metrics failed: {resp.status_code} — {resp.text}"
            data = resp.json()
            # Verify circuit breaker state is present
            assert "circuit_breakers" in data, f"Response missing 'circuit_breakers' key. Keys: {list(data.keys())}"
            assert isinstance(data["circuit_breakers"], dict)
            # Verify time-bucketed latency data is present
            assert "buckets" in data, f"Response missing 'buckets' key. Keys: {list(data.keys())}"
            assert isinstance(data["buckets"], list)
        finally:
            pass

    async def test_metrics_circuit_breaker_has_state_and_failure_count(self, client_with_trace):
        """Each circuit breaker snapshot has 'state' and 'failure_count' fields."""
        try:
            resp = await client_with_trace.get("/api/metrics")
            assert resp.status_code == 200
            data = resp.json()
            cbs = data.get("circuit_breakers", {})
            assert cbs, "No circuit breaker data returned"
            for cb_name, cb_data in cbs.items():
                assert "state" in cb_data, f"Circuit breaker '{cb_name}' missing 'state': {cb_data}"
                assert "failure_count" in cb_data, f"Circuit breaker '{cb_name}' missing 'failure_count': {cb_data}"
        finally:
            pass

    async def test_metrics_buckets_contain_latency_data(self, client_with_trace):
        """Metric buckets contain avg_latency_ms and p95_latency_ms fields."""
        try:
            resp = await client_with_trace.get("/api/metrics")
            assert resp.status_code == 200
            data = resp.json()
            buckets = data.get("buckets", [])
            assert buckets, "No metric buckets returned"
            # Check the first bucket has latency fields
            first_bucket = buckets[0]
            assert "avg_latency_ms" in first_bucket, f"Bucket missing 'avg_latency_ms': {first_bucket}"
            assert "p95_latency_ms" in first_bucket, f"Bucket missing 'p95_latency_ms': {first_bucket}"
        finally:
            pass
