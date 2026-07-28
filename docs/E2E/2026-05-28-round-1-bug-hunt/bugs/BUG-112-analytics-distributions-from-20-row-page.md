# BUG-112: Query Analytics distributions computed from the 20-row page, not all queries

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:10:00Z in Phase 6 (P6-S3)
- **Phase scenario**: P6-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Observability → Query Analytics.
2. Compare the Latency + Confidence Distribution charts against `/api/stats`.
3. Charts reflect only the 20 fetched traces (limit=20, offset=0), not the 1008 total; Confidence chart is High-dominant (8/8/4) while `/api/stats` `avg_confidence` over all 1008 = 31.1 (Low).

## Expected
"Query Analytics" distributions represent the full query population, or clearly label the sample as partial.

## Actual
Both charts are a client-side re-slice of the current 20-row trace page; changing page/offset changes the "analytics"; no disclaimer exists. The picture actively misleads — it looks high-confidence when the system is low-confidence overall.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S3-analytics-evidence.md (gitignored)

## Root-cause hypothesis
`ObservabilityClient.tsx:33` `PAGE_LIMIT=20`; `:41-51` a single `useTraces({limit:20})` fetch feeds both the table and the charts; `:99`/`:118` pass that 20-row array as the `traces` prop; `LatencyChart.tsx:33-40` `buildLatencyData()` and `ConfidenceDistribution.tsx:33-56` `buildConfidenceData()` filter the prop only — zero `/api/stats` usage anywhere in either chart.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/167
- **Rationale**: Both charts re-slice the current 20-row page with no disclaimer, so "Query Analytics" reads High-dominant while /api/stats avg_confidence over all 1008 traces is 31.1 (Low) — the panel actively asserts the opposite of the truth.

## Notes
Related: BUG-111 (missing budget visualization on the same panel), BUG-113 (bucket range, same LatencyChart component).
