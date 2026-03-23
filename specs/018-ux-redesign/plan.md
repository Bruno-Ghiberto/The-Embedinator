# Implementation Plan: UX/UI Redesign — "Intelligent Warmth"

**Branch**: `018-ux-redesign` | **Date**: 2026-03-19 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/018-ux-redesign/spec.md`

## Summary

Redesign The Embedinator's frontend from a plain top-nav utility app into a polished,
personality-driven, shadcn/ui-based application. The redesign replaces the fixed top
navigation with a collapsible sidebar, introduces the "Obsidian Violet" design token
system, adds manual dark/light mode toggle via next-themes, and restyles all 5 pages
and 21 components to surface AI intelligence (confidence scores, citations, meta-reasoning
status, stage timings) as first-class visual elements.

**Scope**: 38 FRs, 4 NFRs, 8 SCs across 6 User Stories. Frontend-only — no backend changes.

## Technical Context

**Language/Version**: TypeScript 5.7, Node.js LTS
**Primary Dependencies**: Next.js 16, React 19, Tailwind CSS 4, shadcn/ui (new), next-themes (new), lucide-react (new), SWR 2, recharts 2, react-dropzone 14
**Storage**: localStorage (browser-side: chat persistence, sidebar state, theme preference)
**Testing**: vitest 3 (unit), playwright 1.50 (e2e)
**Target Platform**: Web browser (all modern browsers), served via Next.js standalone build
**Project Type**: Web application — frontend-only changes within existing Next.js 16 App Router
**Performance Goals**: < 2s initial meaningful content (NFR-004), < 200ms skeleton display, zero CLS on theme switch (NFR-001)
**Constraints**: No new charting libraries (NFR-003), CSS-only animations, no backend changes, no new routes, no hook rewrites, no lib/types.ts changes
**Scale/Scope**: 5 pages, 21 existing components (restyle), 4 new components, 21 shadcn/ui primitives, ~200+ hard-coded color class migrations across 22 files

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Local-First Privacy | PASS | No new network calls. No authentication. Frontend-only. localStorage stores chat messages, not credentials. |
| II. Three-Layer Agent Architecture | N/A | Frontend spec — does not touch ConversationGraph, ResearchGraph, or MetaReasoningGraph. |
| III. Retrieval Pipeline Integrity | N/A | No changes to chunking, search, or reranking pipeline. |
| IV. Observability from Day One | PASS | /observability page is redesigned with improved health cards, chart restyling, trace detail panel. Confidence score visible in chat UI (FR-015). Trace recording unchanged. |
| V. Secure by Design | PASS | API key input retains show/hide toggle (FR-029). No new endpoints. localStorage stores only chat messages (no credentials). |
| VI. NDJSON Streaming Contract | PASS | Frontend consumes all existing NDJSON event types (session, status, chunk, citation, confidence, meta_reasoning, clarification, groundedness, done, error). Protocol format unchanged. |
| VII. Simplicity by Default | PASS | No new external services (still 4 Docker services). CSS-only animations. shadcn/ui wraps existing Radix primitives. No new charting library. |
| VIII. Cross-Platform Compatibility | N/A | Frontend runs in browser — inherently cross-platform. No platform-specific code. |

**Gate result**: ALL PASS. No violations. No complexity tracking needed.

## Project Structure

### Documentation (this feature)

```text
specs/018-ux-redesign/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── ui-components.md # Component contract definitions
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── layout.tsx              # MODIFIED — SidebarProvider + ThemeProvider + Sonner Toaster
│   ├── globals.css             # MODIFIED — full Obsidian Violet token system
│   ├── chat/page.tsx           # MODIFIED — height calc fix, localStorage integration
│   ├── collections/page.tsx    # MODIFIED — restyled
│   ├── documents/[id]/page.tsx # MODIFIED — two-column layout + token migration
│   ├── settings/page.tsx       # MODIFIED — shadcn Tabs, Sonner, token migration
│   └── observability/page.tsx  # MODIFIED — restyled, token migration
├── components/
│   ├── ui/                     # NEW — shadcn component registry (~21 files)
│   ├── SidebarNav.tsx          # NEW — replaces Navigation.tsx
│   ├── ThemeToggle.tsx         # NEW — dark/light mode toggle
│   ├── CommandPalette.tsx      # NEW — Cmd+K palette
│   ├── PageBreadcrumb.tsx      # NEW — page context breadcrumb
│   ├── Navigation.tsx          # DELETED — replaced by SidebarNav
│   ├── Toast.tsx               # DELETED — replaced by Sonner
│   ├── ChatPanel.tsx           # MODIFIED — message bubbles, citations, confidence
│   ├── ChatInput.tsx           # MODIFIED — shadcn Textarea + Button
│   ├── ChatSidebar.tsx         # MODIFIED — shadcn Select
│   ├── ConfidenceIndicator.tsx # MODIFIED — Badge + Tooltip + Popover
│   ├── CitationTooltip.tsx     # MODIFIED — Badge + Popover
│   ├── CollectionCard.tsx      # MODIFIED — shadcn Card + Badge + DropdownMenu
│   ├── CollectionList.tsx      # MODIFIED — grid layout, search, skeletons
│   ├── CollectionStats.tsx     # MODIFIED — token migration
│   ├── CreateCollectionDialog.tsx # MODIFIED — shadcn Dialog + Input + Select
│   ├── DocumentList.tsx        # MODIFIED — shadcn Table + Badge
│   ├── DocumentUploader.tsx    # MODIFIED — shadcn Progress
│   ├── ProviderHub.tsx         # MODIFIED — shadcn Card + Input + Button
│   ├── HealthDashboard.tsx     # MODIFIED — shadcn Card
│   ├── TraceTable.tsx          # MODIFIED — shadcn Table, Sheet detail panel
│   ├── LatencyChart.tsx        # MODIFIED — token-based colors
│   ├── StageTimingsChart.tsx   # MODIFIED — token-based colors
│   ├── ConfidenceDistribution.tsx # MODIFIED — token-based colors
│   ├── MetricsTrends.tsx       # MODIFIED — token-based colors
│   └── ModelSelector.tsx       # MODIFIED — shadcn Select
├── hooks/
│   ├── useChatStorage.ts       # NEW — localStorage chat persistence
│   ├── useStreamChat.ts        # UNCHANGED
│   ├── useCollections.ts       # UNCHANGED
│   ├── useModels.ts            # UNCHANGED
│   ├── useTraces.ts            # UNCHANGED
│   └── useMetrics.ts           # UNCHANGED
├── lib/
│   ├── api.ts                  # UNCHANGED
│   ├── types.ts                # UNCHANGED
│   └── utils.ts                # NEW — cn() utility from shadcn init
├── component.json              # NEW — shadcn configuration
├── package.json                # MODIFIED — new dependencies
└── next.config.ts              # MODIFIED — optimizePackageImports
```

**Structure Decision**: Frontend-only changes within the existing Next.js 16 App Router
structure. No new routes. No backend modifications. The `components/ui/` directory is
new (shadcn registry). Four new custom components (SidebarNav, ThemeToggle, CommandPalette,
PageBreadcrumb) and one new hook (useChatStorage) are added.

**File count**: 4 new custom files, 1 new hook, ~21 new shadcn/ui files, 22 modified files, 2 deleted files.

## Implementation Phases

### Phase 0 — Foundation Setup

**Goal**: Install shadcn/ui, next-themes, lucide-react, and supporting utilities.
**FRs**: Foundation for all FRs (no specific FR — infrastructure)
**Blocking**: Everything depends on this phase.

**Tasks**:
1. Install new npm dependencies: `next-themes`, `lucide-react`, `class-variance-authority`, `clsx`, `tailwind-merge`
2. Run `npx shadcn@latest init` — creates `component.json` and `lib/utils.ts` (cn() helper)
3. Install 21 shadcn components: sidebar, sheet, command, badge, skeleton, card, button, input, textarea, select, tabs, table, dialog, popover, tooltip, scroll-area, progress, separator, dropdown-menu, sonner, breadcrumb
4. Update `next.config.ts` — add `lucide-react` and `class-variance-authority` to `optimizePackageImports`
5. Verify: `npm run build` succeeds with no errors

**Files**: NEW: `component.json`, `lib/utils.ts`, `components/ui/*.tsx` (~21). MODIFIED: `package.json`, `next.config.ts`

**Verification**: `npm run build` passes; `ls frontend/components/ui/` shows 21+ files

---

### Phase 1 — Design Token System

**Goal**: Rewrite globals.css with the complete Obsidian Violet color palette and design tokens.
**FRs**: FR-006, FR-007, FR-008
**Blocking**: All component restyling depends on tokens being available.

**Tasks**:
1. Rewrite `app/globals.css` with full token system in `@theme` block:
   - Color tokens: `--color-background`, `--color-surface`, `--color-border`, `--color-accent`, `--color-text-primary`, `--color-text-muted`, `--color-success`, `--color-warning`, `--color-destructive`
   - Typography tokens: `--font-size-h1` through `--font-size-label`
   - Spacing tokens: `--space-page`, `--space-card-gap`, `--space-section`
   - **CRITICAL** — shadcn Sidebar CSS vars: `--sidebar-background`, `--sidebar-foreground`, `--sidebar-primary`, `--sidebar-primary-foreground`, `--sidebar-accent`, `--sidebar-accent-foreground`, `--sidebar-border`, `--sidebar-ring`
2. Map `:root` selector to light mode Obsidian Violet values (from FR-006)
3. Map `.dark` selector to dark mode Obsidian Violet values (from FR-006)
4. Remove old `@media (prefers-color-scheme: dark)` block — replaced by class-based switching
5. Verify: inspect both `:root` and `.dark` selectors produce correct hex values

**Files**: MODIFIED: `app/globals.css`

**Verification**: CSS vars resolve to correct hex values in both selectors

---

### Phase 2 — Theme System

**Goal**: Add next-themes ThemeProvider and create ThemeToggle component.
**FRs**: FR-009, FR-010, FR-011
**Blocking**: Dark mode toggle needed before any page can be fully verified.

**Tasks**:
1. Create `components/ThemeToggle.tsx` — Sun/Moon icon button using `useTheme()` from next-themes and lucide-react icons (Sun, Moon)
2. Modify `app/layout.tsx`:
   - Add `suppressHydrationWarning` to `<html>` element
   - Import ThemeProvider from `next-themes`
   - Wrap children: `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>`
   - ThemeProvider goes INSIDE `<body>`, wrapping all content
3. Verify: toggling applies `.dark` class to `<html>`, CSS vars switch correctly
4. Verify: page refresh preserves theme choice, no flash of wrong theme

**Files**: NEW: `components/ThemeToggle.tsx`. MODIFIED: `app/layout.tsx`

**Verification**: Toggle works; refresh preserves; no hydration errors in console

---

### Phase 3 — Sidebar Layout (HIGHEST RISK)

**Goal**: Replace Navigation.tsx with collapsible shadcn Sidebar in layout.tsx.
**FRs**: FR-001, FR-002, FR-003, FR-005
**Blocking**: All page redesigns depend on the new layout structure.

**Tasks**:
1. Create `components/SidebarNav.tsx` using shadcn Sidebar compound components:
   - `SidebarHeader`: app name "The Embedinator"
   - `SidebarContent > SidebarGroup > SidebarMenu`: 5 nav links with lucide icons (MessageSquare→Chat, FolderOpen→Collections, FileText→Documents, Settings→Settings, Activity→Observability)
   - `SidebarFooter`: ThemeToggle component + system health status indicator
   - `SidebarRail` for hover-to-expand affordance
   - `collapsible="icon"` prop for icon-only collapsed state
   - Active link highlighting via `usePathname()` + `isActive` prop on `SidebarMenuButton`
2. Modify `app/layout.tsx`:
   - Remove `import Navigation` and `<Navigation />`
   - Remove `<main className="pt-16">` wrapper (no top-nav offset needed)
   - Add SidebarProvider wrapping content (INSIDE ThemeProvider):
     ```
     <ThemeProvider>
       <SidebarProvider defaultOpen={true}>
         <SidebarNav />
         <SidebarInset>
           <main>{children}</main>
         </SidebarInset>
       </SidebarProvider>
     </ThemeProvider>
     ```
3. Add localStorage persistence for sidebar state (FR-002):
   - Read initial `open` from `localStorage.getItem("sidebar-open")`
   - Use SidebarProvider's controlled `open` + `onOpenChange` props
   - Write to localStorage on change
4. Fix ChatPage height calc in `app/chat/page.tsx`: change `h-[calc(100vh-4rem)]` → `h-dvh`
5. Delete `components/Navigation.tsx`
6. Verify: all 5 page routes render; sidebar expand/collapse works; mobile hamburger overlay works

**Files**: NEW: `components/SidebarNav.tsx`. MODIFIED: `app/layout.tsx`, `app/chat/page.tsx`. DELETED: `components/Navigation.tsx`

**RISK**: Root layout change — if broken, ALL pages fail. Test immediately.

**Verification**: All 5 routes render; sidebar toggles; mobile overlay works; `npm run build` passes

---

### Phase 4 — Chat Page Redesign (Most Complex)

**Goal**: Redesign the chat experience to surface AI intelligence.
**FRs**: FR-012, FR-013, FR-014, FR-015, FR-016, FR-017, FR-018, FR-019

**Tasks**:
1. Redesign message bubbles in `ChatPanel.tsx`: user right-aligned (accent bg), assistant left-aligned (surface bg), use shadcn ScrollArea
2. Add blinking caret cursor during streaming (CSS `@keyframes blink` animation on `<span>`) (FR-013)
3. Add stage-status indicator from `onStatus` callback → small Badge showing current node name (FR-013)
4. Migrate `CitationTooltip.tsx` → citation chips using Badge + Popover (FR-014)
5. Migrate `ConfidenceIndicator.tsx` → colored Badge (green>=70, yellow 40-69, red<40) + expandable Popover with 5-signal breakdown (FR-015)
6. Add meta-reasoning indicator Badge when `onMetaReasoning` fires (FR-016)
7. Add clarification Card when `onClarification` fires (FR-017)
8. Add copy-to-clipboard button on hover per assistant message (FR-018)
9. Create empty state with greeting + 3-4 clickable starter questions (FR-012)
10. Create `hooks/useChatStorage.ts` — localStorage read/write for ChatMessage[] (FR-019):
    - Key: `embedinator-chat-session`
    - Auto-evict previous conversation on new session start
    - Last-write-wins multi-tab (no sync)
    - Integrate with existing `useStreamChat` hook
11. Restyle `ChatSidebar.tsx` — shadcn Select for model/collection pickers
12. Restyle `ChatInput.tsx` — shadcn Textarea + Button
13. Migrate all color classes to design tokens (remove all `dark:` variants, use CSS vars)

**Files**: MODIFIED: `ChatPanel.tsx`, `ChatInput.tsx`, `ChatSidebar.tsx`, `ConfidenceIndicator.tsx`, `CitationTooltip.tsx`, `app/chat/page.tsx`. NEW: `hooks/useChatStorage.ts`

**Verification**: Tokens stream with cursor; citations render as chips; confidence badge colored correctly; empty state shows; localStorage persists across refresh

---

### Phase 5 — Collections Page Redesign

**Goal**: Card grid with search, skeletons, and polished dialogs.
**FRs**: FR-020, FR-021, FR-022, FR-023, FR-024

**Tasks**:
1. Restyle `CollectionList.tsx` — responsive grid (1col mobile, 2col md, 3col lg), search input at top (FR-020, FR-021)
2. Restyle `CollectionCard.tsx` — shadcn Card + Badge for stats + DropdownMenu for actions (FR-020, FR-022)
3. Restyle `CreateCollectionDialog.tsx` — shadcn Dialog + Input + Select (FR-024)
4. Add Skeleton card placeholders while loading (FR-023)
5. Add empty state with CTA button (FR-023)
6. Restyle `CollectionStats.tsx` — token-based colors
7. Migrate all hard-coded `text-gray-*` / `bg-gray-*` / `border-gray-*` classes

**Files**: MODIFIED: `CollectionList.tsx`, `CollectionCard.tsx`, `CollectionStats.tsx`, `CreateCollectionDialog.tsx`, `app/collections/page.tsx`

**Verification**: Card grid responsive at 3 breakpoints; search filters; skeletons display; empty state shows; both themes correct

---

### Phase 6 — Documents Page Redesign

**Goal**: Two-column layout with upload progress tracking.
**FRs**: FR-025, FR-026, FR-027

**Tasks**:
1. Implement two-column layout in `app/documents/[id]/page.tsx`: desktop side-by-side, mobile stacked vertically (FR-025)
2. Restyle `DocumentList.tsx` — shadcn Table + Badge for status (pending/processing/complete/failed) (FR-027)
3. Restyle `DocumentUploader.tsx` — enhanced drop zone visual + shadcn Progress for ingestion tracking (FR-026)
4. Migrate all hard-coded gray classes

**Files**: MODIFIED: `DocumentList.tsx`, `DocumentUploader.tsx`, `app/documents/[id]/page.tsx`

**Verification**: Two-column on desktop, stacked on mobile; upload progress bar tracks; status badges correct; both themes correct

---

### Phase 7 — Settings Page Redesign

**Goal**: Tabbed settings with Sonner toast notifications.
**FRs**: FR-028, FR-029, FR-030

**Tasks**:
1. Restructure `app/settings/page.tsx` — shadcn Tabs (Providers, Models, Inference, System) (FR-028)
2. Restyle `ProviderHub.tsx` — shadcn Card + Input + Button, status dot indicator (FR-029)
3. Add Sonner `<Toaster />` to `app/layout.tsx` (BEFORE deleting Toast.tsx)
4. Replace all `Toast` usage in `app/settings/page.tsx` with `toast()` from sonner (FR-030)
5. Delete `components/Toast.tsx`
6. Migrate all hard-coded gray classes

**Files**: MODIFIED: `ProviderHub.tsx`, `app/settings/page.tsx`, `app/layout.tsx`. DELETED: `components/Toast.tsx`

**Verification**: Tabs switch; provider status dots correct; toast notifications fire on save/delete; both themes correct

---

### Phase 8 — Observability Page Redesign

**Goal**: Polished health dashboard with trace detail panel.
**FRs**: FR-031, FR-032, FR-033, FR-034

**Tasks**:
1. Restyle `HealthDashboard.tsx` — shadcn Card with colored status dots (green/yellow/red/gray) (FR-031)
2. Restyle `StageTimingsChart.tsx` — horizontal bar with token-based colors per stage, tooltip with stage name + ms (FR-032)
3. Restyle `TraceTable.tsx` — shadcn Table + pagination + session/confidence filter (FR-033)
4. Add trace detail Sheet (slide-out panel from right) showing: query, timings, citations, confidence, reasoning steps (FR-034)
5. Restyle `LatencyChart.tsx`, `ConfidenceDistribution.tsx`, `MetricsTrends.tsx` — token-based colors
6. Migrate ALL hard-coded gray classes (this page has ZERO dark: variants — largest migration)

**Files**: MODIFIED: `HealthDashboard.tsx`, `StageTimingsChart.tsx`, `TraceTable.tsx`, `LatencyChart.tsx`, `ConfidenceDistribution.tsx`, `MetricsTrends.tsx`, `app/observability/page.tsx`

**Verification**: Health cards show status dots; chart tooltips work; trace table filters; Sheet detail panel opens; both themes correct

---

### Phase 9 — Command Palette + Breadcrumbs

**Goal**: Cmd+K command palette and contextual breadcrumbs.
**FRs**: FR-004, FR-005

**Tasks**:
1. Create `components/CommandPalette.tsx` — shadcn Command in Dialog (FR-004):
   - Commands: navigate to 5 pages, "Create Collection", "Clear Chat", "Toggle Dark Mode"
   - Register global `Cmd+K` / `Ctrl+K` keydown listener (useEffect in layout or component)
2. Create `components/PageBreadcrumb.tsx` — shadcn Breadcrumb using `usePathname()` (FR-005)
3. Add CommandPalette to `app/layout.tsx` (rendered once, globally)
4. Add PageBreadcrumb to SidebarInset header area (all pages)

**Files**: NEW: `components/CommandPalette.tsx`, `components/PageBreadcrumb.tsx`. MODIFIED: `app/layout.tsx`

**Verification**: Cmd+K opens palette; search filters commands; commands execute; breadcrumbs reflect current route

---

### Phase 10 — Cross-Cutting Polish + QA

**Goal**: Final accessibility, responsive, and consistency audit.
**FRs**: FR-035, FR-036, FR-037, FR-038, NFR-001, NFR-002, NFR-003, NFR-004

**Tasks**:
1. Add shadcn Tooltip to ALL icon-only buttons (sidebar collapse, theme toggle, copy, actions) (FR-035)
2. Audit Skeleton loaders — verify every async section has one (FR-038)
3. Keyboard navigation audit: Tab through all interactive elements; Esc closes all modals/sheets/popovers (FR-037)
4. Responsive audit: all 5 pages at 375px, 768px, 1280px (FR-036)
5. Dark/light audit: verify ZERO remaining hard-coded `text-gray-*`, `bg-gray-*`, `border-gray-*`, or `bg-white` classes in frontend/ source files
6. `npm run build` — verify no TypeScript or build errors
7. `npm run test` — update any Vitest tests that break due to component structure changes
8. `npm run test:e2e` — update Playwright selectors if component markup changed

**Verification**: Build passes; tests pass; no hard-coded color classes remain; all interactive elements keyboard-accessible

## Dependency Graph

```
Phase 0 ──→ Phase 1 ──→ Phase 2 ──→ Phase 3 ──→ Phase 4 (Chat)
                                         ├──→ Phase 5 (Collections)
                                         ├──→ Phase 6 (Documents)
                                         ├──→ Phase 7 (Settings)
                                         └──→ Phase 8 (Observability)
                                                  │ (all join)
                                                  ▼
                                            Phase 9 ──→ Phase 10
```

- Phases 0→3: strictly sequential (each depends on prior)
- Phases 4→8: parallelizable (all depend only on Phase 3)
- Phase 9: depends on all page redesigns (needs Cmd+K commands for all features)
- Phase 10: depends on Phase 9 (final audit after all changes)

## Agent Team Structure

### 4-Wave Execution

| Wave | Phases | Agent(s) | Type | Notes |
|------|--------|----------|------|-------|
| 1 | 0, 1, 2 | A1 (frontend-architect) | Sequential | Foundation + tokens + theme |
| 2 | 3 | A2 (frontend-architect) | Sequential | Sidebar integration (highest risk, isolated) |
| 3 | 4, 5, 6, 7, 8 | A3–A7 (frontend-architect) | Parallel | One agent per page |
| 4 | 9, 10 | A8 (quality-engineer) | Sequential | Command palette + QA audit |

### Wave 2 Gate Check

Before spawning Wave 3 agents, verify:
- `npm run build` succeeds
- All 5 page routes render (no blank pages or crashes)
- Sidebar expand/collapse toggle works on desktop
- Mobile hamburger opens Sheet overlay
- Dark/light theme toggle works on all pages

If any check fails, fix before proceeding.

### Wave 3 Agent Assignment

| Agent | Page | FRs | Complexity |
|-------|------|-----|------------|
| A3 | Chat | FR-012–FR-019 | HIGH — streaming, localStorage, citations, confidence |
| A4 | Collections | FR-020–FR-024 | MEDIUM — card grid, search, dialog, skeletons |
| A5 | Documents | FR-025–FR-027 | MEDIUM — two-column, upload progress, table |
| A6 | Settings | FR-028–FR-030 | MEDIUM — tabs, provider cards, Sonner migration |
| A7 | Observability | FR-031–FR-034 | MEDIUM-HIGH — charts, trace table, Sheet detail |

## Color Migration Guide

### Token Mapping Table

| Old Class Pattern | New Token-Based Class |
|-------------------|-----------------------|
| `text-gray-900`, `text-neutral-900` | `text-[var(--color-text-primary)]` |
| `text-gray-700`, `text-gray-600` | `text-[var(--color-text-primary)]` |
| `text-gray-500`, `text-gray-400`, `text-neutral-500` | `text-[var(--color-text-muted)]` |
| `bg-white` | `bg-[var(--color-background)]` |
| `bg-gray-50`, `bg-gray-100` | `bg-[var(--color-surface)]` |
| `border-gray-200`, `border-gray-300`, `border-neutral-200` | `border-[var(--color-border)]` |
| `bg-blue-600`, `text-blue-600` | `bg-[var(--color-accent)]` / `text-[var(--color-accent)]` |
| `focus:ring-blue-500`, `focus:border-blue-500` | `focus:ring-[var(--color-accent)]` |

**Rule**: Remove ALL `dark:` variant classes. The CSS variable system handles dark mode automatically — no `dark:` prefix needed.

### Migration Scope per File

**Files with ZERO dark mode (broken in dark theme — highest priority)**:
- `TraceTable.tsx` — ~30+ classes (LARGEST)
- `CreateCollectionDialog.tsx` — ~25+ classes
- `app/settings/page.tsx` — ~20 classes
- `app/observability/page.tsx` — ~15 classes
- `DocumentList.tsx` — ~14 classes
- `CollectionCard.tsx` — ~12 classes
- `CollectionStats.tsx` — ~12 classes
- `MetricsTrends.tsx` — ~12 classes
- `ProviderHub.tsx` — ~10 classes
- `CollectionList.tsx` — ~9 classes
- `DocumentUploader.tsx` — ~9 classes
- `HealthDashboard.tsx` — ~8 classes
- `app/documents/[id]/page.tsx` — ~4 classes
- `LatencyChart.tsx` — ~1 class
- `ConfidenceDistribution.tsx` — ~1 class

**Files with existing dark: variants (need token migration, not emergency)**:
- `ChatSidebar.tsx` — ~15 pairs
- `ModelSelector.tsx` — ~12 pairs
- `ChatPanel.tsx` — ~10 pairs
- `CitationTooltip.tsx` — ~8 pairs
- `ConfidenceIndicator.tsx` — ~7 pairs
- `ChatInput.tsx` — ~6 pairs

## Risk Register

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| 1 | shadcn Sidebar requires specific CSS vars (`--sidebar-background`, etc.) | Sidebar renders with broken colors | Phase 1 MUST include these vars in globals.css |
| 2 | ChatPage `h-[calc(100vh-4rem)]` assumes top-nav | Chat page overflows or collapses after sidebar | Phase 3 changes to `h-dvh` |
| 3 | ObservabilityPage has ZERO dark: classes | Completely unreadable in dark mode | Phase 8 migrates ALL classes |
| 4 | next-themes ThemeProvider placement wrong | Hydration errors on every page | Must be: `<html suppressHydrationWarning> <body> <ThemeProvider>` |
| 5 | ThemeProvider vs SidebarProvider nesting order | Theme not available when sidebar renders | ThemeProvider wraps SidebarProvider, not vice versa |
| 6 | Existing Radix deps use `latest` tag | shadcn pins specific versions, potential conflicts | Verify `npm run build` after Phase 0 |
| 7 | Toast.tsx deleted before Sonner added | Settings page crashes | Add Sonner `<Toaster />` to layout BEFORE deleting Toast.tsx |
| 8 | TraceTable.tsx largest migration (~30+ classes) | High effort, error-prone | Allocate to dedicated agent (A7) with extra review |
| 9 | `cn()` utility not adopted | Inconsistent className handling | Phase 0 creates lib/utils.ts; all subsequent phases use `cn()` |

## Testing Matrix

### Per-Phase Verification

| Phase | Verification |
|-------|-------------|
| 0 | `npm run build` passes; `components/ui/` has 21+ files |
| 1 | CSS vars resolve correctly in `:root` and `.dark` selectors |
| 2 | Theme toggle works; refresh preserves; no hydration errors |
| 3 | All 5 routes render; sidebar toggles; mobile overlay works |
| 4 | Tokens stream; citations clickable; confidence colored; empty state; localStorage persists |
| 5 | Card grid responsive; search filters; skeletons; empty state; both themes |
| 6 | Two-column desktop, stacked mobile; upload progress; status badges; both themes |
| 7 | Tabs switch; provider dots; toast notifications; both themes |
| 8 | Health dots; chart tooltips; trace table filters; Sheet detail; both themes |
| 9 | Cmd+K opens; commands execute; breadcrumbs reflect route |
| 10 | Build passes; tests pass; zero hard-coded color classes; keyboard nav complete |

### Final QA Audit

- 30 screenshots: 5 pages x 3 breakpoints (375/768/1280) x 2 themes (dark/light)
- Accessibility audit per page (WCAG 2.1 AA)
- Performance audit per page (< 2s meaningful content)
- Zero remaining `text-gray-*`, `bg-gray-*`, `border-gray-*`, or `bg-white` in source

## Success Criteria Mapping

| SC | Satisfied by Phase(s) | Verification |
|----|----------------------|--------------|
| SC-001 (Sidebar) | Phase 3 | Sidebar renders, collapses, mobile overlay |
| SC-002 (Dark/Light) | Phase 1 + 2 | Toggle works, persists, no flash |
| SC-003 (All pages render) | Phase 3 + 4–8 | All 5 pages, both themes, no errors |
| SC-004 (Chat intelligence) | Phase 4 | Streaming cursor, citations, confidence badge |
| SC-005 (Cmd+K) | Phase 9 | Palette opens, searches, executes |
| SC-006 (Stage timing chart) | Phase 8 | Bars with colors, tooltip with ms |
| SC-007 (Skeletons) | Phase 4–8, 10 | Every async section has skeleton |
| SC-008 (Keyboard nav) | Phase 10 | Tab reaches all; Esc closes all; tooltips on icons |
