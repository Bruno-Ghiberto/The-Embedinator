#!/usr/bin/env bash
# gate-baseline.sh — deterministic verdict for one external test run.
#
# WHY THIS EXISTS
#   The campaign rule is "gate against zero failures, never a pass count". Until
#   now that rule was applied by whoever read Docs/Tests/<run>.summary — an agent,
#   every time, at token cost and with judgment in the loop. This script is that
#   rule as code: it reads the two files run-tests-external.sh writes and exits
#   with the verdict. It never runs tests; a gate that produces its own evidence
#   proves nothing (the same principle as .claude/hooks/require-tests-before-complete.sh).
#
# VERDICTS / EXIT CODES
#   0  GREEN       status is a finished PASSED and the pytest result line reports
#                  failed=0 errors=0. Coverage below threshold does NOT make a run
#                  red here: run-tests-external.sh already records that case as
#                  PASSED (scripts/lib/coverage-gate.sh) and coverage is a separate
#                  gate.
#   1  RED         any failed/error count > 0, or a finished status other than
#                  PASSED (FAILED, ERROR, INTERRUPTED, NO_TESTS). Counts outvote the
#                  status word: PASSED next to "3 failed" is RED.
#   2  NO-VERDICT  nothing can be concluded — no run name, missing .status or
#                  .summary, status RUNNING, or no pytest result line in the
#                  summary. Fails closed.
#
# USAGE
#   scripts/gate-baseline.sh <run-name> [output-dir]
#     run-name    the -n value given to run-tests-external.sh
#     output-dir  defaults to <repo>/Docs/Tests
#
#   stdout: GATE <run>: <VERDICT> passed=N skipped=N xfailed=N xpassed=N failed=N errors=N status=<S>
#   stderr: the reason, whenever the verdict is not GREEN.
#
# Behaviour tests: scripts/test-gate-baseline.sh

set -uo pipefail

run="${1:-}"
if [[ -z "$run" ]]; then
  echo "usage: $0 <run-name> [output-dir]" >&2
  echo "GATE ?: NO-VERDICT"
  exit 2
fi

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dir="${2:-$repo/Docs/Tests}"
status_file="$dir/$run.status"
summary_file="$dir/$run.summary"

no_verdict() {
  echo "GATE $run: NO-VERDICT"
  echo "reason: $1" >&2
  exit 2
}

# --- status ------------------------------------------------------------------
[[ -f "$status_file" ]] || no_verdict "missing $status_file"
status="$(tr -d '[:space:]' < "$status_file")"
[[ "$status" == "RUNNING" ]] && no_verdict "run is still RUNNING"

# --- summary -----------------------------------------------------------------
[[ -f "$summary_file" ]] || no_verdict "missing $summary_file"

# pytest's terminal result line: "=+ <counts> in <seconds>s =+", including the
# count-free "no tests ran in 0.01s" form.
line="$(grep -E -m1 '^=+ .* in [0-9.]+s' "$summary_file" || true)"
[[ -n "$line" ]] || no_verdict "no pytest result line in $summary_file"

# count <token-regex> → integer, 0 when the token is absent. The leading space in
# the pattern is what keeps "16 xpassed" from counting as "passed" and "45 xfailed"
# from counting as "failed".
count() {
  local n
  n="$(printf '%s' "$line" | grep -oE "[0-9]+ $1\b" | head -1 | grep -oE '^[0-9]+' || true)"
  echo "${n:-0}"
}

passed="$(count passed)"
skipped="$(count skipped)"
xfailed="$(count xfailed)"
xpassed="$(count xpassed)"
failed="$(count failed)"
errors="$(count 'errors?')"

tuple="passed=$passed skipped=$skipped xfailed=$xfailed xpassed=$xpassed failed=$failed errors=$errors status=$status"

red() {
  echo "GATE $run: RED $tuple"
  echo "reason: $1" >&2
  exit 1
}

# --- verdict -----------------------------------------------------------------
if (( failed > 0 || errors > 0 )); then
  red "failed=$failed errors=$errors — the zero-failure rule is not met"
fi
if [[ "$status" != "PASSED" ]]; then
  red "status is $status, not PASSED"
fi

echo "GATE $run: GREEN $tuple"
exit 0
