# BUG-105: Trace Detail has no per-stage input/output drill-down (bars inert)

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Trace Detail.
2. Click any stage bar in the STAGE TIMINGS chart.
3. Observe nothing happens.

## Expected
Per playbook P6-S1: clicking into a stage reveals its inputs/outputs.

## Actual
Stage bars have no click handler; there is no stage-scoped detail view. The panel shows flat, non-stage-scoped sections (sub-questions, reasoning steps, strategy switches, citations) plus a hover tooltip that shows duration only.

## Artifacts
- Screenshot: screenshots/P6-S1-trace-detail-stage-timings.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
`StageTimingsChart.tsx:126-133` `<Bar>`/`<Cell>` elements have no `onClick`; `TraceDetailSheet` (`frontend/components/TraceTable.tsx:53-237`) renders all sections unconditionally, none gated behind a stage selection.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Additional supporting artifact: screenshots/P6-S1-stage-hover-tooltip.png (shows the hover-only affordance). Related: BUG-102 (same panel).
