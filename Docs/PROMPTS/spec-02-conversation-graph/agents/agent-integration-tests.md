# Agent: Integration Tests

**Mission**: Write integration tests that verify full graph execution, interrupt/resume flow, NDJSON streaming output format, and error handling paths using the mock ResearchGraph.

**Subagent Type**: `quality-engineer`
**Model**: `opus`
**Wave**: 5 (Parallel -- runs in worktree alongside Agent-E)

## Assigned Tasks

- **T005**: Create `tests/mocks.py` with `build_mock_research_graph()` -- a compiled LangGraph `StateGraph(ResearchState)` with a single node that returns a fixed `SubAnswer` with one `Citation` and `confidence_score=0.85`
- **T030**: Write integration test for full RAG path in `tests/integration/test_conversation_graph.py` using mock ResearchGraph -- submit a complex question, verify metadata frame contains `confidence` (int 0-100) and `citations` list
- **T035**: Write integration test for session continuity in `tests/integration/test_conversation_graph.py` -- submit question + follow-up with same `thread_id`; verify follow-up answer references prior context from `state["messages"]`
- **T039**: Write integration test for clarification interrupt/resume in `tests/integration/test_conversation_graph.py` -- submit ambiguous query; verify `__interrupt__` in graph state; call `graph.invoke(Command(resume="the user clarification"), config)`; verify graph produces an answer; verify `iteration_count` is 1
- **T040**: Write integration test for 2-round clarification cap in `tests/integration/test_conversation_graph.py` -- trigger clarification twice with still-ambiguous responses; verify on third attempt `should_clarify` returns `False` (cap reached) and graph proceeds to `fan_out` with best-effort interpretation
- **T046**: Write integration test for full chat endpoint in `tests/integration/test_conversation_graph.py` using `httpx.AsyncClient` -- POST `/api/chat` with a valid request; parse NDJSON stream; verify chunk frames arrive, metadata frame is last, `confidence` is 0-100 integer, `citations` list is present
- **T047**: Write integration test for error paths in `tests/integration/test_conversation_graph.py` -- empty message (HTTP 400), no collections selected (error frame), all sub-questions fail (error frame with gap message)

## Files Created

| File | Purpose |
|------|---------|
| `tests/mocks.py` | `build_mock_research_graph()` -- mock ResearchGraph returning fixed SubAnswer |
| `tests/integration/test_conversation_graph.py` | All integration tests for graph execution, streaming, error handling |

## Constraints

### Mock ResearchGraph (tests/mocks.py)

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import ResearchState
from backend.agent.schemas import Citation, SubAnswer

def mock_research_node(state: ResearchState) -> dict:
    return {
        "answer": f"Mock answer for: {state['sub_question']}",
        "confidence_score": 0.85,
        "citations": [
            Citation(
                passage_id="mock-p1",
                document_id="mock-doc",
                document_name="test.pdf",
                start_offset=0,
                end_offset=100,
                text="Mock passage text for testing.",
                relevance_score=0.85,
            )
        ],
        "retrieved_chunks": [],
    }

def build_mock_research_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("research", mock_research_node)
    graph.add_edge(START, "research")
    graph.add_edge("research", END)
    return graph.compile()
```

### Integration Test Patterns

- Use `pytest-asyncio` for async tests
- Use `MemorySaver` checkpointer for tests (NOT `AsyncSqliteSaver` -- avoids file system dependency)
- Build full `ConversationState` dicts for graph invocation
- Use `graph.invoke()` for synchronous tests, `graph.astream()` for streaming tests
- For HTTP tests: use `httpx.AsyncClient` with `app` from `backend.main.create_app()`
- Mock LLM calls within nodes using `unittest.mock.patch` or dependency injection
- Thread IDs must be unique per test to avoid checkpoint collisions

### NDJSON Validation

When testing the chat endpoint, parse the response body line by line:

```python
lines = response.text.strip().split("\n")
frames = [json.loads(line) for line in lines]

# Verify frame types
chunk_frames = [f for f in frames if f["type"] == "chunk"]
metadata_frames = [f for f in frames if f["type"] == "metadata"]

assert len(metadata_frames) == 1
assert metadata_frames[0] == frames[-1]  # metadata is last
assert 0 <= metadata_frames[0]["confidence"] <= 100
assert isinstance(metadata_frames[0]["citations"], list)
```

### Clarification Interrupt Testing

```python
from langgraph.types import Command

# Submit ambiguous query
config = {"configurable": {"thread_id": "test-session-1"}}
result = graph.invoke(initial_state, config)

# Check for interrupt
state = graph.get_state(config)
assert state.next  # graph is paused
assert "__interrupt__" in str(state)  # interrupt is present

# Resume with clarification
result = graph.invoke(Command(resume="I meant the API docs"), config)
# Verify answer is produced
assert result.get("final_response") is not None
```

### Key Test Scenarios

**T030 -- Full RAG path**:
- Build state with a document question and selected collections
- Run graph to completion with mock ResearchGraph
- Verify `final_response` is populated
- Verify `confidence_score` is int 0-100
- Verify `citations` list is non-empty

**T035 -- Session continuity**:
- Invoke graph with question 1 using `thread_id="session-A"`
- Invoke graph with follow-up using same `thread_id`
- Verify messages from first invocation are present in second invocation state

**T039 -- Clarification interrupt/resume**:
- Set up state where `classify_intent` returns `"ambiguous"` or `rewrite_query` returns `is_clear=False`
- Verify graph pauses (interrupt detected)
- Resume with `Command(resume=clarification)`
- Verify graph completes with answer
- Verify `iteration_count` is 1

**T040 -- 2-round cap**:
- Trigger clarification twice (both responses still ambiguous)
- On third attempt, verify `should_clarify` returns `False`
- Verify graph proceeds to `fan_out` with best-effort interpretation

**T046 -- Chat endpoint NDJSON**:
- POST `/api/chat` with valid request body
- Parse response as NDJSON (line-delimited JSON)
- Verify content type is `application/x-ndjson`
- Verify chunk frames have `{"type": "chunk", "text": "..."}`
- Verify metadata frame is last with `confidence`, `citations`, `latency_ms`

**T047 -- Error paths**:
- Empty message: expect HTTP 400
- Empty `collection_ids`: expect error frame `{"type":"error","code":"NO_COLLECTIONS"}`

### Test Fixtures

```python
@pytest.fixture
def mock_research_graph():
    from tests.mocks import build_mock_research_graph
    return build_mock_research_graph()

@pytest.fixture
def conversation_graph(mock_research_graph):
    from backend.agent.conversation_graph import build_conversation_graph
    from langgraph.checkpoint.memory import MemorySaver
    return build_conversation_graph(mock_research_graph, checkpointer=MemorySaver())
```

## Dependencies

- Wave 4 (API) must be complete: `chat.py` refactored, `main.py` updated
- All node and edge functions implemented
- `build_conversation_graph()` compiles successfully
- `build_mock_research_graph()` creates valid mock (T005 is in this agent's scope)

## Test Execution Policy

**NEVER run pytest directly inside Claude Code.** Use the external test runner:

```zsh
# Launch (returns immediately):
zsh scripts/run-tests-external.sh -n integ-wave5 tests/integration/test_conversation_graph.py

# Poll status:
cat Docs/Tests/integ-wave5.status

# Read summary:
cat Docs/Tests/integ-wave5.summary

# Debug specific failures:
grep "FAILED" Docs/Tests/integ-wave5.log
grep -A5 "test_name" Docs/Tests/integ-wave5.log
```

Your job is to **write** the test files and the mock graph. Validation runs externally.

## Done Criteria

- [ ] `tests/mocks.py` provides `build_mock_research_graph()` returning valid compiled StateGraph
- [ ] Full RAG path test: graph executes end-to-end, produces response with citations and confidence
- [ ] Session continuity test: follow-up question uses prior conversation history
- [ ] Clarification interrupt test: graph pauses, resumes from checkpoint, produces answer
- [ ] 2-round cap test: after 2 clarifications, graph proceeds with best-effort
- [ ] Chat endpoint test: NDJSON response has correct frame types and order
- [ ] Error path tests: empty message (400), no collections (error frame)
- [ ] All tests pass (verified via external runner summary)
- [ ] No tests use real LLM calls or real Qdrant -- all dependencies mocked
- [ ] Each test uses a unique `thread_id` to avoid checkpoint collisions
