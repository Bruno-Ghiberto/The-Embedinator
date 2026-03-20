# Spec 18 — UX/UI Redesign: Full Speckit Pipeline Session (2026-03-19)

## Status: FULL PIPELINE COMPLETE — Ready for speckit.implement

## Branch: `018-ux-redesign`

## Speckit Pipeline Stages Completed
1. **18-specify.md** (417 lines) — context prompt for speckit.specify
2. **speckit.specify** → spec.md (280 lines, 38 FRs, 4 NFRs, 8 SCs, 6 USs)
3. **speckit.clarify** → 3 clarifications resolved (localStorage limits, multi-tab conflict, documents mobile layout)
4. **18-plan.md** (495 lines) — context prompt for speckit.plan
5. **speckit.plan** → plan.md (521 lines), research.md (139), data-model.md (110), contracts/ui-components.md (100), quickstart.md (92)
6. **speckit.tasks** → tasks.md (59 tasks across 9 phases)
7. **speckit.analyze** → 0 CRITICAL, 0 HIGH, 4 MEDIUM (all remediated), 6 LOW
8. **18-implement.md** (176 lines) — orchestrator context for speckit.implement
9. **7 agent instruction files** — A1, A3–A8 (1140 lines total)

## Design Decisions
- **Palette**: Obsidian Violet (Palette A) — user chose explicitly
- **Sidebar default**: Expanded on first visit, persist via localStorage
- **Chat persistence**: localStorage, single conversation, auto-evict, last-write-wins
- **Animation budget**: CSS-only (no Framer Motion)
- **Documents mobile**: Stack vertically (file list top, chunks below)

## Agent Team Structure (4 Waves)
- Wave 1: A1 (frontend-architect) — T001–T015 — Foundation + Tokens + Theme + Sidebar
- Wave 2: GATE CHECK — orchestrator verifies build + routes + sidebar + theme
- Wave 3: A3–A7 (5x frontend-architect) — T016–T044 — 5 pages in parallel
  - A3=Chat (HIGH), A4=Collections (MED), A5=Documents (MED), A6=Settings (MED), A7=Observability (MED-HIGH)
- Wave 4: A8 (quality-engineer) — T045–T057 — Command Palette + Breadcrumbs + Full QA

## Key Gotchas for Implementation
1. shadcn Sidebar CSS vars MUST be in globals.css (--sidebar-background, etc.)
2. ThemeProvider wraps SidebarProvider (NOT vice versa)
3. ChatPage height calc `h-[calc(100vh-4rem)]` → `h-dvh` after sidebar
4. 15 files have ZERO dark mode support (200+ hard-coded gray classes)
5. TraceTable.tsx has 30+ hard-coded gray classes (largest migration)
6. Toast.tsx → Sonner: add Toaster to layout BEFORE deleting Toast.tsx
7. ModelSelector.tsx is shared (ChatSidebar + Settings) — A3 restyles it
8. layout.tsx touched by A1 (Phase 2), A6 (Toaster), A8 (CommandPalette/Breadcrumb)
9. Preserve onGroundedness rendering in ChatPanel during restyle

## File Map
```
Docs/PROMPTS/spec-18-UX_UI-Redesign/
├── 18-specify.md, 18-plan.md, 18-implement.md
└── agents/ (A1, A3, A4, A5, A6, A7, A8 instructions)

specs/018-ux-redesign/
├── spec.md, plan.md, tasks.md
├── research.md, data-model.md, quickstart.md
├── contracts/ui-components.md
└── checklists/requirements.md
```

## MCPs Used During Pipeline
- serena: component inventory, referencing symbols, pattern search (gray classes)
- gitnexus: api.ts dependency graph (14 importers), execution flows
- shadcn-ui: 21 components verified, sidebar examples (33 code samples)
- context7: next-themes setup, Next.js 16 layouts, Tailwind CSS 4
- sequential-thinking: palette design, phase ordering, migration strategy
- mcp-chart: attempted (unavailable — fallback to recharts)
- MCP_DOCKER: nextjs_docs checked, nextjs_runtime reviewed
