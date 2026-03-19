# Spec 16: Testing — Feature Specification Context

## Feature Description

The Testing Strategy for The Embedinator defines the complete test infrastructure: test framework stack, test pyramid (unit, integration, E2E), directory structure, shared fixtures, mock strategies, and test targets per module. The system uses pytest for all Python backend tests, vitest with @testing-library/react for frontend unit tests, and Playwright for end-to-end browser tests.

Specs 01–15 have already produced 1405 passing tests across unit, integration, and regression tiers. Spec 16 fills the remaining coverage gaps: modules introduced after the original blueprint, missing fixture infrastructure, and the currently empty `tests/e2e/` backend tier.

---

## Current Codebase State

### Backend Module Map (actual paths)

```
backend/
  __init__.py
  config.py
  errors.py                     # EmbeddinatorError hierarchy (10 subclasses)
  main.py                       # App factory, lifespan, structlog configure()
  middleware.py                 # TraceIDMiddleware, RequestLoggingMiddleware, RateLimitMiddleware
  agent/
    answer_generator.py
    citations.py
    confidence.py
    conversation_graph.py
    edges.py
    meta_reasoning_edges.py
    meta_reasoning_graph.py
    meta_reasoning_nodes.py
    nodes.py
    prompts.py
    research_edges.py
    research_graph.py
    research_nodes.py
    retrieval.py
    schemas.py
    state.py
    tools.py
  api/
    chat.py
    collections.py
    documents.py
    health.py
    ingest.py
    models.py
    providers.py
    settings.py
    traces.py
  ingestion/
    chunker.py
    embedder.py
    incremental.py
    pipeline.py
  providers/
    anthropic.py
    base.py
    key_manager.py
    ollama.py
    openai.py
    openrouter.py
    registry.py
  retrieval/
    reranker.py
    score_normalizer.py
    searcher.py
  storage/
    chunker.py                  # chunk_text() helper
    document_parser.py          # parse_document(), _parse_text(), _parse_pdf()
    indexing.py                 # index_chunks() helper
    parent_store.py
    qdrant_client.py            # QdrantClientWrapper + QdrantStorage + data classes
    sqlite_db.py                # SQLiteDB (7 tables, full CRUD)
```

### Actual Test Directory Structure (as of spec 15)

```
tests/
  __init__.py
  mocks.py                           # build_mock_research_graph(), build_simple_chat_graph()
  unit/
    __init__.py
    api/                             # Added in spec-13 for security tests
      __init__.py
      test_chat_security.py
      test_ingest_security.py
      test_metrics.py                # spec-15: MetricsResponse, bucket logic
      test_providers_security.py
      test_traces_stage_timings.py   # spec-14: stage timings in traces API
    retrieval/
      __init__.py
      test_searcher_security.py      # spec-13
    test_accuracy_nodes.py           # spec-05
    test_answer_generator.py
    test_citations.py
    test_chunker.py                  # spec-06 ingestion chunker
    test_component_log_levels.py     # spec-15: structlog filter_by_component
    test_config.py
    test_confidence.py
    test_contracts_agent.py          # spec-11
    test_contracts_cross_cutting.py  # spec-11
    test_contracts_ingestion.py      # spec-11
    test_contracts_providers.py      # spec-11
    test_contracts_retrieval.py      # spec-11
    test_contracts_storage.py        # spec-11
    test_chat_ndjson.py              # spec-08
    test_collections_router.py       # spec-08
    test_document_parser.py
    test_documents_router.py         # spec-08
    test_edges.py
    test_embedder.py                 # spec-06
    test_error_contracts.py          # spec-12
    test_health_router.py            # spec-08
    test_hybrid_searcher.py
    test_incremental.py              # spec-06
    test_ingest_router.py            # spec-08
    test_ingestion_api.py            # spec-08
    test_ingestion_pipeline.py       # spec-06
    test_key_manager.py              # spec-07
    test_main_security.py            # spec-13
    test_meta_reasoning_edges.py     # spec-04
    test_meta_reasoning_nodes.py     # spec-04
    test_middleware_rate_limit.py    # spec-08
    test_models_router.py            # spec-08
    test_ndjson_frames.py            # spec-02
    test_nodes.py
    test_parent_store.py             # spec-07
    test_providers.py
    test_providers_router.py         # spec-08/10
    test_qdrant_storage.py           # spec-07 (imports from backend.storage.qdrant_client)
    test_research_confidence.py      # spec-03
    test_research_edges.py           # spec-03
    test_research_nodes.py           # spec-03
    test_research_tools.py           # spec-03
    test_retrieval.py
    test_schema_migration.py         # spec-07
    test_schemas.py
    test_schemas_api.py              # spec-08
    test_settings_router.py          # spec-08
    test_sqlite_db.py                # spec-07
    test_stage_timings.py            # spec-14: ConversationState/ResearchState fields
    test_stage_timings_db.py         # spec-14: SQLite stage_timings_json column
    test_trace_context.py            # spec-15: structlog contextvars
    test_traces_router.py            # spec-08
  integration/
    __init__.py
    conftest.py                      # unique_name() helper only
    test_accuracy_integration.py     # spec-05
    test_api_integration.py          # spec-08
    test_app_startup.py              # spec-08
    test_concurrent_reads.py         # spec-07
    test_concurrent_streams.py       # spec-08
    test_conversation_graph.py       # spec-02
    test_error_handlers.py           # spec-12
    test_ingestion_pipeline.py       # spec-06
    test_meta_reasoning_graph.py     # spec-04
    test_ndjson_streaming.py         # spec-08
    test_performance.py              # spec-14
    test_providers_integration.py    # spec-10
    test_rate_limiting.py            # spec-08
    test_research_graph.py           # spec-03
    test_schema_validation.py        # spec-07
    test_storage_integration.py      # spec-07
    test_us1_e2e.py                  # spec-08: create collection → upload → query
    test_us3_streaming.py            # spec-08: NDJSON stream parsing
    test_us4_traces.py               # spec-08: trace record creation
  regression/
    __init__.py
    test_regression.py               # spec-07 regression suite (FR/SC checks)
  e2e/                               # Backend-level E2E (currently empty — spec-16 populates)
```

### Frontend Test Structure (actual paths)

```
frontend/
  playwright.config.ts             # testDir: ./tests/e2e, baseURL: http://localhost:3000
  vitest.config.ts                 # environment: jsdom, exclude: e2e, coverage >= 70%
  tests/
    setup.ts
    unit/
      api.test.ts
      components.test.tsx
      hooks.test.ts
    e2e/
      chat.spec.ts
      collections.spec.ts
      documents.spec.ts
      responsive.spec.ts
      settings.spec.ts
      workflow.spec.ts
```

---

## Requirements

### Functional Requirements

1. **Test Pyramid**: Unit tests (fast, isolated, mocked dependencies), integration tests (real services or FastAPI TestClient), E2E tests (browser automation with Playwright).
2. **Python Backend Tests**: Use `pytest` with `pytest-asyncio` for async tests, `pytest-cov` for coverage, and `httpx` / FastAPI `TestClient` for HTTP testing.
3. **Frontend Unit Tests**: Use `vitest` with `@testing-library/react` for component and hook testing. Coverage target: >= 70% lines.
4. **Frontend E2E Tests**: Use `@playwright/test` for full browser automation. Playwright config in `frontend/playwright.config.ts`; tests in `frontend/tests/e2e/`.
5. **Shared Fixtures**: A top-level `tests/conftest.py` providing in-memory SQLite, sample chunk data, mock LLM, mock Qdrant results, and a `qdrant_container` fixture for integration tests.
6. **Coverage Targets**: Backend >= 80% line coverage enforced via `pytest-cov`; frontend >= 70% via `vitest --coverage`.
7. **Test Directory Structure**: New unit tests added at `tests/unit/` (flat) except for grouped subdirs `api/` and `retrieval/` that already exist.

### Non-Functional Requirements

- Unit tests must run in under 30 seconds for the entire suite.
- Integration tests may take longer but must complete in under 5 minutes.
- E2E tests require a running backend and frontend; they are executed separately.
- All SQL operations in unit tests use in-memory SQLite (`:memory:`) for speed.
- Mock LLM must return predictable structured output for deterministic agent tests.

---

## Key Technical Details

### Test Framework Stack

| Layer | Framework | Plugins |
|-------|-----------|---------|
| Python backend (unit + integration) | `pytest` | `pytest-asyncio`, `pytest-cov` |
| Python HTTP tests | `httpx` | FastAPI `TestClient` |
| LangGraph integration | `pytest` + `MemorySaver` | Custom fixtures (not `AsyncMock`) |
| Frontend unit | `vitest` | `@testing-library/react` |
| Frontend E2E | `@playwright/test` | Chromium only (configured in `playwright.config.ts`) |

### Important Implementation Notes

- **SQLiteDB constructor**: `SQLiteDB(db_path: str)` then `await db.connect()` — there is no `initialize()` method. See `tests/unit/test_sqlite_db.py` for the correct pattern.
- **QdrantStorage location**: Both `QdrantClientWrapper` and `QdrantStorage` are in `backend/storage/qdrant_client.py`. Import as `from backend.storage.qdrant_client import QdrantStorage`.
- **mocks.py**: `tests/mocks.py` provides `build_mock_research_graph()` and `build_simple_chat_graph()` — reuse these instead of building new mock graphs.
- **structlog pattern**: All loggers use `structlog.get_logger().bind(component=__name__)` — NOT `structlog.get_logger(__name__)`.
- **LangGraph checkpointer in tests**: Use `MemorySaver()` — never `AsyncMock()` for the checkpointer argument.
- **`data/embedinator.db` schema**: The real DB may have an old schema. All unit/integration tests must use `tmp_path` or `:memory:` SQLite — never the project-level `data/` database.
- **ProviderRegistry class**: Located at `backend/providers/registry.py`, class `ProviderRegistry`. Methods: `initialize()`, `get_active_llm()`, `get_active_langchain_model()`, `get_embedding_provider()`, `set_active_provider()`.
- **Error hierarchy**: `backend/errors.py` defines `EmbeddinatorError` with 10 subclasses including `CircuitOpenError`, `QdrantConnectionError`, `OllamaConnectionError`, `LLMCallError`, `IngestionError`, etc.
- **Middleware**: `backend/middleware.py` contains `TraceIDMiddleware`, `RequestLoggingMiddleware`, `RateLimitMiddleware` — all already covered by existing tests.

### Unit Test Targets (what to test and coverage status)

| Module | Existing Test File | Notes |
|--------|-------------------|-------|
| `backend/agent/nodes.py` | `test_nodes.py` | 30+ tests for all node functions |
| `backend/agent/edges.py` | `test_edges.py` | Routing logic |
| `backend/agent/tools.py` | `test_research_tools.py` | Tool factory tests |
| `backend/agent/schemas.py` | `test_schemas.py` | Pydantic validation |
| `backend/agent/confidence.py` | `test_confidence.py`, `test_research_confidence.py` | Both legacy + spec-03 paths |
| `backend/agent/citations.py` | `test_citations.py` | Citation build, dedup |
| `backend/agent/answer_generator.py` | `test_answer_generator.py` | Stream tokens |
| `backend/agent/retrieval.py` | `test_retrieval.py` | Filter, top_k, empty results |
| `backend/agent/research_nodes.py` | `test_research_nodes.py` | 6 research node functions |
| `backend/agent/research_edges.py` | `test_research_edges.py` | 2 edge functions |
| `backend/agent/meta_reasoning_nodes.py` | `test_meta_reasoning_nodes.py` | 3 strategies |
| `backend/agent/meta_reasoning_edges.py` | `test_meta_reasoning_edges.py` | Routing |
| `backend/agent/state.py` | `test_stage_timings.py`, `test_contracts_agent.py` | State field coverage |
| `backend/ingestion/pipeline.py` | `test_ingestion_pipeline.py` | Mock Rust output |
| `backend/ingestion/embedder.py` | `test_embedder.py` | Batch splitting, retry |
| `backend/ingestion/chunker.py` | `test_chunker.py` | Chunk splitting logic |
| `backend/ingestion/incremental.py` | `test_incremental.py` | Hash + dedup |
| `backend/retrieval/searcher.py` | `test_hybrid_searcher.py` | Hybrid search, circuit breaker |
| `backend/retrieval/reranker.py` | **MISSING** | Score ordering, top-k, pair scoring |
| `backend/retrieval/score_normalizer.py` | `test_hybrid_searcher.py` (partial) | Normalization math |
| `backend/storage/qdrant_client.py` | `test_qdrant_storage.py` | Full CRUD, circuit breaker, retry |
| `backend/storage/sqlite_db.py` | `test_sqlite_db.py` | All 7 tables, full CRUD |
| `backend/storage/parent_store.py` | `test_parent_store.py` | Parent chunk reader |
| `backend/storage/document_parser.py` | `test_document_parser.py` | parse_document(), PDF/text |
| `backend/storage/chunker.py` | **MISSING** | chunk_text() helper; pure logic |
| `backend/storage/indexing.py` | **MISSING** | index_chunks() helper |
| `backend/providers/registry.py` | `test_providers.py`, `test_providers_router.py` | Provider resolution |
| `backend/providers/key_manager.py` | `test_key_manager.py` | Fernet encryption/decryption |
| `backend/middleware.py` | `test_middleware_rate_limit.py` | All 3 middleware classes |
| `backend/errors.py` | `test_error_contracts.py` | Exception hierarchy |
| `backend/config.py` | `test_config.py` | Defaults, env vars |
| `backend/api/chat.py` | `test_chat_ndjson.py`, `test_chat_security.py` | NDJSON streaming, 10 events |
| `backend/api/ingest.py` | `test_ingest_router.py`, `test_ingest_security.py` | Upload, magic bytes |
| `backend/api/collections.py` | `test_collections_router.py` | CRUD |
| `backend/api/documents.py` | `test_documents_router.py` | List, delete |
| `backend/api/models.py` | `test_models_router.py` | Model listing |
| `backend/api/settings.py` | `test_settings_router.py` | PUT settings |
| `backend/api/providers.py` | `test_providers_router.py` | CRUD + key endpoints |
| `backend/api/traces.py` | `test_traces_router.py`, `test_metrics.py` | Traces + metrics |
| `backend/api/health.py` | `test_health_router.py` | Health checks |
| `backend/main.py` | `test_main_security.py`, `test_app_startup.py` | App factory |

**New unit test files to create in spec-16**:

- `tests/unit/test_reranker.py` — `backend/retrieval/reranker.py`: score ordering, top-k truncation, pair scoring; mock CrossEncoder model
- `tests/unit/test_score_normalizer.py` — `backend/retrieval/score_normalizer.py`: per-collection min-max normalization math; pure logic, no mocks
- `tests/unit/test_storage_chunker.py` — `backend/storage/chunker.py`: `chunk_text()` helper; pure logic, no mocks
- `tests/unit/test_storage_indexing.py` — `backend/storage/indexing.py`: `index_chunks()` helper; mock QdrantStorage + SQLiteDB
- `tests/unit/test_errors.py` — `backend/errors.py`: exception hierarchy, subclass relationships, HTTP status mappings

### Integration Test Scenarios (existing vs. new)

| Scenario | Existing Test File | Status |
|----------|--------------------|--------|
| App startup (create_app + mock services) | `test_app_startup.py` | Exists |
| LangGraph conversation flow | `test_conversation_graph.py` | Exists |
| Research graph execution | `test_research_graph.py` | Exists |
| Meta-reasoning graph | `test_meta_reasoning_graph.py` | Exists |
| Accuracy integration (retries, circuit breaker) | `test_accuracy_integration.py` | Exists |
| Ingestion pipeline end-to-end | `test_ingestion_pipeline.py` | Exists |
| Storage layer integration | `test_storage_integration.py` | Exists |
| Concurrent SQLite reads | `test_concurrent_reads.py` | Exists |
| Schema validation | `test_schema_validation.py` | Exists |
| NDJSON streaming (TestClient) | `test_ndjson_streaming.py` | Exists |
| Concurrent stream isolation | `test_concurrent_streams.py` | Exists |
| Rate limiting | `test_rate_limiting.py` | Exists |
| API integration (all routers) | `test_api_integration.py` | Exists |
| Error handler middleware | `test_error_handlers.py` | Exists |
| Provider switching | `test_providers_integration.py` | Exists |
| US1 e2e (collection → upload → query) | `test_us1_e2e.py` | Exists |
| US3 streaming | `test_us3_streaming.py` | Exists |
| US4 traces | `test_us4_traces.py` | Exists |
| Performance budgets | `test_performance.py` | Exists |
| Regression suite (FR/SC checks) | `tests/regression/test_regression.py` | Exists |
| Qdrant CRUD with real container | `test_qdrant_integration.py` | **To create** |
| Hybrid search accuracy | `test_hybrid_search.py` | **To create** |
| Circuit breaker activation | `test_circuit_breaker.py` | **To create** |

### Test Fixtures

#### Missing: `tests/conftest.py` (top-level shared fixtures)

The blueprint specifies a top-level `tests/conftest.py` but it does not exist. Only `tests/integration/conftest.py` exists (contains only `unique_name()`). Spec-16 must create `tests/conftest.py`.

**Correct fixture pattern** (matches actual SQLiteDB API):

```python
# tests/conftest.py
import pytest
import pytest_asyncio
from backend.storage.sqlite_db import SQLiteDB

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite for fast tests."""
    database = SQLiteDB(":memory:")
    await database.connect()          # NOT initialize() — the method is connect()
    yield database
    await database.close()

@pytest.fixture
def sample_chunks() -> list[dict]:
    """Pre-built chunk data for testing."""
    return [
        {"text": "WSAA uses certificate-based authentication...", "page": 12},
        {"text": "The token format follows SAML 2.0...", "page": 13},
    ]

@pytest.fixture
def mock_llm():
    """Mock LLM that returns predictable structured output."""
    # Use unittest.mock.AsyncMock returning a structured AIMessage
    ...

@pytest.fixture
def mock_qdrant_results():
    """Pre-built Qdrant search results."""
    from backend.storage.qdrant_client import SearchResult
    return [
        SearchResult(id=1, score=0.92, payload={"text": "chunk 1", "parent_id": "p1"}),
        SearchResult(id=2, score=0.81, payload={"text": "chunk 2", "parent_id": "p2"}),
    ]

@pytest_asyncio.fixture
async def qdrant_container():
    """Start Qdrant in Docker for integration tests.
    Uses testcontainers-python or pytest-docker.
    Only used in tests/integration/test_qdrant_integration.py.
    """
    ...
```

#### `tests/integration/conftest.py` (already exists and correct)

```python
import uuid

def unique_name(prefix: str = "test") -> str:
    """Generate unique collection names to avoid 409 conflicts.
    Names are lowercased to satisfy regex: ^[a-z0-9][a-z0-9_-]*$
    """
    return f"{prefix.lower()}-{uuid.uuid4().hex[:8]}"
```

### Test Runner (critical — agents must use this)

**Do not run pytest directly.** All test runs must use the detached runner script:

```bash
# Agent usage (invisible background — check status file):
zsh scripts/run-tests-external.sh -n <run-name> <target>

# Poll status (1 line, ~5 tokens):
cat Docs/Tests/<run-name>.status
# → RUNNING | PASSED | FAILED | ERROR | NO_TESTS

# Read summary when done (~20 lines):
cat Docs/Tests/<run-name>.summary

# Debug specific failures only if needed:
grep "FAILED" Docs/Tests/<run-name>.log

# Examples:
zsh scripts/run-tests-external.sh -n unit-check tests/unit/
zsh scripts/run-tests-external.sh -n integ-check tests/integration/
zsh scripts/run-tests-external.sh -n spec16-verify tests/
```

The script auto-creates/updates the `.venv`, handles coverage, and writes outputs to `Docs/Tests/`.

**Human-readable (watch live in tmux)**:

```bash
zsh scripts/run-tests-external.sh --visible -n full-suite tests/
```

**Makefile targets** (for reference only — humans may use these; agents must not):

```makefile
test:             pytest tests/ -v
test-unit:        pytest tests/unit/ -v
test-integration: pytest tests/integration/ -v
```

### Frontend Test Commands

```bash
# Unit tests (vitest, runs from frontend/):
cd frontend && npm run test          # → executes "vitest run"

# Unit tests with coverage:
cd frontend && npm run test -- --coverage

# E2E tests (Playwright, requires running backend + frontend on localhost:3000):
cd frontend && npx playwright test

# E2E tests for a specific file:
cd frontend && npx playwright test tests/e2e/chat.spec.ts
```

---

## E2E Test Scenarios

### Frontend E2E (Playwright) — `frontend/tests/e2e/`

Six spec files already exist:

| File | Coverage |
|------|----------|
| `chat.spec.ts` | Streaming workflow, confidence indicator, citation markers, clarification event |
| `collections.spec.ts` | Collection CRUD |
| `documents.spec.ts` | Document upload and listing |
| `settings.spec.ts` | Provider configuration |
| `responsive.spec.ts` | Responsive layout |
| `workflow.spec.ts` | Full upload-and-query workflow |

Spec-16 may extend these files or add a new `observability.spec.ts` for the metrics/traces dashboard (spec-15 feature).

### Backend E2E — `tests/e2e/` (currently empty)

The `tests/e2e/` directory exists but contains no files. Spec-16 creates backend-level E2E test scripts for scenarios requiring a running backend but no browser:

| Scenario | File | Approach |
|----------|------|----------|
| Upload and query flow | `test_upload_and_query.py` | `httpx.AsyncClient` against real running backend |
| Collection lifecycle | `test_collection_lifecycle.py` | Full CRUD cycle against running backend |
| Observability traces | `test_observability_e2e.py` | Run queries, verify trace records via API |

These tests must be marked with `@pytest.mark.e2e` and require a running backend (`docker compose up backend qdrant`). They are excluded from the normal unit/integration test run.

---

## Test Fixture Files

The blueprint specifies `tests/fixtures/` with sample PDF/MD/TXT. These files do not exist in the codebase. Spec-16 creates:

- `tests/fixtures/sample.pdf` — minimal 3-page PDF (can be generated programmatically with `fpdf2` or included as a binary fixture)
- `tests/fixtures/sample.md` — 200-word test Markdown document
- `tests/fixtures/sample.txt` — 200-word plain text document

---

## Dependencies

### Python Test Dependencies (all already in requirements.txt)

- `pytest>=8.0`
- `pytest-asyncio>=0.24`
- `pytest-cov>=6.0`
- `httpx>=0.28`

Verify with:

```bash
.venv/bin/pip show pytest pytest-asyncio pytest-cov httpx | grep -E "^Name:|^Version:"
```

### Frontend Test Dependencies (already in frontend/package.json)

- `vitest>=3.0` — unit test runner
- `@testing-library/react>=16.0` — component testing
- `@playwright/test>=1.50` — E2E automation

### Optional: Integration Test Infrastructure

- `testcontainers` — Python package for Qdrant Docker container fixture
- Docker with `qdrant/qdrant:latest` image pulled

---

## Acceptance Criteria

1. `zsh scripts/run-tests-external.sh -n spec16 tests/unit/` runs all unit tests with zero new failures.
2. `zsh scripts/run-tests-external.sh -n spec16-integ tests/integration/` passes against real or mocked Qdrant.
3. `zsh scripts/run-tests-external.sh -n spec16-all tests/` shows total passing count >= 1405.
4. `zsh scripts/run-tests-external.sh -n cov tests/` reports backend line coverage >= 80%.
5. `cd frontend && npm run test` runs vitest and passes with zero failures.
6. `tests/conftest.py` exists and provides working `db` (using `await db.connect()`), `sample_chunks`, `mock_llm`, `mock_qdrant_results`, and `qdrant_container` fixtures.
7. Each missing module in the unit test targets table (`test_reranker.py`, `test_score_normalizer.py`, `test_storage_chunker.py`, `test_storage_indexing.py`, `test_errors.py`) has a corresponding test file under `tests/unit/`.
8. `tests/fixtures/sample.pdf`, `tests/fixtures/sample.md`, and `tests/fixtures/sample.txt` exist and are loadable.
9. `tests/e2e/` contains at least one backend E2E test file marked with `@pytest.mark.e2e`.
10. The 39 pre-existing failures remain unchanged — do not fix pre-existing failures as part of spec-16.

---

## Known Pre-Existing Test Failures (do not fix)

There are 39 pre-existing test failures stable across specs 07–15. These relate to schema migration tests against the real `data/embedinator.db` (old schema) and stale DB fixture issues in certain integration tests. Do not modify these as part of spec-16.

---

## Architecture Reference

### Structlog Configuration (spec-15)

The `configure_logging()` function in `backend/main.py` sets up an 8-processor chain:

```
merge_contextvars → _filter_by_component → add_log_level → TimeStamper →
StackInfoRenderer → format_exc_info → CallsiteParameterAdder → JSONRenderer
```

The `_filter_by_component` processor reads `event_dict.get("component", "")` and `method_name` to apply per-component log level overrides from the `LOG_COMPONENT_OVERRIDES` env var.

### `tests/mocks.py` Shared Infrastructure

```python
# Key functions available:
build_simple_chat_graph()      # Returns a compiled LangGraph for conversation tests
build_mock_research_graph()    # Returns a mock ResearchGraph with _mock_research_node
```

Import these in integration tests instead of building custom mock graphs:

```python
from tests.mocks import build_mock_research_graph, build_simple_chat_graph
```

### Error Hierarchy

```python
# backend/errors.py
EmbeddinatorError               # Base
├── QdrantConnectionError
├── OllamaConnectionError
├── SQLiteError
├── LLMCallError
├── EmbeddingError
├── IngestionError
├── SessionLoadError
├── StructuredOutputParseError
├── RerankerError
└── CircuitOpenError
```

### Circuit Breaker "Unknown" State Gotcha

When checking `QdrantClientWrapper` or `QdrantStorage` circuit state, always check `if instance is None` BEFORE `getattr(instance, '_circuit_open', False)`. A `None` instance returns `False` from `getattr`, which incorrectly reports the circuit as "closed".

### `ProviderRateLimitError` Note

`ProviderRateLimitError` is defined separately (not in `errors.py`). When testing provider error paths, import it from `backend/providers/base.py`.
