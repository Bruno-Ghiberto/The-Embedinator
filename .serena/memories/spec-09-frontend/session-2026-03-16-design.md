# Spec 09 Frontend — Full Design Pipeline Complete

## Status: COMPLETE — all speckit artifacts generated, analyze remediated, implement.md + agents written

## Branch & Artifacts
- **Branch**: `009-next-frontend` (active)
- **Spec**: `specs/009-next-frontend/spec.md` — 5 user stories, 23 FRs, 8 SCs, 1 NFR, 5 clarifications
- **Plan**: `specs/009-next-frontend/plan.md` — Technical context, constitution check, project structure
- **Tasks**: `specs/009-next-frontend/tasks.md` — 52 tasks (T001–T052), 9 phases, 7 agents
- **Research**: `specs/009-next-frontend/research.md` — 7 findings all resolved
- **Data Model**: `specs/009-next-frontend/data-model.md` — 13 entities + NDJSON event union
- **Contracts**: `specs/009-next-frontend/contracts/api-client.ts` — 17 API functions + streamChat
- **Quickstart**: `specs/009-next-frontend/quickstart.md` — Developer setup guide
- **Checklist**: `specs/009-next-frontend/checklists/requirements.md` — from speckit.specify

## Context Prompts
- `Docs/PROMPTS/spec-09-frontend/09-specify.md` — Coherence-reviewed (7 issues fixed)
- `Docs/PROMPTS/spec-09-frontend/09-plan.md` — Rewritten (390 lines, NDJSON, Agent Teams)
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` — Full rewrite (1030 lines, all schemas correct)
- `Docs/PROMPTS/spec-09-frontend/agents/A1-foundation.md` — system-architect, Opus, T001-T014
- `Docs/PROMPTS/spec-09-frontend/agents/A2-chat-page.md` — frontend-architect, Opus, T015-T021
- `Docs/PROMPTS/spec-09-frontend/agents/A3-collections-page.md` — frontend-architect, Sonnet, T022-T025
- `Docs/PROMPTS/spec-09-frontend/agents/A4-documents-page.md` — frontend-architect, Sonnet, T026-T028
- `Docs/PROMPTS/spec-09-frontend/agents/A5-settings-page.md` — frontend-architect, Sonnet, T029-T031
- `Docs/PROMPTS/spec-09-frontend/agents/A6-observability-page.md` — performance-engineer, Sonnet, T032-T037
- `Docs/PROMPTS/spec-09-frontend/agents/A7-quality-tests.md` — quality-engineer, Sonnet, T038-T046

## Speckit Pipeline Executed
1. `speckit.clarify` — 5 questions asked and answered (auth, multi-turn, streaming lock, upload limit, toast)
2. `sc:improve 09-plan.md` — Rewrote plan context prompt (SSE→NDJSON, Agent Teams added)
3. `speckit.plan` — Generated plan.md, research.md, data-model.md, contracts/, quickstart.md
4. `speckit.tasks` — Generated tasks.md (52 tasks, 9 phases)
5. `speckit.analyze` — 12 findings (0 CRITICAL, 1 HIGH, 7 MEDIUM, 4 LOW); all remediated
6. `sc:design 09-implement.md` — Full rewrite + 7 agent instruction files

## Key Clarifications (spec.md Session 2026-03-16)
- No authentication — all pages open (localhost/internal access)
- Multi-turn chat thread — messages scroll vertically, appended at bottom
- Send button disabled while streaming — re-enabled on done/error/clarification
- 50 MB per-file client-side upload limit
- Settings saves: toast notification after API response (no optimistic UI)

## Key Research Findings
- `clarification` event ends stream WITHOUT `done` — isStreaming must release on clarification too
- `Citation.source_removed: bool` exists — CitationTooltip must show "source removed" badge
- `page` and `breadcrumb` exist in backend `RetrievedChunk` but NOT in Citation schema
- DocumentResponse.status (5 values) ≠ IngestionJobResponse.status (7 values)
- Settings endpoint is PUT (not PATCH)
- No per-collection chunk count in API — use aggregate from /api/stats
- `is_active` and `has_key` are independent provider fields

## Analyze Remediation Applied
- H1: FR-002 updated to remove page_number/breadcrumb (not in Citation schema)
- M1/M6: FR-013 rewritten to separate document status (5) from job status (7)
- M2: T022 updated — CollectionCard now includes next/link to /documents/{id}
- M3: T004 updated with responsive breakpoints; T051 added (Playwright viewport test)
- M7: T052 added (SC-003 cross-page E2E workflow test)

## Agent Teams Configuration
| Wave | Agents | Focus | Model |
|------|--------|-------|-------|
| 1 | A1 (serial) | Scaffold, types, API, hooks | Opus |
| 2 | A2 + A3 (parallel) | Chat page / Collections page | Opus + Sonnet |
| 3 | A4 + A5 (parallel) | Documents / Settings + ProviderHub | Sonnet + Sonnet |
| 4 | A6 (serial) | Observability (charts, health, traces) | Sonnet |
| 5 | A7 (serial) | vitest, Playwright, TypeScript audit | Sonnet |

## Next Step
Run `/speckit.implement` to execute the Agent Teams implementation.
