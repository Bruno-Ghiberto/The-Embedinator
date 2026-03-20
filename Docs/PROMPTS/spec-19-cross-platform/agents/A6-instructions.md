# A6 — Backend Architect: Graceful Shutdown & Environment

## Role & Mission

You are the backend architect responsible for implementing graceful shutdown (shutting_down flag, WAL checkpoint, checkpointer close), shutdown rejection in the chat endpoint, and updating `.env.example` with new Docker/launcher variables.

## FR Ownership

FR-043, FR-050, FR-051, FR-052

## Task Ownership

T069 through T074 (Phase 7: Graceful Shutdown + Environment)

### Tasks

- **T069**: Modify `backend/main.py`: add `app.state.shutting_down = False` at the start of `lifespan()` (before `yield`). Set `app.state.shutting_down = True` at start of the shutdown section (after `yield`) (FR-050). **IMPORTANT**: A3 already modified the startup section in Wave 1 (upload dir + write-access). Your changes go in the shutdown section (after `yield`) PLUS one line before `yield`.
- **T070**: Modify `backend/api/chat.py`: add early return at the top of the chat endpoint — if `request.app.state.shutting_down`, yield NDJSON error `{"type": "error", "code": "SHUTTING_DOWN", "message": "Server is shutting down. Please retry in a moment."}` and return (FR-050)
- **T071**: Modify `backend/main.py`: in the shutdown section, add `await db.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")` for the main SQLite database BEFORE `await db.close()` (FR-051)
- **T072**: Modify `backend/main.py`: in the shutdown section, open the checkpoints DB, execute `PRAGMA wal_checkpoint(TRUNCATE)`, close connection. Then explicitly close the LangGraph checkpointer connection via `checkpointer.conn.close()` (FR-051, FR-052)
- **T073**: Modify `.env.example`: add a new `Docker / Launcher` section at the TOP of the file with documented entries for `BACKEND_URL`, `OLLAMA_MODELS`, `EMBEDINATOR_GPU`, and all 5 `EMBEDINATOR_PORT_*` variables with defaults and descriptions. Include comment explaining these are NOT read by Pydantic Settings (FR-043)
- **T074**: Verify `python -c "from backend.main import create_app"` succeeds. Verify `.env.example` contains all 8 new variables.

## Files to CREATE

None — all modifications to existing files.

## Files to MODIFY

| File | Changes |
|------|---------|
| `backend/main.py` | Add `shutting_down` flag (before yield), WAL checkpoint + checkpointer close (after yield). A3 already modified startup — your changes are in shutdown section. |
| `backend/api/chat.py` | Add early return for shutdown rejection with NDJSON error event |
| `.env.example` | Add Docker/Launcher section at TOP with 8 new variables |

## Files NEVER to Touch

- `Makefile` — SC-010
- `backend/config.py` — no Settings changes. The `EMBEDINATOR_PORT_*` vars are for Docker Compose, NOT Pydantic Settings.
- `requirements.txt` — no new Python packages
- `frontend/**` — owned by A2 and A5
- `docker-compose*.yml` — owned by A1 (Wave 1, already done)
- `Dockerfile*` — owned by A1
- `backend/api/health.py` — owned by A3 (Wave 1, already done)
- `backend/agent/schemas.py` — owned by A3
- `backend/middleware.py` — owned by A3
- Any `tests/**` files

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Section 6.3 (Graceful Shutdown), Section 6.4 (Database Initialization)
3. `specs/019-cross-platform-dx/spec.md` — FR-043, FR-050, FR-051, FR-052
4. `specs/019-cross-platform-dx/tasks.md` — T069 through T074
5. `specs/019-cross-platform-dx/data-model.md` — Environment Variable Contracts section
6. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — risk gotchas

## Key Gotchas

1. **`backend/main.py` multi-touch** — A3 already modified the startup section (before `yield`) in Wave 1 — upload dir creation and write-access test. Read the current file to see A3's changes. Your `shutting_down = False` line goes before `yield` (but after A3's additions). ALL your shutdown logic (T071, T072) goes after `yield`.
2. **`.env.example` append at TOP, don't modify existing** — Add a new "Docker / Launcher" section at the very TOP of the file. The existing 28+ Settings fields below MUST NOT be modified. Include a clear comment: "These variables are read by Docker Compose and the launcher script, NOT by Pydantic Settings (backend/config.py)."
3. **WAL checkpoint order** — Execute `PRAGMA wal_checkpoint(TRUNCATE)` BEFORE `await db.close()`. If you close first, you can't checkpoint.
4. **Checkpoints DB** — The checkpoints database is separate from the main database. It's at `data/checkpoints.db`. You need to open it with `aiosqlite` (or sync `sqlite3`), checkpoint, then close. Also close the LangGraph checkpointer connection.
5. **NDJSON shutdown error** — The chat endpoint uses NDJSON streaming. The shutdown rejection should yield a single NDJSON line: `{"type": "error", "code": "SHUTTING_DOWN", "message": "Server is shutting down. Please retry in a moment."}` and then return. Check the existing chat endpoint pattern for how NDJSON events are yielded.
6. **No new packages** — Use existing `aiosqlite` (already a dependency) for checkpoint DB operations.
7. **Checkpointer connection** — The LangGraph `AsyncSqliteSaver` checkpointer stores its connection. Access it via `checkpointer.conn` to close it explicitly. Read `backend/main.py` to find how the checkpointer is stored (likely in `app.state`).

## `.env.example` New Section Template

Add this at the TOP of `.env.example` (before existing content):

```bash
# ══════════════════════════════════════════════════════════════════════════════
# Docker / Launcher Configuration
# ══════════════════════════════════════════════════════════════════════════════
# These variables are read by Docker Compose and the launcher script
# (embedinator.sh / embedinator.ps1). They are NOT read by Pydantic Settings
# (backend/config.py). The backend does not use these directly.
# ──────────────────────────────────────────────────────────────────────────────

# BACKEND_URL — Server-side URL for Next.js rewrites to reach the backend.
# Inside Docker: http://backend:8000. Local dev: http://localhost:8000.
# BACKEND_URL=http://backend:8000

# OLLAMA_MODELS — Comma-separated list of models to auto-download on first run.
# OLLAMA_MODELS=qwen2.5:7b,nomic-embed-text

# EMBEDINATOR_GPU — Force GPU profile. Auto-detected if not set.
# Valid values: nvidia, amd, intel, none
# EMBEDINATOR_GPU=

# EMBEDINATOR_PORT_FRONTEND — Frontend (Next.js) host port. Default: 3000.
# EMBEDINATOR_PORT_FRONTEND=3000

# EMBEDINATOR_PORT_BACKEND — Backend API (FastAPI) host port. Default: 8000.
# EMBEDINATOR_PORT_BACKEND=8000

# EMBEDINATOR_PORT_QDRANT — Qdrant HTTP API host port. Default: 6333.
# EMBEDINATOR_PORT_QDRANT=6333

# EMBEDINATOR_PORT_QDRANT_GRPC — Qdrant gRPC API host port. Default: 6334.
# EMBEDINATOR_PORT_QDRANT_GRPC=6334

# EMBEDINATOR_PORT_OLLAMA — Ollama API host port. Default: 11434.
# EMBEDINATOR_PORT_OLLAMA=11434

# ══════════════════════════════════════════════════════════════════════════════
# Application Settings (read by Pydantic Settings in backend/config.py)
# ══════════════════════════════════════════════════════════════════════════════
```

## Verification Commands

```bash
# Main module imports
python -c "from backend.main import create_app" && echo "PASS: main.py loads" || echo "FAIL"

# .env.example has all new vars
grep -q 'BACKEND_URL' .env.example && echo "PASS: BACKEND_URL" || echo "FAIL"
grep -q 'OLLAMA_MODELS' .env.example && echo "PASS: OLLAMA_MODELS" || echo "FAIL"
grep -q 'EMBEDINATOR_GPU' .env.example && echo "PASS: EMBEDINATOR_GPU" || echo "FAIL"
grep -q 'EMBEDINATOR_PORT_FRONTEND' .env.example && echo "PASS: PORT_FRONTEND" || echo "FAIL"
grep -q 'EMBEDINATOR_PORT_BACKEND' .env.example && echo "PASS: PORT_BACKEND" || echo "FAIL"
grep -q 'EMBEDINATOR_PORT_QDRANT' .env.example && echo "PASS: PORT_QDRANT" || echo "FAIL"
grep -q 'EMBEDINATOR_PORT_QDRANT_GRPC' .env.example && echo "PASS: PORT_QDRANT_GRPC" || echo "FAIL"
grep -q 'EMBEDINATOR_PORT_OLLAMA' .env.example && echo "PASS: PORT_OLLAMA" || echo "FAIL"

# Shutdown flag in main.py
grep -q 'shutting_down' backend/main.py && echo "PASS: shutdown flag" || echo "FAIL"

# Chat endpoint has shutdown check
grep -q 'SHUTTING_DOWN' backend/api/chat.py && echo "PASS: shutdown rejection" || echo "FAIL"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
