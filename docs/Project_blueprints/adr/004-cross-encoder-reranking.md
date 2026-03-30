# ADR-004: Cross-Encoder Reranking

**Status**: Accepted
**Date**: 2026-03-03
**Decision Makers**: Architecture Team

## Context

Bi-encoder retrieval (dense vector search + BM25) is optimized for speed and recall — it scores query and chunk independently. However, bi-encoders do not model the interaction between query tokens and chunk tokens, limiting precision.

Neither source system included cross-encoder reranking:
- GRAVITEA had multi-stage reranking with keyword boosting but no cross-encoder
- agentic-rag-for-dummies had no reranking stage at all

## Decision

Apply **cross-encoder reranking** (using `sentence-transformers` with `cross-encoder/ms-marco-MiniLM-L-6-v2`) to the top-k results from hybrid retrieval.

## Rationale

1. **Joint scoring**: Cross-encoders score (query, chunk) pairs jointly, attending to query-relevant terms within the chunk.
2. **Precision on final ranking**: Applied only to top-k (typically k=20-50), preserving recall from hybrid retrieval while using cross-encoder precision for final ranking.
3. **Dual use**: Also used inside MetaReasoningGraph to evaluate retrieval quality without requiring an LLM call.
4. **Small model**: MiniLM-L-6 runs on CPU with ~150ms latency for 20 pairs — acceptable for interactive use.

## Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| No reranking | Bi-encoder-only ranking misses query-chunk interactions |
| LLM-based reranking | Much higher latency and cost; overkill for reranking |
| Keyword boosting only (GRAVITEA approach) | Does not capture semantic relevance |
| Cohere Rerank API | Adds cloud dependency; not self-hosted |

## Consequences

### Positive
- Significantly more accurate final passage ranking
- Dual-purpose: reranking and retrieval quality evaluation
- CPU-only inference, no GPU required

### Negative
- ~200 MB RAM for loaded model
- ~150ms latency per reranking pass (20 candidates)
- Linear scaling with number of candidates

### Risks
- Model may underperform on non-English content — monitor with observability traces
