# Tasks: UX/UI Redesign — "Intelligent Warmth"

**Input**: Design documents from `/specs/018-ux-redesign/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/ui-components.md

**Tests**: No new test files are created per spec (existing tests updated only if they break). Test tasks are limited to build verification and existing test suite passes.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend app**: `frontend/app/`
- **Components**: `frontend/components/`
- **shadcn primitives**: `frontend/components/ui/`
- **Hooks**: `frontend/hooks/`
- **Lib**: `frontend/lib/`
- **Config**: `frontend/` root (package.json, component.json, next.config.ts)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install shadcn/ui, next-themes, lucide-react, and supporting utilities. Creates the component foundation.

- [X] T001 Install npm dependencies: `next-themes`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge` in `frontend/package.json`
- [X] T002 Run `npx shadcn@latest init` to create `frontend/component.json` and `frontend/lib/utils.ts` (cn() helper)
- [X] T003 Install 21 shadcn components via `npx shadcn@latest add sidebar sheet command badge skeleton card button input textarea select tabs table dialog popover tooltip scroll-area progress separator dropdown-menu sonner breadcrumb` in `frontend/components/ui/`
- [X] T004 Update `frontend/next.config.ts` — add `lucide-react` and `class-variance-authority` to `optimizePackageImports` array
- [X] T005 Verify: run `npm run build` in frontend/ — must succeed with zero errors

**Checkpoint**: shadcn/ui foundation ready. `frontend/components/ui/` has 21+ files. `cn()` available from `@/lib/utils`.

---

## Phase 2: Foundational (Design Tokens + Theme + Sidebar) [US1 Core]

**Purpose**: Design token system, dark/light theme toggle, and sidebar layout — the foundation ALL page redesigns depend on.

**⚠️ CRITICAL**: No page redesign (Phases 3–8) can begin until this phase is complete.

**FRs**: FR-001, FR-002, FR-003, FR-006, FR-007, FR-008, FR-009, FR-010, FR-011

### Design Tokens (FR-006, FR-007, FR-008)

- [X] T006 [US1] Rewrite `frontend/app/globals.css` — replace existing `@theme` block and `:root`/dark media query with full Obsidian Violet token system: 9 color tokens (`--color-background`, `--color-surface`, `--color-border`, `--color-accent`, `--color-text-primary`, `--color-text-muted`, `--color-success`, `--color-warning`, `--color-destructive`), typography tokens (`--font-size-h1` through `--font-size-label`), spacing tokens (`--space-page`, `--space-card-gap`, `--space-section`). Map `:root` to light mode values, `.dark` class to dark mode values per FR-006. Remove old `@media (prefers-color-scheme: dark)` block.
- [X] T007 [US1] Add shadcn Sidebar CSS vars to `frontend/app/globals.css` — `--sidebar-background`, `--sidebar-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring` in both `:root` and `.dark` selectors. Values must match Obsidian Violet surface/accent tokens (see data-model.md).

### Theme System (FR-009, FR-010, FR-011)

- [X] T008 [US1] Create `frontend/components/ThemeToggle.tsx` — client component using `useTheme()` from next-themes and Sun/Moon icons from lucide-react. Displays Sun in dark mode, Moon in light mode. Clicking toggles between themes.
- [X] T009 [US1] Modify `frontend/app/layout.tsx` — add `suppressHydrationWarning` to `<html>`, import and wrap content with `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>` inside `<body>`. ThemeProvider must be the outermost wrapper (before SidebarProvider).

### Sidebar Layout (FR-001, FR-002, FR-003)

- [X] T010 [US1] Create `frontend/components/SidebarNav.tsx` — shadcn Sidebar compound component with: `SidebarHeader` (app name "The Embedinator"), `SidebarContent > SidebarGroup > SidebarMenu` (5 nav links: MessageSquare→/chat, FolderOpen→/collections, FileText→/documents, Settings→/settings, Activity→/observability), `SidebarFooter` (ThemeToggle + health status dot), `SidebarRail`. Use `collapsible="icon"` prop. Active link via `usePathname()` + `isActive` on `SidebarMenuButton`.
- [X] T011 [US1] Modify `frontend/app/layout.tsx` — remove `import Navigation` and `<Navigation />`, remove `<main className="pt-16">`. Add `SidebarProvider` (inside ThemeProvider): `<SidebarProvider defaultOpen={true}><SidebarNav /><SidebarInset><main>{children}</main></SidebarInset></SidebarProvider>`.
- [X] T012 [US1] Add localStorage persistence for sidebar state in `frontend/app/layout.tsx` or `frontend/components/SidebarNav.tsx` — read initial `open` from `localStorage.getItem("sidebar-open")`, write on change via SidebarProvider's `onOpenChange` prop (FR-002).
- [X] T013 [US1] Fix chat page height in `frontend/app/chat/page.tsx` — change `h-[calc(100vh-4rem)]` to `h-dvh` (no top-nav offset needed after sidebar layout).
- [X] T014 [US1] Delete `frontend/components/Navigation.tsx` — fully replaced by SidebarNav.
- [X] T015 [US1] Verify: run `npm run build`, load all 5 routes (/chat, /collections, /documents, /settings, /observability) — sidebar renders, collapse toggle works, mobile hamburger opens Sheet overlay, dark/light toggle works. No console errors.

**Checkpoint**: Foundation ready — sidebar layout, design tokens, and theme system all working. Page redesigns can now begin in parallel.

---

## Phase 3: User Story 2 — Intelligent Chat Experience (Priority: P2) 🎯

**Goal**: Redesign the chat page to surface AI intelligence: streaming cursor, citation chips, confidence badge, meta-reasoning indicator, empty state, chat persistence.

**Independent Test**: Send a query, watch tokens stream with blinking cursor, click a citation chip, expand confidence breakdown, refresh page and see conversation restored.

**FRs**: FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019

### Implementation

- [X] T016 [US2] Create `frontend/hooks/useChatStorage.ts` — localStorage read/write for `StoredChat` shape (`{ sessionId, messages, updatedAt }`). Key: `embedinator-chat-session`. Methods: `saveMessages(msgs, sessionId)`, `clearChat()`. Auto-evict previous session when new sessionId differs. Last-write-wins multi-tab (FR-019).
- [X] T017 [US2] Redesign message bubbles in `frontend/components/ChatPanel.tsx` — user messages right-aligned with accent bg, assistant messages left-aligned with surface bg. Use shadcn ScrollArea for message container. Replace all hard-coded neutral/gray classes with design tokens. Remove all `dark:` variant classes. IMPORTANT: Preserve existing `onGroundedness` rendering — do not remove groundedness data display during restyle.
- [X] T018 [US2] Add blinking caret cursor in `frontend/components/ChatPanel.tsx` — CSS `@keyframes blink` animation on streaming `<span>` element. Add stage-status Badge showing current pipeline node from `onStatus` callback (FR-013).
- [X] T019 [US2] Migrate `frontend/components/CitationTooltip.tsx` — replace Radix Tooltip with shadcn Badge chips + Popover expansion showing full citation text, source document name, and relevance score. Migrate color classes to design tokens (FR-014).
- [X] T020 [US2] Migrate `frontend/components/ConfidenceIndicator.tsx` — replace Radix Tooltip with colored Badge (green>=70, yellow 40-69, red<40) + expandable Popover showing 5-signal confidence breakdown. Migrate color classes to design tokens (FR-015).
- [X] T021 [US2] Add meta-reasoning indicator in `frontend/components/ChatPanel.tsx` — small Badge when `onMetaReasoning` fires, showing strategies attempted list (FR-016).
- [X] T022 [US2] Add clarification card in `frontend/components/ChatPanel.tsx` — styled shadcn Card appearing in message stream when `onClarification` fires, with question text and response CTA (FR-017).
- [X] T023 [US2] Add copy-to-clipboard button in `frontend/components/ChatPanel.tsx` — appears on hover over assistant messages, copies text to clipboard (FR-018).
- [X] T024 [US2] Create chat empty state in `frontend/components/ChatPanel.tsx` — centered greeting with 3-4 clickable suggested starter questions when no messages exist (FR-012).
- [X] T025 [US2] Integrate useChatStorage with `frontend/app/chat/page.tsx` — load stored messages on mount, save on update, clear via "New Chat" action. Connect to existing useStreamChat hook (FR-019).
- [X] T026 [P] [US2] Restyle `frontend/components/ChatSidebar.tsx` and `frontend/components/ModelSelector.tsx` — replace raw Radix Select with shadcn Select for model/collection pickers. ModelSelector is shared by ChatSidebar and Settings page — restyle it here as the shared component. Migrate all neutral/gray color classes to design tokens.
- [X] T027 [P] [US2] Restyle `frontend/components/ChatInput.tsx` — use shadcn Textarea + Button. Migrate all neutral/gray color classes to design tokens.

**Checkpoint**: Chat page fully functional — streaming with cursor, citation chips, confidence badge, meta-reasoning, copy button, empty state, localStorage persistence. Verify in both dark and light mode.

---

## Phase 4: User Story 3 — Collection Management (Priority: P3)

**Goal**: Card grid layout with search, skeletons, empty state, and polished create dialog.

**Independent Test**: View collections grid (responsive), search/filter, create a new collection, use card quick actions.

**FRs**: FR-020, FR-021, FR-022, FR-023, FR-024

### Implementation

- [X] T028 [P] [US3] Restyle `frontend/components/CollectionList.tsx` — responsive grid (1col mobile, 2col md, 3col lg), search/filter input at top. Add Skeleton card placeholders while loading. Add empty state with CTA. Migrate all gray classes to design tokens (FR-020, FR-021, FR-023).
- [X] T029 [P] [US3] Restyle `frontend/components/CollectionCard.tsx` — use shadcn Card + Badge for stats (document count, chunk count, embedding model) + DropdownMenu for actions (View Documents, Delete with confirmation Dialog). Migrate all gray classes to design tokens (FR-020, FR-022).
- [X] T030 [P] [US3] Restyle `frontend/components/CreateCollectionDialog.tsx` — migrate from raw Radix Dialog/Select to shadcn Dialog + Input + Select. Fields: name (required), description (optional), embedding model (selectable), chunk profile (selectable). Migrate all gray classes to design tokens (FR-024).
- [X] T031 [P] [US3] Restyle `frontend/components/CollectionStats.tsx` — migrate all gray classes to design tokens.
- [X] T032 [US3] Restyle `frontend/app/collections/page.tsx` — integrate restyled components, verify responsive grid at all breakpoints in both themes.

**Checkpoint**: Collections page fully functional — card grid, search, skeletons, empty state, create dialog. Verify in both dark and light mode at 375/768/1280px.

---

## Phase 5: User Story 4 — Document Management & Ingestion (Priority: P4)

**Goal**: Two-column layout with drag-and-drop upload, ingestion progress tracking, and status badges.

**Independent Test**: Navigate to a collection's documents, upload a file, watch progress bar, verify two-column desktop and stacked mobile layout.

**FRs**: FR-025, FR-026, FR-027

### Implementation

- [X] T033 [P] [US4] Restyle `frontend/components/DocumentList.tsx` — use shadcn Table + Badge for ingestion status (pending/processing/complete/failed). Migrate all gray classes to design tokens (FR-027).
- [X] T034 [P] [US4] Restyle `frontend/components/DocumentUploader.tsx` — enhance drop zone visual (border color + bg tint on drag-over). Use shadcn Progress for ingestion job tracking. Migrate all gray classes to design tokens (FR-026).
- [X] T035 [US4] Restyle `frontend/app/documents/[id]/page.tsx` — two-column layout on desktop (file list left, chunk preview right with ScrollArea), stacked vertically on mobile (< 768px). Migrate all gray classes to design tokens (FR-025).

**Checkpoint**: Documents page fully functional — two-column/stacked layout, upload with progress, status badges. Verify in both themes at all breakpoints.

---

## Phase 6: User Story 5 — Settings & Provider Configuration (Priority: P5)

**Goal**: Tabbed settings interface with provider cards, API key management, and toast notifications replacing custom Toast component.

**Independent Test**: Navigate to settings, switch tabs, add a provider key, save inference parameters, verify toast notifications.

**FRs**: FR-028, FR-029, FR-030

### Implementation

- [X] T036 [US5] Add Sonner `<Toaster />` component to `frontend/app/layout.tsx` — place as sibling inside ThemeProvider (not inside SidebarProvider). This MUST be done BEFORE deleting Toast.tsx.
- [X] T037 [P] [US5] Restyle `frontend/components/ProviderHub.tsx` — use shadcn Card + Input (with show/hide toggle for API key) + Button. Status dot: green if `has_key`, gray if not. Migrate all gray classes to design tokens (FR-029).
- [X] T038 [US5] Restyle `frontend/app/settings/page.tsx` — restructure with shadcn Tabs ("Providers", "Models", "Inference", "System"). Replace all `Toast` usage with `toast()` from sonner. Migrate all gray classes (~20 instances) to design tokens (FR-028, FR-030).
- [X] T039 [US5] Delete `frontend/components/Toast.tsx` — fully replaced by Sonner.

**Checkpoint**: Settings page fully functional — tabs, provider cards with status dots, API key show/hide, toast notifications. Verify in both themes.

---

## Phase 7: User Story 6 — Observability & Performance Monitoring (Priority: P6)

**Goal**: Polished health dashboard, restyled charts, filterable trace table with slide-out detail panel.

**Independent Test**: View health cards, examine charts, filter trace table, click a trace to see detail panel.

**FRs**: FR-031, FR-032, FR-033, FR-034

### Implementation

- [X] T040 [P] [US6] Restyle `frontend/components/HealthDashboard.tsx` — use shadcn Card per service (SQLite, Qdrant, Ollama) with colored status dot (green/yellow/red/gray) and latency ms. Migrate all gray classes to design tokens (FR-031).
- [X] T041 [P] [US6] Restyle `frontend/components/StageTimingsChart.tsx` — horizontal bar chart with token-based distinct colors per stage (retrieval, rerank, compress, meta-reasoning, inference). Tooltip showing stage name + latency ms. Dark-mode compatible chart colors (FR-032).
- [X] T042 [P] [US6] Restyle `frontend/components/TraceTable.tsx` — use shadcn Table + pagination controls + session ID and confidence range filter inputs. Add trace detail Sheet (slide-out from right) showing query text, stage timings, citations, confidence breakdown, reasoning steps. Migrate ALL ~30+ gray classes to design tokens (FR-033, FR-034). **NOTE**: This is the LARGEST migration — allocate extra review.
- [X] T043 [P] [US6] Restyle `frontend/components/LatencyChart.tsx`, `frontend/components/ConfidenceDistribution.tsx`, `frontend/components/MetricsTrends.tsx` — migrate all gray classes to design tokens, use token-based chart colors for dark/light mode compatibility.
- [X] T044 [US6] Restyle `frontend/app/observability/page.tsx` — migrate ALL hard-coded gray classes (~15 instances, ZERO existing dark: variants). Integrate restyled components. Verify all charts render in both themes.

**Checkpoint**: Observability page fully functional — health dots, chart tooltips, trace table filters, Sheet detail panel. Verify in both dark and light mode. ZERO hard-coded gray classes remaining.

---

## Phase 8: User Story 1 Completion — Command Palette + Breadcrumbs

**Purpose**: Complete remaining US1 deliverables that depend on all pages being redesigned.

**FRs**: FR-004, FR-005

- [X] T045 [US1] Create `frontend/components/CommandPalette.tsx` — shadcn Command in Dialog. Commands: navigate to 5 pages (Chat, Collections, Documents, Settings, Observability), "Create Collection" (opens dialog), "Clear Chat" (calls clearChat from useChatStorage), "Toggle Dark Mode" (calls setTheme). Register global `Cmd+K` / `Ctrl+K` keydown listener via useEffect (FR-004).
- [X] T046 [US1] Create `frontend/components/PageBreadcrumb.tsx` — shadcn Breadcrumb component, derives crumbs from `usePathname()`. Handles: `/chat` → "Chat", `/collections` → "Collections", `/documents/[id]` → "Documents / {id}", `/settings` → "Settings", `/observability` → "Observability" (FR-005).
- [X] T047 [US1] Add CommandPalette to `frontend/app/layout.tsx` — render once globally as sibling inside ThemeProvider (after SidebarProvider).
- [X] T048 [US1] Add PageBreadcrumb to SidebarInset header area in `frontend/app/layout.tsx` or in each page file — displays current navigation context at top of content area.

**Checkpoint**: Cmd+K opens palette, search filters commands, commands execute correctly. Breadcrumbs reflect current route on all pages.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final accessibility, responsive, and consistency audit across all pages.

**FRs**: FR-035, FR-036, FR-037, FR-038, NFR-001, NFR-002, NFR-003, NFR-004

- [X] T049 [P] Add shadcn Tooltip to all icon-only buttons across all pages — sidebar collapse toggle, theme toggle, copy button, card action buttons, filter icons (FR-035)
- [X] T050 [P] Audit and add Skeleton loaders for every async-loaded section: collections grid, documents list, trace table, settings form, health dashboard, chat message loading (FR-038)
- [X] T051 Keyboard navigation audit — Tab through all interactive elements on all 5 pages. Verify all modals (Dialog), slide-out panels (Sheet), and popovers close on Escape (FR-037)
- [X] T052 Responsive audit — verify all 5 pages render correctly at 375px, 768px, and 1280px. No content inaccessible at any breakpoint (FR-036)
- [X] T053 Dark/light mode audit — search all frontend source files for remaining hard-coded `text-gray-*`, `bg-gray-*`, `border-gray-*`, `bg-white` classes. Fix any found. Verify zero remaining (NFR-001)
- [X] T053b [P] WCAG contrast ratio audit — verify all Obsidian Violet token pairs meet 4.5:1 minimum for normal text and 3:1 for large text: text-primary on background, text-muted on surface, accent on background, success/warning/destructive on both background and surface. Use browser DevTools accessibility panel or online contrast checker (NFR-002)
- [X] T054 Run `npm run build` in frontend/ — verify zero TypeScript errors and zero build errors
- [X] T054b Run Lighthouse performance audit on all 5 pages — verify initial meaningful content renders within 2 seconds and skeleton loaders appear within 200ms of page load. Flag any page exceeding thresholds (NFR-004)
- [X] T055 Run `npm run test` in frontend/ — update any Vitest tests that break due to component structure changes (e.g., Navigation → SidebarNav, Toast → Sonner)
- [X] T056 Run `npm run test:e2e` in frontend/ — update Playwright selectors if component markup changed
- [X] T057 Run quickstart.md validation — verify setup steps and token usage examples

**Checkpoint**: All 5 pages pass accessibility, responsive, and dark/light audits. Build succeeds. Tests pass. Zero hard-coded color classes remain.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories
- **US2 Chat (Phase 3)**: Depends on Foundational (Phase 2)
- **US3 Collections (Phase 4)**: Depends on Foundational (Phase 2)
- **US4 Documents (Phase 5)**: Depends on Foundational (Phase 2)
- **US5 Settings (Phase 6)**: Depends on Foundational (Phase 2)
- **US6 Observability (Phase 7)**: Depends on Foundational (Phase 2)
- **US1 Completion (Phase 8)**: Depends on Phases 3–7 (command palette references all page features)
- **Polish (Phase 9)**: Depends on Phase 8

### User Story Dependencies

- **US1 (P1)**: Core delivered in Phase 2 (Foundational). Completed in Phase 8 (Command Palette + Breadcrumbs). Blocks all other stories.
- **US2 (P2)**: Can start after Phase 2. No dependency on US3–US6.
- **US3 (P3)**: Can start after Phase 2. No dependency on US2 or US4–US6.
- **US4 (P4)**: Can start after Phase 2. No dependency on US2–US3 or US5–US6.
- **US5 (P5)**: Can start after Phase 2. No dependency on US2–US4 or US6. **Note**: T036 (Sonner Toaster) modifies layout.tsx — must coordinate if running in parallel with other layout.tsx changes.
- **US6 (P6)**: Can start after Phase 2. No dependency on US2–US5.

### Within Each User Story

- Token migration (gray→tokens) can be done in any order per file
- Component restyling before page integration
- Layout/structure changes before color migration

### Parallel Opportunities

- All Setup tasks run sequentially (npm install → shadcn init → add components)
- Foundational tasks are sequential (tokens → theme → sidebar)
- **After Phase 2**: Phases 3–7 (US2–US6) can ALL run in parallel (5 independent page redesigns)
- Within each page phase: tasks marked [P] can run in parallel (different files)

---

## Parallel Example: After Phase 2 (Foundational)

```bash
# Launch 5 page redesigns in parallel (Agent Teams):
Agent A3: US2 Chat — T016-T027 (frontend/components/Chat*.tsx, frontend/hooks/useChatStorage.ts)
Agent A4: US3 Collections — T028-T032 (frontend/components/Collection*.tsx, frontend/components/CreateCollectionDialog.tsx)
Agent A5: US4 Documents — T033-T035 (frontend/components/Document*.tsx, frontend/app/documents/)
Agent A6: US5 Settings — T036-T039 (frontend/components/ProviderHub.tsx, frontend/app/settings/, Toast.tsx)
Agent A7: US6 Observability — T040-T044 (frontend/components/Health*.tsx, frontend/components/Trace*.tsx, frontend/components/*Chart.tsx)
```

---

## Implementation Strategy

### MVP First (US1 = Layout + Theme)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T015)
3. **STOP and VALIDATE**: Sidebar renders, theme toggles, tokens work on all pages
4. This is the MVP — the new layout with design system is usable even before page redesigns

### Incremental Delivery

1. Setup + Foundational → Layout + Theme ready (MVP)
2. Add US2 Chat → Test independently → Primary surface polished
3. Add US3 Collections → Test independently → Collection management polished
4. Add US4 Documents → Test independently → Document workflow polished
5. Add US5 Settings → Test independently → Configuration polished
6. Add US6 Observability → Test independently → Monitoring polished
7. Add US1 Completion → Command Palette + Breadcrumbs
8. Polish → Final audit + tests

### Agent Team Strategy (4 Waves)

| Wave | Tasks | Agents | Parallelism |
|------|-------|--------|-------------|
| 1 | T001–T015 | A1 (frontend-architect) | Sequential |
| 2 (GATE) | Verify all 5 routes render, sidebar works, theme works | — | Gate check |
| 3 | T016–T044 | A3–A7 (5x frontend-architect) | 5 agents parallel |
| 4 | T045–T057 | A8 (quality-engineer) | Sequential |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- **CRITICAL**: T036 (Sonner Toaster in layout.tsx) must be done BEFORE T039 (delete Toast.tsx)
- **CRITICAL**: Phase 2 gate check must pass before any Phase 3–7 work begins
- Color migration: use token mapping table from plan.md; verify zero hard-coded gray classes remain per file after migration
