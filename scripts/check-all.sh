#!/usr/bin/env bash
# check-all.sh — run every deterministic gate once and print one verdict.
#
# WHY THIS EXISTS
#   Four gates decide whether a candidate is even worth reviewing: pre-commit
#   (ruff, ruff-format, whitespace, EOF — what the CI `pre-commit-parity` job
#   runs), the TypeScript typecheck, eslint, and vitest. Until now they were
#   spelled out in prose inside every writer prompt and run one at a time. This
#   script is that prose as code: every gate runs, every gate is reported, and
#   the exit code is the verdict.
#
#   Backend pytest is deliberately NOT here. It runs only through
#   scripts/run-tests-external.sh and is judged by scripts/gate-baseline.sh.
#
# ORDER
#   pre-commit runs first because it is the only gate that may rewrite files; the
#   checks after it see the normalized tree. When it rewrites anything it exits 1
#   and the gate reads FAIL — review the rewrite, then run again.
#
# EXIT CODES
#   0  every gate passed        → last line "check-all: ALL GREEN"
#   1  at least one gate failed → last line gives the count; each FAIL is named
#   2  NO-VERDICT               → a precondition is missing (frontend/package.json
#                                 or a tool on PATH); no gate runs
#
# LOGS
#   Full output of each gate: Docs/Tests/check-all/<gate>.log (overwritten every
#   run). On FAIL the last 25 lines are echoed under the gate line.
#
# USAGE
#   scripts/check-all.sh
#
# Behaviour tests: scripts/test-check-all.sh

set -uo pipefail

repo="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fe="$repo/frontend"
logdir="$repo/Docs/Tests/check-all"

no_verdict() {
  echo "check-all: NO-VERDICT — $1" >&2
  exit 2
}

# --- preconditions: refuse to render a verdict on a broken setup ---------------
[[ -f "$fe/package.json" ]] || no_verdict "frontend/package.json not found under $repo"
for tool in pre-commit npm; do
  command -v "$tool" >/dev/null 2>&1 || no_verdict "$tool is not on PATH"
done
mkdir -p "$logdir"

# --- gates ---------------------------------------------------------------------
gates=(pre-commit typecheck lint vitest)
declare -A gate_dir=(
  [pre-commit]="$repo"
  [typecheck]="$fe"
  [lint]="$fe"
  [vitest]="$fe"
)
declare -A gate_cmd=(
  [pre-commit]="pre-commit run --all-files"
  [typecheck]="npm run typecheck"
  [lint]="npm run lint"
  [vitest]="npm test"
)

echo "check-all @ $(date '+%Y-%m-%d %H:%M:%S') — $repo"
failed=0
for gate in "${gates[@]}"; do
  log="$logdir/$gate.log"
  # shellcheck disable=SC2086  # word-splitting the command string is intended
  ( cd "${gate_dir[$gate]}" && ${gate_cmd[$gate]} ) > "$log" 2>&1
  rc=$?
  if (( rc == 0 )); then
    printf '  %-11s PASS\n' "$gate"
  else
    printf '  %-11s FAIL (exit %d) → %s\n' "$gate" "$rc" "$log"
    tail -25 "$log" | sed 's/^/      /'
    failed=$((failed + 1))
  fi
done

if (( failed == 0 )); then
  echo "check-all: ALL GREEN (${#gates[@]} gates)"
  exit 0
fi
echo "check-all: FAIL ($failed of ${#gates[@]} gates failed)"
exit 1
