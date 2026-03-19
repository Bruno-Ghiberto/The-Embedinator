# Tasks: API Reference — HTTP Interface Layer

**Input**: Design documents from `/specs/008-api-reference/`
**Branch**: `008-api-reference` | **Generated**: 2026-03-15
**Prerequisites**: plan.md ✓ spec.md ✓ research.md ✓ data-model.md ✓ contracts/api-endpoints.md ✓ quickstart.md ✓

**Organization**: Tasks grouped by user story (US1–US5). Each story is independently implementable and testable.

**Testing**: Tests included — constitution requires ≥ 80% backend line coverage.

**Execution**: All test runs MUST use `scripts/run-tests-external.sh`. Never run pytest inside Claude Code.

```bash
# Test runner pattern for all tasks
zsh scripts/run-tests-external.sh -n spec08-<name> <test-target>
cat Docs/Tests/spec08-<name>.status      # poll
cat Docs/Tests/spec08-<name>.summary     # read when done
```

## Format: `[ID] [P?] [Story?] Description with file path`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: User story this task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: Verify structure and create agent instruction file stubs before implementation begins.

- [X] T001 Verify backend/api/ file inventory — confirm chat.py, collections.py, documents.py, providers.py, traces.py, health.py exist; confirm ingest.py, models.py, settings.py are absent (to be created)
- [X] T002 Populate Docs/PROMPTS/spec-08-api/agents/ instruction files for A1–A8 — each file must contain: agent role, assigned task IDs, exact file targets, test runner commands, and key constraints (NDJSON not SSE, int confidence, 12 file types, external test runner only). Source content from the Wave Spawn Prompts section of Docs/PROMPTS/spec-08-api/08-plan.md. Files: A1-schemas-config.md (T003–T004, schemas.py + config.py), A2-middleware.md (T005, middleware.py), A3-chat-ndjson.md (T008–T011, chat.py), A4-ingest-router.md (T012–T014 + T017, ingest.py + test), A5-documents-collections.md (T015–T016, collections.py + documents.py), A6-models-providers-settings.md (T018–T021 + T026–T027, providers.py + models.py + settings.py), A7-traces-health-wiring.md (T022–T025 + T028–T029, traces.py + health.py + main.py), A8-quality-tests.md (T030–T033, integration tests + ruff + regression)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core schemas, config fields, middleware extension, and missing SQLiteDB methods that ALL user stories depend on. No user story work starts until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase passes its checkpoint.

- [X] T003 Extend backend/agent/schemas.py — add CollectionCreateRequest with description/embedding_model/chunk_profile optional fields + regex field_validator `^[a-z0-9][a-z0-9_-]*$`; add CollectionResponse (9 fields); add DocumentResponse with correct status literals; add IngestionJobResponse; add ModelInfo; add ProviderKeyRequest; add ProviderDetailResponse with has_key bool; add SettingsResponse with confidence_threshold Field(ge=0, le=100); add SettingsUpdateRequest (all Optional); add HealthServiceStatus; add HealthResponse; add StatsResponse; add QueryTraceResponse; add QueryTraceDetailResponse; add 10 NDJSON event TypedDicts (SessionEvent, StatusEvent, ChunkEvent, CitationEvent, MetaReasoningEvent, ConfidenceEvent, GroundednessEvent, DoneEvent, ClarificationEvent, ErrorEvent); extend ChatRequest with optional embed_model field
- [X] T004 [P] Extend backend/config.py — add rate_limit_provider_keys_per_minute: int = 5 and rate_limit_general_per_minute: int = 120 to Settings class
- [X] T005 Extend backend/middleware.py — update RateLimitMiddleware._get_limit() and _get_bucket() to add 4th category (PUT/DELETE **/key → 5/min, bucket provider_key:{ip}); update general limit from 100 to 120 reading from settings.rate_limit_general_per_minute; read all limits from settings fields (not hardcoded); ensure 429 responses include trace_id in body (depends on T004)
- [X] T006 [P] Add list_traces() and get_trace() to backend/storage/sqlite_db.py — list_traces(session_id, collection_id, min_confidence, max_confidence, limit, offset) → list[dict]; get_trace(trace_id) → dict | None; both query the query_traces table
- [X] T007 Add get_active_provider() and upsert_provider() to backend/storage/sqlite_db.py — get_active_provider() → dict | None (SELECT WHERE is_active=1); upsert_provider(name, provider_type, config_json, is_active) → None (INSERT OR REPLACE); add ALTER TABLE migration for provider_type (VARCHAR) and config_json (TEXT) columns if not present (depends on T006 — modifies same file)

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-foundation tests/unit/test_schemas_api.py tests/unit/test_middleware_rate_limit.py` → must PASS before Phase 3.

---

## Phase 3: User Story 1 — Chat Streaming (Priority: P1) 🎯 MVP

**Goal**: POST /api/chat streams all 10 NDJSON event types with correct format, media type, and trace recording.

**Independent Test**: Send a POST to /api/chat with a valid collection_id and message; verify the response is `application/x-ndjson`, the first line is `{"type":"session",...}`, the last success line is `{"type":"done",...}`, and all intermediate lines are valid JSON with no `data:` prefix.

### Tests for User Story 1

- [X] T008 [P] [US1] Write tests/unit/test_chat_ndjson.py — test all 10 event type emissions; assert media_type="application/x-ndjson"; assert json.dumps+"\n" format (no SSE prefix); assert confidence score is int 0–100; assert session event is first; assert done event is last on success; mock ConversationGraph astream; test error event on CircuitOpenError; test clarification event on interrupt; test multi-turn session continuity (FR-016): send two requests with same session_id and verify second request receives prior context via graph checkpointer (mock graph.get_state returns prior state)
- [X] T009 [P] [US1] Write tests/integration/test_ndjson_streaming.py — end-to-end: parse each response line as JSON; assert no line starts with "data:"; assert media type header; assert all 10 event types exercised across test scenarios; record wall-clock time from request start to first "chunk" event and assert ≤500ms (SC-002 target, skip if CI latency unreliable)

### Implementation for User Story 1

- [X] T010 [US1] Rewrite event_generator() in backend/api/chat.py — add session event (before astream call); add status event per metadata["langgraph_node"]; keep chunk events; add citation event from final_state["citations"]; add meta_reasoning event from final_state["attempted_strategies"] if non-empty; add confidence event (int conversion); add groundedness event from final_state["groundedness_result"]; rename metadata→done event with latency_ms; add trace_id to error event; all yields use json.dumps(event)+"\n" with media_type="application/x-ndjson"
- [X] T011 [US1] Fix backend/api/chat.py trace recording — replace calls to missing db.create_query(), db.create_trace(), db.create_answer() with a single db.create_query_trace() call after stream completes; populate all fields including sub_questions_json, reasoning_steps_json, strategy_switches_json, meta_reasoning_triggered

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-us1 tests/unit/test_chat_ndjson.py tests/integration/test_ndjson_streaming.py` → must PASS.

---

## Phase 4: User Story 2 — Collections, Documents & Ingestion (Priority: P2)

**Goal**: Full CRUD for collections and documents, file upload with background ingestion, job status polling, duplicate detection, and cascade collection deletion.

**Independent Test**: Create a collection (verify 201 + name regex enforcement), upload a PDF (verify 202 + job_id), poll job status (verify all phase values), list documents (verify document appears), delete document (verify 204), delete collection (verify cascade cancels active jobs + removes Qdrant collection).

### Tests for User Story 2

- [X] T012 [P] [US2] Write tests/unit/test_collections_router.py — test name regex validation (400 on uppercase/spaces); test 409 on duplicate name; test DELETE cascade: jobs cancelled → qdrant deleted → collection deleted; mock SQLiteDB + QdrantStorage
- [X] T013 [P] [US2] Write tests/unit/test_documents_router.py — test GET /documents (list + collection_id filter); test GET /documents/{id} (200 and 404); test DELETE /documents/{id} (204 and 404); mock SQLiteDB
- [X] T014 [P] [US2] Write tests/unit/test_ingest_router.py — test 12 allowed extensions (including .c/.cpp/.h); test 400 on unsupported extension; test 413 on file over 100 MB; test 409 on duplicate content hash; test 404 on unknown collection_id; test GET job status endpoint; test asyncio.create_task background launch; mock IngestionPipeline + IncrementalChecker

### Implementation for User Story 2

- [X] T015 [P] [US2] Extend backend/api/collections.py — use CollectionCreateRequest with field_validator for name regex (FR-002); catch UNIQUE constraint for 409 (FR-003); extend DELETE to: list active jobs via db.list_ingestion_jobs(), set each to failed, then call qdrant_storage.delete_collection(qdrant_collection_name), then db.delete_collection() (FR-005); wire to app.state.qdrant_storage
- [X] T016 [US2] Rewrite backend/api/documents.py — remove ingest_document() function and _process_document() background task (legacy Phase 1 stub); keep GET /api/documents with optional collection_id query param; keep GET /api/documents/{id}; keep DELETE /api/documents/{id}; align all db.* calls to actual SQLiteDB method signatures from spec-07; use DocumentResponse schema (T017 depends on this completing — ingest.py must not import from legacy documents.py)
- [X] T017 [US2] Create backend/api/ingest.py — POST /api/collections/{collection_id}/ingest: validate extension (12 types), validate file size (≤100 MB), verify collection exists (404 if not), compute SHA-256 hash, check IncrementalChecker for duplicates (409 if duplicate), save file to settings.upload_dir/collection_id/filename, create document + job via db, launch IngestionPipeline.ingest_file() as asyncio.create_task(), return 202 with IngestionJobResponse; GET /api/collections/{collection_id}/ingest/{job_id}: fetch via db.get_ingestion_job(), return IngestionJobResponse or 404

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-us2 tests/unit/test_collections_router.py tests/unit/test_documents_router.py tests/unit/test_ingest_router.py` → must PASS.

---

## Phase 5: User Story 3 — Providers & Models (Priority: P3)

**Goal**: Save and delete encrypted provider API keys (never returning key values), list providers with has_key indicator, and list available language + embedding models from configured providers.

**Independent Test**: GET /providers → verify has_key bool, no key value in response; PUT /providers/openai/key → verify has_key:true returned; GET /providers → verify has_key:true; DELETE /providers/openai/key → verify has_key:false; GET /models/llm → verify ModelInfo list with provider + name fields.

### Tests for User Story 3

- [X] T018 [P] [US3] Write tests/unit/test_providers_router.py — test has_key:true/false in list response; test key value never returned; test PUT /key encrypts via KeyManager and stores; test DELETE /key sets has_key false; test 503 when key_manager is None; mock SQLiteDB + KeyManager
- [X] T019 [P] [US3] Write tests/unit/test_models_router.py — test GET /models/llm returns ModelInfo list; test GET /models/embed returns embed type only; test 503 when Ollama unreachable; mock httpx client

### Implementation for User Story 3

- [X] T020 [US3] Extend backend/api/providers.py — add PUT /api/providers/{name}/key: accept ProviderKeyRequest, encrypt via request.app.state.key_manager.encrypt(), store via db, return {name, has_key:true}; add DELETE /api/providers/{name}/key: remove encrypted key from DB, return {name, has_key:false}; update GET /api/providers: add has_key:bool to each provider, NEVER include api_key_encrypted or decrypted key; switch all Fernet usage from inline instantiation to app.state.key_manager; return 503 with KEY_MANAGER_UNAVAILABLE if key_manager is None
- [X] T021 [US3] Create backend/api/models.py — GET /api/models/llm: call httpx.AsyncClient().get(f"{settings.ollama_base_url}/api/tags") with timeout, parse response into list[ModelInfo] with model_type="llm", return 503 on failure; GET /api/models/embed: same but filter for known embedding model names (nomic-embed-text, mxbai-embed-large, *:embed, *:embedding); handle missing/unconfigured cloud providers gracefully (return empty list)

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-us3 tests/unit/test_providers_router.py tests/unit/test_models_router.py` → must PASS.

---

## Phase 6: User Story 4 — Observability (Priority: P4)

**Goal**: Health endpoint reports per-service status + latency; traces endpoint supports session filter and pagination; stats endpoint returns aggregate query metrics.

**Independent Test**: GET /health → verify 200 with services list each having name/status/latency_ms; stop Qdrant → verify 503 with qdrant service showing "error"; GET /traces?session_id=x → verify empty list returned (not 404); GET /stats → verify all 7 numeric fields present.

### Tests for User Story 4

- [X] T022 [P] [US4] Write tests/unit/test_traces_router.py — test pagination (limit, offset); test session_id filter; test empty result returns [] not 404; test GET /traces/{id} 200 and 404; test GET /stats returns StatsResponse with all fields; mock SQLiteDB
- [X] T023 [P] [US4] Write tests/unit/test_health_router.py — test 200 when all services ok; test 503 when one service errors; test latency_ms is float in each service entry; test error_message is null when ok; mock db, qdrant, ollama probes

### Implementation for User Story 4

- [X] T024 [US4] Extend backend/api/traces.py — add optional session_id: str | None = Query(None) filter to GET /api/traces; add offset: int = Query(0) for pagination; call db.list_traces(session_id, collection_id, min_confidence, max_confidence, limit, offset); add GET /api/stats endpoint: compute aggregate counts and averages from query_traces (total_collections, total_documents, total_chunks, total_queries, avg_confidence, avg_latency_ms, meta_reasoning_rate); update response to QueryTraceResponse schema
- [X] T025 [US4] Rewrite backend/api/health.py — measure latency of each probe with time.monotonic(); return HealthResponse with services: list[HealthServiceStatus]; each entry has name, status ("ok"/"error"), latency_ms (float|null), error_message (str|null); return 200 if all ok, 503 if any error; probe order: sqlite (db.db.execute("SELECT 1")), qdrant (qdrant_storage.health_check()), ollama (registry._ollama_llm.health_check())

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-us4 tests/unit/test_traces_router.py tests/unit/test_health_router.py` → must PASS.

---

## Phase 7: User Story 5 — Settings (Priority: P5)

**Goal**: Read and partially update system-wide configuration with type validation.

**Independent Test**: GET /settings → verify all 7 fields present with correct types and defaults; PUT /settings with {confidence_threshold: 75} → verify only that field changes; PUT /settings with {confidence_threshold: 150} → verify 400 validation error.

### Tests for User Story 5

- [X] T026 [P] [US5] Write tests/unit/test_settings_router.py — test GET returns SettingsResponse with all 7 fields; test defaults match config.py values; test PUT updates only submitted fields; test PUT with confidence_threshold=150 returns 400; test PUT with confidence_threshold=0 and =100 returns 200; mock SQLiteDB

### Implementation for User Story 5

- [X] T027 [US5] Create backend/api/settings.py — GET /api/settings: call db.list_settings() to get dict of string key-value pairs, merge with config defaults (fallback for missing keys), coerce types (int, bool, float), return SettingsResponse; PUT /api/settings: accept SettingsUpdateRequest (all Optional fields), validate confidence_threshold 0–100 (400 if out of range), for each non-None field call db.set_setting(key, str(value)), return full SettingsResponse after update

**Checkpoint**: Run `zsh scripts/run-tests-external.sh -n spec08-us5 tests/unit/test_settings_router.py` → must PASS.

---

## Phase 8: Wiring, Integration & Regression

**Purpose**: Register new routers in app factory, run cross-story integration tests, validate rate limiting, verify full regression passes with zero regressions vs spec-07 baseline.

- [X] T028 [P] Update backend/main.py — import and register 3 new routers: `from backend.api import ingest, models, settings`; `app.include_router(ingest.router, tags=["ingest"])`; `app.include_router(models.router, tags=["models"])`; `app.include_router(settings.router, tags=["settings"])`; verify app.state.key_manager is accessible in provider route (already set in lifespan)
- [X] T029 [P] Update backend/api/__init__.py — export new router objects from ingest, models, settings modules
- [X] T030 Write tests/integration/test_api_integration.py — full request cycle for each endpoint group using TestClient; verify 409 on duplicate collection name (FR-003); verify 400 on invalid name pattern (FR-002); verify 413 on oversized file, 400 on unsupported extension (FR-008); verify has_key never returns key value (FR-018, SC-005); verify confidence in responses is int 0–100 (FR-015); verify 204 on delete with cascade; verify trace_id present in all error responses (FR-026)
- [X] T031 Write tests/integration/test_rate_limiting.py — burst 31 chat requests → verify exactly 1 returns 429 (SC-004); burst 11 ingest requests → verify exactly 1 returns 429; burst 6 provider key requests → verify exactly 1 returns 429; verify Retry-After header present on 429; verify X-Trace-ID header on all responses
- [X] T032 Run ruff check on all modified/created files: backend/api/chat.py, ingest.py, models.py, providers.py, settings.py, traces.py, health.py, collections.py, documents.py, backend/middleware.py, backend/main.py, backend/storage/sqlite_db.py, backend/agent/schemas.py, backend/config.py — fix any lint errors
- [X] T033 Run full regression: `zsh scripts/run-tests-external.sh -n spec08-full tests/` — verify PASSED; read Docs/Tests/spec08-full.summary; confirm zero regressions vs spec-07 baseline (238 spec-07 tests must still pass)
- [X] T034 Write tests/integration/test_concurrent_streams.py — launch 10 simultaneous POST /api/chat requests using asyncio.gather(); verify all 10 complete without event loss or dropped frames; verify no 500 errors; verify all 10 responses contain the "done" event as their last frame (SC-010 target: 10 concurrent streams)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **User Stories (Phases 3–7)**: All depend on Phase 2 completion
  - US1–US5 can proceed in priority order (P1 → P2 → P3 → P4 → P5)
  - Or in parallel if using Agent Teams (Wave 2+ are parallel per 08-plan.md)
- **Wiring + Regression (Phase 8)**: Depends on all user stories complete

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 (schemas, config, middleware) only
- **US2 (P2)**: Depends on Phase 2; no dependency on US1
- **US3 (P3)**: Depends on Phase 2 + T006/T007 (SQLiteDB provider methods)
- **US4 (P4)**: Depends on Phase 2 + T006 (SQLiteDB trace methods)
- **US5 (P5)**: Depends on Phase 2 only (uses db.list_settings/set_setting which exist)

### Within Each User Story

- Tests written before implementation (write test → verify it fails → implement → verify it passes)
- Schemas before endpoints (T003 foundational)
- SQLiteDB methods before dependent routers (T006 before US4, T007 before US3)
- Individual router files are independent within a story

### Key Cross-Task Dependencies

```
T004 → T005                    (middleware reads config rate limit fields)
T006 → T007                    (same sqlite_db.py file — must sequence)
T003 → T010, T015, T016, T017, T020, T021, T024, T025, T027 (schemas needed by all routers)
T006 → T024                    (traces router needs list_traces/get_trace)
T007 → T020                    (providers router needs upsert_provider)
T016 → T017                    (ingest.py must not import legacy functions removed by T016)
T028 → T030, T031, T034        (main.py wiring needed for integration + concurrent tests)
```

---

## Parallel Opportunities

### Phase 2 (Foundational)

```bash
# Can run in parallel:
T003: Extend backend/agent/schemas.py
T004: Extend backend/config.py       ← different file
T006: Add list_traces/get_trace to sqlite_db.py    ← different file

# Then sequentially (same file as T006):
T007: Add get_active_provider/upsert_provider to sqlite_db.py  ← depends on T006

# Then sequentially:
T005: Extend backend/middleware.py   ← depends on T004 (config fields)
```

### Phase 4 (US2)

```bash
# Wave 2 (A4): Tests and new ingest router in parallel with other files:
T012: test_collections_router.py     ← parallel (different file)
T013: test_documents_router.py       ← parallel (different file)
T014: test_ingest_router.py          ← parallel (different file)
T017: ingest.py (new)                ← parallel (new file, no legacy deps)

# Wave 3 (A5): collections.py and documents.py
T015: collections.py (extend)        ← can parallel with T016
T016: documents.py (rewrite)         ← can parallel with T015, but T017 must complete after T016
```

### Phase 5 (US3 — 2-way parallel)

```bash
T018: test_providers_router.py   ← parallel
T019: test_models_router.py      ← parallel, different file
T020: providers.py (extend)      ← parallel with T021
T021: models.py (new)            ← parallel with T020
```

### Phase 8 (Wiring — parallel then sequential)

```bash
T028: main.py update    ← parallel
T029: __init__.py       ← parallel
# Then sequentially (need T028):
T030, T031, T032, T033
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1 + Phase 2 (foundational)
2. Complete Phase 3 (US1 — chat streaming)
3. **VALIDATE**: NDJSON stream produces all 10 event types with correct format
4. Complete Phase 8 partial (T028, T029, T033)

**Result**: Working chat endpoint with correct streaming protocol.

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → Chat streaming works ← **MVP**
3. Phase 4 (US2) → Collections/docs/ingest works
4. Phase 5 (US3) → Provider key management + model listing works
5. Phase 6 (US4) → Health/traces/stats works
6. Phase 7 (US5) → Settings management works
7. Phase 8 → Full integration validated

### Agent Teams Strategy (per 08-plan.md)

```
Wave 1 (parallel): T003 + T004 + T005 + T006 + T007         (A1 schemas+config, A2 middleware)
Wave 2 (parallel): T008-T011 + T012-T014 + T017             (A3 chat NDJSON, A4 ingest router + tests)
Wave 3 (parallel): T015-T016 + T018-T021 + T026-T027        (A5 docs+collections, A6 models+providers+settings)
Wave 4 (serial):   T022-T025 + T028-T029                    (A7 traces+health+wiring+main.py)
Wave 5 (serial):   T030-T034                                 (A8 tests+integration+regression+concurrent)
```

See `Docs/PROMPTS/spec-08-api/08-plan.md` for exact agent spawn prompts and checkpoint gates.

---

## Notes

- **NEVER run pytest inside Claude Code** — use `scripts/run-tests-external.sh` (constitution requirement)
- **Confidence scores are always int 0–100** — never float; validated with `Field(ge=0, le=100)`
- **NDJSON not SSE** — `json.dumps(event)+"\n"`, `media_type="application/x-ndjson"`, no `data:` prefix
- **Provider keys never returned** — only `has_key: bool` in any response (SC-005)
- **12 file types** — `.c`, `.cpp`, `.h` are required in addition to the original 9
- **Settings are key-value rows** — assembled at read time via `db.list_settings()` + config defaults
- **ingest.py is a new separate router** — not part of collections.py or documents.py
- **Rate limit general is 120/min** — not 100/min (spec supersedes constitution v1)
- Each task includes a concrete file path — agents can execute without additional context
