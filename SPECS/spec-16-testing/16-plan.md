# Spec 16: Testing -- Implementation Plan Context

## Component Overview

The Testing infrastructure provides the complete test pyramid for The Embedinator: unit tests for isolated component validation, integration tests with real services, and E2E browser tests for user journey verification. This spec covers setting up the test directory structure, creating shared fixtures, configuring test runners, and establishing patterns for mocking external dependencies.

## Technical Approach

### Unit Tests (pytest)

- Each backend module gets a corresponding test file in `tests/unit/{module}/`.
- Use `pytest-asyncio` for all async test functions (most backend code is async).
- Mock external dependencies (LLM calls, Qdrant HTTP, Ollama HTTP) using `unittest.mock.AsyncMock` or `httpx` response mocking.
- Use in-memory SQLite (`:memory:`) for all database tests -- no disk I/O, instant teardown.
- Pure logic modules (chunker, score normalizer, edge routing) require no mocks.

### Integration Tests (pytest + Docker)

- Use `testcontainers-python` to spin up Qdrant containers per test session.
- Integration tests verify real interactions: Qdrant CRUD, full ingestion pipeline, LangGraph graph execution.
- Mark integration tests with `@pytest.mark.integration` so they can be run separately.
- Integration tests may require a running Ollama instance; provide a `@pytest.mark.requires_ollama` marker for those.

### E2E Tests (Playwright)

- Written in TypeScript using `@playwright/test`.
- Tests run against a fully running system (backend + frontend + Qdrant + Ollama).
- Cover five critical user journeys: upload+query, collection CRUD, provider config, meta-reasoning trigger, observability dashboard.
- Use Playwright's built-in wait mechanisms for SSE streaming assertions.

### Frontend Unit Tests (vitest)

- Test React components in isolation using `@testing-library/react`.
- Mock API calls using vitest's built-in mocking.
- Focus on rendering logic, user interactions, and state management.

### Mock Strategies

- **Mock LLM**: Create a `MockChatModel` that returns predictable `AIMessage` objects with structured output. Used for agent node and graph tests.
- **Mock Qdrant**: Use `httpx` mock responses or `unittest.mock.AsyncMock` on the `QdrantStorage` class.
- **Mock Rust Worker**: Create mock NDJSON output that simulates the Rust worker's stdout stream.
- **Mock Embeddings**: Return fixed-dimension vectors (e.g., all-zeros or random seeded) instead of calling Ollama.

## File Structure

```
tests/
  conftest.py                    # Shared fixtures: db, sample_chunks, mock_llm, etc.
  pytest.ini                     # (or pyproject.toml [tool.pytest]) config
  unit/
    __init__.py
    agent/
      __init__.py
      test_nodes.py
      test_edges.py
      test_tools.py
      test_schemas.py
    ingestion/
      __init__.py
      test_pipeline.py
      test_embedder.py
      test_chunker.py
      test_incremental.py
    retrieval/
      __init__.py
      test_searcher.py
      test_reranker.py
      test_score_normalizer.py
    storage/
      __init__.py
      test_sqlite_db.py
      test_qdrant_client.py
    providers/
      __init__.py
      test_registry.py
      test_key_manager.py
    test_config.py
    test_validators.py
    test_middleware.py
  integration/
    __init__.py
    conftest.py                  # Integration-specific fixtures (Qdrant container)
    test_qdrant_integration.py
    test_ingestion_e2e.py
    test_langgraph_flow.py
    test_hybrid_search.py
  e2e/
    playwright.config.ts
    test_chat_flow.spec.ts
    test_collections.spec.ts
    test_observability.spec.ts
  fixtures/
    sample.pdf                   # 3-page test PDF with known content
    sample.md                    # Test markdown with headings
    sample.txt                   # Test plain text

frontend/
  vitest.config.ts               # Vitest configuration
  __tests__/                     # Or colocated .test.tsx files
    components/
      ChatPanel.test.tsx
      CollectionCard.test.tsx
      LatencyChart.test.tsx
      HealthDashboard.test.tsx
```

## Implementation Steps

1. **Create test directory structure**: Set up all directories and `__init__.py` files as specified above.
2. **Create `tests/conftest.py`**: Implement shared fixtures -- in-memory SQLite, sample chunks, mock LLM, mock Qdrant results.
3. **Configure pytest**: Add pytest configuration to `pyproject.toml` or `pytest.ini` with async mode, markers, and coverage settings.
4. **Create test fixture files**: Add `sample.pdf` (3-page PDF with known searchable content), `sample.md`, and `sample.txt` to `tests/fixtures/`.
5. **Write unit test stubs**: Create test files for each module with test function signatures and docstrings describing what each test validates.
6. **Implement priority unit tests**: Start with pure-logic modules (chunker, score normalizer, edges) that need no mocking, then proceed to mocked tests.
7. **Set up integration test fixtures**: Create `tests/integration/conftest.py` with a Qdrant container fixture using testcontainers.
8. **Write integration tests**: Implement Qdrant CRUD, full ingestion pipeline, and LangGraph flow tests.
9. **Configure Playwright**: Create `tests/e2e/playwright.config.ts` with base URL and timeout settings.
10. **Write E2E test scripts**: Implement the five E2E scenarios using Playwright page objects.
11. **Configure vitest**: Create `frontend/vitest.config.ts` with React plugin and testing-library setup.
12. **Write frontend unit tests**: Test key components (ChatPanel, CollectionCard, LatencyChart, HealthDashboard).
13. **Add Makefile targets**: Ensure `make test`, `make test-cov`, and `make test-frontend` work correctly.
14. **Create `requirements-dev.txt`**: List all Python dev/test dependencies.

## Integration Points

- **All other specs**: Every spec's implementation should have corresponding unit tests in this test infrastructure.
- **Infrastructure (Spec 17)**: Makefile targets for running tests. Docker containers for integration tests.
- **Observability (Spec 15)**: E2E test for the observability dashboard validates that traces are displayed.
- **Security (Spec 13)**: Unit tests for KeyManager, FileValidator, and RateLimiter.
- **Performance (Spec 14)**: Performance benchmark tests in `tests/integration/test_performance.py`.

## Key Code Patterns

### Async Test Function Pattern

```python
import pytest

@pytest.mark.asyncio
async def test_sqlite_create_collection(db):
    """Test creating a collection in SQLite."""
    collection_id = await db.create_collection("test-collection", "Test")
    assert collection_id is not None

    collection = await db.get_collection(collection_id)
    assert collection["name"] == "test-collection"
```

### Mock LLM Pattern

```python
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

@pytest.fixture
def mock_llm():
    """Mock LLM returning predictable structured output."""
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="Test answer"))
    llm.with_structured_output = MagicMock(return_value=llm)
    return llm
```

### Qdrant Container Fixture Pattern

```python
import pytest_asyncio

@pytest_asyncio.fixture(scope="session")
async def qdrant_container():
    """Start a Qdrant container for the test session."""
    # Option 1: testcontainers-python
    from testcontainers.qdrant import QdrantContainer
    container = QdrantContainer()
    container.start()
    yield container.get_connection_url()
    container.stop()
```

### Playwright E2E Pattern

```typescript
import { test, expect } from '@playwright/test';

test('upload and query flow', async ({ page }) => {
  await page.goto('/collections');
  // Create collection
  await page.click('button:has-text("Create Collection")');
  await page.fill('input[name="name"]', 'test-collection');
  await page.click('button:has-text("Create")');
  // Upload file
  await page.setInputFiles('input[type="file"]', 'tests/fixtures/sample.pdf');
  // Wait for ingestion
  await page.waitForSelector('text=Ingestion complete', { timeout: 30000 });
  // Ask question
  await page.goto('/chat');
  await page.fill('textarea', 'What is in the document?');
  await page.press('textarea', 'Enter');
  // Verify answer
  await expect(page.locator('.chat-message')).toContainText(/./);
});
```

## Phase Assignment

- **Phase 1 (MVP)**: Test directory structure, conftest.py with shared fixtures, unit tests for storage (sqlite_db), config, and core agent logic. Basic pytest configuration.
- **Phase 2 (Performance and Resilience)**: Integration tests with Qdrant containers, full agent graph tests with mock LLM, ingestion pipeline integration tests, performance benchmark tests.
- **Phase 3 (Ecosystem and Polish)**: Comprehensive E2E test suite (all 5 scenarios), frontend vitest configuration and component tests, full coverage reporting, CI pipeline integration.
