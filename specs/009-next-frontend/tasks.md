# Tasks: Frontend Application

**Input**: Design documents from `/specs/009-next-frontend/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api-client.ts ✅, quickstart.md ✅

**Agent Teams**: 5 waves, 7 agents — see `Docs/PROMPTS/spec-09-frontend/09-plan.md`
**Testing**: ALL test runs via `scripts/run-tests-external.sh` or npm scripts — NEVER inline in Claude Code

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies among [P] tasks in same phase)
- **[Story]**: User story label (US1–US5) — omitted in Setup, Foundational, and Polish phases
- Exact file paths in all descriptions

---

## Phase 1: Setup (Shared Infrastructure) — Agent A1, Wave 1

**Purpose**: Initialize the Next.js 16 project, install dependencies, configure tooling.

**Agent**: A1 (`Docs/PROMPTS/spec-09-frontend/agents/A1-foundation.md`)

- [X] T001 Initialize Next.js 16 App Router project with TypeScript in `frontend/` — `npx create-next-app@16 frontend --typescript --app --no-src-dir`
- [X] T002 Install runtime dependencies in `frontend/` — `tailwindcss@4`, `swr@2`, `recharts@2`, `react-dropzone@14`, `@radix-ui/react-tooltip`, `@radix-ui/react-dialog`, `@radix-ui/react-select`, `react-hook-form`
- [X] T003 [P] Install dev dependencies in `frontend/` — `vitest@3`, `@testing-library/react@16`, `@testing-library/jest-dom`, `@playwright/test@1.50`, `@vitejs/plugin-react`, `jsdom`, `@vitest/coverage-v8`
- [X] T004 [P] Configure Tailwind CSS v4 in `frontend/tailwind.config.ts` and add global styles import in `frontend/app/globals.css`; define responsive breakpoints: `md` (768px tablet) and `lg` (1024px desktop) to be used consistently across all layout components (FR-023)
- [X] T005 [P] Configure TypeScript strict mode and path aliases in `frontend/tsconfig.json` — `strict: true`, `"@/*": ["./*"]`
- [X] T006 Create `frontend/next.config.ts` — `NEXT_PUBLIC_API_URL` env passthrough; `optimizePackageImports` for `@radix-ui/react-tooltip`, `@radix-ui/react-dialog`, `@radix-ui/react-select` (Vercel BP-2)
- [X] T007 [P] Create `frontend/app/layout.tsx` — root HTML structure, Tailwind globals import, Inter font, Navigation component slot, metadata
- [X] T008 [P] Create `frontend/components/Navigation.tsx` — top nav bar; links to `/chat`, `/collections`, `/documents`, `/settings`, `/observability`; active route highlight via `usePathname`; logo

**Checkpoint**: `cd frontend && npx tsc --noEmit` exits 0

---

## Phase 2: Foundational (Blocking Prerequisites) — Agent A1, Wave 1

**Purpose**: Shared types, full API client, and all SWR hooks — MUST complete before any user story.

**⚠️ CRITICAL**: No user story phase can begin until this phase is complete.

**Agent**: A1 (`Docs/PROMPTS/spec-09-frontend/agents/A1-foundation.md`)

- [X] T009 Create `frontend/lib/types.ts` — all TypeScript interfaces: `Collection`, `Document` (status: 5 values), `IngestionJob` (status: 7 values), `ChatMessage`, `Citation` (with `source_removed: boolean`), `ModelInfo`, `Provider` (`is_active` and `has_key` independent), `Settings`, `SettingsUpdateRequest` (all optional), `QueryTrace`, `QueryTraceDetail`, `HealthStatus`, `HealthService`, `SystemStats`, `NdjsonEvent` discriminated union (all 10 types — `chunk.text` not `content`), `ChatRequest`, `StreamChatCallbacks`, `ApiErrorResponse`, `UPLOAD_CONSTRAINTS` constant (50 MB, `['pdf','md','txt','rst']`)
- [X] T010 Create `frontend/lib/api.ts` — `ApiError` class; `API_BASE`; all 17 typed async functions per `specs/009-next-frontend/contracts/api-client.ts`; `streamChat()` using `ReadableStream` + `TextDecoder` + line-split `JSON.parse()` (NO `data:` prefix); all 10 event types dispatched to `StreamChatCallbacks`; `clarification` handler calls `onClarification` AND releases `isStreaming` (no `done` follows); settings endpoint is `PUT /api/settings` (not PATCH)
- [X] T011 [P] Create `frontend/hooks/useStreamChat.ts` — `isStreaming` state (default `false`); `setIsStreaming(false)` in `onDone`, `onError`, AND `onClarification` handlers; functional `setState` for message accumulation (Vercel BP-3); `AbortController` stored in ref; abort on component unmount (Vercel BP-7)
- [X] T012 [P] Create `frontend/hooks/useCollections.ts` — `useSWR('/api/collections', getCollections)`; return `{ collections, isLoading, isError, mutate }`; optimistic delete via `mutate`
- [X] T013 [P] Create `frontend/hooks/useModels.ts` — separate `useSWR` for `getLLMModels` and `getEmbedModels`; return `{ llmModels, embedModels, isLoading, isError }`
- [X] T014 [P] Create `frontend/hooks/useTraces.ts` — `useSWR` for `getTraces`; accept `params` (limit, offset, session_id); return `{ traces, total, isLoading, isError, mutate }`

**Checkpoint**: `cd frontend && npx tsc --noEmit` exits 0; `streamChat()` exported; all 4 hooks exported

---

## Phase 3: User Story 1 — Conversational RAG Query (Priority: P1) 🎯 MVP

**Goal**: Multi-turn chat with NDJSON streaming, inline citations, confidence indicator, send-button lock.

**Agent**: A2 (`Docs/PROMPTS/spec-09-frontend/agents/A2-chat-page.md`) — Wave 2, parallel with A3

**Independent Test**: Open `/chat`; select a collection; submit a question; verify tokens appear word by word; send button locks during streaming and re-enables on completion; citations rendered inline; confidence dot shown after completion.

- [X] T015 [P] [US1] Create `frontend/components/ConfidenceIndicator.tsx` — integer 0–100 score; `getConfidenceTier`: `≥70` → green, `≥40` → yellow, `<40` → red; colored dot; numeric score visible on Radix Tooltip hover
- [X] T016 [P] [US1] Create `frontend/components/CitationTooltip.tsx` — Radix Tooltip wrapping inline `[N]` citation marker; renders `citation.text` (passage) and `citation.document_name` (file name); renders "source removed" badge instead of source link when `citation.source_removed === true` (Constitution IV); NOTE: `page` and `breadcrumb` absent from current Citation schema — do NOT fabricate them; add when backend extends Citation model
- [X] T017 [P] [US1] Create `frontend/components/ChatInput.tsx` — controlled textarea; send button `disabled={isStreaming || !message.trim() || selectedCollections.length === 0}`; Enter-to-submit (Shift+Enter for newline); `onSubmit(message)` callback; clears on submit
- [X] T018 [P] [US1] Create `frontend/components/ModelSelector.tsx` — Radix Select wrapping `ModelInfo[]`; separate exports `LLMModelSelector` and `EmbedModelSelector`; `selectedModel: string`, `onSelect: (model: string) => void` props
- [X] T019 [US1] Create `frontend/components/ChatSidebar.tsx` — collection multi-select checkboxes from `useCollections`; `LLMModelSelector` and `EmbedModelSelector`; reads/writes URL params via `useSearchParams` + `useRouter`; lazy `useState` init for URL param parsing (Vercel BP-8)
- [X] T020 [US1] Create `frontend/components/ChatPanel.tsx` — scrollable multi-turn message thread; new Q&A appended at bottom; token accumulation via functional `setState` (Vercel BP-3); `CitationTooltip` rendered per citation in assistant message; `ConfidenceIndicator` shown after complete response; passive scroll event listener (Vercel BP-7); auto-scroll to bottom on new message
- [X] T021 [US1] Create `frontend/app/chat/page.tsx` — `'use client'`; reads collections/llm/embed from URL params; wires `ChatPanel`, `ChatInput`, `ChatSidebar`; calls `useStreamChat`; passes `isStreaming` to `ChatInput`; session ID persisted across turns

**Checkpoint**: `/chat` renders; streaming works end-to-end; send button locks during stream; `npx tsc --noEmit` exits 0

---

## Phase 4: User Story 2 — Collection Management (Priority: P2)

**Goal**: Collection grid with CRUD, slug validation, conflict error without dialog close.

**Agent**: A3 (`Docs/PROMPTS/spec-09-frontend/agents/A3-collections-page.md`) — Wave 2, parallel with A2

**Independent Test**: Open `/collections`; create a collection with a valid slug; verify card appears; try invalid name → inline error; try duplicate name → conflict error inside open dialog; delete collection → confirmation → removed from grid.

- [X] T022 [P] [US2] Create `frontend/components/CollectionCard.tsx` — card showing `name`, `description`, `document_count`, `embedding_model`, `chunk_profile`; card title (or "View Documents" button) is a `next/link` to `/documents/{id}` (FR-010); delete button opens Radix Dialog confirmation; on confirm calls `deleteCollection(id)` + `mutate`
- [X] T023 [P] [US2] Create `frontend/components/CreateCollectionDialog.tsx` — Radix Dialog; `name` field with inline validation regex `^[a-z0-9][a-z0-9_-]*$`; optional `description`; `embedding_model` Radix Select; on submit calls `createCollection()`; catches `ApiError` with code `COLLECTION_NAME_CONFLICT` → shows inline error WITHOUT closing dialog; on success closes and calls `mutate`
- [X] T024 [US2] Create `frontend/components/CollectionList.tsx` — responsive card grid from `useCollections`; loading skeleton; empty state with call-to-action; `CreateCollectionDialog` trigger button
- [X] T025 [US2] Create `frontend/app/collections/page.tsx` — `'use client'`; renders `CollectionList`; error boundary for failed fetch

**Checkpoint**: `/collections` CRUD works independently; `npx tsc --noEmit` exits 0

---

## Phase 5: User Story 3 — Document Upload and Ingestion Tracking (Priority: P3)

**Goal**: Drag-and-drop upload with 50 MB + extension validation, job status polling, status badge table.

**Agent**: A4 (`Docs/PROMPTS/spec-09-frontend/agents/A4-documents-page.md`) — Wave 3, parallel with A5

**Independent Test**: Open `/documents/[collectionId]`; drag a PDF; progress bar appears; status badge cycles; completed badge shown. Drag a >50 MB file → inline error, no upload. Drag `.exe` → inline error.

- [X] T026 [P] [US3] Create `frontend/components/DocumentList.tsx` — table with `Document[]`; color-coded status badges for all 5 `DocumentStatus` values (`pending`, `ingesting`, `completed`, `failed`, `duplicate`); delete button calls `deleteDocument(id)` + `mutate`; loading and empty states
- [X] T027 [US3] Create `frontend/components/DocumentUploader.tsx` — `react-dropzone` with `accept` from `UPLOAD_CONSTRAINTS.accept`; client-side size guard: `file.size > UPLOAD_CONSTRAINTS.maxSizeBytes` → show inline error, NO `ingestFile()` call; extension guard: extension not in `UPLOAD_CONSTRAINTS.allowedExtensions` → inline error; on valid file: call `ingestFile(collectionId, file)`; poll `getIngestionJob()` every 2s using `setInterval`; clear interval on terminal state (`completed` | `failed`); show progress fraction `chunks_processed/chunks_total`; call `mutate` on completion
- [X] T028 [US3] Create `frontend/app/documents/[id]/page.tsx` — `'use client'`; `collectionId` from `useParams`; renders `DocumentList` + `DocumentUploader`; handle invalid/missing collection ID

**Checkpoint**: 50 MB guard prevents upload; extension guard prevents upload; valid file polls to completion; `npx tsc --noEmit` exits 0

---

## Phase 6: User Story 4 — Settings and Provider API Key Management (Priority: P4)

**Goal**: Agent behavior settings form, provider key management, toast notifications on save.

**Agent**: A5 (`Docs/PROMPTS/spec-09-frontend/agents/A5-settings-page.md`) — Wave 3, parallel with A4

**Independent Test**: Open `/settings`; change `confidence_threshold`; save → toast success; refresh → value persisted. Enter provider key → masked display. Delete key → `has_key: false`.

- [X] T029 [P] [US4] Create `frontend/components/Toast.tsx` — `{ message: string; type: 'success' | 'error' }` props; fixed position (bottom-right); auto-dismiss after 3s via `setTimeout`; color-coded (green success, red error)
- [X] T030 [P] [US4] Create `frontend/components/ProviderHub.tsx` — renders `Provider[]` from `getProviders()`; `is_active` badge and `has_key` indicator shown independently; when `has_key`: show `"••••••••"`, never raw key; input for new key; save via `setProviderKey(name, key)`; delete via `deleteProviderKey(name)`; SWR mutate after each action
- [X] T031 [US4] Create `frontend/app/settings/page.tsx` — `'use client'`; `React Hook Form` for all 7 `Settings` fields; `defaultValues` from `getSettings()`; submit calls `updateSettings(data)` (`PUT`); on success: `setToast({ message: 'Settings saved', type: 'success' })`; on error: `setToast({ message: '...', type: 'error' })`; NO optimistic UI; `Toast` component rendered; `ProviderHub` section below form

**Checkpoint**: Settings save persists; toast appears on success/error; provider key masked; `npx tsc --noEmit` exits 0

---

## Phase 7: User Story 5 — Observability and System Health (Priority: P5)

**Goal**: Health cards, latency histogram, confidence distribution, paginated trace table with expandable detail.

**Agent**: A6 (`Docs/PROMPTS/spec-09-frontend/agents/A6-observability-page.md`) — Wave 4, serial

**Independent Test**: Open `/observability`; health cards show sqlite/qdrant/ollama with status and latency; charts render; trace table paginates; expanding a row shows reasoning steps.

- [X] T032 [P] [US5] Create `frontend/components/HealthDashboard.tsx` — 3 service cards from `getHealth()`; service names `sqlite`/`qdrant`/`ollama`; green `ok` / red `error` status badge; `latency_ms` value; `error_message` shown on error state
- [X] T033 [P] [US5] Create `frontend/components/LatencyChart.tsx` — `recharts` `BarChart` showing query latency distribution (buckets from trace data); loaded via `next/dynamic` with `{ ssr: false }` (Vercel BP-1); loading placeholder
- [X] T034 [P] [US5] Create `frontend/components/ConfidenceDistribution.tsx` — `recharts` `BarChart` with 3 bars (green ≥70, yellow 40–69, red <40) computed from trace `confidence_score` values; loaded via `next/dynamic` with `{ ssr: false }` (Vercel BP-1)
- [X] T035 [P] [US5] Create `frontend/components/TraceTable.tsx` — paginated via `useTraces`; previous/next controls; `session_id` filter input; expand row fetches `getTraceDetail(id)` on demand; expanded row shows `sub_questions`, `reasoning_steps`, `strategy_switches`, `meta_reasoning_triggered` flag
- [X] T036 [P] [US5] Create `frontend/components/CollectionStats.tsx` — per-collection `document_count` from `useCollections`; aggregate `total_chunks` and `total_documents` from `getStats()`; parallel `useSWR` keys (Vercel BP-6)
- [X] T037 [US5] Create `frontend/app/observability/page.tsx` — `'use client'`; composes `HealthDashboard`, `LatencyChart`, `ConfidenceDistribution`, `TraceTable`, `CollectionStats`; parallel SWR fetches for health and stats; incremental loading states (each section renders independently)

**Checkpoint**: All 5 observability sections render; trace table paginates; `npx tsc --noEmit` exits 0

---

## Phase 8: Quality and Testing — Agent A7, Wave 5

**Purpose**: vitest unit tests, Playwright E2E tests, TypeScript audit.

**Agent**: A7 (`Docs/PROMPTS/spec-09-frontend/agents/A7-quality-tests.md`) — Wave 5, serial

- [X] T038 [P] Create `frontend/vitest.config.ts` — jsdom environment, `@vitejs/plugin-react`, coverage provider `v8`, coverage threshold lines ≥70%; add `test` script to `frontend/package.json`: `vitest run`; add `test:coverage` script
- [X] T039 [P] Create `frontend/playwright.config.ts` — `baseURL: 'http://localhost:3000'`; screenshots on failure; trace on first retry; `testDir: './tests/e2e'`; add `test:e2e` script to `frontend/package.json`
- [X] T040 [P] Write unit tests in `frontend/tests/unit/api.test.ts` — `streamChat()` NDJSON parsing for all 10 event types; `clarification` calls `onClarification` and releases `isStreaming` (no `done` follows); `updateSettings` sends `PUT` not `PATCH`; error response parsed as `ApiError`; `source_removed` field preserved in `Citation`
- [X] T041 [P] Write unit tests in `frontend/tests/unit/components.test.ts` — `ConfidenceIndicator` tier boundaries: score 0→red, 39→red, 40→yellow, 69→yellow, 70→green, 100→green; `CitationTooltip` renders "source removed" badge when `source_removed===true`; `CollectionCard` delete confirmation dialog appears before action; `CreateCollectionDialog` invalid slug shows error, valid slug does not
- [X] T042 [P] Write unit tests in `frontend/tests/unit/hooks.test.ts` — `useStreamChat` `isStreaming` released on `done` event; released on `error` event; released on `clarification` event; message array appended correctly; functional setState prevents stale closure on rapid chunks
- [X] T043 Write E2E test in `frontend/tests/e2e/chat.spec.ts` — submit query with collection selected; streaming tokens appear; send button disabled during stream; send button re-enabled on completion; confidence indicator rendered after `done`; citation `[1]` marker visible; hover shows tooltip
- [X] T044 [P] Write E2E test in `frontend/tests/e2e/collections.spec.ts` — create with valid name → card in grid; invalid name (`-foo`) → inline error; duplicate name → dialog stays open with conflict error; delete → dialog → confirmed → card removed
- [X] T045 [P] Write E2E test in `frontend/tests/e2e/documents.spec.ts` — upload file >50 MB → inline error, no network request; upload `.exe` → inline error; upload valid PDF → progress shown → polling → completed badge
- [X] T046 [P] Write E2E test in `frontend/tests/e2e/settings.spec.ts` — change `confidence_threshold`, save → toast "Settings saved" appears; refresh → value persisted; enter provider key → field shows masked value; delete key → has_key indicator shows false

**Checkpoint**: `cd frontend && npm run test -- --run` passes; `npx playwright test` passes; `npx tsc --noEmit` exits 0

---

## Phase 9: Docker Integration and Polish

**Purpose**: Docker Compose integration, Python regression baseline, final coverage audit.

- [X] T047 Add `frontend` service to `docker-compose.yml` — port 3000, `NEXT_PUBLIC_API_URL=http://backend:8000`, `depends_on: [backend]`; create `Dockerfile.frontend` with Node.js LTS, `npm ci`, `npm run build`, `CMD ["npm", "start"]`
- [X] T048 [P] TypeScript strict compile audit — run `cd frontend && npx tsc --noEmit`; fix all remaining type errors; `strict: true` must be enforced throughout
- [X] T049 [P] Run Python regression baseline — `zsh scripts/run-tests-external.sh -n spec09-regression tests/`; poll `cat Docs/Tests/spec09-regression.status`; verify PASSED (0 regressions from frontend work)
- [X] T050 Final vitest coverage check — `cd frontend && npm run test:coverage`; verify ≥70% line coverage reported; fix any gaps if below threshold
- [X] T051 [P] Write Playwright E2E responsive viewport test in `frontend/tests/e2e/responsive.spec.ts` — verify all 5 pages render without horizontal overflow at 768px and 1024px widths via `page.setViewportSize()`; verify navigation bar visible at both breakpoints (FR-023, SC-002)
- [X] T052 Write Playwright E2E cross-page workflow test in `frontend/tests/e2e/workflow.spec.ts` — create a new collection, navigate to its documents page, upload a valid file, wait for "completed" status badge, navigate to chat, select that collection, submit a query, verify a streamed response appears (SC-003 end-to-end journey)

**Checkpoint**: `docker compose up` starts all 4 services including frontend on :3000; Python baseline PASSED; vitest coverage ≥70%; responsive test passes at 768px and 1024px; SC-003 workflow E2E passes

---

## Dependencies and Execution Order

### Phase Dependencies

- **Phase 1** (Setup, T001–T008): No dependencies — start immediately
- **Phase 2** (Foundational, T009–T014): Depends on Phase 1 — BLOCKS all user story phases
- **Phase 3** (US1 Chat, T015–T021): Requires Phase 2
- **Phase 4** (US2 Collections, T022–T025): Requires Phase 2 — **parallel with Phase 3** (Wave 2)
- **Phase 5** (US3 Documents, T026–T028): Requires Phase 2 and Phase 4 (collection context)
- **Phase 6** (US4 Settings, T029–T031): Requires Phase 2 — **parallel with Phase 5** (Wave 3)
- **Phase 7** (US5 Observability, T032–T037): Requires Phase 2
- **Phase 8** (Quality, T038–T046): Requires all user story phases complete (Wave 5)
- **Phase 9** (Docker, T047–T052): Requires Phase 8

### Agent → Phase Mapping

| Agent | Wave | Phases | Tasks | Model |
|-------|------|--------|-------|-------|
| A1 | 1 | Phase 1 + 2 | T001–T014 | Opus |
| A2 | 2 (parallel) | Phase 3 / US1 | T015–T021 | Opus |
| A3 | 2 (parallel) | Phase 4 / US2 | T022–T025 | Sonnet |
| A4 | 3 (parallel) | Phase 5 / US3 | T026–T028 | Sonnet |
| A5 | 3 (parallel) | Phase 6 / US4 | T029–T031 | Sonnet |
| A6 | 4 | Phase 7 / US5 | T032–T037 | Sonnet |
| A7 | 5 | Phase 8 Quality | T038–T046 | Sonnet |

Phase 9 (T047–T052) is orchestrator-level work post Wave 5.

### Within Each Phase

- [P]-marked tasks can run simultaneously (different files, no inter-dependencies)
- Unmarked tasks must run after their [P] predecessors in the same phase
- Within US1: T015–T018 parallel → T019 → T020 → T021
- Within US5: T032–T036 parallel → T037

---

## Parallel Execution Examples

### Wave 2 (A2 + A3 simultaneous)
```
A2: T015 ConfidenceIndicator.tsx
    T016 CitationTooltip.tsx       ← all 4 in parallel
    T017 ChatInput.tsx
    T018 ModelSelector.tsx
    → T019 ChatSidebar.tsx
    → T020 ChatPanel.tsx
    → T021 chat/page.tsx

A3: T022 CollectionCard.tsx        ← parallel with A2
    T023 CreateCollectionDialog.tsx
    → T024 CollectionList.tsx
    → T025 collections/page.tsx
```

### Wave 3 (A4 + A5 simultaneous)
```
A4: T026 DocumentList.tsx
    → T027 DocumentUploader.tsx
    → T028 documents/[id]/page.tsx

A5: T029 Toast.tsx                  ← parallel with A4
    T030 ProviderHub.tsx
    → T031 settings/page.tsx
```

### Wave 5 (A7 — all [P] first)
```
T038 vitest.config.ts               ← all [P] tasks in parallel
T039 playwright.config.ts
T040 api.test.ts
T041 components.test.ts
T042 hooks.test.ts
→ T043 chat.spec.ts                 ← serial (comprehensive E2E)
T044 collections.spec.ts            ← [P] after T043
T045 documents.spec.ts
T046 settings.spec.ts
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 only)

1. Phase 1: Setup
2. Phase 2: Foundational (CRITICAL — blocks all stories)
3. Phase 3: US1 Chat (A2, Wave 2)
4. Phase 4: US2 Collections (A3, Wave 2, parallel with A3)
5. **STOP and VALIDATE**: `/chat` and `/collections` work independently
6. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready (A1)
2. US1 Chat + US2 Collections → MVP (A2 + A3 parallel)
3. US3 Documents + US4 Settings → Upload + config (A4 + A5 parallel)
4. US5 Observability → Full observability (A6)
5. Quality pass → Production-ready (A7)
6. Docker integration → Deployable

---

## Notes

- `[P]` tasks = different files, no intra-phase dependencies
- `[USn]` label maps task to user story for traceability
- `TypeScript strict mode` enforced throughout — `npx tsc --noEmit` is a wave gate
- NEVER run `npm test` or `vitest` inline in Claude Code — use npm scripts in background
- NEVER display raw provider API keys — `has_key: bool` only
- `source_removed: true` in Citation MUST render a "source removed" badge (Constitution IV)
- `streamChat()` `clarification` event ends the stream without `done` — MUST release `isStreaming`
- Settings endpoint is `PUT /api/settings` (not PATCH)
- File upload: 50 MB guard + extension allowlist BEFORE any `ingestFile()` call (Constitution V)
