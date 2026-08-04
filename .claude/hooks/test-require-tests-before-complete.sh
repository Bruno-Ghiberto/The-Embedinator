#!/usr/bin/env bash
# test-require-tests-before-complete.sh — behaviour tests for the TaskCompleted gate.
#
# WHY THIS FILE EXISTS
#   `require-tests-before-complete.sh` is the mechanism that stops "the fix compiles"
#   from being recorded as "the fix works". A gate nobody tested is theatre, so the
#   gate itself gets a test suite that drives it exactly the way Claude Code does:
#   a TaskCompleted JSON payload on stdin, an exit code out.
#
#   Exit-code contract under test (see hooks docs, TaskCompleted event):
#     0 → completion proceeds
#     2 → completion is BLOCKED and stderr is shown to the model
#
# USAGE
#   bash .claude/hooks/test-require-tests-before-complete.sh
#
#   Exits 0 when every case passes, 1 on the first failure summary.
#   No arguments, no network, no repository writes — every case runs against a
#   throwaway project root under $TMPDIR.

set -uo pipefail

HOOK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/require-tests-before-complete.sh"

if [[ ! -f "$HOOK" ]]; then
  echo "FATAL: hook under test not found at $HOOK" >&2
  exit 1
fi

pass_count=0
fail_count=0

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# make_root — create a throwaway project root and echo its path.
make_root() {
  local root
  root="$(mktemp -d)"
  mkdir -p "$root/Docs/Tests"
  echo "$root"
}

# put_status <root> <name> <content> [age_seconds]
#   Write Docs/Tests/<name>.status. When age_seconds is given the file mtime is
#   backdated by that many seconds, which is how the staleness cases are built.
put_status() {
  local root="$1" name="$2" content="$3" age="${4:-0}"
  printf '%s\n' "$content" > "$root/Docs/Tests/${name}.status"
  if [[ "$age" -gt 0 ]]; then
    touch -d "@$(( $(date +%s) - age ))" "$root/Docs/Tests/${name}.status"
  fi
}

# payload <root> <task_name> — emit a TaskCompleted stdin payload.
payload() {
  local root="$1" task_name="$2"
  jq -n \
    --arg cwd "$root" \
    --arg name "$task_name" \
    '{
       session_id: "test-session",
       transcript_path: "/dev/null",
       cwd: $cwd,
       permission_mode: "default",
       hook_event_name: "TaskCompleted",
       task_id: "task-1",
       task_name: $name,
       task_description: ""
     }'
}

# expect_exit <expected_code> <label> <stdin_payload> [env assignments...]
expect_exit() {
  local expected="$1" label="$2" stdin_data="$3"
  shift 3

  local actual stderr_file
  stderr_file="$(mktemp)"

  if [[ $# -gt 0 ]]; then
    printf '%s' "$stdin_data" | env "$@" bash "$HOOK" >/dev/null 2>"$stderr_file"
  else
    printf '%s' "$stdin_data" | bash "$HOOK" >/dev/null 2>"$stderr_file"
  fi
  actual=$?

  if [[ "$actual" -eq "$expected" ]]; then
    # A block must always explain itself — an empty reason tells the model nothing.
    if [[ "$expected" -eq 2 && ! -s "$stderr_file" ]]; then
      echo "FAIL: $label — blocked with exit 2 but wrote an empty reason to stderr"
      fail_count=$(( fail_count + 1 ))
      rm -f "$stderr_file"
      return
    fi
    echo "ok:   $label"
    pass_count=$(( pass_count + 1 ))
  else
    echo "FAIL: $label — expected exit $expected, got $actual"
    echo "      stderr: $(head -c 300 "$stderr_file")"
    fail_count=$(( fail_count + 1 ))
  fi
  rm -f "$stderr_file"
}

# ---------------------------------------------------------------------------
# Case 1 — a task that claims no fix is none of the gate's business.
# ---------------------------------------------------------------------------
root="$(make_root)"
expect_exit 0 "non-fix task is allowed through" "$(payload "$root" "Update the harness README")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 2 — a fix claim with no evidence at all is the core block.
# ---------------------------------------------------------------------------
root="$(make_root)"
expect_exit 2 "fix claim with no evidence is blocked" "$(payload "$root" "BUG-054 proxy idle timeout")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 3 — stale evidence is not evidence.
#   Docs/Tests/ carries 42 stale June files. A gate that accepts any PASSED file
#   on disk is satisfied by a run from another month and gates nothing.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "PASSED" 604800   # 7 days old
expect_exit 2 "stale PASSED evidence is rejected" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 4 — the happy path: a fresh green run.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "PASSED"
expect_exit 0 "fresh PASSED green run is accepted" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 5 — a fresh failure blocks even though the task claims success.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "FAILED"
expect_exit 2 "fresh FAILED run blocks the claim" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 6 — you cannot claim done while the test is still in flight.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "RUNNING"
expect_exit 2 "RUNNING run blocks the claim" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 7 — a green run does not cancel out a sibling failure in the same window.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "PASSED"
put_status "$root" "s31-b0-074-green" "FAILED"
expect_exit 2 "a fresh sibling failure still blocks" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 8 — ERROR is not PASSED.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "ERROR"
expect_exit 2 "ERROR status blocks the claim" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 9 — NO_TESTS means the target selected nothing. It is not a pass.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "NO_TESTS"
expect_exit 2 "NO_TESTS status blocks the claim" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 10 — pre-campaign run names are archive, not evidence.
#   Only s31-* runs count. A fresh file named anything else must not satisfy it.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "baseline" "PASSED"
expect_exit 2 "a fresh non-s31 run name is not evidence" "$(payload "$root" "Fix BUG-054")"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 11 — malformed stdin fails CLOSED.
#   Exit 1 would be a non-blocking error and the task would complete anyway, so a
#   hook that cannot parse its input must block rather than wave the claim through.
# ---------------------------------------------------------------------------
expect_exit 2 "malformed stdin fails closed" "not json at all"

# ---------------------------------------------------------------------------
# Case 12 — empty stdin fails closed for the same reason.
# ---------------------------------------------------------------------------
expect_exit 2 "empty stdin fails closed" ""

# ---------------------------------------------------------------------------
# Case 13 — the human override releases the gate.
#   The override is an environment variable on the Claude Code process, which an
#   agent cannot set from a Bash tool call. It is deliberately human-only.
# ---------------------------------------------------------------------------
root="$(make_root)"
expect_exit 0 "human override releases the gate" "$(payload "$root" "Fix BUG-054")" \
  EMBEDINATOR_TEST_GATE=off
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 14 — a bug id anywhere in the description also arms the gate.
#   Renaming the task must not be a way around it.
# ---------------------------------------------------------------------------
root="$(make_root)"
stdin_data="$(jq -n --arg cwd "$root" '{
  cwd: $cwd, hook_event_name: "TaskCompleted", task_id: "t", task_name: "Wrap up",
  task_description: "Closes BUG-126 on the outage path"
}')"
expect_exit 2 "bug id in the description arms the gate" "$stdin_data"
rm -rf "$root"

# ---------------------------------------------------------------------------
# Case 15 — the freshness window is configurable and is actually honoured.
# ---------------------------------------------------------------------------
root="$(make_root)"
put_status "$root" "s31-b0-054-green" "PASSED" 600      # 10 minutes old
expect_exit 0 "evidence inside a widened window is accepted" "$(payload "$root" "Fix BUG-054")" \
  EMBEDINATOR_TEST_GATE_MAX_AGE=3600
expect_exit 2 "evidence outside a narrowed window is rejected" "$(payload "$root" "Fix BUG-054")" \
  EMBEDINATOR_TEST_GATE_MAX_AGE=60
rm -rf "$root"

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "require-tests-before-complete: ${pass_count} passed, ${fail_count} failed."

if [[ "$fail_count" -gt 0 ]]; then
  echo "FAIL"
  exit 1
fi

echo "PASS"
exit 0
