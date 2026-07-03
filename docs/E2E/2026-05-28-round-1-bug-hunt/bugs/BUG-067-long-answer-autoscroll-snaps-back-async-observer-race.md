# BUG-067: Long-answer auto-scroll snaps back once on scroll-up (async observer race)

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-26T20:10:00Z in Phase 3 (P3-S3)
- **Phase scenario**: P3-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send a query producing a long streamed answer that overflows the viewport.
2. As tokens stream, scroll up to re-read earlier text.
3. Observe one involuntary snap-back to bottom before subsequent tokens respect the user's position.

## Expected
When the user scrolls up mid-stream, auto-scroll disables immediately and all subsequent tokens respect the user's position without snapping back to bottom.

## Actual
Exactly one snap-back to bottom occurs after the user scrolls up (one more token fires scrollIntoView("smooth") before the IntersectionObserver disables auto-scroll). Subsequent tokens then respect the user's position. A second snap can occur on stream completion (onDone updates messages) if the observer hasn't yet fired.

## Artifacts
- Screenshot: screenshots/BUG-067.png (gitignored)
- Log excerpt: logs/BUG-067.log (gitignored)
- Trace: null

## Root-cause hypothesis
ChatPanel.tsx:43-65 — IntersectionObserver (async; fires after paint/rAF) sets shouldAutoScrollRef.current; useEffect([messages]) (sync; fires after React commit) reads it → one-render race window. Guard B (ScrollToBottom.tsx:22-29) uses a synchronous scroll listener correctly; Guard A should do the same. Suggested fix: replace Guard A's IntersectionObserver with a synchronous scroll event listener setting shouldAutoScrollRef directly (same pattern as Guard B).

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
REQUIRED CAVEAT (Pilot decision): auto-scroll-present was LIVE-confirmed (P3-S3, 2026-06-26, hunt-pdfs); the one-snap-back was NOT live-reproducible this session because the model returned short answers that didn't overflow enough to scroll up mid-stream. Defect is code-confirmed at HIGH confidence (deterministic async/sync race, frontend-inspector). No clipping risk (container overflow-y-auto + min-h-0 + h-full, no max-height — code-confirmed). User impact: mildly disorienting, self-corrects after one snap, does not prevent reading. Primary artifact: frontend/components/ChatPanel.tsx:43-65.
