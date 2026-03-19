# Agent: agent-unit-tests

**subagent_type**: quality-engineer | **Model**: Sonnet 4.6 | **Wave**: 4

## Mission

Write comprehensive unit tests for all ResearchGraph components: retrieval layer, tools, node functions, edge functions, and confidence scoring.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- unit test table in Testing section
2. `backend/agent/research_nodes.py` -- node implementations to test
3. `backend/agent/research_edges.py` -- edge implementations to test
4. `backend/agent/tools.py` -- tool factory to test
5. `backend/agent/confidence.py` -- 5-signal formula to test
6. `backend/retrieval/searcher.py` -- HybridSearcher to test
7. `backend/retrieval/reranker.py` -- Reranker to test
8. `backend/retrieval/score_normalizer.py` -- normalize_scores to test
9. `backend/storage/parent_store.py` -- ParentStore to test
10. `backend/agent/state.py` -- ResearchState for test fixture construction
11. `backend/agent/schemas.py` -- RetrievedChunk, ParentChunk for test data
12. `tests/` -- existing test structure and patterns

## Assigned Tasks

- T044: Tests for retrieval layer (HybridSearcher circuit breaker, Reranker rank API, ScoreNormalizer)
- T045: Tests for tool factory and individual tools
- T046: Tests for node functions (orchestrator, tools_node, should_compress_context, compress_context, collect_answer, fallback_response)
- T047: Tests for edge functions (should_continue_loop confidence-first ordering, route_after_compress_check)
- T048: Tests for confidence scoring (5-signal formula, edge cases, scale conversion)

## Files to Create/Modify

- CREATE: `tests/unit/test_research_retrieval.py`
- CREATE: `tests/unit/test_research_tools.py`
- CREATE: `tests/unit/test_research_nodes.py`
- CREATE: `tests/unit/test_research_edges.py`
- CREATE: `tests/unit/test_confidence.py`

## Key Patterns

- Use `monkeypatch.setenv()` for env vars, never `os.environ[]` directly
- Use `unittest.mock.AsyncMock` for async dependencies (LLM, searcher, etc.)
- Build `ResearchState` dicts manually as test fixtures
- Build `RetrievedChunk` objects with realistic scores for confidence tests
- Test the confidence-first ordering in `should_continue_loop` (F1): when confidence >= threshold, must return "sufficient" even if budget is not exhausted
- Test retry-once counting: verify both original + retry count against budget (R7)
- Test `_no_new_tools` flag detection in `should_continue_loop` (F4)
- Test `_needs_compression` flag set/read pattern (F3)
- Test confidence scale mismatch: `settings.confidence_threshold / 100` comparison
- Test reranker uses `rank()` not `predict()` (R5)

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- Use `monkeypatch` for all environment variable manipulation
- Mock all external dependencies (Qdrant, LLM, CrossEncoder) -- unit tests must not require running services
- Do NOT write integration tests -- that is agent-integration-tests' job
- Place all test files under `tests/unit/`

## Checkpoint

All unit tests pass when run via `zsh scripts/run-tests-external.sh -n spec03-unit tests/unit/test_research_*.py tests/unit/test_confidence.py`. Check `Docs/Tests/spec03-unit.status` for PASSED.
