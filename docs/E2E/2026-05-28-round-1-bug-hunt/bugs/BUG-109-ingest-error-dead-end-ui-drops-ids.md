# BUG-109: Ingest error dead-ends — UI drops job/doc id, timestamp, trace-id from API

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-11T19:40:00Z in Phase 6 (P6-S2)
- **Phase scenario**: P6-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Upload a malformed PDF to a collection (used `audit-timing-test`).
2. The ingest job fails.
3. UI shows "Failed" + the raw `error_message` + a "Try again" button.
4. No click on the error surface navigates to any detail view.
5. Network `GET .../ingest/{job_id}` returns `job_id`, `document_id`, `started_at`, `status`, `error_message` plus an `x-trace-id` response header — the UI surfaces only `status` + `error_message`.

## Expected
Per playbook P6-S2: one click from the error message to its detail; error code + timestamp + originating operation all present.

## Actual
No navigation affordance exists from the error message. The structured fields the API already returns (`job_id`, `document_id`, `started_at` timestamp, `x-trace-id` header) are all dropped by the UI; only the raw error string plus a "Try again" button (which re-fails on the same malformed file) are shown.

## Artifacts
- Screenshot: screenshots/P6-S2-ingest-error.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S2-ingest-error-jobstatus.json (gitignored)

## Root-cause hypothesis
The frontend upload/error UI renders only `status` + `error_message`; it does not render `job_id`/`document_id`/`started_at`/`x-trace-id`, and provides no error-detail navigation of any kind.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.1-defer
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/166
- **Rationale**: The error string shown is the real one; the UI merely omits job_id/document_id/started_at/x-trace-id and offers no detail navigation — missing affordances rather than a false report.

## Notes
Related: BUG-051 (the same error surface's unconditional "Try again" retry affordance), BUG-110 (the same job's `completed_at` never set on the failure path), BUG-048 (same family — a backend-provided `trace_id`/correlation key that the frontend drops at the UI boundary, now confirmed on a second surface).
