"""ConversationGraph -- Layer 1 of the three-layer LangGraph agent.

The outermost graph and entry point for every chat request. Manages the full
conversation lifecycle: session init, intent classification, query decomposition,
parallel dispatch to ResearchGraph, answer aggregation, verification, and
response formatting.
"""

from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from backend.agent.edges import route_after_rewrite, route_intent
from backend.agent.nodes import (
    aggregate_answers,
    classify_intent,
    format_response,
    handle_collection_mgmt,
    request_clarification,
    rewrite_query,
    summarize_history,
    validate_citations,
    verify_groundedness,
)
from backend.agent.state import ConversationState


def build_conversation_graph(
    research_graph: Any = None,
    checkpointer: Any = None,
    store: Any = None,
) -> Any:
    """Build and return the compiled ConversationGraph.

    Args:
        research_graph: The compiled ResearchGraph subgraph to dispatch
            sub-questions to via Send().
        checkpointer: Optional LangGraph checkpointer for session persistence
            (e.g. AsyncSqliteSaver). Defaults to MemorySaver() for tests.
        store: Optional LangGraph Store for cross-session memory
            (e.g. InMemoryStore). Passed to graph.compile().

    Returns:
        A compiled StateGraph ready to be invoked.
    """
    graph = StateGraph(ConversationState)

    # Core nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("research", research_graph)
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("summarize_history", summarize_history)
    graph.add_node("format_response", format_response, retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.5))

    # Phase 2 stubs
    graph.add_node(
        "verify_groundedness", verify_groundedness, retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.5)
    )
    graph.add_node("validate_citations", validate_citations)

    # Out-of-scope stub
    graph.add_node("handle_collection_mgmt", handle_collection_mgmt)

    # Edges
    graph.add_edge(START, "classify_intent")
    graph.add_conditional_edges(
        "classify_intent",
        route_intent,
        {
            "rag_query": "rewrite_query",
            "collection_mgmt": "handle_collection_mgmt",
            "ambiguous": "request_clarification",
        },
    )
    graph.add_edge("handle_collection_mgmt", END)
    graph.add_edge("request_clarification", "classify_intent")
    graph.add_conditional_edges("rewrite_query", route_after_rewrite, ["request_clarification", "research"])
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "summarize_history")
    graph.add_edge("summarize_history", "format_response")
    graph.add_edge("format_response", END)

    compile_kwargs: dict[str, Any] = {"checkpointer": checkpointer or MemorySaver()}
    if store is not None:
        compile_kwargs["store"] = store
    return graph.compile(**compile_kwargs)
