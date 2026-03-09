# Spec 04: MetaReasoningGraph -- Implementation Context

## Implementation Scope

### Files to Create / Modify

| File | Action | Purpose |
|------|--------|---------|
| `backend/agent/meta_reasoning_graph.py` | Create | StateGraph definition for MetaReasoningGraph |
| `backend/agent/nodes.py` | Modify | Add MetaReasoningGraph node functions |
| `backend/agent/edges.py` | Modify | Add MetaReasoningGraph edge functions |
| `backend/agent/prompts.py` | Modify | Add meta-reasoning prompt templates |
| `backend/agent/research_graph.py` | Modify | Wire in MetaReasoningGraph as subgraph |
| `backend/main.py` | Modify | Build and wire all three graphs in correct order |

## Code Specifications

### backend/agent/meta_reasoning_graph.py

```python
from langgraph.graph import StateGraph, START, END
from backend.agent.state import MetaReasoningState
from backend.agent.nodes import (
    generate_alternative_queries,
    evaluate_retrieval_quality,
    decide_strategy,
    report_uncertainty,
)
from backend.agent.edges import route_after_strategy


def build_meta_reasoning_graph():
    """Build and compile the MetaReasoningGraph.

    Flow:
    START -> generate_alternative_queries -> evaluate_retrieval_quality
          -> decide_strategy -> [retry (END) | report_uncertainty -> END]

    When the graph exits with recovery_strategy set and modified_state populated,
    the ResearchGraph uses modified_state to reset its loop and retry.
    When the graph exits via report_uncertainty, the answer and uncertainty_reason
    are propagated back through the ResearchGraph to the ConversationGraph.

    Returns:
        Compiled LangGraph StateGraph.
    """
    graph = StateGraph(MetaReasoningState)

    # Nodes
    graph.add_node("generate_alternative_queries", generate_alternative_queries)
    graph.add_node("evaluate_retrieval_quality", evaluate_retrieval_quality)
    graph.add_node("decide_strategy", decide_strategy)
    graph.add_node("report_uncertainty", report_uncertainty)

    # Edges
    graph.add_edge(START, "generate_alternative_queries")
    graph.add_edge("generate_alternative_queries", "evaluate_retrieval_quality")
    graph.add_edge("evaluate_retrieval_quality", "decide_strategy")
    graph.add_conditional_edges("decide_strategy", route_after_strategy, {
        "retry": END,               # modified_state ready; ResearchGraph re-enters
        "report": "report_uncertainty",
    })
    graph.add_edge("report_uncertainty", END)

    return graph.compile()
```

### backend/agent/nodes.py -- MetaReasoningGraph Nodes

```python
import structlog
from typing import List
from sentence_transformers import CrossEncoder

from backend.agent.state import MetaReasoningState
from backend.agent.schemas import RetrievedChunk
from backend.agent.prompts import GENERATE_ALT_QUERIES_SYSTEM, REPORT_UNCERTAINTY_SYSTEM
from backend.config import Settings

logger = structlog.get_logger()
settings = Settings()

# --- MetaReasoningGraph nodes ---

async def generate_alternative_queries(
    state: MetaReasoningState,
    *,
    llm,
) -> MetaReasoningState:
    """Produce 3 rephrased query variants using LLM.

    Strategies applied:
    1. Rephrase using different terminology (synonyms, technical vs. plain language)
    2. Break into simpler sub-components
    3. Broaden the scope (remove specific constraints)

    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["alternative_queries"] (List[str], length 3)
    """
    sub_question = state["sub_question"]
    chunk_summaries = "\n".join(
        f"- {c.text[:100]}..." for c in state["retrieved_chunks"][:5]
    )

    prompt = GENERATE_ALT_QUERIES_SYSTEM.format(
        sub_question=sub_question,
        chunk_summaries=chunk_summaries or "(no chunks retrieved)",
    )

    response = await llm.ainvoke([
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Generate 3 alternative queries for: {sub_question}"},
    ])

    # Parse response into list of 3 queries
    # Expected format: numbered list or newline-separated
    lines = [
        line.strip().lstrip("0123456789.-) ")
        for line in response.content.strip().split("\n")
        if line.strip() and not line.strip().startswith("#")
    ]
    alternative_queries = lines[:3] if len(lines) >= 3 else lines + [sub_question]

    return {**state, "alternative_queries": alternative_queries}


async def evaluate_retrieval_quality(
    state: MetaReasoningState,
    *,
    reranker: CrossEncoder,
) -> MetaReasoningState:
    """Score all retrieved chunks with cross-encoder.

    Computes mean relevance score across all chunks. This is a quantitative
    signal (not LLM self-assessment) that drives strategy selection.

    Reads: state["sub_question"], state["retrieved_chunks"]
    Writes: state["mean_relevance_score"], state["chunk_relevance_scores"]
    """
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

    logger.info(
        "meta_reasoning.retrieval_quality",
        mean_score=round(mean_score, 4),
        chunk_count=len(chunks),
        min_score=round(min(scores_list), 4),
        max_score=round(max(scores_list), 4),
    )

    return {
        **state,
        "mean_relevance_score": mean_score,
        "chunk_relevance_scores": scores_list,
    }


def decide_strategy(state: MetaReasoningState) -> MetaReasoningState:
    """Select recovery strategy based on quantitative evaluation.

    Decision logic:
    1. meta_attempt_count >= 2 -> force report_uncertainty (no more retries)
    2. mean_score < 0.2 AND chunk_count < 3 -> WIDEN_SEARCH
    3. mean_score < 0.2 AND chunk_count >= 3 -> CHANGE_COLLECTION
    4. mean_score >= 0.2 AND coherence issues -> RELAX_FILTERS
    5. None of the above -> report_uncertainty

    Reads: state["mean_relevance_score"], state["chunk_relevance_scores"],
           state["meta_attempt_count"]
    Writes: state["recovery_strategy"], state["modified_state"],
            state["meta_attempt_count"] (incremented)
    """
    mean_score = state["mean_relevance_score"]
    chunk_count = len(state["retrieved_chunks"])
    attempt_count = state["meta_attempt_count"]

    # Guard: max 2 meta-reasoning attempts
    if attempt_count >= settings.meta_reasoning_max_attempts:
        logger.info(
            "meta_reasoning.max_attempts_reached",
            attempt_count=attempt_count,
        )
        return {
            **state,
            "recovery_strategy": None,
            "modified_state": None,
        }

    alt_queries = state.get("alternative_queries", [])
    alt_query = alt_queries[0] if alt_queries else state["sub_question"]

    if mean_score < 0.2 and chunk_count < 3:
        # Few chunks with low relevance -> widen search
        logger.info("meta_reasoning.strategy", strategy="WIDEN_SEARCH")
        return {
            **state,
            "recovery_strategy": "WIDEN_SEARCH",
            "modified_state": {
                "sub_question": alt_query,
                "selected_collections": [],  # search all collections
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
        # Many chunks but irrelevant -> change collection
        logger.info("meta_reasoning.strategy", strategy="CHANGE_COLLECTION")
        return {
            **state,
            "recovery_strategy": "CHANGE_COLLECTION",
            "modified_state": {
                "sub_question": alt_query,
                # Collection rotation: exclude currently searched collections
                "retrieved_chunks": [],
                "retrieval_keys": set(),
                "tool_call_count": 0,
                "iteration_count": 0,
                "confidence_score": 0.0,
                "context_compressed": False,
            },
            "meta_attempt_count": attempt_count + 1,
        }

    if mean_score >= 0.2:
        # Moderate relevance but coherence issues -> relax filters
        logger.info("meta_reasoning.strategy", strategy="RELAX_FILTERS")
        return {
            **state,
            "recovery_strategy": "RELAX_FILTERS",
            "modified_state": {
                "sub_question": state["sub_question"],  # keep original
                # Keep existing retrieved_chunks (they have some relevance)
                "tool_call_count": 0,
                "iteration_count": 0,
                "confidence_score": 0.0,
                # Signal to ResearchGraph: increase top_k, remove metadata filters
            },
            "meta_attempt_count": attempt_count + 1,
        }

    # No strategy applies
    return {
        **state,
        "recovery_strategy": None,
        "modified_state": None,
    }


async def report_uncertainty(
    state: MetaReasoningState,
    *,
    llm=None,
) -> MetaReasoningState:
    """Generate honest "I don't know" response.

    Explains what was searched, what was found (if anything), why results
    were insufficient, and suggests user actions. Does NOT fabricate an answer.

    Reads: state["sub_question"], state["mean_relevance_score"],
           state["retrieved_chunks"]
    Writes: state["answer"], state["uncertainty_reason"]
    """
    sub_q = state["sub_question"]
    mean_score = state["mean_relevance_score"]
    chunk_count = len(state["retrieved_chunks"])

    # Build context for the uncertainty report
    if chunk_count == 0:
        found_summary = "No relevant document chunks were found."
        reason = "The search returned no results across the available collections."
    elif mean_score < 0.2:
        found_summary = (
            f"Found {chunk_count} document chunks, but their relevance scores "
            f"were very low (mean: {mean_score:.2f})."
        )
        reason = (
            "The retrieved chunks did not contain information relevant to your question. "
            "The documents in the available collections may not cover this topic."
        )
    else:
        found_summary = (
            f"Found {chunk_count} partially relevant chunks "
            f"(mean relevance: {mean_score:.2f}), but could not construct "
            f"a confident answer."
        )
        reason = (
            "While some relevant information was found, it was insufficient "
            "to fully answer the question with confidence."
        )

    answer = (
        f"I was unable to find sufficient evidence to answer your question: "
        f"\"{sub_q}\"\n\n"
        f"{found_summary}\n\n"
        f"Suggestions:\n"
        f"- Try rephrasing your question using different terminology\n"
        f"- Check if the relevant documents have been uploaded to a collection\n"
        f"- Try selecting a different collection that may contain this information\n"
        f"- Upload additional documents that cover this topic"
    )

    uncertainty_reason = reason

    logger.info(
        "meta_reasoning.report_uncertainty",
        sub_question=sub_q,
        mean_relevance=round(mean_score, 4),
        chunk_count=chunk_count,
    )

    return {
        **state,
        "answer": answer,
        "uncertainty_reason": uncertainty_reason,
    }
```

### backend/agent/edges.py -- MetaReasoningGraph Edges

```python
from backend.agent.state import MetaReasoningState


def route_after_strategy(state: MetaReasoningState) -> str:
    """Route after decide_strategy.

    Returns:
        "retry": recovery_strategy is set, modified_state is ready.
                 ResearchGraph will re-enter with new parameters.
        "report": No strategy available (max attempts or no applicable strategy).
                  Route to report_uncertainty.
    """
    if state.get("recovery_strategy") and state.get("modified_state") is not None:
        return "retry"
    return "report"
```

### backend/agent/prompts.py -- MetaReasoningGraph Additions

```python
# --- MetaReasoningGraph prompts ---

GENERATE_ALT_QUERIES_SYSTEM = """The retrieval system failed to find sufficient evidence
for the following question. Generate 3 alternative query formulations that might
retrieve better results.

Strategies to try:
1. Rephrase using different terminology (synonyms, technical vs. plain language)
2. Break into simpler sub-components
3. Broaden the scope (remove specific constraints)

Original question: {sub_question}
Retrieved chunks (low relevance): {chunk_summaries}
"""

REPORT_UNCERTAINTY_SYSTEM = """Generate an honest response explaining that the system
could not find sufficient evidence to answer the question.

Include:
1. What collections were searched
2. What was found (if anything partially relevant)
3. Why the results were insufficient
4. Suggestions for the user (different query, different collection, upload more docs)

Do NOT fabricate an answer. Do NOT say "based on the available context" and then guess.
"""
```

### backend/main.py -- Graph Assembly

```python
from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph
from backend.agent.research_graph import build_research_graph
from backend.agent.conversation_graph import build_conversation_graph


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...

    # Build graphs inside-out (innermost first)
    meta_reasoning_graph = build_meta_reasoning_graph()
    research_graph = build_research_graph(
        meta_reasoning_graph=meta_reasoning_graph,
    )
    conversation_graph = build_conversation_graph(
        research_graph_compiled=research_graph,
    )

    app.state.conversation_graph = conversation_graph

    yield
    # ... existing shutdown code ...
```

## Configuration

Relevant settings from `backend/config.py`:
- `meta_reasoning_max_attempts: int = 2` -- Maximum meta-reasoning retry attempts
- `confidence_threshold: float = 0.6` -- Triggers MetaReasoningGraph when below this
- `reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"` -- Cross-encoder for quality evaluation

Strategy decision thresholds (hardcoded in `decide_strategy`, could be moved to config):
- `mean_cross_encoder_score < 0.2` -- Low relevance threshold
- `chunk_count < 3` -- Few chunks threshold

## Error Handling

| Node | Error | Recovery |
|------|-------|----------|
| `generate_alternative_queries` | `LLMCallError` | Use original sub_question as all 3 alternatives, log warning |
| `evaluate_retrieval_quality` | `RerankerError` (cross-encoder failure) | Set `mean_relevance_score = 0.0`, route to WIDEN_SEARCH by default |
| `decide_strategy` | No applicable strategy | Return `recovery_strategy = None`, route to `report_uncertainty` |
| `report_uncertainty` | `LLMCallError` (if using LLM for report) | Generate static template response without LLM |

## Testing Requirements

### Unit Tests
- `test_generate_alternative_queries`: Mock LLM, verify 3 query variants produced
- `test_generate_alternative_queries_fallback`: Mock LLM failure, verify original query is used
- `test_evaluate_retrieval_quality_with_chunks`: Mock cross-encoder, verify mean_relevance_score computed correctly
- `test_evaluate_retrieval_quality_no_chunks`: Verify 0.0 mean score when no chunks
- `test_decide_strategy_widen_search`: Set mean_score=0.1, chunk_count=1, verify WIDEN_SEARCH selected
- `test_decide_strategy_change_collection`: Set mean_score=0.1, chunk_count=5, verify CHANGE_COLLECTION selected
- `test_decide_strategy_relax_filters`: Set mean_score=0.3, verify RELAX_FILTERS selected
- `test_decide_strategy_max_attempts`: Set meta_attempt_count=2, verify recovery_strategy=None
- `test_report_uncertainty_no_chunks`: Verify honest message with suggestions
- `test_report_uncertainty_low_relevance`: Verify message explains low relevance
- `test_report_uncertainty_partial_relevance`: Verify message explains partial match
- `test_route_after_strategy_retry`: Verify "retry" when strategy and modified_state are set
- `test_route_after_strategy_report`: Verify "report" when strategy is None

### Integration Tests
- `test_meta_reasoning_graph_end_to_end`: Run full graph with mock LLM and cross-encoder, verify correct strategy selection
- `test_meta_reasoning_with_research_graph`: Wire MetaReasoningGraph into ResearchGraph, verify retry loop works
- `test_max_attempts_prevents_infinite_loop`: Run with meta_attempt_count=1, trigger again, verify report_uncertainty is forced on second invocation

## Done Criteria

- [ ] `backend/agent/meta_reasoning_graph.py` defines and compiles a valid LangGraph StateGraph
- [ ] `generate_alternative_queries` produces 3 alternative query formulations
- [ ] `evaluate_retrieval_quality` uses cross-encoder (not LLM) to compute mean relevance score
- [ ] `decide_strategy` correctly selects WIDEN_SEARCH when mean < 0.2 and chunks < 3
- [ ] `decide_strategy` correctly selects CHANGE_COLLECTION when mean < 0.2 and chunks >= 3
- [ ] `decide_strategy` correctly selects RELAX_FILTERS when mean >= 0.2
- [ ] `decide_strategy` forces report_uncertainty when meta_attempt_count >= 2
- [ ] `report_uncertainty` produces honest response without fabrication
- [ ] `report_uncertainty` includes what was searched, what was found, and user suggestions
- [ ] `route_after_strategy` correctly routes to "retry" or "report"
- [ ] `modified_state` correctly resets ResearchState fields for retry
- [ ] MetaReasoningGraph integrates with ResearchGraph (wired as subgraph)
- [ ] Graph assembly order in `main.py` is correct (inside-out: meta -> research -> conversation)
- [ ] Maximum 2 meta-reasoning attempts are enforced
- [ ] All error recovery paths work as specified
- [ ] Unit tests pass for all four node functions
- [ ] Unit tests pass for strategy decision logic (all three strategies + max attempts)
- [ ] Integration test for full MetaReasoningGraph execution passes
