# BUG-111: No performance-budget visualization — no in-budget vs breached distinction

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:10:00Z in Phase 6 (P6-S3)
- **Phase scenario**: P6-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Observability → Show Charts + Metrics Trends.
2. Look for any threshold line/marker, or breached-vs-in-budget styling.
3. Observe: none exists anywhere on either surface.

## Expected
Per playbook P6-S3: in-budget vs breached operations are visually distinct; spec-14 §perf-budgets thresholds are the binding line.

## Actual
No budget-breach visualization exists in Query Analytics or Metrics Trends. With avg latency 33s (every query breaches any reasonable budget), the surface gives zero at-a-glance breach signal.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S3-analytics-evidence.md (gitignored)

## Root-cause hypothesis
No recharts `<ReferenceLine>`, no spec-14/spec-26 threshold constant referenced anywhere; `LatencyChart.tsx:83` uses a single flat fill for all buckets; `MetricsTrends.tsx:152-168` line colors distinguish series only, not budget. Same absence pattern as BUG-106 (Trace Detail).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-106 (same missing-threshold-visualization pattern on the Trace Detail chart), BUG-112 (distribution sampling), BUG-113 (bucket range).
