"""Tests for search filter key whitelist (FR-002)."""

from unittest.mock import MagicMock

import pytest
from qdrant_client.models import FieldCondition, MatchValue

from backend.retrieval.searcher import ALLOWED_FILTER_KEYS, HybridSearcher


@pytest.fixture
def searcher():
    """Create HybridSearcher with mock client and settings."""
    mock_client = MagicMock()
    mock_settings = MagicMock()
    mock_settings.hybrid_dense_weight = 0.7
    mock_settings.hybrid_sparse_weight = 0.3
    mock_settings.top_k_retrieval = 20
    mock_settings.circuit_breaker_failure_threshold = 5
    mock_settings.circuit_breaker_cooldown_secs = 30
    return HybridSearcher(mock_client, mock_settings)


class TestFilterKeyWhitelist:
    def test_known_key_passes(self, searcher):
        """Known filter keys are included in the Qdrant filter."""
        result = searcher._build_filter({"doc_type": "Prose"})
        assert result is not None
        assert len(result.must) == 1
        assert result.must[0].key == "doc_type"

    def test_unknown_key_dropped(self, searcher):
        """AC-2: Unknown filter keys are silently ignored."""
        result = searcher._build_filter({"arbitrary_field": "x"})
        assert result is None

    def test_mixed_keys_keep_known_only(self, searcher):
        """Mixed known+unknown filters only keep known keys."""
        result = searcher._build_filter({
            "doc_type": "Prose",
            "evil_field": "hack",
            "source_file": "readme.md",
        })
        assert result is not None
        assert len(result.must) == 2
        keys = {c.key for c in result.must}
        assert keys == {"doc_type", "source_file"}

    def test_all_unknown_returns_none(self, searcher):
        """All-unknown filters return None (unfiltered results)."""
        result = searcher._build_filter({
            "unknown1": "a",
            "unknown2": "b",
        })
        assert result is None

    def test_all_allowed_keys_accepted(self, searcher):
        """All 4 allowed keys pass through."""
        result = searcher._build_filter({
            "doc_type": "Code",
            "source_file": "main.py",
            "page": 1,
            "chunk_index": 0,
        })
        assert result is not None
        assert len(result.must) == 4
