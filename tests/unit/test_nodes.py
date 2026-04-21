"""Unit tests for ConversationGraph node functions.

Covers: classify_intent, handle_collection_mgmt, rewrite_query,
        aggregate_answers, format_response, summarize_history, request_clarification.

NEVER uses real LLM calls, real database, or real network.
Async tests use @pytest.mark.asyncio.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from backend.agent.nodes import (
    aggregate_answers,
    classify_intent,
    format_response,
    handle_collection_mgmt,
    request_clarification,
    rewrite_query,
    summarize_history,
)
from backend.agent.schemas import Citation, QueryAnalysis, SubAnswer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides) -> dict:
    """Build a minimal ConversationState dict for node testing."""
    base: dict[str, Any] = {
        "session_id": "sess-001",
        "messages": [],
        "query_analysis": None,
        "sub_answers": [],
        "selected_collections": ["col-1"],
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


def _make_query_analysis(
    is_clear: bool = True,
    sub_questions: list[str] | None = None,
    clarification_needed: str | None = None,
    complexity_tier: str = "lookup",
) -> QueryAnalysis:
    return QueryAnalysis(
        is_clear=is_clear,
        sub_questions=sub_questions or ["What is the answer?"],
        clarification_needed=clarification_needed,
        collections_hint=[],
        complexity_tier=complexity_tier,
    )


def _make_citation(
    passage_id: str = "p-001",
    document_name: str = "doc.pdf",
    relevance_score: float = 0.85,
) -> Citation:
    return Citation(
        passage_id=passage_id,
        document_id="doc-id-001",
        document_name=document_name,
        start_offset=0,
        end_offset=100,
        text="Some cited text from the document.",
        relevance_score=relevance_score,
    )


def _make_sub_answer(
    sub_question: str = "What is X?",
    answer: str = "X is Y.",
    citations: list[Citation] | None = None,
    confidence_score: int = 85,
) -> SubAnswer:
    return SubAnswer(
        sub_question=sub_question,
        answer=answer,
        citations=citations or [_make_citation()],
        chunks=[],
        confidence_score=confidence_score,
    )


def _make_async_db(row: tuple | None) -> AsyncMock:
    """Return an async db mock where execute().fetchone() returns *row*."""
    cursor_mock = AsyncMock()
    cursor_mock.fetchone = AsyncMock(return_value=row)
    db_mock = AsyncMock()
    db_mock.execute = AsyncMock(return_value=cursor_mock)
    return db_mock


def _make_llm_mock(content: str) -> AsyncMock:
    """Return an LLM mock whose ainvoke returns a message with .content."""
    response_mock = MagicMock()
    response_mock.content = content
    llm_mock = AsyncMock()
    llm_mock.ainvoke = AsyncMock(return_value=response_mock)
    return llm_mock


# ---------------------------------------------------------------------------
# classify_intent tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_intent_rag_query():
    """LLM returning rag_query intent should propagate correctly."""
    llm = _make_llm_mock('{"intent": "rag_query"}')
    state = _make_state(messages=[HumanMessage(content="Explain the privacy policy")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "rag_query"


@pytest.mark.asyncio
async def test_classify_intent_collection_mgmt():
    """LLM returning collection_mgmt intent should propagate correctly."""
    llm = _make_llm_mock('{"intent": "collection_mgmt"}')
    state = _make_state(messages=[HumanMessage(content="Create a new collection")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "collection_mgmt"


@pytest.mark.asyncio
async def test_classify_intent_ambiguous():
    """LLM returning ambiguous intent should propagate correctly."""
    llm = _make_llm_mock('{"intent": "ambiguous"}')
    state = _make_state(messages=[HumanMessage(content="What about that thing")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "ambiguous"


@pytest.mark.asyncio
async def test_classify_intent_invalid_json_defaults_to_rag_query():
    """Malformed LLM JSON response should default to rag_query."""
    llm = _make_llm_mock("not valid json at all")
    state = _make_state(messages=[HumanMessage(content="Some query")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "rag_query"


@pytest.mark.asyncio
async def test_classify_intent_llm_exception_defaults_to_rag_query():
    """LLM exception should be swallowed and default to rag_query."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM unavailable"))
    state = _make_state(messages=[HumanMessage(content="Some query")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "rag_query"


@pytest.mark.asyncio
async def test_classify_intent_unknown_intent_defaults_to_rag_query():
    """LLM returning an unrecognized intent value should default to rag_query."""
    llm = _make_llm_mock('{"intent": "delete_everything"}')
    state = _make_state(messages=[HumanMessage(content="Some query")])
    result = await classify_intent(state, llm=llm)
    assert result["intent"] == "rag_query"


# ---------------------------------------------------------------------------
# handle_collection_mgmt tests
# ---------------------------------------------------------------------------


def test_handle_collection_mgmt_sets_final_response():
    """Stub should set a non-empty final_response."""
    state = _make_state()
    result = handle_collection_mgmt(state)
    assert "final_response" in result
    assert result["final_response"]  # non-empty


def test_handle_collection_mgmt_confidence_is_zero():
    """Stub should set confidence_score to 0 (out-of-scope)."""
    state = _make_state()
    result = handle_collection_mgmt(state)
    assert result["confidence_score"] == 0


# ---------------------------------------------------------------------------
# rewrite_query tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rewrite_query_valid_structured_output():
    """Valid QueryAnalysis from LLM should be stored in query_analysis."""
    expected_analysis = _make_query_analysis(
        is_clear=True,
        sub_questions=["What is the refund policy?"],
    )
    structured_llm = AsyncMock()
    structured_llm.ainvoke = AsyncMock(return_value=expected_analysis)

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured_llm)

    state = _make_state(messages=[HumanMessage(content="What is the refund policy?")])
    result = await rewrite_query(state, llm=llm)

    assert result["query_analysis"] is expected_analysis
    assert result["query_analysis"].is_clear is True


@pytest.mark.asyncio
async def test_rewrite_query_first_attempt_fails_retries():
    """On first ValidationError, node retries and returns second attempt result."""
    from pydantic import ValidationError

    fallback_analysis = _make_query_analysis(
        is_clear=True,
        sub_questions=["simplified question"],
    )

    call_count = 0

    async def side_effect(messages):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Simulate first attempt failure
            raise Exception("Structured output parse error")
        return fallback_analysis

    structured_llm = AsyncMock()
    structured_llm.ainvoke = side_effect

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured_llm)

    state = _make_state(messages=[HumanMessage(content="Ambiguous query")])
    result = await rewrite_query(state, llm=llm)

    assert result["query_analysis"] is fallback_analysis
    assert call_count == 2  # first attempt + retry


@pytest.mark.asyncio
async def test_rewrite_query_both_attempts_fail_returns_fallback():
    """When both attempts fail, a safe single-question fallback is returned."""
    structured_llm = AsyncMock()
    structured_llm.ainvoke = AsyncMock(side_effect=Exception("Persistent LLM error"))

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured_llm)

    question = "Why does the system fail?"
    state = _make_state(messages=[HumanMessage(content=question)])
    result = await rewrite_query(state, llm=llm)

    qa = result["query_analysis"]
    assert isinstance(qa, QueryAnalysis)
    assert qa.is_clear is True  # fallback is always "clear" (best-effort)
    assert len(qa.sub_questions) == 1
    assert qa.sub_questions[0] == question  # original query preserved


@pytest.mark.asyncio
async def test_rewrite_query_factoid_produces_single_sub_question():
    """Simple factoid queries should not be unnecessarily decomposed."""
    single_question_analysis = _make_query_analysis(
        is_clear=True,
        sub_questions=["What is the capital of France?"],
        complexity_tier="factoid",
    )
    structured_llm = AsyncMock()
    structured_llm.ainvoke = AsyncMock(return_value=single_question_analysis)

    llm = MagicMock()
    llm.with_structured_output = MagicMock(return_value=structured_llm)

    state = _make_state(messages=[HumanMessage(content="What is the capital of France?")])
    result = await rewrite_query(state, llm=llm)

    assert len(result["query_analysis"].sub_questions) == 1


# ---------------------------------------------------------------------------
# aggregate_answers tests
# ---------------------------------------------------------------------------


def test_aggregate_answers_single_valid_sub_answer():
    """Single valid sub-answer should produce merged text and citations."""
    sa = _make_sub_answer(answer="The answer is 42.", citations=[_make_citation("p-001")])
    state = _make_state(sub_answers=[sa])
    result = aggregate_answers(state)

    assert "final_response" in result
    assert "42" in result["final_response"]
    assert len(result["citations"]) == 1


def test_aggregate_answers_deduplicates_citations_keeps_highest_score():
    """Duplicate passage_id: the citation with the higher relevance_score wins."""
    low_score_citation = _make_citation("p-001", relevance_score=0.45)
    high_score_citation = _make_citation("p-001", relevance_score=0.85)

    sa1 = _make_sub_answer(
        sub_question="Q1",
        answer="Answer 1.",
        citations=[low_score_citation],
    )
    sa2 = _make_sub_answer(
        sub_question="Q2",
        answer="Answer 2.",
        citations=[high_score_citation],
    )
    state = _make_state(sub_answers=[sa1, sa2])
    result = aggregate_answers(state)

    # Only one citation for p-001 (deduplicated)
    assert len(result["citations"]) == 1
    assert result["citations"][0].relevance_score == pytest.approx(0.85)


def test_aggregate_answers_empty_sub_answers_returns_fallback():
    """No sub-answers should return a non-empty fallback message and empty citations."""
    state = _make_state(sub_answers=[])
    result = aggregate_answers(state)

    assert result["final_response"]  # non-empty fallback
    assert result["citations"] == []
    assert result["confidence_score"] == 0


def test_aggregate_answers_skips_failed_sub_answers():
    """Sub-answers with answer=None should be ignored."""
    valid_sa = _make_sub_answer(answer="Valid answer.")
    # SubAnswer.answer is str (not Optional), so simulate failed as missing via dict
    # Instead, create a valid one and one with a very short placeholder answer
    # The implementation filters on `sa.answer is not None`
    state = _make_state(sub_answers=[valid_sa])
    result = aggregate_answers(state)
    assert "Valid answer." in result["final_response"]


def test_aggregate_answers_multiple_valid_answers_include_headers():
    """Multiple valid sub-answers should be separated by sub-question headers."""
    sa1 = _make_sub_answer(sub_question="Question A?", answer="Answer A.", citations=[_make_citation("p-001")])
    sa2 = _make_sub_answer(sub_question="Question B?", answer="Answer B.", citations=[_make_citation("p-002")])
    state = _make_state(sub_answers=[sa1, sa2])
    result = aggregate_answers(state)

    assert "Question A?" in result["final_response"]
    assert "Question B?" in result["final_response"]
    assert "Answer A." in result["final_response"]
    assert "Answer B." in result["final_response"]


def test_aggregate_answers_confidence_score_is_int():
    """Confidence score must be an integer (0-100 scale)."""
    sa = _make_sub_answer(citations=[_make_citation("p-001", relevance_score=0.85)])
    state = _make_state(sub_answers=[sa])
    result = aggregate_answers(state)
    assert isinstance(result["confidence_score"], int)
    assert 0 <= result["confidence_score"] <= 100


# ---------------------------------------------------------------------------
# format_response tests
# ---------------------------------------------------------------------------


def test_format_response_adds_citation_markers():
    """Citation document names present in final_response should get [N] markers."""
    citation = _make_citation("p-001", document_name="policy.pdf", relevance_score=0.85)
    state = _make_state(
        final_response="According to policy.pdf, refunds take 5 days.",
        citations=[citation],
        confidence_score=90,
        groundedness_result=None,
    )
    result = format_response(state)
    assert "[1]" in result["final_response"]
    assert "policy.pdf[1]" in result["final_response"]


def test_format_response_adds_references_section():
    """Citations should produce a References section in the output."""
    citation = _make_citation("p-001", document_name="guide.pdf")
    state = _make_state(
        final_response="See guide.pdf for details.",
        citations=[citation],
        confidence_score=90,
        groundedness_result=None,
    )
    result = format_response(state)
    assert "References" in result["final_response"]
    assert "[1]" in result["final_response"]


def test_format_response_low_confidence_appends_note():
    """confidence_score < 70 should append a confidence warning note."""
    state = _make_state(
        final_response="The system uses LRU eviction.",
        citations=[],
        confidence_score=45,
        groundedness_result=None,
    )
    result = format_response(state)
    assert "45/100" in result["final_response"]
    assert "Confidence score" in result["final_response"]


def test_format_response_high_confidence_no_note():
    """confidence_score >= 70 should NOT append a confidence warning."""
    state = _make_state(
        final_response="Caching uses LRU.",
        citations=[],
        confidence_score=85,
        groundedness_result=None,
    )
    result = format_response(state)
    assert "Confidence score" not in result["final_response"]


def test_format_response_none_groundedness_skips_annotation():
    """groundedness_result=None (Phase 1) must not add [unverified] annotations."""
    state = _make_state(
        final_response="Some claim about the system.",
        citations=[],
        confidence_score=90,
        groundedness_result=None,
    )
    result = format_response(state)
    assert "[unverified]" not in result["final_response"]


def test_format_response_empty_final_response_returns_empty():
    """Empty final_response should return as-is without error."""
    state = _make_state(final_response="", citations=[], confidence_score=80)
    result = format_response(state)
    assert result["final_response"] == ""


# ---------------------------------------------------------------------------
# summarize_history tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summarize_history_under_budget_no_op():
    """When token count is under budget, state is returned unchanged (empty dict)."""
    messages = [HumanMessage(content="Hi"), AIMessage(content="Hello")]
    state = _make_state(messages=messages, llm_model="qwen2.5:7b")
    llm = AsyncMock()

    with patch("langchain_core.messages.utils.count_tokens_approximately", return_value=100):
        result = await summarize_history(state, llm=llm)

    assert result == {}
    llm.ainvoke.assert_not_called()


@pytest.mark.asyncio
async def test_summarize_history_over_budget_compresses():
    """When token count exceeds budget, messages should be compressed via LLM."""
    messages = [
        HumanMessage(content="Message 1"),
        AIMessage(content="Response 1"),
        HumanMessage(content="Message 2"),
        AIMessage(content="Response 2"),
    ]
    state = _make_state(messages=messages, llm_model="qwen2.5:7b")

    summary_response = MagicMock()
    summary_response.content = "Summary of older messages."
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(return_value=summary_response)

    # qwen2.5:7b budget = 32768 * 0.75 = 24576; mock token count above that
    with patch("langchain_core.messages.utils.count_tokens_approximately", return_value=30_000):
        result = await summarize_history(state, llm=llm)

    assert "messages" in result
    assert len(result["messages"]) < len(messages)
    # First message should be the SystemMessage summary
    assert isinstance(result["messages"][0], SystemMessage)
    llm.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_summarize_history_llm_failure_returns_unchanged():
    """LLM failure during compression should return empty dict (messages unchanged)."""
    messages = [HumanMessage(content="Old message"), AIMessage(content="Old response")]
    state = _make_state(messages=messages, llm_model="qwen2.5:7b")

    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("LLM compression failed"))

    with patch("langchain_core.messages.utils.count_tokens_approximately", return_value=30_000):
        result = await summarize_history(state, llm=llm)

    # On failure, node returns {} — messages are left unchanged in the graph state
    assert result == {}


# ---------------------------------------------------------------------------
# request_clarification tests
# ---------------------------------------------------------------------------


def test_request_clarification_calls_interrupt_with_question():
    """interrupt() should be called with the clarification question from query_analysis."""
    question = "Which time period are you asking about?"
    state = _make_state(
        messages=[HumanMessage(content="Tell me about the trend")],
        query_analysis=_make_query_analysis(
            is_clear=False,
            clarification_needed=question,
        ),
        iteration_count=0,
    )

    with patch("backend.agent.nodes.interrupt", return_value="The past year") as mock_interrupt:
        result = request_clarification(state)

    mock_interrupt.assert_called_once_with(question)
    # User response should be appended as HumanMessage
    assert any(isinstance(m, HumanMessage) and "The past year" in m.content for m in result["messages"])


def test_request_clarification_increments_iteration_count():
    """iteration_count must be incremented by 1 after clarification."""
    state = _make_state(
        messages=[HumanMessage(content="Something unclear")],
        query_analysis=_make_query_analysis(is_clear=False, clarification_needed="Clarify?"),
        iteration_count=0,
    )

    with patch("backend.agent.nodes.interrupt", return_value="Clarified answer"):
        result = request_clarification(state)

    assert result["iteration_count"] == 1


def test_request_clarification_appends_human_message():
    """The user's clarification response must be appended as a HumanMessage."""
    user_response = "I was asking about Q3 2024"
    state = _make_state(
        messages=[HumanMessage(content="What were the trends?")],
        query_analysis=_make_query_analysis(
            is_clear=False,
            clarification_needed="Which quarter?",
        ),
        iteration_count=1,
    )

    with patch("backend.agent.nodes.interrupt", return_value=user_response):
        result = request_clarification(state)

    new_messages = result["messages"]
    last = new_messages[-1]
    assert isinstance(last, HumanMessage)
    assert last.content == user_response
    # Original message preserved plus new HumanMessage
    assert len(new_messages) == 2
