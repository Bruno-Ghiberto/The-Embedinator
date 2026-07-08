# BUG-074: Stream close without a done event leaves the chat stuck streaming forever

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Phase scenario**: Q-014 (P3 exit-checklist, analytical multi-source)
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. During a streaming answer, the connection closes abnormally (proxy idle timeout / reset) BEFORE the backend emits a `done` or `error` NDJSON event — reproduced via Q-014's first run (trace `cda553a5`, cancelled by the ~30s idle timeout mid-stream, see BUG-073/BUG-054).
2. Observe: the UI stays streaming forever — the red ■ stop indicator never reverts, `isStreaming` stays `true`, no error surfaces, no recovery path. The only escape is a manual Stop click, a page reload (which loses the in-progress work), or a backend restart.
3. Confirm there is NO client-side timeout anywhere in the streaming path.

## Expected
The client detects an abnormal stream close (the connection ended with no terminal event) and surfaces an error, offers a retry, or resets the streaming state on its own.

## Actual
The reader loop exits silently when the connection closes with no terminal NDJSON line; nothing resets `isStreaming`, so the UI is stuck in a permanent streaming state with no feedback and no client-driven recovery.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-074-075-hang-frontend-code-trace.log (gitignored) — frontend-inspector's code trace, covers both BUG-074 and BUG-075.
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (frontend-inspector) — `frontend/lib/api.ts:158-159`: `const {done, value} = await reader.read(); if (done) break;` — on close, `done:true` and the loop breaks SILENTLY (no exception thrown); execution falls out of the surrounding `try`/`catch` (~`api.ts:207-208`) with NO `onDone`/`onError` call. The terminal state is reachable ONLY via the explicit `case "done"` / `case "error"` NDJSON line handlers (`api.ts:191-195`), which require the SERVER to have actually sent that line — which it never does when cancelled (see BUG-073). In `frontend/hooks/useStreamChat.ts`, the hook-level `isStreaming` (~L8) and the per-message `isStreaming` flag (~L25) are reset ONLY by `onDone` (~L90), `onClarification` (~L58), or `onError` (~L106) — none of which fire on a silent close, so both stay `true` forever. There is NO client-side timeout anywhere in the streaming path (no `setTimeout`, no `AbortSignal.timeout`); the `AbortController` only fires on an explicit user Stop / Escape action or on component unmount (see BUG-072, a related but distinct trigger).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Cross-refs: BUG-073 (the backend counterpart — the server-side cancellation this bug fails to detect); BUG-072 (same "stuck stream" family, but a distinct trigger — component unmount + explicit abort, vs this bug's abnormal external close with no exception at all); the broader known gap of "no client-side streaming timeout" applies to both.

Fix surface: track a `receivedTerminalEvent` flag in the reader loop — if it exits without having seen `done`, `error`, or `clarification`, call `onError("Stream ended unexpectedly", "STREAM_INCOMPLETE")`; additionally add a client-side idle timeout so a silent stream cannot hang indefinitely regardless of cause.

**UPDATE 2026-07-03 (P4-S4 repro)**: same stuck-stream symptom reproduced after the BUG-082 unbounded ambiguous-intent loop was cancelled at the ~30s idle cutoff — empty skeleton + Stop button stuck active, no `done` event ever received, matching the mechanism above exactly. Confirms the frontend has no defense against a silent close regardless of the backend-side root cause (slow research loop, per the original finding, OR an intent-routing infinite loop, per BUG-082). Cross-ref BUG-082.

**P4-S4 final-state CAVEAT (2026-07-03, frontend-inspector late passive read)**: the stuck-skeleton was observed FOREGROUND only ~2 min before the tab was backgrounded ~4h (Pilot EOD). The state later surfaced "Stream read error: network error" + Retry via `net::ERR_NETWORK_IO_SUSPENDED` (trace `56c94450`, reqid 447 — status 200 then response body discarded by DevTools), which is a Chrome backgrounded-tab IO-suspension artifact, NOT the product's natural foreground recovery. So this instance does NOT cleanly prove "stuck-forever" on the foreground timeline — the ~2min foreground stuck window is consistent with BUG-074, but the eventual error is a backgrounding artifact. Re-observe the foreground stuck-timeline on the P4-S4 re-run.

**UPDATE 2026-07-08 (P4-S6 induced-timeout repro)**: same user-visible symptom reproduced during the induced-Ollama-pause probe (trace `8ba310a8-661e-4979-a9b3-b54480ec298b`, collection `nag-corpus-bm25`) — the assistant bubble rendered EMPTY (no text, no error, no Retry) after the frontend eventually gave up client-side, while the backend task remained hung server-side (see BUG-088, the new root cause: an in-flight LLM `ainvoke()` call has no enforced timeout and blocks the graph forever — `max_loop_seconds` is only checked at the edge function, which never runs while a node is stuck mid-await). Confirms the frontend-gives-up / backend-keeps-running split: this record's mechanism (no client-side terminal-event detection) is the frontend half; BUG-088 is the newly-identified backend half for THIS specific trigger (an unbounded in-flight LLM call, distinct from the BUG-054/073 idle-timeout-cancellation trigger this record originally documented). Pilot screenshot: empty bubble, nag-corpus-bm25, ~2026-07-08T16:59Z local.
