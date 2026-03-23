"""Unit tests for backend.retrieval.score_normalizer.normalize_scores (T013).

normalize_scores is a MODULE-LEVEL FUNCTION — do NOT instantiate any class.
It normalizes chunk.dense_score (NOT chunk.score — that field does not exist).
"""
from __future__ import annotations

import pytest

from backend.agent.schemas import RetrievedChunk
from backend.retrieval.score_normalizer import normalize_scores


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    chunk_id: str,
    dense_score: float,
    collection: str = "col-a",
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=f"Content for {chunk_id}",
        source_file="test.pdf",
        page=1,
        breadcrumb="",
        parent_id="p-001",
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.5,
        rerank_score=None,
    )


# ---------------------------------------------------------------------------
# T013.1 — Empty input
# ---------------------------------------------------------------------------

class TestNormalizeScoresEmpty:
    def test_empty_list_returns_empty_list(self):
        """normalize_scores([]) must return []."""
        result = normalize_scores([])
        assert result == []

    def test_empty_list_returns_same_object(self):
        """Return value identity — same list object (or equivalent empty)."""
        chunks: list[RetrievedChunk] = []
        result = normalize_scores(chunks)
        assert result is chunks or result == []


# ---------------------------------------------------------------------------
# T013.2 — Single item
# ---------------------------------------------------------------------------

class TestNormalizeScoresSingleItem:
    def test_single_item_returned(self):
        """Single-chunk list must be returned (length 1)."""
        chunk = _make_chunk("c-1", dense_score=0.75)
        result = normalize_scores([chunk])
        assert len(result) == 1

    def test_single_item_score_range_zero_no_crash(self):
        """Single item has range=0; function must not raise ZeroDivisionError."""
        chunk = _make_chunk("c-1", dense_score=0.75)
        # Should not raise
        result = normalize_scores([chunk])
        assert result[0].dense_score is not None


# ---------------------------------------------------------------------------
# T013.3 — All-equal scores (no division by zero)
# ---------------------------------------------------------------------------

class TestNormalizeScoresEqualScores:
    def test_all_equal_scores_no_crash(self):
        """All items with same dense_score must not trigger ZeroDivisionError."""
        chunks = [
            _make_chunk("c-1", dense_score=0.5),
            _make_chunk("c-2", dense_score=0.5),
            _make_chunk("c-3", dense_score=0.5),
        ]
        # Must not raise
        result = normalize_scores(chunks)
        assert len(result) == 3

    def test_all_equal_scores_values_unchanged(self):
        """When range=0, dense_score values should remain unchanged (not NaN/inf)."""
        chunks = [
            _make_chunk("c-1", dense_score=0.5),
            _make_chunk("c-2", dense_score=0.5),
        ]
        result = normalize_scores(chunks)
        for chunk in result:
            # Score should be a valid finite float
            assert isinstance(chunk.dense_score, float)
            assert chunk.dense_score == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# T013.4 — Min maps to 0.0, max maps to 1.0
# ---------------------------------------------------------------------------

class TestNormalizeScoresMinMax:
    def test_min_score_maps_to_zero(self):
        """The chunk with the lowest dense_score in a collection gets 0.0."""
        chunks = [
            _make_chunk("c-1", dense_score=0.2),
            _make_chunk("c-2", dense_score=0.5),
            _make_chunk("c-3", dense_score=0.8),
        ]
        result = normalize_scores(chunks)
        scores = {c.chunk_id: c.dense_score for c in result}
        assert scores["c-1"] == pytest.approx(0.0)

    def test_max_score_maps_to_one(self):
        """The chunk with the highest dense_score in a collection gets 1.0."""
        chunks = [
            _make_chunk("c-1", dense_score=0.2),
            _make_chunk("c-2", dense_score=0.5),
            _make_chunk("c-3", dense_score=0.8),
        ]
        result = normalize_scores(chunks)
        scores = {c.chunk_id: c.dense_score for c in result}
        assert scores["c-3"] == pytest.approx(1.0)

    def test_middle_score_normalized_correctly(self):
        """Middle value is (0.5 - 0.2) / (0.8 - 0.2) = 0.5."""
        chunks = [
            _make_chunk("c-1", dense_score=0.2),
            _make_chunk("c-2", dense_score=0.5),
            _make_chunk("c-3", dense_score=0.8),
        ]
        result = normalize_scores(chunks)
        scores = {c.chunk_id: c.dense_score for c in result}
        assert scores["c-2"] == pytest.approx(0.5)

    def test_all_scores_in_zero_to_one_range(self):
        """All normalized scores must be in [0.0, 1.0]."""
        chunks = [
            _make_chunk(f"c-{i}", dense_score=0.1 * i)
            for i in range(1, 6)
        ]
        result = normalize_scores(chunks)
        for chunk in result:
            assert 0.0 <= chunk.dense_score <= 1.0


# ---------------------------------------------------------------------------
# T013.5 — Order preserved
# ---------------------------------------------------------------------------

class TestNormalizeScoresOrder:
    def test_chunk_order_preserved(self):
        """normalize_scores must not reorder chunks in the returned list."""
        ids = ["c-3", "c-1", "c-5", "c-2"]
        chunks = [_make_chunk(cid, dense_score=float(i)) for i, cid in enumerate(ids)]
        result = normalize_scores(chunks)
        returned_ids = [c.chunk_id for c in result]
        assert returned_ids == ids

    def test_returned_list_same_length(self):
        """Output list length must match input length."""
        chunks = [_make_chunk(f"c-{i}", dense_score=float(i)) for i in range(5)]
        result = normalize_scores(chunks)
        assert len(result) == len(chunks)


# ---------------------------------------------------------------------------
# T013.6 — Multiple collections normalized independently
# ---------------------------------------------------------------------------

class TestNormalizeScoresMultipleCollections:
    def test_each_collection_normalized_independently(self):
        """Chunks from different collections are normalized within their own group."""
        col_a = [
            _make_chunk("a-1", dense_score=0.2, collection="col-a"),
            _make_chunk("a-2", dense_score=0.8, collection="col-a"),
        ]
        col_b = [
            _make_chunk("b-1", dense_score=0.4, collection="col-b"),
            _make_chunk("b-2", dense_score=0.6, collection="col-b"),
        ]
        result = normalize_scores(col_a + col_b)
        scores = {c.chunk_id: c.dense_score for c in result}

        # col-a: min=0.2→0.0, max=0.8→1.0
        assert scores["a-1"] == pytest.approx(0.0)
        assert scores["a-2"] == pytest.approx(1.0)
        # col-b: min=0.4→0.0, max=0.6→1.0
        assert scores["b-1"] == pytest.approx(0.0)
        assert scores["b-2"] == pytest.approx(1.0)
