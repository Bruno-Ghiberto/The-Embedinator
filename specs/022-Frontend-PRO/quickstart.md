# Quickstart: Frontend PRO (Spec 022)

## Prerequisites

- Node.js LTS (22+)
- pnpm (package manager)
- Running backend (Docker Compose or local) — for chat/API testing
- Running Qdrant — for document search functionality

## Branch Setup

```bash
# Create feature branch from current work
git checkout 021-e2e-debug-verification
git checkout -b 022-frontend-pro
```

## Install New Dependencies

```bash
cd frontend

# New npm packages (only 3 new deps)
pnpm add react-markdown remark-gfm rehype-highlight

# New shadcn components (not yet installed)
pnpm dlx shadcn@latest add hover-card collapsible kbd

# Optional recommended shadcn components
pnpm dlx shadcn@latest add avatar alert checkbox
```

## Verify Current State

```bash
# Build should succeed (CSS is broken visually, not syntactically)
pnpm run build

# Tests should pass (53 baseline)
pnpm run test

# Dev server
pnpm run dev
# Open http://localhost:3000 — expect unstyled components
```

## Key Files to Understand

| File | Purpose | Read First? |
|------|---------|-------------|
| `app/globals.css` | CSS tokens, @theme inline, custom --color-* vars | Yes — this is where CSS scanning breaks |
| `app/chat/page.tsx` | Chat page structure, ChatSidebar integration | Yes — primary page being redesigned |
| `components/SidebarNav.tsx` | Navigation sidebar (needs ChatHistory added) | Yes |
| `hooks/useStreamChat.ts` | NDJSON streaming hook (token accumulation) | Yes — understand streaming model |
| `hooks/useChatStorage.ts` | Current single-session localStorage | Yes — will be extended |
| `lib/api.ts` | 18 API functions, streaming support | Reference |
| `lib/types.ts` | All TypeScript interfaces | Reference |
| `components/ui/sidebar.tsx` | shadcn sidebar (722 lines, 24 sub-components) | Reference |

## Development Workflow

### Phase 1: CSS Foundation (Must complete first)

1. Edit `globals.css` — add `@source` directives, remove custom tokens
2. Build — verify marker classes in CSS output
3. Check all 5 pages in browser — components should be styled

### Phase 2+: Feature Development

```bash
# Start dev server
pnpm run dev

# In another terminal, run tests in watch mode
pnpm run test -- --watch

# Build check before committing
pnpm run build
```

## Testing Commands

```bash
# Run all frontend tests (53 baseline)
pnpm run test

# Run specific test file
pnpm run test -- components/ChatMessageBubble.test.tsx

# Build verification (no TypeScript errors)
pnpm run build

# Lint
pnpm run lint
```

## Backend API (for manual testing)

All API endpoints are proxied via Next.js rewrites (`/api/*` → backend):

```bash
# Health check
curl http://localhost:3000/api/health

# List collections
curl http://localhost:3000/api/collections

# Chat (NDJSON stream)
curl -N -X POST http://localhost:3000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"query":"What is this about?","collection_ids":["<id>"]}'
```

## Constraints Checklist

Before every commit, verify:
- [ ] `pnpm run build` passes
- [ ] `pnpm run test` passes (>= 53 tests)
- [ ] No files modified outside `frontend/`
- [ ] Makefile unchanged (`diff Makefile` against baseline)
- [ ] No new dependencies beyond: react-markdown, remark-gfm, rehype-highlight
- [ ] No `var(--color-*)` custom tokens in component files (Phase 1+)
- [ ] shadcn v4 patterns: `render` prop for Base UI, `asChild` for Radix only
