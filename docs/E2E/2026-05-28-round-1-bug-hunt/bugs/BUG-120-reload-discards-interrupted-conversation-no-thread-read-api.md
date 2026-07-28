# BUG-120: Reload discards the interrupted conversation; no API can read a thread back

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-28T14:08:47Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Send a chat question; the backend mints thread `d4303789-f4f9-4938-a52f-f162afd7d8c3` and emits it in the `session` NDJSON event at +16ms.
2. Interrupt the turn (P7-S1: `docker kill embedinator-backend` mid-stream), then restart the backend and let it return healthy.
3. Reload the page. Observe the chat is completely empty — the user's own question is gone, with no interruption notice.
4. Inspect `location.href` — no `?session=` parameter was ever written.
5. Inspect `localStorage` key `embedinator-sessions:v1` — the local-history entry `8d729373-eb20-48d5-88bc-e7874e475050` exists but ends with `messages: []` (0 messages).
6. Confirm the checkpoint survived server-side: the interrupted thread still holds 2 checkpoints (step -1 `source=input`, step 0 `source=loop`) after restart.
7. `GET /openapi.json` — the ONLY chat path in the entire API surface is `POST /api/chat`. Probed and 404'd: `/api/chat/sessions`, `/api/sessions`, `/api/conversations`, `/api/chat/{session_id}`, `/api/chat/sessions/{session_id}`.

## Expected
An interrupted conversation is recoverable: either the client can restore it from a persisted identifier, or the server exposes a way to read the thread back so the user does not silently lose their question and any partial work.

## Actual
The conversation is unrecoverable through every available surface. The backend thread id and the frontend local-history id are DIVERGENT and never reconciled; the URL carries no session parameter; the local-history entry holds zero messages, so even the user's own question was never persisted client-side. The LangGraph checkpoint DOES survive server-side, but no product surface can read a thread back — resume is only expressible as a NEW `POST /api/chat` carrying `session_id`, which continues the thread rather than recovering the interrupted turn.

## Artifacts
- Screenshot: screenshots/P7-S1-post-restart.png (gitignored) — post-reload, chat completely empty
- Log excerpt: null
- Trace: traces/P7-S1-ckpt-inflight.txt (gitignored) — the 2 surviving checkpoint rows for the interrupted thread

## Root-cause hypothesis
HIGH confidence, evidence-confirmed on both sides. Client side: the backend `session_id` is never propagated to any durable surface — not the URL, not the local-history record — so a reload has nothing to restore from (same structural gap family as BUG-064, where the id lives only in a private `useRef`). Server side: the API exposes no read path for a conversation thread at all; `POST /api/chat` is the sole chat endpoint, confirmed against `openapi.json` plus five 404-probed candidate routes. The persistence layer therefore holds recoverable state that no API can return. Fix surface is two-part and both parts are required: persist the backend `session_id` client-side (URL or local history), AND add a thread-read endpoint.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/170
- **Rationale**: An interrupted conversation is silently and permanently lost from the user's point of view — question included — even though the server still holds the checkpoint, because no product surface can read a thread back; conversation continuity is a documented core flow.

## Notes
Reporter: frontend-inspector (Playwright MCP). Dedup-checked before minting against all 94 prior records; grep for `openapi.json`, thread-read and GET-session coverage returned zero hits.

**Distinct from BUG-064**, which is the mirror-image client-side defect: BUG-064 is that `session_id` lives only in a private `useRef` so a REMOUNT silently starts a fresh thread while the UI still displays earlier messages re-hydrated from local history. THIS record is that after an INTERRUPTED turn there is nothing to display at all (local history holds 0 messages) and — the genuinely new half — that the server offers no read path, so the surviving checkpoint is unreachable by design rather than by a frontend bug. Cross-ref BUG-064 (session-id persistence), BUG-072 (in-flight stream lost on unmount), BUG-074 (the stream never terminates in the first place).

**Directly constrains P7-S5**: checkpoint-resume validation cannot be performed through any product surface, only by issuing a new `POST /api/chat` with the prior `session_id`. Recorded here so P7-S5's method is not mistaken for a product capability.
