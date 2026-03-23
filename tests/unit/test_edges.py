"""Unit tests for ConversationGraph edge functions.

Covers: route_intent (3 cases), should_clarify (5 cases).
"""
from backend.agent.edges import route_intent, should_clarify
from backend.agent.schemas import QueryAnalysis


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides):
    """Build a minimal ConversationState dict for edge testing."""
    base = {
        "session_id": "test-session",
        "messages": [],
        "query_analysis": None,
        "sub_answers": [],
        "selected_collections": [],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "intent": "rag_query",
        "final_response": None,
        "citations": [],
        "groundedness_result": None,
        "confidence_score": 0,
        "iteration_count": 0,
    }
    base.update(overrides)
    return base


def _make_query_analysis(is_clear: bool = True, clarification_needed: str | None = None) -> QueryAnalysis:
    return QueryAnalysis(
        is_clear=is_clear,
        sub_questions=["test question"],
        clarification_needed=clarification_needed,
        collections_hint=[],
        complexity_tier="lookup",
    )


# ---------------------------------------------------------------------------
# route_intent tests
# ---------------------------------------------------------------------------


def test_route_intent_rag_query():
    state = _make_state(intent="rag_query")
    assert route_intent(state) == "rag_query"


def test_route_intent_collection_mgmt():
    state = _make_state(intent="collection_mgmt")
    assert route_intent(state) == "collection_mgmt"


def test_route_intent_ambiguous():
    state = _make_state(intent="ambiguous")
    assert route_intent(state) == "ambiguous"


# ---------------------------------------------------------------------------
# should_clarify tests
# ---------------------------------------------------------------------------


def test_should_clarify_is_clear_returns_false():
    """Clear query should never trigger clarification regardless of count."""
    state = _make_state(
        query_analysis=_make_query_analysis(is_clear=True),
        iteration_count=0,
    )
    assert should_clarify(state) is False


def test_should_clarify_unclear_count_zero_returns_true():
    """Unclear query with no prior iterations should trigger clarification."""
    state = _make_state(
        query_analysis=_make_query_analysis(
            is_clear=False,
            clarification_needed="What time period are you asking about?",
        ),
        iteration_count=0,
    )
    assert should_clarify(state) is True


def test_should_clarify_unclear_count_one_returns_true():
    """Unclear query with one prior iteration (below cap) should still clarify."""
    state = _make_state(
        query_analysis=_make_query_analysis(
            is_clear=False,
            clarification_needed="Which product do you mean?",
        ),
        iteration_count=1,
    )
    assert should_clarify(state) is True


def test_should_clarify_cap_reached_returns_false():
    """Unclear query at cap (iteration_count=2) must NOT trigger clarification."""
    state = _make_state(
        query_analysis=_make_query_analysis(
            is_clear=False,
            clarification_needed="Please be more specific.",
        ),
        iteration_count=2,
    )
    assert should_clarify(state) is False


def test_should_clarify_none_query_analysis_returns_false():
    """Defensive guard: None query_analysis must return False, not raise."""
    state = _make_state(query_analysis=None, iteration_count=0)
    assert should_clarify(state) is False
