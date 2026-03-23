# Data Model: Component Interface Contracts

**Feature**: 011-component-interfaces
**Date**: 2026-03-17

## Overview

This spec does not introduce new data entities. It validates existing entities' type contracts. The "data model" here describes the contract categories being tested.

## Contract Categories

### State Schemas (3)

| Schema | Module | Fields | Key Contract |
|--------|--------|--------|-------------|
| ConversationState | backend/agent/state.py | 12 | confidence_score: int (0-100) |
| ResearchState | backend/agent/state.py | 16 | confidence_score: float (0.0-1.0), includes _no_new_tools, _needs_compression |
| MetaReasoningState | backend/agent/state.py | 11 | attempted_strategies: set[str] |

**Dual confidence scale**: ConversationState uses int 0-100 (user-facing), ResearchState uses float 0.0-1.0 (internal). Conversion in aggregate_answers via `int(score * 100)`.

### Node Functions (20)

| Graph | Module | Count | DI Pattern |
|-------|--------|-------|-----------|
| ConversationGraph | nodes.py | 11 | `*, llm: Any` or `**kwargs` or none |
| ResearchGraph | research_nodes.py | 5 | `config: RunnableConfig = None` |
| MetaReasoningGraph | meta_reasoning_nodes.py | 4 | `config: RunnableConfig = None` |

All nodes return `dict` (partial state updates), not full State TypedDicts.

### Edge Functions (7)

| Module | Functions | Purpose |
|--------|-----------|---------|
| edges.py | route_intent, should_clarify, route_after_rewrite, route_fan_out | ConversationGraph routing |
| research_edges.py | should_continue_loop, route_after_compress_check | ResearchGraph routing |
| meta_reasoning_edges.py | route_after_strategy | MetaReasoningGraph routing |

### Storage Methods

| Class | Module | Methods | Return Type |
|-------|--------|---------|-------------|
| SQLiteDB | sqlite_db.py | 35+ | dict or None |
| QdrantStorage | qdrant_client.py | 12+ | varies (int, bool, list[SearchResult]) |
| ParentStore | parent_store.py | 2 | list[ParentChunk] |

SQLiteDB has NO ORM row types — all methods use individual params and return raw `dict`.

### Error Hierarchy (11 classes)

```
EmbeddinatorError (base)
├── QdrantConnectionError
├── OllamaConnectionError
├── SQLiteError
├── LLMCallError
├── EmbeddingError
├── IngestionError
├── SessionLoadError
├── StructuredOutputParseError
├── RerankerError
└── CircuitOpenError
```

### Pydantic Schemas (40+)

**Cross-layer (full field validation)**: QueryAnalysis, RetrievedChunk, Citation, SubAnswer, GroundednessResult, ClaimVerification

**API models (import check only)**: CollectionResponse, DocumentResponse, ChatRequest, ProviderResponse, HealthResponse, ErrorResponse, IngestionJobResponse, ModelInfo, SettingsResponse, QueryTraceResponse, and 20+ more

**NDJSON events (10)**: SessionEvent, StatusEvent, ChunkEvent, CitationEvent, MetaReasoningEvent, ConfidenceEvent, GroundednessEvent, DoneEvent, ClarificationEvent, ErrorEvent

## Relationships

```
ConversationGraph nodes → ConversationState (read/write)
ResearchGraph nodes → ResearchState (read/write)
MetaReasoningGraph nodes → MetaReasoningState (read/write)
Nodes → SQLiteDB, ProviderRegistry (dependency injection)
Tools → HybridSearcher, Reranker, ParentStore (closure injection)
IngestionPipeline → SQLiteDB, QdrantClientWrapper, BatchEmbedder (constructor DI)
ProviderRegistry → LLMProvider, EmbeddingProvider (ABC resolution)
All layers → EmbeddinatorError hierarchy (error propagation)
```
