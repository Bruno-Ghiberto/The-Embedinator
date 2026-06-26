# BUG-055: Warm factoid chat latency 32.2s exceeds spec-26 19.5s p50 by 65%

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-06-18T16:52:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start the full stack with GPU-aware backend (docker compose up -d).
2. Send Q-001 ("¿Cuál es el objeto del Reglamento Técnico NAG-200?") in hunt-pdfs after at least one prior warm query (warm-cache condition).
3. Measure total latency in query_traces (started_at → completed_at).
4. Compare against spec-26 warm factoid p50 baseline of 19.5s.

## Expected
Warm factoid query completes within ≤19.5s (spec-26 p50 baseline); regression threshold ≤30s.

## Actual
Trace 2f4d0b4f completed in 32,212ms — 65% over spec-26 p50. Dominant contributor: research-loop 2nd iteration adds ~21s. Answer was correct (High confidence 91%, 4 citations).

## Artifacts
- Screenshot: screenshots/BUG-055-trace-latency.png (gitignored)
- Log excerpt: logs/BUG-055-backend-trace.log (gitignored)
- Trace: traces/BUG-055-2f4d0b4f.trace.zip (gitignored)

## Root-cause hypothesis
Research-loop fires a 2nd iteration that dominates wall-clock time. Causally entangled with BUG-047 (qwen2.5:7b serves inference instead of qwen3:14b — weaker structured output increases BUG-056 parser retries, which may trigger the 2nd loop iteration). Fixing BUG-047 may reduce but not eliminate the latency gap.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Capture: /tmp/spec30-captures/P3-S1-backend-trace.log. Answer was correct — this is a performance regression, not a correctness failure. Flag for spec-31 triage alongside BUG-047 root-cause analysis; fixing the model override may change the latency profile materially.
