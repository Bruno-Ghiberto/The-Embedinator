# BUG-072: Mid-stream navigation silently aborts the answer with no feedback or recovery

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (P3-S6)
- **Phase scenario**: P3-S6
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. On `/chat`, send a query; while the answer is STREAMING (red ■ stop button visible)...
2. Navigate to a different page via the left rail (Collections or Observability) before it completes.
3. Navigate back to `/chat`.
4. Observe: the assistant answer bubble is EMPTY — no content, no error, no partial text, no "interrupted"/cancelled marker, no retry. The stream did NOT complete in background and did NOT resume; the answer is silently lost.

## Expected
The stream either cancels gracefully (a clear interrupted/cancelled state, or the pending turn is removed) OR completes in background and shows on return. Neither documented behavior occurs.

## Actual
Navigating away mid-stream silently kills the in-flight answer with zero user feedback — no error, no partial content, no interrupted marker — and the user returns to a dead/empty answer bubble.

## Artifacts
- Screenshot: screenshots/BUG-072-mid-stream-navigating-away.png (gitignored) — streaming state, red stop button visible.
- Screenshot: screenshots/BUG-072-empty-answer-on-return.png (gitignored) — empty answer bubble after returning to /chat.
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (frontend-inspector) — `useStreamChat.ts:121-125`: an empty-dependency-array `useEffect` cleanup calls `controllerRef.current?.abort()` on UNMOUNT. A route change unmounts `ChatPageContent`, which unmounts this hook, which aborts the in-flight fetch (`api.ts:134`, `signal` wired to the same controller). The abort is SILENT BY DESIGN: `api.ts:200-201` and `209-210` explicitly EXCLUDE `AbortError` from the `onError` path, so no error event, no callback, nothing surfaces to the UI. There is no background-complete path either — the stream reader (`res.body.getReader()`) lives inside the torn-down hook closure, with no service worker or detached reader to keep it alive. There is no graceful-cancel path — unmount bypasses the hook's own explicit `abort()` (`~L115-119`, which at least flips `isStreaming`), and nothing marks the individual message as interrupted (the `ChatMessage` type has `isError`/`clarification`/`traceId` fields, but none of them are set on an abort-via-unmount). There is no resume/persistence either — the interrupted turn existed purely in hook React state and never reached the `wasStreaming → !isStreaming` localStorage sync at `chat/page.tsx` (~L119-131).

Post-return nuance: code analysis predicts the interrupted turn should be ABSENT entirely after a true remount (nothing persisted it); the observed screenshot instead shows an EMPTY bubble in place, which is more consistent with Next.js 16's Router Cache showing a stale mid-stream snapshot of the `/chat` route segment (no `staleTimes` override found in `next.config.ts`). Either mechanism produces the same user-facing outcome: the answer is lost with no feedback.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
No documented cancel-or-background policy exists for this scenario — per the P3-S6 playbook scenario, "the absence of clear policy is itself a MAJOR finding," which applies here directly (sidebar-toggle sub-variant of this same scenario PASSED cleanly; only the route-change sub-variant fails).

Cross-refs: BUG-064 (SAME unmount trigger — a route change unmounting the chat page — but a DISTINCT defect: BUG-064 is backend `session_id`/history persistence being lost; BUG-072 is the in-flight stream's lifecycle and total absence of interruption feedback; different fix surfaces, do not merge). BUG-067 (another unmount/lifecycle-adjacent race in the same chat-page component family — grouped as a related-trigger cluster, not the same bug).

Fix-surface note for spec-31: either (a) on abort-via-unmount, mark the message `interrupted` and offer a retry affordance, or (b) detach the stream reader from the component's lifecycle so it survives navigation (true background-complete + persist-and-restore on return).

No trace_id — the stream was aborted before a `query_traces` row was written; evidence is code-path analysis plus the two screenshots. Lead+Pilot approved MAJOR/Frontend.
