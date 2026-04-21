# Contract: Phase Summary Template

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

Every phase MUST produce a summary before advancing to the next phase (NFR-003). Phase summaries are persisted to Engram and serve as the data source for the final report.

## Template

```markdown
# Phase {N} Summary: {Phase Name}

**Status**: PASS / PARTIAL_PASS / FAIL
**Duration**: {start_time} to {end_time}
**Agent(s)**: {assigned agents}

## Success Criteria Results

| SC | Description | Status | Notes |
|----|-------------|--------|-------|
| SC-{NNN} | {description} | PASS/FAIL | {details} |

## Functional Requirements Results

| FR | Description | Status | Notes |
|----|-------------|--------|-------|
| FR-{NNN} | {short description} | PASS/FAIL/PARTIAL | {details} |

## Key Findings

- [Finding 1]
- [Finding 2]
- [Finding N]

## Bugs Found

| Bug ID | Severity | Title |
|--------|----------|-------|
| BUG-{NNN} | P{N}-{LEVEL} | {title} |

(If no bugs: "No bugs found in this phase.")

## Recommendations

- [Recommendation 1]
- [Recommendation N]

(If no recommendations: "No additional recommendations.")

## Log Observations

[Notable log patterns, warnings, or anomalies observed during this phase.
Not bugs per se, but worth documenting for context.]
```

## Status Definitions

| Status | Meaning | Criteria |
|--------|---------|----------|
| PASS | All applicable SCs passed | Every SC in this phase is PASS |
| PARTIAL_PASS | Some SCs passed, some failed | At least one SC PASS and at least one SC FAIL |
| FAIL | Critical SCs failed | The primary SC for this phase is FAIL |

## Validation Rules

1. **Must be persisted before phase transitions to COMPLETED** --- this is enforced by the CEO.
2. **Every applicable SC must have a status** --- no SC can be left as "not evaluated."
3. **Every applicable FR must have a status** --- at minimum PASS/FAIL/PARTIAL.
4. **Key Findings must have at least 1 entry** --- if nothing notable, state "All tests passed without notable findings."
5. **Bug references must use the global bug ID** (e.g., BUG-003), not a local identifier.

## Engram Persistence

Each phase summary is persisted to its own topic key:

| Phase | Topic Key |
|-------|-----------|
| P1 | spec-25/p1-infrastructure |
| P2 | spec-25/p2-core-functionality |
| P3 | spec-25/p3-model-matrix |
| P4 | spec-25/p4-data-quality |
| P5 | spec-25/p5-chaos-engineering |
| P6 | spec-25/p6-security |
| P7 | spec-25/p7-ux-journey |
| P8 | spec-25/p8-regression |
| P9 | spec-25/p9-performance |
| P10 | spec-25/p10-final-report |

The CEO persists via `mem_save` with `topic_key` and `project: "The-Embedinator"`.
