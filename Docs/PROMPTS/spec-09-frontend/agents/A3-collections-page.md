# Agent A3: Collections Page Architect

**Agent Type**: `frontend-architect`
**Model**: Sonnet
**Wave**: 2 (parallel with A2)
**Tasks**: T022-T025

## Mission

Build the collections management page with a responsive card grid, collection creation dialog with slug validation and conflict error handling that keeps the dialog open, and delete confirmation via Radix Dialog.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- Collection interface, createCollection, deleteCollection signatures
- `specs/009-next-frontend/data-model.md` -- Collection entity, CollectionCreateRequest, validation rules
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T022-T025
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Component props, error handling patterns

## Tasks

1. **T022** [P] [US2] Create `frontend/components/CollectionCard.tsx` -- card showing `name`, `description`, `document_count`, `embedding_model`, `chunk_profile`; card title (or "View Documents" button) is a `next/link` to `/documents/{id}` (FR-010); delete button opens Radix Dialog confirmation; on confirm calls `deleteCollection(id)` + `mutate`
2. **T023** [P] [US2] Create `frontend/components/CreateCollectionDialog.tsx` -- Radix Dialog; `name` field with inline validation regex `^[a-z0-9][a-z0-9_-]*$`; optional `description`; `embedding_model` Radix Select; on submit calls `createCollection()`; catches `ApiError` with code `COLLECTION_NAME_CONFLICT` -- shows inline error WITHOUT closing dialog; on success closes and calls `mutate`
3. **T024** [US2] Create `frontend/components/CollectionList.tsx` -- responsive card grid from `useCollections`; loading skeleton; empty state with call-to-action; `CreateCollectionDialog` trigger button
4. **T025** [US2] Create `frontend/app/collections/page.tsx` -- `'use client'`; renders `CollectionList`; error boundary for failed fetch

## Key Constraints

- **Collection interface**: `{ id, name, description, embedding_model, chunk_profile, document_count, created_at }`. There is NO `totalChunks` field -- do not fabricate it.
- **Slug validation**: Name must match `^[a-z0-9][a-z0-9_-]*$`, max 100 chars. Validate inline before submission.
- **Conflict error handling**: When `createCollection()` throws `ApiError` with `error.code === "COLLECTION_NAME_CONFLICT"`, display the error message INSIDE the dialog WITHOUT closing it. Only close on success.
- **Error shape**: `ApiError` has `.code` and `.message` properties (NOT `.detail`). Check `error.code` for programmatic branching.
- **Link to documents**: Each collection card must link to `/documents/{collection.id}` (FR-010).
- **SWR mutate**: After create or delete, call `mutate()` from `useCollections` to refresh the list.

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile: `cd frontend && npx tsc --noEmit`
- Visual verification: `/collections` renders; create with valid slug works; invalid slug shows error; duplicate shows conflict in open dialog; delete confirms then removes

## Done Criteria

- `/collections` page renders a responsive card grid
- Create dialog validates slug format inline
- Conflict error (409) displays inside open dialog without closing
- Delete shows Radix Dialog confirmation before executing
- Collection cards link to `/documents/{id}`
- `npx tsc --noEmit` exits 0
