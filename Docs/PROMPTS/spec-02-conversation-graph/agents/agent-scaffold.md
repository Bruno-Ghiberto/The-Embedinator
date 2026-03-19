# Agent: Scaffold

**Mission**: Create all file shells, extend state and prompt modules, implement edge functions and foundational node setup for the ConversationGraph.

**Subagent Type**: `python-expert`
**Model**: `opus`
**Wave**: 1 (Sequential -- must finish before Wave 2)

## Assigned Tasks

### Phase 1: Setup

- **T001**: Add `langgraph-checkpoint-sqlite>=2.0` to `requirements.txt` and run `pip install -r requirements.txt`
- **T002**: Create `backend/agent/nodes.py` with module-level imports and empty stub functions for all 11 nodes: `init_session`, `classify_intent`, `rewrite_query`, `request_clarification`, `fan_out`, `aggregate_answers`, `verify_groundedness`, `validate_citations`, `summarize_history`, `format_response`, `handle_collection_mgmt` -- each raises `NotImplementedError`
- **T003**: Create `backend/agent/edges.py` with module-level imports and empty stub functions: `route_intent`, `should_clarify`, `route_fan_out` -- each raises `NotImplementedError`
- **T004**: Create `backend/agent/conversation_graph.py` with module-level imports and empty `build_conversation_graph(research_graph, checkpointer=None)` stub

### Phase 2: Foundational

- **T006**: Add `intent: str` field to `ConversationState` TypedDict in `backend/agent/state.py` -- place after `embed_model`, add inline comment `# "rag_query" | "collection_mgmt" | "ambiguous"`, default value `"rag_query"`
- **T007**: Add 7 new prompt constants to `backend/agent/prompts.py`: `CLASSIFY_INTENT_SYSTEM`, `CLASSIFY_INTENT_USER`, `REWRITE_QUERY_SYSTEM`, `REWRITE_QUERY_USER`, `VERIFY_GROUNDEDNESS_SYSTEM`, `FORMAT_RESPONSE_SYSTEM`, `SUMMARIZE_HISTORY_SYSTEM`
- **T008**: Add `MODEL_CONTEXT_WINDOWS` dict and `get_context_budget(model_name: str) -> int` function to `backend/agent/nodes.py` -- budget is `int(window * 0.75)`, default window 32768
- **T009**: Implement `route_intent(state: ConversationState) -> str` in `backend/agent/edges.py` -- returns `state["intent"]`
- **T010**: Implement `should_clarify(state: ConversationState) -> bool` in `backend/agent/edges.py` -- returns `not state["query_analysis"].is_clear and state["iteration_count"] < 2`; if `query_analysis` is `None` returns `False`
- **T011**: Implement `route_fan_out(state: ConversationState) -> list[Send]` in `backend/agent/edges.py` -- returns `[Send("research", {...})]` for each sub-question; falls back to original query if list is empty; uses `collections_hint or selected_collections`

## Files Created

| File | Action |
|------|--------|
| `backend/agent/nodes.py` | CREATE -- all 11 stub functions + `MODEL_CONTEXT_WINDOWS` + `get_context_budget()` |
| `backend/agent/edges.py` | CREATE -- 3 edge functions (stubs replaced with implementations) |
| `backend/agent/conversation_graph.py` | CREATE -- empty `build_conversation_graph()` stub |

## Files Modified

| File | Changes |
|------|---------|
| `requirements.txt` | Add `langgraph-checkpoint-sqlite>=2.0` |
| `backend/agent/state.py` | Add `intent: str` field to `ConversationState` |
| `backend/agent/prompts.py` | Add 7 new prompt constants |

## Constraints

- All node stubs in `nodes.py` must raise `NotImplementedError` (Wave 2 agents will replace them)
- The `intent` field in `ConversationState` must be placed after `embed_model` with inline comment
- Prompt constants must match the text verbatim from `Docs/PROMPTS/spec-02-conversation-graph/02-specify.md` (Architecture Reference section)
- `SUMMARIZE_HISTORY_SYSTEM` is a new prompt not in 02-specify.md -- write it to instruct the LLM to summarize older conversation messages while preserving key context, decisions, and referenced entities
- Edge functions use types from `langgraph.types` (`Send`) and `backend/agent/state` (`ConversationState`)
- `route_fan_out` must populate ALL `ResearchState` fields in each `Send()` payload (see data-model.md)
- Import `structlog` at module level in `nodes.py`
- Do NOT import or use `tiktoken`. Use `count_tokens_approximately` from `langchain_core.messages.utils`
- `get_context_budget` covers these models: `qwen2.5:7b` (32768), `llama3.1:8b` (131072), `mistral:7b` (32768), `gpt-4o` (131072), `gpt-4o-mini` (131072), `claude-sonnet-4-20250514` (200000). Default: 32768

## Dependencies

- None -- this is the first wave
- Phase 1 codebase must be on branch `002-conversation-graph`
- Existing `backend/agent/state.py`, `backend/agent/schemas.py`, `backend/agent/prompts.py` must exist

## Done Criteria

- [ ] `pip install -r requirements.txt` succeeds with `langgraph-checkpoint-sqlite`
- [ ] `python -c "from backend.agent.nodes import init_session, classify_intent, rewrite_query, request_clarification, fan_out, aggregate_answers, verify_groundedness, validate_citations, summarize_history, format_response, handle_collection_mgmt"` succeeds
- [ ] `python -c "from backend.agent.edges import route_intent, should_clarify, route_fan_out"` succeeds
- [ ] `python -c "from backend.agent.conversation_graph import build_conversation_graph"` succeeds
- [ ] `python -c "from backend.agent.state import ConversationState; print(ConversationState.__annotations__['intent'])"` prints `str`
- [ ] All 7 new prompt constants importable from `backend.agent.prompts`
- [ ] `route_intent`, `should_clarify`, `route_fan_out` are implemented (not `NotImplementedError`)
- [ ] `get_context_budget("gpt-4o")` returns `98304` (131072 * 0.75)
- [ ] All 11 node stubs raise `NotImplementedError` when called
