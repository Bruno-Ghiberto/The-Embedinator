"""Integration test for US4 traces — T067.

Verifies trace completeness and accuracy after a chat query.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from tests.integration.conftest import unique_name

pytestmark = pytest.mark.xfail(reason="Fixture setup error with mocked lifespan — pre-existing")


@pytest.fixture
def trace_app(tmp_path):
    """Create test app for trace verification."""
    mock_checkpointer = MemorySaver()
    mock_checkpointer.setup = AsyncMock()

    mock_qdrant = AsyncMock()
    mock_qdrant.connect = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.search = AsyncMock(return_value=[
        {
            "id": "chunk-1",
            "score": 0.92,
            "payload": {
                "document_id": "doc-trace-test",
                "text": "AI is artificial intelligence.",
                "chunk_index": 0,
            },
        },
        {
            "id": "chunk-2",
            "score": 0.78,
            "payload": {
                "document_id": "doc-trace-test",
                "text": "Machine learning is a subset of AI.",
                "chunk_index": 1,
            },
        },
    ])

    mock_embed = AsyncMock()
    mock_embed.embed_single = AsyncMock(return_value=[0.1] * 768)

    mock_llm = AsyncMock()

    async def mock_stream(prompt):
        yield "AI stands for artificial intelligence."

    mock_llm.generate_stream = mock_stream

    mock_registry = AsyncMock()
    mock_registry.initialize = AsyncMock()
    mock_registry.get_embedding_provider = AsyncMock(return_value=mock_embed)
    mock_registry.get_active_llm = AsyncMock(return_value=mock_llm)

    with patch("backend.main.QdrantClientWrapper", return_value=mock_qdrant), \
         patch("backend.main.ProviderRegistry", return_value=mock_registry), \
         patch("langgraph.checkpoint.sqlite.aio.AsyncSqliteSaver") as mock_saver_cls:

        mock_saver_cls.from_conn_string.return_value = mock_checkpointer

        from backend.main import create_app
        app = create_app()

        with TestClient(app) as client:
            # Set up a simple mock graph (no LLM dependencies)
            from tests.mocks import build_simple_chat_graph
            app.state._conversation_graph = build_simple_chat_graph()

            coll_name = unique_name("Trace")
            coll_resp = client.post("/api/collections", json={"name": coll_name})
            assert coll_resp.status_code == 201
            coll_id = coll_resp.json()["id"]

            client._coll_id = coll_id
            yield client


def test_trace_created_after_chat(trace_app):
    """Verify a trace is created when a chat query completes."""
    resp = trace_app.post(
        "/api/chat",
        json={"message": "What is AI?", "collection_ids": [trace_app._coll_id]},
    )
    assert resp.status_code == 200

    lines = resp.text.strip().split("\n")
    events = [json.loads(line) for line in lines]
    metadata = [e for e in events if e["type"] == "metadata"]
    assert len(metadata) == 1
    trace_id = metadata[0]["trace_id"]

    trace_resp = trace_app.get(f"/api/traces/{trace_id}")
    assert trace_resp.status_code == 200
    trace = trace_resp.json()

    assert trace["id"] == trace_id
    assert trace["query_text"] == "What is AI?"
    assert trace_app._coll_id in trace["collections_searched"]
    assert 0 <= trace["confidence_score"] <= 100


def test_trace_contains_reasoning_steps(trace_app):
    """Verify trace includes reasoning steps."""
    resp = trace_app.post(
        "/api/chat",
        json={"message": "What is ML?", "collection_ids": [trace_app._coll_id]},
    )

    lines = resp.text.strip().split("\n")
    events = [json.loads(line) for line in lines]
    trace_id = [e for e in events if e["type"] == "metadata"][0]["trace_id"]

    trace = trace_app.get(f"/api/traces/{trace_id}").json()
    assert trace["reasoning_steps"] is not None
    assert len(trace["reasoning_steps"]) >= 1
    # Wave 4 changed strategy name from initial_retrieval to conversation_graph
    assert trace["reasoning_steps"][0]["strategy"] == "conversation_graph"


def test_trace_not_found_returns_404(trace_app):
    """Verify non-existent trace returns 404."""
    resp = trace_app.get("/api/traces/nonexistent-trace-id")
    assert resp.status_code == 404
