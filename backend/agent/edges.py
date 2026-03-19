"""Edge functions (routing logic) for the ConversationGraph.

Edge functions determine which node to execute next based on the current state.
"""

from __future__ import annotations

from langgraph.types import Send

from backend.agent.state import ConversationState, ResearchState


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

    If clarification is needed (query unclear + iteration_count < 2), returns
    "request_clarification". Otherwise, delegates to route_fan_out() which
    returns Send() objects for parallel ResearchGraph dispatch.

    This combined function is necessary because LangGraph does not support
    two add_conditional_edges from the same source node.
    """
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
        }
        sends.append(Send("research", payload))

    return sends
