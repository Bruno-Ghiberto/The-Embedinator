# Implementation Plan: Frontend Application

**Branch**: `009-next-frontend` | **Date**: 2026-03-16 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/009-next-frontend/spec.md`

## Summary

Build the Next.js 16 App Router frontend for The Embedinator RAG system with five pages: chat (multi-turn NDJSON streaming), collections (CRUD with slug validation), documents (upload with 50 MB guard and job polling), settings (agent configuration with toast notifications and provider key management), and observability (health dashboard, charts, paginated trace table). No authentication. All communication through a centralized typed API client consuming the spec-08-api FastAPI backend. Implemented via Agent Teams: 5 waves, 7 agents.

## Technical Context

**Language/Version**: TypeScript 5.7, Node.js LTS
**Primary Dependencies**: Next.js 16, React 19, Tailwind CSS v4, SWR v2, recharts v2, react-dropzone v14, Radix UI (tooltip, dialog, select), React Hook Form, vitest v3 + React Testing Library v16, Playwright v1.50
**Storage**: N/A — data from FastAPI backend via REST/NDJSON (`spec-08-api`)
**Testing**: vitest + React Testing Library (unit, ≥70% line coverage), Playwright (E2E); all runs via `scripts/run-tests-external.sh`, never inline
**Target Platform**: Browser (desktop 1024px+, tablet 768px+); Next.js is 4th Docker Compose service
**Project Type**: web-app (Next.js 16 App Router, client components for all interactive pages)
**Performance Goals**: First token ≤500ms (SC-001), UI cold load <2s (constitution)
**Constraints**: No auth, NDJSON only (no SSE/WebSockets), 50 MB client-side upload guard, TypeScript strict mode, responsive 1024px+/768px+
**Scale/Scope**: 5 pages, 20 components, 4 SWR hooks, 17 typed API functions, 1–5 concurrent users

## Constitution Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1 design.*

| Principle | Status | Resolution |
|-----------|--------|------------|
| I. Local-First Privacy | ✅ PASS | NFR-SEC-001: no auth, open localhost access (constitution permanent design decision) |
| II. Three-Layer Agent Architecture | ✅ N/A | Frontend does not implement agent layers |
| III. Retrieval Pipeline Integrity | ✅ N/A | Retrieval runs in backend; frontend renders citations from stream |
| IV. Observability from Day One | ⚠️ PARTIAL → RESOLVED | `source_removed: bool` exists in backend `Citation` schema — `CitationTooltip` must show "source removed" indicator when `true`. Added to data-model and contracts. |
| V. Secure by Design | ⚠️ MINOR GAP → RESOLVED | Client-side extension allowlist (pdf, md, txt) absent from FR-011 — `DocumentUploader` must validate extension before upload. Added to contracts. |
| VI. NDJSON Streaming Contract | ✅ PASS | All 10 event types handled; `chunk.text` field (not `content`); `clarification` ends stream without `done` — `isStreaming` released on `clarification`, `done`, AND `error`. |
| VII. Simplicity by Default | ✅ PASS | No new services; 4th Docker service already in compose; YAGNI throughout |

**Gate result**: 2 minor gaps resolved at design time. No blocking violations.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|--------------------------------------|
| `source_removed` rendering | Constitution IV mandates indicator when source deleted | Spec omitted it; backend schema has the field; skipping violates the constitution |
| Client-side extension validation | Constitution V requires allowlist at system boundary | Spec omitted it; backend rejects post-upload — wastes network and user time |

## Project Structure

### Documentation (this feature)

```text
specs/009-next-frontend/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── api-client.ts    # TypeScript API client types and function signatures
└── tasks.md             # Phase 2 output (speckit.tasks — not created here)
```

### Source Code

```text
frontend/
  app/
    layout.tsx                    # Root layout with Navigation, fonts, Tailwind
    chat/page.tsx                 # Chat page (client component)
    collections/page.tsx          # Collections grid
    documents/[id]/page.tsx       # Per-collection documents + uploader
    settings/page.tsx             # Settings form + ProviderHub
    observability/page.tsx        # Health, charts, trace table
  components/
    Navigation.tsx                # Top nav, 5 links, active route highlight
    ChatPanel.tsx                 # Multi-turn message thread, NDJSON token accumulation
    ChatInput.tsx                 # Textarea + send button (disabled while isStreaming)
    ChatSidebar.tsx               # Collection multi-select + model dropdowns
    CitationTooltip.tsx           # Radix Tooltip; source_removed-aware
    ConfidenceIndicator.tsx       # Integer 0-100 → green/yellow/red dot
    CollectionList.tsx            # Responsive card grid
    CollectionCard.tsx            # Card with name, doc count, delete action
    CreateCollectionDialog.tsx    # Radix Dialog, slug validation, conflict error
    DocumentList.tsx              # Table with document status badges
    DocumentUploader.tsx          # react-dropzone, 50 MB + extension guard, job polling
    ModelSelector.tsx             # Radix Select for LLM/embed models
    ProviderHub.tsx               # Provider list, has_key masking, save/delete key
    Toast.tsx                     # Success/error banner (auto-dismiss 3s)
    TraceTable.tsx                # Paginated, expandable rows, session filter
    LatencyChart.tsx              # recharts bar histogram
    ConfidenceDistribution.tsx    # recharts bar chart by tier
    HealthDashboard.tsx           # Service status cards (sqlite, qdrant, ollama)
    CollectionStats.tsx           # Per-collection doc count + aggregate stats
  lib/
    api.ts                        # 17 typed async API functions + streamChat NDJSON
    types.ts                      # TypeScript interfaces mirroring backend schemas
  hooks/
    useStreamChat.ts              # NDJSON hook; isStreaming released on done/error/clarification
    useCollections.ts             # SWR for collections list
    useModels.ts                  # SWR for LLM + embed model lists
    useTraces.ts                  # SWR for paginated traces
  tests/
    unit/                         # vitest + React Testing Library
    e2e/                          # Playwright
  next.config.ts
  package.json
  tailwind.config.ts
  tsconfig.json
```

**Structure Decision**: Frontend-only project under `frontend/` (existing repo slot). No new backend modules.

## Key Design Decisions

See `research.md` for full rationale. Summary:

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Stream parsing | ReadableStream + TextDecoder + line split | NDJSON has no `data:` prefix; native Fetch API; no additional deps |
| `isStreaming` release | on `done`, `error`, AND `clarification` | Clarification ends the stream without a `done` event |
| Settings endpoint | `PUT /api/settings` (not PATCH) | Backend uses PUT with optional fields |
| Per-collection chunk count | Not available; use `document_count` from CollectionResponse | No per-collection chunk endpoint exists; aggregate from `/api/stats` |
| Citation `source_removed` | Render "source removed" badge in CitationTooltip | Constitution IV requires this; backend field exists |
| File extension allowlist | `pdf`, `md`, `txt`, `rst` client-side | Constitution V; backend allowlist is the authoritative gate |
| Document status vs job status | Two separate status models | DocumentResponse has 5 states; IngestionJobResponse has 7 states |
| Toast location | Settings page only | Only FR-015 requires it; other mutations use SWR mutate + optimistic |

## Agent Teams Orchestration

See `Docs/PROMPTS/spec-09-frontend/09-plan.md` for full wave table, agent instruction files, and checkpoint gates.

Wave summary:

| Wave | Agents | Focus |
|------|--------|-------|
| 1 | A1 (serial, Opus) | Scaffold, types, API client, SWR hooks |
| 2 | A2 + A3 (parallel, Opus + Sonnet) | Chat page / Collections page |
| 3 | A4 + A5 (parallel, Sonnet + Sonnet) | Documents page / Settings + ProviderHub |
| 4 | A6 (serial, Sonnet) | Observability page |
| 5 | A7 (serial, Sonnet) | vitest unit tests, Playwright E2E, TypeScript audit |

Instruction files: `Docs/PROMPTS/spec-09-frontend/agents/A{1-7}-*.md` (created by speckit.tasks).

## Testing Policy

**NEVER run tests inline inside Claude Code.**

```bash
# TypeScript compile check (before each wave gate)
cd frontend && npx tsc --noEmit

# Unit tests (vitest)
cd frontend && npm run test -- --run

# E2E tests (Playwright)
cd frontend && npx playwright test

# Python regression baseline (no backend changes in spec-09)
zsh scripts/run-tests-external.sh -n spec09-regression tests/
cat Docs/Tests/spec09-regression.status
cat Docs/Tests/spec09-regression.summary
```

Rules:
- All agents run tests in background — never blocking inline
- Read `.summary` files only; never `cat` the `.log`
- Wave gates require `npx tsc --noEmit` exit 0 before proceeding
- Gate 5 requires all vitest + Playwright + Python regression passing
