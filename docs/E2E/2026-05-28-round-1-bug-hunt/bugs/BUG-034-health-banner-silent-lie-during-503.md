# BUG-034: Silent health-lie window — banner stays green while /api/health returns 503

- **Severity**: CRITICAL
- **Layer**: Frontend
- **Discovered**: 2026-06-10T22:11:36Z in Phase 1 (P1-S3)
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

## Root-cause hypothesis
The banner component reacts only to the circuit-breaker error string in the health response body, not to raw HTTP 503 status codes or timeout responses; non-CB-tripped degradation states (early 503s) are silently swallowed, leaving the banner green.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/126
- **Rationale**: Banner displays "Backend connected" through 19 consecutive HTTP 503s for 6-9s — the playbook's explicit CRITICAL silent-health-lie criterion.

## Notes
Reporters: frontend-inspector (primary), corroborated by log-analyst. Additional artifacts: screenshots/P1-S3-baseline.png. Cross-references: BUG-026 (aggregate health-lie sibling on cold start), BUG-027 (no per-service badges), BUG-035 (backend hang — upstream cause of the lie window), BUG-036 (misleading degradation message once CB does trip). Root cause source-confirmed by inspector: delay is upstream in BackendStatusProvider polling cadence — banner component reacts immediately to provider state changes; fix belongs in provider polling/error handling, not the banner.
