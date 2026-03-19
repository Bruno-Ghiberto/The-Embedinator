# A7 — Full Validation + Report (Wave 5)

**Agent type**: `quality-engineer`
**Model**: `claude-sonnet-4-6`
**Wave**: 5 (sequential — after Wave 4 completes)
**Gate requirement**: All fixture files committed (verify with `git ls-files tests/fixtures/`); `pytest.ini` coverage gate confirmed. Confirm with orchestrator before starting.

Read `specs/016-testing-strategy/tasks.md` then await orchestrator instructions before proceeding.

---

## Assigned Tasks

| Task | Description |
|------|-------------|
| T032 | Run full suite with coverage gate |
| T033 | Extract and verify test count (>= 1405) |
| T034 | Verify pre-existing failure count is exactly 39 |
| T034b | Verify unit suite timing under 30 seconds |
| T035 | Verify E2E tests pass explicitly |
| T036 | Verify Docker tests skip cleanly |
| T037 | Verify coverage gate behavior |
| T038 | Write validation report |

---

## T032 — Full Suite Run

```bash
zsh scripts/run-tests-external.sh -n spec16-final tests/
```

This run includes the coverage gate (`--cov-fail-under=80`). If coverage is below 80%, status will be FAILED — report this to the orchestrator; do NOT proceed to mark spec-16 complete.

```bash
cat Docs/Tests/spec16-final.status    # PASSED or FAILED
cat Docs/Tests/spec16-final.summary   # test counts + coverage
```

---

## T033 — Test Count Verification

```bash
grep -E "passed|failed" Docs/Tests/spec16-final.summary
```

The total passing count must be >= 1405 (spec-15 baseline).

---

## T034 — Pre-existing Failure Verification

```bash
grep "FAILED" Docs/Tests/spec16-final.log | wc -l
```

Result must be exactly **39**. If it is:
- Greater than 39: new failures were introduced — find and fix them.
- Less than 39: pre-existing failures were accidentally fixed or suppressed — investigate.

---

## T034b — Unit Suite Timing (parallel with T037, T038)

Record wall-clock elapsed time:
```bash
START=$(date +%s)
zsh scripts/run-tests-external.sh -n spec16-unit-timing --no-cov tests/unit/
END=$(date +%s)
echo "Elapsed: $((END - START)) seconds"
cat Docs/Tests/spec16-unit-timing.status
```

Elapsed time must be under 30 seconds (SC-003). Record the actual value in the T038 report.

---

## T035 — E2E Explicit Verification

```bash
zsh scripts/run-tests-external.sh -n spec16-e2e-final --no-cov -m "e2e" tests/e2e/
cat Docs/Tests/spec16-e2e-final.status   # must be PASSED
```

Confirm all 4 E2E test files ran: `test_ingest_e2e.py`, `test_chat_e2e.py`, `test_collection_e2e.py`, `test_observability_e2e.py`.

---

## T036 — Docker Tests Skip Cleanly

With Qdrant NOT running:
```bash
zsh scripts/run-tests-external.sh -n spec16-skip-final --no-cov tests/integration/test_qdrant_integration.py tests/integration/test_hybrid_search.py tests/integration/test_circuit_breaker.py
cat Docs/Tests/spec16-skip-final.status   # must be PASSED (skips count as pass)
grep "skipped" Docs/Tests/spec16-skip-final.summary
```

Confirm the summary shows skips (not failures) for the three Docker test files.

---

## T037 — Coverage Gate Verification (parallel with T034b, T038)

From the T032 full run:
```bash
grep "TOTAL" Docs/Tests/spec16-final.summary
```

The TOTAL line shows actual coverage percentage. Record this in T038. If the gate fired (status FAILED), the coverage is below 80% and the spec cannot be marked complete.

---

## T038 — Validation Report

Write to `specs/016-testing-strategy/validation-report.md`:

```markdown
# Spec 16: Testing Strategy — Validation Report

**Date**: <today>
**Branch**: 016-testing-strategy

## SC Results

| SC | Criterion | Status | Evidence |
|----|-----------|--------|---------|
| SC-001 | 1405+ tests passing, 0 regressions | PASS/FAIL | Total: <count> |
| SC-002 | Backend coverage >= 80% (hard gate) | PASS/FAIL | Coverage: <pct>% |
| SC-003 | Unit suite < 30 seconds | PASS/FAIL | Elapsed: <secs>s |
| SC-004 | 5 new unit test files with passing tests | PASS/FAIL | test_reranker, test_score_normalizer, test_storage_chunker, test_storage_indexing, test_errors |
| SC-005 | 3 E2E test files, excluded from default runs, pass when invoked | PASS/FAIL | spec16-e2e-final.status: <value> |
| SC-006 | 3 integration test files pass with Docker | PASS/FAIL | Skipped cleanly without Docker |
| SC-007 | tests/conftest.py with 4 fixtures importable | PASS/FAIL | db, sample_chunks, mock_llm, mock_qdrant_results |
| SC-008 | 3 fixture files in tests/fixtures/, sample.pdf < 50 KB | PASS/FAIL | git ls-files shows all 3 |

## New Test File Breakdown

| File | Task | Test Count |
|------|------|-----------|
| tests/unit/test_reranker.py | T012 | <n> |
| tests/unit/test_score_normalizer.py | T013 | <n> |
| tests/unit/test_storage_chunker.py | T014 | <n> |
| tests/unit/test_storage_indexing.py | T015 | <n> |
| tests/unit/test_errors.py | T016 | <n> |
| tests/e2e/test_ingest_e2e.py | T020 | <n> |
| tests/e2e/test_chat_e2e.py | T021 | <n> |
| tests/e2e/test_collection_e2e.py | T022 | <n> |
| tests/e2e/test_observability_e2e.py | T022b | <n> |
| tests/integration/test_qdrant_integration.py | T024 | <n> |
| tests/integration/test_hybrid_search.py | T025 | <n> |
| tests/integration/test_circuit_breaker.py | T026 | <n> |

## Final Counts

- Baseline (spec-15): 1405 tests passing
- After spec-16: <total> tests passing
- New tests added: <delta>
- Pre-existing failures: <count> (must be 39)
- Backend line coverage: <pct>%
```

---

## SC Status: All 8 Must Pass

Spec 16 is COMPLETE when:
1. SC-001: total passing >= 1405
2. SC-002: coverage >= 80% (hard gate fires on failure)
3. SC-003: unit suite < 30 seconds
4. SC-004: 5 unit test files with passing tests
5. SC-005: 4 E2E files pass with `e2e` marker
6. SC-006: 3 integration files skip cleanly without Docker
7. SC-007: conftest.py with 4 fixtures importable
8. SC-008: 3 fixture files committed, sample.pdf < 50 KB

---

## Critical Gotchas

- NEVER run `pytest` directly. Always use `zsh scripts/run-tests-external.sh`.
- The T032 full run uses coverage — this is intentional and MUST NOT use `--no-cov`.
- T034b, T037, T038 can run in parallel (different targets, different output files).
- If SC-002 fails (coverage < 80%), report this clearly — do not mark spec-16 complete.
- Pre-existing failure count must be EXACTLY 39. Neither more nor fewer.
