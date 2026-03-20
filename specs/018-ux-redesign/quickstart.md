# Quickstart: UX/UI Redesign — "Intelligent Warmth"

**Phase 1 output** | **Date**: 2026-03-19

## Prerequisites

- Node.js LTS (for `npm` commands)
- The frontend dev server running: `cd frontend && npm run dev`
- Existing backend running (for API data): `make up` or `docker compose up -d`

## Getting Started After Phase 0 (Foundation)

After Phase 0 completes, the following is available:

```bash
# Verify shadcn components installed
ls frontend/components/ui/
# Should show: sidebar.tsx, badge.tsx, card.tsx, skeleton.tsx, command.tsx, ...

# Verify new dependencies
cd frontend && npm ls next-themes lucide-react class-variance-authority

# Verify build
npm run build
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `frontend/app/globals.css` | Design tokens (Obsidian Violet palette) |
| `frontend/app/layout.tsx` | Root layout (ThemeProvider + SidebarProvider + Toaster) |
| `frontend/components/SidebarNav.tsx` | Main navigation sidebar |
| `frontend/components/ThemeToggle.tsx` | Dark/light mode toggle |
| `frontend/components/CommandPalette.tsx` | Cmd+K command palette |
| `frontend/components/ui/*.tsx` | shadcn/ui primitives |
| `frontend/lib/utils.ts` | `cn()` class name utility |
| `frontend/hooks/useChatStorage.ts` | localStorage chat persistence |
| `frontend/component.json` | shadcn configuration |

## Design Token Usage

All color references use CSS custom properties. Never use hard-coded gray/neutral classes.

```tsx
// CORRECT — uses design tokens (dark mode handled automatically)
<div className="bg-[var(--color-surface)] text-[var(--color-text-primary)] border-[var(--color-border)]">

// WRONG — hard-coded colors (breaks dark mode)
<div className="bg-white text-gray-900 border-gray-200">

// CORRECT — use cn() for conditional classes
import { cn } from "@/lib/utils";
<div className={cn("rounded-lg", isActive && "bg-[var(--color-accent)]")}>

// WRONG — template literal class merging
<div className={`rounded-lg ${isActive ? "bg-blue-600" : ""}`}>
```

## Theme Toggle Testing

```bash
# Start dev server
cd frontend && npm run dev

# Open http://localhost:3000
# 1. Click Sun/Moon toggle in sidebar footer
# 2. Verify all colors switch
# 3. Refresh page — theme should persist
# 4. Open DevTools → Elements → <html> should have class="dark" or no dark class
```

## Adding a New shadcn Component

```bash
cd frontend
npx shadcn@latest add [component-name]
# Component is added to components/ui/[component-name].tsx
```

## Running Tests

```bash
# Unit tests
cd frontend && npm run test

# E2E tests (requires dev server running)
cd frontend && npm run test:e2e

# Build check
cd frontend && npm run build
```
