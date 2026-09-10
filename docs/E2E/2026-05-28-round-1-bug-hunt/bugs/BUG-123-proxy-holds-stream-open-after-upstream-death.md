# BUG-123: proxy holds client stream open after upstream socket dies

> **FIXED 2026-09-09** by spec-31 Batch 2, task 2.4 (unit 1) — commit `8b7d640`; re-probed on the
> final images at the Batch 2 exit gate. The user-visible defect is closed: a proxied stream whose
> upstream dies now reaches a terminal, retryable state 120.000 s after its last received frame,
> instead of staying open indefinitely. **The proxy's own behaviour is unchanged** — it still never
> delivers EOF — so the mechanism this record registers is bounded, not repaired, and the "why"
> question below stays open as a proxy-layer question. See [Resolution](#resolution).
>
> **History — CONFIRMED 2026-08-05** by the spec-31 task 1.6 isolation probe. The `UNCONFIRMED`
> marker was removed from the title because the qualification it protected no longer applied —
> see [`../BUG-123-PROBE-VERDICT.md`](../BUG-123-PROBE-VERDICT.md). Triage moved
> `v1.1-defer` → `v1.0-fix`; scope 38 → 39; design decision D3 **Branch T** activated. Batch 1
> established the mechanism and nothing more; confirmation was never a fix, and the fix was
> task 2.4 in Batch 2.

- **Severity**: MAJOR
- **Layer**: Infrastructure
- **Discovered**: 2026-07-28T14:08:27Z in Phase 7 (P7-S1)
- **Confirmed**: 2026-08-05 (spec-31 task 1.6)
- **Fixed**: 2026-09-09 (spec-31 task 2.4, commit `8b7d640`; exit-gate re-probe 2026-09-09)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Open a chat stream through the Next.js proxy (browser → `localhost:3000` → `rewrites()` → backend `:8000`) and let it run.
2. `docker kill embedinator-backend` while the stream is open.
3. Observe on the PROXIED path: neither the application's reader nor an independent in-page `response.body.tee()` receives EOF — the TCP/HTTP response stays open for at least 189s though the upstream process is dead.
4. Repeat with the request issued DIRECT to `:8000`, bypassing the proxy (P7-S1d, `curl` client).
5. Observe on the DIRECT path: the client's stream terminates promptly on kill rather than hanging.

## Expected
When the upstream process dies, the downstream client's response is terminated so the client can observe EOF and run its terminal path.

## Actual
On the proxied path the downstream response appears to remain open indefinitely after upstream death (≥189s observed, no EOF on two independent readers). On the direct path the same backend death terminates the client stream promptly. The two observations are consistent with the proxy holding the downstream response open after the upstream socket dies — but this has NOT been isolated by a controlled experiment.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S1-frontend-timeline.md (gitignored) — proxied observation, incl. the independent tee; traces/P7-S1d-mid-generation-kill.md — direct-to-:8000 observation

## Root-cause hypothesis

**ISOLATED 2026-08-05.** A controlled re-run — same client, same reader, same query, same turn
state, killed after exactly 3 `chunk` frames, each path killed twice — reproduced the split 2/2:

| Path | `eof_reason` | kill → EOF |
|---|---|---|
| proxied `:3000` | `still_open` | never (>120s) |
| direct `:8000` | `peer_closed` | **0.3s** |

The only remaining difference between a 0.3-second EOF and no EOF at all is whether the request
traversed the proxy. The direct arm doubles as the control that exonerates the reader. Full
method, the fork-rule reading, and the honest 120s bound: [`../BUG-123-PROBE-VERDICT.md`](../BUG-123-PROBE-VERDICT.md).
Evidence: [`../public-evidence/BUG-123-isolation-probe.log`](../public-evidence/BUG-123-isolation-probe.log).

**Still open**: *why* — whether Next's `rewrites()` fails to propagate upstream socket death, or
holds the downstream response open by design pending `proxyTimeout`. Task 2.4's client-side
watchdog is robust to either, so the fix does not wait on that answer.

### Original hypothesis, as filed (retained for the record)
UNCONFIRMED — hypothesis only, deliberately not asserted. Candidate mechanism: the Next.js `rewrites()` proxy does not propagate upstream socket termination to the downstream client for a streaming response, so the client observes an open-but-silent connection instead of EOF. Evidence FOR: two independent readers saw no EOF for 189s on the proxied path (frontend-inspector), while a direct-to-`:8000` client terminated promptly under the same backend kill (team-lead, P7-S1d). Evidence AGAINST / limits: this is ONE observation on each path, gathered for other purposes; neither run was designed to isolate the proxy variable, no re-kill was performed to confirm reproducibility, and other differences existed between the runs (browser fetch reader vs `curl`, different turn states). Cross-ref BUG-054, which independently locates a separate defect in the same proxy layer (~30s idle timeout), making a shared proxy-configuration root cause plausible but unproven.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: **v1.0-fix** (re-triaged 2026-08-05; was `v1.1-defer`)
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/172
- **Rationale**: The isolation probe the original deferral asked for has now been run and the
  mechanism is established, so the sole ground for deferring — "a mechanism not yet
  established" — no longer holds. Fix lands as spec-31 task 2.4 (D3 Branch T).
- **Superseded rationale (2026-05-28)**: Registered UNCONFIRMED on two single observations that were not controlled for the proxy variable; it warrants a dedicated isolation probe in spec-31 rather than a v1.0 fix to a mechanism not yet established.

## Notes
Reporters: frontend-inspector (proxied observation, flagged by its author as a hypothesis needing corroboration and explicitly not re-killed to isolate) + team-lead (direct-to-`:8000` counter-observation at P7-S1d).

**Registered deliberately as UNCONFIRMED, per team-lead ruling.** The title carries the UNCONFIRMED marker so the qualification cannot be lost if the title is read in isolation — e.g. in an issue list or a summary table. This phase's binding standard is that a clean result counts only if the engineering behind it can be cited; the same discipline is applied in reverse here, and a defect is not asserted on evidence that has not isolated its variable.

**Why it is registered at all rather than dropped**: if confirmed it is a SECOND, INDEPENDENT defect from BUG-074. BUG-074 is that `api.ts:158-160` wedges when EOF arrives; this is that EOF may never arrive in the first place. Both were observed in the same 189s window. Fixing BUG-074 alone would therefore not resolve the observed hang, which is exactly the kind of conclusion that would be lost if this evidence were discarded.

**Recommended next step (spec-31)**: a dedicated probe — identical query and turn state, killed twice, once proxied and once direct, with EOF timing recorded on both — to isolate the proxy variable and either confirm or retract this record.

**DONE — 2026-08-05, spec-31 task 1.6.** The probe was run exactly as recommended and returned
`still_open` on the proxied path both times against `peer_closed` in 0.3s on the direct path
both times. The record is **confirmed**, not retracted.

The decision to keep this record separate from BUG-074 is now vindicated by measurement rather
than by argument: BUG-074's Branch E adds a `sawTerminal` check *after* the read loop, and on
the proxied path that loop never exits, so the check never runs. Fixing BUG-074 alone would
indeed not have resolved the observed hang — which is what this record predicted, and what
would have been lost had the evidence been discarded.

## Resolution

**FIXED** — spec-31 Batch 2, task 2.4 (unit 1). Commit `8b7d640`, 9 files, +529/−29, shared with
BUG-054, BUG-040 and BUG-074's Branch T. Closed on the Batch 2 exit-gate re-probe of 2026-09-09,
run on the images carrying the branch's final bytes.

**What is fixed, and what is not.** The proxy still holds the downstream response open after the
upstream socket dies. Nothing in this batch touched `rewrites()`, and a client that waits for EOF
would still wait forever. What changed is that **the client no longer depends on EOF**: the idle
watchdog shipped in `8b7d640` (`STREAM_IDLE_TIMEOUT_MS = 120_000` in
`frontend/hooks/useStreamChat.ts`) aborts the request 120 s after the last received frame and marks
the assistant bubble terminal — `isError`, `errorCode: "STREAM_STALLED"`, `isStreaming: false`,
destructive styling and a `Retry` control. This record is closed on its user-visible consequence,
not on its transport mechanism, and the distinction is recorded here so a future reader is not
misled into thinking the proxy was repaired.

That is also why the record was kept separate from BUG-074, and the separation is now vindicated
twice over. BUG-074's Branch E adds a `sawTerminal` check *after* the read loop; on the proxied
path that loop never exits, so the check never runs. Branch T is the only thing that ends a stream
the transport will not end.

**The gate.** LAUNCH-BATCH-2 §7, verbatim: "BUG-123 re-probed against the **live Docker stack**
(never `tests/e2e_real`'s proxy fixtures — documented host-loopback artifact): proxied `:3000` must
reach a terminal event well inside the 120 s budget instead of `still_open`."

**How that wording is read here, and why the reading is stated rather than assumed.** "Well inside"
was written loosely: the 120 s budget *is* the client watchdog, so by construction the terminal
event lands **at** the budget measured from the last received frame, never before it. The operative
condition the gate rules out is `still_open` — a stream with no terminal event at all past the
budget, which is what the 2026-08-05 probe measured. This run met that condition: the terminal
state arrived exactly at the budget, and the runbook's operational FAIL bound of 150 s (an internal
working file; stated here so the record is self-contained) was never approached.

**Result, 2026-09-09 — PASS.** Chat submitted at `:3000/chat` on collection `arcas-new` with model
`qwen2.5:7b` (the same collection and model as the 2026-09-02 run), `docker kill
embedinator-backend` mid-stream after 337 characters had streamed, a 200 s outage, then
`docker start`:

| Measurement | Delta |
|---|---|
| `docker kill` → terminal bubble | **+119.8 s** (13:32:13.110 → 13:34:12.866) |
| last received frame → terminal bubble | **+120.000 s** (13:32:12.866 → 13:34:12.866) |
| first reachable `/api/health` → banner `Backend connected` and composer enabled | **+2.5 s** (13:35:38.644 → 13:35:41.166) |
| container `healthy` → banner recovered | **−2.4 s** — the page saw the backend before Docker's own healthcheck did |
| stalled bubble + `Retry` persist across recovery | **117.5 s**, until the retried stream started (114.8 s to the `Retry` click) |
| retried turn | `done` in **17.4 s**, 4 sources |

Read the two stream numbers precisely: the terminal event landed **exactly at** the configured
120 s budget measured from the last received frame — which is what that budget means — and 119.8 s
after the kill, the difference being the 244 ms between the last frame and the kill. The 2026-08-05
isolation probe had measured `still_open` past 120 s on this same path against `peer_closed` in
0.3 s direct.

The run also re-confirms two neighbours on the final images: BUG-124's fix (the page followed the
backend back within one 5 s poll interval, ahead of Docker's healthcheck) and BUG-119's (the dead
turn stayed visibly dead and retryable while the chrome reported healthy).

*Why nothing could be deleted or relaxed instead:* no new mechanism was added for this record. The
watchdog already existed for BUG-074's Branch T, and BUG-123 is the reason a client-side timer is
the only workable layer at all — the proxy cannot be disabled, only given a longer window, and no
backend heartbeat can report a backend that is dead.

**Evidence.**

- Exit-gate re-probe, 2026-09-09, on the images carrying the branch's final production bytes:
  [`../public-evidence/spec-31-b2-123/probe-2026-09-09.md`](../public-evidence/spec-31-b2-123/probe-2026-09-09.md),
  with the raw docker, host-curl and 100 ms page-poller stamps beside it. The provenance is a
  chain, not a diff, and its strongest link is what the running images demonstrably contain.
  **Checked inside the containers**: the frontend bundle carries all three frontend units'
  markers — `"The response stalled"` in 2 files under `/app/.next`, `"Stream ended without
  completion"` in 10, `onErrorRetry` in 4 — and the backend carries `route_after_clarification`
  in `edges.py` and `invoke_with_deadline` in `llm_deadline.py`. **Corroborated by build timing**:
  each image predates the squashed commit it is equated with, so the link runs through the
  pre-squash tree it was built from. Frontend `117b66e9…` (built 09:32:12) from the unit-3 GREEN
  tree `830f0de` (09:29:44), with `git diff 830f0de e148b07 -- frontend/ ':!frontend/tests'` empty
  — the squash added only test files — and `git diff e148b07 dbc0d0e -- frontend/` empty; backend
  `a105ac7e…` (12:14:55) from `93df7c9` (12:12:57), with `git diff 93df7c9 9d42210 -- backend/` and
  `git diff 9d42210 dbc0d0e -- backend/` both empty. That second half is an **inference** from
  build timing plus the 2026-09-04 build records, not a cryptographic link: `docker image inspect`
  shows both images carry only `com.docker.compose.{project,service,version}` labels and no
  `org.opencontainers.image.revision`.
- Prior run on the unit-1 image, 2026-09-02: terminal state at **≤ +129 s** after the kill (coarse
  poll, between +85 s and +129 s) —
  [`../public-evidence/spec-31-b2-gc2/browser-probe-2026-09-02.md`](../public-evidence/spec-31-b2-gc2/browser-probe-2026-09-02.md).
- Isolation probe, 2026-08-05: [`../BUG-123-PROBE-VERDICT.md`](../BUG-123-PROBE-VERDICT.md) and
  [`../public-evidence/BUG-123-isolation-probe.log`](../public-evidence/BUG-123-isolation-probe.log).

**Still open / follow-ups.**

- **The proxy is unchanged.** Whether Next's `rewrites()` fails to propagate upstream socket death
  or holds the downstream response open by design pending `proxyTimeout` is still unanswered. It is
  a proxy-layer question, not a blocker: the client watchdog is robust to either answer, which is
  why the fix never waited on it.
- **The stall sentence is hidden when partial content exists.** `"The response stalled: no data for
  120s."` did not render on this run, because 337 characters had already streamed and
  `useStreamChat.ts:59` writes `content: msg.content || message`, keeping the partial text. The
  terminal state is still unambiguous — error styling, `Retry`, and `errorCode: "STREAM_STALLED"`
  on the message — but the user is not told *why* the answer stopped mid-sentence. A UX follow-up,
  not a regression; the 2026-09-02 run saw the sentence only because nothing had streamed yet.
- **Neither image records the commit it was built from.** Both carry only Compose's own labels, so
  "built from `830f0de`/`93df7c9`" rests on build timing and the 2026-09-04 build records. Stamp
  `org.opencontainers.image.revision` in both Dockerfiles so a future gate can prove provenance
  instead of arguing it (Phase 8).
- GitHub issue [#172](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/172) is to be closed
  when the Batch 2 PR merges.
