# Agent: Integration

**Mission**: Wire all node and edge functions into `conversation_graph.py` to produce a fully compiled LangGraph StateGraph. Verify the graph compiles and routes correctly for all intent paths.

**Subagent Type**: `backend-architect`
**Model**: `opus`
**Wave**: 3 (Sequential -- after all Wave 2 agents complete)

## Assigned Tasks

- **T018**: Wire US1 subgraph in `backend/agent/conversation_graph.py`: add `init_session`, `classify_intent`, `handle_collection_mgmt` nodes; add `START -> init_session -> classify_intent`; add `add_conditional_edges("classify_intent", route_intent, {"rag_query": "rewrite_query", "collection_mgmt": "handle_collection_mgmt", "ambiguous": "request_clarification"})`; add `handle_collection_mgmt -> END`
- **T026**: Wire full RAG path: add `rewrite_query`, `research` (subgraph), `aggregate_answers`, `verify_groundedness`, `validate_citations`, `format_response` nodes; add `should_clarify` conditional edge from `rewrite_query`; add `route_fan_out` conditional edge for Send dispatch; add sequential edges `research -> aggregate_answers -> verify_groundedness -> validate_citations -> summarize_history -> format_response -> END`
- **T033**: Add `summarize_history` node between `validate_citations` and `format_response`; add edge `validate_citations -> summarize_history -> format_response`
- **T037**: Wire clarification path: `request_clarification -> classify_intent` (re-classification after clarification); verify `should_clarify` edge caps at 2 rounds via `iteration_count`; compile with checkpointer parameter

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/conversation_graph.py` | Full implementation of `build_conversation_graph()` |

## Constraints

### Graph Structure

The final `build_conversation_graph()` must match this exact wiring:

```python
def build_conversation_graph(research_graph, checkpointer=None):
    graph = StateGraph(ConversationState)

    # Core nodes
    graph.add_node("init_session", init_session)
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("rewrite_query", rewrite_query)
    graph.add_node("request_clarification", request_clarification)
    graph.add_node("research", research_graph)
    graph.add_node("aggregate_answers", aggregate_answers)
    graph.add_node("summarize_history", summarize_history)
    graph.add_node("format_response", format_response)

    # Phase 2 stubs
    graph.add_node("verify_groundedness", verify_groundedness)
    graph.add_node("validate_citations", validate_citations)

    # Out-of-scope stub
    graph.add_node("handle_collection_mgmt", handle_collection_mgmt)

    # Edges
    graph.add_edge(START, "init_session")
    graph.add_edge("init_session", "classify_intent")
    graph.add_conditional_edges("classify_intent", route_intent, {
        "rag_query": "rewrite_query",
        "collection_mgmt": "handle_collection_mgmt",
        "ambiguous": "request_clarification",
    })
    graph.add_edge("handle_collection_mgmt", END)
    graph.add_edge("request_clarification", "classify_intent")
    graph.add_conditional_edges("rewrite_query", should_clarify, {
        True: "request_clarification",
        False: "fan_out",
    })
    graph.add_conditional_edges("rewrite_query", route_fan_out)
    graph.add_edge("research", "aggregate_answers")
    graph.add_edge("aggregate_answers", "verify_groundedness")
    graph.add_edge("verify_groundedness", "validate_citations")
    graph.add_edge("validate_citations", "summarize_history")
    graph.add_edge("summarize_history", "format_response")
    graph.add_edge("format_response", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
```

### Import Requirements

- Import all 11 node functions from `backend.agent.nodes`
- Import all 3 edge functions from `backend.agent.edges`
- Import `StateGraph`, `START`, `END` from `langgraph.graph`
- Import `MemorySaver` from `langgraph.checkpoint.memory`
- Import `ConversationState` from `backend.agent.state`

### Key Design Points

- `research_graph` is passed as a parameter -- it is a compiled subgraph (or mock)
- `checkpointer` defaults to `None`; when `None`, falls back to `MemorySaver()` (in-memory, for tests)
- For production, `AsyncSqliteSaver` is passed by `main.py` lifespan
- `route_fan_out` returns `list[Send]` -- this is how LangGraph handles dynamic fan-out
- `request_clarification` routes back to `classify_intent` (not `rewrite_query`) to allow re-classification after user provides clarification
- The `fan_out` node is NOT added explicitly -- `route_fan_out` edge function produces `Send()` objects that directly target the `"research"` node

### Verification

After wiring, verify the graph compiles without errors:

```python
from tests.mocks import build_mock_research_graph
mock_rg = build_mock_research_graph()
graph = build_conversation_graph(mock_rg)
# Should not raise
```

## Dependencies

- Wave 1 (Scaffold) must be complete
- Wave 2 (all 4 agents) must be complete: all 11 node functions implemented in `nodes.py`, all 3 edge functions implemented in `edges.py`
- `build_mock_research_graph()` should exist in `tests/mocks.py` (T005 from Wave 5, but may need to be created early for verification)

## Done Criteria

- [ ] `build_conversation_graph()` returns a compiled LangGraph StateGraph
- [ ] Graph includes all 11 nodes (init_session, classify_intent, rewrite_query, request_clarification, research, aggregate_answers, verify_groundedness, validate_citations, summarize_history, format_response, handle_collection_mgmt)
- [ ] `route_intent` conditional edge routes to 3 targets: rewrite_query, handle_collection_mgmt, request_clarification
- [ ] `should_clarify` conditional edge routes to request_clarification (True) or fan_out (False)
- [ ] `route_fan_out` produces Send() objects targeting "research" node
- [ ] Sequential edges: research -> aggregate -> verify -> validate -> summarize -> format -> END
- [ ] `handle_collection_mgmt -> END` edge exists
- [ ] `request_clarification -> classify_intent` loop edge exists
- [ ] Graph compiles with `MemorySaver()` (default)
- [ ] Graph compiles with injected checkpointer parameter
