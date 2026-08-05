#!/usr/bin/env bash
# coverage-gate.sh — classify a pytest exit code 1 as coverage-only or a real failure.
#
# Sourced by scripts/run-tests-external.sh. Defines one function and has no side
# effects, so it is safe to source from a script running under `set -euo pipefail`.
#
# WHY THIS IS ITS OWN FILE
#   This function decides what PASSED means in Docs/Tests/<run>.status, and
#   .claude/hooks/require-tests-before-complete.sh gates task completion on that
#   word. It is the most consequential twenty lines in the test tooling, so it
#   lives where it can be driven directly by scripts/lib/test-coverage-gate.sh
#   instead of only through a full pytest run.

# coverage_only_failure <log_file>
#
#   Returns 0 when pytest's exit code 1 was caused by --cov-fail-under ALONE,
#   meaning every test that ran passed and the status may be recorded as PASSED.
#   Returns 1 in every other case, including every case it cannot positively
#   explain.
#
#   Fails closed by construction: each clause demands positive evidence. Absence
#   of a "FAILED" line is never treated as proof that nothing failed, because a
#   collection error, a crash, or a truncated log all produce that same absence.
coverage_only_failure() {
    local log_file="${1:-}"

    # No log, no evidence. A run that produced no output explains nothing.
    if [[ -z "$log_file" || ! -s "$log_file" ]]; then
        return 1
    fi

    # 1. Any reported failure or error disqualifies the run outright. Anchored at
    #    line start so a test NAME containing "failed" cannot trigger it.
    if grep -qE '^(FAILED|ERROR) ' "$log_file"; then
        return 1
    fi

    # 2. The coverage gate must be positively present. Without this line the
    #    exit 1 came from something else entirely and must not be laundered.
    #    Format verified against pytest_cov/plugin.py:415 (pytest-cov 7.1.0).
    if ! grep -qE '^FAIL Required test coverage of ' "$log_file"; then
        return 1
    fi

    # 3. A result summary must exist and must report passing tests.
    #    The `|| true` is defensive, not currently load-bearing: an all-skipped
    #    run makes this grep exit 1 (pytest omits zero counts, so there is no
    #    "passed" token at all), and run-tests-external.sh runs under
    #    `set -euo pipefail`. Today's only call site is an `if` condition, where
    #    `set -e` is suppressed — so keep it, because moving the call out of that
    #    condition would otherwise turn an all-skipped run into a hard abort.
    local result_line
    result_line="$(grep -E '[0-9]+ passed' "$log_file" | tail -1 || true)"
    if [[ -z "$result_line" ]]; then
        return 1
    fi

    # 4. That summary must be clean. Note "48 xfailed" does not match: the
    #    pattern requires digits, a space, then "failed" — the "x" breaks it.
    if printf '%s\n' "$result_line" | grep -qE '[0-9]+ (failed|error)'; then
        return 1
    fi

    return 0
}
