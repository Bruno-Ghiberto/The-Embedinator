"""Unit tests for backend.retrieval.reranker.Reranker (T012).

Strategy: mock sentence_transformers.CrossEncoder to avoid loading real
model weights (SC-003 — unit suite must complete in < 30 seconds).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.config import Settings
from backend.errors import RerankerError
from backend.retrieval.reranker import Reranker


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides) -> Settings:
    """Build a minimal Settings object."""
    defaults = {
        "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
        "top_k_rerank": 5,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def _make_reranker(mock_cross_encoder_cls) -> Reranker:
    """Instantiate Reranker with a mock CrossEncoder class."""
    settings = _make_settings()
    return Reranker(settings)


# ---------------------------------------------------------------------------
# T012.1 — Instantiation
# ---------------------------------------------------------------------------


class TestRerankerInstantiation:
    def test_instantiates_without_error(self):
        """Reranker() must not raise when CrossEncoder is mocked."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_cls.return_value = MagicMock()
            reranker = _make_reranker(mock_cls)
        assert reranker is not None

    def test_model_attribute_set_on_init(self):
        """After init, self.model must be the CrossEncoder instance."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance
            reranker = _make_reranker(mock_cls)
        assert reranker.model is mock_instance

    def test_default_top_k_taken_from_settings(self):
        """default_top_k must match settings.top_k_rerank."""
        with patch("sentence_transformers.CrossEncoder"):
            settings = _make_settings(top_k_rerank=7)
            reranker = Reranker(settings)
        assert reranker.default_top_k == 7


# ---------------------------------------------------------------------------
# T012.2 — rerank() calls underlying model
# ---------------------------------------------------------------------------


class TestRerankerCallsModel:
    def test_rerank_calls_model_rank(self, sample_chunks):
        """rerank() must call model.rank() with query and documents."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_model.rank.return_value = [
                {"corpus_id": 0, "score": 0.9},
                {"corpus_id": 1, "score": 0.7},
                {"corpus_id": 2, "score": 0.5},
            ]
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        reranker.rerank("test query", sample_chunks, top_k=3)

        mock_model.rank.assert_called_once_with(
            "test query",
            [c.text for c in sample_chunks],
            top_k=3,
            return_documents=False,
        )

    def test_rerank_empty_chunks_skips_model(self):
        """rerank() with empty list must return [] without calling model."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        result = reranker.rerank("query", [], top_k=5)

        assert result == []
        mock_model.rank.assert_not_called()


# ---------------------------------------------------------------------------
# T012.3 — Results sorted descending
# ---------------------------------------------------------------------------


class TestRerankerOrdering:
    def test_results_ordered_descending_by_rerank_score(self, sample_chunks):
        """rerank() must return chunks ordered by score descending."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            # Return order: chunk 2 (0.95), chunk 0 (0.80), chunk 1 (0.60)
            mock_model.rank.return_value = [
                {"corpus_id": 2, "score": 0.95},
                {"corpus_id": 0, "score": 0.80},
                {"corpus_id": 1, "score": 0.60},
            ]
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        result = reranker.rerank("query", sample_chunks, top_k=3)

        scores = [c.rerank_score for c in result]
        assert scores == sorted(scores, reverse=True), f"Expected descending scores, got {scores}"

    def test_rerank_score_populated_on_returned_chunks(self, sample_chunks):
        """Every chunk in the result must have a float rerank_score."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_model.rank.return_value = [
                {"corpus_id": 0, "score": 0.88},
                {"corpus_id": 1, "score": 0.55},
            ]
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        result = reranker.rerank("query", sample_chunks, top_k=2)

        for chunk in result:
            assert isinstance(chunk.rerank_score, float)


# ---------------------------------------------------------------------------
# T012.4 — top_k truncation
# ---------------------------------------------------------------------------


class TestRerankerTopK:
    def test_top_k_limits_result_count(self, sample_chunks):
        """rerank() must pass top_k to model.rank() limiting result count."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            # Simulate model returning only top_k items
            mock_model.rank.return_value = [
                {"corpus_id": 0, "score": 0.9},
                {"corpus_id": 1, "score": 0.7},
            ]
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        result = reranker.rerank("query", sample_chunks, top_k=2)

        assert len(result) == 2

    def test_top_k_one_returns_single_result(self, sample_chunks):
        """top_k=1 must return exactly one chunk."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_model.rank.return_value = [
                {"corpus_id": 0, "score": 0.99},
            ]
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        result = reranker.rerank("query", sample_chunks, top_k=1)

        assert len(result) == 1
        assert result[0].rerank_score == pytest.approx(0.99)


# ---------------------------------------------------------------------------
# T012.5 — RerankerError on model failure
# ---------------------------------------------------------------------------


class TestRerankerError:
    def test_reranker_error_raised_when_model_raises(self, sample_chunks):
        """RerankerError must be raised when model.rank() raises any exception."""
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_model.rank.side_effect = RuntimeError("CUDA OOM")
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        with pytest.raises(RerankerError):
            reranker.rerank("query", sample_chunks, top_k=3)

    def test_reranker_error_is_embedinator_error(self):
        """RerankerError must be importable from backend.errors."""
        from backend.errors import EmbeddinatorError

        assert issubclass(RerankerError, EmbeddinatorError)

    def test_original_exception_chained(self, sample_chunks):
        """RerankerError.__cause__ must carry the original exception."""
        original_exc = ValueError("bad tensor shape")
        with patch("sentence_transformers.CrossEncoder") as mock_cls:
            mock_model = MagicMock()
            mock_model.rank.side_effect = original_exc
            mock_cls.return_value = mock_model
            reranker = _make_reranker(mock_cls)

        with pytest.raises(RerankerError) as exc_info:
            reranker.rerank("query", sample_chunks, top_k=3)

        assert exc_info.value.__cause__ is original_exc
