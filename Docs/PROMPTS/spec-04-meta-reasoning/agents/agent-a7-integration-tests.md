# Agent: agent-a7-integration-tests

**subagent_type**: quality-engineer | **Model**: Sonnet 4.6 | **Wave**: 5

## Mission

Write integration tests for the MetaReasoningGraph: graph compilation, end-to-end recovery flow, uncertainty flow, strategy deduplication across attempts, `max_attempts=0` bypass, and infrastructure error handling during retry.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs (verify expected behavior, graph flow)
2. `backend/agent/meta_reasoning_graph.py` -- `build_meta_reasoning_graph()` to test
3. `backend/agent/meta_reasoning_nodes.py` -- node implementations (understand what to mock)
4. `backend/agent/meta_reasoning_edges.py` -- `route_after_strategy` edge
5. `backend/agent/research_graph.py` -- `build_research_graph()` with mapper node (for T041 bypass test)
6. `backend/agent/state.py` -- `MetaReasoningState`, `ResearchState` TypedDicts
7. `backend/agent/schemas.py` -- `RetrievedChunk` model
8. `backend/config.py` -- `settings.meta_reasoning_max_attempts`
9. `tests/integration/test_research_graph.py` -- reference for integration test patterns
10. `tests/mocks.py` -- reference for mock graph patterns
11. `specs/004-meta-reasoning/spec.md` -- acceptance scenarios for user stories

## Assigned Tasks

- T037: Write integration test for graph compilation in `tests/integration/test_meta_reasoning_graph.py` -- verify `build_meta_reasoning_graph()` compiles without error, graph has expected nodes ("generate_alternative_queries", "evaluate_retrieval_quality", "decide_strategy", "report_uncertainty")
- T038: Write integration test for recovery flow -- end-to-end: provide state with low-relevance chunks (mean < 0.2, 2 chunks), mock LLM and Reranker via config, invoke graph, verify WIDEN_SEARCH selected and `modified_state` returned
- T039: Write integration test for uncertainty flow -- end-to-end: set `meta_attempt_count` at max, invoke graph, verify `report_uncertainty` produces `answer` and `uncertainty_reason`, `recovery_strategy` is None
- T040: Write integration test for strategy dedup across attempts -- first invocation with `attempted_strategies=set()` selects strategy A, second invocation with `attempted_strategies={A}` selects strategy B (different strategy)
- T041: Write integration test for `max_attempts=0` bypass -- build research graph with `meta_reasoning_graph=None`, verify `should_continue_loop` "exhausted" routes to `fallback_response` (not meta_reasoning). This tests FR-011 at the graph level.
- T041a: Write integration test for infrastructure error during retry -- mock `meta_reasoning_graph.ainvoke` to raise `ConnectionError`, verify the mapper node returns `answer` with error noted and `confidence_score=0.0` (FR-017)

## Files to Create/Modify

- CREATE: `tests/integration/test_meta_reasoning_graph.py`

## Key Patterns

- **Async tests**: Use `@pytest.mark.asyncio` for all graph invocation tests
- **Graph invocation**: `result = await graph.ainvoke(input_state, config=config)` where `config = {"configurable": {"llm": mock_llm, "reranker": mock_reranker}}`
- **Mock LLM for integration**: `AsyncMock` with `.ainvoke` returning object with `.content` attribute
- **Mock Reranker for integration**: `MagicMock` with `.rerank` returning scored `RetrievedChunk` list
- **Build test input state**: Full `MetaReasoningState` dict with all required fields initialized
- **Graph compilation test**: `graph = build_meta_reasoning_graph()` then check `graph.get_graph().nodes` for expected node names
- **Recovery flow verification**: After `ainvoke`, check `result["recovery_strategy"]` is set and `result["modified_state"]` contains expected overrides
- **Uncertainty flow verification**: After `ainvoke`, check `result["answer"]` is non-empty and `result["recovery_strategy"]` is None
- **Strategy dedup test**: Run graph twice with different `attempted_strategies` sets, verify different strategies selected
- **max_attempts=0 test (T041)**: Test at the `build_research_graph` level -- pass `meta_reasoning_graph=None`, verify graph topology routes "exhausted" to "fallback_response"
- **Infrastructure error test (T041a)**: Create a mock compiled graph whose `.ainvoke` raises `ConnectionError`. Build the mapper closure in `research_graph.py` by calling `build_research_graph(tools=mock_tools, meta_reasoning_graph=mock_failing_graph)` and invoke to verify error handling.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify implementation files -- only create test files
- Integration tests should exercise the full graph flow (compile + invoke), not just individual nodes
- Use `monkeypatch.setenv()` for settings overrides, NOT `os.environ[]`
- Mock external dependencies (LLM, Reranker) but let the graph framework run for real
- Test names should be descriptive: `test_graph_compiles_with_expected_nodes`, `test_recovery_flow_widen_search`, `test_uncertainty_when_max_attempts_reached`
- For T041, you may need to build a minimal ResearchGraph with mock tools to test the routing
- For T041a, create a mock graph object with `ainvoke = AsyncMock(side_effect=ConnectionError("Qdrant unavailable"))`

## Checkpoint

All integration tests created and importable. Tests cover graph compilation, recovery flow, uncertainty flow, strategy dedup, max_attempts=0 bypass, and infrastructure error. Running the following shows test count:
```bash
python -c "import tests.integration.test_meta_reasoning_graph; print('imports OK')"
ruff check tests/integration/test_meta_reasoning_graph.py
```
