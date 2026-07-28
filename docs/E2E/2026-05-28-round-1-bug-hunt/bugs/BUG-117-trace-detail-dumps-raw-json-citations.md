# BUG-117: Trace Detail dumps citations/reasoning/strategy as raw JSON — unreadable

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T20:20:00Z in Phase 6 (P6-S4)
- **Phase scenario**: P6-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open any Trace Detail.
2. Observe CITATIONS renders each citation as a raw `JSON.stringify` blob (`{"passage_id":...,"relevance_score":...,"source_removed":...}`); Reasoning Steps + Strategy Switches likewise when present.
3. Confirmed live on trace `7e79a12b` (20 citations, all raw JSON).

## Expected
Per playbook P6-S4: a non-technical reader can understand the operation detail.

## Actual
Citations/reasoning-steps/strategy-switches are raw JSON dumps — unreadable to a non-technical reader.

## Artifacts
- Screenshot: screenshots/P6-S4-trace-detail-raw-json-citations.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
`TraceDetailSheet` in `frontend/components/TraceTable.tsx` renders Reasoning Steps (`178-191`), Strategy Switches (`194-207`), and Citations (`210-223`) via `<code>{JSON.stringify(x)}</code>`.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Additional supporting artifact: screenshots/P6-S1-trace-detail-stage-timings.png (same panel, prior scenario). Related: BUG-116 (same P6-S4 readability mandate, different surface), BUG-105 (same Trace Detail panel — no drill-down affordance), BUG-066 (citation-count accumulation, same panel's citation display).
