# BUG-055: All warm queries breach spec-26 latency p50 (2nd research-loop iteration)

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
P3-S3 broadened to ALL warm queries (analyst-correlated, HIGH confidence): Analytical trace 618fb649 (2026-06-18T16:46:43 local) = 31.6s, +97.3% over spec-26 analytical p50 16.0s; orchestrator_calls=2; stage breakdown: intent 2.18s / research_orchestrator 17.48s (55.4%) / retrieval 592.8ms (1 call) / answer_generation 3.81s / ranking 0.0ms / unaccounted 7.51s. Factoid Q-001 = 32.2s (trace 2f4d0b4f), +65.1% over p50 19.5s; orchestrator_calls=2. Systemic root consistent in both: the 2nd research-loop iteration ALWAYS fires (agent_loop_exit_tool_exhaustion, routing=sufficient) but does NOT retrieve again — it doubles LLM cost regardless of query type. Cross-ref BUG-056 (rewrite_query OutputParserException fallback +4.3s, present in both). llm_model=qwen2.5:7b.
P3-S4 (2026-07-03) clean-probe data points, both warm factoid queries: T1 = 32,892ms (~32.9s, trace f3348415); T2 = 34,950ms (~35.0s, trace 30307482). Both breach spec-26 warm factoid p50 (19.5s) by a similar margin to the original P3-S1 finding, consistent with the systemic 2nd-research-loop root cause (no new mechanism identified).
P3-S5 (2026-07-03) COUNTER-data-point + accuracy nuance: latency 18,563ms (~18.6s) — this MET the spec-26 factoid p50 (19.5s), and it was a COLD first query on a brand-new collection (nag-corpus-spec28), yet FASTER than the same day's WARM hunt-pdfs queries (32.9s/35.0s). Trace 80c47266. This indicates the latency breach is INTERMITTENT and tracks whether the redundant 2nd research-loop iteration fires — NOT a simple warm/cold-cache effect, and NOT universal to every factoid query. FLAG FOR VERIFY GATE: the current title's "All warm queries" framing may need softening at phase close if further warm queries meet budget; do NOT retitle now per Lead direction — this is a flag for the closure/verify step, not an immediate change.

**UPDATE 2026-07-03** (Q-014 exit-checklist incident, no severity change): the wasteful 2nd/3rd research-loop iteration's latency is what pushes analytical/multi-source queries into a long single-node silent dwell that trips the ~30s idle timeout (BUG-054) → direct contributor to the BUG-073/074 hang chain. Q-014 data: iterations=2 → 50.2s total, HUNG (cancelled mid-stream); iterations=3 → 44.8s total, COMPLETED (no single silent gap crossed 30s). Cross-ref BUG-073/074/075.
