# BUG-073: Streaming handler swallows CancelledError → cancelled requests die invisibly

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Phase scenario**: Q-014 (P3 exit-checklist, analytical multi-source)
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run a chat query where a SINGLE node dwell goes silent (no NDJSON bytes emitted) for more than ~30s — Q-014 (analytical multi-source, `nag-corpus-spec28`) first run = 50.2s total with a 34.79s silent gap during the research orchestrator's 2nd iteration.
2. The ~30s idle proxy timeout (BUG-054) cancels the connection during that silent gap.
3. Observe: the request task unwinds with ZERO logging, NO `query_traces` row written, NO error event, NO done event — the failure is completely invisible (py-spy shows an idle event loop; `/proc/net/tcp` shows the connection already `TIME_WAIT`).
4. Confirm via a control retest (trace `552e3cf6`) that a healthy run's post-research chain (research_loop_end → aggregate → verify → format) takes ~9ms — proving the original multi-minute silence was a cancellation, not slow compute.

## Expected
A cancelled/disconnected request is caught and logged (and ideally a partial trace is written) so the failure is observable rather than silent.

## Actual
The cancellation unwinds through the streaming handler with no logging path at all — no trace row, no log line, no client-visible signal.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-073-research-hang-dump.txt (gitignored) — py-spy idle-event-loop dump captured during the hang; logs/P3-Q014-retest-control.log (gitignored) — control retest (trace 552e3cf6) proving the healthy post-research chain is ~9ms.
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed — `backend/api/chat.py` (~316-380) catches `GraphRecursionError`, `RuntimeError`, `CircuitOpenError`, and a bare `except Exception` — but there is NO `except asyncio.CancelledError` and NO `except BaseException`. Since Python 3.8, `asyncio.CancelledError` inherits from `BaseException` (NOT `Exception`), so it unwinds past all four `except` clauses with no logging and no trace write. The control retest (trace `552e3cf6`) independently confirms the mechanism: when nothing cancels the task, the post-research chain completes in ~9ms, ruling out slow compute as the explanation for the original 34.79s silent gap.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Traces: hung = `cda553a5-c0af-4b23-a1ac-770000c9a98f` (session `f28869df`); control = `552e3cf6`.

Cross-refs: BUG-074 (frontend counterpart — the client never detects this silent server-side death); BUG-054 (the idle-timeout trigger that initiates the cancellation); BUG-055 (the 2nd research-loop iteration's latency is what creates the long silent gap in the first place); BUG-075 (the missing keepalive that would otherwise prevent the gap from ever reaching the idle-timeout threshold).

Fix surface: add `except asyncio.CancelledError` (log + re-raise, since re-raising is required for correct asyncio cancellation propagation) and ideally `except BaseException` as a final catch-all that persists a partial trace before re-raising, so cancelled requests are never silent again.
