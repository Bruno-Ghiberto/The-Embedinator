# Spec 09 Frontend — speckit.specify Complete

## Status: COMPLETE — branch created, spec written, checklist all-pass

## What Was Done
Ran `speckit.specify` for the Next.js 16 frontend (spec-09) using the coherence-reviewed
`Docs/PROMPTS/spec-09-frontend/09-specify.md` as the feature description.

## Branch & Artifacts
- **Branch**: `009-next-frontend` (checked out, created from `008-api-reference`)
- **Spec**: `specs/009-next-frontend/spec.md`
- **Checklist**: `specs/009-next-frontend/checklists/requirements.md` — all items ✅

## Spec Contents Summary

### User Stories (5 total, all with acceptance scenarios)
| Priority | Story | Pages |
|----------|-------|-------|
| P1 | Conversational RAG Query | /chat |
| P2 | Collection Management | /collections |
| P3 | Document Upload & Ingestion Tracking | /documents/[collectionId] |
| P4 | Settings & Provider API Key Management | /settings |
| P5 | Observability & System Health | /observability |

### Functional Requirements: FR-001 through FR-023
- FR-001–FR-006: Chat streaming, citations, confidence, clarification, model/collection selection, URL state
- FR-007–FR-010: Collection grid, creation, deletion, navigation
- FR-011–FR-014: Document upload, progress polling, status badges, deletion
- FR-015–FR-017: Settings form, provider listing, API key management (masked)
- FR-018–FR-021: Observability — health cards, latency chart, confidence chart, trace table, collection stats
- FR-022–FR-023: Top navigation, responsive layout (1024px+ desktop, 768px+ tablet)

### Key Entities (9)
Collection, Document, Ingestion Job, Chat Session, Chat Message, Citation, Query Trace, Provider, Model

### Success Criteria: SC-001 through SC-008
- SC-001: First streamed word within 500ms
- SC-002: All 5 pages navigable without full reload
- SC-003: End-to-end workflow in single session
- SC-004: Confidence indicator correctly color-coded
- SC-005: URL-based state survives browser refresh
- SC-006: Observability page renders without error
- SC-007: Heavy components load asynchronously (no initial render delay)
- SC-008: Collection name validation gives inline feedback

## Spec Quality
- 0 [NEEDS CLARIFICATION] markers
- All 23 FRs are testable and unambiguous
- No implementation details (framework, library, API endpoint names stripped)
- Checklist: all 13 items pass

## Key Spec Decisions
- Confidence thresholds are INTEGER-based (≥70 = green, 40–69 = yellow, <40 = red) — matches backend
- Citation hover described behaviorally (no lazy fetch mention — left to plan)
- URL-based state persistence included as FR-006 (shareability requirement)
- All 7 ingestion status values listed: pending, started, streaming, embedding, completed, failed, paused
- Collection name validation regex `^[a-z0-9][a-z0-9_-]*$` included in FR-008 (matches backend constraint)
- Observability services described as "vector store, LLM runtime, database" (not Qdrant/Ollama/SQLite) for tech-agnosticism

## Next Steps
Run `speckit.clarify` to surface ambiguities, or `speckit.plan` to go straight to design.
