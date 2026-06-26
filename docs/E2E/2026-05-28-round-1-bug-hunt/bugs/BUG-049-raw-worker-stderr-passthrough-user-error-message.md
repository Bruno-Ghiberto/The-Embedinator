# BUG-049: Raw worker stderr + exit code passed unsanitized to user-facing error message

- **Severity**: MINOR
- **Layer**: Ingestion
- **Discovered**: 2026-06-11T13:12:00Z in Phase 2 (P2-S3)
- **Phase scenario**: P2-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. head -c 100 data/Collection-Docs/NAG-200.pdf > /tmp/broken.pdf.
2. Upload /tmp/broken.pdf to a collection via the UI.
3. Observe the failure bubble in the uploader.

## Expected
A human-readable, user-facing error (e.g., "Failed to process PDF: the file may be corrupted or invalid"); raw process detail kept in structured logs only.

## Actual
UI renders verbatim "Worker exited with code 2: [ERROR] Failed to open PDF: PDF error: Invalid cross-reference table (invalid start value)" — leaking the subprocess architecture, process exit codes, and the Rust binary's internal log prefix. No sanitization at any hop: backend/ingestion/pipeline.py:140 assembles f"Worker exited with code {proc.returncode}: {stderr_output}" → stored as error_msg (pipeline.py:155) → exposed via IngestionJobResponse.error_message (backend/api/ingest.py:232) → rendered verbatim by the frontend.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-049-P2-S3.log (gitignored)
- Trace: null

## Root-cause hypothesis
No sanitization/mapping layer exists between worker stderr and the API's error_message field; raw concatenation was the path of least resistance.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
NOT security-relevant in this error class (no paths/credentials leaked; analyst-assessed), but stderr could carry paths in other error conditions — sanitization layer is the fix, keeping raw stderr only in the ingestion_worker_failed structured log event (already captured there with full context). The failure path is otherwise EXEMPLARY: ~4ms POST-to-failure, documents/jobs rows land status=failed with error stored, no stuck rows, no orphan vectors (BUG-039 mechanism not triggered), collection fully usable after. Cross-evidence: the failed job walked pending→started→streaming→failed — further confirmation of BUG-041's real state machine; finished_at=NULL on the failed job extends BUG-044 to failure paths.
