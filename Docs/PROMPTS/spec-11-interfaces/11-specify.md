# Spec 11: Component Interface Contracts -- Feature Specification Context

## Feature Description

This specification defines the exact function signatures, input/output types, error conditions, and injected dependencies for every major module in The Embedinator. These contracts serve as the "glue" between all other specs -- they define how agent nodes, edge functions, tools, graph builders, ingestion pipeline, embedder, searcher, reranker, Qdrant storage, SQLite database, provider registry, and error hierarchy interact with each other. Every inter-component call must conform to these type contracts.

The contracts are organized by layer:

1. **Agent Layer**: State schemas, ConversationGraph nodes/edges, ResearchGraph nodes/edges, MetaReasoningGraph nodes/edges, tools, confidence scoring, graph builders
2. **Retrieval Layer**: Hybrid searcher, reranker, score normalizer
3. **Ingestion Layer**: Pipeline orchestrator, chunk splitter, batch embedder, incremental checker
4. **Storage Layer**: SQLite database, Qdrant storage, parent store
5. **Provider Layer**: LLM/embedding provider ABCs, provider registry, key manager
6. **Cross-Cutting**: Error hierarchy, Pydantic schemas, config

## Requirements

### Functional Requirements

1. All agent node functions must read from and write to a TypedDict state object, returning `dict` (partial state updates)
2. ConversationGraph nodes receive dependencies via keyword-only arguments (`*, llm: Any`) or `**kwargs`; ResearchGraph and MetaReasoningGraph nodes receive dependencies via `config: RunnableConfig = None`
3. All Pydantic models and NDJSON event schemas must be defined in `backend/agent/schemas.py`
4. All storage operations must be async and use the `SQLiteDB` and `QdrantStorage` classes; both use raw `dict` returns (no ORM row types)
5. All search operations must go through the `HybridSearcher` abstraction
6. All reranking operations must go through the `Reranker` class
7. All embedding operations must go through the `BatchEmbedder` class
8. Every function must declare its error conditions (what it raises or catches internally)
9. Edge functions control graph routing and must be documented alongside the node functions they route between
10. Graph builder functions (`build_conversation_graph`, `build_research_graph`, `build_meta_reasoning_graph`) wire nodes and edges into compiled LangGraph StateGraphs
11. The provider layer abstracts LLM and embedding backends behind ABC interfaces, with `ProviderRegistry` resolving the active provider at runtime

### Non-Functional Requirements

- All async functions must support cancellation via `asyncio.CancelledError`
- Type annotations use Python 3.14+ syntax: `list[]` not `List[]`, `| None` not `Optional[]`, `dict` not `Dict`
- All state reads/writes must be documented per node function
- Error handling must follow the propagation rules defined in spec-12

## Key Technical Details

### State Schemas

```python
# backend/agent/state.py

class ConversationState(TypedDict):
    session_id: str
    messages: list                              # List[BaseMessage] -- deferred import to avoid LangGraph dep at import time
    query_analysis: QueryAnalysis | None
    sub_answers: list[SubAnswer]
    selected_collections: list[str]
    llm_model: str
    embed_model: str
    intent: str                                 # "rag_query" | "collection_mgmt" | "ambiguous"
    final_response: str | None
    citations: list[Citation]
    groundedness_result: GroundednessResult | None
    confidence_score: int                       # 0-100 scale (user-facing integer)
    iteration_count: int

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
    confidence_score: float                     # Internal computation (0.0-1.0)
    answer: str | None
    citations: list[Citation]
    context_compressed: bool
    messages: list                              # AIMessage/ToolMessage for orchestrator<->tools communication
    _no_new_tools: bool                         # Flag: orchestrator produced no tool calls (F4)
    _needs_compression: bool                    # Flag: context exceeds token budget (F3)

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
    attempted_strategies: set[str]              # FR-015: dedup -- prevents repeating failed strategies
```

**Dual confidence scale**: `ConversationState.confidence_score` is `int` 0-100 (user-facing). `ResearchState.confidence_score` is `float` 0.0-1.0 (internal). Conversion happens in `aggregate_answers` via `int(score * 100)`. The edge function `should_continue_loop` divides `config.confidence_threshold` (int 0-100) by 100 before comparing against `ResearchState.confidence_score`.

### Pydantic Schemas (`backend/agent/schemas.py`)

The module defines 40+ models. Key categories:

**Agent-internal models:**
```python
class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: list[str]                    # max 5 decomposed sub-questions
    clarification_needed: str | None            # human-readable clarification prompt
    collections_hint: list[str]                 # suggested collection names to search
    complexity_tier: Literal[
        "factoid", "lookup", "comparison", "analytical", "multi_hop"
    ]

class RetrievedChunk(BaseModel): ...            # chunk_id, text, collection, dense_score, rerank_score, parent_id, ...
class ParentChunk(BaseModel): ...               # parent_id, text, collection, document_id, ...
class Citation(BaseModel): ...                  # passage_id, text, collection, relevance_score, ...
class SubAnswer(BaseModel): ...                 # sub_question, answer, citations, confidence_score (int 0-100)

class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: str | None
    explanation: str

class GroundednessResult(BaseModel):
    verifications: list[ClaimVerification]
    overall_grounded: bool                      # True if >50% claims supported
    confidence_adjustment: float                # modifier applied to confidence score
```

**API response/request models:**
```python
class CollectionResponse(BaseModel): ...
class CollectionCreateRequest(BaseModel): ...
class DocumentResponse(BaseModel): ...
class ChatRequest(BaseModel): ...
class AnswerResponse(BaseModel): ...
class IngestionJobResponse(BaseModel): ...
class ProviderResponse(BaseModel): ...
class ProviderConfigRequest(BaseModel): ...
class ProviderKeyRequest(BaseModel): ...
class ProviderHealthSchema(BaseModel): ...
class ProviderDetailResponse(BaseModel): ...
class SettingsResponse(BaseModel): ...
class SettingsUpdateRequest(BaseModel): ...
class StatsResponse(BaseModel): ...
class QueryTraceResponse(BaseModel): ...
class QueryTraceDetailResponse(BaseModel): ...
class ModelInfo(BaseModel): ...
class HealthServiceStatus(BaseModel): ...
class HealthResponse(BaseModel): ...
class ErrorDetail(BaseModel): ...
class ErrorResponse(BaseModel): ...
class Passage(BaseModel): ...
class ReasoningStep(BaseModel): ...
class TraceResponse(BaseModel): ...
```

**NDJSON streaming event models:**
```python
class SessionEvent(TypedDict): ...             # type="session", session_id
class StatusEvent(TypedDict): ...              # type="status", node (NOT message)
class ChunkEvent(TypedDict): ...               # type="chunk", text (NOT content)
class CitationEvent(TypedDict): ...            # type="citation", citations list
class MetaReasoningEvent(TypedDict): ...       # type="meta_reasoning", strategies_attempted
class ConfidenceEvent(TypedDict): ...          # type="confidence", score (int 0-100)
class GroundednessEvent(TypedDict): ...        # type="groundedness", overall_grounded, supported, unsupported, contradicted
class DoneEvent(TypedDict): ...                # type="done", latency_ms, trace_id
class ClarificationEvent(TypedDict): ...       # type="clarification", question (ends stream)
class ErrorEvent(TypedDict): ...               # type="error", message, code, trace_id
```

### Agent Node Contracts -- ConversationGraph

```python
# backend/agent/nodes.py
# All nodes return dict (partial state updates), NOT the full State TypedDict.

# --- Helper functions ---
def get_context_budget(model_name: str) -> int:
    """Return token budget for the given model name. Looks up MODEL_CONTEXT_WINDOWS."""

def _apply_groundedness_annotations(response: str, result: GroundednessResult) -> str:
    """Annotate unsupported claims with [unverified], remove contradicted claims."""

def _extract_claim_for_citation(text: str, marker: str) -> str:
    """Extract the sentence containing the citation marker from text."""

# --- Circuit breaker (module-level globals) ---
def _check_inference_circuit() -> None:
    """Raise CircuitOpenError if inference circuit breaker is open."""

def _record_inference_success() -> None:
    """Reset inference failure counter on success."""

def _record_inference_failure() -> None:
    """Increment failure count, trip circuit if threshold exceeded."""

# --- Node functions ---
async def init_session(
    state: ConversationState,
    **kwargs: Any,
) -> dict:
    """Load or create session. Restores message history from SQLite.
    Reads: state["session_id"]
    Writes: state["messages"], state["selected_collections"]
    Raises: SessionLoadError (caught internally, falls back to fresh session)
    """

async def classify_intent(
    state: ConversationState,
    *,
    llm: Any,
) -> dict:
    """Classify user intent as rag_query, collection_mgmt, or ambiguous.
    Reads: state["messages"]
    Returns: {"intent": "rag_query" | "collection_mgmt" | "ambiguous"}
    Raises: LLMCallError (caught, defaults to "rag_query")
    """

async def rewrite_query(
    state: ConversationState,
    *,
    llm: Any,
) -> dict:
    """Decompose query into sub-questions with structured output.
    Reads: state["messages"], state["selected_collections"]
    Writes: state["query_analysis"]
    Raises: StructuredOutputParseError (retry once, then single-question fallback)
    """

def request_clarification(
    state: ConversationState,
) -> dict:
    """LangGraph interrupt() -- pause graph, yield clarification question to UI.
    Calls interrupt() to checkpoint state and pause execution.
    Resumes when Command(resume=user_response) is invoked externally.
    The 2-round clarification cap is enforced by should_clarify in edges.py.
    Reads: state["query_analysis"]
    Writes: (via interrupt/resume mechanism)
    """

def fan_out(
    state: ConversationState,
    **kwargs: Any,
) -> ConversationState:
    """DEAD STUB -- actual Send() dispatch is in route_fan_out edge function.
    This node exists for graph wiring but does not perform fan-out logic.
    """

def aggregate_answers(
    state: ConversationState,
    **kwargs: Any,
) -> dict:
    """Merge sub-answers, deduplicate citations, rank by relevance.
    Reads: state["sub_answers"]
    Writes: state["final_response"], state["citations"], state["confidence_score"]
    Note: confidence_score computed via compute_confidence() -> int 0-100
    """

async def verify_groundedness(
    state: ConversationState,
    *,
    llm: Any = None,
) -> dict:
    """NLI-based claim verification against retrieved context (GAV).
    Reads: state["final_response"], state["citations"], state["sub_answers"]
    Writes: state["groundedness_result"], state["confidence_score"]
    Raises: LLMCallError (caught, sets groundedness_result=None)
    Note: llm is OPTIONAL -- if None, groundedness check is skipped.
    """

async def validate_citations(
    state: ConversationState,
    *,
    reranker: Any = None,
) -> dict:
    """Cross-encoder alignment check for each citation.
    Reads: state["final_response"], state["citations"]
    Writes: state["citations"] (corrected)
    Raises: RerankerError (caught, passes citations through unvalidated)
    Note: reranker is OPTIONAL (type Any), not CrossEncoder.
    """

async def summarize_history(
    state: ConversationState,
    **kwargs: Any,
) -> dict:
    """Compress conversation history when token budget is approached.
    Reads: state["messages"], state["llm_model"]
    Writes: state["messages"] (compressed)
    """

def format_response(
    state: ConversationState,
    **kwargs: Any,
) -> dict:
    """Apply citation annotations, confidence indicator, NDJSON formatting.
    Reads: state["final_response"], state["citations"],
           state["groundedness_result"], state["confidence_score"]
    Writes: state["final_response"] (formatted)
    """

def handle_collection_mgmt(
    state: ConversationState,
    **kwargs: Any,
) -> dict:
    """Handle collection management commands (create, delete, list).
    Out-of-scope stub. Returns a user-facing message directing
    users to the Collections page. No LLM call, no side effects.
    Reads: state["messages"]
    Writes: state["final_response"]
    """
```

### Edge Functions -- ConversationGraph

```python
# backend/agent/edges.py

def route_intent(state: ConversationState) -> str:
    """Route based on classified intent.
    Returns: "rag_query" | "collection_mgmt" | "ambiguous"
    """

def should_clarify(state: ConversationState) -> bool:
    """Determine whether clarification is needed.
    Returns True if query_analysis.is_clear is False AND iteration_count < 2.
    Returns False if query_analysis is None (defensive guard).
    """

def route_after_rewrite(state: ConversationState) -> list[Send] | str:
    """Combined routing: clarify or fan-out to research.
    If clarification is needed: returns "request_clarification".
    Otherwise: delegates to route_fan_out() returning Send() objects.
    Combined because LangGraph forbids two add_conditional_edges from same source.
    """

def route_fan_out(state: ConversationState) -> list[Send]:
    """Create a Send() for each sub-question to dispatch to ResearchGraph.
    THIS is where actual Send() dispatch happens -- fan_out node is a dead stub.
    Falls back to original query as sole sub-question if sub_questions is empty.
    Populates all ResearchState fields in each Send() payload.
    """
```

### Agent Node Contracts -- ResearchGraph

```python
# backend/agent/research_nodes.py
# All nodes use config: RunnableConfig = None for DI.
# LLM and tools are resolved from config at runtime.

# --- Helper functions ---
def normalize_query(query: str) -> str:
    """Lowercase + strip whitespace for dedup key construction."""

def dedup_key(query: str, parent_id: str) -> str:
    """Construct dedup key: f"{normalize_query(query)}:{parent_id}"."""

async def should_compress_context(state: ResearchState) -> dict:
    """Check if context token count exceeds budget. Sets _needs_compression flag in returned dict."""

def _build_citations(chunks: list[RetrievedChunk], answer_text: str) -> list[Citation]:
    """Map inline [N] references in answer text to RetrievedChunk objects."""

# --- Node functions ---
async def orchestrator(
    state: ResearchState,
    config: RunnableConfig = None,
) -> dict:
    """Decide which tools to call based on current context.
    Reads: state["sub_question"], state["retrieved_chunks"],
           state["tool_call_count"], state["iteration_count"]
    Writes: state["iteration_count"], state["messages"] (with AIMessage),
            state["_no_new_tools"]
    Raises: LLMCallError (triggers fallback_response)
    """

async def tools_node(
    state: ResearchState,
    config: RunnableConfig = None,
) -> dict:
    """Execute pending tool calls from orchestrator with retry-once (FR-016).
    Reads: state["messages"] (last AIMessage), state["retrieval_keys"],
           state["retrieved_chunks"], state["tool_call_count"]
    Writes: state["retrieved_chunks"], state["retrieval_keys"],
            state["tool_call_count"], state["messages"]
    Deduplication key: f"{normalize_query(query)}:{parent_id}"
    Both original attempt and retry count against the tool call budget.
    """

async def compress_context(
    state: ResearchState,
    config: RunnableConfig = None,
) -> dict:
    """Summarize retrieved chunks when context window is approached.
    Reads: state["retrieved_chunks"], state["llm_model"]
    Writes: state["retrieved_chunks"] (compressed), state["context_compressed"]
    On LLM failure: skip compression, continue with uncompressed chunks.
    """

async def collect_answer(
    state: ResearchState,
    config: RunnableConfig = None,
) -> dict:
    """Generate answer from retrieved chunks, compute confidence.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"], state["citations"],
            state["confidence_score"] (float 0.0-1.0)
    Confidence via compute_confidence() -- 5-signal formula, NOT LLM self-assessment.
    """

async def fallback_response(
    state: ResearchState,
) -> dict:
    """Generate graceful insufficient-information response.
    Does NOT hallucinate. States what was searched and why results were insufficient.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["answer"], state["confidence_score"] (0.0)
    """
```

### Edge Functions -- ResearchGraph

```python
# backend/agent/research_edges.py

def should_continue_loop(state: ResearchState) -> str:
    """Determine whether the orchestrator loop should continue.
    IMPORTANT (F1): Confidence is checked FIRST.
    CONFIDENCE SCALE MISMATCH: config threshold is int 0-100, state is float 0.0-1.0.
    Returns:
        "sufficient": confidence >= threshold -> collect_answer
        "exhausted": budget or tools exhausted -> meta_reasoning or fallback
        "continue": keep looping
    """

def route_after_compress_check(state: ResearchState) -> str:
    """Route after context size check.
    Reads the _needs_compression flag.
    Returns:
        "compress": token count exceeds threshold
        "continue": token count within budget, loop back to orchestrator
    """
```

### Agent Node Contracts -- MetaReasoningGraph

```python
# backend/agent/meta_reasoning_nodes.py (NOT nodes.py)
# All nodes use config: RunnableConfig = None for DI.
# Reranker + LLM resolved from config.

# --- Constants ---
STRATEGY_WIDEN_SEARCH = "WIDEN_SEARCH"
STRATEGY_CHANGE_COLLECTION = "CHANGE_COLLECTION"
STRATEGY_RELAX_FILTERS = "RELAX_FILTERS"
FALLBACK_ORDER = [STRATEGY_WIDEN_SEARCH, STRATEGY_CHANGE_COLLECTION, STRATEGY_RELAX_FILTERS]

# --- Helper functions ---
def _build_modified_state_widen(alternative_queries: list[str]) -> dict: ...
def _build_modified_state_change_collection(alternative_queries: list[str]) -> dict: ...
def _build_modified_state_relax() -> dict: ...

# --- Node functions ---
async def generate_alternative_queries(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Produce 3 rephrased query variants using LLM (FR-001).
    Strategies: synonym replacement, sub-component breakdown, scope broadening.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["alternative_queries"]
    Graceful degradation: on LLM failure, return [original sub_question].
    """

async def evaluate_retrieval_quality(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Score all chunks with cross-encoder (FR-002, FR-003).
    Uses Reranker (NOT LLM self-assessment). Reranker resolved from config DI.
    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["mean_relevance_score"], state["chunk_relevance_scores"]
    """

async def decide_strategy(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Select recovery strategy based on quantitative evaluation (FR-004).
    Decision logic:
      mean < threshold AND chunk_count < 3     -> WIDEN_SEARCH
      mean < threshold AND chunk_count >= 3    -> CHANGE_COLLECTION
      mean >= threshold AND variance > var_thr -> RELAX_FILTERS
      mean >= threshold AND variance <= var_thr -> None (report_uncertainty)
      attempt >= max_attempts                  -> None (forced, FR-006)
      candidate in attempted_strategies        -> next untried or None (FR-015)
    Reads: state["mean_relevance_score"], state["chunk_relevance_scores"],
           state["retrieved_chunks"], state["meta_attempt_count"],
           state["attempted_strategies"]
    Writes: state["recovery_strategy"], state["modified_state"],
            state["meta_attempt_count"], state["attempted_strategies"]
    """

async def report_uncertainty(
    state: MetaReasoningState,
    config: RunnableConfig = None,
) -> dict:
    """Generate honest I-don't-know response (FR-007, FR-008).
    Uses LLM with REPORT_UNCERTAINTY_SYSTEM prompt. No-fabrication guardrail.
    Reads: state["sub_question"], state["retrieved_chunks"],
           state["mean_relevance_score"], state["meta_attempt_count"],
           state["alternative_queries"]
    Writes: state["answer"], state["uncertainty_reason"]
    """
```

### Edge Functions -- MetaReasoningGraph

```python
# backend/agent/meta_reasoning_edges.py

def route_after_strategy(state: MetaReasoningState) -> str:
    """Route after decide_strategy.
    Returns:
        "retry": recovery_strategy is set -> END (modified_state ready for
                 ResearchGraph to re-enter with new parameters)
        "report": recovery_strategy is None -> report_uncertainty
    """
```

### Graph Builders

```python
# backend/agent/conversation_graph.py
def build_conversation_graph(
    research_graph: Any = None,
    checkpointer: Any = None,
) -> Any:
    """Build and return the compiled ConversationGraph.
    Wires: init_session -> classify_intent -> route_intent ->
           rewrite_query -> route_after_rewrite -> [research/clarify] ->
           aggregate_answers -> verify_groundedness -> validate_citations ->
           summarize_history -> format_response
    """

# backend/agent/research_graph.py
def build_research_graph(
    tools: list,
    meta_reasoning_graph: Any = None,
) -> Any:
    """Build and compile the ResearchGraph.
    Contains inner function meta_reasoning_mapper for subgraph dispatch.
    Wires: orchestrator -> tools_node -> should_continue_loop ->
           [collect_answer / meta_reasoning / compress_context / fallback]
    """

# backend/agent/meta_reasoning_graph.py
def build_meta_reasoning_graph() -> Any:
    """Build and compile the MetaReasoningGraph.
    Wires: generate_alternative_queries -> evaluate_retrieval_quality ->
           decide_strategy -> route_after_strategy -> [retry(END) / report_uncertainty]
    """
```

### Confidence Scoring (`backend/agent/confidence.py`)

```python
def compute_confidence(
    chunks: list[Any],
    top_k: int = 5,
    expected_chunk_count: int = 5,
    num_collections_searched: int = 1,
    num_collections_total: int = 1,
) -> float | int:
    """Compute confidence score from retrieval signals.
    Dual call patterns:
    1. New (spec-03): list[RetrievedChunk] -> float 0.0-1.0 (via _signal_confidence)
    2. Legacy (spec-02): list[dict] with "relevance_score" -> int 0-100 (via _legacy_confidence)
    5-signal formula (R8), NOT LLM self-assessment.
    """

def _legacy_confidence(chunks: list[dict], top_k: int, ...) -> int: ...
def _signal_confidence(chunks: list[RetrievedChunk], top_k: int, ...) -> float: ...
```

### Score Normalizer (`backend/retrieval/score_normalizer.py`)

```python
def normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Per-collection min-max normalization of dense_score.
    Groups chunks by collection, normalizes within each group to [0.0, 1.0].
    """
```

### Agent Tools (`backend/agent/tools.py`)

Tools are created via **closure-based factory**, NOT standalone `@tool` decorators:

```python
def create_research_tools(
    searcher: HybridSearcher,
    reranker: Reranker,
    parent_store: ParentStore,
) -> list:
    """Factory that creates 6 tool instances with injected dependencies.
    Returns list of LangChain tool objects ready for llm.bind_tools().
    """

    # Inner @tool functions (closures over searcher, reranker, parent_store):

    @tool
    async def search_child_chunks(
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
    ) -> list[RetrievedChunk]:
        """Hybrid dense+BM25 search + cross-encoder reranking.
        Raises: QdrantConnectionError, EmbeddingError
        """

    @tool
    async def retrieve_parent_chunks(
        parent_ids: list[str],
    ) -> list[ParentChunk]:
        """Fetch parent chunks from SQLite by ID list. Missing IDs silently skipped.
        Raises: SQLiteError
        """

    @tool
    async def cross_encoder_rerank(
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score and rerank (query, chunk) pairs.
        Raises: RerankerError
        """

    @tool
    async def filter_by_collection(
        collection_name: str,
    ) -> dict:
        """Constrain subsequent searches to a specific named collection.
        Returns: {"active_collection_filter": collection_name}
        """

    @tool
    async def filter_by_metadata(
        filters: dict,
    ) -> dict:
        """Apply Qdrant payload filter constraints.
        Supported filter keys: doc_type, page_range, source_file, breadcrumb
        Returns: {"active_metadata_filters": filters}
        """

    @tool
    async def semantic_search_all_collections(
        query: str,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all collections with score normalization + reranking.
        Raises: QdrantConnectionError, EmbeddingError
        """

    return [
        search_child_chunks,
        retrieve_parent_chunks,
        cross_encoder_rerank,
        filter_by_collection,
        filter_by_metadata,
        semantic_search_all_collections,
    ]
```

### Ingestion Pipeline (`backend/ingestion/pipeline.py`)

```python
@dataclass
class IngestionResult:
    """Result of a completed ingestion job."""
    document_id: str
    job_id: str
    status: str                                 # "completed", "failed", "duplicate", etc.
    chunks_processed: int = 0
    chunks_skipped: int = 0
    error: str | None = None                    # NOT error_msg, NO elapsed_ms

class UpsertBuffer:
    """Buffers Qdrant upsert batches with pause/resume on outage.
    MAX_CAPACITY = 1000.
    """
    def __init__(self) -> None: ...
    def add(self, points: list[dict]) -> bool: ...
    async def flush(self, qdrant: QdrantClientWrapper, collection_id: str) -> int: ...
    @property
    def pending_count(self) -> int: ...          # NOTE: @property, NOT a method call

class IngestionPipeline:
    def __init__(
        self,
        db: SQLiteDB,
        qdrant: QdrantClientWrapper,            # NOTE: QdrantClientWrapper, NOT QdrantStorage
        embedding_provider=None,
    ) -> None:
        """ChunkSplitter and BatchEmbedder created internally -- NOT injected."""

    async def ingest_file(
        self,
        file_path: str,
        filename: str,
        collection_id: str,
        document_id: str,
        job_id: str,
        file_hash: str | None = None,
    ) -> IngestionResult:
        """Full ingestion pipeline: parse -> split -> embed -> upsert.
        Steps: spawn Rust worker -> read NDJSON -> ChunkSplitter ->
               BatchEmbedder -> batch upsert to Qdrant -> store parents in SQLite
        Returns: IngestionResult with chunk counts and status
        Raises: IngestionError, EmbeddingError, QdrantConnectionError
        """

    # NOTE: check_duplicate is on IncrementalChecker, NOT on IngestionPipeline
```

### Chunk Splitter (`backend/ingestion/chunker.py`)

```python
@dataclass
class ParentChunkData: ...                      # Intermediate chunk data structure

class ChunkSplitter:
    def __init__(self, parent_size: int | None = None, child_size: int | None = None): ...
    def split_into_parents(self, raw_chunks: list[dict], source_file: str) -> list[ParentChunkData]: ...
    def split_parent_into_children(self, parent_text: str, target_size: int | None = None) -> list[str]: ...
    @staticmethod
    def prepend_breadcrumb(text: str, heading_path: list[str]) -> str: ...
    @staticmethod
    def compute_point_id(source_file: str, page: int, chunk_index: int) -> str:
        """Deterministic UUID5 for idempotent chunk upserts."""
```

### Incremental Checker (`backend/ingestion/incremental.py`)

```python
class IncrementalChecker:
    def __init__(self, db: SQLiteDB): ...
    @staticmethod
    def compute_file_hash(file_path: str) -> str: ...   # NOTE: @staticmethod, no self param
    async def check_duplicate(self, collection_id: str, file_hash: str) -> tuple[bool, str | None]:
        """Returns (is_duplicate, existing_document_id).
        NOTE: This method lives here, NOT on IngestionPipeline.
        """
    async def check_change(self, collection_id: str, filename: str, new_hash: str) -> tuple[bool, str | None]: ...
```

### Embedder (`backend/ingestion/embedder.py`)

```python
def validate_embedding(
    vector: list[float],
    expected_dim: int,
) -> tuple[bool, str]:
    """STANDALONE function (NOT a method). Returns (is_valid, reason).
    Checks: dimension count, NaN values, zero vector, magnitude threshold (1e-6).
    """

class BatchEmbedder:
    def __init__(
        self,
        model: str | None = None,
        max_workers: int | None = None,
        batch_size: int | None = None,
        embedding_provider=None,
    ) -> None:
        """Defaults from settings if not specified."""

    async def embed_chunks(
        self,
        texts: list[str],
    ) -> tuple[list[list[float] | None], int]:
        """Embed a list of texts in parallel batches with validation.
        Returns: (embeddings, chunks_skipped) where embeddings preserves input
        order. Invalid embeddings are replaced with None and counted as skipped.
        Raises: EmbeddingError (if all retries exhausted)
        """
```

### Hybrid Searcher (`backend/retrieval/searcher.py`)

```python
class HybridSearcher:
    def __init__(
        self,
        client: AsyncQdrantClient,
        settings: Settings,
    ) -> None:
        """NOT (qdrant, embedder, reranker) -- uses raw AsyncQdrantClient + Settings."""

    # --- Circuit breaker methods ---
    async def _check_circuit(self) -> None: ...  # NOTE: async in HybridSearcher
    def _record_success(self) -> None: ...
    def _record_failure(self) -> None: ...

    # --- Query helpers ---
    def _build_filter(self, filters: dict | None) -> Filter | None: ...
    def _points_to_chunks(self, points: list, collection: str) -> list[RetrievedChunk]: ...

    async def search(
        self,
        query: str,
        collection: str,
        top_k: int = 20,
        filters: dict | None = None,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Hybrid dense+BM25 search with circuit breaker (C1).
        Uses Qdrant query_points with prefetch (dense + sparse) + Fusion.RRF.
        Raises: QdrantConnectionError
        """

    async def search_all_collections(
        self,
        query: str,
        top_k: int = 20,
        embed_fn: Any = None,
    ) -> list[RetrievedChunk]:
        """Fan-out search across all available collections.
        Queries each collection in parallel, merges results.
        Partial failures return results from successful collections only.
        Raises: QdrantConnectionError
        """
```

### Reranker (`backend/retrieval/reranker.py`)

```python
class Reranker:
    def __init__(
        self,
        settings: Settings,
    ) -> None:
        """NOT (model_name: str). Loads model from settings.
        Lazy import of sentence_transformers in __init__ to avoid PyTorch import at module level.
        """

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score and rerank (query, chunk) pairs with cross-encoder.
        Uses model.rank() (NOT model.predict()).
        Returns: Top-k chunks sorted by cross-encoder score descending,
                 with rerank_score populated.
        Raises: RerankerError
        """

    # NOTE: score_pair() DOES NOT EXIST -- removed from spec.
```

### Qdrant Storage (`backend/storage/qdrant_client.py`)

The file contains two client classes: `QdrantClientWrapper` (legacy, Phase 1) and `QdrantStorage` (spec-07). Both coexist. The spec-07 `QdrantStorage` is the primary interface.

**Data classes (same file):**
```python
@dataclass
class SparseVector:
    indices: list[int]
    values: list[float]

@dataclass
class QdrantPoint:
    id: int | str
    vector: list[float]                         # Dense embedding (768 dims)
    sparse_vector: SparseVector | None          # BM25 token sparse vector
    payload: dict

@dataclass
class SearchResult:
    id: int | str
    score: float                                # Hybrid score after weighted rank fusion
    payload: dict
```

**QdrantStorage interface:**
```python
class QdrantStorage:
    def __init__(self, host: str = "localhost", port: int = 6333) -> None: ...

    # --- Circuit breaker ---
    def _check_circuit(self): ...
    def _record_success(self): ...
    def _record_failure(self): ...

    async def health_check(self) -> bool:
        """Return True if Qdrant is reachable, False otherwise."""

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int = 768,
        distance: str = "cosine",
    ) -> None:
        """Create collection with dense (HNSW cosine) + sparse (BM25 IDF) config.
        Raises: QdrantConnectionError
        """

    async def collection_exists(self, collection_name: str) -> bool:
        """Return True if the collection exists in Qdrant."""

    async def delete_collection(self, collection_name: str) -> None:
        """Remove collection and all its points.
        Raises: QdrantConnectionError
        """

    async def get_collection_info(self, collection_name: str) -> dict:
        """Return {name, points_count, vector_size, status} for the collection.
        Raises: QdrantConnectionError
        """

    async def batch_upsert(
        self,
        collection_name: str,
        points: list[QdrantPoint],
    ) -> int:
        """Idempotent batch upsert. Validates all 11 payload fields. Returns count.
        Raises: QdrantConnectionError (after retries exhausted)
        """

    async def search_hybrid(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: SparseVector | None,
        top_k: int = 10,
        dense_weight: float = 0.6,
        sparse_weight: float = 0.4,
        score_threshold: float | None = None,
    ) -> list[SearchResult]:
        """Weighted rank fusion of dense cosine + sparse BM25 search results.
        Raises: QdrantConnectionError
        """

    async def delete_points(self, collection_name: str, point_ids: list[int]) -> int:
        """Delete points by ID list. Returns count of submitted IDs.
        Raises: QdrantConnectionError
        """

    async def delete_points_by_filter(
        self,
        collection_name: str,
        filter: dict,
    ) -> int:
        """Delete points matching payload filter dict. Returns 0 (count unknown).
        Raises: QdrantConnectionError
        """

    async def get_point(
        self,
        collection_name: str,
        point_id: int,
    ) -> dict | None:
        """Return {id, vector, payload} for a single point, or None if not found."""

    async def get_points_by_ids(
        self,
        collection_name: str,
        point_ids: list[int],
    ) -> list[dict]:
        """Batch retrieval of points by ID list."""

    async def scroll_points(
        self,
        collection_name: str,
        limit: int = 100,
        offset: int | None = None,
    ) -> tuple[list[dict], int | None]:
        """Cursor-based iteration through a collection. Returns (points, next_offset)."""
```

### Parent Store (`backend/storage/parent_store.py`)

```python
class ParentStore:
    """Read parent chunks from SQLite parent_chunks table."""

    def __init__(self, db: SQLiteDB): ...

    async def get_by_ids(self, parent_ids: list[str]) -> list[ParentChunk]:
        """Fetch parent chunks by ID list. Missing IDs silently skipped.
        Uses SQL column aliases (id AS parent_id, collection_id AS collection).
        """

    async def get_all_by_collection(self, collection_id: str) -> list[ParentChunk]: ...
```

### SQLite Database (`backend/storage/sqlite_db.py`)

All methods use individual parameters and return raw `dict` objects. There are NO ORM row types (`CollectionRow`, `DocumentRow`, etc.) or create types (`CollectionCreate`, `DocumentCreate`, etc.).

```python
class SQLiteDB:
    def __init__(self, db_path: str) -> None: ...
    async def connect(self) -> None:
        """Open connection, enable WAL + FKs, init schema."""
    async def close(self) -> None: ...
    async def __aenter__(self): ...
    async def __aexit__(self, ...): ...

    # --- Collections ---
    async def create_collection(
        self, id: str, name: str, embedding_model: str,
        chunk_profile: str, qdrant_collection_name: str,
        description: str | None = None,
    ) -> None: ...
    async def get_collection(self, collection_id: str) -> dict | None: ...
    async def get_collection_by_name(self, name: str) -> dict | None: ...
    async def list_collections(self) -> list[dict]: ...
    async def update_collection(self, collection_id: str, **kwargs: Any) -> None: ...
    async def delete_collection(self, collection_id: str) -> None: ...

    # --- Documents ---
    async def create_document(
        self, id: str, collection_id: str, filename: str, file_hash: str,
        file_path: str | None = None, status: str = "pending",
    ) -> None: ...
    async def get_document(self, doc_id: str) -> dict | None: ...
    async def get_document_by_hash(self, collection_id: str, file_hash: str) -> dict | None: ...
    async def list_documents(self, collection_id: str) -> list[dict]: ...
    async def update_document(self, doc_id: str, **kwargs: Any) -> None: ...
    async def delete_document(self, doc_id: str) -> None: ...

    # --- Ingestion Jobs ---
    async def create_ingestion_job(
        self, id: str, document_id: str, status: str = "started",
    ) -> None: ...
    async def get_ingestion_job(self, job_id: str) -> dict | None: ...
    async def list_ingestion_jobs(self, document_id: str) -> list[dict]: ...
    async def update_ingestion_job(
        self, job_id: str, status: str | None = None,
        chunks_processed: int | None = None, chunks_skipped: int | None = None,
        finished_at: str | None = None, error_msg: str | None = None,
    ) -> None: ...

    # --- Parent Chunks ---
    async def create_parent_chunk(
        self, id: str, collection_id: str, document_id: str,
        text: str, metadata_json: str | None = None,
    ) -> None: ...
    async def get_parent_chunk(self, parent_id: str) -> dict | None: ...
    async def get_parent_chunks_batch(self, parent_ids: list[str]) -> list[dict]: ...
    async def list_parent_chunks(
        self, collection_id: str, document_id: str | None = None,
    ) -> list[dict]: ...
    async def delete_parent_chunks(self, document_id: str) -> None: ...

    # --- Query Traces ---
    async def create_query_trace(
        self, id: str, session_id: str, query: str,
        collections_searched: str, chunks_retrieved_json: str, latency_ms: int,
        llm_model: str | None = None, embed_model: str | None = None,
        confidence_score: int | None = None,
        sub_questions_json: str | None = None,
        reasoning_steps_json: str | None = None,
        strategy_switches_json: str | None = None,
        meta_reasoning_triggered: bool = False,
        provider_name: str | None = None,
    ) -> None: ...
    async def list_query_traces(self, session_id: str, limit: int = 100) -> list[dict]: ...
    async def list_traces(
        self, session_id: str | None = None, collection_id: str | None = None,
        min_confidence: int | None = None, max_confidence: int | None = None,
        limit: int = 20, offset: int = 0,
    ) -> list[dict]: ...
    async def get_trace(self, trace_id: str) -> dict | None: ...
    async def get_query_traces_by_timerange(
        self, start_ts: str, end_ts: str, limit: int = 1000,
    ) -> list[dict]: ...

    # --- Settings ---
    async def get_setting(self, key: str) -> str | None: ...
    async def set_setting(self, key: str, value: str) -> None: ...
    async def list_settings(self) -> dict[str, str]: ...
    async def delete_setting(self, key: str) -> None: ...

    # --- Providers ---
    async def create_provider(
        self, name: str, api_key_encrypted: str | None = None,
        base_url: str | None = None, is_active: bool = True,
    ) -> None: ...
    async def get_provider(self, name: str) -> dict | None: ...
    async def list_providers(self) -> list[dict]: ...
    async def update_provider(
        self, name: str, is_active: bool | None = None,
        api_key_encrypted: str | None = None, base_url: str | None = None,
    ) -> None: ...
    async def delete_provider(self, name: str) -> None: ...
    async def get_active_provider(self) -> dict | None:
        """Return the first active provider, or None."""
    async def upsert_provider(
        self, name: str, provider_type: str | None = None,
        config_json: str | None = None, is_active: bool = True,
    ) -> None:
        """Insert or replace a provider record.
        Deactivates other providers on INSERT OR REPLACE (fixed from spec-10 bug).
        """
```

### Provider Layer (`backend/providers/`)

```python
# backend/providers/base.py

class ProviderRateLimitError(Exception):
    """Raised when provider rate limit is exceeded."""
    def __init__(self, ...): ...

class LLMProvider(ABC):
    """Abstract interface for LLM inference providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a complete response."""

    @abstractmethod
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        """Generate a streaming response, yielding tokens."""

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    def get_model_name(self) -> str: ...

class EmbeddingProvider(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for a list of texts."""

    @abstractmethod
    async def embed_single(self, text: str, model: str | None = None) -> list[float]: ...

    @abstractmethod
    def get_model_name(self) -> str: ...

    @abstractmethod
    def get_dimension(self) -> int: ...

# backend/providers/registry.py

class ProviderRegistry:
    """Resolves provider names to instances. Reads active provider from DB on each call."""

    def __init__(self, settings: Settings) -> None: ...

    async def initialize(self, ...): ...

    async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
        """Get the currently active LLM provider instance."""

    async def get_active_langchain_model(self, db: SQLiteDB) -> BaseChatModel:
        """Return a LangChain BaseChatModel for the active provider.
        Used by agent graph nodes (ainvoke, with_structured_output, bind_tools).
        Coexists with get_active_llm() which returns LLMProvider for httpx streaming.
        """

    async def get_embedding_provider(self) -> EmbeddingProvider: ...  # NOTE: async

    async def set_active_provider(self, db: SQLiteDB, name: str, config: dict | None = None) -> bool: ...

# backend/providers/key_manager.py

class KeyManager:
    """Fernet symmetric encryption for API keys.
    Loads EMBEDINATOR_FERNET_KEY from environment.
    """

    def __init__(self) -> None: ...               # NOTE: no key param, loads from EMBEDINATOR_FERNET_KEY env var
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...
    def is_valid_key(self, ciphertext: str) -> bool: ...
```

**Concrete providers** (all in `backend/providers/`):
- `ollama.py` -- Ollama local provider
- `openrouter.py` -- OpenRouter cloud provider
- `openai.py` -- OpenAI cloud provider
- `anthropic.py` -- Anthropic cloud provider

### Error Hierarchy (`backend/errors.py`)

```python
class EmbeddinatorError(Exception):             # Base for all project errors
    """Base exception for The Embedinator."""

class QdrantConnectionError(EmbeddinatorError): ...   # Qdrant unreachable or query failure
class OllamaConnectionError(EmbeddinatorError): ...   # Ollama unreachable
class SQLiteError(EmbeddinatorError): ...              # SQLite operation failure
class LLMCallError(EmbeddinatorError): ...             # LLM inference failure
class EmbeddingError(EmbeddinatorError): ...           # Embedding generation failure
class IngestionError(EmbeddinatorError): ...           # Ingestion pipeline failure
class SessionLoadError(EmbeddinatorError): ...         # Session restore failure
class StructuredOutputParseError(EmbeddinatorError): ...  # Pydantic structured output parse failure
class RerankerError(EmbeddinatorError): ...            # Cross-encoder inference failure
class CircuitOpenError(EmbeddinatorError): ...         # Circuit breaker is open
```

### Configuration (`backend/config.py`)

```python
class Settings(BaseSettings):
    """Pydantic Settings for centralized configuration.
    Reads from environment variables with EMBEDINATOR_ prefix.
    """
    # Includes: db_path, qdrant_host, qdrant_port, ollama_url,
    # embedding_model, reranker_model, llm_model, confidence_threshold (int 0-100),
    # meta_relevance_threshold (float), meta_variance_threshold (float),
    # max_meta_attempts, context_window, qdrant_upsert_batch_size, ...
```

## Dependencies

### Spec Dependencies
- **spec-02-conversation-graph**: Defines ConversationGraph nodes and edges that use these contracts
- **spec-03-research-graph**: Defines ResearchGraph nodes and edges that use these contracts
- **spec-04-meta-reasoning**: Defines MetaReasoningGraph nodes and edges that use these contracts
- **spec-05-accuracy**: Defines groundedness verification and citation validation using these contracts
- **spec-06-ingestion**: Defines ingestion pipeline using these contracts
- **spec-07-storage**: Defines SQLiteDB and QdrantStorage using these contracts
- **spec-08-api**: API routes call these interfaces
- **spec-10-providers**: Provider interfaces (LLMProvider, EmbeddingProvider) and registry
- **spec-12-errors**: Error types raised by these contracts

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `pydantic` | `>=2.12` | Schemas, structured output, validation |
| `pydantic-settings` | (via pydantic) | `BaseSettings` for config |
| `langchain_core` | (via langchain) | `BaseMessage`, `BaseChatModel`, `tool` decorator, `RunnableConfig` |
| `langgraph` | `>=1.0.10` | `StateGraph`, `Send`, `interrupt`, `Command`, `MemorySaver` |
| `sentence-transformers` | `>=5.2.3` | CrossEncoder model for Reranker (lazy import) |
| `qdrant-client` | `>=1.17.0` | `AsyncQdrantClient` type for HybridSearcher |
| `aiosqlite` | `>=0.21` | Async SQLite operations |
| `cryptography` | `>=44.0` | Fernet encryption for KeyManager |
| `httpx` | `>=0.28` | HTTP client for cloud providers |
| `tenacity` | `>=9.0` | Retry logic |
| `structlog` | `>=24.0` | Structured logging |

## Acceptance Criteria

1. All TypedDict state schemas (`ConversationState`, `ResearchState`, `MetaReasoningState`) are fully defined with correct types and all fields documented
2. All 40+ Pydantic schemas and 10 NDJSON event models in `backend/agent/schemas.py` are defined and importable
3. Every ConversationGraph node function has a complete type signature with correct DI pattern (`*, llm: Any` or `**kwargs`)
4. Every ResearchGraph and MetaReasoningGraph node function has `config: RunnableConfig = None` parameter
5. All edge functions (`route_intent`, `should_clarify`, `route_after_rewrite`, `route_fan_out`, `should_continue_loop`, `route_after_compress_check`, `route_after_strategy`) are documented with return types and routing logic
6. All 3 graph builder functions are documented with their wiring topology
7. The closure-based tool factory `create_research_tools()` is documented with all 6 inner tools
8. Storage classes (`SQLiteDB`, `QdrantStorage`) define all CRUD methods with individual parameter signatures and `dict` returns
9. `HybridSearcher` and `Reranker` define their complete interfaces with `Settings`-based constructors
10. `BatchEmbedder` defines batch embedding with `embed_chunks` (not `embed_batch`) returning `tuple[list[list[float] | None], int]`
11. `IngestionPipeline` defines full ingestion flow with `@dataclass IngestionResult` (not BaseModel)
12. Provider ABCs (`LLMProvider`, `EmbeddingProvider`), `ProviderRegistry`, and `KeyManager` are fully documented
13. Error hierarchy from `backend/errors.py` is completely enumerated including `CircuitOpenError`
14. No fictional types referenced (no `CollectionCreate`, `DocumentRow`, `EmbeddingResult`, `ProviderRow`, etc.)
15. Dual confidence scale (int 0-100 user-facing vs float 0.0-1.0 internal) is explicitly documented with conversion points

## Architecture Reference

### Dependency Injection Patterns

The codebase uses three distinct DI patterns depending on the graph layer:

**Pattern 1 -- ConversationGraph nodes** (keyword-only args or `**kwargs`):
```python
async def classify_intent(
    state: ConversationState,
    *,
    llm: Any,                                   # injected via graph compile config
) -> dict:
```

**Pattern 2 -- ResearchGraph / MetaReasoningGraph nodes** (RunnableConfig):
```python
async def orchestrator(
    state: ResearchState,
    config: RunnableConfig = None,               # LLM + tools resolved from config
) -> dict:
```

**Pattern 3 -- Tool factory** (closure injection):
```python
def create_research_tools(
    searcher: HybridSearcher,
    reranker: Reranker,
    parent_store: ParentStore,
) -> list:
    # Inner @tool functions close over injected dependencies
```

### Error Propagation Rules

| Layer | Catches | Bubbles Up | Notes |
|-------|---------|-----------|-------|
| Storage (`qdrant_client`, `sqlite_db`) | Raw HTTP/DB errors | `QdrantConnectionError`, `SQLiteError` | Wraps raw exceptions with context |
| Ingestion (`pipeline`, `embedder`) | Storage errors, Rust worker errors | `IngestionError`, `EmbeddingError` | Logs per-chunk failures, continues batch |
| Agent (`nodes`, `tools`) | `LLMCallError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError` | Node-specific fallback | Caught internally with graceful degradation |
| API (`routes`) | All `EmbeddinatorError` subtypes | HTTP error responses | Maps to status codes, logs internally |

### Query-Adaptive Retrieval Depth

The `complexity_tier` in `QueryAnalysis` drives retrieval parameters:

| Tier | top_k | max_iterations | max_tool_calls | Confidence Threshold |
|------|-------|---------------|----------------|---------------------|
| `factoid` | 5 | 3 | 3 | 0.7 |
| `lookup` | 10 | 5 | 5 | 0.6 |
| `comparison` | 15 | 7 | 6 | 0.55 |
| `analytical` | 25 | 10 | 8 | 0.5 |
| `multi_hop` | 30 | 10 | 8 | 0.45 |
