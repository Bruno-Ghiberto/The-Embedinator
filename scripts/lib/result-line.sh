#!/usr/bin/env bash
# result-line.sh — extract pytest's terminal result line from a run log.
#
# Sourced by scripts/run-tests-external.sh. Defines one function and has no
# side effects, so it is safe to source from a script running under
# `set -euo pipefail`.
#
# WHY THIS IS ITS OWN FILE
#   run-tests-external.sh used to grep the log for "[0-9]+ passed" alone when
#   building <run>.summary, so a run where every test failed (or only errored,
#   e.g. a collection ImportError) left no result line in the summary at all.
#   With no result line, scripts/gate-baseline.sh cannot find one either and
#   returns NO-VERDICT instead of RED. The gate itself fails closed, but every
#   strict-TDD RED step where all new tests fail loses its verdict this way.
#   The extraction lives here so it can be driven directly by
#   scripts/lib/test-result-line.sh instead of only through a full pytest run
#   — the same split coverage-gate.sh uses for the coverage-only classifier.

# pytest_result_line <log_file>
#
#   Prints pytest's own terminal result line — "=+ N passed/failed/... in
#   Ns =+", whatever the counts are — if the log has one; prints nothing
#   otherwise. Always exits 0: an empty result reports "no line found" the
#   same way scripts/gate-baseline.sh's own grep for this line does.
#
#   Must never return:
#     - run-tests-external.sh's own appended "=== Completed in Ns (exit code:
#       N) ===" line. That line also starts with "=+ " and ends with
#       " in [0-9.]+s" — the exact shape scripts/gate-baseline.sh accepts as a
#       pytest result line — so shape alone cannot tell the two apart.
#     - a coverage "TOTAL ..." line, which pytest-cov prints just above the
#       real result line.
#
#   What actually tells them apart is vocabulary: pytest's own terminal
#   summary always names at least one outcome (passed/failed/error(s)/
#   skipped/xfailed/xpassed/deselected) or reads "no tests ran"; neither
#   run-tests-external.sh's synthetic line nor pytest-cov's TOTAL line ever
#   does, so a second, narrower grep on that vocabulary is what excludes them
#   — not a stricter version of the shape both already share.
pytest_result_line() {
    local log_file="${1:-}"

    [[ -n "$log_file" && -f "$log_file" ]] || return 0

    tail -20 "$log_file" \
        | grep -E '^=+ .* in [0-9.]+s' \
        | grep -E '([0-9]+ (passed|failed|errors?|skipped|xfailed|xpassed|deselected))|(no tests ran)' \
        | tail -1 \
        || true
}
