"""Integration test for concurrent chat streams — T034.

Launch 10 simultaneous POST /api/chat requests and verify:
- All 10 complete without event loss or dropped frames
- No 500 errors
- All 10 responses contain the "done" event as their last frame (SC-010)
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from langchain_core.messages import AIMessageChunk

from backend.api import chat
from backend.middleware import TraceIDMiddleware


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_mock_graph():
    """Build a mock ConversationGraph for concurrent stream tests."""
    graph = MagicMock()

    async def mock_astream(state, *, stream_mode="messages", config=None):
        # Yield a few chunks to simulate real streaming
        for i in range(3):
            msg = AIMessageChunk(content=f"Token-{i} ")
            yield msg, {"langgraph_node": "format_response"}
            # Small yield to let other coroutines run
            await asyncio.sleep(0)

    graph.astream = mock_astream

    state_snapshot = MagicMock()
    state_snapshot.values = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 75,
        "groundedness_result": None,
        "sub_questions": [],
        "final_response": "Token-0 Token-1 Token-2 ",
    }
    graph.get_state = MagicMock(return_value=state_snapshot)
    return graph


def _make_concurrent_app() -> FastAPI:
    """Build a test app for concurrent stream testing."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    app.include_router(chat.router)

    app.state.db = AsyncMock()
    app.state.checkpointer = None
    app.state.research_graph = None
    app.state._conversation_graph = _build_mock_graph()

    return app


def _parse_ndjson(text: str) -> list[dict]:
    """Parse NDJSON text into event dicts."""
    lines = text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_10_concurrent_streams_all_complete():
    """Launch 10 simultaneous chat requests — all must complete with done event."""
    app = _make_concurrent_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = []
        for i in range(10):
            task = asyncio.create_task(
                client.post(
                    "/api/chat",
                    json={
                        "message": f"Concurrent query {i}",
                        "collection_ids": ["test-collection"],
                        "session_id": f"concurrent-{i}",
                    },
                    timeout=30.0,
                )
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks)

    # Verify all 10 completed
    assert len(responses) == 10

    for i, resp in enumerate(responses):
        # No 500 errors
        assert resp.status_code == 200, f"Stream {i} returned {resp.status_code}"

        # Parse NDJSON
        events = _parse_ndjson(resp.text)
        assert len(events) > 0, f"Stream {i} had no events"

        # No internal errors
        for event in events:
            assert event.get("code") != "INTERNAL_ERROR", f"Stream {i} had internal error: {event}"

        # Last event is "done"
        last_event = events[-1]
        assert last_event["type"] == "done", f"Stream {i} last event was '{last_event['type']}', expected 'done'"

        # First event is "session"
        assert events[0]["type"] == "session", f"Stream {i} first event was '{events[0]['type']}', expected 'session'"

        # Has chunk events (content was streamed)
        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) > 0, f"Stream {i} had no chunk events"


@pytest.mark.asyncio
async def test_concurrent_streams_no_event_loss():
    """All 10 streams must have the same event structure — no dropped frames."""
    app = _make_concurrent_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            asyncio.create_task(
                client.post(
                    "/api/chat",
                    json={
                        "message": f"Query {i}",
                        "collection_ids": ["c1"],
                        "session_id": f"stream-{i}",
                    },
                    timeout=30.0,
                )
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)

    event_counts = []
    for resp in responses:
        events = _parse_ndjson(resp.text)
        event_counts.append(len(events))

    # All streams should have the same number of events (same mock graph)
    assert len(set(event_counts)) == 1, f"Event counts vary across streams: {event_counts}"


@pytest.mark.asyncio
async def test_concurrent_streams_valid_json():
    """Every line in every concurrent response must be valid JSON."""
    app = _make_concurrent_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            asyncio.create_task(
                client.post(
                    "/api/chat",
                    json={
                        "message": f"Q{i}",
                        "collection_ids": ["c1"],
                        "session_id": f"json-{i}",
                    },
                    timeout=30.0,
                )
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)

    for i, resp in enumerate(responses):
        lines = resp.text.strip().split("\n")
        for j, line in enumerate(lines):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
                assert isinstance(parsed, dict), f"Stream {i} line {j} parsed to non-dict: {type(parsed)}"
                assert "type" in parsed, f"Stream {i} line {j} missing 'type' field"
            except json.JSONDecodeError as e:
                pytest.fail(f"Stream {i} line {j} invalid JSON: {line!r} ({e})")


@pytest.mark.asyncio
async def test_concurrent_streams_unique_sessions():
    """Each concurrent stream should have its own session_id in the session event."""
    app = _make_concurrent_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        tasks = [
            asyncio.create_task(
                client.post(
                    "/api/chat",
                    json={
                        "message": f"Q{i}",
                        "collection_ids": ["c1"],
                        "session_id": f"unique-{i}",
                    },
                    timeout=30.0,
                )
            )
            for i in range(10)
        ]
        responses = await asyncio.gather(*tasks)

    session_ids = set()
    for resp in responses:
        events = _parse_ndjson(resp.text)
        session_event = events[0]
        assert session_event["type"] == "session"
        session_ids.add(session_event["session_id"])

    # All 10 should have distinct session IDs
    assert len(session_ids) == 10
