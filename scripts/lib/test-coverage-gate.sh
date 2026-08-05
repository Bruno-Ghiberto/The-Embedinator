#!/usr/bin/env bash
# test-coverage-gate.sh — behaviour tests for the coverage-only exit-1 classifier.
#
# WHY THIS FILE EXISTS
#   run-tests-external.sh writes Docs/Tests/<run>.status, and
#   .claude/hooks/require-tests-before-complete.sh refuses to let a fix be marked
#   done unless that file reads PASSED. So `coverage_only_failure` decides what
#   "PASSED" MEANS for every run in the campaign.
#
#   pytest exits 1 for two unrelated reasons — a test failed, or --cov-fail-under
#   was not met. Only the second one may be laundered into PASSED. Get that wrong
#   in the permissive direction and a red run becomes evidence of a green fix,
#   silently, for every batch that follows.
#
#   An untested classifier of that consequence is exactly the "it compiles, ship
#   it" standard this campaign exists to reject.
#
# FIXTURE PROVENANCE
#   Every log fixture below uses formats verified against real output, not recalled:
#     - summary + FAILED lines : Docs/Tests/s31-baseline.log
#     - coverage FAIL line     : pytest_cov/plugin.py:415 (pytest-cov 7.1.0, .venv)
#
# USAGE
#   bash scripts/lib/test-coverage-gate.sh
#
#   Exits 0 when every case passes, 1 on the first failure summary.
#   No arguments, no network, no repository writes — every fixture is a temp file.

set -uo pipefail

LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/coverage-gate.sh"

if [[ ! -f "$LIB" ]]; then
  echo "FATAL: library under test not found at $LIB" >&2
  exit 1
fi

# shellcheck source=./coverage-gate.sh
source "$LIB"

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

# expect <coverage_only|real_failure> <label> <log_path>
#   coverage_only → the classifier must return 0 (exit 1 was the coverage gate alone)
#   real_failure  → the classifier must return non-zero (status must stay FAILED)
expect() {
  local expected="$1" label="$2" log_path="$3"

  coverage_only_failure "$log_path"
  local rc=$?

  local actual="real_failure"
  [[ "$rc" -eq 0 ]] && actual="coverage_only"

  if [[ "$actual" == "$expected" ]]; then
    echo "ok:   $label"
    pass_count=$(( pass_count + 1 ))
  else
    echo "FAIL: $label"
    echo "      expected $expected, got $actual (return $rc)"
    fail_count=$(( fail_count + 1 ))
  fi
}

COV_FAIL='FAIL Required test coverage of 80% not reached. Total coverage: 42.13%'

# ---------------------------------------------------------------------------
# Case 1 — the whole point: tests all passed, only the coverage gate tripped.
# ---------------------------------------------------------------------------
log="$(make_log case1 "collecting ...
tests/unit/test_confidence.py ..........                                 [100%]

$COV_FAIL
========================= 10 passed in 1.20s =========================")"
expect coverage_only "a green run that misses --cov-fail-under is coverage-only" "$log"

# ---------------------------------------------------------------------------
# Case 2 — the real baseline shape. 'xfailed' contains the substring 'failed',
#   and a classifier that scans loosely for it will call a green run red.
#   Summary copied from the shape in Docs/Tests/s31-baseline.log.
# ---------------------------------------------------------------------------
log="$(make_log case2 "$COV_FAIL
====== 1534 passed, 34 skipped, 48 xfailed, 16 xpassed, 203 warnings in 47.33s ======")"
expect coverage_only "xfailed/xpassed in the summary do not read as failures" "$log"

# ---------------------------------------------------------------------------
# Case 3 — a genuine test failure with no coverage complaint at all.
# ---------------------------------------------------------------------------
log="$(make_log case3 "=========================== short test summary info ============================
FAILED tests/unit/test_confidence.py::test_scores_five_signals - AssertionError
========================= 1 failed, 9 passed in 1.30s =========================")"
expect real_failure "a plain test failure stays FAILED" "$log"

# ---------------------------------------------------------------------------
# Case 4 — BOTH causes present. The coverage line must never launder a real
#   failure that happens to sit beside it.
# ---------------------------------------------------------------------------
log="$(make_log case4 "=========================== short test summary info ============================
FAILED tests/unit/test_confidence.py::test_scores_five_signals - AssertionError
$COV_FAIL
========================= 1 failed, 9 passed in 1.30s =========================")"
expect real_failure "a failure beside a coverage miss is still a failure" "$log"

# ---------------------------------------------------------------------------
# Case 5 — a collection error. Exit 1, no FAILED lines, nothing passed.
#   Inferring "no failures seen" from absence would wave this through.
# ---------------------------------------------------------------------------
log="$(make_log case5 "==================================== ERRORS ====================================
ERROR tests/unit/test_broken.py - ImportError: cannot import name 'Missing'
=========================== short test summary info ============================
ERROR tests/unit/test_broken.py
========================== 1 error in 0.40s ===========================")"
expect real_failure "a collection error is not a coverage-only pass" "$log"

# ---------------------------------------------------------------------------
# Case 6 — a teardown error alongside real passes and a coverage miss.
# ---------------------------------------------------------------------------
log="$(make_log case6 "=========================== short test summary info ============================
ERROR tests/integration/test_qdrant.py::test_upsert - RuntimeError: teardown
$COV_FAIL
===================== 9 passed, 1 error in 2.10s =====================")"
expect real_failure "an error beside a coverage miss is still a failure" "$log"

# ---------------------------------------------------------------------------
# Case 7 — exit 1 with no coverage complaint and no visible failure.
#   Cause unknown, so the honest answer is to stay FAILED rather than guess.
# ---------------------------------------------------------------------------
log="$(make_log case7 "collecting ...
========================= 10 passed in 1.20s =========================")"
expect real_failure "exit 1 with no coverage line fails closed" "$log"

# ---------------------------------------------------------------------------
# Case 8 — an empty log proves nothing.
# ---------------------------------------------------------------------------
log="$(make_log case8 "")"
expect real_failure "an empty log fails closed" "$log"

# ---------------------------------------------------------------------------
# Case 9 — a log that was never written at all (pytest died before output).
# ---------------------------------------------------------------------------
expect real_failure "a missing log file fails closed" "$tmpdir/does-not-exist.log"

# ---------------------------------------------------------------------------
# Case 10 — a passing test whose NAME contains 'failed', in verbose output.
#   Real test names in this repo do this (test_stall_forever, test_..._failed_upload),
#   so a classifier matching 'failed' anywhere would reject a green run.
# ---------------------------------------------------------------------------
log="$(make_log case10 "tests/unit/test_retry.py::test_handles_failed_upload PASSED               [ 50%]
tests/unit/test_retry.py::test_error_path_recovers PASSED                [100%]

$COV_FAIL
========================= 2 passed in 0.90s =========================")"
expect coverage_only "a test named '...failed...' does not read as a failure" "$log"

# ---------------------------------------------------------------------------
# Case 11 — captured output that mentions FAILED mid-line, in a green run.
#   Not contrived: this campaign's own suites assert on the literal status words
#   this script writes, so "FAILED" reaches the log as captured stdout. Only the
#   line-start anchor separates that from a real pytest failure line.
# ---------------------------------------------------------------------------
log="$(make_log case11 "----------------------------- Captured stdout call -----------------------------
gate rejected the claim because .status still reads FAILED for that run

$COV_FAIL
========================= 3 passed in 1.10s =========================")"
expect coverage_only "FAILED quoted mid-line in captured output is not a failure" "$log"

# ---------------------------------------------------------------------------
# Case 12 — a run where every test skipped, plus a coverage miss.
#   Directly reachable in this campaign: `run-tests-external.sh -n x tests/e2e_real/`
#   without E2E_REAL=1 skips the whole directory (tests/e2e_real/conftest.py:51),
#   and a directory-scoped run misses the 80% whole-codebase threshold by
#   construction. Nothing was proven, so nothing may be recorded as PASSED.
#   Note pytest omits zero counts, so the summary carries no "passed" token at all.
# ---------------------------------------------------------------------------
log="$(make_log case12 "$COV_FAIL
========================= 20 skipped in 2.10s =========================")"
expect real_failure "an all-skipped run is not evidence of anything" "$log"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "coverage-gate: ${pass_count} passed, ${fail_count} failed."

if [[ "$fail_count" -gt 0 ]]; then
  echo "FAIL"
  exit 1
fi

echo "PASS"
exit 0
