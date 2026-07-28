# BUG-122: Checkpoint prune silently resets backend context on old conversations

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-28T14:10:02Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Observe the checkpoint retention policy at `backend/config.py:49` — the spec-26 DISK-001 fix, which prunes to the most recent 100 threads and is documented as configurable ("Set 0 to disable").
2. Confirm it is active: phase-entry counts show 100 threads retained (baseline 100thr/1930ck, in-flight 101/1932, post-restart 100/1912).
3. Hold a conversation, then let it age past the 100-most-recent window.
4. Reopen that conversation in the UI — chat history renders in full, because it is served from `localStorage`, independent of backend checkpoints.
5. Send a follow-up turn and observe the assistant answers as if it were turn 1: the backend thread's checkpoint is gone, so no prior context reaches the graph.

## Expected
If backend conversation context has been pruned, the UI either reflects that the thread can no longer be continued with context, or the backend context is reconstructed from the history the client still holds.

## Actual
The UI shows a complete conversation while the backend has no context for it, and nothing signals the divergence. The user sees their full history on screen and reasonably expects continuity; the assistant answers as though the conversation had just begun.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S1-kill-boundary-forensics.txt (gitignored) — thread/checkpoint counts at phase entry showing the 100-thread retention window in effect

## Root-cause hypothesis
MEDIUM confidence. Chat history and backend conversation state have independent lifetimes and no reconciliation: history is persisted in `localStorage` with no expiry, while backend context lives in LangGraph checkpoints subject to the 100-thread prune. Neither side is told about the other, so a pruned thread produces a UI that is fully populated and a graph that is empty. Fix surface: on send, detect that the referenced `session_id` has no surviving checkpoint and either surface it to the user or replay the locally-held history into the new thread.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Reporter: log-analyst. Dedup-checked before minting against all 94 prior records; grep for checkpoint-prune and DISK-001 coverage returned zero hits.

**Framing deliberately narrow, per log-analyst — this is NOT "unbounded history loss".** The prune is a documented, tested, configurable spec-26 DISK-001 fix, not an accident, and chat history itself is not lost (it lives in `localStorage` and still renders). The real residual is exactly one thing: resuming a conversation older than the 100 most recent gives a SILENT backend context reset, with the UI showing full history while the assistant answers as if from turn 1. Recorded at MINOR on that bounded scope.

Cross-ref BUG-064 (session id lost on remount → fresh empty thread; same user-visible symptom of a context reset, entirely different cause) and BUG-077 (New Chat leaks the prior thread forward — the inverse failure).
