# Spec 18 — UX/UI Redesign: Design Session (2026-03-19)

## Status: 18-specify.md + 18-plan.md WRITTEN — ready for speckit.plan

## File Location
`Docs/PROMPTS/spec-18-UX_UI-Redesign/18-specify.md` (417 lines)

## Key Decisions Encoded in File

### Design Philosophy: "Intelligent Warmth"
- Visible intelligence: confidence, citations, meta-reasoning are first-class UI citizens
- Dark mode as default (developer audience)
- Progressively revealed complexity

### 4 Color Palette Proposals (user must choose before FRs are written)
- **A: Obsidian Violet** — near-black + violet-400 accent (recommended, most distinctive)
- **B: Warm Slate + Indigo** — indigo-500 accent, warmer gray bg (familiar dev tool aesthetic)
- **C: Teal + Carbon** — teal-300 accent, deep carbon bg (most differentiated)
- **D: Warm Amber + Stone** — amber-400 accent, stone bg (editorial, humanist)

### Layout Architecture Change
- Fixed top-nav (Navigation.tsx) → shadcn `Sidebar` (collapsible)
- SidebarProvider wraps layout.tsx
- Mobile: hamburger → Sheet slide-in
- Navigation.tsx replaced by `components/SidebarNav.tsx`

### Dark Mode
- next-themes ThemeProvider, `attribute="class"` strategy, manual toggle in sidebar footer
- `suppressHydrationWarning` on `<html>` required

### shadcn/ui Components Required (21 components)
sidebar, sheet, command, badge, skeleton, card, button, input, textarea, select,
tabs, table, dialog, popover, tooltip, scroll-area, progress, separator,
dropdown-menu, sonner, breadcrumb

### Per-Page Priorities
1. Chat — streaming bubbles, citation chips, confidence badge, meta-reasoning status
2. Collections — card grid, skeletons, search, empty state
3. Documents — two-column layout, upload zone, progress bar
4. Settings — tabs (Providers/Models/Inference/System), provider hub cards
5. Observability — health cards, stage timing bar chart, trace table + Sheet detail

## MCP Tools Used During Design
- serena: mapped all 21 components, 5 pages, 5 hooks — verified current baseline
- gitnexus: api.ts context — 14 importers identified; streamChat is core streaming fn
- shadcn-ui: full component inventory; badge/skeleton/command/sidebar details verified
- context7: Next.js 16 layout + font CSS var patterns verified
- sequential-thinking: 5-step design reasoning completed
- mcp-chart: UNAVAILABLE (failed, likely needs server process running)

## Key Gotchas for Speckit.specify
- shadcn Sidebar requires SidebarProvider — spec must require this
- next-themes suppressHydrationWarning is mandatory
- Tailwind 4 uses @theme in globals.css (NOT tailwind.config.ts)
- mcp-chart unavailable — observability chart specs based on recharts (already installed)
- Existing Radix primitives already installed (tooltip, dialog, select) — no conflicts
