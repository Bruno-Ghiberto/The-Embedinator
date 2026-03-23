"""Cross-encoder reranking for retrieved chunks.

Uses model.rank() API (R5) -- NOT model.predict(). The rank() method
returns a list of dicts with corpus_id and score, which avoids manual
pair construction.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from backend.agent.schemas import RetrievedChunk

if TYPE_CHECKING:
    from sentence_transformers import CrossEncoder
from backend.config import Settings
from backend.errors import RerankerError

logger = structlog.get_logger().bind(component=__name__)


class Reranker:
    """Cross-encoder reranking for retrieved chunks."""

    def __init__(self, settings: Settings):
        from sentence_transformers import CrossEncoder
        self.model = CrossEncoder(settings.reranker_model)
        self.default_top_k = settings.top_k_rerank  # 5

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = 5,
    ) -> list[RetrievedChunk]:
        """Score (query, chunk) pairs and return top-k sorted by score.

        Uses model.rank() (R5) which returns:
            [{"corpus_id": int, "score": float}, ...]

        NOT model.predict() -- rank() handles pair construction internally.

        Args:
            query: The search query text.
            chunks: List of chunks to rerank.
            top_k: Number of top results to return.

        Returns:
            List of RetrievedChunk objects sorted by cross-encoder score descending,
            with rerank_score populated.

        Raises:
            RerankerError: If cross-encoder inference fails.
        """
        if not chunks:
            return []

        documents = [c.text for c in chunks]

        try:
            # R5: model.rank() returns [{"corpus_id": int, "score": float}]
            rankings = self.model.rank(
                query, documents, top_k=top_k, return_documents=False
            )
        except Exception as exc:
            logger.warning("retrieval_reranker_failed", error=type(exc).__name__)
            raise RerankerError(f"Cross-encoder reranking failed: {exc}") from exc

        ranked_chunks: list[RetrievedChunk] = []
        for entry in rankings:
            idx = entry["corpus_id"]
            chunk = chunks[idx]
            chunk.rerank_score = float(entry["score"])
            ranked_chunks.append(chunk)

        logger.info("retrieval_rerank_complete", input_count=len(chunks),
                     output_count=len(ranked_chunks))
        return ranked_chunks
