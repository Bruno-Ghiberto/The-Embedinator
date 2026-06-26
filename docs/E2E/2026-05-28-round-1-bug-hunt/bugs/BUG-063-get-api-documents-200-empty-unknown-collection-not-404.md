# BUG-063: GET /api/documents returns 200 empty for unknown collection_id, not 404

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-18T18:45:00Z in Phase 3 (P3-S2)
- **Phase scenario**: P3-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Send GET /api/documents?collection_id=<any-nonexistent-uuid> (e.g. a parent-chunk UUID such as 9a674844…).
2. Observe HTTP response: 200 {"documents": []}.

## Expected
404 response when the specified collection_id does not exist, distinguishing "valid empty collection" from "invalid collection".

## Actual
200 {"documents": []} returned for any UUID — the endpoint never validates collection existence. Confirmed with 4 chunk UUIDs during P3-S2 citation-click flow (all returned 200 []).

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-063-api-response.log (gitignored)
- Trace: null

## Root-cause hypothesis
GET /api/documents endpoint queries documents filtered by collection_id without first checking the collection exists; an empty result set is indistinguishable from a nonexistent collection. Fix: validate collection exists before querying documents; return 404 for unknown collection_id.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Cross-ref BUG-061: this behavior MASKS BUG-061 — when citation click routes /documents/{chunk-uuid}, the SWR fetch returns 200 [] instead of 404, so the FE error branch never fires and the user sees the misleading "No documents yet" page rather than an error. Confirmed via /tmp/spec30-captures/P3-S2-citation-payload-score.log (4× 200 [] for chunk UUIDs 9a674844, 907ed763, a49b801e, 2c04624d).
