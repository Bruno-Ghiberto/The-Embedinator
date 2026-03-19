# Tasks: ConversationGraph — Agent Layer 1

**Input**: Design documents from `/specs/002-conversation-graph/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/chat-api.md ✅, quickstart.md ✅

**Tests**: Included — Constitution Principle IV mandates ≥80% backend line coverage.

**Organization**: Tasks grouped by user story. Each phase is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase
- **[Story]**: Which user story this task belongs to (US1–US4)
- File paths are relative to repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependency, create file shells, set up test infrastructure.

- [x] T001 Add `langgraph-checkpoint-sqlite>=2.0` to `requirements.txt` and run `pip install -r requirements.txt`
- [x] T002 [P] Create `backend/agent/nodes.py` with module-level imports and empty stub functions for all 11 nodes: `init_session`, `classify_intent`, `rewrite_query`, `request_clarification`, `fan_out`, `aggregate_answers`, `verify_groundedness`, `validate_citations`, `summarize_history`, `format_response`, `handle_collection_mgmt` — each raises `NotImplementedError`
- [x] T003 [P] Create `backend/agent/edges.py` with module-level imports and empty stub functions: `route_intent`, `should_clarify`, `route_fan_out` — each raises `NotImplementedError`
- [x] T004 [P] Create `backend/agent/conversation_graph.py` with module-level imports and empty `build_conversation_graph(research_graph, checkpointer=None)` stub
- [x] T005 Create `tests/mocks.py` with `build_mock_research_graph()` — a compiled LangGraph `StateGraph(ResearchState)` with a single node that returns a fixed `SubAnswer` with one `Citation` and `confidence_score=0.85`

**Checkpoint**: File structure exists. All stubs importable without errors.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: State schema, prompts, edge functions, and `init_session` node — must be complete before any user story can be wired.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T006 Add `intent: str` field to `ConversationState` TypedDict in `backend/agent/state.py` — place after `embed_model`, add inline comment `# "rag_query" | "collection_mgmt" | "ambiguous"`, default value `"rag_query"`
- [x] T007 Add 7 new prompt constants to `backend/agent/prompts.py` verbatim from `Docs/PROMPTS/spec-02-conversation-graph/02-specify.md`: `CLASSIFY_INTENT_SYSTEM`, `CLASSIFY_INTENT_USER`, `REWRITE_QUERY_SYSTEM`, `REWRITE_QUERY_USER`, `VERIFY_GROUNDEDNESS_SYSTEM`, `FORMAT_RESPONSE_SYSTEM`, `SUMMARIZE_HISTORY_SYSTEM`
- [x] T008 Add `MODEL_CONTEXT_WINDOWS: dict[str, int]` lookup dict and `get_context_budget(model_name: str) -> int` function to `backend/agent/nodes.py` — budget is `int(window * 0.75)` where window defaults to `32_768` for unknown models; cover: `qwen2.5:7b` (32768), `llama3.1:8b` (131072), `mistral:7b` (32768), `gpt-4o` (131072), `gpt-4o-mini` (131072), `claude-sonnet-4-20250514` (200000)
- [x] T009 [P] Implement `route_intent(state: ConversationState) -> str` in `backend/agent/edges.py` — returns `state["intent"]`; used as routing key for `add_conditional_edges`
- [x] T010 [P] Implement `should_clarify(state: ConversationState) -> bool` in `backend/agent/edges.py` — returns `not state["query_analysis"].is_clear and state["iteration_count"] < 2`; if `query_analysis` is `None` returns `False`
- [x] T011 Implement `route_fan_out(state: ConversationState) -> list[Send]` in `backend/agent/edges.py` — returns `[Send("research", {...})]` for each sub-question in `query_analysis.sub_questions`; if list is empty falls back to `[state["messages"][-1].content]` as sole sub-question; uses `collections_hint or selected_collections` for each Send payload; include full ResearchState fields from `data-model.md`
- [x] T012 Implement `init_session(state: ConversationState, *, db) -> dict` in `backend/agent/nodes.py` — load session row from SQLite `sessions` table by `session_id`; restore `messages` (deserialize JSON), `selected_collections`, `llm_model`, `embed_model`; on any exception create fresh session and log `structlog` warning with `session_id`
- [x] T013 [P] Write unit tests for `route_intent` in `tests/unit/test_edges.py` — test each of the 3 routing values
- [x] T014 [P] Write unit tests for `should_clarify` in `tests/unit/test_edges.py` — test `is_clear=True`, `is_clear=False` with count <2, `is_clear=False` with count=2, `query_analysis=None`
- [x] T015 Write unit tests for `init_session` in `tests/unit/test_nodes.py` — mock `aiosqlite`, test successful load, SQLite failure fallback, missing session (fresh create)

**Checkpoint**: Foundation ready. `pytest tests/unit/` passes. User story phases can begin.

---

## Phase 3: User Story 1 — Intelligent Query Routing (Priority: P1) 🎯 MVP

**Goal**: Every user message is classified as `rag_query`, `collection_mgmt`, or `ambiguous` and routed correctly. The partial graph compiles and runs end-to-end for the routing path.

**Independent Test**: POST `/api/chat` with (1) a document question, (2) `"list my collections"`, (3) `"help me"`. Verify NDJSON responses reflect correct routing for each.

- [x] T016 [P] [US1] Implement `classify_intent(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` — format `CLASSIFY_INTENT_USER` with last message + conversation history + selected collections; call LLM; parse JSON response for `{"intent": "..."}` key; write `state["intent"]`; on any exception default to `"rag_query"` and log warning
- [x] T017 [P] [US1] Implement `handle_collection_mgmt(state: ConversationState) -> dict` stub in `backend/agent/nodes.py` — sets `final_response` to `"Collection management is not yet implemented. Please use the Collections page."` and `confidence_score` to `0`
- [x] T018 [US1] Wire US1 subgraph in `backend/agent/conversation_graph.py`: add `init_session`, `classify_intent`, `handle_collection_mgmt` nodes; add `START → init_session → classify_intent`; add `add_conditional_edges("classify_intent", route_intent, {"rag_query": "rewrite_query", "collection_mgmt": "handle_collection_mgmt", "ambiguous": "request_clarification"})`; add `handle_collection_mgmt → END`; compile with `MemorySaver()` as temporary checkpointer
- [x] T019 [P] [US1] Write unit tests for `classify_intent` in `tests/unit/test_nodes.py` — mock LLM returning `{"intent": "rag_query"}`, `{"intent": "collection_mgmt"}`, `{"intent": "ambiguous"}`; test LLM failure defaults to `"rag_query"`
- [x] T020 [P] [US1] Write unit tests for `handle_collection_mgmt` in `tests/unit/test_nodes.py` — verify `final_response` is set and `confidence_score` is `0`

**Checkpoint**: US1 complete. `classify_intent` routes correctly for all 3 intent types. Tests pass.

---

## Phase 4: User Story 2 — Complex Query Decomposition (Priority: P2)

**Goal**: Complex queries are decomposed into 1–5 sub-questions, dispatched to ResearchGraph instances in parallel, results aggregated with deduplicated citations, and formatted as an NDJSON response with inline citation markers and confidence score.

**Independent Test**: Ask `"Compare the security requirements and the API design in my documents"`. Verify the NDJSON response contains a `metadata` frame with ≥2 citations from different passages, and `confidence` is an integer 0–100.

- [x] T021 [P] [US2] Implement `rewrite_query(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` — format `REWRITE_QUERY_USER` with last message + collections + conversation context; call `llm.with_structured_output(QueryAnalysis)`; on `ValidationError` retry once with simplified single-question prompt; on second failure construct `QueryAnalysis(is_clear=True, sub_questions=[original_query], complexity_tier="lookup", collections_hint=[], clarification_needed=None)`; write `state["query_analysis"]`
- [x] T022 [P] [US2] Implement `aggregate_answers(state: ConversationState) -> dict` in `backend/agent/nodes.py` — collect all `SubAnswer` objects from `state["sub_answers"]`; merge answer texts with sub-question headers; deduplicate citations by `passage_id` keeping highest `relevance_score`; compute `confidence_score` as `int(weighted_avg * 100)` using `compute_confidence()` from `backend/agent/confidence.py`; write `state["final_response"]` and `state["citations"]`
- [x] T023 [P] [US2] Implement `verify_groundedness(state: ConversationState, *, llm) -> dict` Phase 2 stub in `backend/agent/nodes.py` — immediately returns `{"groundedness_result": None}`; add `# Phase 2: implement NLI-based claim verification` comment
- [x] T024 [P] [US2] Implement `validate_citations(state: ConversationState, *, reranker) -> dict` Phase 2 stub in `backend/agent/nodes.py` — immediately returns `{"citations": state["citations"]}`; add `# Phase 2: implement cross-encoder citation alignment (threshold=0.3)` comment
- [x] T025 [US2] Implement `format_response(state: ConversationState) -> dict` in `backend/agent/nodes.py` — call `FORMAT_RESPONSE_SYSTEM` with final_response + citations as numbered list `[1] passage_text…`; apply inline `[N]` citation markers by matching citation indices; append confidence summary if `confidence_score < 70`; handle `groundedness_result=None` (Phase 1: skip annotation); update `state["final_response"]`
- [x] T026 [US2] Wire full RAG path in `backend/agent/conversation_graph.py`: add `rewrite_query`, `research` (mock subgraph), `aggregate_answers`, `verify_groundedness`, `validate_citations`, `format_response` nodes; add `add_conditional_edges("rewrite_query", should_clarify, {True: "request_clarification", False: "fan_out"})`; add `add_conditional_edges("rewrite_query", route_fan_out)` for Send dispatch; add sequential edges `research → aggregate_answers → verify_groundedness → validate_citations → format_response → END`
- [x] T027 [P] [US2] Write unit tests for `rewrite_query` in `tests/unit/test_nodes.py` — mock LLM with structured output; test valid QueryAnalysis, ValidationError fallback, factoid query not decomposed unnecessarily (1 sub-question)
- [x] T028 [P] [US2] Write unit tests for `aggregate_answers` in `tests/unit/test_nodes.py` — test citation deduplication (same passage_id keeps highest score), confidence score computation, empty sub_answers fallback
- [x] T029 [P] [US2] Write unit tests for `format_response` in `tests/unit/test_nodes.py` — test inline citation markers [1][2], confidence summary shown when < 70, groundedness_result=None skips annotation
- [x] T030 [US2] Write integration test for full RAG path in `tests/integration/test_conversation_graph.py` using mock ResearchGraph — submit a complex question, verify metadata frame contains `confidence` (int 0–100) and `citations` list

**Checkpoint**: US2 complete. Full RAG path runs end-to-end with mock ResearchGraph. Citations and confidence in output.

---

## Phase 5: User Story 3 — Conversation Continuity (Priority: P3)

**Goal**: Follow-up questions are answered in context of prior messages. Sessions persist across requests. History is compressed when approaching the model's context window.

**Independent Test**: POST three messages in sequence using same `session_id`. Third message references "the first point". Verify response is contextually relevant. After 20+ exchanges, verify no context overflow error occurs.

- [x] T031 [P] [US3] Implement `summarize_history(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` — import `count_tokens_approximately` from `langchain_core.messages.utils`; check if token count > `get_context_budget(state["llm_model"])`; if yes, call LLM with `SUMMARIZE_HISTORY_SYSTEM` to produce summary of oldest 50% of messages; replace old messages with `[SystemMessage(content=summary)] + recent_messages`; write `state["messages"]`; on LLM failure return unchanged state and log warning
- [x] T032 [US3] Add `AsyncSqliteSaver` checkpointer to app lifespan in `backend/main.py` — import from `langgraph.checkpoint.sqlite.aio`; open `AsyncSqliteSaver.from_conn_string("data/checkpoints.db")` in lifespan context manager; store in `app.state.checkpointer`; pass to `build_conversation_graph()` call
- [x] T033 [US3] Update `build_conversation_graph()` in `backend/agent/conversation_graph.py` — replace `MemorySaver()` with the injected `checkpointer` parameter; add `summarize_history` node after `validate_citations` and before `format_response`; add edge `validate_citations → summarize_history → format_response`
- [x] T034 [P] [US3] Write unit tests for `summarize_history` in `tests/unit/test_nodes.py` — test no-op when under 75% budget, compression triggered when over budget, LLM failure returns unchanged messages
- [x] T035 [US3] Write integration test for session continuity in `tests/integration/test_conversation_graph.py` — submit question + follow-up with same `thread_id`; verify follow-up answer references prior context from `state["messages"]`

**Checkpoint**: US3 complete. Sessions persist, follow-up questions use history, long conversations compress gracefully.

---

## Phase 6: User Story 4 — Clarification When Needed (Priority: P4)

**Goal**: Ambiguous queries trigger a clarification interrupt. The graph checkpoints state to SQLite. When the user responds, the graph resumes from the checkpoint without restarting.

**Independent Test**: POST `"What about the data?"` with no prior context. Verify a `{"type":"clarification","question":"..."}` NDJSON frame is returned. POST a follow-up with same `session_id`. Verify the system resumes and produces an answer.

- [x] T036 [P] [US4] Implement `request_clarification(state: ConversationState) -> dict` in `backend/agent/nodes.py` — extract clarification question from `state["query_analysis"].clarification_needed`; call `interrupt(clarification_question)` from `langgraph.types`; when execution resumes (user response in `Command(resume=response)`), append user response as `HumanMessage` to `state["messages"]`; increment `state["iteration_count"]`; return updated state dict
- [x] T037 [US4] Wire clarification path in `backend/agent/conversation_graph.py` — verify `request_clarification` node is connected: `request_clarification` routes back to `classify_intent` (allows re-classification after clarification); the `should_clarify` edge already caps at 2 rounds via `iteration_count`; ensure graph is compiled with the `AsyncSqliteSaver` checkpointer (required for interrupt persistence)
- [x] T038 [P] [US4] Write unit tests for `request_clarification` in `tests/unit/test_nodes.py` — mock `interrupt()`; test that clarification question from `query_analysis.clarification_needed` is passed to interrupt; test `iteration_count` increments
- [x] T039 [US4] Write integration test for clarification interrupt/resume in `tests/integration/test_conversation_graph.py` — submit ambiguous query; verify `__interrupt__` in graph state; call `graph.invoke(Command(resume="the user clarification"), config)`; verify graph produces an answer; verify `iteration_count` is 1
- [x] T040 [US4] Write integration test for 2-round clarification cap in `tests/integration/test_conversation_graph.py` — trigger clarification twice with still-ambiguous responses; verify on third attempt `should_clarify` returns `False` (cap reached) and graph proceeds to `fan_out` with best-effort interpretation

**Checkpoint**: US4 complete. Graph pauses for clarification, checkpoints to SQLite, resumes correctly. 2-round cap enforced.

---

## Phase 7: Chat API Refactor & Integration

**Purpose**: Replace the existing direct RAG pipeline in `chat.py` with ConversationGraph invocation. This phase wires everything together and validates the full end-to-end flow.

- [x] T041 Refactor `backend/api/chat.py` to import and invoke `build_conversation_graph()` — build initial `ConversationState` from request fields: `session_id`, `messages=[HumanMessage(request.message)]`, `selected_collections=request.collection_ids`, `llm_model`, `embed_model`, `intent="rag_query"` (default), `query_analysis=None`, `sub_answers=[]`, `citations=[]`, `groundedness_result=None`, `confidence_score=0`, `iteration_count=0`, `final_response=None`
- [x] T042 Implement NDJSON streaming in `backend/api/chat.py` — replace direct LLM streaming with `async for chunk, metadata in graph.astream(state, stream_mode="messages", config={"configurable": {"thread_id": session_id}}):`; yield `json.dumps({"type":"chunk","text":chunk.content}) + "\n"` for each `AIMessageChunk` with non-empty content; detect `"__interrupt__"` key in metadata and yield `json.dumps({"type":"clarification","question":value}) + "\n"` then return
- [x] T043 Implement metadata frame in `backend/api/chat.py` — after stream completes, call `graph.get_state(config).values` to get final state; yield `json.dumps({"type":"metadata","trace_id":trace_id,"confidence":final_state["confidence_score"],"citations":[c.model_dump() for c in final_state["citations"]],"latency_ms":latency_ms}) + "\n"`; preserve existing `query_trace` SQLite write (Constitution Principle IV)
- [x] T044 Add empty-collections guard in `backend/api/chat.py` — before invoking graph, if `request.collection_ids` is empty yield `json.dumps({"type":"error","message":"Please select at least one collection before searching.","code":"NO_COLLECTIONS"}) + "\n"` and return
- [x] T045 Get checkpointer from `app.state.checkpointer` in `backend/api/chat.py` and pass to `build_conversation_graph(research_graph=get_research_graph_stub(), checkpointer=app.state.checkpointer)`; use `app.state` for graph instance caching
- [x] T046 Write integration test for full chat endpoint in `tests/integration/test_conversation_graph.py` using `httpx.AsyncClient` and `TestClient` — POST `/api/chat` with a valid request; parse NDJSON stream; verify chunk frames arrive, metadata frame is last, `confidence` is 0–100 integer, `citations` list is present
- [x] T047 Write integration test for error paths in `tests/integration/test_conversation_graph.py` — empty message (HTTP 400), no collections selected (error frame), all sub-questions fail (error frame with gap message)

**Checkpoint**: Full chat endpoint operational end-to-end with ConversationGraph.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Coverage verification, constitution compliance checks, and documentation.

- [x] T048 Run `pytest --cov=backend --cov-report=term-missing` and verify ≥80% line coverage; add targeted unit tests for any uncovered branches in `nodes.py` or `edges.py`
- [x] T049 [P] Verify all NDJSON output frames match `contracts/chat-api.md` schema — write a frame-schema validation helper in `tests/unit/test_ndjson_frames.py` that parses each frame type and validates required fields
- [x] T050 [P] Add `source_removed: bool` field to Citation serialization in `format_response` — check document deletion status before building metadata frame (Constitution Principle IV requires `source_removed: true` indicator)
- [x] T051 Run `quickstart.md` validation steps manually — verify graph compiles, mock ResearchGraph works, all 3 intent routes produce valid NDJSON output
- [x] T052 Update `CLAUDE.md` with new agent modules: `nodes.py`, `edges.py`, `conversation_graph.py`, `data/checkpoints.db` location

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — no dependencies on other user stories
- **US2 (Phase 4)**: Depends on Phase 2 — no dependencies on US1
- **US3 (Phase 5)**: Depends on Phase 2 — no dependencies on US1/US2
- **US4 (Phase 6)**: Depends on Phase 2 + US2 (needs `rewrite_query` node) — no dependency on US1/US3
- **API Refactor (Phase 7)**: Depends on US1 + US2 + US3 + US4 all complete
- **Polish (Phase 8)**: Depends on Phase 7

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — independent
- **US2 (P2)**: After Phase 2 — independent; mock ResearchGraph satisfies spec-03 dependency
- **US3 (P3)**: After Phase 2 — independent; needs `init_session` from Phase 2
- **US4 (P4)**: After Phase 2 + US2 (`rewrite_query` must exist for `should_clarify` edge)
- **US5 (P5, Phase 2)**: Stubs created in Phase 4 (T023, T024). Full activation deferred to spec-??

### Within Each Phase

- [P]-marked tasks can run in parallel
- Node implementations (T016-T025, T031, T036) are fully parallel within their phase
- Graph wiring tasks (T018, T026, T033, T037) must follow node implementation
- API refactor (Phase 7) must follow all graph wiring

### Parallel Opportunities — Claude Code Agent Teams

Per `plan.md` Agent Team Strategy:

**Wave 2 example (Phase 3+4+5 nodes in parallel):**
```bash
# All these can be dispatched simultaneously in separate worktrees:
Task (Agent A): T016 classify_intent + T031 summarize_history
Task (Agent B): T021 rewrite_query + T022 aggregate_answers
Task (Agent C): T023 verify_groundedness stub + T024 validate_citations stub + T025 format_response
Task (Agent D): T017 handle_collection_mgmt + T036 request_clarification
```

**Wave 5 example (tests in parallel):**
```bash
Task (Agent E): T015 + T019 + T020 + T027 + T028 + T029 (unit tests)
Task (Agent F): T030 + T035 + T039 + T040 + T046 + T047 (integration tests)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational
3. Phase 3: US1 (classify + route)
4. Phase 7 partial: Wire minimal chat.py path for `rag_query` intent only
5. **STOP and VALIDATE**: Chat endpoint routes correctly, NDJSON streaming works

### Incremental Delivery

1. Setup + Foundational → Graph skeleton with init_session
2. + US1 → Intent classification and routing live
3. + US2 → Full query decomposition with mock ResearchGraph
4. + US3 → Session persistence and history compression
5. + US4 → Clarification interrupt/resume
6. + API Refactor → Full production endpoint
7. Phase 8 → Coverage ≥80%, all contracts validated

---

## Notes

- **spec-03 dependency**: ResearchGraph does not exist yet. Use `build_mock_research_graph()` from `tests/mocks.py` for all tasks in this spec. Wire real ResearchGraph when spec-03 is complete.
- **Phase 2 stubs**: `verify_groundedness` (T023) and `validate_citations` (T024) are created as stubs in this spec. Activation is deferred to a future spec.
- **Token counting**: `count_tokens_approximately` is a heuristic (~80-90% accuracy). Use it with the 75% threshold for safety margin. Do not use `tiktoken` directly.
- **LangGraph version**: Requires `langgraph>=1.0.10`. Use `interrupt()` + `Command(resume=...)` pattern — not the older `.interrupt()` method.
- **Commit pattern**: Commit after each phase checkpoint with conventional commit message (e.g., `feat: implement US1 intent classification and routing`).
