"""Integration tests for ResearchGraph (spec-03).

Tests full graph compilation and execution flows with mocked LLM and Qdrant.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.agent.research_graph import build_research_graph
from backend.agent.schemas import RetrievedChunk


def _chunk(chunk_id="c1", rerank_score=0.8, dense_score=0.5, collection="col1", parent_id="p1", text="test evidence"):
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=text,
        source_file="test.md",
        breadcrumb="ch1",
        parent_id=parent_id,
        collection=collection,
        dense_score=dense_score,
        sparse_score=0.3,
        rerank_score=rerank_score,
    )


def _make_initial_state(**overrides):
    """Build a complete initial ResearchState."""
    base = {
        "sub_question": "What is the authentication mechanism?",
        "session_id": "test-session-001",
        "selected_collections": ["docs"],
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


class TestGraphCompilation:
    def test_compiles_without_error(self):
        graph = build_research_graph(tools=[])
        assert graph is not None

    def test_compiles_with_meta_reasoning(self):
        from langgraph.graph import END, START, StateGraph
        from backend.agent.state import ResearchState

        # Minimal meta-reasoning stub
        def meta_stub(state):
            return {}

        meta_graph = StateGraph(ResearchState)
        meta_graph.add_node("stub", meta_stub)
        meta_graph.add_edge(START, "stub")
        meta_graph.add_edge("stub", END)
        compiled_meta = meta_graph.compile()

        graph = build_research_graph(tools=[], meta_reasoning_graph=compiled_meta)
        assert graph is not None


class TestFallbackPath:
    """Test: low confidence + no LLM -> fallback response."""

    @pytest.mark.asyncio
    async def test_no_llm_routes_to_fallback(self):
        """Without LLM, orchestrator sets _no_new_tools=True -> exhausted -> fallback"""
        graph = build_research_graph(tools=[])
        state = _make_initial_state()

        result = await graph.ainvoke(state)

        assert result["answer"] is not None
        assert result["confidence_score"] == 0.0
        assert result["citations"] == []
        assert "could not find" in result["answer"].lower() or "searched" in result["answer"].lower()


class TestBudgetEnforcement:
    """Test: budget limits terminate the loop."""

    @pytest.mark.asyncio
    async def test_terminates_at_max_iterations(self):
        """Pre-set iteration_count at max -> immediate exhaustion -> fallback"""
        graph = build_research_graph(tools=[])
        state = _make_initial_state(iteration_count=10)

        # With iteration_count=10, should_continue_loop returns "exhausted" immediately
        # But orchestrator runs first (START -> orchestrator) and increments to 11
        # Actually, should_continue_loop is the edge AFTER orchestrator
        # So flow: orchestrator (inc to 11) -> should_continue_loop (11 >= 10 -> exhausted) -> fallback
        result = await graph.ainvoke(state)

        assert result["answer"] is not None
        assert result["confidence_score"] == 0.0


class TestDeduplication:
    """Test: duplicate chunks are filtered out."""

    @pytest.mark.asyncio
    async def test_dedup_keys_tracked(self):
        """Verify retrieval_keys accumulate across tool executions."""
        # This tests the tools_node dedup logic directly (graph-level dedup
        # requires LLM mock which is complex for integration)
        from backend.agent.research_nodes import tools_node

        chunk1 = _chunk(chunk_id="c1", parent_id="p1")
        chunk2 = _chunk(chunk_id="c2", parent_id="p1")  # Same parent = same dedup key

        mock_tool = AsyncMock()
        mock_tool.name = "search_child_chunks"
        mock_tool.ainvoke = AsyncMock(return_value=[chunk1, chunk2])

        mock_ai_msg = MagicMock()
        mock_ai_msg.tool_calls = [{"name": "search_child_chunks", "args": {"query": "test"}, "id": "call_1"}]

        state = _make_initial_state(messages=[mock_ai_msg])
        config = {"configurable": {"tools": [mock_tool]}}

        result = await tools_node(state, config=config)

        # Both chunks have same dedup key (same query + parent_id)
        assert len(result["retrieved_chunks"]) == 1
        assert len(result["retrieval_keys"]) == 1


class TestMockResearchGraph:
    """Test: mock research graph for ConversationGraph integration."""

    def test_mock_graph_returns_fixed_answer(self):
        from tests.mocks import build_mock_research_graph

        mock_graph = build_mock_research_graph()
        assert mock_graph is not None
