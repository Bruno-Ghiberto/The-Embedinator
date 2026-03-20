# Spec 18 — UX/UI Redesign: Context Prompt for `speckit.specify`

> **How to use this file**: Pass it as context to `speckit.specify`.
> The agent will generate `specs/018-ux-redesign/spec.md` using the description,
> constraints, and clarification targets below.

---

## Feature Title

**Spec 18 — UX/UI Redesign: "Intelligent Warmth"**

One-liner: Redesign The Embedinator's frontend from a plain top-nav utility app into
a polished, personality-driven, shadcn/ui-based application that makes the system's
AI intelligence visible at every surface.

---

## Design Philosophy: "Intelligent Warmth"

The Embedinator's backend is far more sophisticated than its current UI suggests.
The redesign must close that gap — intelligence should be visible, not buried.

**Core principles:**

1. **Visible Intelligence** — Confidence scores, citation chips, meta-reasoning status,
   and stage timings are first-class UI citizens, not footnotes.
2. **Comfortable Density** — Enough whitespace to breathe, enough information density
   to be a productive tool. Not a landing page. Not a data dump.
3. **Consistent Personality** — One cohesive accent color, one type scale, one spacing
   rhythm. No ad-hoc one-off styles per component.
4. **Dark Mode as Default** — The primary user is a developer who works in dark mode.
   Dark theme must be polished first; light theme must be equally complete.
5. **Progressively Revealed Complexity** — Simple on first glance; detail on demand
   (expandable confidence breakdown, trace detail drawer, etc.)

---

## Color Palette Proposals

> **CLARIFICATION REQUIRED**: The `speckit.specify` agent MUST ask the user to choose
> one of these palettes (or describe a custom direction) before generating the FR section.
> Do not pick a palette autonomously. Present all four options with their names and
> short descriptions, then wait for the user's choice.

### Palette A — "Obsidian Violet" (Recommended)

The most distinctive option. Near-black backgrounds with a subtle violet undertone
make the dark theme feel crafted rather than generic. Violet accent sits naturally
between "AI-forward" and "premium."

| Token | Dark Mode | Light Mode |
|-------|-----------|------------|
| Background | `#0d0c14` | `#faf9ff` |
| Surface (cards, panels) | `#15122a` | `#f4f0ff` |
| Border | `#2a2352` | `#d1c4f5` |
| Primary accent | `#a78bfa` (violet-400) | `#7c3aed` (violet-700) |
| Text primary | `#f5f3ff` | `#1e1b4b` |
| Text muted | `#9785d4` | `#6b52b5` |
| Success | `#34d399` | `#059669` |
| Warning | `#fbbf24` | `#d97706` |
| Destructive | `#f87171` | `#dc2626` |

Tailwind scale basis: `violet`, `purple` for accent; `zinc` for neutral.

---

### Palette B — "Warm Slate + Indigo"

The developer-trusted aesthetic. Warm-tinted dark surfaces prevent the clinical
feel of pure zinc/gray. Indigo is the most recognizable "modern dev tool" accent
(Vercel, Linear) — familiar but not boring.

| Token | Dark Mode | Light Mode |
|-------|-----------|------------|
| Background | `#0f0f14` | `#fafaf9` |
| Surface | `#1a1a2e` | `#f5f5f9` |
| Border | `#2e2e50` | `#e2e2ef` |
| Primary accent | `#818cf8` (indigo-400) | `#6366f1` (indigo-500) |
| Text primary | `#f0f0ff` | `#1e1b4b` |
| Text muted | `#8888b8` | `#5a5a9a` |

Tailwind scale basis: `indigo` for accent; `zinc`/`slate` for neutral.

---

### Palette C — "Teal + Carbon"

The most differentiated option in the AI tools market. Deep carbon backgrounds
with teal-cyan accent. Reads as precision and intelligence. Zero other AI tools
use this combination — maximum visual identity.

| Token | Dark Mode | Light Mode |
|-------|-----------|------------|
| Background | `#060d0f` | `#f0f9f9` |
| Surface | `#0d1a1e` | `#e0f5f4` |
| Border | `#1a3040` | `#b0d8d5` |
| Primary accent | `#2dd4bf` (teal-300) | `#0d9488` (teal-600) |
| Text primary | `#f0fafa` | `#0d3330` |
| Text muted | `#6bbab5` | `#257b76` |

Tailwind scale basis: `teal`, `cyan` for accent; `slate` for neutral.

---

### Palette D — "Warm Amber + Stone"

The most editorial and human option. Warm dark stone backgrounds with amber
accent signal warmth and craftsmanship. Highly unusual in AI tooling, making
this feel like a tool built by people who care, not a generic SaaS dashboard.

| Token | Dark Mode | Light Mode |
|-------|-----------|------------|
| Background | `#100e0a` | `#fffbf5` |
| Surface | `#1c1914` | `#fef5e4` |
| Border | `#332e26` | `#e8dcc4` |
| Primary accent | `#fbbf24` (amber-400) | `#d97706` (amber-600) |
| Text primary | `#fefce8` | `#1c1400` |
| Text muted | `#b89a60` | `#7a5c20` |

Tailwind scale basis: `amber`, `yellow` for accent; `stone`, `neutral` for neutral.

---

## Current Frontend Baseline (Verified State)

> Do NOT assume. These facts were verified via serena + gitnexus before writing this file.

### Architecture

- **Framework**: Next.js 16, TypeScript 5.7, React 19, Tailwind CSS 4
- **Layout**: `frontend/app/layout.tsx` — `RootLayout` renders `<Navigation />` (fixed top bar)
  + `<main className="pt-16">`. No sidebar. No `ThemeProvider`.
- **Dark mode**: CSS-only via `@media (prefers-color-scheme: dark)` in `globals.css`.
  No manual toggle, no class-based switching.
- **Design tokens**: `globals.css` has `@theme` with only 2 breakpoints + 2 CSS vars
  (`--foreground`, `--background`). No color palette tokens.
- **shadcn/ui**: NOT installed. No `components/ui/` directory, no `component.json`.
- **Existing Radix**: `@radix-ui/react-tooltip`, `@radix-ui/react-dialog`,
  `@radix-ui/react-select` already in `package.json` (used by hand-built components).
- **Charts**: `recharts` already installed and used.
- **Data fetching**: `SWR` already installed, used via 5 custom hooks.
- **File upload**: `react-dropzone` already installed.

### Pages (5 routes)

| Route | File | Key Components Used |
|-------|------|---------------------|
| `/chat` | `app/chat/page.tsx` | ChatPanel, ChatInput, ModelSelector, ChatSidebar, ConfidenceIndicator, CitationTooltip |
| `/collections` | `app/collections/page.tsx` | CollectionList, CollectionCard, CollectionStats, CreateCollectionDialog |
| `/documents/[id]` | `app/documents/[id]/page.tsx` | DocumentList, DocumentUploader |
| `/settings` | `app/settings/page.tsx` | ProviderHub, ModelSelector |
| `/observability` | `app/observability/page.tsx` | HealthDashboard, TraceTable, LatencyChart, StageTimingsChart, ConfidenceDistribution, MetricsTrends |

### Existing Components (21 hand-built, no shadcn)

```
Navigation.tsx         ChatPanel.tsx          ChatInput.tsx
ChatSidebar.tsx        ModelSelector.tsx      ConfidenceIndicator.tsx
CitationTooltip.tsx    CollectionCard.tsx     CollectionList.tsx
CollectionStats.tsx    CreateCollectionDialog.tsx  DocumentList.tsx
DocumentUploader.tsx   ProviderHub.tsx        Toast.tsx
HealthDashboard.tsx    TraceTable.tsx         LatencyChart.tsx
StageTimingsChart.tsx  ConfidenceDistribution.tsx  MetricsTrends.tsx
```

### Existing Hooks (5, all unchanged by this spec)

```
useStreamChat.ts   useCollections.ts   useModels.ts
useTraces.ts       useMetrics.ts
```

### Key NDJSON Stream Events (visible in UI)

`session`, `status`, `chunk`, `clarification`, `citation`, `meta_reasoning`,
`confidence`, `groundedness`, `done`, `error`

---

## Scope — What Changes

### New Infrastructure (shared)
- `next-themes` installed + `ThemeProvider` wrapping layout
- `components/ui/` directory (shadcn component registry)
- `component.json` (shadcn config)
- `globals.css` expanded with full `@theme` color token system for chosen palette
- `app/layout.tsx` restructured: sidebar layout replaces top-nav layout

### Layout Architecture Change

**From**: Fixed top navbar (Navigation.tsx) + full-width main
**To**: Collapsible left sidebar (shadcn `Sidebar` component) + content area

- Sidebar shows: app name/logo, nav links with icons, dark mode toggle, system status indicator
- On `md`+ breakpoint: sidebar expanded (icons + labels, ~240px) or icon-only (~56px, user toggle)
- On mobile (< `md`): sidebar hidden, hamburger button → `Sheet` slide-in
- Navigation.tsx replaced by new `components/SidebarNav.tsx`

### Dark Mode Toggle

- `next-themes` ThemeProvider with `attribute="class"` strategy
- Manual toggle button (Sun/Moon icon) in sidebar footer
- Respects system preference as initial default

### Per-Page Redesign (priority order)

**1. Chat** (highest priority — primary user surface)
- Redesigned message bubbles: user messages right-aligned with accent bg, assistant messages left with surface bg
- Streaming: animated cursor (blinking caret) during token stream
- Inline citation chips: `Badge` with source title, clickable to expand full citation in `Popover`
- Confidence badge: colored `Badge` (green/yellow/red by score) + expandable popover showing 5-signal breakdown
- Meta-reasoning status: small `Badge` or `Spinner` indicator during research phases (status events)
- Stage status breadcrumb: shows current graph node during streaming (from `status` events)
- Empty state: centered illustration + prompt suggestions when no messages
- Clarification interrupt: styled card with CTA button when `clarification` event fires
- ChatSidebar (collection/model selector): redesigned as `Sheet` or inline panel, using shadcn `Select`
- Message actions: copy button on hover per assistant message

**2. Collections**
- Card grid layout: shadcn `Card` components, 2-col at `md`, 3-col at `lg`
- Stats chips on each card: document count, chunk count, embedding model (as `Badge`)
- Quick actions: kebab `DropdownMenu` per card (delete, view docs)
- Search/filter input at top of page
- Loading skeleton: `Skeleton` cards while fetching
- Empty state with CTA to create first collection
- CreateCollectionDialog: migrated to shadcn `Dialog` + `Input` + `Select`

**3. Documents (`/documents/[id]`)**
- Two-column layout: file list (left) + chunk preview panel (right, `ScrollArea`)
- DocumentUploader: redesigned drop zone with visual drag-over state using react-dropzone
- Upload progress: `Progress` bar per file during ingestion job polling
- DocumentList: `Table` component (shadcn) with status badges
- Ingestion status: `Badge` variants (pending/processing/complete/failed)

**4. Settings**
- Grouped with shadcn `Tabs`: "Providers", "Models", "Inference", "System"
- ProviderHub: each provider as a `Card` with connection status indicator (dot + text)
- API key input: `Input` with show/hide toggle, `Button` to save/delete
- Model selector: shadcn `Select` with optgroup-style grouping
- Toast feedback: migrate from custom `Toast.tsx` → shadcn `Sonner`

**5. Observability**
- Health status row: 3 `Card` components (SQLite, Qdrant, Ollama) with colored status dots
- Stage timings chart: horizontal stacked bar chart per stage
  (recharts `BarChart`, horizontal orientation, one bar per pipeline stage, tooltip showing ms)
  Requirement: bars ordered retrieval → rerank → compress → meta-reasoning → inference,
  tooltip on hover showing stage name + latency ms, distinct color per stage, dark bg chart.
- Trace table: shadcn `Table` with pagination, filterable by session/collection/confidence range
- Trace detail: click row → `Sheet` slide-in showing full trace detail (stage timings, citations, confidence breakdown)
- Latency trend: line chart (recharts) — p50/p95 latency over last N queries
- Confidence distribution: bar histogram (recharts) — count per confidence decile

### Global / Cross-Cutting
- Cmd+K command palette: shadcn `Command` component in `Dialog`, global keyboard shortcut
  - Commands: navigate to pages, create collection, clear chat, toggle dark mode
- Keyboard navigation: all interactive elements reachable via Tab; Esc closes any open modal/sheet
- Responsive: all pages usable at 375px (mobile), 768px (tablet), 1280px+ (desktop)
- `Sonner` toasts replace custom `Toast.tsx` for all feedback messages
- `Tooltip` (shadcn) wraps all icon-only buttons with accessible labels
- `Skeleton` loaders for every async-loaded section
- Breadcrumb at top of content area showing current page + context (e.g., "Documents / collection-name")

---

## shadcn/ui Components Required

> Verified against shadcn-ui MCP — all exist in registry.

| Component | Used in |
|-----------|---------|
| `sidebar` | Global layout — replaces Navigation.tsx |
| `sheet` | Mobile nav, trace detail drawer |
| `command` | Cmd+K palette |
| `badge` | Citations, confidence, status indicators, model tags |
| `skeleton` | All loading states |
| `card` | Collections grid, health status, provider cards |
| `button` | Everywhere |
| `input` | Forms, search, API key fields |
| `textarea` | Chat input |
| `select` | Model selector, collection selector, settings |
| `tabs` | Settings page sections |
| `table` | Trace table, document list |
| `dialog` | Create collection, Cmd+K wrapper |
| `popover` | Citation expansion, confidence breakdown |
| `tooltip` | Icon buttons |
| `scroll-area` | Chat messages, document chunk preview |
| `progress` | Ingestion upload progress |
| `separator` | Sidebar sections, settings groups |
| `dropdown-menu` | Collection card actions |
| `sonner` | Toast notifications (replaces Toast.tsx) |
| `breadcrumb` | Page header context |

---

## Non-Goals / Out of Scope

- **No backend changes** — no new API endpoints, no schema migrations
- **No new routes** — same 5 routes (`/chat`, `/collections`, `/documents/[id]`, `/settings`, `/observability`)
- **No hook rewrites** — `lib/api.ts` and all 5 hooks stay unchanged
- **No new test files** — existing Playwright + Vitest tests updated only if they break
- **No authentication** — intentional design decision (trusted local network model)
- **No i18n / localization**
- **No animations library** — CSS transitions only (Tailwind `transition-*`)

---

## Key Constraints

- **Tailwind CSS 4** — use `@theme` in `globals.css` for design tokens (NOT `tailwind.config.ts`)
- **Next.js 16 App Router** — layout changes go in `app/layout.tsx`, no `pages/` directory
- **No breaking API contracts** — `lib/types.ts` shape must not change
- **next-themes** requires `suppressHydrationWarning` on `<html>` to prevent flash
- **shadcn `Sidebar`** is a complex compound component — plan its integration carefully;
  it requires a `SidebarProvider` wrapping the layout
- **Existing Radix primitives** (`@radix-ui/react-tooltip`, `dialog`, `select`) are already
  installed — shadcn wraps these; no version conflicts expected but verify during plan phase
- **`mcp-chart` note**: mcp-chart was unavailable during this design session.
  The Observability page chart requirements above are based on recharts (already installed)
  and horizontal bar chart patterns verified against the existing `StageTimingsChart.tsx`
  component. Do NOT require chart library changes.

---

## MCP Usage Instructions

Use the following MCP servers throughout this specification task. Each has a defined
role — do not skip the mandatory ones.

### Mandatory (always use)

**serena** — Use for all codebase exploration before writing any requirement.
- `get_symbols_overview` to map the existing frontend structure (pages, components, hooks)
- `find_symbol` to locate specific components before defining what needs to change
- `find_referencing_symbols` to understand what depends on components you plan to redesign
- Do NOT describe current behavior from memory — always verify with serena first

**gitnexus** — Use to understand architecture, assess impact, and trace execution flows.
- `gitnexus_query` to find execution flows related to frontend data fetching, streaming, and API calls
- `gitnexus_context` on any frontend symbol you plan to redesign (especially chat, observability)
- `gitnexus_impact` before declaring any component as "to be replaced" — surface all dependents
- Report blast radius for every component marked for replacement in the spec

**sequential-thinking** — Use to structure your reasoning before writing each major section.
- Activate before drafting User Stories, Functional Requirements, and Success Criteria
- Use to work through trade-offs (e.g. phased rollout vs full rewrite, new component vs extend existing)
- Use when a requirement feels ambiguous — think through edge cases step by step before writing

### Contextual (use when the task calls for it)

**shadcn-ui** — Use when writing requirements that involve specific UI components.
- `list_shadcn_components` once at the start to inventory what is available
- `get_component_details` before writing any FR that references a shadcn component by name
- `get_component_examples` to verify a component actually covers the use case before requiring it
- Do not require a shadcn component in a FR without first confirming it exists and fits

**context7** — Use when writing requirements that depend on framework-specific capabilities.
- Resolve Next.js 16, Tailwind CSS 4, React 19, or next-themes before referencing their APIs in FRs
- Use `query-docs` to confirm that a feature exists in the specific version in use
  (e.g. Next.js 16 app router, Tailwind 4 `@theme` syntax) before making it a requirement
- Especially important for: dark mode (`next-themes`), CSS design tokens (Tailwind 4 `@theme`),
  and streaming (React 19)

**mcp-chart** — Use when specifying the Observability page chart requirements.
- Attempt `generate_waterfall_chart` or `generate_bar_chart` to prototype stage timing visuals
- If mcp-chart is unavailable, use the recharts-based requirements already defined in this
  context file and proceed without chart generation
- Do not block spec generation on mcp-chart availability

---

## Instructions for `speckit.specify` Agent

### Mandatory clarification questions (ask before writing FRs)

1. **Palette choice** (required): Present all 4 palette options (A–D) with their names and
   1-sentence descriptions. Ask the user to choose one, or describe a custom direction.
   Do not write the design token FR until this is answered.

2. **Sidebar behavior preference**: Should the sidebar default to expanded (with labels)
   or icon-only on desktop? Should user preference persist across sessions (localStorage)?

3. **Chat history persistence**: Should the current session's chat history survive a page
   refresh (localStorage/sessionStorage), or is ephemeral-only acceptable for spec-18?

4. **Animation budget**: Framer Motion or CSS-only transitions? (CSS-only is the default
   per non-goals, but confirm with user before writing the FR.)

### Sections to generate in spec.md

1. **Overview** — 2-3 paragraphs: what, why, key outcomes
2. **User Stories** (5-7): developer persona, using Embedinator daily
   - Must include: first-time setup, daily chat usage, document management, observability review, settings configuration
3. **Functional Requirements** (20-30): organized by area
   - Area 1: Layout & Navigation (sidebar, dark mode toggle, Cmd+K, breadcrumbs, mobile)
   - Area 2: Design Token System (CSS vars, color tokens, typography scale, spacing)
   - Area 3: shadcn/ui Foundation (component.json, `components/ui/`, Sonner setup)
   - Area 4: Chat Page (message bubbles, streaming indicators, citations, confidence, meta-reasoning, empty state)
   - Area 5: Collections Page (card grid, search, skeletons, empty state, dialog)
   - Area 6: Documents Page (two-column layout, upload zone, progress, table)
   - Area 7: Settings Page (tabs, provider hub, model selector)
   - Area 8: Observability Page (health cards, stage timing chart, trace table, trace detail)
   - Area 9: Cross-Cutting (keyboard nav, toasts, tooltips, responsive, skeletons)
4. **Non-Functional Requirements** (3-5): performance (no layout shift on theme change),
   accessibility (WCAG 2.1 AA for all interactive elements), bundle size (no new chart library)
5. **Success Criteria** (6-8): verifiable, binary pass/fail
   - Must include: shadcn sidebar renders and collapses, dark/light toggle persists, all 5 pages render without hydration errors, chat streaming renders tokens in real time, confidence badge shows correct color tier, Cmd+K opens and navigates
6. **Out of Scope** — bullet list
7. **Component Migration Map** — table: existing component → shadcn equivalent or "retained + restyled"

### Writing quality standards

- Every FR must be verifiable: "The sidebar MUST collapse to icon-only when the user clicks
  the collapse toggle" — not "The sidebar should look good"
- Cite the specific shadcn component for every UI requirement that uses one
- Use RFC 2119 keywords (MUST, SHOULD, MAY) consistently
- Keep FRs atomic: one observable behavior per requirement
