# Agent: agent-a3-query-uncertainty-nodes

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement `generate_alternative_queries` and `report_uncertainty` in `meta_reasoning_nodes.py`. These are the LLM-dependent nodes: one generates alternative query phrasings for retry, the other produces honest uncertainty reports when all recovery fails.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs (authoritative reference for all function bodies)
2. `backend/agent/meta_reasoning_nodes.py` -- stubs from Wave 1 (fill in the function bodies)
3. `backend/agent/prompts.py` -- `GENERATE_ALT_QUERIES_SYSTEM` and `REPORT_UNCERTAINTY_SYSTEM` constants (added by A1)
4. `backend/agent/state.py` -- `MetaReasoningState` TypedDict
5. `backend/agent/schemas.py` -- `RetrievedChunk` model (has `text`, `collection`, `rerank_score` fields)
6. `specs/004-meta-reasoning/spec.md` -- FR-001 (3 alternatives), FR-007/FR-008 (uncertainty report requirements)

## Assigned Tasks

- T012: Implement `generate_alternative_queries` async node -- resolve LLM from `config["configurable"]["llm"]`, format `GENERATE_ALT_QUERIES_SYSTEM` prompt with `sub_question` and chunk summaries, invoke LLM, parse response into exactly 3 alternatives, return `{"alternative_queries": list[str]}`
- T013: Add graceful degradation to `generate_alternative_queries` -- if LLM call fails: log warning, return `{"alternative_queries": [state["sub_question"]]}` (edge case from spec)
- T014: Add SSE status event and structlog event to `generate_alternative_queries` (FR-014, FR-016)
- T022: Implement `report_uncertainty` async node -- resolve LLM from `config["configurable"]["llm"]`, build context from state (sub_question, collections from chunks, alt_queries, mean_score, attempt count), invoke LLM with `REPORT_UNCERTAINTY_SYSTEM`, return `{"answer": str, "uncertainty_reason": str}`
- T023: Verify `REPORT_UNCERTAINTY_SYSTEM` prompt (from A1) includes the no-fabrication guardrail. If missing, add it directly: "Do NOT fabricate an answer. Do NOT say 'based on the available context' and then guess."
- T024: Add SSE status event and structlog event to `report_uncertainty` (FR-014, FR-016)

## Files to Create/Modify

- MODIFY: `backend/agent/meta_reasoning_nodes.py` (fill in function bodies for: `generate_alternative_queries`, `report_uncertainty`)

## Key Patterns

- **LLM via config DI**: `llm = config["configurable"]["llm"]` then `response = await llm.ainvoke([{"role": "system", ...}, {"role": "user", ...}])`
- **Alternative query parsing**: Expect numbered list or newline-separated. Strip number prefixes. Filter empty lines. Take first 3. Pad with original `sub_question` if fewer than 3.
- **Graceful degradation**: Wrap LLM call in try/except. On failure, return `{"alternative_queries": [sub_question]}` (not empty list, not raise).
- **Uncertainty context**: Build from state fields -- extract unique collections from `chunks[*].collection`, summarize top 5 chunks with text[:80] and rerank_score.
- **Static fallback for report_uncertainty**: If LLM fails, generate a template response without LLM (includes collections searched, chunk count, mean score, suggestions).
- **SSE events**: Emit via `config["configurable"]["callbacks"]` if available. Check for `on_custom_event` method. Format: `{"status": "...", "attempt": N}`.
- **Return partial dict**: `return {"alternative_queries": [...]}` -- NOT `{**state, ...}`
- **Node signature**: `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict:`

## CRITICAL: Shared File with A2

A1 creates `meta_reasoning_nodes.py` with all function stubs. You (A3) fill in `generate_alternative_queries` and `report_uncertainty`. Agent A2 (running in parallel) fills in `evaluate_retrieval_quality`, `decide_strategy`, and `_build_modified_state_*` helpers. You work on DIFFERENT functions in the SAME file. Do NOT touch A2's functions -- leave their stubs as-is.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER touch `evaluate_retrieval_quality`, `decide_strategy`, or `_build_modified_state_*` functions -- those belong to A2
- NEVER modify `prompts.py`, `state.py`, `config.py`, or `schemas.py` -- those are A1's output (except T023 prompt fix)
- `report_uncertainty` MUST NOT fabricate facts -- this is a hard constraint (FR-008)
- `report_uncertainty` MUST include collections searched, what was found, and suggestions (FR-007)
- `generate_alternative_queries` MUST produce exactly 3 alternatives when LLM succeeds (FR-001). Pad with original query if parsing yields fewer than 3.
- If `REPORT_UNCERTAINTY_SYSTEM` prompt is missing the no-fabrication guardrail (T023), the ONLY file you may modify besides `meta_reasoning_nodes.py` is `prompts.py`

## Checkpoint

`generate_alternative_queries` and `report_uncertainty` are fully implemented. Both handle error cases gracefully. Running the following succeeds:
```bash
python -c "from backend.agent.meta_reasoning_nodes import generate_alternative_queries, report_uncertainty; print('OK')"
ruff check backend/agent/meta_reasoning_nodes.py
```
