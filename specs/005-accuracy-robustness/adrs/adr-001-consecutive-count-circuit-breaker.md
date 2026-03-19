# ADR-001: Consecutive-Count Circuit Breaker (Approved Deviation from Constitution §Reliability Standards)

**Date**: 2026-03-12 | **Branch**: `005-accuracy-robustness` | **Status**: ACCEPTED

## Context

The project constitution §Reliability Standards states: *"Circuit breaker MUST wrap ALL Qdrant and Ollama call sites: **5 failures in 30s** opens the circuit; half-open probe after cooldown."*

The phrase "5 failures in 30s" implies a time-windowed failure counter: the circuit opens when 5 failures occur within any rolling 30-second window, and the counter resets outside that window.

## Problem

Spec-03 (`003-research-graph`) implemented `HybridSearcher` with a **consecutive-count** circuit breaker: the circuit opens after 5 consecutive failures with no time window. The 30-second cooldown before the half-open probe is preserved. This implementation was accepted and shipped. Spec-05 (`005-accuracy-robustness`) proposes extending the same pattern to `QdrantClient` and the inference service, following the spec-03 precedent for consistency.

## Decision

**Use consecutive-count circuit breaker** (no time window) across all circuit breaker instances in this codebase. Specifically:

- A circuit opens after **N consecutive failures** (N = `settings.circuit_breaker_failure_threshold`, default 5).
- A success at any time resets the consecutive counter to 0, regardless of how recently failures occurred.
- The 30-second cooldown before the half-open probe is preserved as specified by the constitution.

## Rationale

1. **Consistency**: Deviating between instances would create two different failure semantics in the same process, introducing subtle debugging complexity.
2. **Operational equivalence**: For the 1–5 concurrent user scale of this system, consecutive-count is operationally equivalent to time-windowed counting — a burst of failures from a single request chain behaves identically under both models.
3. **Established precedent**: Spec-03 C1 (HybridSearcher) was reviewed and accepted without raising this issue. This ADR formalises the standing implementation.
4. **YAGNI**: A sliding-window counter adds implementation complexity without measurable benefit at the system's design scale.

## Consequences

- The constitution's Reliability Standards wording ("5 failures in 30s") remains unchanged but is interpreted as "5 consecutive failures + 30s cooldown" for this codebase.
- If the system scales beyond 1–5 concurrent users in a future spec, a new ADR should revisit whether time-windowed counting becomes necessary.
- All three circuit breaker instances (HybridSearcher, QdrantClient, inference service nodes) MUST use this same pattern.

## Supersedes

None. This ADR clarifies the constitution's intent for this implementation context; it does not reverse any prior ADR.
