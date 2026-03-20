# A4 — Wave 3 — frontend-architect (Sonnet)

## CALLSIGN: COLLECTIONS SPECIALIST

## MISSION

You are a Wave 3 frontend-architect running in PARALLEL with A3, A5, A6, A7. You own the Collections page. Your mission: transform the collections view into a responsive card grid with search/filter, skeleton loading, empty state, and a polished create-collection dialog using shadcn/ui components. Migrate all hard-coded gray classes to design tokens.

Do NOT start until the orchestrator signals that Wave 2 gate passed.

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T028–T032
3. `specs/018-ux-redesign/spec.md` — FR-020 through FR-024
4. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide

Read the CURRENT source before modifying:
- `frontend/components/CollectionList.tsx`
- `frontend/components/CollectionCard.tsx`
- `frontend/components/CollectionStats.tsx`
- `frontend/components/CreateCollectionDialog.tsx`
- `frontend/app/collections/page.tsx`

## ASSIGNED TASKS

T028 through T032 (5 tasks). T028–T031 are marked [P] — they touch different files and can be done in any order.

---

**T028** — Restyle `frontend/components/CollectionList.tsx` (FR-020, FR-021, FR-023)

- Responsive grid: `grid-cols-1 md:grid-cols-2 lg:grid-cols-3` with `gap-[var(--space-card-gap)]`
- Search/filter input at top: shadcn `Input` with search icon, filters by collection name/description
- Skeleton loading: render shadcn `Skeleton` card placeholders (3-wide on desktop) while `isLoading`
- Empty state: centered message + prominent shadcn `Button` CTA "Create your first collection"
- Migrate ALL `gray-*` classes (~9 instances) to tokens. No `dark:` variants.

**T029** — Restyle `frontend/components/CollectionCard.tsx` (FR-020, FR-022)

- Use shadcn `Card` + `CardHeader` + `CardContent`
- Stats as shadcn `Badge` variants: document count, chunk count, embedding model
- Actions via shadcn `DropdownMenu`: "View Documents" (navigates to `/documents/[id]`), "Delete" (opens confirmation `Dialog`)
- Migrate ALL `gray-*` classes (~12 instances) to tokens. No `dark:` variants.

**T030** — Restyle `frontend/components/CreateCollectionDialog.tsx` (FR-024)

- Replace raw Radix Dialog/Select with shadcn `Dialog` + `Input` + `Select`
- Fields: name (required), description (optional), embedding model (selectable), chunk profile (selectable)
- Migrate ALL `gray-*` classes (~25+ instances — second largest migration). No `dark:` variants.

**T031** — Restyle `frontend/components/CollectionStats.tsx`

- Migrate all `gray-*` classes (~12 instances) to tokens. No `dark:` variants.

**T032** — Restyle `frontend/app/collections/page.tsx`

- Integrate restyled components
- Verify responsive grid at 375px, 768px, 1280px in both dark and light themes

---

## RULES OF ENGAGEMENT

- Do NOT modify any Chat, Document, Settings, or Observability component.
- Do NOT modify `frontend/app/layout.tsx`.
- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts`.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- After completing: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white\|dark:' frontend/components/Collection*.tsx frontend/components/CreateCollectionDialog.tsx` returns ZERO results.

## COMPLETION SIGNAL

"A4 COMPLETE. Collections page redesigned — card grid, search, skeletons, dialog. Zero hard-coded gray classes."
