# Agent: agent-nodes

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the 6 ResearchGraph node functions, 2 edge functions, update confidence.py with the 5-signal formula, and add prompt constants.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- code specs for research_nodes.py, research_edges.py, confidence.py
2. `backend/agent/research_nodes.py` -- stubs from Wave 1
3. `backend/agent/research_edges.py` -- stubs from Wave 1
4. `backend/agent/confidence.py` -- Phase 1 placeholder to replace
5. `backend/agent/nodes.py` -- `get_context_budget()`, `MODEL_CONTEXT_WINDOWS` (use, do not modify)
6. `backend/agent/state.py` -- ResearchState TypedDict
7. `backend/agent/prompts.py` -- verify prompt constants from Wave 1
8. `backend/config.py` -- Settings fields (confidence_threshold, max_iterations, etc.)

## Assigned Tasks

- T019: Implement `orchestrator` node (bind tools, invoke LLM, parse tool_calls, set `_no_new_tools` flag)
- T020: Implement `tools_node` (execute tool calls with retry-once, deduplicate, merge)
- T021: Implement `should_compress_context` node (token counting via `count_tokens_approximately`, set `_needs_compression` flag)
- T022: Implement `compress_context` node (LLM summarization, preserve citations)
- T032: Implement `collect_answer` node (generate answer, build citations, compute confidence)
- T034: Implement `fallback_response` node (graceful insufficient-info response)
- T035: Implement `should_continue_loop` edge function
- T036: Implement `route_after_compress_check` edge function
- T040: Replace `confidence.py` placeholder with 5-signal formula
- T041: Add `normalize_query()` and `dedup_key()` helper functions

## Files to Create/Modify

- MODIFY: `backend/agent/research_nodes.py`
- MODIFY: `backend/agent/research_edges.py`
- MODIFY: `backend/agent/confidence.py`

## Key Patterns

- F1 (CRITICAL): `should_continue_loop` MUST check confidence FIRST, then budget. If `confidence >= threshold`, return "sufficient" regardless of remaining budget.
- F2: `tools_node` MUST include retry-once logic: try -> except -> count+1 -> retry -> count+1 (R7). Both attempts count against budget.
- F3: `should_compress_context` MUST set `_needs_compression` flag in returned dict. `route_after_compress_check` reads this flag.
- F4: `orchestrator` MUST set `_no_new_tools` flag when LLM returns zero tool calls.
- R3: Use `count_tokens_approximately` from `langchain_core.messages.utils`. Do NOT use tiktoken.
- R7: Retry-once: both original and retry count against `max_tool_calls` budget.
- R8: 5-signal confidence: `mean_rerank(0.4) + chunk_count(0.2) + top_score(0.2) + variance(0.1) + coverage(0.1)`. Returns float 0.0-1.0.
- CONFIDENCE SCALE: `settings.confidence_threshold` is int 60. State `confidence_score` is float 0.0-1.0. Edge must convert: `threshold / 100`.
- FR-017: structlog logging at ALL decision points.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `nodes.py` or `edges.py` (those belong to ConversationGraph)
- NEVER use tiktoken for token counting -- use `count_tokens_approximately` (R3)
- confidence.py must return float 0.0-1.0, NOT int 0-100
- `fallback_response` must NOT hallucinate -- only report what was actually searched/found
- Use existing `get_context_budget()` from `backend/agent/nodes.py` for compression threshold

## Checkpoint

All 6 node functions and 2 edge functions are implemented. `should_continue_loop` checks confidence first (F1). `tools_node` has retry-once (R7). `confidence.py` implements 5-signal formula returning float 0.0-1.0. All functions have structlog logging.
