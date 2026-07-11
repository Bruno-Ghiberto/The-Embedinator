# BUG-115: Failed-ingest docs counted in collection & global doc totals (no status filter)

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T20:20:00Z in Phase 6 (P6-S2)
- **Phase scenario**: P6-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Upload a malformed PDF → the ingest job fails; the document row persists (`status=failed`, `chunk_count=0`, `ingested_at=NULL`).
2. Collections view shows `audit-timing-test` as "1 document".
3. The `documents` table totals 78 completed + 1 failed = 79 rows, both counted identically.

## Expected
Document counts reflect successful documents, or distinguish failed ones.

## Actual
Failed/0-chunk documents are counted identically to real documents in both the collection card and the global "Documents" stat (79); there is no status distinction anywhere in the counting path, and no cleanup path, so they persist indefinitely.

## Artifacts
- Screenshot: screenshots/P6-S3-query-analytics-charts.png (gitignored)
- Log excerpt: null
- Trace: traces/P6-S2-ingest-error-jobstatus.json (gitignored)

## Root-cause hypothesis
`SQLiteDB.list_documents` (`backend/storage/sqlite_db.py:275-283`) has no status clause; consumers `backend/api/collections.py:26,34` (`document_count=len(docs)`) and `backend/api/traces.py:161-166` (`total_documents += len(docs)`) inherit the omission. Only a manual `DELETE /api/documents/{id}` (`documents.py:45-62`) removes a failed row; there is no auto-cleanup/quarantine/TTL. `total_chunks` (`traces.py:166`) is NOT inflated (`chunk_count=0`) — only the document count is wrong.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Related: BUG-109 (same P6-S2 ingest-error scenario, same failed document/job), BUG-110 (same failed row, missing `finished_at`/`completed_at`).
