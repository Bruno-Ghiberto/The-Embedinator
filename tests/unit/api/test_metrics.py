"""Unit tests for GET /api/metrics endpoint (FR-005–FR-008, spec-15 US2)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.traces import router


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_app(db=None):
    """Create a test FastAPI app with the traces router and mocked state."""
    app = FastAPI()
    app.include_router(router)

    mock_db = db or AsyncMock()
    app.state.db = mock_db
    # State objects for circuit breaker inspection
    app.state.qdrant = None
    app.state.hybrid_searcher = None

    @app.middleware("http")
    async def _add_trace_id(request, call_next):
        request.state.trace_id = "test-trace-id"
        return await call_next(request)

    return app


def _make_db(traces: list[dict] | None = None, active_jobs: int = 0) -> AsyncMock:
    """Create a mock SQLiteDB with preset return values for metrics tests."""
    db = AsyncMock()
    db.get_query_traces_by_timerange = AsyncMock(return_value=traces or [])

    # Mock the raw db.db.execute + cursor.fetchone for active ingestion jobs
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=(active_jobs,))
    db.db.execute = AsyncMock(return_value=cursor)

    return db


def _make_trace(
    created_at: str = "2026-03-18T12:00:00+00:00",
    latency_ms: int = 500,
    confidence_score: int = 75,
    meta_reasoning_triggered: int = 0,
    error_type: str | None = None,
) -> dict:
    return {
        "id": "trace-1",
        "session_id": "sess-1",
        "query": "test",
        "created_at": created_at,
        "latency_ms": latency_ms,
        "confidence_score": confidence_score,
        "meta_reasoning_triggered": meta_reasoning_triggered,
        "error_type": error_type,
        "collections_searched": '["c1"]',
        "llm_model": "qwen2.5:7b",
    }


# ── T022: Basic 200 response with all required fields ────────────────────────


class TestMetricsBasicResponse:
    """T022: GET /api/metrics returns 200 with all MetricsResponse fields."""

    def test_returns_200_with_required_fields(self):
        """GET /api/metrics returns 200 and all MetricsResponse top-level fields."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert resp.status_code == 200
        data = resp.json()
        assert "window" in data
        assert "bucket_size" in data
        assert "buckets" in data
        assert "circuit_breakers" in data
        assert "active_ingestion_jobs" in data

    def test_buckets_is_a_list(self):
        """buckets field is a list."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert isinstance(data["buckets"], list)

    def test_bucket_entries_have_required_fields(self):
        """Each MetricsBucket entry has all required fields."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert len(data["buckets"]) > 0
        bucket = data["buckets"][0]
        for field in (
            "timestamp",
            "query_count",
            "avg_latency_ms",
            "p95_latency_ms",
            "avg_confidence",
            "meta_reasoning_count",
            "error_count",
        ):
            assert field in bucket, f"Missing field: {field}"


# ── T023: Bucket-size mapping per window parameter ───────────────────────────


class TestBucketSizeMapping:
    """T023: window param controls bucket_size and bucket count."""

    def test_1h_window_has_5m_bucket_size(self):
        """window=1h → bucket_size=5m."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=1h")

        assert resp.status_code == 200
        assert resp.json()["bucket_size"] == "5m"

    def test_1h_window_has_12_buckets(self):
        """window=1h → 12 buckets (60 min / 5 min)."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=1h")

        assert len(resp.json()["buckets"]) == 12

    def test_24h_window_has_1h_bucket_size(self):
        """window=24h → bucket_size=1h."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=24h")

        assert resp.status_code == 200
        assert resp.json()["bucket_size"] == "1h"

    def test_24h_window_has_24_buckets(self):
        """window=24h → 24 buckets (24h / 1h)."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=24h")

        assert len(resp.json()["buckets"]) == 24

    def test_7d_window_has_1d_bucket_size(self):
        """window=7d → bucket_size=1d."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=7d")

        assert resp.status_code == 200
        assert resp.json()["bucket_size"] == "1d"

    def test_7d_window_has_7_buckets(self):
        """window=7d → 7 buckets (7 days / 1 day)."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=7d")

        assert len(resp.json()["buckets"]) == 7

    def test_default_window_is_24h(self):
        """Default window (no param) → window=24h, bucket_size=1h."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert data["window"] == "24h"
        assert data["bucket_size"] == "1h"


# ── T024: Invalid window → 400 VALIDATION_ERROR ──────────────────────────────


class TestInvalidWindow:
    """T024: Invalid window parameter returns 400 with error envelope."""

    def test_30d_window_returns_400(self):
        """window=30d → HTTP 400."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=30d")

        assert resp.status_code == 400

    def test_30d_window_has_validation_error_code(self):
        """window=30d → error envelope with code=VALIDATION_ERROR."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=30d")

        detail = resp.json()["detail"]
        assert detail["code"] == "VALIDATION_ERROR"

    def test_invalid_window_has_message(self):
        """window=invalid → error envelope has a message."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics?window=invalid")

        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "message" in detail


# ── T025: Empty database → zero-count buckets, no 500 ───────────────────────


class TestEmptyDatabase:
    """T025: Empty DB returns empty-count buckets without raising 500 (SC-007)."""

    def test_empty_db_returns_200(self):
        """Empty query_traces → 200, not 500."""
        db = _make_db(traces=[])
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert resp.status_code == 200

    def test_empty_db_buckets_all_have_zero_query_count(self):
        """Empty query_traces → all buckets have query_count=0."""
        db = _make_db(traces=[])
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert all(b["query_count"] == 0 for b in data["buckets"])

    def test_empty_db_buckets_all_have_zero_latency(self):
        """Empty query_traces → all buckets have avg_latency_ms=0."""
        db = _make_db(traces=[])
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert all(b["avg_latency_ms"] == 0 for b in data["buckets"])


# ── T026: circuit_breakers has exactly 3 keys ────────────────────────────────


class TestCircuitBreakers:
    """T026: circuit_breakers has exactly 3 keys: qdrant, inference, search."""

    def test_circuit_breakers_has_exactly_3_keys(self):
        """circuit_breakers dict has exactly 3 keys."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        cbs = resp.json()["circuit_breakers"]
        assert len(cbs) == 3

    def test_circuit_breakers_has_qdrant_key(self):
        """circuit_breakers contains 'qdrant' key."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert "qdrant" in resp.json()["circuit_breakers"]

    def test_circuit_breakers_has_inference_key(self):
        """circuit_breakers contains 'inference' key."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert "inference" in resp.json()["circuit_breakers"]

    def test_circuit_breakers_has_search_key(self):
        """circuit_breakers contains 'search' key."""
        db = _make_db()
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert "search" in resp.json()["circuit_breakers"]

    def test_circuit_breaker_none_state_is_unknown(self):
        """When app.state.qdrant is None, circuit_breakers.qdrant.state='unknown'."""
        db = _make_db()
        app = _make_app(db=db)
        app.state.qdrant = None
        client = TestClient(app)

        resp = client.get("/api/metrics")

        qdrant_cb = resp.json()["circuit_breakers"]["qdrant"]
        assert qdrant_cb["state"] == "unknown"

    def test_circuit_breaker_closed_state(self):
        """When app.state.qdrant._circuit_open is False → state='closed'."""
        db = _make_db()
        app = _make_app(db=db)
        mock_qdrant = MagicMock()
        mock_qdrant._circuit_open = False
        mock_qdrant._failure_count = 0
        app.state.qdrant = mock_qdrant
        client = TestClient(app)

        resp = client.get("/api/metrics")

        qdrant_cb = resp.json()["circuit_breakers"]["qdrant"]
        assert qdrant_cb["state"] == "closed"

    def test_circuit_breaker_open_state(self):
        """When app.state.qdrant._circuit_open is True → state='open'."""
        db = _make_db()
        app = _make_app(db=db)
        mock_qdrant = MagicMock()
        mock_qdrant._circuit_open = True
        mock_qdrant._failure_count = 5
        app.state.qdrant = mock_qdrant
        client = TestClient(app)

        resp = client.get("/api/metrics")

        qdrant_cb = resp.json()["circuit_breakers"]["qdrant"]
        assert qdrant_cb["state"] == "open"
        assert qdrant_cb["failure_count"] == 5


# ── T027: active_ingestion_jobs is an integer ────────────────────────────────


class TestActiveIngestionJobs:
    """T027: active_ingestion_jobs is an integer field in the response."""

    def test_active_ingestion_jobs_is_integer(self):
        """active_ingestion_jobs is an int in the response."""
        db = _make_db(active_jobs=0)
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert isinstance(data["active_ingestion_jobs"], int)

    def test_active_ingestion_jobs_reflects_count(self):
        """active_ingestion_jobs equals the mock COUNT(*) from ingestion_jobs."""
        db = _make_db(active_jobs=3)
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        data = resp.json()
        assert data["active_ingestion_jobs"] == 3

    def test_active_ingestion_jobs_zero_when_none_processing(self):
        """active_ingestion_jobs is 0 when no jobs are processing."""
        db = _make_db(active_jobs=0)
        app = _make_app(db=db)
        client = TestClient(app)

        resp = client.get("/api/metrics")

        assert resp.json()["active_ingestion_jobs"] == 0
