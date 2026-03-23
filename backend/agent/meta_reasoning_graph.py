"""MetaReasoningGraph -- Layer 3 of the three-layer LangGraph agent.

Failure diagnosis and recovery when the ResearchGraph exhausts its
iteration/tool budget without reaching confidence threshold.

Flow:
  START -> generate_alternative_queries -> evaluate_retrieval_quality
        -> decide_strategy -> [retry: END | report: report_uncertainty -> END]
"""
from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from backend.agent.meta_reasoning_edges import route_after_strategy
from backend.agent.meta_reasoning_nodes import (
    decide_strategy,
    evaluate_retrieval_quality,
    generate_alternative_queries,
    report_uncertainty,
)
from backend.agent.state import MetaReasoningState


def build_meta_reasoning_graph() -> Any:
    """Build and compile the MetaReasoningGraph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(MetaReasoningState)

    # Nodes
    graph.add_node("generate_alternative_queries", generate_alternative_queries)
    graph.add_node("evaluate_retrieval_quality", evaluate_retrieval_quality)
    graph.add_node("decide_strategy", decide_strategy)
    graph.add_node("report_uncertainty", report_uncertainty)

    # Edges
    graph.add_edge(START, "generate_alternative_queries")
    graph.add_edge("generate_alternative_queries", "evaluate_retrieval_quality")
    graph.add_edge("evaluate_retrieval_quality", "decide_strategy")
    graph.add_conditional_edges("decide_strategy", route_after_strategy, {
        "retry": END,                # modified_state ready; ResearchGraph re-enters
        "report": "report_uncertainty",
    })
    graph.add_edge("report_uncertainty", END)

    return graph.compile()
