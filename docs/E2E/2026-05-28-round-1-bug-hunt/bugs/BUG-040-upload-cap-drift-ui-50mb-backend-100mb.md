# BUG-040: Upload cap drift — UI hardcodes 50 MB, backend enforces 100 MB

> **FIXED 2026-08-31** by spec-31 Batch 2, task 2.1 (unit 1) — commit `8b7d640`. The filed
> root-cause hypothesis held; the drift turned out to have a third, undocumented layer.
> See [Resolution](#resolution) below.

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Fixed**: 2026-08-31 (spec-31 task 2.1, commit `8b7d640`)
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

## Resolution

**FIXED** — spec-31 Batch 2, task 2.1 (unit 1). Commit `8b7d640`, 9 files, +529/−29, shared with
BUG-054 and BUG-074's Branch T.

**The filed hypothesis held.** `UPLOAD_CONSTRAINTS.maxSizeBytes` was a hardcoded literal with no
link to the backend's `max_upload_size_mb`, and the two drifted. What the record could not know is
that there was a **third** cap in the path: the Next proxy's own `proxyClientMaxBodySize`, whose
10 MiB default silently truncated every proxied upload above it — well below both of the two caps
this record compares. A user hitting that one saw BUG-054's symptom, not a size message.

**What changed.** `frontend/lib/types.ts` sets `maxSizeBytes: 100 * 1024 * 1024`;
`frontend/components/DocumentUploader.tsx` carries the matching copy at both sites (the dropzone
line "PDF, Markdown, TXT, RST — max 100 MB" and the rejection string "… exceeds the 100 MB
limit."); `frontend/next.config.ts` raises the proxy body cap to `104_857_600`. All three now equal
`backend/config.py`'s `max_upload_size_mb: int = 100`. Nothing was added — the fix is three
literals moved into agreement with the one the backend already enforced.

**Evidence.**

- `frontend/tests/unit/document-uploader.test.tsx` (3 tests) and the updated
  `frontend/tests/e2e/documents.spec.ts` pin the UI cap and its copy.
- `frontend/tests/unit/next-config.test.ts` asserts `proxyClientMaxBodySize === 104_857_600`
  exactly, by importing the config rather than matching its text.
- Frontend suite after unit 1: **96 passed** (74 before).
- No live upload probe was run for this record; the behavioural cover is the three-arm proxy
  measurement recorded under BUG-054 and the upload rows in `tests/e2e_real/README.md`.

**Still open / follow-ups.**

- The three caps agree by literal duplication, not by a shared source. Raising
  `max_upload_size_mb` alone reopens this record; a follow-up would derive the client value from
  the backend at runtime.
- `proxyClientMaxBodySize` counts the raw multipart envelope while the UI and the backend count the
  file, so a file within a few hundred bytes of 100 MiB passes the client guard and is truncated by
  the proxy. Deterministic and narrow; whether the proxy cap gets envelope headroom is undecided.
