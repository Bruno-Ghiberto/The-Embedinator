# Research: Testing Strategy (Spec 16)

## Decision Log

### R1 — Docker Availability Check: Socket vs testcontainers

**Decision**: Use a socket-based `_is_docker_qdrant_available()` check in `tests/conftest.py`.

**Rationale**: `testcontainers` is not installed in the project. A simple `socket.create_connection(("127.0.0.1", 6333), timeout=1)` achieves the same effect: tests requiring Qdrant skip gracefully when no container is running. No new dependency required (Principle VII — Simplicity by Default).

**Alternatives Considered**:
- `testcontainers-python`: Automatic container lifecycle management, but requires installation and Docker daemon API access — adds a new dev dependency with no meaningful benefit given that the project already runs Qdrant via `docker compose`.
- `pytest-docker`: Similar to testcontainers, another new package. Rejected for same reason.

---

### R2 — Parallel Test Execution

**Decision**: Single-process only. No `pytest-xdist`.

**Rationale**: The unit suite runs in < 30 seconds single-process at current scale (1400+ tests). Introducing `pytest-xdist` would require all fixtures to be worker-isolated. The `@pytest_asyncio.fixture` event loop sharing under the current configuration is not guaranteed to be worker-safe. The risk of subtle fixture isolation bugs outweighs the speed benefit at this project scale (Principle VII).

**Alternatives Considered**:
- `pytest-xdist -n auto`: Rejected — event loop / asyncio interaction untested; risk of flaky failures.
- Parallelism at the wave level: Agent Teams already provide parallelism at the implementation level (A2 + A3 write different files simultaneously). No need for runtime parallelism.

---

### R3 — E2E Test Approach: In-Process vs Live Server

**Decision**: In-process FastAPI via `httpx.AsyncClient(app=app, base_url="http://test")`.

**Rationale**: Backend E2E tests in `tests/e2e/` are Python pytest tests, not Playwright. They exercise the full HTTP path (routing, middleware, streaming) using FastAPI's ASGI transport — no running server port needed. This is faster, more isolated, and consistent with how existing integration tests work (`test_us1_e2e.py`, `test_ndjson_streaming.py`). Playwright tests for the frontend already exist in `frontend/tests/e2e/`.

**Alternatives Considered**:
- Live server (subprocess): Slower startup, requires port management, harder to mock dependencies. Rejected.
- `pytest-anyio`: Already handled by `pytest-asyncio` which is installed. No additional package needed.

---

### R4 — Sample PDF: Committed Binary vs Generated

**Decision**: Committed as a static binary in git.

**Rationale**: Zero runtime dependencies, deterministic bytes, works offline. The file is kept < 50 KB (3 pages of text). The ingestion pipeline validates magic bytes (`%PDF`) — a committed real PDF guarantees this constraint without any build step. Generated PDFs can produce different byte sequences across library versions, complicating hash-based deduplication tests.

**Alternatives Considered**:
- `fpdf2` at test runtime: Requires additional package, non-deterministic bytes. Rejected.
- Download from URL: Network dependency at test time. Violates Principle I (local-first) in spirit. Rejected.

---

### R5 — Coverage Gate: Hard Fail vs Warning

**Decision**: Hard gate via `--cov-fail-under=80` in `pytest.ini`.

**Rationale**: At 1405 tests across 15 specs, the codebase is mature. A warning-only threshold will be ignored over time. A hard gate enforces that new production code introduced in future specs must be accompanied by tests. The 80% floor is achievable given existing coverage; spec-16 adds 5 uncovered modules which will raise the number.

**Alternatives Considered**:
- Warning-only (`--cov-report=term-missing` without `--cov-fail-under`): Provides visibility but no enforcement. Rejected.
- CI-only gate: Hard gate in local dev is equally useful — catches regressions before push. Rejected.

---

### R6 — Verified Production Module Symbol Names

Verified via serena `find_symbol` before writing the plan:

| Test File | Import | Symbol Type |
|---|---|---|
| `test_reranker.py` | `from backend.retrieval.reranker import Reranker` | class |
| `test_score_normalizer.py` | `from backend.retrieval.score_normalizer import normalize_scores` | function (NOT a class) |
| `test_storage_chunker.py` | `from backend.storage.chunker import chunk_text` | function |
| `test_storage_indexing.py` | `from backend.storage.indexing import index_chunks` | async function |
| `test_errors.py` | `from backend.errors import EmbeddinatorError` (+ 10 subclasses) | classes |

**Critical**: `normalize_scores` is a module-level function. `ScoreNormalizer` is not a class in the codebase — any test that attempts `ScoreNormalizer(...)` will fail with `ImportError`.

`ProviderRateLimitError` lives in `backend/providers/base.py`, NOT in `backend/errors.py`. The `test_errors.py` file must NOT attempt to import it from `errors.py`.

---

### R7 — pytest.ini Location

**Decision**: Project root (`/home/brunoghiberto/Documents/Projects/The-Embedinator/pytest.ini`).

**Rationale**: The project root is where `scripts/run-tests-external.sh` sets `cd "$PROJECT_ROOT"` before invoking pytest. Placing `pytest.ini` at the project root ensures it is discovered automatically. The `src/` directory is NOT the project root — tests run from the repo root.

**Alternatives Considered**:
- `pyproject.toml [tool.pytest.ini_options]`: Equivalent but adds to an existing file that may have other tooling config. A dedicated `pytest.ini` is simpler and more explicit.
- `src/pytest.ini`: Wrong location — `cd "$PROJECT_ROOT"` in the test runner script sets the working directory to repo root, not `src/`.

---

### R8 — E2E Teardown Guarantee

**Decision**: `yield`-based `@pytest_asyncio.fixture` with `try/finally` or implicit `yield` cleanup.

**Rationale**: pytest's fixture teardown (code after `yield`) runs even when the test raises an assertion error. This guarantees collection cleanup on failure, preventing 409 conflicts on subsequent runs. Using class-based `setup/teardown` methods does NOT guarantee teardown on failure.

```python
@pytest_asyncio.fixture
async def e2e_app():
    app = create_test_app()
    client = httpx.AsyncClient(app=app, base_url="http://test")
    try:
        yield client
    finally:
        await client.aclose()
        # cleanup: delete any collections/documents created
```
