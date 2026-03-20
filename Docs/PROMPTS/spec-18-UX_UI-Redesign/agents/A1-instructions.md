# A1 — Wave 1 — frontend-architect (Sonnet)

## CALLSIGN: FOUNDATION

## MISSION

You are the Wave 1 frontend-architect. You run ALONE before any other agent. Your mission is to build the entire design system foundation: install shadcn/ui, create the Obsidian Violet design token system, integrate next-themes for dark/light mode, and construct the collapsible sidebar layout that replaces the current top navigation bar. Every other agent's work depends on yours. If you fail, the entire spec fails.

## INTEL — Read Before Starting

Read these files IN ORDER. Do not begin any task until all are read.

1. `specs/018-ux-redesign/tasks.md` — canonical task list (your tasks: T001–T015)
2. `specs/018-ux-redesign/plan.md` — wave structure, risk register, token values
3. `specs/018-ux-redesign/spec.md` — FR-001–FR-011 (your scope)
4. `specs/018-ux-redesign/research.md` — R1 (shadcn+TW4), R2 (next-themes), R3 (sidebar pattern), R4 (provider nesting)
5. `specs/018-ux-redesign/data-model.md` — complete Obsidian Violet token table with hex values
6. `specs/018-ux-redesign/contracts/ui-components.md` — SidebarNav and ThemeToggle contracts

## ASSIGNED TASKS

T001 through T015 (15 tasks), executed sequentially.

---

### Phase 1: Setup (T001–T005)

**T001** — Install npm dependencies in `frontend/`:
```bash
cd frontend && npm install next-themes lucide-react class-variance-authority clsx tailwind-merge
```

**T002** — Initialize shadcn/ui:
```bash
cd frontend && npx shadcn@latest init
```
This creates `component.json` and `lib/utils.ts` (the `cn()` helper). If prompted for configuration, select: TypeScript, Tailwind CSS, `components/ui` path, `@/` alias.

**T003** — Install 21 shadcn components:
```bash
cd frontend && npx shadcn@latest add sidebar sheet command badge skeleton card button input textarea select tabs table dialog popover tooltip scroll-area progress separator dropdown-menu sonner breadcrumb
```
Verify: `ls frontend/components/ui/` should show 21+ files.

**T004** — Update `frontend/next.config.ts`:
Add `"lucide-react"` and `"class-variance-authority"` to the `optimizePackageImports` array in `experimental`. The array already contains Radix entries.

**T005** — Verify build:
```bash
cd frontend && npm run build
```
MUST succeed with zero errors. If it fails, diagnose and fix before proceeding.

---

### Phase 2a: Design Tokens (T006–T007)

**T006** — Rewrite `frontend/app/globals.css`.

Read the current file first. Then REPLACE the entire `@theme` block, `:root` block, and `@media (prefers-color-scheme: dark)` block with the full Obsidian Violet token system.

Token values are in `specs/018-ux-redesign/data-model.md` (Design Token entity table). The structure MUST be:

```css
@import "tailwindcss";

@theme {
  --breakpoint-md: 768px;
  --breakpoint-lg: 1024px;
}

:root {
  /* Color tokens — Light mode */
  --color-background: #faf9ff;
  --color-surface: #f4f0ff;
  --color-border: #d1c4f5;
  --color-accent: #7c3aed;
  --color-text-primary: #1e1b4b;
  --color-text-muted: #6b52b5;
  --color-success: #059669;
  --color-warning: #d97706;
  --color-destructive: #dc2626;

  /* Typography tokens */
  --font-size-h1: 2rem;
  --font-size-h2: 1.5rem;
  --font-size-h3: 1.25rem;
  --font-size-h4: 1.125rem;
  --font-size-body: 0.875rem;
  --font-size-small: 0.8125rem;
  --font-size-label: 0.75rem;

  /* Spacing tokens */
  --space-page: 2rem;
  --space-card-gap: 1.5rem;
  --space-section: 2.5rem;

  /* Core foreground/background (used by shadcn) */
  --foreground: #1e1b4b;
  --background: #faf9ff;
}

.dark {
  --color-background: #0d0c14;
  --color-surface: #15122a;
  --color-border: #2a2352;
  --color-accent: #a78bfa;
  --color-text-primary: #f5f3ff;
  --color-text-muted: #9785d4;
  --color-success: #34d399;
  --color-warning: #fbbf24;
  --color-destructive: #f87171;

  --foreground: #f5f3ff;
  --background: #0d0c14;
}
```

Remove the old `@media (prefers-color-scheme: dark)` block entirely. Keep the `body` styles.

**T007** — Add shadcn Sidebar CSS vars to `frontend/app/globals.css`.

Append these vars inside BOTH `:root` and `.dark` selectors. Without these, the sidebar component renders with broken colors.

In `:root` (light mode):
```css
  --sidebar-background: #f4f0ff;
  --sidebar-foreground: #1e1b4b;
  --sidebar-primary: #7c3aed;
  --sidebar-primary-foreground: #faf9ff;
  --sidebar-accent: #ede9fe;
  --sidebar-accent-foreground: #1e1b4b;
  --sidebar-border: #d1c4f5;
  --sidebar-ring: #7c3aed;
```

In `.dark`:
```css
  --sidebar-background: #15122a;
  --sidebar-foreground: #f5f3ff;
  --sidebar-primary: #a78bfa;
  --sidebar-primary-foreground: #0d0c14;
  --sidebar-accent: #1e1744;
  --sidebar-accent-foreground: #f5f3ff;
  --sidebar-border: #2a2352;
  --sidebar-ring: #a78bfa;
```

---

### Phase 2b: Theme System (T008–T009)

**T008** — Create `frontend/components/ThemeToggle.tsx`.

This is a `"use client"` component. Contract is in `contracts/ui-components.md`. Use `useTheme()` from `next-themes` and `Sun`/`Moon` icons from `lucide-react`. Display Sun icon in dark mode, Moon in light mode. Click toggles.

**T009** — Modify `frontend/app/layout.tsx`.

Read the current file first. Then:
1. Add `suppressHydrationWarning` to `<html>` tag
2. Import `ThemeProvider` from `next-themes`
3. Wrap children inside `<body>` with: `<ThemeProvider attribute="class" defaultTheme="system" enableSystem>`
4. ThemeProvider is the OUTERMOST provider (SidebarProvider goes inside it in T011)

---

### Phase 2c: Sidebar Layout (T010–T015)

**T010** — Create `frontend/components/SidebarNav.tsx`.

This is the most complex new component. Contract in `contracts/ui-components.md`. Use shadcn Sidebar compound components:
- `Sidebar` with `collapsible="icon"` prop
- `SidebarHeader`: app name "The Embedinator"
- `SidebarContent > SidebarGroup > SidebarMenu`: 5 nav links with lucide icons:
  - `MessageSquare` → `/chat` (label: "Chat")
  - `FolderOpen` → `/collections` (label: "Collections")
  - `FileText` → `/documents` (label: "Documents")
  - `Settings` → `/settings` (label: "Settings")
  - `Activity` → `/observability` (label: "Observability")
- `SidebarFooter`: renders `<ThemeToggle />`
- `SidebarRail` for hover-to-expand affordance
- Active link: use `usePathname()` from `next/navigation` + `isActive` prop on `SidebarMenuButton`
- Must be a `"use client"` component

**T011** — Restructure `frontend/app/layout.tsx`.

Read the current file. Then:
1. Remove `import Navigation from "@/components/Navigation"` and the `<Navigation />` element
2. Remove `<main className="pt-16">` wrapper (no top-nav offset needed)
3. Import `SidebarProvider`, `SidebarInset` from `@/components/ui/sidebar`
4. Import `SidebarNav` from `@/components/SidebarNav`
5. New structure inside ThemeProvider:
```tsx
<SidebarProvider defaultOpen={true}>
  <SidebarNav />
  <SidebarInset>
    <main>{children}</main>
  </SidebarInset>
</SidebarProvider>
```

**T012** — Add localStorage persistence for sidebar state.

In `SidebarNav.tsx` or `layout.tsx`:
- Read initial open state from `localStorage.getItem("sidebar-open")` (default: `true`)
- Use `SidebarProvider`'s controlled `open` + `onOpenChange` props
- Write to localStorage on change: `localStorage.setItem("sidebar-open", String(newOpen))`
- Must handle SSR (check `typeof window !== "undefined"` before reading localStorage)

**T013** — Fix chat page height in `frontend/app/chat/page.tsx`.

Read the current file. Find `h-[calc(100vh-4rem)]` and change it to `h-dvh`. The 4rem offset was for the old top navigation bar which no longer exists.

**T014** — Delete `frontend/components/Navigation.tsx`.

This file is fully replaced by SidebarNav. Remove it.

**T015** — Verify foundation.

```bash
cd frontend && npm run build
```

Must succeed. Then mentally verify (or note for orchestrator):
- All 5 routes should render with the sidebar
- Sidebar collapse toggle should work
- Mobile hamburger should open Sheet overlay
- Dark/light theme toggle should work

Report completion to the orchestrator.

---

## RULES OF ENGAGEMENT

- Do NOT modify any file in `frontend/components/` other than creating new files (ThemeToggle.tsx, SidebarNav.tsx) and deleting Navigation.tsx.
- Do NOT touch any existing page components (ChatPanel, CollectionList, etc.) — those are Wave 3's job.
- Do NOT modify `frontend/lib/api.ts` or `frontend/lib/types.ts` — ever.
- Do NOT modify any hook in `frontend/hooks/` — ever.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- Every file you create must use `"use client"` directive if it uses hooks or browser APIs.

## COMPLETION SIGNAL

When all 15 tasks are done and `npm run build` passes, report to the orchestrator:
- "Wave 1 COMPLETE. Build passes. Ready for Wave 2 gate check."
