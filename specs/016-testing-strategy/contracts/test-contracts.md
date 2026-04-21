# Test Infrastructure Contracts (Spec 16)

Spec 16 introduces shared infrastructure contracts — agreements between test files and the fixtures/utilities they depend on. These contracts ensure new tests written in later specs can rely on the fixtures without re-reading conftest.py.

---

## Fixture Contract: `db`

**Provided by**: `tests/conftest.py`
**Type**: `SQLiteDB` (from `backend.storage.sqlite_db`)
**Scope**: Per test function (function-scoped)

**Guarantees**:
- Connected to `:memory:` SQLite on injection
- All 7 tables initialized (collections, documents, parent_chunks, child_chunks, query_traces, ingestion_jobs, provider_keys)
- Closed and destroyed after each test — no state leaks between tests
- Never touches `data/embedinator.db`

**Usage contract**:
```python
@pytest.mark.asyncio
async def test_create_collection(db):
    collection_id = await db.create_collection("test", "description")
    assert collection_id is not None
```

**Breaking changes**: If `SQLiteDB` constructor or `connect()` signature changes, `tests/conftest.py` must be updated before any test that uses `db`.

---

## Fixture Contract: `sample_chunks`

**Provided by**: `tests/conftest.py`
**Type**: `list[RetrievedChunk]`
**Scope**: Per test function (function-scoped)
**Count**: 3 chunks with `dense_score` values [0.92, 0.78, 0.65]

**Guarantees**:
- All 3 items are valid `RetrievedChunk` instances (Pydantic-validated) with fields: `chunk_id`, `text`, `source_file`, `page`, `breadcrumb`, `parent_id`, `collection`, `dense_score`, `sparse_score`, `rerank_score`
- `dense_score` values in descending order (suitable for reranking tests)
- All from `"test-collection"` (suitable for collection-scoped tests)

**Usage contract**:
```python
def test_rerank_orders_by_score(sample_chunks):
    result = rerank(sample_chunks, top_k=2)
    assert result[0].dense_score >= result[1].dense_score
```

---

## Fixture Contract: `mock_llm`

**Provided by**: `tests/conftest.py`
**Type**: `MagicMock` (implements `BaseChatModel` interface)
**Scope**: Per test function (function-scoped)

**Guarantees**:
- `mock_llm.ainvoke(messages)` returns `AIMessage(content="This is a test answer.")`
- `mock_llm.with_structured_output(schema)` returns itself (for chained structured output calls)
- `mock_llm.astream(messages)` is an `AsyncMock` returning a single `AIMessage`

**Usage contract**:
```python
async def test_node_calls_llm(mock_llm):
    state = build_test_state(llm=mock_llm)
    result = await some_node(state)
    mock_llm.ainvoke.assert_called_once()
```

---

## Fixture Contract: `mock_qdrant_results`

**Provided by**: `tests/conftest.py`
**Type**: `list[dict]`
**Scope**: Per test function (function-scoped)
**Count**: 2 results with scores [0.92, 0.78]

**Guarantees**:
- Each dict has keys: `id`, `score`, `payload`
- `payload` has keys: `text`, `source_file`, `page`, `breadcrumb`, `parent_id`, `sparse_score`
- Shape matches what `HybridSearcher._points_to_chunks()` expects from raw Qdrant `ScoredPoint` objects

**Usage contract**:
```python
def test_search_returns_results(mock_qdrant_results, mocker):
    mocker.patch.object(QdrantStorage, "search_hybrid", return_value=mock_qdrant_results)
    results = searcher.search("query")
    assert len(results) == 2
```

---

## Marker Contract: `@pytest.mark.require_docker`

**Registered in**: `tests/conftest.py` (via `pytest_configure`) and `pytest.ini`
**Skip condition**: Qdrant is not reachable on `localhost:6333` (socket timeout)
**Used in**: `tests/integration/test_qdrant_integration.py`, `test_hybrid_search.py`, `test_circuit_breaker.py`

**Contract**:
- Tests with this marker MUST NOT assume Qdrant is available
- The skip is automatic — test files MUST NOT call `pytest.skip()` manually
- When Qdrant IS available, these tests run fully and must pass

---

## Marker Contract: `@pytest.mark.e2e`

**Registered in**: `tests/conftest.py` (via `pytest_configure`) and `pytest.ini`
**Skip condition**: Never auto-skipped; excluded from `tests/unit/` and `tests/integration/` target paths
**Used in**: `tests/e2e/test_ingest_e2e.py`, `test_chat_e2e.py`, `test_collection_e2e.py`

**Contract**:
- All E2E tests MUST use in-process ASGI via `httpx.AsyncClient(app=app, base_url="http://test")`
- All E2E tests MUST guarantee fixture teardown via `yield` + `try/finally`
- E2E tests are explicitly invoked via: `zsh scripts/run-tests-external.sh -n <name> -m "e2e" tests/e2e/`

---

## Fixture File Contract: `tests/fixtures/`

All three files in `tests/fixtures/` are committed static assets:

| File | Contract |
|------|---------|
| `sample.pdf` | Passes `content[:4] == b"%PDF"` check; < 50 KB; loadable by `document_parser.parse_document()` |
| `sample.md` | Valid Markdown with headings, list, code block, prose; parseable by the ingestion pipeline |
| `sample.txt` | Plain UTF-8 text; 500+ words; chunked into 2+ chunks by `chunk_text()` at default settings |

**Loading pattern**:
```python
from pathlib import Path
FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

def test_pdf_ingestion():
    pdf_bytes = (FIXTURES_DIR / "sample.pdf").read_bytes()
    assert pdf_bytes[:4] == b"%PDF"
```
