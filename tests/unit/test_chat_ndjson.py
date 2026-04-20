"""Unit tests for chat.py NDJSON streaming — T008.

Tests all 10 event type emissions, NDJSON format, confidence int,
event ordering, error handling, clarification interrupt, and multi-turn
session continuity (FR-016).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from backend.agent.schemas import (
    ChatRequest,
    Citation,
    ClaimVerification,
    GroundednessResult,
)
from backend.api.chat import router
from backend.errors import CircuitOpenError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(
    *,
    graph=None,
    db=None,
    checkpointer=None,
) -> FastAPI:
    """Build a minimal FastAPI app wired to the chat router with mocks."""
    app = FastAPI()
    app.include_router(router)

    app.state.db = db or AsyncMock()
    app.state.checkpointer = checkpointer
    app.state.research_graph = None

    if graph is not None:
        app.state._conversation_graph = graph

    return app


def _parse_ndjson(response_text: str) -> list[dict]:
    """Parse NDJSON response text into a list of dicts."""
    lines = response_text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


@dataclass
class FakeInterrupt:
    value: str


def _build_mock_graph(
    *,
    chunks: list[str] | None = None,
    nodes: list[str] | None = None,
    final_state: dict | None = None,
    interrupt: str | None = None,
    error: Exception | None = None,
):
    """Build a mock graph that simulates astream(stream_mode='messages').

    Args:
        chunks: List of text tokens to yield as AIMessageChunk.
        nodes: List of node names to emit as status events.
        final_state: Dict for graph.get_state(config).values.
        interrupt: If set, emit __interrupt__ metadata with this question.
        error: If set, astream raises this exception.
    """
    graph = MagicMock()
    chunks = chunks or []
    nodes = nodes or ["query_rewrite", "research", "format_response"]

    async def mock_astream(state, *, stream_mode="messages", config=None):
        if error is not None:
            raise error

        node_idx = 0
        for i, text in enumerate(chunks):
            # Assign node from the nodes list (cycle through)
            current_node = nodes[min(node_idx, len(nodes) - 1)]
            if i > 0 and i % max(1, len(chunks) // len(nodes)) == 0 and node_idx < len(nodes) - 1:
                node_idx += 1
                current_node = nodes[node_idx]

            msg = AIMessageChunk(content=text)
            metadata = {"langgraph_node": current_node}

            if interrupt is not None and i == len(chunks) - 1:
                metadata["__interrupt__"] = [FakeInterrupt(value=interrupt)]

            yield msg, metadata

        # If interrupt with no chunks, yield one empty message with interrupt
        if interrupt is not None and not chunks:
            msg = AIMessageChunk(content="")
            metadata = {
                "langgraph_node": "query_rewrite",
                "__interrupt__": [FakeInterrupt(value=interrupt)],
            }
            yield msg, metadata

    graph.astream = mock_astream

    # Mock get_state for final state retrieval
    default_final_state = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 75,
        "groundedness_result": None,
        "sub_questions": [],
        "final_response": "Test response.",
    }
    if final_state:
        default_final_state.update(final_state)

    state_snapshot = MagicMock()
    state_snapshot.values = default_final_state
    graph.get_state = MagicMock(return_value=state_snapshot)

    return graph


# ---------------------------------------------------------------------------
# Test class: Format validation
# ---------------------------------------------------------------------------


class TestNDJSONFormat:
    """Verify NDJSON format: json.dumps + '\\n', no 'data:' prefix."""

    def test_media_type_is_ndjson(self):
        """Assert media_type='application/x-ndjson'."""
        graph = _build_mock_graph(chunks=["Hello"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        assert resp.status_code == 200
        assert "application/x-ndjson" in resp.headers["content-type"]

    def test_no_sse_prefix_on_any_line(self):
        """Assert no line starts with 'data:'."""
        graph = _build_mock_graph(chunks=["Hello ", "world"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        for line in resp.text.strip().split("\n"):
            assert not line.startswith("data:"), f"SSE prefix found: {line}"

    def test_each_line_is_valid_json(self):
        """Every line must be parseable as JSON."""
        graph = _build_mock_graph(chunks=["Token1 ", "Token2"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        for line in resp.text.strip().split("\n"):
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            assert "type" in parsed


# ---------------------------------------------------------------------------
# Test class: Event ordering
# ---------------------------------------------------------------------------


class TestEventOrdering:
    """Verify session is first, done is last on success path."""

    def test_session_event_is_first(self):
        """Session event must be the very first event."""
        graph = _build_mock_graph(chunks=["Hello"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        assert len(events) > 0
        assert events[0]["type"] == "session"
        assert "session_id" in events[0]

    def test_done_event_is_last_on_success(self):
        """Done event must be the last event on a successful stream."""
        graph = _build_mock_graph(chunks=["Hello"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        assert events[-1]["type"] == "done"
        assert "latency_ms" in events[-1]
        assert "trace_id" in events[-1]

    def test_event_type_ordering(self):
        """Verify events follow the specified ordering:
        session -> status -> chunk -> citation -> confidence -> done.
        """
        citations = [
            Citation(
                passage_id="p1",
                document_id="d1",
                document_name="doc.pdf",
                start_offset=0,
                end_offset=10,
                text="passage text",
                relevance_score=0.9,
            )
        ]
        graph = _build_mock_graph(
            chunks=["Hello ", "world"],
            final_state={
                "citations": citations,
                "confidence_score": 82,
            },
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        types = [e["type"] for e in events]

        # session must be first
        assert types[0] == "session"
        # done must be last
        assert types[-1] == "done"

        # status must come before chunk
        if "status" in types and "chunk" in types:
            assert types.index("status") < types.index("chunk")

        # chunk must come before citation
        if "chunk" in types and "citation" in types:
            assert types.index("chunk") < types.index("citation")

        # citation before confidence
        if "citation" in types and "confidence" in types:
            assert types.index("citation") < types.index("confidence")

        # confidence before done
        if "confidence" in types:
            assert types.index("confidence") < types.index("done")


# ---------------------------------------------------------------------------
# Test class: All 10 event types
# ---------------------------------------------------------------------------


class TestAllEventTypes:
    """Verify all 10 event types can be emitted with correct shapes."""

    def test_session_event(self):
        graph = _build_mock_graph(chunks=["Hi"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        session_events = [e for e in events if e["type"] == "session"]
        assert len(session_events) == 1
        assert isinstance(session_events[0]["session_id"], str)

    def test_status_event(self):
        graph = _build_mock_graph(chunks=["Hi"], nodes=["query_rewrite"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        status_events = [e for e in events if e["type"] == "status"]
        assert len(status_events) >= 1
        for ev in status_events:
            assert "node" in ev
            assert isinstance(ev["node"], str)

    def test_chunk_event(self):
        graph = _build_mock_graph(chunks=["Hello ", "world"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        chunk_events = [e for e in events if e["type"] == "chunk"]
        assert len(chunk_events) >= 1
        for ev in chunk_events:
            assert "text" in ev
            assert isinstance(ev["text"], str)

    def test_citation_event(self):
        citations = [
            Citation(
                passage_id="p1",
                document_id="d1",
                document_name="doc.pdf",
                start_offset=0,
                end_offset=10,
                text="passage text",
                relevance_score=0.9,
            )
        ]
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"citations": citations},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        citation_events = [e for e in events if e["type"] == "citation"]
        assert len(citation_events) == 1
        assert isinstance(citation_events[0]["citations"], list)
        assert len(citation_events[0]["citations"]) == 1

    def test_no_citation_event_when_empty(self):
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"citations": []},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        citation_events = [e for e in events if e["type"] == "citation"]
        assert len(citation_events) == 0

    def test_meta_reasoning_event(self):
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={
                "attempted_strategies": {"WIDEN_SEARCH", "CHANGE_COLLECTION"},
            },
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        meta_events = [e for e in events if e["type"] == "meta_reasoning"]
        assert len(meta_events) == 1
        assert isinstance(meta_events[0]["strategies_attempted"], list)
        assert len(meta_events[0]["strategies_attempted"]) == 2

    def test_no_meta_reasoning_event_when_empty(self):
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"attempted_strategies": set()},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        meta_events = [e for e in events if e["type"] == "meta_reasoning"]
        assert len(meta_events) == 0

    def test_confidence_event_is_int(self):
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"confidence_score": 82},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        conf_events = [e for e in events if e["type"] == "confidence"]
        assert len(conf_events) == 1
        assert conf_events[0]["score"] == 82
        assert isinstance(conf_events[0]["score"], int)

    def test_confidence_event_float_is_coerced_to_int(self):
        """Even if confidence_score is float in state, event must be int."""
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"confidence_score": 0.85},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        conf_events = [e for e in events if e["type"] == "confidence"]
        assert len(conf_events) == 1
        assert isinstance(conf_events[0]["score"], int)

    def test_confidence_score_in_range_0_100(self):
        for score in [0, 50, 100]:
            graph = _build_mock_graph(
                chunks=["Answer"],
                final_state={"confidence_score": score},
            )
            app = _make_app(graph=graph)

            with TestClient(app) as client:
                resp = client.post(
                    "/api/chat",
                    json={"message": "test", "collection_ids": ["coll-1"]},
                )

            events = _parse_ndjson(resp.text)
            conf_events = [e for e in events if e["type"] == "confidence"]
            assert len(conf_events) == 1
            assert 0 <= conf_events[0]["score"] <= 100

    def test_groundedness_event(self):
        groundedness = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="Claim 1",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="Supported by evidence.",
                ),
                ClaimVerification(
                    claim="Claim 2",
                    verdict="unsupported",
                    evidence_chunk_id=None,
                    explanation="No evidence found.",
                ),
                ClaimVerification(
                    claim="Claim 3",
                    verdict="contradicted",
                    evidence_chunk_id="c3",
                    explanation="Contradicts evidence.",
                ),
            ],
            overall_grounded=True,
            confidence_adjustment=-0.1,
        )
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"groundedness_result": groundedness},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        ground_events = [e for e in events if e["type"] == "groundedness"]
        assert len(ground_events) == 1
        ge = ground_events[0]
        assert ge["overall_grounded"] is True
        assert ge["supported"] == 1
        assert ge["unsupported"] == 1
        assert ge["contradicted"] == 1

    def test_no_groundedness_event_when_none(self):
        graph = _build_mock_graph(
            chunks=["Answer"],
            final_state={"groundedness_result": None},
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        ground_events = [e for e in events if e["type"] == "groundedness"]
        assert len(ground_events) == 0

    def test_done_event_has_latency_and_trace(self):
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        done_events = [e for e in events if e["type"] == "done"]
        assert len(done_events) == 1
        assert isinstance(done_events[0]["latency_ms"], int)
        assert done_events[0]["latency_ms"] >= 0
        assert isinstance(done_events[0]["trace_id"], str)

    def test_all_10_event_types_can_be_emitted(self):
        """Verify all 10 event types can appear across different scenarios."""
        # This test verifies that each event type CAN be emitted.
        # Not all appear in a single stream — clarification and error
        # are mutually exclusive with the success path.
        all_event_types = {
            "session",
            "status",
            "chunk",
            "citation",
            "meta_reasoning",
            "confidence",
            "groundedness",
            "done",
            "clarification",
            "error",
        }

        # Scenario 1: Full success path (8 types)
        citations = [
            Citation(
                passage_id="p1",
                document_id="d1",
                document_name="doc.pdf",
                start_offset=0,
                end_offset=10,
                text="text",
                relevance_score=0.9,
            )
        ]
        groundedness = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="c",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="ok",
                ),
            ],
            overall_grounded=True,
            confidence_adjustment=0.0,
        )
        graph = _build_mock_graph(
            chunks=["Hello"],
            final_state={
                "citations": citations,
                "attempted_strategies": {"WIDEN_SEARCH"},
                "confidence_score": 85,
                "groundedness_result": groundedness,
            },
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        success_types = {e["type"] for e in events}
        expected_success = {
            "session",
            "status",
            "chunk",
            "citation",
            "meta_reasoning",
            "confidence",
            "groundedness",
            "done",
        }
        assert expected_success == success_types

        # Scenario 2: Clarification (2 types: session + clarification)
        graph2 = _build_mock_graph(interrupt="Which collection?")
        app2 = _make_app(graph=graph2)

        with TestClient(app2) as client2:
            resp2 = client2.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events2 = _parse_ndjson(resp2.text)
        clarif_types = {e["type"] for e in events2}
        assert "clarification" in clarif_types

        # Scenario 3: Error (1 type)
        graph3 = _build_mock_graph(error=CircuitOpenError("service down"))
        app3 = _make_app(graph=graph3)

        with TestClient(app3) as client3:
            resp3 = client3.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events3 = _parse_ndjson(resp3.text)
        error_types = {e["type"] for e in events3}
        assert "error" in error_types

        # All 10 types observed across scenarios
        observed = success_types | clarif_types | error_types
        assert all_event_types == observed


# ---------------------------------------------------------------------------
# Test class: Error handling
# ---------------------------------------------------------------------------


class TestErrorEvents:
    """Verify error event emission on exceptions."""

    def test_circuit_open_error_event(self):
        graph = _build_mock_graph(error=CircuitOpenError("service down"))
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        # Session event first, then error
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "CIRCUIT_OPEN"
        assert "trace_id" in error_events[0]
        assert isinstance(error_events[0]["trace_id"], str)

    def test_generic_error_event(self):
        graph = _build_mock_graph(error=RuntimeError("unexpected"))
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "SERVICE_UNAVAILABLE"
        assert "trace_id" in error_events[0]

    def test_error_codes_are_uppercase(self):
        """Error codes must be UPPERCASE."""
        graph = _build_mock_graph(error=CircuitOpenError("down"))
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        error_events = [e for e in events if e["type"] == "error"]
        for ev in error_events:
            assert ev["code"] == ev["code"].upper()

    def test_no_collections_error(self):
        """Empty collection_ids yields error event with NO_COLLECTIONS code."""
        graph = _build_mock_graph(chunks=["Hello"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": []},
            )

        events = _parse_ndjson(resp.text)
        assert len(events) >= 1
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "NO_COLLECTIONS"


# ---------------------------------------------------------------------------
# Test class: Clarification interrupt
# ---------------------------------------------------------------------------


class TestClarificationEvent:
    """Verify clarification event on LangGraph interrupt."""

    def test_clarification_event_on_interrupt(self):
        graph = _build_mock_graph(
            interrupt="Are you asking about Q1 or Q2 results?",
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        clarif_events = [e for e in events if e["type"] == "clarification"]
        assert len(clarif_events) == 1
        assert clarif_events[0]["question"] == "Are you asking about Q1 or Q2 results?"

    def test_clarification_ends_stream(self):
        """After clarification, no done event should follow."""
        graph = _build_mock_graph(
            interrupt="Which collection?",
        )
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        types = [e["type"] for e in events]
        assert "done" not in types
        assert "clarification" in types

    def test_session_before_clarification(self):
        """Session event must still appear before clarification."""
        graph = _build_mock_graph(interrupt="Which one?")
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        assert events[0]["type"] == "session"


# ---------------------------------------------------------------------------
# Test class: Trace recording
# ---------------------------------------------------------------------------


class TestTraceRecording:
    """Verify db.create_query_trace() is called (not missing methods)."""

    def test_create_query_trace_called(self):
        """db.create_query_trace() must be called after successful stream."""
        mock_db = AsyncMock()
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph, db=mock_db)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test query", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        assert events[-1]["type"] == "done"

        # Verify create_query_trace was called
        mock_db.create_query_trace.assert_awaited_once()

        # Verify the call included required fields
        call_kwargs = mock_db.create_query_trace.call_args
        # Could be positional or keyword args
        if call_kwargs.kwargs:
            assert "session_id" in call_kwargs.kwargs
            assert "query" in call_kwargs.kwargs
            assert "latency_ms" in call_kwargs.kwargs

    def test_old_methods_not_called(self):
        """db.create_query(), db.create_trace(), db.create_answer() must NOT be called."""
        mock_db = AsyncMock()
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph, db=mock_db)

        with TestClient(app) as client:
            client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        # These methods don't exist — ensure they're not called
        assert not mock_db.create_query.called
        assert not mock_db.create_trace.called
        assert not mock_db.create_answer.called

    def test_trace_write_failure_does_not_crash_stream(self):
        """If db.create_query_trace() raises, stream should still emit done."""
        mock_db = AsyncMock()
        mock_db.create_query_trace.side_effect = RuntimeError("DB write failed")
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph, db=mock_db)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        # Stream should still complete with done
        assert events[-1]["type"] == "done"


# ---------------------------------------------------------------------------
# Test class: Multi-turn session continuity (FR-016)
# ---------------------------------------------------------------------------


class TestSessionContinuity:
    """Verify multi-turn session continuity via session_id."""

    def test_provided_session_id_is_used(self):
        """If client provides session_id, it must appear in session event."""
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={
                    "message": "test",
                    "collection_ids": ["coll-1"],
                    "session_id": "my-session-123",
                },
            )

        events = _parse_ndjson(resp.text)
        session_event = events[0]
        assert session_event["type"] == "session"
        assert session_event["session_id"] == "my-session-123"

    def test_auto_generated_session_id(self):
        """If no session_id, one is generated and returned in session event."""
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["coll-1"]},
            )

        events = _parse_ndjson(resp.text)
        session_event = events[0]
        assert session_event["type"] == "session"
        assert isinstance(session_event["session_id"], str)
        assert len(session_event["session_id"]) > 0

    def test_two_requests_same_session_id(self):
        """Two requests with the same session_id get same session in events."""
        graph = _build_mock_graph(chunks=["Answer"])
        app = _make_app(graph=graph)
        session_id = "multi-turn-session"

        with TestClient(app) as client:
            resp1 = client.post(
                "/api/chat",
                json={
                    "message": "first question",
                    "collection_ids": ["coll-1"],
                    "session_id": session_id,
                },
            )
            resp2 = client.post(
                "/api/chat",
                json={
                    "message": "follow up question",
                    "collection_ids": ["coll-1"],
                    "session_id": session_id,
                },
            )

        events1 = _parse_ndjson(resp1.text)
        events2 = _parse_ndjson(resp2.text)

        assert events1[0]["session_id"] == session_id
        assert events2[0]["session_id"] == session_id

    def test_graph_receives_session_id_in_config(self):
        """The graph must be invoked with thread_id matching session_id."""
        graph = MagicMock()
        invoked_configs = []

        async def capture_astream(state, *, stream_mode="messages", config=None):
            invoked_configs.append(config)
            msg = AIMessageChunk(content="Hi")
            yield msg, {"langgraph_node": "respond"}

        graph.astream = capture_astream

        state_snapshot = MagicMock()
        state_snapshot.values = {
            "citations": [],
            "attempted_strategies": set(),
            "confidence_score": 75,
            "groundedness_result": None,
            "sub_questions": [],
            "final_response": "Test.",
        }
        graph.get_state = MagicMock(return_value=state_snapshot)

        app = _make_app(graph=graph)

        with TestClient(app) as client:
            client.post(
                "/api/chat",
                json={
                    "message": "test",
                    "collection_ids": ["coll-1"],
                    "session_id": "sess-42",
                },
            )

        assert len(invoked_configs) == 1
        assert invoked_configs[0]["configurable"]["thread_id"] == "sess-42"
