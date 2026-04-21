# Implementation Plan: Component Interface Contracts

**Branch**: `011-component-interfaces` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/011-component-interfaces/spec.md`

## Summary

Spec 11 validates the type contracts between all major backend components of The Embedinator and produces automated contract tests that introspect actual function signatures via Python's `inspect` module. The deliverable is twofold: (1) a validated `11-specify.md` canonical contract document, and (2) six contract test files that fail when code diverges from documented contracts. No application logic is modified — only new test files are created.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: `inspect` (stdlib), `typing` (stdlib), `dataclasses` (stdlib), `abc` (stdlib), `pydantic` >= 2.12 (for `BaseModel`/`BaseSettings` assertions), `pytest` (test runner)
**Storage**: N/A — contract tests introspect signatures, they do not access databases or services
**Testing**: `pytest` via `zsh scripts/run-tests-external.sh -n <name> <target>` — NEVER run pytest inside Claude Code
**Target Platform**: Linux server (Fedora)
**Project Type**: Test suite (additive — no existing files modified)
**Performance Goals**: N/A — signature introspection is instant
**Constraints**: All contract tests MUST run without external services (Qdrant, Ollama, SQLite). They only import modules and inspect signatures.
**Scale/Scope**: 6 new test files covering 8 primary classes (35+ methods on SQLiteDB alone), 20 node functions, 7 edge functions, 6 tools, 3 graph builders, 11 error classes, 40+ Pydantic schemas

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| # | Principle | Status | Rationale |
|---|-----------|--------|-----------|
| I | Local-First Privacy | PASS | No network calls added. Contract tests are pure import + `inspect` — no services required. |
| II | Three-Layer Agent Architecture | PASS | Contract tests validate the 3-layer structure (ConversationGraph, ResearchGraph, MetaReasoningGraph) by verifying node and edge function signatures exist in their correct files. |
| III | Retrieval Pipeline Integrity | PASS | Contract tests verify HybridSearcher, Reranker, and ScoreNormalizer interfaces match documented contracts. No pipeline components are removed or modified. |
| IV | Observability from Day One | PASS | Contract tests verify `create_query_trace` exists on SQLiteDB with all 16 parameters including `provider_name`. |
| V | Secure by Design | PASS | Contract tests verify KeyManager has `encrypt`, `decrypt`, `is_valid_key` methods. No credentials are accessed or stored. Constitution v1.0.1 §V "ValueError + key_manager=None + 503" pattern is validated by verifying KeyManager constructor signature. |
| VI | NDJSON Streaming Contract | PASS | Contract tests verify all 10 NDJSON event models exist in `schemas.py` with `type` discriminator fields. |
| VII | Simplicity by Default | PASS | Only adding test files to `tests/unit/`. No new services, no new abstractions. The simplest approach: `inspect.signature()` + `assert`. |

**All gates pass. No violations.**

## Project Structure

### Documentation (this feature)

```text
specs/011-component-interfaces/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output (research decisions)
├── data-model.md        # Phase 1 output (contract entity model)
├── quickstart.md        # Phase 1 output (how to run contract tests)
├── contracts/           # Phase 1 output (contract verification approach)
│   └── test-patterns.md # Contract test pattern catalog
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
tests/
  unit/
    test_contracts_agent.py          # NEW — State schemas, node signatures, edge functions,
                                     #        tools, graph builders, confidence scoring
    test_contracts_storage.py        # NEW — SQLiteDB (35+ methods), QdrantStorage (12+ methods),
                                     #        ParentStore, data classes
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

**Structure Decision**: All new files are additive test files in `tests/unit/`. No existing source files are modified. The contract tests use only stdlib `inspect` + `typing` modules to introspect signatures — they do not execute application logic or require external services.

## Phase 0: Research

### Research Decisions

There are no NEEDS CLARIFICATION items in the technical context. The spec clarifications (session 2026-03-17) resolved all ambiguities:

**R1: Deliverable format**
- **Decision**: Validated contract doc + automated contract tests
- **Rationale**: Documentation alone drifts. Automated tests enforce contracts continuously.
- **Alternatives**: Type stubs (.pyi files — rejected: too much maintenance overhead), Protocol classes (rejected: runtime enforcement not needed for existing code)

**R2: Schema documentation depth**
- **Decision**: Full field definitions for 6 cross-layer schemas; categorized name listing for rest
- **Rationale**: Cross-layer schemas (QueryAnalysis, RetrievedChunk, Citation, SubAnswer, GroundednessResult, ClaimVerification) are used across multiple specs. API-specific schemas are consumed only by their own router.
- **Alternatives**: Full fields for all 40+ (rejected: excessive scope), names only (rejected: insufficient for cross-layer integration)

**R3: API routes scope**
- **Decision**: Out of scope — API routes covered by spec-08
- **Rationale**: Spec-11 covers internal inter-component boundaries. API route contracts (HTTP methods, paths, status codes) are spec-08's domain.
- **Alternatives**: Include route→backend dependency mapping (rejected: better suited for spec-08 amendments)

**R4: Contract test approach**
- **Decision**: Python `inspect.signature()` for signature introspection
- **Rationale**: Verifies parameter names, order, kinds (KEYWORD_ONLY vs POSITIONAL_OR_KEYWORD vs VAR_KEYWORD), and default values without executing application logic. Works with all DI patterns.
- **Alternatives**: mypy/pyright static analysis (rejected: requires full type stubs), runtime Protocol checks (rejected: over-engineering for validation)

**R5: Test isolation**
- **Decision**: Contract tests import modules only — no database, network, or service dependencies
- **Rationale**: Tests must run in `tests/unit/` without Docker services. `inspect.signature()` works on imported symbols without instantiation.
- **Alternatives**: Integration-level contract tests (rejected: would require full service stack for simple signature checks)

## Phase 1: Design

### Data Model (`data-model.md` content)

The "entities" for this spec are contract categories — the types of signatures being validated:

| Entity | Description | Count | Key Attributes |
|--------|-------------|-------|----------------|
| State Schema | TypedDict defining graph state | 3 | Field names, field types, field count |
| Node Function | Graph node with DI pattern | 20 | Params, param kinds, return type, module location |
| Edge Function | Graph routing function | 7 | Params, return type, module location |
| Tool | Closure-factory inner function | 6 | Factory params, tool count |
| Graph Builder | StateGraph compile function | 3 | Module location, function existence |
| Storage Method | SQLiteDB/QdrantStorage method | 47+ | Method name, param names, param defaults |
| Retrieval Method | HybridSearcher/Reranker method | 5+ | Constructor params, method params |
| Ingestion Class | Pipeline/Embedder/Chunker | 5 | Constructor params, key methods, result type |
| Provider Interface | ABC abstract methods | 8+ | Abstract method names, concrete subclasses |
| Error Class | Exception hierarchy | 11 | Class name, parent class |
| Pydantic Schema | BaseModel subclass | 40+ | Class name, importability, key fields (6 cross-layer) |
| NDJSON Event | Streaming event model | 10 | Class name, `type` discriminator |

**Validation rules**: Each contract test asserts structural properties (existence, names, types, kinds) — never behavioral properties (those are covered by specs 02-10).

### Interface Contracts (`contracts/test-patterns.md` content)

Seven contract test patterns cover all validation needs:

**Pattern 1: Function Signature**
```python
def test_classify_intent_signature():
    sig = inspect.signature(classify_intent)
    params = list(sig.parameters.keys())
    assert params == ["state", "llm"]
    assert sig.parameters["llm"].kind == inspect.Parameter.KEYWORD_ONLY
```

**Pattern 2: Class Method Existence**
```python
def test_sqlite_db_methods():
    for method_name in REQUIRED_METHODS:
        assert hasattr(SQLiteDB, method_name), f"Missing: {method_name}"
```

**Pattern 3: Error Hierarchy**
```python
def test_error_hierarchy():
    for cls in ALL_ERROR_CLASSES:
        assert issubclass(cls, EmbeddinatorError)
```

**Pattern 4: Dataclass vs Pydantic**
```python
def test_ingestion_result_type():
    assert dataclasses.is_dataclass(IngestionResult)
    assert not issubclass(IngestionResult, BaseModel)
```

**Pattern 5: ABC Enforcement**
```python
def test_llm_provider_abstract():
    abstract_methods = {n for n, m in vars(LLMProvider).items() if getattr(m, "__isabstractmethod__", False)}
    assert abstract_methods == {"generate", "generate_stream", "health_check", "get_model_name"}
```

**Pattern 6: Dual Confidence Scale**
```python
def test_dual_confidence_scale():
    conv_hints = typing.get_type_hints(ConversationState)
    research_hints = typing.get_type_hints(ResearchState)
    assert conv_hints["confidence_score"] is int
    assert research_hints["confidence_score"] is float
```

**Pattern 7: Method Name Assertions (negative)**
```python
def test_no_phantom_methods():
    assert not hasattr(Reranker, "score_pair")
    assert not hasattr(IngestionPipeline, "check_duplicate")
    assert not hasattr(SQLiteDB, "find_by_hash")
```

### Quickstart (`quickstart.md` content)

```bash
# Run all contract tests
zsh scripts/run-tests-external.sh -n contracts tests/unit/test_contracts_*.py

# Run a specific contract test file
zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py

# Check results
cat Docs/Tests/contracts.status      # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/contracts.summary     # ~20 lines summary

# Full regression (includes contract tests + all existing tests)
zsh scripts/run-tests-external.sh -n full-regression tests/
```

### Agent Context Update

```bash
bash .specify/scripts/bash/update-agent-context.sh claude
```

New technology added: None (only stdlib `inspect` module used). The update script will add the spec-11 file references to CLAUDE.md.

## Constitution Re-Check (Post Phase 1)

| # | Principle | Status | Notes |
|---|-----------|--------|-------|
| I | Local-First Privacy | PASS | No change — tests are offline |
| II | Three-Layer Agent Architecture | PASS | Tests validate the 3-layer structure |
| III | Retrieval Pipeline Integrity | PASS | Tests validate pipeline component interfaces |
| IV | Observability from Day One | PASS | Tests validate trace recording interface |
| V | Secure by Design | PASS | Tests validate KeyManager contract |
| VI | NDJSON Streaming Contract | PASS | Tests validate all 10 event models |
| VII | Simplicity by Default | PASS | Only `inspect` + `assert` — minimal complexity |

**All gates pass. No violations. No complexity tracking needed.**
