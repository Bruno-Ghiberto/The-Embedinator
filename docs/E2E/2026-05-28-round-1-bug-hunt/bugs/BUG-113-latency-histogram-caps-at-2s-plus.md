# BUG-113: Latency histogram caps at 2s+ — all 33s-class traffic collapses to one bar

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:10:00Z in Phase 6 (P6-S3)
- **Phase scenario**: P6-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Observability → Query Analytics → Latency Distribution.
2. Observe a single bar in "2s+"; the other 4 buckets are empty.
3. Compare against `/api/stats`: avg latency 33143ms; every observed query is in the 12-57s range.

## Expected
Buckets that discriminate this app's actual latency range.

## Actual
Hardcoded buckets top out at "2s+" (`{min:2000,max:Infinity}`); this product's entire operating range (tens of seconds) collapses into one catch-all bar, making the histogram uninformative.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S3-analytics-evidence.md (gitignored)

## Root-cause hypothesis
`LatencyChart.tsx:25-31` hardcodes `LATENCY_BUCKETS` with no config/props and no relation to this product's documented budgets.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-111 (missing budget visualization), BUG-112 (same component, 20-row sampling defect).

Title note: original dispatch title measured 81 chars (over the 80-char schema limit excluding the "BUG-0NN: " prefix); shortened "histogram buckets cap" → "histogram caps" to bring it to 74 chars while preserving the finding verbatim in the body.
