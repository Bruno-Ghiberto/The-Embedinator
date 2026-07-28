# BUG-037: Degradation banner uses aria-live="polite" — screen readers defer the alert

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T22:16:18Z in Phase 1 (P1-S3)
- **Phase scenario**: P1-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Inspect `frontend/components/StatusBanner.tsx` lines 51-52 — observe `role="status"` + `aria-live="polite"` applied to all banner states
2. Trigger a degradation event (`docker pause embedinator-qdrant`) with a screen reader active
3. Observe: degradation announcement is deferred until the user is idle rather than announced immediately

## Expected
Health-degradation transitions are announced immediately by screen readers; `aria-live="assertive"` or `role="alert"` is the appropriate affordance so visually impaired users are promptly informed of system degradation.

## Actual
`StatusBanner` uses `role="status"` + `aria-live="polite"` for all states including degradation; a visually impaired user is not promptly notified when the system degrades — the announcement waits for user idle. Visual signal is correct (amber + clock icon); the gap is screen-reader announcement timing only.

## Artifacts
- Screenshot: screenshots/P1-S3-during-pause.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
The `aria-live="polite"` attribute was chosen as a blanket default for the status banner without distinguishing between informational state changes (polite is appropriate) and health-degradation alerts (assertive or role="alert" is required); switching the degraded-state render to `role="alert"` would correct the priority.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: frontend-inspector. Source: `frontend/components/StatusBanner.tsx:51-52`. Visual differentiation (amber color + Clock icon) is confirmed correct — this is a screen-reader-only accessibility gap. Related: BUG-029 (separate a11y finding — form field missing id, P1-S2).
