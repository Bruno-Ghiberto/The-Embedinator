"""Parallel batch embedding via Ollama with vector validation."""

import asyncio
import math
from concurrent.futures import ThreadPoolExecutor

import httpx
import structlog

from backend.config import settings

logger = structlog.get_logger().bind(component=__name__)


def validate_embedding(vector: list[float], expected_dim: int) -> tuple[bool, str]:
    """Validate an embedding vector. Returns (is_valid, reason).

    Checks (per data-model.md validation rules):
    1. Correct dimension count
    2. No NaN values
    3. Non-zero vector
    4. Magnitude above threshold (1e-6)
    """
    if len(vector) != expected_dim:
        return False, f"wrong dimensions: got {len(vector)}, expected {expected_dim}"
    if any(math.isnan(v) for v in vector):
        return False, "contains NaN values"
    if all(v == 0.0 for v in vector):
        return False, "zero vector"
    magnitude = math.sqrt(sum(v * v for v in vector))
    if magnitude < 1e-6:
        return False, f"magnitude below threshold: {magnitude}"
    return True, ""


class BatchEmbedder:
    """Parallel batch embedding via Ollama API.

    Uses ThreadPoolExecutor with configurable max_workers (settings.embed_max_workers)
    and batch_size (settings.embed_batch_size) per Ollama call.
    """

    def __init__(
        self,
        model: str | None = None,
        max_workers: int | None = None,
        batch_size: int | None = None,
        embedding_provider=None,
    ):
        self.model = model or settings.default_embed_model
        self.max_workers = max_workers or settings.embed_max_workers
        self.batch_size = batch_size or settings.embed_batch_size
        self.base_url = settings.ollama_base_url
        self._embedding_provider = embedding_provider

    async def embed_chunks(
        self, texts: list[str]
    ) -> tuple[list[list[float] | None], int]:
        """Embed a list of texts in parallel batches with validation.

        Returns (embeddings, chunks_skipped) where embeddings preserves input
        order. Invalid embeddings are replaced with None and counted as skipped.
        """
        if not texts:
            return [], 0

        # Split texts into batches
        batches = [
            texts[i : i + self.batch_size]
            for i in range(0, len(texts), self.batch_size)
        ]

        logger.info(
            "ingestion_embedding_chunks",
            total_texts=len(texts),
            batch_count=len(batches),
            batch_size=self.batch_size,
            max_workers=self.max_workers,
        )

        loop = asyncio.get_running_loop()

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [
                loop.run_in_executor(executor, self._embed_batch, batch)
                for batch in batches
            ]
            batch_results = await asyncio.gather(*futures)

        # Flatten batch results into a single list preserving order
        raw_embeddings: list[list[float]] = []
        for batch_result in batch_results:
            raw_embeddings.extend(batch_result)

        # Validate each embedding (FR-010: skip-and-continue)
        expected_dim = len(raw_embeddings[0]) if raw_embeddings else 0
        results: list[list[float] | None] = []
        chunks_skipped = 0

        for i, vector in enumerate(raw_embeddings):
            is_valid, reason = validate_embedding(vector, expected_dim)
            if not is_valid:
                chunks_skipped += 1
                logger.warning(
                    "ingestion_embedding_validation_failed",
                    chunk_index=i,
                    reason=reason,
                )
                results.append(None)
            else:
                results.append(vector)

        logger.info(
            "ingestion_embedding_complete",
            total_vectors=len(raw_embeddings),
            chunks_skipped=chunks_skipped,
        )
        return results, chunks_skipped

    def _embed_batch(self, batch: list[str]) -> list[list[float]]:
        """Synchronous: embed a single batch via Ollama /api/embed endpoint.

        Called from ThreadPoolExecutor threads.
        """
        with httpx.Client() as client:
            response = client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": batch},
                timeout=60.0,
            )
            response.raise_for_status()
            data = response.json()

        return data["embeddings"]
