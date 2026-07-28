# BUG-043: /api/collections/{id}/stats endpoint does not exist (playbook cites it)

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. curl localhost:8000/api/collections/hunt-pdfs/stats → 404.
2. curl localhost:8000/api/collections/629d3d8b-4790-4e96-ac37-1f211118883f/stats → 404.

## Expected
A per-collection stats endpoint (cited by playbook P2-S1 as the spot-check command).

## Actual
Both forms return 404 {"detail":"Not Found"}; no stats sub-route registered in backend/api/collections.py; collection stats only available via the full GET /api/collections list.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-043-stats-404.txt (gitignored)
- Trace: null

## Root-cause hypothesis
Endpoint never implemented; playbook references a route that was planned but never built.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Playbook erratum — P2-S1 spot-check command is invalid; playbook observation appended to session-log.
