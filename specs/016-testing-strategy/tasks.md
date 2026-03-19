# Tasks: Testing Strategy

**Input**: Design documents from `/specs/016-testing-strategy/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Agent Teams**: 5-wave implementation — Wave 1 (A1/Opus), Wave 2 (A2+A3/Sonnet parallel), Wave 3 (A4+A5/Sonnet parallel), Wave 4 (A6/Sonnet), Wave 5 (A7/Sonnet)

**Test Runner Rule**: ALL agents MUST use `zsh scripts/run-tests-external.sh -n <name> <target>`. NEVER run pytest directly.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story (US1–US5 from spec.md)
- No story label = Setup or foundational task

---

## Phase 1: Setup (Scaffold & Baseline)

**Purpose**: Establish directory structure, verify baseline, create agent instruction files. All of Wave 1 (A1).

**⚠️ CRITICAL**: No user story work can begin until A1 confirms baseline passing.

- [x] T001 Run baseline test suite and record exact passing count in `Docs/Tests/spec16-baseline.summary` — `zsh scripts/run-tests-external.sh -n spec16-baseline --no-cov tests/`
- [x] T002 Verify the 5 production modules exist at exact paths: `backend/retrieval/reranker.py` (class `Reranker`), `backend/retrieval/score_normalizer.py` (function `normalize_scores`), `backend/storage/chunker.py` (function `chunk_text`), `backend/storage/indexing.py` (async function `index_chunks`), `backend/errors.py` (class `EmbeddinatorError` + 10 subclasses)
- [x] T003 Verify `tests/e2e/` directory exists (it already exists but is empty per spec); if absent, create it with `mkdir -p tests/e2e/`
- [x] T004 Create `tests/fixtures/` directory (does not exist)
- [x] T005 Create agent instruction files `Docs/PROMPTS/spec-16-testing/agents/a2-instructions.md` through `a7-instructions.md` with assigned tasks, the mandatory test runner rule, and gate conditions per the plan

**Checkpoint**: Baseline count confirmed; directories created; instruction files ready for Wave 2+

---

## Phase 2: Foundational (US1 — Shared Fixtures)

**Purpose**: `tests/conftest.py` and `pytest.ini` — prerequisite for all other user stories. Still Wave 1 (A1).

**Goal (US1)**: A developer writing any test can import `db`, `sample_chunks`, `mock_llm`, and `mock_qdrant_results` from the shared conftest without boilerplate.

**Independent Test**: Run `zsh scripts/run-tests-external.sh -n spec16-after-scaffold --no-cov tests/unit/` — must pass with same count as baseline (no regressions from conftest.py being added).

- [x] T006 [US1] Create `tests/conftest.py` with `_is_docker_qdrant_available()` socket check, `pytest_configure()` marker registration (`e2e`, `require_docker`), `pytest_runtest_setup()` auto-skip hook, and `db` fixture (`SQLiteDB(":memory:")` + `await instance.connect()` + `yield` + `await instance.close()`)
- [x] T007 [US1] Add `sample_chunks` fixture to `tests/conftest.py` returning `list[RetrievedChunk]` with 3 items (scores 0.92, 0.78, 0.65) using `from backend.agent.schemas import RetrievedChunk`
- [x] T008 [US1] Add `mock_llm` fixture to `tests/conftest.py` returning `MagicMock` with `ainvoke=AsyncMock(return_value=AIMessage("This is a test answer."))`, `with_structured_output=MagicMock(return_value=self)`, and `astream=AsyncMock`
- [x] T009 [US1] Add `mock_qdrant_results` fixture to `tests/conftest.py` returning `list[dict]` with 2 results (scores 0.92, 0.78) in raw Qdrant shape
- [x] T010 [US1] Create `pytest.ini` at project root with `asyncio_mode = auto`, `markers = e2e: ... / require_docker: ...`, and `addopts = --cov=backend --cov-report=term-missing --cov-fail-under=80`
- [x] T011 [US1] Run post-scaffold verification: `zsh scripts/run-tests-external.sh -n spec16-scaffold --no-cov tests/unit/` — confirm PASSED with same count as T001 baseline

**Checkpoint (Gate for Wave 2)**: `spec16-scaffold.status` = PASSED. conftest.py and pytest.ini in place.

---

## Phase 3: User Story 2 — Unit Test Coverage for Missing Modules

**Purpose**: 5 new unit test files covering production modules with zero current coverage. Wave 2 (A2 + A3 in parallel).

**Goal (US2)**: Running `tests/unit/` gives immediate signal for changes to Reranker, normalize_scores, chunk_text, index_chunks, and EmbeddinatorError.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec16-us2 --no-cov tests/unit/test_reranker.py tests/unit/test_score_normalizer.py tests/unit/test_storage_chunker.py tests/unit/test_storage_indexing.py tests/unit/test_errors.py` — all PASSED.

### A2 — 3 unit test files (parallel with A3)

- [x] T012 [P] [US2] Create `tests/unit/test_reranker.py` — import `from backend.retrieval.reranker import Reranker`; mock the cross-encoder model via `unittest.mock.patch` (do NOT load real sentence_transformers weights); test: instantiation with Settings, `rerank()` calls underlying model, `RerankerError` raised when model unavailable, graceful top_k truncation (≥5 tests)
- [x] T013 [P] [US2] Create `tests/unit/test_score_normalizer.py` — import `from backend.retrieval.score_normalizer import normalize_scores`; NOTE: this is a **function**, not a class — do NOT instantiate; the function normalizes `chunk.dense_score` (not a `.score` field — that doesn't exist); test: empty list → empty list, single item → unchanged, all-equal `dense_score` → range=0 so unchanged, min `dense_score` maps to 0.0 and max to 1.0, ordering of chunks preserved (≥5 tests)
- [x] T014 [P] [US2] Create `tests/unit/test_storage_chunker.py` — import `from backend.storage.chunker import chunk_text`; NOTE: function, not class; test: empty string → empty list, short text below chunk_size → single chunk, long text → multiple chunks, no chunk exceeds max_size, overlap parameter respected (≥5 tests)

### A3 — 2 unit test files (parallel with A2)

- [x] T015 [P] [US2] Create `tests/unit/test_storage_indexing.py` — import `from backend.storage.indexing import index_chunks`; mock `app.state.db` and `app.state.qdrant`; test: calls `db.create_parent_chunk()` per chunk, calls `qdrant.batch_upsert()` with correct vectors, empty chunk list handled gracefully, storage errors propagated (≥5 tests)
- [x] T016 [P] [US2] Create `tests/unit/test_errors.py` — import all 11 classes from `backend.errors` (`EmbeddinatorError`, `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError`); NOTE: do NOT test `ProviderRateLimitError` (lives in `backend/providers/base.py`); test: all subclasses inherit from `EmbeddinatorError`, each can be raised and caught as base, each has string representation, `EmbeddinatorError` is an `Exception` (≥6 tests)

### A2 + A3 Gate Runs

- [x] T017 [P] [US2] A2 gate run: `zsh scripts/run-tests-external.sh -n spec16-a2 --no-cov tests/unit/test_reranker.py tests/unit/test_score_normalizer.py tests/unit/test_storage_chunker.py` — confirm PASSED before marking A2 complete
- [x] T018 [P] [US2] A3 gate run: `zsh scripts/run-tests-external.sh -n spec16-a3 --no-cov tests/unit/test_storage_indexing.py tests/unit/test_errors.py` — confirm PASSED before marking A3 complete

**Checkpoint (Gate for Wave 3)**: `spec16-a2.status` = PASSED AND `spec16-a3.status` = PASSED

---

## Phase 4: User Story 3 — Backend E2E Tests

**Purpose**: 3 Python pytest E2E tests in `tests/e2e/` exercising the full HTTP path in-process. Wave 3, A4.

**Goal (US3)**: A developer can run `tests/e2e/` against the in-process ASGI app and verify the ingest → chat → collection lifecycle end-to-end.

**Independent Test**: `zsh scripts/run-tests-external.sh -n spec16-e2e --no-cov -m "e2e" tests/e2e/` — all PASSED.

- [x] T019 [US3] Create `tests/e2e/__init__.py` (empty)
- [x] T020 [US3] Create `tests/e2e/test_ingest_e2e.py` — `@pytest.mark.e2e`; use `httpx.AsyncClient(app=app, base_url="http://test")` in a `@pytest_asyncio.fixture` with `try/finally` teardown; test: POST to `/api/ingest`, poll job status endpoint until terminal state, verify document appears in `/api/documents`
- [x] T021 [US3] Create `tests/e2e/test_chat_e2e.py` — `@pytest.mark.e2e`; mock LLM and Qdrant dependencies; test: POST to `/api/chat`, collect NDJSON stream lines, assert `retrieval_complete`, `answer_chunk`, and `done` event types appear in correct order
- [x] T022 [US3] Create `tests/e2e/test_collection_e2e.py` — `@pytest.mark.e2e`; test: POST `/api/collections` creates collection, GET returns it, DELETE removes it, subsequent GET returns 404
- [x] T022b [US3] Create `tests/e2e/test_observability_e2e.py` — `@pytest.mark.e2e`; use in-process ASGI client; pre-seed at least one trace by posting to `/api/chat` (mock LLM and Qdrant); test: GET `/api/traces` returns a list with ≥1 entry, GET `/api/metrics` returns populated `circuit_breaker` and `latency_p99` fields; fixture teardown in `try/finally` (verifies FR-005 + US3 acceptance scenario 3)
- [x] T023 [US3] A4 gate run: `zsh scripts/run-tests-external.sh -n spec16-a4 --no-cov -m "e2e" tests/e2e/` — confirm PASSED; also run `zsh scripts/run-tests-external.sh -n spec16-no-regression-a4 --no-cov tests/unit/` to confirm 0 new failures

**Checkpoint**: `spec16-a4.status` = PASSED

---

## Phase 5: User Story 4 — Real-Service Integration Tests

**Purpose**: 3 new integration test files requiring a live Qdrant on `localhost:6333`. Wave 3, A5 (parallel with A4).

**Goal (US4)**: A developer with Docker running can verify Qdrant CRUD, hybrid search accuracy, and circuit breaker behavior against real I/O.

**Independent Test**: With Qdrant stopped, `zsh scripts/run-tests-external.sh -n spec16-docker-skip --no-cov tests/integration/test_qdrant_integration.py` shows all tests as **skipped** (not failed).

- [x] T024 [P] [US4] Create `tests/integration/test_qdrant_integration.py` — all functions marked `@pytest.mark.require_docker`; import `from backend.storage.qdrant_client import QdrantStorage`; use `QdrantStorage(host="localhost", port=6333)`; use `unique_name()` from `tests/integration/conftest.py` for collection names; test: `create_collection()`, `batch_upsert()`, `search_hybrid()`, `delete_collection()`; fixture teardown always deletes test collections
- [x] T025 [P] [US4] Create `tests/integration/test_hybrid_search.py` — all functions marked `@pytest.mark.require_docker`; import `from backend.retrieval.searcher import HybridSearcher`; seed Qdrant with known vectors; test: dense-only mode, sparse-only mode, hybrid mode, correct ranking (known-relevant doc in top-3)
- [x] T026 [P] [US4] Create `tests/integration/test_circuit_breaker.py` — all functions marked `@pytest.mark.require_docker`; test: `QdrantStorage._check_circuit()` opens after repeated failures, `CircuitOpenError` raised when circuit is open (import from `backend.errors`), breaker resets after cooldown timeout; NOTE: check `if instance is None` BEFORE `getattr(instance, '_circuit_open', False)` to avoid wrong "closed" state
- [x] T027 [US4] A5 skip-verification run (Qdrant NOT running) — run all 3 Docker test files and confirm each shows skipped (not failed):
  - `zsh scripts/run-tests-external.sh -n spec16-skip-qdrant --no-cov tests/integration/test_qdrant_integration.py`
  - `zsh scripts/run-tests-external.sh -n spec16-skip-hybrid --no-cov tests/integration/test_hybrid_search.py`
  - `zsh scripts/run-tests-external.sh -n spec16-skip-circuit --no-cov tests/integration/test_circuit_breaker.py`
  Confirm all three `.status` files show PASSED (tests skipped cleanly, not errored)

**Checkpoint**: `spec16-skip-qdrant.status` = PASSED AND `spec16-skip-hybrid.status` = PASSED AND `spec16-skip-circuit.status` = PASSED — all 3 Docker test files skip cleanly when Qdrant is unavailable

---

## Phase 6: User Story 5 — Sample Fixture Files

**Purpose**: 3 committed binary/text files in `tests/fixtures/`. Wave 4, A6.

**Goal (US5)**: A developer can load `tests/fixtures/sample.pdf`, `sample.md`, `sample.txt` from any test without generating or downloading at runtime.

**Independent Test**: `(FIXTURES_DIR / "sample.pdf").read_bytes()[:4] == b"%PDF"` passes; all 3 files loadable.

- [x] T028 [US5] Create `tests/fixtures/sample.pdf` — a valid real PDF binary (magic bytes `%PDF-1.x`, readable text content, ≥3 pages, < 50 KB); commit as binary to git; verify it passes `content[:4] == b"%PDF"` check from the ingest security validation
- [x] T029 [US5] Create `tests/fixtures/sample.md` — valid Markdown with ≥1 `##` heading, ≥1 bulleted list, ≥1 fenced code block, ≥2 prose paragraphs; commit as text to git
- [x] T030 [US5] Create `tests/fixtures/sample.txt` — plain UTF-8 text with ≥3 paragraphs and ≥500 words; commit as text to git

**Checkpoint**: All 3 files exist in `tests/fixtures/` and are committed to git

---

## Phase 6b: Coverage Gate Verification

**Purpose**: Confirm `pytest.ini` `--cov-fail-under=80` gate is active. Still Wave 4, A6.

- [x] T031 Verify `pytest.ini` at project root contains `--cov-fail-under=80` in `addopts` (add if A1 omitted); run `zsh scripts/run-tests-external.sh -n spec16-cov tests/unit/` and confirm the summary includes a `TOTAL` coverage line

**Checkpoint (Gate for Wave 5)**: All fixture files committed; `pytest.ini` coverage gate confirmed

---

## Phase 7: Polish & Full Validation

**Purpose**: Full suite validation confirming all SCs pass with 0 regressions. Wave 5, A7.

- [x] T032 Run full suite: `zsh scripts/run-tests-external.sh -n spec16-final tests/` — confirm `spec16-final.status` = PASSED
- [x] T033 Extract test count from `spec16-final.summary` — confirm total passing >= 1405 (baseline from spec-15)
- [x] T034 Extract failure list: `grep "FAILED" Docs/Tests/spec16-final.log` — confirm exactly 39 failures (pre-existing baseline, none new)
- [x] T034b [P] Verify SC-003 / FR-012 unit-suite timing: note wall-clock time before and after `zsh scripts/run-tests-external.sh -n spec16-unit-timing --no-cov tests/unit/` completes; confirm elapsed time is under 30 seconds; include the result in the T038 validation report
- [x] T035 Verify E2E tests explicitly: `zsh scripts/run-tests-external.sh -n spec16-e2e-final --no-cov -m "e2e" tests/e2e/` — confirm PASSED
- [x] T036 Verify Docker tests skip cleanly (Qdrant stopped): `grep "skipped" Docs/Tests/spec16-final.summary` shows require_docker tests as skipped, not failed
- [x] T037 [P] Verify SC-007 coverage gate fires: if coverage < 80%, `spec16-final.status` = FAILED with non-zero exit; if >= 80%, PASSED — report actual percentage in validation report
- [x] T038 [P] Write validation report to `specs/016-testing-strategy/validation-report.md` with: final test count, coverage %, new test breakdown by file (T012–T031), SC-001 through SC-008 pass/fail status, pre-existing failure count

**Checkpoint**: All 8 SCs verified. Spec 16 COMPLETE.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately (Wave 1, A1)
- **Phase 2 (Foundational/US1)**: Depends on Phase 1 T001–T005 — BLOCKS all user story phases
- **Phase 3 (US2)**: Depends on Phase 2 checkpoint — A2 and A3 run in parallel
- **Phase 4 (US3)**: Depends on Phase 2 checkpoint — A4 runs in parallel with A5
- **Phase 5 (US4)**: Depends on Phase 2 checkpoint — A5 runs in parallel with A4
- **Phase 6 (US5)**: Depends on Phase 2 checkpoint — A6 runs after Wave 3 completes
- **Phase 7 (Polish)**: Depends on all Phase 3–6 checkpoints — A7 runs last

### User Story Dependencies

- **US1 (P1)** — Foundational: BLOCKS US2, US3, US4 (they use `db`, `mock_llm` fixtures)
- **US2 (P2)** — Unit tests: Depends only on US1; independent of US3/US4/US5
- **US3 (P3)** — E2E tests: Depends only on US1; independent of US2/US4/US5
- **US4 (P4)** — Integration tests: Depends only on US1; independent of US2/US3/US5
- **US5 (P5)** — Fixture files: Independent of all other stories (no code dependencies)

### Within Each User Story

- US2: T012, T013, T014, T015, T016 all independent — run in parallel (different files)
- US3: T020, T021, T022 sequential within A4 (share app fixture setup pattern)
- US4: T024, T025, T026 independent — run in parallel (different files)
- US5: T028, T029, T030 all independent — run in parallel (different files)

---

## Parallel Execution Examples

### Wave 2: A2 + A3 Parallel

```text
# A2 writes (in parallel):
T012: tests/unit/test_reranker.py
T013: tests/unit/test_score_normalizer.py
T014: tests/unit/test_storage_chunker.py

# A3 writes (in parallel, different files):
T015: tests/unit/test_storage_indexing.py
T016: tests/unit/test_errors.py
```

### Wave 3: A4 + A5 Parallel

```text
# A4 writes (E2E tests, different directory):
T020: tests/e2e/test_ingest_e2e.py
T021: tests/e2e/test_chat_e2e.py
T022: tests/e2e/test_collection_e2e.py
T022b: tests/e2e/test_observability_e2e.py

# A5 writes (integration tests, different files):
T024: tests/integration/test_qdrant_integration.py
T025: tests/integration/test_hybrid_search.py
T026: tests/integration/test_circuit_breaker.py
```

### Within A2 — All 3 files independent

```text
# Can be written in any order, no shared state:
test_reranker.py      (backend/retrieval/reranker.py)
test_score_normalizer.py  (backend/retrieval/score_normalizer.py)
test_storage_chunker.py   (backend/storage/chunker.py)
```

---

## Implementation Strategy

### MVP First (US1 only)

1. Complete Phase 1 (T001–T005): Scaffold
2. Complete Phase 2 (T006–T011): `tests/conftest.py` + `pytest.ini`
3. **STOP and VALIDATE**: `zsh scripts/run-tests-external.sh -n spec16-us1 --no-cov tests/unit/` — must PASS with no regressions
4. All shared fixtures now available for future test development

### Incremental Delivery

1. Phase 1+2 → Fixtures available (MVP)
2. Phase 3 (US2) → 5 missing modules now covered → run unit suite
3. Phase 4+5 (US3+US4 parallel) → E2E + Docker integration coverage → run with markers
4. Phase 6 (US5) → Sample files committed → ingest tests can use realistic PDFs
5. Phase 7 → Full validation, coverage gate, report

### Parallel Team Strategy (Agent Teams)

```
Wave 1 (A1/Opus):   T001–T011 — scaffold + conftest.py + instruction files
     ↓ GATE: spec16-scaffold PASSED
Wave 2 (A2+A3/Sonnet parallel):
  A2: T012–T014, T017
  A3: T015–T016, T018
     ↓ GATE: spec16-a2 + spec16-a3 both PASSED
Wave 3 (A4+A5/Sonnet parallel):
  A4: T019–T023
  A5: T024–T027
     ↓ GATE: spec16-a4 PASSED, spec16-a5-skip shows skips not failures
Wave 4 (A6/Sonnet): T028–T031 — fixture files + coverage gate check
     ↓ GATE: all fixture files committed, pytest.ini confirmed
Wave 5 (A7/Sonnet): T032–T038 — full validation + report
```

---

## Notes

- `[P]` marks tasks writing different files with no shared dependencies — safe to assign to parallel agents
- US1 is foundational — Wave 2/3 agents MUST NOT start until T011 is PASSED
- The 39 pre-existing failures are known; A7 (T034) confirms no new ones appeared
- `--no-cov` flag speeds up development runs; final T032 run MUST use coverage
- Agent instruction files (`a2-instructions.md` through `a7-instructions.md`) are created by A1 in T005 — they are the authoritative task assignments for each wave agent
- All agents must poll `cat Docs/Tests/<name>.status` to check test completion — never block on pytest output
