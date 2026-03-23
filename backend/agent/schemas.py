"""Pydantic models for agent internals and API responses.

Internal agent schemas are used by the 3-layer LangGraph agent.
API response schemas match data-model.md entity definitions.
"""

from typing import Literal, TypedDict

from pydantic import BaseModel, Field


# --- Internal Agent Schemas ---


class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: list[str]
    clarification_needed: str | None = None
    collections_hint: list[str]
    complexity_tier: Literal[
        "factoid", "lookup", "comparison", "analytical", "multi_hop"
    ]


class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    page: int | None = None
    breadcrumb: str
    parent_id: str
    collection: str
    dense_score: float
    sparse_score: float
    rerank_score: float | None = None


class ParentChunk(BaseModel):
    parent_id: str
    text: str
    source_file: str
    page: int | None = None
    breadcrumb: str
    collection: str


class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: str | None = None
    explanation: str


class GroundednessResult(BaseModel):
    verifications: list[ClaimVerification]
    overall_grounded: bool
    confidence_adjustment: float


# --- API Response Schemas (match data-model.md) ---


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    embedding_model: str = "nomic-embed-text"
    chunk_profile: str = "default"
    document_count: int = 0
    created_at: str


class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str | None = None
    embedding_model: str | None = None
    chunk_profile: str | None = None


class DocumentResponse(BaseModel):
    id: str
    collection_id: str
    filename: str
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int | None = None
    created_at: str
    updated_at: str | None = None


class Citation(BaseModel):
    """Citation in an answer. Matches data-model.md Citation object."""

    passage_id: str
    document_id: str
    document_name: str
    start_offset: int
    end_offset: int
    text: str
    relevance_score: float  # 0.0–1.0
    source_removed: bool = False  # True if source doc deleted since indexing


class SubAnswer(BaseModel):
    sub_question: str
    answer: str
    citations: list[Citation]
    chunks: list[RetrievedChunk]
    confidence_score: int = Field(ge=0, le=100)


class Passage(BaseModel):
    """Retrieved passage in a trace. Matches data-model.md Passage object."""

    id: str
    document_id: str
    document_name: str
    text: str
    relevance_score: float
    chunk_index: int
    source_removed: bool = False


class ReasoningStep(BaseModel):
    step_num: int
    strategy: str  # "initial_retrieval", "fallback_reranking", "query_decomposition"
    passages_found: int
    avg_score: float


class TraceResponse(BaseModel):
    """Full trace response. Matches data-model.md Trace entity."""

    id: str
    query_id: str
    query_text: str
    collections_searched: list[str]
    passages_retrieved: list[Passage]
    confidence_score: int = Field(ge=0, le=100)
    reasoning_steps: list[ReasoningStep] | None = None
    created_at: str


class AnswerResponse(BaseModel):
    id: str
    query_id: str
    answer_text: str
    citations: list[Citation]
    confidence_score: int = Field(ge=0, le=100)
    generated_at: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    collection_ids: list[str] = Field(default_factory=list)
    llm_model: str = "qwen2.5:7b"
    embed_model: str | None = None
    session_id: str | None = None


class ProviderResponse(BaseModel):
    name: str
    type: str
    is_active: bool
    status: str = "ready"
    model: str | None = None


class ProviderConfigRequest(BaseModel):
    api_key: str


class HealthServiceStatus(BaseModel):
    name: str
    status: Literal["ok", "error"]
    latency_ms: float | None = None
    error_message: str | None = None
    models: dict[str, bool] | None = None  # Ollama model availability (FR-034)


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "starting"]
    services: list[HealthServiceStatus]


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}


class ErrorResponse(BaseModel):
    error: ErrorDetail


# --- Spec 08: New API Models ---


class IngestionJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: Literal[
        "pending", "started", "streaming", "embedding",
        "completed", "failed", "paused",
    ]
    chunks_processed: int = 0
    chunks_total: int | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class ModelInfo(BaseModel):
    name: str
    provider: str
    model_type: Literal["llm", "embed"]
    size_gb: float | None = None
    quantization: str | None = None
    context_length: int | None = None


class ProviderKeyRequest(BaseModel):
    api_key: str


class ProviderHealthSchema(BaseModel):
    provider: str
    reachable: bool


class ProviderDetailResponse(BaseModel):
    name: str
    is_active: bool = False
    has_key: bool = False
    base_url: str | None = None
    model_count: int = 0


class SettingsResponse(BaseModel):
    default_llm_model: str
    default_embed_model: str
    confidence_threshold: int = Field(ge=0, le=100)
    groundedness_check_enabled: bool
    citation_alignment_threshold: float
    parent_chunk_size: int
    child_chunk_size: int


class SettingsUpdateRequest(BaseModel):
    default_llm_model: str | None = None
    default_embed_model: str | None = None
    confidence_threshold: int | None = Field(None, ge=0, le=100)
    groundedness_check_enabled: bool | None = None
    citation_alignment_threshold: float | None = None
    parent_chunk_size: int | None = None
    child_chunk_size: int | None = None


class StatsResponse(BaseModel):
    total_collections: int
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_confidence: float
    avg_latency_ms: float
    meta_reasoning_rate: float


class QueryTraceResponse(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: list[str]
    confidence_score: int | None = None
    latency_ms: int
    llm_model: str | None = None
    meta_reasoning_triggered: bool = False
    created_at: str


class QueryTraceDetailResponse(QueryTraceResponse):
    sub_questions: list[str] = []
    chunks_retrieved: list[dict] = []
    reasoning_steps: list[dict] = []
    strategy_switches: list[dict] = []


# --- NDJSON Event TypedDicts (Chat Stream) ---


class SessionEvent(TypedDict):
    type: Literal["session"]
    session_id: str


class StatusEvent(TypedDict):
    type: Literal["status"]
    node: str


class ChunkEvent(TypedDict):
    type: Literal["chunk"]
    text: str


class CitationEvent(TypedDict):
    type: Literal["citation"]
    citations: list[dict]


class MetaReasoningEvent(TypedDict):
    type: Literal["meta_reasoning"]
    strategies_attempted: list[str]


class ConfidenceEvent(TypedDict):
    type: Literal["confidence"]
    score: int


class GroundednessEvent(TypedDict):
    type: Literal["groundedness"]
    overall_grounded: bool
    supported: int
    unsupported: int
    contradicted: int


class DoneEvent(TypedDict):
    type: Literal["done"]
    latency_ms: int
    trace_id: str


class ClarificationEvent(TypedDict):
    type: Literal["clarification"]
    question: str


class ErrorEvent(TypedDict):
    type: Literal["error"]
    message: str
    code: str
    trace_id: str


# --- Spec 15: Observability Metrics Models ---


class CircuitBreakerSnapshot(BaseModel):
    state: Literal["closed", "open", "unknown"]
    failure_count: int


class MetricsBucket(BaseModel):
    timestamp: str
    query_count: int
    avg_latency_ms: int
    p95_latency_ms: int
    avg_confidence: int
    meta_reasoning_count: int
    error_count: int


class MetricsResponse(BaseModel):
    window: str
    bucket_size: str
    buckets: list[MetricsBucket]
    circuit_breakers: dict[str, CircuitBreakerSnapshot]
    active_ingestion_jobs: int
