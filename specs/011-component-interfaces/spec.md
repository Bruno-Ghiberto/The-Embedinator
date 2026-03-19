# Feature Specification: Component Interface Contracts

**Feature Branch**: `011-component-interfaces`
**Created**: 2026-03-17
**Status**: Draft
**Input**: User description: "Define exact function signatures, input/output types, error conditions, and injected dependencies for every major module in The Embedinator"

## Clarifications

### Session 2026-03-17

- Q: What artifact does spec-11 implementation produce? → A: Validated contract documentation (based on `11-specify.md`) plus automated contract tests that verify signatures match the live codebase, so contracts stay in sync.
- Q: How deeply should 40+ Pydantic schemas be documented? → A: Full field definitions for cross-layer schemas only (~6: QueryAnalysis, RetrievedChunk, Citation, SubAnswer, GroundednessResult, ClaimVerification); categorized name listing for the rest.
- Q: Should API route contracts (backend/api/) be in scope? → A: No. API routes are covered by spec-08 (API Reference). This spec covers internal inter-component boundaries only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Enforce Agent Node Contracts (Priority: P1)

A developer modifying an agent node (e.g., adding a field to `ConversationState` or changing the return type of `rewrite_query`) can immediately see the exact contract each node must satisfy -- what it reads, what it writes, what it returns, and what it raises -- so that changes stay backward-compatible or all call sites are updated together.

**Why this priority**: Agent nodes are the most frequently edited components. Incorrect signatures cause runtime crashes in the LangGraph graph, and the three distinct dependency injection patterns make it easy to wire dependencies wrong. This is the highest-impact contract to formalize.

**Independent Test**: Can be fully tested by adding a new field to `ResearchState`, verifying that the contract document identifies every node that reads/writes that field, and confirming the test suite fails if the contract is violated.

**Acceptance Scenarios**:

1. **Given** a developer reads the interface contracts, **When** they inspect the `classify_intent` node contract, **Then** they see it accepts `(state: ConversationState, *, llm: Any) -> dict`, reads `state["messages"]`, returns `{"intent": str}`, and catches `LLMCallError` with a default fallback to `"rag_query"`.
2. **Given** a developer wants to add a new field to `MetaReasoningState`, **When** they consult the state schema contract, **Then** they see all 11 fields including `attempted_strategies: set[str]` and the dual confidence scale documentation, and can determine which nodes read or write the new field.
3. **Given** a developer needs to understand the ConversationGraph routing, **When** they read the edge function contracts, **Then** they see that `route_fan_out` (not `fan_out` node) performs the actual `Send()` dispatch, and that `route_after_rewrite` combines clarification routing with fan-out because LangGraph forbids two conditional edges from the same source.

---

### User Story 2 - Enforce Storage Layer Contracts (Priority: P2)

A developer integrating with `SQLiteDB` or `QdrantStorage` can look up the exact method names, parameter lists, and return types for every CRUD operation, so they never call nonexistent methods or pass wrong argument types.

**Why this priority**: Storage methods have the widest blast radius -- they are called from agent nodes, API routes, ingestion pipeline, and provider registry. Wrong method names or types cause immediate runtime failures. The absence of ORM types (raw `dict` returns) makes the contract documentation the only source of truth.

**Independent Test**: Can be fully tested by writing a new API route that calls `SQLiteDB.create_query_trace()` with all 16 parameters, verifying each parameter name and type matches the contract.

**Acceptance Scenarios**:

1. **Given** a developer needs to store a query trace, **When** they consult the SQLiteDB contract, **Then** they see `create_query_trace(self, id, session_id, query, collections_searched, chunks_retrieved_json, latency_ms, llm_model=None, embed_model=None, confidence_score=None, sub_questions_json=None, reasoning_steps_json=None, strategy_switches_json=None, meta_reasoning_triggered=False, provider_name=None) -> None` with individual parameters (not a Pydantic model).
2. **Given** a developer needs to search vectors, **When** they consult the QdrantStorage contract, **Then** they see the method is `search_hybrid` (not `hybrid_search`) and takes `sparse_vector: SparseVector | None` (not separate `sparse_indices` + `sparse_values`), returning `list[SearchResult]`.
3. **Given** a developer needs to look up a document by hash, **When** they consult the SQLiteDB contract, **Then** they see the method is `get_document_by_hash` (not `find_by_hash`) with signature `(collection_id: str, file_hash: str) -> dict | None`.

---

### User Story 3 - Enforce Provider and Retrieval Contracts (Priority: P3)

A developer adding a new LLM or embedding provider can see the exact abstract interfaces (`LLMProvider`, `EmbeddingProvider`) they must implement, how `ProviderRegistry` resolves the active provider, and how the two LLM access paths (streaming vs graph nodes) coexist.

**Why this priority**: The provider layer was the most recent addition (spec-10) and has the most complex interaction pattern (dual LLM paths). New providers must implement the correct abstract methods, and the langchain model factory must be understood to avoid breaking agent nodes.

**Independent Test**: Can be fully tested by implementing a mock provider that satisfies the `LLMProvider` contract (4 methods: `generate`, `generate_stream`, `health_check`, `get_model_name`) and verifying it can be registered and resolved via `ProviderRegistry`.

**Acceptance Scenarios**:

1. **Given** a developer wants to add a new cloud provider, **When** they consult the provider contracts, **Then** they see `LLMProvider` requires `generate(prompt, system_prompt) -> str`, `generate_stream(prompt, system_prompt) -> AsyncIterator[str]`, `health_check() -> bool`, and `get_model_name() -> str`.
2. **Given** a developer needs to understand how agent nodes get their LLM, **When** they read the provider registry contract, **Then** they see `get_active_langchain_model(db) -> BaseChatModel` for graph nodes and `get_active_llm(db) -> LLMProvider` for streaming, and both paths read the active provider from the database on each call.
3. **Given** a developer changes the `HybridSearcher`, **When** they consult the retrieval contracts, **Then** they see the constructor takes `(client: AsyncQdrantClient, settings: Settings)` (not storage/embedder/reranker classes), the search method requires an `embed_fn` callable, and the method is `search_all_collections` (not `search_multi_collection`).

---

### User Story 4 - Enforce Ingestion Pipeline Contracts (Priority: P4)

A developer modifying the ingestion flow can see that `IngestionPipeline` takes only 3 constructor arguments, creates chunk splitter and batch embedder internally, and that duplicate checking lives on `IncrementalChecker` not on the pipeline.

**Why this priority**: The ingestion pipeline spans multiple languages and the constructor dependencies and internal wiring are non-obvious. Incorrect assumptions about which components are injected vs created internally cause initialization failures.

**Independent Test**: Can be fully tested by instantiating `IngestionPipeline` with the 3 documented constructor args and verifying it can process a test file through the full pipeline.

**Acceptance Scenarios**:

1. **Given** a developer wants to check for duplicate files, **When** they consult the ingestion contracts, **Then** they see `check_duplicate` is on `IncrementalChecker` (not `IngestionPipeline`) with signature `(collection_id: str, file_hash: str) -> str | None`.
2. **Given** a developer inspects the `BatchEmbedder` contract, **When** they look for the embedding method, **Then** they see `embed_chunks(texts: list[str]) -> tuple[list[list[float] | None], int]` (not `embed_batch`) and that `validate_embedding` is a standalone module-level function returning `tuple[bool, str]` (not a method returning `bool`).
3. **Given** a developer reads the `IngestionResult` contract, **When** they check its type, **Then** they see it is a dataclass (not a Pydantic model) with fields `document_id`, `job_id`, `status` (str), `chunks_processed`, `chunks_skipped`, `error` (not `error_msg`), and no `elapsed_ms` field.

---

### User Story 5 - Error Hierarchy and Cross-Cutting Contracts (Priority: P5)

A developer handling errors can see the complete exception hierarchy, know which layer raises which exceptions, and understand the propagation rules (storage wraps raw errors, agents catch and degrade gracefully, API maps to status codes).

**Why this priority**: Error handling is the most common source of silent failures. Without a documented hierarchy, developers catch the wrong exception types or let unexpected exceptions crash the graph.

**Independent Test**: Can be fully tested by importing all 11 exception classes from the errors module and verifying each is a subclass of the base error class.

**Acceptance Scenarios**:

1. **Given** a developer catches errors in a research node, **When** they consult the error hierarchy, **Then** they see the full tree: base error class with 10 specific subclasses covering connection, call, parsing, embedding, ingestion, session, reranker, and circuit breaker errors.
2. **Given** a developer writes an API route error handler, **When** they consult the error propagation table, **Then** they see that all project error subtypes should be caught at the API layer and mapped to appropriate status codes.
3. **Given** a developer needs to understand the dual confidence scale, **When** they read the cross-cutting documentation, **Then** they see that one state uses `int` 0-100 (user-facing) while another uses `float` 0.0-1.0 (internal), with conversion in the aggregation node via `int(score * 100)`.

---

### Out of Scope

- API route contracts (HTTP methods, paths, status codes) -- covered by spec-08 (API Reference)
- Frontend component contracts -- covered by spec-09 (Next.js Frontend)
- Rust ingestion worker internal interfaces -- binary boundary only, not internal Rust contracts

### Edge Cases

- What happens when a developer adds a new node to the conversation graph without updating the edge routing functions?
- How does the system behave when a node return type changes from `dict` to full state TypedDict (the graph engine will merge differently)?
- What happens when `validate_citations` receives `reranker=None` -- does it skip validation or raise?
- How should a developer handle the case where the langchain model factory has no active provider in the database?
- What happens when `IngestionPipeline` is instantiated with `embedding_provider=None` -- does it fall back to the default local provider?
- How does the research loop edge handle the confidence scale mismatch (config threshold is int 0-100, state value is float 0.0-1.0)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST define all three TypedDict state schemas with every field, its type, and a comment explaining its purpose.
- **FR-002**: System MUST document the dual confidence scale: integer 0-100 in the conversation state (user-facing) vs float 0.0-1.0 in the research state (internal), including all conversion points.
- **FR-003**: System MUST document every ConversationGraph node function with its exact signature (including dependency injection pattern), state reads, state writes, return type, and error conditions.
- **FR-004**: System MUST document the 3 conversation nodes that previous specs omitted: the clarification interrupt node, history summarization node, and collection management stub.
- **FR-005**: System MUST document all 7 edge functions across 3 files with return types and routing logic, explicitly noting that the fan-out edge (not the fan-out node) performs the actual parallel dispatch.
- **FR-006**: System MUST document the closure-based tool factory with all 6 inner tools, their parameter types, and the injected dependencies they close over.
- **FR-007**: System MUST document all ResearchGraph and MetaReasoningGraph node functions with their config-based dependency injection pattern and their state reads/writes.
- **FR-008**: System MUST document the complete SQLiteDB interface with all 35+ methods, using individual parameter signatures (not model types) and dictionary return types.
- **FR-009**: System MUST document the complete QdrantStorage interface with correct method names (`batch_upsert`, `search_hybrid`, `delete_points_by_filter`) and the coexisting legacy client class.
- **FR-010**: System MUST document the HybridSearcher interface with its actual constructor parameters, the embedding function parameter on search methods, and the correct method name for multi-collection search.
- **FR-011**: System MUST document the Reranker interface with its settings-based constructor and confirm that the `score_pair` method does not exist.
- **FR-012**: System MUST document the BatchEmbedder interface with the correct method name `embed_chunks`, its tuple return type, and the standalone `validate_embedding` function.
- **FR-013**: System MUST document the IngestionPipeline constructor with its actual 3 parameters, confirming that chunk splitter and batch embedder are created internally.
- **FR-014**: System MUST document `IngestionResult` as a dataclass (not Pydantic model) with its actual fields including `error` (not `error_msg`) and no `elapsed_ms`.
- **FR-015**: System MUST document that duplicate checking lives on `IncrementalChecker` (not `IngestionPipeline`).
- **FR-016**: System MUST document the provider abstract interfaces, provider registry with both LLM access paths, and the key manager.
- **FR-017**: System MUST enumerate the complete error hierarchy (11 exception classes) with the layer-to-error-type mapping.
- **FR-018**: System MUST document all 40+ Pydantic schemas and 10 NDJSON event models. Cross-layer schemas (QueryAnalysis, RetrievedChunk, Citation, SubAnswer, GroundednessResult, ClaimVerification) MUST include full field definitions. Remaining API request/response and event models MUST be listed by name in categorized groups.
- **FR-019**: System MUST document the 3 graph builder functions with their wiring topology.
- **FR-020**: System MUST include automated contract tests that introspect actual function signatures (parameter names, types, return types) and fail when code diverges from the documented contracts.
- **FR-021**: Contract tests MUST cover all 8 primary classes and all node/edge functions, verifying method existence, parameter counts, and parameter names at minimum.

### Key Entities

- **State Schema**: A typed dictionary defining the data that flows through a graph layer. Three distinct schemas exist for the three graph layers. Each field has a type, a purpose comment, and a list of nodes that read/write it.
- **Node Function**: An async (or sync) function that reads from and writes to a state schema. Returns a dictionary with partial state updates. Receives dependencies via one of three injection patterns.
- **Edge Function**: A routing function that determines the next node(s) to execute based on current state. Returns strings (node names) or a list of parallel dispatch objects.
- **Tool**: A decorated function created inside a closure factory. Closes over injected dependencies (searcher, reranker, parent store).
- **Storage Interface**: An async class providing CRUD operations with raw dictionary returns. No typed row models exist.
- **Provider Interface**: An abstract base class defining the contract for LLM inference or embedding generation. Concrete implementations exist for 4 providers.
- **Error Class**: A named exception inheriting from the project base error. Each layer catches specific error types and either degrades gracefully or wraps and re-raises.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Every function signature in the contract document matches the actual codebase with zero discrepancies in method names, parameter names, parameter types, and return types.
- **SC-002**: Every state schema field is documented with its correct type, and the dual confidence scale is explicitly annotated at every conversion point.
- **SC-003**: A developer unfamiliar with the codebase can correctly wire a new agent node by reading only the contract document, without consulting source code, within 15 minutes.
- **SC-004**: All 3 dependency injection patterns are documented with working examples that pass type checking.
- **SC-005**: The error hierarchy is complete -- importing all 11 exception classes succeeds and each is confirmed as a subclass of the base error class.
- **SC-006**: Zero fictional types or methods are referenced anywhere in the contracts (no nonexistent model types, wrong method names, or phantom methods).
- **SC-007**: The contract document covers 100% of public methods on the 8 primary classes (SQLiteDB, QdrantStorage, HybridSearcher, Reranker, BatchEmbedder, IngestionPipeline, ProviderRegistry, KeyManager).
- **SC-008**: Every node's state reads and state writes are documented, enabling automated detection of undocumented field access.
- **SC-009**: The contract document serves as the single source of truth for inter-component integration, reducing integration-related test failures by eliminating signature mismatches.
- **SC-010**: Automated contract tests pass when run against the current codebase, confirming zero drift between documented contracts and actual implementations.
