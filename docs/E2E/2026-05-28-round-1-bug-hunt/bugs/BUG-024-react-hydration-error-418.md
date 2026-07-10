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

P3-S2 recurrence (2026-06-18): hydration error #418 reproduced on navigation to /documents/{uuid} via citation click (did NOT repro in P3-S1 on the chat route — route-specific). Same root-cause class: DocumentsPage breadcrumb `collections?.find(c=>c.id===collectionId)?.name ?? collectionId` — SSR renders raw UUID (SWR not yet fired server-side), client resolves collection name after mount → server/client text mismatch triggers #418. Idiomatic fix: client-only breadcrumb guard (suppressHydrationWarning or useEffect defer on name resolution) or Server-Component prefetch. Recorded as recurrence, not new bug.

[2026-07-10T11:02:37-03:00] P5 pre-phase baseline recurrence (apply-5, before any P5-S1 state mutation). Still live. frontend-inspector reproduced React minified error #418 on a clean Playwright instance, on BOTH (a) fresh nav to http://localhost:3000 which redirects to /chat, and (b) direct nav to http://localhost:3000/chat. Not redirect-dependent — it fires on /chat itself. This matches the ORIGINAL P1-S2 pattern, NOT the P3-S2 breadcrumb variant already recorded in these Notes (that one had a different confirmed cause: UUID-vs-name SSR mismatch on /documents/{uuid}). CANDIDATE CAUSE ELIMINATED: SidebarLayout.tsx is ruled out — its localStorage read is correctly deferred to useEffect. Also ruled out: simple theme-class attribute mismatch, because layout.tsx RootLayout (lines 22-42) already sets suppressHydrationWarning on both <html> and <body>, which would suppress that class of warning. REMAINING UNCONFIRMED CANDIDATES in the same tree: BackendStatusProvider.tsx (SWR fires immediately; first-render state may differ SSR vs client) and CommandPalette.tsx (useTheme() from next-themes plus a Radix CommandDialog portal). Stack is fully minified (prod chunk 0bmpc66o4m-9z.js, no sourcemaps); symbolicating further requires a dev-mode build, not attempted — out of hunt scope. Severity UNCHANGED (MAJOR). Source: frontend-inspector, Playwright fallback instance (chrome-devtools unavailable this phase).
