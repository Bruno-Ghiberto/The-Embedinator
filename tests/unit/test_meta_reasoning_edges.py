"""Unit tests for MetaReasoningGraph edge functions."""
from backend.agent.meta_reasoning_edges import route_after_strategy


def _make_meta_state(**overrides):
    base = {
        "sub_question": "test question",
        "retrieved_chunks": [],
        "alternative_queries": [],
        "mean_relevance_score": 0.0,
        "chunk_relevance_scores": [],
        "meta_attempt_count": 0,
        "recovery_strategy": None,
        "modified_state": None,
        "answer": None,
        "uncertainty_reason": None,
        "attempted_strategies": set(),
    }
    base.update(overrides)
    return base


class TestRouteAfterStrategy:
    """Tests for route_after_strategy edge function."""

    def test_retry_when_strategy_set(self):
        """Returns 'retry' when recovery_strategy is set."""
        state = _make_meta_state(recovery_strategy="WIDEN_SEARCH")
        assert route_after_strategy(state) == "retry"

    def test_report_when_strategy_none(self):
        """Returns 'report' when recovery_strategy is None."""
        state = _make_meta_state(recovery_strategy=None)
        assert route_after_strategy(state) == "report"

    def test_report_when_strategy_missing(self):
        """Returns 'report' when recovery_strategy key is absent."""
        state = {"sub_question": "test"}
        assert route_after_strategy(state) == "report"

    def test_report_when_strategy_empty_string(self):
        """Returns 'report' when recovery_strategy is empty string (falsy)."""
        state = _make_meta_state(recovery_strategy="")
        assert route_after_strategy(state) == "report"

    def test_retry_with_each_strategy_name(self):
        """Returns 'retry' for all valid strategy names."""
        for strategy in ["WIDEN_SEARCH", "CHANGE_COLLECTION", "RELAX_FILTERS"]:
            state = _make_meta_state(recovery_strategy=strategy)
            assert route_after_strategy(state) == "retry"
