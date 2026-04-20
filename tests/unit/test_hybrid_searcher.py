"""Unit tests for HybridSearcher and ScoreNormalizer (spec-03)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.agent.schemas import RetrievedChunk
from backend.retrieval.score_normalizer import normalize_scores


def _chunk(chunk_id="c1", dense_score=0.8, collection="col1"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="test",
        source_file="test.md",
        breadcrumb="ch1",
        parent_id="p1",
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.3,
        rerank_score=None,
    )


def _make_settings(**overrides):
    """Create a mock Settings object."""
    s = MagicMock()
    s.hybrid_dense_weight = 0.7
    s.hybrid_sparse_weight = 0.3
    s.top_k_retrieval = 20
    s.circuit_breaker_failure_threshold = 5
    s.circuit_breaker_cooldown_secs = 30
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


class TestHybridSearcherCircuitBreaker:
    """Test circuit breaker logic without needing qdrant_client import."""

    def test_circuit_starts_closed(self):
        # Test the circuit breaker state management logic directly
        from backend.retrieval.searcher import HybridSearcher

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings())

        assert searcher._circuit_open is False
        assert searcher._failure_count == 0

    def test_record_failure_increments(self):
        from backend.retrieval.searcher import HybridSearcher

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings())

        searcher._record_failure()
        assert searcher._failure_count == 1
        assert searcher._circuit_open is False

    def test_circuit_opens_after_threshold(self):
        from backend.retrieval.searcher import HybridSearcher

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings(circuit_breaker_failure_threshold=3))

        for _ in range(3):
            searcher._record_failure()

        assert searcher._circuit_open is True

    def test_record_success_resets(self):
        from backend.retrieval.searcher import HybridSearcher

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings())

        searcher._failure_count = 3
        searcher._circuit_open = True
        searcher._record_success()

        assert searcher._failure_count == 0
        assert searcher._circuit_open is False

    @pytest.mark.asyncio
    async def test_check_circuit_raises_when_open(self):
        from backend.retrieval.searcher import HybridSearcher
        from backend.errors import QdrantConnectionError

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings())
        searcher._circuit_open = True

        with pytest.raises(QdrantConnectionError, match="Circuit breaker is open"):
            await searcher._check_circuit()

    @pytest.mark.asyncio
    async def test_search_returns_empty_without_embed_fn(self):
        from backend.retrieval.searcher import HybridSearcher

        client = AsyncMock()
        searcher = HybridSearcher(client, _make_settings())

        result = await searcher.search("query", "col1", embed_fn=None)
        assert result == []


class TestScoreNormalizer:
    """Test per-collection min-max normalization."""

    def test_empty_input(self):
        assert normalize_scores([]) == []

    def test_single_collection_single_chunk(self):
        chunks = [_chunk(dense_score=0.5)]
        result = normalize_scores(chunks)
        # Single chunk, no range -> score unchanged
        assert result[0].dense_score == 0.5

    def test_single_collection_normalizes(self):
        chunks = [
            _chunk(chunk_id="c1", dense_score=0.2, collection="col1"),
            _chunk(chunk_id="c2", dense_score=0.8, collection="col1"),
            _chunk(chunk_id="c3", dense_score=0.5, collection="col1"),
        ]
        result = normalize_scores(chunks)

        # Min 0.2, max 0.8, range 0.6
        assert result[0].dense_score == pytest.approx(0.0)  # (0.2 - 0.2) / 0.6
        assert result[1].dense_score == pytest.approx(1.0)  # (0.8 - 0.2) / 0.6
        assert result[2].dense_score == pytest.approx(0.5)  # (0.5 - 0.2) / 0.6

    def test_multi_collection_independent(self):
        chunks = [
            _chunk(chunk_id="c1", dense_score=0.1, collection="col1"),
            _chunk(chunk_id="c2", dense_score=0.9, collection="col1"),
            _chunk(chunk_id="c3", dense_score=0.3, collection="col2"),
            _chunk(chunk_id="c4", dense_score=0.7, collection="col2"),
        ]
        result = normalize_scores(chunks)

        # col1: min=0.1, max=0.9, range=0.8
        col1 = [c for c in result if c.collection == "col1"]
        assert col1[0].dense_score == pytest.approx(0.0)
        assert col1[1].dense_score == pytest.approx(1.0)

        # col2: min=0.3, max=0.7, range=0.4
        col2 = [c for c in result if c.collection == "col2"]
        assert col2[0].dense_score == pytest.approx(0.0)
        assert col2[1].dense_score == pytest.approx(1.0)

    def test_same_scores_no_division_by_zero(self):
        chunks = [
            _chunk(chunk_id="c1", dense_score=0.5, collection="col1"),
            _chunk(chunk_id="c2", dense_score=0.5, collection="col1"),
        ]
        result = normalize_scores(chunks)
        # Same scores, range=0 -> scores unchanged
        assert result[0].dense_score == 0.5
        assert result[1].dense_score == 0.5
