"""Integration test for NDJSON streaming — T009.

End-to-end: parse each response line as JSON; assert no line starts with
"data:"; assert media type header; assert all 10 event types exercised
across test scenarios.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessageChunk

from backend.agent.schemas import (
    Citation,
    ClaimVerification,
    GroundednessResult,
)
from backend.api.chat import router
from backend.errors import CircuitOpenError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class FakeInterrupt:
    value: str


def _make_integration_app(
    *,
    graph=None,
    db=None,
) -> FastAPI:
    """Build a test app with the chat router registered."""
    app = FastAPI()
    app.include_router(router)
    app.state.db = db or AsyncMock()
    app.state.checkpointer = None
    app.state.research_graph = None
    if graph is not None:
        app.state._conversation_graph = graph
    return app


def _build_graph(
    *,
    chunks: list[str] | None = None,
    nodes: list[str] | None = None,
    final_state: dict | None = None,
    interrupt: str | None = None,
    error: Exception | None = None,
):
    """Build a mock ConversationGraph for integration tests."""
    graph = MagicMock()
    chunks = chunks or []
    nodes = nodes or ["query_rewrite", "research", "format_response"]

    async def mock_astream(state, *, stream_mode="messages", config=None):
        if error is not None:
            raise error

        node_idx = 0
        for i, text in enumerate(chunks):
            current_node = nodes[min(node_idx, len(nodes) - 1)]
            if i > 0 and i % max(1, len(chunks) // len(nodes)) == 0 and node_idx < len(nodes) - 1:
                node_idx += 1
                current_node = nodes[node_idx]

            msg = AIMessageChunk(content=text)
            metadata = {"langgraph_node": current_node}

            if interrupt is not None and i == len(chunks) - 1:
                metadata["__interrupt__"] = [FakeInterrupt(value=interrupt)]

            yield msg, metadata

        if interrupt is not None and not chunks:
            msg = AIMessageChunk(content="")
            metadata = {
                "langgraph_node": "query_rewrite",
                "__interrupt__": [FakeInterrupt(value=interrupt)],
            }
            yield msg, metadata

    graph.astream = mock_astream

    default_final = {
        "citations": [],
        "attempted_strategies": set(),
        "confidence_score": 75,
        "groundedness_result": None,
        "sub_questions": [],
        "final_response": "Test response.",
    }
    if final_state:
        default_final.update(final_state)

    state_snapshot = MagicMock()
    state_snapshot.values = default_final
    graph.get_state = MagicMock(return_value=state_snapshot)
    return graph


def _parse_events(response) -> list[dict]:
    """Parse NDJSON response into events."""
    lines = response.text.strip().split("\n")
    return [json.loads(line) for line in lines if line.strip()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNDJSONStreamingIntegration:
    """End-to-end integration tests for NDJSON streaming."""

    def test_each_line_is_valid_json(self):
        """Parse each response line as JSON — no malformed lines."""
        graph = _build_graph(chunks=["Hello ", "world ", "answer"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test question", "collection_ids": ["c1"]},
            )

        assert resp.status_code == 200
        lines = resp.text.strip().split("\n")
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
            assert "type" in parsed

    def test_no_line_starts_with_data_prefix(self):
        """Assert no line starts with 'data:' — NDJSON not SSE."""
        graph = _build_graph(chunks=["Token1 ", "Token2 ", "Token3"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        for line in resp.text.strip().split("\n"):
            assert not line.startswith("data:"), f"NDJSON line must NOT start with 'data:': {line}"

    def test_media_type_header(self):
        """Assert Content-Type header contains application/x-ndjson."""
        graph = _build_graph(chunks=["Hi"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        assert "application/x-ndjson" in resp.headers["content-type"]

    def test_session_is_first_event(self):
        graph = _build_graph(chunks=["Answer"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        events = _parse_events(resp)
        assert events[0]["type"] == "session"

    def test_done_is_last_event_on_success(self):
        graph = _build_graph(chunks=["Answer"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        events = _parse_events(resp)
        assert events[-1]["type"] == "done"
        assert isinstance(events[-1]["latency_ms"], int)
        assert isinstance(events[-1]["trace_id"], str)

    def test_all_10_event_types_across_scenarios(self):
        """Assert all 10 event types exercised across test scenarios."""
        observed_types: set[str] = set()

        # Scenario 1: Full success path with all optional events
        citations = [
            Citation(
                passage_id="p1",
                document_id="d1",
                document_name="report.pdf",
                start_offset=0,
                end_offset=50,
                text="Evidence passage",
                relevance_score=0.92,
            )
        ]
        groundedness = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="c1",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="ok",
                ),
            ],
            overall_grounded=True,
            confidence_adjustment=0.0,
        )
        graph1 = _build_graph(
            chunks=["The answer ", "is 42"],
            nodes=["query_rewrite", "format_response"],
            final_state={
                "citations": citations,
                "attempted_strategies": {"WIDEN_SEARCH"},
                "confidence_score": 88,
                "groundedness_result": groundedness,
            },
        )
        app1 = _make_integration_app(graph=graph1)

        with TestClient(app1) as client:
            resp1 = client.post(
                "/api/chat",
                json={"message": "What is the answer?", "collection_ids": ["c1"]},
            )

        events1 = _parse_events(resp1)
        for ev in events1:
            observed_types.add(ev["type"])

        # Verify success path event types
        success_expected = {
            "session",
            "status",
            "chunk",
            "citation",
            "meta_reasoning",
            "confidence",
            "groundedness",
            "done",
        }
        assert success_expected.issubset(observed_types)

        # Scenario 2: Clarification interrupt
        graph2 = _build_graph(interrupt="Which quarter are you asking about?")
        app2 = _make_integration_app(graph=graph2)

        with TestClient(app2) as client:
            resp2 = client.post(
                "/api/chat",
                json={"message": "revenue", "collection_ids": ["c1"]},
            )

        events2 = _parse_events(resp2)
        for ev in events2:
            observed_types.add(ev["type"])

        assert "clarification" in observed_types

        # Scenario 3: Error
        graph3 = _build_graph(error=CircuitOpenError("Qdrant down"))
        app3 = _make_integration_app(graph=graph3)

        with TestClient(app3) as client:
            resp3 = client.post(
                "/api/chat",
                json={"message": "test", "collection_ids": ["c1"]},
            )

        events3 = _parse_events(resp3)
        for ev in events3:
            observed_types.add(ev["type"])

        assert "error" in observed_types

        # Final: all 10 types observed
        all_10 = {
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
        assert all_10 == observed_types

    def test_confidence_is_always_int(self):
        """Confidence score must always be an integer, never float."""
        graph = _build_graph(
            chunks=["Answer"],
            final_state={"confidence_score": 72},
        )
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        events = _parse_events(resp)
        conf_events = [e for e in events if e["type"] == "confidence"]
        assert len(conf_events) == 1
        assert isinstance(conf_events[0]["score"], int)
        assert 0 <= conf_events[0]["score"] <= 100

    def test_error_event_includes_trace_id(self):
        graph = _build_graph(error=CircuitOpenError("down"))
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": ["c1"]},
            )

        events = _parse_events(resp)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "trace_id" in error_events[0]
        assert isinstance(error_events[0]["trace_id"], str)

    def test_no_collections_error_response(self):
        """Empty collection_ids should yield an error event."""
        graph = _build_graph(chunks=["hello"])
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "Test", "collection_ids": []},
            )

        events = _parse_events(resp)
        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert error_events[0]["code"] == "NO_COLLECTIONS"

    def test_clarification_stream_ends_after_question(self):
        """Stream must end after clarification — no done event."""
        graph = _build_graph(interrupt="Please clarify")
        app = _make_integration_app(graph=graph)

        with TestClient(app) as client:
            resp = client.post(
                "/api/chat",
                json={"message": "ambiguous", "collection_ids": ["c1"]},
            )

        events = _parse_events(resp)
        types = [e["type"] for e in events]
        assert "clarification" in types
        assert "done" not in types

    def test_multi_turn_session_continuity(self):
        """Two requests with same session_id maintain consistent session."""
        graph = _build_graph(chunks=["Answer"])
        app = _make_integration_app(graph=graph)
        sid = "integration-session-001"

        with TestClient(app) as client:
            r1 = client.post(
                "/api/chat",
                json={
                    "message": "first",
                    "collection_ids": ["c1"],
                    "session_id": sid,
                },
            )
            r2 = client.post(
                "/api/chat",
                json={
                    "message": "second",
                    "collection_ids": ["c1"],
                    "session_id": sid,
                },
            )

        e1 = _parse_events(r1)
        e2 = _parse_events(r2)

        assert e1[0]["type"] == "session"
        assert e2[0]["type"] == "session"
        assert e1[0]["session_id"] == sid
        assert e2[0]["session_id"] == sid
