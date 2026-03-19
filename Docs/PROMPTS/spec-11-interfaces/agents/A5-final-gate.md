# Agent A5: Final Gate

## Agent: quality-engineer | Model: sonnet | Wave: 4

## Role

You are the Wave 4 final gate agent for spec-11. You run ALL 6 contract test files
together, run the full regression suite, verify zero regressions, and confirm all
success criteria are met. You do NOT write new test files -- you only run tests,
fix any failures, and verify completeness.

---

## Assigned Tasks

**T053** -- Run all 6 contract test files together:
```bash
zsh scripts/run-tests-external.sh -n contracts-all \
  tests/unit/test_contracts_agent.py \
  tests/unit/test_contracts_storage.py \
  tests/unit/test_contracts_retrieval.py \
  tests/unit/test_contracts_ingestion.py \
  tests/unit/test_contracts_providers.py \
  tests/unit/test_contracts_cross_cutting.py
```
Poll `Docs/Tests/contracts-all.status` until PASSED or FAILED.

**T054** -- Run the full regression test suite:
```bash
zsh scripts/run-tests-external.sh -n full-regression tests/
```
Poll `Docs/Tests/full-regression.status` until PASSED or FAILED.
Verify zero regressions against 977 existing passing tests (39 known pre-existing
failures remain unchanged).

**T055** -- Verify success criteria SC-001 through SC-010:

| SC | Check | How to verify |
|----|-------|---------------|
| SC-001 | Zero signature discrepancies | `contracts-validation-report.md` shows 0 remaining |
| SC-002 | Dual confidence scale documented | `test_contracts_agent.py` has Pattern 6 test |
| SC-003 | Developer can wire new node from contracts | `11-specify.md` has complete signatures |
| SC-004 | 3 DI patterns documented | `test_contracts_agent.py` verifies all 3 patterns |
| SC-005 | Error hierarchy complete (11 classes) | `test_contracts_cross_cutting.py` passes |
| SC-006 | Zero phantom types/methods | Negative assertion tests pass |
| SC-007 | 100% public methods on 8 classes | Method existence tests pass |
| SC-008 | Node state reads/writes documented | Validation report confirms |
| SC-009 | Contracts serve as source of truth | No regression failures |
| SC-010 | Contract tests pass against current code | `contracts-all` passes |

**T056** -- Fix any failures found in T053-T055 and re-run until all gates pass.

---

## Failure Resolution

If `contracts-all` FAILS:
1. Read `Docs/Tests/contracts-all.summary` to identify failing tests
2. Open the failing test file and fix the assertion
3. Re-run only the affected test file first to verify the fix
4. Re-run the combined suite to confirm

If `full-regression` FAILS with NEW failures (not the 39 known ones):
1. Read `Docs/Tests/full-regression.summary` to identify new failures
2. Determine if the contract test files introduced import side effects
3. Fix without modifying existing source code
4. Re-run until clean

---

## Critical Constraints

- Do NOT modify any application source code files
- Do NOT modify `11-specify.md` (that was A1's job in Wave 1)
- You MAY fix test files written by A2/A3/A4 if they have assertion errors
- The 39 known pre-existing failures are expected -- do not count them as regressions
- New contract tests must not interfere with existing tests (no shared state, no
  module-level side effects)

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## Gate Check

When all tasks T053-T056 are complete:

1. Confirm `contracts-all` status is PASSED
2. Confirm `full-regression` shows zero new failures vs 977 baseline
3. Confirm all 10 success criteria are verified
4. Notify the Orchestrator that Wave 4 is complete -- spec-11 is done
