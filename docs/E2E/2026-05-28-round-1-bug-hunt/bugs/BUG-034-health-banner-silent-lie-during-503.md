# BUG-034: Silent health-lie window — banner stays green while /api/health returns 503

> **FIXED 2026-08-05** by spec-31 Batch 1, task 1.3 — commit `c87812e`.
> **⚠ The filed root-cause hypothesis below is WRONG and is retained only for the record.** The
> banner was not ignoring the 503s; the provider was not asking. See [Resolution](#resolution).

- **Severity**: CRITICAL
- **Layer**: Frontend
- **Discovered**: 2026-06-10T22:11:36Z in Phase 1 (P1-S3)
- **Fixed**: 2026-08-05 (spec-31 task 1.3, commit `c87812e`)
- **Phase scenario**: P1-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ensure stack is healthy and dashboard is open at `http://localhost:3000`
2. Run `docker pause embedinator-qdrant`
3. Watch the banner and the DevTools Network panel simultaneously
4. Observe: `/api/health` returns HTTP 503 (browser network log: 19 consecutive 503s, reqid 166-184) while banner continues to display "Backend connected" for ≥6-9s (2-3 polling cycles)

## Expected
Banner reflects degraded state within one polling cycle (~3s) of the first non-200 `/api/health` response — per playbook P1-S3 explicit criterion: connected/green shown while health endpoint returns non-200 = CRITICAL silent health-lie.

## Actual
Banner displayed "Backend connected" for ~6-9s while `/api/health` returned HTTP 503 with `status: "degraded"` and `qdrant: "Unreachable"`; banner only changed when the circuit-breaker error string appeared at ~t+12s.

## Artifacts
- Screenshot: screenshots/P1-S3-during-pause.png (gitignored)
- Log excerpt: logs/P1-S3-health-poll.log (gitignored)
- Trace: null
- Public evidence: public-evidence/P1-S3-health-poll.log (tracked)

## Root-cause hypothesis

**⚠ REFUTED 2026-08-05 — this hypothesis is wrong.** It is retained verbatim because it was the
filed reasoning, but it must not be used as a starting point if this area is revisited. See
[Resolution](#resolution) for what the code actually did.

The banner component reacts only to the circuit-breaker error string in the health response body, not to raw HTTP 503 status codes or timeout responses; non-CB-tripped degradation states (early 503s) are silently swallowed, leaving the banner green.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/126
- **Rationale**: Banner displays "Backend connected" through 19 consecutive HTTP 503s for 6-9s — the playbook's explicit CRITICAL silent-health-lie criterion.

## Notes
Reporters: frontend-inspector (primary), corroborated by log-analyst. Additional artifacts: screenshots/P1-S3-baseline.png. Cross-references: BUG-026 (aggregate health-lie sibling on cold start), BUG-027 (no per-service badges), BUG-035 (backend hang — upstream cause of the lie window), BUG-036 (misleading degradation message once CB does trip). Root cause source-confirmed by inspector: delay is upstream in BackendStatusProvider polling cadence — banner component reacts immediately to provider state changes; fix belongs in provider polling/error handling, not the banner.

## Resolution

**FIXED** — spec-31 Batch 1, task 1.3. Commit `c87812e`, 2 files, +205/-23.

**The filed hypothesis was wrong.** It blamed the banner for matching only the circuit-breaker
error string and ignoring raw 503s. That is not what the code did: `fetchHealth` already handled
503 explicitly, `StatusBanner` re-renders immediately on any provider state change, and there is
no circuit-breaker string match anywhere in the provider. The reporter's own closing note in
[Notes](#notes) — that the delay is upstream in the provider's polling cadence — was the accurate
reading, and it contradicts the hypothesis recorded above it.

**The real defect was the adaptive polling schedule.** While healthy the provider polled every
**30s**, so a healthy → degraded transition was invisible for up to a full 30 seconds. The banner
was not ignoring the 503s; it was not asking. Detection latency while healthy IS the bug, and
healthy is exactly the state you occupy when degradation begins — so the adaptive schedule
optimised the one interval that could not afford it.

Replaced with a single 5s cadence for every state. The adaptive machinery was removed rather than
retuned: the three intervals existed only to slow down the healthy case, which is the case that
needed to be fast.

**Also bounds the request with a 3s `AbortController` timeout.** BUG-035 (the ~18s `/api/health`
hang) was deferred on the explicit assumption that this fix would "treat any non-200 or timeout as
degraded". Without a timeout an un-aborted hang never settles, SWR retains the last healthy
payload with no error, and the UI shows stale green for the entire hang. The timeout is what keeps
that deferral honest, not an extra.

**Consequence worth recording**: `useBackendStatus` also gates `ChatInput`, so the stale-green
window let users submit into a backend that could not serve them. That is narrowed to one cycle
as well.

**Evidence**: adds `frontend/tests/unit/backend-status-provider.test.tsx`, the first coverage for
this provider — 6 tests, RED before the change for the bug's own reasons (5 failed, 1 control
passed). Frontend suite 59 passed (53 + 6 new), `tsc` clean, 0 new lint warnings, coverage gate
holds at 88.2% branches against an 85% threshold.
