# BUG-102: Stage-timings chart drops bare-number stages, hiding the 18s bottleneck

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run any RAG chat.
2. Observability → click trace → Trace Detail.
3. Read the STAGE TIMINGS chart.

## Expected
Each stage's real duration is shown; the largest contributor is visually dominant.

## Actual
`research_orchestrator_ms` (18108.8ms = 69% of the 26113ms total) renders as an empty bar; `intent_classification` (1900ms) appears largest instead. 4 bare-number keys (`research_orchestrator_ms`/`_calls`, `research_tools_ms`/`_calls`) become phantom empty rows; their stored values are never plotted.

## Artifacts
- Screenshot: screenshots/P6-S1-trace-detail-stage-timings.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S1-stage-timings-analysis.md (gitignored)

## Root-cause hypothesis
Backend writes `research_orchestrator_ms`/`_calls` and `research_tools_ms`/`_calls` as bare numeric values in `stage_timings` (`research_nodes.py:139-140,200-201,232-233,320-321,444-445,462-463`), siblings to `{duration_ms}` entries. Frontend contract `frontend/lib/types.ts:140` expects `Record<string,{duration_ms:number;failed?:boolean}>`; `buildChartData()` (`frontend/components/StageTimingsChart.tsx:29-37`) reads `timing.duration_ms` on every value → `undefined` for bare numbers → empty bars + dropped values.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/162
- **Rationale**: This observability surface does not merely omit — it misreports: the 18.1s orchestrator (69% of total) renders as an empty bar and the 1.9s intent_classification is shown as the dominant stage, so the chart names the wrong bottleneck.

## Notes
Additional supporting artifact: screenshots/P6-S1-stage-hover-tooltip.png. Related: BUG-103 (ranking stage always 0ms — same chart, adjacent mechanism), BUG-104 (embedding/retrieval alias — same instrumentation gap family).
