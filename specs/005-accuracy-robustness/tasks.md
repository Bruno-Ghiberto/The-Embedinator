# Tasks: Accuracy, Precision & Robustness Enhancements

**Branch**: `005-accuracy-robustness` | **Date**: 2026-03-12 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)
**Input**: Design documents from `specs/005-accuracy-robustness/`

## Format: `[ID] [P?] [Story] Description with file path`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[US#]**: Which user story this task belongs to
- Tests run via `zsh scripts/run-tests-external.sh` — NEVER run pytest inside Claude Code
- Poll: `cat Docs/Tests/<name>.status` | Read: `cat Docs/Tests/<name>.summary`

## Agent Team Wave Assignment (4-wave, 7-agent)

| Agent | Wave | Responsibility | Phases |
|-------|------|----------------|--------|
| A1    | 1+4  | Foundation: VERIFY_PROMPT, test skeletons; Wave 4: validation run | Phase 1, 2, 10 |
| A2    | 2    | `verify_groundedness` node body + US1 tests | Phase 3 |
| A3    | 2    | `validate_citations` node body + US2 tests | Phase 4 |
| A4    | 2    | `TIER_PARAMS` constant + `rewrite_query` extension + US4 tests | Phase 6 |
| A5    | 3    | `QdrantClient` + inference service circuit breakers + CircuitOpenError handling + US6 tests | Phase 8 |
| A6    | 3    | NDJSON metadata frame update + US3 tests | Phase 5 |
| A7    | 3    | Integration tests | Phase 9 |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Audit existing code state and create test file scaffolding

- [ ] T001 Audit `verify_groundedness` and `validate_citations` stub bodies in `backend/agent/nodes.py` — confirm both return `{"groundedness_result": None}` / `{"citations": state["citations"]}` placeholders
- [ ] T002 [P] Audit `ClaimVerification`, `GroundednessResult`, `QueryAnalysis` (incl. `complexity_tier` field) in `backend/agent/schemas.py` — confirm all three exist and DO NOT modify
- [ ] T003 [P] Read `HybridSearcher._check_circuit`, `_record_success`, `_record_failure` in `backend/retrieval/searcher.py` — capture the exact 4-field state machine pattern as reference for Phase 8
- [ ] T004 [P] Create `tests/unit/test_accuracy_nodes.py` with imports, fixture stubs, and `pytest.mark` groupings for US1–US6
- [ ] T005 [P] Create `tests/integration/test_accuracy_integration.py` with imports, fixtures using `unique_name()` helper, and `pytest.mark.integration` grouping

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: `VERIFY_PROMPT` and settings verification that all user stories depend on

**⚠️ CRITICAL**: US1 and US2 nodes cannot be implemented until T006 is complete

- [ ] T006 Add `VERIFY_PROMPT` system prompt constant to `backend/agent/prompts.py` — instructs LLM to extract factual claims from the full answer, classify each as SUPPORTED/UNSUPPORTED/CONTRADICTED against the provided context, and return structured `GroundednessResult` output
- [ ] T007 [P] Verify these Settings fields already exist in `backend/config.py` (DO NOT add): `groundedness_check_enabled`, `citation_alignment_threshold`, `circuit_breaker_failure_threshold`, `circuit_breaker_cooldown_secs`, `retry_max_attempts`, `retry_backoff_initial_secs`

**Checkpoint**: Foundation ready — Wave 2 agents (A2, A3, A4) and Wave 3 agents (A5, A6) can now proceed in parallel

---

## Phase 3: User Story 1 — Grounded Answer Verification (Priority: P1) 🎯 MVP

**Goal**: Implement `verify_groundedness` node body: batch-evaluate claims via structured LLM call, annotate unsupported claims with `[unverified]`, remove contradicted claims, adjust confidence score.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec05-us1 tests/unit/test_accuracy_nodes.py::TestVerifyGroundedness`

**Agent**: A2

### Implementation

- [ ] T008 [P] [US1] Add `_apply_groundedness_annotations(response: str, result: GroundednessResult) -> str` helper in `backend/agent/nodes.py` — appends `[unverified]` to UNSUPPORTED claims, removes CONTRADICTED claims with a brief explanation, and prepends a warning banner when >50% of claims are unsupported
- [ ] T009 [US1] Implement `verify_groundedness` node body in `backend/agent/nodes.py` (replaces Phase 2 stub): (1) guard on `settings.groundedness_check_enabled`; (2) build context string from `state["sub_answers"]`; (3) low-temperature `llm.with_structured_output(GroundednessResult)` call with `VERIFY_PROMPT`; (4) call `_apply_groundedness_annotations`; (5) compute `int(mean(sub_scores) * result.confidence_adjustment)` clamped 0–100; (6) return `{"groundedness_result": result, "confidence_score": adjusted, "final_response": annotated}`; (7) catch all exceptions → return `{"groundedness_result": None}` + log warning

### Tests

- [ ] T010 [US1] Add unit tests for `_apply_groundedness_annotations` in `tests/unit/test_accuracy_nodes.py`: supported claim unchanged, unsupported claim gets `[unverified]`, contradicted claim removed, >50% unsupported triggers warning banner, 0% unsupported no banner
- [ ] T011 [US1] Add unit tests for `verify_groundedness` node in `tests/unit/test_accuracy_nodes.py`: `groundedness_check_enabled=False` → returns None immediately; structured LLM success → annotated response + adjusted confidence; LLM raises exception → graceful degradation returns None; empty sub_answers → confidence=0
- [ ] T012 [US1] Run US1 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us1 --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us1.status` until PASSED

**Checkpoint**: US1 fully functional — `verify_groundedness` node annotates claims and adjusts confidence independently

---

## Phase 4: User Story 2 — Citation-Chunk Alignment Validation (Priority: P2)

**Goal**: Implement `validate_citations` node body: score each citation's claim text against its cited chunk via cross-encoder, remap or strip citations below the alignment threshold.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec05-us2 tests/unit/test_accuracy_nodes.py::TestValidateCitations`

**Agent**: A3

### Implementation

- [ ] T013 [P] [US2] Add `_extract_claim_for_citation(text: str, marker: str) -> str` regex helper in `backend/agent/nodes.py` — splits on sentence boundaries (`(?<=[.!?])\s+`), finds sentence containing `marker` (e.g. `[1]`), falls back to first 200 chars
- [ ] T014 [US2] Implement `validate_citations` node body in `backend/agent/nodes.py` (replaces Phase 2 stub): (1) for each citation in `state["citations"]`, extract claim text via `_extract_claim_for_citation`; (2) batch-score `(claim_text, chunk.text)` pairs via `reranker.model.rank()` (reuse existing `CrossEncoder` from `backend/retrieval/reranker.py`); (3) if score < `settings.citation_alignment_threshold`: remap to highest-scoring chunk that clears threshold, or strip citation entirely if none qualifies; (4) return `{"citations": corrected}`; (5) catch all exceptions → return `{"citations": state["citations"]}` + log warning

### Tests

- [ ] T015 [US2] Add unit tests for `_extract_claim_for_citation` in `tests/unit/test_accuracy_nodes.py`: marker found in middle sentence, marker at sentence start, marker in last sentence, no sentence match → fallback to first 200 chars
- [ ] T016 [US2] Add unit tests for `validate_citations` node in `tests/unit/test_accuracy_nodes.py`: citation scores above threshold → preserved unchanged; citation scores below threshold → remapped to best chunk; no chunk clears threshold → citation stripped; reranker raises exception → pass-through unvalidated
- [ ] T017 [US2] Run US2 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us2 --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us2.status` until PASSED

**Checkpoint**: US2 functional — citations are validated and corrected without blocking response delivery

---

## Phase 5: User Story 3 — Meaningful Confidence Indicator (Priority: P3)

**Goal**: Ensure GAV-adjusted confidence score flows through to the NDJSON metadata frame with an optional `groundedness` summary object matching the contract in `contracts/sse-events.md`.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec05-us3 tests/unit/test_accuracy_nodes.py::TestConfidenceIndicator`

**Agent**: A6

### Implementation

- [ ] T018 [US3] Update NDJSON metadata frame emission in `backend/api/chat.py`: read `groundedness_result` from the final `ConversationState` dict returned by the graph run (key `"groundedness_result"`); serialize it into `{"supported": N, "unsupported": N, "contradicted": N, "overall_grounded": bool}` (or `null` when `groundedness_result is None` or no verifications); include as `"groundedness"` field in the `metadata` NDJSON frame emitted as the last line, alongside existing `confidence`, `citations`, `latency_ms` — note: the `"confidence"` value must use the GAV-adjusted `confidence_score` from `ConversationState`, not the pre-GAV raw score

### Tests

- [ ] T019 [US3] Add unit tests for confidence adjustment formula in `tests/unit/test_accuracy_nodes.py`: `confidence_adjustment=1.0` → score unchanged; `confidence_adjustment=0.7` → score reduced proportionally; `confidence_adjustment=0.0` → score clamped to 0; result clamped to 100 when adjustment would exceed
- [ ] T020 [US3] Add unit test for NDJSON metadata frame structure in `tests/unit/test_accuracy_nodes.py`: with groundedness result → `groundedness` object has all 4 fields; without groundedness result → `groundedness` is `null`; confidence value is GAV-adjusted int 0–100
- [ ] T021 [US3] Run US3 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us3 --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us3.status` until PASSED

**Checkpoint**: US3 functional — confidence indicator reflects GAV adjustment; metadata frame includes groundedness object

---

## Phase 6: User Story 4 — Query-Adaptive Retrieval Depth (Priority: P4)

**Goal**: Add `TIER_PARAMS` module-level dict to `nodes.py` and extend `rewrite_query` to look up tier parameters and include them in the return dict for downstream `Send()` config injection.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec05-us4 tests/unit/test_accuracy_nodes.py::TestTierParams`

**Agent**: A4

### Implementation

- [ ] T022 [US4] Add `TIER_PARAMS: dict[str, dict]` module-level constant to `backend/agent/nodes.py` with exactly 5 entries: `factoid` (top_k=5, max_iterations=3, max_tool_calls=3, confidence_threshold=0.7), `lookup` (top_k=10, max_iterations=5, max_tool_calls=5, confidence_threshold=0.6), `comparison` (top_k=15, max_iterations=7, max_tool_calls=6, confidence_threshold=0.55), `analytical` (top_k=25, max_iterations=10, max_tool_calls=8, confidence_threshold=0.5), `multi_hop` (top_k=30, max_iterations=10, max_tool_calls=8, confidence_threshold=0.45)
- [ ] T023 [US4] Extend `rewrite_query` in `backend/agent/nodes.py`: after `analysis = await structured_llm.ainvoke(...)`, look up `tier_params = TIER_PARAMS[analysis.complexity_tier]` and include `"retrieval_params": tier_params` in the returned state dict — pass via `Send()` config to ResearchGraph fan-out, NOT by adding a new field to `ConversationState` TypedDict

### Tests

- [ ] T024 [US4] Add unit tests for `TIER_PARAMS` and `rewrite_query` tier lookup in `tests/unit/test_accuracy_nodes.py`: all 5 tiers present in dict; `factoid` has the shallowest config (lowest top_k); `multi_hop` has deepest config (highest top_k, lowest confidence_threshold); `rewrite_query` returns `retrieval_params` key populated from `TIER_PARAMS` for all 5 tiers; unrecognised tier raises `KeyError` (LLM Literal enforces valid values upstream)
- [ ] T025 [US4] Run US4 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us4 --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us4.status` until PASSED

**Checkpoint**: US4 functional — tier classification drives retrieval depth independently of other stories

---

## Phase 7: User Story 5 — Embedding Integrity Validation (Priority: P5) ⚠️ DEFERRED

**Status**: DEFERRED to spec-06 — `backend/ingestion/embedder.py` does not exist in this branch. This phase documents the interface contract for spec-06 to implement.

- [ ] T026 [US5] Document `validate_embedding()` interface contract as a new file `specs/005-accuracy-robustness/contracts/embedder-validation.md`: define the 4 validation checks (correct dimension count, no NaN values, non-zero vector, magnitude above threshold), the expected function signature `def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]`, and the skip-and-log behavior per FR-014/FR-015 — this contract is the authoritative input for spec-06 implementors

**Note**: No code changes in this phase. Deferred items tracked in [research.md](./research.md) §Deferred Items.

---

## Phase 8: User Story 6 — Resilience Under External Service Failures (Priority: P6)

**Goal**: Extend `QdrantClient` with the HybridSearcher-pattern circuit breaker (Closed → Open → HalfOpen → Closed) and Tenacity retry decorator on all public methods.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec05-us6 tests/unit/test_accuracy_nodes.py::TestCircuitBreaker`

**Agent**: A5

### Implementation

- [ ] T027 [P] [US6] Add circuit breaker state fields to `QdrantClient.__init__` in `backend/storage/qdrant_client.py`: `self._circuit_open: bool = False`, `self._failure_count: int = 0`, `self._last_failure_time: float | None = None`, `self._max_failures: int = settings.circuit_breaker_failure_threshold`, `self._cooldown_secs: int = settings.circuit_breaker_cooldown_secs`
- [ ] T028 [US6] Implement `_check_circuit(self) -> None` in `QdrantClient` in `backend/storage/qdrant_client.py`: if `_circuit_open` and `time.monotonic() - _last_failure_time < _cooldown_secs` → raise `CircuitOpenError`; if `_circuit_open` and cooldown elapsed → set `_circuit_open = False` (half-open probe — allow one request through)
- [ ] T029 [US6] Implement `_record_success(self)` and `_record_failure(self)` in `QdrantClient` in `backend/storage/qdrant_client.py`: success resets `_failure_count = 0` and `_circuit_open = False`; failure increments `_failure_count`, records `_last_failure_time = time.monotonic()`, sets `_circuit_open = True` when `_failure_count >= _max_failures`
- [ ] T030 [US6] Wrap `create_collection`, `upsert`, `search`, `delete` public methods in `QdrantClient` in `backend/storage/qdrant_client.py` with `self._check_circuit()` guard at start and `self._record_success()` / `self._record_failure()` calls in try/except around the Qdrant client call
- [ ] T031 [US6] Add Tenacity `@retry` decorator to `QdrantClient` public methods in `backend/storage/qdrant_client.py`: `stop=stop_after_attempt(settings.retry_max_attempts)`, `wait=wait_exponential(multiplier=settings.retry_backoff_initial_secs, min=1, max=10) + wait_random(0, 1)` (jitter), `retry=retry_if_exception_type(QdrantException)`, `reraise=True` — ensure `_record_failure` is called only on final failure (not on each retry)

### Tests

- [ ] T032 [US6] Add unit tests for `QdrantClient` circuit breaker state machine in `tests/unit/test_accuracy_nodes.py`: 4 consecutive failures → circuit remains closed; 5 consecutive failures → circuit opens; open circuit rejects immediately without calling Qdrant; 30s cooldown elapsed → one probe request allowed through; probe success → circuit closes and `_failure_count` resets; probe failure → circuit reopens
- [ ] T033 [US6] Add unit tests for Tenacity retry behavior on `QdrantClient` in `tests/unit/test_accuracy_nodes.py`: call succeeds on 2nd attempt → 1 retry; call fails 3 times → reraises after 3rd; `CircuitOpenError` is NOT retried (not `QdrantException`)
- [ ] T034 [US6] Run US6 (Qdrant side) unit tests: `zsh scripts/run-tests-external.sh -n spec05-us6-qdrant --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us6-qdrant.status` until PASSED

### Inference Service Circuit Breaker (FR-017 — inference side) [H1 fix]

- [ ] T044 [US6] Add module-level inference circuit breaker state to `backend/agent/nodes.py`: `_inf_circuit_open: bool = False`, `_inf_failure_count: int = 0`, `_inf_last_failure_time: float | None = None` — implement `_check_inference_circuit()`, `_record_inference_success()`, `_record_inference_failure()` functions following the exact same consecutive-count pattern as `QdrantClient` (see ADR-001); wrap all `llm.ainvoke()` and `llm.with_structured_output(...).ainvoke()` calls in `verify_groundedness`, `rewrite_query`, and `synthesize_response` with `_check_inference_circuit()` guard and success/failure recording
- [ ] T045 [US6] Add unit tests for inference service circuit breaker in `tests/unit/test_accuracy_nodes.py`: 5 consecutive LLM failures → circuit opens; open circuit rejects without calling LLM; cooldown elapsed → probe request allowed; probe success → circuit closes; verify `_check_inference_circuit` raises `CircuitOpenError` consistent with Qdrant CB pattern

### Error Response Handling (FR-019) [H2 fix]

- [ ] T046 [US6] Add `CircuitOpenError` and LLM-unavailable error handling to `backend/api/chat.py` streaming generator: catch `CircuitOpenError` (from either inference or Qdrant circuit) and emit `{"type": "error", "message": "A required service is temporarily unavailable. Please try again in a few seconds.", "code": "circuit_open"}` as NDJSON error frame; catch broad LLM/connection exceptions and emit `{"type": "error", "message": "Unable to process your request. Please retry.", "code": "service_unavailable"}` — in both cases, close the stream cleanly rather than hanging or returning an HTTP 500
- [ ] T047 [US6] Run full US6 unit tests: `zsh scripts/run-tests-external.sh -n spec05-us6 --no-cov tests/unit/test_accuracy_nodes.py` — poll `cat Docs/Tests/spec05-us6.status` until PASSED

**Checkpoint**: US6 functional — both circuit breakers (Qdrant + inference) implemented and tested; error frames emitted to users on circuit-open

---

## Phase 9: Integration Tests

**Purpose**: End-to-end flows validating all stories work together in the full pipeline

**Agent**: A7

- [ ] T035 Add end-to-end GAV flow integration test in `tests/integration/test_accuracy_integration.py`: submit query against test collection where answer includes one supported, one unsupported, one contradicted claim; verify final NDJSON response contains `[unverified]` annotation on unsupported, contradicted claim absent, `groundedness` metadata object has correct counts
- [ ] T036 [P] Add citation alignment integration test in `tests/integration/test_accuracy_integration.py`: insert chunk A (high relevance) and chunk B (irrelevant); generate answer with citation `[1]` mispointing to chunk B; run pipeline; verify citation remapped to chunk A or stripped in response
- [ ] T037 [P] Add query-adaptive retrieval depth integration test in `tests/integration/test_accuracy_integration.py`: submit factoid query and multi_hop query; verify logged `retrieval_params` differ — factoid has lower `top_k` and higher `confidence_threshold` than multi_hop
- [ ] T038 Add circuit breaker integration test in `tests/integration/test_accuracy_integration.py`: mock Qdrant to fail 5 consecutive times; verify `CircuitOpenError` raised on 6th call without Qdrant being contacted; mock recovery → verify next call after cooldown succeeds and circuit closes
- [ ] T039 Run full integration suite: `zsh scripts/run-tests-external.sh -n spec05-integration tests/integration/test_accuracy_integration.py` — poll `cat Docs/Tests/spec05-integration.status` until PASSED

---

## Phase 10: Polish & Cross-Cutting Concerns

**Agent**: A1 (Wave 4 verification pass)

- [ ] T040 Run full test suite including all prior specs: `zsh scripts/run-tests-external.sh -n spec05-full tests/` — poll `cat Docs/Tests/spec05-full.status` until PASSED; read `cat Docs/Tests/spec05-full.summary` and confirm 0 regressions from spec-04 baseline (expected pre-existing failures: `test_config.py::test_default_settings`, 3 conversation graph failures, `test_app_startup`)
- [ ] T041 [P] Run `ruff check .` on all modified files (`backend/agent/nodes.py`, `backend/agent/prompts.py`, `backend/storage/qdrant_client.py`, `backend/api/chat.py`) and fix any style violations before marking phase complete
- [ ] T042 [P] Verify NDJSON metadata frame shape matches `specs/005-accuracy-robustness/contracts/sse-events.md`: confirm `groundedness` field presence, null handling, and `confidence` semantics (GAV-adjusted int 0–100)
- [ ] T043 [P] Validate `specs/005-accuracy-robustness/quickstart.md` code patterns are correct — specifically `verify_groundedness` implementation snippet, `TIER_PARAMS` constant values, and test runner command syntax
- [ ] T048 [P] Add SC-010 performance micro-test in `tests/unit/test_accuracy_nodes.py`: call `validate_citations` with a mocked reranker and 10 citations; assert wall-clock time < 50ms using `time.perf_counter()` — ensures citation validation never blocks the response pipeline (SC-010)
- [ ] T049 [P] Add SC-008 performance micro-test in `tests/unit/test_accuracy_nodes.py`: trigger an open circuit on `QdrantClient` and `_check_inference_circuit`, measure time to raise `CircuitOpenError` via `time.perf_counter()`; assert < 1s (target: < 10ms since no I/O occurs) — ensures circuit-open errors do not cause user-visible hangs (SC-008)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1** (Setup): No dependencies — start immediately
- **Phase 2** (Foundational): Depends on Phase 1 — **BLOCKS** Phase 3, 4, 5 (all need `VERIFY_PROMPT`)
- **Phase 3** (US1): Depends on Phase 2 — can proceed independently once T006 complete
- **Phase 4** (US2): Depends on Phase 2 — can proceed in parallel with Phase 3
- **Phase 5** (US3): Depends on Phase 3 (confidence adjustment lives in `verify_groundedness`)
- **Phase 6** (US4): Depends on Phase 2 only — can run in parallel with Phase 3, 4, 8
- **Phase 7** (US5): No code dependencies — documentation task only
- **Phase 8** (US6): Depends on Phase 2 only — can run in parallel with Phase 3, 4, 6
- **Phase 9** (Integration): Depends on Phases 3, 4, 5, 6, 8 all complete
- **Phase 10** (Polish): Depends on Phase 9

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|------------|-------------------|
| US1 (P1) | Phase 2 | US2, US4, US6 |
| US2 (P2) | Phase 2 | US1, US4, US6 |
| US3 (P3) | US1 (confidence in verify_groundedness) | US2, US4, US6 |
| US4 (P4) | Phase 2 | US1, US2, US3, US6 |
| US5 (P5) | DEFERRED — no code deps | All (doc only) |
| US6 (P6) | Phase 2 | US1, US2, US3, US4 |

### Within Each User Story

- Helper functions (`[P]`) before nodes that use them
- Node implementation before tests
- Unit tests before integration tests
- External test runner checkpoint before advancing to next story

---

## Parallel Execution Examples

### Wave 1 — Agent A1 (Foundation)

```bash
# Sequential (T006 blocks US1, US2):
Task: "Add VERIFY_PROMPT constant to backend/agent/prompts.py"
Task: "Create tests/unit/test_accuracy_nodes.py with imports and fixtures"
Task: "Create tests/integration/test_accuracy_integration.py with imports and fixtures"
```

### Wave 2 — Agents A2, A3, A4 in parallel (after Wave 1)

```bash
# A2 — US1: verify_groundedness
Task: "Add _apply_groundedness_annotations helper in backend/agent/nodes.py"
Task: "Implement verify_groundedness node body in backend/agent/nodes.py"

# A3 — US2: validate_citations (parallel with A2)
Task: "Add _extract_claim_for_citation regex helper in backend/agent/nodes.py"
Task: "Implement validate_citations node body in backend/agent/nodes.py"

# A4 — US4: TIER_PARAMS + rewrite_query (parallel with A2, A3)
Task: "Add TIER_PARAMS dict constant to backend/agent/nodes.py"
Task: "Extend rewrite_query to look up TIER_PARAMS and return retrieval_params"
```

### Wave 3 — Agents A5, A6, A7 in parallel (after Wave 1)

```bash
# A5 — US6: circuit breakers (both sides) + error handling
Task: "Add circuit breaker state fields to QdrantClient.__init__ in backend/storage/qdrant_client.py"
Task: "Implement _check_circuit, _record_success, _record_failure in backend/storage/qdrant_client.py"
Task: "Add inference circuit breaker state + functions to backend/agent/nodes.py"
Task: "Catch CircuitOpenError in backend/api/chat.py, emit NDJSON error frame"

# A6 — US3: NDJSON metadata + confidence tests (after A2 completes US1)
Task: "Update metadata frame in backend/api/chat.py to include groundedness object"

# A7 — Integration tests (after Waves 2 and 3 complete)
Task: "Add end-to-end GAV flow integration test in tests/integration/test_accuracy_integration.py"
Task: "Add citation alignment, tier-params, circuit breaker integration tests"
```

### Wave 4 — Agent A1 (Verification)

```bash
Task: "Run full test suite: zsh scripts/run-tests-external.sh -n spec05-full tests/"
Task: "Run ruff check on all modified files and fix violations"
Task: "Validate NDJSON contract and quickstart.md patterns"
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (T006 — VERIFY_PROMPT)
3. Complete Phase 3: US1 — `verify_groundedness` node
4. **STOP**: Run `zsh scripts/run-tests-external.sh -n spec05-mvp tests/unit/test_accuracy_nodes.py::TestVerifyGroundedness`
5. Validate: Groundedness annotations appear in response, confidence adjusts, failure degrades gracefully

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → GAV functional — test independently
3. Phase 4 (US2) → Citation alignment functional — test independently
4. Phase 5 (US3) → Confidence indicator complete — metadata frame extended
5. Phase 6 (US4) → Adaptive retrieval depth — test independently
6. Phase 8 (US6) → Circuit breaker hardened — test independently
7. Phase 9 → Full integration validated
8. Phase 10 → Regression-clean, style-clean

### Files Modified Summary

| File | Change Type | US |
|------|-------------|-----|
| `backend/agent/prompts.py` | Add `VERIFY_PROMPT` constant | US1 |
| `backend/agent/nodes.py` | Implement 2 stubs + 2 helpers + `TIER_PARAMS` + extend `rewrite_query` + inference circuit breaker | US1, US2, US4, US6 |
| `backend/storage/qdrant_client.py` | Add circuit breaker state machine + retry decorators | US6 |
| `backend/api/chat.py` | Add `groundedness` object to NDJSON metadata frame + catch `CircuitOpenError` and emit error frame | US3, US6 |
| `tests/unit/test_accuracy_nodes.py` | New test file (all unit tests incl. SC-008/SC-010 perf micro-tests) | US1–US6 |
| `tests/integration/test_accuracy_integration.py` | New test file (end-to-end flows) | US1–US6 |

**Files NOT modified** (per plan.md constraints):
- `backend/agent/confidence.py` — spec-03 R8 formula; do not touch
- `backend/agent/schemas.py` — `ClaimVerification`, `GroundednessResult`, `QueryAnalysis` already exist
- `backend/agent/conversation_graph.py` — stubs already wired; no changes needed
- `backend/ingestion/embedder.py` — does not exist; deferred to spec-06

---

## Notes

- `[P]` tasks operate on different files or are independent within a file — safe to run in parallel
- `[US#]` label traces each task back to a user story for acceptance validation
- Each user story has an independent test checkpoint before advancing to the next
- Always use `zsh scripts/run-tests-external.sh` — never `pytest` directly inside Claude Code
- US5 (Embedding Integrity) is DEFERRED — `backend/ingestion/embedder.py` created by spec-06
- Spawn agents with: `"Read your instruction file at Docs/PROMPTS/spec-05-accuracy/agents/<file> FIRST, then execute all assigned tasks."`
