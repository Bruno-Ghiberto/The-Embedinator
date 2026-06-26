# BUG-050: throwApiError misses FastAPI detail envelope; error messages lost

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T14:02:00Z in Phase 2 (P2-S5)
- **Phase scenario**: P2-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Re-upload an identical file to a collection → backend responds 409 with {"detail":{"error":{"code":"DUPLICATE_DOCUMENT","message":"A document with identical content already exists in this collection","details":{"existing_document_id":"<uuid>"}},"trace_id":"<id>"}}.
2. Observe the upload widget renders only "Conflict".

## Expected
UI renders the backend's human-readable message and can use code/details/trace_id (e.g., link to the existing document).

## Actual
throwApiError (frontend/lib/api.ts:33-43) reads body.error?.code, body.error?.message, body.trace_id — but FastAPI HTTPException nests everything under body.detail → all three resolve undefined → message falls back to res.statusText ("Conflict"), code to "UNKNOWN", trace_id lost. DocumentUploader.tsx:82-88 renders err.message verbatim. SYSTEMIC: every endpoint raising HTTPException loses its structured message at this one parser.

## Artifacts
- Screenshot: screenshots/BUG-050-conflict-bare.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
One-level path mismatch (body.error vs body.detail.error); fix = unwrap the FastAPI detail envelope in throwApiError.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Explains BUG-048's trace_id drop on REST paths (same wrong path body.trace_id vs body.detail.trace_id) — cross-ref BUG-048, BUG-049 (error-fidelity family: frontend over-shares raw stderr in S3, under-shares structured messages in S5). Backend 409 verified exemplary (trace d3db5522, ingestion_duplicate_detected, 24ms).

P2-S6 cross-evidence: the UI rendered "Internal Server Error" for an event whose backend-logged status was 400 (trace a9128936, duration 30028 ms — proxy timeout, BUG-054). The backend emitted no detail envelope (zero structlog error events — the handler never entered error handling), so the proxy 400 arrives at throwApiError as an unstructured response body; throwApiError's fallback resolves statusText only, but the UI displayed "Internal Server Error" — confirming that the degraded display path fires across multiple error shapes, not only the 409 case. Second independent scenario confirming SYSTEMIC scope.
