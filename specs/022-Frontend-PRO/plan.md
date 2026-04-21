# Implementation Plan: Frontend PRO (Spec 022)

**Spec**: `specs/022-Frontend-PRO/spec.md` (21 FRs, 5 NFRs, 15 SCs, 7 User Scenarios)
**Research**: `specs/022-Frontend-PRO/research.md` (11 decisions)
**Data Model**: `specs/022-Frontend-PRO/data-model.md` (6 entities)
**Contracts**: `specs/022-Frontend-PRO/contracts/ui-components.md` (12 component APIs)
**Branch**: `022-frontend-pro` (from `021-e2e-debug-verification`)
**Zero backend changes** — frontend-only.

---

## Component Overview

| Category | Count | Details |
|----------|-------|---------|
| New files | 13 | 8 components, 2 hooks, 2 lib modules, 1 loading page |
| Modified files | 14 | globals.css, package.json, 5 pages, 7 components |
| Deleted files | 2 | ChatSidebar.tsx, CitationTooltip.tsx |
| New shadcn installs | 3 | hover-card, collapsible, kbd |
| New npm deps | 3 | react-markdown, remark-gfm, rehype-highlight |

---

## What Already Exists — Verify, Do Not Recreate

These layers are functional and MUST be preserved. Read before modifying.

**Hooks** (all working):
- `useStreamChat.ts` — NDJSON streaming with abort, token accumulation, event callbacks
- `useCollections.ts` — SWR collection fetching with revalidation
- `useModels.ts` — LLM + embed model fetching
- `useTraces.ts` — Paginated trace fetching
- `useMetrics.ts` — Computed stats from traces
- `useChatStorage.ts` — Single-session localStorage (will be extended, not replaced)

**Lib** (all working):
- `api.ts` — 18 API functions including `streamChat()` with NDJSON parsing
- `types.ts` — All TypeScript interfaces matching backend schemas
- `utils.ts` — `cn()` helper for class merging

**Working components** (need CSS fix only, not rewrite):
- `BackendStatusProvider.tsx` — Polls `/api/health`, adaptive intervals
- `CommandPalette.tsx` — `Cmd+K` handler + `CommandDialog` (code correct, CSS broken)
- `CollectionCard.tsx` — Delete confirmation, shadcn v4 `render` prop pattern
- `ThemeToggle.tsx` — Theme switching via next-themes
- `PageBreadcrumb.tsx` — Dynamic breadcrumb from pathname

**Config** (keep as-is):
- `next.config.ts` — Rewrites `/api/*` to backend, standalone output, `optimizePackageImports`
- `lib/types.ts` — All types match backend schemas

---

## Implementation Phases

### Phase 1: CSS Foundation (FR-001, FR-002, FR-003, FR-004)

**Goal**: Fix Tailwind scanning, standardize tokens, fix layout height. After this phase, ALL existing components render with proper styling.

**SC Coverage**: SC-001, SC-002, SC-003, SC-004, SC-012, SC-014

#### Tasks

**T001: Install new shadcn components and npm deps**
- File: `package.json`
- Run: `pnpm add react-markdown remark-gfm rehype-highlight`
- Run: `pnpm dlx shadcn@latest add hover-card collapsible kbd`
- Verify: `ls components/ui/hover-card.tsx components/ui/collapsible.tsx components/ui/kbd.tsx`

**T002: Fix Tailwind v4 CSS scanning**
- File: `globals.css`
- Add `@source` directives to tell Tailwind where to find utility classes:
  ```css
  @source "../components/**/*.tsx";
  @source "../app/**/*.tsx";
  ```
- Position: After `@import "tailwindcss"` line
- Verify: `pnpm run build`, then grep compiled CSS for `bg-sidebar`, `text-sidebar-foreground`, `data-\[state=open\]`, `group-data-\[collapsible=icon\]`
- If scanning still fails: create minimal `tailwind.config.ts` with `content` paths as fallback

**T003: Standardize CSS token system**
- File: `globals.css`
- Remove ALL custom `--color-*` token declarations from `:root` and `.dark`
- Keep only shadcn standard tokens + `--warning` and `--success` custom tokens
- Convert Obsidian Violet hex values to OKLCH format
- Add `@custom-variant dark (&:where(.dark, .dark *));` if not already present
- Ensure `@theme inline` block maps all CSS vars to Tailwind color system

**T004: Migrate component files from custom to standard tokens**
- Files: ALL component files referencing `var(--color-*)`
- Search: `grep -r "var(--color-" frontend/components/ frontend/app/`
- Replace each occurrence per the migration map (research.md Decision 2)
- Verify: `grep -r "var(--color-" frontend/` returns zero matches (excluding `--color-warning` and `--color-success`)

**T005: Clean up Radix/Base UI dependency conflict**
- File: `package.json`
- Grep all `components/ui/*.tsx` for `@radix-ui` imports
- Remove `@radix-ui/react-*` packages with ZERO imports
- For packages still imported: leave them OR regenerate the component with `pnpm dlx shadcn@latest add <component> --overwrite`
- Update `next.config.ts` `optimizePackageImports`: remove Radix entries no longer needed

**T006: Fix layout height chain**
- File: `components/SidebarLayout.tsx` — change `<main>` to `flex flex-col flex-1 min-h-0`
- File: `app/chat/page.tsx` — replace `h-dvh` with `flex-1 flex flex-col min-h-0`
- File: `components/ChatPanel.tsx` — add `flex-1 overflow-y-auto min-h-0`
- File: `components/ChatInput.tsx` — add `shrink-0 border-t` (sticky at bottom via flex)

**T007: Fix StatusBanner token references**
- File: `components/StatusBanner.tsx`
- Replace any `var(--color-*)` references with shadcn token equivalents

**T008: Verify all pages render correctly**
- Visit all 5 pages in browser (dev server)
- Verify: sidebar styled, breadcrumbs styled, command palette works, no console errors
- Build: `pnpm run build` passes
- Tests: `pnpm run test` passes (>= 53)

#### Gate 1 Checklist
- [ ] `pnpm run build` succeeds
- [ ] Sidebar renders with styled background, not unstyled `<ul>` (SC-001)
- [ ] Breadcrumbs render as styled inline text, not `<ol>` list (SC-003)
- [ ] `Cmd+K` opens command palette as floating dialog (SC-004)
- [ ] `grep -r "var(--color-" frontend/components/ frontend/app/` returns only warning/success (SC-014)
- [ ] Chat page fills viewport — input at bottom, messages scroll (SC-002)
- [ ] No JavaScript console errors on all 5 pages (SC-012)
- [ ] Makefile unchanged

---

### Phase 2a: Chat Core — Markdown + Config (FR-005, FR-006, FR-009)

**Goal**: Rich markdown rendering, collapsible config panel, streaming UX improvements.

**SC Coverage**: SC-005 (partial)

#### Tasks

**T009: Create lib/markdown-components.tsx**
- New file: `lib/markdown-components.tsx`
- Define custom component map at MODULE level (Vercel `rerender-no-inline-components`)
- Components: h1-h4, code (inline + block), pre (with copy button), a, ul, ol, table, blockquote, img
- Destructure `node` from all component props before spreading
- Import: `highlight.js/styles/github-dark.css` for syntax highlighting theme

**T010: Create MarkdownRenderer.tsx**
- New file: `components/MarkdownRenderer.tsx`
- Dynamic import via `next/dynamic` with `ssr: false` (Vercel `bundle-dynamic-imports`)
- Integrate `react-markdown` + `remark-gfm` + `rehype-highlight`
- Import `markdownComponents` from module-level map
- Handle streaming: detect incomplete code fences, show skeleton for incomplete blocks
- No raw HTML (react-markdown default behavior — FR-005 XSS requirement)

**T011: Create ChatMessageBubble.tsx**
- New file: `components/ChatMessageBubble.tsx`
- Wrap in `React.memo` (Vercel `rerender-memo`)
- User messages: right-aligned, `bg-primary text-primary-foreground rounded-2xl`
- Assistant messages: left-aligned, `bg-muted rounded-2xl`, uses `MarkdownRenderer`
- Add `content-visibility: auto; contain-intrinsic-size: 0 80px;` CSS (Vercel `rendering-content-visibility`)
- Show blinking cursor during streaming (existing `animate-[blink_530ms]` pattern)

**T012: Create ChatToolbar.tsx**
- New file: `components/ChatToolbar.tsx`
- Props per contract in `contracts/ui-components.md`
- 40px slim bar: collection badges (Badge secondary), model pill (Badge outline), gear icon, "New Chat" button
- Wrap in `React.memo`

**T013: Create ChatConfigPanel.tsx**
- New file: `components/ChatConfigPanel.tsx`
- Uses shadcn `Collapsible` component (newly installed)
- Migrate collection checkbox logic from existing `ChatSidebar.tsx`
- Migrate model dropdown logic from existing `ModelSelector` usage in `ChatSidebar.tsx`
- Auto-apply on change (no "Apply" button)

**T014: Refactor app/chat/page.tsx**
- File: `app/chat/page.tsx`
- Remove `ChatSidebar` import and usage
- Add `ChatToolbar` + `ChatConfigPanel` above message area
- Wire config state: `isConfigOpen`, collection/model state
- Read URL param `?collections=<id>` to pre-select collections (for collection-to-chat nav, FR-012)
- Wire `useSearchParams()` inside `<Suspense>` boundary (Next.js requirement)

**T015: Refactor ChatPanel.tsx for MessageBubble**
- File: `components/ChatPanel.tsx`
- Replace inline message rendering with `ChatMessageBubble` component
- Pass streaming state, current stage, citations to each bubble

**T016: Update ChatInput.tsx — stop button + auto-resize**
- File: `components/ChatInput.tsx`
- Add stop button: replace Send button with Stop during streaming, wire to `abort()` from `useStreamChat`
- Auto-resize: add `min-h-10 max-h-[120px]` constraints (CSS `field-sizing-content` handles the rest)
- Reset height after send

**T017: Delete ChatSidebar.tsx**
- File: `components/ChatSidebar.tsx` — DELETE
- Verify: `grep -r "ChatSidebar" frontend/` returns zero matches after refactoring
- Update any remaining imports

#### Gate 2a Checklist
- [ ] Markdown with `## Heading` + ` ```python ``` ` renders as styled `<h2>` + syntax-highlighted code (SC-005)
- [ ] Config panel collapses/expands smoothly
- [ ] Stop button halts streaming
- [ ] Textarea auto-resizes from 1 to 5 rows
- [ ] `pnpm run build` passes
- [ ] `pnpm run test` passes

---

### Phase 2b: Chat Core — Citations + Streaming UX (FR-007, FR-008, FR-009, FR-010)

**Goal**: Citation hover cards, pipeline stage indicator, scroll-to-bottom, confidence meter.

**SC Coverage**: SC-005 (complete), SC-006, SC-007

#### Tasks

**T018: Create lib/stage-labels.ts**
- New file: `lib/stage-labels.ts`
- Export `stageLabels` map and `getStageLabel()` function
- Map all pipeline node names to human-readable labels

**T019: Create CitationHoverCard.tsx**
- New file: `components/CitationHoverCard.tsx`
- Uses shadcn `HoverCard` (newly installed)
- Props per contract: citation number, citation data, click handler
- Trigger: rounded pill `[N]` with `bg-primary/10 text-primary`
- Content: document name, collection name, excerpt, relevance score bar
- Color-coded relevance: green >= 0.7, yellow >= 0.4, red < 0.4
- On mobile: tap to show (no hover available)

**T020: Create PipelineStageIndicator.tsx**
- New file: `components/PipelineStageIndicator.tsx`
- Props: `stage` (node name from status event), `isVisible`
- Uses `getStageLabel()` to map to human-readable text
- Animated pill with spinner + text, smooth transitions

**T021: Create ScrollToBottom.tsx**
- New file: `components/ScrollToBottom.tsx`
- Shows when scrolled up > 100px from bottom during streaming
- Circular button with ArrowDown icon
- Smooth scroll on click
- Uses `{ passive: true }` on scroll listener (Vercel `client-passive-event-listeners`)

**T022: Integrate citations into ChatMessageBubble**
- File: `components/ChatMessageBubble.tsx`
- Parse message text for `[N]` patterns, render as `CitationHoverCard` inline
- Add collapsible "N sources" section below assistant messages
- Display confidence meter after completion (colored arc/ring + numeric on hover)
- Show groundedness data when available

**T023: Integrate stage indicator + scroll-to-bottom into ChatPanel**
- File: `components/ChatPanel.tsx`
- Add `PipelineStageIndicator` below streaming message
- Add `ScrollToBottom` component with ref to scroll container

**T024: Delete CitationTooltip.tsx**
- File: `components/CitationTooltip.tsx` — DELETE
- Verify: `grep -r "CitationTooltip" frontend/` returns zero matches

#### Gate 2b Checklist
- [ ] Citation badges `[1]` `[2]` appear in responses (SC-006)
- [ ] Hovering badge shows document name + excerpt + relevance score (SC-006)
- [ ] Pipeline stage indicator shows labels during streaming (SC-007)
- [ ] Scroll-to-bottom button appears when scrolled up during streaming
- [ ] Confidence meter shows High/Medium/Low after completion
- [ ] `pnpm run build` passes

---

### Phase 3: Sidebar & Navigation (FR-011, FR-012, FR-013)

**Goal**: Chat history in sidebar, collection-to-chat navigation, documents page breadcrumb.

**SC Coverage**: SC-009, SC-010, SC-011

#### Tasks

**T025: Create hooks/useChatHistory.ts**
- New file: `hooks/useChatHistory.ts`
- API per contract in `contracts/ui-components.md`
- Storage key: `embedinator-sessions:v1`
- All access in try-catch (private browsing)
- Max 50 sessions, LRU eviction
- Read in `useEffect` (hydration safe)
- Migration from old `embedinator-chat-session` key
- Search: filter sessions by title match

**T026: Create ChatHistory.tsx**
- New file: `components/ChatHistory.tsx`
- Groups sessions by: Today, Yesterday, Previous 7 Days, Older
- Entry: title, relative timestamp, message count badge
- Actions: rename (inline edit), delete (with Dialog confirmation)
- Search input at top
- Active session highlighted
- Renders inside SidebarNav as SidebarGroup

**T027: Update SidebarNav.tsx**
- File: `components/SidebarNav.tsx`
- Add "New Chat" button in sidebar header
- Add `ChatHistory` section above navigation links
- Connect to `useChatHistory` hook

**T028: Update CollectionCard.tsx — add "Chat" action**
- File: `components/CollectionCard.tsx`
- Add "Chat" item to the dropdown menu actions
- Navigate to `/chat?collections=<collectionId>` on click

**T029: Update documents page — collection name + breadcrumb**
- File: `app/documents/[id]/page.tsx`
- Fetch collection details via `GET /api/collections`
- Display collection name as page title (not UUID)
- Update breadcrumb: Collections > Collection Name > Documents
- Add "Chat with this collection" button in header

**T030: Wire chat page to URL session parameter**
- File: `app/chat/page.tsx`
- Read `?session=<id>` URL param to load a specific session
- When sidebar session clicked: navigate to `/chat?session=<id>`
- When "New Chat" clicked: clear messages, generate new session ID, navigate to `/chat`

#### Gate 3 Checklist (Phase 3)
- [ ] Sidebar shows past chat sessions grouped by date (SC-009)
- [ ] Clicking a session loads its messages (SC-009)
- [ ] Collection cards have "Chat" action navigating to `/chat?collections=:id` (SC-010)
- [ ] Documents page shows collection name, not UUID (SC-011)
- [ ] Breadcrumb: Collections > Name > Documents (SC-011)
- [ ] `pnpm run build` passes

---

### Phase 4: Ingestion & Upload (FR-014, FR-015)

**Goal**: Real-time ingestion progress with file details and multi-file support.

**SC Coverage**: SC-008

#### Tasks

**T031: Create IngestionProgress.tsx**
- New file: `components/IngestionProgress.tsx`
- Wraps/enhances existing polling logic from `DocumentUploader`
- Props per contract: collectionId, jobId, onComplete, onRetry
- shadcn `Progress` with render function for percentage text
- Status labels: Pending, Processing, Embedding, Complete, Failed
- On complete: calls `onComplete` (parent refreshes doc list), success toast
- On failed: inline error + retry button

**T032: Enhance DocumentUploader.tsx**
- File: `components/DocumentUploader.tsx`
- Add file type icons based on extension (PDF, MD, TXT, RST) using lucide icons
- Show file size in human-readable format
- Support multi-file: queue files, upload sequentially, show individual progress
- Integrate `IngestionProgress` for each queued file
- Keep existing `react-dropzone` integration

#### Gate 4 Checklist
- [ ] After upload, progress bar updates every 2s (SC-008)
- [ ] Status labels transition through stages (SC-008)
- [ ] Completed: document list refreshes, success toast shown
- [ ] Failed: error message with retry button
- [ ] `pnpm run build` passes

---

### Phase 5: Empty States & Onboarding (FR-016, FR-017)

**Goal**: Context-aware empty states that guide user actions.

**SC Coverage**: (tested as part of SC-012 — no errors)

#### Tasks

**T033: Chat page empty states (3 variants)**
- File: `app/chat/page.tsx`
- **No collections**: Onboarding card with step-by-step guide, CTA to `/collections`, hide chat input
- **Collections exist, none selected**: Show available collections as clickable Card components
- **Collection selected, no messages**: Show 3-4 suggested prompts as clickable cards that send on click
- Use ternary conditional rendering (Vercel `rendering-conditional-render`)

**T034: Collections page empty state**
- File: `app/collections/page.tsx`
- Centered display: folder icon, "No collections yet" heading, description text
- CTA button opens `CreateCollectionDialog`
- Improve visual treatment of existing empty state

#### Gate 5 Checklist
- [ ] Chat empty states are context-aware (3 variants work correctly)
- [ ] Collections empty state has welcoming CTA
- [ ] No console errors
- [ ] `pnpm run build` passes

---

### Phase 6: Polish & QA (FR-018, FR-019, FR-020, FR-021)

**Goal**: Keyboard shortcuts, error states, loading states, mobile responsiveness, full QA audit.

**SC Coverage**: SC-012, SC-013, SC-015, NFR-001, NFR-002, NFR-004

#### Tasks

**T035: Keyboard shortcuts**
- File: `components/CommandPalette.tsx` — add new commands (New Chat, etc.)
- `Cmd+K`: already handled by CommandPalette
- `Cmd+B`: already handled by shadcn SidebarProvider
- `Escape`: close dialogs / stop streaming — wire abort controller
- Show shortcut hints in tooltips using `Kbd` component (newly installed)
- Add shortcut display in CommandPalette items via `CommandShortcut`

**T036: Error states improvement**
- File: `components/ChatPanel.tsx` + `components/ChatInput.tsx`
- Network errors: render as system message bubble with warning styling
- Failed messages: "Retry" button on the failed assistant message
- Preserve user input on error (don't clear textarea)
- File: `components/StatusBanner.tsx` — make dismissible once backend online

**T037: Loading states**
- Files: all data-fetching pages
- Verify `Skeleton` components render correctly after CSS fix (Phase 1)
- Add `Skeleton` to any component missing loading state
- Create `app/chat/loading.tsx` — route-level loading skeleton
- Chat streaming: shimmer/pulse animation on assistant message placeholder

**T038: Mobile responsiveness**
- Sidebar: verify `collapsible="offcanvas"` works on small screens (Sheet-based)
- Chat config panel: full-width on mobile
- Message bubbles: `max-w-full` on mobile (remove 80% constraint)
- Chat input: sticky at viewport bottom
- Citation hover cards: tap-to-expand on touch devices
- All interactive elements: verify minimum 44x44px touch targets
- Test at 375px viewport width

**T039: Test audit**
- Run `pnpm run test` — verify >= 53 tests pass
- Update any tests broken by component structure changes
- Run `pnpm run build` — verify no TypeScript errors
- Check all 5 pages for console errors

**T040: Accessibility + Performance audit (MCP-assisted)**
- Use Playwright: screenshot all 5 pages at 375px, 768px, 1280px (30 screenshots)
- Use Browser Tools: `runAccessibilityAudit` on each page (WCAG 2.1 AA)
- Use Browser Tools: `runPerformanceAudit` — verify FCP < 1.5s (NFR-001)
- Use Chrome DevTools: `lighthouse_audit` for comprehensive quality gate
- Verify: all interactive elements have accessible names, focus visible, contrast >= 4.5:1 (NFR-004)

#### Final Gate Checklist
- [ ] All 15 SCs pass
- [ ] All 53+ frontend tests pass (SC-013)
- [ ] `Cmd+K` opens command palette (SC-004)
- [ ] Errors display as inline system messages with retry (FR-019)
- [ ] Skeleton loading on all data-fetching components (FR-020)
- [ ] Mobile: sidebar off-canvas, input sticky, touch targets >= 44px (SC-015)
- [ ] Lighthouse FCP < 1.5s (NFR-001)
- [ ] No console errors on any page (SC-012)
- [ ] Makefile unchanged

---

## Dependency Graph

```
Phase 1 (CSS Foundation)
    │
    ▼
Phase 2a (Markdown + Config) ──parallel──> Phase 2b (Citations + Streaming)
    │                                           │
    └───────────────┬───────────────────────────┘
                    ▼
    Phase 3 (Sidebar + Nav) ──parallel──> Phase 4 (Ingestion) ──parallel──> Phase 5 (Empty States)
                    │                          │                                │
                    └──────────────────────────┴────────────────────────────────┘
                                               │
                                               ▼
                                    Phase 6 (Polish + QA)
```

---

## Agent Team Structure

### 7 Agents, 4 Waves

| Wave | Agents | Phases | Parallel? |
|------|--------|--------|-----------|
| Wave 1 | A1 (solo) | Phase 1 | No — sequential |
| Wave 2 | A2 + A3 | Phase 2a + 2b | Yes — parallel |
| Wave 3 | A4 + A5 + A6 | Phase 3 + 4 + 5 | Yes — parallel |
| Wave 4 | A7 (solo) | Phase 6 | No — sequential |

### Agent Assignments

| Agent | Type | Phase | Tasks | MCP Tools |
|-------|------|-------|-------|-----------|
| A1 | frontend-architect | 1 | T001-T008 | Serena, shadcn-ui, Context7 (TW v4), Chrome DevTools |
| A2 | frontend-architect | 2a | T009-T017 | Serena, shadcn-ui, Context7 (react-markdown) |
| A3 | frontend-architect | 2b | T018-T024 | Serena, shadcn-ui |
| A4 | frontend-architect | 3 | T025-T030 | Serena, shadcn-ui, Context7 (Next.js useSearchParams) |
| A5 | frontend-architect | 4 | T031-T032 | Serena, Context7 (SWR polling) |
| A6 | frontend-architect | 5 | T033-T034 | Serena |
| A7 | quality-engineer | 6 | T035-T040 | Serena, Playwright, Browser Tools, Chrome DevTools |

### Gate Check Protocol

Each gate check is performed by the orchestrator between waves:
1. `pnpm run build` — must pass
2. `pnpm run test` — must pass (>= 53)
3. `diff Makefile` — must be unchanged
4. `grep -r "var(--color-" frontend/components/ frontend/app/` — must return only warning/success (after Phase 1)
5. Visual verification per phase-specific checklist
6. No JavaScript console errors on all 5 pages

---

## Success Criteria Mapping

| SC | Phase | Verification Task |
|----|-------|-------------------|
| SC-001 | 1 | T008 — sidebar renders styled |
| SC-002 | 1 | T006, T008 — layout fills viewport |
| SC-003 | 1 | T008 — breadcrumbs styled |
| SC-004 | 1 | T008 — command palette works |
| SC-005 | 2a | T010, T011 — markdown renders |
| SC-006 | 2b | T019, T022 — citations with hover cards |
| SC-007 | 2b | T020, T023 — pipeline stage indicator |
| SC-008 | 4 | T031, T032 — ingestion progress |
| SC-009 | 3 | T025, T026, T027 — chat history |
| SC-010 | 3 | T028 — collection-to-chat |
| SC-011 | 3 | T029 — document page collection name |
| SC-012 | 6 | T039 — no console errors |
| SC-013 | 6 | T039 — 53+ tests pass |
| SC-014 | 1 | T003, T004 — token standardization |
| SC-015 | 6 | T038 — mobile responsiveness |

---

## Risk Register

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | Tailwind `@source` position matters | HIGH — silent failure | Add `@source`, build, verify 4 marker classes BEFORE any other work |
| 2 | HoverCard may use `asChild` not `render` | MEDIUM | Use `mcp__shadcn-ui__get_component_details("hover-card")` to verify |
| 3 | react-markdown re-parses on every token | HIGH — layout thrashing | Debounce: accumulate in ref, render at 100ms intervals via rAF |
| 4 | localStorage 5-10MB with 50 sessions | MEDIUM | Store minimal fields, drop citation full-text, add size check |
| 5 | `useChatStorage` refactor breaks consumers | HIGH | A2 refactors internals, A4 adds NEW `useChatHistory` hook separately |
| 6 | Removing Radix deps breaks UI components | HIGH | Grep `components/ui/` for imports BEFORE removing any package |
| 7 | CommandPalette already exists | LOW | Gate 1 verifies it works. Don't recreate. |
| 8 | Makefile SACRED | CRITICAL | `diff` check at every gate |

---

## Vercel Best Practices Enforcement

### Per-Phase Rules

| Phase | Rules to Apply |
|-------|---------------|
| 1 | `bundle-barrel-imports` (import shadcn directly), `client-localstorage-schema` (version keys) |
| 2a | `bundle-dynamic-imports` (MarkdownRenderer), `rerender-no-inline-components` (markdown-components at module level), `rerender-memo` (ChatMessageBubble), `rendering-content-visibility` (message items) |
| 2b | `rerender-memo` (CitationHoverCard, PipelineStageIndicator), `client-passive-event-listeners` (scroll listener), `rendering-conditional-render` (ternary for citations) |
| 3 | `rendering-hydration-no-flicker` (localStorage reads in useEffect), `client-localstorage-schema` (versioned session store), `async-suspense-boundaries` (useSearchParams in Suspense) |
| 4 | `rerender-derived-state-no-effect` (derive isTerminal from job status) |
| 5 | `rendering-conditional-render` (ternary for empty states), `async-suspense-boundaries` |
| 6 | Full audit of all rules across all modified files |

---

## Constraints

- **Zero backend changes**: No files outside `frontend/` modified
- **Makefile SACRED**: `diff` at every gate
- **53 tests baseline**: `pnpm run test` passes at every gate
- **3 new deps only**: react-markdown, remark-gfm, rehype-highlight
- **shadcn v4**: `render` prop for Base UI, `asChild` for Radix only
- **Tailwind v4**: `@source` + `@theme inline`, no `@apply` in component files
- **XSS safe**: react-markdown default (no `rehype-raw`)
