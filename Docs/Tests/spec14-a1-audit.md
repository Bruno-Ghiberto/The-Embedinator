# Spec-14 Pre-Flight Audit Report
Date: 2026-03-18

## Summary
Overall Verdict: PASS

All 5 target production files are confirmed in their pre-FR state. No spec-14 changes have been
applied yet. Line-level insertion points are documented for A2 and A3. One architectural discrepancy
is noted: embedding, retrieval, and LLM answer generation occur inside the ResearchGraph (Layer 2),
not in `nodes.py` (Layer 1). A2 must account for this when instrumenting those stages.

---

## Target File 1: backend/agent/state.py

Pre-FR state: CONFIRMED
ConversationState field count: 13
Fields (lines 18-30):
  1. session_id: str (line 18)
  2. messages: list (line 19)
  3. query_analysis: QueryAnalysis | None (line 20)
  4. sub_answers: list[SubAnswer] (line 21)
  5. selected_collections: list[str] (line 22)
  6. llm_model: str (line 23)
  7. embed_model: str (line 24)
  8. intent: str (line 25)
  9. final_response: str | None (line 26)
  10. citations: list[Citation] (line 27)
  11. groundedness_result: GroundednessResult | None (line 28)
  12. confidence_score: int (line 29)
  13. iteration_count: int (line 30)

stage_timings field present: NO
Insertion point for A2: line 31 (after `iteration_count: int` on line 30)

---

## Target File 2: backend/agent/nodes.py

Pre-FR state: CONFIRMED (with discrepancy notes below)
time module imported: YES (line 13: `import time`) -- this is EXPECTED (already used by circuit breaker at lines 118, 138)

Node instrumentation targets in nodes.py (ConversationGraph Layer 1):

- intent_classification: `classify_intent()`, line 192
  - LLM call at line 225 (`llm.ainvoke`). Timing wraps the entire function body.

- grounded_verification (conditional): `verify_groundedness()`, line 470
  - LLM call at line 512. Conditional on `settings.groundedness_check_enabled` (line 482).
  - Timing wraps from function entry; records only when the function actually runs the LLM call.

- ranking: `validate_citations()`, line 557
  - Cross-encoder reranker calls at lines 592-593 (`reranker.model.rank(...)`).

### ARCHITECTURAL DISCREPANCY: Embedding, Retrieval, and Answer Generation

The plan (14-plan.md) expects 7 instrumentation targets in nodes.py. However, the following stages
do NOT occur in nodes.py -- they happen inside the ResearchGraph (Layer 2):

- **embedding**: Occurs inside `tools_node()` in `backend/agent/research_nodes.py` (line 131).
  The research tools (created by `create_research_tools()`) invoke the embedding model as part of
  `HybridSearcher.search()`. This is called during the tool execution loop at line 190.

- **retrieval**: Also inside `tools_node()` in research_nodes.py. The `HybridSearcher.search()`
  call is encapsulated within the tool functions.

- **answer_generation**: Occurs in `collect_answer()` in `backend/agent/research_nodes.py`
  (line 382). The LLM generation call is at line 444 (`llm.ainvoke`).

The ConversationGraph invokes the ResearchGraph as a subgraph node at line 54 of
`conversation_graph.py`: `graph.add_node("research", research_graph)`. Because the research
graph runs as a single node from the ConversationGraph's perspective, instrumenting individual
stages (embedding, retrieval, answer_generation) requires adding timing code inside
`research_nodes.py`, not `nodes.py`.

**Implication for A2**: The instruction file says to instrument in `nodes.py`, but A2 must
instrument `research_nodes.py` for the embedding, retrieval, and answer_generation stages.
The state propagation pattern will still work since ResearchState results flow back to
ConversationState via the subgraph mechanism, but the stage_timings dict must be propagated
through the SubAnswer/aggregation path or by instrumenting the "research" node wrapper in
nodes.py to time the entire subgraph call. The simplest approach: instrument nodes.py at the
ConversationGraph level by wrapping:
  - `classify_intent` (intent_classification) -- in nodes.py
  - The "research" subgraph node call (embedding + retrieval + ranking combined) -- but this
    would not give per-stage granularity
  - `verify_groundedness` (grounded_verification) -- in nodes.py
  - `validate_citations` (ranking) -- in nodes.py

To get individual stage timings for embedding, retrieval, and answer_generation, A2 needs to:
  1. Either instrument research_nodes.py (tools_node for embedding+retrieval, collect_answer for
     answer_generation) and propagate timings back through state
  2. Or wrap the subgraph node in nodes.py and accept combined timing for the research phase

The spec requires 5 always-present stages (SC-007), so per-stage instrumentation in
research_nodes.py is the correct approach.

ConversationGraph node flow (from conversation_graph.py):
  START -> init_session -> classify_intent -> [route_intent]
    -> rewrite_query -> [route_after_rewrite] -> research (subgraph)
    -> aggregate_answers -> verify_groundedness -> validate_citations
    -> summarize_history -> format_response -> END

---

## Target File 3: backend/storage/sqlite_db.py

Pre-FR state: CONFIRMED
create_query_trace() parameter count: 14 explicit parameters (+ self)
  Parameters (lines 430-446):
    1. id: str
    2. session_id: str
    3. query: str
    4. collections_searched: str
    5. chunks_retrieved_json: str
    6. latency_ms: int
    7. llm_model: str | None = None
    8. embed_model: str | None = None
    9. confidence_score: int | None = None
    10. sub_questions_json: str | None = None
    11. reasoning_steps_json: str | None = None
    12. strategy_switches_json: str | None = None
    13. meta_reasoning_triggered: bool = False
    14. provider_name: str | None = None

stage_timings_json parameter present: NO

INSERT column count: 15 (14 parameters + created_at auto-generated)
INSERT statement (lines 448-461):
  Column list: id, session_id, query, sub_questions_json, collections_searched,
               chunks_retrieved_json, reasoning_steps_json, strategy_switches_json,
               meta_reasoning_triggered, latency_ms, llm_model, embed_model,
               confidence_score, provider_name, created_at
  VALUES: 15 placeholders (?)

Migration pattern reference: `_migrate_query_traces_columns()`, line 153
  Pattern: PRAGMA table_info(query_traces) -> check column set -> ALTER TABLE ADD COLUMN if missing -> commit
  Used by existing `provider_name` column addition (lines 153-161).
  A3 should follow the same pattern: check if "stage_timings_json" in columns, if not: ALTER TABLE ADD COLUMN.

Insertion point for A3 - method signature: line 445 (after `provider_name: str | None = None,`)
Insertion point for A3 - INSERT column list: line 453 (after `confidence_score, provider_name, created_at)`)
Insertion point for A3 - VALUES tuple: line 459 (after `confidence_score, provider_name, now,`)
Insertion point for A3 - migration: inside `_migrate_query_traces_columns()` after line 161

---

## Target File 4: backend/api/chat.py

Pre-FR state: CONFIRMED
time.monotonic() used for latency_ms: YES (line 60: `start_time = time.monotonic()`)
final_state extraction: line 138 (`final_state = graph.get_state(config).values`)
latency_ms computed: line 139 (`latency_ms = int((time.monotonic() - start_time) * 1000)`)
stage_timings extracted from final_state: NO

create_query_trace() call: lines 176-197
  Last argument: `provider_name=provider_name,` (line 196)

Insertion point for A3 - stage_timings extraction: line 140 (after latency_ms on line 139, before citation event)
  Add: `stage_timings = final_state.get("stage_timings", {})`

Insertion point for A3 - create_query_trace argument: line 197 (after `provider_name=provider_name,`)
  Add: `stage_timings_json=json.dumps(stage_timings) if stage_timings else None,`

Note: `json` is already imported at line 8. No new import needed for A3 in this file.

initial_state dict (lines 77-91) does NOT include `stage_timings` -- A3 may need to add
`"stage_timings": {}` to initial_state for LangGraph to propagate the field, OR A2's
node implementations can use `state.get("stage_timings", {})` defensively.

---

## Target File 5: backend/api/traces.py

Pre-FR state: CONFIRMED
stage_timings_json in SELECT: NO
  SELECT statement (lines 82-87):
    id, session_id, query, collections_searched,
    chunks_retrieved_json, confidence_score, latency_ms,
    llm_model, embed_model, sub_questions_json,
    reasoning_steps_json, strategy_switches_json,
    meta_reasoning_triggered, created_at
  -- 14 columns, NO stage_timings_json

stage_timings in response dict: NO
  Response dict (lines 115-130):
    Last key-value: `"strategy_switches": parse_json(d.get("strategy_switches_json"), []),` (line 129)
    Closing brace on line 130.

parse_json() helper present: YES (lines 105-113, local function inside get_trace)

Insertion point for A3 - SELECT: line 87 (after `meta_reasoning_triggered, created_at`)
  Add: `stage_timings_json` to the column list before `FROM query_traces`

Insertion point for A3 - response dict: line 129 (after strategy_switches line)
  Add: `"stage_timings": parse_json(d.get("stage_timings_json"), {}),`
  Note: default is `{}` (empty dict), NOT `[]` (empty list)

Note: `parse_json()` is a LOCAL function defined inside `get_trace()`, not a module-level import.
It is NOT imported -- it is defined inline at line 105. A3 just uses it as `parse_json(...)`.

---

## Existing tests/integration/test_performance.py

test_parent_retrieval_latency_target: PRESENT (line 97)
test_search_latency_target: PRESENT (line 120)
Spec-14 tests already present: NONE

File structure for A4:
- Module docstring: lines 1-8
- Imports: lines 9-20 (time, uuid, datetime, pytest, pytest_asyncio, QdrantPoint, QdrantStorage, SQLiteDB, unique_name)
- Helper functions: lines 28-50 (unique_collection_name, _make_point)
- Fixture: lines 58-88 (seeded_db -- file-based SQLiteDB with 100 parent chunks)
- Test 1: lines 96-116 (test_parent_retrieval_latency_target -- SQLite batch read)
- Test 2: lines 119-165 (test_search_latency_target -- Qdrant hybrid search, requires live Qdrant)

Import pattern: `from __future__ import annotations`, stdlib, pytest, project imports.
Test pattern: `@pytest.mark.asyncio` decorator, async test functions.
The Qdrant test does NOT use a fixture -- it creates its own QdrantStorage("localhost", 6333).
A4 should add new tests AFTER the existing ones (after line 165) and follow the same patterns.

---

## Do Not Touch Files (verified read-only)

| File | Status |
|------|--------|
| backend/agent/conversation_graph.py | Read -- node names confirmed (classify_intent, research, aggregate_answers, verify_groundedness, validate_citations, summarize_history, format_response) |
| backend/agent/research_graph.py | Read -- subgraph structure confirmed (orchestrator, tools, should_compress_context, compress_context, collect_answer, fallback_response, meta_reasoning) |
| backend/agent/research_nodes.py | Read -- embedding/retrieval in tools_node(), answer generation in collect_answer() |
| backend/config.py | Not modified by spec-14 |
| backend/ingestion/embedder.py | ThreadPoolExecutor already implemented (spec-06) |
| backend/retrieval/reranker.py | Singleton cross-encoder (spec-07) |
| backend/retrieval/searcher.py | No changes needed |
| backend/middleware.py | Rate limiting complete (spec-08) |
| backend/agent/edges.py | Routing logic not involved in timing |

---

## Overall Verdict

PASS -- all 5 target files confirmed in pre-FR state; all insertion points documented.

**Key findings**:
1. `ConversationState` has 13 fields, NO `stage_timings` field -- ready for A2.
2. `create_query_trace()` has 14 parameters (15 INSERT columns including created_at), NO `stage_timings_json` -- ready for A3.
3. `get_trace()` SELECT has 14 columns, NO `stage_timings_json` -- ready for A3.
4. `time` module is ALREADY imported in nodes.py (used by circuit breaker) -- A2 does NOT need to add this import.
5. Embedding/retrieval/answer_generation happen in `research_nodes.py` (Layer 2), NOT in `nodes.py` (Layer 1). A2 must instrument research_nodes.py for those stages OR find an alternative propagation approach.
6. `chat.py` initial_state (lines 77-91) does NOT include `stage_timings: {}`. A2/A3 should ensure the field initializes properly (either via initial_state or defensive `.get()` in nodes).
