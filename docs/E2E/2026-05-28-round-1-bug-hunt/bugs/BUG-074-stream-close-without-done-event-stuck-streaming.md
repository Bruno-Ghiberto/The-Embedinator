# BUG-074: Stream close without a done event leaves the chat stuck streaming forever

> **FIXED 2026-09-02** by spec-31 Batch 2, tasks 2.4 and 2.3 (units 1 and 2) — commits `8b7d640`
> (Branch T, the idle watchdog) and `a29f4aa` (Branch E, the missing-terminal check). Closed only
> now because both branches were required. The filed root-cause hypothesis held, and the error
> code it proposed was renamed. See [Resolution](#resolution) below.

- **Severity**: CRITICAL
- **Layer**: Frontend
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (Q-014, P3 exit-checklist)
- **Fixed**: 2026-09-02 (spec-31 tasks 2.4 + 2.3, commits `8b7d640` and `a29f4aa`)
- **Phase scenario**: P3-S7
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
- Public evidence: public-evidence/BUG-074-075-hang-frontend-code-trace.log (tracked)

## Root-cause hypothesis
HIGH confidence, code-confirmed (frontend-inspector) — `frontend/lib/api.ts:158-159`: `const {done, value} = await reader.read(); if (done) break;` — on close, `done:true` and the loop breaks SILENTLY (no exception thrown); execution falls out of the surrounding `try`/`catch` (~`api.ts:207-208`) with NO `onDone`/`onError` call. The terminal state is reachable ONLY via the explicit `case "done"` / `case "error"` NDJSON line handlers (`api.ts:191-195`), which require the SERVER to have actually sent that line — which it never does when cancelled (see BUG-073). In `frontend/hooks/useStreamChat.ts`, the hook-level `isStreaming` (~L8) and the per-message `isStreaming` flag (~L25) are reset ONLY by `onDone` (~L90), `onClarification` (~L58), or `onError` (~L106) — none of which fire on a silent close, so both stay `true` forever. There is NO client-side timeout anywhere in the streaming path (no `setTimeout`, no `AbortSignal.timeout`); the `AbortController` only fires on an explicit user Stop / Escape action or on component unmount (see BUG-072, a related but distinct trigger).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/148
- **Rationale**: A silent reader close never fires onDone/onError, so isStreaming stays true and the stop indicator never reverts — the UI asserts "still working" indefinitely on a request that is already dead, with no client-side timeout anywhere in the path.

## Notes
Cross-refs: BUG-073 (the backend counterpart — the server-side cancellation this bug fails to detect); BUG-072 (same "stuck stream" family, but a distinct trigger — component unmount + explicit abort, vs this bug's abnormal external close with no exception at all); the broader known gap of "no client-side streaming timeout" applies to both.

Fix surface: track a `receivedTerminalEvent` flag in the reader loop — if it exits without having seen `done`, `error`, or `clarification`, call `onError("Stream ended unexpectedly", "STREAM_INCOMPLETE")`; additionally add a client-side idle timeout so a silent stream cannot hang indefinitely regardless of cause.

**⚠ NAME CORRECTED IN SHIPPING, 2026-09-02.** The code proposed above is `STREAM_INCOMPLETE`; the
code that shipped is **`STREAM_TRUNCATED`** (design D3 / task 2.3), with the message "Stream ended
without completion". Both halves of the proposed fix surface shipped, in the order given: the
client-side idle timeout as Branch T (`STREAM_STALLED`), the terminal-event check as Branch E.

**UPDATE 2026-07-03 (P4-S4 repro)**: same stuck-stream symptom reproduced after the BUG-082 unbounded ambiguous-intent loop was cancelled at the ~30s idle cutoff — empty skeleton + Stop button stuck active, no `done` event ever received, matching the mechanism above exactly. Confirms the frontend has no defense against a silent close regardless of the backend-side root cause (slow research loop, per the original finding, OR an intent-routing infinite loop, per BUG-082). Cross-ref BUG-082.

**P4-S4 final-state CAVEAT (2026-07-03, frontend-inspector late passive read)**: the stuck-skeleton was observed FOREGROUND only ~2 min before the tab was backgrounded ~4h (Pilot EOD). The state later surfaced "Stream read error: network error" + Retry via `net::ERR_NETWORK_IO_SUSPENDED` (trace `56c94450`, reqid 447 — status 200 then response body discarded by DevTools), which is a Chrome backgrounded-tab IO-suspension artifact, NOT the product's natural foreground recovery. So this instance does NOT cleanly prove "stuck-forever" on the foreground timeline — the ~2min foreground stuck window is consistent with BUG-074, but the eventual error is a backgrounding artifact. Re-observe the foreground stuck-timeline on the P4-S4 re-run.

**UPDATE 2026-07-08 (P4-S6 induced-timeout repro)**: same user-visible symptom reproduced during the induced-Ollama-pause probe (trace `8ba310a8-661e-4979-a9b3-b54480ec298b`, collection `nag-corpus-bm25`) — the assistant bubble rendered EMPTY (no text, no error, no Retry) after the frontend eventually gave up client-side, while the backend task remained hung server-side (see BUG-088, the new root cause: an in-flight LLM `ainvoke()` call has no enforced timeout and blocks the graph forever — `max_loop_seconds` is only checked at the edge function, which never runs while a node is stuck mid-await). Confirms the frontend-gives-up / backend-keeps-running split: this record's mechanism (no client-side terminal-event detection) is the frontend half; BUG-088 is the newly-identified backend half for THIS specific trigger (an unbounded in-flight LLM call, distinct from the BUG-054/073 idle-timeout-cancellation trigger this record originally documented). Pilot screenshot: empty bubble, nag-corpus-bm25, ~2026-07-08T16:59Z local.

**Scenario id normalized 2026-07-28 (schema compliance, no semantic change)**: `scenario_id` set to `P3-S7`; originally logged as `Q-014 (P3 exit-checklist, analytical multi-source)`, which does not satisfy the `bug-registry-schema.json` pattern `^P[0-7]-S[0-9]+$`. Phase 3 ran P3-S1..S6, so the exit checklist is its 7th step. The `Discovered` line above retains the original `Q-014` provenance verbatim.

**UPDATE 2026-07-28 (P7-S1 backend-kill mid-stream — strongest evidence to date)**: reproduced under a hard backend kill, and sustained far past any prior observation. Timeline (thread `d4303789-f4f9-4938-a52f-f162afd7d8c3`, trace `33a1816c-6e8e-4c04-a8ad-b3b04d4bbf53`): stream opened 14:02:11Z, the `session` event at +16ms was the ONLY byte the server ever sent; `docker kill embedinator-backend` at +187s; backend restarted and `/api/health` returned healthy at +16s after restart; at **+189s post-kill / +79s AFTER the backend was healthy again** the stream was STILL open, `endKind: null`, "Stop generation" still rendered, no error, no explanation. This record's registered mechanism is confirmed verbatim: `frontend/lib/api.ts:158-160` breaks on transport EOF with NO terminal callback, so `onDone`/`onError` never run, so `setIsStreaming(false)` (`useStreamChat.ts:91`/`:107`) never runs; the `AbortController` at `api.ts:130` is wired only to user abort (`useStreamChat.ts:116-120`) and unmount cleanup (`:122-126`) — there is no `AbortSignal.timeout` and no watchdog anywhere in the path. Artifacts: screenshots/P7-S1-post-kill.png, screenshots/P7-S1-post-restart-noreload.png, traces/P7-S1-frontend-timeline.md.

**Registrar note on scope**: this update was routed as a candidate NEW CRITICAL finding; it was dedup-matched to THIS record instead, because the proposed finding cited the same file, the same lines (`api.ts:158-160` vs the `158-159` already recorded), the same mechanism and the same consequence. No new ID was minted. **Severity remains MAJOR pending Lead adjudication** — the registrar does not self-adjudicate severity. The escalation case is recorded here for that decision: unlike the earlier ~30s idle-timeout repros, the dead spinner here survived a full backend recovery, so a user watching a healthy-looking application waited on a conversation that could never complete. The record's existing severity note held MAJOR on the grounds that "the user-facing no-answer harm is already carried by BUG-074/BUG-088" — that reasoning belongs to BUG-073; here BUG-074 IS the user-facing harm. Cross-ref BUG-119 (the separate finding that the resulting state is indistinguishable from healthy work and is contradicted by recovering global chrome).

**SECOND, INDEPENDENT DEFECT OBSERVED — NOT part of this record, flagged as HYPOTHESIS**: neither the application's reader nor an independent in-page `response.body.tee()` ever received EOF at all, for the full 189s after SIGKILL — the TCP/HTTP response stayed open although the upstream process was dead. Inspector hypothesis: the Next.js `rewrites()` proxy holds the downstream client response open after the upstream socket dies. Explicitly NOT asserted — the inspector did not re-kill to isolate it and flagged it as needing log-analyst corroboration. Recorded here so the evidence is not lost, and deliberately NOT registered as a finding pending corroboration. Note the consequence if confirmed: BOTH layers are broken independently — the transport never delivers EOF, AND `api.ts:160` would wedge anyway if it did — so fixing this record alone would not resolve the observed hang.

**SEVERITY ESCALATED MAJOR -> CRITICAL, 2026-07-28 (team-lead ruling, apply-7).** Basis: the dead spinner survived a COMPLETE backend recovery — the user watched a healthy-looking application while their conversation could never complete. The prior MAJOR rationale held that "the user-facing no-answer harm is already carried by BUG-074/BUG-088"; that reasoning belongs to BUG-073, and here BUG-074 IS the user-facing harm. Triage decision is unchanged (`v1.0-fix`); the public issue label requires the corresponding MAJOR -> CRITICAL edit.

**CONTROL CASE — the sharpest available framing of this defect (frontend-inspector).** When the response carries a NON-OK HTTP status, the error path works CORRECTLY: the spinner clears, error text renders, and Retry is offered (`frontend/lib/api.ts:138-145`). The failure occurs ONLY for transport-level termination of a stream that has ALREADY returned 200. So this is not "error handling is missing" — error handling exists and is correct for HTTP-status failures, and is entirely absent for transport termination. One defect, precisely bounded.

**BACKEND-SIDE EVIDENCE — P7-S1d, the genuine mid-generation kill (2026-07-28T14:32:01.302Z, `docker kill embedinator-backend`, exit 137).** Attempts 1-3 missed the premise (one hit a BUG-054 wedge, two hit already-completed turns); attempt 4 landed the kill **6 chunks into visible token generation**, on a fresh session (turn 1, avoiding the classifier-degradation trap), warm model, issued direct to `:8000` so the Next proxy could not confound it. At-kill snapshot: 6 chunks, 8 status, 1 session — **no `done`, no `error`**. The final stream ends mid-sentence on `{"type":"chunk","text":" detailed"}`. It does not close; it stops. The user was left looking at: *"The provided passages do not contain detailed"*.

**Durability across all three kill timings:**

| Kill timing | checkpoints | trace row | client stream |
|---|---|---|---|
| wedged, pre-graph (S1 #1) | 2 | 0 | never terminated |
| **mid-generation (S1d)** | **13** (steps -1..7) | **0** | **cut mid-sentence, no terminal event** |
| already completed (S1c) | 20 | 1 | complete |

**What this establishes, and it cuts both ways.** Graph state IS durably persisted up to the last completed superstep — 13 checkpoints survived an unclean SIGKILL, and that half is genuinely engineered and works. But the GENERATED ANSWER TEXT is not persisted: tokens stream to the client and are checkpointed only when their superstep completes, so the 7 chunks the user watched exist solely in the browser DOM — not in any checkpoint, not in a trace row. The sharp consequence, which directly sharpens P7-S5: **a resume restores 13 checkpoints of state and still cannot reproduce the one thing the user actually saw.** "The checkpoint survived" and "the user's turn is recoverable" are different claims, and this is the empirical separation of the two. Artifacts: traces/P7-S1d-mid-generation-kill.md, traces/P7-S1d-stream.ndjson, traces/P7-S1d-at-kill.ndjson.

## Resolution

**FIXED** — spec-31 Batch 2, tasks 2.4 (Branch T) and 2.3 (Branch E). Commit `8b7d640`
(2026-08-31, 9 files, +529/−29, shared with BUG-054 and BUG-040) and commit `a29f4aa` (2026-09-02,
4 files, +510/−3, shared with BUG-119). The record was held open until both landed.

**The filed hypothesis held, verbatim and in both files it named.** `api.ts`'s reader loop broke on
transport EOF without calling any terminal callback, so `onDone`/`onError` never ran, so
`useStreamChat`'s `setIsStreaming(false)` never ran; the `AbortController` was wired only to user
abort and unmount. The inspector's control case is what made the boundary exact: a non-OK HTTP
status already cleared the spinner and offered Retry correctly. The defect was never "error
handling is missing"; it was that error handling did not cover transport termination.

**Two branches were required, and the reason is BUG-123.** Branch E's check runs *after* the read
loop exits — and on the proxied path that loop never exits, because the proxy never delivers EOF.
Branch T is what ends a stream that the transport will not end. Neither branch alone closes the
user-visible symptom, which is exactly what BUG-123 predicted before either shipped.

**Branch T — `frontend/hooks/useStreamChat.ts`.** `STREAM_IDLE_TIMEOUT_MS = 120_000` (at least twice
the 31.1 s cold first call measured on the live stack — the floor `next-config.test.ts` asserts;
120 s is nearly four times it. The largest warm gap was 14.8 s, and the value sits strictly inside
`proxyTimeout`'s 600 s). The timer is armed before the request leaves, re-armed on every progress
frame, and disarmed on `done`/`error`/`clarification`, on abort and on unmount. On expiry it aborts
the controller first — `api.ts` swallows the resulting `AbortError`, so nothing can touch the
bubble afterwards — then reports `STREAM_STALLED` with the partial content preserved. A
`watchedStreamIdRef` ownership check keeps the shared timer bound to the newest stream, so a Retry
on an older bubble cannot disarm a live one; that defect was found in review of this commit and
fixed inside it.

*Why nothing could be deleted or relaxed instead:* no layer below the client can end a stream that
is ESTAB with no upstream socket. The proxy holds it open (BUG-123) and cannot be disabled, only
given a longer window; and a backend heartbeat would make a hung turn look alive rather than end
it. A client-side timer is the only place where "no bytes for 120 s" is observable.

**Branch E — `frontend/lib/api.ts`.** A `sawTerminal` flag is set by the `done`, `error` and
`clarification` line handlers. If the loop exits without it, and the client did not abort, the
reader calls `onError("Stream ended without completion", "STREAM_TRUNCATED")` exactly once. The
abort condition matters: a user Stop must stay silent, not raise an error the user caused.

**Evidence.**

- Branch T: `frontend/tests/unit/use-stream-chat-stall.test.ts` drives the real `api.ts` with a
  stubbed fetch and proves exactly one terminal error; `frontend/tests/unit/hooks.test.ts` covers
  arm / re-arm / disarm / ownership. Frontend suite after unit 1: **96 passed** (74 before).
- Branch E: `frontend/tests/unit/api.test.ts` (+238 lines) and the page-level
  `frontend/tests/unit/chat-page-single-owner.test.tsx`, which runs the real page, the real hook
  and the real `api.ts` together. Frontend suite after unit 2: **105 passed**.
- Live stack, Branch T, 2026-09-02 — `docker kill embedinator-backend` mid-turn at `:3000`: the
  page still rendered "Stop generation" at +85 s and, at **+129 s**, rendered
  `"The response stalled: no data for 120s."` with a Retry button. The watchdog ended a dead
  proxied stream inside its 120 s budget measured from the last received frame:
  [`../public-evidence/spec-31-b2-gc2/browser-probe-2026-09-02.md`](../public-evidence/spec-31-b2-gc2/browser-probe-2026-09-02.md).
- Branch E has **no browser-level proof through the proxy, by construction**: the proxy never
  delivers EOF (BUG-123), so the code path Branch E guards is not reachable at `:3000`. Its
  integration evidence is the page-level vitest test named above.

**Still open / follow-ups.**

- Watchdog ownership is never released after a terminal frame, so a post-`done` progress frame
  (the backend emits none today) would re-arm the timer for a finished bubble. Hardening candidate;
  needs its own RED test.
- A non-2xx response whose body then stalls ≥ 120 s reports `UNKNOWN` rather than `STREAM_STALLED`:
  `res.json()` swallows the abort and the error path overwrites the code. The terminal state is
  still correct; only the code is unstable on that narrow path.
- A `done`/`error` frame arriving without a trailing newline is dropped by the line splitter and
  now reports `STREAM_TRUNCATED`. Unreachable — every emit site in `backend/api/chat.py` appends
  `\n` — and recorded rather than fixed.
- Starting a New Chat mid-stream never aborts the live stream, so the orphan's terminal frame can
  still clear `isStreaming` for a newer turn. Pre-existing, not introduced here; parked for Batch 5
  (tasks 5.2 and 5.4).
- When partial content has already streamed, `STREAM_STALLED` is never shown as text:
  `useStreamChat.ts:59` writes `content: msg.content || message`, so the stall sentence replaces the
  bubble only when nothing arrived. Observed 2026-09-09 at the Batch 2 exit gate — the terminal
  state is still carried by the error styling, the `Retry` control and `errorCode`, but the reason
  the answer stopped is not stated. UX follow-up.
