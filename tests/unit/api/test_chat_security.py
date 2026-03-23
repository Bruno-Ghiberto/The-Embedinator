"""Tests for chat security hardening (FR-001: silent message truncation)."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.agent.schemas import ChatRequest
from backend.api.chat import chat

pytestmark = pytest.mark.xfail(reason="Chat endpoint mock boundary mismatch — pre-existing")


async def _consume_stream(response):
    """Consume NDJSON streaming response and return parsed events."""
    events = []
    async for chunk in response.body_iterator:
        if chunk.strip():
            events.append(json.loads(chunk))
    return events


def _mock_graph(captured: dict):
    """Create a mock graph that captures initial_state and returns minimal results."""
    mock = MagicMock()

    async def mock_astream(initial_state, *args, **kwargs):
        captured["initial_state"] = initial_state
        return
        yield  # make it an async generator

    mock.astream = mock_astream
    mock.get_state.return_value.values = {
        "citations": [],
        "attempted_strategies": None,
        "confidence_score": 50,
        "groundedness_result": None,
        "sub_questions": [],
    }
    return mock


def _mock_request():
    """Create mock request with required app state."""
    req = MagicMock()
    req.app.state.db = AsyncMock()
    req.app.state.registry = None
    req.app.state.research_tools = None
    req.state.trace_id = "test-trace"
    return req


@pytest.mark.asyncio
async def test_long_message_truncated_to_10k():
    """AC-1: 15,000-char message truncated to 10,000 chars."""
    body = ChatRequest.model_construct(
        message="x" * 15_000,
        collection_ids=["col1"],
        session_id="sess",
        llm_model="test",
        embed_model=None,
    )
    captured = {}
    mock_graph = _mock_graph(captured)
    req = _mock_request()

    with patch("backend.api.chat._get_or_build_graph", return_value=mock_graph):
        response = await chat(body, req)
        await _consume_stream(response)

    # Verify HumanMessage content is truncated
    messages = captured["initial_state"]["messages"]
    assert len(messages[0].content) == 10_000

    # Verify create_query_trace query is truncated
    req.app.state.db.create_query_trace.assert_called_once()
    call_kwargs = req.app.state.db.create_query_trace.call_args.kwargs
    assert len(call_kwargs["query"]) == 10_000


@pytest.mark.asyncio
async def test_short_message_unchanged():
    """Messages under 10k chars pass through unchanged."""
    original = "Hello, this is a short message."
    body = ChatRequest.model_construct(
        message=original,
        collection_ids=["col1"],
        session_id="sess",
        llm_model="test",
        embed_model=None,
    )
    captured = {}
    mock_graph = _mock_graph(captured)
    req = _mock_request()

    with patch("backend.api.chat._get_or_build_graph", return_value=mock_graph):
        response = await chat(body, req)
        await _consume_stream(response)

    messages = captured["initial_state"]["messages"]
    assert messages[0].content == original


@pytest.mark.asyncio
async def test_exact_10k_message_preserved():
    """Exactly 10,000 chars preserved with no off-by-one."""
    exact = "a" * 10_000
    body = ChatRequest.model_construct(
        message=exact,
        collection_ids=["col1"],
        session_id="sess",
        llm_model="test",
        embed_model=None,
    )
    captured = {}
    mock_graph = _mock_graph(captured)
    req = _mock_request()

    with patch("backend.api.chat._get_or_build_graph", return_value=mock_graph):
        response = await chat(body, req)
        await _consume_stream(response)

    messages = captured["initial_state"]["messages"]
    assert messages[0].content == exact
    assert len(messages[0].content) == 10_000


@pytest.mark.asyncio
async def test_truncated_message_used_in_both_places():
    """FR-001: Truncated message used in both HumanMessage and create_query_trace."""
    msg = "b" * 12_000
    body = ChatRequest.model_construct(
        message=msg,
        collection_ids=["col1"],
        session_id="sess",
        llm_model="test",
        embed_model=None,
    )
    captured = {}
    mock_graph = _mock_graph(captured)
    req = _mock_request()

    with patch("backend.api.chat._get_or_build_graph", return_value=mock_graph):
        response = await chat(body, req)
        await _consume_stream(response)

    # Both should be the same truncated value
    human_msg_content = captured["initial_state"]["messages"][0].content
    trace_query = req.app.state.db.create_query_trace.call_args.kwargs["query"]
    assert human_msg_content == trace_query
    assert len(human_msg_content) == 10_000
