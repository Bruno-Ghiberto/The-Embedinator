# BUG-056: OutputParserException x2 on rewrite_query node adds ~4.3s via fallback

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-18T16:52:00Z in Phase 3 (P3-S1)
- **Phase scenario**: P3-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send any factoid query via chat (Q-001 confirmed).
2. Inspect backend logs for rewrite_query node execution.
3. Observe: two OutputParserException events, both recovered via fallback path (+4.3s total overhead).
4. Check query_traces for the total latency impact.

## Expected
rewrite_query node produces valid structured output on first attempt; no fallback overhead.

## Actual
OutputParserException fires twice during P3-S1 trace 2f4d0b4f; fallback recovery adds ~4.3s to total latency (contributing to BUG-055).

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-056-parser-exception.log (gitignored)
- Trace: traces/BUG-056-2f4d0b4f.trace.zip (gitignored)

## Root-cause hypothesis
Structured output parsing fails on qwen2.5:7b responses (weaker instruction-following than qwen3:14b). Likely resolves if BUG-047 is fixed and qwen3:14b serves inference.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Capture: /tmp/spec30-captures/P3-S1-backend-trace.log. May resolve as a side-effect of fixing BUG-047 (model upgrade to qwen3:14b). Log-analyst finding (trace 2f4d0b4f). Linked to BUG-055 (latency) and BUG-047 (model override).
