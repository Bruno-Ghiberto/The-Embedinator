# BUG-114: Metrics Trends: zero-query buckets render as flat-0 line, no empty state

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:10:00Z in Phase 6 (P6-S3)
- **Phase scenario**: P6-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Observability → Metrics Trends.
2. Select a window with no queries (Last 24h — newest query is ~28h old, outside window).
3. Observe: a flat line at 0 renders with an auto-scaled "0-4 ms" axis, reading as "latency ≈ 0ms" instead of "no data."

## Expected
An explicit "no data in window" state when buckets have `query_count 0`.

## Actual
The empty-state check only fires when the buckets ARRAY itself is empty; buckets that exist but have `query_count=0` fall through and plot flat at 0, indistinguishable from a real 0ms measurement.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S3-analytics-evidence.md (gitignored)

## Root-cause hypothesis
`MetricsTrends.tsx:118-123` checks `chartData.length===0` only; `:69-75` maps buckets but never reads `b.query_count` (present on the `MetricsBucket` type, `useMetrics.ts:9-11`) — zero-query buckets are indistinguishable from real 0 values.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-112 (same panel, sampling/representativeness family).
