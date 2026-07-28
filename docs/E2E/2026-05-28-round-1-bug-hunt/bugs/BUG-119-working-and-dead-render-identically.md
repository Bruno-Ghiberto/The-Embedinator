# BUG-119: Working and permanently dead render as the same screen; chrome contradicts it

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-28T14:08:27Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Send an analytical chat question and let the stream run (P7-S1: 187s of open stream, zero bytes after the initial `session` event).
2. Capture the in-progress UI (`screenshots/P7-S1-pre-kill.png`) — pulse skeleton + blinking cursor.
3. `docker kill embedinator-backend`, wait, then `docker compose up -d backend` and let health recover.
4. Capture again with no reload (`screenshots/P7-S1-post-restart-noreload.png`) — 79s after the backend is healthy again, 189s after the kill.
5. Compare the two captures: they differ only in the phase of the caret blink.

## Expected
A conversation that is still being worked on and a conversation that is permanently dead are visually distinguishable, so the user can tell whether waiting is rational.

## Actual
The two states are pixel-equivalent apart from caret blink phase. Worse, the only liveness signals in the product are GLOBAL chrome — the health banner and the composer placeholder — and those recover to a healthy appearance once the backend restarts, while the conversation itself stays permanently dead. The chrome therefore actively asserts that the system is working over a conversation that can never complete, so the single strongest signal available to the user points the wrong way.

## Artifacts
- Screenshot: screenshots/P7-S1-post-restart-noreload.png (gitignored) — banner recovered to "Backend connected", spinner still alive on a dead conversation
- Log excerpt: null
- Trace: traces/P7-S1-frontend-timeline.md (gitignored) — full timeline incl. the pre-kill/post-restart capture pair

## Root-cause hypothesis
MEDIUM-HIGH confidence. There is no per-conversation liveness model in the UI: streaming state is a boolean (`isStreaming`) with no notion of "last byte received at", so the renderer cannot distinguish "waiting on a slow but live stream" from "waiting on a stream that will never produce another byte". Health state is tracked globally by `BackendStatusProvider` (`frontend/components/BackendStatusProvider.tsx:43-48`, SWR poll at `refreshInterval: 5000`) and is entirely decoupled from any individual conversation's state, so it recovers independently of whether in-flight work survived. Fix surface: track a per-stream last-activity timestamp and surface a stalled/dead state, and stop letting global health imply conversation health.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/169
- **Rationale**: The product's only liveness signals revert to "healthy" while the conversation is permanently dead, so the UI actively tells the user the system is working when their request can never complete — a false statement about system state on the primary surface.

## Notes
Reporter: frontend-inspector (Playwright MCP). Dedup-checked before minting against all 94 prior records.

**Deliberately scoped to be DISTINCT from BUG-074, not a duplicate of it.** BUG-074 is the mechanism — the reader loop breaks on EOF with no terminal callback, so `isStreaming` is never reset. THIS record is the separate finding that the resulting state is indistinguishable from healthy work AND is contradicted by recovering global chrome. BUG-074's fix (fire a terminal callback) would resolve this symptom too, but the underlying gap — no per-conversation liveness model, global health implying conversation health — would survive any narrow fix to the reader loop. Cross-ref BUG-074 (mechanism), BUG-065 (backend emits no status events during the research loop, so even a correctly-wired stage indicator would render nothing across the whole 187s).

**MERGED EVIDENCE 2026-07-28 (P7-S1 D2, team-lead routed as a candidate separate finding; folded here rather than minted)**: during a permanently wedged turn the composer stays ENABLED and the banner reads "Backend connected", so a user can pile further messages onto a conversation that is already dead. Dedup reasoning: this is the same defect this record registers — global chrome asserting health over a dead conversation — observed on a second surface (the composer's enabled state) rather than a distinct mechanism. The contradiction, its cause (health state is global and decoupled from any individual conversation) and its fix surface are identical, so it is recorded as additional evidence rather than a duplicate ID.

Consequence worth stating explicitly, because it is worse than a passive display bug: the user is not merely misinformed, they are actively INVITED to keep working. Every subsequent message is accepted by an interface that cannot deliver it.
