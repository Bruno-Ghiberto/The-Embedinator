# Spec 16: Testing Strategy — Implementation Plan

## Component Overview

Spec 16 fills specific test coverage gaps. It makes **no production code changes**. All work is pure test infrastructure:

- A shared `tests/conftest.py` with 4 reusable fixtures used across the suite
- 5 unit test files for production modules that currently have zero coverage
- 3 backend end-to-end tests in `tests/e2e/` (Python, not Playwright/TypeScript)
- 3 integration test files requiring a live Qdrant instance (`@pytest.mark.require_docker`)
- 3 static binary fixture files committed to `tests/fixtures/`
- A `pytest.ini` at the project root registering custom markers and enforcing the 80% coverage gate

Playwright/TypeScript E2E tests already exist in `frontend/tests/e2e/` — do not touch them. Frontend vitest tests already exist — do not touch them. All work here is Python backend only.

---

## What Already Exists — DO NOT Recreate

The following test files exist and must not be recreated or modified unless explicitly required to fix a regression:

**`tests/unit/` (flat structure, 40+ files):**
```
test_accuracy_nodes.py         test_meta_reasoning_nodes.py
test_answer_generator.py       test_middleware_rate_limit.py
test_chat_ndjson.py            test_ndjson_frames.py
test_chunker.py                test_nodes.py
test_citations.py              test_parent_store.py
test_collections_router.py     test_providers.py
test_component_log_levels.py   test_providers_router.py
test_confidence.py             test_qdrant_storage.py
test_config.py                 test_research_confidence.py
test_contracts_agent.py        test_research_edges.py
test_contracts_cross_cutting.py test_research_nodes.py
test_contracts_ingestion.py    test_research_tools.py
test_contracts_providers.py    test_schema_migration.py
test_contracts_retrieval.py    test_schemas.py
test_contracts_storage.py      test_schemas_api.py
test_document_parser.py        test_settings_router.py
test_documents_router.py       test_sqlite_db.py
test_edges.py                  test_stage_timings.py
test_embedder.py               test_stage_timings_db.py
test_error_contracts.py        test_trace_context.py
test_health_router.py          test_traces_router.py
test_hybrid_searcher.py        test_incremental.py
test_ingest_router.py          test_ingestion_api.py
test_ingestion_pipeline.py     test_key_manager.py
test_main_security.py          test_meta_reasoning_edges.py
test_models_router.py
```

**`tests/unit/api/`:**
```
test_chat_security.py   test_ingest_security.py
test_metrics.py         test_providers_security.py
test_traces_stage_timings.py
```

**`tests/unit/retrieval/`:**
```
test_searcher_security.py
```

**`tests/integration/` (20 files):**
```
test_api_integration.py        test_providers_integration.py
test_app_startup.py            test_rate_limiting.py
test_accuracy_integration.py   test_research_graph.py
test_concurrent_reads.py       test_schema_validation.py
test_concurrent_streams.py     test_storage_integration.py
test_conversation_graph.py     test_us1_e2e.py
test_error_handlers.py         test_us3_streaming.py
test_ingestion_pipeline.py     test_us4_traces.py
test_meta_reasoning_graph.py   test_ndjson_streaming.py
test_performance.py
```

**`tests/regression/test_regression.py`** — do not touch.

**`tests/mocks.py`** — provides `build_mock_research_graph()` and `build_simple_chat_graph()`. Do not modify.

**`tests/integration/conftest.py`** — contains only `unique_name()` helper. Do not modify.

---

## What Spec-16 Creates — New Files Only

```
tests/
  conftest.py                          # NEW — 4 shared fixtures (P1)
  pytest.ini                           # NEW — markers + coverage gate (Wave 4)
  unit/
    test_reranker.py                   # NEW — Reranker class unit tests (P2, A2)
    test_score_normalizer.py           # NEW — normalize_scores() unit tests (P2, A2)
    test_storage_chunker.py            # NEW — chunk_text() unit tests (P2, A2)
    test_storage_indexing.py           # NEW — index_chunks() unit tests (P2, A3)
    test_errors.py                     # NEW — EmbeddinatorError hierarchy tests (P2, A3)
  e2e/
    __init__.py                        # NEW
    test_ingest_e2e.py                 # NEW — full ingest pipeline E2E (P3, A4)
    test_chat_e2e.py                   # NEW — full chat flow E2E (P3, A4)
    test_collection_e2e.py             # NEW — collection CRUD E2E (P3, A4)
  integration/
    test_qdrant_integration.py         # NEW — Qdrant CRUD via QdrantStorage (P4, A5)
    test_hybrid_search.py              # NEW — hybrid search end-to-end (P4, A5)
    test_circuit_breaker.py            # NEW — circuit breaker under real I/O (P4, A5)
  fixtures/
    sample.pdf                         # NEW — committed binary, valid PDF < 50 KB (P5, A6)
    sample.md                          # NEW — committed Markdown file (P5, A6)
    sample.txt                         # NEW — committed plain text file (P5, A6)

Docs/PROMPTS/spec-16-testing/agents/
  a1-instructions.md                   # Created by orchestrator before Wave 1
  a2-instructions.md                   # Created by A1 for Wave 2
  a3-instructions.md                   # Created by A1 for Wave 2
  a4-instructions.md                   # Created by A1 for Wave 3
  a5-instructions.md                   # Created by A1 for Wave 3
  a6-instructions.md                   # Created by A1 for Wave 4
  a7-instructions.md                   # Created by A1 for Wave 5
```

---

## Test Runner Rules — MANDATORY

> These rules are absolute. Every agent must follow them. Violations will cause silent failures or incorrect test results.

**Rule 1 — NEVER run pytest directly inside Claude Code.**

Wrong:
```
pytest tests/unit/
.venv/bin/pytest tests/unit/
python -m pytest tests/unit/
```

Correct:
```bash
zsh scripts/run-tests-external.sh -n <run-name> <target>
```

**Rule 2 — Always use a descriptive run name with `-n`.**
```bash
zsh scripts/run-tests-external.sh -n spec16-baseline tests/
zsh scripts/run-tests-external.sh -n spec16-unit-a2 tests/unit/test_reranker.py
zsh scripts/run-tests-external.sh -n spec16-e2e tests/e2e/
zsh scripts/run-tests-external.sh -n spec16-integ tests/integration/test_qdrant_integration.py
```

**Rule 3 — Poll status, never read the full log.**
```bash
# Check completion (1 line):
cat Docs/Tests/<name>.status        # → RUNNING | PASSED | FAILED | ERROR | NO_TESTS

# Read summary when done (~20 lines):
cat Docs/Tests/<name>.summary

# Debug specific failures only:
grep "FAILED" Docs/Tests/<name>.log
grep -A 10 "test_name_here" Docs/Tests/<name>.log
```

**Rule 4 — Use `--no-cov` for speed during development; run with coverage for final validation.**
```bash
# Fast iteration (no coverage):
zsh scripts/run-tests-external.sh -n quick --no-cov tests/unit/test_reranker.py

# Full validation with coverage gate:
zsh scripts/run-tests-external.sh -n spec16-final tests/
```

**Rule 5 — Run Docker-dependent tests explicitly by marker when Qdrant is available.**
```bash
zsh scripts/run-tests-external.sh -n spec16-docker -m "require_docker" tests/integration/
```

**Rule 6 — DO NOT recreate any test file listed in the "What Already Exists" section.**

---

## Technical Approach

### P1 — Shared Fixtures (`tests/conftest.py`)

Create `tests/conftest.py` with exactly these 4 fixtures plus the Docker-skip hook:

```python
"""Shared fixtures for all test modules."""
import socket
import pytest
import pytest_asyncio
from backend.storage.sqlite_db import SQLiteDB
from backend.agent.schemas import RetrievedChunk


def _is_docker_qdrant_available() -> bool:
    """Check if Qdrant is reachable on localhost:6333."""
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=1):
            return True
    except OSError:
        return False


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "require_docker: skip if Qdrant is not running on localhost:6333"
    )
    config.addinivalue_line(
        "markers", "e2e: end-to-end tests that start the full application stack"
    )


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker("require_docker") and not _is_docker_qdrant_available():
        pytest.skip("Qdrant not available on localhost:6333 — start Docker first")


@pytest_asyncio.fixture
async def db():
    """In-memory SQLite database, freshly connected and closed per test."""
    instance = SQLiteDB(":memory:")
    await instance.connect()
    yield instance
    await instance.close()


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """A small list of realistic RetrievedChunk objects for use in tests."""
    return [
        RetrievedChunk(
            id="chunk-001",
            content="Paris is the capital of France and a major European city.",
            score=0.92,
            collection="test-collection",
            document_id="doc-001",
            chunk_index=0,
            parent_id=None,
            metadata={},
        ),
        RetrievedChunk(
            id="chunk-002",
            content="The Eiffel Tower was built in 1889 for the World's Fair.",
            score=0.78,
            collection="test-collection",
            document_id="doc-001",
            chunk_index=1,
            parent_id=None,
            metadata={},
        ),
        RetrievedChunk(
            id="chunk-003",
            content="France is a republic with a president as head of state.",
            score=0.65,
            collection="test-collection",
            document_id="doc-002",
            chunk_index=0,
            parent_id=None,
            metadata={},
        ),
    ]


@pytest.fixture
def mock_llm():
    """Mock LangChain chat model returning predictable AIMessage objects."""
    from unittest.mock import AsyncMock, MagicMock
    from langchain_core.messages import AIMessage

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="This is a test answer."))
    llm.with_structured_output = MagicMock(return_value=llm)
    llm.astream = AsyncMock(return_value=iter([AIMessage(content="Test")]))
    return llm


@pytest.fixture
def mock_qdrant_results() -> list[dict]:
    """Mock raw Qdrant search results (list of dicts matching ScoredPoint shape)."""
    return [
        {
            "id": "chunk-001",
            "score": 0.92,
            "payload": {
                "content": "Paris is the capital of France.",
                "collection": "test-collection",
                "document_id": "doc-001",
                "chunk_index": 0,
            },
        },
        {
            "id": "chunk-002",
            "score": 0.78,
            "payload": {
                "content": "The Eiffel Tower was built in 1889.",
                "collection": "test-collection",
                "document_id": "doc-001",
                "chunk_index": 1,
            },
        },
    ]
```

**Critical constraints for the `db` fixture:**
- Use `SQLiteDB(":memory:")` — never a path to `data/embedinator.db` (old schema)
- Call `await instance.connect()` — NOT `await instance.initialize()` (method does not exist)
- Use `@pytest_asyncio.fixture` — not `@pytest.fixture` — for async fixtures
- `yield` the instance, then `await instance.close()` for teardown

### P2 — 5 Missing Unit Test Files

All 5 new files go in `tests/unit/` (flat, matching the existing structure). Do NOT create subdirectories under `tests/unit/` for these files.

**Verified production module names (use these exactly):**

| New Test File | Production Module | Key Symbol |
|---|---|---|
| `test_reranker.py` | `backend/retrieval/reranker.py` | `class Reranker` |
| `test_score_normalizer.py` | `backend/retrieval/score_normalizer.py` | `def normalize_scores()` |
| `test_storage_chunker.py` | `backend/storage/chunker.py` | `def chunk_text()` |
| `test_storage_indexing.py` | `backend/storage/indexing.py` | `async def index_chunks()` |
| `test_errors.py` | `backend/errors.py` | `class EmbeddinatorError` + 10 subclasses |

**`test_reranker.py`** — tests for `Reranker` class:
- Import as `from backend.retrieval.reranker import Reranker`
- `Reranker.__init__` takes a `Settings` instance; use lazy import pattern (sentence_transformers is lazy — do not call `.rank()` in unit tests without mocking the model)
- Test: initialization stores settings; `rerank()` method (or equivalent public method) calls the underlying model; graceful failure when model unavailable raises `RerankerError`
- Mock the underlying cross-encoder model via `unittest.mock.patch` — do not load real sentence_transformers weights in unit tests

**`test_score_normalizer.py`** — tests for `normalize_scores()` function:
- Import as `from backend.retrieval.score_normalizer import normalize_scores`
- `normalize_scores` is a **function**, not a class — do not instantiate it
- Test: empty list returns empty list; single-item list returns same item; all equal scores produce valid output; min score maps to 0.0, max to 1.0; preserves order

**`test_storage_chunker.py`** — tests for `chunk_text()` function:
- Import as `from backend.storage.chunker import chunk_text`
- `chunk_text` is a **function**, not a class — do not instantiate it
- Test: empty string returns empty list; short text below chunk size returns single chunk; long text produces multiple chunks; chunks respect overlap parameter; no chunk exceeds max size

**`test_storage_indexing.py`** — tests for `index_chunks()` async function:
- Import as `from backend.storage.indexing import index_chunks`
- `index_chunks(app, doc_id, chunks)` takes an app object with `state.db` and `state.qdrant` — use mocked app
- Test: calls `db.create_parent_chunk()` for each chunk; calls `qdrant.batch_upsert()` with correct vectors; handles empty chunk list gracefully; propagates storage errors

**`test_errors.py`** — tests for `backend/errors.py` exception hierarchy:
- Import all 11 classes: `EmbeddinatorError`, `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`, `CircuitOpenError`
- Do NOT test `ProviderRateLimitError` — it lives in `backend/providers/base.py`, not `errors.py`
- Test: all subclasses inherit from `EmbeddinatorError`; each can be raised and caught as `EmbeddinatorError`; each can be raised and caught as its specific type; `EmbeddinatorError` is itself an `Exception`; each carries a meaningful string representation

### P3 — Backend E2E Tests (`tests/e2e/`)

These are **Python pytest tests** using `httpx.AsyncClient` and `TestClient` — NOT TypeScript Playwright tests. The existing Playwright tests are in `frontend/tests/e2e/` and must not be touched.

All E2E tests:
1. Use `@pytest.mark.e2e` marker
2. Use fixture teardown that **always** runs, even on test failure — use `pytest_asyncio.fixture` with `try/finally` or `yield` in fixtures (never `setup/teardown` methods)
3. Spin up the FastAPI application in-process using `httpx.AsyncClient(app=app, base_url="http://test")`
4. Use `:memory:` SQLite and mock Qdrant/LLM dependencies — no external services required

**Teardown guarantee pattern:**
```python
@pytest_asyncio.fixture
async def test_app():
    """Application fixture with guaranteed teardown."""
    # setup
    app = create_app_for_testing()
    client = httpx.AsyncClient(app=app, base_url="http://test")
    try:
        yield client
    finally:
        # teardown always runs — even if the test raises
        await client.aclose()
        # clean up any state created during test
```

**Three E2E test files:**

`test_ingest_e2e.py` — POST `/ingest`, poll job status, verify document appears in `/documents`:
- Creates a collection, posts a file, verifies job reaches terminal status

`test_chat_e2e.py` — POST `/chat`, streams NDJSON response, verifies event types in correct order:
- Verifies `retrieval_complete`, `answer_chunk`, and `done` events appear in the stream

`test_collection_e2e.py` — POST/GET/DELETE `/collections`, verifies lifecycle:
- Creates, reads, and deletes a collection; verifies 404 after deletion

### P4 — Docker-Dependent Integration Tests

All three new integration test files use `@pytest.mark.require_docker`. The skip behavior is automatic via the `pytest_runtest_setup` hook in `tests/conftest.py` — no manual skip calls in the test files themselves.

These tests connect to a real Qdrant instance at `localhost:6333`. They do NOT use `testcontainers` (package is not installed). To run them, start Qdrant via Docker first:
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**`test_qdrant_integration.py`** — tests `QdrantStorage` CRUD operations:
- Import as `from backend.storage.qdrant_client import QdrantStorage`
- Uses `QdrantStorage(host="localhost", port=6333)`
- Tests: `create_collection()`, `batch_upsert()`, `search_hybrid()`, `delete_collection()`
- Uses `unique_name()` from `tests/integration/conftest.py` for collection names to avoid conflicts
- Always deletes test collections in fixture teardown (use `yield` + `await storage.delete_collection()`)

**`test_hybrid_search.py`** — tests `HybridSearcher` against real Qdrant:
- Import as `from backend.retrieval.searcher import HybridSearcher`
- Seeds Qdrant with known vectors, then runs `HybridSearcher.search()`, verifies results ranked by score
- Tests dense-only, sparse-only, and hybrid modes

**`test_circuit_breaker.py`** — tests Qdrant circuit breaker behavior:
- Verifies `QdrantStorage._check_circuit()` opens after repeated failures
- Verifies `CircuitOpenError` (from `backend/errors.py`) is raised when circuit is open
- Tests reset after timeout

### P5 — Committed Binary Fixture Files (`tests/fixtures/`)

Create `tests/fixtures/` directory with three static files committed to git:

**`tests/fixtures/sample.pdf`**: A valid, minimal PDF file under 50 KB. Must be a real PDF (magic bytes `%PDF`), not a renamed text file. The ingestion pipeline validates magic bytes and will reject a fake PDF.

**`tests/fixtures/sample.md`**: A Markdown file with headings, a list, a code block, and body text. Used for chunker and ingestion tests.

**`tests/fixtures/sample.txt`**: Plain text with multiple paragraphs. Used for basic ingestion tests.

These files are static assets — commit them as binary blobs. Do not generate them at test runtime.

---

## Key Technical Patterns

### Correct Class and Function Names

```python
# Reranker — it IS a class, NOT CrossEncoderReranker
from backend.retrieval.reranker import Reranker

# normalize_scores — it IS a function, NOT ScoreNormalizer (no class)
from backend.retrieval.score_normalizer import normalize_scores

# chunk_text — function
from backend.storage.chunker import chunk_text

# index_chunks — async function
from backend.storage.indexing import index_chunks

# QdrantStorage — class in qdrant_client.py (not qdrant_storage.py)
from backend.storage.qdrant_client import QdrantStorage

# SQLiteDB — class with connect() method
from backend.storage.sqlite_db import SQLiteDB

# EmbeddinatorError hierarchy (all in backend/errors.py)
from backend.errors import (
    EmbeddinatorError, QdrantConnectionError, OllamaConnectionError,
    SQLiteError, LLMCallError, EmbeddingError, IngestionError,
    SessionLoadError, StructuredOutputParseError, RerankerError, CircuitOpenError,
)

# ProviderRateLimitError — NOT in errors.py, lives in providers/base.py
from backend.providers.base import ProviderRateLimitError
```

### SQLiteDB Fixture Pattern

```python
# CORRECT — always use :memory: and await connect()
@pytest_asyncio.fixture
async def db():
    instance = SQLiteDB(":memory:")
    await instance.connect()          # NOT initialize()
    yield instance
    await instance.close()

# WRONG — never use the real data/embedinator.db (old schema)
# WRONG — never call await instance.initialize()
```

### pytest.ini for Markers and Coverage Gate

Create `pytest.ini` at the project root (`src/pytest.ini` if the project root is `src/`, otherwise at repo root alongside `scripts/`):

```ini
[pytest]
asyncio_mode = auto
markers =
    e2e: end-to-end tests requiring full application stack
    require_docker: tests requiring Qdrant running on localhost:6333
addopts =
    --cov=backend
    --cov-report=term-missing
    --cov-fail-under=80
```

The `--cov-fail-under=80` is the hard gate — the suite exits non-zero if coverage drops below 80%. Agents running with `--no-cov` bypass this gate intentionally (for fast iteration). The final validation run must NOT use `--no-cov`.

### Logger Pattern (if any test needs to verify logging)

```python
# All production loggers use:
structlog.get_logger().bind(component=__name__)
# NOT:
structlog.get_logger(__name__)  # WRONG — PrintLoggerFactory drops positional args
```

### LangGraph Checkpointer in Tests

```python
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()   # CORRECT
# NOT AsyncMock() — LangGraph validates the checkpointer interface strictly
```

### Async Test Functions

```python
import pytest
import pytest_asyncio

# Mark async tests — with asyncio_mode = auto in pytest.ini, no decorator needed
# But adding it explicitly is always safe:
@pytest.mark.asyncio
async def test_something(db):
    result = await db.create_collection("test", "desc")
    assert result is not None
```

### Docker-Skip Marker Usage

```python
# In integration tests (NOT in conftest.py — the hook handles skipping automatically):
@pytest.mark.require_docker
@pytest.mark.asyncio
async def test_qdrant_create_collection():
    storage = QdrantStorage(host="localhost", port=6333)
    # test body — this only runs when Qdrant is available
```

---

## Agent Team Wave Structure

Implementation uses 5 waves of Agent Teams with the pattern established in specs 07–15.

### Wave 1 — A1 (quality-engineer, Opus)

**Goal**: Scaffold test infrastructure; create instruction files for all downstream agents.

**Tasks**:
1. Run baseline suite to confirm 1405 tests passing:
   ```bash
   zsh scripts/run-tests-external.sh -n spec16-baseline --no-cov tests/
   ```
   Verify status = PASSED and extract the test count from the summary.
2. Verify the 5 production modules exist at exact paths:
   - `backend/retrieval/reranker.py` → contains `class Reranker`
   - `backend/retrieval/score_normalizer.py` → contains `def normalize_scores`
   - `backend/storage/chunker.py` → contains `def chunk_text`
   - `backend/storage/indexing.py` → contains `async def index_chunks`
   - `backend/errors.py` → contains `class EmbeddinatorError` + 10 subclasses
3. Create `tests/conftest.py` with the 4 shared fixtures as specified in the Technical Approach section (P1).
4. Create `tests/fixtures/` directory (empty; A6 populates it).
5. Create `pytest.ini` at the project root with asyncio_mode, markers, and coverage addopts.
6. Create `Docs/PROMPTS/spec-16-testing/agents/` directory.
7. Write instruction files `a2-instructions.md` through `a7-instructions.md` for downstream agents.
8. Run unit suite to confirm conftest.py does not break existing tests:
   ```bash
   zsh scripts/run-tests-external.sh -n spec16-after-conftest --no-cov tests/unit/
   ```

**Gate before Wave 2**: `spec16-after-conftest.status` must be PASSED.

### Wave 2 — A2 + A3 (python-expert, Sonnet, parallel)

**Goal**: Write the 5 missing unit test files. A2 and A3 work on different files — no overlap.

**A2 — 3 unit test files**:
- `tests/unit/test_reranker.py` — tests for `Reranker` class
- `tests/unit/test_score_normalizer.py` — tests for `normalize_scores()` function
- `tests/unit/test_storage_chunker.py` — tests for `chunk_text()` function

After writing all 3 files, A2 runs:
```bash
zsh scripts/run-tests-external.sh -n spec16-a2 --no-cov \
  tests/unit/test_reranker.py tests/unit/test_score_normalizer.py tests/unit/test_storage_chunker.py
```
All tests must pass before A2 finishes.

**A3 — 2 unit test files**:
- `tests/unit/test_storage_indexing.py` — tests for `index_chunks()` async function
- `tests/unit/test_errors.py` — tests for `EmbeddinatorError` hierarchy

After writing both files, A3 runs:
```bash
zsh scripts/run-tests-external.sh -n spec16-a3 --no-cov \
  tests/unit/test_storage_indexing.py tests/unit/test_errors.py
```
All tests must pass before A3 finishes.

**Gate before Wave 3**: Both A2 and A3 runs must be PASSED.

### Wave 3 — A4 + A5 (python-expert, Sonnet, parallel)

**Goal**: Write E2E tests and Docker-dependent integration tests. A4 and A5 work in different directories.

**A4 — 3 E2E test files in `tests/e2e/`**:
- Create `tests/e2e/__init__.py`
- `tests/e2e/test_ingest_e2e.py` — full ingest pipeline E2E
- `tests/e2e/test_chat_e2e.py` — full chat flow with NDJSON streaming
- `tests/e2e/test_collection_e2e.py` — collection CRUD lifecycle

All tests use `@pytest.mark.e2e`. All fixtures use `yield` with `try/finally` for guaranteed teardown.

A4 runs with the e2e marker:
```bash
zsh scripts/run-tests-external.sh -n spec16-a4 --no-cov -m "e2e" tests/e2e/
```

**A5 — 3 integration test files in `tests/integration/`**:
- `tests/integration/test_qdrant_integration.py` — QdrantStorage CRUD against real Qdrant
- `tests/integration/test_hybrid_search.py` — HybridSearcher with real Qdrant
- `tests/integration/test_circuit_breaker.py` — circuit breaker under real I/O

All tests use `@pytest.mark.require_docker`. The skip hook in `tests/conftest.py` handles auto-skip when Qdrant is unavailable.

A5 verifies the auto-skip works:
```bash
# When Qdrant is NOT running, these should all show as skipped (not failed):
zsh scripts/run-tests-external.sh -n spec16-a5-skip --no-cov tests/integration/test_qdrant_integration.py
# Check: grep "skipped" Docs/Tests/spec16-a5-skip.summary
```

**Gate before Wave 4**: A4 run must be PASSED. A5 run must be PASSED or show all `require_docker` tests as skipped.

### Wave 4 — A6 (python-expert, Sonnet)

**Goal**: Create committed binary fixture files; finalize `pytest.ini` coverage gate.

**Tasks**:
1. Create `tests/fixtures/sample.pdf` — a minimal valid PDF (starts with `%PDF-1.4` magic bytes, contains readable text). Must be < 50 KB. This is a real binary file committed to git.
2. Create `tests/fixtures/sample.md` — Markdown with headings, list items, a fenced code block, and prose paragraphs.
3. Create `tests/fixtures/sample.txt` — plain text with 3+ paragraphs and 500+ words.
4. Verify `pytest.ini` has `--cov-fail-under=80` in addopts (add if A1 omitted it).
5. Run the coverage check to confirm the gate fires correctly:
   ```bash
   zsh scripts/run-tests-external.sh -n spec16-coverage tests/unit/
   ```
   Verify the summary shows a coverage percentage. If the percentage is below 80%, this is expected to fail — confirm the gate is working.

**Gate before Wave 5**: All fixture files committed; `pytest.ini` confirmed correct.

### Wave 5 — A7 (quality-engineer, Sonnet)

**Goal**: Full suite validation — confirm all SCs pass, 0 regressions.

**Tasks**:
1. Run the complete suite:
   ```bash
   zsh scripts/run-tests-external.sh -n spec16-final tests/
   ```
2. Extract the test count from the summary. Confirm it is >= 1405 (the pre-spec baseline).
3. Confirm 0 new failures compared to the pre-existing 39 failure baseline (listed in the Acceptance Criteria section below).
4. Verify the `@pytest.mark.require_docker` auto-skip works when Qdrant is not running:
   ```bash
   # With Qdrant stopped, all 3 require_docker test files should skip:
   grep "skipped" Docs/Tests/spec16-final.summary
   ```
5. Run the E2E tests explicitly to confirm they pass:
   ```bash
   zsh scripts/run-tests-external.sh -n spec16-e2e --no-cov -m "e2e" tests/e2e/
   ```
6. If the coverage gate fires (< 80%), investigate which modules lack coverage and report — do NOT lower the threshold.
7. Write a brief validation report to `specs/016-testing-strategy/validation-report.md` summarizing: final test count, coverage %, new test breakdown by file, SC pass/fail status.

---

## Agent Instruction File Specifications

Each instruction file at `Docs/PROMPTS/spec-16-testing/agents/` must contain:

**Common sections in every instruction file**:
- Role and model assignment
- Assigned tasks (explicit list, not prose)
- The MANDATORY test runner rule: "NEVER run pytest directly; ALWAYS use `zsh scripts/run-tests-external.sh -n <name> <target>`"
- Gate conditions (what must be true before proceeding)
- How to signal completion (update `Docs/Tests/<run-name>.status` indirectly by running the script)

**a1-instructions.md** must include:
- Baseline test count verification procedure
- Exact content of `tests/conftest.py` (copy from this plan's P1 section)
- Exact content of `pytest.ini`
- Instructions to create all other agent instruction files (a2 through a7) before finishing
- Gate: suite must still pass after conftest.py is created

**a2-instructions.md** must include:
- Names and descriptions of the 3 test files (reranker, score_normalizer, storage_chunker)
- Warning: `normalize_scores` is a function, not a class — do not instantiate it
- Warning: `Reranker.__init__` lazy-loads sentence_transformers — mock the model in unit tests
- Warning: `chunk_text` is a function — do not instantiate it
- Test run gate command

**a3-instructions.md** must include:
- Names and descriptions of the 2 test files (storage_indexing, errors)
- Warning: `index_chunks` is async and takes `(app, doc_id, chunks)` — mock `app.state.db` and `app.state.qdrant`
- Warning: test_errors.py covers only `backend/errors.py` — NOT `ProviderRateLimitError` which is in `backend/providers/base.py`
- Complete list of 11 classes in `backend/errors.py`
- Test run gate command

**a4-instructions.md** must include:
- Clarification that E2E tests are Python pytest (not TypeScript Playwright)
- The teardown guarantee pattern (try/finally in fixtures)
- The `@pytest.mark.e2e` requirement for all E2E test functions
- That tests use `httpx.AsyncClient` in-process — no running server required
- Test run gate command using `-m "e2e"`

**a5-instructions.md** must include:
- Warning: `testcontainers` is NOT installed — do not import it
- That tests connect to Qdrant on `localhost:6333` directly
- The `@pytest.mark.require_docker` requirement for all test functions
- That the skip hook is already in `tests/conftest.py` — no manual `pytest.skip()` calls needed in test functions
- How to use `unique_name()` from `tests/integration/conftest.py`
- Test run gate command verifying auto-skip behavior

**a6-instructions.md** must include:
- That `sample.pdf` must start with `%PDF` magic bytes (the ingestion pipeline validates this)
- Size limit: sample.pdf must be < 50 KB
- That `sample.md` must have headings (`##`, `###`), a list, a code block, and prose
- That all 3 files must be committed to git as binary assets (not generated at runtime)
- Coverage gate verification procedure

**a7-instructions.md** must include:
- The baseline of 39 pre-existing failures (listed below) — any new failure is a regression
- The exact final test count to verify (>= 1405)
- How to write the validation report at `specs/016-testing-strategy/validation-report.md`
- Escalation procedure if coverage < 80% (report, do not lower threshold)

---

## Acceptance Criteria

These map directly to the spec's success criteria (SC-001 through SC-008).

| SC | Criterion | Verified by |
|---|---|---|
| SC-001 | `tests/conftest.py` exists with `db`, `sample_chunks`, `mock_llm`, `mock_qdrant_results` fixtures | A1 + A7 |
| SC-002 | All 5 new unit test files exist and all their tests pass | A2 + A3 + A7 |
| SC-003 | All 3 E2E test files exist in `tests/e2e/`, use `@pytest.mark.e2e`, and pass | A4 + A7 |
| SC-004 | All 3 Docker integration test files use `@pytest.mark.require_docker` and auto-skip when Qdrant is unavailable | A5 + A7 |
| SC-005 | `tests/fixtures/sample.pdf` is a valid PDF < 50 KB, `sample.md` and `sample.txt` exist | A6 + A7 |
| SC-006 | `pytest.ini` registers `e2e` and `require_docker` markers; no `PytestUnknownMarkWarning` in suite output | A1 + A7 |
| SC-007 | Coverage hard gate: `--cov-fail-under=80` in `pytest.ini`; suite exits non-zero if coverage < 80% | A6 + A7 |
| SC-008 | Total passing tests >= 1405 (pre-spec baseline); 0 new failures introduced | A7 |

---

## Pre-existing Failure Baseline

These 39 test failures exist before spec-16 work begins. They are known and must remain unchanged — any new failure beyond this list is a regression introduced by spec-16.

A7 must confirm that after all spec-16 work is complete, the failure list has not grown. Do not attempt to fix pre-existing failures as part of this spec.

To extract the current failure list before beginning:
```bash
zsh scripts/run-tests-external.sh -n spec16-prefail-check --no-cov tests/
grep "FAILED" Docs/Tests/spec16-prefail-check.log
```

The exact 39 failures are those present on the `015-observability` branch at the start of spec-16 implementation. A1 must record this list in `a7-instructions.md` after running the baseline check.
