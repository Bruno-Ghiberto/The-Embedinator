# GC-2 browser half — live-stack probe, 2026-09-02 (watchdog / Branch T)

Instrument: Playwright MCP against the running Docker stack (`the-embedinator-frontend:latest`
built 2026-08-31T11:41:10-03:00, 15 s after commit 8b7d640 — carries the unit-1 watchdog,
not unit 2). Backend killed with `docker kill embedinator-backend` (exit 137). Note: a manual
`docker kill` bypasses `restart: unless-stopped`; the container stayed Exited until started by hand.

| UTC | Event | Page state (accessibility snapshot, verbatim) |
|---|---|---|
| 13:02:22 | question submitted at `:3000/chat?collections=67f187b8…` (arcas-new, qwen2.5:7b) | textbox active; `button "Stop generation"` rendered |
| 13:02:41.565 | `docker kill embedinator-backend` → `Exited (137)` | — |
| 13:03:19 (+37 s) | poll | banner `Connecting to backend...`; textbox `Waiting for backend to start...`; `button "Stop generation"` still rendered |
| 13:04:07 (+85 s) | poll | unchanged: still `button "Stop generation"` (streaming state) |
| 13:04:50.804 (+129 s) | poll | `paragraph: "The response stalled: no data for 120s."` + `button "Retry"`; composer `[disabled]`; banner `Connecting to backend...` |

Verdict: the client-side watchdog (`STREAM_IDLE_TIMEOUT_MS = 120_000`, `useStreamChat.ts`,
commit 8b7d640) terminated the dead proxied stream between +85 s and +129 s after the kill —
inside the 120 s budget measured from the last received frame — and rendered a distinguishable
error state (BUG-119 symptom: working vs dead now render differently) with a Retry affordance.
Screenshot: `browser-probe-2026-09-02-post-watchdog.png`.

This closes the "STILL OPEN: browser half" item of `LAUNCH-BATCH-2.md §4`. It exercises Branch T
only; Branch E (unit 2, commit 7e05c75) is not reachable through the proxy (BUG-123: the proxy
never delivers EOF) and is proven by the page-level vitest test
`frontend/tests/unit/chat-page-single-owner.test.tsx` (real page + real hook + real api.ts).

## Post-restart timeline (BUG-119 contradiction + BUG-124 side-observation)

| UTC | Event | Page state (verbatim) |
|---|---|---|
| 13:05:26.352 | `docker start embedinator-backend` (manual; kill had bypassed the restart policy) | — |
| 13:05:51.504 | container health = `healthy` | — |
| 13:05:57 (+6 s healthy) | poll | banner `Connecting to backend...`; textbox `Waiting for backend to start...` `[disabled]`; error bubble `"The response stalled: no data for 120s."` + `button "Retry"` persists |
| 13:06:22 (+31 s) | poll | unchanged — banner still `Connecting to backend...` (screenshot `browser-probe-2026-09-02-post-recovery-31s.png`) |
| 13:07:16 (+85 s) | poll | unchanged — banner still `Connecting to backend...` |
| 13:09:08 (+197 s) | poll | banner `Backend connected` + `button "Dismiss status banner"`; textbox `Ask a question...` enabled; error bubble + `button "Retry"` PERSISTS (screenshot `browser-probe-2026-09-02-post-recovery-final.png`) |

Readings:
- **BUG-119**: after full backend recovery the conversation still shows its dead state (red stalled bubble + Retry) while the chrome reports healthy — the two no longer contradict each other. Before unit 1 the same timeline showed a live-looking streaming bubble 79 s after recovery (P7-S1).
- **BUG-124 (unit 3, task 2.6) observed live**: the global banner/composer stayed locked in `Connecting to backend...` for more than 85 s and at most 197 s after the container was healthy. The record's "31–60 s" lockout is an under-estimate on this run.
