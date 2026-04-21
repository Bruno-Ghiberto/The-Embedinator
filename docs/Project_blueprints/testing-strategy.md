# The Embedinator — Testing Strategy

**Version**: 1.0
**Date**: 2026-03-10
**Source**: `docs/architecture-design.md` Section 19 (Testing Strategy)

---

## Test Framework Stack

| Layer | Framework | Plugins |
|---|---|---|
| Python backend (unit + integration) | `pytest` | `pytest-asyncio`, `pytest-cov` |
| Python HTTP tests | `httpx` | `httpx[asyncio]` via `TestClient` |
| LangGraph integration | `pytest` + LangGraph test utilities | Custom fixtures |
| Frontend unit | `vitest` | `@testing-library/react` |
| Frontend E2E | `playwright` | `@playwright/test` |

---

## Test Pyramid

```
         /\
        /  \     E2E Tests (Playwright)
       / 5% \    Full browser flows
      /------\
     /        \   Integration Tests
    /   20%    \  Real services, cross-component
   /------------\
  /              \  Unit Tests
 /     75%        \ Pure logic, mocked dependencies
/------------------\
```

### Coverage Targets

| Layer | Target | Enforcement |
|---|---|---|
| Backend unit tests | >= 80% line coverage | `pytest-cov` |
| Backend integration | Key flows covered | Manual verification |
| Frontend unit tests | >= 70% line coverage | `vitest --coverage` |
| Frontend E2E | Critical user journeys | Playwright test suite |

---

## Unit Test Targets

| Module | What to Test | What to Mock |
|---|---|---|
| `backend/agent/nodes.py` | Each node function in isolation; correct state reads/writes; error handling fallbacks | LLM calls (`BaseChatModel`), CrossEncoder, SQLiteDB |
| `backend/agent/tools.py` | Tool return types; deduplication via `retrieval_keys`; filter validation | QdrantStorage, BatchEmbedder |
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
| `backend/agent/retrieval.py` | Filter by collection; exclude deleted docs; top_k; empty results | QdrantStorage, SQLiteDB |
| `backend/agent/confidence.py` | Zero/perfect/mixed scores; clamping; top_k weighting | None (pure logic) |
| `backend/agent/citations.py` | Basic citation build; dedup; max limit; truncation; prompt formatting | None (pure logic) |
| `backend/agent/answer_generator.py` | Stream tokens; empty stream; complete generation | LLMProvider |

---

## Integration Test Scenarios

| Scenario | Components | Fixture Requirements |
|---|---|---|
| Qdrant CRUD cycle | `qdrant_client` + real Qdrant | Docker Qdrant container (test fixture) |
| Ingestion end-to-end | `pipeline` + `chunker` + `embedder` + `qdrant_client` + `sqlite_db` | Small test PDF, real Qdrant + SQLite |
| LangGraph conversation flow | All agent graphs + mock LLM | Mock LLM returning predictable structured output |
| Hybrid search accuracy | `searcher` + `reranker` + Qdrant | Pre-indexed test collection with known-relevant chunks |
| Provider switching | `registry` + `OllamaProvider` | Running Ollama instance |
| Circuit breaker activation | `qdrant_client` with unreachable server | Network mock or stopped Qdrant container |
| App startup | `create_app()` + mock services | Mock Qdrant, mock ProviderRegistry |
| US1 e2e flow | create collection → upload → query → verify | FastAPI TestClient, tmp SQLite |
| US3 streaming | chat endpoint → NDJSON stream parsing | FastAPI TestClient, mock LLM |
| US4 traces | chat → verify trace record created | FastAPI TestClient, tmp SQLite |

---

## E2E Test Scenarios (Playwright)

| Scenario | Steps | Assertions |
|---|---|---|
| Upload and query | 1. Create collection via UI; 2. Upload test PDF; 3. Wait for ingestion; 4. Ask question; 5. Verify streamed answer with citations | Answer non-empty; >= 1 citation; confidence visible |
| Collection management | 1. Create collection; 2. Verify in list; 3. Delete; 4. Verify removed | Card appears/disappears; Qdrant collection CRUD |
| Provider configuration | 1. Navigate to settings; 2. Enter test API key; 3. Verify active; 4. Select cloud model; 5. Query | Provider status updates; model in dropdown; query succeeds |
| Meta-reasoning trigger | 1. Create collection with minimal docs; 2. Ask out-of-scope question; 3. Verify meta-reasoning event | `meta_reasoning` SSE event; uncertainty message |
| Observability | 1. Run queries; 2. Navigate to observability; 3. Verify traces; 4. Verify charts | Trace table populated; chart renders; health green |

---

## Test Fixtures and Factories

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

### `unique_name()` Helper

```python
# tests/integration/conftest.py
import uuid

def unique_name(prefix: str) -> str:
    """Generate unique collection names to avoid 409 conflicts."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"
```

---

## Test Directory Structure

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
    test_retrieval.py            # Retrieval module tests
    test_confidence.py           # Confidence scoring tests
    test_citations.py            # Citation building tests
    test_answer_generator.py     # Answer generation tests
  integration/
    conftest.py                  # unique_name() helper
    test_qdrant_integration.py   # Real Qdrant container
    test_ingestion_e2e.py        # Full pipeline
    test_langgraph_flow.py       # Agent graph execution
    test_hybrid_search.py        # Search accuracy
    test_app_startup.py          # App factory and lifespan
    test_us1_e2e.py              # User Story 1 flow
    test_us3_streaming.py        # NDJSON streaming
    test_us4_traces.py           # Trace recording
  e2e/
    test_chat_flow.spec.ts       # Playwright: upload + query
    test_collections.spec.ts     # Playwright: CRUD
    test_observability.spec.ts   # Playwright: dashboard
  fixtures/
    sample.pdf                   # 3-page test PDF
    sample.md                    # Test markdown
    sample.txt                   # Test plain text
```

---

## Running Tests

```bash
# Unit tests only (fast, no external services)
pytest tests/unit/ -v

# Unit tests with coverage
pytest tests/unit/ --cov=backend --cov-report=term-missing

# Integration tests (requires Docker services)
docker compose up -d qdrant ollama
pytest tests/integration/ -v

# All Python tests
pytest -v

# Frontend unit tests
cd frontend && npx vitest run

# Frontend E2E tests
cd frontend && npx playwright test
```

---

## CI Pipeline (Recommended)

```yaml
# .github/workflows/test.yml
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with: { python-version: "3.14" }
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: pytest tests/unit/ --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration-tests:
    runs-on: ubuntu-latest
    services:
      qdrant: { image: qdrant/qdrant:latest, ports: ["6333:6333"] }
    steps:
      - run: pytest tests/integration/ -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - run: cd frontend && npm ci && npx vitest run
```

---

*Extracted from `docs/architecture-design.md` Section 19 (Testing Strategy), supplemented with current test implementation details.*
