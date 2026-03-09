# Spec 11: Component Interface Contracts -- Implementation Plan Context

## Component Overview

This spec defines the exact type contracts between all major components of The Embedinator. It does not implement the logic -- it defines the function signatures, type annotations, state schemas, Pydantic models, and error conditions that every other spec must conform to. Think of it as the system's type-level specification that ensures all components fit together correctly.

The contracts span: agent state schemas, agent node function signatures, agent tool signatures, ingestion pipeline interface, embedder interface, searcher interface, reranker interface, Qdrant storage interface, and SQLite database interface.

## Technical Approach

### Contract-First Development
1. Define all type contracts (TypedDict states, Pydantic models, function signatures) before implementation
2. Each component spec (02-10) implements the contracts defined here
3. Tests can be written against these contracts using mock implementations
4. Type checking (`pyright` or `mypy`) validates that implementations match contracts

### Key Design Decisions
- **TypedDict over dataclass** for LangGraph state: LangGraph requires TypedDict for graph state
- **Pydantic BaseModel** for all structured data: Validation, serialization, structured output parsing
- **Keyword-only injection**: All dependencies injected via `*` separator to prevent positional misuse
- **Explicit error documentation**: Every function documents what it raises and what it catches

## File Structure

```
backend/
  agent/
    state.py          # TypedDict state schemas for all three graphs
    schemas.py        # Pydantic models: QueryAnalysis, SubAnswer, Citation, etc.
    nodes.py          # Node function signatures (implemented in specs 02-04)
    tools.py          # Tool function signatures (implemented in spec 03)
  ingestion/
    pipeline.py       # IngestionPipeline class interface
    embedder.py       # BatchEmbedder class interface
  retrieval/
    searcher.py       # HybridSearcher class interface
    reranker.py       # Reranker class interface
  storage/
    qdrant_client.py  # QdrantStorage class interface
    sqlite_db.py      # SQLiteDB class interface
  providers/
    base.py           # LLMProvider, EmbeddingProvider ABCs
```

## Implementation Steps

### Step 1: State Schemas (`backend/agent/state.py`)
1. Define `ConversationState(TypedDict)` with all 12 fields
2. Define `ResearchState(TypedDict)` with all 13 fields
3. Define `MetaReasoningState(TypedDict)` with all 10 fields
4. Import all referenced types (QueryAnalysis, SubAnswer, Citation, etc.)

### Step 2: Pydantic Schemas (`backend/agent/schemas.py`)
1. Define `QueryAnalysis(BaseModel)` with validation: `sub_questions` max 5, `complexity_tier` as Literal
2. Define `ClaimVerification(BaseModel)` with verdict Literal
3. Define `GroundednessResult(BaseModel)` with computed `overall_grounded`
4. Define `SubAnswer(BaseModel)` for research graph outputs
5. Define `Citation(BaseModel)` for chunk references
6. Define `RetrievedChunk(BaseModel)` for search results
7. Define `ParentChunk(BaseModel)` for parent chunk data

### Step 3: Agent Node Signatures (`backend/agent/nodes.py`)
1. Define all ConversationGraph node signatures with complete type annotations
2. Define all ResearchGraph node signatures
3. Define all MetaReasoningGraph node signatures
4. Document state reads/writes/raises for each node

### Step 4: Agent Tool Signatures (`backend/agent/tools.py`)
1. Define all `@tool` decorated functions with typed parameters and return types
2. Document error conditions for each tool

### Step 5: Ingestion Interface (`backend/ingestion/pipeline.py`, `backend/ingestion/embedder.py`)
1. Define `IngestionPipeline` class with constructor and method signatures
2. Define `IngestionResult(BaseModel)` return type
3. Define `BatchEmbedder` class with constructor and method signatures
4. Define `EmbeddingResult(BaseModel)` return type

### Step 6: Retrieval Interfaces (`backend/retrieval/searcher.py`, `backend/retrieval/reranker.py`)
1. Define `HybridSearcher` class with constructor and method signatures
2. Define `Reranker` class with constructor and method signatures
3. Document error conditions and default parameters

### Step 7: Storage Interfaces (`backend/storage/qdrant_client.py`, `backend/storage/sqlite_db.py`)
1. Define `QdrantStorage` class with all CRUD + search method signatures
2. Define `SQLiteDB` class with all table operation signatures
3. Define row/create types for SQLite operations (CollectionRow, DocumentRow, JobRow, etc.)

### Step 8: Validation
1. Run type checker on all interface files
2. Verify that all cross-references resolve (imported types exist)
3. Verify that error types from spec-12 are correctly referenced

## Integration Points

Every other backend spec depends on these contracts:

| Spec | Uses Contracts From |
|------|-------------------|
| spec-02 (ConversationGraph) | `ConversationState`, node signatures, schemas |
| spec-03 (ResearchGraph) | `ResearchState`, node/tool signatures, schemas |
| spec-04 (MetaReasoning) | `MetaReasoningState`, node signatures |
| spec-05 (Accuracy) | `GroundednessResult`, `ClaimVerification`, confidence formula |
| spec-06 (Ingestion) | `IngestionPipeline`, `BatchEmbedder`, `EmbeddingResult` |
| spec-07 (Storage) | `SQLiteDB`, `QdrantStorage`, all row/create types |
| spec-08 (API) | Pydantic request/response models, error types |
| spec-10 (Providers) | `LLMProvider`, `EmbeddingProvider`, `ModelInfo` |
| spec-12 (Errors) | All error classes referenced in raises/catches |

## Key Code Patterns

### Dependency Injection Pattern
```python
async def classify_intent(
    state: ConversationState,
    *,                          # keyword-only separator
    llm: BaseChatModel,         # injected, not imported
) -> dict:
```

### State Read/Write Documentation Pattern
```python
async def rewrite_query(state: ConversationState, *, llm: BaseChatModel) -> ConversationState:
    """Decompose query into sub-questions.
    Reads: state["messages"], state["selected_collections"]
    Writes: state["query_analysis"]
    Raises: StructuredOutputParseError (retry once, then fallback)
    """
```

### Pydantic Validation Pattern
```python
class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str] = Field(max_length=5)
    complexity_tier: Literal["factoid", "lookup", "comparison", "analytical", "multi_hop"]
```

### Error Propagation Documentation
```python
async def search(self, query, collection_name, ...) -> List[RetrievedChunk]:
    """Hybrid dense+BM25 search.
    Raises: QdrantConnectionError, EmbeddingError
    """
```

## Phase Assignment

- **Phase 1 (MVP)**: All state schemas, all Pydantic models, ConversationGraph + ResearchGraph node signatures, all tool signatures, ingestion pipeline interface, embedder interface, searcher interface, reranker interface, all storage interfaces. Provider base interfaces (LLMProvider, EmbeddingProvider).
- **Phase 2**: MetaReasoningGraph node signatures, GAV-related schemas (ClaimVerification, GroundednessResult), confidence scoring interface.
- **Phase 3**: Additional provider interface methods, per-document chunk profile types.

These contracts should be defined early (Phase 1) even for components that are implemented later, to ensure consistent interfaces across the entire system.
