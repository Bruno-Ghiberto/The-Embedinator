# Data Model: Comprehensive E2E Testing

**Feature**: 023-e2e-testing
**Date**: 2026-03-25

## Entities

This spec does not introduce new persistent data structures. The entities below describe the testing workflow model used in the execution log (logs.md) and guide (e2e-guide.md).

### Test Phase

| Field | Type | Description |
|-------|------|-------------|
| number | Integer (0-10) | Sequential phase number |
| name | String | Phase name (e.g., "Environment Pre-flight") |
| type | Enum | AUTOMATED, MANUAL, HYBRID |
| fr_coverage | String[] | List of FR IDs covered (e.g., ["FR-001", "FR-002"]) |
| sc_coverage | String[] | List of SC IDs covered |
| estimated_time | Integer (minutes) | Expected duration |
| gate_status | Enum | PASS, FAIL, PARTIAL, PENDING |

### Check

| Field | Type | Description |
|-------|------|-------------|
| id | String | Unique check ID (e.g., "P0-C01") |
| phase | Integer | Parent phase number |
| description | String | What is being verified |
| type | Enum | AUTOMATED, MANUAL |
| status | Enum | PASS, FAIL, SKIP, BLOCKED |
| evidence | String | Command output, screenshot path, or observation |
| bug_id | String (nullable) | Reference to Bug if failure found |

### Bug

| Field | Type | Description |
|-------|------|-------------|
| id | String | Sequential bug ID (e.g., "BUG-001") |
| severity | Enum | BLOCKER, HIGH, MEDIUM, LOW |
| check_id | String | Check where discovered |
| phase | Integer | Phase where discovered |
| description | String | What went wrong |
| root_cause | String (nullable) | Analysis of why |
| fix_applied | String | Description of fix, or "DEFERRED" |
| files_modified | String[] | Paths of modified files |
| verified | Enum | YES, NO, DEFERRED |
| is_known | Boolean | Whether this matches a KNOWN-NNN issue |
| known_id | String (nullable) | Reference to KNOWN-NNN if applicable |

### Gate

| Field | Type | Description |
|-------|------|-------------|
| phase | Integer | Phase number |
| checks_total | Integer | Total checks in phase |
| checks_passed | Integer | Checks that passed |
| checks_failed | Integer | Checks that failed |
| checks_skipped | Integer | Checks that were skipped |
| bugs_blocker | Integer | BLOCKER bugs found |
| bugs_high | Integer | HIGH bugs found |
| bugs_medium | Integer | MEDIUM bugs found |
| bugs_low | Integer | LOW bugs found |
| status | Enum | PASS, FAIL, PARTIAL |
| user_confirmed | Boolean | User explicitly approved advancing |

### Acceptance Report

| Field | Type | Description |
|-------|------|-------------|
| total_phases | Integer | Always 11 (0-10) |
| phases_passed | Integer | Phases with PASS status |
| phases_partial | Integer | Phases with PARTIAL status |
| phases_failed | Integer | Phases with FAIL status |
| total_bugs | Integer | Total bugs discovered |
| bugs_fixed | Integer | Bugs resolved during testing |
| bugs_deferred | Integer | Bugs documented but not fixed |
| known_issues_hit | Integer | How many KNOWN-NNN issues were encountered |
| recommendation | Enum | ACCEPT, CONDITIONAL_ACCEPT, REJECT |
| total_duration | Integer (minutes) | Total E2E testing time |

## Relationships

```
Test Phase 1──* Check
Check *──0..1 Bug
Test Phase 1──1 Gate
Gate *──1 Acceptance Report (aggregation)
Bug *──0..1 Known Issue (KNOWN-NNN reference)
```

## State Transitions

### Check Lifecycle

```
PENDING -> PASS (automated check succeeds or user confirms)
PENDING -> FAIL (automated check fails or user reports issue)
PENDING -> SKIP (check cannot be executed, documented reason)
PENDING -> BLOCKED (depends on failed prerequisite)
FAIL -> PASS (after impasse fix + re-verify)
```

### Bug Lifecycle

```
DISCOVERED -> TRIAGED (severity classified)
TRIAGED -> FIXING (for BLOCKER/HIGH)
TRIAGED -> DEFERRED (for MEDIUM/LOW with user approval)
FIXING -> FIXED (fix applied + verified)
FIXING -> ESCALATED (fix failed, user consulted)
```

### Phase Gate Lifecycle

```
PENDING -> PASS (all checks pass, or failures are acceptable LOW/MEDIUM)
PENDING -> PARTIAL (some checks pass, non-blocking failures documented)
PENDING -> FAIL (BLOCKER/HIGH bugs unresolved)
FAIL -> PASS (after impasse resolution)
```
