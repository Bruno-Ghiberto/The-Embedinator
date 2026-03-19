# Agent: agent-scaffold

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 1

## Mission

Create all new files with correct module structure, imports, and function/class stubs. Add new prompt constants and the new config field. Ensure all modules are importable before Wave 2 agents begin.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- full implementation spec
2. `Docs/PROMPTS/spec-03-research-graph/03-plan.md` -- plan with file structure
3. `backend/agent/state.py` -- ResearchState definition (use as-is, do NOT modify)
4. `backend/agent/schemas.py` -- RetrievedChunk, ParentChunk, Citation, SubAnswer (use as-is)
5. `backend/agent/prompts.py` -- existing prompts to append to
6. `backend/config.py` -- add compression_threshold field
7. `backend/errors.py` -- existing error hierarchy (use as-is)

## Assigned Tasks

- T001-T004: Create `backend/retrieval/__init__.py`, `searcher.py`, `reranker.py`, `score_normalizer.py` with class/function stubs
- T005: Create `backend/storage/parent_store.py` with `ParentStore` stub
- T006: Create `backend/agent/tools.py` with `create_research_tools()` factory stub returning 6 tool stubs
- T007: Create `backend/agent/research_nodes.py` with 6 node function stubs
- T008: Create `backend/agent/research_edges.py` with 2 edge function stubs
- T009: Create `backend/agent/research_graph.py` with `build_research_graph()` stub
- T010: Append 4 prompt constants to `backend/agent/prompts.py` (ORCHESTRATOR_SYSTEM, ORCHESTRATOR_USER, COMPRESS_CONTEXT_SYSTEM, COLLECT_ANSWER_SYSTEM)
- T011: Add `compression_threshold: float = 0.75` to `backend/config.py` Settings class
- T012: Verify all new modules are importable (run `python -c "from backend.agent.research_graph import build_research_graph"` etc.)

## Files to Create/Modify

- CREATE: `backend/retrieval/__init__.py`
- CREATE: `backend/retrieval/searcher.py`
- CREATE: `backend/retrieval/reranker.py`
- CREATE: `backend/retrieval/score_normalizer.py`
- CREATE: `backend/storage/parent_store.py`
- CREATE: `backend/agent/tools.py`
- CREATE: `backend/agent/research_nodes.py`
- CREATE: `backend/agent/research_edges.py`
- CREATE: `backend/agent/research_graph.py`
- MODIFY: `backend/agent/prompts.py`
- MODIFY: `backend/config.py`

## Key Patterns

- All stubs must have correct type hints and docstrings matching 03-implement.md
- tools.py uses closure-based factory pattern (R6) -- NOT module-level @tool
- research_nodes.py and research_edges.py are SEPARATE files from nodes.py and edges.py
- Use `from __future__ import annotations` in all new files
- Follow existing structlog pattern: `logger = structlog.get_logger(__name__)`

## Constraints

- NEVER modify `state.py`, `schemas.py`, `nodes.py`, or `edges.py`
- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- Stubs must raise `NotImplementedError` or use `...` (ellipsis) -- Wave 2 agents fill them in
- Do NOT add tiktoken as a dependency
- Imports must work -- verify each new module is importable

## Checkpoint

All new files exist with correct signatures. Running `python -c "from backend.agent.research_graph import build_research_graph"` succeeds without ImportError. Prompt constants added to prompts.py. `compression_threshold` field exists in config.py.
