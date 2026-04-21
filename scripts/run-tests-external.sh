#!/usr/bin/env zsh
# ================================================================
# The Embedinator — Detached Test Runner for Claude Code Agents
# ================================================================
#
# PURPOSE
#   Runs pytest outside of Claude Code so test output doesn't
#   consume tokens. Results are written to files that agents
#   can read cheaply (~20 lines instead of ~2000).
#
# HOW IT WORKS
#   Default mode (no flags):
#     Launches pytest as an invisible background process via
#     setsid/nohup. The calling shell returns immediately.
#     Check progress via the .status file.
#
#   --visible mode:
#     Opens a NEW tmux pane where you can watch pytest run
#     in real-time. The calling shell still returns immediately.
#     Same output files are generated. Requires active tmux session.
#
#   --fg mode:
#     Runs pytest in the current terminal (blocking). Useful
#     for manual debugging. If stdout is a TTY, output streams
#     to both screen and log file simultaneously.
#
# OUTPUT FILES (in Docs/Tests/)
#   {name}.status   — 1 line: RUNNING | PASSED | FAILED | ERROR
#   {name}.summary  — ~20-30 lines: counts, failures, coverage
#   {name}.log      — Full pytest output (only grep this, never cat)
#
# ================================================================
#
# USAGE FOR CLAUDE CODE AGENTS
#
#   Step 1 — Launch:
#     zsh scripts/run-tests-external.sh -n myrun tests/unit/
#     → Returns immediately with file paths
#
#   Step 2 — Poll status (1 line, ~5 tokens):
#     cat Docs/Tests/myrun.status
#     → RUNNING | PASSED | FAILED | ERROR | NO_TESTS
#
#   Step 3 — Read summary when done (~20 lines, ~100 tokens):
#     cat Docs/Tests/myrun.summary
#
#   Step 4 — Debug specific failures only if needed:
#     grep "FAILED" Docs/Tests/myrun.log
#     grep -A5 "test_specific_name" Docs/Tests/myrun.log
#
#   NEVER read the full .log file — it defeats the purpose.
#
# USAGE FOR HUMANS
#
#   Watch tests live in a new tmux pane:
#     zsh scripts/run-tests-external.sh --visible -n myrun tests/
#
#   Run interactively in current terminal:
#     zsh scripts/run-tests-external.sh --fg tests/unit/
#
#   Quick smoke test (no coverage, minimal output):
#     zsh scripts/run-tests-external.sh --fg -n smoke --no-cov --quiet tests/unit/test_config.py
#
#   Full regression:
#     zsh scripts/run-tests-external.sh --visible -n full-regression tests/
#
#   Only unit tests, fail on first error:
#     zsh scripts/run-tests-external.sh --visible -n units --fail-fast tests/unit/
#
# ================================================================

set -euo pipefail

# ── Resolve project paths ──────────────────────────────────────
SCRIPT_DIR="${0:A:h}"
PROJECT_ROOT="${SCRIPT_DIR:h}"
OUTPUT_DIR="$PROJECT_ROOT/Docs/Tests"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"
DEPS_HASH_FILE="$VENV_DIR/.deps-hash"

# ── Defaults ───────────────────────────────────────────────────
RUN_NAME=""
MARKERS=""
FILTER=""
TEST_TARGET="tests/"
NO_COV=0
FAIL_FAST=0
QUIET=0
FOREGROUND=0
VISIBLE=0

# ── Parse arguments ────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        -n|--name)
            RUN_NAME="$2"; shift 2 ;;
        -m|--markers)
            MARKERS="$2"; shift 2 ;;
        -k|--filter)
            FILTER="$2"; shift 2 ;;
        --no-cov)
            NO_COV=1; shift ;;
        --fail-fast)
            FAIL_FAST=1; shift ;;
        --quiet)
            QUIET=1; shift ;;
        --fg)
            FOREGROUND=1; shift ;;
        --visible)
            VISIBLE=1; shift ;;
        -h|--help)
            cat <<'HELP'
Usage: scripts/run-tests-external.sh [OPTIONS] [TEST_TARGET]

Runs pytest outside Claude Code. Results go to Docs/Tests/.

Execution modes:
  (default)     Invisible background process (agents use this)
  --visible     Opens a new tmux pane (humans watch live)
  --fg          Runs in current terminal, blocking (manual debug)

Options:
  -n, --name NAME      Run identifier (default: YYYYMMDD-HHMMSS)
  -m, --markers EXPR   Pytest marker expression (e.g. "unit and not slow")
  -k, --filter EXPR    Pytest -k name filter
  --no-cov             Disable coverage collection (faster)
  --fail-fast          Stop on first failure (-x)
  --quiet              Minimal output (-q -q --tb=line)
  -h, --help           Show this help

Examples (for agents — invisible background):
  scripts/run-tests-external.sh -n t025-verify tests/
  scripts/run-tests-external.sh -n unit-only tests/unit/

Examples (for humans — visible tmux pane):
  scripts/run-tests-external.sh --visible -n full tests/
  scripts/run-tests-external.sh --visible -n quick --no-cov tests/unit/

Examples (interactive — blocks current terminal):
  scripts/run-tests-external.sh --fg tests/unit/

Output files (Docs/Tests/):
  {name}.status   → RUNNING | PASSED | FAILED | ERROR | NO_TESTS
  {name}.summary  → Token-efficient ~20 line summary
  {name}.log      → Full pytest output (grep only, never cat)
HELP
            exit 0 ;;
        -*)
            echo "Error: unknown option '$1'. Use -h for help." >&2
            exit 1 ;;
        *)
            TEST_TARGET="$1"; shift ;;
    esac
done

# ── Auto-generate run name ─────────────────────────────────────
if [[ -z "$RUN_NAME" ]]; then
    RUN_NAME="$(date +%Y%m%d-%H%M%S)"
fi

# ── Ensure output directory ────────────────────────────────────
mkdir -p "$OUTPUT_DIR"

# ── Output file paths ──────────────────────────────────────────
STATUS_FILE="$OUTPUT_DIR/${RUN_NAME}.status"
SUMMARY_FILE="$OUTPUT_DIR/${RUN_NAME}.summary"
LOG_FILE="$OUTPUT_DIR/${RUN_NAME}.log"

# ── Build relaunch args (used by both detach and visible) ──────
RELAUNCH_ARGS=(--fg -n "$RUN_NAME")
[[ -n "$MARKERS" ]] && RELAUNCH_ARGS+=(-m "$MARKERS")
[[ -n "$FILTER" ]]  && RELAUNCH_ARGS+=(-k "$FILTER")
(( NO_COV ))    && RELAUNCH_ARGS+=(--no-cov)
(( FAIL_FAST )) && RELAUNCH_ARGS+=(--fail-fast)
(( QUIET ))     && RELAUNCH_ARGS+=(--quiet)
RELAUNCH_ARGS+=("$TEST_TARGET")

# ── Dispatch: visible | detached | foreground ──────────────────
if (( ! FOREGROUND )); then

    if (( VISIBLE )); then
        # ── VISIBLE MODE: open a new tmux pane ──────────────────
        if [[ -z "${TMUX:-}" ]]; then
            echo "Error: --visible requires an active tmux session." >&2
            echo "Start tmux first or use --fg for foreground mode." >&2
            echo "Falling back to invisible background mode." >&2
            VISIBLE=0
        fi
    fi

    if (( VISIBLE )); then
        SCRIPT_ABS="${0:A}"
        QUOTED_ARGS="${(q)RELAUNCH_ARGS}"

        # Launch new tmux window with the test runner
        tmux new-window -n "test:$RUN_NAME" \
            "zsh -c 'echo \"\\033[96m══ The Embedinator Test Runner — $RUN_NAME ══\\033[0m\"; echo \"\"; zsh \"$SCRIPT_ABS\" ${RELAUNCH_ARGS[@]}; echo \"\"; if [[ \$? -eq 0 ]]; then echo \"\\033[92mAll tests passed. Press Enter to close.\\033[0m\"; else echo \"\\033[91mTests had failures. Press Enter to close.\\033[0m\"; fi; read -r'"

        echo "Test run '$RUN_NAME' launched in tmux window 'test:$RUN_NAME'"
        echo "  Status:  $STATUS_FILE"
        echo "  Summary: $SUMMARY_FILE"
        echo "  Log:     $LOG_FILE"
        exit 0
    fi

    # ── DETACHED MODE: invisible background process ────────────
    setsid nohup zsh "${0:A}" "${RELAUNCH_ARGS[@]}" \
        </dev/null &>/dev/null &
    BG_PID=$!

    echo "Test run '$RUN_NAME' launched (PID: $BG_PID)"
    echo "  Status:  $STATUS_FILE"
    echo "  Summary: $SUMMARY_FILE"
    echo "  Log:     $LOG_FILE"
    exit 0
fi

# ================================================================
# FOREGROUND EXECUTION (reached via --fg, --visible tab, or direct)
# ================================================================

# ── Helper: atomic status write ────────────────────────────────
write_status() {
    echo "$1" > "${STATUS_FILE}.tmp" && mv "${STATUS_FILE}.tmp" "$STATUS_FILE"
}

# Detect if stdout is a real terminal (--visible tab or --fg in terminal)
IS_TTY=0
[[ -t 1 ]] && IS_TTY=1

# ── Ensure venv exists and dependencies are current ────────────
ensure_venv() {
    local sys_python
    sys_python="$(command -v python3 2>/dev/null || true)"

    # 1. Verify system Python exists
    if [[ -z "$sys_python" ]]; then
        echo "FATAL: python3 not found on PATH" >&2
        return 1
    fi

    # 2. Create venv if missing or corrupted
    if [[ ! -x "$PYTHON" ]]; then
        (( IS_TTY )) && echo "Creating venv at $VENV_DIR ..."
        rm -rf "$VENV_DIR"
        "$sys_python" -m venv "$VENV_DIR"
        "$PIP" install --upgrade pip --quiet 2>/dev/null
    fi

    # 3. Collect all requirements files and compute combined hash
    local req_files=()
    for f in "$PROJECT_ROOT"/requirements*.txt; do
        [[ -f "$f" ]] && req_files+=("$f")
    done

    if [[ ${#req_files[@]} -eq 0 ]]; then
        (( IS_TTY )) && echo "Warning: no requirements*.txt found, skipping dep install"
        return 0
    fi

    local current_hash
    current_hash="$(cat "${req_files[@]}" | sha256sum | cut -d' ' -f1)"
    local stored_hash=""
    [[ -f "$DEPS_HASH_FILE" ]] && stored_hash="$(cat "$DEPS_HASH_FILE")"

    # 4. Install only if hash changed (or first run)
    if [[ "$current_hash" != "$stored_hash" ]]; then
        (( IS_TTY )) && echo "Dependencies changed — installing ..."
        for f in "${req_files[@]}"; do
            "$PIP" install -r "$f" --quiet 2>&1 | tail -5
        done
        if [[ $? -ne 0 ]]; then
            echo "FATAL: pip install failed" >&2
            return 1
        fi
        echo "$current_hash" > "$DEPS_HASH_FILE"
        (( IS_TTY )) && echo "Dependencies installed successfully"
    else
        (( IS_TTY )) && echo "Dependencies up to date (hash match)"
    fi

    return 0
}

# ── Validate venv ──────────────────────────────────────────────
if ! ensure_venv; then
    write_status "ERROR"
    {
        echo "ERROR: Failed to set up Python venv at $VENV_DIR"
        echo "Try manually: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    } > "$SUMMARY_FILE"
    (( IS_TTY )) && cat "$SUMMARY_FILE"
    exit 1
fi

# ── Mark as RUNNING ────────────────────────────────────────────
write_status "RUNNING"

# ── Record start time ──────────────────────────────────────────
START_EPOCH=$(date +%s)

# ── Write log header ───────────────────────────────────────────
{
    echo "=== The Embedinator Test Run: $RUN_NAME ==="
    echo "Started:  $(date -Iseconds)"
    echo "Host:     $(hostname)"
    echo "Python:   $($PYTHON --version 2>&1)"
    echo "Venv:     $VENV_DIR"
    echo "Target:   $TEST_TARGET"
    echo "Markers:  ${MARKERS:-<all>}"
    echo "Filter:   ${FILTER:-<none>}"
    echo "Coverage: $( (( NO_COV )) && echo "disabled" || echo "enabled" )"
    echo "FailFast: $( (( FAIL_FAST )) && echo "yes" || echo "no" )"
    echo "Quiet:    $( (( QUIET )) && echo "yes" || echo "no" )"
    echo "========================================"
    echo ""
} > "$LOG_FILE"

# Show header on screen if in a terminal
(( IS_TTY )) && cat "$LOG_FILE"

# ── Build pytest command ───────────────────────────────────────
PYTEST_CMD=("$PYTHON" -m pytest "$TEST_TARGET")

[[ -n "$MARKERS" ]] && PYTEST_CMD+=(-m "$MARKERS")
[[ -n "$FILTER" ]]  && PYTEST_CMD+=(-k "$FILTER")
# Only pass --no-cov if pytest-cov is installed (avoids unrecognized argument error)
if (( NO_COV )) && "$PYTHON" -c "import pytest_cov" 2>/dev/null; then
    PYTEST_CMD+=(--no-cov)
fi
(( FAIL_FAST )) && PYTEST_CMD+=(-x)
(( QUIET ))     && PYTEST_CMD+=(-q -q --tb=line --no-header)

# Log the command being run
echo "Command: ${PYTEST_CMD[*]}" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
(( IS_TTY )) && echo "Command: ${PYTEST_CMD[*]}" && echo ""

# ── Execute pytest ─────────────────────────────────────────────
cd "$PROJECT_ROOT"

# Temporarily relax error handling to capture pytest exit code
set +eo pipefail

if (( IS_TTY )); then
    # Terminal mode: stream to both screen AND log file
    "${PYTEST_CMD[@]}" 2>&1 | tee -a "$LOG_FILE"
    EXIT_CODE="${pipestatus[1]}"
else
    # Background mode: log file only (no stdout)
    "${PYTEST_CMD[@]}" >> "$LOG_FILE" 2>&1
    EXIT_CODE=$?
fi

set -eo pipefail

# ── Record timing ──────────────────────────────────────────────
END_EPOCH=$(date +%s)
DURATION=$(( END_EPOCH - START_EPOCH ))

# Append timing to log
echo "" >> "$LOG_FILE"
echo "=== Completed in ${DURATION}s (exit code: $EXIT_CODE) ===" >> "$LOG_FILE"

# ── Generate token-efficient summary ───────────────────────────
{
    echo "=== Test Summary: $RUN_NAME ==="
    echo "Duration: ${DURATION}s"
    echo "Exit:     $EXIT_CODE"
    echo "Target:   $TEST_TARGET"
    [[ -n "$MARKERS" ]] && echo "Markers:  $MARKERS"
    [[ -n "$FILTER" ]]  && echo "Filter:   $FILTER"
    echo ""

    # Extract the pytest result line (e.g. "= 334 passed, 20 skipped in 45.2s =")
    RESULT_LINE=$(tail -20 "$LOG_FILE" | grep -E "[0-9]+ passed" | tail -1 || true)
    if [[ -n "$RESULT_LINE" ]]; then
        echo "$RESULT_LINE"
        echo ""
    fi

    # Extract failed test names
    FAILED_TESTS=$(grep -E "^FAILED " "$LOG_FILE" 2>/dev/null || true)
    if [[ -n "$FAILED_TESTS" ]]; then
        FAIL_COUNT=$(echo "$FAILED_TESTS" | wc -l | tr -d ' ')
        echo "--- Failed ($FAIL_COUNT) ---"
        echo "$FAILED_TESTS"
        echo ""
    fi

    # Extract error lines
    ERROR_TESTS=$(grep -E "^ERROR " "$LOG_FILE" 2>/dev/null || true)
    if [[ -n "$ERROR_TESTS" ]]; then
        ERR_COUNT=$(echo "$ERROR_TESTS" | wc -l | tr -d ' ')
        echo "--- Errors ($ERR_COUNT) ---"
        echo "$ERROR_TESTS"
        echo ""
    fi

    # Extract coverage total line
    COV_LINE=$(grep -E "^TOTAL\s+" "$LOG_FILE" 2>/dev/null | tail -1 || true)
    if [[ -n "$COV_LINE" ]]; then
        echo "--- Coverage ---"
        echo "$COV_LINE"
        echo ""
    fi

    echo "Log: $LOG_FILE"

} > "$SUMMARY_FILE"

# ── Write final status atomically ──────────────────────────────
case $EXIT_CODE in
    0) FINAL_STATUS="PASSED" ;;
    1) FINAL_STATUS="FAILED" ;;
    2) FINAL_STATUS="INTERRUPTED" ;;
    5) FINAL_STATUS="NO_TESTS" ;;
    *) FINAL_STATUS="ERROR" ;;
esac

write_status "$FINAL_STATUS"

# Print summary to screen if in a terminal
if (( IS_TTY )); then
    echo ""
    echo "─────────────────────────────────────────"
    cat "$SUMMARY_FILE"
fi

exit $EXIT_CODE
