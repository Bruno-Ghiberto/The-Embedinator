# Agent: agent-integration

**subagent_type**: backend-architect | **Model**: Opus 4.6 | **Wave**: 3

## Mission

Wire the ResearchGraph into the application. Update research_graph.py to use real nodes/edges, connect it to ConversationGraph, initialize infrastructure in main.py lifespan, and ensure mocks.py remains functional.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- code specs for research_graph.py, main.py modifications, conversation_graph.py integration
2. `backend/agent/research_graph.py` -- stub from Wave 1 (complete the wiring)
3. `backend/agent/conversation_graph.py` -- `build_conversation_graph(research_graph=...)` integration point
4. `backend/main.py` -- lifespan function to extend with infrastructure init
5. `tests/mocks.py` -- `build_mock_research_graph()` must continue to work
6. `backend/agent/research_nodes.py` -- node functions to import (Wave 2 output)
7. `backend/agent/research_edges.py` -- edge functions to import (Wave 2 output)
8. `backend/agent/tools.py` -- `create_research_tools()` factory (Wave 2 output)
9. `backend/storage/qdrant_client.py` -- QdrantClientWrapper (has `.client` attribute for AsyncQdrantClient)
10. `backend/config.py` -- settings instance

## Assigned Tasks

- T023: Complete `build_research_graph()` in `research_graph.py` -- wire all nodes, edges, and conditional routing
- T024: Update `main.py` lifespan to init HybridSearcher, Reranker, ParentStore
- T025: Update `main.py` lifespan to call `create_research_tools()` and `build_research_graph()`
- T026: Update `main.py` lifespan to call `build_conversation_graph(research_graph=..., checkpointer=...)`
- T033: Store `conversation_graph` on `app.state` for the chat endpoint to use
- T037: Ensure `qdrant.client` (AsyncQdrantClient) is passed to HybridSearcher, not the wrapper
- T038: Ensure `db` (SQLiteDB instance) is passed to ParentStore
- T039: Verify `tests/mocks.py` `build_mock_research_graph()` still compiles and returns valid graph
- T042: Verify graph compiles: `build_research_graph(tools=research_tools)` returns without error
- T043: Verify conversation graph compiles with real research graph injected

## Files to Create/Modify

- MODIFY: `backend/agent/research_graph.py`
- MODIFY: `backend/main.py`
- MODIFY: `tests/mocks.py` (if needed to keep compatible)

## Key Patterns

- `HybridSearcher(qdrant.client, settings)` -- pass the inner `AsyncQdrantClient`, not the `QdrantClientWrapper`
- `Reranker(settings)` -- constructor loads CrossEncoder model
- `ParentStore(db)` -- pass the `SQLiteDB` instance
- `create_research_tools(searcher, reranker, parent_store)` -- returns list of tools (R6)
- `build_research_graph(tools=research_tools, meta_reasoning_graph=None)` -- Phase 1 has no meta-reasoning
- `build_conversation_graph(research_graph=compiled_graph, checkpointer=checkpointer)`
- Lifespan order: DB -> Qdrant -> Registry -> Checkpointer -> HybridSearcher -> Reranker -> ParentStore -> Tools -> ResearchGraph -> ConversationGraph

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER break existing lifespan initialization order (DB, Qdrant, Registry, Checkpointer must init first)
- NEVER modify ConversationGraph node/edge logic -- only pass the research_graph parameter
- Keep `build_mock_research_graph()` in mocks.py working for existing spec-02 tests
- Use structlog for all new initialization log messages (FR-017)
- Store all new objects on `app.state` for access by API endpoints

## Checkpoint

`build_research_graph()` compiles without error. `main.py` lifespan initializes all infrastructure and builds both graphs. `app.state.conversation_graph` is set. `build_mock_research_graph()` still works for tests.
