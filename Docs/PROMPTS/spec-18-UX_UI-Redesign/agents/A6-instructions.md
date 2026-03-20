# A6 — Wave 3 — frontend-architect (Sonnet)

## CALLSIGN: SETTINGS SPECIALIST

## MISSION

You are a Wave 3 frontend-architect running in PARALLEL with A3, A4, A5, A7. You own the Settings page. Your mission: restructure settings into a tabbed interface, restyle provider cards with status indicators, and execute the Toast.tsx → Sonner migration. You are the ONLY Wave 3 agent that touches `layout.tsx` (to add the Sonner `<Toaster />`).

Do NOT start until the orchestrator signals that Wave 2 gate passed.

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T036–T039
3. `specs/018-ux-redesign/spec.md` — FR-028 through FR-030
4. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide

Read the CURRENT source before modifying:
- `frontend/components/ProviderHub.tsx`
- `frontend/components/Toast.tsx` (this gets DELETED)
- `frontend/app/settings/page.tsx`
- `frontend/app/layout.tsx` (read carefully — you only ADD the Toaster)

## ASSIGNED TASKS

T036 through T039 (4 tasks). Execute in ORDER — T036 MUST be done before T039.

---

**T036** — Add Sonner `<Toaster />` to `frontend/app/layout.tsx` (FR-030)

**CRITICAL**: This MUST be done BEFORE T039 (deleting Toast.tsx). If you delete Toast.tsx first, the settings page crashes.

Read `layout.tsx`. Add:
```tsx
import { Toaster } from "@/components/ui/sonner";
```

Place `<Toaster />` as a sibling INSIDE `ThemeProvider` but OUTSIDE `SidebarProvider`:
```tsx
<ThemeProvider attribute="class" defaultTheme="system" enableSystem>
  <SidebarProvider defaultOpen={true}>
    <SidebarNav />
    <SidebarInset><main>{children}</main></SidebarInset>
  </SidebarProvider>
  <Toaster />  {/* ← ADD THIS */}
</ThemeProvider>
```

Do NOT modify any other part of layout.tsx.

**T037** — Restyle `frontend/components/ProviderHub.tsx` (FR-029)

- Use shadcn `Card` per provider
- Status dot: green (`--color-success`) if `has_key` is true, gray (`--color-text-muted`) if not
- API key input: shadcn `Input` with a show/hide toggle button (eye/eye-off icons from lucide-react)
- Save/Delete buttons: shadcn `Button`
- Migrate ALL `gray-*` classes (~10 instances) to tokens. No `dark:` variants.

**T038** — Restyle `frontend/app/settings/page.tsx` (FR-028, FR-030)

Read the current file (it's the largest settings page with inline forms). Then:
- Restructure with shadcn `Tabs` + `TabsList` + `TabsTrigger` + `TabsContent`
- Tab sections: "Providers" (contains ProviderHub), "Models", "Inference", "System"
- Replace all `Toast` component usage with `toast()` function from `sonner`:
  ```tsx
  import { toast } from "sonner";
  // Instead of: setToast({ message: "Saved!", type: "success" })
  // Use: toast.success("Settings saved successfully")
  ```
- Migrate ALL `gray-*` classes (~20 instances) to tokens. No `dark:` variants.

**T039** — Delete `frontend/components/Toast.tsx`

After T036 and T038 are both complete, delete this file. It is fully replaced by Sonner.

Verify: `grep -r "Toast" frontend/app/settings/page.tsx` should show ONLY `toast()` function calls (from sonner), NOT the old `<Toast` component import.

---

## RULES OF ENGAGEMENT

- Do NOT modify any Chat, Collection, Document, or Observability component.
- In `layout.tsx`, ONLY add the `<Toaster />` import and element — do NOT change anything else.
- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts`.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- T036 BEFORE T039 — non-negotiable ordering.
- After completing: `grep -r 'text-gray-\|bg-gray-\|border-gray-\|bg-white\|dark:' frontend/components/ProviderHub.tsx frontend/app/settings/page.tsx` returns ZERO results.

## COMPLETION SIGNAL

"A6 COMPLETE. Settings page redesigned — tabs, provider cards, Sonner toasts. Toast.tsx deleted. Zero hard-coded gray classes."
