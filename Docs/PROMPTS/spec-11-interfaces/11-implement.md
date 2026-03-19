# Implementation Guide: Component Interface Contracts (spec-11)

---

> **AGENT TEAMS -- tmux IS REQUIRED**
>
> This spec uses 4 waves with 5 agents. Wave 2 runs A2 and A3 in parallel -- each agent
> MUST get its own tmux pane. Without an active tmux session, parallel execution falls back
> to sequential, which is slower but still correct. Start implementation inside tmux:
> `tmux new-session -s spec11` or attach to your existing session.
>
> **Orchestrator protocol**:
> 1. Read THIS file first (you are doing this now)
> 2. Spawn agents by wave, one per tmux pane
> 3. Each agent's FIRST action is to read its instruction file
> 4. Wait for wave gate before spawning the next wave
>
> Spawn command for every agent (no exceptions):
> ```
> Agent(
>   subagent_type="<type>",
>   model="<model>",
>   prompt="Read your instruction file at Docs/PROMPTS/spec-11-interfaces/agents/<file>.md FIRST, then execute all assigned tasks"
> )
> ```

---

## Wave Definitions

### Wave 1: Validate Contracts (sequential -- must complete before Wave 2)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A1 | quality-engineer | opus | T003-T012 | Validated `11-specify.md` + `Docs/Tests/contracts-validation-report.md` |

**Instruction file**: `Docs/PROMPTS/spec-11-interfaces/agents/A1-validation.md`

**Gate**: Validation report confirms zero discrepancies between `11-specify.md` and live code. If discrepancies are found, A1 fixes `11-specify.md` before reporting done.

### Wave 2: Agent + Storage Contract Tests (PARALLEL -- two tmux panes)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A2 | python-expert | sonnet | T013-T022 | `tests/unit/test_contracts_agent.py` |
| A3 | python-expert | sonnet | T023-T029, T035-T038 | `tests/unit/test_contracts_storage.py`, `tests/unit/test_contracts_retrieval.py` |

**Instruction files**:
- `Docs/PROMPTS/spec-11-interfaces/agents/A2-agent-contracts.md`
- `Docs/PROMPTS/spec-11-interfaces/agents/A3-storage-retrieval-contracts.md`

**Gate**: Both agents report done AND both test files pass via external runner.

### Wave 3: Remaining Contract Tests (sequential after Wave 2)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A4 | python-expert | sonnet | T030-T034, T039-T052 | `tests/unit/test_contracts_providers.py`, `tests/unit/test_contracts_ingestion.py`, `tests/unit/test_contracts_cross_cutting.py` |

**Instruction file**: `Docs/PROMPTS/spec-11-interfaces/agents/A4-remaining-contracts.md`

**Gate**: All 3 test files pass via external runner.

### Wave 4: Final Gate (sequential after Wave 3)

| Agent | Type | Model | Tasks | Output |
|-------|------|-------|-------|--------|
| A5 | quality-engineer | sonnet | T053-T056 | Verified zero regressions |

**Instruction file**: `Docs/PROMPTS/spec-11-interfaces/agents/A5-final-gate.md`

**Gate**: All 6 contract test files pass AND full regression passes with zero regressions against 977 existing tests.

---

## Implementation Scope

### What This Spec Does

The codebase already exists (specs 02-10 are fully implemented, 977 tests passing). Spec 11 does NOT create application code. It:

1. **Validates** the contract documentation in `11-specify.md` against the live codebase
2. **Writes 6 contract test files** using Python `inspect.signature()` introspection
3. **Runs all tests** via the external test runner to confirm zero drift

### Files to Create

```
tests/unit/
  test_contracts_agent.py         # State schemas, 20 nodes, 7 edges, tools, graph builders, confidence
  test_contracts_storage.py       # SQLiteDB (35+ methods), QdrantStorage, ParentStore
  test_contracts_retrieval.py     # HybridSearcher, Reranker, ScoreNormalizer
  test_contracts_ingestion.py     # IngestionPipeline, BatchEmbedder, ChunkSplitter, IncrementalChecker, UpsertBuffer
  test_contracts_providers.py     # LLMProvider, EmbeddingProvider, ProviderRegistry, KeyManager, concrete providers
  test_contracts_cross_cutting.py # Error hierarchy, Pydantic schemas, NDJSON events, Settings

Docs/Tests/
  contracts-validation-report.md  # A1 validation output
```

### Files NOT to Modify

No existing source files should be modified by any agent. The only exception is `11-specify.md` itself, which A1 may fix if validation reveals discrepancies.

### What Already Exists

- `Docs/PROMPTS/spec-11-interfaces/11-specify.md` -- 1320 lines of contract documentation
- All backend code from specs 02-10 (fully implemented)
- 977 passing tests, 39 known pre-existing failures

---

## Contract Test Patterns

All contract tests use pure introspection -- no application logic is executed, no services or databases are required. Reference: `specs/011-component-interfaces/contracts/test-patterns.md`

### Pattern 1: Function Signature Verification

```python
import inspect

def test_classify_intent_signature():
    from backend.agent.nodes import classify_intent
    sig = inspect.signature(classify_intent)
    params = list(sig.parameters.keys())
    assert params == ["state", "llm"]
    assert sig.parameters["state"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert sig.parameters["llm"].kind == inspect.Parameter.KEYWORD_ONLY
```

Applies to: all 20 node functions, 7 edge functions, tool factory, graph builders.

### Pattern 2: Class Method Existence

```python
def test_sqlite_db_methods():
    from backend.storage.sqlite_db import SQLiteDB
    required = ["create_collection", "get_collection", ...]
    for name in required:
        assert hasattr(SQLiteDB, name), f"SQLiteDB missing: {name}"
```

Applies to: SQLiteDB (35+), QdrantStorage (12+), HybridSearcher, Reranker, BatchEmbedder, IngestionPipeline, ProviderRegistry, KeyManager.

### Pattern 3: Error Hierarchy Verification

```python
def test_error_hierarchy():
    from backend.errors import EmbeddinatorError, QdrantConnectionError, ...
    for cls in [...]:
        assert issubclass(cls, EmbeddinatorError)
```

Applies to: 11 error classes in `backend/errors.py`.

### Pattern 4: Dataclass vs Pydantic Distinction

```python
import dataclasses
from pydantic import BaseModel

def test_ingestion_result_is_dataclass():
    from backend.ingestion.pipeline import IngestionResult
    assert dataclasses.is_dataclass(IngestionResult)
    assert not issubclass(IngestionResult, BaseModel)
```

Applies to: `IngestionResult` (dataclass), all Pydantic schemas (BaseModel).

### Pattern 5: ABC Enforcement

```python
import abc

def test_llm_provider_abstract():
    from backend.providers.base import LLMProvider
    assert abc.ABC in LLMProvider.__mro__
    abstract_methods = {
        n for n, m in vars(LLMProvider).items()
        if getattr(m, "__isabstractmethod__", False)
    }
    assert abstract_methods == {"generate", "generate_stream", "health_check", "get_model_name"}
```

Applies to: LLMProvider (4 methods), EmbeddingProvider (4 methods).

### Pattern 6: Dual Confidence Scale

```python
import typing

def test_dual_confidence_scale():
    from backend.agent.state import ConversationState, ResearchState
    conv = typing.get_type_hints(ConversationState)
    research = typing.get_type_hints(ResearchState)
    assert conv["confidence_score"] is int
    assert research["confidence_score"] is float
```

Applies to: `ConversationState.confidence_score` (int), `ResearchState.confidence_score` (float).

### Pattern 7: Negative Assertions (Phantom Methods)

```python
def test_no_phantom_methods():
    from backend.retrieval.reranker import Reranker
    assert not hasattr(Reranker, "score_pair")
```

Applies to: all known wrong method names identified during contract validation.

---

## Key Technical Facts

The previous version of `11-implement.md` was completely wrong. These 15 corrections prevent agents from repeating old mistakes:

1. **3 DI patterns, not uniform keyword-only**: ConversationGraph nodes use `*, llm: Any` (keyword-only) or `**kwargs` (VAR_KEYWORD) or nothing. ResearchGraph and MetaReasoningGraph nodes use `config: RunnableConfig = None`.

2. **Node functions return `dict`, not full State TypedDicts**: Every node returns a partial dict with only the fields it updates. LangGraph merges these into the state.

3. **`llm` type is `Any`, not `BaseChatModel`**: The `llm` parameter on conversation nodes is typed as `Any` (from `typing`), not `BaseChatModel`.

4. **No ORM types exist**: There are no `CollectionRow`, `DocumentRow`, `JobRow`, `TraceRow`, `ParentChunkRow`, or `ProviderRow` Pydantic models. `SQLiteDB` methods return raw `dict` values.

5. **No `EmbeddingResult` class**: The embedder does not define an `EmbeddingResult` model. `embed_chunks` returns `tuple[list[list[float] | None], int]`.

6. **`IngestionResult` is a `@dataclass`, not a `BaseModel`**: Use `dataclasses.is_dataclass()` to verify, not `issubclass(IngestionResult, BaseModel)`.

7. **Method name: `embed_chunks`, not `embed_batch`**: The `BatchEmbedder` method is `embed_chunks(texts: list[str]) -> tuple[list[list[float] | None], int]`.

8. **Method name: `batch_upsert`, not `upsert_batch`**: The `QdrantStorage` method is `batch_upsert`.

9. **Method name: `search_hybrid`, not `hybrid_search`**: The `QdrantStorage` method is `search_hybrid`.

10. **Method name: `search_all_collections`, not `search_multi_collection`**: The `HybridSearcher` method is `search_all_collections`.

11. **`validate_embedding` is a standalone function, not a method**: It is a module-level function in `embedder.py`, not a method on `BatchEmbedder`.

12. **`check_duplicate` lives on `IncrementalChecker`, not `IngestionPipeline`**: The pipeline does not have a `check_duplicate` method.

13. **`IngestionResult.error`, not `error_msg`**: The field is named `error`, and there is no `elapsed_ms` field.

14. **`IngestionPipeline` constructor takes 3 params**: `db`, `qdrant` (a `QdrantClientWrapper`, NOT `QdrantStorage`), and `embedding_provider`.

15. **`Reranker` constructor takes `settings: Settings`**: Not `model_name: str`. And `score_pair` does NOT exist.

---

## Testing Policy

**NEVER run pytest inside Claude Code.** Always use the external test runner:

```bash
zsh scripts/run-tests-external.sh -n <name> <target>
```

Output files:
- `Docs/Tests/<name>.status` -- poll for RUNNING | PASSED | FAILED | ERROR
- `Docs/Tests/<name>.summary` -- ~20 lines, token-efficient
- `Docs/Tests/<name>.log` -- full output

### Commands Per Wave

**Wave 1** (A1): No test execution -- validation only.

**Wave 2** (A2):
```bash
zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py
```

**Wave 2** (A3):
```bash
zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py
zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py
```

**Wave 3** (A4):
```bash
zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py
zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py
zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py
```

**Wave 4** (A5):
```bash
zsh scripts/run-tests-external.sh -n contracts-all tests/unit/test_contracts_agent.py tests/unit/test_contracts_storage.py tests/unit/test_contracts_retrieval.py tests/unit/test_contracts_ingestion.py tests/unit/test_contracts_providers.py tests/unit/test_contracts_cross_cutting.py
zsh scripts/run-tests-external.sh -n full-regression tests/
```

---

## Done Criteria

Mapped to success criteria from `spec.md`:

| SC | Criterion | Verified By |
|----|-----------|-------------|
| SC-001 | Every function signature matches live code with zero discrepancies | A1 validation report |
| SC-002 | Dual confidence scale documented at every conversion point | A2 test (Pattern 6) |
| SC-003 | Developer can wire a new node from contracts alone | 11-specify.md completeness |
| SC-004 | All 3 DI patterns documented with examples | 11-specify.md + A2 tests |
| SC-005 | Error hierarchy complete (11 classes, all subclass base) | A4 test (Pattern 3) |
| SC-006 | Zero fictional types or phantom methods | A3 negative assertions (Pattern 7) |
| SC-007 | 100% public methods on 8 primary classes covered | A2/A3/A4 method existence tests (Pattern 2) |
| SC-008 | Every node's state reads/writes documented | A1 validation of 11-specify.md |
| SC-009 | Contracts serve as single source of truth | Regression test confirms no breakage |
| SC-010 | Automated contract tests pass against current codebase | A5 final gate |
