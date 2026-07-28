# BUG-106: Trace stage bars render one color — STAGE_COLOR_MAP keys mismatched

- **Severity**: COSMETIC
- **Layer**: Frontend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open the Trace Detail STAGE TIMINGS chart.
2. Observe all stage bars render in the same color (only a failed stage turns red).

## Expected
Stages are visually distinguishable by color (per spec-22 frontend-pro).

## Actual
`STAGE_COLOR_MAP` (`StageTimingsChart.tsx:41-47`) keys (`retrieval`/`rerank`/`compress`/`meta-reasoning`/`inference`) don't match the real stage names except `retrieval`; `getStageColor` (`:51-54`) falls back to `var(--primary)` for every unmatched key → uniform color across the chart; only the binary `failed` flag yields red.

## Artifacts
- Screenshot: screenshots/P6-S1-trace-detail-stage-timings.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Stale/mismatched color-map keys — the map was never updated to match the actual `stage_timings` key set.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-102 (same chart). Separately noted: no budget-threshold coloring exists at all (no spec-14 threshold constant referenced anywhere in the color map) — that gap is out of scope here and will be registered separately under P6-S3 (performance-budget chart scenario).
