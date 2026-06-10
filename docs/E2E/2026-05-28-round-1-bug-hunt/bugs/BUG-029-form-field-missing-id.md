# BUG-029: Form field element missing id and name attributes — a11y violation

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T21:43:55Z in Phase 1 (P1-S2)
- **Phase scenario**: P1-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open `http://localhost:3000`
2. Open DevTools → Issues panel
3. Observe: one form field element reported as missing id or name attribute

## Expected
All form field elements have id and/or name attributes to support accessibility tooling, label association, and form data submission.

## Actual
DevTools Issues panel reports one form field element on the dashboard without an id or name attribute.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
A form input or textarea in the dashboard component was rendered without an id prop, preventing label association and screen reader identification.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: frontend-inspector. Count: 1 element. WCAG 2.1 SC 1.3.1 advisory; workaround exists via direct keyboard navigation.
