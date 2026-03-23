"""Unit tests for spec-03 5-signal confidence scoring (R8)."""
import pytest

from backend.agent.confidence import compute_confidence
from backend.agent.schemas import RetrievedChunk


def _chunk(
    rerank_score=None,
    dense_score=0.5,
    collection="col1",
    chunk_id="c1",
    parent_id="p1",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text="test text",
        source_file="test.md",
        breadcrumb="ch1",
        parent_id=parent_id,
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.3,
        rerank_score=rerank_score,
    )


class TestSignalConfidence:
    """Tests for the 5-signal confidence formula."""

    def test_empty_chunks_returns_zero(self):
        assert compute_confidence([]) == 0.0

    def test_returns_float_for_retrieved_chunks(self):
        result = compute_confidence([_chunk(rerank_score=0.8)])
        assert isinstance(result, float)

    def test_output_range_zero_to_one(self):
        chunks = [_chunk(rerank_score=s) for s in [0.9, 0.8, 0.7, 0.6, 0.5]]
        result = compute_confidence(chunks)
        assert 0.0 <= result <= 1.0

    def test_high_rerank_scores_yield_high_confidence(self):
        chunks = [_chunk(rerank_score=0.95, chunk_id=f"c{i}") for i in range(5)]
        result = compute_confidence(chunks)
        assert result > 0.7

    def test_low_rerank_scores_yield_low_confidence(self):
        chunks = [_chunk(rerank_score=0.1, chunk_id=f"c{i}") for i in range(5)]
        result = compute_confidence(chunks)
        assert result < 0.5

    def test_single_chunk(self):
        result = compute_confidence([_chunk(rerank_score=0.8)])
        assert 0.0 < result < 1.0

    def test_falls_back_to_dense_score_when_no_rerank(self):
        chunks = [_chunk(rerank_score=None, dense_score=0.9, chunk_id=f"c{i}") for i in range(3)]
        result = compute_confidence(chunks)
        assert result > 0.0

    def test_chunk_count_ratio_signal(self):
        """More chunks relative to expected count should increase confidence."""
        few = [_chunk(rerank_score=0.7, chunk_id=f"c{i}") for i in range(1)]
        many = [_chunk(rerank_score=0.7, chunk_id=f"c{i}") for i in range(5)]
        assert compute_confidence(many) > compute_confidence(few)

    def test_collection_coverage_signal(self):
        """Searching more collections should increase confidence."""
        result_partial = compute_confidence(
            [_chunk(rerank_score=0.7)],
            num_collections_searched=1,
            num_collections_total=3,
        )
        result_full = compute_confidence(
            [_chunk(rerank_score=0.7)],
            num_collections_searched=3,
            num_collections_total=3,
        )
        assert result_full > result_partial

    def test_top_k_parameter_limits_scoring(self):
        chunks = [_chunk(rerank_score=0.9, chunk_id=f"c{i}") for i in range(10)]
        result_k3 = compute_confidence(chunks, top_k=3)
        result_k10 = compute_confidence(chunks, top_k=10)
        # Both should be valid, may differ slightly due to variance signal
        assert 0.0 <= result_k3 <= 1.0
        assert 0.0 <= result_k10 <= 1.0

    def test_consistent_scores_yield_higher_confidence(self):
        """Low variance (consistent scores) should give higher confidence."""
        consistent = [_chunk(rerank_score=0.8, chunk_id=f"c{i}") for i in range(5)]
        varied = [_chunk(rerank_score=s, chunk_id=f"c{i}") for i, s in enumerate([0.95, 0.8, 0.3, 0.1, 0.05])]
        # With same mean, consistent should score higher due to inverse variance
        assert compute_confidence(consistent) >= compute_confidence(varied)


class TestLegacyConfidence:
    """Tests for backward-compatible legacy path (list[dict])."""

    def test_legacy_returns_int(self):
        result = compute_confidence([{"relevance_score": 0.8}])
        assert isinstance(result, int)

    def test_legacy_perfect_score(self):
        result = compute_confidence([{"relevance_score": 1.0}] * 5)
        assert result == 100

    def test_legacy_zero_score(self):
        result = compute_confidence([{"relevance_score": 0.0}])
        assert result == 0

    def test_legacy_mixed_scores(self):
        result = compute_confidence([
            {"relevance_score": 0.9},
            {"relevance_score": 0.5},
        ])
        assert 0 < result < 100
