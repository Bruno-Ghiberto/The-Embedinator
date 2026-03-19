# Agent: agent-tools

**subagent_type**: python-expert | **Model**: Sonnet 4.6 | **Wave**: 2

## Mission

Implement the closure-based tool factory and all 6 LangChain tool definitions. Tools close over HybridSearcher, Reranker, and ParentStore dependencies injected at creation time.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- code spec for tools.py
2. `backend/agent/tools.py` -- stub from Wave 1 (fill in implementations)
3. `backend/agent/schemas.py` -- RetrievedChunk, ParentChunk return types
4. `backend/retrieval/searcher.py` -- HybridSearcher interface (search, search_all_collections)
5. `backend/retrieval/reranker.py` -- Reranker interface (rerank)
6. `backend/retrieval/score_normalizer.py` -- normalize_scores function
7. `backend/storage/parent_store.py` -- ParentStore interface (get_by_ids)

## Assigned Tasks

- T018: Implement `create_research_tools()` factory function
- T027: Implement `search_child_chunks` tool (hybrid search + rerank)
- T028: Implement `retrieve_parent_chunks` tool (SQLite read)
- T029: Implement `cross_encoder_rerank` tool (standalone rerank)
- T030: Implement `filter_by_collection` and `filter_by_metadata` tools (state modification)
- T031 (partial): Implement `semantic_search_all_collections` tool (fan-out + normalize + rerank)

## Files to Create/Modify

- MODIFY: `backend/agent/tools.py` (fill stubs from Wave 1)

## Key Patterns

- R6: Closure-based DI. `create_research_tools(searcher, reranker, parent_store)` returns a list of tool objects. Each tool is defined with `@tool` inside the factory function, closing over the infrastructure parameters. Tools are NOT module-level.
- All tools use `@tool` decorator from `langchain_core.tools`
- Tool docstrings are critical -- they become the schema that the LLM sees via `bind_tools()`
- `search_child_chunks` calls `searcher.search()` then `reranker.rerank()`
- `semantic_search_all_collections` calls `searcher.search_all_collections()`, `normalize_scores()`, then `reranker.rerank()`
- `filter_by_collection` and `filter_by_metadata` return plain dicts (state modification hints)

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER define tools at module level -- all must be inside `create_research_tools()`
- Tools must have complete docstrings (used by LLM for tool selection)
- Do NOT catch exceptions inside tools -- let them propagate to `tools_node` retry logic
- Do NOT modify files outside `backend/agent/tools.py`

## Checkpoint

`create_research_tools(searcher, reranker, parent_store)` returns a list of 6 tool objects. Each tool has correct type hints, args, and docstrings. Tools correctly delegate to injected dependencies.
