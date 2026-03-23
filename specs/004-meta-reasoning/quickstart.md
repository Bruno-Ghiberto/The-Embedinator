# Quickstart: MetaReasoningGraph

**Branch**: `004-meta-reasoning` | **Date**: 2026-03-11

## Prerequisites

- Spec-01 (state.py, schemas.py, config.py) — implemented
- Spec-02 (ConversationGraph) — implemented
- Spec-03 (ResearchGraph, Reranker, research_edges.py) — implemented
- Python 3.14+, all dependencies from `requirements.txt`

## Implementation Order

### 1. Foundation (Wave 1)

Update existing files first:

```bash
# Files to modify:
backend/agent/prompts.py      # Add 2 prompt constants
backend/agent/state.py        # Add attempted_strategies to MetaReasoningState
backend/config.py             # Add meta_relevance_threshold, meta_variance_threshold
```

Verify: `python -c "from backend.agent.state import MetaReasoningState; print('OK')"`

### 2. Node Functions (Wave 2)

Create `backend/agent/meta_reasoning_nodes.py` with 4 async functions:

| Function | Dependencies | Key Behavior |
|----------|-------------|-------------|
| `generate_alternative_queries` | LLM via config | Produces 3 query variants |
| `evaluate_retrieval_quality` | Reranker via config | Scores ALL chunks, computes mean |
| `decide_strategy` | Settings (thresholds) | Selects strategy + builds modified_state |
| `report_uncertainty` | LLM via config | Honest uncertainty report |

All follow: `async def name(state: MetaReasoningState, config: RunnableConfig = None) -> dict`

### 3. Edges + Graph (Wave 3)

Create:
- `backend/agent/meta_reasoning_edges.py` — `route_after_strategy` conditional edge
- `backend/agent/meta_reasoning_graph.py` — `build_meta_reasoning_graph()` returning `CompiledGraph`

Graph flow: `START → generate_alternative_queries → evaluate_retrieval_quality → decide_strategy → [retry: END | report: report_uncertainty → END]`

### 4. Integration (Wave 4)

Wire into existing graphs:

```bash
# Files to modify:
backend/agent/research_edges.py   # "exhausted" → meta_reasoning (was fallback_response)
backend/agent/research_graph.py   # Accept + wire meta_reasoning subgraph
backend/main.py                   # Build inside-out: meta → research → conversation
```

### 5. Tests (Wave 5)

```bash
# Run unit tests:
zsh scripts/run-tests-external.sh -n spec04-unit tests/unit/test_meta_reasoning_nodes.py tests/unit/test_meta_reasoning_edges.py

# Run integration tests:
zsh scripts/run-tests-external.sh -n spec04-integration tests/integration/test_meta_reasoning_graph.py

# Run regression (all specs):
zsh scripts/run-tests-external.sh -n spec04-regression tests/
```

**NEVER run pytest inside Claude Code.** Always use `scripts/run-tests-external.sh`.

## Key Gotchas

1. **Config param type**: Use `config: RunnableConfig = None` — NOT `RunnableConfig | None` (LangGraph quirk)
2. **Return type**: Return `dict` (partial state), NOT full `MetaReasoningState`
3. **Confidence scale**: `settings.confidence_threshold` is `int` 0-100, `state["confidence_score"]` is `float` 0.0-1.0
4. **Reranker scoring**: Call `reranker.rerank(query, chunks, top_k=len(chunks))` to score ALL chunks
5. **Python syntax**: Use `list[str]`, `str | None` — NOT `List[str]`, `Optional[str]` (Python 3.14+)
6. **Empty chunks guard**: Protect against zero-division in mean/stdev calculations (FR-013)
7. **Strategy dedup**: Check `attempted_strategies` set before selecting (FR-015)
8. **max_attempts=0**: Skip meta-reasoning entirely, keep current `fallback_response` routing (FR-011)

## Environment Variables

```env
# New (optional — sensible defaults):
META_RELEVANCE_THRESHOLD=0.2      # Mean score below which retrieval is "poor"
META_VARIANCE_THRESHOLD=0.15      # Stdev above which results are "noisy"
META_REASONING_MAX_ATTEMPTS=2     # Max recovery attempts (0 = disabled)
```
