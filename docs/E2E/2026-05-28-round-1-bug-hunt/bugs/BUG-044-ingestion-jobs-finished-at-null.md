# BUG-044: ingestion_jobs.finished_at never written — NULL on all completed jobs

- **Severity**: MINOR
- **Layer**: Ingestion
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. sqlite3 data/embedinator.db "SELECT COUNT(*) FROM ingestion_jobs WHERE status='completed' AND finished_at IS NULL;" → returns 74 (of 74 completed).

## Expected
Completed jobs carry finished_at so job duration is queryable from the DB.

## Actual
74/74 completed jobs have finished_at=NULL; the ingestion pipeline never writes the column. documents.ingested_at IS written (incidental workaround).

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-044-finished-at-null.txt (gitignored)
- Trace: null

## Root-cause hypothesis
Job-completion path in the ingestion pipeline updates status and documents.ingested_at but omits ingestion_jobs.finished_at.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Limits operational visibility (no DB-queryable job durations); non-blocking for v1.0.
