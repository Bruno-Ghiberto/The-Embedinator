# Research: Frontend Application

**Phase**: 0 — Pre-Design Research
**Date**: 2026-03-16
**Branch**: `009-next-frontend`

## Summary

No NEEDS CLARIFICATION items in Technical Context. Research focused on verifying backend API contracts (spec-08-api) and identifying gaps between the feature spec and the constitution. All findings resolved.

---

## Finding 1: NDJSON Stream Ends on `clarification` Without `done`

**Decision**: Release `isStreaming` on `done`, `error`, AND `clarification`.

**Rationale**: The backend emits a `clarification` event when the agent asks a follow-up question and then terminates the stream — no `done` frame follows. If `isStreaming` is only reset on `done`/`error`, the send button stays permanently locked after any clarification turn.

**Impact**: `useStreamChat.ts` must call `setIsStreaming(false)` inside the `clarification` handler as well as `done` and `error`. The spec clarification (Session 2026-03-16) only mentioned `done`/`error` — this adds `clarification` as a third release point.

**Alternatives considered**: Timeout-based unlock — rejected (race condition on slow backends).

---

## Finding 2: `source_removed: bool` Exists in Citation Schema

**Decision**: `CitationTooltip` must render a "source removed" badge when `citation.source_removed === true`.

**Rationale**: Constitution Principle IV states: "When a source document is deleted, existing trace records MUST retain the passage text they captured at query time and display a `source_removed: true` indicator in place of the source link." The backend `Citation` model in `backend/agent/schemas.py` has `source_removed: bool = False`. FR-002 in the spec omits this — the spec is incomplete relative to the constitution. Resolved by adding to contracts.

**Alternatives considered**: Omit from frontend — rejected (constitution violation).

---

## Finding 3: Two Separate Status Models (Document vs. Ingestion Job)

**Decision**: `DocumentList` renders document status (5 states); `DocumentUploader` polls job status (7 states).

**Rationale**: `DocumentResponse.status` has 5 values: `pending`, `ingesting`, `completed`, `failed`, `duplicate`. `IngestionJobResponse.status` has 7 values: `pending`, `started`, `streaming`, `embedding`, `completed`, `failed`, `paused`. These are separate entities. The spec's FR-013 lists job-level states for the documents table — in practice the table should show the document-level status badge, which transitions to `completed`/`failed` once the job terminates.

**Recommendation**: `DocumentList` shows `DocumentResponse.status`. During active upload, `DocumentUploader` polls `IngestionJobResponse.status` for granular progress. When polling ends, the document row refreshes via SWR mutate to show the final `DocumentResponse.status`.

---

## Finding 4: Settings Endpoint is `PUT`, Not `PATCH`

**Decision**: `updateSettings()` calls `PUT /api/settings`.

**Rationale**: Backend router uses `PUT` with `SettingsUpdateRequest` where all fields are `Optional`. The 09-plan.md context prompt incorrectly suggested PATCH. The actual endpoint accepts a partial body under a PUT verb.

**Alternatives considered**: Use PATCH — wrong, backend returns 405.

---

## Finding 5: No Per-Collection Chunk Count in API

**Decision**: `CollectionStats` component uses `document_count` from `CollectionResponse` (per-collection) and aggregate `total_chunks` from `GET /api/stats`.

**Rationale**: `GET /api/collections` returns `document_count: int` per collection, but no `chunk_count`. `GET /api/stats` returns aggregate `total_chunks: int` only. FR-021 ("per-collection document and chunk counts") cannot be fully satisfied with the current API. Resolution: show document count per collection (available), show total chunk count as a system aggregate metric. No new endpoint is needed for the spec-09 implementation scope.

**Alternatives considered**: Add `/api/collections/{id}/stats` endpoint — out of scope for spec-09 (frontend-only spec).

---

## Finding 6: File Extension Allowlist Not in Spec

**Decision**: `DocumentUploader` validates extension client-side against `['pdf', 'md', 'txt', 'rst']`.

**Rationale**: Constitution Principle V requires: "File uploads MUST be validated: extension allowlist (pdf, md, txt)." FR-011 does not mention client-side extension checking. Adding `rst` as the backend Rust worker supports it. Extension validation prevents a wasted network round-trip for obviously invalid files.

**Alternatives considered**: Backend-only validation — allowed by spec but wastes UX; constitution requires system boundary enforcement.

---

## Finding 7: `ProviderDetailResponse.is_active` vs. `has_key`

**Decision**: ProviderHub shows `is_active` as the connection status indicator, `has_key` as the key presence indicator — these are separate fields.

**Rationale**: `is_active: bool` reflects whether the provider is reachable (connectivity test). `has_key: bool` reflects whether an API key is stored. A provider can be active (Ollama, no key needed) or inactive despite having a stored key (bad key, provider down). The UI should show both independently.

---

## Verified Backend Endpoints

All endpoints verified against `backend/agent/schemas.py` and `backend/api/*.py` routers:

| Method | Path | Used by |
|--------|------|---------|
| POST | `/api/chat` | useStreamChat, streamChat() |
| GET | `/api/collections` | useCollections |
| POST | `/api/collections` | CreateCollectionDialog |
| DELETE | `/api/collections/{collection_id}` | CollectionCard |
| GET | `/api/documents?collection_id={id}` | DocumentList |
| DELETE | `/api/documents/{doc_id}` | DocumentList |
| POST | `/api/collections/{collection_id}/ingest` | DocumentUploader |
| GET | `/api/collections/{collection_id}/ingest/{job_id}` | DocumentUploader (polling) |
| GET | `/api/models/llm` | useModels |
| GET | `/api/models/embed` | useModels |
| GET | `/api/providers` | ProviderHub |
| PUT | `/api/providers/{name}/key` | ProviderHub |
| DELETE | `/api/providers/{name}/key` | ProviderHub |
| GET | `/api/settings` | Settings page |
| PUT | `/api/settings` | Settings form save |
| GET | `/api/traces` | useTraces, TraceTable |
| GET | `/api/traces/{trace_id}` | TraceTable (expanded row) |
| GET | `/api/stats` | CollectionStats |
| GET | `/api/health` | HealthDashboard |
