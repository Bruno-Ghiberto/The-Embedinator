# Spec 16: Testing Strategy — Implementation Context

**Status**: Ready for implementation
**Branch**: `016-testing-strategy`
**No production code is modified.** All changes are test infrastructure only.

---

## MANDATORY: tmux Multi-Pane Agent Spawning

Agent Teams for this spec use 5 waves with parallel agents in Waves 2 and 3. Each agent spawned by the orchestrator automatically gets its own tmux pane. This is NOT optional — without tmux, parallel agents cannot run independently.

**Before spawning any agent**, confirm you are inside a tmux session:
```bash
echo $TMUX   # must print a non-empty string
```

**Spawning pattern** (orchestrator uses this for each wave):
- Read the agent instruction file at its path FIRST, then execute all assigned tasks.
- Spawn Wave 2 agents (A2, A3) simultaneously — they write different files with no shared state.
- Spawn Wave 3 agents (A4, A5) simultaneously after Wave 2 gates pass — different directories.
- Do NOT spawn Wave 4 (A6) until both Wave 3 gate `.status` files show PASSED.
- Do NOT spawn Wave 5 (A7) until Wave 4 gate `.status` file shows PASSED.

**Gate verification** between waves:
```bash
cat Docs/Tests/spec16-scaffold.status   # must be PASSED before Wave 2 starts
cat Docs/Tests/spec16-a2.status         # must be PASSED before Wave 3 starts
cat Docs/Tests/spec16-a3.status         # must be PASSED before Wave 3 starts
cat Docs/Tests/spec16-a4.status         # must be PASSED before Wave 4 starts
```

---

## MANDATORY: Test Runner Rule

NEVER run `pytest` directly. ALL test invocations MUST use the external runner script.

```bash
# Correct form:
zsh scripts/run-tests-external.sh -n <name> [--no-cov] [target]

# Read results from:
cat Docs/Tests/<name>.status    # PASSED or FAILED
cat Docs/Tests/<name>.summary   # counts, coverage %
cat Docs/Tests/<name>.log       # full pytest output
```

**Why**: The script sets `cd "$PROJECT_ROOT"`, discovers `pytest.ini`, and writes structured output to `Docs/Tests/`. Running pytest from an arbitrary working directory will fail to discover configuration.

**Common commands**:
```bash
# Unit tests only (fast, no coverage gate)
zsh scripts/run-tests-external.sh -n spec16-unit --no-cov tests/unit/

# E2E tests (must pass the e2e marker)
zsh scripts/run-tests-external.sh -n spec16-e2e --no-cov -m "e2e" tests/e2e/

# Docker integration tests (Qdrant must be running)
zsh scripts/run-tests-external.sh -n spec16-docker --no-cov -m "require_docker" tests/integration/

# Full suite with coverage gate
zsh scripts/run-tests-external.sh -n spec16-final tests/

# Check coverage line in summary
grep "TOTAL" Docs/Tests/spec16-final.summary
```

---

## Agent Team Structure

5-wave implementation. Waves 2 and 3 run in parallel pairs.

```
Wave 1 (A1/Opus — quality-engineer):
  T001–T011 — baseline verification, directory scaffold, tests/conftest.py, pytest.ini
  Gate run: zsh scripts/run-tests-external.sh -n spec16-scaffold --no-cov tests/unit/
  Unblocks: Wave 2 AND Wave 3 (both depend on conftest.py + pytest.ini)

     ↓ GATE: Docs/Tests/spec16-scaffold.status = PASSED

Wave 2 — parallel pair (A2 + A3 / Sonnet):
  A2 (T012–T014, T017): tests/unit/test_reranker.py, test_score_normalizer.py, test_storage_chunker.py
  A3 (T015–T016, T018): tests/unit/test_storage_indexing.py, test_errors.py

     ↓ GATE: spec16-a2.status = PASSED AND spec16-a3.status = PASSED

Wave 3 — parallel pair (A4 + A5 / Sonnet):
  A4 (T019–T023): tests/e2e/__init__.py + 4 E2E test files
  A5 (T024–T027): tests/integration/ — 3 Docker integration test files + skip verification

     ↓ GATE: spec16-a4.status = PASSED AND spec16-a5-skip check shows skips not failures

Wave 4 (A6 / Sonnet — python-expert):
  T028–T031 — tests/fixtures/ (sample.pdf, sample.md, sample.txt) + coverage gate verification

     ↓ GATE: all 3 fixture files committed to git; pytest.ini coverage gate confirmed

Wave 5 (A7 / Sonnet — quality-engineer):
  T032–T038, T034b — full suite validation, SC verification, validation report
```

---

## Implementation Scope

### Files to Create

These are the ONLY files spec-16 creates. No production code is modified.

**Shared infrastructure**:
- `tests/conftest.py` — shared fixtures + marker hooks
- `pytest.ini` — at project root (NOT in src/, NOT in pyproject.toml)

**Unit test files** (5 new files, all in `tests/unit/`):
- `tests/unit/test_reranker.py`
- `tests/unit/test_score_normalizer.py`
- `tests/unit/test_storage_chunker.py`
- `tests/unit/test_storage_indexing.py`
- `tests/unit/test_errors.py`

**Backend E2E test files** (Python pytest, in-process ASGI):
- `tests/e2e/__init__.py`
- `tests/e2e/test_ingest_e2e.py`
- `tests/e2e/test_chat_e2e.py`
- `tests/e2e/test_collection_e2e.py`
- `tests/e2e/test_observability_e2e.py`

**Docker integration test files**:
- `tests/integration/test_qdrant_integration.py`
- `tests/integration/test_hybrid_search.py`
- `tests/integration/test_circuit_breaker.py`

**Fixture files** (committed static assets):
- `tests/fixtures/sample.pdf` — valid PDF binary, < 50 KB
- `tests/fixtures/sample.md` — Markdown with headings, list, code block, prose
- `tests/fixtures/sample.txt` — plain UTF-8, 500+ words

**NOT created by spec-16**:
- No `playwright.config.ts` — backend E2E uses Python pytest, not Playwright
- No `.spec.ts` files — TypeScript Playwright tests are frontend-only, already in `frontend/tests/e2e/`
- No `requirements-dev.txt` — all test packages are already installed
- No `tests/integration/conftest.py` changes — it already exists with only `unique_name()`

---

## Code Specifications

### tests/conftest.py

The complete shared fixture file. Every section is required.

```python
"""Shared test fixtures for The Embedinator backend tests."""

import socket
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage

from backend.storage.sqlite_db import SQLiteDB
from backend.agent.schemas import RetrievedChunk


def _is_docker_qdrant_available() -> bool:
    """Check if Qdrant is reachable on localhost:6333 via socket."""
    try:
        with socket.create_connection(("127.0.0.1", 6333), timeout=1):
            return True
    except OSError:
        return False


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "e2e: backend Python E2E tests using in-process ASGI"
    )
    config.addinivalue_line(
        "markers", "require_docker: tests requiring Qdrant on localhost:6333"
    )


def pytest_runtest_setup(item):
    if item.get_closest_marker("require_docker") and not _is_docker_qdrant_available():
        pytest.skip("Qdrant not available on localhost:6333")


@pytest_asyncio.fixture
async def db():
    """Isolated in-memory SQLiteDB. MUST use connect(), not initialize()."""
    instance = SQLiteDB(":memory:")
    await instance.connect()
    yield instance
    await instance.close()


@pytest.fixture
def sample_chunks() -> list[RetrievedChunk]:
    """Pre-built list[RetrievedChunk] with 3 items, scores [0.92, 0.78, 0.65]."""
    return [
        RetrievedChunk(
            chunk_id="chunk-001",
            text="Authentication requires a valid certificate from the WSAA service.",
            source_file="test-document.pdf",
            page=1,
            breadcrumb="Section 1 > Authentication",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.92,
            sparse_score=0.75,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-002",
            text="Token validation uses SAML 2.0 assertions for authorization.",
            source_file="test-document.pdf",
            page=2,
            breadcrumb="Section 1 > Tokens",
            parent_id="parent-001",
            collection="test-collection",
            dense_score=0.78,
            sparse_score=0.60,
            rerank_score=None,
        ),
        RetrievedChunk(
            chunk_id="chunk-003",
            text="Digital signatures require X.509 certificates for electronic invoicing.",
            source_file="test-document.pdf",
            page=5,
            breadcrumb="Section 2 > Invoicing",
            parent_id="parent-002",
            collection="test-collection",
            dense_score=0.65,
            sparse_score=0.48,
            rerank_score=None,
        ),
    ]


@pytest.fixture
def mock_llm():
    """MagicMock satisfying BaseChatModel interface.

    ainvoke returns AIMessage("This is a test answer.").
    with_structured_output returns self (supports chaining).
    """
    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=AIMessage(content="This is a test answer."))
    llm.with_structured_output = MagicMock(return_value=llm)
    llm.astream = AsyncMock()
    return llm


@pytest.fixture
def mock_qdrant_results() -> list[dict]:
    """Raw Qdrant result dicts matching HybridSearcher payload format.

    Payload keys: text, source_file, page, breadcrumb, parent_id, sparse_score.
    Scores: [0.92, 0.78].
    """
    return [
        {
            "id": "chunk-001",
            "score": 0.92,
            "payload": {
                "text": "Authentication requires a valid certificate from the WSAA service.",
                "source_file": "test-document.pdf",
                "page": 1,
                "breadcrumb": "Section 1 > Authentication",
                "parent_id": "parent-001",
                "sparse_score": 0.75,
            },
        },
        {
            "id": "chunk-002",
            "score": 0.78,
            "payload": {
                "text": "Token validation uses SAML 2.0 assertions for authorization.",
                "source_file": "test-document.pdf",
                "page": 2,
                "breadcrumb": "Section 1 > Tokens",
                "parent_id": "parent-001",
                "sparse_score": 0.60,
            },
        },
    ]
```

### pytest.ini (project root)

Create at `/path/to/repo/pytest.ini` — NOT in `src/`, NOT in `pyproject.toml`.

```ini
[pytest]
asyncio_mode = auto
markers =
    e2e: backend Python E2E tests (in-process ASGI via httpx)
    require_docker: tests requiring Qdrant on localhost:6333 (auto-skipped when unavailable)
addopts = --cov=backend --cov-report=term-missing --cov-fail-under=80
```

### Backend E2E Test Pattern (Python pytest — NOT Playwright)

E2E tests in `tests/e2e/` are Python pytest files using FastAPI's in-process ASGI transport. There are no `.spec.ts` files, no `playwright.config.ts`, and no browser automation in `tests/e2e/`.

```python
# tests/e2e/test_collection_e2e.py
import pytest
import pytest_asyncio
import httpx
from backend.main import app

@pytest.mark.e2e
class TestCollectionLifecycle:
    @pytest_asyncio.fixture
    async def client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as c:
            yield c
        # teardown: e.g., delete any collections created by this test

    async def test_create_list_delete(self, client):
        # POST to create
        resp = await client.post("/api/collections", json={"name": "e2e-test", "description": "test"})
        assert resp.status_code == 201
        collection_id = resp.json()["id"]

        try:
            # GET to verify
            resp = await client.get(f"/api/collections/{collection_id}")
            assert resp.status_code == 200

            # DELETE
            resp = await client.delete(f"/api/collections/{collection_id}")
            assert resp.status_code == 204

            # Verify gone
            resp = await client.get(f"/api/collections/{collection_id}")
            assert resp.status_code == 404
        finally:
            # Guarantee teardown — attempt delete even if assertions failed
            await client.delete(f"/api/collections/{collection_id}")
```

### Integration Test Pattern (require_docker — NOT testcontainers)

```python
# tests/integration/test_qdrant_integration.py
import pytest
from backend.storage.qdrant_client import QdrantStorage
from tests.integration.conftest import unique_name

@pytest.mark.require_docker
async def test_create_collection():
    """Skip automatically if Qdrant is not running on localhost:6333."""
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("crud")
    try:
        await storage.create_collection(name, vector_size=384)
        collections = await storage.list_collections()
        assert any(c["name"] == name for c in collections)
    finally:
        await storage.delete_collection(name)
```

### Observability E2E Test (T022b — mandatory)

```python
# tests/e2e/test_observability_e2e.py
import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from backend.main import app

@pytest.mark.e2e
class TestObservabilityE2E:
    @pytest_asyncio.fixture
    async def client(self):
        async with httpx.AsyncClient(app=app, base_url="http://test") as c:
            yield c

    async def test_traces_and_metrics(self, client):
        # Pre-seed: POST to /api/chat to generate at least one trace
        # Mock LLM and Qdrant so no real services are required
        with patch("backend.agent.nodes.get_llm") as mock_get_llm, \
             patch("backend.retrieval.searcher.HybridSearcher.search") as mock_search:
            mock_get_llm.return_value = MagicMock(
                ainvoke=AsyncMock(return_value=MagicMock(content="Test answer."))
            )
            mock_search.return_value = []
            # POST chat (collect NDJSON stream)
            async with client.stream("POST", "/api/chat",
                json={"message": "test question", "collection": "test"}) as resp:
                async for _ in resp.aiter_lines():
                    pass

        # Assert traces endpoint returns populated data
        resp = await client.get("/api/traces")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # Assert metrics endpoint returns required fields
        resp = await client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "circuit_breaker" in data
        assert "latency_p99" in data
```

---

## Critical Gotchas

### 1. SQLiteDB: use `connect()` not `initialize()`

`SQLiteDB` has no `initialize()` method. The method at line 103 of `backend/storage/sqlite_db.py` is `connect()`. Using `initialize()` raises `AttributeError` at test collection time.

```python
# WRONG — will raise AttributeError:
await db.initialize()

# CORRECT:
await db.connect()
```

### 2. RetrievedChunk fields — use actual Pydantic model fields

The actual `RetrievedChunk` fields (from `backend/agent/schemas.py`) are:

| Field | Type |
|-------|------|
| `chunk_id` | `str` |
| `text` | `str` |
| `source_file` | `str` |
| `page` | `int \| None` |
| `breadcrumb` | `str` |
| `parent_id` | `str` |
| `collection` | `str` |
| `dense_score` | `float` |
| `sparse_score` | `float` |
| `rerank_score` | `float \| None` |

Do NOT use: `id`, `content`, `score`, `document_id`, `chunk_index`, `metadata`. Those fields do not exist on `RetrievedChunk`.

### 3. normalize_scores is a function, not a class

```python
# CORRECT import:
from backend.retrieval.score_normalizer import normalize_scores

# WRONG — ScoreNormalizer does not exist:
from backend.retrieval.score_normalizer import ScoreNormalizer
```

### 4. ProviderRateLimitError is NOT in backend.errors

```python
# CORRECT:
from backend.providers.base import ProviderRateLimitError

# WRONG — will raise ImportError:
from backend.errors import ProviderRateLimitError
```

The `test_errors.py` file covers the 11 classes in `backend/errors.py` only. `ProviderRateLimitError` is tested separately if needed.

### 5. pytest.ini location is project root, not src/ or pyproject.toml

The test runner script does `cd "$PROJECT_ROOT"` before invoking pytest. The project root is the repo root, not `src/`. `pytest.ini` MUST be at the repo root. Do NOT add pytest configuration to `pyproject.toml`.

### 6. E2E tests are Python pytest, not Playwright TypeScript

`tests/e2e/` contains `.py` files only. Playwright tests exist in `frontend/tests/e2e/` and are out of scope for spec-16. Do NOT create `playwright.config.ts` or `.spec.ts` files anywhere in `tests/e2e/`.

### 7. testcontainers is NOT installed — use socket check

The auto-skip mechanism is a `pytest_runtest_setup` hook using `socket.create_connection`, implemented in `tests/conftest.py`. There is no `testcontainers` package. Do NOT import from `testcontainers`. Do NOT add `testcontainers` to any requirements file.

### 8. pytest markers — only `e2e` and `require_docker`

The two valid markers for spec-16 are `e2e` and `require_docker`. Do NOT use `integration`, `slow`, or `requires_ollama` — those are not registered and will generate `PytestUnknownMarkWarning`.

### 9. addopts must include --cov-fail-under=80

The `pytest.ini` `addopts` line MUST include `--cov-fail-under=80`. This is the hard coverage gate (SC-002). Omitting it makes the gate a warning-only report.

### 10. Circuit breaker None-check ordering

When testing circuit breaker state:

```python
# WRONG — None.get() raises AttributeError; getattr(None, ...) returns False (misleads):
if getattr(instance, '_circuit_open', False):
    ...

# CORRECT — check None first:
if instance is None:
    raise CircuitOpenError("No circuit breaker instance")
if getattr(instance, '_circuit_open', False):
    raise CircuitOpenError("Circuit is open")
```

### 11. mock_qdrant_results payload keys

The payload keys in `mock_qdrant_results` must match what `HybridSearcher._points_to_chunks()` reads from Qdrant `ScoredPoint` objects. From `backend/retrieval/searcher.py` lines 93–101, those keys are: `text`, `source_file`, `page`, `breadcrumb`, `parent_id`, `sparse_score`. Do NOT use `content` or `document_id` as payload keys.

### 12. Pre-existing failures must remain at exactly 39

The baseline has 39 known failing tests. After all spec-16 work, the failure count must be exactly 39 — neither more nor fewer. A7 verifies this in T034 by running `grep "FAILED" Docs/Tests/spec16-final.log | wc -l`.

---

## Done Criteria / SC Verification

All 8 SCs must pass before spec-16 is complete. A7 verifies each.

| SC | Criterion | Verification |
|----|-----------|-------------|
| SC-001 | 1405+ existing tests still pass, 0 regressions | `cat Docs/Tests/spec16-final.summary` — total >= 1405 |
| SC-002 | Backend coverage >= 80% (hard gate) | `grep "TOTAL" Docs/Tests/spec16-final.summary` — coverage line shows >= 80% |
| SC-003 | Unit suite completes under 30 seconds | Wall-clock time from `zsh scripts/run-tests-external.sh -n spec16-unit-timing --no-cov tests/unit/` |
| SC-004 | 5 new unit test files exist with passing tests | `zsh scripts/run-tests-external.sh -n spec16-us2 --no-cov tests/unit/test_reranker.py tests/unit/test_score_normalizer.py tests/unit/test_storage_chunker.py tests/unit/test_storage_indexing.py tests/unit/test_errors.py` — PASSED |
| SC-005 | 3 E2E test files marked `e2e`, excluded from default runs, pass when invoked | `zsh scripts/run-tests-external.sh -n spec16-e2e-final --no-cov -m "e2e" tests/e2e/` — PASSED |
| SC-006 | 3 integration test files pass when Docker is available | `zsh scripts/run-tests-external.sh -n spec16-docker --no-cov -m "require_docker" tests/integration/` — PASSED with Qdrant running |
| SC-007 | `tests/conftest.py` exists with all 4 fixtures importable | `python -c "from tests.conftest import db, sample_chunks, mock_llm, mock_qdrant_results"` — no ImportError |
| SC-008 | 3 fixture files in `tests/fixtures/`, committed in git, sample.pdf < 50 KB | `git ls-files tests/fixtures/` shows all 3; `python -c "p=open('tests/fixtures/sample.pdf','rb').read(); assert p[:4]==b'%PDF'"` passes |
