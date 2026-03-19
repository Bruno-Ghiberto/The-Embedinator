# Agent: agent-a2-eval-strategy-nodes

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 2

## Mission

Implement `evaluate_retrieval_quality`, `decide_strategy`, and the 3 private `_build_modified_state_*` helpers in `meta_reasoning_nodes.py`. These are the quantitative evaluation and strategy selection functions that form the diagnostic core of the MetaReasoningGraph.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs (authoritative reference for all function bodies)
2. `backend/agent/meta_reasoning_nodes.py` -- stubs from Wave 1 (fill in the function bodies)
3. `backend/retrieval/reranker.py` -- `Reranker.rerank(query, chunks, top_k)` API (returns `list[RetrievedChunk]` with `rerank_score` populated)
4. `backend/agent/schemas.py` -- `RetrievedChunk` model (has `rerank_score: float | None`)
5. `backend/agent/state.py` -- `MetaReasoningState` TypedDict (verify `attempted_strategies` field exists)
6. `backend/config.py` -- `settings.meta_relevance_threshold`, `settings.meta_variance_threshold`, `settings.meta_reasoning_max_attempts`
7. `specs/004-meta-reasoning/plan.md` -- strategy decision logic table (Section "Strategy Decision Logic")
8. `specs/004-meta-reasoning/data-model.md` -- entity definitions, recovery strategy table

## Assigned Tasks

- T008: Implement `evaluate_retrieval_quality` async node -- resolve Reranker from `config["configurable"]["reranker"]`, call `reranker.rerank(sub_question, chunks, top_k=len(chunks))` to score ALL chunks, extract `rerank_score` per chunk, compute `mean_relevance_score = sum(scores) / len(scores)`, return partial dict
- T009: Add empty-chunks guard to `evaluate_retrieval_quality` -- if `not chunks`: return `{"mean_relevance_score": 0.0, "chunk_relevance_scores": []}` (FR-013)
- T010: Add Reranker unavailability guard -- if reranker is None or raises exception: log warning, return `{"mean_relevance_score": 0.0, "chunk_relevance_scores": []}` (FR-012)
- T011: Add SSE status event and structlog event to `evaluate_retrieval_quality` (FR-014, FR-016)
- T015: Implement `_build_modified_state_widen` helper -- returns `{"selected_collections": "ALL", "top_k_retrieval": 40, "alternative_queries": alt_queries}`
- T016: Implement `_build_modified_state_change_collection` helper -- returns `{"selected_collections": "ROTATE", "sub_question": alternative_queries[0]}`
- T017: Implement `_build_modified_state_relax` helper -- returns `{"top_k_retrieval": 40, "payload_filters": None, "top_k_rerank": 10}`
- T018: Implement `decide_strategy` async node -- compute `statistics.stdev(scores)` (guard `len < 2` -> 0.0), read thresholds from settings, select candidate per decision logic, call `_build_modified_state_*`, return partial dict
- T019: Add max_attempts guard to `decide_strategy` -- if `attempt >= max_attempts`: return `{"recovery_strategy": None}` (FR-006)
- T020: Add strategy deduplication to `decide_strategy` -- if candidate in `attempted_strategies`, try next from `FALLBACK_ORDER`; if none untried: return `{"recovery_strategy": None}` (FR-015)
- T021: Add structlog event to `decide_strategy` -- `log.info("strategy_selected", strategy=..., mean_score=..., variance=..., chunk_count=..., attempt=...)` (FR-016)

## Files to Create/Modify

- MODIFY: `backend/agent/meta_reasoning_nodes.py` (fill in function bodies for: `evaluate_retrieval_quality`, `decide_strategy`, `_build_modified_state_widen`, `_build_modified_state_change_collection`, `_build_modified_state_relax`)

## Key Patterns

- **Reranker API**: Call `reranker.rerank(sub_question, chunks, top_k=len(chunks))` -- this returns `list[RetrievedChunk]` with `rerank_score` populated. Do NOT call `reranker.model.predict()` or `reranker.model.rank()` directly.
- **Config DI**: `reranker = config["configurable"]["reranker"]` and `settings_obj = config["configurable"].get("settings", settings)`
- **Variance computation (R2)**: Use `statistics.stdev(scores)` (standard deviation), NOT `statistics.variance()`. Guard `len(scores) < 2` -> return 0.0.
- **Strategy decision thresholds (R4)**: `cfg_settings.meta_relevance_threshold` (default 0.2) and `cfg_settings.meta_variance_threshold` (default 0.15). Do NOT hardcode.
- **Strategy dedup (FR-015)**: If candidate is in `attempted_strategies`, iterate `FALLBACK_ORDER` to find next untried. If none untried, return `recovery_strategy=None`.
- **Return partial dict**: `return {"recovery_strategy": ..., "modified_state": ..., "meta_attempt_count": ...}` -- NOT `{**state, ...}`
- **Node signature**: `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict:` -- NOT `RunnableConfig | None`
- **Private helpers are sync**: `_build_modified_state_*` are regular functions, NOT async

## CRITICAL: Shared File with A3

A1 creates `meta_reasoning_nodes.py` with all function stubs. You (A2) fill in `evaluate_retrieval_quality`, `decide_strategy`, `_build_modified_state_widen`, `_build_modified_state_change_collection`, and `_build_modified_state_relax`. Agent A3 (running in parallel) fills in `generate_alternative_queries` and `report_uncertainty`. You work on DIFFERENT functions in the SAME file. Do NOT touch A3's functions -- leave their stubs as-is.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER touch `generate_alternative_queries` or `report_uncertainty` -- those belong to A3
- NEVER modify `reranker.py`, `schemas.py`, `state.py`, `config.py`, or `prompts.py` -- those are A1's output
- NEVER call `reranker.model.predict()` directly -- use `reranker.rerank(query, chunks, top_k)`
- NEVER hardcode threshold values -- always read from `cfg_settings.meta_relevance_threshold` / `cfg_settings.meta_variance_threshold`
- Edge case: identical scores (all equal) -> `stdev=0.0`, so if `mean < threshold`, still routes to WIDEN_SEARCH or CHANGE_COLLECTION based on chunk count

## Checkpoint

`evaluate_retrieval_quality` and `decide_strategy` are fully implemented. All 3 `_build_modified_state_*` helpers return correct dicts. Running the following succeeds:
```bash
python -c "from backend.agent.meta_reasoning_nodes import evaluate_retrieval_quality, decide_strategy; print('OK')"
ruff check backend/agent/meta_reasoning_nodes.py
```
