# Spec 07: Storage Architecture -- Implementation Plan Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## ⚠️ CRITICAL MANDATORY: EXTERNAL TESTING ONLY

**NO pytest execution inside Claude Code. PERIOD.**

Every single agent (A1-A5) and the lead orchestrator MUST use:

```bash
zsh scripts/run-tests-external.sh -n <run-name> <test-target>
```

**This is non-negotiable.** Violations = implementation failure.

**Why**: External runner provides:
- Isolated venv with fingerprinted dependencies (sha256 of requirements*.txt)
- Atomic status files (`Docs/Tests/<name>.status` = RUNNING|PASSED|FAILED|ERROR)
- Token-efficient summary output (~20 lines, not megabytes of pytest output)
- Checkpoint gates can poll asynchronously without blocking Claude Code session

**If any agent or orchestrator violates this rule → STOP and escalate.**

---

## Authoritative References

Before spawning ANY agent, all participants must be able to reference:

| Document | Purpose | Location |
|----------|---------|----------|
| **Feature Spec** | Source of truth for requirements, 16 FRs, 11 SCs, 4 user stories | `specs/007-storage-architecture/spec.md` |
| **Data Model** | 7 entities, relationships, validation rules, UUID5 determinism | `specs/007-storage-architecture/data-model.md` |
| **Task List** | 163 tasks across 9 phases with dependencies | `specs/007-storage-architecture/tasks.md` |
| **SQLite Contract** | SQLiteDB interface: all methods, signatures, error handling | `specs/007-storage-architecture/contracts/sqlite-contract.md` |
| **Qdrant Contract** | QdrantStorage interface: collection, search, delete methods, payload schema | `specs/007-storage-architecture/contracts/qdrant-contract.md` |
| **KeyManager Contract** | KeyManager interface: encrypt/decrypt/is_valid_key | `specs/007-storage-architecture/contracts/key-manager-contract.md` |
| **A1 Instructions** | Wave 1 agent: SQLiteDB foundation + schema + tests | `Docs/PROMPTS/spec-07-storage/agents/A1-foundation-schema.md` |
| **A2 Instructions** | Wave 2 agent: QdrantStorage implementation + tests | `Docs/PROMPTS/spec-07-storage/agents/A2-qdrant-storage.md` |
| **A3 Instructions** | Wave 2 agent: KeyManager implementation + tests | `Docs/PROMPTS/spec-07-storage/agents/A3-key-manager.md` |
| **A4 Instructions** | Wave 3 agent: Integration wiring + startup + tests | `Docs/PROMPTS/spec-07-storage/agents/A4-integration-wiring.md` |
| **A5 Instructions** | Wave 4 agent: Full regression + quality + final validation | `Docs/PROMPTS/spec-07-storage/agents/A5-quality-polish.md` |

---

## Testing Protocol (MANDATORY)

**ALL agents and orchestrator MUST follow this exactly.**

### Background Mode (Agents Use This)

Agents spawn tests in background and poll status:

```bash
# Start test run (returns immediately, runs in background)
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py

# Poll status (1 line, returns immediately)
cat Docs/Tests/spec07-wave1.status

# When done (status = PASSED or FAILED), read summary
cat Docs/Tests/spec07-wave1.summary   # ~20 lines, token efficient
```

### Visible Mode (Orchestrator Uses at Checkpoints)

Lead orchestrator runs checkpoints in visible mode (human watches):

```bash
# Visible checkpoint run (shows progress in real-time)
zsh scripts/run-tests-external.sh --visible -n spec07-wave1 tests/unit/test_sqlite_db.py
```

### Status File Meanings

| Status | Meaning | Action |
|--------|---------|--------|
| RUNNING | Tests in progress | Wait, poll again in 10s |
| PASSED | All tests passed | Proceed to next wave |
| FAILED | Tests failed | Review Docs/Tests/<name>.summary, ask agent to debug |
| ERROR | Test infrastructure failed | Check scripts/run-tests-external.sh, debug environment |

### Summary File Format

```
Test Run: spec07-wave1
Target: tests/unit/test_sqlite_db.py
Duration: 45s
Result: PASSED (28 of 28 tests passed)

[Coverage report if --cov specified]

Next step: Checkpoint passed, proceed to Wave 2
```

**Never parse full log directly.** Always use status + summary files.

---

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

### Architecture

The **lead session** (you, the orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results, runs final regression |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list (from tasks.md) with dependency tracking -- teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Agent Team Composition

| Agent | Role | Model | Wave | Primary Tasks | Instruction File |
|-------|------|-------|------|-----------------|-----------------|
| A1 | Foundation + SQLite Schema | Sonnet 4.6 | 1 | T001-T010 (SQLiteDB class, schema, CRUD, unit tests) | A1-foundation-schema.md |
| A2 | Qdrant + Parent Store | Sonnet 4.6 | 2 | T011-T018 (QdrantStorage class, hybrid search, tests) | A2-qdrant-storage.md |
| A3 | Key Manager + Providers | Sonnet 4.6 | 2 | T019-T023 (KeyManager encrypt/decrypt, tests) | A3-key-manager.md |
| A4 | Integration + Startup Wiring | Sonnet 4.6 | 3 | T024-T032 (ParentStore, main.py init, integration tests) | A4-integration-wiring.md |
| A5 | Full Regression + Polish | Sonnet 4.6 | 4 | T033-T040 (Full tests, performance, schema validation, regression) | A5-quality-polish.md |

**Model Selection Rationale**:
- Sonnet 4.6 is sufficient for all agents (schema DDL, Qdrant integration, encryption, startup wiring, test writing)
- Escalate to Opus only if agent reports being stuck on complex logic reasoning (very unlikely for storage layer)
- Cost efficiency: Sonnet << Opus, and storage layer is mostly straightforward I/O code

---

## Wave Execution Order

```
Wave 1 (A1):        Foundation + SQLite Schema                   → CHECKPOINT GATE
Wave 2 (A2 + A3):   Qdrant Layer + Key Manager (parallel)        → CHECKPOINT GATE
Wave 3 (A4):        Integration + Startup Wiring                 → CHECKPOINT GATE
Wave 4 (A5):        Full Regression + Polish                     → FINAL VALIDATION
```

**Key constraint**: Each wave is a hard dependency. Wave N+1 CANNOT start until Wave N passes checkpoint.

---

## Implementation Strategy

### Clarifications from Spec Session

The spec clarifications session (2026-03-13) resolved 5 key architectural decisions that shape this plan:

1. **Data Scale (Medium Deployment)**: 1K-10K documents per collection, <1K chunks per document. SQLite WAL write serialization is acceptable for single-user local deployment.

2. **Concurrent Write Behavior (Sequential Queue)**: Jobs are queued in memory by the orchestrator (via ingestion pipeline in spec-06). System processes one document at a time. Failed jobs are logged but do not block subsequent jobs in the queue.

3. **Idempotent Resume Strategy**: UUID5 deterministic parent IDs enable safe re-runs. Duplicate Qdrant vectors are skipped (upsert replaces), duplicate SQLite parent chunks detected by UUID5 uniqueness. Failed jobs persist partial data; orchestrator can resume without explicit rollback.

4. **Qdrant Batch Failure (Fail Entire Batch)**: If Qdrant mid-batch upsert fails (e.g., 30 of 50 vectors uploaded then timeout), entire batch fails. UUID5 idempotent upserts make retry safe (duplicates skipped). Orchestrator retries full batch when Qdrant recovers.

5. **Query Trace Archival (Out of Scope)**: Traces stored indefinitely for observability. Users manage archival externally via SQL dumps/cron. Schema supports future retention policies without changes.

### Component Architecture

The storage layer provides dual-store persistence:

- **SQLite (Relational Metadata)**: Collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers. All relationships enforce referential integrity via foreign keys. WAL mode enables concurrent readers with single serialized writer.

- **Qdrant (Vector Search)**: Child chunk vectors with hybrid dense+sparse (BM25 IDF) support. Each point carries parent_id payload linking back to SQLite parent_chunks.id. Upserts are batched (batch_size=50) for throughput.

- **Parent-Child Linking**: Child chunks as searchable vectors in Qdrant (UUID4 IDs). Parent chunks as full context text in SQLite (UUID5 deterministic IDs). Breadcrumb metadata (page, section, source_file) in parent chunk JSON.

- **Encryption**: API keys stored encrypted in providers table via Fernet symmetric encryption. Decryption occurs only in memory during provider lookups.

---

## Step-by-Step Orchestration

### Setup: Create the Team

```
Create an agent team called "spec07-storage" to implement the Storage Architecture
feature for The Embedinator.

Reference the authoritative documents:
- Feature spec: specs/007-storage-architecture/spec.md
- Task list: specs/007-storage-architecture/tasks.md
```

All teammates will appear in their own tmux panes automatically.

### Wave 1: Foundation + SQLite Schema (Agent A1)

**Prerequisites**: None (Wave 1 has no dependencies)

**Agent**: A1-foundation-schema (Sonnet 4.6)

**Instruction**: Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A1-foundation-schema.md FIRST.

Then execute all assigned tasks from specs/007-storage-architecture/tasks.md [T001-T010].

You are implementing:
1. SQLiteDB class (async context manager)
2. PRAGMA setup (WAL mode, foreign key enforcement)
3. Full schema DDL for 7 tables: collections, documents, ingestion_jobs, parent_chunks, query_traces, settings, providers
4. CRUD methods for all tables (create, read, update, delete, batch operations)
5. Proper foreign key constraints and indexes per specs/007-storage-architecture/data-model.md
6. Comprehensive unit tests covering all public methods

CRITICAL CONSTRAINTS:
- Reference contracts/sqlite-contract.md for exact method signatures
- Use CREATE TABLE IF NOT EXISTS for schema idempotency
- Enforce UNIQUE(collection_id, file_hash) on documents table
- Create indexes on parent_chunks(collection_id, document_id) and query_traces(session_id, created_at)
- All foreign keys must reference correct tables with proper cascading

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py
- Poll status: cat Docs/Tests/spec07-wave1.status
- When PASSED, send message to lead: "Wave 1 complete, ready for checkpoint gate"
```

**Checkpoint Gate for Wave 1:**

```bash
# Lead orchestrator runs (visible mode, human watches):
zsh scripts/run-tests-external.sh --visible -n spec07-wave1 tests/unit/test_sqlite_db.py

# Poll status:
cat Docs/Tests/spec07-wave1.status
```

**PASS Criteria**:
- Status = PASSED
- Summary shows: "XX of XX tests passed"
- All test names in summary match pattern: `test_*` in test_sqlite_db.py

**FAIL Criteria**:
- Status = FAILED or ERROR
- Any test shows as FAILED in summary

**Action if PASS**: Proceed to Wave 2 (spawn A2 + A3 in parallel)

**Action if FAIL**:
```
DO NOT PROCEED.
Send message to A1: "Wave 1 checkpoint failed. Review Docs/Tests/spec07-wave1.summary
and Docs/Tests/spec07-wave1.log. Fix the failing tests and re-run:
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py"

When A1 reports "Wave 1 retry complete", re-run the checkpoint gate.
```

---

### Wave 2: Qdrant + Key Manager (Agents A2 & A3, Parallel)

**Prerequisites**: Wave 1 MUST pass checkpoint

**Agents**: A2-qdrant-storage and A3-key-manager (both Sonnet 4.6, run in parallel)

**Agent A2 (Qdrant Storage)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A2-qdrant-storage.md FIRST.

Then execute all assigned tasks from specs/007-storage-architecture/tasks.md [T011-T018].

You are implementing:
1. QdrantStorage class with async methods
2. create_collection() with dual vector config: dense (768d, cosine distance) + sparse (BM25 IDF)
3. batch_upsert() with 50-item batching and payload structure validation
4. hybrid_search() with configurable dense/sparse weights (default 0.6/0.4)
5. delete_by_source(), delete_collection(), scroll_points()
6. @retry decorators (tenacity) for transient failures
7. CircuitBreaker guards (from spec-05) for Qdrant health
8. Comprehensive unit tests with mocked Qdrant client

CRITICAL CONSTRAINTS:
- Reference contracts/qdrant-contract.md for exact method signatures
- Payload MUST include all 11 required fields: text, parent_id, breadcrumb, source_file, page, chunk_index, doc_type, chunk_hash, embedding_model, collection_name, ingested_at
- Hybrid search must perform weighted rank fusion of dense + sparse results
- All Qdrant errors → raise QdrantError with descriptive message
- No real Qdrant dependency in unit tests (use AsyncMock)

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
- Poll status: cat Docs/Tests/spec07-wave2-qdrant.status
- When PASSED, send message to lead: "A2 complete: Qdrant storage ready"
```

**Agent A3 (Key Manager)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A3-key-manager.md FIRST.

Then execute all assigned tasks from specs/007-storage-architecture/tasks.md [T019-T023].

You are implementing:
1. KeyManager class for Fernet symmetric encryption
2. __init__() loads EMBEDINATOR_SECRET_KEY env var, derives Fernet key
3. encrypt(plaintext: str) → ciphertext (base64-encoded Fernet token)
4. decrypt(ciphertext: str) → plaintext (raises InvalidToken on HMAC failure)
5. is_valid_key(ciphertext: str) → bool (fast validation without decryption)
6. Comprehensive unit tests validating encryption/decryption round-trips

CRITICAL CONSTRAINTS:
- Reference contracts/key-manager-contract.md for exact method signatures
- Use cryptography >=44.0 Fernet (AES-128-CBC + HMAC-SHA256)
- Plaintext NEVER logged, NEVER cached, NEVER written to disk
- HMAC verification detects tampering (raises InvalidToken)
- Fail-secure: ValueError if EMBEDINATOR_SECRET_KEY missing and no fallback
- All tests must use monkeypatch.setenv() for env var injection

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec07-wave2-keys tests/unit/test_key_manager.py
- Poll status: cat Docs/Tests/spec07-wave2-keys.status
- When PASSED, send message to lead: "A3 complete: KeyManager encryption ready"
```

**Checkpoint Gate for Wave 2:**

```bash
# Lead orchestrator waits for both A2 and A3 messages ("complete")
# Then runs (visible mode):
zsh scripts/run-tests-external.sh --visible -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
zsh scripts/run-tests-external.sh --visible -n spec07-wave2-keys tests/unit/test_key_manager.py

# Poll statuses:
cat Docs/Tests/spec07-wave2-qdrant.status
cat Docs/Tests/spec07-wave2-keys.status
```

**PASS Criteria**:
- Both statuses = PASSED
- Summaries show all tests passed

**FAIL Criteria**:
- Either status = FAILED or ERROR

**Action if PASS**: Proceed to Wave 3 (spawn A4)

**Action if FAIL**:
```
DO NOT PROCEED.
Identify which agent failed (A2 or A3).
Send message: "Wave 2 checkpoint failed (Agent: A2|A3).
Review Docs/Tests/spec07-wave2-{qdrant|keys}.summary.
Fix and re-run: zsh scripts/run-tests-external.sh -n spec07-wave2-{qdrant|keys} tests/unit/test_*.py"

When agent reports "Wave 2 retry complete", re-run the checkpoint gate.
```

---

### Wave 3: Integration + Startup Wiring (Agent A4)

**Prerequisites**: Wave 2 MUST pass checkpoint

**Agent**: A4-integration-wiring (Sonnet 4.6)

**Instruction**: Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A4-integration-wiring.md FIRST.

Then execute all assigned tasks from specs/007-storage-architecture/tasks.md [T024-T032].

You are implementing:
1. ParentStore class (convenience wrapper over SQLiteDB for parent chunk operations)
2. get_parent_by_id(parent_id) → full text + metadata from SQLiteDB
3. get_parents_by_ids(parent_ids: list[str]) → batch retrieval with performance <10ms for 100 chunks
4. insert_parents() batch insert in transaction with duplicate detection
5. Startup initialization in backend/main.py:
   - Create SQLiteDB instance and verify schema
   - Create QdrantStorage instance and verify Qdrant connectivity
   - Wire KeyManager to provider registry
   - Store all instances in app state for request handlers
6. Integration tests validating:
   - Parent-child linking (create parent in SQLite, verify child in Qdrant with parent_id payload)
   - Qdrant-SQLite cross-references (every parent_id in Qdrant resolves to parent_chunks row)
   - Performance targets (batch parent retrieval <10ms, search <100ms)
7. Error handling tests (Qdrant unavailable, SQLite locked, missing encryption key)

CRITICAL CONSTRAINTS:
- Reference contracts/sqlite-contract.md and contracts/qdrant-contract.md for interface details
- Use real Qdrant and SQLite in integration tests (not mocks)
- Test with unique collection names to avoid 409 conflicts
- Verify all parent_id payloads in Qdrant match rows in parent_chunks table
- Performance: measure latency, log if exceeds targets
- Clean up test data after each integration test

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/test_storage_integration.py
- Additional tests: zsh scripts/run-tests-external.sh -n spec07-concurrent tests/integration/test_concurrent_reads.py
- Poll status: cat Docs/Tests/spec07-wave3.status
- When PASSED, send message to lead: "Wave 3 complete, integration tests pass"
```

**Checkpoint Gate for Wave 3:**

```bash
# Lead orchestrator waits for A4 message ("complete")
# Then runs (visible mode):
zsh scripts/run-tests-external.sh --visible -n spec07-wave3 tests/integration/test_storage_integration.py

# Poll status:
cat Docs/Tests/spec07-wave3.status
```

**PASS Criteria**:
- Status = PASSED
- Summary shows all parent-child linking tests pass
- Performance tests show latencies under targets

**FAIL Criteria**:
- Status = FAILED or ERROR
- Cross-reference validation failures
- Performance targets exceeded

**Action if PASS**: Proceed to Wave 4 (spawn A5)

**Action if FAIL**:
```
DO NOT PROCEED.
Send message to A4: "Wave 3 checkpoint failed.
Review Docs/Tests/spec07-wave3.summary and Docs/Tests/spec07-wave3.log.
Debug the integration test failures and re-run:
zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/test_storage_integration.py"

When A4 reports "Wave 3 retry complete", re-run the checkpoint gate.
```

---

### Wave 4: Full Regression + Polish (Agent A5)

**Prerequisites**: Wave 3 MUST pass checkpoint

**Agent**: A5-quality-polish (Sonnet 4.6)

**Instruction**: Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-07-storage/agents/A5-quality-polish.md FIRST.

Then execute all assigned tasks from specs/007-storage-architecture/tasks.md [T033-T040].

You are implementing:
1. COMPREHENSIVE regression test suite (30+ tests):
   - Specification compliance: Validate all 16 FRs (FR-001 to FR-016)
   - Success criteria validation: Verify all 11 SCs (SC-001 to SC-011)
   - Known issue prevention: Tests for duplicate detection, cascade deletes, idempotent retries
2. Performance validation:
   - Parent retrieval latency <10ms for 100 chunks
   - Hybrid search latency <100ms for large collections
3. Schema validation:
   - All 7 tables exist with correct columns and types
   - WAL mode enabled, foreign keys enforced
   - All indexes present and working
4. Duplicate prevention:
   - Re-ingest file with same file_hash → marked duplicate, no duplicate vectors
5. Concurrent read validation:
   - WAL mode allows 5+ parallel readers without blocking
6. Error handling validation:
   - Qdrant unavailable → batch fails entirely (fail-safe)
   - SQLite locked → retry with backoff
   - Missing encryption key → startup fails (fail-secure)
7. Code review (SOLID, security, performance, maintainability)
8. Documentation audit (ensure spec.md, contracts match implementation)
9. CLAUDE.md update with storage layer summary
10. Final commit and cleanup

CRITICAL CONSTRAINTS:
- Reference specs/007-storage-architecture/spec.md for all FR/SC requirements
- Use external test runner for ALL tests: scripts/run-tests-external.sh
- No mocking in regression tests (use real Qdrant + SQLite)
- Test cleanup: Remove all test collections/documents after each test
- Performance: Log if any test exceeds targets, report in summary
- Code quality: Run ruff check, type hints on public methods, docstrings complete

TESTING:
- Run all tests with: zsh scripts/run-tests-external.sh -n spec07-regression tests/regression/test_regression.py
- Full suite with: zsh scripts/run-tests-external.sh -n spec07-full tests/
- Poll status: cat Docs/Tests/spec07-regression.status
- When PASSED, send message to lead: "Wave 4 complete, all regression tests pass, storage layer ready"
```

**Final Checkpoint (Lead Orchestrator):**

```bash
# Wait for A5 message ("complete")
# Then run final checkpoint (visible mode):
zsh scripts/run-tests-external.sh --visible -n spec07-full tests/

# Poll status:
cat Docs/Tests/spec07-full.status

# Read summary:
cat Docs/Tests/spec07-full.summary
```

**PASS Criteria**:
- Status = PASSED
- Summary shows: "STORAGE ARCHITECTURE IMPLEMENTATION COMPLETE"
- All regression tests pass
- No open issues in code review or documentation

**FAIL Criteria**:
- Status = FAILED or ERROR
- Any regression test fails
- Code review finds violations

**Action if PASS**:
```
✅ IMPLEMENTATION COMPLETE

All 4 waves have passed their checkpoints.
Storage architecture is production-ready.

Next steps:
1. Merge branch into main
2. Proceed to Spec 08 (REST API) which depends on this storage layer
```

**Action if FAIL**:
```
DO NOT MERGE.
Send message to A5: "Final checkpoint failed.
Review Docs/Tests/spec07-full.summary and Docs/Tests/spec07-full.log.
Fix remaining issues and re-run:
zsh scripts/run-tests-external.sh -n spec07-full tests/"

When A5 reports "Final retry complete", re-run the final checkpoint.
```

---

## Key Implementation Patterns

### SQLiteDB Async Context Manager

```python
class SQLiteDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def __aenter__(self):
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._init_schema()
        return self

    async def _init_schema(self):
        # Execute full CREATE TABLE IF NOT EXISTS DDL
        # Idempotent: safe to run on every startup
        ...
```

### Hybrid Search with Qdrant Dense + Sparse

```python
class QdrantStorage:
    async def hybrid_search(
        self,
        collection_name: str,
        dense_vector: list[float],
        sparse_vector: dict,  # {indices: [...], values: [...]}
        top_k: int = 20,
        dense_weight: float = 0.7,
        sparse_weight: float = 0.3,
    ) -> list[dict]:
        # Execute hybrid search with both dense and sparse vectors
        # Return ranked results with parent_id payload for SQLite lookup
        ...
```

### Fernet Encryption for API Keys

```python
class KeyManager:
    def __init__(self, secret: str):
        if not secret:
            secret = Fernet.generate_key().decode()
        self.fernet = Fernet(secret.encode() if isinstance(secret, str) else secret)

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

---

## File Structure

```
backend/
  storage/
    sqlite_db.py          # SQLiteDB: async context, schema init, all table CRUD
    qdrant_client.py      # QdrantStorage: collection creation, batch_upsert, hybrid search
    parent_store.py       # ParentStore: parent chunk convenience layer
  providers/
    key_manager.py        # KeyManager: Fernet encryption/decryption for API keys
  main.py                 # Updated: storage layer initialization in lifespan

data/
  embedinator.db          # SQLite database (gitignored, created at runtime)
  qdrant_db/              # Qdrant persistence (gitignored)

specs/007-storage-architecture/
  spec.md                 # Feature specification (4 user stories, 16 FRs, 11 SCs)
  data-model.md           # 7 entities, relationships, validation rules
  plan.md                 # This file (orchestration + implementation strategy)
  tasks.md                # 163 tasks across 9 phases with dependencies
  contracts/
    sqlite-contract.md    # SQLiteDB interface contract
    qdrant-contract.md    # QdrantStorage interface contract
    key-manager-contract.md  # KeyManager interface contract

tests/
  unit/
    test_sqlite_db.py              # SQLiteDB CRUD, schema, constraints, indexes
    test_qdrant_storage.py         # QdrantStorage collection, search, delete (mocked)
    test_key_manager.py            # KeyManager encrypt/decrypt
  integration/
    test_storage_integration.py    # Parent-child linking, Qdrant-SQLite cross-ref (real services)
    test_concurrent_reads.py       # WAL mode concurrent reader validation
    test_schema_validation.py      # Foreign keys, indexes, constraints, WAL
  regression/
    test_regression.py             # 30+ tests validating all FRs/SCs

Docs/PROMPTS/spec-07-storage/agents/
  A1-foundation-schema.md    # Wave 1 agent instruction
  A2-qdrant-storage.md       # Wave 2 agent A2 instruction
  A3-key-manager.md          # Wave 2 agent A3 instruction
  A4-integration-wiring.md   # Wave 3 agent instruction
  A5-quality-polish.md       # Wave 4 agent instruction
```

---

## Integration Points

- **Ingestion Pipeline** (spec-06): Writes to documents, ingestion_jobs, parent_chunks tables via SQLiteDB. Upserts child vectors to Qdrant via QdrantStorage.batch_upsert().
- **API** (spec-08): All endpoints use SQLiteDB for collection/document CRUD, QdrantStorage for search in chat endpoint.
- **Agent Graphs** (specs 02-04): ResearchGraph queries Qdrant via QdrantStorage.hybrid_search(), resolves parent text via ParentStore.get_parents_by_ids().
- **Retrieval** (spec-11): Searcher and reranker use QdrantStorage for hybrid search with circuit breaker protection.
- **Accuracy** (spec-05): Circuit breaker and retry wrap all QdrantStorage methods.
- **Providers** (spec-10): Provider registry reads/writes providers table via SQLiteDB, uses KeyManager for encryption/decryption.
- **Observability** (spec-15): Query traces written to query_traces table via SQLiteDB after every chat request.

---

## Dependencies

**Internal specs**:
- Spec 02 (ConversationGraph): Uses separate checkpoints.db via LangGraph checkpointer (independent from embedinator.db).
- Spec 03 (ResearchGraph): Requires parent chunk retrieval and breadcrumb metadata from storage layer.
- Spec 04 (MetaReasoningGraph): Requires confidence_score and strategy tracking in query traces.
- Spec 05 (Accuracy/Robustness): Requires circuit breaker support (applied to QdrantStorage methods).
- Spec 06 (Ingestion Pipeline): Writes to documents, ingestion_jobs, parent_chunks, and Qdrant collections.

**External libraries**:
- `qdrant-client >=1.17.0`: Vector database client with sparse vector support (BM25).
- `aiosqlite >=0.21`: Async SQLite access.
- `cryptography >=44.0`: Fernet encryption for API keys.
- `tenacity >=9.0`: @retry decorators for QdrantStorage methods.

**Infrastructure**:
- Qdrant Docker container (existing).
- SQLite 3.45+ with WAL mode support.

---

## Success Validation

After all 4 waves pass their checkpoints, lead orchestrator performs final validation:

1. ✅ All 7 SQLite tables exist with correct columns, types, constraints, foreign keys, indexes.
2. ✅ SQLite WAL mode enabled, foreign key enforcement active (PRAGMA queries in startup).
3. ✅ Parent chunk UUID5 IDs are deterministic and reproducible.
4. ✅ Qdrant collections have both dense and sparse vector configurations.
5. ✅ Child chunks in Qdrant carry all required payload fields (11 total).
6. ✅ Parent chunk retrieval from SQLite by ID list completes in under 10ms for 100-chunk lists.
7. ✅ Document re-ingestion with same file_hash is marked as duplicate (not re-processed).
8. ✅ Concurrent reads to SQLite proceed without blocking (WAL mode tested with 5+ readers).
9. ✅ API keys are encrypted in providers table, decrypted only in memory.
10. ✅ Query traces are recorded for every chat query with all required fields.
11. ✅ Qdrant-SQLite cross-references are consistent (every parent_id in Qdrant resolves to parent_chunks row).

All validation performed via external test runner with results in Docs/Tests/spec07-full.{status,summary,log}.

---

## Important Reminders

- **EXTERNAL TESTING ONLY**: No pytest inside Claude Code. Ever. Use scripts/run-tests-external.sh.
- **Wave Gates Are Hard Stops**: Don't skip waves or proceed if checkpoint fails.
- **Agent Instructions Are Authoritative**: Each agent's instruction file is the detailed source of truth for their wave.
- **Real Services in Integration**: Use real Qdrant + SQLite in integration tests (no mocks), with unique names to avoid conflicts.
- **Idempotency via UUID5**: Parent chunk IDs are UUID5(namespace, content), making retries safe (duplicates skipped).
- **Parallel Wave 2**: A2 + A3 run in parallel tmux panes. Wave 1 and Wave 3 must complete before their successor waves.
- **Checkpoint Polling**: Use `cat Docs/Tests/<name>.status` to poll, `cat Docs/Tests/<name>.summary` to read results.
