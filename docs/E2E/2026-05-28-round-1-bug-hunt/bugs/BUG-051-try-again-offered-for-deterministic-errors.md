# BUG-051: "Try again" offered unconditionally for all upload errors, including deterministic 409 duplicates

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T14:02:00Z in Phase 2 (P2-S5)
- **Phase scenario**: P2-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Trigger a duplicate-upload 409.
2. Observe "Try again" under the error.
3. Click it — file re-queues (DocumentUploader.tsx:100-106), same ingestFile() → same 409 → identical "Conflict" loop forever.

## Expected
Retry only for transient error classes; deterministic errors (DUPLICATE_DOCUMENT, FILE_TOO_LARGE) get no retry or a meaningful affordance (e.g., "view existing document" via details.existing_document_id).

## Actual
DocumentUploader.tsx:218-229 renders the retry button for all error states with no inspection of ApiError.status or ApiError.code — both available on the ApiError class (api.ts:21-31).

## Artifacts
- Screenshot: screenshots/BUG-050-conflict-bare.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Error branch of the upload queue renderer treats all errors as homogeneous/transient.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Compounding with BUG-050 — user gets a meaningless word plus useless guidance.
