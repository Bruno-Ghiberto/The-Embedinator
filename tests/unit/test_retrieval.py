"""Unit tests for retrieval logic — T047."""

import pytest

from backend.agent.retrieval import retrieve_passages


class MockQdrant:
    """Mock QdrantClientWrapper returning predefined search results."""

    def __init__(self, results: list[dict]):
        self._results = results

    async def search(self, collection, vector, limit=20):
        return self._results


class MockDB:
    """Mock SQLiteDB returning predefined documents."""

    def __init__(self, documents: dict[str, dict]):
        self._docs = documents

    async def get_document(self, doc_id: str):
        return self._docs.get(doc_id)


@pytest.mark.asyncio
async def test_retrieve_filters_by_collection():
    """Verify passages are filtered by collection membership."""
    qdrant = MockQdrant([
        {"id": "p1", "score": 0.95, "payload": {"document_id": "doc1", "text": "matched", "chunk_index": 0}},
        {"id": "p2", "score": 0.80, "payload": {"document_id": "doc2", "text": "other coll", "chunk_index": 0}},
    ])
    db = MockDB({
        "doc1": {"name": "test.pdf", "status": "indexed", "collection_ids": ["col-1"]},
        "doc2": {"name": "other.pdf", "status": "indexed", "collection_ids": ["col-2"]},
    })

    passages = await retrieve_passages([0.1] * 768, ["col-1"], qdrant, db)
    assert len(passages) == 1
    assert passages[0]["document_id"] == "doc1"


@pytest.mark.asyncio
async def test_retrieve_excludes_deleted():
    """Verify deleted documents are excluded."""
    qdrant = MockQdrant([
        {"id": "p1", "score": 0.95, "payload": {"document_id": "doc1", "text": "deleted", "chunk_index": 0}},
    ])
    db = MockDB({
        "doc1": {"name": "test.pdf", "status": "deleted", "collection_ids": ["col-1"]},
    })

    passages = await retrieve_passages([0.1] * 768, ["col-1"], qdrant, db)
    assert len(passages) == 0


@pytest.mark.asyncio
async def test_retrieve_returns_top_k():
    """Verify only top_k passages are returned."""
    qdrant = MockQdrant([
        {"id": f"p{i}", "score": 1.0 - i * 0.1, "payload": {"document_id": f"doc{i}", "text": f"text{i}", "chunk_index": 0}}
        for i in range(10)
    ])
    db = MockDB({
        f"doc{i}": {"name": f"d{i}.pdf", "status": "indexed", "collection_ids": ["col-1"]}
        for i in range(10)
    })

    passages = await retrieve_passages([0.1] * 768, ["col-1"], qdrant, db, top_k=3)
    assert len(passages) == 3
    # Should be sorted by score descending
    assert passages[0]["relevance_score"] >= passages[1]["relevance_score"]


@pytest.mark.asyncio
async def test_retrieve_empty_results():
    """Verify empty Qdrant results yield empty passages."""
    qdrant = MockQdrant([])
    db = MockDB({})
    passages = await retrieve_passages([0.1] * 768, ["col-1"], qdrant, db)
    assert passages == []
