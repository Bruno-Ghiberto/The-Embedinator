# BUG-027: No per-service health badges on dashboard — single coarse "Backend connected" banner only

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T21:43:55Z in Phase 1 (P1-S2)
- **Phase scenario**: P1-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Start the stack and open `http://localhost:3000`
2. Inspect the accessibility tree (DevTools → Accessibility panel) or the DOM
3. Observe: exactly one status element with role=status displaying "Backend connected" + dismiss button; no badges for qdrant, sqlite, ollama, or individual models

## Expected
Dashboard displays per-service health indicators (badges or icons) for each backend service (qdrant, sqlite, ollama, embedding model) so individual service degradation is visible to the user.

## Actual
A single coarse banner "Backend connected" is the only health surface on the dashboard; per-service state is not exposed; playbook scenario P1-S3 (badge transition on degraded service) is untestable as written.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
The frontend status component was implemented using only the outer `status` boolean from `/api/health` and was never extended to render per-service or per-model detail from the full health response payload.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Reporter: frontend-inspector. Renders playbook P1-S3 (degraded badge transitions) untestable until fixed. Related to BUG-026 (aggregate health silent lie).
