# BUG-057: ranking stage timing reports 0.0ms despite reranker executing

- **Severity**: MINOR
- **Layer**: Observability
- **Discovered**: 2026-06-18T16:52:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send any chat query that triggers the reranker (factoid query with ≥1 result chunk).
2. Inspect query_traces.stage_timings_json for the ranking stage duration.
3. Observe: ranking duration_ms = 0.0 despite the reranker (CrossEncoder) executing and returning results.

## Expected
stage_timings_json records the actual elapsed time for the ranking stage (non-zero duration_ms).

## Actual
ranking stage duration_ms = 0.0ms in trace 2f4d0b4f; reranker ran and produced valid reranked results, but timing was not instrumented or was clobbered.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-057-stage-timings.log (gitignored)
- Trace: traces/BUG-057-2f4d0b4f.trace.zip (gitignored)

## Root-cause hypothesis
Stage timing instrumentation for the ranking node is missing or records a zero-duration window (e.g., timer started after reranker completes, or timing context not propagated into the reranker wrapper).

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Capture: /tmp/spec30-captures/P3-S1-backend-trace.log. Log-analyst finding. Pure observability gap — ranking is functionally correct. Makes latency profiling unreliable for the ranking stage.
