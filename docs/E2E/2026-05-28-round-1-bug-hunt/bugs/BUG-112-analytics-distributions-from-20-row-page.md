# BUG-112: Query Analytics distributions computed from the 20-row page, not all queries

> **FIXED 2026-08-05** by spec-31 Batch 1, task 1.5 — commit `4736465`. The filed root-cause
> hypothesis held; the fix required a backend `/api/stats` change. See [Resolution](#resolution).

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:10:00Z in Phase 6 (P6-S3)
- **Fixed**: 2026-08-05 (spec-31 task 1.5, commit `4736465`)
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

## Resolution

**FIXED** — spec-31 Batch 1, task 1.5. Commit `4736465`, 12 files.

The filed root-cause hypothesis was confirmed. Both charts were a client-side re-slice of the
current 20-row `useTraces` page, so "Query Analytics" described one page and called it the system.
The panel read High-dominant (8/8/4) while `avg_confidence` across all 1008 traces was 31.1 — Low.
Paging the table silently changed the "analytics", and nothing labelled the sample as partial.

**Filed as a frontend bug, but the fix is backend-first.** The counts now come from `/api/stats`,
computed in a single SQL aggregate with conditional `SUM`s over every matching row — not by
fetching more rows and re-slicing them client-side, which would only have moved the ceiling.

Design decisions worth recording:

- **Bucket boundaries and their display labels live together in the backend**, so the two cannot
  drift apart. The frontend keeps only the tier → colour map, keyed by tier *name* rather than
  position, so a reordered response cannot paint "Low" green.
- **`/api/stats` gains an optional `session_id`** that narrows the trace aggregates only. Without
  it, honouring the trace table's session filter would have been traded for a second lie — "every
  session" presented as the filtered one. It is part of the SWR cache key in the new `useStats`
  hook, or switching filters would serve the previous session's distribution.
- Collection, document and chunk counts are unaffected by the filter. The new response fields are
  additive; `CollectionStats` reads the same endpoint and is unchanged apart from an explicit
  fetcher arity.

**Evidence**: backend 1548 passed, 0 failed (baseline 1542 + 6 new). Frontend 74 passed.
