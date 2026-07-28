# BUG-108: rewrite_query has no stage timing — hides 15-47% of each request's latency

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T19:40:00Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run any RAG chat.
2. Open its trace.
3. Sum `stage_timings`' `*_ms` values vs the total latency — 15-47% is unaccounted for.
4. Log-verified across 3/6 traces: the gap equals `rewrite_query` execution time (`classify_intent`-end → orchestrator-start of iteration 0), which has zero `stage_timings` instrumentation.

## Expected
Every wall-clock phase of a request — including `rewrite_query` — is instrumented, so `sum(stage_ms) ≈ total latency` and a developer can locate where the time actually goes.

## Actual
`rewrite_query` (`nodes.py:250-338`) writes NO `stage_timings` entry; it systemically hides 4.6-6.3s (15-47%) of every `rag_query`, invisible in the trace UI and visible only in raw container logs. In the observed traces the hidden time is often two failed structured-output LLM calls (BUG-056 `OutputParserException`) followed by a degraded fallback `QueryAnalysis`.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-108-trace-08124655-window.log (gitignored)
- Trace: traces/P6-S1-stage-timings-analysis.md (gitignored)

## Root-cause hypothesis
No `stage_timings` write exists between the `rewrite_query` function definition (`backend/agent/nodes.py:250`) and the next node's definition (`nodes.py:339`).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/165
- **Rationale**: A pure instrumentation gap — every stage that is reported is accurate, rewrite_query simply writes no stage_timings entry, so the surface omits rather than misstates.

## Notes
Evidence: 3/6 traces log-verified — 08124655 (99.6% of the gap = `rewrite_query`), c9d5d6c5 (93.7%), effe246c (84.7%); residuals explained by trace-specific noise (BUG-098's retry storm, T0-anchor slop). `research_orchestrator_ms` instrumentation was independently confirmed EXACT (log-sum == stored value), so it is NOT part of this gap.

Additional log artifacts: logs/BUG-108-trace-c9d5d6c5-window.log, logs/BUG-108-trace-effe246c-window.log.

Related: BUG-102 (same stage_timings instrumentation family — bare-number keys dropped from the chart), BUG-055/BUG-056 (the structured-output retry failures that inflate this gap in the observed traces), BUG-098 (retry-storm noise source in one of the 3 log-verified traces).
