# Agent: agent-a5-integration

**subagent_type**: system-architect | **Model**: Opus 4.6 | **Wave**: 4

## Mission

Wire the MetaReasoningGraph into the application. Add the ResearchState-to-MetaReasoningState mapper node body in `research_graph.py`, update `main.py` lifespan to build MetaReasoningGraph and pass it to `build_research_graph()`, and implement the FR-011 guard and FR-017 infrastructure error handling.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs for `research_graph.py` mapper node and `main.py` changes (authoritative reference)
2. `backend/agent/research_graph.py` -- EXISTING code (lines 49-58 already wire conditional routing). Your job is to replace the simple `graph.add_node("meta_reasoning", meta_reasoning_graph)` with a mapper closure. Read this file CAREFULLY before making changes.
3. `backend/agent/research_edges.py` -- `should_continue_loop` already returns `"exhausted"` (lines 55, 64). VERIFY but do NOT modify.
4. `backend/main.py` -- lifespan function (replace lines 99-106 with inside-out graph assembly)
5. `backend/agent/meta_reasoning_graph.py` -- `build_meta_reasoning_graph()` from Wave 3
6. `backend/agent/state.py` -- `ResearchState` and `MetaReasoningState` TypedDicts
7. `backend/config.py` -- `settings.meta_reasoning_max_attempts`
8. `specs/004-meta-reasoning/plan.md` -- integration points section
9. `specs/004-meta-reasoning/data-model.md` -- modified_state semantics ("ALL", "ROTATE")

## Assigned Tasks

- T027: VERIFY `should_continue_loop` in `research_edges.py` already returns `"exhausted"`. VERIFY routing in `build_research_graph` already directs `"exhausted"` -> `meta_reasoning`. This is a verification-only task -- no code changes expected.
- T028: Add `meta_reasoning_max_attempts == 0` guard in `main.py` -- when `max_attempts == 0`, pass `None` to `build_research_graph(meta_reasoning_graph=None)` so routing keeps `"exhausted"` -> `fallback_response` (FR-011). The guard belongs in main.py at graph-building time, NOT in the edge function.
- T029: Add ResearchState-to-MetaReasoningState mapper closure in `research_graph.py` -- replace the simple `graph.add_node("meta_reasoning", meta_reasoning_graph)` with an `async def meta_reasoning_mapper` that: (1) maps ResearchState fields into MetaReasoningState input dict, (2) invokes `meta_reasoning_graph.ainvoke(meta_input, config=config)`, (3) on recovery (`recovery_strategy` set): applies `modified_state` back to ResearchState -- interprets "ALL" as search-all-collections (empty list), interprets "ROTATE" as next-different-collection (rotate list), resets loop counters, (4) on uncertainty (`recovery_strategy` None): sets `answer` from subgraph + `confidence_score=0.0`
- T030: Update `main.py` lifespan to build graphs inside-out: `meta_reasoning_graph = build_meta_reasoning_graph()` -> pass to `build_research_graph(tools=research_tools, meta_reasoning_graph=meta_reasoning_graph)` -> pass to `build_conversation_graph(...)`
- T031: Handle infrastructure error during subgraph invocation in the mapper node -- wrap `meta_reasoning_graph.ainvoke()` in try/except, on failure return `{"answer": "...(error noted)...", "confidence_score": 0.0}` (FR-017)

## Files to Create/Modify

- MODIFY: `backend/agent/research_graph.py` (add mapper node, add `RunnableConfig` import)
- MODIFY: `backend/main.py` (update lifespan graph build section)

## Key Patterns

- **EXISTING ROUTING IS CORRECT**: `build_research_graph` already has `if meta_reasoning_graph:` block (lines 49-73) that wires conditional edges. Do NOT rewrite the routing logic. Only replace the `graph.add_node("meta_reasoning", meta_reasoning_graph)` line with the mapper closure.
- **Mapper closure**: Define `async def meta_reasoning_mapper(state: ResearchState, config: RunnableConfig = None) -> dict:` INSIDE the `if meta_reasoning_graph:` block. It captures `meta_reasoning_graph` from the enclosing scope.
- **Forward map**: ResearchState -> MetaReasoningState. Map `sub_question`, `retrieved_chunks` directly. Initialize `alternative_queries=[]`, `mean_relevance_score=0.0`, etc. Carry over attempt tracking via `state.get("_meta_attempt_count", 0)` and `state.get("_attempted_strategies", set())`.
- **Reverse map - recovery**: When `result["recovery_strategy"]` is set, apply `modified_state` overrides. "ALL" -> `selected_collections=[]` (empty = search all). "ROTATE" -> rotate collection list. Reset `retrieved_chunks=[]`, `tool_call_count=0`, `iteration_count=0`, `confidence_score=0.0`, etc.
- **Reverse map - uncertainty**: When `result["recovery_strategy"]` is None, return `{"answer": result["answer"], "confidence_score": 0.0}`.
- **ROTATE single-collection guard**: If `len(current_collections) <= 1`, rotation is impossible. Fall through to uncertainty response.
- **Inside-out build order**: MetaReasoningGraph -> ResearchGraph -> ConversationGraph
- **FR-011 guard**: In main.py, `if settings.meta_reasoning_max_attempts > 0: meta_reasoning_graph = build_meta_reasoning_graph()` else `meta_reasoning_graph = None`
- **Add import**: `from langchain_core.runnables import RunnableConfig` at top of `research_graph.py`
- **Add import**: `import structlog` and `logger = structlog.get_logger(__name__)` in `research_graph.py` for FR-017 error logging

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `should_continue_loop` in `research_edges.py` -- it already returns "exhausted" correctly
- NEVER overwrite the existing conditional edges routing in `build_research_graph` (lines 52-58) -- only replace the `graph.add_node("meta_reasoning", ...)` call
- NEVER modify `meta_reasoning_nodes.py`, `meta_reasoning_edges.py`, or `meta_reasoning_graph.py`
- NEVER break existing ConversationGraph lifespan initialization (DB, Qdrant, Registry, Checkpointer must init first)
- Keep the existing `graph.add_edge("meta_reasoning", "orchestrator")` line (line 73) -- the mapper node returns state updates that feed back into the orchestrator
- The mapper's `meta_reasoning_graph.ainvoke()` call is async -- the mapper function MUST be async

## Checkpoint

Full graph chain compiles. `should_continue_loop` verified to return "exhausted". FR-011 guard works (max_attempts=0 -> meta_reasoning_graph is None). Running the following succeeds:
```bash
python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; from backend.agent.research_graph import build_research_graph; print('imports OK')"
ruff check backend/agent/research_graph.py backend/main.py
```
