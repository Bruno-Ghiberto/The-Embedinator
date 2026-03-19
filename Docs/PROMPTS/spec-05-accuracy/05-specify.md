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
- **Confidence Scoring**: The confidence_score in ResearchState is already computed by `compute_confidence()` in `backend/agent/confidence.py` (spec-03 R8 decision) using a 5-signal weighted formula: mean rerank score (0.4), chunk count ratio (0.2), top rerank score (0.2), inverse variance / consistency (0.1), and collection coverage (0.1). This spec does NOT redefine the formula -- it adds a post-hoc **confidence adjustment** via GAV: the `confidence_adjustment` field in `GroundednessResult` is applied as a multiplier to the pre-computed score after verification completes. The adjusted score is written to `ConversationState.confidence_score` (int 0-100).
- **Query-Adaptive Depth**: The `rewrite_query` node must classify queries into five complexity tiers (factoid, lookup, comparison, analytical, multi_hop) and set top_k, max_iterations, max_tool_calls, and confidence_threshold accordingly.
- **Embedding Validation**: Before any vector is upserted to Qdrant, it must pass four checks: correct dimension count, no NaN values, not an all-zero vector, and magnitude above 1e-6. Failed chunks are logged and skipped without aborting the batch.
- **Circuit Breaker**: All HTTP calls to Ollama and Qdrant must use retry (3 attempts, exponential backoff 1s->2s->4s with 0.5s jitter) and circuit breaker (open after 5 consecutive failures, 30s cooldown, half-open test request). Note: `HybridSearcher` in `backend/retrieval/searcher.py` already implements this pattern (spec-03 C1). This spec standardizes and extends the pattern to `backend/storage/qdrant_client.py` and `backend/ingestion/embedder.py` (created by spec-06).

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

### Confidence Formula (Already Implemented -- spec-03 R8)

The confidence formula is already implemented in `backend/agent/confidence.py` (`_signal_confidence`) and called from `collect_answer` in `backend/agent/research_nodes.py`. **Do not redefine or replace it.**

```python
def compute_confidence(
    chunks: list[RetrievedChunk],
    top_k: int = 5,
    expected_chunk_count: int = 5,
    num_collections_searched: int = 1,
    num_collections_total: int = 1,
) -> float:
    """5-signal weighted formula (R8) returning float 0.0-1.0.

    Signals:
        mean_rerank     * 0.4  -- average rerank score of top-k chunks
        chunk_count     * 0.2  -- ratio of retrieved vs expected chunks
        top_score       * 0.2  -- best single rerank score
        variance        * 0.1  -- inverse of score variance (consistency)
        coverage        * 0.1  -- ratio of collections searched vs total
    """
```

### GAV Confidence Adjustment

After GAV runs, the `confidence_adjustment` field in `GroundednessResult` modifies the pre-computed confidence score from ResearchGraph. The `verify_groundedness` node applies it and writes the adjusted value to `ConversationState.confidence_score` (int 0-100 scale):

```python
# In verify_groundedness node:
raw_confidence = mean(sub_answer.confidence_score for sub_answer in state["sub_answers"])
adjusted = raw_confidence * groundedness_result.confidence_adjustment
state["confidence_score"] = max(0, min(100, int(adjusted)))
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
- Open: Reject immediately, return cached/error (triggered by 5 consecutive failures)
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

1. GAV node (`verify_groundedness`) exists in ConversationGraph in the chain `aggregate_answers -> verify_groundedness -> validate_citations -> summarize_history -> format_response`; produces GroundednessResult structured output and applies confidence_adjustment to the pre-computed confidence score.
2. Citation alignment validation runs on every answer; invalid citations are remapped or stripped.
3. Confidence score is computed from the existing 5-signal formula (spec-03 R8), never from LLM self-assessment. GAV applies a post-hoc confidence_adjustment multiplier.
4. Query complexity classification produces correct tier assignments for factoid vs. analytical queries, with measurable differences in retrieval parameters.
5. No embedding with NaN, zero-vector, or wrong dimensions reaches Qdrant.
6. Circuit breaker transitions correctly through Closed -> Open -> HalfOpen -> Closed states.
7. Graceful degradation returns informative errors instead of hanging or crashing.

## Architecture Reference

- **GAV node location**: `backend/agent/nodes.py` -- `verify_groundedness` node (Phase 2 stub, to be implemented by this spec)
- **Citation validation location**: `backend/agent/nodes.py` -- `validate_citations` node (Phase 2 stub, to be implemented by this spec)
- **Confidence scoring location**: `backend/agent/confidence.py` -- `compute_confidence()` / `_signal_confidence()` (already implemented by spec-03 R8); called from `collect_answer` in `backend/agent/research_nodes.py`
- **Query-adaptive depth location**: `backend/agent/nodes.py` -- `rewrite_query` node (complexity_tier classification exists; tier-to-parameter mapping is new)
- **Embedding validation location**: `backend/ingestion/embedder.py` -- post-embedding check (file created by spec-06; does not exist yet)
- **Circuit breaker locations**: `backend/retrieval/searcher.py` -- `HybridSearcher` (already implemented, spec-03 C1); `backend/storage/qdrant_client.py` (existing, to be extended); `backend/ingestion/embedder.py` (created by spec-06)
- **Configuration**: `backend/config.py` -- `groundedness_check_enabled`, `citation_alignment_threshold`, `circuit_breaker_failure_threshold`, `circuit_breaker_cooldown_secs`, `retry_max_attempts`, `retry_backoff_initial_secs` (all fields already exist in Settings)
