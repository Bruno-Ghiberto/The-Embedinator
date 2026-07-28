# BUG-104: Trace embedding & retrieval timings are false aliases of one timer

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Compare `embedding` vs `retrieval` durations across traces — byte-identical in single-iteration traces.
2. Multi-iteration trace `e6d35cd6`: `embedding` = `retrieval` = 0.6ms while `research_tools_ms` = 1411.1ms.

## Expected
`embedding` and `retrieval` report independent per-stage durations.

## Actual
Both are written from the same `tools_node` wall-clock; no separate timers exist. On multi-iteration traces both show only the last iteration's value while `research_tools_ms` accumulates across all iterations.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P6-S1-stage-timings-analysis.md (gitignored)

## Root-cause hypothesis
`research_nodes.py:309/317-318` and `:432/441-442` write `embedding` and `retrieval` from the same `_duration_ms` variable; no dedicated per-stage timers exist for either.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-102 (same trace-instrumentation family — stage_timings keys not matching what the panel/chart needs).
