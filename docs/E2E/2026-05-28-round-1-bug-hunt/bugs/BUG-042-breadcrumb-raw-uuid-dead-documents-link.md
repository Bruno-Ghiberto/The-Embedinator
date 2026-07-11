# BUG-042: Header breadcrumb renders raw UUID + dead /documents link

- **Severity**: MINOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Navigate to Collections → hunt-pdfs (route /documents/{uuid}).
2. Observe TOP header breadcrumb.
3. Click "Documents" in the header breadcrumb.

## Expected
Header breadcrumb shows the collection display name; all breadcrumb links resolve.

## Actual
Header renders raw UUID "629d3d8b-4790-4e96-ac37-1f211118883f"; its "Documents" link targets /documents which has no index route (404). The in-page breadcrumb is correct (fetches collection.name via API).

## Artifacts
- Screenshot: screenshots/BUG-042-breadcrumb-uuid.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
PageBreadcrumb.tsx:61-81 deriveCrumbs() maps URL segments via static ROUTE_LABELS with `?? seg` raw fallback (line 71); no dynamic segment resolution and no route-existence check.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Two defects, one root component — bundled per inspector recommendation. Also references screenshots/BUG-042-pilot-view.png (shared with BUG-041, gitignored).

P3-S2 additional repro path (2026-06-18): citation click from chat routes to /documents/{chunk-uuid}, triggering BOTH halves: (1) breadcrumb renders raw UUID (e.g. a49b801e / 2c04624d — parent-chunk UUIDs, not collection UUIDs; same root — deriveCrumbs() fallback with no dynamic resolution); (2) RSC 404 on /documents?_rsc base-route prefetch (dead /documents-link half). BUG-061 shares the /documents/[id]-page-treats-id-as-collection route substrate but has a distinct trigger (citation click) and root cause (wrong ID type in Citation schema, no collection_id field) — registered as a separate bug with cross-ref.

**UPDATE 2026-07-11 (P6-S2/S3)**: Root-caused + recurrence confirmed. Global auto-derived breadcrumb: `PageBreadcrumb.tsx` `deriveCrumbs()` (lines 61-81), rendered site-wide via `SidebarLayout.tsx:34`, emits a real `<Link href='/documents'>` for the "documents" segment — but no `/documents` index route exists (only `frontend/app/documents/[id]/page.tsx`) → 404 (confirmed live in network). The `[id]` segment has no `ROUTE_LABELS` entry (`PageBreadcrumb.tsx:14-20`) → rendered as the raw UUID. A second inline breadcrumb in `documents/[id]/page.tsx:88-104` is correct (resolves the collection name); the two stack visually. Same `deriveCrumbs` mechanism will break any other dynamic `[id]` route not in `ROUTE_LABELS`. Severity UNCHANGED (MINOR).
