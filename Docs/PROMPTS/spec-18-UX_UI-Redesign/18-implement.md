# Spec 18: UX/UI Redesign — Implementation Context

```
# MANDATORY: TMUX MULTI-PANE SPAWNING REQUIRED
# Agent Teams MUST run in tmux. Each wave agent gets its own pane.
# Use TeamCreate → TaskCreate → Agent(team_name=...) → SendMessage
# NEVER spawn agents/subagents in the same pane. Each agent = separate tmux pane.
```

---

## What This Spec Does

Spec-18 redesigns The Embedinator's frontend from a plain top-nav utility app into a
polished, personality-driven, shadcn/ui-based application. It replaces the fixed top
Navigation bar with a collapsible sidebar, introduces the "Obsidian Violet" design token
system, adds dark/light mode toggle via next-themes, and restyles all 5 pages + 21
components to surface AI intelligence at every surface.

**Scope**: 59 tasks (T001–T057 + T053b + T054b), 38 FRs, 4 NFRs, 8 SCs.
**Frontend-only** — no backend changes, no new routes, no API changes.

---

## Authoritative Files — Read Order

Every agent MUST read its own instruction file FIRST, then these shared files:

| Priority | File | Contains |
|----------|------|----------|
| 1 | Agent instruction file (`Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A{N}-instructions.md`) | Assigned tasks, detailed orders |
| 2 | `specs/018-ux-redesign/tasks.md` | Canonical task list (T001–T057) |
| 3 | `specs/018-ux-redesign/plan.md` | Wave structure, risk register, color migration guide |
| 4 | `specs/018-ux-redesign/spec.md` | FR-001–FR-038, SC-001–SC-008 |
| 5 | `specs/018-ux-redesign/research.md` | Technical decisions (shadcn setup, next-themes, provider nesting) |
| 6 | `specs/018-ux-redesign/data-model.md` | Obsidian Violet token values, entity definitions |
| 7 | `specs/018-ux-redesign/contracts/ui-components.md` | New component contracts (SidebarNav, ThemeToggle, CommandPalette, useChatStorage) |

---

## Build Verification Protocol

```
All build verification runs in the frontend/ directory.

Build check:    cd frontend && npm run build
Unit tests:     cd frontend && npm run test
E2E tests:      cd frontend && npm run test:e2e

There is NO external test runner for frontend (unlike backend pytest).
Run commands directly. Output is immediate.
```

---

## Color Migration Guide — ALL WAVE 3 AGENTS MUST READ

Replace hard-coded Tailwind gray/neutral/blue classes with CSS variable-based tokens.
Remove ALL `dark:` variant prefixes — the token system handles dark mode automatically.

| Old Class Pattern | New Token Class |
|-------------------|-----------------|
| `text-gray-900`, `text-neutral-900` | `text-[var(--color-text-primary)]` |
| `text-gray-700`, `text-gray-600` | `text-[var(--color-text-primary)]` |
| `text-gray-500`, `text-gray-400`, `text-neutral-500` | `text-[var(--color-text-muted)]` |
| `bg-white` | `bg-[var(--color-background)]` |
| `bg-gray-50`, `bg-gray-100` | `bg-[var(--color-surface)]` |
| `border-gray-200`, `border-gray-300`, `border-neutral-200` | `border-[var(--color-border)]` |
| `bg-blue-600`, `text-blue-600` | `bg-[var(--color-accent)]` / `text-[var(--color-accent)]` |
| `focus:ring-blue-500`, `focus:border-blue-500` | `focus:ring-[var(--color-accent)]` |

**After migration**: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white' <your-files>` MUST return zero results.

Use `cn()` from `@/lib/utils` for all conditional class merging (NOT template literals).

---

## Risk Gotchas — EVERY AGENT MUST KNOW

1. **shadcn Sidebar CSS vars** — `--sidebar-background`, `--sidebar-foreground`, etc. MUST be in globals.css or sidebar has broken colors.
2. **ChatPage height** — `h-[calc(100vh-4rem)]` assumes top-nav. After sidebar layout, change to `h-dvh`.
3. **ThemeProvider wraps SidebarProvider** — NOT the other way around. Wrong order = hydration errors.
4. **`<html suppressHydrationWarning>`** — Required by next-themes. Without it, React warns on every page.
5. **Toast.tsx → Sonner** — Add `<Toaster />` to layout.tsx BEFORE deleting Toast.tsx (A6's responsibility).
6. **TraceTable.tsx** — 30+ hard-coded gray classes. Largest single-file migration (A7's responsibility).
7. **ModelSelector.tsx** — Shared by ChatSidebar AND Settings page. A3 restyles it; A6 inherits the change.
8. **layout.tsx multi-touch** — Modified by A1 (Phase 2), A6 (Toaster), A8 (CommandPalette, Breadcrumb). Sequential waves prevent conflicts.

---

## Agent Team Roster

| Agent | Role | Wave | Type | Tasks | Mission |
|-------|------|------|------|-------|---------|
| A1 | frontend-architect | 1 | Sonnet | T001–T015 | Foundation: shadcn init, design tokens, theme system, sidebar layout |
| — | *GATE CHECK* | 2 | Orchestrator | — | Verify build, 5 routes, sidebar, theme toggle |
| A3 | frontend-architect | 3 | Sonnet | T016–T027 | Chat page: streaming, citations, confidence, localStorage |
| A4 | frontend-architect | 3 | Sonnet | T028–T032 | Collections page: card grid, search, skeletons, dialog |
| A5 | frontend-architect | 3 | Sonnet | T033–T035 | Documents page: two-column layout, upload progress |
| A6 | frontend-architect | 3 | Sonnet | T036–T039 | Settings page: tabs, provider cards, Sonner toast |
| A7 | frontend-architect | 3 | Sonnet | T040–T044 | Observability page: health cards, charts, trace table |
| A8 | quality-engineer | 4 | Sonnet | T045–T057 | Command Palette, Breadcrumbs, full QA audit |

---

## Wave Execution Sequence

### Wave 1 — A1 SOLO (Sequential)

```
1. TeamCreate("spec18-ux-redesign")
2. TaskCreate(team="spec18-ux-redesign", task for A1)
3. Agent(team_name="spec18-ux-redesign", subagent_type="frontend-architect")
   Prompt: "Read your instruction file at Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A1-instructions.md FIRST, then execute all assigned tasks."
4. Wait for A1 to complete.
```

### Wave 2 — GATE CHECK (Orchestrator)

After A1 completes, the orchestrator runs these checks directly:

```bash
cd frontend && npm run build           # Must succeed
# Then manually verify in browser or via playwright:
# - All 5 routes render (/chat, /collections, /documents, /settings, /observability)
# - Sidebar expand/collapse toggle works
# - Mobile hamburger opens overlay
# - Dark/light theme toggle works
# - No console errors
```

**If any check fails**: Fix issues before proceeding to Wave 3. Do NOT spawn Wave 3 agents on a broken foundation.

### Wave 3 — A3, A4, A5, A6, A7 PARALLEL (5 separate tmux panes)

```
Spawn all 5 agents simultaneously via Agent Teams.
Each agent gets its own tmux pane. They work on DIFFERENT files.

A3: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A3-instructions.md FIRST, then execute all assigned tasks."
A4: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A4-instructions.md FIRST, then execute all assigned tasks."
A5: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A5-instructions.md FIRST, then execute all assigned tasks."
A6: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A6-instructions.md FIRST, then execute all assigned tasks."
A7: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A7-instructions.md FIRST, then execute all assigned tasks."
```

**Coordination note**: A6 modifies `layout.tsx` (adds Sonner `<Toaster />`). No other Wave 3 agent touches layout.tsx. Safe to parallelize.

### Wave 4 — A8 SOLO (Sequential)

After all Wave 3 agents complete:

```
A8: "Read Docs/PROMPTS/spec-18-UX_UI-Redesign/agents/A8-instructions.md FIRST, then execute all assigned tasks."
```

A8 runs the final QA audit, creates Command Palette + Breadcrumbs, and runs all verification checks.

---

## Success Criteria Verification (Final)

After Wave 4 completes, the orchestrator verifies all 8 SCs:

| SC | Check |
|----|-------|
| SC-001 | Sidebar renders on all 5 pages, collapses, mobile overlay works |
| SC-002 | Theme toggle persists across reloads, no flash |
| SC-003 | All 5 pages render in both themes, no hydration/console errors |
| SC-004 | Chat: streaming cursor, citation chips, confidence badge with correct color tier |
| SC-005 | Cmd+K opens, searches, executes commands |
| SC-006 | Observability: stage-timing bars with colors, tooltips with ms |
| SC-007 | Skeleton loaders on every async section |
| SC-008 | Tab reaches all interactive elements; Esc closes all modals/sheets; icon tooltips |

All 8 must PASS. If any fails, fix and re-verify before marking spec-18 complete.
