# Spec 04: MetaReasoningGraph -- Implementation Plan Context

## Component Overview

The MetaReasoningGraph is the failure recovery layer of the three-layer agent. It diagnoses retrieval failures using quantitative cross-encoder scoring rather than LLM self-assessment, selects a recovery strategy based on the failure pattern, modifies state, and re-enters the ResearchGraph for another attempt. It prevents silent failures and gives the system a second chance to find relevant evidence before admitting uncertainty.

## Technical Approach

- **LangGraph StateGraph**: Define `MetaReasoningGraph` using `StateGraph(MetaReasoningState)` with a linear flow through evaluation and decision nodes, plus conditional routing to strategy-specific state modification or uncertainty reporting.
- **Cross-Encoder Scoring**: Use `sentence-transformers` `CrossEncoder` for quantitative retrieval quality evaluation. Score every (sub_question, chunk) pair and compute mean.
- **Strategy Pattern**: Each recovery strategy (WIDEN_SEARCH, CHANGE_COLLECTION, RELAX_FILTERS) produces a `modified_state` dict that overwrites specific fields of the ResearchState before re-entry.
- **Attempt Counter**: `meta_attempt_count` is incremented each time the MetaReasoningGraph runs. At >= 2, `report_uncertainty` is forced.
- **LLM for Query Generation**: Use the active LLM for generating alternative query formulations and for the uncertainty report.

## File Structure

```
backend/
  agent/
    meta_reasoning_graph.py  # StateGraph definition for MetaReasoningGraph
    nodes.py                 # Add MetaReasoningGraph node functions
    edges.py                 # Add MetaReasoningGraph edge functions
    prompts.py               # Add meta-reasoning prompt templates
    state.py                 # MetaReasoningState (already created in spec-01)
```

## Implementation Steps

1. **Add meta-reasoning prompts to `backend/agent/prompts.py`**:
   - `GENERATE_ALT_QUERIES_SYSTEM` template
   - `REPORT_UNCERTAINTY_SYSTEM` template

2. **Implement MetaReasoningGraph node functions in `backend/agent/nodes.py`**:
   - `generate_alternative_queries(state, *, llm)` -- LLM call to produce 3 alternative formulations
   - `evaluate_retrieval_quality(state, *, reranker)` -- Cross-encoder scoring of all chunks
   - `decide_strategy(state)` -- Pure logic: classify failure mode and select strategy
   - `report_uncertainty(state, *, llm)` -- Generate honest uncertainty response

3. **Implement MetaReasoningGraph edge functions in `backend/agent/edges.py`**:
   - `route_strategy(state)` -- Returns strategy node name or "report_uncertainty" based on decision logic
   - `should_retry_or_report(state)` -- Check meta_attempt_count, return "retry" or "report"

4. **Define the graph in `backend/agent/meta_reasoning_graph.py`**:
   - Create `StateGraph(MetaReasoningState)`
   - Linear flow: `generate_alternative_queries` -> `evaluate_retrieval_quality` -> `decide_strategy`
   - Conditional edges from `decide_strategy` to strategy application or `report_uncertainty`
   - Terminal: modified_state ready for ResearchGraph re-entry, or answer from report_uncertainty
   - Compile

5. **Integrate with ResearchGraph (spec-03)**:
   - Pass compiled MetaReasoningGraph to `build_research_graph(meta_reasoning_graph=compiled_mrg)`
   - Ensure state mapping between MetaReasoningState and ResearchState

6. **Wire up in `backend/main.py`**:
   - Build MetaReasoningGraph first
   - Pass to ResearchGraph builder
   - Pass ResearchGraph to ConversationGraph builder

## Integration Points

- **ResearchGraph (spec-03)**: MetaReasoningGraph is invoked as a subgraph node in ResearchGraph. It receives state when confidence is below threshold and budget is exhausted. It produces `modified_state` that the ResearchGraph uses to reset its loop parameters for a retry.
- **Cross-Encoder (shared)**: The same `CrossEncoder` instance used by ResearchGraph's reranker is used by `evaluate_retrieval_quality` to score chunks.
- **LLM (shared)**: Uses the same LLM provider as the ResearchGraph for alternative query generation and uncertainty reporting.
- **ConversationGraph (spec-02)**: Not directly connected. ConversationGraph receives the final SubAnswer from ResearchGraph regardless of whether MetaReasoningGraph was involved.

## Key Code Patterns

### MetaReasoningGraph Definition

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import MetaReasoningState
from backend.agent.nodes import (
    generate_alternative_queries, evaluate_retrieval_quality,
    decide_strategy, report_uncertainty,
)
from backend.agent.edges import route_after_strategy


def build_meta_reasoning_graph():
    graph = StateGraph(MetaReasoningState)

    graph.add_node("generate_alternative_queries", generate_alternative_queries)
    graph.add_node("evaluate_retrieval_quality", evaluate_retrieval_quality)
    graph.add_node("decide_strategy", decide_strategy)
    graph.add_node("report_uncertainty", report_uncertainty)

    graph.add_edge(START, "generate_alternative_queries")
    graph.add_edge("generate_alternative_queries", "evaluate_retrieval_quality")
    graph.add_edge("evaluate_retrieval_quality", "decide_strategy")
    graph.add_conditional_edges("decide_strategy", route_after_strategy, {
        "retry": END,              # modified_state ready for ResearchGraph re-entry
        "report": "report_uncertainty",
    })
    graph.add_edge("report_uncertainty", END)

    return graph.compile()
```

### Strategy State Modification Pattern

```python
def decide_strategy(state: MetaReasoningState) -> MetaReasoningState:
    mean_score = state["mean_relevance_score"]
    chunk_count = len(state["retrieved_chunks"])
    attempt_count = state["meta_attempt_count"]

    if attempt_count >= 2:
        return {**state, "recovery_strategy": None}  # force report_uncertainty

    if mean_score < 0.2 and chunk_count < 3:
        return {
            **state,
            "recovery_strategy": "WIDEN_SEARCH",
            "modified_state": {
                "selected_collections": [],  # search all
                "sub_question": state["alternative_queries"][0],
                "retrieved_chunks": [],
                "retrieval_keys": set(),
                "tool_call_count": 0,
                "iteration_count": 0,
                "confidence_score": 0.0,
                "context_compressed": False,
            },
            "meta_attempt_count": attempt_count + 1,
        }

    if mean_score < 0.2 and chunk_count >= 3:
        return {
            **state,
            "recovery_strategy": "CHANGE_COLLECTION",
            "modified_state": {
                "sub_question": state["alternative_queries"][0],
                # Keep different collections (rotation logic)
                "retrieved_chunks": [],
                "retrieval_keys": set(),
                "tool_call_count": 0,
                "iteration_count": 0,
                "confidence_score": 0.0,
                "context_compressed": False,
            },
            "meta_attempt_count": attempt_count + 1,
        }

    # mean_score >= 0.2 but coherence issue
    return {
        **state,
        "recovery_strategy": "RELAX_FILTERS",
        "modified_state": {
            # Keep existing chunks but reset loop counters
            "tool_call_count": 0,
            "iteration_count": 0,
            "confidence_score": 0.0,
            # Relax retrieval parameters in state
        },
        "meta_attempt_count": attempt_count + 1,
    }
```

### Cross-Encoder Quality Evaluation

```python
async def evaluate_retrieval_quality(
    state: MetaReasoningState, *, reranker
) -> MetaReasoningState:
    sub_q = state["sub_question"]
    chunks = state["retrieved_chunks"]

    if not chunks:
        return {
            **state,
            "mean_relevance_score": 0.0,
            "chunk_relevance_scores": [],
        }

    pairs = [(sub_q, chunk.text) for chunk in chunks]
    scores = reranker.predict(pairs)
    scores_list = [float(s) for s in scores]
    mean_score = sum(scores_list) / len(scores_list)

    return {
        **state,
        "mean_relevance_score": mean_score,
        "chunk_relevance_scores": scores_list,
    }
```

### Graph Assembly Order (backend/main.py)

```python
# Build graphs inside-out:
meta_reasoning_graph = build_meta_reasoning_graph()
research_graph = build_research_graph(meta_reasoning_graph=meta_reasoning_graph)
conversation_graph = build_conversation_graph(research_graph_compiled=research_graph)

app.state.conversation_graph = conversation_graph
```

## Phase Assignment

- **Phase 2 (Performance & Resilience)**: MetaReasoningGraph is a Phase 2 feature. In Phase 1, the ResearchGraph routes budget exhaustion to `fallback_response` directly. In Phase 2, MetaReasoningGraph is built and wired in.
  - Phase 2 includes: All four nodes, strategy decision logic, cross-encoder quality evaluation, retry loop with attempt counter, report_uncertainty.
