# A5 — Frontend Architect: Degraded States & Onboarding

## Role & Mission

You are the frontend architect responsible for implementing the backend status provider, degraded state banner, chat input gating, and first-run onboarding experience. Your work makes the frontend gracefully handle backend startup delays.

## FR Ownership

FR-046, FR-047, FR-048, FR-049

## Task Ownership

T061 through T068 (Phase 6: Frontend Degraded States)

### Tasks

- **T061** [P]: Add `BackendStatus` type to `frontend/lib/types.ts`: `type BackendStatus = "unreachable" | "degraded" | "ready"` and `BackendHealthResponse` interface matching the enhanced `/api/health` response (FR-046)
- **T062**: Create `frontend/components/BackendStatusProvider.tsx`: React context using SWR to poll `/api/health` with adaptive intervals (5s unreachable, 10s degraded, 30s ready). Export `useBackendStatus()` hook returning `{ state, services }`. Handle fetch errors as `unreachable` (FR-046)
- **T063**: Create `frontend/components/StatusBanner.tsx`: non-dismissible banner with contextual messages per degraded state. Use `role="status"` and `aria-live="polite"`. Use existing design tokens (CSS variables), not hardcoded colors. Auto-hide when status becomes `ready` (FR-047)
- **T064**: Modify `frontend/app/layout.tsx`: wrap `SidebarLayout` with `BackendStatusProvider` inside `ThemeProvider`. Provider order: `ThemeProvider > BackendStatusProvider > SidebarLayout` (FR-046)
- **T065**: Modify `frontend/components/SidebarLayout.tsx`: import and render `StatusBanner` between the `<header>` and `<main>` inside `SidebarInset` (FR-047)
- **T066**: Modify `frontend/components/ChatInput.tsx`: import `useBackendStatus()`, add backend status to `canSend` check (disabled when not `ready`), change placeholder to contextual: "Waiting for backend to start..." / "AI models are still loading..." / "Vector database is starting..." / current placeholder when ready (FR-048)
- **T067**: Modify `frontend/components/ChatPanel.tsx`: when zero collections exist (check via existing SWR collections hook), replace the standard empty state with an onboarding card showing: (1) "Create a collection" button linking to `/collections`, (2) "Upload documents" with supported formats, (3) "Ask questions" explanation. When collections exist, show standard starter questions (FR-049)
- **T068**: Verify `cd frontend && npm run build && npm run test` passes. Verify components are wired correctly.

## Files to CREATE

| File | Purpose |
|------|---------|
| `frontend/components/BackendStatusProvider.tsx` | React context provider for backend health polling via SWR |
| `frontend/components/StatusBanner.tsx` | Non-dismissible degraded state banner component |

## Files to MODIFY

| File | Changes |
|------|---------|
| `frontend/lib/types.ts` | Add `BackendStatus` type and `BackendHealthResponse` interface |
| `frontend/app/layout.tsx` | Wrap `SidebarLayout` with `BackendStatusProvider` (after ThemeProvider) |
| `frontend/components/SidebarLayout.tsx` | Insert `StatusBanner` between header and main in SidebarInset |
| `frontend/components/ChatInput.tsx` | Import `useBackendStatus()`, add status gating, contextual placeholder |
| `frontend/components/ChatPanel.tsx` | Add first-run onboarding card when zero collections |

## Files NEVER to Touch

- `Makefile` — SC-010
- `frontend/package.json` — no new npm packages
- `frontend/next.config.ts` — owned by A2 (Wave 1, already done)
- `frontend/lib/api.ts` — owned by A2
- `frontend/app/healthz/route.ts` — owned by A2
- `frontend/app/page.tsx` — owned by A2
- Any `backend/**` files
- Any `tests/**` files

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Section 7 (Frontend Degraded State Handling)
3. `specs/019-cross-platform-dx/spec.md` — FR-046 through FR-049, User Stories 6 and 7
4. `specs/019-cross-platform-dx/tasks.md` — T061 through T068
5. `specs/019-cross-platform-dx/data-model.md` — Section 4 (Frontend Backend Status)
6. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — risk gotchas

## Key Gotchas

1. **Use SWR for polling** — SWR is already a dependency (`frontend/package.json`). Use `useSWR` with `refreshInterval` set dynamically based on the current backend status. Do NOT add a new polling library.
2. **Adaptive polling intervals** — 5s when unreachable, 10s when degraded, 30s when ready. The data-model.md has the exact table.
3. **Design tokens, not hardcoded colors** — The app uses Tailwind CSS 4 with CSS variables (shadcn/ui theme system). Use classes like `bg-destructive/10 text-destructive` for error states, `bg-warning/10 text-warning` for warnings, etc. Do NOT hardcode hex colors or use plain Tailwind colors like `bg-red-500`.
4. **Accessibility** — StatusBanner MUST use `role="status"` and `aria-live="polite"` for screen reader announcements.
5. **No new packages** — Use only existing dependencies: SWR, React, lucide-react for icons if needed.
6. **Provider order in layout.tsx** — Must be `ThemeProvider > BackendStatusProvider > SidebarLayout`. The `BackendStatusProvider` needs to be a client component ("use client" directive). The `StatusBanner` consumes the context.
7. **BackendStatusProvider is "use client"** — Since it uses hooks (SWR, useState), it MUST have the `"use client"` directive.
8. **Onboarding card (T067)** — Check the existing collections hook/fetch pattern in ChatPanel.tsx. When `collections.length === 0`, show the onboarding card. When collections exist, show the existing empty state.
9. **Chat input gating** — The `ChatInput` component likely already has a `canSend` or disabled check. Add backend status to that condition without breaking the existing collection-selection check.
10. **Status derivation** — Map backend responses to frontend status per data-model.md Section 4: fetch error → `unreachable`, HTTP 503 → `degraded`, `status: "starting"` → `degraded`, `status: "degraded"` → `degraded`, `status: "healthy"` → `ready`.

## Verification Commands

```bash
# Frontend builds
cd frontend && npm run build && echo "PASS: frontend build" || echo "FAIL"

# Frontend tests pass
cd frontend && npm run test && echo "PASS: frontend tests" || echo "FAIL"

# Components wired correctly
grep -q 'BackendStatusProvider' frontend/app/layout.tsx && echo "PASS: provider in layout" || echo "FAIL"
grep -q 'StatusBanner' frontend/components/SidebarLayout.tsx && echo "PASS: banner in sidebar" || echo "FAIL"
grep -q 'useBackendStatus' frontend/components/ChatInput.tsx && echo "PASS: status gating in chat" || echo "FAIL"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
