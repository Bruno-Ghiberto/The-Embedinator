"""Unit tests for traces router — T022.

Tests pagination (limit, offset), session_id filter, empty result returns []
not 404, GET /traces/{id} 200 and 404 TRACE_NOT_FOUND, GET /stats returns
StatsResponse with all 7 numeric fields.
Mocks SQLiteDB (db.db.execute for raw SQL, db.list_collections/list_documents).
"""

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.traces import router


def _make_app(db=None):
    """Create a test FastAPI app with mocked db."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()

    @app.middleware("http")
    async def _trace_middleware(request, call_next):
        request.state.trace_id = "test-trace-id"
        return await call_next(request)

    return app


def _make_cursor(fetchone_val=None, fetchall_val=None):
    """Create a mock async cursor with preset return values."""
    cursor = AsyncMock()
    cursor.fetchone = AsyncMock(return_value=fetchone_val)
    cursor.fetchall = AsyncMock(return_value=fetchall_val or [])
    return cursor


def _make_trace_row(
    trace_id="t1",
    session_id="sess1",
    query="test query",
    collections_searched='["c1"]',
    confidence_score=75,
    latency_ms=500,
    llm_model="qwen2.5:7b",
    meta_reasoning_triggered=0,
    created_at="2026-03-15T00:00:00Z",
    chunks_retrieved_json=None,
    sub_questions_json=None,
    reasoning_steps_json=None,
    strategy_switches_json=None,
    embed_model=None,
):
    """Create a dict mimicking a query_traces DB row."""
    return {
        "id": trace_id,
        "session_id": session_id,
        "query": query,
        "collections_searched": collections_searched,
        "confidence_score": confidence_score,
        "latency_ms": latency_ms,
        "llm_model": llm_model,
        "meta_reasoning_triggered": meta_reasoning_triggered,
        "created_at": created_at,
        "chunks_retrieved_json": chunks_retrieved_json,
        "sub_questions_json": sub_questions_json,
        "reasoning_steps_json": reasoning_steps_json,
        "strategy_switches_json": strategy_switches_json,
        "embed_model": embed_model,
    }


# ── GET /api/traces ──────────────────────────────────────────────


class TestListTraces:
    """GET /api/traces — paginated listing with filters."""

    def test_pagination_limit_offset(self):
        """limit=5, offset=0 returns first 5 with total count."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 10})
        rows = [_make_trace_row(trace_id=f"t{i}") for i in range(5)]
        data_cursor = _make_cursor(fetchall_val=rows)
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces?limit=5&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 10
        assert data["limit"] == 5
        assert data["offset"] == 0
        assert len(data["traces"]) == 5

    def test_pagination_offset_5(self):
        """offset=5 returns next batch."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 10})
        rows = [_make_trace_row(trace_id=f"t{i}") for i in range(5)]
        data_cursor = _make_cursor(fetchall_val=rows)
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces?limit=5&offset=5")
        assert resp.status_code == 200
        data = resp.json()
        assert data["offset"] == 5
        assert data["total"] == 10

    def test_session_id_filter(self):
        """session_id filter returns only matching traces."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 1})
        rows = [_make_trace_row(session_id="target-session")]
        data_cursor = _make_cursor(fetchall_val=rows)
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces?session_id=target-session")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["traces"]) == 1
        assert data["traces"][0]["session_id"] == "target-session"

    def test_empty_result_returns_empty_list_not_404(self):
        """Empty filter matching returns [] not 404."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 0})
        data_cursor = _make_cursor(fetchall_val=[])
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces?session_id=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["traces"] == []
        assert data["total"] == 0

    def test_collections_searched_parsed_from_json(self):
        """collections_searched is parsed from JSON string to list."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 1})
        rows = [_make_trace_row(collections_searched='["col-a", "col-b"]')]
        data_cursor = _make_cursor(fetchall_val=rows)
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        trace = resp.json()["traces"][0]
        assert trace["collections_searched"] == ["col-a", "col-b"]

    def test_meta_reasoning_triggered_is_bool(self):
        """meta_reasoning_triggered is converted from int to bool."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 1})
        rows = [_make_trace_row(meta_reasoning_triggered=1)]
        data_cursor = _make_cursor(fetchall_val=rows)
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        trace = resp.json()["traces"][0]
        assert trace["meta_reasoning_triggered"] is True

    def test_default_pagination(self):
        """Default limit=20, offset=0 when not specified."""
        db = AsyncMock()
        count_cursor = _make_cursor(fetchone_val={"cnt": 0})
        data_cursor = _make_cursor(fetchall_val=[])
        db.db.execute = AsyncMock(side_effect=[count_cursor, data_cursor])

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert data["limit"] == 20
        assert data["offset"] == 0


# ── GET /api/traces/{trace_id} ────────────────────────────────────


class TestGetTrace:
    """GET /api/traces/{trace_id} — full detail or 404."""

    def test_get_existing_200(self):
        """Returns full detail with parsed JSON fields."""
        db = AsyncMock()
        row = _make_trace_row(
            sub_questions_json='["q1", "q2"]',
            chunks_retrieved_json='[{"chunk_id": "c1"}]',
            reasoning_steps_json='[{"step": 1}]',
            strategy_switches_json='[{"from": "a"}]',
        )
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == "t1"
        assert data["sub_questions"] == ["q1", "q2"]
        assert data["chunks_retrieved"] == [{"chunk_id": "c1"}]
        assert data["reasoning_steps"] == [{"step": 1}]
        assert data["strategy_switches"] == [{"from": "a"}]

    def test_get_existing_null_json_fields(self):
        """Null JSON fields return empty lists."""
        db = AsyncMock()
        row = _make_trace_row()  # All JSON fields are None
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sub_questions"] == []
        assert data["chunks_retrieved"] == []
        assert data["reasoning_steps"] == []
        assert data["strategy_switches"] == []

    def test_get_nonexistent_404(self):
        """Returns 404 TRACE_NOT_FOUND."""
        db = AsyncMock()
        cursor = _make_cursor(fetchone_val=None)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/nonexistent")
        assert resp.status_code == 404
        body = resp.json()
        assert body["detail"]["error"]["code"] == "TRACE_NOT_FOUND"

    def test_404_includes_trace_id(self):
        """404 response includes trace_id from request state."""
        db = AsyncMock()
        cursor = _make_cursor(fetchone_val=None)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/nonexistent")
        body = resp.json()
        assert body["detail"]["trace_id"] == "test-trace-id"


# ── GET /api/stats ───────────────────────────────────────────────


class TestStats:
    """GET /api/stats — aggregate system statistics."""

    def test_returns_all_7_fields(self):
        """StatsResponse has all 7 numeric fields."""
        db = AsyncMock()
        db.list_collections = AsyncMock(
            return_value=[
                {"id": "c1", "name": "docs"},
                {"id": "c2", "name": "notes"},
            ]
        )
        db.list_documents = AsyncMock(
            return_value=[
                {"id": "d1", "chunk_count": 100},
                {"id": "d2", "chunk_count": 50},
            ]
        )
        stats_cursor = _make_cursor(
            fetchone_val={
                "total_queries": 20,
                "avg_confidence": 72.5,
                "avg_latency_ms": 1500.0,
                "meta_count": 3,
            }
        )
        db.db.execute = AsyncMock(return_value=stats_cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()

        assert "total_collections" in data
        assert "total_documents" in data
        assert "total_chunks" in data
        assert "total_queries" in data
        assert "avg_confidence" in data
        assert "avg_latency_ms" in data
        assert "meta_reasoning_rate" in data

    def test_stats_values_computed_correctly(self):
        """Verify aggregate computation."""
        db = AsyncMock()
        db.list_collections = AsyncMock(
            return_value=[
                {"id": "c1", "name": "docs"},
                {"id": "c2", "name": "notes"},
            ]
        )
        db.list_documents = AsyncMock(
            return_value=[
                {"id": "d1", "chunk_count": 100},
                {"id": "d2", "chunk_count": 50},
            ]
        )
        stats_cursor = _make_cursor(
            fetchone_val={
                "total_queries": 20,
                "avg_confidence": 72.5,
                "avg_latency_ms": 1500.0,
                "meta_count": 3,
            }
        )
        db.db.execute = AsyncMock(return_value=stats_cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/stats")
        data = resp.json()

        assert data["total_collections"] == 2
        # 2 docs per collection x 2 collections
        assert data["total_documents"] == 4
        # (100+50) per collection x 2 collections
        assert data["total_chunks"] == 300
        assert data["total_queries"] == 20
        assert data["avg_confidence"] == 72.5
        assert data["avg_latency_ms"] == 1500.0
        # 3/20 = 0.15
        assert data["meta_reasoning_rate"] == 0.15

    def test_stats_empty_returns_zeroes(self):
        """No data returns zeroes, not error."""
        db = AsyncMock()
        db.list_collections = AsyncMock(return_value=[])
        stats_cursor = _make_cursor(
            fetchone_val={
                "total_queries": 0,
                "avg_confidence": None,
                "avg_latency_ms": None,
                "meta_count": 0,
            }
        )
        db.db.execute = AsyncMock(return_value=stats_cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_collections"] == 0
        assert data["total_documents"] == 0
        assert data["total_chunks"] == 0
        assert data["total_queries"] == 0
        assert data["avg_confidence"] == 0
        assert data["avg_latency_ms"] == 0
        assert data["meta_reasoning_rate"] == 0

    def test_stats_null_chunk_count_treated_as_zero(self):
        """Documents with null chunk_count contribute 0 to total_chunks."""
        db = AsyncMock()
        db.list_collections = AsyncMock(return_value=[{"id": "c1", "name": "test"}])
        db.list_documents = AsyncMock(
            return_value=[
                {"id": "d1", "chunk_count": None},
                {"id": "d2", "chunk_count": 10},
            ]
        )
        stats_cursor = _make_cursor(
            fetchone_val={
                "total_queries": 0,
                "avg_confidence": None,
                "avg_latency_ms": None,
                "meta_count": 0,
            }
        )
        db.db.execute = AsyncMock(return_value=stats_cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/stats")
        data = resp.json()
        assert data["total_chunks"] == 10
