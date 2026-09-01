#!/usr/bin/env bash
# test-check-all.sh — behaviour tests for scripts/check-all.sh.
#
# WHY THIS FILE EXISTS
#   check-all.sh is the single entry point for the four deterministic gates that
#   every candidate must clear before review (pre-commit, typecheck, lint, vitest).
#   Its whole value is the contract: run every gate, report each one, exit non-zero
#   if any failed, and refuse to render a verdict when a precondition is missing.
#   These tests pin that contract without running the real tools.
#
# HOW
#   The script under test is copied into a throwaway repository root, and the
#   commands it calls (pre-commit, npm) are shims placed first on PATH. Each shim
#   records its invocation and exits with a code taken from $rc_dir/<cmd>-<args>
#   when such a file exists, 0 otherwise. No production code is test-aware.
#
# USAGE
#   bash scripts/test-check-all.sh
#
#   Exits 0 when every case passes, 1 otherwise. No network, no repository writes.

set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/check-all.sh"

pass_count=0
fail_count=0
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

# ---------------------------------------------------------------------------
# Fake repository + shims
# ---------------------------------------------------------------------------

make_repo() {  # make_repo <dir>  — fresh fake root with the script copied in
  local root="$1"
  rm -rf "$root"
  mkdir -p "$root/scripts" "$root/frontend"
  printf '{"name":"fake","scripts":{"typecheck":"x","lint":"x","test":"x"}}\n' > "$root/frontend/package.json"
  : > "$root/.pre-commit-config.yaml"
  if [[ -f "$SRC" ]]; then
    cp "$SRC" "$root/scripts/check-all.sh"
    chmod +x "$root/scripts/check-all.sh"
  fi
}

bin="$tmpdir/bin"
rc_dir="$tmpdir/rc"
calls="$tmpdir/calls.log"
mkdir -p "$bin" "$rc_dir"

make_shim() {  # make_shim <command-name>
  cat > "$bin/$1" <<EOF
#!/usr/bin/env bash
name="\$(basename "\$0")"
echo "\$name \$*" >> "$calls"
key="\$name\${1:+-\$1}\${2:+-\$2}"
if [[ -f "$rc_dir/\$key" ]]; then exit "\$(cat "$rc_dir/\$key")"; fi
exit 0
EOF
  chmod +x "$bin/$1"
}
make_shim pre-commit
make_shim npm

reset() {  # reset — clear recorded calls and forced exit codes
  : > "$calls"
  rm -f "$rc_dir"/*
}

# run_check <root>  → sets $out and $got
run_check() {
  out="$(PATH="$bin:$PATH" bash "$1/scripts/check-all.sh" 2>&1)"
  got=$?
}

check() {  # check <label> <condition-exit-code>
  if [[ "$2" -eq 0 ]]; then
    echo "ok:   $1"
    pass_count=$((pass_count + 1))
  else
    echo "FAIL: $1"
    printf '      %s\n' "$(printf '%s' "${out:-}" | head -4)"
    fail_count=$((fail_count + 1))
  fi
}

# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------

repo="$tmpdir/repo"

# 1. Every gate green.
make_repo "$repo"; reset
run_check "$repo"
check "all gates green exits 0"                        $([[ "$got" -eq 0 ]]; echo $?)
check "all gates green prints ALL GREEN"                $([[ "$out" == *"ALL GREEN"* ]]; echo $?)
check "runs pre-commit over all files"                  $(grep -q '^pre-commit run --all-files' "$calls"; echo $?)
check "runs the typecheck script"                       $(grep -q '^npm run typecheck' "$calls"; echo $?)
check "runs the lint script"                            $(grep -q '^npm run lint' "$calls"; echo $?)
check "runs vitest"                                     $(grep -q '^npm test' "$calls"; echo $?)
check "pre-commit runs first (normalizers before checks)" $([[ "$(head -1 "$calls")" == pre-commit* ]]; echo $?)

# 2. One gate fails: reported by name, overall exit 1, later gates still run.
make_repo "$repo"; reset
echo 1 > "$rc_dir/npm-run-lint"
run_check "$repo"
check "a failing gate makes the overall exit 1"         $([[ "$got" -eq 1 ]]; echo $?)
check "the failing gate is named in the verdict"        $([[ "$out" == *"lint"*"FAIL"* ]]; echo $?)
check "gates after the failure still run"               $(grep -q '^npm test' "$calls"; echo $?)
check "a failing run does not print ALL GREEN"          $([[ "$out" != *"ALL GREEN"* ]]; echo $?)

# 3. Missing frontend directory: no verdict.
make_repo "$repo"; reset
rm -rf "$repo/frontend"
run_check "$repo"
check "missing frontend/ gives no verdict (exit 2)"     $([[ "$got" -eq 2 && "$out" == *"NO-VERDICT"* ]]; echo $?)

# 4. Missing tool: no verdict, nothing runs. A second shim dir holds only npm, and
#    PATH is reduced to it plus the directory bash lives in, so pre-commit (installed
#    under ~/.local/bin on this machine) cannot be resolved. The precondition is
#    asserted rather than assumed.
make_repo "$repo"; reset
bin_nopc="$tmpdir/bin-no-precommit"
mkdir -p "$bin_nopc"
cp "$bin/npm" "$bin_nopc/npm"
sysbin="$(dirname "$(command -v bash)")"
if PATH="$bin_nopc:$sysbin" command -v pre-commit >/dev/null 2>&1; then
  echo "FAIL: case 4 precondition — pre-commit resolves from $sysbin; cannot simulate a missing tool"
  fail_count=$((fail_count + 1))
else
  out="$(PATH="$bin_nopc:$sysbin" bash "$repo/scripts/check-all.sh" 2>&1)"; got=$?
  check "missing pre-commit gives no verdict (exit 2)"    $([[ "$got" -eq 2 && "$out" == *"NO-VERDICT"* ]]; echo $?)
  check "nothing runs when a tool is missing"             $([[ ! -s "$calls" ]]; echo $?)
fi

echo
echo "check-all: $pass_count passed, $fail_count failed."
if [[ "$fail_count" -eq 0 ]]; then
  echo "PASS"
  exit 0
fi
echo "FAIL"
exit 1
