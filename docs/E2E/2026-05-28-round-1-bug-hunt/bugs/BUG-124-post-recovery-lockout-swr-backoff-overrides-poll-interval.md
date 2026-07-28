# BUG-124: Post-recovery lockout 31-60s — SWR backoff overrides the 5s poll interval

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-07-28T14:12:00Z in Phase 7 (P7-S1)
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

Cross-ref BUG-119 (the inverse-facing defect: global chrome asserting health over a dead conversation — here the chrome asserts unreachability over a healthy backend; both stem from health state being global and loosely coupled to what the user is actually doing) and BUG-034/BUG-038 (the health-banner state-transition family).
