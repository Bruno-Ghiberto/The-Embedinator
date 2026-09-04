"""Edge functions (routing logic) for the ConversationGraph.

Edge functions determine which node to execute next based on the current state.
"""

from __future__ import annotations

from langgraph.graph import END
from langgraph.types import Send

from backend.agent.state import ConversationState, ResearchState

#: Stop a clarification cycle this many supersteps before the recursion limit would trip
#: (the LangGraph docs' RemainingSteps pattern) — the proactive bound; ``recursion_limit``
#: in chat.py stays the reactive backstop.
REMAINING_STEPS_FLOOR = 2


def route_after_clarification(state: ConversationState) -> str:
    """BUG-082: decide where a turn goes after ``request_clarification``.

    The node only calls ``interrupt()`` when ``rewrite_query`` produced a ``query_analysis``.
    On the direct "ambiguous" route it has none, returns its fallback answer, and the old
    unconditional edge sent that answer back to ``classify_intent`` to be re-classified until
    the recursion limit. End the turn when the fallback fired, and end it before the limit on
    any remaining cycle; otherwise continue to re-classify the user's clarification.
    """
    if state.get("query_analysis") is None:
        return END
    if state["remaining_steps"] <= REMAINING_STEPS_FLOOR:
        return END
    return "classify_intent"


def route_intent(state: ConversationState) -> str:
    """Route based on classified intent.

    Returns the intent string which LangGraph uses to select the next branch:
    - "rag_query" -> rewrite_query path
    - "collection_mgmt" -> collection management handler
    - "ambiguous" -> clarification path
    """
    return state["intent"]


def should_clarify(state: ConversationState) -> bool:
    """Determine whether clarification is needed.

    Returns True if the query analysis indicates the query is unclear
    AND the clarification round limit (2) has not been reached.
    Returns False if query_analysis is None (defensive guard).
    """
    query_analysis = state.get("query_analysis")
    if query_analysis is None:
        return False
    return not query_analysis.is_clear and state["iteration_count"] < 2


def route_after_rewrite(state: ConversationState) -> list[Send] | str:
    """Combined routing from rewrite_query: clarify or fan-out to research.

    If the user has already specified collections to search, skip clarification
    and go straight to research — we have enough context to retrieve.
    Otherwise, if clarification is needed (query unclear + iteration_count < 2),
    returns "request_clarification". Otherwise, delegates to route_fan_out()
    which returns Send() objects for parallel ResearchGraph dispatch.

    This combined function is necessary because LangGraph does not support
    two add_conditional_edges from the same source node.
    """
    # User-specified collections mean we have enough context to search
    if state.get("selected_collections"):
        return route_fan_out(state)
    if should_clarify(state):
        return "request_clarification"
    return route_fan_out(state)


def route_fan_out(state: ConversationState) -> list[Send]:
    """Create a Send() for each sub-question to dispatch to ResearchGraph.

    Falls back to the original query as the sole sub-question if the
    sub_questions list is empty. Populates all ResearchState fields in
    each Send() payload.
    """
    query_analysis = state.get("query_analysis")

    # Determine sub-questions: use decomposed list or fall back to original query
    if query_analysis and query_analysis.sub_questions:
        sub_questions = query_analysis.sub_questions
    else:
        # Fall back to original query from the last human message
        messages = state.get("messages", [])
        original_query = ""
        for msg in reversed(messages):
            # Support both dict-style and BaseMessage-style messages
            if hasattr(msg, "type") and msg.type == "human":
                original_query = msg.content
                break
            elif isinstance(msg, dict) and msg.get("type") == "human":
                original_query = msg.get("content", "")
                break
        sub_questions = [original_query] if original_query else [""]

    # Determine collections to search: prefer collections_hint, fall back to selected_collections
    collections = []
    if query_analysis and query_analysis.collections_hint:
        collections = query_analysis.collections_hint
    if not collections:
        collections = state.get("selected_collections", [])

    sends = []
    for sub_q in sub_questions:
        payload: ResearchState = {
            "sub_question": sub_q,
            "session_id": state["session_id"],
            "selected_collections": collections,
            "llm_model": state["llm_model"],
            "embed_model": state["embed_model"],
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
            "stage_timings": {},
            "sub_answers": [],
            "_meta_attempt_count": 0,
            "_attempted_strategies": set(),
            "_top_k_retrieval": None,
            "_top_k_rerank": None,
            "_payload_filters": None,
            "loop_start_time": None,
        }
        sends.append(Send("research", payload))

    return sends
