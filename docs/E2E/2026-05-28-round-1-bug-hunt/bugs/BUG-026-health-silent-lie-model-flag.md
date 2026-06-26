# BUG-026: Overall health stays "healthy" and UI shows "Backend connected" while a model flag is false

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T21:46:49Z in Phase 1 (P1-S1)
- **Phase scenario**: P1-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start the stack (`docker compose up -d`)
2. Run `curl localhost:8000/api/health` — observe outer `"status": "healthy"` while `models["nomic-embed-text"]` is `false`
3. Open `http://localhost:3000` — observe dashboard shows "Backend connected" only, with no model warning

## Expected
When any required model flag is false, the aggregate health status reflects degradation and the UI surfaces a warning to the user so they are not silently operating with a missing capability.

## Actual
`/api/health` returns `"status": "healthy"` and the dashboard displays "Backend connected" with no warning, even when `models["nomic-embed-text"]` is `false`; a genuinely missing required model would be entirely invisible to users end-to-end.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: logs/P1-S1-startup-warnings.log (gitignored)
- Trace: null

## Root-cause hypothesis
The health aggregation logic does not incorporate model availability flags into the outer status decision; the frontend status component only checks the outer `status` field and does not render per-model state from the health response payload.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Reporters: frontend-inspector + log-analyst. Related to BUG-025 (false model flag source — tag-suffix mismatch) and BUG-027 (no per-service UI badges). Note: the BUG-025 false flag is a string-match bug; this bug describes the separate architectural issue that any false model flag does not propagate to aggregate health or UI regardless of its cause.
