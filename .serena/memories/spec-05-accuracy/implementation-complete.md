# Spec-05 Accuracy — Implementation Complete

## Status
IMPLEMENTATION COMPLETE — 2026-03-13

## Test Results
- **335 passed**, 5 pre-existing failures (same as spec-04 baseline), 0 regressions
- Pre-existing failures: test_app_startup, 3 conversation graph tests, test_default_settings

## What Was Implemented (49 tasks, 4 waves, 7 agents)

### US1 — Grounded Answer Verification (A2)
- `_apply_groundedness_annotations()` helper in nodes.py
- `verify_groundedness` node: guards, structured LLM call, annotation, GAV-adjusted confidence
- 11 unit tests (TestVerifyGroundedness) all passing

### US2 — Citation Validation (A3)
- `_extract_claim_for_citation()` helper in nodes.py
- `validate_citations` node: cross-encoder scoring, remap/strip, graceful degradation
- 10 unit tests (TestValidateCitations) all passing

### US3 — Confidence Indicator (A6)
- NDJSON metadata frame updated in chat.py to include `groundedness` object (null when GAV disabled)
- GAV-adjusted confidence_score (int 0-100) emitted in metadata frame

### US4 — Tier Params (A4)
- `TIER_PARAMS` dict (5 tiers: factoid/lookup/comparison/analytical/multi_hop) added to nodes.py
- `rewrite_query` extended at all 3 return paths to include `retrieval_params`
- 5 unit tests (TestTierParams) all passing

### US5 — DEFERRED to spec-06
- embedder.py does not exist, correctly not created

### US6 — Circuit Breakers (A5)
- `CircuitOpenError` added to errors.py
- `QdrantClientWrapper` fully refactored: _check_circuit (half-open/cooldown), _record_success, _record_failure, Tenacity retry on inner methods, CB only on final failure
- Inference CB: module-level globals + 3 functions in nodes.py, wraps LLM calls in verify_groundedness
- CircuitOpenError caught in chat.py before generic Exception, emits `{"type":"error","code":"circuit_open"}`
- 14 unit tests (TestCircuitBreaker) all passing

### Integration Tests (A7)
- 17 integration tests across 4 classes (TestGAVIntegration, TestCitationAlignmentIntegration, TestTierParamsIntegration, TestCircuitBreakerIntegration)
- Used MemorySaver() instead of AsyncMock for checkpointer (LangGraph strict validation)

## Files Modified
- `backend/agent/nodes.py` — _apply_groundedness_annotations, verify_groundedness, _extract_claim_for_citation, validate_citations, TIER_PARAMS, rewrite_query extension, inference CB
- `backend/agent/prompts.py` — VERIFY_PROMPT constant added
- `backend/storage/qdrant_client.py` — full CB refactor + Tenacity retry
- `backend/api/chat.py` — groundedness in metadata frame, CircuitOpenError handler
- `backend/errors.py` — CircuitOpenError added
- `tests/unit/test_accuracy_nodes.py` — created (60 tests)
- `tests/integration/test_accuracy_integration.py` — created (17 tests)

## Key Gotchas
- Integration tests must use `MemorySaver()` not `AsyncMock()` for LangGraph checkpointer
- Tenacity retry wraps inner `_*_with_retry` methods; CB recording happens in outer public method (not inside retry)
- `import time` required at nodes.py module level for inference CB
- Wave 2 agents (A2/A3/A4) use local imports in tests to avoid module-level lazy-import interference from parallel agents
