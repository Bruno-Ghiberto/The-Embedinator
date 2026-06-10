# BUG-038: Backend restart invisible to UI — HTTP 5xx with unparseable body produces no banner state change

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T22:20:50Z in Phase 1 (P1-S4)
- **Phase scenario**: P1-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ensure stack is healthy and dashboard is open at `http://localhost:3000`
2. Run `docker compose restart backend`
3. Watch the banner and the DevTools Network panel simultaneously
4. Observe: `/api/health` returns HTTP 500 with null body ×2 polls (~10-12s window); banner remains "Backend connected" with ready-state primary tint throughout — zero visual or textual change (console: 2× "Failed to load resource: 500")

## Expected
Banner reflects backend unavailability within one polling cycle of the first non-200 `/api/health` response; any HTTP error status without a parseable body should transition the banner to a degraded/unreachable state.

## Actual
`BackendStatusProvider` transitions only on fetch throws ("unreachable") or successfully parsed qdrant-error JSON ("degraded"); raw HTTP error codes with a null/unparseable body leave the provider frozen at last known good state; the banner stays "Backend connected" for the entire ~10-12s restart window. Any user action in this window receives unhandled errors with no prior warning.

## Artifacts
- Screenshot: screenshots/P1-S4-baseline.png (gitignored)
- Log excerpt: logs/P1-S4-health-poll.log (gitignored)
- Trace: null

## Root-cause hypothesis
The `BackendStatusProvider` error-handling path checks only for network-level throw (fetch failure) or a specific parsed JSON shape; an HTTP 500 with a null body falls through all conditional branches and leaves the previous `status` state unchanged; the fix is to treat any non-200 response as unreachable/degraded regardless of body parseability.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Reporters: frontend-inspector (primary), corroborated by log-analyst. Additional artifacts: logs/P1-S4-backend-restart.log, screenshots/P1-S4-post-recovery.png. Same root family as BUG-034 (silent health-lie during qdrant 503s) — shared fix: treat any non-200 as unreachable/degraded. Log-analyst note: 15s restart budget passes with ~2.2s headroom (borderline) — cold page cache or slower disk would breach it (log-only observation, no separate bug filed).
