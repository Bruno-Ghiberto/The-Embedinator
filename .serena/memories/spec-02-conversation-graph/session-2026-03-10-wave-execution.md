# Spec 02: ConversationGraph — Wave Execution Session

## Status: IMPLEMENTATION COMPLETE
- 52/52 tasks done
- 147 tests passing, 1 known pre-existing failure (test_default_settings)
- Branch: `002-conversation-graph`

## Wave Execution Summary

### Wave 1: Scaffold (Agent-Scaffold, opus)
- Most files pre-existing from prior session
- Added: `intent: str` field to ConversationState, 7 prompt constants
- Checkpoint: all stubs importable, edge functions implemented

### Wave 2: Node Implementations (4 parallel teammates, tmux panes)
- session-history (sonnet): init_session + summarize_history
- intent-analysis (opus): classify_intent + rewrite_query
- dispatch-aggregation (sonnet): handle_collection_mgmt + aggregate_answers + format_response
- interrupt-stubs (sonnet): request_clarification + verify_groundedness stub + validate_citations stub
- All 10 active node functions implemented, fan_out is dead stub

### Wave 3: Integration (integration agent, opus)
- Wired all nodes/edges into conversation_graph.py
- Created tests/mocks.py with build_mock_research_graph()
- Added AsyncSqliteSaver checkpointer to main.py lifespan
- Design deviation: combined should_clarify + route_fan_out into route_after_rewrite() (LangGraph limitation)

### Wave 4: API Refactor (api-refactor agent, opus)
- Refactored chat.py: ConversationGraph invocation + NDJSON streaming
- ChatRequest field renames: query→message, model_name→llm_model
- Added NO_COLLECTIONS guard, metadata frame, graph caching on app.state

### Wave 5: Tests (2 parallel teammates)
- unit-tests (sonnet): 33 unit tests — test_nodes.py, test_edges.py
- integration-tests (opus): 15 integration tests — test_conversation_graph.py
- All 48 new tests passed; 9 Phase 1 tests broke from Wave 4 renames

### Wave 6: Polish (polish agent, opus)
- Fixed all 9 broken Phase 1 tests
- Created test_ndjson_frames.py (28 tests)
- Added source_removed field to Citation
- Updated CLAUDE.md
- Final: 147 passed, 1 known failure

## Design Deviations
1. `route_after_rewrite()` combines should_clarify + route_fan_out — LangGraph rejects two add_conditional_edges from same node
2. `fan_out` in nodes.py is dead stub — functionality in route_fan_out edge function

## Agent Teams Learnings
- Use TeamCreate/TaskCreate/Agent(team_name=...)/SendMessage/TeamDelete workflow
- Keep spawn prompts minimal: "Read your instruction file at <path> FIRST"
- Do NOT inline spec content — agents must read authoritative files
- Each teammate gets own tmux pane when running inside tmux session
- Shut down teammates before TeamDelete
