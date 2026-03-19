# Agent: Unit Tests

**Mission**: Write comprehensive unit tests for all node and edge functions, achieving coverage of all success paths, failure paths, and edge cases.

**Subagent Type**: `quality-engineer`
**Model**: `sonnet`
**Wave**: 5 (Parallel -- runs in worktree alongside Agent-F)

## Assigned Tasks

### Edge Tests (tests/unit/test_edges.py)

- **T013**: Write unit tests for `route_intent` -- test each of the 3 routing values (`rag_query`, `collection_mgmt`, `ambiguous`)
- **T014**: Write unit tests for `should_clarify` -- test `is_clear=True`, `is_clear=False` with count <2, `is_clear=False` with count=2, `query_analysis=None`

### Node Tests (tests/unit/test_nodes.py)

- **T015**: Write unit tests for `init_session` -- mock `aiosqlite`, test successful load, SQLite failure fallback, missing session (fresh create)
- **T019**: Write unit tests for `classify_intent` -- mock LLM returning `{"intent": "rag_query"}`, `{"intent": "collection_mgmt"}`, `{"intent": "ambiguous"}`; test LLM failure defaults to `"rag_query"`
- **T020**: Write unit tests for `handle_collection_mgmt` -- verify `final_response` is set and `confidence_score` is `0`
- **T027**: Write unit tests for `rewrite_query` -- mock LLM with structured output; test valid `QueryAnalysis`, `ValidationError` fallback, factoid query not decomposed unnecessarily (1 sub-question)
- **T028**: Write unit tests for `aggregate_answers` -- test citation deduplication (same `passage_id` keeps highest score), confidence score computation, empty `sub_answers` fallback
- **T029**: Write unit tests for `format_response` -- test inline citation markers `[1][2]`, confidence summary shown when < 70, `groundedness_result=None` skips annotation
- **T034**: Write unit tests for `summarize_history` -- test no-op when under 75% budget, compression triggered when over budget, LLM failure returns unchanged messages
- **T038**: Write unit tests for `request_clarification` -- mock `interrupt()`; test that clarification question from `query_analysis.clarification_needed` is passed to interrupt; test `iteration_count` increments

## Files Created

| File | Purpose |
|------|---------|
| `tests/unit/test_edges.py` | Unit tests for `route_intent`, `should_clarify`, `route_fan_out` |
| `tests/unit/test_nodes.py` | Unit tests for all 11 node functions |

## Constraints

### Testing Patterns

- Use `pytest` with `pytest-asyncio` for async node tests
- Use `unittest.mock.AsyncMock` for mocking async dependencies (LLM, DB)
- Use `unittest.mock.patch` for mocking `interrupt()` in `request_clarification` tests
- Use `monkeypatch.setenv()` for environment variables -- NOT `os.environ[]` directly
- Use `pytest.fixture` for common test state construction

### Mock Construction

- Build `ConversationState` dicts manually for each test case -- do NOT rely on database
- Mock LLM: use `AsyncMock` with `return_value` set to expected response
- Mock `llm.with_structured_output()`: return another mock whose `ainvoke()` returns `QueryAnalysis`
- Mock `aiosqlite`: use `AsyncMock` for connection and cursor objects
- Mock `interrupt()`: patch `langgraph.types.interrupt` to capture the argument and return a fixed user response
- Mock `compute_confidence()`: patch to return a known value for deterministic testing

### Test Data

- Use `SubAnswer`, `Citation`, `QueryAnalysis` from `backend.agent.schemas` to build realistic test data
- Citation `passage_id` values should be deterministic (e.g., `"p-001"`, `"p-002"`)
- Confidence scores: use `0.85` (high), `0.45` (low) for testing threshold behavior
- Messages: use `HumanMessage`, `AIMessage`, `SystemMessage` from `langchain_core.messages`

### Key Test Scenarios

**route_intent**:
- `state["intent"] = "rag_query"` -> returns `"rag_query"`
- `state["intent"] = "collection_mgmt"` -> returns `"collection_mgmt"`
- `state["intent"] = "ambiguous"` -> returns `"ambiguous"`

**should_clarify**:
- `is_clear=True` -> `False`
- `is_clear=False`, `iteration_count=0` -> `True`
- `is_clear=False`, `iteration_count=1` -> `True`
- `is_clear=False`, `iteration_count=2` -> `False` (cap reached)
- `query_analysis=None` -> `False`

**init_session**:
- Successful load: returns messages, collections, models from SQLite
- SQLite error: returns fresh session, logs warning
- Missing session row: returns fresh session, logs warning

**classify_intent**:
- LLM returns valid JSON with each intent type
- LLM returns invalid JSON: defaults to `"rag_query"`
- LLM raises exception: defaults to `"rag_query"`

**rewrite_query**:
- Valid structured output: returns `QueryAnalysis`
- `ValidationError` on first try: retries, succeeds on second
- Both attempts fail: returns single-question fallback `QueryAnalysis`

**aggregate_answers**:
- Multiple `SubAnswer` objects: merged text, deduplicated citations
- Duplicate `passage_id`: keeps highest `relevance_score`
- Empty `sub_answers`: returns appropriate fallback

**format_response**:
- Citations present: `[1]`, `[2]` markers in output
- `confidence_score < 70`: confidence summary appended
- `groundedness_result is None`: no `[unverified]` annotations

**summarize_history**:
- Under budget: returns unchanged state
- Over budget: calls LLM, returns compressed messages
- LLM fails during compression: returns unchanged state

**request_clarification**:
- `interrupt()` called with correct clarification question
- `iteration_count` incremented
- User response appended as `HumanMessage`

## Dependencies

- Wave 4 (API) must be complete: all implementation files finalized
- All node functions implemented in `backend/agent/nodes.py`
- All edge functions implemented in `backend/agent/edges.py`
- `backend/agent/schemas.py` has `QueryAnalysis`, `SubAnswer`, `Citation`

## Test Execution Policy

**NEVER run pytest directly inside Claude Code.** Use the external test runner:

```zsh
# Launch (returns immediately):
zsh scripts/run-tests-external.sh -n unit-wave5 tests/unit/test_edges.py tests/unit/test_nodes.py

# Poll status:
cat Docs/Tests/unit-wave5.status

# Read summary:
cat Docs/Tests/unit-wave5.summary

# Debug specific failures:
grep "FAILED" Docs/Tests/unit-wave5.log
grep -A5 "test_name" Docs/Tests/unit-wave5.log
```

Your job is to **write** the test files. Validation runs externally.

## Done Criteria

- [ ] `tests/unit/test_edges.py` covers `route_intent` (3 cases), `should_clarify` (5 cases)
- [ ] `tests/unit/test_nodes.py` covers all 11 node functions
- [ ] Each node test covers: success path, failure/fallback path, edge cases
- [ ] All tests pass (verified via external runner summary)
- [ ] No tests use real LLM calls, real database, or real network
- [ ] Tests use `monkeypatch.setenv()` not `os.environ[]`
- [ ] Async tests use `pytest.mark.asyncio` decorator
