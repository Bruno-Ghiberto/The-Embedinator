#!/usr/bin/env bash
# test-gate-baseline.sh — behaviour tests for scripts/gate-baseline.sh.
#
# WHY THIS FILE EXISTS
#   gate-baseline.sh turns "is this run green?" from a judgment made while reading
#   Docs/Tests/<run>.summary into a deterministic exit code. The rule it encodes is
#   the campaign's: zero failures and zero errors — never a pass count. A gate that
#   misreads a red run as green would launder a broken fix into evidence, so the
#   gate gets its tests before it gets its code.
#
# FIXTURE PROVENANCE
#   Every fixture reproduces a format seen in a real file, not one recalled:
#     - green summary line : Docs/Tests/s31-b2-baseline.summary
#     - failed summary line: Docs/Tests/s31-b1-026-red.summary
#     - error summary line : pytest terminal summary ("N error" / "N errors")
#     - status vocabulary  : scripts/run-tests-external.sh (RUNNING PASSED FAILED
#                            ERROR INTERRUPTED NO_TESTS); PASSED may be written on
#                            pytest exit 1 when coverage-gate.sh classifies the
#                            exit as coverage-only.
#
# USAGE
#   bash scripts/test-gate-baseline.sh
#
#   Exits 0 when every case passes, 1 otherwise. No arguments, no network, no
#   repository writes — every fixture lives in a temp directory.

set -uo pipefail

GATE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/gate-baseline.sh"

pass_count=0
fail_count=0
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

# summary_body <name> <exit> <pytest-line>
#   Reproduces the shape run-tests-external.sh writes to <name>.summary.
summary_body() {
  printf '=== Test Summary: %s ===\nDuration: 68s\nExit:     %s\nTarget:   tests/\n\n%s\n\n--- Coverage ---\nTOTAL                                    4064    568    86%%\n\nLog: /x/%s.log\n' \
    "$1" "$2" "$3" "$1"
}

# write_run <name> <status|-> <summary-body|->
#   "-" leaves that file absent.
write_run() {
  local name="$1" status="$2" body="$3"
  [[ "$status" != "-" ]] && printf '%s\n' "$status" > "$tmpdir/$name.status"
  [[ "$body" != "-" ]] && printf '%s\n' "$body" > "$tmpdir/$name.summary"
  return 0
}

# expect <label> <expected-exit> <run-name> [<output-must-contain>]
expect() {
  local label="$1" want="$2" run="$3" needle="${4:-}"
  local out got
  out="$(bash "$GATE" "$run" "$tmpdir" 2>&1)"
  got=$?
  if [[ "$got" -ne "$want" ]]; then
    echo "FAIL: $label — expected exit $want, got $got"
    printf '      %s\n' "$(printf '%s' "$out" | head -3)"
    fail_count=$((fail_count + 1))
    return
  fi
  if [[ -n "$needle" && "$out" != *"$needle"* ]]; then
    echo "FAIL: $label — output lacks '$needle'"
    printf '      %s\n' "$(printf '%s' "$out" | head -3)"
    fail_count=$((fail_count + 1))
    return
  fi
  echo "ok:   $label"
  pass_count=$((pass_count + 1))
}

GREEN_LINE='= 1553 passed, 34 skipped, 45 xfailed, 16 xpassed, 232 warnings in 64.89s (0:01:04) ='
RED_LINE='=================== 3 failed, 17 passed, 1 warning in 0.49s ===================='
ERR_LINE='============================== 2 errors in 0.51s ==============================='
NONE_LINE='============================ no tests ran in 0.01s ============================='

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

write_run green PASSED "$(summary_body green 0 "$GREEN_LINE")"
expect "green baseline exits 0"                              0 green "GREEN"
expect "green baseline reports the count tuple"              0 green "passed=1553 skipped=34 xfailed=45 xpassed=16 failed=0 errors=0"

write_run red FAILED "$(summary_body red 1 "$RED_LINE")"
expect "failed run exits 1"                                  1 red "RED"
expect "failed run reports failed=3"                         1 red "failed=3"

write_run errs ERROR "$(summary_body errs 1 "$ERR_LINE")"
expect "error run exits 1 and reports errors=2"              1 errs "errors=2"

write_run lie PASSED "$(summary_body lie 0 "$RED_LINE")"
expect "a PASSED status cannot outvote a failed count"       1 lie "RED"

write_run covonly PASSED "$(summary_body covonly 1 "$GREEN_LINE")"
expect "coverage-only exit 1 with status PASSED is green"    0 covonly "GREEN"

write_run running RUNNING -
expect "RUNNING run gives no verdict (exit 2)"               2 running "NO-VERDICT"

write_run nostatus - "$(summary_body nostatus 0 "$GREEN_LINE")"
expect "missing .status gives no verdict"                    2 nostatus "NO-VERDICT"

write_run nosummary PASSED -
expect "missing .summary gives no verdict"                   2 nosummary "NO-VERDICT"

write_run garbage PASSED "$(summary_body garbage 0 'nothing pytest-like on this line')"
expect "summary without a pytest result line gives no verdict" 2 garbage "NO-VERDICT"

write_run notests NO_TESTS "$(summary_body notests 5 "$NONE_LINE")"
expect "NO_TESTS is red, never green"                        1 notests "RED"

write_run interrupted INTERRUPTED "$(summary_body interrupted 2 "$GREEN_LINE")"
expect "INTERRUPTED is red even with a green-looking line"   1 interrupted "RED"

out="$(bash "$GATE" 2>&1)"
got=$?
if [[ "$got" -eq 2 && "$out" == *"usage"* ]]; then
  echo "ok:   no run name prints usage and exits 2"
  pass_count=$((pass_count + 1))
else
  echo "FAIL: no run name — expected usage + exit 2, got exit $got"
  fail_count=$((fail_count + 1))
fi

echo
echo "gate-baseline: $pass_count passed, $fail_count failed."
if [[ "$fail_count" -eq 0 ]]; then
  echo "PASS"
  exit 0
fi
echo "FAIL"
exit 1
