# Agent: agent-integration-tests

**subagent_type**: quality-engineer | **Model**: Opus 4.6 | **Wave**: 4

## Mission

Write integration tests that exercise the full ResearchGraph execution flow with mocked external services (Qdrant, LLM, CrossEncoder). Verify the complete orchestrator loop, termination conditions, and MetaReasoningGraph trigger routing.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- integration test table in Testing section
2. `backend/agent/research_graph.py` -- `build_research_graph()` to test
3. `backend/agent/research_nodes.py` -- nodes wired into graph
4. `backend/agent/research_edges.py` -- edges wired into graph
5. `backend/agent/tools.py` -- `create_research_tools()` for tool injection
6. `backend/agent/state.py` -- ResearchState for initial state construction
7. `backend/agent/schemas.py` -- RetrievedChunk, Citation for mock data
8. `tests/mocks.py` -- existing mock patterns
9. `backend/agent/edges.py` -- `route_fan_out()` payload structure (lines 87-101)

## Assigned Tasks

- T049: `test_research_graph_with_mock_qdrant` -- Full loop with mocked Qdrant returning predefined chunks. Verify: graph compiles, loop executes, `collect_answer` or `fallback_response` is reached, output state has answer + citations + confidence_score.
- T050: `test_research_graph_meta_reasoning_trigger` -- Verify routing to MetaReasoningGraph (or fallback) when confidence stays below threshold and budget is exhausted. Verify: loop runs until `max_iterations` or `max_tool_calls`, then routes to "exhausted" target.

## Files to Create/Modify

- CREATE: `tests/integration/test_research_graph.py`

## Key Patterns

- Build initial `ResearchState` dict matching the payload from `route_fan_out()` in `backend/agent/edges.py:87-101`
- Mock HybridSearcher, Reranker, ParentStore with `AsyncMock` / `MagicMock`
- Create tools via `create_research_tools(mock_searcher, mock_reranker, mock_parent_store)`
- Build graph via `build_research_graph(tools=mock_tools, meta_reasoning_graph=None)`
- Invoke graph: `result = await graph.ainvoke(initial_state)`
- Verify terminal state fields: `answer`, `citations`, `confidence_score`
- For meta-reasoning trigger test: mock searcher to return low-quality chunks so confidence stays below threshold
- Use `unique_name()` helper pattern for collection names if creating actual Qdrant collections (but prefer mocks)

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- Use `monkeypatch.setenv()` for env vars, never `os.environ[]`
- Mock ALL external services -- integration tests must run without Qdrant, Ollama, or GPU
- Place test files under `tests/integration/`
- Each test must be self-contained -- no shared mutable state between tests

## Checkpoint

Both integration tests pass when run via `zsh scripts/run-tests-external.sh -n spec03-integration tests/integration/test_research_graph.py`. Check `Docs/Tests/spec03-integration.status` for PASSED.
