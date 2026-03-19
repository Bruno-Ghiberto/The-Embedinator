# Agent: agent-a6-unit-tests

**subagent_type**: quality-engineer | **Model**: Sonnet 4.6 | **Wave**: 5

## Mission

Write unit tests for all 4 MetaReasoningGraph node functions and the `route_after_strategy` edge function. Tests must mock LLM and Reranker dependencies via the config DI pattern.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs (verify expected behavior)
2. `backend/agent/meta_reasoning_nodes.py` -- implementation to test (all 4 nodes + 3 helpers)
3. `backend/agent/meta_reasoning_edges.py` -- `route_after_strategy` to test
4. `backend/agent/state.py` -- `MetaReasoningState` TypedDict (construct test states from this)
5. `backend/agent/schemas.py` -- `RetrievedChunk` model (construct test chunks)
6. `backend/config.py` -- `settings` (mock thresholds in tests)
7. `tests/unit/test_research_nodes.py` -- reference for test patterns (mock config DI, async tests)
8. `tests/unit/test_research_edges.py` -- reference for edge function test patterns
9. `tests/unit/test_research_confidence.py` -- reference for score-based test patterns
10. `specs/004-meta-reasoning/spec.md` -- acceptance scenarios for each user story

## Assigned Tasks

- T032: Write unit tests for `evaluate_retrieval_quality` in `tests/unit/test_meta_reasoning_nodes.py`:
  - Test: scores all chunks correctly via Reranker, computes correct mean
  - Test: empty chunks returns `mean=0.0, scores=[]` (FR-013)
  - Test: Reranker is None returns `mean=0.0, scores=[]` (FR-012)
  - Test: Reranker raises exception returns `mean=0.0, scores=[]`
- T033: Write unit tests for `generate_alternative_queries` in `tests/unit/test_meta_reasoning_nodes.py`:
  - Test: produces exactly 3 alternatives when LLM succeeds
  - Test: LLM failure degrades gracefully to `[original sub_question]`
  - Test: SSE event callback invoked
- T034: Write unit tests for `decide_strategy` in `tests/unit/test_meta_reasoning_nodes.py`:
  - Test: WIDEN_SEARCH selected (low mean + few chunks, mean=0.1, 2 chunks)
  - Test: CHANGE_COLLECTION selected (low mean + many chunks, mean=0.1, 5 chunks)
  - Test: RELAX_FILTERS selected (moderate mean + high variance, mean=0.3, stdev=0.2)
  - Test: report_uncertainty path (moderate mean + low variance, mean=0.3, stdev=0.05)
  - Test: max_attempts guard returns `recovery_strategy=None` (FR-006)
  - Test: strategy dedup -- candidate in `attempted_strategies` selects next untried (FR-015)
  - Test: all strategies attempted returns `recovery_strategy=None`
  - Test: `len(scores) < 2` guard returns `score_variance=0.0`
  - Test: identical scores (all equal) -- stdev=0.0, verify routes by chunk count not variance
- T035: Write unit tests for `report_uncertainty` in `tests/unit/test_meta_reasoning_nodes.py`:
  - Test: includes collections searched in output
  - Test: includes user suggestions in output
  - Test: does NOT fabricate answers (verify no "based on the available context" pattern)
  - Test: LLM failure produces static template response
- T036: Write unit tests for `route_after_strategy` in `tests/unit/test_meta_reasoning_edges.py`:
  - Test: returns `"retry"` when `recovery_strategy` is set (e.g., "WIDEN_SEARCH")
  - Test: returns `"report"` when `recovery_strategy` is None

## Files to Create/Modify

- CREATE: `tests/unit/test_meta_reasoning_nodes.py`
- CREATE: `tests/unit/test_meta_reasoning_edges.py`

## Key Patterns

- **Async tests**: Use `@pytest.mark.asyncio` decorator for all node tests (nodes are async)
- **Mock config DI**: Build config dict: `config = {"configurable": {"llm": mock_llm, "reranker": mock_reranker, "settings": mock_settings}}`
- **Mock LLM**: Use `AsyncMock` with `.ainvoke` returning an object with `.content` attribute (e.g., `MagicMock(content="1. query A\n2. query B\n3. query C")`)
- **Mock Reranker**: Use `MagicMock` with `.rerank` method returning `list[RetrievedChunk]` with `rerank_score` set
- **Build test chunks**: `RetrievedChunk(chunk_id="c1", text="...", source_file="f.pdf", breadcrumb="b", parent_id="p1", collection="col1", dense_score=0.5, sparse_score=0.3, rerank_score=0.8)`
- **Build test state**: Dict matching `MetaReasoningState` TypedDict keys with appropriate test values
- **Mock settings**: Use `monkeypatch.setattr` or pass via `config["configurable"]["settings"]`
- **Edge tests are sync**: `route_after_strategy` is not async -- test directly without `@pytest.mark.asyncio`
- **Use `monkeypatch.setenv()`** for env-based settings, NOT `os.environ[]` (prevents env leak)

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify implementation files -- only create test files
- Each test function should test ONE specific behavior (single assertion focus)
- Use descriptive test names: `test_evaluate_quality_empty_chunks_returns_zero`, `test_decide_strategy_widen_search_low_mean_few_chunks`
- Mock Reranker via config DI, NOT by patching imports
- Do NOT import `sentence_transformers` in test files -- use mocks
- Include `from unittest.mock import AsyncMock, MagicMock, patch` as needed

## Checkpoint

All unit test files created and importable. Tests cover all acceptance scenarios from spec.md. Running the following shows test count:
```bash
python -c "import tests.unit.test_meta_reasoning_nodes; import tests.unit.test_meta_reasoning_edges; print('imports OK')"
ruff check tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py
```
