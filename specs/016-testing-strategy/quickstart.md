# Quickstart: Testing Strategy (Spec 16)

## Overview

Spec 16 adds test coverage infrastructure to The Embedinator. No production code is modified.

## What Gets Added

| Component | Location | Purpose |
|-----------|----------|---------|
| Shared fixtures | `tests/conftest.py` | `db`, `sample_chunks`, `mock_llm`, `mock_qdrant_results` |
| pytest config | `pytest.ini` | Marker registration + 80% coverage hard gate |
| 5 unit test files | `tests/unit/` | Cover: Reranker, normalize_scores, chunk_text, index_chunks, EmbeddinatorError |
| 3 E2E test files | `tests/e2e/` | Python ASGI tests: ingest, chat, collection lifecycle |
| 3 integration files | `tests/integration/` | Real Qdrant: CRUD, hybrid search, circuit breaker |
| 3 fixture files | `tests/fixtures/` | sample.pdf, sample.md, sample.txt — committed binaries |

---

## Running Tests

**IMPORTANT**: Never run `pytest` directly. Always use the external runner script.

### Unit tests only (fast, < 30s)
```bash
zsh scripts/run-tests-external.sh -n spec16-unit --no-cov tests/unit/
cat Docs/Tests/spec16-unit.status     # → PASSED
cat Docs/Tests/spec16-unit.summary    # → test counts
```

### Full suite with coverage gate
```bash
zsh scripts/run-tests-external.sh -n spec16-full tests/
cat Docs/Tests/spec16-full.status
cat Docs/Tests/spec16-full.summary    # includes coverage % and any failures
```

### E2E tests only
```bash
zsh scripts/run-tests-external.sh -n spec16-e2e --no-cov -m "e2e" tests/e2e/
```

### Docker-dependent integration tests (requires Qdrant running)
```bash
# Start Qdrant first:
docker run -d -p 6333:6333 qdrant/qdrant

# Run Docker-marked tests:
zsh scripts/run-tests-external.sh -n spec16-docker --no-cov -m "require_docker" tests/integration/
```

### Verify Docker tests auto-skip (without Qdrant)
```bash
# With Qdrant stopped:
zsh scripts/run-tests-external.sh -n spec16-skip-check --no-cov tests/integration/test_qdrant_integration.py
grep "skipped" Docs/Tests/spec16-skip-check.summary
```

---

## Using the Shared Fixtures

### In-memory database
```python
import pytest
import pytest_asyncio

@pytest.mark.asyncio
async def test_my_feature(db):
    # db is a connected SQLiteDB(:memory:) — use it directly
    collection_id = await db.create_collection("my-test", "description")
    assert collection_id is not None
    # no cleanup needed — db is destroyed after test
```

### Sample chunks
```python
def test_reranker_orders_chunks(sample_chunks):
    # sample_chunks is list[RetrievedChunk] with 3 items, scores [0.92, 0.78, 0.65]
    reranker = Reranker(settings)
    result = reranker.rerank(sample_chunks, query="test query", top_k=2)
    assert len(result) == 2
```

### Mock LLM
```python
async def test_node_calls_llm(mock_llm):
    # mock_llm.ainvoke() returns AIMessage("This is a test answer.")
    state = ConversationState(query="test", llm=mock_llm, ...)
    result = await answer_generation_node(state)
    mock_llm.ainvoke.assert_called_once()
```

### Fixture files
```python
from pathlib import Path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def test_pdf_passes_magic_byte_check():
    pdf_bytes = (FIXTURES_DIR / "sample.pdf").read_bytes()
    assert pdf_bytes[:4] == b"%PDF"
```

---

## Marker Guide

| Marker | When to use | Auto-skip? |
|--------|------------|-----------|
| `@pytest.mark.e2e` | ASGI E2E tests in `tests/e2e/` | No |
| `@pytest.mark.require_docker` | Tests requiring `localhost:6333` | Yes — skips when Qdrant unreachable |

---

## Coverage Gate

The `pytest.ini` enforces `--cov-fail-under=80`. The full suite exits non-zero if coverage drops below 80%.

To **bypass the gate** during development (fast iteration):
```bash
zsh scripts/run-tests-external.sh -n quick --no-cov tests/unit/
```

To **check coverage** without failing on the threshold:
```bash
# Run with coverage but review the number without gating:
zsh scripts/run-tests-external.sh -n cov-check tests/unit/
grep "TOTAL" Docs/Tests/cov-check.summary
```

---

## Pre-existing Failures

39 tests were failing before spec-16. These are known and must remain unchanged. After all spec-16 work, the failure count must still be exactly 39 — no more, no fewer.

To check:
```bash
grep "FAILED" Docs/Tests/spec16-full.log | wc -l   # should be 39
```
