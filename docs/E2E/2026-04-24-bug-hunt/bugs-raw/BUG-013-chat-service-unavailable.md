# BUG-013: Every /api/chat request ends in SERVICE_UNAVAILABLE

- **Severity**: Blocker
- **Layer**: Backend (Reasoning secondary)
- **Discovered**: 2026-04-28 ~17:00 UTC via Live Block Charter 1 BUG-006 fix verification (A3)
- **F/D/P decision**: D→F (Session 5 close 2026-04-29 — operational fix, no source change. Initial D rationale preserved below; resolution added in §Resolution. The D→F transition is documented in `session-log.md` per the fdp-gate-contract note that this is a non-standard variant for bugs deferred outside the Live Block.)

## Steps to Reproduce

1. Stack up: 4 services healthy. Backend HEAD includes BUG-002 + BUG-006 fixes (commits 97bbe98 + 7c4203e + 6d8b27a).
2. Issue any /api/chat request with valid `collection_ids`:
   ```
   POST /api/chat
   {"message": "diámetro mínimo NAG-200", "session_id": "any", "collection_ids": ["22923ab5-ea0d-4bea-8ef2-15bf0262674f"]}
   ```
3. Observe NDJSON stream.

## Expected

Stream completes with `{"type": "done", ...}` event after `chunk` and `confidence` events.

## Actual

Stream ends in error event with code `SERVICE_UNAVAILABLE` after the orchestrator→tools→orchestrator pattern. Exception escapes `chat.py`'s `except Exception` handler without logging; root error never surfaces in `docker compose logs backend`.

## Artifacts

- A3's baseline trace `bug006-v1.ndjson` (captured BEFORE BUG-006 fix) shows the IDENTICAL error pattern, exonerating commit 6d8b27a
- Orchestrator's prior end-to-end verify at trace `b95d971d` (15:14 UTC, post-BUG-002-amendment) returned cleanly with `done` event — so the regression appeared between 15:14 and ~17:00 UTC
- File refs (probable):
  - `backend/api/chat.py` — exception handler around `except Exception as e` (ENH-006 / FR-050 area)
  - `backend/agent/research_graph.py` — research → conversation state merge
  - `backend/utils/logging_config.py` (or equivalent) — `cache_logger_on_first_use=True` setting causing chat.py logger to cache before `_configure_logging()` runs

## Root-cause hypothesis

Multiple plausible causes, no single root identified within Live Block budget:

1. **structlog config race**: `cache_logger_on_first_use=True` causes `backend.api.chat` logger to be cached BEFORE `_configure_logging()` runs at startup, so `logger.error("http_chat_stream_error", ...)` calls are silently swallowed. Fix: configure logging earlier in app startup, or remove `cache_logger_on_first_use`.

2. **State-merge issue between research_graph and conversation_graph**: exception fires AFTER `collect_answer` streams its content but before `done`/`citation` events emit, suggesting failure during state merge from the subgraph back to the parent. Could be a Pydantic validation error on a state field that the merge introduces.

3. **Qdrant DNS workaround lost on backend restart**: A3 noted earlier (during BUG-002 first-fix verify at ~15:00 UTC) that the backend container required a manual `/etc/hosts` entry to resolve `qdrant`. That entry won't survive container recreate, so any restart afterwards returns the system to broken state. But A3 also confirmed Qdrant is reachable from inside the container during BUG-013 investigation — so this hypothesis is partially refuted.

4. **Contextvar plumbing from BUG-002 amendment**: the `selected_collections_var` contextvar might not be propagating across asyncio task boundaries within the LangGraph executor. ContextVar.set() inside an async function only affects the current Task; child tasks need explicit context binding (e.g., `asyncio.copy_context()`).

## Causal context / spec-28 implications

- Did NOT regress in commits 97bbe98, 7c4203e, or 6d8b27a — A3 confirmed via baseline trace
- Blocks live verification of BUG-006 fix (~75% citation target unmeasurable while every request fails)
- Blocks RAGAS Wave 3 execution (every Q&A query would fail) — Wave 3 cannot proceed until BUG-013 is fixed
- Investigation outside Live Block scope: needs dedicated debug session with deeper logging (likely temporary `cache_logger_on_first_use=False` to capture the actual error) and step-through across the research → conversation graph state-merge boundary

## Defer rationale (for D decision)

Live Block budget effectively exhausted at 4h+ elapsed; remaining time prioritized for proper close-out (validator, commit, TeamDelete, engram session_summary). BUG-013 surfaces a real production-blocker but needs methodical debugging that cannot fit a F-path patch — would risk an under-investigated fix landing without proper observability. v1.1 spec investigates with a clean slate.

## Resolution (Session 5, 2026-04-29)

**All 4 hypotheses above were refuted.** None of structlog cache, state-merge, Qdrant DNS, or contextvar plumbing was the cause. The actual root cause is operational data corruption.

**True root cause**: `data/checkpoints.db` (LangGraph SQLite checkpointer) was corrupt — `PRAGMA integrity_check` reported multiple double-referenced freelist pages (e.g. "Freelist: 2nd reference to page 8976"). Forensic stats: 89,257 pages × 4 KB = 366 MB total; **81,079 pages on the freelist (91% of the file is deleted-but-unreclaimed space)**, ~32 MB of live data, 1,870 checkpoints across 102 distinct threads, WAL clean.

**Failure mechanic**: `graph.astream(...)` writes a checkpoint to SQLite per node. With a corrupt B-tree, a write that tries to reuse a freelist page raises `DatabaseError: database disk image is malformed`. The exception escapes `chat.py:376` `except Exception as e` → `logger.error("http_chat_stream_error", error="DatabaseError", detail="database disk image is malformed", ...)` → the user-facing yield emits `{"type": "error", "code": "SERVICE_UNAVAILABLE"}`. The H1 hypothesis (logger swallowing) was incorrect: once the freshly built backend image was running, the structlog `error` log fired correctly with the actual exception detail. The reason A3 saw "no error in logs" during the Live Block was different: **the running backend image was built 2026-04-14, two weeks before the spec-28 fixes (97bbe98 + 7c4203e + 6d8b27a, all 2026-04-28), so live `/api/chat` traffic was hitting code that didn't yet have the structlog config or the BUG-002/BUG-006 patches.** The `Dockerfile.backend` does not volume-mount `backend/`, so `docker compose restart` does NOT pick up source changes — only `docker compose build backend && docker compose up -d backend` does. This is captured separately as BUG-014.

**Likely cause of corruption**: spec-26's `_prune_old_checkpoint_threads` (`backend/main.py:119-137`) DELETEs old threads but never VACUUMs. The 91% freelist ratio is the fingerprint. An ungraceful shutdown (SIGKILL during a freelist-page reuse write) corrupts the B-tree. See BUG-014 for the prevention follow-up.

**Recovery procedure (validated, runbook-worthy)**:
1. `docker compose stop backend` (release file locks)
2. `sqlite3 data/checkpoints.db "VACUUM INTO 'data/checkpoints.db.salvage';"` — produces clean 33 MB copy with only live data
3. `sqlite3 data/checkpoints.db.salvage "REINDEX;"` — VACUUM INTO copies index entries that may be stale; REINDEX rebuilds them from table data
4. `sqlite3 data/checkpoints.db.salvage "PRAGMA integrity_check;"` — must return `ok` (it did)
5. Rename corrupt → backup; rename salvage → primary; remove `.db-shm` and `.db-wal` (SQLite recreates them)
6. `docker compose start backend`

In our case the salvage retained all 102 threads / 1,870 checkpoints / 9,962 writes (slight count adjustments post-REINDEX: 104 / 1,991 / 8,498). No checkpoint-state loss.

**Verification (3-query smoke, 2026-04-29 12:51 UTC, post-recovery)**:
- Q1 factoid `diametro minimo NAG-200` (trace `0b11f219`) — done @ 10.9s, 1 collection queried, 8 passages
- Q2 analytical Spanish `¿Qué requisitos se aplican a la selección de materiales en redes de gas natural según NAG-200?` (trace `9f022983`) — done @ 38.4s, 1 collection, 5 passages
- Q3 OOS English `What is the airspeed velocity of an unladen swallow?` (trace `1ca71b56`) — done @ 28.6s, 1 collection, 5 passages, graceful decline (no hallucinated citations — BUG-007 user-facing closure holds)
- Logs: zero SERVICE_UNAVAILABLE, zero DatabaseError, zero `cross_encoder_rerank` ValidationError, zero `retrieval_unscoped_fanout`. BUG-002 amendment verified end-to-end: each trace queried exactly 1 collection (the user's `collection_ids`).

**Wave 3 (RAGAS run) is unblocked.** Session 6 (Q-018/Q-019/Q-020 user-authored golden pairs + RAGAS evaluation) can proceed.
