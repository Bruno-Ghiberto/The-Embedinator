# BUG-039: Orphaned Qdrant vector collections — app-created namespaces with zero SQLite metadata and no cleanup mechanism

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-06-10T22:49:00Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Interrupt the backend (SIGKILL) between Qdrant collection creation and SQLite metadata commit during ingestion, OR delete a collection row from SQLite without performing the corresponding Qdrant collection delete
2. Run `curl localhost:6333/collections` — observe app-namespaced collections (e.g. `emb-<uuid>`) that have no corresponding rows in SQLite `collections` or `documents` tables
3. Run `curl localhost:8000/api/collections` — orphaned namespaces are absent (app is blind to them)
4. Orphan persists indefinitely across restarts with no automatic cleanup

## Expected
SQLite and Qdrant writes are atomic across both stores (or compensating cleanup exists); any Qdrant collection without a corresponding SQLite metadata row is detected and flagged or removed by a reconciliation mechanism.

## Actual
Phase 2 entry baseline reconciliation found 3 orphaned Qdrant collections following the app's `emb-<uuid>` naming convention with zero SQLite metadata: `emb-0bbcfc45` (1 point), `emb-9d465858` (6259 points — likely a full ~18-doc ingestion run whose metadata was lost; this collection also triggered WAL replay during P1 cold start), `emb-0ea45e41` (823 points). Total: 7083 orphaned 768-dim child vectors. No user-facing failure (orphans invisible to app, don't block queries) but storage accumulates per crash cycle.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P2-baseline-collection-reconciliation.log (gitignored)
- Trace: null

## Root-cause hypothesis
SQLite and Qdrant writes are not atomic/transactional across stores — a crash, rollback, or deletion between the Qdrant write and the SQLite commit strands vector data in Qdrant with no corresponding metadata; no garbage-collection or reconciliation job exists to detect or clean orphaned namespaces.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Reporter: log-analyst. Pre-existing state from prior runs, surfaced by Phase 2 entry baseline. Cross-context: playbook P2-S6 (mid-upload backend kill) may reproduce this pattern live during Phase 2. The `emb-9d465858` collection (6259 points) had WAL replay noted at P1 cold start — likely a full ~18-doc ingestion run whose SQLite metadata was lost in a prior session.

P2-S6 live evidence: `storage_qdrant_collection_created` fires at `POST /api/collections` (16:16:09Z — over 2 minutes before the first upload attempt). When the subsequent upload fails via proxy timeout (BUG-054, trace a9128936, 16:23:19Z), the Qdrant collection `hunt-s6-skill` is left with 0 vectors and no SQLite document row — a fresh orphan created live during the hunt. Confirms the orphan-creation path does not require a crash: any failure between collection creation and successful ingest (proxy abort, worker error, network drop) strands an empty or partial collection with no cleanup.
