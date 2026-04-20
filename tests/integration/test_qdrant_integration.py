"""Integration tests for QdrantStorage CRUD operations.

All tests require a live Qdrant on localhost:6333.
They are auto-skipped when Qdrant is unreachable via the pytest_runtest_setup
hook in tests/conftest.py — do NOT call pytest.skip() manually here.
"""

import datetime

import pytest

from backend.storage.qdrant_client import QdrantPoint, QdrantStorage
from tests.integration.conftest import unique_name


def _make_payload(text: str, collection_name: str) -> dict:
    """Build a minimal valid payload with all 11 required FR-011 fields."""
    return {
        "text": text,
        "parent_id": "parent-001",
        "breadcrumb": "Section 1 > Tests",
        "source_file": "test-document.pdf",
        "page": 1,
        "chunk_index": 0,
        "doc_type": "Prose",
        "chunk_hash": "abc123hash456",
        "embedding_model": "nomic-embed-text",
        "collection_name": collection_name,
        "ingested_at": datetime.datetime.utcnow().isoformat(),
    }


@pytest.mark.require_docker
async def test_create_collection():
    """create_collection() succeeds — collection appears in collection_exists()."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("crud")
    try:
        await storage.create_collection(name, vector_size=384)
        exists = await storage.collection_exists(name)
        assert exists is True
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_batch_upsert_inserts_vectors():
    """batch_upsert() inserts vectors — verify via return count and collection info."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("upsert")
    try:
        await storage.create_collection(name, vector_size=384)
        points = [
            QdrantPoint(
                id=1,
                vector=[0.1] * 384,
                sparse_vector=None,
                payload=_make_payload("first document about authentication", name),
            ),
            QdrantPoint(
                id=2,
                vector=[0.5] * 384,
                sparse_vector=None,
                payload=_make_payload("second document about tokens", name),
            ),
            QdrantPoint(
                id=3,
                vector=[0.9] * 384,
                sparse_vector=None,
                payload=_make_payload("third document about invoicing", name),
            ),
        ]
        count = await storage.batch_upsert(name, points)
        assert count == 3
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_search_hybrid_returns_results_in_descending_order():
    """search_hybrid() returns results with scores sorted in descending order."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("search")
    try:
        await storage.create_collection(name, vector_size=384)
        points = [
            QdrantPoint(
                id=i,
                vector=[round(0.1 * i, 2)] * 384,
                sparse_vector=None,
                payload=_make_payload(f"document number {i}", name),
            )
            for i in range(1, 5)
        ]
        await storage.batch_upsert(name, points)

        results = await storage.search_hybrid(
            name,
            dense_vector=[0.1] * 384,
            sparse_vector=None,
            top_k=5,
        )
        assert len(results) > 0
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), "Results should be sorted by descending score"
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_delete_collection_removes_it():
    """delete_collection() removes the collection — subsequent collection_exists() is False."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("delete")

    await storage.create_collection(name, vector_size=384)
    assert await storage.collection_exists(name) is True

    await storage.delete_collection(name)
    assert await storage.collection_exists(name) is False
