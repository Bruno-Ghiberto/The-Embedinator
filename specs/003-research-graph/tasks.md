# Tasks: ResearchGraph

**Input**: Design documents from `/specs/003-research-graph/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Included — plan.md Wave 4 explicitly designs test agents.

**Organization**: Tasks grouped by user story with shared foundational tasks. US2+US3 combined (iterative loop + budget enforcement are inseparable). US4+US5+US6 combined (quality features on the loop).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Scaffold)

**Purpose**: Create all new files with correct stubs, add prompts and constants. Maps to plan Wave 1 (agent-scaffold).

- [X] T001 Create `backend/retrieval/__init__.py` with package docstring
- [X] T002 [P] Create `backend/retrieval/searcher.py` with `HybridSearcher` class stub (async `search()` method signature matching R4 pattern)
- [X] T003 [P] Create `backend/retrieval/reranker.py` with `Reranker` class stub (async `rerank()` method signature matching R5 pattern)
- [X] T004 [P] Create `backend/retrieval/score_normalizer.py` with `normalize_scores()` function stub
- [X] T005 [P] Create `backend/storage/parent_store.py` with `ParentStore` class stub (async `get_by_ids()` method returning `list[ParentChunk]`)
- [X] T006 [P] Create `backend/agent/tools.py` with `create_research_tools(searcher, reranker, parent_store)` factory stub returning list of 6 `@tool` stubs per contracts/internal-contract.md
- [X] T007 [P] Create `backend/agent/research_nodes.py` with 6 node function stubs: `orchestrator`, `tools_node`, `should_compress_context`, `compress_context`, `collect_answer`, `fallback_response` — all `async def (state: ResearchState, **kwargs) -> dict`
- [X] T008 [P] Create `backend/agent/research_edges.py` with 2 edge function stubs: `should_continue_loop(state) -> str`, `route_after_compress_check(state) -> str`
- [X] T009 [P] Create `backend/agent/research_graph.py` with `build_research_graph(meta_reasoning_graph=None)` stub returning a minimal compiled StateGraph
- [X] T010 Add `ORCHESTRATOR_SYSTEM`, `ORCHESTRATOR_USER`, `COMPRESS_CONTEXT_SYSTEM`, `COLLECT_ANSWER_SYSTEM` prompt constants to `backend/agent/prompts.py`
- [X] T011 Add `MAX_ITERATIONS=10`, `MAX_TOOL_CALLS=8`, `CONFIDENCE_THRESHOLD=0.6`, `COMPRESSION_THRESHOLD=0.75` to `backend/config.py` Settings class
- [X] T012 Verify all new modules are importable: `python -c "from backend.retrieval.searcher import HybridSearcher; from backend.agent.research_graph import build_research_graph"` etc.

**Checkpoint**: All new modules importable, stubs have correct type signatures matching `state.py` and `schemas.py`.

---

## Phase 2: Foundational (Retrieval Layer + Cross-Cutting)

**Purpose**: Implement the retrieval infrastructure that ALL user stories depend on. Maps to plan Wave 2 (agent-retrieval) + confidence upgrade.

**CRITICAL**: No user story work can begin until this phase is complete.

- [X] T013 [P] Implement `HybridSearcher` class in `backend/retrieval/searcher.py`: async `search(query, collection, top_k, filters)` using Qdrant `query_points` with `prefetch` + `FusionQuery(Fusion.RRF)` per research.md R4. Accept `AsyncQdrantClient` in constructor. Use `models.Filter` for metadata filtering.
- [X] T014 [P] Implement `Reranker` class in `backend/retrieval/reranker.py`: load `CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")` once in constructor, async `rerank(query, chunks, top_k)` using `model.rank()` per research.md R5. Populate `rerank_score` on each `RetrievedChunk`.
- [X] T015 [P] Implement `normalize_scores(results_by_collection)` in `backend/retrieval/score_normalizer.py`: per-collection min-max normalization before cross-collection merge per research.md R4.
- [X] T016 [P] Implement `ParentStore` class in `backend/storage/parent_store.py`: async `get_by_ids(parent_ids)` reading from SQLite `parent_chunks` table using parameterized queries. Follow `backend/storage/sqlite_db.py` patterns.
- [X] T017 Upgrade `compute_confidence()` in `backend/agent/confidence.py`: replace placeholder with 5-signal weighted computation per research.md R8 (mean rerank 0.4, chunk count 0.2, top score 0.2, variance 0.1, coverage 0.1). New signature: `compute_confidence(chunks: list[RetrievedChunk], target_collections: list[str], expected_chunks: int = 5) -> float`.

**Checkpoint**: Retrieval layer compiles and is importable. `compute_confidence()` returns float 0.0-1.0 from retrieval signals.

---

## Phase 3: User Story 1 - Evidence Retrieval (Priority: P1) MVP

**Goal**: A research worker accepts a sub-question, searches a collection via hybrid retrieval, reranks results, generates an answer with citations and confidence score, and returns a SubAnswer.

**Independent Test**: Send a sub-question with a target collection containing known documents → verify the system returns relevant chunks, a coherent answer, citations pointing to source documents, and a confidence score > CONFIDENCE_THRESHOLD.

### Implementation for User Story 1

- [X] T018 [US1] Implement `create_research_tools()` factory in `backend/agent/tools.py`: closure-based dependency injection per research.md R6. Implement `search_child_chunks` and `cross_encoder_rerank` tools with full logic. Other 4 tools can remain stubs returning empty results.
- [X] T019 [US1] Implement `orchestrator` node in `backend/agent/research_nodes.py`: bind tools to LLM via `.bind_tools()`, invoke with ORCHESTRATOR_SYSTEM + ORCHESTRATOR_USER prompts, parse `AIMessage.tool_calls` per research.md R1. Resolve LLM from `state["llm_model"]` via provider registry. Add structlog logging (FR-017): `research_loop_start`, `orchestrator_decision`.
- [X] T020 [US1] Implement `tools_node` in `backend/agent/research_nodes.py`: dispatch each tool call from `orchestrator` response, execute via `tool_fn.ainvoke(args)`, create `ToolMessage` with matching `tool_call_id`. Merge results into `state["retrieved_chunks"]`. Increment `state["tool_call_count"]`. Add structlog logging (FR-017): `tool_call` with tool name, status, new chunk count.
- [X] T021 [US1] Implement `collect_answer` node in `backend/agent/research_nodes.py`: generate answer from `retrieved_chunks` using LLM with COLLECT_ANSWER_SYSTEM prompt. Call updated `compute_confidence(chunks, target_collections)` and convert `float→int` via `int(score * 100)`. Build `Citation` objects from `RetrievedChunk` fields. Add structlog logging (FR-017): `research_loop_end` with confidence, total chunks, iterations.
- [X] T022 [US1] Implement `should_continue_loop` edge in `backend/agent/research_edges.py`: return `"sufficient"` if `confidence_score >= CONFIDENCE_THRESHOLD`, `"continue"` otherwise. (Budget checks added in Phase 4.)
- [X] T023 [US1] Wire basic `build_research_graph()` in `backend/agent/research_graph.py`: `StateGraph(ResearchState)` with `START→orchestrator`, conditional edges from `orchestrator` via `should_continue_loop` to `tools` or `collect_answer`, `tools→orchestrator` loop, `collect_answer→END`. Compile and return.
- [X] T024 [US1] Update `backend/agent/conversation_graph.py`: pass compiled `research_graph` (from `build_research_graph()`) to `build_conversation_graph(research_graph=...)` instead of None/mock.
- [X] T025 [US1] Update `backend/main.py` lifespan: instantiate `HybridSearcher`, `Reranker`, `ParentStore` at startup. Call `create_research_tools()` to get tools list. Build research graph with tools. Pass to conversation graph builder. Load cross-encoder model at startup.
- [X] T026 [US1] Update `tests/mocks.py`: add `build_mock_research_graph()` that returns a simple compiled graph which immediately populates `answer`, `citations`, `confidence_score` with canned values.

**Checkpoint**: ResearchGraph compiles and executes a single sub-question through the full loop: orchestrator→tools→collect_answer→SubAnswer. Integration with ConversationGraph works via Send().

---

## Phase 4: User Story 2+3 - Iterative Refinement + Budget Enforcement (Priority: P2)

**Goal**: The orchestrator iterates through multiple search strategies (rephrasing, metadata filtering, cross-collection, parent context) until confidence is sufficient or budget (10 iterations / 8 tool calls) is exhausted.

**Independent Test**: (US2) Send a sub-question requiring multi-hop evidence → verify multiple tool calls with different strategies. (US3) Send a sub-question with no matches → verify termination at budget limits.

### Implementation for User Stories 2+3

- [X] T027 [P] [US2] Implement `retrieve_parent_chunks` tool in `backend/agent/tools.py`: call `ParentStore.get_by_ids()`, return `list[ParentChunk]`
- [X] T028 [P] [US2] Implement `filter_by_collection` tool in `backend/agent/tools.py`: return state modification dict constraining searches to named collection
- [X] T029 [P] [US2] Implement `filter_by_metadata` tool in `backend/agent/tools.py`: accept `filters: dict` with keys like `doc_type`, `page_range`, `source_file`, return Qdrant-compatible filter dict
- [X] T030 [P] [US2] Implement `semantic_search_all_collections` tool in `backend/agent/tools.py`: fan-out via `asyncio.gather` across all collections per research.md R4, normalize scores via `ScoreNormalizer`, merge and return sorted results
- [X] T031 [US3] Enhance `should_continue_loop` in `backend/agent/research_edges.py`: add `"exhausted"` return when `iteration_count >= MAX_ITERATIONS` or `tool_call_count >= MAX_TOOL_CALLS` or no pending tool calls (tool exhaustion per FR-007). Check budget BEFORE confidence.
- [X] T032 [US3] Increment `state["iteration_count"]` in `orchestrator` node in `backend/agent/research_nodes.py` at the start of each loop cycle
- [X] T033 [US2] Update `build_research_graph()` in `backend/agent/research_graph.py`: wire full orchestrator loop with `tools→should_compress_context→orchestrator` cycle path (compression check pass-through for now)

**Checkpoint**: Full orchestrator loop runs multiple iterations. Budget enforcement halts execution at limits. All 6 tools operational.

---

## Phase 5: User Story 4 - Deduplication (Priority: P3)

**Goal**: Track (normalized_query, parent_id) pairs and skip duplicates across iterations to ensure each retrieval adds genuinely new evidence.

**Independent Test**: Run a research worker where the same query returns overlapping results → verify no duplicate (query, parent_chunk) pairs in final result set.

### Implementation for User Story 4

- [X] T034 [US4] Add `normalize_query(query: str) -> str` and `dedup_key(query: str, parent_id: str) -> str` helper functions in `backend/agent/research_nodes.py` (or a utils module)
- [X] T035 [US4] Enhance `tools_node` in `backend/agent/research_nodes.py`: after each tool returns results, compute dedup key for each chunk, check against `state["retrieval_keys"]`, add new key to set, skip chunk if already seen. Log dedup stats via structlog: `dedup_filtered` with original count and kept count.

**Checkpoint**: Deduplication is 100% effective — duplicate (query, chunk) pairs never appear in `retrieved_chunks`.

---

## Phase 6: User Story 5 - Graceful Degradation (Priority: P3)

**Goal**: When budget is exhausted with low confidence, route to meta-reasoning (stub) or generate a fallback "insufficient information" response rather than fabricating an answer.

**Independent Test**: Send a sub-question with no relevant documents → verify fallback response (not fabricated answer) with low confidence.

### Implementation for User Story 5

- [X] T036 [US5] Implement `fallback_response` node in `backend/agent/research_nodes.py`: generate graceful "insufficient information" message using `NO_RELEVANT_INFO_RESPONSE` pattern from `prompts.py`. Set `confidence_score = 0.0`, empty citations. Log via structlog: `fallback_triggered` with sub_question and iteration/tool counts.
- [X] T037 [US5] Update `should_continue_loop` in `backend/agent/research_edges.py`: when returning `"exhausted"`, check if `meta_reasoning_graph` is available — route to `"meta_reasoning"` if yes, `"fallback_response"` if no.
- [X] T038 [US5] Wire `fallback_response→END` and `meta_reasoning` (stub) → `fallback_response` edges in `backend/agent/research_graph.py`. The meta-reasoning stub immediately forwards to fallback_response in Phase 1.
- [X] T039 [US5] Handle edge case: empty/nonexistent collection returns zero-confidence fallback immediately in `orchestrator` node (check `selected_collections` validity at loop start)

**Checkpoint**: Budget exhaustion + low confidence → fallback response, never a fabricated answer. Meta-reasoning stub wired for future spec-04.

---

## Phase 7: User Story 6 - Context Compression (Priority: P3)

**Goal**: When accumulated tokens reach 75% of model context window, compress (summarize) retrieved chunks before continuing the loop. Preserve citation references through compression.

**Independent Test**: Run a research worker that accumulates a large volume of chunks → verify compression triggers at 75%, and the research continues with compressed context.

### Implementation for User Story 6

- [X] T040 [US6] Implement `should_compress_context` node in `backend/agent/research_nodes.py`: use `count_tokens_approximately` from `langchain_core.messages.utils` per research.md R3, compare against `get_context_budget(state["llm_model"])` from existing `nodes.py`. Return routing flag (not a state mutation).
- [X] T041 [US6] Implement `compress_context` node in `backend/agent/research_nodes.py`: summarize `state["retrieved_chunks"]` via LLM call using `COMPRESS_CONTEXT_SYSTEM` prompt. Preserve citation metadata (chunk_id, source_file, parent_id) in compressed form per FR-011. Set `state["context_compressed"] = True`. Log via structlog: `context_compressed` with before/after token counts.
- [X] T042 [US6] Implement `route_after_compress_check` edge in `backend/agent/research_edges.py`: return `"compress"` if should_compress_context flagged compression needed, `"continue"` to return to orchestrator.
- [X] T043 [US6] Wire compression path in `backend/agent/research_graph.py`: `tools→should_compress_context`, conditional edges to `compress_context` or `orchestrator`, `compress_context→orchestrator`.

**Checkpoint**: Context compression fires at 75% capacity. Research continues after compression with preserved citation references.

---

## Phase 8: Tests

**Purpose**: Comprehensive unit and integration tests. Maps to plan Wave 4 (agent-unit-tests + agent-integration-tests).

### Unit Tests

- [X] T044 [P] Create `tests/unit/test_hybrid_searcher.py` + `tests/unit/test_research_tools.py`: test HybridSearcher circuit breaker, test ScoreNormalizer, test all 6 @tool functions with mocked deps
- [X] T045 [P] Create `tests/unit/test_research_tools.py`: test all 6 @tool functions with mocked searcher/reranker/parent_store. Verify correct signatures for LLM schema generation. Test closure-based injection.
- [X] T046 [P] Create `tests/unit/test_research_nodes.py`: test orchestrator (mock LLM returning tool_calls and text responses), test tools_node (mock tool execution, dedup filtering, retry-once), test collect_answer (confidence computation, citation building, float→int conversion), test compress_context (mock LLM summarization, citation preservation), test fallback_response (correct message, zero confidence), test should_compress_context (below threshold, above threshold)
- [X] T047 [P] Create `tests/unit/test_research_edges.py`: test should_continue_loop (all 3 return values: continue, sufficient, exhausted — including iteration limit, tool limit, tool exhaustion, confidence threshold), test route_after_compress_check (compress vs continue)
- [X] T048 [P] Create `tests/unit/test_research_confidence.py`: test compute_confidence with various signal combinations (all reranked, no reranked, single chunk, multi-collection, empty input). Verify output range 0.0-1.0.

### Integration Tests

- [X] T049 Create `tests/integration/test_research_graph.py`: test full graph compilation (`build_research_graph()` compiles without error). Test budget exhaustion, fallback path, deduplication, mock research graph.
- [ ] T050 Create `tests/integration/test_conversation_integration.py`: test ConversationGraph with real ResearchGraph (mock LLM + mock Qdrant). Verify Send() payload delivery, SubAnswer collection in aggregate_answers, and NDJSON streaming with research results.

**Checkpoint**: All tests pass via `zsh scripts/run-tests-external.sh`. Target: ≥80% line coverage on new code.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Fix broken tests, verify cross-cutting requirements, update documentation. Maps to plan Wave 5 (agent-polish).

- [X] T051 Fix any broken Phase 1/Phase 2 tests caused by integration changes (conversation_graph.py, main.py updates) — VERIFIED: all failures pre-existing
- [X] T052 Verify FR-016 (retry-once): confirmed via test_retry_once_on_failure — both attempts count against budget
- [X] T053 Verify FR-017 (structured logging): all 9 events present (orchestrator_start, orchestrator_decision, tool_call_complete, tool_call_failed, dedup_filtered, compress_check, context_compressed, research_loop_end, fallback_triggered)
- [X] T054 Handle edge case: orchestrator generates invalid/unsupported tool call → unknown_tool logged + skipped (test_unknown_tool_skipped)
- [X] T055 Handle edge case: all collections disabled → _no_new_tools=True → exhausted → fallback_response
- [X] T056 Update `CLAUDE.md` with spec-03 project structure additions (retrieval/, new agent files, test files)
- [X] T057 Run full test suite: 218 passed, 83 spec-03 tests green, 0 regressions (5 failures + 8 errors all pre-existing)

**Checkpoint**: All tests green. FR-016 + FR-017 verified. CLAUDE.md updated. No broken Phase 1/2 tests.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP target
- **US2+US3 (Phase 4)**: Depends on Phase 3 (needs basic loop)
- **US4 (Phase 5)**: Depends on Phase 3 (modifies tools_node)
- **US5 (Phase 6)**: Depends on Phase 4 (needs "exhausted" routing)
- **US6 (Phase 7)**: Depends on Phase 4 (inserts into loop path)
- **Tests (Phase 8)**: Depends on Phases 3-7 (tests all features)
- **Polish (Phase 9)**: Depends on Phase 8

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational)
                         ↓
                  Phase 3 (US1 - MVP)
                    ↓         ↓
         Phase 4 (US2+US3)  Phase 5 (US4)
              ↓       ↓
       Phase 6 (US5) Phase 7 (US6)
              ↓       ↓
          Phase 8 (Tests)
                ↓
          Phase 9 (Polish)
```

### Within Each User Story

- Stubs and interfaces before implementations
- Retrieval layer before tools
- Tools before nodes
- Nodes and edges before graph wiring
- Graph wiring before integration (conversation_graph, main.py)
- Core implementation before edge case handling

### Parallel Opportunities

**Phase 1** (Setup): T002-T009 can all run in parallel (different files)
**Phase 2** (Foundational): T013-T016 can all run in parallel (different files)
**Phase 4** (US2+US3): T027-T030 can all run in parallel (different tools, same file but independent functions)
**Phase 8** (Tests): T044-T048 unit tests can all run in parallel (different test files)

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Launch all retrieval layer tasks together (Wave 2 agent-retrieval):
Task: "Implement HybridSearcher in backend/retrieval/searcher.py"
Task: "Implement Reranker in backend/retrieval/reranker.py"
Task: "Implement ScoreNormalizer in backend/retrieval/score_normalizer.py"
Task: "Implement ParentStore in backend/storage/parent_store.py"
```

## Parallel Example: Phase 8 (Tests)

```bash
# Launch all unit test tasks together (Wave 4 agent-unit-tests):
Task: "Create tests/unit/test_retrieval.py"
Task: "Create tests/unit/test_tools.py"
Task: "Create tests/unit/test_research_nodes.py"
Task: "Create tests/unit/test_research_edges.py"
Task: "Create tests/unit/test_confidence.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (scaffold)
2. Complete Phase 2: Foundational (retrieval layer)
3. Complete Phase 3: US1 (basic orchestrator→tools→collect_answer)
4. **STOP and VALIDATE**: Test US1 independently via external runner
5. A single sub-question produces an answer with citations and confidence

### Incremental Delivery

1. Setup + Foundational → Retrieval layer ready
2. Add US1 → MVP: single-iteration search+answer works
3. Add US2+US3 → Full iterative loop with budget enforcement
4. Add US4 → Deduplication prevents wasted tool calls
5. Add US5 → Graceful degradation on failure (no hallucination)
6. Add US6 → Context compression for long research sessions
7. Tests → Comprehensive coverage
8. Polish → Production-ready

### Subagent Team Strategy (from plan.md)

| Wave | Phase(s) | Agents | Model | Parallel? |
|------|----------|--------|-------|-----------|
| 1 | Phase 1 | agent-scaffold | opus | No |
| 2 | Phase 2 + Phase 3-7 | agent-retrieval, agent-tools, agent-nodes | opus/sonnet | Yes (3 parallel) |
| 3 | Phase 3 (integration) | agent-integration | opus | No |
| 4 | Phase 8 | agent-unit-tests, agent-integration-tests | sonnet/opus | Yes (2 parallel) |
| 5 | Phase 9 | agent-polish | opus | No |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable after its phase
- Test execution: `zsh scripts/run-tests-external.sh -n <name> <target>` — NEVER pytest inside Claude Code
- Use `monkeypatch.setenv()` not `os.environ[]` in tests
- Use `unique_name()` helper for Qdrant collection names in integration tests
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
