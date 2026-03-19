# A4: Regression Gate -- Spec 12 Error Handling

**Wave**: 4 of 4 | **Branch**: `012-error-handling`

---

## This Is Your Briefing File

Your orchestrator spawned you with the prompt:
> "Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/A4-regression.md FIRST, then await further instructions."

After you finish reading this file in full, signal readiness to the orchestrator by posting:

```
A4 ready -- briefing complete
```

The orchestrator will then send you specific task assignments via `SendMessage`. Execute each task as it arrives, using the MCP tools and task details in this file as your reference.

---

## Agent Configuration

| Field | Value |
|-------|-------|
| **subagent_type** | `quality-engineer` |
| **model** | `claude-sonnet-4-6` |
| **rationale** | Regression analysis and report writing; Sonnet is sufficient for test suite analysis |

---

## MCP Tools Available

Use these tools during verification and before writing your final report.

| Tool | When to use |
|------|-------------|
| `mcp__serena__find_symbol` | Verify the 4 new handlers exist in `backend/main.py` after A2's work (final sanity check) |
| `mcp__serena__get_symbols_overview` | Confirm both new test files exist and contain expected test classes |
| `mcp__gitnexus__detect_changes` | Run before writing the final report to confirm only expected files were changed (`backend/main.py` + 2 test files) |

---

## Prerequisites

1. Confirm `Docs/Tests/spec12-us5-final.status` contains `PASSED` (A3 complete).
2. Read `Docs/Tests/spec12-a1-audit.md` for the pre-implementation baseline.
3. Read `Docs/Tests/spec12-us1.status` and `Docs/Tests/spec12-us2-us4.status` -- both must show `PASSED`.

If any prerequisite is not met, stop and notify the orchestrator.

---

## Mission

Run the full test suite, verify zero regressions against the 1250 existing tests, fix any test assertions that reference the old (wrong) `ProviderRateLimitError` handler format, and write a final report.

---

## Critical Rules

- **NEVER run pytest inside Claude Code.** Use `zsh scripts/run-tests-external.sh` only.
- **NEVER modify production code** (`backend/main.py`, `backend/errors.py`, etc.) -- A2 has already completed those changes. If you find a production bug, flag it to the orchestrator.
- If regressions are found, fix them in test files only (update stale test assertions). Exception: if a production code bug is identified, flag it rather than silently patching tests.
- The 39 pre-existing failures must remain unchanged -- do NOT attempt to fix them.

---

## Tasks (T037-T040)

### T037: Run full test suite

```bash
zsh scripts/run-tests-external.sh -n spec12-regression tests/
```

This will take 1-3 minutes. Poll:

```bash
cat Docs/Tests/spec12-regression.status
```

Expected statuses: `RUNNING` → `PASSED` or `FAILED`

Wait until status is no longer `RUNNING` before proceeding.

### T038: Analyze regression summary

```bash
cat Docs/Tests/spec12-regression.summary
```

Verify all of the following:

**a. All 1250 existing tests still pass**
Expected test count: 1250 previously passing + ~35-50 new spec-12 tests.

**b. All new spec-12 tests pass**
New test files:
- `tests/unit/test_error_contracts.py` -- 7 test classes, ~25-35 test methods
- `tests/integration/test_error_handlers.py` -- 4 test classes, ~20 test methods

**c. Pre-existing 39 failures unchanged**
These 39 failures are pre-existing and known. They must NOT change count upward or downward. If any of these newly pass (unexpected), note it but do not block.

**d. Zero new failures**
Any failure not in the 39 known pre-existing failures is a regression. Each one must be investigated.

If all criteria pass → proceed to T040.
If any new failures found → proceed to T039.

### T039: Fix regressions (if any)

For each new failure found in T038:

**Step 1: Identify the failure**

Read `Docs/Tests/spec12-regression.log` and find the failing test name and assertion.

**Step 2: Classify the failure**

- **Stale test asserting old handler format**: A test that asserts `{"type": "error", ..., "code": "rate_limit"}` (the old wrong format). Fix: update the test assertion to match the new nested envelope `{"error": {"code": "PROVIDER_RATE_LIMIT", ...}, "trace_id": ...}`.

  ```bash
  # Search for tests asserting the old format:
  grep -rn '"rate_limit"' tests/
  grep -rn '"type": "error"' tests/  # (in non-chat tests)
  ```

- **Import error due to new import in `backend/main.py`**: If adding the new import (`from backend.errors import EmbeddinatorError, ...`) caused a circular import. Fix: check `backend/errors.py` for any import of `backend.main`. If found, flag to the orchestrator -- do not change imports silently.

- **Test failing due to changed handler behavior**: A test that was previously hitting FastAPI's default 500 handler and asserting `{"detail": "Internal Server Error"}` -- now it hits the new `EmbeddinatorError` handler and returns `{"error": {"code": "INTERNAL_ERROR"}, "trace_id": ""}`. Fix: update the test assertion to match the new response.

- **Production bug**: If the handler itself is returning wrong data. Flag to the orchestrator -- do not patch tests to hide a production bug.

**Step 3: Apply fix to test files only**

Only modify test files. Use the Edit tool with precise old_string/new_string.

**Step 4: Document the fix**

Record in your final report: test file, test name, old assertion, new assertion, reason.

### T040: Re-run if fixes applied and write final report

If T039 made changes:

```bash
zsh scripts/run-tests-external.sh -n spec12-regression-final tests/
```

Wait for PASSED. Then run `mcp__gitnexus__detect_changes` to confirm changed file scope, and write the final report:

```
Docs/Tests/spec12-final-report.md
```

Report structure:

```markdown
# Spec 12 -- Final Regression Report
**Date**: 2026-03-17  |  **Agent**: A4  |  **Branch**: 012-error-handling

## Test Counts
- Pre-spec-12 baseline: 1250 passing
- New spec-12 tests added: [count]
- Total passing after spec-12: [count]
- Pre-existing failures (unchanged): 39
- New failures introduced: [0 expected]

## New Test Files
| File | Test Classes | Test Methods |
|------|-------------|-------------|
| tests/unit/test_error_contracts.py | 7 | [count] |
| tests/integration/test_error_handlers.py | 4 | [count] |

## Regressions Found and Fixed
[List each regression: test name, root cause, fix applied]
OR: "None -- zero regressions"

## Pre-existing Failures (unchanged)
These 39 failures existed before spec-12 and were not introduced by this spec.
They are tracked as known issues.

## Production Changes Summary
| File | Change |
|------|--------|
| backend/main.py | Fixed ProviderRateLimitError handler (body replacement) |
| backend/main.py | Added EmbeddinatorError handler (HTTP 500, INTERNAL_ERROR) |
| backend/main.py | Added QdrantConnectionError handler (HTTP 503, QDRANT_UNAVAILABLE) |
| backend/main.py | Added OllamaConnectionError handler (HTTP 503, OLLAMA_UNAVAILABLE) |
| backend/main.py | Added import: EmbeddinatorError, QdrantConnectionError, OllamaConnectionError |

## Status
COMPLETE -- All handlers standardised. All contracts locked. Zero regressions.
```

---

## What Counts as a "Pre-existing Failure"

The 39 pre-existing failures are documented in prior spec implementations. Common ones:
- `test_config.py::test_default_settings`
- 3 conversation graph failures: `SessionContinuity`, `ClarificationInterrupt`, `TwoRoundClarificationCap`
- `test_app_startup` (LangGraph strict checkpointer type validation vs AsyncMock)
- Schema migration and stale DB tests

If the regression run produces exactly 39 failures AND all of them are in these known categories, the gate passes.

---

## Success Criteria

Gate PASSES when:
1. `spec12-regression.status` (or `spec12-regression-final.status`) = `PASSED`
2. Total test count >= 1285 (1250 existing + 35 new minimum)
3. Number of pre-existing failures = 39 (unchanged)
4. Number of new failures = 0

---

## Reference Documents

- Tasks: `specs/012-error-handling/tasks.md` -- Phase 6
- Plan (testing protocol): `specs/012-error-handling/plan.md` -- "Testing Protocol"
- A1 audit: `Docs/Tests/spec12-a1-audit.md`
- A3 gate: `Docs/Tests/spec12-us5-final.status`
