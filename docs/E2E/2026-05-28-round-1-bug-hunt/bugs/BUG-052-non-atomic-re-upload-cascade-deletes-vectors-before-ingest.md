# BUG-052: Non-atomic re-upload deletes old vectors before ingest succeeds

- **Severity**: CRITICAL
- **Layer**: Ingestion
- **Discovered**: 2026-06-11T14:12:30Z in Phase 2 (P2-S5)
- **Phase scenario**: P2-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Have a completed document (filename F, hash H1) in a collection.
2. Upload filename F with different content (hash H2) that will fail ingestion (e.g., corrupt file).
3. check_change (ingest.py:144-155) matches the completed row → cascade DELETES the old document's Qdrant vectors + parent chunks and marks the doc deleted BEFORE the worker runs.
4. Worker fails → new row status=failed, 0 chunks.
5. The collection has permanently lost F's content — no rollback, no user notification.

## Expected
Replace-on-change is atomic — old content stays queryable until the new ingest succeeds (swap-on-success or compensation-on-failure).

## Actual
Deletion runs unconditionally before worker execution (backend/ingestion/pipeline.py ~135-165); no transaction or compensation wraps delete→ingest. Live evidence (twice in sequence): 14:02:45Z trace 23a1149b — cascade deleted bc68288b's 1074 vectors, worker failed "Invalid file header"; 14:04:32Z trace b7ea20cc — cascade deleted a631d3b2's 951 vectors, worker failed. Net: 2,025 vectors permanently destroyed; emb-629d3d8b degraded 1135 → 61 points (only the .md + .txt remain). The reuse path (ingest.py:159-161) reuses the DB row only — it does not protect Qdrant state.

## Artifacts
- Screenshot: screenshots/BUG-052-collection-state.png (gitignored)
- Log excerpt: logs/BUG-052-cascade-data-loss.txt (gitignored)
- Trace: null
- Public evidence: public-evidence/BUG-052-cascade-data-loss.txt (tracked)

## Root-cause hypothesis
Cross-store delete→ingest sequence has no atomicity or compensation; sibling of BUG-039 (inverse failure: BUG-039 = vectors without rows, BUG-052 = rows without vectors — both from missing cross-store transactional discipline; cross-ref).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/136
- **Rationale**: Replace-on-change destroys the old document's vectors before the new ingest runs, with no rollback and no notification — 2,025 vectors permanently lost live; the hunt's most severe data-integrity finding.

## Notes
Most severe data-integrity finding of the hunt. Discovered via Lead-dispatched inspector probing; dismissed hypotheses (documented for the record): "dedup gate bypassable" REFUTED — probe files had different SHA-256 hashes (30a52d1a corrupt, af8dc16a older version) so the gate behaved correctly; "chunk nondeterminism" REFUTED — 951 chunks matches all historical ingests of the older file version, deterministic per version.
