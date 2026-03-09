# Spec 11: Component Interface Contracts -- Feature Specification Context

## Feature Description

This specification defines the exact function signatures, input/output types, error conditions, and injected dependencies for every major module in The Embedinator. These contracts serve as the "glue" between all other specs -- they define how agent nodes, tools, ingestion pipeline, embedder, searcher, reranker, Qdrant storage, SQLite database, and provider registry interact with each other. Every inter-component call must conform to these type contracts.

The contracts are organized by layer: Agent Nodes (ConversationGraph, ResearchGraph, MetaReasoningGraph), Agent Tools, Ingestion Pipeline, Embedder, Hybrid Searcher, Reranker, Qdrant Storage, and SQLite Database.

## Requirements

### Functional Requirements

1. All agent node functions must be stateless async functions that read from and write to a TypedDict state object
2. All dependencies (db, llm, reranker, embedder) must be injected via keyword arguments, never imported globally
3. All Pydantic models must be defined in `backend/agent/schemas.py` for agent-layer types
4. All storage operations must be async and use the `SQLiteDB` and `QdrantStorage` classes
5. All search operations must go through the `HybridSearcher` abstraction
6. All reranking operations must go through the `Reranker` class
7. All embedding operations must go through the `BatchEmbedder` class
8. Every function must declare its error conditions (what it raises or catches internally)

### Non-Functional Requirements

- All async functions must support cancellation via `asyncio.CancelledError`
- Type annotations must be complete -- no `Any` types except in `**kwargs`
- All state reads/writes must be documented per node function
- Error handling must follow the propagation rules defined in spec-12

## Key Technical Details

### State Schemas

```python
# backend/agent/state.py

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
    confidence_score: float            # computed from retrieval signals, not LLM self-assessment
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
class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str]              # max 5 decomposed sub-questions
    clarification_needed: Optional[str]   # human-readable clarification prompt
    collections_hint: List[str]           # suggested collection names to search
    complexity_tier: Literal[
        "factoid", "lookup", "comparison", "analytical", "multi_hop"
    ]

class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str]
    explanation: str

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool             # True if >50% claims supported
    confidence_adjustment: float       # modifier applied to confidence score
```

### Agent Node Contracts -- ConversationGraph

```python
# backend/agent/nodes.py

async def init_session(
    state: ConversationState,
    *,
    db: SQLiteDB,
) -> ConversationState:
    """Load or create session. Restores message history from SQLite.
    Reads: state["session_id"]
    Writes: state["messages"], state["selected_collections"]
    Raises: SessionLoadError (caught internally, falls back to fresh session)
    """

async def classify_intent(
    state: ConversationState,
    *,
    llm: BaseChatModel,
) -> dict:
    """Classify user intent as rag_query, collection_mgmt, or ambiguous.
    Reads: state["messages"]
    Returns: {"intent": Literal["rag_query", "collection_mgmt", "ambiguous"]}
    Raises: LLMCallError (caught, defaults to "rag_query")
    """

async def rewrite_query(
    state: ConversationState,
    *,
    llm: BaseChatModel,
) -> ConversationState:
    """Decompose query into sub-questions with structured output.
    Reads: state["messages"], state["selected_collections"]
    Writes: state["query_analysis"]
    Raises: StructuredOutputParseError (retry once, then single-question fallback)
    """

async def fan_out(
    state: ConversationState,
) -> List[Send]:
    """Spawn ResearchGraph instances via LangGraph Send().
    Reads: state["query_analysis"], state["selected_collections"],
           state["llm_model"], state["embed_model"]
    Returns: List[Send] -- one per sub-question
    """

async def aggregate_answers(
    state: ConversationState,
) -> ConversationState:
    """Merge sub-answers, deduplicate citations, rank by relevance.
    Reads: state["sub_answers"]
    Writes: state["final_response"], state["citations"]
    """

async def verify_groundedness(
    state: ConversationState,
    *,
    llm: BaseChatModel,
) -> ConversationState:
    """NLI-based claim verification against retrieved context.
    Reads: state["final_response"], state["citations"], state["sub_answers"]
    Writes: state["groundedness_result"], state["confidence_score"]
    Raises: LLMCallError (caught, sets groundedness_result=None)
    """

async def validate_citations(
    state: ConversationState,
    *,
    reranker: CrossEncoder,
) -> ConversationState:
    """Cross-encoder alignment check for each citation.
    Reads: state["final_response"], state["citations"]
    Writes: state["citations"] (corrected)
    Raises: RerankerError (caught, passes citations through unvalidated)
    """

async def format_response(
    state: ConversationState,
) -> ConversationState:
    """Apply citation annotations, confidence indicator, SSE formatting.
    Reads: state["final_response"], state["citations"],
           state["groundedness_result"], state["confidence_score"]
    Writes: state["final_response"] (formatted)
    """
```

### Agent Node Contracts -- ResearchGraph

```python
async def orchestrator(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Decide which tools to call based on current context.
    Reads: state["sub_question"], state["retrieved_chunks"],
           state["tool_call_count"], state["iteration_count"]
    Writes: internal tool_call decisions
    Raises: LLMCallError (triggers fallback_response)
    """

async def collect_answer(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Generate answer from retrieved chunks, compute confidence.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"], state["citations"], state["confidence_score"]
    """

async def compress_context(
    state: ResearchState,
    *,
    llm: BaseChatModel,
) -> ResearchState:
    """Summarize retrieved chunks when context window is approached.
    Reads: state["retrieved_chunks"], state["llm_model"]
    Writes: state["retrieved_chunks"] (compressed), state["context_compressed"]
    """

async def fallback_response(
    state: ResearchState,
) -> ResearchState:
    """Generate graceful insufficient-information response.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"]
    """
```

### Agent Node Contracts -- MetaReasoningGraph

```python
async def generate_alternative_queries(
    state: MetaReasoningState,
    *,
    llm: BaseChatModel,
) -> MetaReasoningState:
    """Produce rephrased query variants.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["alternative_queries"]
    """

async def evaluate_retrieval_quality(
    state: MetaReasoningState,
    *,
    reranker: CrossEncoder,
) -> MetaReasoningState:
    """Score all chunks with cross-encoder.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["mean_relevance_score"], state["chunk_relevance_scores"]
    """

async def decide_strategy(
    state: MetaReasoningState,
) -> MetaReasoningState:
    """Select recovery strategy based on evaluation.
    Reads: state["mean_relevance_score"], state["chunk_relevance_scores"],
           state["meta_attempt_count"]
    Writes: state["recovery_strategy"], state["modified_state"]
    """

async def report_uncertainty(
    state: MetaReasoningState,
) -> MetaReasoningState:
    """Generate honest I-don't-know response.
    Reads: state["sub_question"], state["mean_relevance_score"]
    Writes: state["answer"], state["uncertainty_reason"]
    """
```

### Agent Tools (`backend/agent/tools.py`)

```python
@tool
async def search_child_chunks(
    query: str,
    collection: str,
    top_k: int = 20,
    filters: Optional[dict] = None,
) -> List[RetrievedChunk]:
    """Hybrid dense+BM25 search with cross-encoder reranking.
    Raises: QdrantConnectionError, EmbeddingError
    """

@tool
async def retrieve_parent_chunks(
    parent_ids: List[str],
) -> List[ParentChunk]:
    """Fetch parent chunks from SQLite by ID list.
    Raises: DatabaseError
    """

@tool
async def cross_encoder_rerank(
    query: str,
    chunks: List[RetrievedChunk],
    top_k: int = 5,
) -> List[RetrievedChunk]:
    """Score and rerank (query, chunk) pairs.
    Raises: RerankerError
    """

@tool
async def filter_by_metadata(
    filters: dict,
) -> dict:
    """Apply Qdrant payload filter constraints.
    Valid filter keys: doc_type, page_min, page_max, source_file
    Raises: InvalidFilterError
    """

@tool
async def semantic_search_all_collections(
    query: str,
    top_k: int = 20,
) -> List[RetrievedChunk]:
    """Fan-out search across all collections with score normalization.
    Raises: QdrantConnectionError, EmbeddingError
    """
```

### Ingestion Pipeline (`backend/ingestion/pipeline.py`)

```python
class IngestionPipeline:
    def __init__(
        self,
        db: SQLiteDB,
        qdrant: QdrantStorage,
        embedder: BatchEmbedder,
        chunker: ChunkSplitter,
        incremental: IncrementalChecker,
        rust_worker_path: str,
    ) -> None: ...

    async def ingest_file(
        self,
        file_path: str,
        collection_id: str,
        document_id: str,
        job_id: str,
    ) -> IngestionResult:
        """Full ingestion pipeline: parse -> split -> embed -> upsert.
        Returns: IngestionResult with chunk counts and status
        Raises: IngestionError, RustWorkerError, EmbeddingError, QdrantConnectionError
        """

    async def check_duplicate(
        self,
        file_path: str,
        collection_id: str,
    ) -> Optional[str]:
        """Check if file hash already exists. Returns document_id if duplicate, None otherwise."""

class IngestionResult(BaseModel):
    document_id: str
    job_id: str
    status: Literal["completed", "failed", "duplicate"]
    chunks_processed: int
    chunks_skipped: int
    error_msg: Optional[str]
    elapsed_ms: int
```

### Embedder (`backend/ingestion/embedder.py`)

```python
class BatchEmbedder:
    def __init__(
        self,
        provider: EmbeddingProvider,
        model: str,
        batch_size: int = 16,
        max_workers: int = 4,
    ) -> None: ...

    async def embed_batch(
        self,
        texts: List[str],
    ) -> List[EmbeddingResult]:
        """Embed a batch of texts with validation.
        Returns: List of EmbeddingResult (vector + validation status)
        Raises: EmbeddingError (if all retries exhausted)
        """

    def validate_embedding(
        self,
        embedding: List[float],
        expected_dim: int,
    ) -> bool:
        """Check embedding for NaN, zero-vector, dimension mismatch."""

class EmbeddingResult(BaseModel):
    text: str
    vector: Optional[List[float]]
    valid: bool
    error: Optional[str]
```

### Hybrid Searcher (`backend/retrieval/searcher.py`)

```python
class HybridSearcher:
    def __init__(
        self,
        qdrant: QdrantStorage,
        embedder: BatchEmbedder,
        reranker: Reranker,
    ) -> None: ...

    async def search(
        self,
        query: str,
        collection_name: str,
        top_k: int = 20,
        filters: Optional[dict] = None,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> List[RetrievedChunk]:
        """Hybrid dense+BM25 search with RRF fusion.
        Raises: QdrantConnectionError, EmbeddingError
        """

    async def search_multi_collection(
        self,
        query: str,
        collection_names: List[str],
        top_k: int = 20,
    ) -> List[RetrievedChunk]:
        """Search across multiple collections with score normalization.
        Raises: QdrantConnectionError, EmbeddingError
        """
```

### Reranker (`backend/retrieval/reranker.py`)

```python
class Reranker:
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ) -> None: ...

    def rerank(
        self,
        query: str,
        chunks: List[RetrievedChunk],
        top_k: int = 5,
    ) -> List[RetrievedChunk]:
        """Score and rerank (query, chunk) pairs with cross-encoder.
        Returns: Top-k chunks sorted by cross-encoder score descending
        Raises: RerankerError
        """

    def score_pair(
        self,
        text_a: str,
        text_b: str,
    ) -> float:
        """Score a single (text_a, text_b) pair. Used for citation validation."""
```

### Qdrant Storage (`backend/storage/qdrant_client.py`)

```python
class QdrantStorage:
    def __init__(self, host: str = "localhost", port: int = 6333) -> None: ...

    async def create_collection(self, name: str, dense_dim: int) -> None:
        """Create a Qdrant collection with dense + sparse vector config.
        Raises: QdrantConnectionError, CollectionExistsError
        """

    async def delete_collection(self, name: str) -> None:
        """Delete a Qdrant collection.
        Raises: QdrantConnectionError, CollectionNotFoundError
        """

    async def upsert_batch(self, collection_name: str, points: List[PointStruct]) -> None:
        """Batch upsert points with retry.
        Raises: QdrantConnectionError (after retries exhausted)
        """

    async def hybrid_search(
        self,
        collection_name: str,
        dense_vector: List[float],
        sparse_indices: List[int],
        sparse_values: List[float],
        top_k: int = 20,
        filters: Optional[dict] = None,
    ) -> List[ScoredPoint]:
        """Execute hybrid dense+sparse search with RRF fusion.
        Raises: QdrantConnectionError
        """

    async def delete_by_filter(
        self, collection_name: str, filter_conditions: dict
    ) -> int:
        """Delete points matching filter. Returns count of deleted points.
        Raises: QdrantConnectionError
        """

    async def health_check(self) -> Tuple[bool, Optional[int]]:
        """Check Qdrant connectivity. Returns (is_healthy, latency_ms)."""
```

### SQLite Database (`backend/storage/sqlite_db.py`)

```python
class SQLiteDB:
    def __init__(self, db_path: str) -> None: ...
    async def initialize(self) -> None: ...

    # --- Collections ---
    async def create_collection(self, collection: CollectionCreate) -> CollectionRow: ...
    async def get_collection(self, collection_id: str) -> Optional[CollectionRow]: ...
    async def list_collections(self) -> List[CollectionRow]: ...
    async def delete_collection(self, collection_id: str) -> bool: ...

    # --- Documents ---
    async def create_document(self, doc: DocumentCreate) -> DocumentRow: ...
    async def get_document(self, doc_id: str) -> Optional[DocumentRow]: ...
    async def list_documents(self, collection_id: str) -> List[DocumentRow]: ...
    async def update_document_status(self, doc_id: str, status: str, chunk_count: int = 0) -> None: ...
    async def find_by_hash(self, collection_id: str, file_hash: str) -> Optional[DocumentRow]: ...
    async def delete_document(self, doc_id: str) -> bool: ...

    # --- Ingestion Jobs ---
    async def create_ingestion_job(self, job: JobCreate) -> JobRow: ...
    async def update_job_status(self, job_id: str, status: str, error_msg: Optional[str] = None) -> None: ...
    async def get_ingestion_job(self, job_id: str) -> Optional[JobRow]: ...

    # --- Parent Chunks ---
    async def store_parent_chunks(self, chunks: List[ParentChunkCreate]) -> None: ...
    async def get_parent_chunks(self, parent_ids: List[str]) -> List[ParentChunkRow]: ...
    async def delete_parent_chunks(self, document_id: str) -> int: ...

    # --- Query Traces ---
    async def store_trace(self, trace: TraceCreate) -> None: ...
    async def list_traces(self, page: int, limit: int, session_id: Optional[str] = None) -> Tuple[List[TraceRow], int]: ...
    async def get_trace(self, trace_id: str) -> Optional[TraceRow]: ...

    # --- Settings ---
    async def get_setting(self, key: str) -> Optional[str]: ...
    async def set_setting(self, key: str, value: str) -> None: ...
    async def get_all_settings(self) -> dict: ...

    # --- Providers ---
    async def get_provider(self, name: str) -> Optional[ProviderRow]: ...
    async def list_providers(self) -> List[ProviderRow]: ...
    async def set_provider_key(self, name: str, encrypted_key: str) -> None: ...
    async def delete_provider_key(self, name: str) -> None: ...

    # --- Health ---
    async def health_check(self) -> bool: ...
```

## Dependencies

### Spec Dependencies
- **spec-02-conversation-graph**: Defines ConversationGraph nodes that use these contracts
- **spec-03-research-graph**: Defines ResearchGraph nodes that use these contracts
- **spec-04-meta-reasoning**: Defines MetaReasoningGraph nodes that use these contracts
- **spec-05-accuracy**: Defines groundedness verification and citation validation using these contracts
- **spec-06-ingestion**: Defines ingestion pipeline using these contracts
- **spec-07-storage**: Defines SQLiteDB and QdrantStorage using these contracts
- **spec-08-api**: API routes call these interfaces
- **spec-10-providers**: Provider interfaces (LLMProvider, EmbeddingProvider) referenced by nodes and tools
- **spec-12-errors**: Error types raised by these contracts

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | `>=2.12` | Schemas, structured output, validation |
| `langchain_core` | (via langchain) | `BaseMessage`, `BaseChatModel`, `tool` decorator |
| `sentence-transformers` | `>=5.2.3` | `CrossEncoder` type for reranker injection |
| `qdrant-client` | `>=1.17.0` | `PointStruct`, `ScoredPoint` types |
| `aiosqlite` | `>=0.21` | Async SQLite operations |

## Acceptance Criteria

1. All TypedDict state schemas (`ConversationState`, `ResearchState`, `MetaReasoningState`) are fully defined with correct types
2. All Pydantic schemas (`QueryAnalysis`, `ClaimVerification`, `GroundednessResult`, `IngestionResult`, `EmbeddingResult`, `ModelInfo`) are defined and importable
3. Every agent node function has a complete type signature with injected dependencies as keyword-only arguments
4. Every function documents its state reads, state writes, and error conditions
5. Every tool function has a `@tool` decorator and complete type annotations
6. Storage classes (`SQLiteDB`, `QdrantStorage`) define all CRUD methods with typed inputs and outputs
7. `HybridSearcher` and `Reranker` define their complete interfaces with error conditions
8. `BatchEmbedder` defines batch embedding with validation interface
9. `IngestionPipeline` defines full ingestion flow with result type
10. No `Any` types used except in `**kwargs` parameters
11. All async functions properly typed with `async def` and correct return types
12. Error types from spec-12 are correctly referenced in all raise conditions

## Architecture Reference

### Dependency Injection Pattern

All agent nodes receive their dependencies via keyword-only arguments. This enables testing with mock implementations:

```python
async def classify_intent(
    state: ConversationState,
    *,
    llm: BaseChatModel,  # injected via ProviderRegistry
) -> dict:
```

### Error Propagation Rules

| Layer | Catches | Bubbles Up | Notes |
|-------|---------|-----------|-------|
| Storage (`qdrant_client`, `sqlite_db`) | Raw HTTP/DB errors | `QdrantConnectionError`, `DatabaseError` | Wraps raw exceptions with context |
| Ingestion (`pipeline`, `embedder`) | Storage errors, Rust worker errors | `IngestionError` subtypes | Logs per-chunk failures, continues batch |
| Agent (`nodes`, `tools`) | LLM errors, tool errors | `AgentError` subtypes | Node-specific fallback before bubbling |
| API (`routes`) | All `EmbdinatorError` subtypes | HTTP error responses | Maps to status codes, logs internally |

### Query-Adaptive Retrieval Depth

The `complexity_tier` in `QueryAnalysis` drives retrieval parameters:

| Tier | top_k | max_iterations | max_tool_calls | Confidence Threshold |
|------|-------|---------------|----------------|---------------------|
| `factoid` | 5 | 3 | 3 | 0.7 |
| `lookup` | 10 | 5 | 5 | 0.6 |
| `comparison` | 15 | 7 | 6 | 0.55 |
| `analytical` | 25 | 10 | 8 | 0.5 |
| `multi_hop` | 30 | 10 | 8 | 0.45 |
