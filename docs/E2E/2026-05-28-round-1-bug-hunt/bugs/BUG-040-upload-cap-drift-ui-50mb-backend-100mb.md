# BUG-040: Upload cap drift — UI hardcodes 50 MB, backend enforces 100 MB

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open a collection documents page at localhost:3000.
2. Observe dropzone text "PDF, Markdown, TXT, RST — max 50 MB".
3. Attempt a 50–100 MB upload → client-side rejection "<file> exceeds the 50 MB limit."
4. POST the same file directly to /api/collections/{id}/ingest → backend accepts (cap 100 MB).

## Expected
UI cap matches the backend-enforced cap (Constitution: 100 MB), sourced from shared config.

## Actual
frontend hardcodes maxSizeBytes: 50*1024*1024 at frontend/lib/types.ts:226; UI text at DocumentUploader.tsx:176; error string at DocumentUploader.tsx:119. Backend enforces max_upload_size_mb=100 (backend/config.py:59) at backend/api/ingest.py:70. Valid 50–100 MB uploads blocked client-side with a false limit message; direct API bypasses the UI gate.

## Artifacts
- Screenshot: screenshots/BUG-040-dropzone-cap.png (gitignored)
- Screenshot: screenshots/BUG-040-ui-rejection-live.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
UPLOAD_CONSTRAINTS.maxSizeBytes is a hardcoded literal with no synchronization to backend Settings.max_upload_size_mb; the two values drift independently.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/130
- **Rationale**: The UI states a 50 MB limit that is not the system's limit and blocks valid 50-100 MB uploads with a false rejection message — breaks the upload flow and misstates the constraint.

## Notes
Severity adjudicated MAJOR by Lead+Pilot (analyst proposed MINOR, inspector MAJOR). P2-S4 amended: test ~55 MB via UI (frontend-only rejection) AND 101 MB via direct API curl (backend enforcement, unreachable from UI). Live-confirmed at P2-S4: 55 MB file rejected client-side with 'oversized55.pdf exceeds the 50 MB limit.' while the backend (tested via direct API, P2-S4b) correctly enforces 100 MB with HTTP 413 FILE_TOO_LARGE — the two-layer drift is fully evidenced.
