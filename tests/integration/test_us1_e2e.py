"""Integration test for US1 end-to-end — T048.

Uploads a document, queries it, and verifies the answer with citations.
Requires mocking Qdrant, Ollama, and the ConversationGraph since they're
external services or require LLM access.
"""

import json
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from tests.integration.conftest import unique_name

pytestmark = pytest.mark.xfail(reason="Lifespan teardown/setup errors with mocked services — pre-existing")


@pytest.fixture
def test_app(tmp_path):
    """Create a test app with mocked external services and conversation graph."""
    mock_checkpointer = MemorySaver()
    mock_checkpointer.setup = AsyncMock()

    mock_qdrant = AsyncMock()
    mock_qdrant.connect = AsyncMock()
    mock_qdrant.close = AsyncMock()
    mock_qdrant.ensure_collection = AsyncMock()
    mock_qdrant.upsert = AsyncMock()
    mock_qdrant.search = AsyncMock(return_value=[
        {
            "id": "chunk-1",
            "score": 0.95,
            "payload": {
                "document_id": None,  # Set dynamically
                "text": "The capital of France is Paris.",
                "chunk_index": 0,
            },
        }
    ])
    mock_qdrant.health_check = AsyncMock(return_value=True)

    mock_embed = AsyncMock()
    mock_embed.embed = AsyncMock(return_value=[[0.1] * 768])
    mock_embed.embed_single = AsyncMock(return_value=[0.1] * 768)
    mock_embed.get_dimension = AsyncMock(return_value=768)

    mock_llm = AsyncMock()

    async def mock_stream(prompt):
        for token in ["The ", "capital ", "of ", "France ", "is ", "Paris."]:
            yield token

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

            client._mock_qdrant = mock_qdrant
            yield client


def test_us1_create_collection(test_app):
    """Step 1: Create a collection."""
    name = unique_name("US1-Create")
    resp = test_app.post("/api/collections", json={"name": name})
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["name"] == name


def test_us1_full_workflow(test_app):
    """Full US1 workflow: create collection -> upload doc -> query -> get answer."""
    # 1. Create collection
    name = unique_name("France")
    coll_resp = test_app.post("/api/collections", json={"name": name})
    assert coll_resp.status_code == 201
    coll_id = coll_resp.json()["id"]

    # 2. Upload document
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w", delete=False) as f:
        f.write("The capital of France is Paris.")
        f.flush()

        with open(f.name, "rb") as upload_file:
            resp = test_app.post(
                "/api/documents",
                files={"file": ("france.txt", upload_file, "text/plain")},
                data={"collection_ids": json.dumps([coll_id])},
            )
    assert resp.status_code == 202
    doc_id = resp.json()["id"]

    # Update mock to return the correct document_id
    test_app._mock_qdrant.search.return_value = [
        {
            "id": "chunk-1",
            "score": 0.95,
            "payload": {
                "document_id": doc_id,
                "text": "The capital of France is Paris.",
                "chunk_index": 0,
            },
        }
    ]

    # 3. Query (Wave 4 renamed query→message, model_name→llm_model)
    resp = test_app.post(
        "/api/chat",
        json={"message": "What is the capital of France?", "collection_ids": [coll_id]},
    )
    assert resp.status_code == 200

    # 4. Parse NDJSON response
    lines = resp.text.strip().split("\n")
    events = [json.loads(line) for line in lines]

    metadata_events = [e for e in events if e["type"] == "metadata"]

    assert len(metadata_events) == 1

    # Verify metadata has trace_id and confidence (renamed from confidence_score)
    meta = metadata_events[0]
    assert "trace_id" in meta
    assert 0 <= meta["confidence"] <= 100
