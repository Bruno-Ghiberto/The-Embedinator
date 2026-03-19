# Agent A5: Quality Assurance, Regression & Polish

**Spec**: 007 (Storage Architecture) | **Wave**: 4 (sequential, final) | **subagent_type**: quality-engineer | **Model**: Sonnet 4.6

## Mission

Final quality pass: SOLID code review, security audit, documentation audit, comprehensive regression test suite covering all 16 FRs and 11 SCs, edge case validation, and full test suite execution. Ensure the storage layer is production-ready with zero regressions from prior specs.

## Assigned Tasks

T098-T163 and T164 from `specs/007-storage-architecture/tasks.md`:

- T098-T105: Code review (SOLID, security audit, SQL injection, HMAC, env var, error messages)
- T106-T107: Performance audit (parent <10ms, search <100ms)
- T108-T111: Code quality (ruff, PEP 8, type hints, docstrings, no print())
- T112-T119: Documentation audit (spec, data-model, contracts, quickstart, plan, CLAUDE.md)
- T120-T150: Regression tests (FR-001 to FR-016, SC-001 to SC-011, edge cases)
- T151-T156: Full test suite execution + coverage
- T157-T163: Commits and completion

## Critical Constraints

1. **Depends on Wave 3**: All A4 integration tests must pass before starting
2. **NEVER run pytest inside Claude Code**. Use: `zsh scripts/run-tests-external.sh -n spec07-full tests/`
3. **No new features** -- only polish, tests, documentation, and code review
4. **`confidence_score` is INTEGER (0-100)** -- verify this in regression tests
5. **`query_traces` includes `reasoning_steps_json` and `strategy_switches_json`** -- verify this
6. **`EMBEDINATOR_FERNET_KEY`** is the env var name -- verify KeyManager uses it
7. **Do NOT modify implementation files** unless fixing a confirmed bug (coordinate via SendMessage)
8. **Regression tests must cover ALL 16 FRs and ALL 11 SCs** -- no shortcuts

## Deliverables

### 1. Code Review Checklist

Review all implementation files against:

**SOLID Principles**:
- [ ] Single Responsibility: SQLiteDB (persistence), QdrantStorage (vectors), KeyManager (encryption)
- [ ] Open/Closed: Interfaces stable, implementations extendable
- [ ] Interface Segregation: Methods focused, no bloated interfaces
- [ ] Dependency Inversion: Dependencies on abstractions (aiosqlite, qdrant-client)

**Security**:
- [ ] No plaintext API keys in logs or cache (KeyManager, providers CRUD)
- [ ] SQL parameterization throughout (no string concatenation in queries)
- [ ] Fernet HMAC validates ciphertext integrity
- [ ] `EMBEDINATOR_FERNET_KEY` loaded from env, never hardcoded
- [ ] Error messages do not leak sensitive data

**Performance**:
- [ ] Parent retrieval < 10ms for 100 chunks (indexed)
- [ ] Batch operations used (no N+1 queries)
- [ ] WAL mode enables concurrent readers

**Code Quality**:
- [ ] `ruff check backend/storage backend/providers` passes
- [ ] Type hints on all public methods
- [ ] Docstrings on classes and public methods
- [ ] No `print()` statements (structlog only)
- [ ] Async/await consistent (no sync blocking)

### 2. tests/regression/test_regression.py

**FR Regression Tests** (one test per FR):

| Test | FR | Verifies |
|------|-----|----------|
| `test_fr_001_collections_table` | FR-001 | Collections table with all fields |
| `test_fr_002_documents_table` | FR-002 | Documents with UNIQUE(collection_id, file_hash) |
| `test_fr_003_ingestion_jobs_table` | FR-003 | IngestionJobs with status enum |
| `test_fr_004_parent_chunks_table` | FR-004 | ParentChunks with UUID5 deterministic id |
| `test_fr_005_query_traces_table` | FR-005 | QueryTraces with reasoning_steps_json, strategy_switches_json, confidence_score INTEGER |
| `test_fr_006_settings_table` | FR-006 | Settings key-value store |
| `test_fr_007_providers_table` | FR-007 | Providers with encrypted API keys |
| `test_fr_008_wal_mode` | FR-008 | PRAGMA journal_mode returns "wal" |
| `test_fr_009_foreign_keys` | FR-009 | PRAGMA foreign_keys returns 1 |
| `test_fr_010_qdrant_dense_sparse` | FR-010 | Dense 768d + sparse BM25 configs |
| `test_fr_011_qdrant_payload` | FR-011 | All 11 payload fields present |
| `test_fr_012_uuid5_determinism` | FR-012 | Same content produces same UUID5 |
| `test_fr_013_api_key_encryption` | FR-013 | Fernet encrypt/decrypt round-trip |
| `test_fr_014_parent_retrieval` | FR-014 | Batch retrieval with column aliases |
| `test_fr_015_sequential_ingestion` | FR-015 | Jobs status tracking supports sequential queue |
| `test_fr_016_idempotent_resume` | FR-016 | Failed jobs resumable via UUID5 |

**SC Regression Tests** (one test per SC):

| Test | SC | Verifies |
|------|-----|----------|
| `test_sc_001_all_tables_created` | SC-001 | 7 tables with correct columns |
| `test_sc_002_wal_fk_pragmas` | SC-002 | WAL mode + FKs enabled |
| `test_sc_003_uuid5_reproducible` | SC-003 | Same content -> same UUID5 |
| `test_sc_004_qdrant_vectors` | SC-004 | Dense + sparse configs |
| `test_sc_005_payload_fields` | SC-005 | All required payload fields |
| `test_sc_006_parent_latency` | SC-006 | <10ms for 100 chunks |
| `test_sc_007_duplicate_prevention` | SC-007 | Re-ingest marked duplicate |
| `test_sc_008_wal_concurrency` | SC-008 | Concurrent reads don't block |
| `test_sc_009_encrypted_keys` | SC-009 | No plaintext keys in DB/logs |
| `test_sc_010_traces_recorded` | SC-010 | All trace fields including reasoning_steps_json, strategy_switches_json, confidence_score 0-100 |
| `test_sc_011_cross_references` | SC-011 | parent_id links resolve correctly |

**Edge Case Tests**:

| Test | Scenario |
|------|----------|
| `test_empty_collection_search` | Returns empty result, not error |
| `test_file_same_hash_different_collections` | Same file_hash allowed in different collections |
| `test_qdrant_unavailable_mid_batch` | Entire batch fails on timeout |
| `test_failed_job_resumable` | Partial data persists, resumable without rollback |

### 3. Documentation Audit

Verify these files match the implementation:

- [ ] `specs/007-storage-architecture/spec.md` -- 4 user stories, 16 FRs, 11 SCs accurate
- [ ] `specs/007-storage-architecture/data-model.md` -- 7 entities match DB schema
- [ ] `specs/007-storage-architecture/contracts/sqlite-contract.md` -- method signatures match code
- [ ] `specs/007-storage-architecture/contracts/qdrant-contract.md` -- method signatures match code
- [ ] `specs/007-storage-architecture/contracts/key-manager-contract.md` -- method signatures match code
- [ ] `specs/007-storage-architecture/plan.md` -- tech context accurate
- [ ] Code docstrings on all public methods

If any discrepancy is found, note it but do NOT modify spec files. Document the discrepancy for the orchestrator.

### 4. Full Test Suite Execution

```bash
# Re-run all prior wave gates (regression baseline)
zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py
zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py
zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py

# Regression test suite
zsh scripts/run-tests-external.sh -n spec07-regression tests/regression/test_regression.py

# Full test suite (all tests)
zsh scripts/run-tests-external.sh -n spec07-full tests/

# Code quality
ruff check backend/storage backend/providers
```

### 5. Commits (after all tests pass)

Follow this commit sequence:
1. `git add tests/regression/ && git commit -m "test: add regression test suite for spec-07 storage architecture"`
2. `git add -A && git commit -m "docs: audit and update storage architecture documentation"`
3. Verify clean: `git status` shows "nothing to commit, working tree clean"

## Acceptance Criteria

- All 16 FR regression tests passing
- All 11 SC regression tests passing
- All edge case tests passing
- Code review checklist 100% complete
- Security audit passed (no plaintext, HMAC works, SQL parameterized)
- Performance targets verified (< 10ms parent retrieval)
- `ruff check backend/storage backend/providers` passes
- Full test suite passing with 0 regressions
- Documentation audit complete (discrepancies noted)

## Testing Protocol

```bash
# Full validation
docker compose up qdrant -d
zsh scripts/run-tests-external.sh -n spec07-full tests/
cat Docs/Tests/spec07-full.status      # must be PASSED
cat Docs/Tests/spec07-full.summary     # review coverage

ruff check backend/storage backend/providers
```

## Key References

- Spec: `specs/007-storage-architecture/spec.md` (all FRs and SCs)
- All Contracts: `specs/007-storage-architecture/contracts/`
- Data Model: `specs/007-storage-architecture/data-model.md`
- Plan: `specs/007-storage-architecture/plan.md`

## Execution Flow

1. Wait for A4 gate (all integration tests must pass)
2. Read this instruction file
3. Read spec.md to understand all 16 FRs and 11 SCs
4. Code review: check implementation against SOLID/security/performance checklist
5. Create `tests/regression/test_regression.py`
6. Run regression tests via external runner
7. Documentation audit (note discrepancies)
8. Run full test suite
9. Run `ruff check`
10. Commit regression tests and documentation fixes
11. Signal spec-07 completion

**Wave 4 Gate**: All tests + code review + documentation must pass. Spec 007 COMPLETE.
