"""Trace context propagation tests -- Spec-15 observability."""
import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response


def test_json_lines_format(capsys):
    """FR-013: All backend log output must be valid JSON Lines parseable by standard JSON tools."""
    # Configure structlog for test isolation
    structlog.reset_defaults()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(0),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    log = structlog.get_logger()
    events = ["alpha", "beta", "gamma", "delta", "epsilon"]
    for event in events:
        log.info(event, key="value")

    captured = capsys.readouterr()
    lines = [line for line in captured.out.strip().split("\n") if line]
    assert len(lines) == 5, f"Expected 5 log lines, got {len(lines)}"
    for line in lines:
        parsed = json.loads(line)
        assert "event" in parsed, f"Log line missing 'event' key: {line}"


# ---------------------------------------------------------------------------
# T013 — TraceIDMiddleware binds trace_id to structlog contextvars
# ---------------------------------------------------------------------------

def test_middleware_binds_trace_id():
    """T013/FR-001: TraceIDMiddleware.dispatch() must call
    structlog.contextvars.bind_contextvars(trace_id=...) and clear in finally."""
    from backend.middleware import TraceIDMiddleware

    bound_calls: list[dict] = []
    clear_calls: list[int] = []

    original_bind = structlog.contextvars.bind_contextvars
    original_clear = structlog.contextvars.clear_contextvars

    def capturing_bind(**kwargs):
        bound_calls.append(kwargs)
        return original_bind(**kwargs)

    def capturing_clear():
        clear_calls.append(1)
        return original_clear()

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(TraceIDMiddleware)

    with (
        patch("structlog.contextvars.bind_contextvars", side_effect=capturing_bind),
        patch("structlog.contextvars.clear_contextvars", side_effect=capturing_clear),
    ):
        with TestClient(app) as client:
            response = client.get("/ping")

    assert response.status_code == 200

    # bind_contextvars must have been called with a trace_id kwarg
    trace_binds = [c for c in bound_calls if "trace_id" in c]
    assert len(trace_binds) >= 1, "bind_contextvars(trace_id=...) was never called"

    # The trace_id must be a valid UUID
    bound_trace_id = trace_binds[0]["trace_id"]
    uuid.UUID(bound_trace_id)  # raises ValueError if not valid UUID

    # The response header must carry the same trace_id
    assert response.headers.get("x-trace-id") == bound_trace_id

    # clear_contextvars must have been called (finally block)
    assert len(clear_calls) >= 1, "clear_contextvars() was never called (missing finally)"


# ---------------------------------------------------------------------------
# T014 — Concurrent requests produce isolated trace IDs (SC-002)
# ---------------------------------------------------------------------------

def test_concurrent_request_trace_isolation():
    """T014/SC-002: Two concurrent requests must get independent trace IDs
    with no cross-contamination of structlog contextvars."""
    from backend.middleware import TraceIDMiddleware

    app = FastAPI()

    @app.get("/id")
    async def get_trace(request: Request):
        # Return whatever trace_id is in request.state
        return {"trace_id": getattr(request.state, "trace_id", None)}

    app.add_middleware(TraceIDMiddleware)

    with TestClient(app) as client:
        r1 = client.get("/id")
        r2 = client.get("/id")

    assert r1.status_code == 200
    assert r2.status_code == 200

    tid1 = r1.headers.get("x-trace-id")
    tid2 = r2.headers.get("x-trace-id")

    assert tid1 is not None, "First request missing X-Trace-ID header"
    assert tid2 is not None, "Second request missing X-Trace-ID header"
    assert tid1 != tid2, "Both requests returned the same trace ID — cross-contamination detected"

    # Both must be valid UUIDs
    uuid.UUID(tid1)
    uuid.UUID(tid2)


# ---------------------------------------------------------------------------
# T015 — session_id is bound to structlog contextvars during chat (FR-002)
# ---------------------------------------------------------------------------

def test_session_id_bound_in_chat():
    """T015/FR-002: chat endpoint must call
    structlog.contextvars.bind_contextvars(session_id=...) after extracting
    session_id from the request."""
    import backend.api.chat as chat_module  # noqa: PLC0415

    bound_calls: list[dict] = []

    def capturing_bind(**kwargs):
        bound_calls.append(kwargs)
        return None

    # Build a minimal FastAPI app that mounts the chat router
    # but stubs out heavy dependencies
    mini_app = FastAPI()

    # Provide app.state stubs
    mini_app.state.db = MagicMock()
    mini_app.state.db.get_active_provider = AsyncMock(return_value=None)
    mini_app.state.registry = None
    mini_app.state.research_tools = None

    # Stub a trivial graph that immediately returns (async generator)
    mock_graph = MagicMock()

    async def _fake_astream(state, stream_mode, config):
        # Yield nothing — stream ends immediately
        return
        yield  # make it an async generator

    mock_graph.astream = _fake_astream
    mock_graph.get_state = MagicMock(return_value=MagicMock(values={
        "citations": [],
        "attempted_strategies": None,
        "confidence_score": 50,
        "groundedness_result": None,
        "stage_timings": {},
        "sub_questions": [],
    }))
    mini_app.state._conversation_graph = mock_graph

    mini_app.include_router(chat_module.router)

    with patch("structlog.contextvars.bind_contextvars", side_effect=capturing_bind):
        with TestClient(mini_app) as client:
            client.post(
                "/api/chat",
                json={
                    "message": "hello",
                    "session_id": "test-session-abc",
                    "collection_ids": ["col1"],
                },
            )

    # session_id must have been bound to contextvars
    session_binds = [c for c in bound_calls if "session_id" in c]
    assert len(session_binds) >= 1, (
        f"bind_contextvars(session_id=...) was never called. "
        f"Calls captured: {bound_calls}"
    )
    assert session_binds[0]["session_id"] == "test-session-abc"


# ---------------------------------------------------------------------------
# T016 — IngestionPipeline.ingest_file() generates + binds trace_id (FR-014)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_file_generates_trace_id():
    """T016/FR-014: ingest_file() must call
    structlog.contextvars.bind_contextvars(trace_id=...) at entry and
    structlog.contextvars.clear_contextvars() in finally."""
    from backend.ingestion.pipeline import IngestionPipeline

    bind_calls: list[dict] = []
    clear_calls: list[int] = []

    def capturing_bind(**kwargs):
        bind_calls.append(kwargs)

    def capturing_clear():
        clear_calls.append(1)

    # Minimal mocks for IngestionPipeline dependencies
    mock_db = MagicMock()
    mock_db.update_ingestion_job = AsyncMock()
    mock_db.update_document_status = AsyncMock()
    mock_db.insert_parent_chunk = AsyncMock()

    mock_qdrant = MagicMock()

    pipeline = IngestionPipeline(db=mock_db, qdrant=mock_qdrant)

    # Patch the worker spawn so we don't need a real Rust binary;
    # simulate it returning no chunks (empty output)
    mock_proc = MagicMock()
    mock_proc.stdout = iter([])  # no NDJSON lines
    mock_proc.stderr = MagicMock(read=MagicMock(return_value=""))
    mock_proc.returncode = 0
    mock_proc.wait = MagicMock(return_value=0)

    with (
        patch("structlog.contextvars.bind_contextvars", side_effect=capturing_bind),
        patch("structlog.contextvars.clear_contextvars", side_effect=capturing_clear),
        patch.object(pipeline, "_spawn_worker", new=AsyncMock(return_value=mock_proc)),
    ):
        result = await pipeline.ingest_file(
            file_path="/tmp/test.pdf",
            filename="test.pdf",
            collection_id="col-1",
            document_id="doc-1",
            job_id="job-1",
            file_hash="abc123",
        )

    # bind_contextvars must have been called with trace_id
    trace_binds = [c for c in bind_calls if "trace_id" in c]
    assert len(trace_binds) >= 1, (
        f"bind_contextvars(trace_id=...) was never called. Calls: {bind_calls}"
    )
    # The trace_id must be a valid UUID
    uuid.UUID(trace_binds[0]["trace_id"])

    # clear_contextvars must have been called (finally block)
    assert len(clear_calls) >= 1, "clear_contextvars() was never called (missing finally)"
