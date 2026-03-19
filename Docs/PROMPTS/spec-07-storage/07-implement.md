# Spec 07: Storage Architecture -- Implementation Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## Agent Team Orchestration Protocol

> **MANDATORY**: Agent Teams is REQUIRED for this spec. You MUST be running
> inside tmux. Agent Teams auto-detects tmux and spawns each teammate in its
> own split pane (the default `"auto"` teammateMode).
>
> **Enable**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`:
> ```json
> {
>   "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
> }
> ```
>
> **tmux multi-pane spawning is REQUIRED.** Each agent gets its own tmux pane
> for real-time visibility. Do NOT run agents sequentially in a single pane.
>
> **Reference**: https://code.claude.com/docs/en/agent-teams

### Architecture

The **lead session** (you, the orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list with dependency tracking -- teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Agent Team Composition

| Agent | Role | subagent_type | Model | Wave | Tasks |
|-------|------|---------------|-------|------|-------|
| A1 | SQLiteDB Foundation & Schema | python-expert | **Opus 4.6** | 1 | T001-T027 |
| A2 | QdrantStorage | backend-architect | Sonnet 4.6 | 2 | T028-T045 |
| A3 | KeyManager | security-engineer | Sonnet 4.6 | 2 | T046-T057 |
| A4 | Integration Wiring | system-architect | Sonnet 4.6 | 3 | T058-T097 |
| A5 | Quality & Regression | quality-engineer | Sonnet 4.6 | 4 | T098-T163, T164 |

**Rationale for Opus on A1**: SQLiteDB is the most complex component -- 7 tables, full CRUD, async context management, schema constraints, WAL configuration, error handling, and comprehensive tests. All other waves depend on A1 being correct. A2 and A3 are straightforward implementations from clear contracts.

### Wave Execution Order

```
Wave 1 (A1):        SQLiteDB Foundation & Schema (sequential)     -> Checkpoint Gate
Wave 2 (A2 + A3):   QdrantStorage + KeyManager (parallel)         -> Checkpoint Gate
Wave 3 (A4):        Integration Wiring + Cross-Store Tests        -> Checkpoint Gate
Wave 4 (A5):        Quality, Regression & Polish                  -> Done
```

### Step 1: Create the Team

```
Create an agent team called "spec07-storage" to implement the Storage
Architecture feature.
```

The lead creates the team. All teammates will appear in their own tmux panes automatically.

### Step 2: Create Tasks with Dependencies

Create tasks in the shared task list so teammates can self-claim. Tasks encode the wave dependency chain:

```
Create the following tasks for the team:

Wave 1 -- SQLiteDB Foundation & Schema:
- T001-T027: Project structure, SQLiteDB class, all 7 tables, CRUD methods, unit tests (assign to A1)

Wave 2 -- QdrantStorage + KeyManager (parallel, after Wave 1 completes):
- T028-T045: QdrantStorage class, hybrid search, batch upsert, unit tests (assign to A2, depends on Wave 1)
- T046-T057: KeyManager class, Fernet encryption, security tests (assign to A3, depends on Wave 1)

Wave 3 -- Integration Wiring (after Wave 2 completes):
- T058-T097: ParentStore, __init__.py exports, main.py lifespan, integration tests,
  concurrent reads, schema validation, performance (assign to A4, depends on Wave 2)

Wave 4 -- Quality & Regression (after Wave 3 completes):
- T098-T163, T164: Code review, security audit, documentation audit, regression tests,
  full test suite, commits (assign to A5, depends on Wave 3)
```

### Step 3: Spawn Teammates per Wave

**Wave 1 -- Spawn A1 (SQLiteDB Foundation):**
```
Spawn a teammate named "A1-foundation-schema" with subagent_type "python-expert" and model Opus.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A1-foundation-schema.md FIRST, then execute all assigned tasks."
```

Wait for A1 to complete. Run checkpoint gate (see below). Then proceed to Wave 2.

**Wave 2 -- Spawn A2 + A3 (parallel, each in own tmux pane):**
```
Spawn two teammates in parallel:

1. Teammate "A2-qdrant-storage" with subagent_type "backend-architect" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A2-qdrant-storage.md FIRST, then execute all assigned tasks."

2. Teammate "A3-key-manager" with subagent_type "security-engineer" and model Sonnet:
   "Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A3-key-manager.md FIRST, then execute all assigned tasks."
```

Wait for both A2 and A3 to complete. Run checkpoint gate. Then proceed to Wave 3.

**Wave 3 -- Spawn A4 (Integration Wiring):**
```
Spawn a teammate named "A4-integration-wiring" with subagent_type "system-architect" and model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A4-integration-wiring.md FIRST, then execute all assigned tasks."
```

Wait for A4. Run checkpoint gate. Then proceed to Wave 4.

**Wave 4 -- Spawn A5 (Quality & Polish):**
```
Spawn a teammate named "A5-quality-polish" with subagent_type "quality-engineer" and model Sonnet.
Prompt: "Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A5-quality-polish.md FIRST, then execute all assigned tasks."
```

### Step 4: Checkpoint Gates (Lead Runs After Each Wave)

The lead runs these verification commands after each wave completes. If a gate fails, message the relevant teammate to fix it before proceeding.

```bash
# Wave 1: SQLiteDB Foundation ready
python -c "from backend.storage.sqlite_db import SQLiteDB; print('SQLiteDB importable')"
python -c "
import asyncio, aiosqlite
async def check():
    from backend.storage.sqlite_db import SQLiteDB
    db = SQLiteDB(':memory:')
    await db.connect()
    cursor = await db.db.execute('PRAGMA journal_mode')
    mode = (await cursor.fetchone())[0]
    cursor2 = await db.db.execute('PRAGMA foreign_keys')
    fk = (await cursor2.fetchone())[0]
    print(f'WAL: {mode}, FK: {fk}')
    await db.close()
asyncio.run(check())
"
ruff check backend/storage/sqlite_db.py

# Wave 2: QdrantStorage + KeyManager importable
python -c "from backend.storage.qdrant_client import QdrantStorage; print('QdrantStorage importable')"
python -c "from backend.providers.key_manager import KeyManager; print('KeyManager importable')"
ruff check backend/storage/qdrant_client.py backend/providers/key_manager.py

# Wave 3: Integration wiring
python -c "from backend.storage import SQLiteDB, QdrantStorage; print('storage exports OK')"
python -c "from backend.storage.parent_store import ParentStore; print('ParentStore OK')"
ruff check backend/storage/__init__.py backend/storage/parent_store.py

# Wave 4: Full test suite
zsh scripts/run-tests-external.sh -n spec07-full tests/
cat Docs/Tests/spec07-full.status
cat Docs/Tests/spec07-full.summary
```

### Step 5: Shutdown and Cleanup

After all waves complete and checkpoint gates pass:

```
Ask all teammates to shut down, then clean up the team.
```

This removes the shared team resources. Always shut down teammates before cleanup.

### Orchestration Rules

1. **Never skip checkpoint gates** -- a failed gate means the next wave's teammates will build on broken code.
2. **Use SendMessage for steering** -- if a teammate is going off-track, message them directly in their tmux pane or via the lead's messaging system.
3. **Parallel waves share files safely** -- Wave 2 agents create different files: A2 owns `qdrant_client.py`, A3 owns `key_manager.py`. No merge conflicts.
4. **Teammate prompts are minimal** -- just point to the instruction file. All context lives in the instruction files and CLAUDE.md.
5. **Model selection** -- A1 (SQLiteDB, complex async schema + 7 tables + comprehensive CRUD) uses Opus. All others use Sonnet for cost efficiency.
6. **Monitor via tmux** -- click into any teammate's pane to see their progress.
7. **If a teammate fails** -- shut it down and spawn a replacement with the same instruction file. The task list tracks which tasks are done.
8. **Never inline spec content in spawn prompts** -- agents MUST read their instruction file FIRST. All authoritative context lives in the instruction files and spec artifacts.
9. **Wave 2 file ownership** -- A2 owns `qdrant_client.py`. A3 owns `key_manager.py`. No overlap.
10. **All tests use external runner** -- absolutely NO pytest inside Claude Code.

---

## Authoritative Reference Table

| Artifact | Path | Purpose |
|----------|------|---------|
| Spec | `specs/007-storage-architecture/spec.md` | 4 user stories, 16 FRs, 11 SCs |
| Plan | `specs/007-storage-architecture/plan.md` | Tech stack, constitution check, project structure |
| Tasks | `specs/007-storage-architecture/tasks.md` | 164 tasks (T001-T163 + T164), 9 phases, 4-wave agents |
| Data Model | `specs/007-storage-architecture/data-model.md` | 7 entities with fields, constraints, relationships |
| SQLite Contract | `specs/007-storage-architecture/contracts/sqlite-contract.md` | SQLiteDB method signatures |
| Qdrant Contract | `specs/007-storage-architecture/contracts/qdrant-contract.md` | QdrantStorage method signatures |
| KeyManager Contract | `specs/007-storage-architecture/contracts/key-manager-contract.md` | Encryption interface |
| Quickstart | `specs/007-storage-architecture/quickstart.md` | Usage examples |
| Agent Instructions | `Docs/PROMPTS/spec-07-storage/agents/A*.md` | Per-agent task details |

---

## Implementation Scope

### Files to Create

| File | Agent | Purpose |
|------|-------|---------|
| `backend/storage/sqlite_db.py` | A1 | SQLiteDB class: 7 tables, full CRUD, WAL mode |
| `backend/storage/qdrant_client.py` | A2 | QdrantStorage class: hybrid search, batch upsert |
| `backend/providers/key_manager.py` | A3 | KeyManager: Fernet encryption/decryption |
| `backend/storage/parent_store.py` | A4 | ParentStore: convenience wrapper for parent chunks |
| `backend/storage/__init__.py` | A4 | Public API exports |
| `tests/unit/test_sqlite_db.py` | A1 | SQLiteDB CRUD, schema, constraints |
| `tests/unit/test_qdrant_storage.py` | A2 | QdrantStorage mocked unit tests |
| `tests/unit/test_key_manager.py` | A3 | KeyManager encryption unit tests |
| `tests/unit/test_parent_store.py` | A4 | ParentStore unit tests |
| `tests/integration/test_storage_integration.py` | A4 | Cross-store integration tests |
| `tests/integration/test_concurrent_reads.py` | A4 | WAL concurrency validation |
| `tests/integration/test_schema_validation.py` | A4 | Schema, FK, index validation |
| `tests/integration/test_performance.py` | A4 | Latency target validation |
| `tests/regression/test_regression.py` | A5 | FR/SC regression prevention |

### Files to Modify

| File | Agent | What Changes |
|------|-------|--------------|
| `backend/config.py` | A4 | Add `embedinator_fernet_key` field (if not using env-only) |
| `backend/main.py` | A4 | Initialize storage components in lifespan |

### Files That Exist and Are NOT Modified

- `backend/errors.py` -- `CircuitOpenError`, `SQLiteError`, `IngestionError` already exist. DO NOT MODIFY.
- `backend/agent/schemas.py` -- `ParentChunk` model with `parent_id`, `collection` fields. DO NOT MODIFY. ParentStore uses SQL column aliases instead.
- `backend/agent/conversation_graph.py` -- Graph definition. DO NOT TOUCH.
- `backend/agent/research_graph.py` -- ResearchGraph. DO NOT TOUCH.
- `backend/agent/nodes.py` -- Conversation nodes. DO NOT TOUCH.
- `backend/agent/confidence.py` -- 5-signal confidence formula. DO NOT TOUCH.
- `backend/retrieval/searcher.py` -- HybridSearcher. DO NOT TOUCH.
- `backend/retrieval/reranker.py` -- Reranker. DO NOT TOUCH.

### FR-to-Task-to-Agent Mapping

| FR | Description | Tasks | Agent |
|----|-------------|-------|-------|
| FR-001 | Collections table | T009 | A1 |
| FR-002 | Documents table with UNIQUE | T010 | A1 |
| FR-003 | Ingestion jobs table | T011 | A1 |
| FR-004 | Parent chunks table (UUID5) | T012 | A1 |
| FR-005 | Query traces table (reasoning_steps_json, strategy_switches_json) | T013 | A1 |
| FR-006 | Settings table | T014 | A1 |
| FR-007 | Providers table (encrypted keys) | T015 | A1 |
| FR-008 | SQLite WAL mode | T008 | A1 |
| FR-009 | SQLite foreign keys ON | T008 | A1 |
| FR-010 | Qdrant dual vector config (dense + sparse) | T030 | A2 |
| FR-011 | Qdrant payload (11 fields) | T036 | A2 |
| FR-012 | UUID5 deterministic IDs | T012, T032 | A1, A2 |
| FR-013 | Fernet API key encryption | T047, T048 | A3 |
| FR-014 | Parent batch retrieval with aliases | T059 | A4 |
| FR-015 | Sequential ingestion queue (status tracking) | T011 | A1 |
| FR-016 | Idempotent resume via UUID5 | T012, T032 | A1, A2 |

---

## Codebase Verification (Verified Against Live Code)

These facts were verified against the live codebase. Agents MUST respect them.

1. **Settings class** at `config.py:6-74`: ALREADY has `qdrant_host`, `qdrant_port`, `sqlite_path`, `api_key_encryption_secret`. The field `api_key_encryption_secret` is currently a plain string (line 25). Spec-07 uses `EMBEDINATOR_FERNET_KEY` env var instead (Constitution Principle V). A4 must add the new field or ensure proper env var loading.
2. **Existing `QdrantClientWrapper`** at `qdrant_client.py:21-183`: Has `connect()`, `close()`, `health_check()`, `search()`, `upsert()`, `ensure_collection()` with circuit breaker and tenacity retry. Spec-07 creates a NEW `QdrantStorage` class in the SAME file that adds hybrid search, sparse vectors, batch upsert with payload validation, and collection management. The existing `QdrantClientWrapper` remains for backward compatibility.
3. **Existing `ParentStore`** at `parent_store.py:16-69`: Has `get_by_ids()` with SQL aliases `id AS parent_id`, `collection_id AS collection`. This was updated in spec-06. Spec-07 A4 extends this with additional convenience methods.
4. **Existing `SQLiteDB`** at `sqlite_db.py:17-`: Has `connect()`, `close()`, `_create_tables()` with 6 tables. Spec-07 A1 creates a NEW version of this class with all 7 tables, async context manager, and full CRUD. The spec-06 migration pattern established the create-copy-drop-rename approach.
5. **lifespan** at `main.py:44-125`: Initializes SQLiteDB, QdrantClientWrapper, ProviderRegistry, AsyncSqliteSaver, HybridSearcher, Reranker, ParentStore, research tools, graphs. A4 updates this to also initialize QdrantStorage and KeyManager.
6. **`CircuitOpenError`** at `errors.py`: Already exists. Used by QdrantClientWrapper and inference CB.
7. **`SQLiteError`** at `errors.py`: Already exists. Used by ParentStore.
8. **`IngestionError`** at `errors.py`: Already exists. Used by pipeline.

---

## Code Specifications

### Critical Patterns (ALL Agents MUST Follow)

```python
# Import settings at function/method level for testability
from backend.config import settings

# structlog pattern
import structlog
logger = structlog.get_logger(__name__)

# Async context manager for SQLiteDB
async with SQLiteDB("data/embedinator.db") as db:
    ...

# Constructor DI pattern
class ParentStore:
    def __init__(self, db: SQLiteDB):
        self.db = db

# Return dicts from database methods, not Pydantic models
async def get_collection(self, collection_id: str) -> dict | None:
    ...

# External test runner -- NEVER pytest inside Claude Code
# zsh scripts/run-tests-external.sh -n <name> <target>
```

> **IMPORTANT**: The existing Qdrant wrapper is `QdrantClientWrapper`. Spec-07 adds a NEW
> `QdrantStorage` class in the same file (`qdrant_client.py`). Both classes coexist.
> The existing `QdrantClientWrapper` is NOT removed or renamed.

---

### SQLite Schema SQL (backend/storage/sqlite_db.py)

All 7 tables per FR-001 through FR-007. Pay special attention to:
- `query_traces` includes `reasoning_steps_json` and `strategy_switches_json` (FR-005)
- `confidence_score` is `INTEGER` (0-100 scale), NOT REAL (FR-005, SC-010)
- `EMBEDINATOR_FERNET_KEY` is the env var name (Constitution V), NOT `SECRET_KEY`

```sql
CREATE TABLE IF NOT EXISTS collections (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    embedding_model     TEXT NOT NULL DEFAULT 'nomic-embed-text',
    chunk_profile       TEXT NOT NULL DEFAULT 'default',
    qdrant_collection_name  TEXT NOT NULL UNIQUE,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    filename        TEXT NOT NULL,
    file_path       TEXT NOT NULL,
    file_hash       TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    chunk_count     INTEGER DEFAULT 0,
    ingested_at     TEXT,
    UNIQUE(collection_id, file_hash)
);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id              TEXT PRIMARY KEY,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    status          TEXT NOT NULL DEFAULT 'started',
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    error_msg       TEXT,
    chunks_processed INTEGER DEFAULT 0,
    chunks_skipped  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parent_chunks (
    id              TEXT PRIMARY KEY,
    collection_id   TEXT NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    document_id     TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    metadata_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_collection ON parent_chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_parent_chunks_document ON parent_chunks(document_id);

CREATE TABLE IF NOT EXISTS query_traces (
    id                          TEXT PRIMARY KEY,
    session_id                  TEXT NOT NULL,
    query                       TEXT NOT NULL,
    sub_questions_json          TEXT,
    collections_searched        TEXT,
    chunks_retrieved_json       TEXT,
    reasoning_steps_json        TEXT,
    strategy_switches_json      TEXT,
    meta_reasoning_triggered    INTEGER DEFAULT 0,
    latency_ms                  INTEGER,
    llm_model                   TEXT,
    embed_model                 TEXT,
    confidence_score            INTEGER,
    created_at                  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_traces_session ON query_traces(session_id);
CREATE INDEX IF NOT EXISTS idx_traces_created ON query_traces(created_at);

CREATE TABLE IF NOT EXISTS settings (
    key     TEXT PRIMARY KEY,
    value   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS providers (
    name       TEXT PRIMARY KEY,
    api_key_encrypted TEXT,
    base_url   TEXT,
    is_active  INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);
```

**Key differences from the old 07-implement.md schema:**
- `query_traces` now has `reasoning_steps_json TEXT` and `strategy_switches_json TEXT` (FR-005)
- `confidence_score` is `INTEGER` not `REAL` (0-100 scale per FR-005, SC-010)
- Foreign keys include `ON DELETE CASCADE` (per data-model.md)

---

### SQLiteDB Class (backend/storage/sqlite_db.py)

```python
class SQLiteDB:
    """Async SQLite storage with WAL mode and FK enforcement."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection, enable WAL + FKs, init schema."""

    async def close(self) -> None:
        """Close database connection."""

    async def __aenter__(self) -> SQLiteDB:
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _init_schema(self) -> None:
        """Create all 7 tables (idempotent). Set PRAGMAs."""
```

Full CRUD methods per the SQLite contract (`specs/007-storage-architecture/contracts/sqlite-contract.md`).

---

### QdrantStorage Class (backend/storage/qdrant_client.py)

A NEW class added to the SAME file as the existing `QdrantClientWrapper`. Both coexist.

Key methods from the Qdrant contract:
- `create_collection()` -- dense 768d cosine + sparse BM25 with IDF modifier
- `batch_upsert()` -- idempotent via point ID, fail-entire-batch on timeout
- `search_hybrid()` -- weighted rank fusion (default 0.6 dense + 0.4 sparse)
- `delete_points()` / `delete_points_by_filter()` -- point removal
- `health_check()` -- returns True/False for circuit breaker integration

Qdrant point payload (11 required fields per FR-011):

```python
payload = {
    "text": child_chunk_text,        # ~500 chars (Constitution III)
    "parent_id": uuid5_parent_id,    # links to SQLite parent_chunks.id
    "breadcrumb": "Collection > Document > Section",
    "source_file": "report.pdf",
    "page": 3,
    "chunk_index": 5,
    "doc_type": "Prose",             # or "Code" -- only two values
    "chunk_hash": "sha256_hex",
    "embedding_model": "all-MiniLM-L6-v2",
    "collection_name": "qdrant_collection_name",
    "ingested_at": "2026-03-13T10:00:00Z",
}
```

---

### KeyManager Class (backend/providers/key_manager.py)

```python
class KeyManager:
    """Fernet symmetric encryption for API keys."""

    def __init__(self):
        """Load EMBEDINATOR_FERNET_KEY from environment."""

    def encrypt(self, plaintext: str) -> str:
        """Encrypt plaintext API key. Returns base64-encoded ciphertext."""

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt ciphertext. Returns plaintext. Raises on failure."""

    def is_valid_key(self, ciphertext: str) -> bool:
        """Quick validation without decryption."""
```

**Constitution V compliance**: The env var is `EMBEDINATOR_FERNET_KEY`, NOT `SECRET_KEY`, NOT `api_key_encryption_secret`. The existing `api_key_encryption_secret` field in `config.py` line 25 is a Phase 1 artifact. KeyManager reads directly from `os.environ["EMBEDINATOR_FERNET_KEY"]`.

---

### ParentStore Class (backend/storage/parent_store.py)

Extends the existing ParentStore with additional convenience methods:

```python
class ParentStore:
    def __init__(self, db: SQLiteDB): ...

    async def get_by_ids(self, parent_ids: list[str]) -> list[ParentChunk]:
        """Batch retrieval with column aliases (id AS parent_id, collection_id AS collection)."""

    async def get_all_by_collection(self, collection_id: str) -> list[ParentChunk]:
        """Retrieve all parent chunks for a collection."""
```

The SQL aliases (`id AS parent_id`, `collection_id AS collection`) ensure the `ParentChunk` Pydantic model in `schemas.py` is NOT modified. This pattern was established in spec-06.

---

### Configuration Updates (backend/config.py)

The `Settings` class already has:
- `qdrant_host`, `qdrant_port` -- Qdrant connection
- `sqlite_path` -- SQLite database path
- `api_key_encryption_secret` -- Phase 1 artifact (KeyManager uses `EMBEDINATOR_FERNET_KEY` env var instead)

No new config fields are strictly required for spec-07. The `EMBEDINATOR_FERNET_KEY` is loaded directly from `os.environ` by KeyManager, not from the Settings class.

---

### main.py Lifespan Updates (backend/main.py)

A4 updates the lifespan to initialize QdrantStorage (separate from QdrantClientWrapper) and KeyManager:

```python
# In lifespan(), after existing QdrantClientWrapper initialization:
from backend.storage.qdrant_client import QdrantStorage

qdrant_storage = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
app.state.qdrant_storage = qdrant_storage
logger.info("qdrant_storage_initialized")

# KeyManager initialization (optional -- only if providers need encryption)
from backend.providers.key_manager import KeyManager
try:
    key_manager = KeyManager()
    app.state.key_manager = key_manager
    logger.info("key_manager_initialized")
except ValueError as e:
    logger.warning("key_manager_skipped", reason=str(e))
    app.state.key_manager = None
```

---

## Error Handling

| Location | Error | Recovery |
|----------|-------|----------|
| `SQLiteDB.connect()` | Connection failure | Log error and raise. App cannot start without SQLite. |
| `SQLiteDB._init_schema()` | Schema conflict | Use CREATE TABLE IF NOT EXISTS for idempotency. |
| `SQLiteDB` CRUD | IntegrityError | Unique/FK constraint violation. Raise to caller. |
| `SQLiteDB` CRUD | OperationalError | Database locked, no space, corrupt. Log and raise. |
| `QdrantStorage.create_collection()` | Collection exists | Check existence first, return without error. |
| `QdrantStorage.batch_upsert()` | Timeout/connection | Fail entire batch. Caller retries (idempotent). |
| `QdrantStorage` methods | Circuit open | Raise CircuitOpenError. |
| `KeyManager.__init__()` | Missing EMBEDINATOR_FERNET_KEY | Raise ValueError. Startup fails (fail-secure). |
| `KeyManager.decrypt()` | Invalid ciphertext | Raise ValueError or InvalidToken. Provider disabled. |
| `KeyManager.decrypt()` | HMAC tamper detected | Raise InvalidToken. Log security warning. |

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** All test execution uses the external runner.

```bash
# Wave 1: SQLiteDB unit tests
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py

# Wave 2: QdrantStorage + KeyManager unit tests
zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py

# Wave 3: Integration tests (requires Qdrant running)
docker compose up qdrant -d
zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/test_storage_integration.py
zsh scripts/run-tests-external.sh -n spec07-concurrent tests/integration/test_concurrent_reads.py
zsh scripts/run-tests-external.sh -n spec07-schema tests/integration/test_schema_validation.py

# Wave 4: Full regression + full suite
zsh scripts/run-tests-external.sh -n spec07-regression tests/regression/test_regression.py
zsh scripts/run-tests-external.sh -n spec07-full tests/

# Check status:
cat Docs/Tests/<name>.status       # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/<name>.summary      # ~20 lines summary
```

---

## Checkpoint Gate Definitions

### Wave 1 Gate (after A1 completes)

**Verification**:
1. `SQLiteDB` class importable with all CRUD methods
2. All 7 tables created with correct schema
3. PRAGMA journal_mode returns "wal"
4. PRAGMA foreign_keys returns 1
5. All unit tests passing via external runner
6. `ruff check backend/storage/sqlite_db.py` passes

**Gate command**:
```bash
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py
cat Docs/Tests/spec07-wave1.status  # must be PASSED
```

### Wave 2 Gate (after A2 + A3 both complete)

**Verification**:
1. `QdrantStorage` class importable with all contract methods
2. `KeyManager` class importable with encrypt/decrypt/is_valid_key
3. All unit tests passing for both modules
4. `ruff check` passes on both files

**Gate command**:
```bash
zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py
cat Docs/Tests/spec07-wave2-qdrant.status   # must be PASSED
cat Docs/Tests/spec07-wave2-keymanager.status  # must be PASSED
```

### Wave 3 Gate (after A4 completes)

**Verification**:
1. ParentStore extended with convenience methods
2. `__init__.py` exports SQLiteDB, QdrantStorage
3. main.py lifespan initializes all storage components
4. All integration tests passing (with Qdrant running)
5. Parent retrieval <10ms for 100 chunks verified
6. Concurrent WAL reads verified

**Gate command**:
```bash
docker compose up qdrant -d
zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/
cat Docs/Tests/spec07-wave3.status  # must be PASSED
```

### Wave 4 Gate (after A5 completes -- final)

**Verification**:
1. All regression tests for FR-001 through FR-016 passing
2. All regression tests for SC-001 through SC-011 passing
3. Full test suite passing (unit + integration + regression)
4. `ruff check backend/storage backend/providers` passes
5. No regressions from prior specs (005, 006)

**Gate command**:
```bash
zsh scripts/run-tests-external.sh -n spec07-full tests/
cat Docs/Tests/spec07-full.status   # must be PASSED
cat Docs/Tests/spec07-full.summary  # review coverage
```

---

## Key Spec Compliance Notes

These are the most common errors found when comparing the old 07-implement.md against the authoritative spec. Agents MUST get these right:

1. **`confidence_score` is INTEGER (0-100)**, not REAL/float. The spec (FR-005, SC-010) is explicit. The data-model.md incorrectly says "FLOAT 0.0-1.0" -- the spec.md is authoritative.

2. **`query_traces` includes `reasoning_steps_json` and `strategy_switches_json`**. The old implement.md was missing these fields. FR-005 requires them.

3. **Environment variable is `EMBEDINATOR_FERNET_KEY`**, not `SECRET_KEY` or `api_key_encryption_secret`. Constitution Principle V mandates this exact name.

4. **Child chunks are ~500 chars** (Constitution Principle III), not ~300 chars. Some contracts say ~300 -- the Constitution is authoritative.

5. **Foreign keys include `ON DELETE CASCADE`** per data-model.md. The old implement.md was missing cascade behavior.

6. **`doc_type` values are "Prose" and "Code" only**. No "Table" or "Mixed" (established in spec-06).

7. **ParentStore uses SQL column aliases** (`id AS parent_id`, `collection_id AS collection`) so the `ParentChunk` Pydantic model in schemas.py is NOT modified. This pattern was established in spec-06.

8. **The class name is `QdrantStorage` (NEW class)**, NOT a rename of `QdrantClientWrapper`. Both coexist in `qdrant_client.py`. The existing `QdrantClientWrapper` remains for backward compatibility with specs 02-06.

---

## Done Criteria

- [ ] SQLiteDB class connects, creates all 7 tables with correct schema (including `reasoning_steps_json`, `strategy_switches_json` in query_traces, `confidence_score` as INTEGER)
- [ ] All CRUD methods for collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers implemented per contracts
- [ ] SQLite WAL mode enabled (PRAGMA journal_mode=WAL)
- [ ] SQLite foreign keys enforced (PRAGMA foreign_keys=ON) with ON DELETE CASCADE
- [ ] QdrantStorage creates collections with both dense (768d cosine) and sparse (BM25 IDF) vector configurations
- [ ] QdrantStorage batch_upsert stores points with complete 11-field payload (FR-011)
- [ ] QdrantStorage search_hybrid implements weighted rank fusion (default 0.6/0.4)
- [ ] All QdrantStorage methods have tenacity retry with exponential backoff
- [ ] KeyManager encrypts and decrypts API keys using Fernet (EMBEDINATOR_FERNET_KEY env var)
- [ ] KeyManager fails secure -- missing key raises ValueError on startup
- [ ] KeyManager never logs plaintext keys
- [ ] ParentStore.get_by_ids() returns with column aliases (id AS parent_id, collection_id AS collection)
- [ ] Indexes on parent_chunks(collection_id), parent_chunks(document_id), query_traces(session_id), query_traces(created_at)
- [ ] UNIQUE(collection_id, file_hash) constraint on documents table
- [ ] UUID5 deterministic IDs for parent chunks
- [ ] Storage initialized in app startup (lifespan)
- [ ] Unit tests pass for all CRUD operations, encryption, and Qdrant methods
- [ ] Integration tests pass for cross-store linking, concurrency, and performance targets
- [ ] Regression tests validate all 16 FRs and 11 SCs
- [ ] Full test suite passes with 0 regressions from prior specs
- [ ] `ruff check backend/storage backend/providers` passes
