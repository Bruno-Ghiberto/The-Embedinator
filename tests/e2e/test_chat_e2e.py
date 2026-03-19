"""E2E: Chat NDJSON stream — POST /api/chat → collect stream → verify event types.

Uses a mock ConversationGraph (no LLM or Qdrant required).
All tests marked @pytest.mark.e2e.
"""

from __future__ import annotations

import json

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from langchain_core.messages import AIMessageChunk
from unittest.mock import AsyncMock, MagicMock

from backend.api import chat, health
from backend.middleware import TraceIDMiddleware


def _build_mock_graph(chunks: list[str] | None = None):
    """Mock ConversationGraph that streams fixed content and returns a state snapshot."""
    graph = MagicMock()
    chunks = chunks or ["This is a test answer."]

    async def mock_astream(state, *, stream_mode="messages", config=None):
        for text in chunks:
            msg = AIMessageChunk(content=text)
            metadata = {"langgraph_node": "format_response"}
            yield msg, metadata

    graph.astream = mock_astream

    state_snapshot = MagicMock()
    state_snapshot.values = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 80,
        "groundedness_result": None,
        "sub_questions": [],
        "stage_timings": {},
        "final_response": "This is a test answer.",
    }
    graph.get_state = MagicMock(return_value=state_snapshot)
    return graph


def _make_chat_app(mock_graph) -> "FastAPI":
    """Minimal app with chat + health routers and pre-set conversation graph."""
    app = FastAPI()
    app.add_middleware(TraceIDMiddleware)
    app.include_router(chat.router)
    app.include_router(health.router)

    # Mock DB — supply all methods used by the chat endpoint
    db = AsyncMock()
    db.get_active_provider = AsyncMock(return_value=None)
    db.create_query_trace = AsyncMock()

    app.state.db = db
    # Pre-set the graph so _get_or_build_graph returns it immediately
    app.state._conversation_graph = mock_graph
    # Set registry to None to skip provider resolution (provider_name defaults to "ollama")
    app.state.registry = None
    app.state.research_tools = None

    return app


@pytest.mark.e2e
class TestChatStream:
    """Chat NDJSON streaming end-to-end tests."""

    @pytest_asyncio.fixture
    async def client(self):
        """ASGI test client with mock graph."""
        mock_graph = _build_mock_graph()
        app = _make_chat_app(mock_graph)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
            yield c

    async def test_stream_contains_required_event_types(self, client):
        """POST /api/chat streams NDJSON with session, chunk, confidence, and done events."""
        lines = []

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "message": "What is the capital of France?",
                    "collection_ids": ["test-collection"],
                },
            ) as resp:
                assert resp.status_code == 200
                assert "ndjson" in resp.headers.get("content-type", "")
                async for line in resp.aiter_lines():
                    if line.strip():
                        lines.append(json.loads(line))
        finally:
            pass  # stateless mock, nothing to clean up

        event_types = [evt.get("type") for evt in lines]

        # Core events that must be present
        assert "session" in event_types, f"Missing 'session' in {event_types}"
        assert "chunk" in event_types, f"Missing 'chunk' in {event_types}"
        assert "done" in event_types, f"Missing 'done' in {event_types}"

    async def test_stream_event_ordering(self, client):
        """session event appears before chunk and done; done is last."""
        lines = []

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "message": "Test ordering",
                    "collection_ids": ["test-collection"],
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        lines.append(json.loads(line))
        finally:
            pass

        event_types = [evt.get("type") for evt in lines]
        assert len(event_types) >= 2, f"Expected at least 2 events, got: {event_types}"

        # session must be first
        assert event_types[0] == "session", f"First event should be 'session', got: {event_types}"
        # done must be last
        assert event_types[-1] == "done", f"Last event should be 'done', got: {event_types}"

    async def test_done_event_has_trace_id(self, client):
        """done event includes a trace_id field."""
        done_events = []

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json={
                    "message": "Check trace id",
                    "collection_ids": ["test-collection"],
                },
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        evt = json.loads(line)
                        if evt.get("type") == "done":
                            done_events.append(evt)
        finally:
            pass

        assert done_events, "No 'done' event received"
        assert "trace_id" in done_events[0], f"'done' event missing trace_id: {done_events[0]}"
        assert "latency_ms" in done_events[0], f"'done' event missing latency_ms: {done_events[0]}"

    async def test_empty_collection_ids_returns_error(self, client):
        """Sending no collection_ids returns an error event (not HTTP error)."""
        lines = []

        try:
            async with client.stream(
                "POST",
                "/api/chat",
                json={"message": "test", "collection_ids": []},
            ) as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.strip():
                        lines.append(json.loads(line))
        finally:
            pass

        event_types = [evt.get("type") for evt in lines]
        assert "error" in event_types, f"Expected 'error' event for empty collection_ids, got: {event_types}"
        error_evt = next(e for e in lines if e.get("type") == "error")
        assert error_evt.get("code") == "NO_COLLECTIONS"
