# Agent: agent-retrieval

**subagent_type**: python-expert | **Model**: Opus 4.6 | **Wave**: 2

## Mission

Implement the full retrieval layer: HybridSearcher with Qdrant hybrid search and circuit breaker, Reranker with CrossEncoder, and ScoreNormalizer for cross-collection merging.

## Context Files (Read FIRST)

1. `Docs/PROMPTS/spec-03-research-graph/03-implement.md` -- code specs for searcher.py, reranker.py, score_normalizer.py
2. `backend/storage/qdrant_client.py` -- existing circuit breaker pattern to follow
3. `backend/agent/schemas.py` -- RetrievedChunk, ParentChunk models
4. `backend/config.py` -- Settings fields used by retrieval layer
5. `backend/errors.py` -- QdrantConnectionError, EmbeddingError, RerankerError

## Assigned Tasks

- T013: Implement `HybridSearcher.search()` using AsyncQdrantClient `query_points` with `prefetch` (dense + sparse) + `FusionQuery(Fusion.RRF)` (R4)
- T014: Implement `HybridSearcher.search_all_collections()` with asyncio.gather fan-out
- T015: Implement circuit breaker in HybridSearcher (`_check_circuit`, `_record_success`, `_record_failure`) per C1
- T016: Implement `Reranker.rerank()` using `model.rank()` API (R5) and `ScoreNormalizer.normalize_scores()`

## Files to Create/Modify

- MODIFY: `backend/retrieval/searcher.py` (fill stubs from Wave 1)
- MODIFY: `backend/retrieval/reranker.py` (fill stubs from Wave 1)
- MODIFY: `backend/retrieval/score_normalizer.py` (fill stubs from Wave 1)

## Key Patterns

- R4: Qdrant hybrid search uses `query_points` with `prefetch` (dense + sparse) + `FusionQuery(Fusion.RRF)`. Use `AsyncQdrantClient`.
- R5: CrossEncoder uses `model.rank(query, documents, top_k, return_documents=False)` which returns `[{"corpus_id": int, "score": float}]`. Do NOT use `model.predict()`.
- C1 (Constitution): Circuit breaker on ALL Qdrant call sites. Follow the pattern in `backend/storage/qdrant_client.py` -- track `_failure_count`, `_circuit_open`, `_max_failures`.
- Per-collection min-max normalization in `score_normalizer.py` for cross-collection score comparability.

## Constraints

- NEVER run pytest inside Claude Code. Use: `zsh scripts/run-tests-external.sh -n <name> <target>`
- NEVER use `model.predict()` in Reranker -- only `model.rank()` (R5)
- NEVER use synchronous QdrantClient -- only `AsyncQdrantClient` (R4)
- ALL Qdrant calls MUST go through circuit breaker (C1 -- Constitution requirement)
- structlog logging at all decision points (FR-017): circuit breaker state changes, search results, rerank results
- Do NOT modify files outside the `backend/retrieval/` directory

## Checkpoint

`HybridSearcher` can execute hybrid search against Qdrant with circuit breaker protection. `Reranker` can score and sort chunks using `model.rank()`. `normalize_scores()` correctly normalizes dense scores per-collection.
