# BUG-121: Graceful-shutdown path unreachable; SIGKILL always wins during a chat

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-28T14:05:18Z in Phase 7 (P7-S1)
- **Phase scenario**: P7-S1
- **BLOCKER-PATCHED**: no

## Steps to Reproduce
1. Read `backend/api/chat.py:110` — the request-path guard that is supposed to short-circuit new work once shutdown has begun.
2. Read `backend/main.py:668` — the shutting-down flag is only flipped AFTER the lifespan `yield`.
3. Observe the ordering consequence under uvicorn 0.49.0: lifespan shutdown runs only after `_wait_tasks_to_complete()`, so by the time the flag is set there are no in-flight requests left to observe it. `chat.py:110`'s guard can therefore never evaluate True in production.
4. Observe no `--timeout-graceful-shutdown` is configured — the drain is unbounded.
5. Observe `stop_grace_period: 15s` in the compose service definition — so a stop during an active chat reaches SIGKILL first.
6. Live confirmation: at 14:05:18.732Z the backend took SIGKILL, `exit=137`, `oom=false`, with ZERO shutdown log lines emitted.

## Expected
FR-050/051/052 are reachable: new work is refused once shutdown begins (FR-050), the SQLite WAL is checkpointed (FR-051), and the LangGraph checkpointer is closed cleanly (FR-052).

## Actual
All three are unreachable on the path that matters. The FR-050 guard can never fire because the flag it reads is set after in-flight requests have already been awaited. FR-051's WAL checkpoint and FR-052's checkpointer close never run on a stop-during-chat, because the unbounded drain (no `--timeout-graceful-shutdown`) is guaranteed to outlast the 15s `stop_grace_period`, so SIGKILL always arrives first. The documented graceful-shutdown behaviour is therefore not merely slow or best-effort — it is structurally unreachable.

## Artifacts
- Screenshot: null
- Log excerpt: logs/P7-S1-backend-killboundary.log (gitignored) — SIGKILL at 14:05:18.732Z, exit=137, oom=false, zero shutdown log lines
- Trace: traces/P7-S1-kill-boundary-forensics.txt (gitignored)

## Root-cause hypothesis
HIGH confidence, code-confirmed. Two independent ordering defects compound. (1) Flag-set ordering: the shutting-down flag is set after the lifespan `yield` (`main.py:668`), but uvicorn runs lifespan shutdown only after `_wait_tasks_to_complete()`, so the flag is always set too late for `chat.py:110` to act on. (2) Timeout ordering: with no `--timeout-graceful-shutdown` the drain is unbounded, while `stop_grace_period: 15s` bounds the container's patience — so for any request longer than 15s the SIGKILL deadline is reached first, deterministically. Fix surface: set the shutdown flag BEFORE awaiting in-flight tasks, and configure `--timeout-graceful-shutdown` to a value strictly below `stop_grace_period` so the drain can actually complete.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/171
- **Rationale**: Three documented requirements (FR-050/051/052) are structurally unreachable rather than merely unreliable, so every stop during an active chat skips the WAL checkpoint and checkpointer close that the spec requires.

## Notes
Reporter: log-analyst. Dedup-checked before minting against all 94 prior records; grep for graceful-shutdown, FR-050/051/052, `stop_grace_period` and `timeout-graceful` returned zero hits.

**Explicitly NOT filed as "the backend logged nothing on the way down"** — SIGKILL is uncatchable and emitting nothing under it is correct behaviour, not a defect. The finding is the ordering that makes SIGKILL the guaranteed outcome in the first place, and the unreachability of the FR-050 guard independent of any signal.

Scope note: the P7-S1 SIGKILL was operator-induced (`docker kill`) and so is not itself evidence of user-facing harm. The defect is that a NORMAL `docker compose down`/`stop` during an active chat reaches the same terminal state by the same deterministic route.

**UPGRADED FROM INFERENCE TO DEMONSTRATED BEHAVIOUR, 2026-07-28 (P7-S4).** This record originally established the defect by reading the code path; it has now been observed end-to-end. Captured sequence:

```
14:49:37.116Z  POST /api/chat 200 OK
14:49:37.396Z  INFO: Shutting down                       <- SIGTERM, +280ms after the request
14:49:37.496Z  INFO: Waiting for connections to close.
               <- the last line the process ever emitted
```

`grep -c storage_shutdown_complete` = **0** — the shutdown completion event never fires. Timing corroborates the drain/grace-period collision this record predicts: `docker compose down` took **16.0s with a request in flight** versus **1.5s idle**, i.e. the 15s `stop_grace_period` expiring rather than a drain completing. The client received only the `session` event, 74 bytes — no `SHUTTING_DOWN`, no error, no `done`.

**A 280ms-old connection was sufficient.** No long-running query is required to reach this state, which removes the last argument that it is an edge case.

**Framing, deliberately precise and NOT overclaimed (log-analyst's wording, adopted verbatim in substance)**: the risk here is NOT "data is lost". It is that **the application's own durability guarantees are never exercised, and the system is relying on SQLite's crash-safety instead of the shutdown path that was written for the purpose.** P7-S4 independently confirms nothing was in fact lost across a full teardown — documents 81->81, ingestion_jobs 81->81, query_traces 1014->1014, Qdrant collections 26->26, provider ciphertext intact at 140 bytes and still encrypted, all 7 settings preserved, with `storage_checkpoint_integrity_ok` logged at 14:48:25.200Z. The defect is that this outcome is owed to the storage engine, not to FR-051/FR-052, which never ran.

**WAL-ordering sub-claim NOT recorded — withdrawn as unproven.** log-analyst retracted it: run #2 skipped the relevant block entirely so it could not test the claim, and run #1's measurement was taken on the wrong side of the restart boundary. Left as an OPEN QUESTION for spec-31, alongside the BUG-123 proxy-EOF probe and the BUG-069 turn-depth series. Recorded explicitly so a later reader does not mistake its absence for an untested gap.

Artifact: logs/P7-S4-shutdown-sequence.log (gitignored).
