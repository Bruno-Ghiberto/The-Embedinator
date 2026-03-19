"""Unit tests for MetaReasoningGraph node functions."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.meta_reasoning_nodes import (
    decide_strategy,
    evaluate_retrieval_quality,
    generate_alternative_queries,
    report_uncertainty,
    STRATEGY_CHANGE_COLLECTION,
    STRATEGY_RELAX_FILTERS,
    STRATEGY_WIDEN_SEARCH,
    _build_modified_state_change_collection,
    _build_modified_state_relax,
    _build_modified_state_widen,
)
from backend.agent.schemas import RetrievedChunk


def _chunk(chunk_id="c1", text="test text", rerank_score=0.8, dense_score=0.5,
           collection="col1", parent_id="p1", source_file="test.md"):
    return RetrievedChunk(
        chunk_id=chunk_id, text=text, source_file=source_file,
        breadcrumb="ch1", parent_id=parent_id, collection=collection,
        dense_score=dense_score, sparse_score=0.3, rerank_score=rerank_score,
    )


def _make_meta_state(**overrides):
    base = {
        "sub_question": "What is quantum entanglement?",
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


def _make_config(llm=None, reranker=None, settings_obj=None, callbacks=None):
    configurable = {}
    if llm is not None:
        configurable["llm"] = llm
    if reranker is not None:
        configurable["reranker"] = reranker
    if settings_obj is not None:
        configurable["settings"] = settings_obj
    if callbacks is not None:
        configurable["callbacks"] = callbacks
    return {"configurable": configurable}


# ====================
# evaluate_retrieval_quality
# ====================

class TestEvaluateRetrievalQuality:
    """Tests for evaluate_retrieval_quality node (FR-002, FR-003)."""

    @pytest.mark.asyncio
    async def test_scores_all_chunks_and_computes_mean(self):
        """Core path: reranker scores all chunks, returns correct mean."""
        chunks = [_chunk(chunk_id=f"c{i}", rerank_score=0.1 * i) for i in range(1, 6)]
        scored = [_chunk(chunk_id=f"c{i}", rerank_score=0.1 * i) for i in range(1, 6)]

        reranker = MagicMock()
        reranker.rerank.return_value = scored

        state = _make_meta_state(
            retrieved_chunks=chunks,
            sub_question="What is X?",
        )
        config = _make_config(reranker=reranker)

        result = await evaluate_retrieval_quality(state, config)

        reranker.rerank.assert_called_once_with("What is X?", chunks, top_k=5)
        assert len(result["chunk_relevance_scores"]) == 5
        for actual, expected in zip(result["chunk_relevance_scores"], [0.1, 0.2, 0.3, 0.4, 0.5]):
            assert abs(actual - expected) < 1e-9
        assert abs(result["mean_relevance_score"] - 0.3) < 0.001

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_zero(self):
        """FR-013: empty chunks -> mean=0.0, scores=[]."""
        state = _make_meta_state(retrieved_chunks=[])
        config = _make_config(reranker=MagicMock())

        result = await evaluate_retrieval_quality(state, config)

        assert result["mean_relevance_score"] == 0.0
        assert result["chunk_relevance_scores"] == []

    @pytest.mark.asyncio
    async def test_reranker_none_returns_zero(self):
        """FR-012: reranker is None -> graceful degradation."""
        chunks = [_chunk()]
        state = _make_meta_state(retrieved_chunks=chunks)
        config = _make_config(reranker=None)

        result = await evaluate_retrieval_quality(state, config)

        assert result["mean_relevance_score"] == 0.0
        assert result["chunk_relevance_scores"] == []

    @pytest.mark.asyncio
    async def test_reranker_missing_from_config(self):
        """FR-012: reranker not in config -> graceful degradation."""
        chunks = [_chunk()]
        state = _make_meta_state(retrieved_chunks=chunks)
        config = {"configurable": {}}

        result = await evaluate_retrieval_quality(state, config)

        assert result["mean_relevance_score"] == 0.0
        assert result["chunk_relevance_scores"] == []

    @pytest.mark.asyncio
    async def test_reranker_exception_returns_zero(self):
        """FR-012: reranker raises -> graceful degradation."""
        chunks = [_chunk()]
        reranker = MagicMock()
        reranker.rerank.side_effect = RuntimeError("model crashed")

        state = _make_meta_state(retrieved_chunks=chunks)
        config = _make_config(reranker=reranker)

        result = await evaluate_retrieval_quality(state, config)

        assert result["mean_relevance_score"] == 0.0
        assert result["chunk_relevance_scores"] == []


# ====================
# generate_alternative_queries
# ====================

class TestGenerateAlternativeQueries:
    """Tests for generate_alternative_queries node (FR-001)."""

    @pytest.mark.asyncio
    async def test_produces_exactly_3_alternatives(self):
        """Core path: LLM returns 3 queries."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content="1. What are quantum entangled particles?\n2. How does entanglement work?\n3. Define quantum entanglement simply"
        )

        state = _make_meta_state()
        config = _make_config(llm=llm)

        result = await generate_alternative_queries(state, config)

        assert len(result["alternative_queries"]) == 3
        assert "quantum entangled particles" in result["alternative_queries"][0].lower()

    @pytest.mark.asyncio
    async def test_pads_to_3_if_fewer(self):
        """If LLM returns fewer than 3, pad with original question."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="1. Alternative one\n2. Alternative two")

        state = _make_meta_state(sub_question="Original question")
        config = _make_config(llm=llm)

        result = await generate_alternative_queries(state, config)

        assert len(result["alternative_queries"]) == 3
        assert result["alternative_queries"][2] == "Original question"

    @pytest.mark.asyncio
    async def test_graceful_llm_failure(self):
        """On LLM failure, return [original sub_question]."""
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("LLM unavailable")

        state = _make_meta_state(sub_question="My question")
        config = _make_config(llm=llm)

        result = await generate_alternative_queries(state, config)

        assert result["alternative_queries"] == ["My question"]

    @pytest.mark.asyncio
    async def test_sse_event_emitted(self):
        """FR-014: SSE callback invoked."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="1. A\n2. B\n3. C")

        callback = MagicMock()
        callback.on_custom_event = MagicMock()

        state = _make_meta_state()
        config = _make_config(llm=llm, callbacks=[callback])

        await generate_alternative_queries(state, config)

        callback.on_custom_event.assert_called_once()
        args = callback.on_custom_event.call_args
        assert args[0][0] == "meta_reasoning"
        assert "Generating alternative queries" in args[0][1]["status"]


# ====================
# decide_strategy
# ====================

class TestDecideStrategy:
    """Tests for decide_strategy node (FR-004, FR-006, FR-015)."""

    def _settings(self, max_attempts=2, rel_thr=0.2, var_thr=0.15):
        s = MagicMock()
        s.meta_reasoning_max_attempts = max_attempts
        s.meta_relevance_threshold = rel_thr
        s.meta_variance_threshold = var_thr
        return s

    @pytest.mark.asyncio
    async def test_widen_search_low_mean_few_chunks(self):
        """Low mean + few chunks -> WIDEN_SEARCH."""
        chunks = [_chunk(), _chunk(chunk_id="c2")]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            chunk_relevance_scores=[0.1, 0.1],
            alternative_queries=["alt1", "alt2"],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] == STRATEGY_WIDEN_SEARCH
        assert result["meta_attempt_count"] == 1
        assert STRATEGY_WIDEN_SEARCH in result["attempted_strategies"]
        assert result["modified_state"]["selected_collections"] == "ALL"

    @pytest.mark.asyncio
    async def test_change_collection_low_mean_many_chunks(self):
        """Low mean + many chunks (>=3) -> CHANGE_COLLECTION."""
        chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            chunk_relevance_scores=[0.1] * 5,
            alternative_queries=["alt1"],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] == STRATEGY_CHANGE_COLLECTION
        assert result["modified_state"]["selected_collections"] == "ROTATE"

    @pytest.mark.asyncio
    async def test_relax_filters_moderate_mean_high_variance(self):
        """Mean >= threshold + high variance -> RELAX_FILTERS."""
        chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
        # scores with high stdev: [0.1, 0.9, 0.1, 0.9, 0.1]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.42,
            chunk_relevance_scores=[0.1, 0.9, 0.1, 0.9, 0.1],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] == STRATEGY_RELAX_FILTERS
        assert result["modified_state"]["payload_filters"] is None

    @pytest.mark.asyncio
    async def test_report_uncertainty_moderate_mean_low_variance(self):
        """Mean >= threshold + low variance -> no strategy (report_uncertainty)."""
        chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.3,
            chunk_relevance_scores=[0.29, 0.30, 0.31, 0.30, 0.30],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] is None

    @pytest.mark.asyncio
    async def test_max_attempts_guard(self):
        """FR-006: at max_attempts -> forced report_uncertainty."""
        state = _make_meta_state(
            meta_attempt_count=2,
            mean_relevance_score=0.05,
            chunk_relevance_scores=[0.05],
            retrieved_chunks=[_chunk()],
        )
        config = _make_config(settings_obj=self._settings(max_attempts=2))

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] is None
        assert result["meta_attempt_count"] == 2

    @pytest.mark.asyncio
    async def test_strategy_dedup(self):
        """FR-015: already-tried strategy falls through to next untried."""
        chunks = [_chunk(), _chunk(chunk_id="c2")]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            chunk_relevance_scores=[0.1, 0.1],
            attempted_strategies={STRATEGY_WIDEN_SEARCH},
            alternative_queries=["alt1"],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        # Should fall through to CHANGE_COLLECTION (next in FALLBACK_ORDER)
        assert result["recovery_strategy"] == STRATEGY_CHANGE_COLLECTION

    @pytest.mark.asyncio
    async def test_all_strategies_exhausted(self):
        """FR-015: all strategies tried -> no viable strategy."""
        chunks = [_chunk(), _chunk(chunk_id="c2")]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            chunk_relevance_scores=[0.1, 0.1],
            attempted_strategies={
                STRATEGY_WIDEN_SEARCH,
                STRATEGY_CHANGE_COLLECTION,
                STRATEGY_RELAX_FILTERS,
            },
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] is None

    @pytest.mark.asyncio
    async def test_configurable_thresholds(self):
        """Thresholds from settings control strategy selection."""
        chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.15,
            chunk_relevance_scores=[0.15] * 5,
        )
        # With rel_thr=0.1, mean 0.15 is ABOVE threshold -> no WIDEN or CHANGE
        # With var_thr=0.5, stdev 0.0 is below -> report_uncertainty
        config = _make_config(settings_obj=self._settings(rel_thr=0.1, var_thr=0.5))

        result = await decide_strategy(state, config)

        assert result["recovery_strategy"] is None

    @pytest.mark.asyncio
    async def test_single_score_variance_zero(self):
        """< 2 scores -> variance 0.0; strategy based on mean only."""
        chunks = [_chunk()]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            chunk_relevance_scores=[0.1],
            alternative_queries=["alt"],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        # Low mean + 1 chunk (< 3) -> WIDEN_SEARCH
        assert result["recovery_strategy"] == STRATEGY_WIDEN_SEARCH

    @pytest.mark.asyncio
    async def test_identical_scores_stdev_zero(self):
        """All identical scores -> stdev=0.0; low mean path selects based on chunk count."""
        chunks = [_chunk(chunk_id=f"c{i}") for i in range(5)]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.05,
            chunk_relevance_scores=[0.05, 0.05, 0.05, 0.05, 0.05],
            alternative_queries=["alt"],
        )
        config = _make_config(settings_obj=self._settings())

        result = await decide_strategy(state, config)

        # Low mean + 5 chunks (>= 3) -> CHANGE_COLLECTION
        assert result["recovery_strategy"] == STRATEGY_CHANGE_COLLECTION


# ====================
# report_uncertainty
# ====================

class TestReportUncertainty:
    """Tests for report_uncertainty node (FR-007, FR-008)."""

    @pytest.mark.asyncio
    async def test_generates_uncertainty_report(self):
        """Core path: LLM generates uncertainty report."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content="I could not find relevant information about quantum entanglement in the searched collections."
        )

        chunks = [_chunk(collection="physics")]
        state = _make_meta_state(
            retrieved_chunks=chunks,
            mean_relevance_score=0.1,
            meta_attempt_count=2,
        )
        config = _make_config(llm=llm)

        result = await report_uncertainty(state, config)

        assert result["answer"] is not None
        assert len(result["answer"]) > 0
        assert result["uncertainty_reason"] is not None
        assert "0.100" in result["uncertainty_reason"]

    @pytest.mark.asyncio
    async def test_includes_collections_searched(self):
        """Report includes which collections were searched."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(content="Report with collections.")

        chunks = [_chunk(collection="physics"), _chunk(chunk_id="c2", collection="biology")]
        state = _make_meta_state(retrieved_chunks=chunks)
        config = _make_config(llm=llm)

        await report_uncertainty(state, config)

        # Verify the LLM was called with context that includes collection names
        call_args = llm.ainvoke.call_args[0][0]
        user_msg = call_args[1]["content"]
        assert "physics" in user_msg or "biology" in user_msg

    @pytest.mark.asyncio
    async def test_no_fabrication_llm_failure(self):
        """FR-008: on LLM failure, static template does NOT fabricate."""
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("LLM down")

        state = _make_meta_state(sub_question="My question")
        config = _make_config(llm=llm)

        result = await report_uncertainty(state, config)

        assert "My question" in result["answer"]
        assert "Suggestions" in result["answer"]
        assert "fabricat" not in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_includes_suggestions(self):
        """Report includes actionable suggestions for the user."""
        llm = AsyncMock()
        llm.ainvoke.side_effect = RuntimeError("LLM down")

        state = _make_meta_state()
        config = _make_config(llm=llm)

        result = await report_uncertainty(state, config)

        assert "rephras" in result["answer"].lower()
        assert "collection" in result["answer"].lower()


# ====================
# Strategy helpers
# ====================

class TestBuildModifiedState:
    def test_widen_search(self):
        result = _build_modified_state_widen(["alt1", "alt2"])
        assert result["selected_collections"] == "ALL"
        assert result["top_k_retrieval"] == 40
        assert result["alternative_queries"] == ["alt1", "alt2"]

    def test_change_collection(self):
        result = _build_modified_state_change_collection(["alt1", "alt2"])
        assert result["selected_collections"] == "ROTATE"
        assert result["sub_question"] == "alt1"

    def test_change_collection_empty_queries(self):
        result = _build_modified_state_change_collection([])
        assert result["sub_question"] == ""

    def test_relax_filters(self):
        result = _build_modified_state_relax()
        assert result["top_k_retrieval"] == 40
        assert result["payload_filters"] is None
        assert result["top_k_rerank"] == 10
