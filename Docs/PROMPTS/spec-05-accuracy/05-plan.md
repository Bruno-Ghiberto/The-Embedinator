# Spec 05: Accuracy, Precision & Robustness Enhancements -- Implementation Plan Context

## Agent Teams Orchestration Protocol

**IMPORTANT: Read this section FIRST before reviewing the rest of the plan.**

Implementation uses the Claude Code Agent Teams API with 4 waves across 7 agents. Each agent reads its instruction file before starting any implementation work.

### Wave Structure

```
Wave 1 (Parallel) ─── A1: Circuit Breaker Extension (qdrant_client.py)
                   └── A2: Query-Adaptive Retrieval Depth (nodes.py rewrite_query)

Wave 2 (Parallel) ─── A3: GAV Node Implementation (verify_groundedness)
   [Gate: Wave 1]  └── A4: Citation Validation Implementation (validate_citations)

Wave 3 (Sequential) ── A5: Prompts + Integration Wiring
   [Gate: Wave 2]

Wave 4 (Parallel) ─── A6: Unit Tests
   [Gate: Wave 3]  └── A7: Integration Tests
```

### Agent Responsibilities

| Agent | Wave | Focus | Key Files |
|-------|------|-------|-----------|
| A1 | 1 | Circuit breaker pattern in `qdrant_client.py` | `backend/storage/qdrant_client.py` |
| A2 | 1 | Tier-based parameter lookup in `rewrite_query` | `backend/agent/nodes.py` |
| A3 | 2 | GAV `verify_groundedness` node body + confidence adjustment | `backend/agent/nodes.py` |
| A4 | 2 | Citation alignment `validate_citations` node body | `backend/agent/nodes.py`, `backend/retrieval/reranker.py` |
| A5 | 3 | `VERIFY_PROMPT` in prompts.py, `groundedness_check_enabled` flag wiring | `backend/agent/prompts.py`, `backend/agent/nodes.py` |
| A6 | 4 | Unit tests: circuit breaker, tier mapping, citation threshold | `tests/unit/` |
| A7 | 4 | Integration tests: GAV flow, citation flow, adaptive depth | `tests/integration/` |

### Spawn Protocol

Instruction files live at `Docs/PROMPTS/spec-05-accuracy/agents/`:
- `a1-circuit-breaker.md`
- `a2-adaptive-depth.md`
- `a3-gav-node.md`
- `a4-citation-validation.md`
- `a5-integration-wiring.md`
- `a6-unit-tests.md`
- `a7-integration-tests.md`

Spawn prompt for each agent: `"Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/<file> FIRST, then execute all assigned tasks."`

### Gate Conditions

- **Wave 1 → Wave 2**: Both A1 and A2 must complete without errors. Verify `qdrant_client.py` has one circuit per service; verify `rewrite_query` applies TIER_PARAMS lookup.
- **Wave 2 → Wave 3**: Both A3 and A4 must complete. Verify `verify_groundedness` returns a real `GroundednessResult`; verify `validate_citations` remaps/strips by threshold.
- **Wave 3 → Wave 4**: A5 must complete. Verify `VERIFY_PROMPT` is in `prompts.py`; verify `groundedness_check_enabled` short-circuits the node correctly.

### Testing Protocol

**CRITICAL: NEVER run pytest inside Claude Code.** All test execution uses the external runner:

```zsh
# Launch (returns immediately)
zsh scripts/run-tests-external.sh -n spec05-<wave> tests/

# Poll status
cat Docs/Tests/spec05-<wave>.status   # → RUNNING | PASSED | FAILED

# Read summary when done
cat Docs/Tests/spec05-<wave>.summary  # ~20 lines
```

Agents A6 and A7 write test files only. The orchestrator runs tests via the external script after Wave 4 completes.

---

## Implementation Scope

### What This Spec Does (New Work)

- Implements the body of `verify_groundedness` node (Phase 2 stub from spec-02)
- Implements the body of `validate_citations` node (Phase 2 stub from spec-02)
- Extends the circuit breaker pattern to `backend/storage/qdrant_client.py`
- Implements tier-to-parameters lookup in the existing `rewrite_query` node
- Applies GAV's `confidence_adjustment` to compute `ConversationState.confidence_score`

### What This Spec Does NOT Do

- **Does NOT redefine confidence formula**: `compute_confidence()` and `_signal_confidence()` are already fully implemented in `backend/agent/confidence.py` (spec-03 R8). Do not modify them.
- **Does NOT redefine schemas**: `ClaimVerification`, `GroundednessResult`, and `QueryAnalysis.complexity_tier` are already defined in `backend/agent/schemas.py`. Do not redefine.
- **Does NOT create `backend/ingestion/embedder.py`**: This file does not exist yet. Embedding validation and circuit breaker for the ingestion pipeline are deferred to spec-06, which will create `backend/ingestion/embedder.py`.
- **Does NOT re-wire ConversationGraph**: `verify_groundedness` and `validate_citations` are already wired in `conversation_graph.py` (they exist as Phase 2 stubs). Implement the bodies only.
- **Does NOT change `HybridSearcher`**: The circuit breaker in `backend/retrieval/searcher.py` is complete (spec-03 C1). This spec standardizes the same pattern in `qdrant_client.py`.

---

## Component Overview

This spec implements five active subsystems that eliminate the most common RAG failure modes: confident wrong answers, phantom citations, wasted retrieval effort, corrupt index vectors (deferred to spec-06), and cascading service failures.

1. **Grounded Answer Verification (GAV)** — Implement the Phase 2 stub `verify_groundedness` node
2. **Citation-Chunk Alignment Validation** — Implement the Phase 2 stub `validate_citations` node
3. **GAV Confidence Adjustment** — Apply `GroundednessResult.confidence_adjustment` to update `ConversationState.confidence_score`
4. **Query-Adaptive Retrieval Depth** — Apply `complexity_tier` from `QueryAnalysis` to dynamically set retrieval parameters
5. **Circuit Breaker Extension** — Standardize the HybridSearcher pattern in `qdrant_client.py`

---

## Technical Approach

### GAV (Grounded Answer Verification)
- Implement the body of `verify_groundedness` in `backend/agent/nodes.py` (replacing the Phase 2 stub)
- Uses a separate low-temperature LLM call with structured output (`GroundednessResult`)
- Reads `state["final_response"]`, `state["sub_answers"]`, `state["citations"]`
- Applies `[unverified]` annotations and removes contradicted claims from `final_response`
- Applies `confidence_adjustment` multiplier to produce `state["confidence_score"]` (int 0-100)
- When `groundedness_check_enabled=False`: return `{"groundedness_result": None}` immediately (no-op)

### Citation-Chunk Alignment
- Implement the body of `validate_citations` in `backend/agent/nodes.py` (replacing the Phase 2 stub)
- Reuses the existing cross-encoder reranker (`backend/retrieval/reranker.py`) — no new model loaded
- Scores each `(claim_text, chunk_text)` pair against `CITATION_ALIGNMENT_THRESHOLD` (from Settings)
- Remaps low-scoring citations to the highest-scoring chunk; strips if no chunk clears the threshold
- On reranker failure: pass citations through unchanged (graceful degradation)

### GAV Confidence Adjustment
- Computed inside `verify_groundedness` after obtaining `GroundednessResult`
- `raw_confidence` = mean of `sub_answer.confidence_score` for all sub-answers (int 0-100)
- `adjusted = int(raw_confidence * groundedness_result.confidence_adjustment)`
- Clamped to `[0, 100]`, stored in `state["confidence_score"]`

### Query-Adaptive Retrieval Depth
- The `rewrite_query` node already classifies `complexity_tier` via LLM structured output
- New: apply `TIER_PARAMS` lookup after classification to set dynamic retrieval parameters
- These parameters override the global defaults from Settings for the current request
- Pass via ResearchGraph invocation config (not mutating global state)

### Circuit Breaker Extension
- Pattern already implemented in `HybridSearcher._check_circuit/_record_success/_record_failure`
- Implement the same pattern in `backend/storage/qdrant_client.py` for all Qdrant CRUD operations
- One circuit per service (one for Qdrant, independently from the HybridSearcher's circuit)
- Configuration from Settings: `circuit_breaker_failure_threshold=5`, `circuit_breaker_cooldown_secs=30`
- On circuit open: raise immediately rather than forwarding the request

---

## File Structure

```
backend/
  agent/
    nodes.py              # verify_groundedness (GAV impl), validate_citations (impl), rewrite_query (tier params)
    prompts.py            # VERIFY_PROMPT (new), FORMAT_RESPONSE_SYSTEM (update for groundedness annotations)
    schemas.py            # ClaimVerification, GroundednessResult, QueryAnalysis — ALREADY EXIST; do not redefine
    confidence.py         # compute_confidence() — ALREADY IMPLEMENTED (spec-03 R8); do not modify
    research_nodes.py     # collect_answer() — ALREADY IMPLEMENTED; confidence_adjustment applied in nodes.py GAV
    conversation_graph.py # Graph wiring — ALREADY DONE; stubs in place; no changes needed
  retrieval/
    reranker.py           # CrossEncoder — ALREADY EXISTS; reused for citation alignment scoring
  storage/
    qdrant_client.py      # Add circuit breaker state machine (same pattern as HybridSearcher)
  config.py               # All accuracy/robustness fields ALREADY EXIST; no new fields needed
  # NOTE: backend/ingestion/embedder.py does NOT exist — created by spec-06
tests/
  unit/
    test_accuracy_nodes.py        # GAV, citation alignment, tier params, circuit breaker
  integration/
    test_accuracy_integration.py  # End-to-end GAV flow, citation flow, adaptive depth propagation
```

---

## Implementation Steps

1. **Implement circuit breaker in `qdrant_client.py`** (A1): Add `_circuit_open`, `_failure_count`, `_max_failures`, `_cooldown_secs` state. Implement `_check_circuit()`, `_record_success()`, `_record_failure()` methods following the `HybridSearcher` pattern. Wrap all Qdrant HTTP calls.

2. **Implement query-adaptive depth in `rewrite_query`** (A2): Add `TIER_PARAMS` lookup table constant. After LLM structured output returns `QueryAnalysis`, extract `complexity_tier` and apply tier-specific `top_k`, `max_iterations`, `max_tool_calls`, `confidence_threshold` to the request context for downstream ResearchGraph invocation.

3. **Implement `verify_groundedness` node body** (A3): Replace the Phase 2 stub. Create low-temperature LLM call with `with_structured_output(GroundednessResult)`. Apply claim annotations to `final_response`. Apply `confidence_adjustment` to produce `confidence_score`. Handle `groundedness_check_enabled=False` by returning no-op. Handle LLM call failure by returning `{"groundedness_result": None}` (existing graceful degradation pattern).

4. **Implement `validate_citations` node body** (A4): Replace the Phase 2 stub. Use `reranker.model.rank()` to score each `(claim, chunk)` pair. Iterate citations; remap low-scorers to best available chunk or strip. Handle reranker failure by passing citations through unchanged.

5. **Add `VERIFY_PROMPT` and wire `groundedness_check_enabled` flag** (A5): Add prompt constant to `backend/agent/prompts.py`. Wire the `groundedness_check_enabled` config flag into `verify_groundedness` early-return path. Confirm `format_response` reads `groundedness_result` and `confidence_score` from state correctly.

6. **Write unit tests** (A6): Tests for circuit breaker state transitions (closed → open → half-open → closed), tier parameter mapping (all 5 tiers), citation threshold logic (remap vs strip), confidence adjustment arithmetic, and `groundedness_check_enabled=False` short-circuit.

7. **Write integration tests** (A7): End-to-end `verify_groundedness` with mock LLM returning a `GroundednessResult`. End-to-end `validate_citations` with mock reranker returning scores above and below threshold. Query tier classification → retrieval parameter propagation through ResearchGraph.

8. **Run all tests via external runner** (Orchestrator): After Wave 4 completes, launch the external test runner and poll for results. Do not run pytest inside Claude Code.

---

## Integration Points

- **ConversationGraph** (spec-02): `verify_groundedness` and `validate_citations` stubs already wired between `aggregate_answers` and `format_response`. Only node bodies change.
- **ResearchGraph** (spec-03): `confidence_score` (float 0.0-1.0) already computed in `collect_answer` via `compute_confidence()` in `confidence.py`. GAV reads `sub_answers[*].confidence_score` (int 0-100) for the ConversationState adjustment.
- **MetaReasoningGraph** (spec-04): Triggered when `confidence < CONFIDENCE_THRESHOLD` after ResearchGraph iterations; GAV confidence adjustment only affects the ConversationState score (user-facing), not the ResearchState score that drives MetaReasoning.
- **Retrieval Layer** (spec-03): `backend/retrieval/reranker.py` (CrossEncoder) is shared between retrieval reranking and citation alignment — no new model dependency.
- **Storage** (spec-07): Circuit breaker wraps all `qdrant_client.py` calls. Qdrant unavailability returns error to chat endpoint; upsert buffering deferred to spec-06 ingestion pipeline.
- **API** (spec-08): SSE events emit `confidence` score and `groundedness` summary counts (supported/unsupported/contradicted). Chat endpoint propagates circuit breaker errors as informative messages.
- **Ingestion Pipeline** (spec-06): Embedding validation (`validate_embedding`) and ingestion circuit breaker are deferred to spec-06, which creates `backend/ingestion/embedder.py`.

---

## Key Code Patterns

### TIER_PARAMS Lookup Table
```python
TIER_PARAMS: dict[str, dict] = {
    "factoid":    {"top_k": 5,  "max_iterations": 3,  "max_tool_calls": 3, "confidence_threshold": 0.7},
    "lookup":     {"top_k": 10, "max_iterations": 5,  "max_tool_calls": 5, "confidence_threshold": 0.6},
    "comparison": {"top_k": 15, "max_iterations": 7,  "max_tool_calls": 6, "confidence_threshold": 0.55},
    "analytical": {"top_k": 25, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.5},
    "multi_hop":  {"top_k": 30, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.45},
}
```

### Circuit Breaker Pattern (follow HybridSearcher in `backend/retrieval/searcher.py`)
```python
class QdrantCircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown_secs: int = 30):
        self._circuit_open: bool = False
        self._failure_count: int = 0
        self._last_failure_time: float | None = None
        self._max_failures: int = failure_threshold
        self._cooldown_secs: int = cooldown_secs

    def _check_circuit(self) -> None:
        """Raise CircuitOpenError if circuit is open and cooldown has not elapsed."""
        ...

    def _record_success(self) -> None: ...
    def _record_failure(self) -> None: ...
```

### GAV Confidence Adjustment Pattern
```python
# In verify_groundedness node, after obtaining groundedness_result:
raw_confidence = int(
    sum(sa.confidence_score for sa in state["sub_answers"]) / max(1, len(state["sub_answers"]))
)
adjusted = int(raw_confidence * groundedness_result.confidence_adjustment)
adjusted = max(0, min(100, adjusted))
return {
    "groundedness_result": groundedness_result,
    "confidence_score": adjusted,
    "final_response": annotated_response,
}
```

### External Test Runner (use for ALL test execution)
```zsh
# Wave 4 — launch tests (returns immediately)
zsh scripts/run-tests-external.sh -n spec05-final tests/

# Poll
cat Docs/Tests/spec05-final.status

# Read summary
cat Docs/Tests/spec05-final.summary
```

---

## Phase Assignment

- **Phase 1 (implement first)**: Circuit breaker extension (`qdrant_client.py`), query-adaptive retrieval depth (`rewrite_query` tier params). These are infrastructure improvements with no LLM dependency.
- **Phase 2 (implement after Phase 1 gates pass)**: GAV node implementation, citation-chunk alignment validation, GAV confidence adjustment wiring.
- **Deferred to spec-06**: Embedding integrity validation (`validate_embedding`), ingestion circuit breaker, in-memory upsert buffering — all require `backend/ingestion/embedder.py` which spec-06 creates.
