# Spec 05: Accuracy, Precision & Robustness Enhancements -- Implementation Plan Context

## Component Overview

This spec implements six cross-cutting reliability mechanisms that ensure The Embedinator produces trustworthy, well-grounded answers and handles infrastructure failures gracefully. These mechanisms span the agent layer (GAV, citation validation, confidence scoring, query-adaptive depth) and the infrastructure layer (embedding validation, circuit breaker + retry). Together they eliminate the most common RAG failure modes: confident wrong answers, phantom citations, meaningless confidence scores, wasted retrieval effort, corrupt vectors, and cascading service failures.

## Technical Approach

### GAV (Grounded Answer Verification)
- Implement as a LangGraph node `verify_groundedness` in ConversationGraph
- Uses a separate low-temperature LLM call with structured output (Pydantic model)
- Placed between `aggregate_answers` and `format_response` nodes
- Returns `GroundednessResult` with per-claim verdicts

### Citation-Chunk Alignment
- Implement as a function `validate_citations` called within the ConversationGraph
- Uses the cross-encoder reranker (already loaded for reranking) to score claim-chunk pairs
- Threshold-based: remap or strip citations below `CITATION_ALIGNMENT_THRESHOLD`

### Computed Confidence Scoring
- Implement `compute_confidence()` in the `collect_answer` node of ResearchGraph
- Four weighted signals: retrieval relevance (0.35), coverage (0.30), consistency (0.20), depth (0.15)
- Score drives MetaReasoningGraph trigger and user-facing confidence indicator

### Query-Adaptive Retrieval Depth
- Extend `QueryAnalysis` Pydantic model with `complexity_tier` field
- LLM classifies query complexity during `rewrite_query` node
- Tier maps to dynamic `top_k`, `max_iterations`, `max_tool_calls`, `confidence_threshold`

### Embedding Integrity Validation
- Implement `validate_embedding()` in `backend/ingestion/embedder.py`
- Called after every Ollama embedding call, before Qdrant upsert
- Failed vectors logged to ingestion_job error; chunk skipped, batch continues

### Circuit Breaker & Retry
- Use `tenacity` library decorators on all HTTP calls to Ollama and Qdrant
- Implement circuit breaker state machine (Closed/Open/HalfOpen)
- Per-service circuit breakers (separate for Ollama and Qdrant)
- Graceful degradation: informative error messages, job pausing, in-memory buffering

## File Structure

```
backend/
  agent/
    nodes.py              # verify_groundedness, validate_citations, compute_confidence, rewrite_query (query-adaptive)
    schemas.py            # ClaimVerification, GroundednessResult, QueryAnalysis (extended)
  ingestion/
    embedder.py           # validate_embedding(), retry decorators on embed calls
  storage/
    qdrant_client.py      # retry decorators + circuit breaker on all Qdrant calls
  config.py               # accuracy/robustness configuration fields
```

## Implementation Steps

1. **Add Pydantic schemas** (`backend/agent/schemas.py`): Define `ClaimVerification`, `GroundednessResult`. Extend `QueryAnalysis` with `complexity_tier` field.

2. **Implement embedding validation** (`backend/ingestion/embedder.py`): Add `validate_embedding()` function. Integrate into the embedding pipeline so every vector is validated before batch upsert.

3. **Implement retry + circuit breaker** (`backend/storage/qdrant_client.py`, `backend/ingestion/embedder.py`): Add tenacity `@retry` decorators. Implement `CircuitBreaker` class with Closed/Open/HalfOpen state transitions. Wire into all Ollama and Qdrant HTTP call sites.

4. **Implement query-adaptive depth** (`backend/agent/nodes.py`): In `rewrite_query` node, use the LLM's classification of `complexity_tier`. Create a tier-to-parameters lookup table. Apply dynamic parameters to the ResearchGraph invocation.

5. **Implement computed confidence scoring** (`backend/agent/nodes.py`): In `collect_answer` node, compute confidence from the four-signal formula. Store the score in ResearchState.

6. **Implement GAV** (`backend/agent/nodes.py`): Create `verify_groundedness` node. Add VERIFY_PROMPT template. Parse structured output into `GroundednessResult`. Apply annotations/removals to the answer text.

7. **Implement citation validation** (`backend/agent/nodes.py`): Create `validate_citations` function. Use the cross-encoder reranker to score claim-chunk pairs. Remap or strip invalid citations.

8. **Add configuration fields** (`backend/config.py`): Add `groundedness_check_enabled`, `citation_alignment_threshold`, `circuit_breaker_failure_threshold`, `circuit_breaker_cooldown_secs`, `retry_max_attempts`, `retry_backoff_initial_secs`.

9. **Wire into ConversationGraph** (`backend/agent/conversation_graph.py`): Insert `verify_groundedness` node between `aggregate_answers` and `format_response`. Insert citation validation call.

10. **Write tests**: Unit tests for `validate_embedding()`, `compute_confidence()`, circuit breaker state transitions, tier parameter mapping, citation alignment logic.

## Integration Points

- **ConversationGraph** (spec-02): GAV and citation validation are nodes/steps in the conversation graph flow.
- **ResearchGraph** (spec-03): Confidence scoring runs inside `collect_answer`. Query-adaptive depth sets parameters for retrieval iterations.
- **MetaReasoningGraph** (spec-04): Triggered when confidence score falls below threshold.
- **Ingestion Pipeline** (spec-06): Embedding validation and circuit breaker protect the ingestion path.
- **Storage** (spec-07): Failed embeddings logged to `ingestion_jobs.error_msg`. Circuit breaker wraps all Qdrant client calls.
- **API** (spec-08): SSE events emit confidence score and groundedness results. Chat endpoint returns circuit breaker errors.
- **Retrieval** (spec-11): Reranker (cross-encoder) is shared between retrieval reranking and citation alignment.

## Key Code Patterns

### Tenacity Retry Decorator Pattern
```python
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5),
    reraise=True
)
async def call_ollama_embed(text: str, model: str) -> List[float]:
    ...
```

### Circuit Breaker State Tracking
```python
class CircuitBreaker:
    def __init__(self, failure_threshold=5, cooldown_secs=30):
        self.state = "closed"  # closed | open | half_open
        self.failure_count = 0
        self.last_failure_time = None
        self.failure_threshold = failure_threshold
        self.cooldown_secs = cooldown_secs
```

### Tier Parameter Lookup
```python
TIER_PARAMS = {
    "factoid":    {"top_k": 5,  "max_iterations": 3,  "max_tool_calls": 3, "confidence_threshold": 0.7},
    "lookup":     {"top_k": 10, "max_iterations": 5,  "max_tool_calls": 5, "confidence_threshold": 0.6},
    "comparison": {"top_k": 15, "max_iterations": 7,  "max_tool_calls": 6, "confidence_threshold": 0.55},
    "analytical": {"top_k": 25, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.5},
    "multi_hop":  {"top_k": 30, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.45},
}
```

## Phase Assignment

- **Phase 1 (MVP)**: Circuit breaker + retry on all Ollama/Qdrant calls, embedding integrity validation, query-adaptive retrieval depth.
- **Phase 2 (Performance and Resilience)**: Grounded Answer Verification (GAV), Citation-Chunk Alignment Validation, computed confidence scoring.
