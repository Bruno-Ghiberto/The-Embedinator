# A5 — Docker Integration Tests (Wave 3)

**Agent type**: `python-expert`
**Model**: `claude-sonnet-4-6`
**Wave**: 3 (parallel with A4)
**Gate requirement**: `Docs/Tests/spec16-scaffold.status` must equal `PASSED` before starting. Confirm with orchestrator that Wave 2 gates also passed.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | File to Create |
|------|----------------|
| T024 | `tests/integration/test_qdrant_integration.py` |
| T025 | `tests/integration/test_hybrid_search.py` |
| T026 | `tests/integration/test_circuit_breaker.py` |
| T027 | Skip-verification runs (see below) |

---

## Integration Test Architecture

All tests in these three files MUST be marked `@pytest.mark.require_docker`.

The auto-skip is handled by `pytest_runtest_setup` in `tests/conftest.py` via a socket check to `localhost:6333`. Tests skip automatically when Qdrant is unreachable. Do NOT call `pytest.skip()` manually. Do NOT import from `testcontainers` — it is not installed.

```python
# Correct pattern — rely on automatic skip from conftest.py hook:
@pytest.mark.require_docker
async def test_something():
    storage = QdrantStorage(host="localhost", port=6333)
    ...
```

Use `unique_name()` from `tests/integration/conftest.py` for all collection names:
```python
from tests.integration.conftest import unique_name
name = unique_name("crud")  # generates e.g. "crud-a1b2c3d4"
```

Always use `try/finally` to delete test collections even when assertions fail.

---

## T024 — test_qdrant_integration.py

**Import**: `from backend.storage.qdrant_client import QdrantStorage`

Required test cases (minimum 4, all `@pytest.mark.require_docker`):
1. `create_collection(name, vector_size=384)` succeeds — collection appears in `list_collections()`.
2. `batch_upsert(name, points)` inserts vectors — verify count via `search_hybrid()` or collection info.
3. `search_hybrid(name, query_vector, top_k=5)` returns results in descending score order.
4. `delete_collection(name)` removes collection — subsequent `list_collections()` no longer contains it.

```python
@pytest.mark.require_docker
async def test_collection_crud():
    storage = QdrantStorage(host="localhost", port=6333)
    name = unique_name("crud")
    try:
        await storage.create_collection(name, vector_size=384)
        collections = await storage.list_collections()
        assert any(c["name"] == name for c in collections)
    finally:
        await storage.delete_collection(name)
```

---

## T025 — test_hybrid_search.py

**Import**: `from backend.retrieval.searcher import HybridSearcher`

Required test cases (minimum 3, all `@pytest.mark.require_docker`):
1. Seed Qdrant with at least 3 known vectors, then query — known-relevant document appears in top-3.
2. Dense-only search (no sparse prefetch) returns results.
3. Hybrid search (dense + sparse) returns results in correct ranking order.

Seed pattern:
```python
# Use a deterministic vector so the test is reproducible
known_vector = [0.1] * 384
await storage.batch_upsert(name, [{"id": "known-1", "vector": known_vector, "payload": {"text": "target document"}}])
```

---

## T026 — test_circuit_breaker.py

**Import**: `from backend.retrieval.searcher import HybridSearcher`
**Import**: `from backend.errors import CircuitOpenError`

Required test cases (minimum 3, all `@pytest.mark.require_docker`):
1. After repeated failures (Qdrant unreachable), `_circuit_open` becomes `True`.
2. When circuit is open, `CircuitOpenError` is raised without attempting a network call.
3. After cooldown period expires, the circuit resets.

**CRITICAL — circuit breaker None-check ordering**:

When checking circuit breaker state on an instance, ALWAYS check `if instance is None` BEFORE calling `getattr`:

```python
# WRONG — getattr(None, '_circuit_open', False) returns False, hiding the error:
if getattr(instance, '_circuit_open', False):
    raise CircuitOpenError(...)

# CORRECT:
if instance is None:
    raise CircuitOpenError("No circuit breaker instance")
if getattr(instance, '_circuit_open', False):
    raise CircuitOpenError("Circuit is open")
```

For the cooldown test, avoid flakiness by using a short test cooldown (mock or configure `_cooldown_secs` to 1 second) and asserting state after `asyncio.sleep(1.1)`.

---

## T027 — Skip Verification Runs

These runs verify the auto-skip mechanism works when Qdrant is NOT running.

**Stop Qdrant before running these** (or run on a machine without Docker):

```bash
zsh scripts/run-tests-external.sh -n spec16-skip-qdrant --no-cov tests/integration/test_qdrant_integration.py
zsh scripts/run-tests-external.sh -n spec16-skip-hybrid --no-cov tests/integration/test_hybrid_search.py
zsh scripts/run-tests-external.sh -n spec16-skip-circuit --no-cov tests/integration/test_circuit_breaker.py
```

All three `.status` files must show `PASSED` (tests skipped cleanly, not errored):
```bash
cat Docs/Tests/spec16-skip-qdrant.status    # PASSED (skips count as pass)
cat Docs/Tests/spec16-skip-hybrid.status    # PASSED
cat Docs/Tests/spec16-skip-circuit.status   # PASSED
```

Report all three skip-verification status values to the orchestrator.

---

## Critical Gotchas

- `testcontainers` is NOT installed. Do NOT import from it.
- The auto-skip hook lives in `tests/conftest.py` — do NOT add skip logic to individual test files.
- Use `unique_name()` from `tests/integration/conftest.py` for all collection names.
- `@pytest.mark.require_docker` only — do NOT use `@pytest.mark.integration` or `@pytest.mark.slow`.
- Check `if instance is None` BEFORE `getattr(instance, '_circuit_open', False)` in circuit breaker tests.
- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
- `asyncio_mode = auto` in `pytest.ini` — no `@pytest.mark.asyncio` needed on individual async tests.
