# BUG-102: Stage-timings chart drops bare-number stages, hiding the 18s bottleneck

> **FIXED 2026-08-05** by spec-31 Batch 1, task 1.4 — commit `f534a60`. The filed root-cause
> hypothesis held exactly as written, line references included. See [Resolution](#resolution).

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Fixed**: 2026-08-05 (spec-31 task 1.4, commit `f534a60`)
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

## Resolution

**FIXED** — spec-31 Batch 1, task 1.4. Commit `f534a60`, 3 files, +142/-9.

The filed root-cause hypothesis was confirmed as written. `stage_timings` carries two shapes side
by side: graph nodes write `{duration_ms, failed?}` records, while the research accumulators are
written straight in as bare numbers (`research_nodes.py:139-140, 200-201, 232-233, 320-321`).
`buildChartData` read `.duration_ms` off every value, so every bare number resolved to `undefined`
— four keys became phantom empty rows and their stored values were never plotted.

The transform now accepts both shapes. Three judgment calls are worth recording:

- **Unreadable entries are dropped, not charted at zero.** An empty bar asserts "this stage took
  no time", which is a stronger and falser claim than not charting it at all.
- **The `*_calls` keys are excluded outright.** They count invocations, not milliseconds, so
  plotting them at face value on a duration axis would have swapped one misreport for another.
  Excluding them also removes the phantom rows they produced.
- **Stage labels are left as the raw backend keys.** Trimming the `_ms` suffix would read better
  on the axis, but it is a cosmetic change to a chart whose defect was numeric, and it risks
  colliding with a same-named object-shaped entry.

The `stage_timings` contract in `frontend/lib/types.ts` was widened to match what the backend has
always sent — the frontend type, not the backend payload, was the thing that was wrong.

**Evidence**: adds `frontend/tests/unit/stage-timings-chart.test.ts`, the first coverage for this
component — 9 tests. `buildChartData` is exported so the transform can be tested directly; the
defect is entirely in it, and rendering recharts under jsdom gives near-zero signal because
`ResponsiveContainer` collapses to 0×0. The export landed as a separate no-behaviour-change step
so the RED run failed on the bug's own assertions rather than on a missing symbol: 5 failed, 4
passed. Frontend suite 68 passed (59 + 9), `tsc` clean.
