# Agent A5: Settings Page Architect

**Agent Type**: `frontend-architect`
**Model**: Sonnet
**Wave**: 3 (parallel with A4)
**Tasks**: T029-T031

## Mission

Build the settings page with React Hook Form for all 7 settings fields, the ProviderHub for API key management with masked display, and the Toast component for save feedback. Settings saves use PUT (not PATCH) with no optimistic UI.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- Settings (7 fields), Provider, updateSettings (PUT), setProviderKey, deleteProviderKey
- `specs/009-next-frontend/data-model.md` -- Settings entity, Provider entity, save pattern
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T029-T031
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Toast pattern, component props, error handling

## Tasks

1. **T029** [P] [US4] Create `frontend/components/Toast.tsx` -- `{ message: string; type: 'success' | 'error' }` props; fixed position (bottom-right); auto-dismiss after 3s via `setTimeout`; color-coded (green success, red error)
2. **T030** [P] [US4] Create `frontend/components/ProviderHub.tsx` -- renders `Provider[]` from `getProviders()`; `is_active` badge and `has_key` indicator shown independently; when `has_key`: show `"--------"`, never raw key; input for new key; save via `setProviderKey(name, key)`; delete via `deleteProviderKey(name)`; SWR mutate after each action
3. **T031** [US4] Create `frontend/app/settings/page.tsx` -- `'use client'`; `React Hook Form` for all 7 `Settings` fields; `defaultValues` from `getSettings()`; submit calls `updateSettings(data)` (`PUT`); on success: `setToast({ message: 'Settings saved', type: 'success' })`; on error: `setToast({ message: '...', type: 'error' })`; NO optimistic UI; `Toast` component rendered; `ProviderHub` section below form

## Key Constraints

- **Settings has exactly 7 fields**: `default_llm_model`, `default_embed_model`, `confidence_threshold` (integer 0-100), `groundedness_check_enabled`, `citation_alignment_threshold`, `parent_chunk_size`, `child_chunk_size`. There is NO `default_provider`, `max_iterations`, or `max_tool_calls`.
- **PUT, not PATCH**: `updateSettings()` sends `PUT /api/settings` with a partial body. The backend accepts PUT with optional fields.
- **No optimistic UI**: Wait for the API response, THEN show the Toast. Do not update form state before the response arrives.
- **Provider key masking**: When `has_key === true`, display `"--------"` (masked placeholder). NEVER display the raw API key -- the backend does not return it.
- **is_active and has_key are independent**: A provider can be active without a key (e.g., Ollama), or have a key but be inactive. Show both indicators.
- **Toast auto-dismiss**: Auto-dismiss after 3 seconds using `setTimeout`. Color-coded: green for success, red for error.
- **Error shape**: `ApiError` has `.code` and `.message`. Use `error.message` for toast display.

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile: `cd frontend && npx tsc --noEmit`
- Visual verification: Save settings shows toast; refresh shows persisted values; provider key entry shows masked display; delete key updates indicator

## Done Criteria

- `/settings` page renders with React Hook Form for all 7 fields
- Save triggers `PUT /api/settings` and shows Toast on success/error
- No optimistic UI -- waits for API response
- `ProviderHub` renders provider list with `is_active` and `has_key` indicators
- Provider key input masks the display (never shows raw key)
- Toast auto-dismisses after 3 seconds
- `npx tsc --noEmit` exits 0
