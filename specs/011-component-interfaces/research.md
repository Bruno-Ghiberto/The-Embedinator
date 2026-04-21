# Research: Component Interface Contracts

**Feature**: 011-component-interfaces
**Date**: 2026-03-17

## Research Decisions

### R1: Deliverable Format

- **Decision**: Validated contract documentation (11-specify.md) + automated contract tests
- **Rationale**: Documentation alone drifts silently. Automated tests that introspect actual signatures via `inspect.signature()` fail immediately when code changes break contracts, providing continuous enforcement without runtime overhead.
- **Alternatives considered**:
  - Type stubs (.pyi files): Rejected — high maintenance burden, requires mypy/pyright CI pipeline, and doesn't cover method existence or DI pattern verification
  - Protocol classes: Rejected — adds runtime complexity for enforcement that can be achieved more simply with test-time introspection
  - Documentation only: Rejected — spec's Q1 clarification explicitly chose tests + docs

### R2: Schema Documentation Depth

- **Decision**: Full field definitions for 6 cross-layer schemas; categorized name listing for remaining 34+
- **Rationale**: Cross-layer schemas (QueryAnalysis, RetrievedChunk, Citation, SubAnswer, GroundednessResult, ClaimVerification) are consumed by multiple specs and DI patterns — incorrect field assumptions cause integration failures. API-specific schemas (ProviderResponse, SettingsUpdateRequest, etc.) are consumed only by their own FastAPI router.
- **Alternatives considered**:
  - Full fields for all 40+ models: Rejected — doubles contract doc size for models with single-consumer scope
  - Names only for all: Rejected — insufficient for the 6 models that cross agent/storage/retrieval boundaries

### R3: API Routes Scope

- **Decision**: Out of scope — API routes covered by spec-08 (API Reference)
- **Rationale**: Spec-11 covers internal inter-component boundaries (nodes calling storage, tools calling searcher, etc.). HTTP-level contracts (methods, paths, status codes, request/response bodies) are spec-08's domain.
- **Alternatives considered**:
  - Include route→backend dependency mapping: Rejected — would duplicate spec-08 without adding value; better addressed by amending spec-08 if needed

### R4: Contract Test Approach

- **Decision**: Python `inspect.signature()` for all signature introspection
- **Rationale**: The `inspect` module is stdlib, requires no external dependencies, works on imported symbols without instantiation, and verifies parameter names, order, kinds (KEYWORD_ONLY, POSITIONAL_OR_KEYWORD, VAR_KEYWORD), and default values. It handles all three DI patterns correctly.
- **Alternatives considered**:
  - mypy/pyright static analysis: Rejected — requires full type stubs and CI integration; overkill for verifying method existence and parameter names
  - AST parsing: Rejected — more complex than `inspect` and doesn't handle dynamic attributes
  - Runtime Protocol checks: Rejected — requires instantiation which needs external services

### R5: Test Isolation

- **Decision**: Contract tests import modules only — no database, network, or service dependencies
- **Rationale**: Tests must run in `tests/unit/` without Docker services (Qdrant, Ollama). `inspect.signature()` and `typing.get_type_hints()` work on imported Python symbols without instantiating objects or connecting to services.
- **Alternatives considered**:
  - Integration-level contract tests: Rejected — would require full Docker stack just to verify that `SQLiteDB.create_query_trace` has the right parameter names

## No Unresolved Items

All NEEDS CLARIFICATION items were resolved during the `/speckit.clarify` session (2026-03-17). No further research is required.
