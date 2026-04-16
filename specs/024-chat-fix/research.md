# Research: Chat & Agentic RAG Pipeline Fix

**Feature**: 024-chat-fix | **Date**: 2026-03-27

## Status: No Unknowns

All technical questions were resolved empirically during the 2026-03-27 diagnostic session. This research document records the verified findings as decisions.

## Decision 1: Backend NDJSON Streaming

**Decision**: Backend is NOT the root cause. NDJSON streaming works correctly.
**Rationale**: Verified via `curl POST localhost:8000/api/chat` — produces complete stream (session, status × 4, chunk, citation, confidence, groundedness, done). Same output through Next.js proxy on port 3000.
**Alternatives considered**: Backend buffering, incorrect Content-Type — ruled out by curl evidence.

## Decision 2: Frontend Rendering is the Root Cause

**Decision**: The bug is in the frontend React rendering chain, not the backend or proxy.
**Rationale**: Backend produces correct output. Proxy forwards it correctly. Frontend container rebuild didn't fix it (ruling out stale code). The browser shows skeleton bars indefinitely — the `onToken` callback is either never called or its state updates are overwritten.
**Alternatives considered**: Next.js rewrite buffering — ruled out by curl through port 3000 showing streaming works.

## Decision 3: Dual localStorage System is Prime Suspect

**Decision**: The dual localStorage system (`useChatStorage` legacy + `useChatHistory` v1) likely causes race conditions that overwrite streaming state.
**Rationale**: `ChatPageContent` has 3+ `useEffect` hooks calling `setMessages`. The hydration effect (line 124-129) reads from `useChatStorage` (legacy) and can overwrite the messages array after `sendMessage` creates the assistant placeholder. The `onToken` callback then finds no matching message ID and silently does nothing.
**Alternatives considered**: Single system (`useChatHistory` only) — this is the recommended fix direction.

## Decision 4: CallLimitCallback Regression

**Decision**: The instantiation at `chat.py:156` hardcodes old limits (20/10) despite class defaults being 100/50.
**Rationale**: Backend logs show `call_limit_llm_exceeded` at 21 LLM calls vs max 20. The BUG-012 fix changed class defaults but not the instantiation site.
**Alternatives considered**: None — this is a clear regression. Fix: use default args `CallLimitCallback()`.

## Decision 5: Citation Deduplication Strategy

**Decision**: Deduplicate at the NDJSON emission point (`chat.py:211-217`), not in the state reducer.
**Rationale**: `Send()` fan-out creates N sub-question research loops. Each appends citations via the state reducer (`operator.add`). Dedup in the reducer would require tracking across parallel branches (complex). Dedup at emission is simpler — `passage_id` as unique key, applied once before the yield.
**Alternatives considered**: Dedup in state reducer — rejected because it adds complexity to LangGraph state management with no benefit.

## Decision 6: Sidebar Fix Approach

**Decision**: Use URL-based signaling (`?new=1`) for sidebar "New Chat" button.
**Rationale**: `SidebarNav` is a separate component without access to `ChatPageContent` state. URL params are the existing state management pattern (collections, session, llm, embed are all URL params). Adding `?new=1` is consistent and requires no new abstractions.
**Alternatives considered**: (A) Shared context/hook — adds complexity violating Principle VII. (B) Custom DOM event — fragile and non-standard. (C) URL param — chosen for simplicity.
