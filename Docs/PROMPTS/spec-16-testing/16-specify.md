# Spec 16: Testing -- Feature Specification Context

## Feature Description

The Testing Strategy for The Embedinator defines the complete test infrastructure: test framework stack, test pyramid (unit, integration, E2E), directory structure, shared fixtures, mock strategies, and test targets per module. The system uses pytest for all Python backend tests, vitest with @testing-library/react for frontend unit tests, and Playwright for end-to-end browser tests. Integration tests use real Qdrant containers via testcontainers-python and in-memory SQLite.

## Requirements

### Functional Requirements

1. **Test Pyramid**: Unit tests (fast, isolated, mocked dependencies), integration tests (real services in containers), E2E tests (browser automation with Playwright).
2. **Python Backend Tests**: Use `pytest` with `pytest-asyncio` for async tests, `pytest-cov` for coverage, and `httpx` for HTTP testing via FastAPI `TestClient`.
3. **Frontend Unit Tests**: Use `vitest` with `@testing-library/react` for component testing.
4. **Frontend E2E Tests**: Use `@playwright/test` for full browser automation tests covering upload-and-query, collection management, provider configuration, meta-reasoning trigger, and observability.
5. **Test Fixtures**: Shared fixtures in `tests/conftest.py` including in-memory SQLite, sample chunk data, mock LLM, mock Qdrant results, and Qdrant Docker container fixture.
6. **Coverage Targets**: Backend code coverage targets must be defined and enforced.
7. **Test Directory Structure**: Tests organized by type (unit/integration/e2e) and module (agent/ingestion/retrieval/storage/providers).

### Non-Functional Requirements

- Unit tests must run in under 30 seconds for the entire suite.
- Integration tests may take longer but must complete in under 5 minutes.
- E2E tests require a running backend and frontend; they are run separately from unit/integration tests.
- All SQL operations tested with in-memory SQLite (`:memory:`) for speed.
- Mock LLM must return predictable structured output for deterministic agent tests.

## Key Technical Details

### Test Framework Stack

| Layer | Framework | Plugins |
|-------|-----------|---------|
| Python backend (unit + integration) | `pytest` | `pytest-asyncio`, `pytest-cov` |
| Python HTTP tests | `httpx` | `httpx[asyncio]` via `TestClient` |
| LangGraph integration | `pytest` + LangGraph test utilities | Custom fixtures |
| Frontend unit | `vitest` | `@testing-library/react` |
| Frontend E2E | `playwright` | `@playwright/test` |

### Unit Test Targets

| Module | What to Test | What to Mock |
|--------|-------------|-------------|
| `backend/agent/nodes.py` | Each node function in isolation; correct state reads/writes; error handling fallbacks | LLM calls (`BaseChatModel`), CrossEncoder, SQLiteDB |
| `backend/agent/tools.py` | Tool return types; deduplication via retrieval_keys; filter validation | QdrantStorage, BatchEmbedder |
| `backend/agent/edges.py` | Conditional routing logic; all branch conditions covered | State dictionaries (mock data) |
| `backend/ingestion/pipeline.py` | Full pipeline with mock Rust output; duplicate detection; error accumulation | Rust subprocess (mock NDJSON stdin), QdrantStorage, BatchEmbedder |
| `backend/ingestion/embedder.py` | Batch splitting; validation logic; retry behavior | Ollama HTTP calls |
| `backend/ingestion/chunker.py` | Parent/child size constraints; breadcrumb prepending; sentence boundary detection | None (pure logic) |
| `backend/ingestion/incremental.py` | Hash computation; duplicate detection; re-ingestion logic | SQLiteDB |
| `backend/retrieval/searcher.py` | Hybrid search query construction; multi-collection merge; score normalization | QdrantStorage, BatchEmbedder |
| `backend/retrieval/reranker.py` | Score ordering; top-k truncation; pair scoring | CrossEncoder model (use small test model) |
| `backend/storage/qdrant_client.py` | Collection CRUD; upsert batching; retry/circuit breaker behavior | Qdrant HTTP (use `responses` or `httpx` mock) |
| `backend/storage/sqlite_db.py` | All CRUD operations; concurrent read behavior; migration | In-memory SQLite (`:memory:`) |
| `backend/providers/registry.py` | Model-to-provider resolution; key decryption; fallback handling | Provider instances, KeyManager |
| `backend/config.py` | Default values; env var override; validation | Environment variables |

### Integration Test Scenarios

| Scenario | Components | Fixture Requirements |
|----------|-----------|---------------------|
| Qdrant CRUD cycle | `qdrant_client` + real Qdrant | Docker Qdrant container (test fixture) |
| Ingestion end-to-end | `pipeline` + `chunker` + `embedder` + `qdrant_client` + `sqlite_db` | Small test PDF, real Qdrant + SQLite |
| LangGraph conversation flow | All agent graphs + mock LLM | Mock LLM returning predictable structured output |
| Hybrid search accuracy | `searcher` + `reranker` + Qdrant | Pre-indexed test collection with known-relevant chunks |
| Provider switching | `registry` + `OllamaProvider` | Running Ollama instance |
| Circuit breaker activation | `qdrant_client` with unreachable server | Network mock or stopped Qdrant container |

### E2E Test Scenarios

| Scenario | Steps | Assertions |
|----------|-------|-----------|
| Upload and query | 1. Create collection via UI; 2. Upload test PDF; 3. Wait for ingestion complete; 4. Ask question; 5. Verify streamed answer contains citations | Answer is non-empty; at least 1 citation rendered; confidence indicator visible |
| Collection management | 1. Create collection; 2. Verify appears in list; 3. Delete collection; 4. Verify removed | Collection card appears/disappears; Qdrant collection created/deleted |
| Provider configuration | 1. Navigate to settings; 2. Enter test API key; 3. Verify provider shows as active; 4. Select cloud model; 5. Query with cloud model | Provider status updates; model appears in dropdown; query succeeds |
| Meta-reasoning trigger | 1. Create collection with minimal docs; 2. Ask question outside doc scope; 3. Verify meta-reasoning event in SSE stream | `meta_reasoning` SSE event received; uncertainty message displayed |
| Observability | 1. Run several queries; 2. Navigate to observability; 3. Verify traces appear; 4. Verify latency chart renders | Trace table populated; chart renders; health checks show green |

### Test Fixtures and Factories

```python
# tests/conftest.py

import pytest
import pytest_asyncio
from backend.storage.sqlite_db import SQLiteDB

@pytest_asyncio.fixture
async def db():
    """In-memory SQLite for fast tests."""
    db = SQLiteDB(":memory:")
    await db.initialize()
    yield db

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
    ...

@pytest.fixture
def mock_qdrant_results():
    """Pre-built Qdrant search results."""
    ...

@pytest_asyncio.fixture
async def qdrant_container():
    """Start Qdrant in Docker for integration tests."""
    # Uses testcontainers-python or manual docker-compose
    ...
```

### Test Directory Structure

```
tests/
  conftest.py                    # Shared fixtures
  unit/
    agent/
      test_nodes.py              # Node function tests
      test_edges.py              # Edge routing tests
      test_tools.py              # Tool execution tests
      test_schemas.py            # Pydantic model tests
    ingestion/
      test_pipeline.py           # Pipeline orchestration
      test_embedder.py           # Embedding + validation
      test_chunker.py            # Chunk splitting logic
      test_incremental.py        # Hash + dedup logic
    retrieval/
      test_searcher.py           # Search query construction
      test_reranker.py           # Reranking logic
      test_score_normalizer.py   # Normalization math
    storage/
      test_sqlite_db.py          # All SQLite operations
      test_qdrant_client.py      # Qdrant client (mocked)
    providers/
      test_registry.py           # Provider resolution
      test_key_manager.py        # Encryption/decryption
  integration/
    test_qdrant_integration.py   # Real Qdrant container
    test_ingestion_e2e.py        # Full pipeline
    test_langgraph_flow.py       # Agent graph execution
    test_hybrid_search.py        # Search accuracy
  e2e/
    test_chat_flow.spec.ts       # Playwright: upload + query
    test_collections.spec.ts     # Playwright: CRUD
    test_observability.spec.ts   # Playwright: dashboard
  fixtures/
    sample.pdf                   # 3-page test PDF
    sample.md                    # Test markdown
    sample.txt                   # Test plain text
```

## Dependencies

- **Python test dependencies**: `pytest>=8.0`, `pytest-asyncio>=0.24`, `pytest-cov>=6.0`, `httpx>=0.28`
- **Frontend test dependencies**: `vitest>=3.0`, `@playwright/test>=1.50`, `@testing-library/react>=16.0`
- **Infrastructure for integration tests**: Docker (for Qdrant containers via testcontainers-python)
- **Test fixtures**: Sample PDF (3 pages), sample Markdown, sample plain text files in `tests/fixtures/`

## Acceptance Criteria

1. `pytest tests/unit/` runs all unit tests and passes with zero failures.
2. `pytest tests/integration/` runs integration tests against real Qdrant containers and passes.
3. `npx playwright test` runs all E2E tests against a running backend+frontend.
4. `pytest --cov=backend` reports code coverage.
5. `cd frontend && npm run test` runs vitest frontend unit tests.
6. The `tests/conftest.py` file provides working in-memory SQLite, sample chunk, and mock LLM fixtures.
7. Each module listed in the unit test targets table has a corresponding test file.
8. Test fixture files (sample.pdf, sample.md, sample.txt) exist in `tests/fixtures/`.
9. Integration tests use Docker containers for Qdrant (not mocked).
10. E2E tests cover the five scenarios: upload+query, collection management, provider config, meta-reasoning, observability.

## Architecture Reference

Makefile targets for testing:

```makefile
test:
	.venv/bin/pytest tests/ -q --tb=short --no-header

test-cov:
	.venv/bin/pytest tests/ --cov=backend --cov-report=term-missing -q --tb=short

test-frontend:
	cd frontend && npm run test
```

Dev/test dependency versions from the architecture document:

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | `>=8.0` | Test runner |
| `pytest-asyncio` | `>=0.24` | Async test support |
| `pytest-cov` | `>=6.0` | Coverage reporting |
| `httpx` | `>=0.28` | Test HTTP client |
| `vitest` | `>=3.0` | Frontend unit tests |
| `@playwright/test` | `>=1.50` | Frontend E2E tests |
| `@testing-library/react` | `>=16.0` | Component testing |
