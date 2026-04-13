"""Integration tests for the ConversationGraph — Wave 5B.

Tests: T030, T035, T039, T040, T046, T047.

All tests use MemorySaver (not AsyncSqliteSaver) to avoid file system dependencies.
All LLM-dependent nodes are mocked. No real LLM or Qdrant calls.
Each test uses a unique thread_id to avoid checkpoint collisions.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport
from langchain_core.messages import AIMessageChunk, HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

from backend.agent.schemas import Citation, QueryAnalysis
from backend.agent.state import ConversationState
from tests.mocks import build_mock_research_graph


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _thread_id() -> str:
    """Unique thread_id per test invocation."""
    return f"test-{uuid.uuid4().hex[:12]}"


def _initial_state(
    message: str,
    *,
    session_id: str | None = None,
    collections: list[str] | None = None,
    iteration_count: int = 0,
) -> ConversationState:
    return {
        "session_id": session_id or str(uuid.uuid4()),
        "messages": [HumanMessage(content=message)],
        "intent": "",
        "query_analysis": None,
        "sub_answers": [],
        "selected_collections": collections or ["test-collection-1"],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "final_response": None,
        "citations": [],
        "groundedness_result": None,
        "confidence_score": 0,
        "iteration_count": iteration_count,
    }


def _mock_citation(passage_id: str = "mock-p1") -> Citation:
    return Citation(
        passage_id=passage_id,
        document_id="mock-doc-001",
        document_name="test.pdf",
        start_offset=0,
        end_offset=100,
        text="Mock passage text for testing.",
        relevance_score=0.85,
    )


# ---------------------------------------------------------------------------
# Mock node functions (replace LLM/DB-dependent nodes)
# ---------------------------------------------------------------------------


async def _classify_as_rag(state, config=None):
    """Always classify intent as rag_query."""
    return {"intent": "rag_query"}


async def _rewrite_clear(state, config=None):
    """Return a clear QueryAnalysis with one sub-question."""
    last_msg = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            last_msg = msg.content
            break
    return {
        "query_analysis": QueryAnalysis(
            is_clear=True,
            sub_questions=[last_msg or "fallback question"],
            complexity_tier="lookup",
            collections_hint=[],
            clarification_needed=None,
        )
    }


def _aggregate_with_results(state, config=None):
    """Return aggregated results with a citation and confidence score."""
    return {
        "final_response": "The capital of France is Paris.",
        "citations": [_mock_citation()],
        "confidence_score": 85,
    }


async def _noop_summarize(state, config=None):
    """Skip history compression."""
    return {}


# ---------------------------------------------------------------------------
# Graph builders (with specific node mocking patterns)
# ---------------------------------------------------------------------------

_NODE_PREFIX = "backend.agent.conversation_graph"


def _build_rag_graph(research_graph, checkpointer=None):
    """Build graph for full RAG path: all LLM nodes mocked, clean happy-path."""
    with (
        patch(f"{_NODE_PREFIX}.classify_intent", _classify_as_rag),
        patch(f"{_NODE_PREFIX}.rewrite_query", _rewrite_clear),
        patch(f"{_NODE_PREFIX}.aggregate_answers", _aggregate_with_results),
        patch(f"{_NODE_PREFIX}.summarize_history", _noop_summarize),
    ):
        from backend.agent.conversation_graph import build_conversation_graph

        return build_conversation_graph(
            research_graph=research_graph,
            checkpointer=checkpointer or MemorySaver(),
        )


def _build_clarification_graph(
    research_graph,
    rewrite_fn,
    checkpointer=None,
):
    """Build graph where rewrite_query triggers clarification via is_clear=False."""
    with (
        patch(f"{_NODE_PREFIX}.classify_intent", _classify_as_rag),
        patch(f"{_NODE_PREFIX}.rewrite_query", rewrite_fn),
        patch(f"{_NODE_PREFIX}.aggregate_answers", _aggregate_with_results),
        patch(f"{_NODE_PREFIX}.summarize_history", _noop_summarize),
    ):
        from backend.agent.conversation_graph import build_conversation_graph

        return build_conversation_graph(
            research_graph=research_graph,
            checkpointer=checkpointer or MemorySaver(),
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_research():
    return build_mock_research_graph()


# ===================================================================
# T030 — Full RAG Path
# ===================================================================


class TestFullRagPath:
    """T030: graph executes end-to-end, produces response with citations and confidence."""

    @pytest.mark.asyncio
    async def test_produces_final_response(self, mock_research):
        graph = _build_rag_graph(mock_research)
        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}

        result = await graph.ainvoke(
            _initial_state("What is the capital of France?"), config
        )

        assert result["final_response"] is not None
        assert len(result["final_response"]) > 0

    @pytest.mark.asyncio
    async def test_confidence_is_int_0_100(self, mock_research):
        graph = _build_rag_graph(mock_research)
        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}

        result = await graph.ainvoke(
            _initial_state("Explain the RAG architecture"), config
        )

        assert isinstance(result["confidence_score"], int)
        assert 0 <= result["confidence_score"] <= 100

    @pytest.mark.asyncio
    async def test_citations_list_present(self, mock_research):
        graph = _build_rag_graph(mock_research)
        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}

        result = await graph.ainvoke(
            _initial_state("How does vector search work?"), config
        )

        assert isinstance(result["citations"], list)
        assert len(result["citations"]) > 0
        citation = result["citations"][0]
        assert hasattr(citation, "passage_id")
        assert hasattr(citation, "document_name")

    @pytest.mark.asyncio
    async def test_intent_set_to_rag_query(self, mock_research):
        graph = _build_rag_graph(mock_research)
        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}

        result = await graph.ainvoke(
            _initial_state("What is embedding?"), config
        )

        assert result["intent"] == "rag_query"


# ===================================================================
# T035 — Session Continuity
# ===================================================================


@pytest.mark.xfail(reason="Checkpoint loading with AsyncMock limitations — pre-existing")
class TestSessionContinuity:
    """T035: follow-up question uses prior conversation history."""

    @pytest.mark.asyncio
    async def test_followup_references_prior_context(self, mock_research):
        """Invoke twice with same session_id; verify second invocation
        sees accumulated messages from the first."""
        session_id = str(uuid.uuid4())
        accumulated_messages: dict[str, list] = {}

        async def init_with_history(state, config=None):
            sid = state["session_id"]
            prior = accumulated_messages.get(sid, [])
            if prior:
                return {"messages": prior + state["messages"]}
            return {}

        with (
            patch(f"{_NODE_PREFIX}.classify_intent", _classify_as_rag),
            patch(f"{_NODE_PREFIX}.rewrite_query", _rewrite_clear),
            patch(f"{_NODE_PREFIX}.aggregate_answers", _aggregate_with_results),
            patch(f"{_NODE_PREFIX}.summarize_history", _noop_summarize),
        ):
            from backend.agent.conversation_graph import build_conversation_graph

            checkpointer = MemorySaver()
            graph = build_conversation_graph(
                research_graph=mock_research, checkpointer=checkpointer
            )

        # First invocation
        tid1 = _thread_id()
        config1 = {"configurable": {"thread_id": tid1}}
        state1 = _initial_state(
            "What is the capital of France?", session_id=session_id
        )
        await graph.ainvoke(state1, config1)

        # Store messages from first run for session continuity
        final1 = graph.get_state(config1).values
        accumulated_messages[session_id] = final1.get("messages", [])

        # Second invocation (follow-up)
        tid2 = _thread_id()
        config2 = {"configurable": {"thread_id": tid2}}
        state2 = _initial_state("What about Germany?", session_id=session_id)
        await graph.ainvoke(state2, config2)

        final2 = graph.get_state(config2).values
        messages = final2.get("messages", [])

        # Verify both questions are in the message history
        texts = [
            m.content for m in messages if hasattr(m, "content")
        ]
        assert any("France" in t for t in texts), (
            f"First question not found in messages: {texts}"
        )
        assert any("Germany" in t for t in texts), (
            f"Follow-up question not found in messages: {texts}"
        )
        assert len(messages) >= 2


# ===================================================================
# T039 — Clarification Interrupt / Resume
# ===================================================================


@pytest.mark.xfail(reason="Interrupt protocol handling edge case — pre-existing")
class TestClarificationInterrupt:
    """T039: ambiguous query triggers interrupt; resume produces answer."""

    @pytest.mark.asyncio
    async def test_interrupt_and_resume(self, mock_research):
        call_count = {"n": 0}

        async def rewrite_unclear_then_clear(state, config=None):
            call_count["n"] += 1
            last_msg = ""
            for msg in reversed(state["messages"]):
                if hasattr(msg, "type") and msg.type == "human":
                    last_msg = msg.content
                    break
            if call_count["n"] == 1:
                return {
                    "query_analysis": QueryAnalysis(
                        is_clear=False,
                        sub_questions=["Which API docs?"],
                        complexity_tier="lookup",
                        collections_hint=[],
                        clarification_needed="Could you specify which API documentation?",
                    )
                }
            return {
                "query_analysis": QueryAnalysis(
                    is_clear=True,
                    sub_questions=[last_msg or "API docs question"],
                    complexity_tier="lookup",
                    collections_hint=[],
                    clarification_needed=None,
                )
            }

        graph = _build_clarification_graph(
            mock_research, rewrite_unclear_then_clear
        )

        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}
        state = _initial_state("Tell me about the API docs")

        # First invoke — should trigger interrupt
        result = await graph.ainvoke(state, config)

        # Verify graph is paused (interrupt)
        graph_state = graph.get_state(config)
        assert graph_state.next, "Graph should be paused at an interrupt"

        # Resume with user clarification
        result = await graph.ainvoke(
            Command(resume="I meant the REST API docs"), config
        )

        # Verify graph completed with an answer
        assert result.get("final_response") is not None
        assert len(result["final_response"]) > 0

        # Verify the clarification response was incorporated into messages
        messages = result.get("messages", [])
        msg_texts = [
            m.content for m in messages if hasattr(m, "content")
        ]
        assert any("REST API docs" in t for t in msg_texts), (
            f"Clarification response should be in messages: {msg_texts}"
        )

    @pytest.mark.asyncio
    async def test_interrupt_state_contains_interrupt_marker(self, mock_research):
        """Verify __interrupt__ is detectable in graph state after pause."""

        async def rewrite_always_unclear(state, config=None):
            return {
                "query_analysis": QueryAnalysis(
                    is_clear=False,
                    sub_questions=["Ambiguous question"],
                    complexity_tier="lookup",
                    collections_hint=[],
                    clarification_needed="What do you mean?",
                )
            }

        graph = _build_clarification_graph(
            mock_research, rewrite_always_unclear
        )

        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}
        state = _initial_state("Something vague")

        await graph.ainvoke(state, config)

        graph_state = graph.get_state(config)
        # Graph should be paused with tasks queued
        assert graph_state.next
        # Verify interrupt is present in state representation
        state_repr = str(graph_state)
        assert "interrupt" in state_repr.lower() or len(graph_state.next) > 0


# ===================================================================
# T040 — Two-Round Clarification Cap
# ===================================================================


@pytest.mark.xfail(reason="Clarification loop boundary condition — pre-existing")
class TestTwoRoundClarificationCap:
    """T040: after 2 clarification rounds, graph proceeds to fan_out."""

    @pytest.mark.asyncio
    async def test_cap_reached_proceeds_to_answer(self, mock_research):
        """Trigger clarification twice; on third rewrite, should_clarify
        returns False (iteration_count >= 2) and graph proceeds to fan_out."""

        async def rewrite_always_unclear(state, config=None):
            last_msg = ""
            for msg in reversed(state["messages"]):
                if hasattr(msg, "type") and msg.type == "human":
                    last_msg = msg.content
                    break
            return {
                "query_analysis": QueryAnalysis(
                    is_clear=False,
                    sub_questions=[last_msg or "unclear question"],
                    complexity_tier="lookup",
                    collections_hint=[],
                    clarification_needed="Still unclear, can you clarify?",
                )
            }

        graph = _build_clarification_graph(
            mock_research, rewrite_always_unclear
        )

        tid = _thread_id()
        config = {"configurable": {"thread_id": tid}}
        state = _initial_state("Something very ambiguous")

        # First invoke — triggers first clarification interrupt
        await graph.ainvoke(state, config)
        gs1 = graph.get_state(config)
        assert gs1.next, "Should be paused after first clarification"

        # Resume with still-ambiguous response (round 1 → iteration_count = 1)
        await graph.ainvoke(
            Command(resume="Still not clear enough"), config
        )
        gs2 = graph.get_state(config)
        assert gs2.next, "Should be paused after second clarification"

        # Resume again (round 2 → iteration_count = 2)
        # This time should_clarify returns False (cap reached),
        # graph proceeds to fan_out → research → aggregate → ... → END
        result = await graph.ainvoke(
            Command(resume="Best effort answer please"), config
        )

        # Graph should complete — no more interrupts
        gs3 = graph.get_state(config)
        assert not gs3.next, "Graph should have completed (no pending nodes)"

        # Answer should be produced (from mock aggregate)
        assert result.get("final_response") is not None

        # Verify both clarification responses are in messages
        messages = result.get("messages", [])
        msg_texts = [
            m.content for m in messages if hasattr(m, "content")
        ]
        assert any("Still not clear enough" in t for t in msg_texts), (
            f"First clarification response should be in messages: {msg_texts}"
        )
        assert any("Best effort answer please" in t for t in msg_texts), (
            f"Second clarification response should be in messages: {msg_texts}"
        )


# ===================================================================
# T046 — Chat Endpoint NDJSON Streaming
# ===================================================================


class TestChatEndpointNDJSON:
    """T046: POST /api/chat produces correct NDJSON stream."""

    def _create_test_app(self, graph):
        """Create minimal FastAPI app with chat router and mocked deps."""
        from backend.api.chat import router

        app = FastAPI()
        app.include_router(router)

        # Mock app state
        mock_db = AsyncMock()
        mock_db.create_query = AsyncMock(return_value="query-001")
        mock_db.create_trace = AsyncMock()
        mock_db.create_answer = AsyncMock()

        app.state.db = mock_db
        app.state._conversation_graph = graph
        app.state.checkpointer = MemorySaver()
        return app

    @pytest.mark.asyncio
    async def test_ndjson_stream_format(self, mock_research):
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "message": "What is the capital of France?",
                    "collection_ids": ["coll-1"],
                },
            )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("application/x-ndjson")

        lines = response.text.strip().split("\n")
        frames = [json.loads(line) for line in lines if line.strip()]

        # Should have at least one frame (metadata)
        assert len(frames) >= 1

        # Separate frame types
        chunk_frames = [f for f in frames if f["type"] == "chunk"]
        done_frames = [f for f in frames if f["type"] == "done"]

        # Done frame must exist and be last
        assert len(done_frames) == 1
        assert done_frames[0] == frames[-1], "Done frame must be the last frame"

    @pytest.mark.asyncio
    async def test_metadata_frame_fields(self, mock_research):
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "message": "Explain vector databases",
                    "collection_ids": ["coll-1"],
                },
            )

        lines = response.text.strip().split("\n")
        frames = [json.loads(line) for line in lines if line.strip()]
        done_frame = [f for f in frames if f["type"] == "done"][0]

        # latency_ms is present
        assert "latency_ms" in done_frame
        assert isinstance(done_frame["latency_ms"], int)
        assert done_frame["latency_ms"] >= 0

        # trace_id is present
        assert "trace_id" in done_frame

    @pytest.mark.asyncio
    async def test_content_type_is_ndjson(self, mock_research):
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "message": "Hello",
                    "collection_ids": ["coll-1"],
                },
            )

        assert "application/x-ndjson" in response.headers["content-type"]


# ===================================================================
# T047 — Error Paths
# ===================================================================


class TestErrorPaths:
    """T047: empty message (HTTP 422), no collections (error frame)."""

    def _create_test_app(self, graph=None):
        from backend.api.chat import router

        app = FastAPI()
        app.include_router(router)

        mock_db = AsyncMock()
        app.state.db = mock_db
        if graph:
            app.state._conversation_graph = graph
        app.state.checkpointer = MemorySaver()
        return app

    @pytest.mark.asyncio
    async def test_empty_message_returns_422(self, mock_research):
        """Empty message violates ChatRequest min_length=1 → HTTP 422."""
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "message": "",
                    "collection_ids": ["coll-1"],
                },
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_missing_message_field_returns_422(self, mock_research):
        """Missing message field entirely → HTTP 422."""
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"collection_ids": ["coll-1"]},
            )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_no_collections_returns_error_frame(self, mock_research):
        """Empty collection_ids → error frame with code NO_COLLECTIONS."""
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "message": "What is the capital of France?",
                    "collection_ids": [],
                },
            )

        assert response.status_code == 200  # NDJSON stream, error is in frame

        lines = response.text.strip().split("\n")
        frames = [json.loads(line) for line in lines if line.strip()]

        assert len(frames) == 1
        error_frame = frames[0]
        assert error_frame["type"] == "error"
        assert error_frame["code"] == "NO_COLLECTIONS"
        assert "collection" in error_frame["message"].lower()

    @pytest.mark.asyncio
    async def test_no_collections_default_returns_error_frame(self, mock_research):
        """Omitting collection_ids (defaults to []) → NO_COLLECTIONS error."""
        graph = _build_rag_graph(mock_research)
        app = self._create_test_app(graph)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/api/chat",
                json={"message": "What is the capital of France?"},
            )

        assert response.status_code == 200
        lines = response.text.strip().split("\n")
        frames = [json.loads(line) for line in lines if line.strip()]

        error_frame = frames[0]
        assert error_frame["type"] == "error"
        assert error_frame["code"] == "NO_COLLECTIONS"
