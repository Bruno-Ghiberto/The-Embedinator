# Agent: agent-a1-foundation

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 1

## Mission

Create all new file scaffolds with correct imports and function stubs, add 2 prompt constants, add `attempted_strategies` field to `MetaReasoningState`, and add 2 config threshold fields. Ensure all modules are importable before Wave 2 agents begin.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- full code specifications (the authoritative reference)
2. `backend/agent/state.py` -- `MetaReasoningState` TypedDict (add `attempted_strategies` field)
3. `backend/agent/prompts.py` -- existing prompts (append 2 new constants after line 184)
4. `backend/config.py` -- `Settings` class (add 2 threshold fields after line 42)
5. `backend/agent/schemas.py` -- `RetrievedChunk` model (use as-is, do NOT modify)
6. `backend/agent/research_nodes.py` -- reference for node signature pattern (`config: RunnableConfig = None`)
7. `backend/errors.py` -- existing error hierarchy (use as-is, do NOT modify)

## Assigned Tasks

- T001: Create `backend/agent/meta_reasoning_nodes.py` with module docstring, imports (`structlog`, `statistics`, `RunnableConfig`, `MetaReasoningState`, `settings`, `RetrievedChunk`, prompts), `logger = structlog.get_logger(__name__)`, strategy constants (`STRATEGY_WIDEN_SEARCH`, `STRATEGY_CHANGE_COLLECTION`, `STRATEGY_RELAX_FILTERS`, `FALLBACK_ORDER`), and 4 async function stubs + 3 private helper stubs with correct signatures and docstrings
- T002: Create `backend/agent/meta_reasoning_edges.py` with module docstring, imports, and `route_after_strategy` function stub
- T003: Create `backend/agent/meta_reasoning_graph.py` with module docstring, imports (`StateGraph`, `START`, `END`), and `build_meta_reasoning_graph` function stub
- T004: Add `GENERATE_ALT_QUERIES_SYSTEM` prompt constant to `backend/agent/prompts.py` with `{sub_question}` and `{chunk_summaries}` placeholders. Append after the `COLLECT_ANSWER_SYSTEM` constant (after line 184).
- T005: Add `REPORT_UNCERTAINTY_SYSTEM` prompt constant to `backend/agent/prompts.py` with no-fabrication guardrail. Append directly after `GENERATE_ALT_QUERIES_SYSTEM`.
- T006: Add `attempted_strategies: set[str]` field to `MetaReasoningState` TypedDict in `backend/agent/state.py` as the last field (after `uncertainty_reason`)
- T007: Add `meta_relevance_threshold: float = 0.2` and `meta_variance_threshold: float = 0.15` to `Settings` class in `backend/config.py` directly after `meta_reasoning_max_attempts: int = 2` (after line 42)

## Files to Create/Modify

- CREATE: `backend/agent/meta_reasoning_nodes.py`
- CREATE: `backend/agent/meta_reasoning_edges.py`
- CREATE: `backend/agent/meta_reasoning_graph.py`
- MODIFY: `backend/agent/prompts.py`
- MODIFY: `backend/agent/state.py`
- MODIFY: `backend/config.py`

## Key Patterns

- All node stubs MUST use: `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict:`
- NOT `config: RunnableConfig | None` -- this is a LangGraph quirk
- NOT `**kwargs` or `*, llm` keyword args -- use config DI
- `from langchain_core.runnables import RunnableConfig`
- `from __future__ import annotations` in all new files
- `logger = structlog.get_logger(__name__)` in all new files
- Private helpers `_build_modified_state_*` are regular sync functions, NOT async
- Function stubs should raise `NotImplementedError("Implemented in Wave 2")` or use `...`
- Prompt constants use exact placeholders from 04-implement.md
- `REPORT_UNCERTAINTY_SYSTEM` MUST include the no-fabrication guardrail text

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify `schemas.py`, `research_nodes.py`, `research_edges.py`, `research_graph.py`, `nodes.py`, or `edges.py`
- `meta_reasoning_max_attempts: int = 2` already exists in `config.py` -- do NOT duplicate it
- `MetaReasoningState` already has 10 fields (lines 52-63) -- only ADD `attempted_strategies` as field 11
- Prompt constants go AFTER line 184 in prompts.py (after the `COLLECT_ANSWER_SYSTEM` constant)
- Do NOT add `from __future__ import annotations` to files that do not already have it (state.py, config.py)

## Checkpoint

All new files exist with correct signatures. Running all of these succeeds:
```bash
python -c "from backend.agent.meta_reasoning_nodes import generate_alternative_queries, evaluate_retrieval_quality, decide_strategy, report_uncertainty; print('nodes OK')"
python -c "from backend.agent.meta_reasoning_edges import route_after_strategy; print('edges OK')"
python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; print('graph OK')"
python -c "from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM; print('prompts OK')"
python -c "from backend.agent.state import MetaReasoningState; print('state OK')"
python -c "from backend.config import settings; print(settings.meta_relevance_threshold, settings.meta_variance_threshold)"
ruff check .
```
