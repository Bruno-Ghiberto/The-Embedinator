# Tasks: Error Handling

**Input**: Design documents from `/specs/012-error-handling/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Agent Teams**: 4 waves — A1 (audit, Opus) → A2 (handlers, Sonnet) → A3 (tests, Sonnet) → A4 (gate, Sonnet)
**Agent instruction files**: `Docs/PROMPTS/spec-12-errors/agents/`
**Testing**: ALWAYS via `zsh scripts/run-tests-external.sh` — NEVER inside Claude Code

---

## Phase 1: Setup — Pre-Implementation Audit (Wave 1: A1)

**Purpose**: Verify every assumption in 12-plan.md against the live codebase before any code changes. A1 must complete and write a gate report before Wave 2 begins.

**⚠️ GATE**: A1 confirms all T001–T009 findings match the plan. Any discrepancy is logged in the audit report and must be resolved before T011.

- [X] T001 [P] Read `backend/errors.py` via serena and verify exactly 11 classes extend `EmbeddinatorError` directly (list them in audit)
- [X] T002 [P] Read `backend/providers/base.py` and verify `ProviderRateLimitError` extends `Exception` (not `EmbeddinatorError`) with `provider: str` attribute
- [X] T003 [P] Read `backend/agent/schemas.py` and verify `ErrorDetail` has `code: str`, `message: str`, `details: dict = {}` and `ErrorResponse` has `error: ErrorDetail` with NO `trace_id` field
- [X] T004 [P] Read `backend/config.py` `Settings` and verify all 8 required fields exist: `circuit_breaker_failure_threshold`, `circuit_breaker_cooldown_secs`, `retry_max_attempts`, `retry_backoff_initial_secs`, `rate_limit_chat_per_minute`, `rate_limit_ingest_per_minute`, `rate_limit_provider_keys_per_minute`, `rate_limit_general_per_minute`
- [X] T005 [P] Read `backend/main.py` `create_app()` and confirm: (a) current `ProviderRateLimitError` handler returns `{"type": "error", ..., "code": "rate_limit"}`, (b) NO `EmbeddinatorError` handler exists, (c) NO `QdrantConnectionError` handler exists, (d) NO `OllamaConnectionError` handler exists
- [X] T006 [P] Read `backend/middleware.py` `RateLimitMiddleware.dispatch()` and verify it returns `JSONResponse(status_code=429)` with `{"error": {"code": "RATE_LIMIT_EXCEEDED", ...}, "trace_id": ...}` and `Retry-After: 60` header
- [X] T007 [P] Read `backend/api/chat.py` stream error handling and verify three codes used: `NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE` — all with `trace_id`
- [X] T008 [P] Read `backend/storage/qdrant_client.py` and verify `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10) + wait_random(0, 1), reraise=True)` on internal `_*_with_retry` methods
- [X] T009 Write audit report to `Docs/Tests/spec12-a1-audit.md` summarising T001–T008 findings; list any discrepancies from plan; STOP if critical discrepancy found

---

## Phase 2: Foundational — main.py Handler Changes (Wave 2: A2)

**Purpose**: Apply the four exception handler changes to `backend/main.py`. This is foundational — ALL user stories depend on the correct error envelope shape.

**⚠️ GATE**: After T018, run `zsh scripts/run-tests-external.sh -n spec12-a2-smoke tests/unit/test_schemas_api.py` and confirm no pre-existing tests break before proceeding.

- [X] T010 Read `backend/main.py` in full to understand existing handler registration, imports, and line numbers
- [X] T011 Add `from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError` import to `backend/main.py` after existing provider import (if not already present)
- [X] T012 Replace body of existing `rate_limit_handler` in `backend/main.py` (lines ~174–178): change from `{"type": "error", "message": str(exc), "code": "rate_limit"}` to nested envelope with `"PROVIDER_RATE_LIMIT"` code, `exc.provider` in details, and `trace_id = getattr(request.state, "trace_id", "")`
- [X] T013 Add global `EmbeddinatorError` exception handler in `create_app()` in `backend/main.py`: HTTP 500, code `INTERNAL_ERROR`, standard nested envelope with `trace_id`
- [X] T014 Add `QdrantConnectionError` exception handler in `create_app()` in `backend/main.py`: HTTP 503, code `QDRANT_UNAVAILABLE`, standard nested envelope with `trace_id`
- [X] T015 Add `OllamaConnectionError` exception handler in `create_app()` in `backend/main.py`: HTTP 503, code `OLLAMA_UNAVAILABLE`, standard nested envelope with `trace_id`
- [X] T016 Verify handler registration order in `create_app()` in `backend/main.py`: `ProviderRateLimitError` → `QdrantConnectionError` → `OllamaConnectionError` → `EmbeddinatorError` (specific before generic)
- [X] T017 Run pre-existing test suite smoke check via external runner: `zsh scripts/run-tests-external.sh -n spec12-a2-smoke tests/unit/test_schemas_api.py tests/unit/test_middleware_rate_limit.py` and confirm PASSED
- [X] T018 Confirm no regressions from handler changes; if any fail, investigate and fix in `backend/main.py` before proceeding

---

## Phase 3: US1 — Consistent, Actionable Error Responses (Priority: P1) 🎯 MVP

**Goal**: Contract tests prove the error hierarchy, Pydantic models, and config fields match the spec. Integration tests prove all four exception handlers return correct HTTP status codes and the standard nested envelope.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec12-us1 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py` → PASSED

### Contract Tests — tests/unit/test_error_contracts.py

- [X] T019 [US1] Create `tests/unit/test_error_contracts.py` with module docstring and `from __future__ import annotations` guard
- [X] T020 [P] [US1] Add `TestErrorHierarchy` class to `tests/unit/test_error_contracts.py`: `test_all_required_classes_exist`, `test_no_extra_classes_in_errors_module`, `test_root_base_is_exception`, `test_all_subclasses_extend_embedinator_error_directly`, `test_embedinator_error_has_no_custom_init`, `test_exception_classes_are_instantiable_with_string`
- [X] T021 [P] [US1] Add `TestProviderRateLimitError` class to `tests/unit/test_error_contracts.py`: `test_lives_in_providers_base`, `test_extends_exception_not_embedinator_error`, `test_requires_provider_argument`, `test_has_provider_attribute`, `test_str_message_contains_provider_name`
- [X] T022 [P] [US1] Add `TestErrorSchemas` class to `tests/unit/test_error_contracts.py`: verify `ErrorDetail` has `code`, `message`, `details` fields with correct types; verify `ErrorResponse` has `error: ErrorDetail` field and NO `trace_id` field; verify `ErrorDetail(code="X", message="y")` instantiates with `details == {}`
- [X] T023 [US1] Run unit contract tests via external runner: `zsh scripts/run-tests-external.sh -n spec12-unit-contracts tests/unit/test_error_contracts.py`; poll `cat Docs/Tests/spec12-unit-contracts.status`; fix any failures before T024

### Integration Tests — tests/integration/test_error_handlers.py

- [X] T024 [US1] Create `tests/integration/test_error_handlers.py` with module docstring, `from __future__ import annotations`, required imports, and `app_with_handlers` pytest fixture (minimal FastAPI app with all 4 handlers registered and 7 trigger routes)
- [X] T025 [P] [US1] Add `TestProviderRateLimitHandler` class to `tests/integration/test_error_handlers.py`: `test_returns_429`, `test_response_body_uses_nested_envelope`, `test_error_code_is_uppercase`, `test_response_includes_trace_id`, `test_provider_name_in_details`, `test_no_raw_exception_text`
- [X] T026 [P] [US1] Add `TestQdrantConnectionHandler` class to `tests/integration/test_error_handlers.py`: `test_returns_503`, `test_error_code_is_qdrant_unavailable`, `test_uses_nested_envelope`, `test_no_raw_exception_text`
- [X] T027 [P] [US1] Add `TestOllamaConnectionHandler` class to `tests/integration/test_error_handlers.py`: `test_returns_503`, `test_error_code_is_ollama_unavailable`, `test_uses_nested_envelope`
- [X] T028 [US1] Add `TestGlobalEmbeddinatorErrorHandler` class to `tests/integration/test_error_handlers.py`: `test_generic_embedinator_error_returns_500`, `test_sqlite_error_falls_through_to_global_handler`, `test_llm_call_error_falls_through_to_global_handler`, `test_circuit_open_error_falls_through_to_global_handler`, `test_error_code_is_internal_error`, `test_response_uses_nested_envelope`, `test_no_raw_exception_text_in_any_handler`
- [X] T029 [US1] Run integration handler tests via external runner: `zsh scripts/run-tests-external.sh -n spec12-integration-handlers tests/integration/test_error_handlers.py`; poll `cat Docs/Tests/spec12-integration-handlers.status`; fix any failures before T030
- [X] T030 [US1] Run combined US1 gate: `zsh scripts/run-tests-external.sh -n spec12-us1 tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py`; confirm PASSED

**Checkpoint**: US1 complete — every error response shape is validated and every handler returns the standard nested envelope.

---

## Phase 4: US2-US4 — Circuit Breaker, Rate Limit, Streaming (Priority: P2-P4)

**Goal**: Add targeted contract tests that validate the supporting error infrastructure: circuit breaker config fields, rate limit config fields, and stream error code stability.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec12-us2-us4 tests/unit/test_error_contracts.py` → PASSED (with new test classes added)

- [X] T031 [P] [US3] Add `TestCircuitBreakerConfig` class to `tests/unit/test_error_contracts.py`: verify `circuit_breaker_failure_threshold: int = 5`, `circuit_breaker_cooldown_secs: int = 30`, `retry_max_attempts` and `retry_backoff_initial_secs` reserved fields exist and MUST NOT be removed
- [X] T032 [P] [US4] Add `TestRateLimitConfig` class to `tests/unit/test_error_contracts.py`: verify `rate_limit_chat_per_minute = 30`, `rate_limit_ingest_per_minute = 10`, `rate_limit_provider_keys_per_minute = 5`, `rate_limit_general_per_minute = 120`
- [X] T033 [P] [US2] Add `TestStreamErrorCodes` class to `tests/unit/test_error_contracts.py`: search `backend/api/chat.py` source text and verify strings `"NO_COLLECTIONS"`, `"CIRCUIT_OPEN"`, `"SERVICE_UNAVAILABLE"` are present (static code inspection — ensures stream codes are not accidentally renamed; behavioral coverage for stream error emission is inherited from spec-02/03 regression suite)
- [X] T034 [US2] Run updated unit contract tests via external runner: `zsh scripts/run-tests-external.sh -n spec12-us2-us4 tests/unit/test_error_contracts.py`; confirm PASSED with new test classes

**Checkpoint**: Contract tests now cover all 5 user stories.

---

## Phase 5: US5 — Encrypted Provider Key Errors (Priority: P5)

**Goal**: Contract test verifying `KEY_MANAGER_UNAVAILABLE` code is used in the provider key endpoints (not from the spec-12 handlers, but from `api/providers.py`).

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec12-us5 tests/unit/test_error_contracts.py` → PASSED

- [X] T035 [US5] Add `TestProviderKeyErrorCodes` class to `tests/unit/test_error_contracts.py`: search `backend/api/providers.py` source text and verify string `"KEY_MANAGER_UNAVAILABLE"` is present (ensures this code is not accidentally removed or renamed)
- [X] T036 [US5] Run final unit contract tests via external runner: `zsh scripts/run-tests-external.sh -n spec12-us5-final tests/unit/test_error_contracts.py`; confirm all test classes pass

**Checkpoint**: All 5 user stories have contract coverage. Complete `test_error_contracts.py` is validated.

---

## Phase 6: Polish — Full Regression Gate (Wave 4: A4)

**Purpose**: Verify zero regressions against the 1250 existing tests. Identify and fix any tests that asserted the old broken `ProviderRateLimitError` handler format.

- [X] T037 Run full test suite via external runner: `zsh scripts/run-tests-external.sh -n spec12-regression tests/`; poll until PASSED or FAILED
- [X] T038 Read `Docs/Tests/spec12-regression.summary`; verify: (a) all 1250 existing tests still pass, (b) all new spec-12 tests pass, (c) pre-existing 39 failures unchanged, (d) zero new failures
- [X] T039 If regressions found: search tests for `"rate_limit"` (lowercase) or `"type": "error"` assertions against the provider rate limit handler; update any such assertions to match the new nested envelope format with `"PROVIDER_RATE_LIMIT"` code
- [X] T040 Re-run full suite if T039 had fixes: `zsh scripts/run-tests-external.sh -n spec12-regression-final tests/`; confirm PASSED; write final report to `Docs/Tests/spec12-final-report.md` with test counts before/after, new tests added, regressions introduced (target: 0)

**Checkpoint**: Spec-12 complete. All handlers standardised. All contracts locked. Zero regressions.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Audit)**: No dependencies — start immediately with A1
- **Phase 2 (Handlers)**: Depends on Phase 1 gate — BLOCKS all user story phases
- **Phase 3 (US1)**: Depends on Phase 2 completion (handlers must be in place for integration tests)
- **Phase 4 (US2-US4)**: Depends on Phase 3 test file creation (adds classes to existing files)
- **Phase 5 (US5)**: Depends on Phase 4 (adds classes to existing files)
- **Phase 6 (Regression)**: Depends on all test files being complete and passing

### User Story Dependencies

- **US1 (P1)**: Foundational — requires Phase 2 (handlers). All other stories depend on US1.
- **US2 (P2)**: Can use `test_error_contracts.py` after T019 creates the file — parallel with US1 test class additions
- **US3 (P3)**: Same as US2 — parallel test class addition after T019
- **US4 (P4)**: Same as US2 — parallel test class addition after T019
- **US5 (P5)**: Same as US2 — parallel test class addition after T019

### Within Each Phase

- T001–T008: All parallel (read different files)
- T020–T022: All parallel (add different test classes to same file — write sequentially or merge)
- T025–T027: All parallel (add different test classes to same file — write sequentially or merge)
- T031–T033: All parallel (add different test classes)
- T037 → T038 → T039 → T040: Sequential (each depends on previous)

---

## Parallel Execution Examples

```bash
# Phase 1 — A1 can read all files in parallel:
# (All T001-T008 are independent reads of different files)

# Phase 3 — After T019 creates test_error_contracts.py, add all classes:
# T020, T021, T022 target the same file — write sequentially or coordinate

# Phase 3 — After T024 creates test_error_handlers.py, add handler tests:
# T025, T026, T027 target the same file — write sequentially or coordinate

# Phase 4 — After Phase 3 test files exist, add Phase 4 classes in parallel:
# T031 (TestCircuitBreakerConfig), T032 (TestRateLimitConfig), T033 (TestStreamErrorCodes)
```

---

## Implementation Strategy

### MVP First (US1 Only — minimum viable spec-12)

1. Complete Phase 1: Audit (T001–T009)
2. Complete Phase 2: Handlers (T010–T018)
3. Complete Phase 3: US1 tests (T019–T030)
4. **STOP and VALIDATE**: `zsh scripts/run-tests-external.sh -n spec12-us1-mvp tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py` → PASSED
5. All four handlers standardised; error response contract locked for frontend

### Full Delivery

1. Phase 1 → Phase 2 → Phase 3 (US1 MVP above)
2. Phase 4 (T031–T034) — add contract tests for US2-US4
3. Phase 5 (T035–T036) — add US5 contract test
4. Phase 6 (T037–T040) — full regression gate

### Agent Team Strategy

With 4 agents across 4 waves:

1. **A1 (Wave 1)**: Phases 1 — audit and gate report
2. **A2 (Wave 2)**: Phase 2 — all `backend/main.py` handler changes
3. **A3 (Wave 3)**: Phases 3–5 — all new test files and test classes
4. **A4 (Wave 4)**: Phase 6 — regression gate and final report

---

## Notes

- `[P]` tasks = independent target files or non-conflicting sections — verify before parallelising
- `[US1]`–`[US5]` labels map tasks to user stories from `specs/012-error-handling/spec.md`
- **NEVER** create exception classes in `backend/errors.py` (frozen hierarchy)
- **NEVER** create `CircuitBreaker` class or `backend/circuit_breaker.py`
- **NEVER** wire `retry_max_attempts` or `retry_backoff_initial_secs` to tenacity (dead config)
- **NEVER** modify `backend/api/chat.py` (stream error codes already correct)
- **NEVER** add `"type": "error"` format to REST exception handlers (NDJSON stream format only)
- Commit after each phase or logical group using conventional commits: `feat:`, `test:`, `fix:`
- Stop at any checkpoint to validate independently before proceeding
