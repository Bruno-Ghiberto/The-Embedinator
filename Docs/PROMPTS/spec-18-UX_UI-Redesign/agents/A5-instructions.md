# A5 — Wave 3 — frontend-architect (Sonnet)

## CALLSIGN: DOCUMENTS SPECIALIST

## MISSION

You are a Wave 3 frontend-architect running in PARALLEL with A3, A4, A6, A7. You own the Documents page. Your mission: implement a two-column layout (desktop) / stacked layout (mobile), restyle the document list with shadcn Table and status badges, and enhance the upload zone with shadcn Progress tracking. This is the smallest Wave 3 assignment (3 tasks).

Do NOT start until the orchestrator signals that Wave 2 gate passed.

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T033–T035
3. `specs/018-ux-redesign/spec.md` — FR-025 through FR-027
4. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide

Read the CURRENT source before modifying:
- `frontend/components/DocumentList.tsx`
- `frontend/components/DocumentUploader.tsx`
- `frontend/app/documents/[id]/page.tsx`

## ASSIGNED TASKS

T033 through T035 (3 tasks). T033–T034 are marked [P] — different files.

---

**T033** — Restyle `frontend/components/DocumentList.tsx` (FR-027)

- Use shadcn `Table` (TableHeader, TableBody, TableRow, TableCell)
- Status badges using shadcn `Badge` with variants:
  - `pending` → outline badge
  - `processing` → default badge with spinner
  - `complete` → success-colored badge (use `--color-success`)
  - `failed` → destructive-colored badge (use `--color-destructive`)
- Migrate ALL `gray-*` classes (~14 instances) to tokens. No `dark:` variants.

**T034** — Restyle `frontend/components/DocumentUploader.tsx` (FR-026)

- Enhance drag-and-drop zone: on drag-over, change border to accent color + subtle background tint
- Use shadcn `Progress` component for ingestion job tracking (replace raw progress bar)
- react-dropzone is already installed — keep using it
- Migrate ALL `gray-*` classes (~9 instances) to tokens. No `dark:` variants.

**T035** — Restyle `frontend/app/documents/[id]/page.tsx` (FR-025)

- Two-column layout on desktop (>= 768px): file list table on left, chunk preview with shadcn `ScrollArea` on right
- Stacked vertically on mobile (< 768px): file list on top (full width), chunk preview below (full width)
- Use CSS grid or flex with responsive breakpoints
- Migrate ALL `gray-*` classes (~4 instances) to tokens. No `dark:` variants.

---

## RULES OF ENGAGEMENT

- Do NOT modify any Chat, Collection, Settings, or Observability component.
- Do NOT modify `frontend/app/layout.tsx`.
- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts`.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- After completing: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white\|dark:' frontend/components/Document*.tsx frontend/app/documents/` returns ZERO results.

## COMPLETION SIGNAL

"A5 COMPLETE. Documents page redesigned — two-column layout, upload progress, status badges. Zero hard-coded gray classes."
