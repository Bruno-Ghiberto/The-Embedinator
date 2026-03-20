# A8 — Wave 4 — quality-engineer (Sonnet)

## CALLSIGN: QA COMMANDER

## MISSION

You are the Wave 4 quality-engineer. You run ALONE after ALL Wave 3 agents have completed. Your mission has two phases: (1) create the Command Palette and Breadcrumb components to complete US1, and (2) execute a comprehensive QA audit covering accessibility, responsiveness, dark/light consistency, build verification, and test suite health. You are the final gate before spec-18 can be marked complete.

Do NOT start until the orchestrator signals that ALL Wave 3 agents (A3–A7) have completed.

## INTEL — Read Before Starting

1. Your instruction file (this file)
2. `specs/018-ux-redesign/tasks.md` — your tasks: T045–T057 (+ T053b, T054b)
3. `specs/018-ux-redesign/spec.md` — FR-004, FR-005, FR-035–FR-038, NFR-001–NFR-004, SC-001–SC-008
4. `specs/018-ux-redesign/contracts/ui-components.md` — CommandPalette and PageBreadcrumb contracts
5. `Docs/PROMPTS/spec-18-UX_UI-Redesign/18-implement.md` — Color Migration Guide, SC verification table

Read `frontend/app/layout.tsx` to understand current structure (it has been modified by A1 and A6).

## ASSIGNED TASKS

T045 through T057 + T053b + T054b (15 tasks total).

---

### Part 1: Command Palette + Breadcrumbs (FR-004, FR-005)

**T045** — Create `frontend/components/CommandPalette.tsx` (FR-004)

`"use client"` component. Contract in `contracts/ui-components.md`.

- Use shadcn `Command` inside a shadcn `Dialog`
- Register global keyboard listener: `Cmd+K` (macOS) / `Ctrl+K` (Windows/Linux)
- Open dialog on shortcut, close on Escape or selection
- Command groups:
  - **Navigation**: Chat, Collections, Documents, Settings, Observability (use `useRouter().push()`)
  - **Actions**: "Create Collection" (TODO: trigger CreateCollectionDialog open state), "Clear Chat" (call `clearChat()` from useChatStorage), "Toggle Dark Mode" (call `setTheme()` from next-themes)
- Search input filters commands by label
- Each command shows its label + optional keyboard shortcut hint

**T046** — Create `frontend/components/PageBreadcrumb.tsx` (FR-005)

`"use client"` component. Uses shadcn `Breadcrumb` + `BreadcrumbList` + `BreadcrumbItem` + `BreadcrumbLink` + `BreadcrumbSeparator`.

- Derives breadcrumb items from `usePathname()`:
  - `/chat` → "Chat"
  - `/collections` → "Collections"
  - `/documents/abc123` → "Documents" / "abc123"
  - `/settings` → "Settings"
  - `/observability` → "Observability"
- Optional `items` prop for custom overrides (e.g., showing collection name instead of ID)

**T047** — Add CommandPalette to `frontend/app/layout.tsx`

Read current layout.tsx (already modified by A1 and A6). Add:
```tsx
import CommandPalette from "@/components/CommandPalette";
```
Place `<CommandPalette />` as sibling inside ThemeProvider, after Toaster:
```tsx
<Toaster />
<CommandPalette />
```

**T048** — Add PageBreadcrumb to content area

Either add to layout.tsx (inside SidebarInset, before `<main>`) or to each page file. Preferred: add to SidebarInset in layout.tsx so all pages get it automatically:
```tsx
<SidebarInset>
  <header className="flex items-center px-[var(--space-page)] py-3 border-b border-[var(--color-border)]">
    <SidebarTrigger />
    <PageBreadcrumb />
  </header>
  <main>{children}</main>
</SidebarInset>
```

---

### Part 2: Cross-Cutting Audit (FR-035–FR-038, NFR-001–NFR-004)

**T049** — Tooltip audit (FR-035)

Find ALL icon-only buttons across the entire frontend. Each MUST have a shadcn `Tooltip` wrapper with a descriptive label. Check:
- Sidebar collapse toggle
- Theme toggle (Sun/Moon)
- Copy-to-clipboard button (chat)
- Card action buttons (collections)
- Filter/pagination controls
- Any other icon-only interactive element

**T050** — Skeleton audit (FR-038)

Verify every async-loaded section has animated skeleton placeholders:
- Collections grid loading → Skeleton cards
- Documents list loading → Skeleton table rows
- Trace table loading → Skeleton rows
- Settings form loading → Skeleton form
- Health dashboard loading → Skeleton cards
- Chat history loading (from localStorage) → Skeleton messages

If any are missing, add them.

**T051** — Keyboard navigation audit (FR-037)

Tab through ALL interactive elements on ALL 5 pages. Verify:
- Tab order is logical (left→right, top→bottom)
- All buttons, links, inputs are reachable
- Focus indicators are visible
- All Dialogs close on Escape
- All Sheets close on Escape
- All Popovers close on Escape
- Sidebar closes on Escape (mobile)
- Command palette closes on Escape

**T052** — Responsive audit (FR-036)

Check all 5 pages at THREE breakpoints:
- 375px (mobile)
- 768px (tablet)
- 1280px (desktop)

No content should be inaccessible at any breakpoint. Verify:
- Sidebar hidden at mobile, hamburger visible
- Collections grid: 1-col mobile, 2-col tablet, 3-col desktop
- Documents: stacked mobile, two-column desktop
- Charts readable at all sizes
- No horizontal scrollbar on any page

**T053** — Dark/light mode audit (NFR-001)

Run this search from the `frontend/` directory:
```bash
grep -rn 'text-gray-\|bg-gray-\|border-gray-\|bg-white' components/ app/ --include='*.tsx' --include='*.ts' | grep -v node_modules | grep -v components/ui/
```

This MUST return ZERO results (excluding shadcn/ui primitives in `components/ui/`). If any results appear, fix them by replacing with design token equivalents.

Also check for any remaining `dark:` variant classes in non-ui components — these should have been removed since the token system handles dark mode automatically.

**T053b** — WCAG contrast ratio audit (NFR-002)

Verify these Obsidian Violet token pairs meet WCAG 2.1 AA contrast ratios:
- text-primary (#1e1b4b) on background (#faf9ff) — must be >= 4.5:1 for normal text
- text-primary (#f5f3ff) on background (#0d0c14) — dark mode
- text-muted (#6b52b5) on surface (#f4f0ff) — must be >= 4.5:1
- text-muted (#9785d4) on surface (#15122a) — dark mode
- accent (#7c3aed) on background (#faf9ff)
- accent (#a78bfa) on background (#0d0c14) — dark mode

Use a contrast checker tool or browser DevTools accessibility panel. Flag any pair below 4.5:1.

**T054** — Build verification

```bash
cd frontend && npm run build
```
MUST succeed with ZERO TypeScript errors and ZERO build errors.

**T054b** — Lighthouse performance audit (NFR-004)

Run Lighthouse audit (or equivalent) on all 5 pages. Verify:
- Initial meaningful content renders within 2 seconds
- Skeleton loaders appear within 200ms of page load
- Flag any page exceeding thresholds

**T055** — Unit test verification

```bash
cd frontend && npm run test
```
If tests fail due to component structure changes (e.g., Navigation → SidebarNav, Toast → Sonner), update the test files to match new component names/imports. The goal is ZERO new test failures — pre-existing failures are acceptable.

**T056** — E2E test verification

```bash
cd frontend && npm run test:e2e
```
If Playwright tests fail due to changed selectors or markup structure, update the selectors. The goal is ZERO new failures.

**T057** — Quickstart validation

Read `specs/018-ux-redesign/quickstart.md`. Verify:
- Setup steps are accurate (file paths exist, commands work)
- Token usage examples match actual token names
- Test commands work

---

## RULES OF ENGAGEMENT

- You MAY modify ANY frontend file for audit fixes (tooltips, skeletons, color class fixes).
- You MAY modify `frontend/app/layout.tsx` (adding CommandPalette and Breadcrumb).
- You MAY modify test files to fix broken imports/selectors.
- Do NOT modify `frontend/lib/types.ts` or `frontend/lib/api.ts` — ever.
- Do NOT introduce new npm dependencies.
- Use `cn()` from `@/lib/utils` for all className conditionals.
- Report EVERY audit finding, even if you fix it — the orchestrator needs the full picture.

## COMPLETION SIGNAL

Report to orchestrator with this structure:
```
A8 COMPLETE. Wave 4 finished.

Command Palette: [DONE/ISSUES]
Breadcrumbs: [DONE/ISSUES]
Tooltip audit: [X icon buttons found, Y had tooltips, Z added]
Skeleton audit: [X sections checked, Y had skeletons, Z added]
Keyboard nav: [PASS/FAIL — details]
Responsive: [PASS/FAIL — details]
Dark/light audit: [X remaining hard-coded classes found and fixed / ZERO]
Contrast audit: [X pairs checked, Y pass, Z fail]
Build: [PASS/FAIL]
Lighthouse: [PASS/FAIL — details]
Unit tests: [X pass, Y fail, Z fixed]
E2E tests: [X pass, Y fail, Z fixed]
Quickstart: [VALID/ISSUES]

SC Verification:
SC-001: [PASS/FAIL]
SC-002: [PASS/FAIL]
SC-003: [PASS/FAIL]
SC-004: [PASS/FAIL]
SC-005: [PASS/FAIL]
SC-006: [PASS/FAIL]
SC-007: [PASS/FAIL]
SC-008: [PASS/FAIL]
```
