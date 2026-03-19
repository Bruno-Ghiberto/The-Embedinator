# Agent: Session & History

**Mission**: Implement the `init_session` and `summarize_history` node functions for session lifecycle management and conversation history compression.

**Subagent Type**: `python-expert`
**Model**: `sonnet`
**Wave**: 2 (Parallel -- runs in worktree alongside Agents B, C, D)

## Assigned Tasks

- **T012**: Implement `init_session(state: ConversationState, *, db) -> dict` in `backend/agent/nodes.py` -- load session row from SQLite `sessions` table by `session_id`; restore `messages` (deserialize JSON), `selected_collections`, `llm_model`, `embed_model`; on any exception create fresh session and log `structlog` warning with `session_id`
- **T031**: Implement `summarize_history(state: ConversationState, *, llm) -> dict` in `backend/agent/nodes.py` -- import `count_tokens_approximately` from `langchain_core.messages.utils`; check if token count > `get_context_budget(state["llm_model"])`; if yes, call LLM with `SUMMARIZE_HISTORY_SYSTEM` to produce summary of oldest 50% of messages; replace old messages with `[SystemMessage(content=summary)] + recent_messages`; write `state["messages"]`; on LLM failure return unchanged state and log warning

## Files Modified

| File | Changes |
|------|---------|
| `backend/agent/nodes.py` | Replace `init_session` and `summarize_history` stubs with implementations |

## Constraints

- `init_session` reads from SQLite `sessions` table. The schema is: `id TEXT PRIMARY KEY`, `messages_json TEXT`, `selected_collections TEXT`, `llm_model TEXT`, `embed_model TEXT`, `created_at TEXT`, `updated_at TEXT`
- Use `aiosqlite` for async SQLite access (already in requirements)
- Messages are serialized as JSON in the `messages_json` column. Deserialize using LangChain message types (`HumanMessage`, `AIMessage`, `SystemMessage`)
- On ANY exception during session load (missing row, JSON parse error, SQLite error), create a fresh session with empty messages and log a `structlog` warning including `session_id`
- `summarize_history` uses `count_tokens_approximately` from `langchain_core.messages.utils` -- NOT `tiktoken`
- `get_context_budget()` is already implemented in the same file (from Wave 1 scaffold)
- Compression triggers at 75% of model context window (the `get_context_budget` return value)
- When compressing: summarize the oldest 50% of messages using LLM with `SUMMARIZE_HISTORY_SYSTEM` prompt, keep the most recent 50% intact
- Replace compressed messages with `[SystemMessage(content=summary)] + recent_messages`
- On LLM failure during summarization: return state unchanged, log warning -- do NOT crash
- Both functions must use `structlog.get_logger()` for logging
- Both functions return `dict` (partial state update), not full `ConversationState`

## Dependencies

- Wave 1 (Scaffold) must be complete: `nodes.py` exists with stubs, `state.py` has `intent` field, `prompts.py` has `SUMMARIZE_HISTORY_SYSTEM`
- `get_context_budget()` and `MODEL_CONTEXT_WINDOWS` exist in `nodes.py` from T008

## Done Criteria

- [ ] `init_session` loads session from SQLite and returns dict with `messages`, `selected_collections`, `llm_model`, `embed_model`
- [ ] `init_session` creates fresh session on SQLite failure (returns empty `messages` list)
- [ ] `init_session` logs structlog warning with `session_id` on failure
- [ ] `summarize_history` is a no-op when messages are under 75% context budget
- [ ] `summarize_history` compresses oldest 50% of messages when over budget
- [ ] `summarize_history` replaces old messages with `[SystemMessage(summary)] + recent`
- [ ] `summarize_history` returns unchanged state on LLM failure
- [ ] Neither function raises unhandled exceptions
