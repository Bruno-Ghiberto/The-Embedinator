# Data Model: Testing Strategy (Spec 16)

Spec 16 introduces no new database tables or production data entities. The data model for this spec concerns the shape of test fixtures — the reusable objects injected into tests via `tests/conftest.py`.

---

## Fixture Entities

### `db` (async fixture)

| Field | Type | Value |
|-------|------|-------|
| path | str | `":memory:"` — never a filesystem path |
| connection state | — | Connected via `await db.connect()` |
| teardown | — | `await db.close()` after `yield` |

**Lifecycle**: Created fresh per test function. Connects on setup, closes on teardown. Backed by `backend.storage.sqlite_db.SQLiteDB`.

**Invariants**:
- MUST NOT reference `data/embedinator.db` (old schema, will fail with `OperationalError`)
- MUST use `await db.connect()` — not `await db.initialize()` (method does not exist)
- MUST be declared with `@pytest_asyncio.fixture`, not `@pytest.fixture`

---

### `sample_chunks` (sync fixture)

| Field | Type | Description |
|-------|------|-------------|
| chunk_id | str | Unique chunk identifier (`"chunk-001"`, `"chunk-002"`, `"chunk-003"`) |
| text | str | Readable text relevant to a test topic |
| source_file | str | `"sample.pdf"` |
| page | int \| None | `1`, `2`, `3` |
| breadcrumb | str | `"Section 1"`, `"Section 2"`, `"Section 3"` |
| parent_id | str | `"parent-001"`, `"parent-002"` |
| collection | str | `"test-collection"` |
| dense_score | float | Dense relevance score (0.65–0.92 range) |
| sparse_score | float | Sparse relevance score (0.50–0.80 range) |
| rerank_score | float \| None | `None` (not yet reranked) |

**Type**: `list[RetrievedChunk]` — uses the actual `RetrievedChunk` Pydantic model from `backend.agent.schemas`.

**Count**: 3 chunks (sufficient for reranking, scoring, and deduplication tests).

---

### `mock_llm` (sync fixture)

| Attribute | Value |
|-----------|-------|
| `ainvoke` | `AsyncMock` returning `AIMessage(content="This is a test answer.")` |
| `with_structured_output` | `MagicMock` returning self |
| `astream` | `AsyncMock` returning `iter([AIMessage(content="Test")])` |

**Type**: `unittest.mock.MagicMock` configured to satisfy `BaseChatModel` interface.

**Usage**: Injected into agent node tests and graph integration tests to avoid real LLM calls. Do not use `MemorySaver()` as a mock LLM — they serve different purposes.

---

### `mock_qdrant_results` (sync fixture)

| Field | Type | Description |
|-------|------|-------------|
| id | str | `"chunk-001"`, `"chunk-002"` — maps to `chunk_id` in `RetrievedChunk` |
| score | float | 0.92, 0.78 — Qdrant's fused score, maps to `dense_score` |
| payload.text | str | Readable chunk text |
| payload.source_file | str | `"sample.pdf"` |
| payload.page | int | `1`, `2` |
| payload.breadcrumb | str | `"Section 1"`, `"Section 2"` |
| payload.parent_id | str | `"parent-001"` |
| payload.sparse_score | float | 0.75, 0.60 |

**Type**: `list[dict]` — raw dict format matching the Qdrant `ScoredPoint` shape consumed by `HybridSearcher._points_to_chunks()` in `backend/retrieval/searcher.py`.

**Count**: 2 results (sufficient for reranking and merge tests).

---

## Fixture File Assets

### `tests/fixtures/sample.pdf`

| Property | Constraint |
|----------|-----------|
| Magic bytes | `%PDF` at byte offset 0 |
| Size | < 50 KB |
| Pages | 3 minimum |
| Content | Human-readable text (for chunking and embedding tests) |
| Storage | Committed binary in git |

**Validation**: The ingestion pipeline checks `content[:4] != b"%PDF"` and rejects files that fail. The fixture MUST pass this check.

### `tests/fixtures/sample.md`

| Property | Constraint |
|----------|-----------|
| Format | Valid Markdown |
| Structure | At least 1 heading (`##`), 1 list, 1 code block, 2+ prose paragraphs |
| Size | 1–5 KB |
| Storage | Committed text file in git |

### `tests/fixtures/sample.txt`

| Property | Constraint |
|----------|-----------|
| Format | Plain UTF-8 text |
| Structure | 3+ paragraphs, 500+ words |
| Size | 2–10 KB |
| Storage | Committed text file in git |

---

## Marker Registration

### `pytest.ini` markers

| Marker | Purpose | Auto-skip behavior |
|--------|---------|-------------------|
| `e2e` | Backend Python E2E tests (in-process ASGI) | Not auto-skipped; excluded from default `tests/unit/` and `tests/integration/` runs |
| `require_docker` | Tests requiring Qdrant on `localhost:6333` | Auto-skipped via `pytest_runtest_setup` hook when socket check fails |

**Registration location**: `tests/conftest.py` via `pytest_configure(config)` hook AND `pytest.ini` `markers =` section (both required to suppress `PytestUnknownMarkWarning`).
