"""ResearchGraph -- Layer 2 of the three-layer LangGraph agent.

Per-sub-question worker spawned via Send("research", payload) from
ConversationGraph's route_fan_out() edge. Runs an LLM-driven orchestrator
loop: orchestrator -> tools -> compress check -> (compress | orchestrator).
"""

from __future__ import annotations

import time
from typing import Any

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import RetryPolicy

from backend.agent.research_edges import route_after_compress_check, should_continue_loop
from backend.agent.research_nodes import (
    collect_answer,
    compress_context,
    fallback_response,
    orchestrator,
    should_compress_context,
    tools_node,
)
from backend.agent.state import ResearchState

logger = structlog.get_logger().bind(component=__name__)


def build_research_graph(
    tools: list,
    meta_reasoning_graph: Any = None,
) -> Any:
    """Build and compile the ResearchGraph.

    Args:
        tools: List of LangChain tool objects returned by create_research_tools().
        meta_reasoning_graph: Optional compiled MetaReasoningGraph.
            If None, budget exhaustion routes to fallback_response.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(ResearchState)

    # Bind tools into node closures via functools.partial or config
    graph.add_node(
        "orchestrator", orchestrator, retry_policy=RetryPolicy(max_attempts=3, initial_interval=1.0, backoff_factor=2.0)
    )
    graph.add_node("tools", tools_node, retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.5))
    graph.add_node("should_compress_context", should_compress_context)
    graph.add_node("compress_context", compress_context, retry_policy=RetryPolicy(max_attempts=2, initial_interval=0.5))
    graph.add_node("collect_answer", collect_answer, retry_policy=RetryPolicy(max_attempts=2, initial_interval=1.0))
    graph.add_node("fallback_response", fallback_response)

    if meta_reasoning_graph:

        async def meta_reasoning_mapper(state: ResearchState, config: RunnableConfig = None) -> dict:
            """Map ResearchState -> MetaReasoningState, invoke subgraph, map back."""
            _t0_meta = time.perf_counter()

            # Forward map: ResearchState -> MetaReasoningState input
            meta_input = {
                "sub_question": state["sub_question"],
                "retrieved_chunks": state["retrieved_chunks"],
                "alternative_queries": [],
                "mean_relevance_score": 0.0,
                "chunk_relevance_scores": [],
                "meta_attempt_count": state.get("_meta_attempt_count", 0),
                "recovery_strategy": None,
                "modified_state": None,
                "answer": None,
                "uncertainty_reason": None,
                "attempted_strategies": state.get("_attempted_strategies", set()),
            }

            # Invoke the compiled MetaReasoningGraph subgraph
            try:
                result = await meta_reasoning_graph.ainvoke(meta_input, config=config)
            except Exception as exc:
                # FR-017: infrastructure error during subgraph -> report_uncertainty
                logger.warning("agent_meta_reasoning_infra_error", error=str(exc))
                _duration_ms = round((time.perf_counter() - _t0_meta) * 1000, 1)
                _prior = state.get("stage_timings", {})
                return {
                    "answer": (
                        f"I was unable to complete the search due to an infrastructure "
                        f"error: {exc}. Please try again later."
                    ),
                    "confidence_score": 0.0,
                    "stage_timings": {
                        **_prior,
                        "meta_reasoning": {
                            "duration_ms": _duration_ms,
                            "failed": True,
                        },
                    },
                }

            _duration_ms = round((time.perf_counter() - _t0_meta) * 1000, 1)
            _prior = state.get("stage_timings", {})

            # Reverse map: MetaReasoningState result -> ResearchState updates
            strategy = result.get("recovery_strategy")

            if strategy is not None:
                # Recovery path: apply modified_state back to ResearchState
                modified = result.get("modified_state", {})
                updates = {
                    "_meta_attempt_count": result.get("meta_attempt_count", 0),
                    "_attempted_strategies": result.get("attempted_strategies", set()),
                    "stage_timings": {
                        **_prior,
                        "meta_reasoning": {"duration_ms": _duration_ms},
                    },
                }

                collections = modified.get("selected_collections")
                if collections == "ALL":
                    # Iterate all collections -- set empty list to signal "search all"
                    updates["selected_collections"] = []
                elif collections == "ROTATE":
                    # Next different collection
                    current = state.get("selected_collections", [])
                    if len(current) <= 1:
                        # Only one collection; rotation impossible -> uncertainty
                        return {
                            "answer": result.get("answer", "Unable to find relevant information."),
                            "confidence_score": 0.0,
                            "stage_timings": {
                                **_prior,
                                "meta_reasoning": {"duration_ms": _duration_ms},
                            },
                        }
                    # Rotate: move first collection to end
                    updates["selected_collections"] = current[1:] + current[:1]

                if "sub_question" in modified:
                    updates["sub_question"] = modified["sub_question"]
                if "top_k_retrieval" in modified:
                    updates["_top_k_retrieval"] = modified["top_k_retrieval"]
                if "top_k_rerank" in modified:
                    updates["_top_k_rerank"] = modified["top_k_rerank"]
                if "payload_filters" in modified:
                    updates["_payload_filters"] = modified["payload_filters"]

                # Reset loop state for retry
                updates["retrieved_chunks"] = []
                updates["retrieval_keys"] = set()
                updates["tool_call_count"] = 0
                updates["iteration_count"] = 0
                updates["confidence_score"] = 0.0
                updates["context_compressed"] = False
                updates["_no_new_tools"] = False
                updates["_needs_compression"] = False

                return updates
            else:
                # Uncertainty path: propagate answer back
                return {
                    "answer": result.get("answer", "Unable to find relevant information."),
                    "confidence_score": 0.0,
                    "uncertainty_reason": result.get("uncertainty_reason"),
                    "stage_timings": {
                        **_prior,
                        "meta_reasoning": {"duration_ms": _duration_ms},
                    },
                }

        graph.add_node("meta_reasoning", meta_reasoning_mapper)

    graph.add_edge(START, "orchestrator")

    exhausted_target = "meta_reasoning" if meta_reasoning_graph else "fallback_response"
    graph.add_conditional_edges(
        "orchestrator",
        should_continue_loop,
        {
            "continue": "tools",
            "sufficient": "collect_answer",
            "exhausted": exhausted_target,
        },
    )

    graph.add_edge("tools", "should_compress_context")
    graph.add_conditional_edges(
        "should_compress_context",
        route_after_compress_check,
        {
            "compress": "compress_context",
            "continue": "orchestrator",
        },
    )
    graph.add_edge("compress_context", "orchestrator")
    graph.add_edge("collect_answer", END)
    graph.add_edge("fallback_response", END)

    if meta_reasoning_graph:
        graph.add_edge("meta_reasoning", "orchestrator")

    return graph.compile()
