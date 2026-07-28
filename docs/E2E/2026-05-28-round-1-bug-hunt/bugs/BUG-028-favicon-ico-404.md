# BUG-028: favicon.ico returns 404 — console/network error on every page load

- **Severity**: COSMETIC
- **Layer**: Frontend
- **Discovered**: 2026-06-10T21:43:55Z in Phase 1 (P1-S2)
- **Phase scenario**: P1-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open `http://localhost:3000` in Chromium
2. Open DevTools → Network panel
3. Observe: `GET /favicon.ico` → 404 (network request id 30)

## Expected
`/favicon.ico` returns a valid icon file with 200 status; no console or network errors generated on page load.

## Actual
`GET /favicon.ico` returns 404 on every page load, producing a network error in DevTools; no functional impact on app behavior.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
The favicon.ico file is absent from the Next.js `public/` directory or app root, so the browser's automatic favicon request hits a 404.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: frontend-inspector. No functional impact; cosmetic polish issue for v1.1 backlog.
