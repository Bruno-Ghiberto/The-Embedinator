# Spec-04 MetaReasoningGraph — Implementation Complete

## Status: DONE (2026-03-12)
- 47/47 tasks complete (T001–T046 + T041a)
- 41 spec-04 tests passing (27 node unit + 5 edge unit + 9 integration)
- 0 regressions (259 passed in full suite, 5 failures + 8 errors all pre-existing)

## Files Created
- `backend/agent/meta_reasoning_nodes.py` — 4 async nodes + 3 strategy helpers
- `backend/agent/meta_reasoning_edges.py` — `route_after_strategy`
- `backend/agent/meta_reasoning_graph.py` — `build_meta_reasoning_graph()`
- `tests/unit/test_meta_reasoning_nodes.py` — 27 tests
- `tests/unit/test_meta_reasoning_edges.py` — 5 tests
- `tests/integration/test_meta_reasoning_graph.py` — 9 tests

## Files Modified
- `backend/agent/prompts.py` — GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM
- `backend/agent/state.py` — `attempted_strategies: set[str]`
- `backend/config.py` — `meta_relevance_threshold=0.2`, `meta_variance_threshold=0.15`
- `backend/agent/research_graph.py` — mapper node closure + structlog/RunnableConfig imports
- `backend/main.py` — inside-out graph build + FR-011 guard
- `.env.example` — META_RELEVANCE_THRESHOLD, META_VARIANCE_THRESHOLD

## Key Implementation Details
- Config DI: `config["configurable"]["llm"]`, `config["configurable"]["reranker"]`, `config["configurable"].get("settings", settings)`
- Mapper node is a closure inside `build_research_graph()` — maps ResearchState↔MetaReasoningState
- "ALL" = search all collections, "ROTATE" = next collection (fall through to uncertainty if only one)
- FR-011: `max_attempts=0` → `meta_reasoning_graph=None` → routing keeps exhausted→fallback_response
- FR-017: infrastructure error during subgraph → return answer with error noted + confidence=0.0

## Gotchas Found During Implementation
- LangGraph compiled graph `.nodes.keys()` does NOT include `__end__`
- LangGraph compiled graph nodes are `PregelNode` objects, NOT directly callable
- External test runner takes only the LAST positional arg (run nodes and edges separately)
- Float comparison: `0.1 * 3 = 0.30000000000000004` — use epsilon in tests
- `ruff` catches unused imports even for types used implicitly via state TypedDict
