# BUG-124: Post-recovery lockout 31-60s — SWR backoff overrides the 5s poll interval

> **FIXED 2026-09-04** by spec-31 Batch 2, task 2.6 (unit 3) — commit `e148b07`. The filed
> root-cause hypothesis held and was made precise; the measured lockout is **worse** than the
> 31–60 s in the title. See [Resolution](#resolution) below.

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-28T14:12:00Z in Phase 7 (P7-S1)
- **Fixed**: 2026-09-04 (spec-31 task 2.6, commit `e148b07`)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. With the app open, take the backend down so `/api/health` begins failing.
2. Observe the UI enters its unreachable state and the composer is disabled.
3. Bring the backend back up and confirm `/api/health` returns healthy again.
4. Measure the time until the UI leaves the unreachable state and re-enables input: observed **31-60s**, against a configured `refreshInterval` of 5000ms.
5. Repeat on a cold page load (i.e. the page loaded while the backend was already down) — the same 31-60s lockout reproduces.

## Expected
Once `/api/health` is healthy again the UI recovers within roughly one configured poll interval (~5s) and the user can type.

## Actual
Users remain locked out for 31-60s after the backend is demonstrably healthy — 6-12x the configured interval. The `refreshInterval: 5000` setting does not govern recovery at all, so the configuration reads as though recovery is bounded at ~5s when it is not.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S1-frontend-timeline.md (gitignored)

## Root-cause hypothesis
HIGH confidence, code-confirmed (frontend-inspector). `frontend/components/BackendStatusProvider.tsx:52` returns `"unreachable"` whenever SWR's `error` is set. While an error is latched, SWR's polling is governed by its default `onErrorRetry` exponential backoff, NOT by `refreshInterval` — so successive retries are spaced by a growing delay and the healthy response is not observed until the next backoff tick lands. `refreshInterval` only governs the success path. Fix surface: supply an explicit `onErrorRetry` with a bounded (ideally constant, ~5s) interval, or clear the error latch on a successful probe so `refreshInterval` resumes control.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/173
- **Rationale**: The application blocks input for up to a minute after it is fully healthy, and the configured 5s interval gives no indication that recovery is unbounded by it — the user is told to wait by an application that has already recovered.

## Notes
Reporter: frontend-inspector. Reproduced twice, on a live page and on a cold page load.

**The 31-60s bracket is deliberate, not imprecision.** The inspector measured a range rather than inventing a single figure, because the observed delay depends on which backoff tick the recovery lands between. Preserved as a range here for that reason; a precise curve would require instrumenting SWR's retry schedule directly.

**⚠ THE BRACKET IS AN UNDER-ESTIMATE, measured 2026-09-02.** The method above was sound — the
delay does depend on which backoff tick the recovery lands between — but the range is too low. On
a ~190 s outage against the pre-fix image the banner stayed locked for **197 s after the container
reported healthy**, more than three times the top of the filed range. The longer the outage, the
further out the backoff tick, so there is no fixed upper bound at all. Retained as filed; see
[Resolution](#resolution).

Cross-ref BUG-119 (the inverse-facing defect: global chrome asserting health over a dead conversation — here the chrome asserts unreachability over a healthy backend; both stem from health state being global and loosely coupled to what the user is actually doing) and BUG-034/BUG-038 (the health-banner state-transition family).

## Resolution

**FIXED** — spec-31 Batch 2, task 2.6 (unit 3). Commit `e148b07`, 2 files, +173/−6.

**The filed hypothesis held, and reading the installed SWR made it exact.** In SWR 2.4.1 the
refresh loop revalidates only while the cache entry has no error, so a latched `error` **suspends
`refreshInterval` entirely** and hands scheduling to the default `onErrorRetry` — an exponential
backoff with jitter. The record's "`refreshInterval` only governs the success path" is precisely
right. What the record could not state is the consequence: because the backoff keeps growing for
as long as the outage lasts, the lockout is not bounded by 60 s or by any other constant. A backend
down for ~190 s is re-probed roughly 120 s after it is already healthy: with the jitter pinned the
retries land at +10/+30/+70/+150/+310 s, and 310 − 190 = 120.

**What changed.** `frontend/components/BackendStatusProvider.tsx` supplies an explicit
`onErrorRetry` that re-probes at `POLL_INTERVAL_MS` (5 000 ms), so the poller has one cadence in
every state. This is the second of the two fix surfaces the record proposed, and it adds no state,
flag or timer of its own — SWR's retry policy is replaced by the cadence the provider already used
for the success path.

**A note on why the suite was green on the broken behaviour.** The pre-existing "recovery" test
drove a **503**, and `fetchHealth` returns a 503 body as *data*. SWR therefore never entered the
error state on that path, and the test proved one-cycle recovery through a route the bug does not
live on. The RED tests for this fix use a **down** backend — a thrown `HTTP 5xx` or a rejected
fetch — which is the only harness that reaches the latch.

**Evidence.**

- `frontend/tests/unit/backend-status-provider.test.tsx`: three RED→GREEN tests (live-page
  recovery, cold-load recovery on a rejected fetch, and the real `StatusBanner` text), each
  simulating a 190 s outage with SWR's jitter pinned and expecting recovery within one 5 s
  interval; all three failed on the unmodified tree with `expected 'unreachable' to be 'ready'`.
  Two guards were added after review: a hung-probe outage recovers within
  `POLL_INTERVAL_MS + PROBE_TIMEOUT_MS`, and a downed backend is re-probed 11–13 times per 60 s
  window — the cadence guard, which kills 6 s / 8 s / 500 ms mutants that the recovery assertions
  alone let survive. File 11/11; whole vitest suite **110 passed**; `scripts/check-all.sh` 4/4.
- Live stack, 2026-09-04 — frontend image rebuilt from the fix, `docker stop embedinator-backend`
  → 190 s → `docker start`, observed at `:3000/chat` through the proxy with a 100 ms in-page
  poller: banner `Backend connected` and composer enabled **1.5 s after the first reachable
  `/api/health`**, 6.4 s after `docker start`, and **4.0 s before** Docker's own healthcheck said
  `healthy`. The same scenario on the pre-fix image recovered **197 s after** healthy:
  [`../public-evidence/spec-31-b2-124/probe-2026-09-04.md`](../public-evidence/spec-31-b2-124/probe-2026-09-04.md).

**Still open / follow-ups.**

- `HealthDashboard.tsx` mounts a second `useSWR("/api/health", …)` on the same key without the
  retry override. SWR routes retries through the **first** subscriber of a key, so if the dashboard
  subscribed first the default backoff would return (measured 115 s). The shipped mount order is
  provider-first, so this is latent; a distinct key or the same retry policy on both would remove
  it.
- A hidden tab keeps probing every 5 s throughout an outage. Accepted deliberately: with
  `revalidateOnFocus: false`, a tab that stopped retrying would never recover on refocus.
- An `online` event mid-outage starts a second constant-cadence chain (two probes per interval
  until recovery). Self-healing; `revalidateOnReconnect: false` is a follow-up candidate.
- The recovery bound is one interval measured from the **previous probe's completion**, so a probe
  that hangs to its 3 s abort makes the worst case 8 s, not 5 s. A guard test pins this.
- `/api/health` itself hangs while Ollama is paused, which holds the banner on "Connecting to
  backend..." for the duration — the BUG-035 family, a different record.
