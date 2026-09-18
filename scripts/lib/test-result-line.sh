#!/usr/bin/env bash
# test-result-line.sh — behaviour tests for the pytest result-line extractor.
#
# WHY THIS FILE EXISTS
#   run-tests-external.sh writes Docs/Tests/<run>.summary, and
#   scripts/gate-baseline.sh refuses a verdict (NO-VERDICT, exit 2) when that
#   file has no pytest result line. Before this fix, the extraction only
#   recognised "[0-9]+ passed", so a run where every test failed, or only
#   errored (e.g. a collection ImportError), wrote no result line at all —
#   every strict-TDD RED step where all new tests fail lost its verdict.
#
#   pytest_result_line must return the terminal result line whatever the
#   counts are, while never returning run-tests-external.sh's own appended
#   "=== Completed in Ns (exit code: N) ===" line or a coverage "TOTAL ..."
#   line — both of which can sit in the same tail window as the real line.
#
# FIXTURE PROVENANCE
#   - all-fail line, runner "Completed in" line: run q014-ref-red (2026-09-18)
#   - error-only line, TOTAL line               : scripts/lib/test-coverage-gate.sh
#   - mixed line, "no tests ran" line            : scripts/test-gate-baseline.sh
#
# USAGE
#   bash scripts/lib/test-result-line.sh
#
#   Runs every case; exits 0 when all pass, 1 when any fails.
#   No arguments, no network, no repository writes — every fixture is a temp file.

set -uo pipefail

LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/result-line.sh"

if [[ -f "$LIB" ]]; then
  # shellcheck source=./result-line.sh
  source "$LIB"
else
  echo "WARNING: library under test not found at $LIB — every real case below" >&2
  echo "         is expected to fail; only the harness-sanity case may pass." >&2
fi

pass_count=0
fail_count=0
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# make_log <name> <content> — write a fixture log and echo its path.
make_log() {
  local name="$1" content="$2"
  local path="$tmpdir/${name}.log"
  printf '%s\n' "$content" > "$path"
  echo "$path"
}

# expect <label> <expected-line> <log_path>
#   expected-line may be empty to mean "no result line".
expect() {
  local label="$1" expected="$2" log_path="$3"
  local actual
  actual="$(pytest_result_line "$log_path" 2>&1)"

  if [[ "$actual" == "$expected" ]]; then
    echo "ok:   $label"
    pass_count=$(( pass_count + 1 ))
  else
    echo "FAIL: $label"
    echo "      expected: $expected"
    echo "      actual:   $actual"
    fail_count=$(( fail_count + 1 ))
  fi
}

# ---------------------------------------------------------------------------
# Case 0 — harness sanity, independent of pytest_result_line. Proves the
#   fixture/compare machinery itself works even when every case below is a
#   clean "function not found" failure (e.g. before result-line.sh exists).
# ---------------------------------------------------------------------------
sanity_log="$(make_log sanity "hello")"
if [[ "$(cat "$sanity_log")" == "hello" ]]; then
  echo "ok:   harness sanity — make_log writes and reads back a fixture"
  pass_count=$(( pass_count + 1 ))
else
  echo "FAIL: harness sanity — make_log fixture round-trip broken"
  fail_count=$(( fail_count + 1 ))
fi

ALL_FAIL_LINE='========================= 2 failed, 1 warning in 0.42s ========================='
ERROR_ONLY_LINE='========================== 1 error in 0.40s ==========================='
MIXED_LINE='=================== 3 failed, 17 passed, 1 warning in 0.49s ===================='
ALL_PASS_LINE='========================= 334 passed, 20 skipped in 45.2s ========================='
NO_TESTS_LINE='============================ no tests ran in 0.01s ============================='
DURATION_PAREN_LINE='= 1553 passed, 34 skipped, 45 xfailed, 16 xpassed, 232 warnings in 64.89s (0:01:04) ='
COMPLETED_LINE='=== Completed in 2s (exit code: 1) ==='

# ---------------------------------------------------------------------------
# Case 1 — all-fail line, no "passed" token at all (the bug's own repro:
#   run q014-ref-red, exit code 1, two FAILED tests).
# ---------------------------------------------------------------------------
log="$(make_log allfail "collecting ...
tests/unit/test_golden_qa.py FF                                          [100%]

=========================== short test summary info ============================
FAILED tests/unit/test_golden_qa.py::test_one
FAILED tests/unit/test_golden_qa.py::test_two
$ALL_FAIL_LINE

$COMPLETED_LINE")"
expect "all-fail line is extracted despite no 'passed' token" "$ALL_FAIL_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 2 — errors-only line (a collection ImportError, nothing ran at all).
# ---------------------------------------------------------------------------
log="$(make_log errorsonly "==================================== ERRORS ====================================
ERROR tests/unit/test_broken.py - ImportError: cannot import name 'Missing'
=========================== short test summary info ============================
ERROR tests/unit/test_broken.py
$ERROR_ONLY_LINE

$COMPLETED_LINE")"
expect "errors-only line is extracted" "$ERROR_ONLY_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 3 — mixed line: some failed, some passed.
# ---------------------------------------------------------------------------
log="$(make_log mixed "$MIXED_LINE

$COMPLETED_LINE")"
expect "mixed failed+passed line is extracted" "$MIXED_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 4 — all-pass line (regression: must still work exactly as before).
# ---------------------------------------------------------------------------
log="$(make_log allpass "$ALL_PASS_LINE

$COMPLETED_LINE")"
expect "all-pass line still extracted (no regression)" "$ALL_PASS_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 5 — runner's own "Completed in Ns (exit code: N)" line sits right
#   after the real result line, in the same tail window. It must never be
#   returned even though it matches the same "=+ ... in [0-9.]+s" shape
#   scripts/gate-baseline.sh accepts.
# ---------------------------------------------------------------------------
log="$(make_log withcompleted "$ALL_FAIL_LINE

$COMPLETED_LINE")"
expect "runner's 'Completed in' line is never returned" "$ALL_FAIL_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 6 — a coverage TOTAL line sits just above the real result line.
# ---------------------------------------------------------------------------
log="$(make_log withtotal "---------------------------------------------------------------------
TOTAL                                    4429   4168     6%
FAIL Required test coverage of 80% not reached. Total coverage: 5.89%
=========================== short test summary info ============================
FAILED tests/unit/test_golden_qa.py::test_one
$ALL_FAIL_LINE

$COMPLETED_LINE")"
expect "coverage TOTAL line is never returned" "$ALL_FAIL_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 7 — no result line at all (pytest crashed before printing one).
# ---------------------------------------------------------------------------
log="$(make_log noresult "Traceback (most recent call last):
  File \"pytest\", line 1, in <module>
SystemExit: 3

$COMPLETED_LINE")"
expect "no result line at all yields empty output" "" "$log"

# ---------------------------------------------------------------------------
# Case 8 (bonus) — "no tests ran", the count-free pytest form.
# ---------------------------------------------------------------------------
log="$(make_log notests "$NO_TESTS_LINE

$COMPLETED_LINE")"
expect "'no tests ran' line is extracted" "$NO_TESTS_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 9 (bonus) — a trailing (H:MM:SS) duration alongside the seconds form.
# ---------------------------------------------------------------------------
log="$(make_log longrun "$DURATION_PAREN_LINE

$COMPLETED_LINE")"
expect "line with a trailing (H:MM:SS) duration is extracted" "$DURATION_PAREN_LINE" "$log"

# ---------------------------------------------------------------------------
# Case 10 (bonus) — missing log file fails closed to empty output, not an error.
# ---------------------------------------------------------------------------
expect "a missing log file yields empty output" "" "$tmpdir/does-not-exist.log"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "result-line: ${pass_count} passed, ${fail_count} failed."

if [[ "$fail_count" -gt 0 ]]; then
  echo "FAIL"
  exit 1
fi

echo "PASS"
exit 0
