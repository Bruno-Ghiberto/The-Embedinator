# Tasks: Storage Architecture

**Input**: Design documents from `/specs/007-storage-architecture/`
**Prerequisites**: spec.md (4 user stories), plan.md (tech stack), data-model.md (7 entities), contracts/ (3 interfaces), research.md (confirmed decisions)

**Organization**: Tasks organized by implementation wave (1–4) mapping to user stories for independent development and testing.

**Agent Teams**: 5-wave orchestration (A1 sequential → A2+A3 parallel → A4 sequential → A5 sequential) with external test runner (`scripts/run-tests-external.sh`)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., [US1], [US2], [US3], [US4])
- Exact file paths included in every task description
- All tests use external runner: `zsh scripts/run-tests-external.sh -n <test-name> <test-file>`

---

## Phase 1: Setup & Project Initialization

**Purpose**: Initialize project structure and dependencies per plan.md

- [x] T001 Create backend/storage/ directory structure with __init__.py, sqlite_db.py, qdrant_client.py, parent_store.py
- [x] T002 Create backend/providers/ directory structure with __init__.py, key_manager.py
- [x] T003 Create tests/unit/ directory with __init__.py, test files for sqlite_db, qdrant_storage, key_manager, parent_store
- [x] T004 Create tests/integration/ directory with __init__.py, test files for storage_integration, concurrent_reads, schema_validation
- [x] T005 Create data/ directory (embedinator.db and qdrant_db/ will be created at runtime)
- [x] T006 Verify requirements.txt includes: aiosqlite >=0.21, qdrant-client >=1.17.0, cryptography >=44.0, tenacity >=9.0, structlog >=24.0

**Checkpoint**: Project structure initialized and ready for Wave 1

---

## Phase 2: Foundational - Wave 1 (A1: SQLiteDB Foundation & Schema)

**Purpose**: Implement SQLiteDB class and all 7 database tables (blocking prerequisite for all user stories)

**Wave Gate**: All Wave 1 tests MUST PASS via external runner before Wave 2 begins

### SQLiteDB Implementation: backend/storage/sqlite_db.py

- [x] T007 Implement SQLiteDB.__init__() async context manager with aiosqlite connection to embedinator.db in data/
- [x] T008 Implement SQLiteDB.init_schema() to create all 7 tables with PRAGMA journal_mode=WAL and foreign_keys=ON
- [x] T009 Implement Collections CRUD: create_collection(), get_collection(), get_collection_by_name(), list_collections(), update_collection(), delete_collection() in backend/storage/sqlite_db.py
- [x] T010 Implement Documents CRUD: create_document(), get_document(), get_document_by_hash(), list_documents(), update_document(), delete_document() in backend/storage/sqlite_db.py (includes UNIQUE(collection_id, file_hash) constraint)
- [x] T011 [FR-016] Implement IngestionJobs CRUD: create_ingestion_job(), get_ingestion_job(), list_ingestion_jobs(), update_ingestion_job() in backend/storage/sqlite_db.py (supports status updates for job tracking; status persistence enables idempotent resume per FR-016)
- [x] T012 Implement ParentChunks CRUD: create_parent_chunk(), get_parent_chunk(), get_parent_chunks_batch(), list_parent_chunks(), delete_parent_chunks() in backend/storage/sqlite_db.py (UUID5 deterministic IDs, indexes on collection_id+document_id)
- [x] T013 Implement QueryTraces CRUD: create_query_trace(), list_query_traces(), get_query_traces_by_timerange() in backend/storage/sqlite_db.py (append-only, index on session_id+created_at)
- [x] T014 Implement Settings CRUD: get_setting(), set_setting(), list_settings(), delete_setting() in backend/storage/sqlite_db.py (key-value store)
- [x] T015 Implement Providers CRUD: create_provider(), get_provider(), list_providers(), update_provider(), delete_provider() in backend/storage/sqlite_db.py (api_key_encrypted Fernet field)
- [x] T016 Add comprehensive error handling (IntegrityError, OperationalError) with informative messages in all CRUD methods in backend/storage/sqlite_db.py

### SQLiteDB Unit Tests: tests/unit/test_sqlite_db.py

- [x] T017 Write schema validation tests: test_init_schema_creates_all_tables, test_wal_mode_enabled, test_foreign_keys_enabled, test_schema_idempotent in tests/unit/test_sqlite_db.py
- [x] T018 Write Collections CRUD tests (create, get, list, unique constraint) in tests/unit/test_sqlite_db.py
- [x] T019 Write Documents CRUD tests (create, get_by_hash, list, UNIQUE(collection_id, file_hash) constraint) in tests/unit/test_sqlite_db.py
- [x] T020 Write IngestionJobs CRUD tests (create, update status, list by document) in tests/unit/test_sqlite_db.py
- [x] T021 Write ParentChunks CRUD tests (UUID5 determinism, batch retrieval <10ms latency) in tests/unit/test_sqlite_db.py
- [x] T022 Write QueryTraces CRUD tests (append-only, session filtering, JSON field validation) in tests/unit/test_sqlite_db.py
- [x] T023 Write Settings CRUD tests (upsert behavior, persistence across close/reopen) in tests/unit/test_sqlite_db.py
- [x] T024 Write Providers CRUD tests (encryption optional for Ollama, null api_key allowed) in tests/unit/test_sqlite_db.py
- [x] T025 Write constraint validation tests (FK violations, UNIQUE violations, CHECK constraints) in tests/unit/test_sqlite_db.py
- [x] T026 Write performance test: test_batch_retrieval_latency for get_parent_chunks_batch(100) < 10ms in tests/unit/test_sqlite_db.py
- [x] T027 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py` and verify all tests PASS

**Checkpoint**: SQLiteDB fully implemented and tested. Wave 1 gate complete. Proceed to Wave 2.

---

## Phase 3: Parallel Components - Wave 2 (A2 + A3: QdrantStorage & KeyManager)

**Purpose**: Implement QdrantStorage and KeyManager independently in parallel

**Wave Gate**: Both A2 and A3 tests MUST PASS via external runner before Wave 3 begins

### A2: QdrantStorage Implementation: backend/storage/qdrant_client.py

- [x] T028 [P] Implement QdrantStorage.__init__() with async Qdrant client (host, port configuration) in backend/storage/qdrant_client.py
- [x] T029 [P] Implement QdrantStorage.health_check() returning True/False for circuit breaker integration in backend/storage/qdrant_client.py
- [x] T030 [P] Implement QdrantStorage.create_collection() with dual vector config (768d dense cosine + BM25 sparse) in backend/storage/qdrant_client.py
- [x] T031 [P] Implement QdrantStorage.collection_exists(), delete_collection(), get_collection_info() in backend/storage/qdrant_client.py
- [x] T032 [P] Implement QdrantStorage.batch_upsert() with QdrantPoint class (id, vector, sparse_vector, payload) and idempotent semantics in backend/storage/qdrant_client.py (the `id` field MUST be a deterministic UUID5 keyed on `doc_id:chunk_index` per Constitution III; enforcement is the caller's responsibility)
- [x] T033 [P] Implement QdrantStorage.search_hybrid() with weighted rank fusion (dense_weight=0.6, sparse_weight=0.4) and score threshold filtering in backend/storage/qdrant_client.py
- [x] T034 [P] Implement QdrantStorage.delete_points() and delete_points_by_filter() for point deletion in backend/storage/qdrant_client.py
- [x] T035 [P] Implement QdrantStorage.get_point(), get_points_by_ids(), scroll_points() for point retrieval and pagination in backend/storage/qdrant_client.py
- [x] T036 [P] Validate payload structure (11 required fields: text, parent_id, breadcrumb, source_file, page, chunk_index, doc_type, chunk_hash, embedding_model, collection_name, ingested_at) in backend/storage/qdrant_client.py
- [x] T037 [P] Add error handling for QdrantError (connection, timeout, dimension mismatch) with tenacity retry logic in backend/storage/qdrant_client.py

### A2: QdrantStorage Unit Tests: tests/unit/test_qdrant_storage.py

- [x] T038 [P] Write collection management tests (create_collection, collection_exists, get_info, delete) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T039 [P] Write batch upsert tests (idempotent semantics, payload validation, sparse vectors) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T040 [P] Write hybrid search tests (dense-only, sparse-only, balanced weights, top-k limiting, score threshold) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T041 [P] Write point deletion tests (delete by ID, delete by filter) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T042 [P] Write point retrieval tests (get_point, get_points_by_ids, scroll_points) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T043 [P] Write payload validation tests (required fields present, parent_id format, doc_type enum) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T044 [P] Write error handling tests (connection error, timeout, dimension mismatch, invalid format) with mocked Qdrant in tests/unit/test_qdrant_storage.py
- [x] T045 [P] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py` and verify all tests PASS

### A3: KeyManager Implementation: backend/providers/key_manager.py

- [x] T046 [P] Implement KeyManager.__init__() loading EMBEDINATOR_FERNET_KEY from environment (base64-encoded 32-byte secret) in backend/providers/key_manager.py
- [x] T047 [P] Implement KeyManager.encrypt() using Fernet AES-128-CBC + HMAC-SHA256 (deterministic, returns base64 ciphertext) in backend/providers/key_manager.py
- [x] T048 [P] Implement KeyManager.decrypt() using Fernet (plaintext only in-memory, raises InvalidToken on tampering) in backend/providers/key_manager.py
- [x] T049 [P] Implement KeyManager.is_valid_key() for quick ciphertext validation without decryption in backend/providers/key_manager.py
- [x] T050 [P] Add error handling: ValueError on missing env var, ValueError on invalid format, InvalidToken on HMAC failure in backend/providers/key_manager.py
- [x] T051 [P] Add security validations: plaintext never logged, no caching of decrypted keys, fail-secure on missing key in backend/providers/key_manager.py

### A3: KeyManager Unit Tests: tests/unit/test_key_manager.py

- [x] T052 [P] Write initialization tests (with env var, missing env var, dev fallback) in tests/unit/test_key_manager.py
- [x] T053 [P] Write encryption tests (plaintext → ciphertext, deterministic output, different plaintexts → different ciphertexts, empty strings, long keys) in tests/unit/test_key_manager.py
- [x] T054 [P] Write decryption tests (round-trip plaintext → encrypt → decrypt, invalid format raises ValueError, tampered ciphertext raises InvalidToken, wrong key raises InvalidToken) in tests/unit/test_key_manager.py
- [x] T055 [P] Write key validation tests (valid key returns True, invalid/corrupted key returns False, fast validation) in tests/unit/test_key_manager.py
- [x] T056 [P] Write security tests (plaintext not logged, no key caching, no intermediate plaintext storage, HMAC tampering detected, env var isolation) in tests/unit/test_key_manager.py
- [x] T057 [P] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py` and verify all tests PASS

**Checkpoint**: QdrantStorage and KeyManager fully implemented and tested in parallel. Wave 2 gate complete. Proceed to Wave 3.

---

## Phase 4: User Story 1 - Ingestion Pipeline Stores Documents and Chunks (Priority: P1)

**Goal**: Implement document storage, parent chunk creation, and Qdrant vector upload with deterministic UUIDs and idempotent failure recovery

**Independent Test**: Upload a document to a collection, verify documents table has correct record, verify parent_chunks table has parent text with UUID5 ID, verify Qdrant has child vectors with parent_id payload

### ParentStore Wrapper: backend/storage/parent_store.py

- [x] T058 [US1] Implement ParentStore.__init__() wrapping SQLiteDB for convenience parent chunk operations in backend/storage/parent_store.py
- [x] T059 [US1] Implement ParentStore.get_by_ids() for batch retrieval of parent chunks (column aliases: id AS parent_id, collection_id AS collection) in backend/storage/parent_store.py
- [x] T060 [US1] Implement ParentStore.get_all_by_collection() for retrieving all parents in a collection in backend/storage/parent_store.py
- [x] T061 [US1] Add error handling for ParentStore operations in backend/storage/parent_store.py
- [x] T164 [US1] Write ParentStore unit tests: test_get_by_ids_returns_aliases, test_get_all_by_collection, test_get_by_ids_empty_list, test_get_by_ids_missing_ids, test_error_handling in tests/unit/test_parent_store.py

### Wave 3 Integration: Connect Components

- [x] T062 [US1] Implement backend/storage/__init__.py exporting public API: SQLiteDB, QdrantStorage, ParentStore, KeyManager in backend/storage/__init__.py
- [x] T063 [US1] Update backend/main.py to initialize SQLiteDB and QdrantStorage in lifespan (async context managers) in backend/main.py
- [x] T064 [US1] Create integration test: test_parent_chunk_to_qdrant_linking() verifying parent_id payload links Qdrant → SQLite in tests/integration/test_storage_integration.py
- [x] T065 [US1] Create integration test: test_duplicate_document_detection() for re-ingestion with same file_hash in tests/integration/test_storage_integration.py
- [x] T066 [US1] Create integration test: test_batch_parent_retrieval_performance() verifying <10ms for 100 chunks in tests/integration/test_storage_integration.py
- [x] T067 [US1] Create concurrent reads test: test_concurrent_reads_no_blocking() spawning async readers on SQLite in tests/integration/test_concurrent_reads.py
- [x] T068 [US1] Create schema validation test: test_all_tables_exist() verifying 7 tables present in tests/integration/test_schema_validation.py
- [x] T069 [US1] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave3 tests/integration/test_storage_integration.py` and verify parent-child linking passes
- [x] T070 [US1] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-concurrent tests/integration/test_concurrent_reads.py` and verify no blocking
- [x] T071 [US1] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-schema tests/integration/test_schema_validation.py` and verify schema correctness

**Checkpoint**: User Story 1 (Ingestion) fully implemented and integration tested. Parent-child linking validated.

---

## Phase 5: User Story 2 - Chat/Search Retrieves Parent Chunks and Metadata (Priority: P1)

**Goal**: Implement efficient parent chunk retrieval from SQLite and integration with Qdrant search results

**Independent Test**: Query with known content, verify Qdrant returns parent_ids in payloads, verify parent_store returns full parent text <10ms

### Integration: Search → Retrieval Workflow

- [x] T072 [US2] Create integration test: test_search_returns_parent_id() verifying Qdrant search includes parent_id payload in tests/integration/test_storage_integration.py
- [x] T073 [US2] Create integration test: test_search_parent_retrieval_workflow() combining search and parent lookup in tests/integration/test_storage_integration.py
- [x] T074 [US2] Create integration test: test_collection_isolation() verifying documents/vectors isolated by collection_id in tests/integration/test_storage_integration.py
- [x] T075 [US2] Create integration test: test_parent_id_mismatch_detection() handling orphaned Qdrant vectors in tests/integration/test_storage_integration.py
- [x] T076 [US2] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-search-integration tests/integration/test_storage_integration.py` and verify search-to-retrieval workflow passes

**Checkpoint**: User Story 2 (Retrieval) fully implemented. Search → parent retrieval workflow validated.

---

## Phase 6: User Story 3 - Query Observability Traces All Searches (Priority: P2)

**Goal**: Record query traces with full context for observability and debugging

**Independent Test**: Execute query, verify query_traces table has new record with all fields, verify timestamps accurate

### Query Trace Recording

- [x] T077 [US3] Create integration test: test_create_query_trace_full_flow() recording trace with collections_searched, chunks_retrieved_json, confidence_score in tests/integration/test_storage_integration.py
- [x] T078 [US3] Create integration test: test_query_trace_latency_accuracy() measuring time and recording in trace_latency_ms in tests/integration/test_storage_integration.py
- [x] T079 [US3] Create integration test: test_trace_json_field_validation() verifying JSON fields valid and parseable in tests/integration/test_storage_integration.py
- [x] T080 [US3] Create integration test: test_list_traces_by_session() filtering and ordering traces correctly in tests/integration/test_storage_integration.py
- [x] T081 [US3] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-traces tests/integration/test_storage_integration.py` and verify trace recording passes

**Checkpoint**: User Story 3 (Query Traces) fully implemented. Trace recording validated.

---

## Phase 7: User Story 4 - Multi-Provider LLM Support with Encrypted Keys (Priority: P2)

**Goal**: Implement encrypted API key storage and secure provider configuration

**Independent Test**: Store API key via settings, verify it's encrypted in providers table, verify backend can decrypt and use key

### Provider & KeyManager Integration

- [x] T082 [US4] Create integration test: test_create_provider_with_encrypted_key() storing and retrieving encrypted keys in tests/integration/test_storage_integration.py
- [x] T083 [US4] Create integration test: test_provider_update_changes_key() re-encrypting on update in tests/integration/test_storage_integration.py
- [x] T084 [US4] Create integration test: test_provider_key_isolation() verifying independent decryption of multiple providers in tests/integration/test_storage_integration.py
- [x] T085 [US4] Create integration test: test_plaintext_never_logged() mocking logger to verify no plaintext keys in logs in tests/integration/test_storage_integration.py
- [x] T086 [US4] Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-providers tests/integration/test_storage_integration.py` and verify provider encryption passes

**Checkpoint**: User Story 4 (Provider Management) fully implemented. Encrypted key storage validated.

---

## Phase 8: Integration & Error Recovery (Wave 3: A4)

**Purpose**: Validate cross-store consistency, concurrency, error handling, and idempotent recovery

**Wave Gate**: All integration tests MUST PASS via external runner before Wave 4 begins

### Integration & Cross-Store Validation

- [x] T087 Create integration test: test_document_delete_cascades() verifying FK cascades work in tests/integration/test_storage_integration.py
- [x] T088 Create integration test: test_qdrant_unavailable_batch_fails() simulating Qdrant timeout during batch_upsert in tests/integration/test_storage_integration.py
- [x] T089 Create integration test: test_idempotent_retry_on_failure() retrying batch and verifying no duplicates via UUID5 in tests/integration/test_storage_integration.py
- [x] T090 Create integration test: test_document_status_transitions() tracking pending → ingesting → completed/failed states in tests/integration/test_storage_integration.py
- [x] T091 Create constraint validation test: test_foreign_key_constraints_enforced() in tests/integration/test_schema_validation.py
- [x] T092 Create constraint validation test: test_unique_constraints_enforced() for collections and documents in tests/integration/test_schema_validation.py
- [x] T093 Create constraint validation test: test_check_constraints() validating status enum values in tests/integration/test_schema_validation.py
- [x] T094 Create concurrency test: test_writer_during_reads() simulating ingestion writer while queries running in tests/integration/test_concurrent_reads.py
- [x] T095 Create concurrency test: test_wal_checkpoint_during_reads() verifying reads continue across WAL checkpoint in tests/integration/test_concurrent_reads.py
- [x] T096 Create performance test: test_search_latency_target() validating <100ms for 100K vectors in tests/integration/test_performance.py
- [x] T097 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-full tests/integration/` and verify all integration tests PASS

**Checkpoint**: All integration and error recovery tests passing. Wave 3 gate complete. Proceed to Wave 4.

---

## Phase 9: Quality Assurance, Code Review & Polish (Wave 4: A5)

**Purpose**: Final code review (SOLID, security, performance), documentation audit, regression tests

**Wave Gate**: Code review + all tests + documentation MUST be complete and passing

### Code Review & SOLID Principles

- [x] T098 Review SQLiteDB for SOLID principles: Single Responsibility (persistence), Open/Closed (stable interfaces), Liskov Substitution (async/await consistency), Interface Segregation (focused methods), Dependency Inversion (abstractions) in backend/storage/sqlite_db.py
- [x] T099 Review QdrantStorage for SOLID principles in backend/storage/qdrant_client.py
- [x] T100 Review KeyManager for SOLID principles in backend/providers/key_manager.py
- [x] T101 Security audit: verify no plaintext API keys logged or cached in all modules backend/storage/*, backend/providers/*
- [x] T102 Security audit: verify SQL parameterization prevents injection (aiosqlite binding) in backend/storage/sqlite_db.py
- [x] T103 Security audit: verify Fernet HMAC validation detects tampering in backend/providers/key_manager.py
- [x] T104 Security audit: verify environment variable for EMBEDINATOR_FERNET_KEY (not hardcoded) in backend/providers/key_manager.py
- [x] T105 Security audit: verify error messages don't leak sensitive information in all modules
- [x] T106 Performance audit: verify parent retrieval <10ms for 100 chunks via latency validation in tests/integration/test_performance.py
- [x] T107 Performance audit: verify Qdrant search <100ms for 100K vectors in tests/integration/test_performance.py
- [x] T108 Code quality: run `ruff check backend/storage backend/providers` and fix all style violations
- [x] T109 Code quality: verify PEP 8 compliance and type hints on all public methods in backend/storage/*, backend/providers/*
- [x] T110 Code quality: verify docstrings on classes and public methods (one-liner + params) in all modules
- [x] T111 Code quality: verify no print() statements (use structlog instead) in all modules

### Documentation Audit

- [x] T112 Audit spec.md: verify 4 user stories, 16 FRs, 11 success criteria are accurate and complete in specs/007-storage-architecture/spec.md
- [x] T113 Audit data-model.md: verify 7 entities with fields, relationships, validation rules match implementation in specs/007-storage-architecture/data-model.md
- [x] T114 Audit sqlite-contract.md: verify all SQLiteDB methods documented with signatures matching code in specs/007-storage-architecture/contracts/sqlite-contract.md
- [x] T115 Audit qdrant-contract.md: verify all QdrantStorage methods documented in specs/007-storage-architecture/contracts/qdrant-contract.md
- [x] T116 Audit key-manager-contract.md: verify all KeyManager methods documented in specs/007-storage-architecture/contracts/key-manager-contract.md
- [x] T117 Audit quickstart.md: verify all 8 usage examples work end-to-end in specs/007-storage-architecture/quickstart.md
- [x] T118 Audit plan.md: verify Technical Context, Constitution Check, Project Structure are accurate in specs/007-storage-architecture/plan.md
- [x] T119 Update CLAUDE.md with storage technologies (aiosqlite, qdrant-client, cryptography, tenacity, structlog) in CLAUDE.md

### Regression Test Suite

- [x] T120 Create regression test: test_fr_001_collections_table() verifying collections table with required fields in tests/regression/test_regression.py
- [x] T121 Create regression test: test_fr_002_documents_table() verifying documents table with UNIQUE(collection_id, file_hash) in tests/regression/test_regression.py
- [x] T122 Create regression test: test_fr_003_ingestion_jobs_table() verifying jobs table with status enum in tests/regression/test_regression.py
- [x] T123 Create regression test: test_fr_004_parent_chunks_table() verifying parent_chunks with UUID5 deterministic id in tests/regression/test_regression.py
- [x] T124 Create regression test: test_fr_005_query_traces_table() verifying query_traces with all fields in tests/regression/test_regression.py
- [x] T125 Create regression test: test_fr_006_settings_table() verifying settings key-value store in tests/regression/test_regression.py
- [x] T126 Create regression test: test_fr_007_providers_table() verifying providers with encrypted API keys in tests/regression/test_regression.py
- [x] T127 Create regression test: test_fr_008_wal_mode() verifying PRAGMA journal_mode returns "wal" in tests/regression/test_regression.py
- [x] T128 Create regression test: test_fr_009_foreign_keys() verifying PRAGMA foreign_keys returns 1 in tests/regression/test_regression.py
- [x] T129 Create regression test: test_fr_010_qdrant_dense_sparse() verifying dense 768d + sparse BM25 configs in tests/regression/test_regression.py
- [x] T130 Create regression test: test_fr_011_qdrant_payload() verifying child vectors carry all payload fields in tests/regression/test_regression.py
- [x] T131 Create regression test: test_fr_012_uuid5_determinism() verifying UUID5 IDs deterministic + idempotent in tests/regression/test_regression.py
- [x] T132 Create regression test: test_fr_013_api_key_encryption() verifying Fernet encryption for keys in tests/regression/test_regression.py
- [x] T133 Create regression test: test_fr_014_parent_retrieval() verifying batch parent retrieval with aliases in tests/regression/test_regression.py
- [x] T134 Create regression test: test_fr_015_sequential_ingestion() verifying jobs processed sequentially in tests/regression/test_regression.py
- [x] T135 Create regression test: test_fr_016_idempotent_resume() verifying failed jobs resumable via UUID5 in tests/regression/test_regression.py
- [x] T136 Create regression test: test_sc_001_all_tables_created() verifying all 7 tables created with correct columns in tests/regression/test_regression.py
- [x] T137 Create regression test: test_sc_002_wal_fk_pragmas() verifying WAL mode + FKs enabled in tests/regression/test_regression.py
- [x] T138 Create regression test: test_sc_003_uuid5_reproducible() verifying same content → same UUID5 in tests/regression/test_regression.py
- [x] T139 Create regression test: test_sc_004_qdrant_vectors() verifying dense + sparse configs present in tests/regression/test_regression.py
- [x] T140 Create regression test: test_sc_005_payload_fields() verifying all required payload fields present in tests/regression/test_regression.py
- [x] T141 Create regression test: test_sc_006_parent_latency() verifying <10ms for 100 parent chunks in tests/regression/test_regression.py
- [x] T142 Create regression test: test_sc_007_duplicate_prevention() verifying re-ingest marked duplicate in tests/regression/test_regression.py
- [x] T143 Create regression test: test_sc_008_wal_concurrency() verifying concurrent reads don't block in tests/regression/test_regression.py
- [x] T144 Create regression test: test_sc_009_encrypted_keys() verifying no plaintext keys in DB/logs in tests/regression/test_regression.py
- [x] T145 Create regression test: test_sc_010_traces_recorded() verifying all trace fields populated (including reasoning_steps_json, strategy_switches_json, confidence_score 0–100) in tests/regression/test_regression.py
- [x] T146 Create regression test: test_sc_011_cross_references() verifying parent_id links resolve correctly in tests/regression/test_regression.py
- [x] T147 Create edge case test: test_empty_collection_search() returning empty result not error in tests/regression/test_regression.py
- [x] T148 Create edge case test: test_file_same_hash_different_collections() allowing same file in multiple collections in tests/regression/test_regression.py
- [x] T149 Create edge case test: test_qdrant_unavailable_mid_batch() entire batch fails on Qdrant timeout in tests/regression/test_regression.py
- [x] T150 Create edge case test: test_failed_job_resumable() persisting partial data and resuming without rollback in tests/regression/test_regression.py

### Full Test Suite Execution

- [x] T151 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave1 tests/unit/test_sqlite_db.py` and verify PASSED  # Re-run from Wave 1 gate for regression baseline
- [x] T152 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave2-qdrant tests/unit/test_qdrant_storage.py` and verify PASSED  # Re-run from Wave 2 gate for regression baseline
- [x] T153 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-wave2-keymanager tests/unit/test_key_manager.py` and verify PASSED  # Re-run from Wave 2 gate for regression baseline
- [x] T154 Run external test runner: `zsh scripts/run-tests-external.sh -n spec07-full tests/` and verify ALL tests PASSED with coverage >80%
- [x] T155 Generate coverage report: `zsh scripts/run-tests-external.sh -n spec07-coverage tests/ --cov` and document coverage metrics
- [x] T156 Verify all regressions from prior specs (005, 006) still passing with storage layer integrated

### Final Commits & Completion

- [x] T157 Commit: `git add -A && git commit -m "feat: implement SQLiteDB foundation and schema"` (Wave 1 completion)
- [x] T158 Commit: `git add -A && git commit -m "feat: implement QdrantStorage and KeyManager"` (Wave 2 completion)
- [x] T159 Commit: `git add -A && git commit -m "test: add storage integration tests"` (Wave 3 completion)
- [x] T160 Commit: `git add -A && git commit -m "test: add regression test suite"` (Wave 4a)
- [x] T161 Commit: `git add -A && git commit -m "docs: audit and update all documentation"` (Wave 4b)
- [x] T162 Verify branch is clean: `git status` shows "nothing to commit, working tree clean"
- [x] T163 Signal spec-007 completion in project memory and mark Storage Architecture as IMPLEMENTATION COMPLETE

**Checkpoint**: Wave 4 (A5) Quality Gate COMPLETE. Storage Architecture Spec FULLY IMPLEMENTED ✅

---

## Dependencies & Execution Order

### Wave Dependency Chain

```
Wave 1 (A1: SQLiteDB)
    ↓ (GATE: all tests PASS)
Wave 2 (A2 ∥ A3: QdrantStorage ∥ KeyManager)  [Parallel]
    ↓ (GATE: both tests PASS)
Wave 3 (A4: Integration & Cross-Store)
    ↓ (GATE: all integration tests PASS)
Wave 4 (A5: Quality & Regression)
    ↓ (GATE: code review + all tests PASS)
Spec-007 COMPLETE ✅
```

### User Story Coverage

| User Story | Phase | Tasks | Key Tables | Dependencies |
|-----------|-------|-------|-----------|--------------|
| US1: Ingestion (P1) | 4 | T058–T071 | Documents, ParentChunks, IngestionJobs, Qdrant | Wave 1+2 complete |
| US2: Retrieval (P1) | 5 | T072–T076 | Collections, ParentChunks, Qdrant | US1 complete |
| US3: Query Traces (P2) | 6 | T077–T081 | QueryTraces, Sessions | US1+US2 complete |
| US4: Provider Mgmt (P2) | 7 | T082–T086 | Providers, Settings, KeyManager | Wave 2 complete |

### Parallel Execution Opportunities

**Phase 3 (Wave 2)**: A2 (QdrantStorage) and A3 (KeyManager) can run in parallel (tasks T028–T045 parallelizable with [P] marker)
- Estimated 4 developers: 2 on A2, 1 on A3, 1 on testing infrastructure
- Both waves should complete within same timeframe (~3-5 days each)

**Phase 4–7 (User Stories)**: US1 and US2 are independent after Wave 3. Can be developed in parallel by different teams if resources available.
- US3 and US4 are P2 (lower priority) and depend on P1 completion

### MVP Scope (Minimal Viable Product)

Complete Phases 1-5 for MVP:
- ✅ Phase 1: Setup (T001–T006)
- ✅ Phase 2: SQLiteDB (T007–T027)
- ✅ Phase 3: QdrantStorage + KeyManager (T028–T057)
- ✅ Phase 4: Ingestion integration (T058–T071)
- ✅ Phase 5: Search retrieval (T072–T076)

**MVP Delivery**: Core document ingestion and search fully functional. Optional: Phase 6–9 (Query traces, providers, quality gate) for production readiness.

---

## Task Numbering & Execution

- **Total Tasks**: 164 (T001–T163 + T164)
- **Phase 1 (Setup)**: 6 tasks (T001–T006)
- **Phase 2 (Wave 1)**: 20 tasks (T007–T027)
- **Phase 3 (Wave 2)**: 30 tasks (T028–T057) [A2: 18 tasks, A3: 12 tasks]
- **Phase 4 (US1)**: 15 tasks (T058–T071 + T164)
- **Phase 5 (US2)**: 5 tasks (T072–T076)
- **Phase 6 (US3)**: 5 tasks (T077–T081)
- **Phase 7 (US4)**: 5 tasks (T082–T086)
- **Phase 8 (Integration)**: 10 tasks (T087–T097)
- **Phase 9 (Quality)**: 66 tasks (T098–T163)

**Recommended Execution**: Follow wave gates strictly. Use external test runner for all test verification. Each wave must complete with all tests passing before proceeding to next wave.
