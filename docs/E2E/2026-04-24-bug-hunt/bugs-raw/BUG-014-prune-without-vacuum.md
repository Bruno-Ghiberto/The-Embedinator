# BUG-014: checkpoints.db prune-without-vacuum risks corruption + backend image not auto-rebuilt on source change

- **Severity**: Major
- **Layer**: Infrastructure
- **Discovered**: 2026-04-29 12:30 via Exploratory (Session 5 root-cause investigation of BUG-013)
- **F/D/P decision**: D (defer to v1.1; underlying risk identified post-BUG-013 recovery; needs methodical fix design — `auto_vacuum` mode change is one-shot but irreversible without rebuild, so wants a small spec)

## Steps to Reproduce

This is a latent risk record, not a single-shot reproducer. The conditions that produce corruption are:

1. Run `docker compose up -d` and let backend serve `/api/chat` traffic for some hours/days. The LangGraph SQLite checkpointer writes to `data/checkpoints.db` per node per request. Many threads accumulate.
2. spec-26 `_prune_old_checkpoint_threads` (`backend/main.py:119-137`) periodically DELETEs old threads. Pages move to the freelist. **No VACUUM happens** — the file does not shrink and freelist pages are reused for new writes.
3. Over time the freelist becomes a large fraction of the file (in the BUG-013 incident: **81,079 of 89,257 pages = 91%**).
4. An ungraceful shutdown happens during a write that reuses a freelist page (Docker SIGKILL after compose `down -t` timeout, OOM kill, hard host reboot, etc.).
5. Restart. `PRAGMA integrity_check` shows multiple "Freelist: 2nd reference to page X" entries — the B-tree is corrupt.
6. The first `/api/chat` request that triggers a checkpoint write on a corrupt page raises `DatabaseError: database disk image is malformed`. Result: every request ends in `SERVICE_UNAVAILABLE`. This is BUG-013.

## Expected

- Either: `data/checkpoints.db` does not accumulate a 91% freelist (e.g., `auto_vacuum=incremental` reclaims pages periodically), OR
- The prune routine VACUUMs after every N prunes / on a schedule, OR
- Backend startup detects integrity-check failure and either auto-recovers (VACUUM INTO + REINDEX) or fails-fast with a clear operator message and a one-command recovery hint.

## Actual

- `_prune_old_checkpoint_threads` calls `await checkpointer.adelete_thread(tid)` only. No VACUUM. No `auto_vacuum` PRAGMA set at checkpointer init (LangGraph's `AsyncSqliteSaver` defaults to `auto_vacuum=NONE`).
- Backend startup does not run integrity_check; first failure surfaces only when a request triggers a checkpoint write on a corrupt page.
- BUG-013 (Blocker, every request → SERVICE_UNAVAILABLE) was the user-visible consequence in our case.

## Artifacts

- BUG-013 record (full incident write-up): `bugs-raw/BUG-013-chat-service-unavailable.md`
- Forensic copies of the corrupt DB:
  - `data/checkpoints.db.corrupt-2026-04-29` (renamed primary, 366 MB)
  - `data/checkpoints.db.corrupt-2026-04-29.bak` (separate forensic copy)
- File refs:
  - `backend/main.py:119-137` — `_prune_old_checkpoint_threads` (DELETE without VACUUM)
  - `backend/main.py` `lifespan()` startup — could host an integrity check / auto-recovery hook
  - `Dockerfile.backend` — no source mount; image must be rebuilt on `backend/` changes
  - `docker-compose.yml` — backend service has bind mount only for `data/`, not for `backend/`

## Root-cause hypothesis

Two distinct underlying risks share a common operational footgun (invisible state drift between intent and runtime):

**Risk A — prune-without-vacuum corruption**: SQLite without `auto_vacuum` keeps deleted pages in the freelist forever. Workloads that delete heavily (like spec-26's prune routine) accumulate huge freelists. Freelist B-tree corruption during ungraceful shutdown is a documented SQLite failure mode (see <https://www.sqlite.org/howtocorrupt.html> §3.6). The fix space:

1. Set `PRAGMA auto_vacuum=incremental` at checkpointer DB initialization (must be set BEFORE the schema is created — irreversible without rebuild). Then `PRAGMA incremental_vacuum(N)` reclaims N pages on demand.
2. Run a `VACUUM` after every N prunes inside `_prune_old_checkpoint_threads`. VACUUM is cheap when the freelist is small and expensive when large; sizing N right matters.
3. Add a startup-time `PRAGMA integrity_check` with auto-recovery (VACUUM INTO + REINDEX into a salvage file) if it fails. Fall back to fresh DB if VACUUM INTO fails.
4. Combination: option 1 (prevention) + option 3 (recovery).

**Risk B — backend image not auto-rebuilt on source change** (the orthogonal DX gap that masked spec-28 verification during the Live Block):
- `Dockerfile.backend` produces an image with `backend/` baked in.
- `docker-compose.yml` bind-mounts `data/` only; `backend/` lives inside the image.
- `docker compose restart backend` recreates the container from the existing image — does NOT rebuild.
- Net effect: a developer who edits Python source, runs `restart`, and tests `/api/chat` is hitting STALE BINARIES with no warning.
- Concrete spec-28 impact: the 2026-04-14 image was running until Session 5 forced a rebuild, which means the 2026-04-28 fixes for BUG-002 (commits 97bbe98, 7c4203e) and BUG-006 (6d8b27a) were never deployed during the Live Block live-verify. The "structlog appears silent post-restart" observation in the 15:14 UTC session-log entry was misattributed; the real cause was that the running image had a different structlog config / different code paths than HEAD.
- Fix space:
  1. Document in `CONTRIBUTING.md` that backend code changes require `docker compose build backend` (not just restart).
  2. Add a Makefile target `make backend-rebuild` = `docker compose build backend && docker compose up -d backend` so the right command is one keystroke.
  3. (Bigger lift) Add a dev-mode override compose file with a bind mount of `backend/` and uvicorn `--reload`, similar to the frontend's hot-reload setup, so dev-mode picks up source changes without a rebuild.

## Causal context / spec-28 implications

- Risk A directly caused BUG-013 (Blocker) on 2026-04-29. Without remediation, BUG-013 will recur after the next ungraceful shutdown of a long-running stack.
- Risk B masked spec-28's Wave 1 / Live Block live-verifications. The Live Block's "live verify deferred" notes for BUG-006 (and the later BUG-013 filing itself) are partially explained by Risk B — what was being verified was not what was committed.
- For v1.0.0 launch readiness: at minimum a docs note (CONTRIBUTING + recovery runbook) is mandatory. The `auto_vacuum` change is a small Python diff but needs a fresh DB or a one-time migration, so it wants its own spec.

## Defer rationale (for D decision)

Recovery from the BUG-013 incident is complete (Session 5 close). The underlying risks are not user-facing and do not block the v1.0.0 launch path so long as documentation captures the recovery procedure. Both risks deserve a small focused spec (likely v1.1 or a polish-window task) rather than a tactical patch, because:

- `auto_vacuum=incremental` requires the PRAGMA to be set before the schema is created, which means migrating existing checkpoint DBs (or accepting one fresh-DB cutover at deploy time).
- The dev-mode bind-mount + `--reload` setup needs to coexist with the production Dockerfile cleanly; rushing it risks breaking the prod compose stack.
- A startup-time integrity-check + auto-recovery hook needs careful failure-mode design (don't auto-delete user data; communicate clearly when fallback to fresh DB is used).

Filing now to ensure the risks are not lost; v1.1 spec will design the fix.
