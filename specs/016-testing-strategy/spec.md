# Feature Specification: Testing Strategy

**Feature Branch**: `016-testing-strategy`
**Created**: 2026-03-18
**Status**: Draft
**Input**: Testing infrastructure gap-fill — shared fixtures, missing unit tests, backend E2E tier, real-service integration tests, and sample fixture files.

## Clarifications

### Session 2026-03-18

- Q: When Docker is unavailable, should Qdrant container tests auto-skip, fail hard, or fall back to mocks? → A: Auto-skip via `@pytest.mark.require_docker` when Docker is not available.
- Q: When an E2E test assertion fails mid-scenario, should created collections/data be cleaned up or left for post-mortem? → A: Always clean up via fixture teardown, even on assertion failure.
- Q: Should the 80% coverage target be a hard gate (non-zero exit) or a warning-only report? → A: Hard gate — test run exits non-zero if coverage drops below 80%.
- Q: Should `tests/fixtures/sample.pdf` be a committed binary in git or generated/downloaded at test time? → A: Committed as a binary in git.
- Q: Should the unit suite support parallel execution (pytest-xdist)? → A: Single-process only — no parallel execution requirement.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Shared Test Fixtures (Priority: P1)

A developer writing a new test for any backend module should be able to import a standard set of shared fixtures — an in-memory database, sample document chunks, a mock language model, and pre-built search results — without copying boilerplate from another test file. Today, `tests/integration/conftest.py` only provides a `unique_name()` helper; there is no top-level `tests/conftest.py`.

**Why this priority**: Every other spec-16 story depends on a working fixture foundation. Without shared fixtures, new tests either duplicate setup logic or are blocked entirely.

**Independent Test**: Can be validated by running the five new unit test files (P2) and confirming each one imports and uses `db`, `sample_chunks`, `mock_llm`, and `mock_qdrant_results` without errors.

**Acceptance Scenarios**:

1. **Given** a developer writes a new unit test, **When** they declare `async def test_foo(db)` in the function signature, **Then** an isolated in-memory database is provided automatically — no file system or production database is touched.
2. **Given** a developer needs representative chunk data, **When** they declare `def test_bar(sample_chunks)`, **Then** a pre-populated list of document chunks is injected without manual construction.
3. **Given** a developer needs to simulate LLM responses, **When** they declare `def test_baz(mock_llm)`, **Then** a deterministic mock is provided that returns predictable structured output for every call.
4. **Given** a developer needs to simulate search results, **When** they declare `def test_qux(mock_qdrant_results)`, **Then** pre-built search result objects with realistic scores and payloads are injected.

---

### User Story 2 - Unit Test Coverage for Missing Modules (Priority: P2)

A developer maintaining any backend module should be able to run the unit test suite and receive feedback for every module, including the five that currently have no test file: `retrieval/reranker.py`, `retrieval/score_normalizer.py`, `storage/chunker.py`, `storage/indexing.py`, and `errors.py`.

**Why this priority**: These modules participate in every search and ingestion path. Without unit tests, regressions in their logic go undetected until integration tests catch them, increasing debugging cost.

**Independent Test**: Can be validated by running `tests/unit/` and confirming that five new test files appear and contribute passing tests with no regressions in the remaining 1405+ existing tests.

**Acceptance Scenarios**:

1. **Given** a code change modifies reranking logic, **When** the unit suite runs, **Then** tests targeting score ordering, top-k truncation, and pair scoring provide immediate signal.
2. **Given** a code change modifies score normalization, **When** the unit suite runs, **Then** tests for per-collection min-max normalization catch arithmetic regressions.
3. **Given** a code change modifies the chunk-text helper, **When** the unit suite runs, **Then** tests for size constraints, breadcrumb prepending, and edge inputs catch regressions.
4. **Given** a code change modifies the index-chunks helper, **When** the unit suite runs, **Then** tests for the end-to-end indexing path catch regressions.
5. **Given** a developer needs to verify the error hierarchy, **When** the unit suite runs, **Then** tests for subclass relationships and exception propagation provide confidence.
6. **Given** the unit suite runs on a stock developer machine, **When** all tests complete, **Then** the wall-clock time for `tests/unit/` is under 30 seconds.

---

### User Story 3 - Backend E2E Tests Against a Running System (Priority: P3)

A developer who has started the backend server locally should be able to run a suite of backend-level end-to-end tests that exercise the full upload → ingest → query → observe flow without a browser. Currently `tests/e2e/` exists but is empty.

**Why this priority**: Unit tests mock all dependencies; Docker integration tests require external services. The backend E2E tier fills the gap for verifying routing, middleware, and streaming behavior in-process, without requiring a running server or Docker dependencies.

**Independent Test**: Can be validated by starting the backend, running `tests/e2e/` with the `@pytest.mark.e2e` marker, and confirming three scenarios produce passing assertions.

**Acceptance Scenarios**:

1. **Given** a running backend and Qdrant, **When** the upload-and-query E2E test runs, **Then** it creates a collection, uploads a document via HTTP, waits for ingestion, submits a chat query, and asserts a non-empty NDJSON response with at least one citation.
2. **Given** a running backend, **When** the collection lifecycle E2E test runs, **Then** it creates, lists, and deletes a collection and asserts correct state transitions at each step.
3. **Given** a running backend and several prior queries, **When** the observability E2E test runs, **Then** it asserts that trace records are accessible via the traces API and that the metrics endpoint returns populated circuit-breaker and latency data.
4. **Given** E2E tests are invoked alongside the normal test suite, **When** the `e2e` marker is not requested, **Then** E2E tests are excluded and do not require a running backend.

---

### User Story 4 - Real-Service Integration Tests (Priority: P4)

A developer who has Docker available should be able to run integration tests that verify the Qdrant client, hybrid search accuracy, and circuit breaker activation against a real Qdrant container — not a mock. Three scenarios currently listed in the integration tier lack corresponding test files.

**Why this priority**: Mock-based tests for Qdrant have historically masked production bugs (circuit breaker state tracking, query API version changes). Real-container tests catch these before merge.

**Independent Test**: Can be validated by starting a Qdrant Docker container and running the three new integration test files in isolation.

**Acceptance Scenarios**:

1. **Given** a live Qdrant container, **When** the Qdrant CRUD integration test runs, **Then** it creates a collection, upserts vectors, queries them, and deletes the collection — all assertions pass against real responses.
2. **Given** a pre-indexed test collection, **When** the hybrid search accuracy integration test runs, **Then** it issues a query for a known-relevant document and asserts the correct result appears in the top-3 ranked results.
3. **Given** a Qdrant instance made unreachable (container stopped or network blocked), **When** the circuit breaker integration test runs, **Then** successive failures trip the breaker, subsequent calls return a `CircuitOpenError` without attempting the network, and the breaker resets after the cool-down period.

---

### User Story 5 - Sample Fixture Files for Document Tests (Priority: P5)

A developer writing ingestion or retrieval tests should be able to use realistic sample documents (PDF, Markdown, plain text) from a shared `tests/fixtures/` directory rather than generating synthetic bytes inline or hard-coding base64 strings.

**Why this priority**: Without shared fixture files, each test that needs a document either creates a throwaway byte string (which may not pass magic-byte validation) or duplicates a fixture across test files.

**Independent Test**: Can be validated by running any ingestion test that imports from `tests/fixtures/` and confirming the file is loaded and processed without error.

**Acceptance Scenarios**:

1. **Given** a developer needs a multi-page PDF, **When** they load `tests/fixtures/sample.pdf`, **Then** the file passes PDF magic-byte validation and yields at least one text chunk when ingested.
2. **Given** a developer needs a Markdown document, **When** they load `tests/fixtures/sample.md`, **Then** the file is parseable and produces at least two paragraphs of text.
3. **Given** a developer needs plain text, **When** they load `tests/fixtures/sample.txt`, **Then** the file is readable and produces at least 100 words of content suitable for chunking.

---

### Edge Cases

- What happens when the in-memory database fixture is used in a test marked `asyncio` but the event loop is already closed between fixtures?
- How does the backend E2E suite behave when the backend is unreachable (wrong port, not started)?
- What happens when the Qdrant container fixture times out during startup in CI? (Tests marked `@pytest.mark.require_docker` skip automatically when Docker is unavailable; fixture startup timeout is a separate concern for Docker-capable environments.)
- How does the circuit-breaker integration test avoid flaky behavior when the cooldown timer is near its boundary?
- What happens if an E2E test leaves a collection behind after a failure — does the next run conflict? (Resolved: fixture teardown always runs, FR-006a.)

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The test suite MUST provide a top-level `tests/conftest.py` supplying at minimum four shared fixtures: `db` (isolated in-memory database), `sample_chunks` (pre-built chunk list), `mock_llm` (deterministic LLM mock), and `mock_qdrant_results` (pre-built search results). The `require_docker` auto-skip mechanism is implemented as a `pytest_runtest_setup` hook, not a fixture.
- **FR-002**: The in-memory database fixture MUST be usable in async tests and MUST NOT touch any file-system database.
- **FR-003**: The test suite MUST include unit test files for `retrieval/reranker`, `retrieval/score_normalizer`, `storage/chunker`, `storage/indexing`, and `errors` — each file covering the module's public interface with at least 5 test cases.
- **FR-004**: The reranker unit tests MUST mock the cross-encoder model rather than loading a real model, keeping test startup under 1 second.
- **FR-005**: The `tests/e2e/` directory MUST contain at least three test files, each marked with `@pytest.mark.e2e`, covering upload-and-query, collection lifecycle, and observability trace verification.
- **FR-006**: Backend E2E tests MUST be excluded from normal unit and integration test runs unless explicitly invoked via the e2e marker.
- **FR-006a**: Backend E2E tests MUST guarantee fixture teardown (deletion of created collections, documents, and any other server-side state) after every test scenario, regardless of whether the test passed or failed.
- **FR-007**: The test suite MUST include three new integration test files: Qdrant CRUD against a real container, hybrid search accuracy, and circuit-breaker activation.
- **FR-008**: The Qdrant container integration tests MUST use a Docker-based container fixture (not a mock), isolated from the production Qdrant instance. These tests MUST be marked with `@pytest.mark.require_docker` and MUST be automatically skipped when Docker is not available on the host machine.
- **FR-009**: Sample fixture files (`sample.pdf`, `sample.md`, `sample.txt`) MUST exist in `tests/fixtures/` and MUST be loadable by ingestion tests without modification. All three files MUST be committed as static binaries/text in the git repository (not generated at test time).
- **FR-010**: The `sample.pdf` fixture MUST pass the PDF magic-byte validation enforced by the ingest API. It MUST be a valid PDF binary (not a renamed text file) and MUST remain under 50 KB to avoid impacting repository clone time.
- **FR-011**: Adding spec-16 tests MUST NOT reduce the total passing count below 1405 (the baseline from spec-15).
- **FR-012**: The unit test suite (`tests/unit/`) MUST complete in under 30 seconds on a developer workstation with a warm virtual environment, running single-process (no parallel workers).
- **FR-013**: Backend line coverage, as measured after spec-16 tests are added, MUST reach >= 80%. The test run MUST exit with a non-zero status code if coverage falls below this threshold (hard gate, not warning-only).

### Key Entities

- **Test Fixture**: A reusable pre-condition object (database, chunk list, mock LLM, sample file) injected into a test to eliminate setup boilerplate.
- **E2E Test**: A test that exercises the full system via FastAPI's in-process ASGI transport (`httpx.AsyncClient(app=app, base_url="http://test")`), verifying routing, middleware, and streaming without requiring a live server port. Distinct from unit tests (which mock all dependencies) and Docker integration tests (which require a real Qdrant container).
- **Integration Test**: A test that requires a real external service (Qdrant on `localhost:6333`), marked `@pytest.mark.require_docker`, and automatically skipped when the service is unavailable.
- **Unit Test**: A test that exercises a single module in isolation with all external dependencies mocked.
- **Fixture File**: A static binary or text file (PDF, Markdown, plain text) stored in `tests/fixtures/` for use as realistic input data.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 1405+ existing tests continue to pass with zero regressions after spec-16 changes are merged.
- **SC-002**: Backend code coverage reaches >= 80% line coverage when the full test suite runs, enforced as a hard gate (non-zero exit on failure).
- **SC-003**: The unit test subset completes in under 30 seconds on any developer workstation with dependencies already installed, running single-process.
- **SC-004**: Every backend module listed in the unit test targets table has a corresponding test file — the five currently missing files are created and contain passing tests.
- **SC-005**: Three backend E2E test files exist under `tests/e2e/`, are marked to be excluded from normal runs, and pass when a live backend is available.
- **SC-006**: Three new integration test files (Qdrant CRUD, hybrid search accuracy, circuit breaker) pass when a Docker environment is available.
- **SC-007**: `tests/conftest.py` exists and all four shared fixtures (`db`, `sample_chunks`, `mock_llm`, `mock_qdrant_results`) are importable and functional in both unit and integration test contexts.
- **SC-008**: All three sample fixture files exist in `tests/fixtures/` as committed git objects, are accepted by ingestion tests without producing parse errors, and `sample.pdf` is under 50 KB.

---

## Assumptions

- Specs 01–15 are complete and their 1405 passing tests are the baseline; spec-16 does not modify any production code.
- The project already has all required test framework packages installed (`pytest`, `pytest-asyncio`, `pytest-cov`, `httpx`).
- Docker is available for the Qdrant container fixture in integration tests; CI environments are assumed to support Docker.
- No additional container management packages are required. Docker availability is detected via a direct socket check to `localhost:6333` (research decision R1); tests marked `@pytest.mark.require_docker` skip automatically when the check fails.
- Frontend vitest and Playwright tests are already passing and are out of scope for spec-16 (they are maintained within the frontend workspace).
- The 39 pre-existing test failures are known and stable; spec-16 does not attempt to fix them.
