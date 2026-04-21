# Tasks: MetaReasoningGraph

**Input**: Design documents from `/specs/004-meta-reasoning/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, quickstart.md
**Branch**: `004-meta-reasoning`

**Tests**: Included — plan.md Wave 5 specifies unit + integration tests.
**Testing**: NEVER run pytest inside Claude Code. Use `scripts/run-tests-external.sh` exclusively.

**Organization**: Tasks grouped by user story. US4 and US3 (P2) are placed before US1 (P1) because they are implementation dependencies — US1's `decide_strategy` requires the nodes from US3 and US4 to exist first.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup

**Purpose**: Create new file scaffolds for the MetaReasoningGraph layer

- [x] T001 Create `backend/agent/meta_reasoning_nodes.py` with module docstring, imports (`structlog`, `RunnableConfig`, `MetaReasoningState`, `settings`), and `logger = structlog.get_logger()`
- [x] T002 [P] Create `backend/agent/meta_reasoning_edges.py` with module docstring and imports
- [x] T003 [P] Create `backend/agent/meta_reasoning_graph.py` with module docstring and imports (`StateGraph`, `START`, `END`)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that ALL user stories depend on — prompts, state schema update, config thresholds

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add `GENERATE_ALT_QUERIES_SYSTEM` prompt constant to `backend/agent/prompts.py` with `{sub_question}` and `{chunk_summaries}` placeholders per spec §FR-001
- [x] T005 [P] Add `REPORT_UNCERTAINTY_SYSTEM` prompt constant to `backend/agent/prompts.py` with collections-searched, findings, suggestions structure per spec §FR-007/FR-008
- [x] T006 [P] Add `attempted_strategies: set[str]` field to `MetaReasoningState` TypedDict in `backend/agent/state.py` per data-model.md (FR-015)
- [x] T007 [P] Add `meta_relevance_threshold: float = 0.2` and `meta_variance_threshold: float = 0.15` to `Settings` class in `backend/config.py` per research decision R4

**Checkpoint**: `python -c "from backend.agent.state import MetaReasoningState; from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM; from backend.config import settings; print(settings.meta_relevance_threshold, settings.meta_variance_threshold)"` succeeds + `ruff check .` passes

---

## Phase 3: US4 - Cross-Encoder Quality Evaluation (Priority: P2, dependency for US1)

**Goal**: Quantitative retrieval quality evaluation using cross-encoder scoring via the project's `Reranker` class — not LLM self-assessment (FR-002, FR-003)

**Independent Test**: Provide chunks with known relevance, verify mean score and per-chunk scores are computed correctly

### Implementation for User Story 4

- [x] T008 [US4] Implement `evaluate_retrieval_quality` async node function in `backend/agent/meta_reasoning_nodes.py` — resolve Reranker from `config["configurable"]["reranker"]`, call `reranker.rerank(sub_question, chunks, top_k=len(chunks))` to score ALL chunks, extract `rerank_score` per chunk, compute `mean_relevance_score = sum(scores) / len(scores)`, return partial dict `{"mean_relevance_score": float, "chunk_relevance_scores": list[float]}`
- [x] T009 [US4] Add empty-chunks guard to `evaluate_retrieval_quality` in `backend/agent/meta_reasoning_nodes.py` — if `not chunks`: return `{"mean_relevance_score": 0.0, "chunk_relevance_scores": []}` (FR-013, zero-division protection)
- [x] T010 [US4] Add Reranker unavailability guard to `evaluate_retrieval_quality` in `backend/agent/meta_reasoning_nodes.py` — if `reranker is None` or reranker call raises exception: log warning, return `{"mean_relevance_score": 0.0, "chunk_relevance_scores": []}` (FR-012)
- [x] T011 [US4] Add SSE status event emission (`{"type": "meta_reasoning", "data": {"status": "Evaluating retrieval quality...", "attempt": N}}`) and structlog event (`log.info("eval_quality_complete", mean_score=..., chunk_count=...)`) to `evaluate_retrieval_quality` in `backend/agent/meta_reasoning_nodes.py` (FR-014, FR-016)

**Checkpoint**: `python -c "from backend.agent.meta_reasoning_nodes import evaluate_retrieval_quality; print('OK')"` succeeds

---

## Phase 4: US3 - Alternative Query Formulation (Priority: P2, dependency for US1)

**Goal**: Generate 3 alternative query phrasings using LLM — synonym replacement, sub-component breakdown, scope broadening (FR-001)

**Independent Test**: Provide a technical question with jargon, verify exactly 3 meaningfully different formulations are produced

**NOTE**: Phase 4 can run in parallel with Phase 3 (different functions, no dependencies)

### Implementation for User Story 3

- [x] T012 [P] [US3] Implement `generate_alternative_queries` async node function in `backend/agent/meta_reasoning_nodes.py` — resolve LLM from `config["configurable"]["llm"]`, format `GENERATE_ALT_QUERIES_SYSTEM` prompt with `sub_question` and chunk summaries, invoke LLM, parse response into exactly 3 alternatives, return `{"alternative_queries": list[str]}`
- [x] T013 [US3] Add graceful degradation to `generate_alternative_queries` in `backend/agent/meta_reasoning_nodes.py` — if LLM call fails: log warning, return `{"alternative_queries": [state["sub_question"]]}` (edge case from spec)
- [x] T014 [US3] Add SSE status event (`{"type": "meta_reasoning", "data": {"status": "Generating alternative queries...", "attempt": N}}`) and structlog event (`log.info("alt_queries_generated", count=3, session_id=...)`) to `generate_alternative_queries` in `backend/agent/meta_reasoning_nodes.py` (FR-014, FR-016)

**Checkpoint**: `python -c "from backend.agent.meta_reasoning_nodes import generate_alternative_queries; print('OK')"` succeeds

---

## Phase 5: US1 - Automatic Recovery from Poor Retrieval (Priority: P1) + US5 - Recursion Protection (Priority: P2)

**Goal**: Strategy selection based on quantitative evaluation signals, with concrete `modified_state` for ResearchGraph retry. Bounded by configurable max attempts with strategy deduplication.

**Independent Test (US1)**: Create collection with relevant docs, ask question requiring collection switch or filter relaxation, verify recovery within 2 attempts
**Independent Test (US5)**: Provide unanswerable query (empty collection), verify max 2 attempts then uncertainty report

**NOTE**: US1 and US5 are combined because `decide_strategy` implements both — strategy selection (US1) plus recursion guards and dedup (US5) are interleaved logic in one function.

### Implementation for User Story 1 + 5

- [x] T015 [US1] Implement `_build_modified_state` helper function for WIDEN_SEARCH strategy in `backend/agent/meta_reasoning_nodes.py` — returns `{"selected_collections": "ALL", "top_k_retrieval": 40}` with `alternative_queries` from state (FR-005). Note: "ALL" means the wrapper node (T029) must iterate over all available collections and merge results.
- [x] T016 [P] [US1] Implement `_build_modified_state` helper function for CHANGE_COLLECTION strategy in `backend/agent/meta_reasoning_nodes.py` — returns `{"selected_collections": "ROTATE", "sub_question": alternative_queries[0]}` (FR-005). Note: "ROTATE" means select the next collection from available_collections that is not the current one; if only one collection exists, the wrapper node (T029) should fall through to report_uncertainty.
- [x] T017 [P] [US1] Implement `_build_modified_state` helper function for RELAX_FILTERS strategy in `backend/agent/meta_reasoning_nodes.py` — returns `{"top_k_retrieval": 40, "payload_filters": None, "top_k_rerank": 10}` (FR-005)
- [x] T018 [US1] Implement `decide_strategy` async node function in `backend/agent/meta_reasoning_nodes.py` — compute `score_variance = statistics.stdev(scores)` (guard `len(scores) < 2` → 0.0), read `settings.meta_relevance_threshold` and `settings.meta_variance_threshold`, select candidate strategy per decision logic table in plan.md, call `_build_modified_state`, return `{"recovery_strategy": str, "modified_state": dict, "meta_attempt_count": N+1, "attempted_strategies": updated_set}` (FR-004)
- [x] T019 [US5] Add max_attempts guard to `decide_strategy` in `backend/agent/meta_reasoning_nodes.py` — if `meta_attempt_count >= settings.meta_reasoning_max_attempts`: return `{"recovery_strategy": None}` to force `report_uncertainty` (FR-006)
- [x] T020 [US5] Add strategy deduplication to `decide_strategy` in `backend/agent/meta_reasoning_nodes.py` — if selected candidate is in `attempted_strategies`: try next strategy from fallback order `["WIDEN_SEARCH", "CHANGE_COLLECTION", "RELAX_FILTERS"]`; if none untried: return `{"recovery_strategy": None}` (FR-015)
- [x] T021 [US1] Add structlog event to `decide_strategy` in `backend/agent/meta_reasoning_nodes.py` — `log.info("strategy_selected", strategy=..., mean_score=..., variance=..., chunk_count=..., attempt=...)` (FR-016)

**Checkpoint**: `python -c "from backend.agent.meta_reasoning_nodes import decide_strategy; print('OK')"` succeeds + all 4 node functions importable

---

## Phase 6: US2 - Honest Uncertainty Reporting (Priority: P1)

**Goal**: Generate transparent, actionable uncertainty reports when all recovery strategies fail — no fabrication, no guessing (FR-007, FR-008)

**Independent Test**: Ask about non-existent topic, verify report names collections searched, summarizes findings, suggests user actions, does NOT fabricate

### Implementation for User Story 2

- [x] T022 [US2] Implement `report_uncertainty` async node function in `backend/agent/meta_reasoning_nodes.py` — resolve LLM from `config["configurable"]["llm"]`, build prompt from `REPORT_UNCERTAINTY_SYSTEM` with state context (sub_question, collections from retrieved_chunks, alternative_queries tried, mean_relevance_score, meta_attempt_count), invoke LLM, return `{"answer": str, "uncertainty_reason": str}`
- [x] T023 [US2] Verify that `REPORT_UNCERTAINTY_SYSTEM` prompt constant (created in T005) includes the no-fabrication guardrail: "Do NOT fabricate an answer. Do NOT say 'based on the available context' and then guess." If missing from T005's prompt, add it directly to the constant in `backend/agent/prompts.py` (FR-008)
- [x] T024 [US2] Add SSE status event (`{"type": "meta_reasoning", "data": {"status": "Could not find sufficient evidence", "attempt": N}}`) and structlog event to `report_uncertainty` in `backend/agent/meta_reasoning_nodes.py` (FR-014, FR-016)

**Checkpoint**: All 4 node functions (`generate_alternative_queries`, `evaluate_retrieval_quality`, `decide_strategy`, `report_uncertainty`) importable from `backend.agent.meta_reasoning_nodes` + `ruff check .` passes

---

## Phase 7: US6 - Seamless Integration with ResearchGraph (Priority: P3)

**Goal**: Wire MetaReasoningGraph as subgraph in ResearchGraph, replacing `"exhausted"` → `fallback_response` with `"exhausted"` → `meta_reasoning` (FR-009, FR-010)

**Independent Test**: Run full end-to-end query triggering meta-reasoning, verify graph compiles, routing reaches meta-reasoning, modified state flows back

### Implementation for User Story 6

- [x] T025 [US6] Implement `route_after_strategy` conditional edge function in `backend/agent/meta_reasoning_edges.py` — return `"retry"` if `state["recovery_strategy"]` is set, `"report"` if `None`
- [x] T026 [US6] Implement `build_meta_reasoning_graph()` function in `backend/agent/meta_reasoning_graph.py` — `StateGraph(MetaReasoningState)`, add 4 nodes, add edges: `START → generate_alternative_queries → evaluate_retrieval_quality → decide_strategy`, add conditional edge from `decide_strategy` via `route_after_strategy`: `"retry" → END`, `"report" → report_uncertainty → END`, return `graph.compile()`
- [x] T027 [US6] Verify `should_continue_loop` in `backend/agent/research_edges.py` already returns `"exhausted"` string (it does). Confirm routing in `build_research_graph` already directs `"exhausted"` → `meta_reasoning` when `meta_reasoning_graph` is provided (already wired). No code changes expected — this is a verification task. (FR-009)
- [x] T028 [US6] Add `meta_reasoning_max_attempts == 0` guard to `build_research_graph` in `backend/agent/research_graph.py` — when `max_attempts == 0`, do not pass the meta_reasoning_graph (or pass None), so routing keeps `"exhausted"` → `fallback_response` to preserve current behavior (FR-011). The guard belongs at the graph-building level, not in the edge function.
- [x] T029 [US6] Add ResearchState↔MetaReasoningState mapper logic to the existing `meta_reasoning` node in `backend/agent/research_graph.py` — `build_research_graph` already accepts `meta_reasoning_graph: Any = None` and wires the routing. The new work is: (1) map ResearchState fields into MetaReasoningState input, (2) invoke the compiled subgraph, (3) on recovery (recovery_strategy set): apply `modified_state` back to ResearchState — interpret "ALL" as iterate-all-collections, interpret "ROTATE" as next-collection (fall through to uncertainty if only one collection), (4) on uncertainty (recovery_strategy None): set `answer` from subgraph + `confidence_score=0.0` (FR-010)
- [x] T030 [US6] Update `main.py` lifespan to build graphs inside-out in `backend/main.py` — `meta_reasoning_graph = build_meta_reasoning_graph()` → pass to `build_research_graph(meta_reasoning_graph=...)` → pass to `build_conversation_graph(...)` (FR-009)
- [x] T031 [US6] Handle infrastructure error during retry in `meta_reasoning` wrapper node in `backend/agent/research_graph.py` — if ResearchGraph retry raises infrastructure exception, route to `report_uncertainty` with error noted (FR-017)

**Checkpoint**: `python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; g = build_meta_reasoning_graph(); print('compiled')"` succeeds + full graph chain compiles

---

## Phase 8: Tests

**Purpose**: Unit tests + integration tests for all MetaReasoningGraph components

**CRITICAL**: Run ALL tests via `scripts/run-tests-external.sh` — NEVER run pytest inside Claude Code.

### Unit Tests

- [x] T032 [P] Write unit tests for `evaluate_retrieval_quality` in `tests/unit/test_meta_reasoning_nodes.py` — test: scores all chunks, computes correct mean, handles empty chunks (FR-013), handles Reranker unavailability (FR-012), handles Reranker exception
- [x] T033 [P] Write unit tests for `generate_alternative_queries` in `tests/unit/test_meta_reasoning_nodes.py` — test: produces exactly 3 alternatives, graceful LLM failure degrades to original query, SSE event emitted
- [x] T034 [P] Write unit tests for `decide_strategy` in `tests/unit/test_meta_reasoning_nodes.py` — test: WIDEN_SEARCH (low mean + few chunks), CHANGE_COLLECTION (low mean + many chunks), RELAX_FILTERS (moderate mean + high variance), report_uncertainty path (moderate mean + low variance), max_attempts guard (FR-006), strategy dedup (FR-015), configurable thresholds, score_variance < 2 scores guard, identical scores edge case (all scores equal → stdev=0.0, verify low-mean path still selects WIDEN_SEARCH/CHANGE_COLLECTION based on chunk count, not report_uncertainty)
- [x] T035 [P] Write unit tests for `report_uncertainty` in `tests/unit/test_meta_reasoning_nodes.py` — test: includes collections searched, includes suggestions, does NOT fabricate answers (FR-008)
- [x] T036 [P] Write unit tests for `route_after_strategy` in `tests/unit/test_meta_reasoning_edges.py` — test: returns "retry" when recovery_strategy set, returns "report" when None

### Integration Tests

- [x] T037 [P] Write integration test for graph compilation in `tests/integration/test_meta_reasoning_graph.py` — verify `build_meta_reasoning_graph()` compiles without error, graph has expected nodes
- [x] T038 [P] Write integration test for recovery flow in `tests/integration/test_meta_reasoning_graph.py` — end-to-end: low-relevance chunks → WIDEN_SEARCH → modified_state returned
- [x] T039 [P] Write integration test for uncertainty flow in `tests/integration/test_meta_reasoning_graph.py` — end-to-end: max attempts exceeded → report_uncertainty → answer + uncertainty_reason
- [x] T040 [P] Write integration test for strategy dedup across attempts in `tests/integration/test_meta_reasoning_graph.py` — first attempt selects strategy A, second attempt with A in attempted_strategies selects strategy B
- [x] T041[P] Write integration test for `max_attempts=0` bypass in `tests/integration/test_meta_reasoning_graph.py` — verify should_continue_loop routes to fallback_response when disabled (FR-011)
- [x] T041a [P] Write integration test for infrastructure error during retry in `tests/integration/test_meta_reasoning_graph.py` — mock ResearchGraph retry to raise `ConnectionError`, verify `report_uncertainty` is produced with error noted in `uncertainty_reason` (FR-017)

### Test Execution

- [x] T042 Run unit tests via external runner: `zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py` — poll `cat Docs/Tests/spec04-unit.status`, read `cat Docs/Tests/spec04-unit.summary`
- [x] T043 Run integration tests via external runner: `zsh scripts/run-tests-external.sh -n spec04-integration tests/integration/test_meta_reasoning_graph.py` — poll `cat Docs/Tests/spec04-integration.status`, read `cat Docs/Tests/spec04-integration.summary`

**Checkpoint**: All spec-04 tests pass via external runner

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Regression validation and cleanup

- [x] T044 Run full regression test suite via external runner: `zsh scripts/run-tests-external.sh -n spec04-regression tests/` — verify no regressions across specs 01-03
- [x] T045 [P] Add `META_RELEVANCE_THRESHOLD`, `META_VARIANCE_THRESHOLD` entries to `.env.example` with comments
- [x] T046 Verify `ruff check .` passes on all new and modified files

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — BLOCKS all user stories
- **US4 (Phase 3)**: Depends on Phase 2 — evaluate_retrieval_quality node
- **US3 (Phase 4)**: Depends on Phase 2 — **can run parallel with Phase 3**
- **US1+US5 (Phase 5)**: Depends on Phase 3 + Phase 4 — decide_strategy uses evaluation scores + alt queries
- **US2 (Phase 6)**: Depends on Phase 2 only — but logically follows Phase 5 (report_uncertainty is the fallback)
- **US6 (Phase 7)**: Depends on Phases 3–6 — wires all nodes into graphs
- **Tests (Phase 8)**: Depends on Phase 7 — tests verify full implementation
- **Polish (Phase 9)**: Depends on Phase 8 — regression validation

### User Story Dependencies

- **US4 (P2)**: After Foundational — no dependency on other stories. Implementation dependency for US1.
- **US3 (P2)**: After Foundational — no dependency on other stories. Implementation dependency for US1. **Can run parallel with US4.**
- **US1+US5 (P1+P2)**: After US3 + US4 — decide_strategy uses evaluation results and alternative queries
- **US2 (P1)**: After Foundational — independent, but logically placed after US1 (uncertainty is the fallback path)
- **US6 (P3)**: After all other stories — integration wires everything together

### Within Each User Story

- SSE events + structlog added alongside core logic (not separate tasks per FR-014/FR-016)
- Guards and edge cases added as separate tasks within the story phase
- All nodes follow `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict` convention

### Parallel Opportunities

- **Phase 1**: T002, T003 parallel with T001 (different files)
- **Phase 2**: T005, T006, T007 parallel with T004 (different files or different sections)
- **Phase 3 + Phase 4**: Entirely parallel (different nodes, no dependencies)
- **Phase 5**: T016, T017 parallel (different helper functions)
- **Phase 8**: All test tasks T032–T041 parallel (different test files/classes)

---

## Parallel Example: Phase 3 + Phase 4 (Wave 2)

```bash
# These two phases run as parallel subagents:
# Agent A2: Phase 3 (US4 — evaluate_retrieval_quality)
# Agent A3: Phase 4 (US3 — generate_alternative_queries)

# Agent A2 tasks: T008, T009, T010, T011
# Agent A3 tasks: T012, T013, T014
```

## Parallel Example: Phase 8 (Wave 5)

```bash
# Unit and integration test agents run in parallel:
# Agent A6: T032, T033, T034, T035, T036 (unit tests)
# Agent A7: T037, T038, T039, T040, T041 (integration tests)

# Then sequential:
# T042: Run unit test suite
# T043: Run integration test suite
# T044: Run regression suite
```

---

## Subagent Team Mapping

Tasks map to the 7 agents from plan.md:

| Agent | Wave | Tasks | Files |
|-------|------|-------|-------|
| A1 | 1 | T001–T007 | prompts.py, state.py, config.py, scaffolds |
| A2 | 2 | T008–T011 | meta_reasoning_nodes.py (eval+strategy setup) |
| A3 | 2 | T012–T014 | meta_reasoning_nodes.py (query+uncertainty setup) |
| A2 | 2 | T015–T021 | meta_reasoning_nodes.py (decide_strategy) |
| A3 | 2 | T022–T024 | meta_reasoning_nodes.py (report_uncertainty) |
| A4 | 3 | T025–T026 | meta_reasoning_edges.py, meta_reasoning_graph.py |
| A5 | 4 | T027–T031 | research_edges.py, research_graph.py, main.py |
| A6 | 5 | T032–T036 | test_meta_reasoning_nodes.py, test_meta_reasoning_edges.py |
| A7 | 5 | T037–T041 | test_meta_reasoning_graph.py |

Instruction files at: `Docs/PROMPTS/spec-04-meta-reasoning/agents/`

---

## Implementation Strategy

### MVP First (US4 + US3 + US1 + US5)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (BLOCKS all stories)
3. Complete Phase 3: US4 (cross-encoder eval) + Phase 4: US3 (alt queries) **in parallel**
4. Complete Phase 5: US1+US5 (strategy selection + recursion protection)
5. **STOP and VALIDATE**: decide_strategy can select all 3 strategies correctly, max_attempts guard works
6. Continue to Phase 6: US2 (uncertainty reporting)

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US4 + US3 → Building-block nodes ready
3. US1 + US5 → Core strategy logic ready → **First testable increment**
4. US2 → Uncertainty reporting ready → **Complete node layer**
5. US6 → Integration wired → **Full feature E2E testable**
6. Tests + Polish → **Production ready**

### Subagent Wave Strategy

With agent teams (from plan.md):

1. **Wave 1** (A1): Foundation tasks T001–T007 → Checkpoint
2. **Wave 2** (A2 + A3 parallel): Node tasks T008–T024 → Checkpoint
3. **Wave 3** (A4): Edges + graph T025–T026 → Checkpoint
4. **Wave 4** (A5): Integration T027–T031 → Checkpoint
5. **Wave 5** (A6 + A7 parallel): Tests T032–T043 → Checkpoint
6. **Final**: Polish T044–T046

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- US4 and US3 precede US1 despite lower priority because US1's decide_strategy requires their nodes
- Config param type: `config: RunnableConfig = None` — NOT `RunnableConfig | None` (LangGraph quirk)
- Return type: `dict` (partial state update) — NOT full `MetaReasoningState`
- Python 3.14+ syntax: `list[str]`, `str | None` — NOT `List[str]`, `Optional[str]`
- **NEVER run pytest inside Claude Code** — always use `zsh scripts/run-tests-external.sh`
- Checkpoint gates between waves: next wave does NOT start until previous wave's tests pass
