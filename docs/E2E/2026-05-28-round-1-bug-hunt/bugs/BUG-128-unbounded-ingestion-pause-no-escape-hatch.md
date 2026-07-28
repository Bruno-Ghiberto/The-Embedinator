# BUG-128: Ingestion pause is unbounded with no escape hatch and no operator recourse

- **Severity**: MAJOR
- **Layer**: Ingestion
- **Discovered**: 2026-07-28T14:43:26Z in Phase 7 (P7-S3)
- **Phase scenario**: P7-S3
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Read `_wait_and_flush()` in `backend/ingestion/pipeline.py` — the retry loop is `while True:` with backoff capped at 60s. There is no maximum attempt count, no wall-clock deadline, and no `break` condition other than Qdrant returning.
2. Start an ingestion and `docker stop embedinator-qdrant` mid-run; the job pauses correctly (`ingestion_job_paused_qdrant_outage`).
3. Leave Qdrant down. The job waits indefinitely, holding its buffered points in memory.
4. Search `openapi.json` for any operator control over that job — verified programmatically: there is **no** resume, cancel, retry or abort endpoint anywhere in the API surface.
5. Conclude there is no supported way to end the pause other than restoring Qdrant or restarting the backend and losing the buffer.

## Expected
A paused ingestion is bounded — by attempts, by a deadline, or by an operator-invokable cancel/abort — so a permanently unavailable dependency cannot strand a job forever.

## Actual
The pause is unbounded in both directions: the code will retry forever, and the API offers the operator no way to intervene. A permanently-down Qdrant therefore means a permanently-paused job, holding buffered points in memory, with no recourse short of a backend restart that discards the buffer. The P7-S3 scenario passed **only because Qdrant came back** — the recovery path that was validated is the one where the dependency returns, and the one where it does not was never exercised because it has no terminal state.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S3-ingestion-recovery-timeline.md (gitignored) — pause/resume sequence, breaker open at failure_count=5 and half-open 60.065s later

## Root-cause hypothesis
HIGH confidence, code-confirmed. `_wait_and_flush()` implements the pause as an unbounded retry loop: correct for a transient outage, unbounded for a permanent one, with no distinction drawn between the two. The absence of any job-control endpoint compounds it — the design assumes the dependency always returns, so no terminal state or operator action was ever specified for the case where it does not. Fix surface: bound the loop (max attempts or a wall-clock deadline) and give the stalled job an observable terminal state; and/or expose a cancel/abort endpoint so an operator can reclaim the buffer.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/176
- **Rationale**: A permanently unavailable Qdrant strands an ingestion job forever with buffered points held in memory and no operator recourse of any kind, so the ingestion flow has a reachable state from which the product cannot recover.

## Notes
Reporter: frontend-inspector (code trace + programmatic `openapi.json` verification).

**This is the load-bearing caveat on the P7-S3 PASS and should travel with it.** P7-S3 is registered as a genuine engineered PASS — `_upsert_with_buffer()` / `_wait_and_flush()` traced to FR-012, with dedicated `ingestion_job_paused_qdrant_outage` → `ingestion_job_resumed_qdrant_recovered` events and per-document `exact:true` Qdrant verification showing every claimed vector landed. That PASS is real and is not weakened by this record. What this record establishes is its BOUNDARY: the engineered recovery covers "the dependency comes back", and there is no engineered behaviour at all for "it does not".

Cross-ref BUG-127 (a paused job also records no reason, so a stranded job is both unbounded and undiagnosable) and BUG-099 (the shared circuit breaker whose 60s cooldown governs the retry cadence here).
