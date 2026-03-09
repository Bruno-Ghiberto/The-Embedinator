# Spec 05: Accuracy, Precision & Robustness Enhancements -- Feature Specification Context

## Feature Description

This spec covers the cross-cutting mechanisms that ensure The Embedinator produces reliable, well-grounded answers and degrades gracefully under failure. These components operate across the agent layers (ConversationGraph, ResearchGraph) and the ingestion pipeline. The six subsystems are:

1. **Grounded Answer Verification (GAV)** -- NLI-based claim-by-claim checking of LLM answers against retrieved context.
2. **Citation-Chunk Alignment Validation** -- cross-encoder verification that every inline citation actually points to the chunk it claims to reference.
3. **Computed Confidence Scoring** -- a formula-based confidence score derived from retrieval signals, not LLM self-assessment.
4. **Query-Adaptive Retrieval Depth** -- dynamic tuning of top_k, max_iterations, and max_tool_calls based on query complexity classification.
5. **Embedding Integrity Validation** -- pre-upsert checks on every vector to prevent NaN, zero-vector, or dimension-mismatch corruption of the Qdrant index.
6. **Circuit Breaker & Retry Patterns** -- tenacity-based retry with exponential backoff and circuit breaker state machine on all Ollama and Qdrant HTTP calls.

## Requirements

### Functional Requirements

- **GAV**: After answer generation, a separate low-temperature LLM call must evaluate each factual claim as SUPPORTED, UNSUPPORTED, or CONTRADICTED against the retrieved context. Claims marked UNSUPPORTED are annotated with `[unverified]`. Claims marked CONTRADICTED are removed with an explanation appended. If >50% of claims are unsupported, the entire answer is flagged with a warning.
- **Citation Alignment**: Every inline citation `[1]`, `[2]`, etc. must be validated by computing a cross-encoder score between the claim text and the referenced chunk text. If the score is below `CITATION_ALIGNMENT_THRESHOLD` (default 0.3), the citation is remapped to the highest-scoring chunk or stripped entirely.
- **Confidence Scoring**: The confidence_score in ResearchState must be computed from four measurable signals: retrieval relevance (mean cross-encoder score), coverage (fraction of sub-questions with support), consistency (1.0 - contradiction ratio), and depth (unique parent chunks used). Weighted combination: 0.35 retrieval + 0.30 coverage + 0.20 consistency + 0.15 depth.
- **Query-Adaptive Depth**: The `rewrite_query` node must classify queries into five complexity tiers (factoid, lookup, comparison, analytical, multi_hop) and set top_k, max_iterations, max_tool_calls, and confidence_threshold accordingly.
- **Embedding Validation**: Before any vector is upserted to Qdrant, it must pass four checks: correct dimension count, no NaN values, not an all-zero vector, and magnitude above 1e-6. Failed chunks are logged and skipped without aborting the batch.
- **Circuit Breaker**: All HTTP calls to Ollama and Qdrant must use retry (3 attempts, exponential backoff 1s->2s->4s with 0.5s jitter) and circuit breaker (open after 5 consecutive failures within 60s, 30s cooldown, half-open test request).

### Non-Functional Requirements

- GAV adds at most one additional LLM call per answer.
- Citation validation must not add perceptible latency (cross-encoder inference is fast, <50ms per batch).
- Confidence scoring must be deterministic given the same retrieval results.
- Circuit breaker must prevent cascading failures -- open circuit returns errors immediately without waiting for timeouts.
- Embedding validation must never silently allow corrupt vectors into Qdrant.

## Key Technical Details

### GAV Structured Output Schema

```python
class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str]   # which chunk supports/contradicts
    explanation: str                    # brief reasoning

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool             # True if >50% claims supported
    confidence_adjustment: float       # modifier applied to confidence score
```

### GAV Verification Prompt

```python
VERIFY_PROMPT = """Given ONLY the retrieved context below, evaluate each claim
in the proposed answer. For each claim, respond with:
- SUPPORTED: the context contains evidence for this claim
- UNSUPPORTED: no evidence found in the retrieved context
- CONTRADICTED: the context contradicts this claim

Retrieved Context:
{context}

Proposed Answer:
{answer}
"""
```

### QueryAnalysis Extended Schema

```python
class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str]
    clarification_needed: Optional[str]
    collections_hint: List[str]
    complexity_tier: Literal["factoid", "lookup", "comparison", "analytical", "multi_hop"]
```

### Tier-Based Retrieval Parameters

| Tier | top_k | max_iterations | max_tool_calls | Confidence Threshold |
|------|-------|---------------|----------------|---------------------|
| factoid | 5 | 3 | 3 | 0.7 |
| lookup | 10 | 5 | 5 | 0.6 |
| comparison | 15 | 7 | 6 | 0.55 |
| analytical | 25 | 10 | 8 | 0.5 |
| multi_hop | 30 | 10 | 8 | 0.45 |

### Confidence Formula

```python
def compute_confidence(state: ResearchState) -> float:
    retrieval_score = mean(state.rerank_scores[:state.top_k_used])
    coverage_score = chunks_with_support / total_sub_questions
    consistency_score = 1.0 - contradiction_ratio
    depth_score = min(unique_parents_used / EXPECTED_DEPTH, 1.0)

    confidence = (
        0.35 * retrieval_score +
        0.30 * coverage_score +
        0.20 * consistency_score +
        0.15 * depth_score
    )
    return round(confidence, 3)
```

### Confidence Display Mapping

| Score Range | Color | Label | Icon |
|------------|-------|-------|------|
| 0.7 - 1.0 | Green | High confidence | Solid circle |
| 0.4 - 0.69 | Yellow | Moderate confidence | Half circle |
| 0.0 - 0.39 | Red | Low confidence | Empty circle |

### Embedding Validation Function

```python
def validate_embedding(embedding: List[float], expected_dim: int) -> bool:
    if len(embedding) != expected_dim:
        return False
    if any(math.isnan(x) for x in embedding):
        return False
    if all(x == 0.0 for x in embedding):
        return False
    magnitude = math.sqrt(sum(x*x for x in embedding))
    if magnitude < 1e-6:
        return False
    return True
```

### Circuit Breaker State Machine

```
States: Closed -> Open -> HalfOpen -> Closed (or back to Open)
- Closed: Requests pass through normally
- Open: Reject immediately, return cached/error (triggered by 5 consecutive failures within 60s)
- HalfOpen: Allow one test request after 30s cooldown
  - If test succeeds -> Closed
  - If test fails -> Open
```

### Retry Configuration (tenacity)

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5),
    reraise=True
)
async def call_ollama_embed(text: str, model: str) -> List[float]:
    ...
```

### Graceful Degradation Modes

| Scenario | Behavior |
|----------|----------|
| Ollama down during chat | Return error: "Inference service unavailable" with link to `/observability` |
| Ollama down during ingestion | Pause ingestion job (status=paused), retry when circuit closes |
| Qdrant unreachable during chat | Return error with last-known collection status from SQLite |
| Qdrant unreachable during ingestion | Buffer upserts in-memory (up to 1000 points), flush on recovery |

## Dependencies

- **Internal**: spec-03 (ResearchGraph state for confidence scoring), spec-04 (MetaReasoningGraph triggered by low confidence), spec-06 (ingestion pipeline uses embedding validation + circuit breaker), spec-07 (SQLite stores ingestion_job error logs)
- **Libraries**: `tenacity >=9.0` (retry + circuit breaker), `sentence-transformers >=5.2.3` (cross-encoder for citation alignment), `pydantic >=2.12` (structured output schemas)

## Acceptance Criteria

1. GAV node exists in ConversationGraph between `aggregate_answers` and `format_response`; produces GroundednessResult structured output.
2. Citation alignment validation runs on every answer; invalid citations are remapped or stripped.
3. Confidence score is computed from the four-signal formula, never from LLM self-assessment.
4. Query complexity classification produces correct tier assignments for factoid vs. analytical queries, with measurable differences in retrieval parameters.
5. No embedding with NaN, zero-vector, or wrong dimensions reaches Qdrant.
6. Circuit breaker transitions correctly through Closed -> Open -> HalfOpen -> Closed states.
7. Graceful degradation returns informative errors instead of hanging or crashing.

## Architecture Reference

- **GAV node location**: `backend/agent/nodes.py` -- `verify_groundedness` node
- **Citation validation location**: `backend/agent/nodes.py` -- `validate_citations` node
- **Confidence scoring location**: `backend/agent/nodes.py` -- `collect_answer` node in ResearchGraph
- **Query-adaptive depth location**: `backend/agent/nodes.py` -- `rewrite_query` node
- **Embedding validation location**: `backend/ingestion/embedder.py` -- post-embedding check
- **Circuit breaker location**: `backend/storage/qdrant_client.py`, `backend/ingestion/embedder.py`
- **Configuration**: `backend/config.py` -- `groundedness_check_enabled`, `citation_alignment_threshold`, `circuit_breaker_failure_threshold`, `circuit_breaker_cooldown_secs`, `retry_max_attempts`, `retry_backoff_initial_secs`
