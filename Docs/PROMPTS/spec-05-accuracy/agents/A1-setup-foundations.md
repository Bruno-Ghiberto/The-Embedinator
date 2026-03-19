# Agent: A1-setup-foundations

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 1 + 4

## Mission

**Wave 1**: Audit existing stubs and schemas, create test file scaffolding, add `VERIFY_PROMPT` constant, verify all config settings exist. Ensure all modules are importable before Wave 2 agents begin.

**Wave 4**: Run full regression suite, fix ruff violations, validate NDJSON contract, run performance micro-tests.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-05-accuracy/05-implement.md` -- full code specifications (the authoritative reference)
2. `backend/agent/nodes.py` -- existing stubs for `verify_groundedness` (line 354) and `validate_citations` (line 360)
3. `backend/agent/schemas.py` -- `ClaimVerification`, `GroundednessResult`, `QueryAnalysis` (verify they exist, DO NOT modify)
4. `backend/agent/prompts.py` -- existing prompts (add `VERIFY_PROMPT` constant)
5. `backend/config.py` -- `Settings` class (verify accuracy/robustness fields exist at lines 53-58, DO NOT add)
6. `backend/retrieval/searcher.py` -- `HybridSearcher._check_circuit` pattern (reference for Phase 8 agents)
7. `specs/005-accuracy-robustness/tasks.md` -- task definitions for T001-T007

## Assigned Tasks -- Wave 1

- T001: Audit `verify_groundedness` stub in `backend/agent/nodes.py` (line 354-357) -- confirm it returns `{"groundedness_result": None}` and has signature `async def verify_groundedness(state: ConversationState, *, llm: Any = None) -> dict:`
- T002: [P] Audit `validate_citations` stub in `backend/agent/nodes.py` (line 360-363) -- confirm it returns `{"citations": state["citations"]}` and has signature `async def validate_citations(state: ConversationState, *, reranker: Any = None) -> dict:`
- T003: [P] Audit `ClaimVerification`, `GroundednessResult`, `QueryAnalysis` (including `complexity_tier: Literal[...]` field) in `backend/agent/schemas.py` -- confirm all three exist with correct fields. DO NOT modify.
- T004: [P] Read `HybridSearcher._check_circuit`, `_record_success`, `_record_failure` in `backend/retrieval/searcher.py` -- capture the exact 4-field state machine pattern as reference (document in a brief comment at the top of test scaffolding)
- T005: [P] Create `tests/unit/test_accuracy_nodes.py` with imports, fixture stubs, and `pytest.mark` groupings for test classes: `TestVerifyGroundedness`, `TestValidateCitations`, `TestTierParams`, `TestConfidenceIndicator`, `TestCircuitBreaker`
- T006: [P] Create `tests/integration/test_accuracy_integration.py` with imports, fixtures using `unique_name()` helper pattern, and `pytest.mark.integration` grouping
- T007: Add `VERIFY_PROMPT` system prompt constant to `backend/agent/prompts.py` -- instructs LLM to extract factual claims from the full answer, classify each as SUPPORTED/UNSUPPORTED/CONTRADICTED against the provided context, and return structured `GroundednessResult` output. Must include `{context}` and `{answer}` placeholders. See exact text in `05-implement.md`.

## Assigned Tasks -- Wave 4

- T040: Run full test suite including all prior specs: `zsh scripts/run-tests-external.sh -n spec05-full tests/` -- poll `cat Docs/Tests/spec05-full.status` until PASSED; read `cat Docs/Tests/spec05-full.summary` and confirm 0 regressions from spec-04 baseline (expected pre-existing failures: `test_config.py::test_default_settings`, 3 conversation graph failures, `test_app_startup`)
- T041: [P] Run `ruff check .` on all modified files (`backend/agent/nodes.py`, `backend/agent/prompts.py`, `backend/storage/qdrant_client.py`, `backend/api/chat.py`) and fix any style violations before marking phase complete
- T042: [P] Verify NDJSON metadata frame shape matches `specs/005-accuracy-robustness/contracts/sse-events.md`: confirm `groundedness` field presence, null handling, and `confidence` semantics (GAV-adjusted int 0-100)
- T043: [P] Validate `specs/005-accuracy-robustness/quickstart.md` code patterns are correct (if it exists) -- specifically `verify_groundedness` implementation snippet, `TIER_PARAMS` constant values, and test runner command syntax
- T048: [P] Add SC-010 performance micro-test in `tests/unit/test_accuracy_nodes.py`: call `validate_citations` with a mocked reranker and 10 citations; assert wall-clock time < 50ms using `time.perf_counter()`
- T049: [P] Add SC-008 performance micro-test in `tests/unit/test_accuracy_nodes.py`: trigger an open circuit on `QdrantClientWrapper` and `_check_inference_circuit`, measure time to raise `CircuitOpenError` via `time.perf_counter()`; assert < 1s (target: < 10ms since no I/O occurs)

## Files to Create/Modify

### Wave 1
- CREATE: `tests/unit/test_accuracy_nodes.py` (scaffold with imports + empty test classes)
- CREATE: `tests/integration/test_accuracy_integration.py` (scaffold with imports + fixtures)
- MODIFY: `backend/agent/prompts.py` (add `VERIFY_PROMPT`)

### Wave 4
- MODIFY: `tests/unit/test_accuracy_nodes.py` (add perf micro-tests T048, T049)

## Key Patterns

- Test file imports: `from backend.agent.nodes import verify_groundedness, validate_citations, TIER_PARAMS, _apply_groundedness_annotations, _extract_claim_for_citation`
- Test file imports: `from backend.agent.schemas import ClaimVerification, GroundednessResult, QueryAnalysis, SubAnswer, Citation, RetrievedChunk`
- Test classes: group by user story (`TestVerifyGroundedness`, `TestValidateCitations`, etc.)
- Use `@pytest.mark.asyncio` for async node tests
- Use `from unittest.mock import AsyncMock, MagicMock, patch` for mocks
- `VERIFY_PROMPT` must use exact `{context}` and `{answer}` placeholders
- `VERIFY_PROMPT` must instruct the LLM to return structured `GroundednessResult` output with per-claim verdicts, `overall_grounded`, and `confidence_adjustment`
- Perf tests use `time.perf_counter()` for wall-clock measurement

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `schemas.py`, `state.py`, `config.py`, `confidence.py`, or `conversation_graph.py`
- Settings fields at `config.py:53-58` already exist -- do NOT re-add them
- `VERIFY_PROMPT` is a NEW constant. There is already a `VERIFY_GROUNDEDNESS_SYSTEM` constant -- they are DIFFERENT. Add `VERIFY_PROMPT` as a separate constant.
- Test scaffolding files should have empty test methods or `pass` bodies -- Wave 2/3 agents fill in the test implementations
- The integration test file should import the `unique_name()` helper pattern used in `tests/integration/test_research_graph.py` (if it exists)

## Checkpoint -- Wave 1

All files created, prompt added, audits complete. Running all of these succeeds:
```bash
python -c "from backend.agent.prompts import VERIFY_PROMPT; print('VERIFY_PROMPT OK:', len(VERIFY_PROMPT))"
python -c "from backend.agent.schemas import ClaimVerification, GroundednessResult, QueryAnalysis; print('schemas OK')"
python -c "from backend.config import settings; print('CB threshold:', settings.circuit_breaker_failure_threshold, 'cooldown:', settings.circuit_breaker_cooldown_secs)"
python -c "import tests.unit.test_accuracy_nodes; print('unit tests OK')"
python -c "import tests.integration.test_accuracy_integration; print('integration tests OK')"
ruff check .
```

## Checkpoint -- Wave 4

Full regression passes with 0 new failures. Ruff clean. NDJSON contract validated.
```bash
cat Docs/Tests/spec05-full.status   # PASSED
cat Docs/Tests/spec05-full.summary  # 0 regressions
ruff check .
```
