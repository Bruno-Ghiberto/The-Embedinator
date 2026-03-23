"""TypedDict state schemas for the 3-layer LangGraph agent.

ConversationGraph → ResearchGraph → MetaReasoningGraph
"""

import operator
from typing import Annotated, TypedDict

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


class ConversationState(TypedDict):
    session_id: Annotated[str, _keep_last]
    messages: Annotated[list, operator.add]
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
    sub_question: Annotated[str, _keep_last]
    session_id: Annotated[str, _keep_last]
    selected_collections: Annotated[list[str], _keep_last]
    llm_model: Annotated[str, _keep_last]
    embed_model: Annotated[str, _keep_last]
    retrieved_chunks: Annotated[list[RetrievedChunk], operator.add]
    retrieval_keys: set[str]
    tool_call_count: Annotated[int, _keep_last]
    iteration_count: Annotated[int, _keep_last]
    confidence_score: Annotated[float, _keep_last]
    answer: Annotated[str | None, _keep_last]
    citations: Annotated[list[Citation], operator.add]
    context_compressed: Annotated[bool, _keep_last]
    messages: Annotated[list, operator.add]
    _no_new_tools: Annotated[bool, _keep_last]
    _needs_compression: Annotated[bool, _keep_last]
    stage_timings: Annotated[dict, _merge_dicts]


class MetaReasoningState(TypedDict):
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
    attempted_strategies: set[str]
