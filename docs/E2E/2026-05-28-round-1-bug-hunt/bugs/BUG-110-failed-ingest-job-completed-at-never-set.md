# BUG-110: Ingestion jobs never stamp completed_at — null on every job, success or failure

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T19:40:00Z in Phase 6 (P6-S2)
- **Phase scenario**: P6-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. `sqlite3 data/embedinator.db "SELECT status, COUNT(*), SUM(CASE WHEN finished_at IS NULL THEN 1 ELSE 0 END) FROM ingestion_jobs GROUP BY status"` → completed 78/78 null, failed 1/1 null.

## Expected
A terminal job (completed or failed) records `completed_at`/`finished_at` so its duration/age is computable.

## Actual
`finished_at` (API `completed_at`) is NULL for ALL 79 `ingestion_jobs` rows — 78/78 completed AND 1/1 failed. Not failure-specific; success does not stamp it either. So no ingestion job has a computable duration/age.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P6-S2-ingest-error-jobstatus.json (gitignored)

## Root-cause hypothesis
All 6 `update_ingestion_job()` call sites omit the `finished_at` kwarg: `backend/ingestion/pipeline.py:152-157, 168, 268-274, 292-297, 324-330`; `backend/api/collections.py:132-135`. The param (`backend/storage/sqlite_db.py:342`, writes at `:356-358`), column (`:46`), and API mapping (`backend/api/ingest.py:234` `completed_at=job.get('finished_at')`) are all correct. The sibling `documents` table stamps `ingested_at` correctly (`pipeline.py:167,288`) — the pattern exists, it was just never copied to the job-update call sites.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Correction (2026-07-11)
The original record framed this as failure-path-specific ("failed ingest job never sets completed_at"). log-analyst refuted that framing with a full-table query: the gap is universal — ALL 79 rows (78 completed, 1 failed) have `finished_at=NULL`, not just the failed one. Title, Actual, Steps to Reproduce, and Root-cause hypothesis above have been overwritten to reflect the corrected, broader finding. Severity/layer/scenario unchanged (MINOR/Backend/P6-S2).

## Notes
Related: BUG-109 (same P6-S2 ingest-error scenario, same job record).
