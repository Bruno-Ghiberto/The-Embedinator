"""Integration tests for HybridSearcher against live Qdrant.

All tests require a live Qdrant on localhost:6333.
They are auto-skipped when Qdrant is unreachable via the pytest_runtest_setup
hook in tests/conftest.py — do NOT call pytest.skip() manually here.
"""

import datetime

import pytest
from qdrant_client import AsyncQdrantClient

from backend.config import Settings
from backend.retrieval.searcher import HybridSearcher
from backend.storage.qdrant_client import QdrantPoint, QdrantStorage, SparseVector
from tests.integration.conftest import unique_name


def _make_payload(text: str, collection_name: str) -> dict:
    """Build a valid payload with all 11 required FR-011 fields."""
    return {
        "text": text,
        "parent_id": "parent-001",
        "breadcrumb": "Section 1 > Tests",
        "source_file": "integration-test.pdf",
        "page": 1,
        "chunk_index": 0,
        "doc_type": "Prose",
        "chunk_hash": f"hash-{text[:12].replace(' ', '')}",
        "embedding_model": "nomic-embed-text",
        "collection_name": collection_name,
        "ingested_at": datetime.datetime.utcnow().isoformat(),
    }


async def _seed_collection(
    storage: QdrantStorage, name: str, vector_size: int = 384
) -> None:
    """Create a collection and seed it with 3 known vectors.

    Vector for point id=1 is [1.0, 1.0, ...] — the "known-relevant" document.
    The other two points use dissimilar vectors.
    """
    await storage.create_collection(name, vector_size=vector_size)

    # id=1: highest similarity to a [0.99, ...] query
    known_vector = [1.0] * vector_size
    other_a = [0.1] * vector_size
    other_b = [0.2] * vector_size

    points = [
        QdrantPoint(
            id=1,
            vector=known_vector,
            sparse_vector=None,
            payload=_make_payload("target document about authentication security", name),
        ),
        QdrantPoint(
            id=2,
            vector=other_a,
            sparse_vector=None,
            payload=_make_payload("unrelated document about invoicing taxes", name),
        ),
        QdrantPoint(
            id=3,
            vector=other_b,
            sparse_vector=None,
            payload=_make_payload("another unrelated document about storage systems", name),
        ),
    ]
    await storage.batch_upsert(name, points)


@pytest.mark.require_docker
async def test_known_relevant_document_appears_in_top_results():
    """Known-relevant document (closest vector) appears in top-3 results."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("known")
    try:
        await _seed_collection(storage, name)

        # Query vector close to the known-relevant vector [1.0, ...]
        query_vector = [0.99] * 384
        results = await storage.search_hybrid(
            name,
            dense_vector=query_vector,
            sparse_vector=None,
            top_k=3,
        )
        assert len(results) >= 1
        result_ids = [str(r.id) for r in results]
        assert "1" in result_ids, (
            f"Known-relevant document (id=1) not in top-3, got: {result_ids}"
        )
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_dense_only_search_returns_results():
    """Dense-only search (sparse_vector=None) returns results from Qdrant."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("dense")
    try:
        await _seed_collection(storage, name)

        results = await storage.search_hybrid(
            name,
            dense_vector=[0.5] * 384,
            sparse_vector=None,
            top_k=5,
        )
        assert len(results) > 0
        assert all(hasattr(r, "score") for r in results)
        assert all(hasattr(r, "payload") for r in results)
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_hybrid_search_returns_results_in_correct_ranking_order():
    """Hybrid search (dense + sparse) returns results sorted by descending score."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("hybrid")
    try:
        await _seed_collection(storage, name)

        # Provide a sparse vector alongside the dense vector
        sparse_vec = SparseVector(indices=[0, 1, 2], values=[0.5, 0.3, 0.2])
        results = await storage.search_hybrid(
            name,
            dense_vector=[1.0] * 384,
            sparse_vector=sparse_vec,
            top_k=5,
        )
        assert len(results) > 0
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True), (
            "Hybrid search results must be sorted by descending score"
        )
    finally:
        await storage.delete_collection(name)


@pytest.mark.require_docker
async def test_hybrid_searcher_circuit_breaker_state():
    """HybridSearcher circuit breaker opens after failures and blocks further calls.

    Tests that:
    - Initial state is closed (_circuit_open=False)
    - After manually opening the circuit, search() raises QdrantConnectionError
      via the _check_circuit() guard (no network call is made)
    """
    from backend.errors import QdrantConnectionError

    client = AsyncQdrantClient(host="localhost", port=6333)
    settings = Settings()
    searcher = HybridSearcher(client=client, settings=settings)

    # Verify clean initial state
    assert searcher._circuit_open is False
    assert searcher._failure_count == 0

    # Open the circuit manually (simulates repeated Qdrant failures)
    searcher._circuit_open = True
    searcher._failure_count = searcher._max_failures

    async def mock_embed_fn(text: str) -> list[float]:
        return [1.0] * 384

    # With circuit open, search() must raise before touching the network
    with pytest.raises(QdrantConnectionError):
        await searcher.search(
            query="authentication",
            collection="any-collection",
            top_k=5,
            embed_fn=mock_embed_fn,
        )

    await client.close()
