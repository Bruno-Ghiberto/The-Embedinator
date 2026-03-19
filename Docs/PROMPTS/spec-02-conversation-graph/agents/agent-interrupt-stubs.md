# Agent: Interrupt & Stubs

**Mission**: Implement the `request_clarification` node with LangGraph interrupt/resume, and the Phase 2 stub nodes `verify_groundedness` and `validate_citations`.

**Subagent Type**: `python-expert`
**Model**: `sonnet`
**Wave**: 2 (Parallel -- runs in worktree alongside Agents A, B, C)

## Assigned Tasks

- **T023**: Implement `verify_groundedness(state: ConversationState, *, llm) -> dict` Phase 2 stub in `backend/agent/nodes.py` -- immediately returns `{"groundedness_result": None}`; add `# Phase 2: implement NLI-based claim verification` comment
- **T024**: Implement `validate_citations(state: ConversationState, *, reranker) -> dict` Phase 2 stub in `backend/agent/nodes.py` -- immediately returns `{"citations": state["citations"]}`; add `# Phase 2: implement cross-encoder citation alignment (threshold=0.3)` comment
- **T036**: Implement `request_clarification(state: ConversationState) -> dict` in `backend/agent/nodes.py` -- extract clarification question from `state["query_analysis"].clarification_needed`; call `interrupt(clarification_question)` from `langgraph.types`; when execution resumes (user response in `Command(resume=response)`), append user response as `HumanMessage` to `state["messages"]`; increment `state["iteration_count"]`; return updated state dict

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/nodes.py` | Replace `verify_groundedness`, `validate_citations`, and `request_clarification` stubs with implementations |

## Constraints

### verify_groundedness (Phase 2 stub)

- This is a pass-through stub. Do NOT implement actual verification logic
- Return `{"groundedness_result": None}` immediately
- Accept `llm` as keyword-only argument (for future Phase 2 signature compatibility)
- Add comment: `# Phase 2: implement NLI-based claim verification`
- Function is `async`

### validate_citations (Phase 2 stub)

- This is a pass-through stub. Do NOT implement actual validation logic
- Return `{"citations": state["citations"]}` -- pass citations through unchanged
- Accept `reranker` as keyword-only argument (for future Phase 2 signature compatibility)
- Add comment: `# Phase 2: implement cross-encoder citation alignment (threshold=0.3)`
- Function is `async`

### request_clarification

- Import `interrupt` from `langgraph.types`
- Import `HumanMessage` from `langchain_core.messages`
- Extract `clarification_question` from `state["query_analysis"].clarification_needed`
- Call `user_response = interrupt(clarification_question)` -- this pauses the graph and checkpoints state to SQLite
- When the graph resumes via `Command(resume=user_response)`, execution continues after the `interrupt()` call
- Append the user's response as `HumanMessage(content=user_response)` to the messages list
- Increment `iteration_count` by 1
- Return `{"messages": updated_messages, "iteration_count": new_count}`
- This function is NOT async (LangGraph interrupt is synchronous)
- The 2-round clarification cap is enforced by `should_clarify` in `edges.py`, not by this node

### General

- Use `structlog.get_logger()` for logging in `request_clarification`
- The stubs should be minimal -- they exist only to maintain the graph structure for Phase 2 activation

## Key Pattern: LangGraph Interrupt

```python
from langgraph.types import interrupt, Command

def request_clarification(state: ConversationState) -> dict:
    clarification = state["query_analysis"].clarification_needed
    user_response = interrupt(clarification)
    return {
        "messages": state["messages"] + [HumanMessage(content=user_response)],
        "iteration_count": state["iteration_count"] + 1,
    }
```

The `interrupt()` function:
1. Serializes the current graph state to the checkpointer (SQLite)
2. Yields the interrupt value back to the caller (appears in stream metadata as `__interrupt__`)
3. Pauses execution at this point
4. When `Command(resume=value)` is called, execution resumes and `interrupt()` returns the resume value

## Dependencies

- Wave 1 (Scaffold) must be complete: `nodes.py` exists with stubs, `state.py` has `intent` field
- `langgraph.types` must be importable (`langgraph>=1.0.10` from requirements)
- `QueryAnalysis` model with `clarification_needed` field exists in `backend/agent/schemas.py`

## Done Criteria

- [ ] `verify_groundedness` returns `{"groundedness_result": None}` immediately
- [ ] `verify_groundedness` accepts `llm` keyword argument without using it
- [ ] `validate_citations` returns `{"citations": state["citations"]}` immediately
- [ ] `validate_citations` accepts `reranker` keyword argument without using it
- [ ] `request_clarification` calls `interrupt()` with the clarification question
- [ ] `request_clarification` appends user response as `HumanMessage` to messages
- [ ] `request_clarification` increments `iteration_count` by 1
- [ ] `request_clarification` returns dict with `messages` and `iteration_count` keys
- [ ] Both Phase 2 stubs have comments indicating future implementation
