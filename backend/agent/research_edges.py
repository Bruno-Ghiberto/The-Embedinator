"""Edge functions (routing logic) for the ResearchGraph.

Edge functions determine which node to execute next based on the current state.
These are separate from edges.py which contains ConversationGraph edges.
"""

from __future__ import annotations

import time

import structlog

from backend.agent.state import ResearchState
from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)


def should_continue_loop(state: ResearchState) -> str:
    """Determine whether the orchestrator loop should continue.

    IMPORTANT (F1): Confidence is checked FIRST. If confidence >= threshold,
    route to collect_answer regardless of remaining budget. Then check budget
    exhaustion, then tool exhaustion.

    CONFIDENCE SCALE MISMATCH: config.confidence_threshold is int 0-100,
    but state["confidence_score"] is float 0.0-1.0. Convert threshold
    by dividing by 100.

    Returns:
        "sufficient": confidence >= threshold -> collect_answer
        "exhausted": budget or tools exhausted -> meta_reasoning or fallback
        "continue": keep looping
    """
    confidence = state["confidence_score"]
    threshold = settings.confidence_threshold / 100  # int 60 -> float 0.6

    # 1. Confidence check FIRST (F1)
    if confidence >= threshold:
        logger.info(
            "agent_loop_exit_sufficient",
            confidence=confidence,
            threshold=threshold,
            session_id=state["session_id"],
        )
        return "sufficient"

    # 2. Wall-clock deadline (BUG-008)
    loop_start = state.get("loop_start_time")
    if loop_start is not None:
        elapsed = time.monotonic() - loop_start
        if elapsed >= settings.max_loop_seconds:
            logger.warning(
                "agent_loop_exit_deadline",
                elapsed_secs=round(elapsed, 1),
                max_loop_seconds=settings.max_loop_seconds,
                session_id=state["session_id"],
            )
            return "exhausted"

    # 3. Budget exhaustion
    if state["iteration_count"] >= settings.max_iterations or state["tool_call_count"] >= settings.max_tool_calls:
        logger.info(
            "agent_loop_exit_exhausted",
            iteration_count=state["iteration_count"],
            tool_call_count=state["tool_call_count"],
            confidence=confidence,
            session_id=state["session_id"],
        )
        return "exhausted"

    # 3. Tool exhaustion -- orchestrator produced no new tool calls (F4)
    # If chunks were retrieved, route to collect_answer so the LLM can synthesize
    # a grounded response. Only fall back if there is truly nothing to work with.
    if state.get("_no_new_tools", False):
        if state.get("retrieved_chunks"):
            logger.info(
                "agent_loop_exit_tool_exhaustion",
                confidence=confidence,
                chunk_count=len(state["retrieved_chunks"]),
                routing="sufficient",
                session_id=state["session_id"],
            )
            return "sufficient"
        logger.info(
            "agent_loop_exit_tool_exhaustion",
            confidence=confidence,
            chunk_count=0,
            routing="exhausted",
            session_id=state["session_id"],
        )
        return "exhausted"

    return "continue"


def route_after_compress_check(state: ResearchState) -> str:
    """Route after context size check.

    Reads the _needs_compression flag set by should_compress_context node (F3).

    Returns:
        "compress": Token count exceeds threshold, compress before continuing
        "continue": Token count within budget, loop back to orchestrator
    """
    if state.get("_needs_compression", False):
        return "compress"
    return "continue"
