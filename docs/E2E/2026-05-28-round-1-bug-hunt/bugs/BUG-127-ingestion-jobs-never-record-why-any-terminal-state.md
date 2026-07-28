# BUG-127: No ingestion job in any terminal state ever records why it got there

- **Severity**: MINOR
- **Layer**: Ingestion
- **Discovered**: 2026-07-28T14:43:26Z in Phase 7 (P7-S3)
- **Phase scenario**: P7-S3
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Start an ingestion, then `docker stop embedinator-qdrant` mid-run so the job pauses on the Qdrant outage.
2. Query the job's row while it is paused — `error_message` is `null` for the whole pause window, so a job stalled by an infrastructure outage carries no indication of what stalled it.
3. `docker start embedinator-qdrant`, let the job resume and complete.
4. Widen the query to the whole table: `error_msg` is empty on **every** row — including the one genuinely FAILED job.
5. Confirm there is no other persisted diagnostic: the reason exists only in container stdout, which does not survive `docker compose down`.

## Expected
A job that pauses, fails, or otherwise leaves the happy path records why, so an operator can diagnose it from the system of record rather than from ephemeral container logs.

## Actual
No ingestion job, in any terminal or intermediate state, ever records a reason. A paused job shows `error_message: null` throughout its pause; the single genuinely-failed job in the table also carries an empty `error_msg`. The failure reason is never persisted anywhere durable — it exists only in container stdout, which is destroyed by `docker compose down`. Post-hoc diagnosis of any ingestion problem is therefore impossible from the application's own records.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P7-S3-ingestion-recovery-timeline.md (gitignored) — per-document verification and the pause/resume event sequence

## Root-cause hypothesis
MEDIUM-HIGH confidence. The `ingestion_jobs` row is written on the happy path and its diagnostic columns are never populated on any other branch — the same "records written only on the success path" root cause that BUG-110 identifies for `finished_at`. The pause path (`_wait_and_flush()`) and the failure path both emit rich structured log events but neither writes back to the job row, so the durable record and the ephemeral log diverge completely. Fix surface: populate `error_msg` (and a state reason) at every transition out of the running state, not only where a row is first created.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Reporters: frontend-inspector (per-document verification) + log-analyst (whole-table broadening). Registered as a NEW ID rather than a BUG-110 extension, per team-lead's reasoning that BUG-110 concerns a TIMESTAMP while this concerns DIAGNOSTICS — different columns, different fix, and either could be fixed without the other. They do share a root cause, cross-referenced both ways.

**Severity MINOR, and the reasoning is recorded because it is contestable.** Held at MINOR for consistency with BUG-110 — its sibling, same table, same root-cause family, also MINOR — and because the defect is an ABSENCE rather than a false statement: nothing incorrect is asserted, and the user-facing half of ingestion-error diagnosis is already carried at MAJOR by BUG-109 (the UI drops `job_id`/`document_id`/`started_at`/`x-trace-id` and offers no detail navigation). A MAJOR case exists and is not unreasonable — an operator cannot determine why an ingestion failed from the system of record at all — and the Lead should override if that weighs heavier. Flagged rather than decided unilaterally.

Naming note recorded here as well as on BUG-110: the database column is `finished_at` while the API surfaces it as `completed_at`, so a reader correlating the two surfaces is comparing differently-named fields.

**SEVERITY RULING 2026-07-28 (team-lead): HELD AT MINOR — the MAJOR case is NOTED AND DECLINED, recorded so the call is auditable rather than merely absent.** The registrar flagged this severity as contestable at registration rather than deciding it quietly, and team-lead adjudicated in favour of MINOR on three grounds: (a) consistency with BUG-110 — same table, same "written only on the success path" root-cause family — matters more than the marginal severity difference; (b) this defect is an ABSENCE of information rather than a false statement, so nothing incorrect is asserted to anyone; (c) the user-facing half of ingestion-error diagnosis is already carried at MAJOR by BUG-109 (the UI drops job_id/document_id/started_at/x-trace-id and offers no detail navigation), so the harm is not unrepresented in the registry.

The declined MAJOR case, preserved verbatim so a later reader can re-weigh it rather than re-derive it: an operator whose ingestion failed cannot determine why from the system of record at all, because `error_msg` is empty on every row including the single genuinely-failed job, and the reason exists only in container stdout which `docker compose down` destroys.
