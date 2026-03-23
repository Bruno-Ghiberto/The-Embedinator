# backend/retrieval/

Hybrid search, cross-encoder reranking, and score normalization for
document retrieval.

## Retrieval Pipeline

```
Query --> HybridSearcher --> ScoreNormalizer --> Reranker --> Top-K results
           (dense + BM25)    (per-collection)   (cross-encoder)
```

1. **Hybrid search** -- `HybridSearcher` queries Qdrant with both dense
   vectors and BM25 sparse vectors. Scores are combined using configurable
   weights (default: 0.7 dense, 0.3 sparse).
2. **Score normalization** -- `ScoreNormalizer` applies per-collection min-max
   normalization so scores are comparable across collections.
3. **Reranking** -- `Reranker` uses a cross-encoder model
   (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to re-score the top candidates
   against the original query. Only the top-K results (default: 5) are kept.

## Key Classes

### HybridSearcher (`searcher.py`)

- `search(query, collection_ids, top_k)` -- Search specific collections
- `search_all_collections(query, top_k)` -- Search across all collections
- Built-in circuit breaker with configurable failure threshold and cooldown
- Filter support for metadata fields

### Reranker (`reranker.py`)

- Uses `model.rank()` from sentence-transformers for efficient batch reranking
- Configurable model via `RERANKER_MODEL` environment variable

### ScoreNormalizer (`score_normalizer.py`)

- Per-collection min-max normalization
- Prevents score bias when searching across collections of different sizes

## Circuit Breaker

The `HybridSearcher` includes a circuit breaker to handle Qdrant outages:

- **Closed** (normal) -- Requests pass through
- **Open** (after N failures) -- Raises `CircuitOpenError` immediately
- **Half-open** (after cooldown) -- Allows one test request

Configuration:
- `CIRCUIT_BREAKER_FAILURE_THRESHOLD` (default: 5)
- `CIRCUIT_BREAKER_COOLDOWN_SECS` (default: 30)

## Configuration

| Variable               | Default | Description                          |
|------------------------|---------|--------------------------------------|
| `HYBRID_DENSE_WEIGHT`  | 0.7     | Weight for dense vector scores       |
| `HYBRID_SPARSE_WEIGHT` | 0.3     | Weight for BM25 sparse scores        |
| `TOP_K_RETRIEVAL`      | 20      | Candidates retrieved from Qdrant     |
| `TOP_K_RERANK`         | 5       | Results kept after reranking         |
| `RERANKER_MODEL`       | `cross-encoder/ms-marco-MiniLM-L-6-v2` | Cross-encoder model |
