"""TypedDict state schemas for the 3-layer LangGraph agent.

ConversationGraph → ResearchGraph → MetaReasoningGraph
"""

import operator
from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages

from backend.agent.schemas import (
    Citation,
    GroundednessResult,
    QueryAnalysis,
    RetrievedChunk,
    SubAnswer,
)


def _keep_last(existing, new):
    """Reducer for LangGraph fan-out: keep the latest value."""
    return new


def _merge_dicts(existing, new):
    """Reducer for dicts: merge new keys into existing."""
    merged = dict(existing) if existing else {}
    if new:
        merged.update(new)
    return merged


def _merge_sets(existing, new):
    """Reducer for set fields: union merge, handles None on first call."""
    return (existing or set()) | (new or set())


class ConversationState(TypedDict):
    """State for the outermost ConversationGraph, persisted per session via SQLite checkpointer.

    Fields annotated with reducer functions govern how parallel ResearchGraph
    results (fan-out via Send()) are merged back into the session state.
    """

    session_id: Annotated[str, _keep_last]
    messages: Annotated[list, add_messages]
    query_analysis: Annotated[QueryAnalysis | None, _keep_last]
    sub_answers: Annotated[list[SubAnswer], operator.add]
    selected_collections: Annotated[list[str], _keep_last]
    llm_model: Annotated[str, _keep_last]
    embed_model: Annotated[str, _keep_last]
    intent: Annotated[str, _keep_last]
    final_response: Annotated[str | None, _keep_last]
    citations: Annotated[list[Citation], operator.add]
    groundedness_result: Annotated[GroundednessResult | None, _keep_last]
    confidence_score: Annotated[int, _keep_last]
    iteration_count: Annotated[int, _keep_last]
    stage_timings: Annotated[dict, _merge_dicts]


class ResearchState(TypedDict):
    """State for a single ResearchGraph execution (one sub-question from fan_out).

    Instantiated fresh for each sub-question. Fields prefixed with _ are
    internal graph signals not exposed in the final response.
    May be handed off to MetaReasoningGraph when confidence falls below threshold.
    """

    sub_question: Annotated[str, _keep_last]
    session_id: Annotated[str, _keep_last]
    selected_collections: Annotated[list[str], _keep_last]
    llm_model: Annotated[str, _keep_last]
    embed_model: Annotated[str, _keep_last]
    retrieved_chunks: Annotated[list[RetrievedChunk], _keep_last]
    retrieval_keys: Annotated[set[str], _merge_sets]
    tool_call_count: Annotated[int, _keep_last]
    iteration_count: Annotated[int, _keep_last]
    confidence_score: Annotated[float, _keep_last]
    answer: Annotated[str | None, _keep_last]
    citations: Annotated[list[Citation], operator.add]
    context_compressed: Annotated[bool, _keep_last]
    messages: Annotated[list, add_messages]
    _no_new_tools: Annotated[bool, _keep_last]
    _needs_compression: Annotated[bool, _keep_last]
    stage_timings: Annotated[dict, _merge_dicts]
    sub_answers: Annotated[list, operator.add]
    _meta_attempt_count: Annotated[int, _keep_last]
    _attempted_strategies: Annotated[set, _keep_last]
    _top_k_retrieval: Annotated[int | None, _keep_last]
    _top_k_rerank: Annotated[int | None, _keep_last]
    _payload_filters: Annotated[dict | None, _keep_last]
    loop_start_time: Annotated[float | None, _keep_last]


class MetaReasoningState(TypedDict):
    """State for the MetaReasoningGraph recovery cycle.

    Invoked when ResearchGraph confidence is below threshold and the budget
    is exhausted. Generates alternative queries, evaluates retrieval quality,
    and selects a recovery strategy (widen_search, change_collection,
    relax_filters, or report_uncertainty). Up to Settings.meta_reasoning_max_attempts.
    """

    sub_question: str
    retrieved_chunks: list[RetrievedChunk]
    alternative_queries: list[str]
    mean_relevance_score: float
    chunk_relevance_scores: list[float]
    meta_attempt_count: int
    recovery_strategy: str | None
    modified_state: dict | None
    answer: str | None
    uncertainty_reason: str | None
    attempted_strategies: Annotated[set[str], _keep_last]
