#!/usr/bin/env bash
# validate-bug-records.sh — Spec-28 contract enforcement (session-directory-contract.md)
#
# Walks docs/E2E/*/bugs-raw/*.md and asserts that every bug record contains
# the 7 mandatory fields defined in data-model.md §2. Additionally, any
# record with Severity: Blocker MUST include an F/D/P decision.
#
# Exits 0 if all records are valid. Exits 1 on the first violation found.
#
# Usage:
#   ./scripts/validate-bug-records.sh
#   ./scripts/validate-bug-records.sh docs/E2E/2026-04-24-bug-hunt/bugs-raw/

set -euo pipefail

# ---------------------------------------------------------------------------
# 7 mandatory fields (grep patterns — checked with grep -q)
# ---------------------------------------------------------------------------
declare -a REQUIRED_PATTERNS=(
  "^-?\s*\*\*Severity\*\*:"             # - **Severity**: ... (per data-model.md §2)
  "^-?\s*\*\*Layer\*\*:"                # - **Layer**: ...
  "^-?\s*\*\*Discovered\*\*:"           # - **Discovered**: ...
  "^## Steps to Reproduce"              # ## Steps to Reproduce
  "^## Expected"                        # ## Expected
  "^## Actual"                          # ## Actual
  "^## Root-cause hypothesis"           # ## Root-cause hypothesis
)

declare -a REQUIRED_FIELD_NAMES=(
  "Severity"
  "Layer"
  "Discovered"
  "Steps to Reproduce"
  "Expected"
  "Actual"
  "Root-cause hypothesis"
)

# ---------------------------------------------------------------------------
# Resolve search paths
# ---------------------------------------------------------------------------
if [[ $# -gt 0 ]]; then
  SEARCH_DIRS=("$@")
else
  SEARCH_DIRS=("docs/E2E")
fi

# ---------------------------------------------------------------------------
# Main validation loop
# ---------------------------------------------------------------------------
errors=0
files_checked=0

while IFS= read -r -d '' bug_file; do
  files_checked=$((files_checked + 1))
  file_errors=0

  echo "Checking: $bug_file"

  # -- 1. Check 7 mandatory fields -----------------------------------------
  for i in "${!REQUIRED_PATTERNS[@]}"; do
    pattern="${REQUIRED_PATTERNS[$i]}"
    name="${REQUIRED_FIELD_NAMES[$i]}"
    if ! grep -qE "$pattern" "$bug_file"; then
      echo "  ERROR: missing mandatory field '${name}'"
      file_errors=$((file_errors + 1))
    fi
  done

  # -- 2. Steps to Reproduce must have at least 2 steps ---------------------
  step_count=$(grep -cE "^[0-9]+\." "$bug_file" || true)
  if [[ "$step_count" -lt 2 ]]; then
    echo "  ERROR: 'Steps to Reproduce' must contain at least 2 numbered steps (found ${step_count})"
    file_errors=$((file_errors + 1))
  fi

  # -- 3. F/D/P decision required for Blocker severity ----------------------
  if grep -qE "^-?\s*\*\*Severity\*\*:\s*Blocker" "$bug_file"; then
    if ! grep -qE "^-?\s*\*\*F/D/P decision\*\*:" "$bug_file"; then
      echo "  ERROR: Severity is Blocker but '**F/D/P decision**:' field is missing"
      file_errors=$((file_errors + 1))
    fi
  fi

  # -- 4. Root-cause hypothesis must not be a placeholder -------------------
  if grep -qE "^## Root-cause hypothesis" "$bug_file"; then
    # Extract content after the header (skip blank lines, grab first non-empty)
    rch_content=$(awk '/^## Root-cause hypothesis/{found=1;next} found && /^[^#]/ && NF{print;exit}' "$bug_file")
    rch_lower="${rch_content,,}"
    if [[ -z "$rch_content" || "$rch_lower" == "tbd" || "$rch_lower" == "unknown" ]]; then
      echo "  ERROR: Root-cause hypothesis is empty, 'TBD', or 'unknown'"
      file_errors=$((file_errors + 1))
    fi
  fi

  # -- 5. Expected and Actual must not be identical -------------------------
  expected_line=$(grep -A1 "^## Expected" "$bug_file" | tail -n1 | xargs || true)
  actual_line=$(grep -A1 "^## Actual" "$bug_file" | tail -n1 | xargs || true)
  if [[ -n "$expected_line" && "$expected_line" == "$actual_line" ]]; then
    echo "  ERROR: Expected and Actual sections have identical content"
    file_errors=$((file_errors + 1))
  fi

  if [[ "$file_errors" -eq 0 ]]; then
    echo "  OK"
  else
    errors=$((errors + file_errors))
  fi

done < <(find "${SEARCH_DIRS[@]}" -path "*/bugs-raw/BUG-*.md" -print0 2>/dev/null | sort -z)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "validate-bug-records: ${files_checked} file(s) checked, ${errors} error(s) found."

if [[ "$errors" -gt 0 ]]; then
  echo "FAIL — fix the errors above before session close."
  exit 1
fi

if [[ "$files_checked" -eq 0 ]]; then
  echo "NOTE: No bug records found. This is valid if no bugs were filed this session."
fi

echo "PASS"
exit 0
