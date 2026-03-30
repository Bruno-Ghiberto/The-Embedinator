# Testing Protocol Contract

**Feature**: 023-e2e-testing
**Date**: 2026-03-25

## Gate Report Format

Every phase gate MUST follow this exact format:

```markdown
## Phase {N} Gate: {Phase Name}

| Metric | Value |
|--------|-------|
| Checks completed | {passed + failed + skipped} / {total} |
| Passed | {count} |
| Failed | {count} |
| Skipped | {count} |
| Bugs found | BLOCKER: {n}, HIGH: {n}, MEDIUM: {n}, LOW: {n} |
| Bugs fixed | {count} |
| Bugs deferred | {count} |
| Phase status | PASS | FAIL | PARTIAL |

**Blockers for next phase**: {list or "None"}

-> Proceed to Phase {N+1}? [Awaiting user confirmation]
```

## Log Entry Format

Every check result in logs.md MUST follow this format:

```markdown
#### Step {check-ID}: {description}
- **Type**: AUTOMATED | MANUAL
- **Status**: PASS | FAIL | SKIP | BLOCKED
- **Evidence**: {command output / screenshot path / user observation}
```

When a bug is found, append:

```markdown
- **Bug Found**:
  - ID: BUG-{NNN}
  - Severity: BLOCKER | HIGH | MEDIUM | LOW
  - Description: {what happened}
  - Root Cause: {if determined}
  - Fix Applied: {what was changed, or "DEFERRED"}
  - Files Modified: {paths}
  - Verified: YES | NO | DEFERRED
```

## Severity Classification Rules

| Severity | Criteria | Examples | Action |
|----------|----------|----------|--------|
| BLOCKER | Cannot continue E2E at all | Services down, DB corrupted, build failure | Fix immediately, user must confirm |
| HIGH | Affects downstream phases | Broken API endpoint, missing feature, data loss | Fix immediately, user must confirm |
| MEDIUM | Degrades experience but does not block | Slow response, missing UI element, cosmetic error | Fix or defer, user decides |
| LOW | Cosmetic or minor | Wrong color, alignment issue, benign warning | Document and continue |

## Impasse Resolution Protocol

```
CHECK FAILS
    |
    +-- Is it a KNOWN-NNN issue?
    |   +-- YES -> Log with known ID, continue (don't fix)
    |   +-- NO -> Classify severity
    |           |
    |           +-- BLOCKER/HIGH -> HALT -> FIX -> VERIFY -> RESUME
    |           +-- MEDIUM/LOW -> LOG -> Ask user: fix now or defer?
    |                               |
    |                               +-- Fix now -> FIX -> VERIFY -> RESUME
    |                               +-- Defer -> LOG as DEFERRED -> RESUME
```

## Acceptance Report Format

```markdown
# Acceptance Report -- Spec 23

**Date**: {datetime}
**Duration**: {total hours}
**Branch**: 023-e2e-testing

## Phase Results

| Phase | Name | Status | Checks | Bugs |
|-------|------|--------|--------|------|
| 0 | Pre-flight | {status} | {pass}/{total} | {count} |
| 1 | TUI Install | {status} | {pass}/{total} | {count} |
| ... | ... | ... | ... | ... |
| 10 | Acceptance | {status} | {pass}/{total} | {count} |

## Bug Summary

| Severity | Found | Fixed | Deferred |
|----------|-------|-------|----------|
| BLOCKER | {n} | {n} | {n} |
| HIGH | {n} | {n} | {n} |
| MEDIUM | {n} | {n} | {n} |
| LOW | {n} | {n} | {n} |
| **Total** | **{n}** | **{n}** | **{n}** |

## Known Issues Encountered

| ID | Issue | Phase | Observed Behavior |
|----|-------|-------|-------------------|
| KNOWN-001 | ... | ... | ... |

## Recommendation

**{ACCEPT | CONDITIONAL ACCEPT | REJECT}**

Rationale: {explanation}

### Conditions (if CONDITIONAL ACCEPT)
- {condition 1}
- {condition 2}
```

## Phase Advancement Rules

1. Orchestrator MUST present gate report after every phase
2. Orchestrator MUST NOT advance without explicit user confirmation
3. If a phase has BLOCKER bugs unresolved -> Gate FAIL -> Cannot advance
4. If a phase has only MEDIUM/LOW deferred -> Gate PARTIAL -> Can advance with user approval
5. User can say "skip" for any phase -> Gate SKIP -> Must document reason
