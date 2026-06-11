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

## Expected
Error UI exposes the trace_id (e.g., small copyable reference) so users/operators can correlate failures with backend logs and query traces.

## Actual
The stream handler renders error.message verbatim and discards code + trace_id; the only correlation key is lost at the UI boundary.

## Artifacts
- Screenshot: screenshots/BUG-045-chat-error.png (gitignored)
- Log excerpt: logs/BUG-048-ndjson-error-sample.txt (gitignored)
- Trace: null

## Root-cause hypothesis
useStreamChat error handling maps only the message field into UI state.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Would have cut this hunt's correlation time materially; cheap high-value fix candidate for spec-31. Cross-evidence from P2-S4b: the ingest API's 413 response carries trace_id in BOTH the JSON body and the x-trace-id response header (97095d98-51bf-41ce-a61c-38c0322552c8) — the backend consistently delivers trace_ids; the chat UI is the only surface dropping them.
