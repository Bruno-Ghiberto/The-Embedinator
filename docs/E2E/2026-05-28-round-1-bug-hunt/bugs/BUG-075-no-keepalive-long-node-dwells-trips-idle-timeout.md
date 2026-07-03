# BUG-075: No keepalive during long node dwells → silent stream trips the idle timeout

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Phase scenario**: Q-014 (P3 exit-checklist, analytical multi-source)
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run a query where one graph node dwells on a long operation — Q-014's research-orchestrator 2nd iteration made a 34.79s Ollama call.
2. Observe: the backend emits `status` NDJSON events ONLY on node transitions (8 total for this run, one per node move) — there is no periodic heartbeat while execution stays inside a single node.
3. During the 34.79s dwell, the byte stream is completely silent.
4. Confirm the consequence: the silent gap exceeds the ~30s idle timeout, so the connection is cancelled (feeding directly into BUG-073/BUG-074).

## Expected
A periodic keepalive/ping is emitted during long node dwells so the connection stays alive regardless of how long a single node takes.

## Actual
`status` events fire only on node transitions; a single long-running node produces zero bytes for its entire duration, which is indistinguishable from a dead connection to any idle-timeout mechanism upstream.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-074-075-hang-frontend-code-trace.log (gitignored) — frontend-inspector's code trace, covers both BUG-074 and BUG-075.
- Trace: null

## Root-cause hypothesis
MEDIUM-HIGH confidence — frontend-inspector confirmed exactly 8 status events for the Q-014 run, corresponding to node transitions only, with no periodic heartbeat mechanism during a long single-node operation. This is DISTINCT from BUG-065 (that bug is the FRONTEND's `onStatus` no-op — the callback chain is severed client-side); BUG-075 is that the BACKEND emits zero bytes during a long dwell in the first place, independent of whether the frontend would even consume a heartbeat if one were sent.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Cross-refs: this is the highest-fix-leverage bug in the Q-014 incident chain — a periodic keepalive during long node dwells would prevent BUG-073 and BUG-074 from ever triggering, since the idle timeout (BUG-054) would never see a silent gap long enough to fire. Also cross-ref BUG-055 (the 2nd-loop iteration whose latency is what creates dwells long enough to matter) and BUG-065 (distinct: frontend callback severed vs backend emitting nothing).
