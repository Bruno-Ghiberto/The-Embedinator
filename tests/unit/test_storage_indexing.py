"""Unit tests for backend.storage.indexing.index_chunks."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.storage.indexing import index_chunks


@pytest.fixture
def mock_embed_provider():
    """Fake embedding provider: 384-dim vectors, async embed()."""
    provider = MagicMock()
    provider.get_dimension.return_value = 384
    provider.embed = AsyncMock(return_value=[[0.1] * 384, [0.2] * 384])
    return provider


@pytest.fixture
def mock_app(mock_embed_provider):
    """Fake FastAPI app with qdrant and registry on state."""
    app = MagicMock()
    app.state.qdrant = AsyncMock()
    app.state.registry = MagicMock()
    app.state.registry.get_embedding_provider = AsyncMock(return_value=mock_embed_provider)
    return app


@pytest.fixture
def doc_chunks():
    """Two chunk dicts matching the shape produced by the chunker."""
    return [
        {
            "text": "First chunk text.",
            "chunk_index": 0,
            "start_offset": 0,
            "end_offset": 17,
        },
        {
            "text": "Second chunk text.",
            "chunk_index": 1,
            "start_offset": 18,
            "end_offset": 36,
        },
    ]


async def test_empty_chunks_returns_without_error(mock_app):
    """Empty chunks list triggers early return — no Qdrant or embed calls made."""
    await index_chunks(mock_app, "doc-001", [])

    mock_app.state.qdrant.upsert.assert_not_called()
    mock_app.state.registry.get_embedding_provider.assert_not_called()


async def test_qdrant_upsert_called_with_correct_collection(mock_app, doc_chunks):
    """upsert() must be called with the 'embeddings' collection name as first arg."""
    await index_chunks(mock_app, "doc-001", doc_chunks)

    mock_app.state.qdrant.upsert.assert_called_once()
    collection_arg = mock_app.state.qdrant.upsert.call_args[0][0]
    assert collection_arg == "embeddings"


async def test_chunk_texts_passed_to_embed_provider(mock_app, mock_embed_provider, doc_chunks):
    """embed() must receive exactly the 'text' values from each chunk dict."""
    await index_chunks(mock_app, "doc-001", doc_chunks)

    expected_texts = [c["text"] for c in doc_chunks]
    mock_embed_provider.embed.assert_called_once_with(expected_texts)


async def test_qdrant_storage_errors_propagated(mock_app, doc_chunks):
    """Exceptions raised by qdrant.upsert() must propagate to the caller."""
    mock_app.state.qdrant.upsert.side_effect = RuntimeError("Qdrant unavailable")

    with pytest.raises(RuntimeError, match="Qdrant unavailable"):
        await index_chunks(mock_app, "doc-001", doc_chunks)


async def test_doc_id_appears_in_every_point_payload(mock_app, doc_chunks):
    """Each Qdrant point payload must carry 'document_id' equal to the doc_id arg."""
    await index_chunks(mock_app, "doc-abc-123", doc_chunks)

    points = mock_app.state.qdrant.upsert.call_args[0][1]
    assert len(points) == len(doc_chunks)
    for point in points:
        assert point["payload"]["document_id"] == "doc-abc-123"


async def test_payload_contains_required_keys(mock_app, doc_chunks):
    """Each point payload must have: document_id, text, chunk_index, start_offset, end_offset."""
    await index_chunks(mock_app, "doc-001", doc_chunks)

    points = mock_app.state.qdrant.upsert.call_args[0][1]
    required_keys = {"document_id", "text", "chunk_index", "start_offset", "end_offset"}
    for point in points:
        assert required_keys.issubset(point["payload"].keys())
