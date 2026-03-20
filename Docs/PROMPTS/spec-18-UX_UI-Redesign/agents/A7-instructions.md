# A7 — Wave 3 — frontend-architect (Sonnet)

## CALLSIGN: OBSERVABILITY SPECIALIST

## MISSION

You are a Wave 3 frontend-architect running in PARALLEL with A3–A6. You own the Observability page — the page with the LARGEST color migration burden in the entire spec. This page has ZERO existing dark mode support (no `dark:` classes anywhere). Every single color class is hard-coded light mode. Your mission: restyle health cards, charts, the trace table, add a trace detail Sheet panel, and migrate ALL ~75+ hard-coded color classes across 7 files.

Do NOT start until the orchestrator signals that Wave 2 gate passed.

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T040–T044
3. `specs/018-ux-redesign/spec.md` — FR-031 through FR-034
4. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide (you need this most)

Read the CURRENT source of ALL your files before modifying any:
- `frontend/components/HealthDashboard.tsx` (~8 gray classes)
- `frontend/components/StageTimingsChart.tsx` (recharts, needs token-based colors)
- `frontend/components/TraceTable.tsx` (~30+ gray classes — LARGEST single file)
- `frontend/components/LatencyChart.tsx` (~1 gray class)
- `frontend/components/ConfidenceDistribution.tsx` (~1 gray class)
- `frontend/components/MetricsTrends.tsx` (~12 gray classes)
- `frontend/app/observability/page.tsx` (~15 gray classes)

## ASSIGNED TASKS

T040 through T044 (5 tasks). T040–T043 are marked [P] — different files.

---

**T040** — Restyle `frontend/components/HealthDashboard.tsx` (FR-031)

- Use shadcn `Card` per service (SQLite, Qdrant, Ollama)
- Colored status dot:
  - `healthy` → green dot (`bg-[var(--color-success)]`)
  - `degraded` → yellow dot (`bg-[var(--color-warning)]`)
  - `down` → red dot (`bg-[var(--color-destructive)]`)
  - `unknown`/null → gray dot (`bg-[var(--color-text-muted)]`)
- Display latency in milliseconds
- Migrate ALL gray classes (~8 instances). No `dark:` variants.

**T041** — Restyle `frontend/components/StageTimingsChart.tsx` (FR-032)

- This is a recharts `BarChart` (horizontal orientation) — keep using recharts
- Use token-based colors per stage (derive from CSS vars or define 5 distinct colors that work in both themes):
  - retrieval → accent variant
  - rerank → success variant
  - compress → warning variant
  - meta-reasoning → a purple/violet shade
  - inference → a secondary shade
- Tooltip on hover: show stage name + latency in ms
- Chart background: transparent (inherits from container). No hard-coded `bg-white`.
- The recharts components (Bar, Tooltip, etc.) accept `fill` props — use CSS variable values or compute at render time via `getComputedStyle`.

**T042** — Restyle `frontend/components/TraceTable.tsx` (FR-033, FR-034)

**WARNING**: This is the LARGEST migration — ~30+ hard-coded gray classes.

- Use shadcn `Table` (TableHeader, TableBody, TableRow, TableCell, TableHead)
- Add pagination controls (Previous/Next buttons with shadcn `Button`)
- Add filter inputs: session ID (shadcn `Input`), confidence range (min/max shadcn `Input`)
- Add trace detail `Sheet` (slide-out panel from the right):
  - Triggered by clicking a trace row
  - Shows: query text, response metadata, stage timings, citations, confidence breakdown, reasoning steps
  - Uses shadcn `Sheet` + `SheetContent` + `SheetHeader` + `SheetTitle`
- Migrate ALL ~30+ gray classes to tokens. This includes:
  - Table headers (`bg-gray-50`, `text-gray-600`)
  - Table rows (`border-gray-100`, `hover:bg-gray-50`, `text-gray-900`)
  - Expanded detail rows (`bg-gray-50`, `text-gray-500/600/700`)
  - Pagination controls (`border-gray-300`, `hover:bg-gray-50`)
  - Filter input (`border-gray-300`)
- Remove all hard-coded `bg-white` instances.

**T043** — Restyle chart components (3 files)

Restyle these 3 independent files — all are recharts-based:

1. `frontend/components/LatencyChart.tsx` — migrate `text-gray-700` class. Ensure chart renders in both themes.
2. `frontend/components/ConfidenceDistribution.tsx` — migrate `text-gray-700` class. Ensure chart renders in both themes.
3. `frontend/components/MetricsTrends.tsx` — migrate ALL ~12 gray classes. This component has tab switchers, chart containers, and empty states — all with hard-coded `gray-*` colors.

For all recharts components: ensure chart grid lines, axis labels, and tooltips use token-compatible colors.

**T044** — Restyle `frontend/app/observability/page.tsx` (integration)

- Migrate ALL ~15 hard-coded gray classes (headings, containers, loading states, chart wrappers)
- This page uses `dynamic()` imports for chart components — preserve that pattern
- Verify all charts render correctly in both dark and light mode
- Verify health cards show correct status dots

---

## RULES OF ENGAGEMENT

- Do NOT modify any Chat, Collection, Document, or Settings component.
- Do NOT modify `frontend/app/layout.tsx`.
- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts`.
- Keep using recharts — do NOT introduce any new charting library (NFR-003).
- Use `cn()` from `@/lib/utils` for all className conditionals.
- For recharts colors: you may need to read CSS var values at render time via `getComputedStyle(document.documentElement).getPropertyValue('--color-accent')` or define a color map constant.
- After completing: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white\|dark:' frontend/components/Health*.tsx frontend/components/Trace*.tsx frontend/components/*Chart.tsx frontend/components/MetricsTrends.tsx frontend/app/observability/` returns ZERO results.

## COMPLETION SIGNAL

"A7 COMPLETE. Observability page redesigned — health cards, charts, trace table + Sheet detail. Zero hard-coded gray classes across all 7 files."
