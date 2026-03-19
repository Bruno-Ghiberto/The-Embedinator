# Spec 16: Testing -- Implementation Context

## Implementation Scope

### Files to Create

- `tests/conftest.py` -- Shared test fixtures
- `tests/unit/__init__.py` and all subdirectory `__init__.py` files
- `tests/unit/agent/test_nodes.py`
- `tests/unit/agent/test_edges.py`
- `tests/unit/agent/test_tools.py`
- `tests/unit/agent/test_schemas.py`
- `tests/unit/ingestion/test_pipeline.py`
- `tests/unit/ingestion/test_embedder.py`
- `tests/unit/ingestion/test_chunker.py`
- `tests/unit/ingestion/test_incremental.py`
- `tests/unit/retrieval/test_searcher.py`
- `tests/unit/retrieval/test_reranker.py`
- `tests/unit/retrieval/test_score_normalizer.py`
- `tests/unit/storage/test_sqlite_db.py`
- `tests/unit/storage/test_qdrant_client.py`
- `tests/unit/providers/test_registry.py`
- `tests/unit/providers/test_key_manager.py`
- `tests/unit/test_config.py`
- `tests/unit/test_validators.py`
- `tests/unit/test_middleware.py`
- `tests/integration/__init__.py`
- `tests/integration/conftest.py`
- `tests/integration/test_qdrant_integration.py`
- `tests/integration/test_ingestion_e2e.py`
- `tests/integration/test_langgraph_flow.py`
- `tests/integration/test_hybrid_search.py`
- `tests/e2e/playwright.config.ts`
- `tests/e2e/test_chat_flow.spec.ts`
- `tests/e2e/test_collections.spec.ts`
- `tests/e2e/test_observability.spec.ts`
- `tests/fixtures/sample.pdf`
- `tests/fixtures/sample.md`
- `tests/fixtures/sample.txt`
- `requirements-dev.txt` -- Python dev/test dependencies
- `frontend/vitest.config.ts` -- Vitest configuration (if not already present)

## Code Specifications

### tests/conftest.py

```python
"""Shared test fixtures for The Embedinator backend tests."""

import pytest
import pytest_asyncio
from typing import List
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

from backend.storage.sqlite_db import SQLiteDB


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite for fast tests. Initializes schema automatically."""
    db = SQLiteDB(":memory:")
    await db.initialize()
    yield db
    await db.close()


@pytest.fixture
def sample_chunks() -> List[dict]:
    """Pre-built chunk data for testing retrieval and ingestion."""
    return [
        {
            "text": "WSAA uses certificate-based authentication for web services.",
            "page": 12,
            "chunk_index": 0,
            "source_file": "sample.pdf",
            "breadcrumb": "Chapter 2 > Authentication > WSAA",
            "doc_type": "pdf",
        },
        {
            "text": "The token format follows SAML 2.0 specification for assertions.",
            "page": 13,
            "chunk_index": 1,
            "source_file": "sample.pdf",
            "breadcrumb": "Chapter 2 > Authentication > Tokens",
            "doc_type": "pdf",
        },
        {
            "text": "Electronic invoicing requires digital signatures using X.509 certificates.",
            "page": 25,
            "chunk_index": 2,
            "source_file": "sample.pdf",
            "breadcrumb": "Chapter 3 > Invoicing > Digital Signatures",
            "doc_type": "pdf",
        },
    ]


@pytest.fixture
def mock_llm():
    """Mock LLM that returns predictable structured output.

    Supports both regular ainvoke and with_structured_output patterns.
    """
    llm = MagicMock()
    llm.ainvoke = AsyncMock(
        return_value=AIMessage(content="This is a test response based on the context.")
    )
    llm.with_structured_output = MagicMock(return_value=llm)
    llm.bind_tools = MagicMock(return_value=llm)
    return llm


@pytest.fixture
def mock_embeddings():
    """Mock embedding function returning fixed-dimension vectors."""

    async def embed(texts: list[str]) -> list[list[float]]:
        # Return 768-dim zero vectors (matching nomic-embed-text output dim)
        return [[0.0] * 768 for _ in texts]

    return embed


@pytest.fixture
def mock_qdrant_results() -> list[dict]:
    """Pre-built Qdrant search results for retrieval tests."""
    return [
        {
            "id": "point-1",
            "score": 0.92,
            "payload": {
                "text": "WSAA uses certificate-based authentication...",
                "source_file": "sample.pdf",
                "page": 12,
                "chunk_index": 0,
                "doc_type": "pdf",
                "breadcrumb": "Chapter 2 > Authentication > WSAA",
                "parent_chunk_id": "parent-1",
            },
        },
        {
            "id": "point-2",
            "score": 0.85,
            "payload": {
                "text": "The token format follows SAML 2.0...",
                "source_file": "sample.pdf",
                "page": 13,
                "chunk_index": 1,
                "doc_type": "pdf",
                "breadcrumb": "Chapter 2 > Authentication > Tokens",
                "parent_chunk_id": "parent-2",
            },
        },
    ]


@pytest.fixture
def mock_cross_encoder():
    """Mock cross-encoder model for reranking tests."""
    model = MagicMock()
    # predict() returns scores for each (query, passage) pair
    model.predict = MagicMock(return_value=[0.95, 0.82, 0.71, 0.65, 0.30])
    return model


@pytest.fixture
def settings():
    """Test-specific settings with safe defaults."""
    from backend.config import Settings

    return Settings(
        sqlite_path=":memory:",
        api_key_encryption_secret="test-secret-for-unit-tests",
        qdrant_host="localhost",
        qdrant_port=6333,
        ollama_base_url="http://localhost:11434",
    )
```

### tests/integration/conftest.py

```python
"""Integration test fixtures requiring external services."""

import pytest
import pytest_asyncio


@pytest_asyncio.fixture(scope="session")
async def qdrant_url():
    """Start a Qdrant container for the test session.

    Uses testcontainers-python for automatic container management.
    Falls back to localhost:6333 if testcontainers is not available.
    """
    try:
        from testcontainers.qdrant import QdrantContainer

        container = QdrantContainer()
        container.start()
        url = container.get_connection_url()
        yield url
        container.stop()
    except ImportError:
        # Fall back to a locally running Qdrant
        yield "http://localhost:6333"


@pytest.fixture
def test_pdf_path():
    """Path to the 3-page test PDF fixture."""
    from pathlib import Path

    return Path(__file__).parent.parent / "fixtures" / "sample.pdf"


@pytest.fixture
def test_md_path():
    """Path to the test Markdown fixture."""
    from pathlib import Path

    return Path(__file__).parent.parent / "fixtures" / "sample.md"
```

### pytest configuration (in pyproject.toml)

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = [
    "integration: tests requiring external services (Qdrant, Ollama)",
    "slow: tests that take more than 10 seconds",
    "requires_ollama: tests requiring a running Ollama instance",
    "e2e: end-to-end browser tests",
]
filterwarnings = [
    "ignore::DeprecationWarning",
]
```

### requirements-dev.txt

```
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=6.0
httpx>=0.28
testcontainers[qdrant]>=4.0
```

### tests/e2e/playwright.config.ts

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './',
  timeout: 60000,
  retries: 1,
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
  webServer: [
    {
      command: 'make dev-backend',
      url: 'http://localhost:8000/api/health',
      timeout: 30000,
      reuseExistingServer: true,
    },
    {
      command: 'make dev-frontend',
      url: 'http://localhost:3000',
      timeout: 30000,
      reuseExistingServer: true,
    },
  ],
});
```

### Sample E2E Test (tests/e2e/test_collections.spec.ts)

```typescript
import { test, expect } from '@playwright/test';

test.describe('Collection management', () => {
  test('create and delete collection', async ({ page }) => {
    await page.goto('/collections');

    // Create collection
    await page.click('button:has-text("Create")');
    await page.fill('input[name="name"]', 'playwright-test');
    await page.fill('input[name="description"]', 'Test collection');
    await page.click('button:has-text("Create")');

    // Verify collection appears
    await expect(page.locator('text=playwright-test')).toBeVisible();

    // Delete collection
    await page.click('[data-testid="delete-playwright-test"]');
    await page.click('button:has-text("Confirm")');

    // Verify collection removed
    await expect(page.locator('text=playwright-test')).not.toBeVisible();
  });
});
```

### frontend/vitest.config.ts

```typescript
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./test-setup.ts'],
  },
});
```

## Configuration

### Makefile Targets (already defined in architecture)

```makefile
test:
	.venv/bin/pytest tests/ -q --tb=short --no-header

test-cov:
	.venv/bin/pytest tests/ --cov=backend --cov-report=term-missing -q --tb=short

test-frontend:
	cd frontend && npm run test

test-e2e:
	cd tests/e2e && npx playwright test

test-integration:
	.venv/bin/pytest tests/integration/ -q --tb=short -m integration
```

## Error Handling

- **Qdrant container startup failure**: If testcontainers cannot start Qdrant (e.g., Docker not available), fall back to `localhost:6333`. If that also fails, skip integration tests with a clear message.
- **Missing test fixtures**: If `tests/fixtures/sample.pdf` does not exist, fixture-dependent tests should skip with `pytest.skip("Test PDF fixture not found")`.
- **Ollama not available**: Tests marked with `@pytest.mark.requires_ollama` skip when Ollama is not reachable.
- **Playwright browser not installed**: Provide a `make setup-e2e` target that runs `npx playwright install chromium`.

## Testing Requirements

This spec is self-referential -- the testing infrastructure itself should be validated:

1. `pytest tests/unit/ --co` (collect only) succeeds, finding all test files.
2. `pytest tests/conftest.py` imports successfully and fixtures are instantiable.
3. All `__init__.py` files exist so pytest discovers tests correctly.
4. `requirements-dev.txt` installs without errors.
5. `cd frontend && npx vitest --run` runs without configuration errors.

## Done Criteria

- [ ] Test directory structure matches the architecture specification exactly
- [ ] `tests/conftest.py` provides working fixtures: db, sample_chunks, mock_llm, mock_embeddings, mock_qdrant_results, mock_cross_encoder, settings
- [ ] pytest is configured in `pyproject.toml` with asyncio_mode="auto" and custom markers
- [ ] `requirements-dev.txt` lists all Python test dependencies with version constraints
- [ ] At least one unit test exists per module listed in the unit test targets table
- [ ] `tests/integration/conftest.py` provides a Qdrant container fixture
- [ ] Test fixture files exist: `tests/fixtures/sample.pdf`, `tests/fixtures/sample.md`, `tests/fixtures/sample.txt`
- [ ] Playwright configuration exists at `tests/e2e/playwright.config.ts`
- [ ] At least one E2E test script exists (collection CRUD)
- [ ] Vitest is configured for frontend tests
- [ ] `make test` runs unit tests successfully
- [ ] `make test-cov` produces a coverage report
- [ ] `make test-frontend` runs frontend tests
