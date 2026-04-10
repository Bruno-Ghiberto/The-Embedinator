# Contract: Final Report Structure

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

The final report is the primary deliverable of Spec-25. It must be a standalone, self-contained document (NFR-007) readable by a developer unfamiliar with this spec. It combines all phase findings into a comprehensive quality assessment.

## Report Structure

```markdown
# The Embedinator --- Master Debug Battle Test Report

**Date**: {date}
**Version**: {app version}
**Hardware**: {GPU model, VRAM, OS}
**Tester**: Human + PaperclipAI CEO orchestration
**Testing Duration**: {total hours across sessions}
**Sessions**: {session count}

---

## 1. Executive Summary

[3-5 paragraphs covering:]
- Overall application quality assessment (one sentence verdict)
- Key strengths found during testing
- Critical issues that need immediate attention (P0/P1 bugs)
- Model recommendation summary (best combo and why)
- Recommended next actions (top 3-5)

### Summary Metrics

| Metric | Value |
|--------|-------|
| Total tests executed | {count} |
| Tests passed | {count} ({percentage}) |
| Tests failed | {count} ({percentage}) |
| Bugs found | {total} (P0: {n}, P1: {n}, P2: {n}, P3: {n}) |
| Model combinations tested | {n}/7 |
| Chaos scenarios recovered | {n}/6 |
| Security probes passed | {n}/7 |
| Regression items passed | {n}/11 |

---

## 2. Infrastructure Verification

[Phase 1 findings: service health, GPU info, model availability, seed data, startup logs]
[Source: spec-25/p1-infrastructure]

---

## 3. Model Scorecard

[Phase 3 findings: ranked scorecard table, per-combo detail, recommendation]
[Include the full scorecard table from contracts/scorecard.md format]
[Include tradeoff analysis and recommended default]
[Source: spec-25/p3-model-matrix]

---

## 4. Core Functionality

[Phase 2 findings: chat E2E, CRUD operations, API endpoints, session continuity, settings]
[Source: spec-25/p2-core-functionality]

---

## 5. Chaos Engineering

[Phase 5 findings: per-scenario results with before/during/after status]
[Include recovery times, circuit breaker behavior, data loss assessment]
[Source: spec-25/p5-chaos-engineering]

---

## 6. Security Assessment

[Phase 6 findings: per-probe results, payloads tested, vulnerabilities found]
[Source: spec-25/p6-security]

---

## 7. Data Quality

[Phase 4 findings: citation accuracy, confidence calibration, embedding consistency,
groundedness verification]
[Include quantitative metrics]
[Source: spec-25/p4-data-quality]

---

## 8. Edge Cases

[From Phase 2: edge case test results (FR-034 through FR-045)]
[Include PASS/FAIL table for all 12 edge case tests]

---

## 9. Performance Baseline

[Phase 9 findings: TTFT measurements, GPU memory profiles, ingestion performance,
API endpoint latency]
[Include timing tables and memory charts]
[Source: spec-25/p9-performance]

---

## 10. UX Journey Audit

[Phase 7 findings: onboarding experience, theme audit, error states, keyboard nav,
responsive design]
[Source: spec-25/p7-ux-journey]

---

## 11. Regression Sweep

[Phase 8 findings: 11-item checklist with PASS/FAIL and notes]
[Source: spec-25/p8-regression]

---

## 12. Bug Registry

### By Severity

#### P0 --- Critical
[Bug reports sorted by severity, then by phase of discovery]

#### P1 --- High
[...]

#### P2 --- Medium
[...]

#### P3 --- Low
[...]

### Bug Summary Table

| Bug ID | Severity | Component | Phase | Title | Spec |
|--------|----------|-----------|-------|-------|------|
| BUG-001 | ... | ... | ... | ... | ... |

[Source: spec-25/bugs]

---

## 13. Recommended Actions

[Prioritized list of recommended next steps based on all findings]
[Grouped by: Critical (do immediately), High (next sprint), Medium (backlog), Low (nice-to-have)]

---

## 14. Appendix

### A. Success Criteria Results

| SC | Description | Status |
|----|-------------|--------|
| SC-001 through SC-012 | ... | PASS/FAIL |

### B. Test Environment Details

[Docker versions, service versions, model versions, GPU driver version, OS]

### C. Scoring Rubric Reference

[Full rubric table with dimension definitions]

### D. Query Archetypes Used

[Exact queries sent for model testing, with archetype labels]

### E. Session Log

[Per-session summary: what was done, when, by whom]
```

## Validation Rules

1. **Standalone**: A developer who has never read this spec should understand the report.
2. **All sections required**: Empty sections must state "Not applicable" or "Phase not completed --- see notes."
3. **Bug registry must be complete**: Every bug referenced in phase summaries must appear in Section 12.
4. **Metrics must be quantitative**: "The app is fast" is not acceptable. "TTFT mean: 342ms (P95: 812ms)" is.
5. **Recommendation must be actionable**: Each recommended action must specify what to fix and where.
6. **Model recommendation must include tradeoff analysis**: Not just "Model X is best" but why, with data.

## Engram Persistence

The final report location and completion status are persisted to `spec-25/p10-final-report`.
The report itself is saved as a file in the project documentation directory (path determined at runtime by CEO).
