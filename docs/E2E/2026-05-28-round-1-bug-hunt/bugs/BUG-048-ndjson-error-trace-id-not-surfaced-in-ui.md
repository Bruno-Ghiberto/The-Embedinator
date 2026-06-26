# BUG-048: NDJSON error trace_id never surfaced in UI

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T12:55:00Z in Phase 2 (P2-S2)
- **Phase scenario**: P2-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Trigger any chat error (BUG-045 active suffices).
2. Inspect the NDJSON response: error event carries "code" and "trace_id" fields.
3. Inspect the rendered DOM: only the message text + Retry button; trace_id appears nowhere; console logs nothing.
4. (P3-S1 — happy path) Send Q-001 in hunt-pdfs; intercept NDJSON stream; inspect the `done` event — trace_id field present (e.g. 2f4d0b4f) but zero DOM elements surface it in the success UI path.

## Expected
Error UI exposes the trace_id (e.g., small copyable reference) so users/operators can correlate failures with backend logs and query traces.

## Actual
The stream handler renders error.message verbatim and discards code + trace_id; the only correlation key is lost at the UI boundary. Confirmed also on the happy path: the `done` event carries trace_id (2f4d0b4f in P3-S1) but no DOM element surfaces it in the success UI path either.

## Artifacts
- Screenshot: screenshots/BUG-045-chat-error.png (gitignored)
- Log excerpt: logs/BUG-048-ndjson-error-sample.txt (gitignored)
- Trace: null
- Trace: null

## Root-cause hypothesis
useStreamChat error handling maps only the message field into UI state.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Would have cut this hunt's correlation time materially; cheap high-value fix candidate for spec-31. Cross-evidence from P2-S4b: the ingest API's 413 response carries trace_id in BOTH the JSON body and the x-trace-id response header (97095d98-51bf-41ce-a61c-38c0322552c8) — the backend consistently delivers trace_ids; the chat UI is the only surface dropping them.

P3-S1 update (2026-06-18): confirmed scope is broader than error path only — trace_id is also present in the `done` event on successful requests (2f4d0b4f, captured in /tmp/spec30-captures/p3-s1-ndjson-stream.json) and is never surfaced. 182 NDJSON events streamed (session/status×6/chunk×80/citation/confidence/done); trace_id field present in done event, no DOM element renders it.
