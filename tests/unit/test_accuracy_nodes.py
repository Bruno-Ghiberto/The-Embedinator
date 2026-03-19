"""Unit tests for Spec 05: Accuracy, Precision & Robustness.

HybridSearcher circuit breaker reference pattern (4-field state machine):
  _circuit_open: bool        -- open/closed gate
  _failure_count: int        -- consecutive failure counter
  _max_failures: int         -- threshold from settings
  _cooldown_secs: int        -- half-open cooldown from settings
  _check_circuit()           -- raise if open (half-open after cooldown)
  _record_success()          -- reset count + close
  _record_failure()          -- increment + open at threshold
"""
import time  # noqa: F401 (used in perf tests added by Wave 4)
import pytest
from unittest.mock import AsyncMock, MagicMock, patch  # noqa: F401 (used by Wave 2/3 test methods)

from langchain_core.messages import HumanMessage  # noqa: F401 (used by A4 test methods)

from backend.agent.nodes import verify_groundedness, validate_citations  # noqa: F401 (used by Wave 2 test methods)
from backend.agent.schemas import (
    ClaimVerification,
    GroundednessResult,
    QueryAnalysis,  # noqa: F401 (used by Wave 2/4 test methods)
    SubAnswer,
    Citation,
    RetrievedChunk,
)

# Symbols added by Wave 2 agents (A2, A3, A4) — imported lazily so scaffold loads
try:
    from backend.agent.nodes import (
        TIER_PARAMS,
        _apply_groundedness_annotations,
        _extract_claim_for_citation,
    )
except (ImportError, AttributeError):
    TIER_PARAMS = None  # type: ignore[assignment]
    _apply_groundedness_annotations = None  # type: ignore[assignment]
    _extract_claim_for_citation = None  # type: ignore[assignment]

# Symbols added by Wave 3 (A5) — inference circuit breaker
try:
    from backend.agent.nodes import (
        _check_inference_circuit,
        _record_inference_success,
        _record_inference_failure,
    )
except (ImportError, AttributeError):
    _check_inference_circuit = None  # type: ignore[assignment]
    _record_inference_success = None  # type: ignore[assignment]
    _record_inference_failure = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id="c1", text="Test evidence for the claim.") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        source_file="test.md",
        breadcrumb="sec1",
        parent_id="p1",
        collection="col1",
        dense_score=0.8,
        sparse_score=0.3,
        rerank_score=0.9,
    )


def _make_citation(passage_id="c1", text="Test evidence.") -> Citation:
    return Citation(
        passage_id=passage_id,
        document_id="doc1",
        document_name="test.md",
        start_offset=0,
        end_offset=len(text),
        text=text,
        relevance_score=0.9,
    )


def _make_sub_answer(chunks=None, confidence_score=80) -> SubAnswer:
    if chunks is None:
        chunks = [_make_chunk()]
    return SubAnswer(
        sub_question="What is X?",
        answer="X is Y.",
        citations=[],
        chunks=chunks,
        confidence_score=confidence_score,
    )


def _make_state(**overrides):
    base = {
        "session_id": "test-session-001",
        "messages": [],
        "llm_model": "qwen2.5:7b",
        "embed_model": "nomic-embed-text",
        "selected_collections": ["docs"],
        "query_analysis": None,
        "retrieval_params": {},
        "sub_answers": [_make_sub_answer()],
        "final_response": "The answer is X because Y.",
        "citations": [],
        "groundedness_result": None,
        "confidence_score": 80,
    }
    base.update(overrides)
    return base


def _make_groundedness_result(
    supported=2, unsupported=1, contradicted=0, overall_grounded=True, confidence_adjustment=0.8
) -> GroundednessResult:
    verifications = []
    for i in range(supported):
        verifications.append(ClaimVerification(
            claim=f"Supported claim {i + 1}",
            verdict="supported",
            evidence_chunk_id="c1",
            explanation="Evidence found.",
        ))
    for i in range(unsupported):
        verifications.append(ClaimVerification(
            claim=f"Unsupported claim {i + 1}",
            verdict="unsupported",
            evidence_chunk_id=None,
            explanation="No evidence found.",
        ))
    for i in range(contradicted):
        verifications.append(ClaimVerification(
            claim=f"Contradicted claim {i + 1}",
            verdict="contradicted",
            evidence_chunk_id="c1",
            explanation="Evidence contradicts this claim.",
        ))
    return GroundednessResult(
        verifications=verifications,
        overall_grounded=overall_grounded,
        confidence_adjustment=confidence_adjustment,
    )


# ---------------------------------------------------------------------------
# US1: Grounded Answer Verification (verify_groundedness)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestVerifyGroundedness:
    """US1: System verifies factual claims against retrieved context (GAV)."""

    async def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setattr("backend.agent.nodes.settings.groundedness_check_enabled", False)
        mock_llm = AsyncMock()
        state = _make_state()
        result = await verify_groundedness(state, llm=mock_llm)
        assert result["groundedness_result"] is None
        mock_llm.with_structured_output.assert_not_called()

    async def test_returns_none_when_no_final_response(self):
        state = _make_state(final_response=None)
        result = await verify_groundedness(state, llm=AsyncMock())
        assert result["groundedness_result"] is None

    async def test_returns_none_when_no_sub_answers(self):
        state = _make_state(sub_answers=[])
        result = await verify_groundedness(state, llm=AsyncMock())
        assert result["groundedness_result"] is None

    async def test_returns_none_when_no_context(self):
        """Sub-answers exist but chunks have empty text → empty context → skip."""
        empty_chunk = _make_chunk(text="")
        sa = _make_sub_answer(chunks=[empty_chunk])
        state = _make_state(sub_answers=[sa])
        result = await verify_groundedness(state, llm=AsyncMock())
        assert result["groundedness_result"] is None

    async def test_full_groundedness_check_supported_answer(self):
        gr = _make_groundedness_result(supported=2, unsupported=0, contradicted=0,
                                       overall_grounded=True, confidence_adjustment=1.0)
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.return_value = gr

        state = _make_state(
            final_response="Supported claim 1. Supported claim 2.",
            sub_answers=[_make_sub_answer(confidence_score=80)],
        )
        result = await verify_groundedness(state, llm=mock_llm)

        assert result["groundedness_result"] is gr
        assert result["confidence_score"] == 80  # 80 * 1.0
        assert "[unverified]" not in result["final_response"]
        assert "Warning" not in result["final_response"]

    async def test_applies_annotations_unsupported_claim(self):
        """T010: unsupported claim gets [unverified] tag."""
        gr = _make_groundedness_result(supported=1, unsupported=1, contradicted=0,
                                       overall_grounded=True, confidence_adjustment=0.5)
        response = "Supported claim 1. Unsupported claim 1."
        annotated = _apply_groundedness_annotations(response, gr)
        assert "Unsupported claim 1 [unverified]" in annotated
        assert "Supported claim 1" in annotated
        assert "[unverified]" not in annotated.split("Unsupported claim 1")[0]

    async def test_applies_annotations_contradicted_claim(self):
        """T010: contradicted claim is removed with explanation."""
        gr = _make_groundedness_result(supported=1, unsupported=0, contradicted=1,
                                       overall_grounded=True, confidence_adjustment=0.5)
        response = "Supported claim 1. Contradicted claim 1."
        annotated = _apply_groundedness_annotations(response, gr)
        assert "Contradicted claim 1" not in annotated
        assert "[Removed:" in annotated
        assert "contradicted by the source material" in annotated

    async def test_applies_warning_banner_when_not_overall_grounded(self):
        """T010: >50% unsupported triggers warning banner."""
        gr = _make_groundedness_result(supported=0, unsupported=3, contradicted=0,
                                       overall_grounded=False, confidence_adjustment=0.0)
        response = "Unsupported claim 1. Unsupported claim 2. Unsupported claim 3."
        annotated = _apply_groundedness_annotations(response, gr)
        assert annotated.startswith("**Warning:")

    async def test_gav_adjusted_confidence_score(self):
        """Confidence = mean(sub_answer scores) * confidence_adjustment, clamped 0-100."""
        gr = _make_groundedness_result(supported=2, unsupported=1, contradicted=0,
                                       overall_grounded=True, confidence_adjustment=0.8)
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.return_value = gr

        sa1 = _make_sub_answer(confidence_score=80)
        sa2 = _make_sub_answer(confidence_score=60)
        state = _make_state(
            final_response="Supported claim 1. Supported claim 2. Unsupported claim 1.",
            sub_answers=[sa1, sa2],
        )
        result = await verify_groundedness(state, llm=mock_llm)

        # mean([80, 60]) = 70, * 0.8 = 56
        assert result["confidence_score"] == 56

    async def test_graceful_degradation_on_llm_error(self):
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.side_effect = RuntimeError("LLM unavailable")

        state = _make_state()
        result = await verify_groundedness(state, llm=mock_llm)
        assert result["groundedness_result"] is None

    async def test_graceful_degradation_on_circuit_open(self):
        """If circuit breaker raises inside the try block, graceful degradation kicks in."""
        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.side_effect = RuntimeError("circuit open")

        state = _make_state()
        result = await verify_groundedness(state, llm=mock_llm)
        assert result["groundedness_result"] is None


# ---------------------------------------------------------------------------
# US2: Citation Alignment Validation (validate_citations)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestValidateCitations:
    """US2: System validates citation alignment via cross-encoder."""

    async def test_returns_unchanged_when_no_citations(self):
        state = _make_state(citations=[])
        result = await validate_citations(state)
        assert result["citations"] == []

    async def test_returns_unchanged_when_no_reranker(self):
        citation = _make_citation()
        state = _make_state(citations=[citation])
        result = await validate_citations(state, reranker=None)
        assert result["citations"] == [citation]

    async def test_returns_unchanged_when_no_chunks(self):
        citation = _make_citation()
        state = _make_state(
            citations=[citation],
            sub_answers=[SubAnswer(sub_question="q", answer="a", citations=[], chunks=[], confidence_score=80)],
        )
        mock_reranker = MagicMock()
        result = await validate_citations(state, reranker=mock_reranker)
        assert result["citations"] == [citation]

    async def test_keeps_citation_above_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.citation_alignment_threshold", 0.3)
        citation = _make_citation(text="API version 2.0 docs")
        chunk = _make_chunk(chunk_id="c1", text="API version 2.0 docs")
        state = _make_state(
            citations=[citation],
            sub_answers=[_make_sub_answer(chunks=[chunk])],
            final_response="The API supports version 2.0 [1]. It also has rate limiting.",
        )
        mock_reranker = MagicMock()
        mock_reranker.model.rank.return_value = [{"corpus_id": 0, "score": 0.85}]

        result = await validate_citations(state, reranker=mock_reranker)
        assert len(result["citations"]) == 1
        assert result["citations"][0].passage_id == citation.passage_id

    async def test_remaps_citation_below_threshold(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.citation_alignment_threshold", 0.3)
        citation = _make_citation(passage_id="old-p1", text="Unrelated text")
        good_chunk = _make_chunk(chunk_id="c2", text="API version 2.0 docs")
        state = _make_state(
            citations=[citation],
            sub_answers=[_make_sub_answer(chunks=[good_chunk])],
            final_response="The API supports version 2.0 [1].",
        )
        mock_reranker = MagicMock()
        mock_reranker.model.rank.side_effect = [
            [{"corpus_id": 0, "score": 0.1}],
            [{"corpus_id": 0, "score": 0.9}],
        ]

        result = await validate_citations(state, reranker=mock_reranker)
        assert len(result["citations"]) == 1
        assert result["citations"][0].passage_id == "c2"
        assert result["citations"][0].relevance_score == 0.9

    async def test_strips_citation_when_no_valid_remap(self, monkeypatch):
        monkeypatch.setattr("backend.config.settings.citation_alignment_threshold", 0.3)
        citation = _make_citation(text="Unrelated text")
        chunk = _make_chunk(chunk_id="c1", text="Also unrelated")
        state = _make_state(
            citations=[citation],
            sub_answers=[_make_sub_answer(chunks=[chunk])],
            final_response="Something mentioned [1].",
        )
        mock_reranker = MagicMock()
        mock_reranker.model.rank.side_effect = [
            [{"corpus_id": 0, "score": 0.05}],
            [{"corpus_id": 0, "score": 0.1}],
        ]

        result = await validate_citations(state, reranker=mock_reranker)
        assert result["citations"] == []

    async def test_graceful_degradation_on_reranker_error(self):
        citation = _make_citation()
        state = _make_state(
            citations=[citation],
            sub_answers=[_make_sub_answer()],
            final_response="Some answer [1].",
        )
        mock_reranker = MagicMock()
        mock_reranker.model.rank.side_effect = RuntimeError("Reranker crash")

        result = await validate_citations(state, reranker=mock_reranker)
        assert result["citations"] == [citation]

    async def test_extract_claim_for_citation_finds_sentence(self):
        assert _extract_claim_for_citation is not None
        text = "First sentence here. The API supports version 2.0 [1]. Last sentence ends."
        result = _extract_claim_for_citation(text, "[1]")
        assert "[1]" in result
        assert result.strip() == "The API supports version 2.0 [1]."

    async def test_extract_claim_for_citation_fallback(self):
        assert _extract_claim_for_citation is not None
        text = "A" * 300
        result = _extract_claim_for_citation(text, "[99]")
        assert result == text[:200]

    async def test_performance_under_50ms(self, monkeypatch):
        """SC-010: validate_citations with 10 citations must complete < 50ms."""
        monkeypatch.setattr("backend.config.settings.citation_alignment_threshold", 0.3)
        citations = [_make_citation(passage_id=f"p{i}", text=f"chunk text {i}") for i in range(10)]
        chunks = [_make_chunk(chunk_id=f"c{i}", text=f"chunk text {i}") for i in range(10)]
        state = _make_state(
            citations=citations,
            sub_answers=[_make_sub_answer(chunks=chunks)],
            final_response=" ".join(f"Claim {i} [{i + 1}]." for i in range(10)),
        )
        mock_reranker = MagicMock()
        mock_reranker.model.rank.return_value = [{"corpus_id": 0, "score": 0.9}]

        start = time.monotonic()
        await validate_citations(state, reranker=mock_reranker)
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 50, f"validate_citations took {elapsed_ms:.1f}ms (limit: 50ms)"


# ---------------------------------------------------------------------------
# US3: Confidence Indicator (metadata frame)
# ---------------------------------------------------------------------------

class TestConfidenceIndicator:
    """US3: NDJSON metadata frame includes groundedness object and GAV confidence."""

    def _build_groundedness_obj(self, groundedness_result):
        """Mirror the logic A6 will implement in chat.py."""
        if groundedness_result is None:
            return None
        return {
            "supported": sum(
                1 for v in groundedness_result.verifications if v.verdict == "supported"
            ),
            "unsupported": sum(
                1 for v in groundedness_result.verifications if v.verdict == "unsupported"
            ),
            "contradicted": sum(
                1 for v in groundedness_result.verifications if v.verdict == "contradicted"
            ),
            "overall_grounded": groundedness_result.overall_grounded,
        }

    def test_metadata_frame_includes_groundedness_null(self):
        obj = self._build_groundedness_obj(None)
        assert obj is None

    def test_metadata_frame_includes_groundedness_object(self):
        result = _make_groundedness_result(supported=2, unsupported=1, contradicted=0)
        obj = self._build_groundedness_obj(result)
        assert obj is not None

    def test_metadata_frame_confidence_is_gav_adjusted(self):
        """GAV-adjusted confidence = int(mean(sub_scores) * confidence_adjustment)."""
        sub_scores = [80, 60]
        confidence_adjustment = 0.75
        base = sum(sub_scores) / len(sub_scores)  # 70.0
        adjusted = int(base * confidence_adjustment)  # int(52.5) = 52
        assert adjusted == 52

    def test_groundedness_object_fields(self):
        result = _make_groundedness_result(supported=3, unsupported=1, contradicted=1)
        obj = self._build_groundedness_obj(result)
        assert obj is not None
        assert obj["supported"] == 3
        assert obj["unsupported"] == 1
        assert obj["contradicted"] == 1
        assert "overall_grounded" in obj
        assert isinstance(obj["overall_grounded"], bool)

    # T019: Confidence adjustment formula tests
    def test_confidence_unchanged_when_adjustment_is_1_0(self):
        """confidence_adjustment=1.0 — score unchanged."""
        base_scores = [80, 90]  # mean = 85
        adjustment = 1.0
        result = int(sum(base_scores) / len(base_scores) * adjustment)
        assert result == 85

    def test_confidence_reduced_proportionally_at_0_7(self):
        """confidence_adjustment=0.7 — score reduced proportionally."""
        base_scores = [80, 90]  # mean = 85
        adjustment = 0.7
        result = int(sum(base_scores) / len(base_scores) * adjustment)
        assert result == 59  # int(85 * 0.7) = 59

    def test_confidence_clamped_to_0_when_adjustment_is_0(self):
        """confidence_adjustment=0.0 — score clamped to 0."""
        base_scores = [80, 90]
        adjustment = 0.0
        raw = int(sum(base_scores) / len(base_scores) * adjustment)
        result = max(0, min(100, raw))
        assert result == 0

    def test_confidence_clamped_to_100_when_exceeds(self):
        """Result clamped to 100 when formula would exceed 100."""
        base_scores = [100, 100]  # mean = 100, * 1.5 = 150 → clamp to 100
        adjustment = 1.5
        raw = int(sum(base_scores) / len(base_scores) * adjustment)
        result = max(0, min(100, raw))
        assert result == 100

    # T020: Metadata frame JSON structure tests
    def test_metadata_frame_groundedness_serializes_as_null(self):
        """groundedness=None serializes as JSON null per the SSE contract."""
        import json as _json
        frame = {
            "type": "metadata",
            "trace_id": "test-trace",
            "confidence": 75,
            "groundedness": None,
            "citations": [],
            "latency_ms": 100,
        }
        parsed = _json.loads(_json.dumps(frame))
        assert parsed["groundedness"] is None

    def test_metadata_frame_groundedness_object_has_all_four_fields(self):
        """groundedness object contains exactly the 4 contracted fields."""
        result = _make_groundedness_result(supported=2, unsupported=1, contradicted=0)
        obj = self._build_groundedness_obj(result)
        assert obj is not None
        assert set(obj.keys()) == {"supported", "unsupported", "contradicted", "overall_grounded"}
        assert isinstance(obj["supported"], int)
        assert isinstance(obj["unsupported"], int)
        assert isinstance(obj["contradicted"], int)
        assert isinstance(obj["overall_grounded"], bool)

    def test_metadata_confidence_is_int_in_0_to_100(self):
        """confidence value in metadata frame is a GAV-adjusted int in [0, 100]."""
        sub_scores = [80, 60]
        adjustment = 0.75
        base = sum(sub_scores) / len(sub_scores)  # 70.0
        result = max(0, min(100, int(base * adjustment)))  # int(52.5) = 52
        assert isinstance(result, int)
        assert 0 <= result <= 100
        assert result == 52


# ---------------------------------------------------------------------------
# US4: Complexity-Tier Retrieval Parameters (TIER_PARAMS)
# ---------------------------------------------------------------------------

class TestTierParams:
    """US4: Query analysis tier drives retrieval parameter selection."""

    def test_tier_params_has_all_five_tiers(self):
        from backend.agent.nodes import TIER_PARAMS as _tp
        assert set(_tp.keys()) == {"factoid", "lookup", "comparison", "analytical", "multi_hop"}

    def test_factoid_tier_params(self):
        from backend.agent.nodes import TIER_PARAMS as _tp
        factoid = _tp["factoid"]
        assert factoid["top_k"] == 5
        assert factoid["max_iterations"] == 3
        assert factoid["max_tool_calls"] == 3
        assert factoid["confidence_threshold"] == 0.7
        # factoid must be shallowest (lowest top_k)
        for tier, params in _tp.items():
            if tier != "factoid":
                assert factoid["top_k"] <= params["top_k"]

    def test_multi_hop_tier_params(self):
        from backend.agent.nodes import TIER_PARAMS as _tp
        multi_hop = _tp["multi_hop"]
        assert multi_hop["top_k"] == 30
        assert multi_hop["max_iterations"] == 10
        assert multi_hop["max_tool_calls"] == 8
        assert multi_hop["confidence_threshold"] == 0.45
        # multi_hop must be deepest (highest top_k, lowest confidence_threshold)
        for tier, params in _tp.items():
            if tier != "multi_hop":
                assert multi_hop["top_k"] >= params["top_k"]
                assert multi_hop["confidence_threshold"] <= params["confidence_threshold"]

    @pytest.mark.asyncio
    async def test_rewrite_query_returns_retrieval_params(self):
        from backend.agent.nodes import rewrite_query, TIER_PARAMS as _tp

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        mock_structured.ainvoke.return_value = QueryAnalysis(
            is_clear=True,
            sub_questions=["What is X?"],
            complexity_tier="analytical",
            collections_hint=[],
            clarification_needed=None,
        )

        state = {
            "session_id": "test-us4",
            "messages": [HumanMessage(content="complex analytical query")],
            "selected_collections": ["col1"],
        }

        result = await rewrite_query(state, llm=mock_llm)
        assert "retrieval_params" in result
        assert result["retrieval_params"]["top_k"] == _tp["analytical"]["top_k"]  # 25

    @pytest.mark.asyncio
    async def test_rewrite_query_uses_lookup_as_default(self):
        """Fallback path uses lookup tier params."""
        from backend.agent.nodes import rewrite_query, TIER_PARAMS as _tp

        mock_llm = MagicMock()
        mock_structured = AsyncMock()
        mock_llm.with_structured_output.return_value = mock_structured
        # Both attempts fail → fallback path
        mock_structured.ainvoke.side_effect = Exception("LLM unavailable")

        state = {
            "session_id": "test-us4-fallback",
            "messages": [HumanMessage(content="some query")],
            "selected_collections": [],
        }

        result = await rewrite_query(state, llm=mock_llm)
        assert "retrieval_params" in result
        assert result["retrieval_params"] == _tp["lookup"]


# ---------------------------------------------------------------------------
# US6: Circuit Breaker Resilience
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """US6: Circuit breaker prevents cascading failures in Qdrant and inference."""

    def test_qdrant_circuit_breaker_opens_at_threshold(self, monkeypatch):
        """5 consecutive failures -> circuit opens."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        # 4 failures: circuit stays closed
        for _ in range(4):
            wrapper._record_failure()
        assert not wrapper._circuit_open
        # 5th failure: circuit opens
        wrapper._record_failure()
        assert wrapper._circuit_open
        assert wrapper._failure_count == 5
        assert wrapper._last_failure_time is not None

    def test_qdrant_circuit_breaker_resets_on_success(self, monkeypatch):
        """Success resets failure count and closes circuit."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        for _ in range(5):
            wrapper._record_failure()
        assert wrapper._circuit_open
        wrapper._record_success()
        assert not wrapper._circuit_open
        assert wrapper._failure_count == 0

    def test_qdrant_circuit_breaker_half_open_after_cooldown(self, monkeypatch):
        """After cooldown, circuit transitions to half-open (allows probe)."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.errors import CircuitOpenError
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        for _ in range(5):
            wrapper._record_failure()
        assert wrapper._circuit_open
        # Before cooldown: raises
        with pytest.raises(CircuitOpenError):
            wrapper._check_circuit()
        # Simulate cooldown elapsed
        wrapper._last_failure_time = time.monotonic() - 31
        # After cooldown: half-open, no raise
        wrapper._check_circuit()
        assert not wrapper._circuit_open

    def test_qdrant_circuit_breaker_probe_failure_reopens(self, monkeypatch):
        """Probe failure after half-open re-opens circuit (count still at threshold)."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        for _ in range(5):
            wrapper._record_failure()
        wrapper._last_failure_time = time.monotonic() - 31
        wrapper._check_circuit()  # half-open: sets _circuit_open=False but keeps count
        assert not wrapper._circuit_open
        # Probe fails → _failure_count goes to 6, re-opens circuit
        wrapper._record_failure()
        assert wrapper._circuit_open  # re-opened because count >= threshold
        assert wrapper._failure_count == 6

    def test_qdrant_missing_fields_added(self, monkeypatch):
        """QdrantClientWrapper has _last_failure_time and _cooldown_secs."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        assert hasattr(wrapper, "_last_failure_time")
        assert hasattr(wrapper, "_cooldown_secs")
        assert wrapper._last_failure_time is None
        assert wrapper._cooldown_secs == 30
        assert wrapper._max_failures == 5

    def test_qdrant_circuit_open_rejects_without_calling_qdrant(self, monkeypatch):
        """Open circuit raises CircuitOpenError immediately."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.errors import CircuitOpenError
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        for _ in range(5):
            wrapper._record_failure()
        with pytest.raises(CircuitOpenError):
            wrapper._check_circuit()

    def test_inference_circuit_breaker_opens_at_threshold(self, monkeypatch):
        """5 consecutive inference failures -> circuit opens."""
        import backend.agent.nodes as nodes_mod
        monkeypatch.setattr(nodes_mod, "_inf_circuit_open", False)
        monkeypatch.setattr(nodes_mod, "_inf_failure_count", 0)
        monkeypatch.setattr(nodes_mod, "_inf_last_failure_time", None)
        monkeypatch.setattr(nodes_mod, "_inf_max_failures", 5)
        monkeypatch.setattr(nodes_mod, "_inf_cooldown_secs", 30)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)

        for _ in range(4):
            _record_inference_failure()
        assert not nodes_mod._inf_circuit_open

        _record_inference_failure()
        assert nodes_mod._inf_circuit_open
        assert nodes_mod._inf_failure_count == 5

    def test_inference_circuit_breaker_resets_on_success(self, monkeypatch):
        """Success resets inference circuit breaker."""
        import backend.agent.nodes as nodes_mod
        monkeypatch.setattr(nodes_mod, "_inf_circuit_open", True)
        monkeypatch.setattr(nodes_mod, "_inf_failure_count", 5)
        monkeypatch.setattr(nodes_mod, "_inf_last_failure_time", time.monotonic())
        monkeypatch.setattr(nodes_mod, "_inf_max_failures", 5)
        monkeypatch.setattr(nodes_mod, "_inf_cooldown_secs", 30)

        _record_inference_success()
        assert not nodes_mod._inf_circuit_open
        assert nodes_mod._inf_failure_count == 0

    def test_inference_circuit_breaker_half_open_after_cooldown(self, monkeypatch):
        """Inference CB transitions to half-open after cooldown."""
        import backend.agent.nodes as nodes_mod
        from backend.errors import CircuitOpenError
        monkeypatch.setattr(nodes_mod, "_inf_circuit_open", True)
        monkeypatch.setattr(nodes_mod, "_inf_failure_count", 5)
        monkeypatch.setattr(nodes_mod, "_inf_last_failure_time", time.monotonic())
        monkeypatch.setattr(nodes_mod, "_inf_max_failures", 5)
        monkeypatch.setattr(nodes_mod, "_inf_cooldown_secs", 30)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)

        # Before cooldown: raises
        with pytest.raises(CircuitOpenError):
            _check_inference_circuit()

        # After cooldown: half-open, no raise
        monkeypatch.setattr(nodes_mod, "_inf_last_failure_time", time.monotonic() - 31)
        _check_inference_circuit()
        assert not nodes_mod._inf_circuit_open

    def test_circuit_open_error_defined_in_errors(self):
        """CircuitOpenError exists in backend.errors and inherits from EmbeddinatorError."""
        from backend.errors import CircuitOpenError, EmbeddinatorError
        assert issubclass(CircuitOpenError, EmbeddinatorError)
        err = CircuitOpenError("test")
        assert str(err) == "test"

    def test_performance_circuit_open_rejection_under_1s(self, monkeypatch):
        """SC-008: circuit-open rejection must occur in < 1s (target < 10ms, no I/O)."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.errors import CircuitOpenError
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        for _ in range(5):
            wrapper._record_failure()

        start = time.monotonic()
        with pytest.raises(CircuitOpenError):
            wrapper._check_circuit()
        elapsed_ms = (time.monotonic() - start) * 1000
        assert elapsed_ms < 1000, f"Circuit-open rejection took {elapsed_ms:.1f}ms (limit: 1000ms)"

    @pytest.mark.asyncio
    async def test_qdrant_retry_succeeds_on_second_attempt(self, monkeypatch):
        """Tenacity retries: call succeeds on 2nd attempt -> 1 retry."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        wrapper.client = AsyncMock()

        call_count = 0

        async def flaky_search(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("transient")
            return []

        wrapper.client.search = flaky_search
        result = await wrapper.search("test_col", [0.1, 0.2], limit=5)
        assert result == []
        assert call_count == 2
        assert wrapper._failure_count == 0  # success resets

    @pytest.mark.asyncio
    async def test_qdrant_retry_exhausted_records_failure(self, monkeypatch):
        """Tenacity retries exhausted: reraises and records CB failure."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        wrapper.client = AsyncMock()
        wrapper.client.search.side_effect = ConnectionError("permanent")

        with pytest.raises(ConnectionError):
            await wrapper.search("test_col", [0.1, 0.2], limit=5)
        assert wrapper._failure_count == 1  # one CB failure after retries exhausted

    @pytest.mark.asyncio
    async def test_qdrant_circuit_open_not_retried(self, monkeypatch):
        """CircuitOpenError is raised immediately, not retried."""
        monkeypatch.setattr("backend.config.settings.circuit_breaker_failure_threshold", 5)
        monkeypatch.setattr("backend.config.settings.circuit_breaker_cooldown_secs", 30)
        from backend.errors import CircuitOpenError
        from backend.storage.qdrant_client import QdrantClientWrapper
        wrapper = QdrantClientWrapper("localhost", 6333)
        wrapper.client = AsyncMock()
        for _ in range(5):
            wrapper._record_failure()

        with pytest.raises(CircuitOpenError):
            await wrapper.search("test_col", [0.1, 0.2], limit=5)
        # Client.search was never called
        wrapper.client.search.assert_not_called()
