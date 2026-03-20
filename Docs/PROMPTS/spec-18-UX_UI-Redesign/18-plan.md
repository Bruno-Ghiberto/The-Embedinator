# Spec 18 — UX/UI Redesign: Context Prompt for `speckit.plan`

> **How to use this file**: Pass it as context to `speckit.plan`.
> The agent will generate `specs/018-ux-redesign/plan.md` using the implementation
> architecture, dependency chain, file map, and risk analysis below.

---

## Feature Summary

Redesign The Embedinator's frontend: replace the fixed top-nav with a collapsible shadcn
Sidebar, add dark/light mode toggle via next-themes, implement the "Obsidian Violet" design
token system, and restyle all 5 pages + 21 components to surface AI intelligence at every surface.

**Spec file**: `specs/018-ux-redesign/spec.md`
**38 Functional Requirements**, **4 NFRs**, **8 Success Criteria**, **6 User Stories**

---

## Critical Dependency Chain

The implementation has a strict ordering — phases CANNOT be parallelized until Phase 4.

```
Phase 0: Foundation ─── npm install + shadcn init
    │
    ▼
Phase 1: Design Tokens ─── globals.css rewrite + CSS vars
    │
    ▼
Phase 2: Theme System ─── next-themes ThemeProvider + ThemeToggle
    │
    ▼
Phase 3: Sidebar Layout ─── SidebarNav + layout.tsx restructure (HIGHEST RISK)
    │
    ├──────────────────┬──────────────────┬──────────────────┬──────────────────┐
    ▼                  ▼                  ▼                  ▼                  ▼
Phase 4:          Phase 5:          Phase 6:          Phase 7:          Phase 8:
Chat Page         Collections       Documents         Settings          Observability
(P2, complex)     (P3)              (P4)              (P5)              (P6)
    │                  │                  │                  │                  │
    └──────────────────┴──────────────────┴──────────────────┴──────────────────┘
                                          │
                                          ▼
                                   Phase 9: Command Palette + Breadcrumbs
                                          │
                                          ▼
                                   Phase 10: Cross-Cutting Polish + QA
```

**Why this order**: shadcn components need CSS tokens; tokens need the theme system active;
sidebar restructures layout.tsx which all pages render inside; per-page redesigns depend on
all three foundation layers being stable.

---

## Phase Details

### Phase 0 — Foundation (Blocking: everything depends on this)

**Goal**: Install shadcn/ui, next-themes, lucide-react, and supporting utilities.

**Tasks**:
1. `npm install next-themes lucide-react class-variance-authority clsx tailwind-merge`
2. Run `npx shadcn@latest init` — creates `component.json`, `lib/utils.ts` with `cn()` helper
3. Install core shadcn components (21 total):
   `npx shadcn@latest add sidebar sheet command badge skeleton card button input textarea select tabs table dialog popover tooltip scroll-area progress separator dropdown-menu sonner breadcrumb`
4. Update `next.config.ts` → add `lucide-react` and `class-variance-authority` to `optimizePackageImports`
5. Verify: `npm run build` succeeds with no errors

**New files**: `component.json`, `lib/utils.ts`, `components/ui/*.tsx` (~21 files)
**Modified files**: `package.json`, `package-lock.json`, `next.config.ts`

---

### Phase 1 — Design Tokens (Blocking: all components depend on tokens)

**Goal**: Rewrite `globals.css` with the complete Obsidian Violet token system.

**Tasks**:
1. Rewrite `app/globals.css` `@theme` block with full token set:
   - Color tokens: `--color-background`, `--color-surface`, `--color-border`, `--color-accent`,
     `--color-text-primary`, `--color-text-muted`, `--color-success`, `--color-warning`, `--color-destructive`
   - Typography tokens: `--font-size-h1` through `--font-size-label`
   - Spacing tokens: `--space-page`, `--space-card-gap`, `--space-section`
   - Sidebar-specific tokens required by shadcn: `--sidebar-background`, `--sidebar-foreground`,
     `--sidebar-primary`, `--sidebar-accent`, `--sidebar-border`, `--sidebar-ring`
2. Map `:root` to light mode values, `.dark` class to dark mode values (FR-006)
3. Remove old `@media (prefers-color-scheme: dark)` block (replaced by class-based switching)
4. Verify: both `:root` and `.dark` selectors produce correct colors

**Modified files**: `app/globals.css`
**CRITICAL**: shadcn Sidebar requires specific CSS vars (see code example 24 from shadcn-ui MCP).
The plan MUST include these vars or the sidebar will render with broken colors.

---

### Phase 2 — Theme System (Blocking: dark mode toggle for all pages)

**Goal**: Add next-themes ThemeProvider and create ThemeToggle component.

**Tasks**:
1. Create `components/ThemeToggle.tsx` — Sun/Moon icon button using `useTheme()` from next-themes
2. Modify `app/layout.tsx`:
   - Add `suppressHydrationWarning` to `<html>` element
   - Wrap children with `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>`
   - ThemeProvider goes INSIDE `<body>`, wrapping all content
3. Verify: toggling theme applies `.dark` class to `<html>`, all CSS vars switch correctly
4. Verify: page refresh preserves chosen theme (no flash of wrong theme)

**New files**: `components/ThemeToggle.tsx`
**Modified files**: `app/layout.tsx`

---

### Phase 3 — Sidebar Layout (HIGHEST RISK — changes root layout)

**Goal**: Replace Navigation.tsx with shadcn Sidebar in layout.tsx.

**Tasks**:
1. Create `components/SidebarNav.tsx` using shadcn Sidebar compound components:
   - `SidebarHeader`: app name/logo
   - `SidebarContent > SidebarGroup > SidebarMenu`: 5 nav links with lucide icons
     (MessageSquare, FolderOpen, FileText, Settings, Activity)
   - `SidebarFooter`: ThemeToggle + system status indicator
   - `SidebarRail` for hover-to-expand
   - Use `collapsible="icon"` prop for icon-only collapsed state
   - Active link highlighting via `usePathname()` + `isActive` prop
2. Modify `app/layout.tsx`:
   - Remove `import Navigation` and `<Navigation />`
   - Remove `<main className="pt-16">` wrapper
   - Add `SidebarProvider` wrapping ThemeProvider's children
   - Structure: `<SidebarProvider> <SidebarNav /> <SidebarInset><main>{children}</main></SidebarInset> </SidebarProvider>`
3. Add localStorage persistence for sidebar open/collapsed state:
   - Read initial state from `localStorage.getItem("sidebar-open")`
   - Use `SidebarProvider`'s `open` + `onOpenChange` controlled props
4. Fix ChatPage height calc: change `h-[calc(100vh-4rem)]` → `h-screen` or `h-[calc(100dvh)]`
   (no more top-nav offset needed)
5. Delete `components/Navigation.tsx` (replaced by SidebarNav)
6. Verify: all 5 pages render correctly with sidebar, collapse toggle works,
   mobile hamburger opens Sheet overlay

**New files**: `components/SidebarNav.tsx`
**Modified files**: `app/layout.tsx`, `app/chat/page.tsx`
**Deleted files**: `components/Navigation.tsx`

**RISK**: This changes the root layout wrapping all pages. If SidebarProvider or token wiring
is wrong, ALL pages break simultaneously. Test immediately after this phase before proceeding.

---

### Phases 4–8 — Per-Page Redesigns (PARALLELIZABLE after Phase 3)

Each page redesign is independent. Agent teams can work on these simultaneously.

#### Phase 4 — Chat Page (Most Complex — FR-012 through FR-019)

**Tasks**:
1. Redesign message bubbles in ChatPanel.tsx:
   - User messages: right-aligned, accent background
   - Assistant messages: left-aligned, surface background
   - Use `ScrollArea` for message container
2. Add blinking caret cursor during streaming (CSS animation on `<span>`)
3. Add stage-status indicator (from `onStatus` callback → small Badge showing current node)
4. Migrate CitationTooltip → citation chips using Badge + Popover
5. Migrate ConfidenceIndicator → Badge (colored by tier) + expandable Popover (5-signal breakdown)
6. Add meta-reasoning indicator (Badge when `onMetaReasoning` fires)
7. Add clarification card (styled Card when `onClarification` fires)
8. Add copy-to-clipboard button on hover per assistant message
9. Create empty state with greeting + 3-4 starter questions
10. Implement localStorage chat persistence (FR-019):
    - Create `hooks/useChatStorage.ts` — reads/writes ChatMessage[] to localStorage
    - Key: `embedinator-chat-session`
    - Auto-evict previous conversation on new session start
    - Last-write-wins for multi-tab (no sync)
    - Integrate with existing `useStreamChat` hook
11. Restyle ChatSidebar.tsx — use shadcn Select for model/collection pickers
12. Restyle ChatInput.tsx — use shadcn Textarea + Button

**Modified files**: `ChatPanel.tsx`, `ChatInput.tsx`, `ChatSidebar.tsx`,
  `ConfidenceIndicator.tsx`, `CitationTooltip.tsx`, `app/chat/page.tsx`
**New files**: `hooks/useChatStorage.ts`

#### Phase 5 — Collections Page (FR-020 through FR-024)

**Tasks**:
1. Restyle CollectionList.tsx — responsive grid (1/2/3 cols), search input at top
2. Restyle CollectionCard.tsx — shadcn Card + Badge for stats + DropdownMenu for actions
3. Restyle CreateCollectionDialog.tsx — shadcn Dialog + Input + Select
4. Add skeleton loading (Skeleton Card placeholders)
5. Add empty state with CTA
6. Migrate all hard-coded `text-gray-*` / `bg-gray-*` / `border-gray-*` classes to token-based

**Modified files**: `CollectionList.tsx`, `CollectionCard.tsx`, `CollectionStats.tsx`,
  `CreateCollectionDialog.tsx`, `app/collections/page.tsx`

#### Phase 6 — Documents Page (FR-025 through FR-027)

**Tasks**:
1. Implement two-column layout (desktop) / stacked layout (mobile) on documents/[id]/page.tsx
2. Restyle DocumentList.tsx — shadcn Table + Badge for status
3. Restyle DocumentUploader.tsx — enhanced drop zone + shadcn Progress for ingestion tracking
4. Migrate all hard-coded gray classes to token-based

**Modified files**: `DocumentList.tsx`, `DocumentUploader.tsx`, `app/documents/[id]/page.tsx`

#### Phase 7 — Settings Page (FR-028 through FR-030)

**Tasks**:
1. Restructure settings/page.tsx — shadcn Tabs (Providers, Models, Inference, System)
2. Restyle ProviderHub.tsx — shadcn Card + Input + Button, status dot
3. Replace custom Toast.tsx → install and configure Sonner globally
4. Delete `components/Toast.tsx`
5. Add `<Toaster />` from Sonner to `app/layout.tsx`
6. Migrate all hard-coded gray classes to token-based

**Modified files**: `ProviderHub.tsx`, `app/settings/page.tsx`, `app/layout.tsx`
**Deleted files**: `components/Toast.tsx`

#### Phase 8 — Observability Page (FR-031 through FR-034)

**Tasks**:
1. Restyle HealthDashboard.tsx — shadcn Card with colored status dots
2. Restyle StageTimingsChart.tsx — horizontal bar chart with token-based colors, tooltip
3. Restyle TraceTable.tsx — shadcn Table + pagination + session/confidence filter
4. Create trace detail Sheet (new component or inline in TraceTable) — slide-out panel
5. Restyle LatencyChart, ConfidenceDistribution, MetricsTrends — token-based chart colors
6. Migrate ALL hard-coded gray classes (ObservabilityPage has ZERO dark: classes)

**Modified files**: `HealthDashboard.tsx`, `StageTimingsChart.tsx`, `TraceTable.tsx`,
  `LatencyChart.tsx`, `ConfidenceDistribution.tsx`, `MetricsTrends.tsx`,
  `app/observability/page.tsx`

---

### Phase 9 — Command Palette + Breadcrumbs

**Goal**: Add Cmd+K command palette and page breadcrumbs.

**Tasks**:
1. Create `components/CommandPalette.tsx` — shadcn Command in Dialog
   - Commands: navigate to 5 pages, "Create Collection", "Clear Chat", "Toggle Dark Mode"
   - Register `Cmd+K` / `Ctrl+K` global keydown listener
2. Create `components/PageBreadcrumb.tsx` — shadcn Breadcrumb, uses `usePathname()`
3. Add CommandPalette to `app/layout.tsx` (rendered once, globally)
4. Add PageBreadcrumb to each page's content area (or to SidebarInset header)

**New files**: `components/CommandPalette.tsx`, `components/PageBreadcrumb.tsx`
**Modified files**: `app/layout.tsx`

---

### Phase 10 — Cross-Cutting Polish + QA

**Goal**: Final audit for accessibility, responsiveness, and consistency.

**Tasks**:
1. Add Tooltip to all icon-only buttons (sidebar collapse toggle, theme toggle, etc.)
2. Audit all Skeleton loaders — ensure every async section has one
3. Keyboard navigation audit: Tab through all interactive elements, verify Esc closes modals
4. Responsive audit: test all 5 pages at 375px, 768px, 1280px
5. Dark/light mode audit: verify no hard-coded gray-* or bg-white classes remain in frontend/
6. Run `npm run build` — verify no TypeScript or build errors
7. Run existing Vitest tests — update any that break due to component structure changes
8. Run Playwright tests — update selectors if component markup changed

---

## Color Class Migration Guide

> **CRITICAL**: 15 of 22 frontend source files have hard-coded `text-gray-*` / `bg-gray-*` /
> `border-gray-*` classes with NO dark: variants. These are completely broken in dark mode.
> All must be migrated to token-based classes.

### Migration Pattern

Replace hard-coded Tailwind gray/neutral classes with CSS variable-based utilities:

| Old Class Pattern | New Class (via design tokens) |
|-------------------|-------------------------------|
| `text-gray-900`, `text-neutral-900` | `text-[var(--color-text-primary)]` or `text-foreground` |
| `text-gray-700`, `text-gray-600` | `text-[var(--color-text-primary)]` (context-dependent) |
| `text-gray-500`, `text-gray-400`, `text-neutral-500` | `text-[var(--color-text-muted)]` or `text-muted-foreground` |
| `bg-white` | `bg-[var(--color-background)]` |
| `bg-gray-50`, `bg-gray-100` | `bg-[var(--color-surface)]` |
| `border-gray-200`, `border-gray-300`, `border-neutral-200` | `border-[var(--color-border)]` |
| `bg-blue-600`, `text-blue-600` | `bg-[var(--color-accent)]` / `text-[var(--color-accent)]` |
| `focus:ring-blue-500`, `focus:border-blue-500` | `focus:ring-[var(--color-accent)]` |

**Important**: Remove ALL `dark:` variant classes from files that currently have them.
The token system handles dark mode automatically through CSS vars — no `dark:` prefix needed.

### Files with NO Dark Mode (highest priority — currently broken)

```
app/settings/page.tsx           (~20 hard-coded gray classes)
app/observability/page.tsx      (~15 hard-coded gray classes)
app/documents/[id]/page.tsx     (~4 hard-coded gray classes)
components/CollectionCard.tsx   (~12 hard-coded gray classes)
components/CreateCollectionDialog.tsx (~25+ hard-coded gray classes)
components/CollectionList.tsx   (~9 hard-coded gray classes)
components/CollectionStats.tsx  (~12 hard-coded gray classes)
components/DocumentList.tsx     (~14 hard-coded gray classes)
components/DocumentUploader.tsx (~9 hard-coded gray classes)
components/ProviderHub.tsx      (~10 hard-coded gray classes)
components/HealthDashboard.tsx  (~8 hard-coded gray classes)
components/TraceTable.tsx       (~30+ hard-coded gray classes — LARGEST migration)
components/MetricsTrends.tsx    (~12 hard-coded gray classes)
components/LatencyChart.tsx     (~1 hard-coded gray class)
components/ConfidenceDistribution.tsx (~1 hard-coded gray class)
```

### Files with Existing Dark Variants (need token migration, not emergency)

```
components/Navigation.tsx       → DELETED (replaced by SidebarNav)
components/ChatPanel.tsx        (~10 neutral + dark: pairs)
components/ChatInput.tsx        (~6 neutral + dark: pairs)
components/ChatSidebar.tsx      (~15 neutral + dark: pairs)
components/ModelSelector.tsx    (~12 neutral + dark: pairs)
components/ConfidenceIndicator.tsx (~7 neutral + dark: pairs)
components/CitationTooltip.tsx  (~8 neutral + dark: pairs)
```

---

## Agent Team Strategy

### Recommended Wave Structure

| Wave | Phases | Agents | Type | Parallelism |
|------|--------|--------|------|-------------|
| 1 | 0 + 1 + 2 | A1 (frontend-architect, Sonnet) | Sequential | None — each phase depends on prior |
| 2 | 3 | A2 (frontend-architect, Sonnet) | Sequential | None — highest risk, needs isolation |
| 3 | 4, 5, 6, 7, 8 | A3–A7 (frontend-architect, Sonnet) | Parallel | 5 agents, one page each |
| 4 | 9 + 10 | A8 (quality-engineer, Sonnet) | Sequential | Audit + polish pass |

### Wave 2 Gate

After Wave 2 (sidebar integration), run a **gate check** before proceeding to Wave 3:
- `npm run build` must succeed
- All 5 page routes must render (no blank pages)
- Sidebar toggle must work (expand/collapse/mobile)
- Dark/light mode toggle must work on all pages

If the gate fails, fix issues before spawning Wave 3 agents.

### Wave 3 Agent Assignment

| Agent | Page | Key FRs | Estimated Complexity |
|-------|------|---------|---------------------|
| A3 | Chat | FR-012–FR-019 | HIGH (streaming, localStorage, citation chips, confidence) |
| A4 | Collections | FR-020–FR-024 | MEDIUM (card grid, search, dialog, skeletons) |
| A5 | Documents | FR-025–FR-027 | MEDIUM (two-column, upload progress, table) |
| A6 | Settings | FR-028–FR-030 | MEDIUM (tabs, provider cards, Sonner toast migration) |
| A7 | Observability | FR-031–FR-034 | MEDIUM-HIGH (charts, trace table, Sheet detail panel) |

---

## Risk Mitigation

### Critical Path Gotchas (Verified via serena + gitnexus)

1. **shadcn Sidebar requires specific CSS vars**: `--sidebar-background`, `--sidebar-foreground`,
   `--sidebar-primary`, `--sidebar-accent`, `--sidebar-border`, `--sidebar-ring` —
   these MUST be added to globals.css in Phase 1 or the sidebar will have broken styling.

2. **ChatPage height calc**: `h-[calc(100vh-4rem)]` assumes a 4rem top-nav. After sidebar
   layout (Phase 3), this breaks because there's no top-nav. Must change to `h-dvh` or `h-screen`.

3. **ObservabilityPage has ZERO dark: classes**: Every color in this page is hard-coded light
   mode (`text-gray-900`, `bg-white`, `border-gray-200`). It will be completely unreadable
   in dark mode until Phase 8 runs.

4. **next-themes ThemeProvider placement**: Must be `<html suppressHydrationWarning> <body>
   <ThemeProvider attribute="class">`. If placed elsewhere, hydration errors occur.

5. **SidebarProvider + ThemeProvider nesting**: `ThemeProvider` wraps `SidebarProvider`, NOT
   the other way around. Theme must be available before sidebar renders.

6. **Existing Radix deps use `latest` tag**: `package.json` has `"@radix-ui/react-tooltip": "latest"`.
   shadcn pins specific versions. Running `npx shadcn@latest add` may update these — verify
   no breaking changes after Phase 0.

7. **Toast.tsx only used by settings/page.tsx**: Safe to delete in Phase 7 without affecting
   other pages. But Sonner `<Toaster />` must be added to layout.tsx BEFORE deleting Toast.tsx.

8. **TraceTable.tsx is the largest migration**: 30+ hard-coded gray classes, complex expand/collapse
   row logic, pagination. Allocate extra time for Phase 8.

9. **`cn()` utility from shadcn**: After Phase 0, ALL className conditionals should migrate
   to `cn()` from `lib/utils.ts` instead of template literals. This is a secondary concern
   but improves maintainability.

---

## Testing Strategy

### Per-Phase Verification

| Phase | Verification Method |
|-------|---------------------|
| 0 | `npm run build` succeeds; `components/ui/` directory exists with 21 files |
| 1 | Manual inspect: CSS vars resolve correctly in browser DevTools for both `:root` and `.dark` |
| 2 | Toggle theme: `.dark` class appears/disappears on `<html>`; refresh preserves choice |
| 3 | All 5 routes render; sidebar collapses; mobile overlay opens; no console errors |
| 4–8 | Per-page visual check in both dark and light mode; no hard-coded gray classes remain |
| 9 | Cmd+K opens palette; commands execute; breadcrumbs show correct context |
| 10 | `npm run build`; `npm run test`; `npm run test:e2e`; accessibility audit |

### QA Audit Tools (MCP-Assisted)

- **playwright**: `browser_navigate` → `browser_take_screenshot` at each breakpoint (375/768/1280)
  for all 5 pages in both dark and light mode → 30 screenshots total
- **browser-tools**: `runAccessibilityAudit` + `runNextJSAudit` + `runPerformanceAudit`
  on each page after completion
- **chrome-devtools**: `lighthouse_audit` for final quality gate; `emulate` for device testing

---

## MCP Usage Instructions

Use the following MCP servers during plan generation. Each has a defined role.

### Mandatory (always use)

**serena** — Use for implementation-level codebase exploration.
- `find_symbol` with `include_body=true` on every component being modified — understand current
  implementation before designing the change
- `find_referencing_symbols` on Navigation.tsx and Toast.tsx to confirm all imports that need updating
- `search_for_pattern` for `text-gray-|bg-gray-|border-gray-` to quantify migration scope per file
- `get_symbols_overview` on each page to understand component composition

**gitnexus** — Use for architectural impact analysis.
- `gitnexus_impact` on `layout.tsx` before designing the sidebar restructure
- `gitnexus_context` on `api.ts` to understand the full hook → component dependency graph
- `gitnexus_detect_changes` after plan generation to verify scope matches expectations

**sequential-thinking** — Use to reason through complex design decisions.
- Activate before designing the Phase 3 sidebar integration (complex nesting of providers)
- Use when designing the localStorage chat persistence architecture (FR-019)
- Use when planning the color class migration strategy

### Contextual (use when the task calls for it)

**shadcn-ui** — CRITICAL during planning.
- `get_component_details` for every shadcn component being installed — especially `sidebar`
  (needs SidebarProvider, has complex sub-components)
- `get_component_examples` for sidebar, command, and sonner — these have non-obvious integration patterns
- Verify component dependencies (e.g., sidebar needs sheet, button, separator, input, skeleton)

**context7** — Use for framework integration patterns.
- `/pacocoursey/next-themes`: ThemeProvider setup, `useTheme` hook, `suppressHydrationWarning`
- `/vercel/next.js` (v16): App Router layout patterns, CSS variables with `@theme`

**playwright** — Use when designing visual verification steps.
- Plan screenshot-based verification checkpoints for each phase
- Design the responsive testing matrix (5 pages x 3 breakpoints x 2 themes = 30 checks)

**browser-tools** — Use when designing the QA audit plan.
- Plan which audits to run (accessibility, Next.js, performance, best practices)
- Define pass/fail thresholds for each audit

---

## Instructions for `speckit.plan` Agent

### Plan Structure to Generate

Generate `specs/018-ux-redesign/plan.md` with these sections:

1. **Component Overview** — summary of what's being built
2. **What Already Exists — Verify, Do Not Recreate** — list all existing files/components
3. **Implementation Phases** — 11 phases (0–10) with exact tasks, files, and verification
4. **Dependency Graph** — which phases block which
5. **Agent Team Structure** — 4 waves, agent assignments, gate checks
6. **Color Migration Guide** — mapping table + per-file migration scope
7. **Risk Register** — 9 gotchas with mitigation strategies
8. **Testing Matrix** — per-phase verification + final QA audit plan
9. **Success Criteria Mapping** — which phases satisfy which SCs

### Quality Standards

- Every task must name the exact file(s) it modifies
- Every phase must have a verification step that can be run independently
- The plan must be executable by agents who have NOT read this context file — include
  all necessary technical details inline
- Use the shadcn-ui MCP to verify component details before referencing them in the plan
- Reference specific FR numbers for every task

### What NOT to Include

- Do not include implementation code in the plan (that's for `speckit.implement`)
- Do not repeat the full spec text — reference FR/SC numbers
- Do not include agent instruction files (those are created during implement-prep)
