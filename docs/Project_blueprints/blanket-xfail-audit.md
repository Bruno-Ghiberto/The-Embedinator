# Blanket-xfail audit

**Date**: 2026-08-04 · **Origin**: spec-31 task 0.18 · **Status**: findings recorded, remediation queued

Six test modules carry a **module-level** `pytestmark = pytest.mark.xfail(...)`, which suppresses
every test in the file. Together they hide **46 tests**.

Task 0.18 exists because *"a blanket xfail can hide a regression a fix introduces."* This audit
confirms that risk and finds it is worse than stated, because the suppression is not strict.

---

## Finding 1 — the suppression is bidirectional and silent

`xfail_strict` is **not set** anywhere in `pytest.ini`, `setup.cfg`, or `pyproject.toml`, so it
defaults to `false`. For all 46 tests that means:

| Event | Reported as | Fails the suite? |
|---|---|---|
| A spec-31 fix **breaks** one of these tests | `xfail` (unchanged) | No |
| A spec-31 fix **repairs** one of these tests | `xpass` | No |
| The test keeps failing for its original reason | `xfail` | No |

Every outcome is green. These files cannot report anything to anyone.

The second row is not hypothetical: a full-suite run recorded **16 xpassed**, meaning obsolete
markers are already suppressing tests that work.

## Finding 2 — the blackout overlaps the batches that need cover most

Each module is mapped to the spec-31 batch that will modify the surface it tests.

| Module | Tests | Stated reason | Batch touching this surface | Risk |
|---|---|---|---|---|
| `tests/integration/test_ingestion_pipeline.py` | 7 | mock/service boundary issues | **Batch 4** — BUG-052 / BUG-087 | **High** — the data-destruction batch |
| `tests/unit/api/test_chat_security.py` | 4 | chat endpoint mock boundary mismatch | **Batch 7** — BUG-083 prompt injection | **High** — security work with security tests dark |
| `tests/integration/test_us3_streaming.py` | 3 | fixture setup error with mocked lifespan | **Batch 2** — BUG-074 / 088 / 082 | **High** — the streaming contract |
| `tests/unit/test_schema_migration.py` | 26 | stale `SQLiteDB` API | Batch 4 — SQLite surface | Medium |
| `tests/integration/test_us4_traces.py` | 3 | fixture setup error with mocked lifespan | Batch 1 — BUG-112 analytics | Medium |
| `tests/integration/test_us1_e2e.py` | 3 | lifespan teardown/setup errors | general | Low |

The three High rows are the concern: Batch 4 destroys and recreates vector data, Batch 7 changes
prompt assembly, and Batch 2 changes stream termination — and in each case the module that would
catch a mistake is suppressed.

Note the stated reasons describe **test-harness** problems (mock boundaries, fixture setup, a
stale API), not product defects. That is consistent with the spec-20 triage that moved the
baseline to zero failures: these were suppressed to get a clean signal, not because the product
was broken. The suppression was a reasonable expedient. It has outlived its purpose.

---

## Remediation — queued, not applied

Not applied in this pass because it changes suite-wide behaviour and belongs with the batch that
depends on it, not bundled into the harness close-out.

1. **Run the six modules unsuppressed** and record, per test, whether it passes today. This is a
   measurement, not a change.
2. **Delete the marker** on every test that passes. An obsolete xfail is strictly worse than no
   test, because it reads as covered.
3. **For tests that genuinely still fail**, move the marker from module level to the individual
   test and add `strict=True`, so a later fix that repairs one is *reported* rather than absorbed.
4. **Do steps 1–3 for a module before the batch that touches its surface**, not after:
   - `test_us3_streaming.py` and `test_us4_traces.py` before **Batch 2**
   - `test_ingestion_pipeline.py` and `test_schema_migration.py` before **Batch 4**
   - `test_chat_security.py` before **Batch 7**
5. Consider `xfail_strict = true` globally once the 16 known xpasses are resolved. Setting it
   before that converts them into immediate failures.

## What this does not claim

This audit did **not** re-run the six modules — it reads markers, configuration, and counts. Step
1 above is the measurement, and until it runs, "these tests would pass" is a hypothesis. The
findings that are established are the two structural ones: the suppression is non-strict and
bidirectional, and it overlaps three high-risk batches.
