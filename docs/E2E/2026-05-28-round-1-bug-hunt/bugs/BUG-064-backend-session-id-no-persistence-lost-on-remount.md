# BUG-064: Backend session_id has no persistence across chat page remounts

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-26T19:10:00Z in Phase 3 (P3-S3)
- **Phase scenario**: P3-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start a conversation in the chat UI; note the `?session=` parameter in the URL.
2. Trigger any remount of the chat page's `useStreamChat` hook instance — a hard reload is ONE trigger, but ANY hook-instance recreation reproduces this (confirmed 2026-07-03 on a clean multi-turn probe with NO reload: see Live evidence below).
3. Ask a follow-up question that references the prior turn.
4. Observe the DevTools POST body — `session_id` is `null`.
5. Note the model response ignores prior context (no memory of the first turn) — on 2026-07-03 this produced a visible topic-drift answer (see below).

## Expected
The backend `session_id` persists across any remount of the chat hook (reload, navigation, or otherwise) so that follow-up POSTs carry the correct `session_id` and the LangGraph thread retains prior turns' context.

## Actual
`session_id` lives ONLY in a private `useRef` inside the `useStreamChat` closure — it has ZERO redundant persistence (no component state, no localStorage, no URL). Any remount of that hook instance silently resets the ref to `null`, so the next POST creates a brand-new, empty LangGraph thread and all prior context is lost — even though the UI still visually shows the earlier messages (re-hydrated from a SEPARATE local-history store).

## Artifacts
- Screenshot: screenshots/BUG-064.png (gitignored)
- Log excerpt: logs/BUG-064.log (gitignored)
- Trace: null
- Dual-referenced: screenshots/BUG-062-p3s4-t2-citation1-475pct.png (T2 drifted-answer screenshot, shared evidence with BUG-062 — same physical file, two bug records, per Lead direction)

## Root-cause hypothesis
HIGH confidence, code-confirmed (frontend-inspector) — `useStreamChat.ts:10` `sessionIdRef = useRef(null)` is private to the hook closure and re-initializes to `null` on every mount. It is read on send (`~L33` `session_id: sessionIdRef.current`) and set by the `onSession` callback (`~L37-39`) — `onSession` IS correctly wired (`api.ts:167-169` dispatches the `session` NDJSON event); this is NOT a no-op bug. The ref value is simply NEVER returned or exposed from the hook (`~L127`), so nothing outside `useStreamChat` can persist or restore it. Separately, the `?session=` URL param is a DIFFERENT id namespace entirely: it is the frontend history-bookkeeping id created by `useChatHistory.createSession` (`crypto.randomUUID()`), written at `chat/page.tsx:147-148` / `183-189` and navigated via `SidebarNav`'s `ChatHistorySection` (`~L120-133`). That id is structurally incapable of restoring backend continuity even if it were wired to `useStreamChat` — it is the wrong id type (frontend history UUID, not a LangGraph thread id). Cites: `useStreamChat.ts:10, ~33, ~37-39, ~127`; `api.ts:167-169`; `chat/page.tsx:64-65, 80, 147-148, 183-189`; `useChatHistory.ts` (`createSession`); `SidebarNav.tsx` (`~L120-133`). Residual: the exact remount trigger between the 2026-07-03 T1/T2 turns was not statically pinned — the architecture guarantees the failure mode, and the null-session capture proves it fired on this run, but the specific React lifecycle event was not isolated.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/141
- **Rationale**: session_id lives only in a private useRef with zero redundant persistence, so follow-ups silently open a fresh empty thread while the UI still displays the prior conversation — proven by a visible topic-drift answer; US3 SC-4 cannot pass.

## Notes
Directly impacts P3-S4 multi-turn continuity scenario — US3 SC-4 "model retains conversational context" cannot pass while this bug is present.

Live evidence (clean probe, 2026-07-03, NO reload): T1 POST `session_id=null` → server minted `9c30b2ea`; T2 POST `session_id=null` → server minted `d1f7d690` (a SEPARATE thread from T1, same browser session, no reload). Contrast: the organic 2026-06-26 session carried `session_id=c5ffb174` across all 3 turns (one shared thread) — so transmission is INCONSISTENT / remount-dependent, NOT always-null. This confirms the bug is broader than "URL not restored on reload" — it is "no persistence mechanism exists at all," and reload is only one of several remount triggers.

USER-VISIBLE PROOF (2026-07-03 T2): follow-up "y para gas natural específicamente?" was answered about gas COMPOSITION (citing NAG-602) instead of continuing T1's minimum-diameter thread, because no prior-turn history reached the graph (server minted a brand-new thread `d1f7d690`). Amplified by BUG-056 (downstream): the blind rewrite_query fallback passed the raw 5-word fragment straight to retrieval with no corrective context, compounding the drift. Cross-ref BUG-056 as a downstream amplifier, not an independent cause.

Primary artifact: `frontend/hooks/useStreamChat.ts` (L10, ~33, ~37-39, ~127); secondary: `frontend/app/chat/page.tsx` (L64-65, 80, 147-148, 183-189), `frontend/hooks/useChatHistory.ts` (`createSession`), `frontend/components/SidebarNav.tsx` (~L120-133), `frontend/lib/api.ts` (L167-169). Analyst-correlated HIGH confidence; broadened 2026-07-03 per Lead+Pilot ruling after code trace + live clean-probe reproduction (superseding the original "reload only" framing — filename/title updated accordingly, same BUG-064 ID retained).

3rd session_id-continuity-break data point (2026-07-03, P3-S6, no field change): the NAG-E207 turn (BUG-071) ran on session `119b2304-9df8-42b6-822f-31e84f6ada37`, NOT shared with the same-chat NAG-204 turn (session `2bfae3de-4b4e-446e-b569-cab94c60c6c1`) — another fresh-thread-without-reload occurrence. Today's tally: clean-probe T1 (`9c30b2ea`) → T2 (`d1f7d690`), plus this NAG-204 → NAG-E207 same-chat pair — corroborates the remount/no-persistence failure's frequency (3 separate fresh-thread occurrences in one session, no reload in any of them).

**CORROBORATION 2026-07-28 (P7-S1)**: live re-confirmation — the captured POST body carries `"session_id":null` on a fresh turn, and the backend/frontend identifiers were DIVERGENT and never reconciled (backend thread `d4303789-f4f9-4938-a52f-f162afd7d8c3` from the `session` NDJSON event vs frontend local-history id `8d729373-eb20-48d5-88bc-e7874e475050` in `localStorage embedinator-sessions:v1`). No `?session=` parameter is ever written to the URL. See BUG-120 for the distinct downstream consequence — after an interrupted turn there is nothing to restore from, and no server-side read path exists to recover the surviving checkpoint. No severity change; no new ID.
