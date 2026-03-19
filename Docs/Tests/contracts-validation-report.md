# Contract Validation Report

**Date**: 2026-03-17
**Validated by**: A1 (quality-engineer)
**Source**: Docs/PROMPTS/spec-11-interfaces/11-specify.md
**Target**: Live codebase (branch 011-component-interfaces)

## Summary

- Sections validated: 10/10
- Discrepancies found: 15
- Discrepancies fixed: 15
- Remaining discrepancies: 0

## Section-by-Section Results

### State Schemas (T003)

- ConversationState: [PASS] -- 13 fields match (task description says 12 but spec and code both have 13)
- ResearchState: [PASS] -- 16 fields match exactly
- MetaReasoningState: [PASS] -- 11 fields match exactly
- Dual confidence scale documented correctly: int 0-100 (ConversationState) vs float 0.0-1.0 (ResearchState)

### ConversationGraph Nodes — 11 functions (T004)

- init_session: [PASS] -- `async def init_session(state: ConversationState, **kwargs: Any) -> dict`
- classify_intent: [PASS] -- `async def classify_intent(state: ConversationState, *, llm: Any) -> dict`
- rewrite_query: [PASS] -- `async def rewrite_query(state: ConversationState, *, llm: Any) -> dict`
- request_clarification: [PASS] -- `def request_clarification(state: ConversationState) -> dict`
- fan_out: [PASS] -- `def fan_out(state: ConversationState, **kwargs: Any) -> ConversationState`
- aggregate_answers: [PASS] -- `def aggregate_answers(state: ConversationState, **kwargs: Any) -> dict`
- verify_groundedness: [PASS] -- `async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict`
- validate_citations: [PASS] -- `async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict`
- summarize_history: [PASS] -- `async def summarize_history(state: ConversationState, **kwargs: Any) -> dict`
- format_response: [PASS] -- `def format_response(state: ConversationState, **kwargs: Any) -> dict`
- handle_collection_mgmt: [PASS] -- `def handle_collection_mgmt(state: ConversationState, **kwargs: Any) -> dict`

**Helpers:**
- get_context_budget: [PASS]
- _apply_groundedness_annotations: [PASS]
- _extract_claim_for_citation: [FIXED] -- Spec had `(response: str, citation: Citation)`, code has `(text: str, marker: str)`
- _check_inference_circuit, _record_inference_success, _record_inference_failure: [PASS]

### ResearchGraph + MetaReasoningGraph Nodes (T005)

**ResearchGraph nodes (5):**
- orchestrator: [PASS] -- `config: RunnableConfig = None`
- tools_node: [PASS] -- `config: RunnableConfig = None`
- compress_context: [PASS] -- `config: RunnableConfig = None`
- collect_answer: [PASS] -- `config: RunnableConfig = None`
- fallback_response: [PASS] -- no config param (correct, async with state only)

**ResearchGraph helpers:**
- normalize_query: [PASS]
- dedup_key: [FIXED] -- Spec had `dedup_key(chunk)`, code has `dedup_key(query: str, parent_id: str)`
- should_compress_context: [FIXED] -- Spec had `def ... -> bool` (sync), code has `async def ... -> dict`
- _build_citations: [FIXED] -- Spec had `(chunks, answer)`, code has `(chunks: list[RetrievedChunk], answer_text: str)`

**MetaReasoningGraph nodes (4):**
- generate_alternative_queries: [PASS] -- `config: RunnableConfig = None`
- evaluate_retrieval_quality: [PASS] -- `config: RunnableConfig = None`
- decide_strategy: [PASS] -- `config: RunnableConfig = None`
- report_uncertainty: [PASS] -- `config: RunnableConfig = None`

**MetaReasoning constants:**
- [FIXED] -- Strategy values were lowercase (`"widen_search"`), code uses UPPERCASE (`"WIDEN_SEARCH"`)

**MetaReasoning helpers:**
- _build_modified_state_widen: [FIXED] -- Spec had `(state, config)`, code has `(alternative_queries: list[str])`
- _build_modified_state_change_collection: [FIXED] -- Spec had `(state, config)`, code has `(alternative_queries: list[str])`
- _build_modified_state_relax: [FIXED] -- Spec had `(state, config)`, code has `()` (no params)

### Edge Functions — 7 total (T006)

- route_intent: [PASS] -- `(state: ConversationState) -> str`
- should_clarify: [PASS] -- `(state: ConversationState) -> bool`
- route_after_rewrite: [PASS] -- `(state: ConversationState) -> list[Send] | str`
- route_fan_out: [PASS] -- `(state: ConversationState) -> list[Send]`
- should_continue_loop: [PASS] -- `(state: ResearchState) -> str`
- route_after_compress_check: [PASS] -- `(state: ResearchState) -> str`
- route_after_strategy: [PASS] -- `(state: MetaReasoningState) -> str`

### Storage (T007)

**SQLiteDB (35+ methods):**
- Collections (6): create_collection, get_collection, get_collection_by_name, list_collections, update_collection, delete_collection -- [PASS]
- Documents (6): create_document, get_document, get_document_by_hash, list_documents, update_document, delete_document -- [PASS]
- Ingestion Jobs (4): create_ingestion_job, get_ingestion_job, list_ingestion_jobs, update_ingestion_job -- [PASS]
- Parent Chunks (5): create_parent_chunk, get_parent_chunk, get_parent_chunks_batch, list_parent_chunks, delete_parent_chunks -- [PASS]
- Query Traces (5): create_query_trace (14 params incl. provider_name), list_query_traces, list_traces, get_trace, get_query_traces_by_timerange -- [PASS]
- Settings (4): get_setting, set_setting, list_settings, delete_setting -- [PASS]
- Providers (7): create_provider, get_provider, list_providers, update_provider, delete_provider, get_active_provider, upsert_provider -- [PASS]
- Context manager: __aenter__, __aexit__ -- [PASS]
- Lifecycle: connect, close -- [PASS]
- No ORM types confirmed -- [PASS]

**QdrantStorage:**
- Data classes: SparseVector, QdrantPoint, SearchResult -- [PASS]
- QdrantClientWrapper coexists in same file -- [PASS]
- All methods verified: health_check, create_collection, collection_exists, delete_collection, get_collection_info, batch_upsert, search_hybrid, delete_points, delete_points_by_filter, get_point, get_points_by_ids, scroll_points -- [PASS]
- Method names correct: `batch_upsert` (not upsert_batch), `search_hybrid` (not hybrid_search), `delete_points_by_filter` (not delete_by_filter) -- [PASS]

**ParentStore:**
- Constructor: `def __init__(self, db)` -- [PASS]
- get_by_ids: [PASS]
- get_all_by_collection: [PASS]

### Retrieval (T008)

**HybridSearcher:**
- Constructor: `(client: AsyncQdrantClient, settings: Settings)` -- [PASS]
- _check_circuit: [FIXED] -- Spec had sync, code is async
- _record_success, _record_failure: [PASS]
- search (with embed_fn param): [PASS]
- search_all_collections: [PASS]

**Reranker:**
- Constructor: `(settings: Settings)` -- [PASS]
- rerank: `(query, chunks, top_k=5)` -- [PASS]
- score_pair: confirmed does NOT exist -- [PASS]

**ScoreNormalizer:**
- normalize_scores: module-level function -- [PASS]

### Ingestion (T009)

**IngestionResult:**
- @dataclass (not BaseModel) -- [PASS]
- Fields: document_id, job_id, status, chunks_processed=0, chunks_skipped=0, error=None -- [PASS]
- No error_msg, no elapsed_ms -- [PASS]

**UpsertBuffer:**
- MAX_CAPACITY = 1000 -- [PASS]
- add: [PASS]
- flush: [PASS]
- pending_count: [FIXED] -- Spec had method, code has @property

**IngestionPipeline:**
- Constructor: `(db: SQLiteDB, qdrant: QdrantClientWrapper, embedding_provider=None)` -- [PASS]
- ingest_file signature: [PASS]
- check_duplicate NOT on IngestionPipeline: [PASS]

**ChunkSplitter:**
- split_into_parents: [PASS]
- split_parent_into_children: [PASS]
- prepend_breadcrumb: [FIXED] -- Added @staticmethod annotation
- compute_point_id: [FIXED] -- Added @staticmethod annotation

**BatchEmbedder:**
- Constructor: `(model, max_workers, batch_size, embedding_provider)` -- [PASS]
- embed_chunks: `(texts) -> tuple[list[list[float] | None], int]` -- [PASS]
- validate_embedding is standalone function: [PASS]

**IncrementalChecker:**
- Constructor: `(db: SQLiteDB)` -- [PASS]
- compute_file_hash: [FIXED] -- Spec had instance method, code is @staticmethod
- check_duplicate: [FIXED] -- Spec had `-> str | None`, code returns `-> tuple[bool, str | None]`
- check_change: [PASS]

### Providers (T010)

**LLMProvider ABC:**
- 4 abstract methods: generate, generate_stream, health_check, get_model_name -- [PASS]
- generate params: `(prompt: str, system_prompt: str = "")` -- [PASS]

**EmbeddingProvider ABC:**
- 4 abstract methods: embed, embed_single, get_model_name, get_dimension -- [PASS]
- embed has optional model param: [PASS]

**ProviderRegistry:**
- Constructor: `(settings: Settings)` (NOT SQLiteDB) -- [PASS]
- get_active_llm: [PASS]
- get_active_langchain_model: [PASS]
- get_embedding_provider: [FIXED] -- Spec had sync, code is async
- set_active_provider: [PASS]

**KeyManager:**
- __init__: [FIXED] -- Spec had `(key: str | None = None)`, code has `()` (loads from env var)
- encrypt, decrypt, is_valid_key: [PASS]

**ProviderRateLimitError:** exists in base.py -- [PASS]

**Concrete providers (5):**
- OllamaLLMProvider, OpenRouterLLMProvider, OpenAILLMProvider, AnthropicLLMProvider: [PASS]
- OllamaEmbeddingProvider: [PASS]

### Error Hierarchy and Schemas (T011)

**Error classes (11 total):**
- EmbeddinatorError (base): [PASS]
- QdrantConnectionError: [PASS]
- OllamaConnectionError: [PASS]
- SQLiteError: [PASS]
- LLMCallError: [PASS]
- EmbeddingError: [PASS]
- IngestionError: [PASS]
- SessionLoadError: [PASS]
- StructuredOutputParseError: [PASS]
- RerankerError: [PASS]
- CircuitOpenError: [PASS]

**Pydantic schemas (31 BaseModel subclasses):**
- All 31 importable from `backend/agent/schemas.py` -- [PASS]

**NDJSON events (10):**
- [FIXED] -- Spec had BaseModel, code uses TypedDict
- [FIXED] -- StatusEvent field is `node` not `message`
- All 10 events verified: SessionEvent, StatusEvent, ChunkEvent, CitationEvent, MetaReasoningEvent, ConfidenceEvent, GroundednessEvent, DoneEvent, ClarificationEvent, ErrorEvent

**Settings (config.py):**
- BaseSettings subclass: [PASS]
- confidence_threshold (int): [PASS]
- meta_relevance_threshold (float): [PASS]
- meta_variance_threshold (float): [PASS]

**Graph Builders:**
- build_conversation_graph(research_graph, checkpointer): [PASS]
- build_research_graph(tools, meta_reasoning_graph): [PASS]
- build_meta_reasoning_graph(): [PASS]

**Confidence Scoring:**
- compute_confidence(chunks, top_k, expected_chunk_count, num_collections_searched, num_collections_total): [PASS]
- Dual call paths documented: [PASS]

**Tools Factory:**
- create_research_tools(searcher, reranker, parent_store) -> list: [PASS]
- 6 inner tools verified: [PASS]

## Fixes Applied to 11-specify.md

1. Line 157-166: Changed NDJSON event classes from `BaseModel` to `TypedDict`, fixed field name comments (StatusEvent: message→node, ChunkEvent: content→text, MetaReasoningEvent: strategy,attempt→strategies_attempted, GroundednessEvent: result→overall_grounded,supported,unsupported,contradicted, DoneEvent: final state→latency_ms,trace_id, ErrorEvent: added trace_id)
2. Line 182: Changed `_extract_claim_for_citation(response: str, citation: Citation)` to `_extract_claim_for_citation(text: str, marker: str)`
3. Line 354: Changed `dedup_key(chunk)` to `dedup_key(query: str, parent_id: str)`
4. Line 357: Changed `def should_compress_context(state) -> bool:` to `async def should_compress_context(state: ResearchState) -> dict:`
5. Line 360: Changed `_build_citations(chunks, answer)` to `_build_citations(chunks: list[RetrievedChunk], answer_text: str)`
6. Lines 452-454: Changed strategy constant values from lowercase to UPPERCASE (`"widen_search"` → `"WIDEN_SEARCH"`, etc.)
7. Lines 458-460: Changed `_build_modified_state_widen(state, config)` to `_build_modified_state_widen(alternative_queries: list[str])`, similarly for _change_collection; changed `_build_modified_state_relax(state, config)` to `_build_modified_state_relax()` (no params)
8. Line 797: Changed `def _check_circuit(self)` to `async def _check_circuit(self) -> None:` for HybridSearcher
9. Line 797+: Added type annotations to `_build_filter` and `_points_to_chunks` helper signatures
10. Line 695: Changed `def pending_count(self, ...) -> int:` to `@property def pending_count(self) -> int:` on UpsertBuffer
11. Lines 731-737: Added full parameter types to ChunkSplitter methods and @staticmethod annotations on prepend_breadcrumb and compute_point_id
12. Line 745: Added `@staticmethod` annotation to IncrementalChecker.compute_file_hash, removed self param
13. Line 746: Changed `check_duplicate` return type from `str | None` to `tuple[bool, str | None]`
14. Line 1170: Changed `def get_embedding_provider(self)` to `async def get_embedding_provider(self)` on ProviderRegistry
15. Line 1181: Changed `def __init__(self, key: str | None = None)` to `def __init__(self)` on KeyManager (loads from env var)

## Notable Observations (not discrepancies)

1. **ConversationState field count**: The task description (T003) says 12 fields but both spec and code have 13. No fix needed — spec correctly documents all 13.
2. **IncrementalChecker.check_duplicate calls db.find_document_by_hash**: The actual SQLiteDB method is `get_document_by_hash`. This appears to be a bug in `incremental.py` but is outside the scope of spec validation (spec correctly documents `get_document_by_hash` on SQLiteDB).
3. **providers table DDL lacks provider_type/config_json columns**: These are added by `_migrate_providers_columns()`. The spec correctly documents the `upsert_provider` method with these params.
