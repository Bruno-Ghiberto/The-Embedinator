"""Confidence scoring for retrieval results.

Replaces Phase 1 placeholder with 5-signal formula (R8).
Returns float 0.0-1.0 (NOT int 0-100). Conversion to int is done
in collect_answer: int(score * 100).

5-signal formula:
  score = mean_rerank(0.4) + chunk_count(0.2) + top_score(0.2)
        + variance(0.1) + coverage(0.1)

All signals are computed from measurable retrieval data, NOT LLM
self-assessment (FR-009).

Backward compatibility: aggregate_answers still passes list[dict] with
"relevance_score" keys — detected and handled via legacy path.
"""
from __future__ import annotations

import math
from typing import Any

from backend.agent.schemas import RetrievedChunk


def compute_confidence(
    chunks: list[Any],
    top_k: int = 5,
    expected_chunk_count: int = 5,
    num_collections_searched: int = 1,
    num_collections_total: int = 1,
) -> float | int:
    """Compute confidence score from retrieval signals.

    Supports two call patterns:
    1. New (spec-03): list[RetrievedChunk] -> float 0.0-1.0
    2. Legacy (spec-02 aggregate_answers): list[dict] with "relevance_score" -> int 0-100

    Args:
        chunks: Retrieved chunks or legacy passage dicts.
        top_k: Number of top chunks to consider for scoring.
        expected_chunk_count: Expected number of useful chunks (for ratio).
        num_collections_searched: Collections actually searched.
        num_collections_total: Total available collections.

    Returns:
        Float 0.0-1.0 for RetrievedChunk input, int 0-100 for legacy dict input.
    """
    if not chunks:
        # Return type matches caller expectation
        if chunks is not None and isinstance(chunks, list):
            return 0.0
        return 0

    # --- Legacy path: list[dict] with "relevance_score" (from aggregate_answers) ---
    first = chunks[0]
    if isinstance(first, dict):
        return _legacy_confidence(chunks, top_k)

    # --- New path: list[RetrievedChunk] with 5-signal formula (R8) ---
    return _signal_confidence(chunks, top_k, expected_chunk_count,
                              num_collections_searched, num_collections_total)


def _legacy_confidence(passages: list[dict], top_k: int = 5) -> int:
    """Phase 1 backward-compatible confidence: weighted average of relevance scores.

    Returns int 0-100.
    """
    if not passages:
        return 0

    top_passages = passages[:top_k]
    n = len(top_passages)

    weights = list(range(n, 0, -1))
    total_weight = sum(weights)

    weighted_sum = sum(
        p["relevance_score"] * w
        for p, w in zip(top_passages, weights)
    )

    avg_score = weighted_sum / total_weight
    return min(100, max(0, int(avg_score * 100)))


def _signal_confidence(
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
    if not chunks:
        return 0.0

    # Use top-k chunks by rerank score
    scored = [c for c in chunks if c.rerank_score is not None]
    if not scored:
        # Fall back to dense_score if no rerank scores
        scores = sorted([c.dense_score for c in chunks], reverse=True)[:top_k]
    else:
        scored.sort(key=lambda c: c.rerank_score, reverse=True)
        scores = [c.rerank_score for c in scored[:top_k]]

    if not scores:
        return 0.0

    # Signal 1: Mean rerank score (weight 0.4)
    mean_rerank = sum(scores) / len(scores)
    mean_rerank = max(0.0, min(1.0, mean_rerank))

    # Signal 2: Chunk count ratio (weight 0.2)
    chunk_ratio = min(1.0, len(chunks) / max(1, expected_chunk_count))

    # Signal 3: Top score (weight 0.2)
    top_score = max(0.0, min(1.0, scores[0]))

    # Signal 4: Inverse variance -- consistency (weight 0.1)
    if len(scores) > 1:
        mean = sum(scores) / len(scores)
        variance = sum((s - mean) ** 2 for s in scores) / len(scores)
        inverse_variance = 1.0 / (1.0 + math.sqrt(variance))
    else:
        inverse_variance = 1.0

    # Signal 5: Collection coverage (weight 0.1)
    coverage = min(1.0, num_collections_searched / max(1, num_collections_total))

    # Weighted sum
    confidence = (
        mean_rerank * 0.4
        + chunk_ratio * 0.2
        + top_score * 0.2
        + inverse_variance * 0.1
        + coverage * 0.1
    )

    return max(0.0, min(1.0, confidence))
