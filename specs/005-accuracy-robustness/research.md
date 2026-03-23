# Research: Accuracy, Precision & Robustness Enhancements

**Date**: 2026-03-12 | **Branch**: `005-accuracy-robustness`

## Research Tasks Resolved

### R1: Circuit Breaker — Custom State Machine vs. Tenacity Built-in

**Decision**: Extend the existing HybridSearcher custom state machine pattern.

**Rationale**: Tenacity 9.x does not natively expose the half-open probe semantics (allow exactly one test request after cooldown, re-open on failure). Its `CircuitBreaker` plugin is available but requires additional configuration and deviates from the established pattern. The HybridSearcher already implements the correct Closed → Open → HalfOpen → Closed lifecycle with consecutive-count tracking. Replicating the same 4-field pattern (`_circuit_open`, `_failure_count`, `_max_failures`, `_cooldown_secs`) in `qdrant_client.py` gives zero new learning curve and full consistency.

**Alternatives considered**:
- `tenacity.CircuitBreaker` — rejected: adds indirection, lacks native half-open probe, inconsistent with spec-03 implementation
- pybreaker library — rejected: new dependency; constitution requires justifying new core deps with an ADR

**Implementation reference**: `backend/retrieval/searcher.py:HybridSearcher._check_circuit` (lines 47–51)

---

### R2: GAV Claim Extraction Strategy

**Decision**: Batch evaluation via structured LLM output — the LLM is asked to evaluate the entire proposed answer at once and return per-claim verdicts in `GroundednessResult.verifications`.

**Rationale**: The alternative (splitting the answer into individual claims before calling the LLM) requires a claim-extraction step, doubling LLM calls. The `VERIFY_PROMPT` passes the full answer and asks the LLM to identify and evaluate each factual claim itself. This satisfies SC-009 ("at most one additional inference call per answer") and matches the blueprint design intent.

**Prompt approach**: System prompt instructs the LLM to extract claims from the answer text and return them as structured output. The LLM's claim decomposition is treated as authoritative (no pre-processing).

**Failure handling**: `with_structured_output(GroundednessResult)` raises `ValidationError` on malformed output. Catch at the node level, log warning, return `{"groundedness_result": None}` (graceful degradation per FR-005).

---

### R3: Citation Claim Text Extraction

**Decision**: Regex-based sentence boundary extraction around each `[N]` marker.

**Rationale**: Citations in The Embedinator's format (`[1]`, `[2]`) are inline with claim text. The sentence containing the marker is the relevant claim. A simple regex split on sentence boundaries (`.!?`) around the marker position is deterministic, dependency-free, and adequate for cross-encoder scoring. Sub-sentence precision is not required since cross-encoder scores are coarse (0–1 range, threshold at 0.3).

**Pattern**:
```python
import re

def extract_claim_for_citation(text: str, marker: str) -> str:
    """Return the sentence containing the citation marker."""
    # Split on sentence boundaries, find the sentence with marker
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sentence in sentences:
        if marker in sentence:
            return sentence.strip()
    return text[:200]  # Fallback: first 200 chars
```

**Alternatives considered**:
- spaCy sentence segmentation — rejected: heavy new dependency; regex is sufficient
- Full paragraph context — rejected: cross-encoder context window waste; sentence is specific enough

---

### R4: TIER_PARAMS Placement and Application

**Decision**: Module-level constant dict in `backend/agent/nodes.py`, applied inside `rewrite_query` after LLM classification.

**Rationale**: The tier parameters are consumed exclusively by `rewrite_query` and downstream ResearchGraph invocation. Placing them in `nodes.py` co-locates them with the consuming function. Adding them to `config.py` would be premature complexity (constitution Principle VII) since the values are not operator-tunable in spec-05 (tuning deferred to future spec).

**Application pattern**: After `analysis = await structured_llm.ainvoke(...)`, look up `TIER_PARAMS[analysis.complexity_tier]` and add the result to the returned state dict as `retrieval_params`. The ResearchGraph invocation (fan-out via `Send()`) passes these as configurable values.

**Note**: `ConversationState` does not currently have a `retrieval_params` field. Two options:
1. Add `retrieval_params: dict` to `ConversationState` TypedDict
2. Pass tier params directly in the `Send()` config for each sub-question

**Chosen**: Option 2 — pass via `Send()` config to avoid mutating the established `ConversationState` schema. This is a partial dict return from `rewrite_query` using LangGraph's `Send()` mechanism (consistent with how `fan_out` / `route_fan_out` works in spec-02).

---

### R5: Confidence Adjustment Formula

**Decision**: Multiplier model — `adjusted = clamp(int(mean(sub_answers.confidence_score) × confidence_adjustment), 0, 100)`.

**Rationale**: The `confidence_adjustment` field in `GroundednessResult` is a float multiplier (0.0–1.0). The pre-computed ResearchGraph scores (`SubAnswer.confidence_score`, int 0-100) are aggregated by mean. The multiplier scales the aggregate based on groundedness (e.g., 0.7 if 30% of claims are unsupported, 1.0 if fully grounded). This preserves retrieval quality signal while adding answer quality signal.

**Boundary conditions**:
- `confidence_adjustment = 1.0` (fully grounded): score unchanged
- `confidence_adjustment = 0.0` (all contradicted): score → 0
- No sub-answers (empty list): use 0 as base, adjustment gives 0

---

### R6: SSE/NDJSON Streaming Contract for Groundedness

**Decision**: No new event types. The existing `metadata` frame's `confidence` field carries the GAV-adjusted score. Groundedness summary counts (supported/unsupported/contradicted) are included in the `metadata` frame as an optional `groundedness` object.

**Rationale**: Adding a new `groundedness` SSE event type would require client changes (spec-09, spec-08). The metadata frame already carries `confidence` — upgrading it with an optional `groundedness` sub-object is backwards compatible. Clients that don't read the field are unaffected.

**Updated metadata frame schema**:
```json
{
  "type": "metadata",
  "trace_id": "...",
  "confidence": 75,
  "groundedness": {
    "supported": 4,
    "unsupported": 1,
    "contradicted": 0,
    "overall_grounded": true
  },
  "citations": [...],
  "latency_ms": 1240
}
```
`groundedness` is `null` when `groundedness_check_enabled=False` or when GAV fails gracefully.

---

## Deferred Items

| Item | Deferred To | Reason |
|------|-------------|--------|
| `validate_embedding()` function | spec-06 | `backend/ingestion/embedder.py` doesn't exist yet |
| Ingestion circuit breaker | spec-06 | Same file dependency |
| In-memory upsert buffer | spec-06 | Ingestion pipeline scope |
| Groundedness metric dashboards | spec-15 | Observability spec owns all metrics/dashboards |
