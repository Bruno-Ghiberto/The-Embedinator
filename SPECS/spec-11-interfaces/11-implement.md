# Spec 11: Component Interface Contracts -- Implementation Context

## Implementation Scope

### Files to Create
```
backend/
  agent/
    state.py          # TypedDict state schemas
    schemas.py        # Pydantic models
```

### Files to Define Interfaces In (implementations come from other specs)
```
backend/
  agent/
    nodes.py          # Node function stubs with complete signatures
    tools.py          # Tool function stubs with complete signatures
  ingestion/
    pipeline.py       # IngestionPipeline class stub
    embedder.py       # BatchEmbedder class stub
  retrieval/
    searcher.py       # HybridSearcher class stub
    reranker.py       # Reranker class stub
  storage/
    qdrant_client.py  # QdrantStorage class stub
    sqlite_db.py      # SQLiteDB class stub
  providers/
    base.py           # LLMProvider, EmbeddingProvider ABCs
```

## Code Specifications

### State Schemas (`backend/agent/state.py`)

```python
from typing import List, Optional, Set, TypedDict
from langchain_core.messages import BaseMessage
from backend.agent.schemas import (
    QueryAnalysis,
    SubAnswer,
    Citation,
    GroundednessResult,
    RetrievedChunk,
)


class ConversationState(TypedDict):
    session_id: str
    messages: List[BaseMessage]
    query_analysis: Optional[QueryAnalysis]
    sub_answers: List[SubAnswer]
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    final_response: Optional[str]
    citations: List[Citation]
    groundedness_result: Optional[GroundednessResult]
    confidence_score: float
    iteration_count: int


class ResearchState(TypedDict):
    sub_question: str
    session_id: str
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    retrieved_chunks: List[RetrievedChunk]
    retrieval_keys: Set[str]
    tool_call_count: int
    iteration_count: int
    confidence_score: float
    answer: Optional[str]
    citations: List[Citation]
    context_compressed: bool


class MetaReasoningState(TypedDict):
    sub_question: str
    retrieved_chunks: List[RetrievedChunk]
    alternative_queries: List[str]
    mean_relevance_score: float
    chunk_relevance_scores: List[float]
    meta_attempt_count: int
    recovery_strategy: Optional[str]
    modified_state: Optional[dict]
    answer: Optional[str]
    uncertainty_reason: Optional[str]
```

### Pydantic Schemas (`backend/agent/schemas.py`)

```python
from typing import List, Optional, Literal
from pydantic import BaseModel, Field


class QueryAnalysis(BaseModel):
    """Structured query analysis output from the rewrite_query node."""
    is_clear: bool
    sub_questions: List[str] = Field(max_length=5, description="Decomposed sub-questions, max 5")
    clarification_needed: Optional[str] = Field(
        None, description="Human-readable clarification prompt if is_clear=False"
    )
    collections_hint: List[str] = Field(
        default_factory=list, description="Suggested collection names to search"
    )
    complexity_tier: Literal["factoid", "lookup", "comparison", "analytical", "multi_hop"] = Field(
        description="Drives adaptive retrieval depth (top_k, max_iterations, threshold)"
    )


class RetrievedChunk(BaseModel):
    """A chunk returned from hybrid search, before or after reranking."""
    chunk_id: str
    text: str
    collection: str
    source_file: str
    page: Optional[int] = None
    breadcrumb: Optional[str] = None
    dense_score: float = 0.0
    sparse_score: float = 0.0
    rerank_score: Optional[float] = None
    parent_id: Optional[str] = None


class ParentChunk(BaseModel):
    """A parent chunk retrieved from SQLite for context expansion."""
    parent_id: str
    text: str
    document_id: str
    source_file: str
    page_start: int
    page_end: int
    breadcrumb: str


class Citation(BaseModel):
    """An inline citation linking a response claim to a source chunk."""
    index: int
    chunk_id: str
    source: str
    page: int
    breadcrumb: str
    text: Optional[str] = None  # populated on hover via lazy fetch


class SubAnswer(BaseModel):
    """Output from a single ResearchGraph execution for one sub-question."""
    sub_question: str
    answer: str
    citations: List[Citation]
    confidence_score: float
    chunks_used: int


class ClaimVerification(BaseModel):
    """Verification result for a single claim in the answer."""
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str] = None
    explanation: str


class GroundednessResult(BaseModel):
    """Aggregate groundedness verification for the full answer."""
    verifications: List[ClaimVerification]
    overall_grounded: bool  # True if >50% claims supported
    confidence_adjustment: float  # modifier applied to confidence score
```

### API-Level Pydantic Schemas (referenced by routes)

These are the Pydantic models used by FastAPI route handlers for request/response serialization:

```python
# backend/api/schemas.py (or defined in respective route modules)

class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: Optional[str] = Field(None, max_length=500)
    embedding_model: str = "nomic-embed-text"
    chunk_profile: str = "default"

class CollectionSchema(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_profile: str
    qdrant_collection_name: str
    document_count: int
    total_chunks: int
    created_at: str

class DocumentSchema(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_hash: str
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int
    ingested_at: Optional[str]

class IngestionResponse(BaseModel):
    job_id: str
    document_id: str
    status: Literal["started", "duplicate"]

class IngestionJobSchema(BaseModel):
    id: str
    document_id: str
    status: Literal["started", "streaming", "embedding", "completed", "failed", "paused"]
    started_at: str
    finished_at: Optional[str]
    error_msg: Optional[str]
    chunks_processed: int
    chunks_skipped: int

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    collection_ids: List[str] = Field(..., min_length=1)
    llm_model: str = "llama3.2"
    embed_model: str = "nomic-embed-text"
    session_id: Optional[str] = None

class ModelInfo(BaseModel):
    name: str
    provider: str
    size: Optional[str] = None
    quantization: Optional[str] = None
    context_length: Optional[int] = None
    dims: Optional[int] = None

class ProviderSchema(BaseModel):
    name: str
    is_active: bool
    has_key: bool
    base_url: Optional[str]
    model_count: int

class SettingsSchema(BaseModel):
    default_llm_model: str
    default_embed_model: str
    default_provider: str
    parent_chunk_size: int
    child_chunk_size: int
    max_iterations: int
    max_tool_calls: int
    confidence_threshold: float
    groundedness_check_enabled: bool
    citation_alignment_threshold: float

class QueryTraceSchema(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: List[str]
    meta_reasoning_triggered: bool
    latency_ms: int
    llm_model: str
    confidence_score: Optional[float]
    created_at: str

class QueryTraceDetailSchema(QueryTraceSchema):
    sub_questions: List[str]
    chunks_retrieved: List[dict]  # [{chunk_id, score, collection, source_file}]
    embed_model: str

class HealthResponse(BaseModel):
    qdrant: Literal["ok", "error"]
    ollama: Literal["ok", "error"]
    sqlite: Literal["ok", "error"]
    qdrant_latency_ms: Optional[int]
    ollama_latency_ms: Optional[int]
    timestamp: str

class SystemStatsSchema(BaseModel):
    total_collections: int
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_latency_ms: float
    avg_confidence: float
    meta_reasoning_rate: float

class ErrorResponse(BaseModel):
    detail: str
    code: str
    trace_id: Optional[str] = None
    internal: Optional[dict] = None  # only in dev mode
```

### SQLite Row/Create Types

```python
# These are internal types used by SQLiteDB methods

class CollectionCreate(BaseModel):
    name: str
    description: Optional[str] = None
    embedding_model: str
    chunk_profile: str = "default"

class CollectionRow(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_profile: str
    qdrant_collection_name: str
    document_count: int
    total_chunks: int
    created_at: str

class DocumentCreate(BaseModel):
    collection_id: str
    filename: str
    file_hash: str

class DocumentRow(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_hash: str
    status: str
    chunk_count: int
    ingested_at: Optional[str]

class JobCreate(BaseModel):
    document_id: str

class JobRow(BaseModel):
    id: str
    document_id: str
    status: str
    started_at: str
    finished_at: Optional[str]
    error_msg: Optional[str]
    chunks_processed: int
    chunks_skipped: int

class ParentChunkCreate(BaseModel):
    parent_id: str
    document_id: str
    text: str
    source_file: str
    page_start: int
    page_end: int
    breadcrumb: str

class ParentChunkRow(BaseModel):
    parent_id: str
    document_id: str
    text: str
    source_file: str
    page_start: int
    page_end: int
    breadcrumb: str

class TraceCreate(BaseModel):
    session_id: str
    query: str
    collections_searched: List[str]
    meta_reasoning_triggered: bool
    latency_ms: int
    llm_model: str
    embed_model: str
    confidence_score: Optional[float]
    sub_questions: List[str]
    chunks_retrieved: List[dict]

class TraceRow(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: List[str]
    meta_reasoning_triggered: bool
    latency_ms: int
    llm_model: str
    confidence_score: Optional[float]
    created_at: str

class ProviderRow(BaseModel):
    name: str
    api_key_encrypted: Optional[str]
    base_url: Optional[str]
    is_active: bool
```

### Ingestion Result Types

```python
# backend/ingestion/pipeline.py
class IngestionResult(BaseModel):
    document_id: str
    job_id: str
    status: Literal["completed", "failed", "duplicate"]
    chunks_processed: int
    chunks_skipped: int
    error_msg: Optional[str] = None
    elapsed_ms: int

# backend/ingestion/embedder.py
class EmbeddingResult(BaseModel):
    text: str
    vector: Optional[List[float]] = None
    valid: bool
    error: Optional[str] = None
```

## Configuration

No separate configuration for this spec. The interfaces reference configuration values that are defined in `backend/config.py` (spec-07/spec-08):

- `CONFIDENCE_THRESHOLD`: Used in ResearchGraph loop condition
- `MAX_ITERATIONS`: Used in ResearchGraph loop bound
- `MAX_TOOL_CALLS`: Used in ResearchGraph tool budget
- `PARENT_CHUNK_SIZE`: Used in chunker configuration
- `CHILD_CHUNK_SIZE`: Used in chunker configuration

## Error Handling

This spec documents error conditions but does not implement error handling. The error hierarchy is defined in spec-12. Key error propagation rules:

| Layer | Catches | Bubbles Up |
|-------|---------|-----------|
| Storage | Raw HTTP/DB errors | `QdrantConnectionError`, `DatabaseError` |
| Ingestion | Storage + Rust errors | `IngestionError` subtypes |
| Agent | LLM + tool errors | `AgentError` subtypes |
| API | All `EmbdinatorError` | HTTP error responses |

Each node function documents its error behavior:
- **Catches internally with fallback**: The node handles the error and produces a degraded result
- **Raises**: The error propagates to the calling layer

## Testing Requirements

### Type Checking
- Run `pyright` or `mypy` on all interface files to verify type consistency
- All imports must resolve correctly
- No `Any` types except in `**kwargs`

### Contract Tests
- Verify that `ConversationState`, `ResearchState`, `MetaReasoningState` are valid TypedDict definitions
- Verify that all Pydantic models validate correctly with sample data
- Verify that all Pydantic models serialize/deserialize roundtrip
- Verify that `QueryAnalysis.complexity_tier` rejects invalid values
- Verify that `CreateCollectionRequest.name` validates against the regex pattern
- Verify that `ChatRequest.message` enforces min/max length

### Mock Implementation Tests
- Create mock implementations of `LLMProvider`, `EmbeddingProvider` for testing
- Create mock implementations of `SQLiteDB`, `QdrantStorage` for unit testing agent nodes
- Verify that mock implementations satisfy the ABC contracts

## Done Criteria

1. `backend/agent/state.py` defines all three TypedDict state schemas with complete type annotations
2. `backend/agent/schemas.py` defines all Pydantic models: `QueryAnalysis`, `RetrievedChunk`, `ParentChunk`, `Citation`, `SubAnswer`, `ClaimVerification`, `GroundednessResult`
3. All API-level Pydantic schemas are defined with validation rules matching the architecture spec
4. All SQLite row/create types are defined as Pydantic models
5. All function signatures in node and tool contracts match the architecture document exactly
6. All error conditions are documented in docstrings
7. All injected dependencies use keyword-only arguments (after `*` separator)
8. Type checker passes on all interface files with zero errors
9. Sample data validates correctly against all Pydantic models
10. No circular import issues between `state.py`, `schemas.py`, and other modules
