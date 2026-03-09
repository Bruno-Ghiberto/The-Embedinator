# Spec 05: Accuracy, Precision & Robustness Enhancements -- Implementation Context

## Implementation Scope

### Files to Create
- None (all code goes into existing files defined by the project structure)

### Files to Modify
- `backend/agent/schemas.py` -- Add `ClaimVerification`, `GroundednessResult`, extend `QueryAnalysis`
- `backend/agent/nodes.py` -- Add `verify_groundedness`, `validate_citations`, `compute_confidence` functions; modify `rewrite_query` for query-adaptive depth
- `backend/agent/prompts.py` -- Add `VERIFY_PROMPT` template
- `backend/agent/conversation_graph.py` -- Wire GAV and citation validation nodes into the graph
- `backend/ingestion/embedder.py` -- Add `validate_embedding()`, add `@retry` decorators, integrate circuit breaker
- `backend/storage/qdrant_client.py` -- Add `@retry` decorators, implement `CircuitBreaker` class
- `backend/config.py` -- Add accuracy/robustness configuration fields

## Code Specifications

### Pydantic Schemas (backend/agent/schemas.py)

```python
from pydantic import BaseModel
from typing import List, Optional, Literal

class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str] = None
    explanation: str

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool              # True if >50% claims supported
    confidence_adjustment: float        # modifier applied to confidence score

class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str]
    clarification_needed: Optional[str] = None
    collections_hint: List[str]
    complexity_tier: Literal["factoid", "lookup", "comparison", "analytical", "multi_hop"]
```

### GAV Node (backend/agent/nodes.py)

```python
async def verify_groundedness(state: ConversationState) -> ConversationState:
    """Verify each factual claim in the answer against retrieved context."""
    context = "\n\n".join(chunk.text for sa in state["sub_answers"] for chunk in sa.chunks)
    answer = state["draft_answer"]

    result: GroundednessResult = await llm.with_structured_output(GroundednessResult).ainvoke(
        VERIFY_PROMPT.format(context=context, answer=answer)
    )

    modified_answer = answer
    notes = []

    for v in result.verifications:
        if v.verdict == "unsupported":
            modified_answer = modified_answer.replace(v.claim, f"{v.claim} [unverified]")
        elif v.verdict == "contradicted":
            modified_answer = modified_answer.replace(v.claim, "")
            notes.append(f"Removed contradicted claim: {v.explanation}")

    if not result.overall_grounded:
        notes.insert(0, "Warning: insufficient evidence for most claims in this answer.")

    state["draft_answer"] = modified_answer
    state["groundedness_result"] = result
    state["groundedness_notes"] = notes
    return state
```

### Citation Validation (backend/agent/nodes.py)

```python
async def validate_citations(
    state: ConversationState,
    reranker: CrossEncoder,
) -> ConversationState:
    """Verify each citation points to a chunk that supports the claim."""
    corrected_citations: List[Citation] = []

    for citation in state["citations"]:
        claim_text = citation.claim_text
        chunk_text = citation.chunk.text

        score = reranker.predict([(claim_text, chunk_text)])[0]

        if score >= CITATION_ALIGNMENT_THRESHOLD:
            corrected_citations.append(citation)
        else:
            all_chunks = [sa.chunks for sa in state["sub_answers"]]
            flat_chunks = [c for sublist in all_chunks for c in sublist]
            pairs = [(claim_text, c.text) for c in flat_chunks]
            scores = reranker.predict(pairs)
            best_idx = int(scores.argmax())
            best_score = scores[best_idx]

            if best_score >= CITATION_ALIGNMENT_THRESHOLD:
                citation.chunk = flat_chunks[best_idx]
                corrected_citations.append(citation)
            # else: citation is dropped entirely

    state["citations"] = corrected_citations
    return state
```

### Computed Confidence (backend/agent/nodes.py)

```python
def compute_confidence(state: ResearchState) -> float:
    retrieval_score = mean(state["rerank_scores"][:state["top_k_used"]])
    coverage_score = state["chunks_with_support"] / max(state["total_sub_questions"], 1)
    consistency_score = 1.0 - state["contradiction_ratio"]
    depth_score = min(state["unique_parents_used"] / EXPECTED_DEPTH, 1.0)

    confidence = (
        0.35 * retrieval_score +
        0.30 * coverage_score +
        0.20 * consistency_score +
        0.15 * depth_score
    )
    return round(confidence, 3)
```

### Query-Adaptive Depth (backend/agent/nodes.py)

```python
TIER_PARAMS = {
    "factoid":    {"top_k": 5,  "max_iterations": 3,  "max_tool_calls": 3, "confidence_threshold": 0.7},
    "lookup":     {"top_k": 10, "max_iterations": 5,  "max_tool_calls": 5, "confidence_threshold": 0.6},
    "comparison": {"top_k": 15, "max_iterations": 7,  "max_tool_calls": 6, "confidence_threshold": 0.55},
    "analytical": {"top_k": 25, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.5},
    "multi_hop":  {"top_k": 30, "max_iterations": 10, "max_tool_calls": 8, "confidence_threshold": 0.45},
}

async def apply_adaptive_depth(state: ConversationState, analysis: QueryAnalysis) -> ConversationState:
    params = TIER_PARAMS[analysis.complexity_tier]
    state["top_k"] = params["top_k"]
    state["max_iterations"] = params["max_iterations"]
    state["max_tool_calls"] = params["max_tool_calls"]
    state["confidence_threshold"] = params["confidence_threshold"]
    return state
```

### Embedding Validation (backend/ingestion/embedder.py)

```python
import math

def validate_embedding(embedding: List[float], expected_dim: int) -> bool:
    if len(embedding) != expected_dim:
        return False
    if any(math.isnan(x) for x in embedding):
        return False
    if all(x == 0.0 for x in embedding):
        return False
    magnitude = math.sqrt(sum(x * x for x in embedding))
    if magnitude < 1e-6:
        return False
    return True
```

### Circuit Breaker (backend/storage/qdrant_client.py)

```python
import time
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cooldown_secs: int = 30, window_secs: int = 60):
        self.state = "closed"
        self.failure_count = 0
        self.failure_window_start: float = 0.0
        self.last_failure_time: float = 0.0
        self.failure_threshold = failure_threshold
        self.cooldown_secs = cooldown_secs
        self.window_secs = window_secs

    def record_success(self):
        self.state = "closed"
        self.failure_count = 0

    def record_failure(self):
        now = time.monotonic()
        if now - self.failure_window_start > self.window_secs:
            self.failure_count = 1
            self.failure_window_start = now
        else:
            self.failure_count += 1

        self.last_failure_time = now

        if self.failure_count >= self.failure_threshold:
            self.state = "open"

    def can_proceed(self) -> bool:
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.monotonic() - self.last_failure_time >= self.cooldown_secs:
                self.state = "half_open"
                return True
            return False
        if self.state == "half_open":
            return True
        return False

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=1, max=10, jitter=0.5),
    reraise=True
)
async def call_ollama_embed(text: str, model: str) -> List[float]:
    ...
```

### GAV Prompt (backend/agent/prompts.py)

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

## Configuration

Add to `backend/config.py` `Settings` class:

```python
# Accuracy & Robustness
groundedness_check_enabled: bool = True
citation_alignment_threshold: float = 0.3
circuit_breaker_failure_threshold: int = 5
circuit_breaker_cooldown_secs: int = 30
retry_max_attempts: int = 3
retry_backoff_initial_secs: float = 1.0
```

Environment variables (`.env`):
- `GROUNDEDNESS_CHECK_ENABLED=true`
- `CITATION_ALIGNMENT_THRESHOLD=0.3`
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD=5`
- `CIRCUIT_BREAKER_COOLDOWN_SECS=30`
- `RETRY_MAX_ATTEMPTS=3`
- `RETRY_BACKOFF_INITIAL_SECS=1.0`

## Error Handling

- **GAV LLM call fails**: Log warning, skip verification, pass answer through unmodified. Do not block answer delivery.
- **Citation validation reranker fails**: Log warning, keep original citations unchanged. Better to have unvalidated citations than no answer.
- **Embedding validation fails**: Log the failure reason to `ingestion_jobs.error_msg`, increment `chunks_skipped` counter, continue processing remaining chunks.
- **Circuit breaker opens (Ollama)**: During chat, return HTTP 503 with message "Inference service unavailable. Check Ollama status." During ingestion, pause the job (status=paused), auto-retry when circuit closes.
- **Circuit breaker opens (Qdrant)**: During chat, return error with last-known collection status from SQLite. During ingestion, buffer up to 1000 points in memory, flush when connection recovers.
- **Confidence score computation errors**: Default to 0.5 (moderate) if any signal is unavailable. Log which signal was missing.

## Testing Requirements

### Unit Tests
- `test_validate_embedding`: Test all four failure modes (wrong dim, NaN, zero-vector, near-zero magnitude) and a valid embedding.
- `test_compute_confidence`: Test with known signal values, verify weighted formula produces expected score.
- `test_circuit_breaker_states`: Test Closed->Open transition after N failures, Open->HalfOpen after cooldown, HalfOpen->Closed on success, HalfOpen->Open on failure.
- `test_tier_params`: Verify each complexity tier maps to correct top_k, max_iterations, max_tool_calls, confidence_threshold.
- `test_citation_alignment`: Test with matching citation (above threshold), mismatched citation (remap), and no match (strip).
- `test_groundedness_result`: Test with all-supported, mixed, and majority-unsupported claim sets.

### Integration Tests
- End-to-end chat request with GAV enabled: verify groundedness events in SSE stream.
- Ingestion with deliberately corrupt embeddings: verify chunks are skipped and error is logged.
- Simulated Ollama downtime: verify circuit breaker opens and returns appropriate error.

## Done Criteria

- [ ] `validate_embedding()` rejects NaN, zero-vector, wrong-dimension, and near-zero-magnitude vectors
- [ ] `CircuitBreaker` transitions through all three states correctly
- [ ] `@retry` decorators on all Ollama and Qdrant HTTP calls with exponential backoff
- [ ] `QueryAnalysis.complexity_tier` is populated by rewrite_query and drives dynamic retrieval parameters
- [ ] `compute_confidence()` returns a score derived from four measurable signals
- [ ] `verify_groundedness` node produces `GroundednessResult` and modifies the answer accordingly
- [ ] `validate_citations` remaps or strips citations below the alignment threshold
- [ ] All configuration fields present in `Settings` with sensible defaults
- [ ] Graceful degradation: Ollama/Qdrant outages produce informative errors, not hangs or crashes
- [ ] Unit tests pass for all six subsystems
