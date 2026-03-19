# Agent A1: Foundation Architect

**Agent Type**: `system-architect`
**Model**: Opus
**Wave**: 1
**Tasks**: T001-T014

## Mission

Scaffold the Next.js 16 project, create all shared TypeScript types matching backend contracts exactly, implement the centralized NDJSON API client with all 17+ functions, and build the 4 SWR hooks that every subsequent wave depends on.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- TypeScript types and all API function signatures (AUTHORITATIVE)
- `specs/009-next-frontend/data-model.md` -- Entity definitions, NDJSON event types, confidence tiers
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Implementation context, code specifications, patterns

## Tasks

### Phase 1: Setup (T001-T008)

1. **T001** Initialize Next.js 16 App Router project with TypeScript in `frontend/` -- `npx create-next-app@16 frontend --typescript --app --no-src-dir`
2. **T002** Install runtime dependencies in `frontend/` -- `tailwindcss@4`, `swr@2`, `recharts@2`, `react-dropzone@14`, `@radix-ui/react-tooltip`, `@radix-ui/react-dialog`, `@radix-ui/react-select`, `react-hook-form`
3. **T003** [P] Install dev dependencies in `frontend/` -- `vitest@3`, `@testing-library/react@16`, `@testing-library/jest-dom`, `@playwright/test@1.50`, `@vitejs/plugin-react`, `jsdom`, `@vitest/coverage-v8`
4. **T004** [P] Configure Tailwind CSS v4 in `frontend/tailwind.config.ts` and global styles in `frontend/app/globals.css`; define responsive breakpoints `md` (768px) and `lg` (1024px)
5. **T005** [P] Configure TypeScript strict mode and path aliases in `frontend/tsconfig.json` -- `strict: true`, `"@/*": ["./*"]`
6. **T006** Create `frontend/next.config.ts` -- `NEXT_PUBLIC_API_URL` env passthrough; `optimizePackageImports` for Radix UI packages
7. **T007** [P] Create `frontend/app/layout.tsx` -- root HTML structure, Tailwind globals import, Inter font, Navigation component slot, metadata
8. **T008** [P] Create `frontend/components/Navigation.tsx` -- top nav bar; links to `/chat`, `/collections`, `/documents`, `/settings`, `/observability`; active route highlight via `usePathname`

### Phase 2: Foundational (T009-T014)

9. **T009** Create `frontend/lib/types.ts` -- ALL TypeScript interfaces from `contracts/api-client.ts`: `Collection`, `Document` (status: 5 values), `IngestionJob` (status: 7 values including "pending"), `ChatMessage`, `Citation` (with `source_removed: boolean`), `ModelInfo`, `Provider`, `Settings` (7 fields only), `SettingsUpdateRequest`, `QueryTrace`, `QueryTraceDetail`, `HealthStatus` (with `services[]` array), `HealthService`, `SystemStats`, `NdjsonEvent` discriminated union (all 10 types), `ChatRequest`, `StreamChatCallbacks`, `ApiErrorResponse` (with `error.code/message`), `UPLOAD_CONSTRAINTS`, `getConfidenceTier`
10. **T010** Create `frontend/lib/api.ts` -- `ApiError` class; `API_BASE`; all 17+ typed async functions per contracts; `streamChat()` using `ReadableStream` + `TextDecoder` + line-split `JSON.parse()` (NO `data:` prefix); all 10 NDJSON event types dispatched to `StreamChatCallbacks`; `clarification` releases `isStreaming`; settings endpoint is `PUT`
11. **T011** [P] Create `frontend/hooks/useStreamChat.ts` -- `isStreaming` state; `setIsStreaming(false)` in `onDone`, `onError`, AND `onClarification`; functional `setState` for message accumulation; `AbortController` in ref; abort on unmount
12. **T012** [P] Create `frontend/hooks/useCollections.ts` -- `useSWR('/api/collections', getCollections)`; return `{ collections, isLoading, isError, mutate }`
13. **T013** [P] Create `frontend/hooks/useModels.ts` -- separate `useSWR` for `getLLMModels` and `getEmbedModels`
14. **T014** [P] Create `frontend/hooks/useTraces.ts` -- `useSWR` for `getTraces`; accept params; return `{ traces, total, isLoading, isError, mutate }`

## Key Constraints

- **NDJSON, NOT Server-Sent Events**: `streamChat()` parses raw JSON lines. There is NO `data:` prefix. Never write `line.startsWith("data: ")`.
- **All 10 event types**: session, status, chunk, clarification, citation, meta_reasoning, confidence, groundedness, done, error. The `chunk` event has field `text` (NOT `content`). The callback is named `onToken` but receives `event.text`.
- **clarification ends the stream**: No `done` event follows a `clarification`. `isStreaming` MUST be released in the `onClarification` handler.
- **Confidence is INTEGER 0-100**: Not a float. Tiers: >= 70 green, >= 40 yellow, < 40 red.
- **Citation fields**: `passage_id`, `document_id`, `document_name`, `start_offset`, `end_offset`, `text`, `relevance_score`, `source_removed`. NOT `page`, `breadcrumb`, `index`, `chunkId`, `source`.
- **Error shape**: `{ error: { code, message }, trace_id }`. NOT `{ detail }`.
- **Settings**: 7 fields only. NO `default_provider`, `max_iterations`, `max_tool_calls`.
- **HealthStatus**: `{ status, services[] }` with `HealthService` objects. NOT flat `qdrant`/`ollama`/`sqlite` fields.
- **IngestionJobStatus**: 7 values INCLUDING `"pending"`. Do not omit it.
- **Settings endpoint**: `PUT /api/settings` (NOT PATCH).

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile check: `cd frontend && npx tsc --noEmit`
- This is Gate 1 -- must exit 0 before Wave 2 agents spawn

## Done Criteria

- `npx tsc --noEmit` exits 0
- `streamChat()` is exported and handles all 10 NDJSON event types
- All 4 SWR hooks are exported (`useStreamChat`, `useCollections`, `useModels`, `useTraces`)
- `lib/types.ts` has every interface from `contracts/api-client.ts` with no invented fields
- `lib/api.ts` has all 17+ API functions with correct endpoints and error handling
