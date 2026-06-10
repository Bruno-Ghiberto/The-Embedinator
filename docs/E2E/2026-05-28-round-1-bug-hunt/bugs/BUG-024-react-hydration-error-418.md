# BUG-024: React hydration error #418 on every cold-start first load

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-10T21:43:55Z in Phase 1 (P1-S2)
- **Phase scenario**: P1-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Run `docker compose up -d` to bring up the stack
2. Open `http://localhost:3000` in a fresh Chromium profile or incognito tab
3. Open DevTools → Console tab
4. Observe: "Uncaught Error: Minified React error #418" (ref https://react.dev/errors/418)

## Expected
Dashboard loads with no console errors and the client-side React tree matches the server-rendered HTML.

## Actual
Minified React error #418 (hydration mismatch) thrown on every cold load; production build confirms real SSR/client divergence, likely from a browser-only state read during SSR.

## Artifacts
- Screenshot: screenshots/P1-S2-dashboard-first-paint.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Browser-only state (e.g., localStorage, window dimensions, or Date.now()) is accessed during SSR render, producing a different value server-side vs. client-side; React detects the mismatch at hydration time and throws #418.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Reporter: frontend-inspector. Observed at P1-S1/S2. No visible crash but masks future render divergences.
