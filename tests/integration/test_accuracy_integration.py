"""Integration tests for Spec 05: Accuracy, Precision & Robustness.

End-to-end flows: GAV, citation alignment, tier params routing, circuit breaker.
Uses unique_name() helper to avoid Qdrant collection 409 conflicts across runs.
"""

import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.messages import HumanMessage

from tests.integration.conftest import unique_name
from backend.agent.nodes import (
    verify_groundedness,
    validate_citations,
    rewrite_query,
    TIER_PARAMS,
)
from backend.agent.schemas import (
    ClaimVerification,
    GroundednessResult,
    QueryAnalysis,
    SubAnswer,
    Citation,
    RetrievedChunk,
)
from backend.errors import CircuitOpenError
from backend.storage.qdrant_client import QdrantClientWrapper


# ---------------------------------------------------------------------------
# Module-level fixture: reset inference circuit breaker between tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_inference_cb():
    """Reset module-level inference circuit breaker state before/after each test."""
    import backend.agent.nodes as nodes_module

    nodes_module._inf_circuit_open = False
    nodes_module._inf_failure_count = 0
    nodes_module._inf_last_failure_time = None
    nodes_module._inf_max_failures = 5
    yield
    nodes_module._inf_circuit_open = False
    nodes_module._inf_failure_count = 0
    nodes_module._inf_last_failure_time = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(chunk_id="c1", text="Integration test evidence.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        source_file="test.md",
        breadcrumb="sec1",
        parent_id="p1",
        collection=unique_name("IntCol"),
        dense_score=0.8,
        sparse_score=0.3,
        rerank_score=0.9,
    )


def _make_citation(passage_id="c1", text="Integration evidence.") -> Citation:
    return Citation(
        passage_id=passage_id,
        document_id="doc1",
        document_name="test.md",
        start_offset=0,
        end_offset=len(text),
        text=text,
        relevance_score=0.9,
    )


def _make_sub_answer(chunks=None, confidence_score=75) -> SubAnswer:
    if chunks is None:
        chunks = [_make_chunk()]
    return SubAnswer(
        sub_question="What is the mechanism?",
        answer="The mechanism is X.",
        citations=[],
        chunks=chunks,
        confidence_score=confidence_score,
    )


def _make_state(**overrides):
    base = {
        "session_id": "integration-test-session-001",
        "messages": [],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "selected_collections": ["docs"],
        "query_analysis": None,
        "retrieval_params": {},
        "sub_answers": [_make_sub_answer()],
        "final_response": "The mechanism is X because of Y and Z.",
        "citations": [],
        "groundedness_result": None,
        "confidence_score": 75,
    }
    base.update(overrides)
    return base


def _make_mock_llm(return_value):
    """Return a mock LLM whose with_structured_output().ainvoke() returns return_value."""
    mock_llm = MagicMock()
    mock_structured = AsyncMock()
    mock_llm.with_structured_output.return_value = mock_structured
    mock_structured.ainvoke.return_value = return_value
    return mock_llm, mock_structured


# ---------------------------------------------------------------------------
# IT-01: End-to-End GAV Flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestGAVIntegration:
    """IT-01: Full verify_groundedness flow: LLM call → annotations → adjusted confidence."""

    async def test_full_gav_flow_all_supported(self):
        """All claims supported: no [unverified], no warning, full confidence kept."""
        gr = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="The mechanism is X",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="Found in source.",
                ),
                ClaimVerification(
                    claim="because of Y and Z",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="Confirmed.",
                ),
            ],
            overall_grounded=True,
            confidence_adjustment=1.0,
        )
        mock_llm, _ = _make_mock_llm(gr)
        state = _make_state(
            final_response="The mechanism is X because of Y and Z.",
            sub_answers=[_make_sub_answer(confidence_score=80)],
        )

        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is gr
        assert result["confidence_score"] == 80  # int(80 * 1.0)
        assert "[unverified]" not in result["final_response"]
        assert "Warning" not in result["final_response"]
        assert "[Removed:" not in result["final_response"]

    async def test_full_gav_flow_unsupported_claims_annotated(self):
        """T035: one supported, one unsupported, one contradicted — verify annotations."""
        gr = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="Claim A is true",
                    verdict="supported",
                    evidence_chunk_id="c1",
                    explanation="Found",
                ),
                ClaimVerification(
                    claim="Claim B is also true",
                    verdict="unsupported",
                    evidence_chunk_id=None,
                    explanation="Missing",
                ),
                ClaimVerification(
                    claim="Claim C is correct",
                    verdict="contradicted",
                    evidence_chunk_id="c2",
                    explanation="Contradicts source",
                ),
            ],
            overall_grounded=False,  # only 1/3 supported < 50%
            confidence_adjustment=0.33,
        )
        mock_llm, _ = _make_mock_llm(gr)

        chunk_c1 = _make_chunk(chunk_id="c1", text="Evidence for Claim A")
        chunk_c2 = _make_chunk(chunk_id="c2", text="Contradicts Claim C")
        state = _make_state(
            final_response="Claim A is true. Claim B is also true. Claim C is correct.",
            sub_answers=[_make_sub_answer(chunks=[chunk_c1, chunk_c2], confidence_score=80)],
        )

        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is gr
        # Unsupported claim annotated
        assert "Claim B is also true [unverified]" in result["final_response"]
        # Contradicted claim text replaced with [Removed:...] marker
        assert "Claim C is correct" not in result["final_response"]
        assert "[Removed:" in result["final_response"]
        assert "Contradicts source" in result["final_response"]
        # Warning banner prepended (not overall_grounded)
        assert result["final_response"].startswith("**Warning:")
        # GAV-adjusted confidence: int(80 * 0.33) = 26
        assert result["confidence_score"] == 26
        # Groundedness counts accessible via result
        verds = {v.verdict for v in result["groundedness_result"].verifications}
        assert "supported" in verds
        assert "unsupported" in verds
        assert "contradicted" in verds

    async def test_full_gav_flow_contradicted_claims_removed(self):
        """Contradicted claims are replaced with [Removed:...] marker in response."""
        gr = GroundednessResult(
            verifications=[
                ClaimVerification(
                    claim="X causes Y",
                    verdict="contradicted",
                    evidence_chunk_id="c1",
                    explanation="Source says X does not cause Y",
                ),
            ],
            overall_grounded=False,
            confidence_adjustment=0.0,
        )
        mock_llm, _ = _make_mock_llm(gr)
        state = _make_state(
            final_response="X causes Y in most cases.",
            sub_answers=[_make_sub_answer(confidence_score=60)],
        )

        result = await verify_groundedness(state, llm=mock_llm)

        assert "X causes Y" not in result["final_response"]
        assert "[Removed:" in result["final_response"]
        assert "contradicted by the source material" in result["final_response"]
        assert result["confidence_score"] == 0  # int(60 * 0.0)

    async def test_gav_disabled_skips_llm_call(self, monkeypatch):
        """When groundedness_check_enabled=False, LLM is never called."""
        monkeypatch.setattr("backend.agent.nodes.settings.groundedness_check_enabled", False)
        mock_llm = MagicMock()
        state = _make_state()

        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is None
        mock_llm.with_structured_output.assert_not_called()

    async def test_gav_degradation_on_llm_failure(self):
        """When LLM call raises, verify_groundedness degrades gracefully (FR-005)."""
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.side_effect = RuntimeError("LLM unavailable")
        state = _make_state()

        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is None
        # No exception propagated — graceful degradation


# ---------------------------------------------------------------------------
# IT-02: End-to-End Citation Alignment Flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestCitationAlignmentIntegration:
    """IT-02: Full validate_citations flow: score → remap/strip decisions."""

    async def test_citation_kept_above_threshold(self):
        """Citation with score above threshold (0.3) is kept unchanged."""
        mock_reranker = MagicMock()
        mock_reranker.model.rank.return_value = [{"corpus_id": 0, "score": 0.9}]

        chunk = _make_chunk(chunk_id="c1", text="High-relevance evidence.")
        citation = _make_citation(passage_id="c1", text="High-relevance evidence.")
        state = _make_state(
            final_response="High-relevance evidence supports this claim [1].",
            sub_answers=[_make_sub_answer(chunks=[chunk])],
            citations=[citation],
        )

        result = await validate_citations(state, reranker=mock_reranker)

        assert len(result["citations"]) == 1
        assert result["citations"][0].passage_id == "c1"

    async def test_citation_remapped_to_better_chunk(self):
        """Citation below threshold is remapped to the best-scoring alternative chunk."""
        mock_reranker = MagicMock()
        # First call: original citation scores below threshold (0.3)
        # Second call: scores for all chunks — chunk_c2 (index 1) is best
        mock_reranker.model.rank.side_effect = [
            [{"corpus_id": 0, "score": 0.1}],  # original citation
            [{"corpus_id": 0, "score": 0.1}, {"corpus_id": 1, "score": 0.95}],  # all chunks
        ]

        chunk_c1 = _make_chunk(chunk_id="c1", text="Irrelevant content.")
        chunk_c2 = _make_chunk(chunk_id="c2", text="Highly relevant evidence for the claim.")
        citation = _make_citation(passage_id="c1", text="Irrelevant content.")
        state = _make_state(
            final_response="This claim is supported [1].",
            sub_answers=[_make_sub_answer(chunks=[chunk_c1, chunk_c2])],
            citations=[citation],
        )

        result = await validate_citations(state, reranker=mock_reranker)

        assert len(result["citations"]) == 1
        # Citation remapped to the better chunk (c2)
        assert result["citations"][0].passage_id == "c2"
        assert result["citations"][0].relevance_score == 0.95

    async def test_citation_stripped_no_valid_chunk(self):
        """Citation below threshold with no valid alternative is stripped entirely."""
        mock_reranker = MagicMock()
        # Both original and all-chunk scores below threshold (0.3)
        mock_reranker.model.rank.side_effect = [
            [{"corpus_id": 0, "score": 0.1}],  # original citation
            [{"corpus_id": 0, "score": 0.1}, {"corpus_id": 1, "score": 0.15}],  # all chunks
        ]

        chunk_c1 = _make_chunk(chunk_id="c1", text="Barely relevant content.")
        chunk_c2 = _make_chunk(chunk_id="c2", text="Also barely relevant.")
        citation = _make_citation(passage_id="c1", text="Barely relevant content.")
        state = _make_state(
            final_response="This claim has low-quality evidence [1].",
            sub_answers=[_make_sub_answer(chunks=[chunk_c1, chunk_c2])],
            citations=[citation],
        )

        result = await validate_citations(state, reranker=mock_reranker)

        assert len(result["citations"]) == 0  # stripped

    async def test_citation_passthrough_on_reranker_failure(self):
        """When reranker raises, original citations are returned unchanged (FR-008)."""
        mock_reranker = MagicMock()
        mock_reranker.model.rank.side_effect = RuntimeError("Reranker unavailable")

        citation = _make_citation(passage_id="c1", text="Some evidence.")
        chunk = _make_chunk(chunk_id="c1", text="Some evidence.")
        state = _make_state(
            final_response="Some evidence supports this [1].",
            sub_answers=[_make_sub_answer(chunks=[chunk])],
            citations=[citation],
        )

        result = await validate_citations(state, reranker=mock_reranker)

        # Pass-through: original citations returned
        assert len(result["citations"]) == 1
        assert result["citations"][0].passage_id == "c1"


# ---------------------------------------------------------------------------
# IT-03: Tier Params Routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestTierParamsIntegration:
    """IT-03: rewrite_query returns retrieval_params based on complexity tier."""

    async def test_factoid_tier_returns_correct_params(self):
        """Factoid query returns TIER_PARAMS['factoid'] retrieval params."""
        analysis = QueryAnalysis(
            is_clear=True,
            sub_questions=["What version is installed?"],
            complexity_tier="factoid",
            collections_hint=[],
            clarification_needed=None,
        )
        mock_llm, _ = _make_mock_llm(analysis)
        state = _make_state(
            messages=[HumanMessage(content="What version is installed?")],
        )

        result = await rewrite_query(state, llm=mock_llm)

        assert result["query_analysis"].complexity_tier == "factoid"
        assert result["retrieval_params"] == TIER_PARAMS["factoid"]
        assert result["retrieval_params"]["top_k"] == 5
        assert result["retrieval_params"]["confidence_threshold"] == 0.7

    async def test_analytical_tier_returns_correct_params(self):
        """Analytical query returns TIER_PARAMS['analytical'] retrieval params."""
        analysis = QueryAnalysis(
            is_clear=True,
            sub_questions=["How does the authentication system handle token refresh?"],
            complexity_tier="analytical",
            collections_hint=[],
            clarification_needed=None,
        )
        mock_llm, _ = _make_mock_llm(analysis)
        state = _make_state(
            messages=[HumanMessage(content="How does the authentication system handle token refresh?")],
        )

        result = await rewrite_query(state, llm=mock_llm)

        assert result["query_analysis"].complexity_tier == "analytical"
        assert result["retrieval_params"] == TIER_PARAMS["analytical"]
        assert result["retrieval_params"]["top_k"] == 25
        assert result["retrieval_params"]["confidence_threshold"] == 0.5

    async def test_fallback_to_lookup_on_unknown_tier(self):
        """When both LLM attempts fail, fallback uses lookup tier params."""
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        # Both first attempt and retry fail
        mock_structured.ainvoke.side_effect = [
            RuntimeError("LLM error first attempt"),
            RuntimeError("LLM error retry"),
        ]
        state = _make_state(
            messages=[HumanMessage(content="What is the deployment process?")],
        )

        result = await rewrite_query(state, llm=mock_llm)

        assert result["query_analysis"].complexity_tier == "lookup"
        assert result["retrieval_params"] == TIER_PARAMS["lookup"]

    async def test_factoid_vs_multihop_retrieval_params_differ(self):
        """Factoid tier has lower top_k and higher confidence_threshold than multi_hop."""
        factoid_analysis = QueryAnalysis(
            is_clear=True,
            sub_questions=["What version?"],
            complexity_tier="factoid",
            collections_hint=[],
            clarification_needed=None,
        )
        multihop_analysis = QueryAnalysis(
            is_clear=True,
            sub_questions=["Compare A and B across C"],
            complexity_tier="multi_hop",
            collections_hint=[],
            clarification_needed=None,
        )

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured

        # First call: factoid
        mock_structured.ainvoke.return_value = factoid_analysis
        factoid_state = _make_state(messages=[HumanMessage(content="What version?")])
        factoid_result = await rewrite_query(factoid_state, llm=mock_llm)

        # Second call: multi_hop
        mock_structured.ainvoke.return_value = multihop_analysis
        multihop_state = _make_state(messages=[HumanMessage(content="Compare A and B across C")])
        multihop_result = await rewrite_query(multihop_state, llm=mock_llm)

        assert factoid_result["retrieval_params"]["top_k"] < multihop_result["retrieval_params"]["top_k"]
        assert (
            factoid_result["retrieval_params"]["confidence_threshold"]
            > multihop_result["retrieval_params"]["confidence_threshold"]
        )


# ---------------------------------------------------------------------------
# IT-04: Circuit Breaker Integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.integration
class TestCircuitBreakerIntegration:
    """IT-04: Circuit breaker opens, NDJSON error frame emitted, half-open probe."""

    async def test_qdrant_circuit_opens_and_emits_error_frame(self):
        """T038: CB opens after 5 failures; 6th call raises CircuitOpenError without Qdrant call."""
        wrapper = QdrantClientWrapper("localhost", 6333)
        wrapper.client = AsyncMock()
        wrapper.client.search.side_effect = Exception("Qdrant down")

        # Fail 5 times — patch asyncio.sleep to skip retry delays
        with patch("asyncio.sleep"):
            for _ in range(5):
                with pytest.raises(Exception):
                    await wrapper.search("col", [0.1, 0.2], limit=5)

        assert wrapper._circuit_open is True
        assert wrapper._failure_count >= 5

        # 6th call: circuit open → CircuitOpenError raised before Qdrant is touched
        wrapper.client.search.reset_mock()
        with pytest.raises(CircuitOpenError):
            await wrapper.search("col", [0.1, 0.2], limit=5)

        wrapper.client.search.assert_not_called()

    async def test_inference_circuit_opens_and_degrades_gracefully(self):
        """T039: Inference CB opens after threshold failures; subsequent calls degrade."""
        import backend.agent.nodes as nodes_module

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.side_effect = RuntimeError("LLM service down")

        state = _make_state()

        # Exhaust failures to open the inference circuit (threshold = 5)
        for _ in range(5):
            result = await verify_groundedness(state, llm=mock_llm)
            assert result["groundedness_result"] is None

        assert nodes_module._inf_circuit_open is True
        assert nodes_module._inf_failure_count >= 5

        # Next call: circuit open → LLM not called → graceful degradation
        mock_structured.ainvoke.reset_mock()
        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is None
        mock_structured.ainvoke.assert_not_called()

    async def test_circuit_resets_after_cooldown(self):
        """T038: CB half-open after cooldown; successful probe closes the circuit."""
        wrapper = QdrantClientWrapper("localhost", 6333)
        wrapper.client = AsyncMock()

        # Open circuit directly via _record_failure (skip retry delays)
        for _ in range(5):
            wrapper._record_failure()

        assert wrapper._circuit_open is True

        # spec-26: FR-009 — cooldown is 60s default (was 30s); simulate elapsed
        from backend.config import settings

        wrapper._last_failure_time = time.monotonic() - (settings.circuit_breaker_cooldown_secs + 1)

        # Probe call succeeds (empty result list) → circuit closes
        wrapper.client.search.side_effect = None
        wrapper.client.search.return_value = []  # no hits — _search_with_retry returns []

        result = await wrapper.search("col", [0.1, 0.2], limit=5)

        assert result == []
        assert wrapper._circuit_open is False
        assert wrapper._failure_count == 0

    async def test_fr017_infrastructure_error_during_retry(self):
        """FR-017: infrastructure error during retry triggers inference circuit breaker."""
        import backend.agent.nodes as nodes_module

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured

        # Simulate infrastructure error (e.g., network timeout) during LLM call
        mock_structured.ainvoke.side_effect = ConnectionError("Network timeout during retry")

        state = _make_state()

        # Drive failure count to threshold
        threshold = 5
        for i in range(threshold):
            result = await verify_groundedness(state, llm=mock_llm)
            assert result["groundedness_result"] is None, f"Expected graceful degradation on call {i + 1}"

        # Circuit should now be open
        assert nodes_module._inf_circuit_open is True, (
            "Inference circuit breaker should be open after threshold failures"
        )

        # Verify the circuit blocks further LLM calls
        call_count_before = mock_structured.ainvoke.call_count
        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is None
        # LLM not called again — CB rejected before reaching the LLM
        assert mock_structured.ainvoke.call_count == call_count_before
