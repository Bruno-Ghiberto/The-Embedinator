#!/usr/bin/env bash
# require-tests-before-complete.sh — Claude Code `TaskCompleted` gate.
#
# WHY THIS EXISTS (spec-31 task 0.7)
#   The v1.0 launch decision is NO-GO because eleven CRITICAL bugs survived a full
#   hunt. The fix wave that answers it closes 38 records across roughly eleven
#   sessions, and the failure mode that produced the NO-GO in the first place is
#   an agent recording "the fix compiles" as "the fix works".
#
#   This hook makes the distinction mechanical instead of aspirational: a task that
#   claims a bug is fixed cannot be marked complete unless a test run for it
#   actually finished and actually passed, recently.
#
# THE EVIDENCE PROTOCOL
#   `scripts/run-tests-external.sh` is the only sanctioned way to run pytest in this
#   repository (bare `pytest` is denied at the permission layer). Every run writes:
#
#       Docs/Tests/{name}.status   → one of RUNNING PASSED FAILED ERROR
#                                            INTERRUPTED NO_TESTS
#
#   That file is therefore the only durable proof in the repository that a test
#   genuinely executed. This hook reads it and nothing else. It never runs tests
#   itself — a gate that produces its own evidence proves nothing.
#
#   Three properties make the check meaningful rather than decorative:
#
#     1. FRESHNESS. `Docs/Tests/` holds dozens of stale runs from previous months.
#        A gate that accepts any PASSED file on disk is satisfied by somebody
#        else's June run and gates nothing. Only runs newer than
#        EMBEDINATOR_TEST_GATE_MAX_AGE count.
#     2. NAMESPACE. Only `s31-*` run names count, per the campaign convention
#        `s31-b{N}-{bug}-{red|green}`. Everything else in that directory is archive.
#     3. NO FRESH FAILURES. One green run does not cancel out a sibling that just
#        failed, and a run still in flight is not a result at all.
#
# CONTRACT (Claude Code hooks, TaskCompleted event)
#   stdin  — JSON payload; this hook reads .cwd, .task_name, .task_description
#   exit 0 — completion proceeds
#   exit 2 — completion is BLOCKED and stderr is shown to the model as the reason
#
#   Every other exit code is a NON-BLOCKING error: the task completes anyway. So
#   this hook must never exit 1 to signal a problem. Anything it cannot verify —
#   unparseable input, a missing JSON parser — fails CLOSED with exit 2, because
#   a gate that opens when it breaks is worse than no gate at all.
#
# CONFIGURATION (environment, read from the Claude Code process)
#   EMBEDINATOR_TEST_GATE=off        Release the gate entirely.
#   EMBEDINATOR_TEST_GATE_MAX_AGE=N  Freshness window in seconds (default 14400).
#
#   These are deliberately human-only. An agent cannot set an environment variable
#   on the Claude Code process from a Bash tool call, so the escape hatch belongs
#   to the operator and not to the actor being gated.
#
# WIRING
#   Register under `hooks.TaskCompleted` in `.claude/settings.local.json`. That
#   file is owned by the orchestrator; this script does not modify it.
#
# INSTALLATION NOTE
#   `.gitignore` ignores all of `.claude/`. This file is tracked only because it
#   was force-added (`git add -f`). A copy that was added without `-f` is invisible
#   to review.
#
# TESTS
#   bash .claude/hooks/test-require-tests-before-complete.sh

set -euo pipefail

# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

# Run names that count as campaign evidence. Everything else in Docs/Tests/ is
# pre-campaign archive.
readonly EVIDENCE_GLOB='s31-*.status'

# Task text that arms the gate. Matched case-insensitively against
# "<task_name> <task_description>" so that renaming the task is not a way around
# it. A task that claims no fix is none of this gate's business.
readonly FIX_CLAIM_PATTERN='(BUG-[0-9]+|\bfix(e[ds])?\b|\bbugfix\b|\bresolve[ds]?\b|\bpatch(e[ds])?\b|\brepair(ed|s)?\b|\bregression\b)'

# Statuses that are affirmatively good. Everything else — including NO_TESTS,
# which means the target selected nothing — is not a pass.
readonly PASS_STATUS='PASSED'

readonly DEFAULT_MAX_AGE_SECONDS=14400   # 4 hours

# ---------------------------------------------------------------------------
# Outcome helpers
# ---------------------------------------------------------------------------

# block <reason...> — refuse the completion. stderr becomes what the model reads.
block() {
  echo "BLOCKED by require-tests-before-complete: $*" >&2
  echo "" >&2
  echo "This task claims a fix. Run its test through the sanctioned runner and let it finish:" >&2
  echo "  zsh scripts/run-tests-external.sh -n s31-b{N}-{bug}-green <target>" >&2
  echo "Then poll Docs/Tests/s31-b{N}-{bug}-green.status until it reads ${PASS_STATUS}." >&2
  echo "Compare against the known baseline before calling it green." >&2
  exit 2
}

allow() {
  exit 0
}

# ---------------------------------------------------------------------------
# Payload parsing
#
# Emits exactly two lines: the reported cwd, then the task text with all runs of
# whitespace collapsed so it cannot spill onto a third line. Returns non-zero when
# the payload is absent, malformed, or not a JSON object.
# ---------------------------------------------------------------------------
parse_payload() {
  local raw="$1"

  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$raw" | jq -er '
      if type != "object" then
        error("payload is not a JSON object")
      else
        (.cwd // ""),
        ((((.task_name // "") + " " + (.task_description // "")) | gsub("\\s+"; " ")))
      end
    ' 2>/dev/null
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "$raw" | python3 -c '
import json, re, sys

payload = json.load(sys.stdin)
if not isinstance(payload, dict):
    raise SystemExit(1)

text = "{} {}".format(payload.get("task_name") or "", payload.get("task_description") or "")
print(payload.get("cwd") or "")
print(re.sub(r"\s+", " ", text))
' 2>/dev/null
    return
  fi

  return 127
}

# ---------------------------------------------------------------------------
# file_mtime <path> — epoch seconds. GNU stat first, BSD stat second.
# ---------------------------------------------------------------------------
file_mtime() {
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# The operator override is checked before anything else so that a broken gate can
# always be released without editing this file.
if [[ "${EMBEDINATOR_TEST_GATE:-on}" == "off" ]]; then
  allow
fi

payload_raw="$(cat)"

if ! parsed="$(parse_payload "$payload_raw")"; then
  block "could not read the TaskCompleted payload (no jq or python3 available, or the payload was not valid JSON). Failing closed."
fi

if [[ -z "$parsed" ]]; then
  block "the TaskCompleted payload was empty. Failing closed rather than approving an unverified claim."
fi

reported_cwd="$(printf '%s\n' "$parsed" | sed -n '1p')"
task_text="$(printf '%s\n' "$parsed" | sed -n '2p')"

# Is this a fix claim at all?
if ! printf '%s' "$task_text" | grep -qEi "$FIX_CLAIM_PATTERN"; then
  allow
fi

# Resolve the project root the evidence is read from.
#
# The payload's own cwd wins, and the order matters. Teammates run in isolated git
# worktrees, and `run-tests-external.sh` derives its output directory from wherever it
# was invoked, so a worktree's results land in that worktree's Docs/Tests. Meanwhile
# CLAUDE_PROJECT_DIR can still name the main checkout. Letting that win would fail in
# both directions at once: a teammate holding a genuine green run gets blocked, and
# somebody else's green run in the main checkout clears a claim it never tested.
project_root="$reported_cwd"
[[ -z "$project_root" ]] && project_root="${CLAUDE_PROJECT_DIR:-}"
[[ -z "$project_root" ]] && project_root="$PWD"

evidence_dir="$project_root/Docs/Tests"

if [[ ! -d "$evidence_dir" ]]; then
  block "no test-evidence directory at ${evidence_dir}, so no test has ever run for this claim."
fi

max_age="${EMBEDINATOR_TEST_GATE_MAX_AGE:-$DEFAULT_MAX_AGE_SECONDS}"
if ! [[ "$max_age" =~ ^[0-9]+$ ]]; then
  block "EMBEDINATOR_TEST_GATE_MAX_AGE must be a whole number of seconds, got '${max_age}'."
fi

now="$(date +%s)"
cutoff=$(( now - max_age ))

fresh_passed=""
fresh_running=""
fresh_bad=""

shopt -s nullglob
for status_file in "$evidence_dir"/$EVIDENCE_GLOB; do
  mtime="$(file_mtime "$status_file")" || continue
  [[ -z "$mtime" ]] && continue
  (( mtime < cutoff )) && continue

  run_name="$(basename "$status_file" .status)"
  status="$(tr -d '[:space:]' < "$status_file")"

  case "$status" in
    "$PASS_STATUS") fresh_passed+="${run_name} " ;;
    RUNNING)        fresh_running+="${run_name} " ;;
    *)              fresh_bad+="${run_name}=${status:-<empty>} " ;;
  esac
done
shopt -u nullglob

# A run still in flight is not a result. Claiming completion over it is exactly the
# "the fix compiles" move this gate exists to stop.
if [[ -n "$fresh_running" ]]; then
  block "a test run is still in flight: ${fresh_running% }. Wait for it to reach a terminal status before marking this task complete."
fi

# One green run does not excuse a sibling that just failed.
if [[ -n "$fresh_bad" ]]; then
  block "recent runs did not pass: ${fresh_bad% }. Fix or explain these before marking this task complete."
fi

if [[ -z "$fresh_passed" ]]; then
  block "no ${EVIDENCE_GLOB} run in ${evidence_dir} passed within the last ${max_age}s. A stale run from an earlier session is not evidence for this fix."
fi

allow
