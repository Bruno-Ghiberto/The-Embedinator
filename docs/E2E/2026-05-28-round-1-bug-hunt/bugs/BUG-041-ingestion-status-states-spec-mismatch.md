# BUG-041: Ingestion status state machine — spec states do not exist in implementation

- **Severity**: MAJOR
- **Layer**: Ingestion
- **Discovered**: 2026-06-11T12:31:30Z in Phase 2 (P2-S1)
- **Phase scenario**: P2-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Upload a PDF to a collection.
2. Compare playbook P2-S1 criterion (pending→parsing→chunking→indexing→ready) against the status enum at frontend/lib/types.ts:41-48 and backend structured logs.
3. grep code+logs for parsing|chunking|indexing|ready as status values → zero hits.

## Expected
Implementation status states match the spec's canonical state machine; stage transitions emitted as named structured-log events and renderable in UI.

## Actual
Real enum is pending/started/streaming/embedding/completed/failed/paused (frontend/lib/types.ts:41-48, IngestionProgress.tsx:24-32). Spec state names appear nowhere in the codebase. Backend emits NO named state-transition events — only functional events (ingestion_parent_chunk_created, ingestion_split_into_parents_complete, ingestion_embedding_chunks, ingestion_embedding_complete, ingestion_job_completed; trace_id e6055f6c-e6bc-478f-a858-2a8c58c68b88). Label inconsistency: documents table shows "Completed", progress component shows "Complete!". "paused" state has no resume affordance in UI.

## Artifacts
- Screenshot: screenshots/BUG-042-pilot-view.png (gitignored)
- Log excerpt: logs/BUG-041-P2-S1-backend.log (gitignored)
- Trace: null

## Root-cause hypothesis
spec FR-029 binding table was written against a planned/different backend state machine than implemented; no shared canonical status enum across spec, backend, and frontend.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Renders the playbook's stage-walk criterion untestable as written for P2 and any later phase citing those names. Functional pipeline verified healthy this scenario (14.81s, deltas exact, no functional skips).
