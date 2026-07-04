# BUG-077: New Chat button does not reset backend session — context leaks forward

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-03T19:21:29Z in Phase 4 (P4-S1)
- **Phase scenario**: P4-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open `/chat`, ask a question (backend assigns a `session_id`, e.g. `40078e8d`).
2. Click "+ New Chat" (button, no full page reload).
3. Ask an unrelated question.
4. Inspect `query_traces` — the "new" chat carries the SAME `session_id` as the prior conversation; the LangGraph thread was silently continued, not restarted.

## Expected
"New Chat" starts a genuinely new backend conversation: a fresh `session_id` and empty LangGraph state.

## Actual
The backend thread is reused; the new conversation inherits the prior conversation's accumulated context and state. Live-reproduced during P4-S1: the Pilot's "separate new chat" for Query B (screenshot below) ran under session `40078e8d` — identical to the earlier Australia-question thread (all 3 P4-S1 `query_traces` rows — `91fead10`/`18cdf414`/`d23e4455` — form one continuous checkpoint chain).

## Artifacts
- Screenshot: screenshots/BUG-077-newchat-not-fresh.png (gitignored) — "separate new chat" run that turns out to share the prior session.
- Log excerpt: logs/BUG-077-req61-session-null.network-response (gitignored) — request 61 network response.
- Log excerpt: logs/BUG-077-req65-session-reused.network-response (gitignored) — request 65 network response showing session reuse.
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (both analysts, code + network). `frontend/hooks/useStreamChat.ts` holds `sessionIdRef` as a private ref with no reset path — the hook's return value exposes only `{messages, isStreaming, sendMessage, abort, setMessages}`, nothing that lets a caller clear the session ref. `handleNewChat()` (`frontend/app/chat/page.tsx:225-230`) clears `messages`/`historySessionIdRef`/`sessionLoadedRef` and calls `router.push("/chat")` — a soft navigation that does NOT remount the hook — but never resets `sessionIdRef`. `backend/api/chat.py:101` then honors and reuses the incoming `body.session_id`, silently continuing the old thread.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Cross-ref: BUG-064 (mirror image — that one LOSES the session on reload; this one LEAKS it forward into a chat the user believes is fresh). BUG-072 (same component family, different lifecycle defect — mid-stream navigation abort, not session identity).
