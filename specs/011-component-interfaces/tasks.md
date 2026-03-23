# Tasks: Component Interface Contracts

**Input**: Design documents from `/specs/011-component-interfaces/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/test-patterns.md

**Tests**: Tests ARE the primary implementation for this spec (FR-020, FR-021). Every task in Phases 3-7 produces test code.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- All test files: `tests/unit/test_contracts_*.py`
- Validation report: `Docs/Tests/contracts-validation-report.md`
- Test runner: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER run pytest inside Claude Code

---

## Phase 1: Setup

**Purpose**: Verify project structure and test runner readiness

- [x] T001 Verify `tests/unit/` directory exists and `tests/__init__.py` is present
- [x] T002 Verify `scripts/run-tests-external.sh` is executable and `Docs/Tests/` directory exists

---

## Phase 2: Foundational — Validate 11-specify.md (Wave 1)

**Purpose**: Cross-reference every signature in `Docs/PROMPTS/spec-11-interfaces/11-specify.md` against the live codebase using Serena MCP. Fix any discrepancies before writing tests.

**Agent**: A1 (quality-engineer, Opus)

- [x] T003 Validate state schemas section of `Docs/PROMPTS/spec-11-interfaces/11-specify.md` against `backend/agent/state.py` — verify all 3 TypedDicts, field names, field types, field counts (ConversationState: 12, ResearchState: 16, MetaReasoningState: 11)
- [x] T004 [P] Validate ConversationGraph node signatures section against `backend/agent/nodes.py` — verify all 11 node function signatures, DI patterns (`*, llm: Any` vs `**kwargs` vs none), return type `dict`, and that Reads/Writes docstring annotations match actual state field access (SC-008)
- [x] T005 [P] Validate ResearchGraph + MetaReasoningGraph node signatures against `backend/agent/research_nodes.py` and `backend/agent/meta_reasoning_nodes.py` — verify `config: RunnableConfig = None` pattern on all 9 nodes, and that Reads/Writes docstring annotations match actual state field access (SC-008)
- [x] T006 [P] Validate edge functions section against `backend/agent/edges.py`, `backend/agent/research_edges.py`, `backend/agent/meta_reasoning_edges.py` — verify all 7 edge functions exist
- [x] T007 [P] Validate storage section against `backend/storage/sqlite_db.py` and `backend/storage/qdrant_client.py` — verify method names (`batch_upsert`, `search_hybrid`, `delete_points_by_filter`), param signatures, no ORM types
- [x] T008 [P] Validate retrieval section against `backend/retrieval/searcher.py` and `backend/retrieval/reranker.py` — verify constructor params, `search_all_collections` name, `score_pair` absence
- [x] T009 [P] Validate ingestion section against `backend/ingestion/pipeline.py`, `backend/ingestion/embedder.py`, `backend/ingestion/chunker.py`, `backend/ingestion/incremental.py` — verify constructor params, `embed_chunks` name, `IngestionResult` is dataclass
- [x] T010 [P] Validate provider section against `backend/providers/base.py`, `backend/providers/registry.py`, `backend/providers/key_manager.py` — verify ABC methods, dual LLM paths, concrete provider subclasses
- [x] T011 [P] Validate error hierarchy and Pydantic schemas sections against `backend/errors.py` and `backend/agent/schemas.py` — verify all 11 error classes, all 40+ schema imports, 10 NDJSON events
- [x] T012 Fix any discrepancies found in `Docs/PROMPTS/spec-11-interfaces/11-specify.md` and produce validation report at `Docs/Tests/contracts-validation-report.md`

**Checkpoint**: Validation report confirms zero discrepancies between `11-specify.md` and live code. All subsequent test tasks use verified contracts.

---

## Phase 3: User Story 1 — Enforce Agent Node Contracts (Priority: P1)

**Goal**: Contract tests for state schemas, 20 node functions, 7 edge functions, tool factory, graph builders, and confidence scoring.

**Independent Test**: `zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py`

**Agent**: A2 (python-expert, Sonnet)

### Implementation for User Story 1

- [x] T013 [US1] Create `tests/unit/test_contracts_agent.py` with imports and test structure — import `inspect`, `typing`, all node/edge modules
- [x] T014 [US1] Write state schema field tests (FR-001, FR-002): verify `ConversationState` has 12 fields, `ResearchState` has 16 fields (including `_no_new_tools`, `_needs_compression`), `MetaReasoningState` has 11 fields (including `attempted_strategies`), dual confidence scale (int vs float) in `tests/unit/test_contracts_agent.py`
- [x] T015 [US1] Write ConversationGraph node signature tests (FR-003, FR-004): verify all 11 nodes in `backend/agent/nodes.py` — `classify_intent` (`*, llm: Any` KEYWORD_ONLY), `rewrite_query` (`*, llm: Any`), `verify_groundedness` (`*, llm: Any = None`), `validate_citations` (`*, reranker: Any = None`), `init_session`/`fan_out`/`aggregate_answers`/`summarize_history`/`format_response`/`handle_collection_mgmt` (`**kwargs` VAR_KEYWORD), `request_clarification` (no DI) in `tests/unit/test_contracts_agent.py`
- [x] T016 [US1] Write ResearchGraph node signature tests (FR-007): verify all 5 nodes in `backend/agent/research_nodes.py` — `orchestrator`, `tools_node`, `compress_context`, `collect_answer` have `config: RunnableConfig = None`; `fallback_response` signature (check actual params) in `tests/unit/test_contracts_agent.py`
- [x] T017 [US1] Write MetaReasoningGraph node signature tests (FR-007): verify all 4 nodes in `backend/agent/meta_reasoning_nodes.py` (NOT `nodes.py`) — `generate_alternative_queries`, `evaluate_retrieval_quality`, `decide_strategy`, `report_uncertainty` all have `config` param in `tests/unit/test_contracts_agent.py`
- [x] T018 [US1] Write edge function tests (FR-005): verify 7 functions across 3 files — `route_intent`, `should_clarify`, `route_after_rewrite`, `route_fan_out` in `edges.py`; `should_continue_loop`, `route_after_compress_check` in `research_edges.py`; `route_after_strategy` in `meta_reasoning_edges.py` in `tests/unit/test_contracts_agent.py`
- [x] T019 [US1] Write tool factory tests (FR-006): verify `create_research_tools` in `backend/agent/tools.py` has params `["searcher", "reranker", "parent_store"]` and returns `list` in `tests/unit/test_contracts_agent.py`
- [x] T020 [US1] Write graph builder tests (FR-019): verify `build_conversation_graph` in `conversation_graph.py`, `build_research_graph` in `research_graph.py`, `build_meta_reasoning_graph` in `meta_reasoning_graph.py` exist and are callable in `tests/unit/test_contracts_agent.py`
- [x] T021 [US1] Write confidence scoring tests (FR-002): verify `compute_confidence` exists in `backend/agent/confidence.py` in `tests/unit/test_contracts_agent.py`
- [x] T022 [US1] Run agent contract tests: `zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py` — fix any failures

**Checkpoint**: All agent contract tests pass. State schemas, 20 nodes, 7 edges, tools, builders, and confidence are validated.

---

## Phase 4: User Story 2 — Enforce Storage Layer Contracts (Priority: P2)

**Goal**: Contract tests for SQLiteDB (35+ methods), QdrantStorage (12+ methods), ParentStore, and data classes.

**Independent Test**: `zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py`

**Agent**: A3 (python-expert, Sonnet) — runs in PARALLEL with A2/Phase 3

### Implementation for User Story 2

- [x] T023 [P] [US2] Create `tests/unit/test_contracts_storage.py` with imports — import `inspect`, `SQLiteDB`, `QdrantStorage`, `ParentStore`
- [x] T024 [US2] Write SQLiteDB method existence tests (FR-008): verify all 35+ methods exist on `SQLiteDB` class — collections (6 methods), documents (6), ingestion jobs (4), parent chunks (5), query traces (5), settings (4), providers (7), health (1), context manager (2) in `tests/unit/test_contracts_storage.py`
- [x] T025 [US2] Write SQLiteDB key method signature tests (FR-008): verify `create_query_trace` has all 16 params including `provider_name`, `create_document` uses individual params (not model type), `list_traces` has `session_id`/`collection_id`/`min_confidence`/`max_confidence`/`limit`/`offset` params in `tests/unit/test_contracts_storage.py`
- [x] T026 [US2] Write QdrantStorage tests (FR-009): verify method names (`batch_upsert` not `upsert_batch`, `search_hybrid` not `hybrid_search`, `delete_points_by_filter` not `delete_by_filter`), verify `SparseVector`/`QdrantPoint`/`SearchResult` data classes exist, verify `QdrantClientWrapper` coexists in same file in `tests/unit/test_contracts_storage.py`
- [x] T027 [US2] Write ParentStore tests: verify constructor takes `db` param, `get_by_ids` and `get_all_by_collection` methods exist in `tests/unit/test_contracts_storage.py`
- [x] T028 [US2] Write negative assertion tests (SC-006): verify phantom methods do NOT exist — `SQLiteDB.find_by_hash`, `SQLiteDB.store_parent_chunks`, `SQLiteDB.store_trace`, `SQLiteDB.get_all_settings`, `SQLiteDB.set_provider_key`, `SQLiteDB.delete_provider_key`, `SQLiteDB.update_document_status` in `tests/unit/test_contracts_storage.py`
- [x] T029 [US2] Run storage contract tests: `zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py` — fix any failures

**Checkpoint**: All storage contract tests pass. SQLiteDB (35+ methods), QdrantStorage, and ParentStore are validated.

---

## Phase 5: User Story 3 — Enforce Provider and Retrieval Contracts (Priority: P3)

**Goal**: Contract tests for LLMProvider/EmbeddingProvider ABCs, ProviderRegistry, KeyManager, concrete providers, HybridSearcher, Reranker, ScoreNormalizer.

**Independent Test**: Run both files: `zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py` and `zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py`

**Agent**: A4 (python-expert, Sonnet)

### Implementation for User Story 3

- [x] T030 [P] [US3] Create `tests/unit/test_contracts_providers.py` with imports — import `inspect`, `abc`, all provider modules
- [x] T031 [US3] Write LLMProvider ABC tests (FR-016): verify 4 abstract methods (`generate`, `generate_stream`, `health_check`, `get_model_name`), verify `generate` params include `prompt` and `system_prompt`, verify ABC cannot be instantiated directly in `tests/unit/test_contracts_providers.py`
- [x] T032 [US3] Write EmbeddingProvider ABC tests (FR-016): verify 4 abstract methods (`embed`, `embed_single`, `get_model_name`, `get_dimension`), verify `embed` has optional `model` parameter (spec-10 FR-006) in `tests/unit/test_contracts_providers.py`
- [x] T033 [US3] Write ProviderRegistry tests (FR-016): verify constructor takes `settings` (NOT `SQLiteDB`), verify `get_active_llm`, `get_active_langchain_model`, `get_embedding_provider`, `set_active_provider` methods exist, verify `get_embedding_provider` has NO `db` param in `tests/unit/test_contracts_providers.py`
- [x] T034 [US3] Write KeyManager and concrete provider tests (FR-016): verify `KeyManager` has `encrypt`/`decrypt`/`is_valid_key` methods, verify 4 concrete LLMProvider subclasses (`OllamaLLMProvider`, `OpenRouterLLMProvider`, `OpenAILLMProvider`, `AnthropicLLMProvider`) and 1 EmbeddingProvider subclass (`OllamaEmbeddingProvider`), verify `ProviderRateLimitError` exists in `base.py` in `tests/unit/test_contracts_providers.py`
- [x] T035 [P] [US3] Create `tests/unit/test_contracts_retrieval.py` with imports — import `inspect`, `HybridSearcher`, `Reranker`
- [x] T036 [US3] Write HybridSearcher tests (FR-010): verify constructor params are `["self", "client", "settings"]` (NOT storage/embedder/reranker), verify `search` method has `embed_fn` param, verify method is `search_all_collections` (NOT `search_multi_collection`), verify circuit breaker methods exist (`_check_circuit`, `_record_success`, `_record_failure`) in `tests/unit/test_contracts_retrieval.py`
- [x] T037 [US3] Write Reranker tests (FR-011): verify constructor params are `["self", "settings"]` (NOT `model_name: str`), verify `rerank` method has `["self", "query", "chunks", "top_k"]` params, verify `score_pair` does NOT exist (`assert not hasattr`) in `tests/unit/test_contracts_retrieval.py`
- [x] T038 [US3] Write ScoreNormalizer test: verify `normalize_scores` is a module-level function in `backend/retrieval/score_normalizer.py` (not a class method) in `tests/unit/test_contracts_retrieval.py`
- [x] T039 [US3] Run provider and retrieval contract tests: `zsh scripts/run-tests-external.sh -n contracts-providers tests/unit/test_contracts_providers.py` and `zsh scripts/run-tests-external.sh -n contracts-retrieval tests/unit/test_contracts_retrieval.py` — fix any failures

**Checkpoint**: All provider and retrieval contract tests pass. ABCs, registry, concrete providers, searcher, reranker validated.

---

## Phase 6: User Story 4 — Enforce Ingestion Pipeline Contracts (Priority: P4)

**Goal**: Contract tests for IngestionPipeline, BatchEmbedder, ChunkSplitter, IncrementalChecker, UpsertBuffer, IngestionResult.

**Independent Test**: `zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py`

**Agent**: A4 (python-expert, Sonnet) — sequential after Phase 5

### Implementation for User Story 4

- [x] T040 [US4] Create `tests/unit/test_contracts_ingestion.py` with imports — import `inspect`, `dataclasses`, `pydantic.BaseModel`, all ingestion modules
- [x] T041 [US4] Write IngestionPipeline constructor tests (FR-013): verify constructor takes exactly 3 params (`db`, `qdrant`, `embedding_provider`), verify `qdrant` receives `QdrantClientWrapper` (NOT `QdrantStorage`), verify `check_duplicate` does NOT exist on `IngestionPipeline` in `tests/unit/test_contracts_ingestion.py`
- [x] T042 [US4] Write IngestionResult tests (FR-014): verify is `@dataclass` (NOT `BaseModel`) via `dataclasses.is_dataclass()`, verify fields include `document_id`/`job_id`/`status`/`chunks_processed`/`chunks_skipped`/`error`, verify `error_msg` and `elapsed_ms` do NOT exist in `tests/unit/test_contracts_ingestion.py`
- [x] T043 [US4] Write BatchEmbedder tests (FR-012): verify method is `embed_chunks` (NOT `embed_batch`), verify `validate_embedding` is a standalone module-level function in `embedder.py` (NOT a method on `BatchEmbedder`) in `tests/unit/test_contracts_ingestion.py`
- [x] T044 [US4] Write IncrementalChecker, ChunkSplitter, and UpsertBuffer tests (FR-015): verify `check_duplicate` lives on `IncrementalChecker` (NOT `IngestionPipeline`), verify `compute_file_hash` exists on `IncrementalChecker`, verify `ChunkSplitter` has `split_into_parents`, `split_parent_into_children`, `prepend_breadcrumb`, `compute_point_id` methods, verify `UpsertBuffer` class exists with `add`, `flush`, `pending_count` methods in `tests/unit/test_contracts_ingestion.py`
- [x] T045 [US4] Run ingestion contract tests: `zsh scripts/run-tests-external.sh -n contracts-ingestion tests/unit/test_contracts_ingestion.py` — fix any failures

**Checkpoint**: All ingestion contract tests pass. Pipeline, embedder, chunker, incremental checker validated.

---

## Phase 7: User Story 5 — Error Hierarchy and Cross-Cutting Contracts (Priority: P5)

**Goal**: Contract tests for 11 error classes, 40+ Pydantic schemas (6 with full fields), 10 NDJSON events, Settings config.

**Independent Test**: `zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py`

**Agent**: A4 (python-expert, Sonnet) — sequential after Phase 6

### Implementation for User Story 5

- [x] T046 [US5] Create `tests/unit/test_contracts_cross_cutting.py` with imports — import `inspect`, `typing`, all error classes, schema classes, Settings
- [x] T047 [US5] Write error hierarchy tests (FR-017): import all 11 classes from `backend/errors.py`, verify all 10 specific errors are subclasses of `EmbeddinatorError`, verify `CircuitOpenError` exists (commonly missed) in `tests/unit/test_contracts_cross_cutting.py`
- [x] T048 [US5] Write cross-layer Pydantic schema tests (FR-018): verify `QueryAnalysis` has `complexity_tier` field with correct Literal type, `ClaimVerification` has `verdict` field, `GroundednessResult` has `overall_grounded` field, `RetrievedChunk`/`Citation`/`SubAnswer` are `BaseModel` subclasses with expected key fields in `tests/unit/test_contracts_cross_cutting.py`
- [x] T049 [US5] Write API schema import tests (FR-018): verify all 30+ API models are importable from `backend/agent/schemas.py` — `CollectionResponse`, `DocumentResponse`, `ChatRequest`, `ProviderResponse`, `HealthResponse`, `ErrorResponse`, `IngestionJobResponse`, `ModelInfo`, `SettingsResponse`, `QueryTraceResponse`, etc. (import check only, no field validation) in `tests/unit/test_contracts_cross_cutting.py`
- [x] T050 [US5] Write NDJSON event model tests (FR-018): verify all 10 event models importable (`SessionEvent`, `StatusEvent`, `ChunkEvent`, `CitationEvent`, `MetaReasoningEvent`, `ConfidenceEvent`, `GroundednessEvent`, `DoneEvent`, `ClarificationEvent`, `ErrorEvent`), each is TypedDict (NOT BaseModel) in `tests/unit/test_contracts_cross_cutting.py`
- [x] T051 [US5] Write Settings config test: verify `Settings` is a `BaseSettings` subclass in `backend/config.py`, verify key fields exist (`confidence_threshold`, `meta_relevance_threshold`, `meta_variance_threshold`) in `tests/unit/test_contracts_cross_cutting.py`
- [x] T052 [US5] Run cross-cutting contract tests: `zsh scripts/run-tests-external.sh -n contracts-cross tests/unit/test_contracts_cross_cutting.py` — fix any failures

**Checkpoint**: All cross-cutting contract tests pass. Error hierarchy, schemas, events, and config validated.

---

## Phase 8: Polish — Final Gate (Wave 4)

**Purpose**: Run all contract tests together plus full regression. Verify all success criteria.

**Agent**: A5 (quality-engineer, Sonnet)

- [x] T053 Run all 6 contract test files together: `zsh scripts/run-tests-external.sh -n contracts-all tests/unit/test_contracts_agent.py tests/unit/test_contracts_storage.py tests/unit/test_contracts_retrieval.py tests/unit/test_contracts_ingestion.py tests/unit/test_contracts_providers.py tests/unit/test_contracts_cross_cutting.py` — verify all pass
- [x] T054 Run full regression test suite: `zsh scripts/run-tests-external.sh -n full-regression tests/` — verify 0 regressions against 977 existing passing tests
- [x] T055 Verify success criteria SC-001 through SC-010: confirm zero signature discrepancies (SC-001), dual confidence scale documented (SC-002), DI patterns with examples (SC-004), error hierarchy complete (SC-005), zero phantom types/methods (SC-006), 100% public method coverage on 8 classes (SC-007), all node state reads/writes documented (SC-008), contract tests pass (SC-010)
- [x] T056 Fix any failures found in T053-T055 and re-run until all gates pass

**Checkpoint**: All contract tests pass AND zero regressions. Spec 11 is complete.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories. Must validate 11-specify.md before writing tests.
- **US1 + US2 (Phase 3 + 4)**: Both depend on Phase 2 completion. **Can run in PARALLEL** (different test files, no shared state).
- **US3 (Phase 5)**: Depends on Phase 2 completion. Can run in parallel with US1/US2.
- **US4 (Phase 6)**: Depends on Phase 2 completion. Can run in parallel with earlier stories.
- **US5 (Phase 7)**: Depends on Phase 2 completion. Can run in parallel with earlier stories.
- **Polish (Phase 8)**: Depends on ALL user stories being complete.

### User Story Dependencies

- **US1 (P1)**: Independent — `test_contracts_agent.py` has no imports from other test files
- **US2 (P2)**: Independent — `test_contracts_storage.py` has no imports from other test files
- **US3 (P3)**: Independent — `test_contracts_providers.py` + `test_contracts_retrieval.py` are self-contained
- **US4 (P4)**: Independent — `test_contracts_ingestion.py` is self-contained
- **US5 (P5)**: Independent — `test_contracts_cross_cutting.py` is self-contained

### Agent Teams Wave Mapping

| Wave | Agents | Phases | Parallelism |
|------|--------|--------|-------------|
| 1 | A1 (Opus) | Phase 2 | Sequential — must complete before tests |
| 2 | A2 + A3 (Sonnet) | Phase 3 + Phase 4 | **PARALLEL** — different test files |
| 3 | A4 (Sonnet) | Phase 5 + 6 + 7 | Sequential within wave |
| 4 | A5 (Sonnet) | Phase 8 | Sequential — final gate |

### Parallel Opportunities

- T004-T011 (Phase 2 validation tasks): All marked [P] — validate different sections simultaneously
- Phase 3 (US1) + Phase 4 (US2): Different test files — full parallel execution
- T030 + T035 (US3): Provider and retrieval test file creation can be parallel
- All 5 user stories are technically parallelizable if enough agents are available

---

## Parallel Example: Wave 2

```bash
# Agent A2 (Phase 3 — US1):
# Write test_contracts_agent.py with state schemas, nodes, edges, tools, builders
# Run: zsh scripts/run-tests-external.sh -n contracts-agent tests/unit/test_contracts_agent.py

# Agent A3 (Phase 4 — US2, running simultaneously):
# Write test_contracts_storage.py with SQLiteDB, QdrantStorage, ParentStore
# Run: zsh scripts/run-tests-external.sh -n contracts-storage tests/unit/test_contracts_storage.py
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Validate 11-specify.md
3. Complete Phase 3: US1 — Agent contract tests
4. **STOP and VALIDATE**: Run `test_contracts_agent.py` — confirms agent node contracts enforced
5. This alone validates the most critical contracts (state schemas, 20 nodes, 7 edges)

### Incremental Delivery

1. Setup + Foundational → 11-specify.md validated
2. Add US1 → Agent contracts tested → partial coverage
3. Add US2 → Storage contracts tested → broadened coverage
4. Add US3 → Provider + retrieval tested → broadened coverage
5. Add US4 → Ingestion tested → broadened coverage
6. Add US5 → Error hierarchy + schemas tested → full coverage
7. Each story adds independently verifiable contract enforcement

### Agent Teams Strategy

With 4-wave Agent Teams (5 agents):

1. A1 completes Phase 2 (validate 11-specify.md)
2. A2 + A3 run in parallel (Phase 3 + Phase 4)
3. A4 completes Phase 5 + 6 + 7
4. A5 runs final gate (Phase 8)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story produces one or two test files — independently runnable
- Testing is the implementation (FR-020, FR-021) — every task produces test code
- NEVER run pytest inside Claude Code — always use `scripts/run-tests-external.sh`
- All tests use `inspect.signature()` — no external services required
- Commit after each completed test file
- Stop at any checkpoint to validate that story independently
