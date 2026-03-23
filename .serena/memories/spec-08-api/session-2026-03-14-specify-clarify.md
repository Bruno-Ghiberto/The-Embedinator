# Spec 08: API Reference — Specify + Clarify Session (2026-03-14)

## Status
- speckit.specify: COMPLETE — specs/008-api-reference/spec.md written (5 US, 26 FRs, 10 SCs, 9 edge cases)
- speckit.clarify: COMPLETE — 5/5 questions answered, all taxonomy categories resolved
- Branch: `008-api-reference`
- Next step: `/speckit.plan`

## Spec Structure
- 5 User Stories (P1–P5): Chat streaming, Collections+Docs, Providers+Models, Observability, Settings
- 26 Functional Requirements (FR-001 to FR-026)
- 10 Success Criteria (SC-001 to SC-010)
- 8 Key Entities: Collection, Document, IngestionJob, ChatSession, QueryTrace, Provider, ModelInfo, SystemSettings
- Checklist: specs/008-api-reference/checklists/requirements.md — all items pass

## Clarifications Applied (Session 2026-03-14)
1. **No API version prefix** — paths use `/api/` directly (FR-001 updated, versioning out of scope)
2. **Rate limiting per client IP** — per-IP counters, not global (FR-024 updated)
3. **Collection deletion cancels active jobs** — in-progress jobs → `failed` before collection removed (FR-005 + edge cases updated)
4. **Settings apply to new sessions only** — active sessions continue with settings in effect at start (FR-020 updated)
5. **Query traces retained indefinitely** — no automatic purging (FR-021 updated)

## Key Design Decisions
- NDJSON streaming (not SSE): 10 event types (session, status, chunk, citation, meta_reasoning, confidence, groundedness, done, clarification, error)
- Confidence scores: int 0–100 (not float)
- Rate limits: chat=30/min, ingest=10/min, provider-key=5/min, default=120/min — all per IP
- Provider keys: never returned in responses, only `has_key: bool`
- Duplicate detection: by content hash, returns `duplicate` status without re-processing
- Supported file types: .pdf .md .txt .py .js .ts .rs .go .java .c .cpp .h (12 types, 100MB max)

## Architecture Reference (from 08-specify.md)
- Collections router: backend/api/collections.py — EXISTS, needs extension
- Documents router: backend/api/documents.py — EXISTS, needs rewrite
- Chat router: backend/api/chat.py — EXISTS, needs NDJSON event expansion
- Ingest router: backend/api/ingest.py — NEW
- Models router: backend/api/models.py — NEW
- Providers router: backend/api/providers.py — EXISTS, needs extension
- Settings router: backend/api/settings.py — NEW
- Traces/health/stats: backend/api/traces.py + backend/api/health.py — EXIST, need schema rewrite
- Middleware: backend/middleware.py — NEW (rate limiting + trace ID injection)
- Schemas: backend/agent/schemas.py — EXISTS, significant extension needed
- App factory: backend/main.py — EXISTS, needs router registration updates
- Config: backend/config.py — EXISTS, needs new rate limit fields
