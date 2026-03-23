"""Per-collection min-max normalization of dense scores.

Used when merging results from multiple Qdrant collections to ensure
scores are comparable across collections.
"""
from __future__ import annotations

from backend.agent.schemas import RetrievedChunk


def normalize_scores(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Per-collection min-max normalization of dense_score.

    Groups chunks by collection, applies min-max normalization within
    each group, then returns all chunks with normalized dense_score values.

    Args:
        chunks: List of RetrievedChunk from potentially multiple collections.

    Returns:
        Same list with dense_score normalized to [0.0, 1.0] per collection.
        Returns input unchanged if empty or single-chunk collections.
    """
    if not chunks:
        return chunks

    # Group by collection
    by_collection: dict[str, list[RetrievedChunk]] = {}
    for chunk in chunks:
        by_collection.setdefault(chunk.collection, []).append(chunk)

    # Normalize within each collection
    for collection, group in by_collection.items():
        scores = [c.dense_score for c in group]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        if score_range > 0:
            for c in group:
                c.dense_score = (c.dense_score - min_score) / score_range

    return chunks
