# Spec 11: Component Interface Contracts -- Implementation Plan Context

## Component Overview

This spec validates and enforces the exact type contracts between all major components of The
Embedinator. It does NOT implement application logic or define new interfaces -- it validates
the contracts already documented in `11-specify.md` against the live codebase (specs 02--10 are
fully implemented, 977 tests passing), then produces automated contract tests that introspect
actual function signatures and fail when code diverges from the documented contracts.

The deliverable is twofold:
1. **Validated contract documentation**: `11-specify.md` is the canonical source, verified against
   live code by cross-referencing every signature with Serena MCP introspection.
2. **Automated contract tests**: Python test files that use `inspect.signature()` to verify method
   existence, parameter names, parameter order, default values, and return type annotations.

---

## What Already Exists

### Fully Implemented Code (specs 02--10)

All backend modules are implemented and passing. The contracts in `11-specify.md` describe what
already exists -- they are not blueprints for new code. Key modules:

**Agent Layer** (`backend/agent/`):
- `state.py` -- 3 TypedDict state schemas (`ConversationState`, `ResearchState`, `MetaReasoningState`)
- `nodes.py` -- 11 ConversationGraph node functions (3 DI patterns: `*, llm: Any`, `**kwargs`, no deps)
- `research_nodes.py` -- 5 ResearchGraph node functions (config-based DI: `config: RunnableConfig = None`)
- `meta_reasoning_nodes.py` -- 4 MetaReasoningGraph node functions (config-based DI)
- `edges.py` -- 4 ConversationGraph edge functions (`route_intent`, `should_clarify`, `route_after_rewrite`, `route_fan_out`)
- `research_edges.py` -- 2 ResearchGraph edge functions (`should_continue_loop`, `route_after_compress_check`)
- `meta_reasoning_edges.py` -- 1 MetaReasoningGraph edge function (`route_after_strategy`)
- `tools.py` -- closure-based factory `create_research_tools()` returning 6 `@tool` functions
- `schemas.py` -- 40+ Pydantic models + 10 NDJSON event models
- `confidence.py` -- dual-path confidence scoring (legacy int 0-100, new float 0.0-1.0)
- `prompts.py` -- prompt constants for all nodes
- `conversation_graph.py` -- `build_conversation_graph()` graph builder
- `research_graph.py` -- `build_research_graph()` graph builder
- `meta_reasoning_graph.py` -- `build_meta_reasoning_graph()` graph builder

**Storage Layer** (`backend/storage/`):
- `sqlite_db.py` -- `SQLiteDB` class with 35+ methods, raw `dict` returns (NO ORM row types)
- `qdrant_client.py` -- `QdrantStorage` class with 12+ methods + legacy `QdrantClientWrapper`
- `parent_store.py` -- `ParentStore` class reading parent chunks from SQLite

**Retrieval Layer** (`backend/retrieval/`):
- `searcher.py` -- `HybridSearcher(client: AsyncQdrantClient, settings: Settings)` with circuit breaker
- `reranker.py` -- `Reranker(settings: Settings)` with `model.rank()` (NOT `model.predict()`)
- `score_normalizer.py` -- `normalize_scores()` standalone function

**Ingestion Layer** (`backend/ingestion/`):
- `pipeline.py` -- `IngestionPipeline(db, qdrant, embedding_provider=None)` + `@dataclass IngestionResult`
- `embedder.py` -- `BatchEmbedder` with `embed_chunks()` + standalone `validate_embedding()`
- `chunker.py` -- `ChunkSplitter` with deterministic UUID5 point IDs
- `incremental.py` -- `IncrementalChecker` with `check_duplicate()` (NOT on pipeline)

**Provider Layer** (`backend/providers/`):
- `base.py` -- `LLMProvider(ABC)`, `EmbeddingProvider(ABC)`, `ProviderRateLimitError`
- `registry.py` -- `ProviderRegistry(settings)` with dual access paths (`get_active_llm`, `get_active_langchain_model`)
- `key_manager.py` -- `KeyManager` with Fernet encryption via `EMBEDINATOR_FERNET_KEY`
- `ollama.py`, `openrouter.py`, `openai.py`, `anthropic.py` -- 4 concrete providers

**Cross-Cutting**:
- `errors.py` -- 11 exception classes inheriting from `EmbeddinatorError`
- `config.py` -- `Settings(BaseSettings)` with Pydantic Settings

### Contract Documentation (11-specify.md)

The `11-specify.md` context prompt has already been rewritten with corrected contracts from a
full codebase coherence review. It is 1320 lines and covers all modules listed above. This is
the canonical reference that contract tests will verify against.

### What Does NOT Exist Yet

- **Contract test files** -- no `test_contracts_*.py` files exist. These are the primary NEW
  deliverables of this spec.
- **Validation report** -- no formal report confirming `11-specify.md` matches live code.

---

## What Spec-11 Adds

**1. Validated 11-specify.md** (Wave 1)

Cross-reference every signature documented in `11-specify.md` against the actual codebase using
Serena MCP tools. Fix any remaining discrepancies. Produce a validation report listing every
checked signature and its pass/fail status.

**2. Automated contract tests** (Waves 2--3)

Six test files that use Python's `inspect` module to introspect actual function and class
signatures. These tests:
- Verify method existence on classes
- Verify parameter names and parameter order
- Verify keyword-only vs positional parameter kinds
- Verify return type annotations where present
- Verify class inheritance hierarchies (error classes, ABCs)
- Verify dataclass vs Pydantic model distinctions
- Do NOT test runtime behavior (that is covered by specs 02--10)

**3. Regression-safe test suite** (Wave 4)

Run all contract tests plus the full existing test suite. Confirm zero regressions against the
977 existing passing tests.

---

## Technical Approach

### Contract Testing via `inspect`

Tests introspect actual Python signatures rather than executing application logic. This ensures
the documented contracts stay synchronized with code without duplicating behavioral tests.

```python
import inspect
from backend.agent.nodes import classify_intent

sig = inspect.signature(classify_intent)
params = list(sig.parameters.keys())
assert params == ["state", "llm"], f"Expected ['state', 'llm'], got {params}"
assert sig.parameters["llm"].kind == inspect.Parameter.KEYWORD_ONLY
```

For classes, verify method existence and parameter names:

```python
from backend.storage.sqlite_db import SQLiteDB

# Verify method exists
assert hasattr(SQLiteDB, "create_query_trace")
sig = inspect.signature(SQLiteDB.create_query_trace)
params = list(sig.parameters.keys())
assert "provider_name" in params  # spec-10 FR-019 field
assert "trace_create" not in params  # No ORM types
```

For error hierarchy:

```python
from backend.errors import (
    EmbeddinatorError, QdrantConnectionError, LLMCallError,
    CircuitOpenError, ...
)
assert issubclass(CircuitOpenError, EmbeddinatorError)
```

For dataclass vs Pydantic distinction:

```python
import dataclasses
from pydantic import BaseModel
from backend.ingestion.pipeline import IngestionResult

assert dataclasses.is_dataclass(IngestionResult)
assert not issubclass(IngestionResult, BaseModel)
```

### Three Dependency Injection Patterns

The codebase uses three distinct DI patterns. Contract tests must verify the correct pattern
for each node:

**Pattern 1 -- ConversationGraph nodes** (keyword-only `*, llm: Any` or `**kwargs`):

```python
# Keyword-only: classify_intent, rewrite_query, verify_groundedness, validate_citations
async def classify_intent(state: ConversationState, *, llm: Any) -> dict:
```

```python
# **kwargs: init_session, fan_out, aggregate_answers, summarize_history,
#           format_response, handle_collection_mgmt
async def init_session(state: ConversationState, **kwargs: Any) -> dict:
```

```python
# No injected deps: request_clarification
def request_clarification(state: ConversationState) -> dict:
```

**Pattern 2 -- ResearchGraph / MetaReasoningGraph nodes** (`config: RunnableConfig = None`):

```python
async def orchestrator(state: ResearchState, config: RunnableConfig = None) -> dict:
```

**Pattern 3 -- Tool factory** (closure injection):

```python
def create_research_tools(searcher, reranker, parent_store) -> list:
    # Inner @tool functions close over dependencies
```

### Key Corrections from Previous Plan

The current `11-plan.md` contains 15 factual errors. The corrected plan reflects:

1. **DI pattern is NOT uniform** -- three distinct patterns exist (see above)
2. **Node return type is `dict`** (partial state updates), NOT full State TypedDicts
3. **`llm` type is `Any`**, NOT `BaseChatModel`
4. **`IngestionResult` is `@dataclass`**, NOT `BaseModel`
5. **`EmbeddingResult` class does NOT exist** -- removed
6. **SQLiteDB has NO ORM row types** -- uses raw `dict` returns
7. **Method names**: `embed_chunks` not `embed_batch`, `batch_upsert` not `upsert_batch`,
   `search_hybrid` not `hybrid_search`, `search_all_collections` not `search_multi_collection`
8. **`HybridSearcher`** takes `(AsyncQdrantClient, Settings)`, NOT `(QdrantStorage, BatchEmbedder, Reranker)`
9. **`Reranker`** takes `(Settings)`, NOT `(model_name: str)`; `score_pair()` does not exist
10. **Meta-reasoning nodes** are in `meta_reasoning_nodes.py`, NOT `nodes.py`
11. **7 edge functions across 3 files** were MISSING from previous plan
12. **Provider layer** (base.py, registry.py, key_manager.py, 4 concrete providers) was MISSING
13. **Error hierarchy** (11 classes in errors.py) was MISSING
14. **Graph builders** (3 functions) were MISSING
15. **Confidence module, score normalizer, parent store** were MISSING

---

## File Structure

```
tests/
  unit/
    test_contracts_agent.py          # NEW — State schemas, node signatures, edge functions,
                                     #        tools, graph builders, confidence scoring
    test_contracts_storage.py        # NEW — SQLiteDB (35+ methods), QdrantStorage (12+ methods),
                                     #        ParentStore, data classes (SparseVector, QdrantPoint, SearchResult)
    test_contracts_retrieval.py      # NEW — HybridSearcher, Reranker, ScoreNormalizer
    test_contracts_ingestion.py      # NEW — IngestionPipeline, BatchEmbedder, ChunkSplitter,
                                     #        IncrementalChecker, UpsertBuffer, IngestionResult
    test_contracts_providers.py      # NEW — LLMProvider, EmbeddingProvider, ProviderRegistry,
                                     #        KeyManager, 4 concrete providers, ProviderRateLimitError
    test_contracts_cross_cutting.py  # NEW — Error hierarchy (11 classes), Pydantic schema existence,
                                     #        NDJSON event models, Settings config fields
Docs/
  Tests/
    contracts-validation-report.md   # NEW — Wave 1 output: per-signature pass/fail report
```

No existing files are modified. All new test files are additive.

---

## Implementation Steps

### Step 1: Validate 11-specify.md Against Live Code (Wave 1)

1. Using Serena MCP `find_symbol` and `get_symbols_overview`, cross-reference every function
   signature in `11-specify.md` against the actual codebase.
2. For each module section in `11-specify.md`, verify:
   - Function/method exists at the documented location
   - Parameter names match exactly
   - Parameter order matches exactly
   - Default values match (e.g., `config: RunnableConfig = None`, not `= {}`)
   - Return type annotation matches where present
3. Check class hierarchies: confirm all 11 error classes inherit from `EmbeddinatorError`.
4. Check data structures: confirm `IngestionResult` is `@dataclass`, not `BaseModel`.
5. Fix any discrepancies found in `11-specify.md`.
6. Produce a validation report at `Docs/Tests/contracts-validation-report.md`.

### Step 2: Agent Layer Contract Tests (Wave 2, Agent A2)

Write `tests/unit/test_contracts_agent.py` covering:

1. **State schemas** (FR-001, FR-002):
   - `ConversationState` has all 12 fields with correct types
   - `ResearchState` has all 15 fields (including `_no_new_tools`, `_needs_compression`)
   - `MetaReasoningState` has all 11 fields
   - Dual confidence scale: `ConversationState.confidence_score` annotated `int`,
     `ResearchState.confidence_score` annotated `float`

2. **ConversationGraph node signatures** (FR-003, FR-004):
   - `classify_intent`: params `["state", "llm"]`, `llm` is KEYWORD_ONLY
   - `rewrite_query`: params `["state", "llm"]`, `llm` is KEYWORD_ONLY
   - `verify_groundedness`: params `["state", "llm"]`, `llm` is KEYWORD_ONLY, default `None`
   - `validate_citations`: params `["state", "reranker"]`, `reranker` is KEYWORD_ONLY, default `None`
   - `init_session`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `fan_out`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `aggregate_answers`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `summarize_history`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `format_response`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `handle_collection_mgmt`: params `["state", "kwargs"]`, `kwargs` is VAR_KEYWORD
   - `request_clarification`: params `["state"]` only (no DI)

3. **ResearchGraph node signatures** (FR-007):
   - All 5 nodes (`orchestrator`, `tools_node`, `compress_context`, `collect_answer`,
     `fallback_response`) have `config` parameter with `RunnableConfig` default `None`
   - `fallback_response` has NO `config` parameter (verify actual signature)

4. **MetaReasoningGraph node signatures** (FR-007):
   - All 4 nodes (`generate_alternative_queries`, `evaluate_retrieval_quality`,
     `decide_strategy`, `report_uncertainty`) live in `meta_reasoning_nodes.py`, NOT `nodes.py`
   - All have `config: RunnableConfig = None` parameter

5. **Edge functions** (FR-005):
   - `edges.py`: `route_intent`, `should_clarify`, `route_after_rewrite`, `route_fan_out` exist
   - `research_edges.py`: `should_continue_loop`, `route_after_compress_check` exist
   - `meta_reasoning_edges.py`: `route_after_strategy` exists
   - Total: 7 edge functions across 3 files

6. **Tool factory** (FR-006):
   - `create_research_tools` exists in `tools.py`
   - Takes params `["searcher", "reranker", "parent_store"]`
   - Returns `list`

7. **Graph builders** (FR-019):
   - `build_conversation_graph` exists in `conversation_graph.py`
   - `build_research_graph` exists in `research_graph.py`
   - `build_meta_reasoning_graph` exists in `meta_reasoning_graph.py`

8. **Confidence scoring** (FR-002):
   - `compute_confidence` exists in `confidence.py`
   - Has `chunks` as first param, returns `float | int` (dual path)

### Step 3: Storage + Retrieval Contract Tests (Wave 2, Agent A3)

Write `tests/unit/test_contracts_storage.py` covering:

1. **SQLiteDB** (FR-008):
   - All 35+ methods exist as attributes on `SQLiteDB`
   - `create_query_trace` has `provider_name` parameter (spec-10 addition)
   - `create_collection` uses individual params, NOT a model type
   - `get_document_by_hash` exists (not `find_by_hash`)
   - No `CollectionRow`, `DocumentRow`, `JobRow`, etc. types exist
   - Verify async context manager protocol (`__aenter__`, `__aexit__`)

2. **QdrantStorage** (FR-009):
   - Method is `batch_upsert` (not `upsert_batch`)
   - Method is `search_hybrid` (not `hybrid_search`)
   - Method is `delete_points_by_filter` (not `delete_by_filter`)
   - `search_hybrid` takes `sparse_vector: SparseVector | None` (not separate indices/values)
   - Data classes exist: `SparseVector`, `QdrantPoint`, `SearchResult`
   - Legacy `QdrantClientWrapper` coexists in same file

3. **ParentStore** (FR-008):
   - `get_by_ids` method exists with `parent_ids` parameter
   - Constructor takes `db: SQLiteDB`

Write `tests/unit/test_contracts_retrieval.py` covering:

4. **HybridSearcher** (FR-010):
   - Constructor params are `["self", "client", "settings"]` (NOT storage/embedder/reranker)
   - `search` method has `embed_fn` parameter
   - Method is `search_all_collections` (not `search_multi_collection`)
   - Circuit breaker methods exist: `_check_circuit`, `_record_success`, `_record_failure`

5. **Reranker** (FR-011):
   - Constructor params are `["self", "settings"]` (NOT `model_name: str`)
   - `rerank` method exists with params `["self", "query", "chunks", "top_k"]`
   - `score_pair` method does NOT exist (`assert not hasattr(Reranker, "score_pair")`)

6. **ScoreNormalizer**:
   - `normalize_scores` is a module-level function (not a class method)

### Step 4: Ingestion + Provider Contract Tests (Wave 3, Agent A4)

Write `tests/unit/test_contracts_ingestion.py` covering:

1. **IngestionPipeline** (FR-013):
   - Constructor takes 3 params: `db`, `qdrant`, `embedding_provider`
   - Second param is `qdrant` (receives `QdrantClientWrapper`, NOT `QdrantStorage`)
   - `check_duplicate` does NOT exist on `IngestionPipeline`

2. **IngestionResult** (FR-014):
   - Is a `@dataclass`, NOT a `BaseModel`
   - Has fields: `document_id`, `job_id`, `status`, `chunks_processed`, `chunks_skipped`, `error`
   - Does NOT have `error_msg` or `elapsed_ms` fields

3. **BatchEmbedder** (FR-012):
   - Method is `embed_chunks` (not `embed_batch`)
   - `validate_embedding` is a standalone module-level function, NOT a method on `BatchEmbedder`

4. **IncrementalChecker** (FR-015):
   - `check_duplicate` lives on `IncrementalChecker`, NOT on `IngestionPipeline`
   - `compute_file_hash` is a method on `IncrementalChecker`

5. **ChunkSplitter**:
   - `compute_point_id` method exists (deterministic UUID5)
   - `split_into_parents` method exists
   - `prepend_breadcrumb` method exists

Write `tests/unit/test_contracts_providers.py` covering:

6. **LLMProvider ABC** (FR-016):
   - Has 4 abstract methods: `generate`, `generate_stream`, `health_check`, `get_model_name`
   - `generate` params: `["self", "prompt", "system_prompt"]`
   - Cannot be instantiated directly (ABC enforcement)

7. **EmbeddingProvider ABC** (FR-016):
   - Has 4 abstract methods: `embed`, `embed_single`, `get_model_name`, `get_dimension`
   - `embed` has optional `model` parameter (spec-10 FR-006)

8. **ProviderRegistry** (FR-016):
   - Constructor takes `settings` (NOT `SQLiteDB`)
   - Has `get_active_llm(db)` returning `LLMProvider`
   - Has `get_active_langchain_model(db)` returning `BaseChatModel`
   - Has `get_embedding_provider()` (no db param)
   - Has `set_active_provider(db, name, config)`

9. **KeyManager**:
   - Has `encrypt`, `decrypt`, `is_valid_key` methods

10. **Concrete providers** (4 classes):
    - `OllamaLLMProvider` is subclass of `LLMProvider`
    - `OpenRouterLLMProvider` is subclass of `LLMProvider`
    - `OpenAILLMProvider` is subclass of `LLMProvider`
    - `AnthropicLLMProvider` is subclass of `LLMProvider`
    - `OllamaEmbeddingProvider` is subclass of `EmbeddingProvider`

11. **ProviderRateLimitError**:
    - Exists in `backend.providers.base`
    - Is a standard `Exception` subclass (NOT an `EmbeddinatorError` subclass)

Write `tests/unit/test_contracts_cross_cutting.py` covering:

12. **Error hierarchy** (FR-017):
    - All 11 classes importable from `backend.errors`
    - All 10 specific errors are subclasses of `EmbeddinatorError`
    - Verify: `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`,
      `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`,
      `RerankerError`, `CircuitOpenError`

13. **Pydantic schema existence** (FR-018):
    - Cross-layer schemas importable with correct field names: `QueryAnalysis`, `RetrievedChunk`,
      `Citation`, `SubAnswer`, `GroundednessResult`, `ClaimVerification`
    - All are `BaseModel` subclasses
    - Verify key fields: `QueryAnalysis.complexity_tier`, `ClaimVerification.verdict`,
      `GroundednessResult.overall_grounded`
    - Verify categorized name listing for remaining 30+ models (import check only)

14. **NDJSON event models**:
    - All 10 event models importable from `schemas.py`
    - Each has a `type` field (discriminator)

15. **Settings config**:
    - `Settings` is a `BaseSettings` subclass
    - Key fields exist: `confidence_threshold`, `meta_relevance_threshold`, `meta_variance_threshold`

### Step 5: Final Gate -- Run All Tests (Wave 4)

1. Run all contract tests:
   ```
   zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py
   zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py
   zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py
   zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py
   zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py
   zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py
   ```
2. Fix any failures.
3. Run full regression:
   ```
   zsh scripts/run-tests-external.sh -n full-regression tests/
   ```
4. Verify 0 regressions against the 977 existing passing tests.
5. Verify SC-001 through SC-010 are satisfied.

---

## Agent Teams

### Wave 1 -- A1 (quality-engineer, Opus)

**Goal**: Validate `11-specify.md` contracts against live code.

**Tasks**:
- Cross-reference every function signature in `11-specify.md` against the actual codebase using
  Serena MCP tools (`find_symbol`, `get_symbols_overview`)
- Fix any remaining discrepancies in `11-specify.md`
- Produce a validation report at `Docs/Tests/contracts-validation-report.md`

**Gate**: Validation report confirms zero discrepancies, or all found discrepancies are fixed.

---

### Wave 2 -- A2 + A3 (parallel, python-expert, Sonnet)

**A2: Agent layer contract tests**

**Tasks**:
- Write `tests/unit/test_contracts_agent.py` covering:
  - 3 state schemas (field names, types, field count)
  - 11 ConversationGraph node signatures (DI patterns: `*, llm: Any` vs `**kwargs` vs none)
  - 5 ResearchGraph node signatures (`config: RunnableConfig = None`)
  - 4 MetaReasoningGraph node signatures (in `meta_reasoning_nodes.py`, NOT `nodes.py`)
  - 7 edge functions across 3 files
  - Tool factory `create_research_tools` signature
  - 3 graph builder functions
  - Confidence scoring function dual-path
- Run: `zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py`

**A3: Storage + retrieval contract tests**

**Tasks**:
- Write `tests/unit/test_contracts_storage.py` covering:
  - `SQLiteDB` -- all 35+ methods, individual params, `dict` returns, NO ORM types
  - `QdrantStorage` -- correct method names, `SparseVector`/`QdrantPoint`/`SearchResult` data classes
  - `ParentStore` -- constructor and method signatures
- Write `tests/unit/test_contracts_retrieval.py` covering:
  - `HybridSearcher` -- constructor params, `embed_fn` parameter, `search_all_collections` name
  - `Reranker` -- settings-based constructor, `score_pair` does NOT exist
  - `normalize_scores` -- module-level function
- Run both test files via external runner

**Gate**: All agent + storage + retrieval contract tests pass.

---

### Wave 3 -- A4 (python-expert, Sonnet)

**Goal**: Write contract tests for remaining layers.

**Tasks**:
- Write `tests/unit/test_contracts_ingestion.py` covering:
  - `IngestionPipeline` -- 3 constructor params, `check_duplicate` NOT on pipeline
  - `IngestionResult` -- `@dataclass` NOT `BaseModel`, correct field names
  - `BatchEmbedder` -- `embed_chunks` (not `embed_batch`), `validate_embedding` is standalone
  - `IncrementalChecker` -- `check_duplicate` lives here
  - `ChunkSplitter` -- key methods exist

- Write `tests/unit/test_contracts_providers.py` covering:
  - `LLMProvider` ABC -- 4 abstract methods
  - `EmbeddingProvider` ABC -- 4 abstract methods, optional `model` param on `embed`
  - `ProviderRegistry` -- constructor takes `settings`, dual LLM access paths
  - `KeyManager` -- encrypt/decrypt/is_valid_key
  - 4 concrete provider subclass relationships
  - `ProviderRateLimitError` -- exists, NOT an `EmbeddinatorError`

- Write `tests/unit/test_contracts_cross_cutting.py` covering:
  - Error hierarchy -- 11 classes, all inherit from `EmbeddinatorError`
  - Pydantic schemas -- cross-layer models have correct fields, remaining models importable
  - NDJSON event models -- 10 models with `type` discriminator
  - Settings -- `BaseSettings` subclass with key config fields

- Run all three test files via external runner

**Gate**: All ingestion + provider + cross-cutting contract tests pass.

---

### Wave 4 -- A5 (quality-engineer, Sonnet)

**Goal**: Final verification and regression gate.

**Tasks**:
- Run ALL 6 contract test files and confirm they pass
- Run full regression test suite: `zsh scripts/run-tests-external.sh -n full-regression tests/`
- Verify 0 regressions against the 977 existing passing tests
- Verify each success criterion (SC-001 through SC-010) is satisfied
- Fix any failures found
- Produce final summary report

**Gate**: All contract tests pass AND zero regressions.

---

## Testing Policy

**NEVER run pytest inside Claude Code** -- always use the external test runner:

```bash
zsh scripts/run-tests-external.sh -n <name> <target>
```

Output files:
- `Docs/Tests/{name}.status` -- poll with `cat` (RUNNING | PASSED | FAILED | ERROR)
- `Docs/Tests/{name}.summary` -- ~20 lines, token-efficient
- `Docs/Tests/{name}.log` -- full pytest output

The script auto-creates `.venv/` with fingerprint-based dependency checking.

---

## Integration Points

Every contract test file validates interfaces that span multiple specs:

| Test File | Specs Validated | Key Contracts |
|-----------|----------------|---------------|
| `test_contracts_agent.py` | spec-02, spec-03, spec-04, spec-05 | State schemas, 20 node functions, 7 edge functions, 6 tools, 3 graph builders, confidence |
| `test_contracts_storage.py` | spec-07 | SQLiteDB (35+ methods), QdrantStorage (12+ methods), ParentStore, data classes |
| `test_contracts_retrieval.py` | spec-03, spec-05 | HybridSearcher, Reranker, ScoreNormalizer |
| `test_contracts_ingestion.py` | spec-06 | IngestionPipeline, BatchEmbedder, ChunkSplitter, IncrementalChecker, UpsertBuffer |
| `test_contracts_providers.py` | spec-10 | LLMProvider, EmbeddingProvider, ProviderRegistry, KeyManager, 4 concrete providers |
| `test_contracts_cross_cutting.py` | spec-12, spec-08, all | Error hierarchy (11 classes), 40+ Pydantic schemas, 10 NDJSON events, Settings |

---

## Key Code Patterns

### Contract Test Pattern -- Function Signature

```python
import inspect

def test_classify_intent_signature():
    from backend.agent.nodes import classify_intent

    sig = inspect.signature(classify_intent)
    params = list(sig.parameters.keys())
    assert params == ["state", "llm"], f"Expected ['state', 'llm'], got {params}"
    assert sig.parameters["state"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert sig.parameters["llm"].kind == inspect.Parameter.KEYWORD_ONLY
```

### Contract Test Pattern -- Class Method Existence

```python
def test_sqlite_db_methods():
    from backend.storage.sqlite_db import SQLiteDB

    required_methods = [
        "create_collection", "get_collection", "get_collection_by_name",
        "list_collections", "update_collection", "delete_collection",
        "create_document", "get_document", "get_document_by_hash",
        "list_documents", "update_document", "delete_document",
        "create_query_trace", "list_query_traces", "list_traces", "get_trace",
        # ... all 35+ methods
    ]
    for method_name in required_methods:
        assert hasattr(SQLiteDB, method_name), f"SQLiteDB missing method: {method_name}"
```

### Contract Test Pattern -- Error Hierarchy

```python
def test_error_hierarchy():
    from backend.errors import (
        EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
        SQLiteError, LLMCallError, EmbeddingError, IngestionError,
        SessionLoadError, StructuredOutputParseError, RerankerError,
        CircuitOpenError,
    )

    error_classes = [
        QdrantConnectionError, OllamaConnectionError, SQLiteError,
        LLMCallError, EmbeddingError, IngestionError, SessionLoadError,
        StructuredOutputParseError, RerankerError, CircuitOpenError,
    ]
    for cls in error_classes:
        assert issubclass(cls, EmbeddinatorError), f"{cls.__name__} must inherit EmbeddinatorError"
```

### Contract Test Pattern -- Dataclass vs Pydantic

```python
import dataclasses
from pydantic import BaseModel

def test_ingestion_result_is_dataclass():
    from backend.ingestion.pipeline import IngestionResult

    assert dataclasses.is_dataclass(IngestionResult), "IngestionResult must be a dataclass"
    assert not issubclass(IngestionResult, BaseModel), "IngestionResult must NOT be a BaseModel"

    field_names = [f.name for f in dataclasses.fields(IngestionResult)]
    assert "document_id" in field_names
    assert "error" in field_names
    assert "error_msg" not in field_names  # Common mistake
    assert "elapsed_ms" not in field_names  # Does not exist
```

### Contract Test Pattern -- ABC Enforcement

```python
import abc

def test_llm_provider_is_abstract():
    from backend.providers.base import LLMProvider

    assert abc.ABC in LLMProvider.__mro__, "LLMProvider must be an ABC"

    abstract_methods = {
        name for name, method in vars(LLMProvider).items()
        if getattr(method, "__isabstractmethod__", False)
    }
    assert abstract_methods == {"generate", "generate_stream", "health_check", "get_model_name"}
```

### Dual Confidence Scale Documentation

```python
def test_dual_confidence_scale():
    """Verify the dual confidence scale is correctly typed across state schemas."""
    import typing
    from backend.agent.state import ConversationState, ResearchState

    conv_hints = typing.get_type_hints(ConversationState)
    research_hints = typing.get_type_hints(ResearchState)

    assert conv_hints["confidence_score"] is int, "ConversationState.confidence_score must be int (0-100)"
    assert research_hints["confidence_score"] is float, "ResearchState.confidence_score must be float (0.0-1.0)"
```

---

## Phase Assignment

All work is Phase 1 -- there is no phased rollout for a validation + testing spec.

- **Wave 1**: Validate `11-specify.md` against live code (A1, Opus)
- **Wave 2**: Agent + storage + retrieval contract tests (A2 + A3 parallel, Sonnet)
- **Wave 3**: Ingestion + provider + cross-cutting contract tests (A4, Sonnet)
- **Wave 4**: Final gate -- all tests pass, zero regressions (A5, Sonnet)

The contracts document existing code (specs 02--10 are fully implemented). There is no
"implement early" vs "implement later" distinction. All contract tests must pass against the
current codebase on day one.
