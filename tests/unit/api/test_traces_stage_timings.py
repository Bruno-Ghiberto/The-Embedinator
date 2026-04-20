"""Unit tests for GET /api/traces/{id} stage_timings extension (FR-008)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.traces import router


# ── Test helpers ──────────────────────────────────────────────────


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
    created_at="2026-03-18T00:00:00Z",
    chunks_retrieved_json=None,
    sub_questions_json=None,
    reasoning_steps_json=None,
    strategy_switches_json=None,
    embed_model=None,
    stage_timings_json=None,
):
    """Create a dict mimicking a query_traces DB row including stage_timings_json."""
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
        "stage_timings_json": stage_timings_json,
    }


# ── Tests: stage_timings key presence ────────────────────────────


class TestStageTimingsKeyPresence:
    """GET /api/traces/{id} always includes stage_timings key in response."""

    def test_response_always_includes_stage_timings_key(self):
        """stage_timings key is present even when stage_timings_json is NULL."""
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=None)
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        assert resp.status_code == 200
        assert "stage_timings" in resp.json()

    def test_response_includes_stage_timings_key_when_populated(self):
        """stage_timings key is present when stage_timings_json has data."""
        timings = {"intent_classification": {"duration_ms": 180.4}}
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=json.dumps(timings))
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        assert resp.status_code == 200
        assert "stage_timings" in resp.json()


# ── Tests: populated stage_timings ───────────────────────────────


class TestPopulatedStageTimings:
    """Populated stage_timings_json is returned as a parsed dict."""

    def test_populated_stage_timings_parsed_to_dict(self):
        """Populated stage_timings_json in DB is returned as dict, not raw string."""
        timings = {
            "intent_classification": {"duration_ms": 180.4},
            "embedding": {"duration_ms": 45.1},
            "retrieval": {"duration_ms": 28.3},
            "ranking": {"duration_ms": 142.6},
            "answer_generation": {"duration_ms": 487.2},
        }
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=json.dumps(timings))
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        data = resp.json()
        assert isinstance(data["stage_timings"], dict)
        assert "intent_classification" in data["stage_timings"]

    def test_stage_timings_values_match_original(self):
        """Parsed stage_timings values match what was stored."""
        timings = {
            "intent_classification": {"duration_ms": 180.4},
            "answer_generation": {"duration_ms": 487.2},
        }
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=json.dumps(timings))
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        data = resp.json()
        assert data["stage_timings"] == timings

    def test_failed_stage_marker_returned_correctly(self):
        """failed:true marker in stage entry is returned as-is."""
        timings = {
            "intent_classification": {"duration_ms": 45.2, "failed": True},
        }
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=json.dumps(timings))
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        data = resp.json()
        assert data["stage_timings"]["intent_classification"]["failed"] is True


# ── Tests: NULL / legacy stage_timings ───────────────────────────


class TestNullStageTimings:
    """NULL stage_timings_json (legacy traces) returns {} not null or []."""

    def test_null_stage_timings_json_returns_empty_dict(self):
        """NULL stage_timings_json in DB returns stage_timings: {} (not null, not [])."""
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=None)
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        data = resp.json()
        assert data["stage_timings"] == {}

    def test_null_stage_timings_is_dict_not_list(self):
        """stage_timings default is {} (dict), not [] (list)."""
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=None)
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        data = resp.json()
        assert isinstance(data["stage_timings"], dict)
        assert not isinstance(data["stage_timings"], list)

    def test_legacy_trace_is_readable_without_error(self):
        """Legacy trace (NULL stage_timings_json) does not raise 500."""
        db = AsyncMock()
        row = _make_trace_row(stage_timings_json=None)
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/t1")

        assert resp.status_code == 200

    def test_existing_fields_unchanged_for_legacy_trace(self):
        """Adding stage_timings does not break existing response fields."""
        db = AsyncMock()
        row = _make_trace_row(
            trace_id="legacy-1",
            stage_timings_json=None,
            sub_questions_json='["q1"]',
        )
        cursor = _make_cursor(fetchone_val=row)
        db.db.execute = AsyncMock(return_value=cursor)

        app = _make_app(db=db)
        client = TestClient(app)
        resp = client.get("/api/traces/legacy-1")

        data = resp.json()
        assert data["id"] == "legacy-1"
        assert data["sub_questions"] == ["q1"]
        assert data["stage_timings"] == {}
