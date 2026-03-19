# Spec 09 Frontend — 09-specify.md Coherence Review

## Status: COMPLETE — 7 issues found and fixed

## What Was Done
Full coherence review and rewrite of `Docs/PROMPTS/spec-09-frontend/09-specify.md` against:
- Live backend codebase (`backend/api/chat.py`, `backend/agent/schemas.py`, etc.)
- Spec 08 API Reference
- Project Blueprints
- Vercel React Best Practices skill (`.claude/skills/vercel-react-best-practices/`)

## Issues Fixed

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | CRITICAL | Protocol mislabeled as SSE; backend uses `application/x-ndjson` | Renamed all SSE refs to NDJSON; removed `data: ` prefix stripping |
| 2 | HIGH | Event type `"token"` — backend emits `"chunk"` with field `text` | Fixed case, renamed `onToken` → `onChunk(text: string)` |
| 3 | HIGH | Confidence thresholds used floats (0.7/0.4); backend emits INTEGER 0–100 | Display mapping corrected to `score >= 70`, `score >= 40` |
| 4 | MEDIUM | 4 backend events missing: `session`, `meta_reasoning`, `groundedness`, `clarification` | Added all 4 callbacks with correct TypeScript signatures |
| 5 | MEDIUM | `IngestionJobStatus` missing `"pending"` | Added to union type |
| 6 | LOW | `Collection.totalChunks` not in `/api/collections` endpoint | Removed; redirected to `/api/stats` |
| 7 | LOW | Deps on unimplemented spec-10 and spec-12 | Replaced with `spec-08-api (REQUIRED)` |

## New Section Added
`Vercel React Best Practices` — 8 project-specific rules (BP-1 through BP-8):
- BP-1: `next/dynamic` with `ssr: false` for recharts and react-dropzone
- BP-2: `optimizePackageImports` for Radix UI packages
- BP-3: Functional `setState` for token accumulation in ChatPanel
- BP-4: No component definitions inside render functions
- BP-5: SWR for all GET fetches; `useSWRMutation` for mutations
- BP-6: Parallel SWR keys on multi-data pages (observability)
- BP-7: Passive scroll event listeners during streaming
- BP-8: Lazy `useState` initialization for URL param parsing

## Key Backend Facts Verified
- Chat endpoint: `media_type="application/x-ndjson"`, each line is raw JSON (NO `data: ` prefix)
- 10 event types: session, chunk, citation, status, meta_reasoning, confidence, groundedness, clarification, done, error
- `chunk` event field is `text` (not `content`)
- Confidence score is INTEGER 0–100 (not float)
- `citation` event sends a `citations` list (not one per citation)
- `Collection` API does NOT return `totalChunks` (use `/api/stats` for aggregate counts)
- All provider and model endpoints are in spec-08 (no spec-10 needed)
