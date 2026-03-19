"""Unit tests for ResearchGraph edge functions."""
import pytest

from backend.agent.research_edges import route_after_compress_check, should_continue_loop


def _make_state(**overrides):
    """Build a minimal ResearchState dict for testing."""
    base = {
        "sub_question": "test question",
        "session_id": "test-session",
        "selected_collections": ["col1"],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "retrieved_chunks": [],
        "retrieval_keys": set(),
        "tool_call_count": 0,
        "iteration_count": 0,
        "confidence_score": 0.0,
        "answer": None,
        "citations": [],
        "context_compressed": False,
        "messages": [],
        "_no_new_tools": False,
        "_needs_compression": False,
    }
    base.update(overrides)
    return base


class TestShouldContinueLoop:
    """Tests for should_continue_loop edge function."""

    def test_continue_when_low_confidence_and_budget_remaining(self):
        state = _make_state(confidence_score=0.3, iteration_count=2, tool_call_count=3)
        assert should_continue_loop(state) == "continue"

    def test_sufficient_when_confidence_meets_threshold(self):
        """F1: confidence >= 0.6 (threshold 60/100) -> sufficient"""
        state = _make_state(confidence_score=0.6)
        assert should_continue_loop(state) == "sufficient"

    def test_sufficient_when_confidence_exceeds_threshold(self):
        state = _make_state(confidence_score=0.95)
        assert should_continue_loop(state) == "sufficient"

    def test_exhausted_when_max_iterations_reached(self):
        state = _make_state(confidence_score=0.3, iteration_count=10)
        assert should_continue_loop(state) == "exhausted"

    def test_exhausted_when_max_tool_calls_reached(self):
        state = _make_state(confidence_score=0.3, tool_call_count=8)
        assert should_continue_loop(state) == "exhausted"

    def test_exhausted_when_no_new_tools(self):
        """F4: tool exhaustion flag"""
        state = _make_state(confidence_score=0.3, _no_new_tools=True)
        assert should_continue_loop(state) == "exhausted"

    def test_confidence_checked_first_then_budget(self):
        """F1: Even if budget is exhausted, confidence >= threshold -> sufficient"""
        state = _make_state(
            confidence_score=0.7,
            iteration_count=10,
            tool_call_count=8,
        )
        assert should_continue_loop(state) == "sufficient"

    def test_confidence_exactly_at_threshold(self):
        """Boundary: confidence == 0.6 exactly"""
        state = _make_state(confidence_score=0.6)
        assert should_continue_loop(state) == "sufficient"

    def test_confidence_just_below_threshold(self):
        """Boundary: confidence just below threshold"""
        state = _make_state(confidence_score=0.59)
        assert should_continue_loop(state) == "continue"

    def test_iteration_at_limit_minus_one(self):
        """Boundary: iteration_count == 9 (limit is 10) -> continue"""
        state = _make_state(confidence_score=0.3, iteration_count=9)
        assert should_continue_loop(state) == "continue"

    def test_tool_calls_at_limit_minus_one(self):
        """Boundary: tool_call_count == 7 (limit is 8) -> continue"""
        state = _make_state(confidence_score=0.3, tool_call_count=7)
        assert should_continue_loop(state) == "continue"

    def test_no_new_tools_defaults_false(self):
        """_no_new_tools not in state -> defaults to False via .get()"""
        state = _make_state(confidence_score=0.3)
        del state["_no_new_tools"]
        assert should_continue_loop(state) == "continue"


class TestRouteAfterCompressCheck:
    """Tests for route_after_compress_check edge function."""

    def test_compress_when_flag_set(self):
        state = _make_state(_needs_compression=True)
        assert route_after_compress_check(state) == "compress"

    def test_continue_when_flag_not_set(self):
        state = _make_state(_needs_compression=False)
        assert route_after_compress_check(state) == "continue"

    def test_continue_when_flag_missing(self):
        """_needs_compression not in state -> defaults to False"""
        state = _make_state()
        del state["_needs_compression"]
        assert route_after_compress_check(state) == "continue"
