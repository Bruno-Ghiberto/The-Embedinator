"""Edge functions (routing logic) for the MetaReasoningGraph.

Single conditional edge: route_after_strategy.
"""

from __future__ import annotations

from backend.agent.state import MetaReasoningState


def route_after_strategy(state: MetaReasoningState) -> str:
    """Route after decide_strategy.

    Returns:
        "retry": recovery_strategy is set -> END (modified_state ready for
                 ResearchGraph to re-enter with new parameters)
        "report": recovery_strategy is None -> report_uncertainty
    """
    if state.get("recovery_strategy"):
        return "retry"
    return "report"
