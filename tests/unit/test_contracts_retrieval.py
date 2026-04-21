"""
Contract tests for retrieval layer — T035-T038 (spec-11, US3, FR-010, FR-011).

These tests enforce interface contracts for HybridSearcher, Reranker, and
ScoreNormalizer using introspection. No external services are contacted.
"""

import inspect

from backend.retrieval.searcher import HybridSearcher
from backend.retrieval.reranker import Reranker
from backend.retrieval.score_normalizer import normalize_scores


# ---------------------------------------------------------------------------
# T036 — HybridSearcher tests (FR-010)
# ---------------------------------------------------------------------------


class TestHybridSearcherContract:
    """Verify HybridSearcher constructor, method names, and circuit breaker."""

    def test_constructor_params_are_client_and_settings(self):
        """HybridSearcher.__init__ must take (self, client, settings) only."""
        sig = inspect.signature(HybridSearcher.__init__)
        params = list(sig.parameters.keys())
        assert params == ["self", "client", "settings"], (
            f"HybridSearcher.__init__ params mismatch.\nExpected: ['self', 'client', 'settings']\nGot:      {params}"
        )

    def test_constructor_does_not_take_storage(self):
        """Constructor must NOT accept 'storage' param (old interface)."""
        sig = inspect.signature(HybridSearcher.__init__)
        assert "storage" not in sig.parameters

    def test_constructor_does_not_take_embedder(self):
        """Constructor must NOT accept 'embedder' param (old interface)."""
        sig = inspect.signature(HybridSearcher.__init__)
        assert "embedder" not in sig.parameters

    def test_constructor_does_not_take_reranker(self):
        """Constructor must NOT accept 'reranker' param (old interface)."""
        sig = inspect.signature(HybridSearcher.__init__)
        assert "reranker" not in sig.parameters

    def test_search_method_exists(self):
        assert hasattr(HybridSearcher, "search")
        assert callable(getattr(HybridSearcher, "search"))

    def test_search_has_embed_fn_param(self):
        """search() must accept embed_fn so callers inject the embedding function."""
        sig = inspect.signature(HybridSearcher.search)
        assert "embed_fn" in sig.parameters, "HybridSearcher.search must have an 'embed_fn' parameter"

    def test_search_all_collections_exists_not_search_multi_collection(self):
        """Correct method is search_all_collections, NOT search_multi_collection."""
        assert hasattr(HybridSearcher, "search_all_collections"), "search_all_collections must exist"
        assert not hasattr(HybridSearcher, "search_multi_collection"), (
            "search_multi_collection must NOT exist (use search_all_collections)"
        )

    # --- Circuit breaker methods ---

    def test_check_circuit_exists(self):
        """Circuit breaker check method must exist (C1 pattern)."""
        assert hasattr(HybridSearcher, "_check_circuit")
        assert callable(getattr(HybridSearcher, "_check_circuit"))

    def test_record_success_exists(self):
        """Circuit breaker success recorder must exist."""
        assert hasattr(HybridSearcher, "_record_success")
        assert callable(getattr(HybridSearcher, "_record_success"))

    def test_record_failure_exists(self):
        """Circuit breaker failure recorder must exist."""
        assert hasattr(HybridSearcher, "_record_failure")
        assert callable(getattr(HybridSearcher, "_record_failure"))


# ---------------------------------------------------------------------------
# T037 — Reranker tests (FR-011)
# ---------------------------------------------------------------------------


class TestRerankerContract:
    """Verify Reranker constructor and rerank method contract."""

    def test_constructor_params_are_settings_only(self):
        """Reranker.__init__ must take (self, settings), not model_name: str."""
        sig = inspect.signature(Reranker.__init__)
        params = list(sig.parameters.keys())
        assert params == ["self", "settings"], (
            f"Reranker.__init__ params mismatch.\nExpected: ['self', 'settings']\nGot:      {params}"
        )

    def test_constructor_does_not_take_model_name(self):
        """Constructor must NOT accept 'model_name' param (wrong interface)."""
        sig = inspect.signature(Reranker.__init__)
        assert "model_name" not in sig.parameters, "Reranker.__init__ must NOT have 'model_name' param — use settings"

    def test_rerank_method_exists(self):
        assert hasattr(Reranker, "rerank")
        assert callable(getattr(Reranker, "rerank"))

    def test_rerank_params(self):
        """rerank() must have exactly (self, query, chunks, top_k)."""
        sig = inspect.signature(Reranker.rerank)
        params = list(sig.parameters.keys())
        assert params == ["self", "query", "chunks", "top_k"], (
            f"Reranker.rerank params mismatch.\nExpected: ['self', 'query', 'chunks', 'top_k']\nGot:      {params}"
        )

    def test_rerank_has_query_param(self):
        sig = inspect.signature(Reranker.rerank)
        assert "query" in sig.parameters

    def test_rerank_has_chunks_param(self):
        sig = inspect.signature(Reranker.rerank)
        assert "chunks" in sig.parameters

    def test_rerank_has_top_k_param(self):
        sig = inspect.signature(Reranker.rerank)
        assert "top_k" in sig.parameters

    def test_score_pair_does_not_exist(self):
        """score_pair must NOT exist — reranking uses model.rank() internally."""
        assert not hasattr(Reranker, "score_pair"), "score_pair must NOT exist on Reranker — use rerank()"


# ---------------------------------------------------------------------------
# T038 — ScoreNormalizer test
# ---------------------------------------------------------------------------


class TestScoreNormalizerContract:
    """Verify normalize_scores is a module-level function, not a class method."""

    def test_normalize_scores_is_callable(self):
        """normalize_scores must be directly importable and callable."""
        assert callable(normalize_scores)

    def test_normalize_scores_is_function_not_class(self):
        """normalize_scores must be a function, not a class or method descriptor."""
        assert inspect.isfunction(normalize_scores), (
            "normalize_scores must be a plain module-level function, not a class"
        )

    def test_normalize_scores_is_module_level(self):
        """normalize_scores must live at module scope, not inside a class."""
        import backend.retrieval.score_normalizer as mod

        assert hasattr(mod, "normalize_scores"), "normalize_scores must be accessible directly from the module"
        # Confirm it is not a class
        assert not isinstance(mod.normalize_scores, type)
