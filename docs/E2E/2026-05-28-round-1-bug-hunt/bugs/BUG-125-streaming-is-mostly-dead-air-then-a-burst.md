# BUG-125: Streaming is 85-95% dead air then a burst; answer emitted only at the end

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-07-28T14:12:00Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Send any chat question on a healthy stack — no fault injection is required, this is the normal path.
2. Record the arrival time of each NDJSON `chunk` event.
3. Observe the shape: a long silence, then all tokens at once. Measured examples — **49s of silence then 112 chunks in ~2s**, and **31s of silence then 830 chunks in ~8s**.
4. Compute the ratio: 85-95% of the visible "streaming" period carries no tokens at all.

## Expected
A streaming interface streams: tokens appear progressively across the response window, so perceived latency tracks actual progress.

## Actual
The interface presents as streaming for the whole turn while 85-95% of that window is dead air, followed by a burst delivering the entire answer in a few seconds. The user watches a blinking cursor for 31-49s with no output, then the full answer arrives at once — so the streaming affordance conveys no progress information for the great majority of the wait.

## Artifacts
- Screenshot: screenshots/P7-S1-research-phase-80s.png (gitignored) — 80s into a stream with no tokens rendered
- Log excerpt: null
- Trace: traces/P7-S1-frontend-timeline.md (gitignored)

## Root-cause hypothesis
MEDIUM-HIGH confidence. Answer text is produced only at the `collect_answer` node, at the very end of the research loop; everything before it (intent classification, query rewriting, orchestrator iterations, tool calls, reranking) produces no user-visible tokens. Token streaming is therefore faithful to the backend's actual production schedule — the tokens genuinely do not exist until the end — so this is not a transport defect. The gap is that the UI presents a token-streaming affordance during a phase that is structurally incapable of producing tokens. Fix surface is presentational rather than architectural: render pipeline-stage progress during the research phase (which the backend already emits as status events — see BUG-065) instead of an empty token stream.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Reporter: frontend-inspector. Independent of fault injection — observed on healthy turns, so this is a property of the normal path rather than a recovery defect.

Scope note: this is filed as a perceived-progress/UX defect, NOT as a latency defect. The underlying wall-clock latency is BUG-055's territory; this record is specifically about the streaming affordance conveying no information for 85-95% of the wait, which would remain true even if the total latency were within budget.

Cross-ref BUG-065 (the frontend discards the `onStatus` events that would fill exactly this window — a healthy turn carries 8 status events, so the information needed to fix this is already being sent and thrown away) and BUG-119 (the same dead-air window is what makes a working turn visually indistinguishable from a dead one).
