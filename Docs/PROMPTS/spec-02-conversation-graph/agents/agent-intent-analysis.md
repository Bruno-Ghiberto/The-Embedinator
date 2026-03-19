# Agent: Intent & Analysis

**Mission**: Implement the `classify_intent` and `rewrite_query` node functions for intent classification and query decomposition with LLM structured output.

**Subagent Type**: `python-expert`
**Model**: `opus`
**Wave**: 2 (Parallel -- runs in worktree alongside Agents A, C, D)

## Assigned Tasks

- **T016**: Implement `classify_intent(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` -- format `CLASSIFY_INTENT_USER` with last message + conversation history + selected collections; call LLM; parse JSON response for `{"intent": "..."}` key; write `state["intent"]`; on any exception default to `"rag_query"` and log warning
- **T021**: Implement `rewrite_query(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` -- format `REWRITE_QUERY_USER` with last message + collections + conversation context; call `llm.with_structured_output(QueryAnalysis)`; on `ValidationError` retry once with simplified single-question prompt; on second failure construct `QueryAnalysis(is_clear=True, sub_questions=[original_query], complexity_tier="lookup", collections_hint=[], clarification_needed=None)`; write `state["query_analysis"]`

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/nodes.py` | Replace `classify_intent` and `rewrite_query` stubs with implementations |

## Constraints

### classify_intent

- Format `CLASSIFY_INTENT_USER` template with: `{history}` = conversation history (formatted message list), `{message}` = last user message content, `{collections}` = comma-joined `selected_collections`
- Call LLM with `[SystemMessage(CLASSIFY_INTENT_SYSTEM), HumanMessage(formatted_user_prompt)]`
- Parse the LLM response as JSON to extract `{"intent": "rag_query"|"collection_mgmt"|"ambiguous"}`
- Valid intent values: `"rag_query"`, `"collection_mgmt"`, `"ambiguous"` -- reject any other value by defaulting to `"rag_query"`
- On ANY exception (LLM failure, JSON parse error, invalid intent value): default to `{"intent": "rag_query"}` and log warning via structlog
- Return `dict` with `{"intent": classified_intent}`

### rewrite_query

- Format `REWRITE_QUERY_USER` template with: `{question}` = last user message content, `{collections}` = available collection names, `{context}` = recent conversation context
- Use `llm.with_structured_output(QueryAnalysis)` for Pydantic structured output
- `QueryAnalysis` is imported from `backend.agent.schemas` -- fields: `is_clear`, `sub_questions` (max 5), `clarification_needed`, `collections_hint`, `complexity_tier`
- On `ValidationError` or parse failure: retry ONCE with a simplified prompt that asks for a single sub-question
- On second failure: construct fallback `QueryAnalysis(is_clear=True, sub_questions=[original_query], complexity_tier="lookup", collections_hint=[], clarification_needed=None)`
- Return `dict` with `{"query_analysis": analysis_result}`
- Use `structlog.get_logger()` for all logging

### General

- Both functions are `async`
- Both functions receive `llm` as a keyword-only argument (dependency injection)
- Use LangChain message types: `SystemMessage`, `HumanMessage` from `langchain_core.messages`
- Do NOT import LLM providers directly -- use the injected `llm` parameter
- Reuse existing `QueryAnalysis` from `backend.agent.schemas` -- do NOT redefine it

## Dependencies

- Wave 1 (Scaffold) must be complete: `nodes.py` exists with stubs, `prompts.py` has `CLASSIFY_INTENT_SYSTEM`, `CLASSIFY_INTENT_USER`, `REWRITE_QUERY_SYSTEM`, `REWRITE_QUERY_USER`
- `QueryAnalysis` model exists in `backend/agent/schemas.py` (from spec-01)

## Done Criteria

- [ ] `classify_intent` returns `{"intent": "rag_query"}` for document questions
- [ ] `classify_intent` returns `{"intent": "collection_mgmt"}` for collection commands
- [ ] `classify_intent` returns `{"intent": "ambiguous"}` for unclear messages
- [ ] `classify_intent` defaults to `{"intent": "rag_query"}` on LLM failure
- [ ] `classify_intent` defaults to `{"intent": "rag_query"}` on invalid JSON from LLM
- [ ] `rewrite_query` returns valid `QueryAnalysis` via `llm.with_structured_output()`
- [ ] `rewrite_query` retries once on `ValidationError`
- [ ] `rewrite_query` falls back to single-question `QueryAnalysis` on second failure
- [ ] Neither function raises unhandled exceptions
