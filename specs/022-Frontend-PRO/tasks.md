# Tasks: Frontend PRO (Spec 022)

**Feature**: Professional Agentic RAG Chat Interface
**Branch**: `022-frontend-pro`
**Total Tasks**: 47
**Phases**: 8 (1 setup + 1 foundational + 5 user stories + 1 polish)
**Constraint**: Zero backend changes — frontend-only

---

## Phase 1: Setup

**Goal**: Install dependencies and new shadcn components.

- [x] T001 Install npm dependencies: `pnpm add react-markdown remark-gfm rehype-highlight` in `frontend/package.json`
- [x] T002 Install new shadcn components: `pnpm dlx shadcn@latest add hover-card collapsible kbd` — verify files created in `frontend/components/ui/`
- [x] T003 Install recommended shadcn components: `pnpm dlx shadcn@latest add avatar alert checkbox` in `frontend/components/ui/`

---

## Phase 2: Foundational — CSS Foundation (US-1)

**Goal**: Fix Tailwind v4 CSS scanning, standardize token system, fix layout height. After this phase, ALL 20 existing shadcn components render with proper styling across all 5 pages.

**Story**: US-1 — First Impression (Styled Interface)

**Independent Test Criteria**:
- Sidebar renders with styled background, not unstyled `<ul>` (SC-001)
- Breadcrumbs render as styled inline text, not `<ol>` list (SC-003)
- `Cmd+K` opens command palette as floating dialog (SC-004)
- No `var(--color-*)` custom tokens in component files (SC-014)
- Chat fills viewport: input at bottom, messages scroll (SC-002)
- No JS console errors on all 5 pages (SC-012)

### Tasks

- [x] T004 Add Tailwind v4 `@source` directives in `frontend/app/globals.css` — add `@source "../components/**/*.tsx";` and `@source "../app/**/*.tsx";` after the `@import "tailwindcss"` line
- [x] T005 Verify CSS scanning: run `pnpm run build` in `frontend/` and grep compiled CSS for marker classes `bg-sidebar`, `text-sidebar-foreground`, `data-[state=open]`, `group-data-[collapsible=icon]`
- [x] T006 Remove all custom `--color-*` token declarations from `:root` and `.dark` blocks in `frontend/app/globals.css` — keep only shadcn standard tokens + custom `--warning` and `--success`
- [x] T007 [P] Convert Obsidian Violet palette hex values to OKLCH format in `frontend/app/globals.css` — update `:root` and `.dark` CSS variable values
- [x] T008 [P] Add `@custom-variant dark (&:where(.dark, .dark *));` to `frontend/app/globals.css` if not already present
- [x] T009 Migrate all component files from custom `var(--color-*)` tokens to shadcn standard tokens — search `frontend/components/` and `frontend/app/` for `var(--color-` and replace per migration map in `research.md` Decision 2
- [x] T010 [P] Replace `var(--color-*)` references in `frontend/components/StatusBanner.tsx` with shadcn token equivalents
- [x] T011 Clean up Radix/Base UI dependencies: grep `frontend/components/ui/*.tsx` for `@radix-ui` imports, remove unused `@radix-ui/react-*` packages from `frontend/package.json`, update `optimizePackageImports` in `frontend/next.config.ts`
- [x] T012 Fix layout height chain: update `frontend/components/SidebarLayout.tsx` `<main>` to `flex flex-col flex-1 min-h-0`, update `frontend/app/chat/page.tsx` to replace `h-dvh` with `flex-1 flex flex-col min-h-0`
- [x] T013 Fix ChatPanel and ChatInput flex layout: update `frontend/components/ChatPanel.tsx` to `flex-1 overflow-y-auto min-h-0`, update `frontend/components/ChatInput.tsx` to `shrink-0 border-t`
- [x] T014 Verify all 5 pages render correctly: run `pnpm run build` and `pnpm run test` (>= 53 tests), check all pages in browser for styled components and zero console errors

### Gate 1 Checklist
- `pnpm run build` succeeds
- SC-001: Sidebar styled ✓
- SC-002: Chat layout correct ✓
- SC-003: Breadcrumbs styled ✓
- SC-004: Command palette works ✓
- SC-012: No console errors ✓
- SC-014: No custom `var(--color-*)` tokens ✓
- Makefile unchanged ✓

---

## Phase 3: US-4 — Configuring Collections and Models

**Goal**: Replace the 256px ChatSidebar with a compact, collapsible configuration panel. Create the toolbar + config panel components and restructure the chat page.

**Story**: US-4 — Configuring Collections and Models

**Dependencies**: Phase 2 (Foundational) must be complete.

**Independent Test Criteria**:
- Toolbar shows active collection badges and model pill
- Gear icon expands/collapses config panel smoothly
- Collections and models can be selected in the panel
- URL param `?collections=<id>` pre-selects collections

### Tasks

- [X] T015 [US4] Create `frontend/components/ChatToolbar.tsx` — 40px slim bar with collection Badge chips, model Badge pill, gear icon button, "New Chat" button per contract in `contracts/ui-components.md`. Wrap in `React.memo`.
- [X] T016 [US4] Create `frontend/components/ChatConfigPanel.tsx` — shadcn `Collapsible` component wrapping collection checkboxes (multi-select) and model dropdowns (LLM + embed). Migrate selection logic from existing `ChatSidebar.tsx`. Auto-apply on change (no "Apply" button).
- [X] T017 [US4] Refactor `frontend/app/chat/page.tsx` — remove ChatSidebar import/usage, add ChatToolbar + ChatConfigPanel above message area. Wire `isConfigOpen` state, collection/model selection state. Read URL param `?collections=<id>` via `useSearchParams()` inside `<Suspense>` boundary.
- [X] T018 [US4] Delete `frontend/components/ChatSidebar.tsx` — verify zero remaining imports with `grep -r "ChatSidebar" frontend/`
- [X] T019 [US4] Verify config panel: toolbar displays collection/model summary, panel expands/collapses, collections selectable, `?collections=` URL param pre-selects. Run `pnpm run build`.

### Gate 2 Checklist
- Config panel collapses/expands smoothly
- ChatSidebar deleted with no orphan imports
- URL param `?collections=<id>` pre-selects
- `pnpm run build` passes
- `pnpm run test` passes

---

## Phase 4: US-2 — Chatting with Rich Responses

**Goal**: Implement markdown rendering, citation hover cards, pipeline stage indicator, streaming UX improvements, and confidence meter.

**Story**: US-2 — Chatting with Rich Responses

**Dependencies**: Phase 3 (US-4) must be complete (chat page restructured).

**Independent Test Criteria**:
- Markdown headings + code blocks render styled (SC-005)
- Citation badges show with hover cards (SC-006)
- Pipeline stage indicator shows labels during streaming (SC-007)
- Stop button halts streaming
- Confidence meter shows after completion
- Auto-resize textarea

### Tasks

- [x] T020 [P] [US2] Create `frontend/lib/stage-labels.ts` — export `stageLabels` map and `getStageLabel()` function mapping pipeline node names to human-readable labels per contract
- [x] T021 [P] [US2] Create `frontend/lib/markdown-components.tsx` — define custom component map at MODULE level (not inside render function). Map h1-h4, code (inline + block with copy button), pre, a, ul, ol, table, blockquote, img. Destructure `node` from all props before spreading. Import `highlight.js/styles/github-dark.css`
- [x] T022 [US2] Create `frontend/components/MarkdownRenderer.tsx` — dynamic import via `next/dynamic` with `ssr: false`. Integrate `react-markdown` + `remark-gfm` + `rehype-highlight`. Import `markdownComponents` from module-level map. Handle streaming: detect incomplete code fences, show skeleton for incomplete blocks. No raw HTML (default behavior = XSS safe).
- [x] T023 [US2] Create `frontend/components/ChatMessageBubble.tsx` — wrap in `React.memo`. User messages: right-aligned `bg-primary`. Assistant messages: left-aligned `bg-muted` with `MarkdownRenderer`. Add `content-visibility: auto; contain-intrinsic-size: 0 80px;` CSS class for virtualization. Show blinking cursor during streaming.
- [x] T024 [P] [US2] Create `frontend/components/CitationHoverCard.tsx` — shadcn `HoverCard` with `openDelay={200}`. Trigger: rounded pill `[N]` with `bg-primary/10`. Content: document name, collection name, passage excerpt (`line-clamp-3`), relevance score color bar. Click navigates to `/documents/:collectionId`.
- [x] T025 [P] [US2] Create `frontend/components/PipelineStageIndicator.tsx` — animated pill with spinner icon showing current stage label from `getStageLabel()`. Smooth text transition between stages. Hidden when not streaming.
- [x] T026 [P] [US2] Create `frontend/components/ScrollToBottom.tsx` — floating button with ArrowDown icon. Shows when scrolled up > 100px from bottom during streaming. Smooth scroll on click. Passive scroll listener (`{ passive: true }`).
- [x] T027 [US2] Integrate citations into `frontend/components/ChatMessageBubble.tsx` — parse message text for `[N]` patterns with regex `/\[(\d+)\]/g`, render as `CitationHoverCard`. Add collapsible "N sources" section below assistant messages. Display confidence meter (colored arc: green >= 70, yellow 40-69, red < 40). Show groundedness data when available.
- [x] T028 [US2] Refactor `frontend/components/ChatPanel.tsx` — replace inline message rendering with `ChatMessageBubble` component. Pass streaming state, current stage, citations to each bubble. Add `PipelineStageIndicator` below streaming message. Add `ScrollToBottom` with ref to scroll container.
- [x] T029 [US2] Update `frontend/components/ChatInput.tsx` — add stop button: swap Send/Stop during streaming, wire to `abort()` from `useStreamChat`. Add `min-h-10 max-h-[120px]` constraints for auto-resize (CSS `field-sizing-content` handles the rest). Reset height after send.
- [x] T030 [US2] Delete `frontend/components/CitationTooltip.tsx` — verify zero remaining imports with `grep -r "CitationTooltip" frontend/`
- [x] T031 [US2] Verify rich chat: send test message with `## Heading` + ` ```python ``` `, verify styled rendering. Test citation hover cards. Test stage indicator during streaming. Test stop button. Run `pnpm run build`.

### Gate 3 Checklist
- SC-005: Markdown renders as styled HTML ✓
- SC-006: Citation hover cards work ✓
- SC-007: Pipeline stage labels show ✓
- Stop button halts streaming ✓
- Auto-resize textarea works ✓
- CitationTooltip deleted, no orphans ✓
- `pnpm run build` passes
- `pnpm run test` passes

---

## Phase 5: US-3 — Browsing Conversation History

**Goal**: Add chat session history to the sidebar, enable collection-to-chat navigation, and show collection names on documents page.

**Story**: US-3 — Browsing Conversation History (+ FR-012 collection-to-chat, FR-013 document breadcrumb)

**Dependencies**: Phase 4 (US-2) must be complete (chat page fully refactored).

**Independent Test Criteria**:
- Sidebar shows past sessions grouped by date (SC-009)
- Clicking a session loads its messages
- "New Chat" clears conversation
- Collection cards have "Chat" action (SC-010)
- Documents page shows collection name (SC-011)

### Tasks

- [x] T032 [US3] Create `frontend/hooks/useChatHistory.ts` — multi-session localStorage management. Storage key `embedinator-sessions:v1`. Max 50 sessions, LRU eviction. Read in `useEffect` (hydration safe). All access in try-catch. Migration from old `embedinator-chat-session` key. Search by title. Per contract in `contracts/ui-components.md`.
- [x] T033 [US3] Create `frontend/components/ChatHistory.tsx` — session list grouped by date (Today, Yesterday, Previous 7 Days, Older). Entry: title (truncated), relative timestamp, message count badge. Actions: rename (inline edit), delete (Dialog confirmation). Search input at top. Active session highlighted. Rendered as `SidebarGroup`.
- [x] T034 [US3] Update `frontend/components/SidebarNav.tsx` — add "New Chat" button in sidebar header. Add `ChatHistory` component above navigation links. Connect to `useChatHistory` hook.
- [x] T035 [US3] Wire chat page to session URL param in `frontend/app/chat/page.tsx` — read `?session=<id>` to load a specific session. Sidebar session click navigates to `/chat?session=<id>`. "New Chat" generates new session ID, navigates to `/chat`. **Builds on T017** (chat/page.tsx restructured with ChatToolbar + ChatConfigPanel + `useSearchParams` in Phase 3).
- [x] T036 [P] [US3] Add "Chat" action to `frontend/components/CollectionCard.tsx` — add item to dropdown menu that navigates to `/chat?collections=<collectionId>`
- [x] T037 [P] [US3] Update `frontend/app/documents/[id]/page.tsx` — fetch collection details via API, display collection name as page title (not UUID). Update breadcrumb: Collections > Collection Name > Documents. Add "Chat with this collection" button in header.

### Gate 4 Checklist
- SC-009: Sessions grouped by date, clickable ✓
- SC-010: Collection cards have "Chat" action ✓
- SC-011: Documents page shows collection name + breadcrumb ✓
- "New Chat" works ✓
- Session persistence across refreshes ✓
- `pnpm run build` passes
- `pnpm run test` passes

---

## Phase 6: US-5 — Uploading Documents with Progress

**Goal**: Enhance the document upload experience with file details, multi-file queue, and improved progress display.

**Story**: US-5 — Uploading Documents with Progress

**Dependencies**: Phase 2 (Foundational) must be complete. Can run parallel with Phase 5.

**Independent Test Criteria**:
- File type icons display by extension (SC-008 partial)
- Multi-file upload with queue
- Progress bar updates every 2s (SC-008)
- Success: auto-refresh + toast; Failure: error + retry

### Tasks

- [x] T038 [US5] Create `frontend/components/IngestionProgress.tsx` — visual wrapper around existing polling logic. Props: collectionId, jobId, onComplete, onRetry. shadcn `Progress` with render function for percentage. Status labels: Pending, Processing, Embedding, Complete, Failed. On complete: call `onComplete`, success toast via Sonner. On failed: inline error + retry button.
- [x] T039 [US5] Enhance `frontend/components/DocumentUploader.tsx` — add file type icons (lucide: FileText for MD/TXT/RST, FileType for PDF) and file size display. Support multi-file: queue files, upload sequentially, show individual `IngestionProgress` per file. Keep existing `react-dropzone` integration.
- [x] T040 [US5] Verify ingestion: upload a test file, confirm progress bar updates every 2s, status labels transition, completion refreshes list with toast, failure shows retry. Run `pnpm run build`.

### Gate 5 Checklist
- SC-008: Progress bar updates every 2s until terminal ✓
- Multi-file queue visible ✓
- File type icons + size shown ✓
- `pnpm run build` passes

---

## Phase 7: US-6 — Onboarding and Empty States

**Goal**: Context-aware empty states that guide user actions on chat and collections pages.

**Story**: US-6 — Onboarding and Empty States

**Dependencies**: Phase 3 (US-4) must be complete (config panel exists). Can run parallel with Phase 5/6.

**Independent Test Criteria**:
- Chat with no collections: onboarding flow, input hidden
- Chat with collections but none selected: clickable collection cards
- Chat with selected collection: suggested prompts that send on click
- Collections page: welcoming empty state with CTA

### Tasks

- [x] T041 [US6] Implement 3 chat empty states in `frontend/app/chat/page.tsx` — (1) No collections: onboarding card linking to `/collections`, hide chat input. (2) Collections exist, none selected: show collections as clickable Cards. (3) Collection selected, no messages: show 3-4 suggested prompts as clickable cards that populate and send. Use ternary conditional rendering (Vercel `rendering-conditional-render`). **Builds on T035** (session wiring + URL param handling added to chat/page.tsx in Phase 5).
- [x] T042 [US6] Improve collections empty state in `frontend/app/collections/page.tsx` — centered display with folder icon (lucide `FolderPlus`), "No collections yet" heading, description text, CTA button that opens `CreateCollectionDialog`.
- [x] T043 [US6] Verify empty states: test with 0 collections, with collections but none selected, with selected collection. Verify suggested prompts send on click. Run `pnpm run build`.

### Gate 6 Checklist
- All 3 chat empty states render correctly ✓
- Collections empty state has CTA ✓
- Suggested prompts send on click ✓
- `pnpm run build` passes

---

## Phase 8: Polish & Cross-Cutting (US-7 + QA)

**Goal**: Keyboard shortcuts, error states, loading states, mobile responsiveness, and full quality audit.

**Story**: US-7 — Mobile Experience + cross-cutting polish

**Dependencies**: ALL previous phases must be complete.

**Independent Test Criteria**:
- All 15 SCs pass
- 53+ frontend tests pass (SC-013)
- Mobile: off-canvas sidebar, sticky input, 44px touch targets (SC-015)
- Lighthouse FCP < 1.5s (NFR-001)
- No console errors (SC-012)

### Tasks

- [x] T044 Add keyboard shortcut hints to `frontend/components/CommandPalette.tsx` — add `Kbd` component display for shortcuts in CommandItem entries. Add new commands: "New Chat" (button-only, no keyboard shortcut — `Cmd/Ctrl+N` omitted, conflicts with browser "Open New Window"), `Escape` (close/stop streaming). Shortcuts `Cmd+K` and `Cmd+B` already handled by shadcn.
- [x] T045 Improve error states in `frontend/components/ChatPanel.tsx` and `frontend/components/ChatInput.tsx` — render network/generation errors as system message bubbles (not modals). Add "Retry" button on failed assistant messages. Preserve user input on error (don't clear textarea). Make `StatusBanner.tsx` dismissible once backend online.
- [x] T046 [P] Add loading states across all pages — verify `Skeleton` components render after CSS fix. Add missing skeletons. Create `frontend/app/chat/loading.tsx` as route-level loading skeleton. Add shimmer animation on streaming assistant message placeholder.
- [x] T047 [P] Mobile responsiveness audit — verify sidebar `collapsible="offcanvas"` works at 375px (Sheet-based). Chat config panel: full-width on mobile. Message bubbles: `max-w-full` on mobile. Chat input: sticky at viewport bottom. Citation hover cards: tap-to-expand on touch. All interactive elements: verify >= 44x44px touch targets.
- [x] T048 Test audit — run `pnpm run test` (>= 53 tests). Update any tests broken by component structure changes. Run `pnpm run build`. Check all 5 pages for console errors.
- [x] T049 Accessibility audit — verify all interactive elements have accessible names. Verify focus visible indicators. Verify color contrast >= 4.5:1 (NFR-004). Use MCP `browser-tools:runAccessibilityAudit` if available.
- [x] T050 Performance audit — verify Lighthouse FCP < 1.5s (NFR-001). Verify 60fps during streaming (NFR-002). Verify no new dep > 50KB gzipped (NFR-003). Use MCP `browser-tools:runPerformanceAudit` if available.

### Final Gate Checklist
- All 15 SCs pass ✓
- SC-013: 53+ tests pass ✓
- SC-015: Mobile responsive ✓
- NFR-001: FCP < 1.5s ✓
- NFR-004: WCAG 2.1 AA ✓
- SC-012: No console errors ✓
- Makefile unchanged ✓

---

## Dependency Graph

```
Phase 1 (Setup)
    │
    ▼
Phase 2 (Foundation / US-1) ─── BLOCKS ALL ───
    │
    ▼
Phase 3 (US-4: Config Panel) ─── requires ChatSidebar replacement before chat redesign
    │
    ▼
Phase 4 (US-2: Rich Responses) ─── requires refactored chat page
    │
    ├──────────────────────┬──────────────────────┐
    ▼                      ▼                      ▼
Phase 5 (US-3)        Phase 6 (US-5)        Phase 7 (US-6)
Chat History          Ingestion Progress    Empty States
    │                      │                      │
    └──────────────────────┴──────────────────────┘
                           │
                           ▼
                    Phase 8 (US-7 + Polish)
```

### Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|-----------|-------------------|
| US-1 (Styled Interface) | None | — |
| US-4 (Config Panel) | US-1 | — |
| US-2 (Rich Responses) | US-4 | — |
| US-3 (Chat History) | US-2 | US-5, US-6 |
| US-5 (Ingestion Progress) | US-1 | US-3, US-6 |
| US-6 (Empty States) | US-4 | US-3, US-5 |
| US-7 (Mobile + Polish) | All | — |

---

## Parallel Execution Opportunities

### Within Phase 2 (Foundation)
- T007 (OKLCH conversion) and T008 (dark variant) can run parallel — different sections of globals.css
- T009 (component token migration) and T010 (StatusBanner tokens) can run parallel — different files

### Within Phase 4 (US-2)
- T020 (stage-labels.ts), T021 (markdown-components.tsx), T024 (CitationHoverCard), T025 (PipelineStageIndicator), T026 (ScrollToBottom) — all new files, no dependencies between them

### Across Phases 5-7
- Phase 5 (US-3), Phase 6 (US-5), Phase 7 (US-6) can run in parallel — independent features, different file sets

### Within Phase 8 (Polish)
- T046 (loading states) and T047 (mobile audit) can run parallel — different concerns, minimal file overlap

---

## Implementation Strategy

### MVP Scope (Phase 1-2)
After Phase 1 (Setup) + Phase 2 (Foundation), the existing application renders correctly with styled components. This is the minimum viable increment — every existing feature works visually.

### Incremental Delivery
1. **Increment 1** (Phases 1-2): Styled interface — all existing features work visually
2. **Increment 2** (Phases 3-4): Professional chat — config panel + markdown + citations + streaming UX
3. **Increment 3** (Phases 5-7): Full feature set — history + ingestion + onboarding
4. **Increment 4** (Phase 8): Production-ready — mobile + accessibility + performance

### Agent Team Mapping

| Wave | Agents | Phases | Tasks |
|------|--------|--------|-------|
| Wave 1 | A1 (solo) | 1, 2 | T001-T014 |
| Wave 2 | A2 (US-4) + A3 (US-2) | 3, 4 | T015-T031 |
| Wave 3 | A4 (US-3) + A5 (US-5) + A6 (US-6) | 5, 6, 7 | T032-T043 |
| Wave 4 | A7 (QA) | 8 | T044-T050 |

---

## Task Summary

| Phase | Story | Tasks | Parallel |
|-------|-------|-------|----------|
| Phase 1: Setup | — | T001-T003 (3) | — |
| Phase 2: Foundation | US-1 | T004-T014 (11) | T007+T008, T009+T010 |
| Phase 3: Config | US-4 | T015-T019 (5) | — |
| Phase 4: Rich Responses | US-2 | T020-T031 (12) | T020+T021+T024+T025+T026 |
| Phase 5: Chat History | US-3 | T032-T037 (6) | T036+T037 |
| Phase 6: Ingestion | US-5 | T038-T040 (3) | — |
| Phase 7: Empty States | US-6 | T041-T043 (3) | — |
| Phase 8: Polish + QA | US-7 | T044-T050 (7) | T046+T047 |
| **Total** | | **50** | **14 parallel opportunities** |

---

## Constraints

- **Zero backend changes**: All files in `frontend/` only
- **Makefile SACRED**: Verified unchanged at every gate
- **53 test baseline**: `pnpm run test` passes at every gate
- **3 npm deps**: react-markdown, remark-gfm, rehype-highlight
- **shadcn v4**: `render` prop for Base UI, `asChild` for Radix only
- **XSS safe**: react-markdown default strips HTML (no `rehype-raw`)
