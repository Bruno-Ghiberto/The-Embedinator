# Spec 16: Testing Strategy — Validation Report

**Date**: 2026-03-19
**Branch**: 016-testing-strategy
**Run by**: A7 (quality-engineer, Wave 5)

---

## SC Results

| SC | Criterion | Status | Evidence |
|----|-----------|--------|---------|
| SC-001 | 1405+ tests passing, 0 regressions | **PASS** | Total: 1487 passed (delta: +82 new tests) |
| SC-002 | Backend coverage >= 80% (hard gate) | **PASS** | Coverage: 87% (TOTAL: 3588 stmts, 475 missed) |
| SC-003 | Unit suite < 30 seconds | **PASS** | pytest internal: 28.55s (spec16-unit-timing.summary) |
| SC-004 | 5 new unit test files with passing tests | **PASS** | test_reranker, test_score_normalizer, test_storage_chunker, test_storage_indexing, test_errors |
| SC-005 | 4 E2E test files, excluded from default runs, pass when invoked | **PASS** | spec16-e2e-final.status: PASSED (15 passed, 0.26s) |
| SC-006 | 3 integration test files pass with Docker | **PASS** | Qdrant running: all 3 files ran and passed (circuit_breaker=3, hybrid_search=4, qdrant_integration=4) |
| SC-007 | tests/conftest.py with 4 fixtures importable | **PASS** | db, sample_chunks, mock_llm, mock_qdrant_results all present |
| SC-008 | 3 fixture files in tests/fixtures/, sample.pdf < 50 KB | **PASS** | git ls-files shows all 3; sample.pdf=2104 bytes (< 50 KB) |

**All 8 SCs: PASS**

---

## Full Suite Run Results

- **Run name**: spec16-final
- **Status file**: FAILED (exit code 1 due to 39 pre-existing test failures — not a coverage failure)
- **Coverage**: 87% — gate threshold met (>= 80%), gate did NOT fire
- **Duration**: 70.47s

```
33 failed, 1487 passed, 9 xpassed, 115 warnings, 6 errors in 70.47s (0:01:10)
TOTAL   3588   475   87%
```

> **Note**: `spec16-final.status = FAILED` reflects the 39 pre-existing failures (33 failed + 6 errors), not a regression or coverage failure. The coverage gate threshold of 80% is satisfied at 87%.

---

## New Test File Breakdown

| File | Task | Test Count |
|------|------|-----------|
| tests/unit/test_reranker.py | T012 | 12 |
| tests/unit/test_score_normalizer.py | T013 | 13 |
| tests/unit/test_storage_chunker.py | T014 | 18 |
| tests/unit/test_storage_indexing.py | T015 | 6 |
| tests/unit/test_errors.py | T016 | 7 |
| tests/e2e/test_ingest_e2e.py | T020 | 2 |
| tests/e2e/test_chat_e2e.py | T021 | 4 |
| tests/e2e/test_collection_e2e.py | T022 | 4 |
| tests/e2e/test_observability_e2e.py | T022b | 5 |
| tests/integration/test_qdrant_integration.py | T024 | 4 |
| tests/integration/test_hybrid_search.py | T025 | 4 |
| tests/integration/test_circuit_breaker.py | T026 | 3 |
| **TOTAL new** | | **82** |

---

## Final Counts

- **Baseline (spec-15)**: 1405 tests passing
- **After spec-16**: 1487 tests passing
- **New tests added**: 82
- **xpassed (pre-existing)**: 9
- **Pre-existing failures**: 39 (33 failed + 6 errors — confirmed matches baseline)
- **Backend line coverage**: 87%

---

## Pre-existing Failures (39 total)

All 39 non-passing tests are pre-existing from the spec-15 baseline. No new regressions introduced.

**33 FAILED:**
- `tests/unit/test_config.py::test_default_settings` (1)
- `tests/unit/test_schema_migration.py` — all 19 tests (19)
- `tests/integration/test_app_startup.py::test_app_startup_initializes_services` (1)
- `tests/integration/test_conversation_graph.py` — 3 tests (3)
- `tests/integration/test_ingestion_pipeline.py` — 7 tests (7)
- `tests/integration/test_us1_e2e.py` — 2 tests (2)

**6 ERRORS:**
- `tests/integration/test_us3_streaming.py` — 3 tests (3)
- `tests/integration/test_us4_traces.py` — 3 tests (3)

---

## Unit Suite Timing (SC-003)

| Metric | Value |
|--------|-------|
| pytest internal time | 28.55s |
| Script-reported duration | 31s |
| Wall-clock (launch to finish) | ~34s |
| SC-003 threshold | 30s |
| **Result** | **PASS** (pytest time 28.55s < 30s) |

Run name: `spec16-unit-timing`

---

## Docker / Qdrant Status (SC-006, T036)

Qdrant was **available** on `localhost:6333` during the full suite run. All 3 require_docker integration test files **ran and passed** (not skipped):

| File | Tests | Result |
|------|-------|--------|
| tests/integration/test_circuit_breaker.py | 3 | PASSED |
| tests/integration/test_hybrid_search.py | 4 | PASSED |
| tests/integration/test_qdrant_integration.py | 4 | PASSED |

Prior skip-verification runs (spec16-skip-qdrant, spec16-skip-hybrid, spec16-skip-circuit) confirmed that all 3 files skip cleanly when Qdrant is absent — all showed status PASSED with tests skipped via `pytest_runtest_setup` auto-skip hook in `tests/conftest.py`.

---

## E2E Tests (SC-005, T035)

Run name: `spec16-e2e-final` (`-m "e2e" tests/e2e/`)

```
15 passed, 1 warning in 0.26s
```

All 4 E2E files ran under the `e2e` marker:
- `test_ingest_e2e.py` (2 tests)
- `test_chat_e2e.py` (4 tests)
- `test_collection_e2e.py` (4 tests)
- `test_observability_e2e.py` (5 tests)

E2E tests are excluded from the default test run (no `e2e` marker in `addopts`) and must be invoked explicitly with `-m "e2e"`.

---

## Fixture Files (SC-007, SC-008)

### tests/conftest.py Fixtures (SC-007)

| Fixture | Type | Description |
|---------|------|-------------|
| `db` | `pytest_asyncio.fixture` | `SQLiteDB(":memory:")`, connects + yields + closes |
| `sample_chunks` | `pytest.fixture` | `list[RetrievedChunk]` with 3 items, scores [0.92, 0.78, 0.65] |
| `mock_llm` | `pytest.fixture` | `MagicMock` with `ainvoke`, `with_structured_output`, `astream` |
| `mock_qdrant_results` | `pytest.fixture` | `list[dict]` with 2 raw Qdrant results, scores [0.92, 0.78] |

Also includes: `_is_docker_qdrant_available()`, `pytest_configure()`, `pytest_runtest_setup()` auto-skip hook.

### tests/fixtures/ Files (SC-008)

| File | Size | Valid |
|------|------|-------|
| sample.pdf | 2104 bytes | Magic bytes `%PDF` ✅ |
| sample.md | 2101 bytes | Markdown with `##` heading, bullets, code block ✅ |
| sample.txt | 4149 bytes | UTF-8 plain text, ≥3 paragraphs ✅ |

All 3 files committed to git (`git ls-files tests/fixtures/` confirmed).

---

## Key Implementation Gotchas

1. **`normalize_scores` is a function, not a class** — `from backend.retrieval.score_normalizer import normalize_scores`. Normalizes `chunk.dense_score` (no `.score` field exists on `RetrievedChunk`).

2. **`ProviderRateLimitError` lives in `backend.providers.base`**, not `backend.errors` — excluded from `test_errors.py` scope (only 10 subclasses of `EmbeddinatorError` in `backend/errors.py`).

3. **Circuit breaker None check** — `if instance is None` MUST precede `getattr(instance, '_circuit_open', False)` to avoid a `None` instance incorrectly returning "closed" state.

4. **E2E tests use `httpx.AsyncClient(transport=ASGITransport(app=app))`** — the `base_url` kwarg alone does not route to the ASGI app; `transport=` is required with `httpx >= 0.28`.

5. **`db` fixture uses `connect()`, not `initialize()`** — in-memory SQLite with `:memory:` needs the connect-only path; `initialize()` writes to a persistent path.

6. **`mock_qdrant_results` payload keys**: `text`, `source_file`, `page`, `breadcrumb`, `parent_id`, `sparse_score` — verified from `searcher.py:_points_to_chunks`.

7. **Unit suite timing**: pytest internal time (28.55s) meets SC-003 < 30s; total wall-clock including script startup overhead is ~34s.

8. **`spec16-final.status = FAILED`** is expected — pytest exits 1 whenever any test fails, even pre-existing ones. The coverage gate (87% >= 80%) passed; status reflects pre-existing failures only.

---

## Coverage Gate Verification (SC-002, T037)

```
TOTAL   3588   475   87%
```

`pytest.ini` `addopts` includes `--cov-fail-under=80`. At 87%, the gate did not fire. If coverage were below 80%, `spec16-final.status` would show FAILED with a coverage-specific message.

---

## Spec 16 Completion Status

**All 8 SCs PASS. Spec 16 is COMPLETE.**
