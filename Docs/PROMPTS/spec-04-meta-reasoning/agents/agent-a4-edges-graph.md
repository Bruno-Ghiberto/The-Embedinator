# Agent: agent-a4-edges-graph

**subagent_type**: backend-architect | **Model**: Sonnet 4.6 | **Wave**: 3

## Mission

Implement the `route_after_strategy` conditional edge function and the `build_meta_reasoning_graph()` graph builder. This wires the 4 node functions from Wave 2 into a compiled LangGraph StateGraph.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` -- code specs for `meta_reasoning_edges.py` and `meta_reasoning_graph.py`
2. `backend/agent/meta_reasoning_edges.py` -- stub from Wave 1 (fill in `route_after_strategy`)
3. `backend/agent/meta_reasoning_graph.py` -- stub from Wave 1 (fill in `build_meta_reasoning_graph`)
4. `backend/agent/meta_reasoning_nodes.py` -- 4 node functions from Wave 2 (import these)
5. `backend/agent/research_graph.py` -- reference for LangGraph graph builder pattern (`build_research_graph`)
6. `backend/agent/state.py` -- `MetaReasoningState` TypedDict
7. `specs/004-meta-reasoning/plan.md` -- graph flow diagram (Section "Graph Flow")

## Assigned Tasks

- T025: Implement `route_after_strategy` conditional edge function in `backend/agent/meta_reasoning_edges.py` -- return `"retry"` if `state["recovery_strategy"]` is set (truthy), return `"report"` if None/falsy
- T026: Implement `build_meta_reasoning_graph()` in `backend/agent/meta_reasoning_graph.py` -- create `StateGraph(MetaReasoningState)`, add 4 nodes, add edges: `START -> generate_alternative_queries -> evaluate_retrieval_quality -> decide_strategy`, add conditional edge from `decide_strategy` via `route_after_strategy` with map `{"retry": END, "report": "report_uncertainty"}`, add edge `report_uncertainty -> END`, return `graph.compile()`

## Files to Create/Modify

- MODIFY: `backend/agent/meta_reasoning_edges.py`
- MODIFY: `backend/agent/meta_reasoning_graph.py`

## Key Patterns

- **Graph flow**: `START -> generate_alternative_queries -> evaluate_retrieval_quality -> decide_strategy -> [retry: END | report: report_uncertainty -> END]`
- **Conditional edge**: `graph.add_conditional_edges("decide_strategy", route_after_strategy, {"retry": END, "report": "report_uncertainty"})`
- **"retry" -> END**: When strategy is set, the graph exits with `modified_state` populated. The ResearchGraph mapper node reads this and re-enters the orchestrator loop.
- **"report" -> report_uncertainty -> END**: When no strategy, produce uncertainty report then exit.
- **Edge function signature**: `def route_after_strategy(state: MetaReasoningState) -> str:` -- edge functions are sync, NOT async
- **route_after_strategy check**: Use `state.get("recovery_strategy")` -- truthy check is sufficient (strategy is a non-empty string or None)
- **Import pattern**: Follow `research_graph.py` -- import node functions and edge functions explicitly

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER modify node functions in `meta_reasoning_nodes.py` -- those are Wave 2 output
- NEVER modify `state.py`, `config.py`, `prompts.py`, or `research_graph.py`
- `build_meta_reasoning_graph` MUST return `graph.compile()` (compiled graph, not raw StateGraph)
- The compiled graph is passed to `build_research_graph(meta_reasoning_graph=...)` by A5 in Wave 4
- Do NOT add checkpointer to this graph -- it runs as a subgraph within ResearchGraph

## Checkpoint

`route_after_strategy` returns correct routing strings. `build_meta_reasoning_graph()` compiles without error. Running the following succeeds:
```bash
python -c "from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph; g = build_meta_reasoning_graph(); print('compiled:', type(g))"
python -c "from backend.agent.meta_reasoning_edges import route_after_strategy; print(route_after_strategy({'recovery_strategy': 'WIDEN_SEARCH'}))"
ruff check backend/agent/meta_reasoning_edges.py backend/agent/meta_reasoning_graph.py
```
