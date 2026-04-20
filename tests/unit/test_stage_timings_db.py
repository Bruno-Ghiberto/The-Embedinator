"""Unit tests for stage_timings_json storage round-trip (FR-005)."""

from __future__ import annotations

import inspect
import json
import uuid

import pytest
import pytest_asyncio

from backend.storage.sqlite_db import SQLiteDB


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a file-based SQLiteDB for testing."""
    instance = SQLiteDB(db_path=str(tmp_path / "test.db"))
    await instance.connect()
    yield instance
    await instance.close()


# ── Parameter contract ────────────────────────────────────────────


def test_create_query_trace_signature_has_stage_timings_json():
    """create_query_trace() has stage_timings_json parameter in its signature."""
    sig = inspect.signature(SQLiteDB.create_query_trace)
    assert "stage_timings_json" in sig.parameters


def test_stage_timings_json_parameter_defaults_to_none():
    """stage_timings_json parameter has a default of None."""
    sig = inspect.signature(SQLiteDB.create_query_trace)
    param = sig.parameters["stage_timings_json"]
    assert param.default is None


# ── Round-trip tests ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stage_timings_round_trips_through_sqlite(db):
    """stage_timings written as JSON is returned correctly from get_trace()."""
    timings = {
        "intent_classification": {"duration_ms": 180.4},
        "embedding": {"duration_ms": 45.1},
        "retrieval": {"duration_ms": 28.3},
        "ranking": {"duration_ms": 142.6},
        "answer_generation": {"duration_ms": 487.2},
    }
    trace_id = str(uuid.uuid4())

    await db.create_query_trace(
        id=trace_id,
        session_id="session-timings",
        query="test query",
        collections_searched=json.dumps(["col1"]),
        chunks_retrieved_json=json.dumps([]),
        latency_ms=900,
        confidence_score=72,
        stage_timings_json=json.dumps(timings),
    )
    trace = await db.get_trace(trace_id)
    assert trace is not None
    assert trace["stage_timings"] == timings


@pytest.mark.asyncio
async def test_null_stage_timings_returns_empty_dict(db):
    """A trace written without stage_timings_json returns stage_timings: {} from get_trace()."""
    trace_id = str(uuid.uuid4())

    await db.create_query_trace(
        id=trace_id,
        session_id="session-legacy",
        query="legacy query",
        collections_searched=json.dumps([]),
        chunks_retrieved_json=json.dumps([]),
        latency_ms=200,
        confidence_score=50,
        # stage_timings_json not passed — defaults to None
    )
    trace = await db.get_trace(trace_id)
    assert trace is not None
    assert trace["stage_timings"] == {}


@pytest.mark.asyncio
async def test_failed_stage_marker_round_trips(db):
    """stage entry with failed:True round-trips correctly through SQLite."""
    timings = {
        "intent_classification": {"duration_ms": 45.2, "failed": True},
    }
    trace_id = str(uuid.uuid4())

    await db.create_query_trace(
        id=trace_id,
        session_id="session-failed",
        query="query with failed stage",
        collections_searched=json.dumps([]),
        chunks_retrieved_json=json.dumps([]),
        latency_ms=100,
        confidence_score=0,
        stage_timings_json=json.dumps(timings),
    )
    trace = await db.get_trace(trace_id)
    assert trace is not None
    assert trace["stage_timings"]["intent_classification"]["failed"] is True
    assert trace["stage_timings"]["intent_classification"]["duration_ms"] == 45.2


@pytest.mark.asyncio
async def test_stage_timings_returns_dict_not_list(db):
    """stage_timings from get_trace() is a dict, not a list."""
    timings = {"intent_classification": {"duration_ms": 100.0}}
    trace_id = str(uuid.uuid4())

    await db.create_query_trace(
        id=trace_id,
        session_id="session-typecheck",
        query="type check query",
        collections_searched=json.dumps([]),
        chunks_retrieved_json=json.dumps([]),
        latency_ms=150,
        confidence_score=60,
        stage_timings_json=json.dumps(timings),
    )
    trace = await db.get_trace(trace_id)
    assert isinstance(trace["stage_timings"], dict)


@pytest.mark.asyncio
async def test_get_trace_returns_none_for_missing_id(db):
    """get_trace() returns None for a non-existent trace_id."""
    result = await db.get_trace(str(uuid.uuid4()))
    assert result is None


# ── Column presence / migration ───────────────────────────────────


@pytest.mark.asyncio
async def test_stage_timings_json_column_exists_after_init(db):
    """stage_timings_json column exists in query_traces after connect()."""
    cursor = await db.db.execute("PRAGMA table_info(query_traces)")
    columns = await cursor.fetchall()
    col_names = {c["name"] for c in columns}
    assert "stage_timings_json" in col_names


@pytest.mark.asyncio
async def test_migration_is_idempotent(tmp_path):
    """Calling connect() twice on the same DB path does not raise."""
    db_path = str(tmp_path / "idem.db")

    db1 = SQLiteDB(db_path=db_path)
    await db1.connect()
    await db1.close()

    # Second connect — migration must not raise OperationalError
    db2 = SQLiteDB(db_path=db_path)
    await db2.connect()
    await db2.close()
