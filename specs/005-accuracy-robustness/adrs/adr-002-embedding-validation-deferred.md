# ADR-002: Embedding Validation Deferred to spec-06 (Approved Deferral of Constitution §Reliability Standards MUST)

**Date**: 2026-03-12 | **Branch**: `005-accuracy-robustness` | **Status**: ACCEPTED

## Context

The project constitution §Reliability Standards states: *"Embeddings MUST be validated before upsert: reject NaN values, zero vectors, and dimension mismatches."*

This spec (005-accuracy-robustness) defines FR-014 and FR-015 for embedding vector validation and includes them as User Story 5 (P5). However, the validation logic would live in `backend/ingestion/embedder.py`, which **does not yet exist** — it will be created by spec-06 (Ingestion Pipeline).

## Problem

Implementing FR-014/FR-015 in this spec requires creating or scaffolding `backend/ingestion/embedder.py`, which is out of scope for spec-05 and would create a partial, non-functional ingestion module that spec-06 would then need to integrate. This creates ordering complexity and risks producing code that gets replaced.

## Decision

**Defer the physical implementation** of FR-014/FR-015 (`validate_embedding()` function and integration into the upsert path) to spec-06, which owns the ingestion pipeline and will create `backend/ingestion/embedder.py`.

This spec (005) **does** produce:
- The interface contract (`specs/005-accuracy-robustness/contracts/embedder-validation.md`) defining the function signature, four validation checks, and skip-and-log behaviour.
- FR-014 and FR-015 remain in the spec's Functional Requirements as the authoritative requirement source.

Spec-06 **will** implement:
- `validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]` in `backend/ingestion/embedder.py`.
- Integration into the upsert path before any call to `QdrantClient.upsert()`.

## Rationale

1. **Dependency ordering**: The ingestion pipeline component (`embedder.py`) is the natural home for this validation. Creating it here as a stub would duplicate work and create technical debt.
2. **Scope integrity**: Spec-05 focuses on the chat pipeline (GAV, citations, confidence, circuit breaker). Embedding ingestion is a separate concern.
3. **Contract-first**: Publishing the interface contract now ensures spec-06 implementors have a clear specification without delaying the spec-05 implementation.

## Consequences

- FR-014 and FR-015 are annotated as "deferred to spec-06" in spec.md and Out of Scope for this branch.
- SC-005 ("0% of invalid vectors stored") cannot be verified until spec-06 is implemented.
- Spec-06 MUST reference this ADR and implement the contract defined in `contracts/embedder-validation.md`.
- Until spec-06 ships, the constitution's embedding validation MUST is not satisfied. This is an accepted gap with a defined resolution path.

## Supersedes

None.
