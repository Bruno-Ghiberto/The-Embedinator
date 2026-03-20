# backend/agent/

Three-layer LangGraph agent system that powers The Embedinator's
question-answering pipeline.

## Architecture

The agent is composed of three nested StateGraphs, compiled inside-out:

```
ConversationGraph (Layer 1)
  +-- ResearchGraph (Layer 2)
        +-- MetaReasoningGraph (Layer 3)
```

### Layer 1: ConversationGraph

Defined in `conversation_graph.py`. Manages the outer conversation loop:

1. **init_session** -- Load or create a session
2. **classify_intent** -- Route to RAG query, clarification, or collection management
3. **rewrite_query** -- Improve the user query for retrieval
4. **fan_out** -- Decompose complex questions into sub-questions
5. **[invoke ResearchGraph]** -- Delegate to the research layer
6. **aggregate_answers** -- Combine sub-answers
7. **verify_groundedness** -- Claim-level verification against source chunks
8. **validate_citations** -- Ensure citations map to real retrieved passages
9. **format_response** -- Produce the final streamed answer
10. **summarize_history** -- Compress conversation history when it grows long

Edge functions in `edges.py` handle conditional routing (intent classification,
clarification detection, history compression triggers).

### Layer 2: ResearchGraph

Defined in `research_graph.py`. Executes iterative research:

1. **orchestrator** -- Decide which tool to call next
2. **tools_node** -- Execute the selected research tool
3. **compress_check** -- Evaluate if enough evidence has been gathered
4. **score_and_cite** -- Compute confidence score and extract citations

The graph loops between orchestrator and tools_node until the confidence
threshold is met or the iteration limit is reached. Six tools are available
(created via closure factory in `tools.py`): hybrid search, rerank, parent
chunk lookup, sub-question search, broader search, and focused search.

### Layer 3: MetaReasoningGraph

Defined in `meta_reasoning_graph.py`. Activates when Layer 2 produces
low-quality results:

1. **analyze_failure** -- Detect failure signals (low relevance, high variance)
2. **select_strategy** -- Choose a recovery strategy
3. **execute_strategy** -- Apply query rewrite, broader search, or decomposition
4. **evaluate_improvement** -- Check if the recovery improved results

## State Definitions

`state.py` defines three `TypedDict` classes:

- **ConversationState** -- Session ID, messages, intent, citations, groundedness, confidence score, selected collections
- **ResearchState** -- Query, retrieved chunks, sub-answers, iteration count, tool call history
- **MetaReasoningState** -- Attempted strategies, failure signals, recovery results

## Other Key Files

| File                  | Purpose                                          |
|-----------------------|--------------------------------------------------|
| `schemas.py`          | 40+ Pydantic models for requests, responses, events |
| `confidence.py`       | 5-signal confidence scoring (0-100 integer scale) |
| `prompts.py`          | Prompt templates for all LLM-calling nodes        |
| `tools.py`            | Closure-based research tool factory               |
| `citations.py`        | Citation extraction and alignment scoring         |
| `answer_generator.py` | Final answer formatting with citation markers     |
| `nodes.py`            | 17 conversation node function implementations     |
| `research_nodes.py`   | 6 research node functions                         |
