"""Contract tests for the Agent Layer (spec-11, US1).

Verifies:
- State schema field counts and types (FR-001, FR-002)
- ConversationGraph node signatures: 11 nodes (FR-003, FR-004)
- ResearchGraph node signatures: 5 nodes (FR-007)
- MetaReasoningGraph node signatures: 4 nodes (FR-007)
- Edge function signatures: 7 functions across 3 files (FR-005)
- Tool factory signature and return type (FR-006)
- Graph builder callability (FR-019)
- Confidence scoring function existence (FR-002)
"""
from __future__ import annotations

import inspect
from typing import Any, get_type_hints


# ---------------------------------------------------------------------------
# T014 — State schema field tests (FR-001, FR-002)
# ---------------------------------------------------------------------------

class TestConversationStateSchema:
    """Verify ConversationState TypedDict fields and types."""

    def test_field_count(self):
        """ConversationState must have exactly 14 fields (13 original + stage_timings from spec-14)."""
        from backend.agent.state import ConversationState
        hints = get_type_hints(ConversationState)
        assert len(hints) == 14, (
            f"Expected 14 fields, got {len(hints)}: {list(hints.keys())}"
        )

    def test_required_fields_present(self):
        from backend.agent.state import ConversationState
        hints = get_type_hints(ConversationState)
        required = {
            "session_id", "messages", "query_analysis", "sub_answers",
            "selected_collections", "llm_model", "embed_model", "intent",
            "final_response", "citations", "groundedness_result",
            "confidence_score", "iteration_count",
            "stage_timings",  # FR-005 spec-14
        }
        assert required == set(hints.keys()), (
            f"Missing: {required - set(hints.keys())}; "
            f"Extra: {set(hints.keys()) - required}"
        )

    def test_confidence_score_is_int(self):
        """FR-002: ConversationState.confidence_score is int (0-100 user-facing scale)."""
        from backend.agent.state import ConversationState
        hints = get_type_hints(ConversationState)
        assert hints["confidence_score"] is int, (
            f"Expected int, got {hints['confidence_score']}"
        )


class TestResearchStateSchema:
    """Verify ResearchState TypedDict fields."""

    def test_field_count(self):
        """ResearchState must have exactly 17 fields (16 original + stage_timings from spec-14)."""
        from backend.agent.state import ResearchState
        hints = get_type_hints(ResearchState)
        assert len(hints) == 17, (
            f"Expected 17 fields, got {len(hints)}: {list(hints.keys())}"
        )

    def test_private_flag_fields_present(self):
        """ResearchState must include _no_new_tools and _needs_compression."""
        from backend.agent.state import ResearchState
        hints = get_type_hints(ResearchState)
        assert "_no_new_tools" in hints, "_no_new_tools field missing"
        assert "_needs_compression" in hints, "_needs_compression field missing"

    def test_confidence_score_is_float(self):
        """FR-002: ResearchState.confidence_score is float (0.0-1.0 internal scale)."""
        from backend.agent.state import ResearchState
        hints = get_type_hints(ResearchState)
        assert hints["confidence_score"] is float, (
            f"Expected float, got {hints['confidence_score']}"
        )


class TestMetaReasoningStateSchema:
    """Verify MetaReasoningState TypedDict fields."""

    def test_field_count(self):
        """MetaReasoningState must have exactly 11 fields."""
        from backend.agent.state import MetaReasoningState
        hints = get_type_hints(MetaReasoningState)
        assert len(hints) == 11, (
            f"Expected 11 fields, got {len(hints)}: {list(hints.keys())}"
        )

    def test_attempted_strategies_present(self):
        """MetaReasoningState must include attempted_strategies (FR-015 dedup)."""
        from backend.agent.state import MetaReasoningState
        hints = get_type_hints(MetaReasoningState)
        assert "attempted_strategies" in hints, "attempted_strategies field missing"


class TestDualConfidenceScale:
    """Pattern 6: Verify dual confidence scale across state schemas."""

    def test_conversation_state_uses_int_scale(self):
        """ConversationState.confidence_score is int (0-100 user-facing)."""
        from backend.agent.state import ConversationState
        hints = get_type_hints(ConversationState)
        assert hints["confidence_score"] is int

    def test_research_state_uses_float_scale(self):
        """ResearchState.confidence_score is float (0.0-1.0 internal)."""
        from backend.agent.state import ResearchState
        hints = get_type_hints(ResearchState)
        assert hints["confidence_score"] is float

    def test_scales_are_different_types(self):
        """The two scales must be different Python types."""
        from backend.agent.state import ConversationState, ResearchState
        conv_hints = get_type_hints(ConversationState)
        res_hints = get_type_hints(ResearchState)
        assert conv_hints["confidence_score"] is not res_hints["confidence_score"]


# ---------------------------------------------------------------------------
# T015 — ConversationGraph node signature tests (FR-003, FR-004)
# ---------------------------------------------------------------------------

class TestConversationGraphNodes:
    """Verify all 11 ConversationGraph node signatures in nodes.py."""

    # Pattern A: *, llm: Any (KEYWORD_ONLY DI)
    def test_classify_intent_keyword_only_llm(self):
        from backend.agent.nodes import classify_intent
        sig = inspect.signature(classify_intent)
        params = sig.parameters
        assert "llm" in params, "classify_intent missing 'llm' param"
        assert params["llm"].kind == inspect.Parameter.KEYWORD_ONLY, (
            "'llm' must be KEYWORD_ONLY after *"
        )

    def test_rewrite_query_keyword_only_llm(self):
        from backend.agent.nodes import rewrite_query
        sig = inspect.signature(rewrite_query)
        params = sig.parameters
        assert "llm" in params, "rewrite_query missing 'llm' param"
        assert params["llm"].kind == inspect.Parameter.KEYWORD_ONLY

    # Pattern A with default: *, llm: Any = None
    def test_verify_groundedness_keyword_only_llm_with_default(self):
        from backend.agent.nodes import verify_groundedness
        sig = inspect.signature(verify_groundedness)
        params = sig.parameters
        assert "llm" in params, "verify_groundedness missing 'llm' param"
        assert params["llm"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["llm"].default is None, "verify_groundedness 'llm' default must be None"

    def test_validate_citations_keyword_only_reranker_with_default(self):
        from backend.agent.nodes import validate_citations
        sig = inspect.signature(validate_citations)
        params = sig.parameters
        assert "reranker" in params, "validate_citations missing 'reranker' param"
        assert params["reranker"].kind == inspect.Parameter.KEYWORD_ONLY
        assert params["reranker"].default is None

    # Pattern B: **kwargs (VAR_KEYWORD DI)
    def test_init_session_var_keyword(self):
        from backend.agent.nodes import init_session
        sig = inspect.signature(init_session)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "init_session must accept **kwargs"
        )

    def test_fan_out_var_keyword(self):
        from backend.agent.nodes import fan_out
        sig = inspect.signature(fan_out)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "fan_out must accept **kwargs"
        )

    def test_aggregate_answers_var_keyword(self):
        from backend.agent.nodes import aggregate_answers
        sig = inspect.signature(aggregate_answers)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "aggregate_answers must accept **kwargs"
        )

    def test_summarize_history_var_keyword(self):
        from backend.agent.nodes import summarize_history
        sig = inspect.signature(summarize_history)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "summarize_history must accept **kwargs"
        )

    def test_format_response_var_keyword(self):
        from backend.agent.nodes import format_response
        sig = inspect.signature(format_response)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "format_response must accept **kwargs"
        )

    def test_handle_collection_mgmt_var_keyword(self):
        from backend.agent.nodes import handle_collection_mgmt
        sig = inspect.signature(handle_collection_mgmt)
        param_kinds = [p.kind for p in sig.parameters.values()]
        assert inspect.Parameter.VAR_KEYWORD in param_kinds, (
            "handle_collection_mgmt must accept **kwargs"
        )

    # Pattern C: no DI
    def test_request_clarification_no_di(self):
        """request_clarification takes only state (no DI injection)."""
        from backend.agent.nodes import request_clarification
        sig = inspect.signature(request_clarification)
        params = sig.parameters
        # Only 'state' param, no kwargs or keyword-only params
        assert "state" in params, "request_clarification must have 'state' param"
        has_kwargs = any(
            p.kind in (inspect.Parameter.VAR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
            for p in params.values()
        )
        assert not has_kwargs, (
            "request_clarification should have no DI (no **kwargs or keyword-only params)"
        )

    def test_all_nodes_callable(self):
        """All 11 ConversationGraph nodes are callable."""
        from backend.agent import nodes
        node_names = [
            "init_session", "classify_intent", "rewrite_query",
            "request_clarification", "fan_out", "aggregate_answers",
            "verify_groundedness", "validate_citations", "summarize_history",
            "format_response", "handle_collection_mgmt",
        ]
        for name in node_names:
            assert hasattr(nodes, name), f"nodes.py missing: {name}"
            assert callable(getattr(nodes, name)), f"{name} is not callable"


# ---------------------------------------------------------------------------
# T016 — ResearchGraph node signature tests (FR-007)
# ---------------------------------------------------------------------------

class TestResearchGraphNodes:
    """Verify all 5 ResearchGraph node signatures in research_nodes.py."""

    def _assert_has_config_param(self, func_name: str, func) -> None:
        """Helper: assert function has 'config' as POSITIONAL_OR_KEYWORD with default None."""
        sig = inspect.signature(func)
        params = sig.parameters
        assert "config" in params, f"{func_name} missing 'config' param"
        config_param = params["config"]
        assert config_param.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD, (
            f"{func_name} 'config' must be POSITIONAL_OR_KEYWORD (not keyword-only)"
        )
        assert config_param.default is None, (
            f"{func_name} 'config' default must be None"
        )

    def test_orchestrator_has_config(self):
        from backend.agent.research_nodes import orchestrator
        self._assert_has_config_param("orchestrator", orchestrator)

    def test_tools_node_has_config(self):
        from backend.agent.research_nodes import tools_node
        self._assert_has_config_param("tools_node", tools_node)

    def test_compress_context_has_config(self):
        from backend.agent.research_nodes import compress_context
        self._assert_has_config_param("compress_context", compress_context)

    def test_collect_answer_has_config(self):
        from backend.agent.research_nodes import collect_answer
        self._assert_has_config_param("collect_answer", collect_answer)

    def test_fallback_response_no_config(self):
        """fallback_response takes only state (no config param)."""
        from backend.agent.research_nodes import fallback_response
        sig = inspect.signature(fallback_response)
        params = sig.parameters
        assert "state" in params, "fallback_response must have 'state' param"
        assert "config" not in params, (
            "fallback_response must NOT have 'config' param"
        )

    def test_all_nodes_exist(self):
        """All 5 ResearchGraph nodes are importable from research_nodes.py."""
        from backend.agent import research_nodes
        for name in ["orchestrator", "tools_node", "compress_context",
                     "collect_answer", "fallback_response"]:
            assert hasattr(research_nodes, name), f"research_nodes.py missing: {name}"


# ---------------------------------------------------------------------------
# T017 — MetaReasoningGraph node signature tests (FR-007)
# ---------------------------------------------------------------------------

class TestMetaReasoningGraphNodes:
    """Verify all 4 MetaReasoningGraph node signatures in meta_reasoning_nodes.py."""

    def _assert_has_config_param(self, func_name: str, func) -> None:
        sig = inspect.signature(func)
        params = sig.parameters
        assert "config" in params, f"{func_name} missing 'config' param"

    def test_generate_alternative_queries_has_config(self):
        from backend.agent.meta_reasoning_nodes import generate_alternative_queries
        self._assert_has_config_param("generate_alternative_queries",
                                       generate_alternative_queries)

    def test_evaluate_retrieval_quality_has_config(self):
        from backend.agent.meta_reasoning_nodes import evaluate_retrieval_quality
        self._assert_has_config_param("evaluate_retrieval_quality",
                                       evaluate_retrieval_quality)

    def test_decide_strategy_has_config(self):
        from backend.agent.meta_reasoning_nodes import decide_strategy
        self._assert_has_config_param("decide_strategy", decide_strategy)

    def test_report_uncertainty_has_config(self):
        from backend.agent.meta_reasoning_nodes import report_uncertainty
        self._assert_has_config_param("report_uncertainty", report_uncertainty)

    def test_all_nodes_from_correct_module(self):
        """Nodes come from meta_reasoning_nodes.py, NOT nodes.py."""
        import backend.agent.meta_reasoning_nodes as mrn
        for name in ["generate_alternative_queries", "evaluate_retrieval_quality",
                     "decide_strategy", "report_uncertainty"]:
            assert hasattr(mrn, name), f"meta_reasoning_nodes.py missing: {name}"
            assert callable(getattr(mrn, name)), f"{name} is not callable"


# ---------------------------------------------------------------------------
# T018 — Edge function tests (FR-005)
# ---------------------------------------------------------------------------

class TestConversationEdges:
    """Verify edge functions in edges.py."""

    def test_route_intent_exists(self):
        from backend.agent.edges import route_intent
        assert callable(route_intent)

    def test_route_intent_takes_state(self):
        from backend.agent.edges import route_intent
        sig = inspect.signature(route_intent)
        assert "state" in sig.parameters

    def test_should_clarify_exists(self):
        from backend.agent.edges import should_clarify
        assert callable(should_clarify)

    def test_should_clarify_takes_state(self):
        from backend.agent.edges import should_clarify
        sig = inspect.signature(should_clarify)
        assert "state" in sig.parameters

    def test_route_after_rewrite_exists(self):
        from backend.agent.edges import route_after_rewrite
        assert callable(route_after_rewrite)

    def test_route_after_rewrite_takes_state(self):
        from backend.agent.edges import route_after_rewrite
        sig = inspect.signature(route_after_rewrite)
        assert "state" in sig.parameters

    def test_route_fan_out_exists(self):
        from backend.agent.edges import route_fan_out
        assert callable(route_fan_out)

    def test_route_fan_out_takes_state(self):
        from backend.agent.edges import route_fan_out
        sig = inspect.signature(route_fan_out)
        assert "state" in sig.parameters


class TestResearchEdges:
    """Verify edge functions in research_edges.py."""

    def test_should_continue_loop_exists(self):
        from backend.agent.research_edges import should_continue_loop
        assert callable(should_continue_loop)

    def test_should_continue_loop_takes_state(self):
        from backend.agent.research_edges import should_continue_loop
        sig = inspect.signature(should_continue_loop)
        assert "state" in sig.parameters

    def test_route_after_compress_check_exists(self):
        from backend.agent.research_edges import route_after_compress_check
        assert callable(route_after_compress_check)

    def test_route_after_compress_check_takes_state(self):
        from backend.agent.research_edges import route_after_compress_check
        sig = inspect.signature(route_after_compress_check)
        assert "state" in sig.parameters


class TestMetaReasoningEdges:
    """Verify edge functions in meta_reasoning_edges.py."""

    def test_route_after_strategy_exists(self):
        from backend.agent.meta_reasoning_edges import route_after_strategy
        assert callable(route_after_strategy)

    def test_route_after_strategy_takes_state(self):
        from backend.agent.meta_reasoning_edges import route_after_strategy
        sig = inspect.signature(route_after_strategy)
        assert "state" in sig.parameters


class TestAllEdgeFunctions:
    """Cross-file: verify all 7 edge functions exist."""

    def test_seven_edge_functions_importable(self):
        from backend.agent.edges import (
            route_intent, should_clarify, route_after_rewrite, route_fan_out,
        )
        from backend.agent.research_edges import (
            should_continue_loop, route_after_compress_check,
        )
        from backend.agent.meta_reasoning_edges import route_after_strategy

        all_edges = [
            route_intent, should_clarify, route_after_rewrite, route_fan_out,
            should_continue_loop, route_after_compress_check, route_after_strategy,
        ]
        assert len(all_edges) == 7
        for fn in all_edges:
            assert callable(fn), f"{fn} is not callable"


# ---------------------------------------------------------------------------
# T019 — Tool factory tests (FR-006)
# ---------------------------------------------------------------------------

class TestToolFactory:
    """Verify create_research_tools in tools.py."""

    def test_create_research_tools_exists(self):
        from backend.agent.tools import create_research_tools
        assert callable(create_research_tools)

    def test_create_research_tools_params(self):
        """Factory must have params: searcher, reranker, parent_store."""
        from backend.agent.tools import create_research_tools
        sig = inspect.signature(create_research_tools)
        params = list(sig.parameters.keys())
        assert params == ["searcher", "reranker", "parent_store"], (
            f"Expected ['searcher', 'reranker', 'parent_store'], got {params}"
        )

    def test_create_research_tools_return_annotation(self):
        """Factory return annotation must be list (or 'list' string when annotations are deferred)."""
        from backend.agent.tools import create_research_tools
        sig = inspect.signature(create_research_tools)
        ret = sig.return_annotation
        # Annotation may be the type `list` or the string `'list'` when
        # `from __future__ import annotations` is active in the source file.
        assert ret is list or ret == list or ret == "list", (
            f"Return annotation must be list, got {ret!r}"
        )


# ---------------------------------------------------------------------------
# T020 — Graph builder tests (FR-019)
# ---------------------------------------------------------------------------

class TestGraphBuilders:
    """Verify 3 graph builder functions exist and are callable."""

    def test_build_conversation_graph_exists(self):
        from backend.agent.conversation_graph import build_conversation_graph
        assert callable(build_conversation_graph)

    def test_build_research_graph_exists(self):
        from backend.agent.research_graph import build_research_graph
        assert callable(build_research_graph)

    def test_build_meta_reasoning_graph_exists(self):
        from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph
        assert callable(build_meta_reasoning_graph)

    def test_all_builders_are_functions(self):
        """All three builders are top-level callable functions."""
        from backend.agent.conversation_graph import build_conversation_graph
        from backend.agent.research_graph import build_research_graph
        from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

        for builder in [build_conversation_graph, build_research_graph,
                        build_meta_reasoning_graph]:
            assert inspect.isfunction(builder), f"{builder} is not a function"


# ---------------------------------------------------------------------------
# T021 — Confidence scoring tests (FR-002)
# ---------------------------------------------------------------------------

class TestConfidenceScoring:
    """Verify compute_confidence in confidence.py."""

    def test_compute_confidence_exists(self):
        from backend.agent.confidence import compute_confidence
        assert callable(compute_confidence)

    def test_compute_confidence_is_function(self):
        from backend.agent.confidence import compute_confidence
        assert inspect.isfunction(compute_confidence)

    def test_compute_confidence_params(self):
        """compute_confidence must accept chunks as first positional param."""
        from backend.agent.confidence import compute_confidence
        sig = inspect.signature(compute_confidence)
        params = list(sig.parameters.keys())
        assert "chunks" in params, f"compute_confidence missing 'chunks' param; got {params}"

    def test_compute_confidence_list_input_returns_float(self):
        """New path: list[RetrievedChunk] returns float 0.0-1.0."""
        from backend.agent.confidence import compute_confidence
        from backend.agent.schemas import RetrievedChunk
        chunk = RetrievedChunk(
            chunk_id="c1",
            text="test",
            source_file="file.txt",
            page=None,
            breadcrumb="section",
            parent_id="p1",
            collection="col1",
            dense_score=0.8,
            sparse_score=0.5,
            rerank_score=0.75,
        )
        result = compute_confidence([chunk])
        assert isinstance(result, float), f"Expected float, got {type(result)}"
        assert 0.0 <= result <= 1.0, f"Float score out of range: {result}"

    def test_compute_confidence_dict_input_returns_int(self):
        """Legacy path: list[dict] with 'relevance_score' returns int 0-100."""
        from backend.agent.confidence import compute_confidence
        passages = [{"relevance_score": 0.9}, {"relevance_score": 0.7}]
        result = compute_confidence(passages)
        assert isinstance(result, int), f"Expected int, got {type(result)}"
        assert 0 <= result <= 100, f"Int score out of range: {result}"
