# Agent A4: Documents Page Architect

**Agent Type**: `frontend-architect`
**Model**: Sonnet
**Wave**: 3 (parallel with A5)
**Tasks**: T026-T028

## Mission

Build the per-collection documents page with a status badge table, drag-and-drop file upload with client-side 50 MB and extension guards (no network request on violation), and ingestion job polling until terminal state.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- Document, IngestionJob, UPLOAD_CONSTRAINTS, ingestFile, getIngestionJob signatures
- `specs/009-next-frontend/data-model.md` -- DocumentStatus (5 values), IngestionJobStatus (7 values), terminal states
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T026-T028
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Upload guard pattern, component props

## Tasks

1. **T026** [P] [US3] Create `frontend/components/DocumentList.tsx` -- table with `Document[]`; color-coded status badges for all 5 `DocumentStatus` values (`pending`, `ingesting`, `completed`, `failed`, `duplicate`); delete button calls `deleteDocument(id)` + `mutate`; loading and empty states
2. **T027** [US3] Create `frontend/components/DocumentUploader.tsx` -- `react-dropzone` with `accept` from `UPLOAD_CONSTRAINTS.accept`; client-side size guard: `file.size > UPLOAD_CONSTRAINTS.maxSizeBytes` shows inline error, NO `ingestFile()` call; extension guard: extension not in `UPLOAD_CONSTRAINTS.allowedExtensions` shows inline error; on valid file: call `ingestFile(collectionId, file)`; poll `getIngestionJob()` every 2s using `setInterval`; clear interval on terminal state (`completed` | `failed`); show progress fraction `chunks_processed/chunks_total`; call `mutate` on completion
3. **T028** [US3] Create `frontend/app/documents/[id]/page.tsx` -- `'use client'`; `collectionId` from `useParams`; renders `DocumentList` + `DocumentUploader`; handle invalid/missing collection ID

## Key Constraints

- **50 MB client-side guard**: Check `file.size > UPLOAD_CONSTRAINTS.maxSizeBytes` BEFORE calling `ingestFile()`. Show inline error. Make NO network request for oversized files.
- **Extension allowlist**: Only `pdf`, `md`, `txt`, `rst` are allowed. Check file extension BEFORE calling `ingestFile()`. Show inline error for disallowed types.
- **DocumentStatus**: 5 values -- `pending`, `ingesting`, `completed`, `failed`, `duplicate`. These are document-level states shown in the table.
- **IngestionJobStatus**: 7 values -- `pending`, `started`, `streaming`, `embedding`, `completed`, `failed`, `paused`. These are job-level states shown during active upload polling.
- **Terminal states**: Stop polling when `status` is `"completed"` or `"failed"`.
- **deleteDocument signature**: `deleteDocument(docId: string)` -- takes only the document ID (NOT collection ID + doc ID).
- **Poll interval**: Every 2 seconds using `setInterval`. Clear on terminal state and on component unmount.
- **UPLOAD_CONSTRAINTS**: Import from `lib/types.ts`. Use `UPLOAD_CONSTRAINTS.maxSizeBytes`, `UPLOAD_CONSTRAINTS.allowedExtensions`, and `UPLOAD_CONSTRAINTS.accept`.

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile: `cd frontend && npx tsc --noEmit`
- Visual verification: Upload >50 MB file shows error (no network); upload `.exe` shows error; upload valid PDF shows progress and polls to completion

## Done Criteria

- `/documents/[id]` page renders document table and uploader
- 50 MB guard prevents upload and shows inline error
- Extension guard prevents upload and shows inline error
- Valid file uploads, polls every 2s, and shows progress
- Polling stops on terminal state
- Document table shows all 5 status badge colors
- `npx tsc --noEmit` exits 0
