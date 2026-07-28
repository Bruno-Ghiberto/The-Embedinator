# BUG-053: spec-08 FR-011 duplicate-response contract mismatch

- **Severity**: COSMETIC
- **Layer**: Backend
- **Discovered**: 2026-06-11T14:12:00Z in Phase 2 (P2-S5)
- **Phase scenario**: P2-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Read spec-08 FR-011: system "MUST detect duplicate documents by content and return a `duplicate` status without re-processing" (implies 200 + status field).
2. POST a duplicate → actual response is HTTP 409 with DUPLICATE_DOCUMENT error envelope.

## Expected
Spec and implementation agree on the duplicate response contract.

## Actual
Implementation returns the more-RESTful 409 envelope; the DUPLICATE_DOCUMENT code string, details.existing_document_id field, SHA-256 content-hash key, collection-scoped (not global) dedup, and completed-rows-only predicate (incremental.py:57) are all code-only, undocumented.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-053-spec-fr011-mismatch.txt (gitignored)
- Trace: null

## Root-cause hypothesis
Spec written before/independent of the error-envelope standardization (spec-12); never reconciled.

## Notes
Doc-only fix; the 409 behavior itself is correct and should be kept.
