"""TypedDict state schemas for the 3-layer LangGraph agent.

ConversationGraph → ResearchGraph → MetaReasoningGraph
"""

from typing import TypedDict

from backend.agent.schemas import (
    Citation,
    GroundednessResult,
    QueryAnalysis,
    RetrievedChunk,
    SubAnswer,
)


class ConversationState(TypedDict):
    session_id: str
    messages: list  # List[BaseMessage] — deferred import to avoid LangGraph dep at import time
    query_analysis: QueryAnalysis | None
    sub_answers: list[SubAnswer]
    selected_collections: list[str]
    llm_model: str
    embed_model: str
    intent: str  # "rag_query" | "collection_mgmt" | "ambiguous"
    final_response: str | None
    citations: list[Citation]
    groundedness_result: GroundednessResult | None
    confidence_score: int  # 0–100 scale (user-facing)
    iteration_count: int
    stage_timings: dict  # FR-005: per-stage timing data accumulated by nodes


class ResearchState(TypedDict):
    sub_question: str
    session_id: str
    selected_collections: list[str]
    llm_model: str
    embed_model: str
    retrieved_chunks: list[RetrievedChunk]
    retrieval_keys: set[str]
    tool_call_count: int
    iteration_count: int
    confidence_score: float  # Internal computation (0.0–1.0)
    answer: str | None
    citations: list[Citation]
    context_compressed: bool
    messages: list  # AIMessage/ToolMessage for orchestrator↔tools communication
    _no_new_tools: bool  # Flag: orchestrator produced no tool calls (F4)
    _needs_compression: bool  # Flag: context token count exceeds threshold (F3)
    stage_timings: dict  # FR-005: per-stage timing data accumulated by research nodes


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
    attempted_strategies: set[str]  # FR-015: dedup across attempts
