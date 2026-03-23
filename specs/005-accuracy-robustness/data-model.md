# Data Model: Accuracy, Precision & Robustness Enhancements

**Date**: 2026-03-12 | **Branch**: `005-accuracy-robustness`

## Overview

This feature introduces no new persistent storage. All new entities are ephemeral (in-flight only, not written to SQLite or Qdrant). The circuit breaker state is in-memory per process instance. Existing state fields are extended, not replaced.

---

## Ephemeral Entities (In-Pipeline Only)

### ClaimVerification *(already defined in `backend/agent/schemas.py`)*

Represents the groundedness verdict for one factual claim extracted from the answer.

| Field | Type | Description |
|-------|------|-------------|
| `claim` | `str` | The factual claim text extracted from the answer |
| `verdict` | `Literal["supported", "unsupported", "contradicted"]` | Groundedness verdict from LLM |
| `evidence_chunk_id` | `str \| None` | ID of the chunk that supports or contradicts the claim |
| `explanation` | `str` | Brief LLM-generated reasoning for the verdict |

**Validation rules**:
- `verdict` must be one of exactly three values (Pydantic Literal enforces this)
- `evidence_chunk_id` may be None for unsupported claims (no evidence found)
- `explanation` is always non-empty (LLM is instructed to provide reasoning)

**Lifecycle**: Created inside `verify_groundedness` node; discarded after response delivery.

---

### GroundednessResult *(already defined in `backend/agent/schemas.py`)*

Aggregated output of the groundedness verification step.

| Field | Type | Description |
|-------|------|-------------|
| `verifications` | `list[ClaimVerification]` | Per-claim verdict list |
| `overall_grounded` | `bool` | True if ≥50% of claims are SUPPORTED |
| `confidence_adjustment` | `float` | Multiplier applied to confidence score (0.0–1.0) |

**Validation rules**:
- `confidence_adjustment` is in range [0.0, 1.0]; clamped by application code if LLM returns out-of-range
- `overall_grounded = (supported_count / max(1, len(verifications))) >= 0.5`

**Lifecycle**: Returned by `verify_groundedness`; stored in `ConversationState["groundedness_result"]` during response pipeline; discarded after response delivery. **Not persisted to SQLite or Qdrant.**

---

### ComplexityTier *(already defined as `QueryAnalysis.complexity_tier` in `backend/agent/schemas.py`)*

Enum-like Literal field in `QueryAnalysis` that drives retrieval depth selection.

| Value | top_k | max_iterations | max_tool_calls | confidence_threshold |
|-------|-------|----------------|----------------|---------------------|
| `factoid` | 5 | 3 | 3 | 0.7 |
| `lookup` | 10 | 5 | 5 | 0.6 |
| `comparison` | 15 | 7 | 6 | 0.55 |
| `analytical` | 25 | 10 | 8 | 0.5 |
| `multi_hop` | 30 | 10 | 8 | 0.45 |

**Lifecycle**: Set by LLM during `rewrite_query`; used to configure ResearchGraph invocation via `Send()` config; not stored.

---

## In-Memory Stateful Entity (Per Process)

### CircuitBreakerState (per service instance)

Tracks the health of one external service (Qdrant or Ollama) within a single process instance.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `_circuit_open` | `bool` | `False` | True when circuit is open (failing fast) |
| `_failure_count` | `int` | `0` | Consecutive failure count since last success |
| `_last_failure_time` | `float \| None` | `None` | `time.monotonic()` of most recent failure |
| `_max_failures` | `int` | `5` | Threshold to open circuit (from Settings) |
| `_cooldown_secs` | `int` | `30` | Seconds before half-open probe (from Settings) |

**State transitions**:
```
Closed ──(5 consecutive failures)──► Open
Open   ──(30s cooldown elapsed)────► HalfOpen
HalfOpen ──(probe succeeds)─────────► Closed
HalfOpen ──(probe fails)────────────► Open
```

**Instance count**: Three instances — all use the same consecutive-count pattern (see ADR-001):
1. `HybridSearcher` — wraps Qdrant **search** calls; exists from spec-03 C1
2. `QdrantClient` — wraps Qdrant **ingestion** calls (`upsert`, `delete`, etc.); added by this spec (FR-017 vector store side)
3. `backend/agent/nodes.py` module-level — wraps **LLM inference** calls (`llm.ainvoke()`); added by this spec (FR-017 inference service side)

**Not shared between instances.**

**Persistence**: In-memory only. Circuit state resets on process restart.

---

## ConversationState Extensions

`ConversationState` already contains `groundedness_result: GroundednessResult | None` and `confidence_score: int` from spec-02. This feature **populates** those fields (previously always `None` / default):

| Field | Set By | Previous Value | New Value |
|-------|--------|----------------|-----------|
| `groundedness_result` | `verify_groundedness` node | `None` (stub) | `GroundednessResult` or `None` on failure |
| `confidence_score` | `verify_groundedness` node | `0` (stub) | GAV-adjusted int 0-100 |

No new fields added to `ConversationState`.

---

## No Persistent Storage Changes

| Storage | Change |
|---------|--------|
| `data/embedinator.db` | None — no new tables, no new columns |
| `data/checkpoints.db` | None — checkpoint structure unchanged |
| Qdrant collections | None — no new collections |

The `query_traces` table (spec-15 concern) will eventually include `confidence_score` from `ConversationState`. That write is implemented in the observability spec, not here.
