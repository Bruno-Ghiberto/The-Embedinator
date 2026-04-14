"""Unit tests for BatchEmbedder — spec-06 ingestion pipeline."""

import asyncio
import math
from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.embedder import BatchEmbedder, validate_embedding


class TestBatchEmbedder:
    """Tests for parallel batch embedding."""

    def test_embed_chunks_splits_into_correct_batches(self):
        """100 texts with batch_size=16 produces 7 batches (6*16 + 1*4)."""
        texts = [f"text_{i}" for i in range(100)]
        embedder = BatchEmbedder(batch_size=16, max_workers=2)

        call_count = 0
        original_batches: list[int] = []

        def mock_embed_batch(batch: list[str]) -> list[list[float]]:
            nonlocal call_count
            call_count += 1
            original_batches.append(len(batch))
            return [[0.1] * 384 for _ in batch]

        embedder._embed_batch = mock_embed_batch  # type: ignore[method-assign]

        results, skipped = asyncio.run(embedder.embed_chunks(texts))

        assert call_count == 7  # ceil(100/16) = 7
        assert sum(original_batches) == 100
        assert len(results) == 100
        assert skipped == 0
        # First 6 batches should be full, last one partial
        assert sorted(original_batches, reverse=True)[:6] == [16] * 6
        assert sorted(original_batches)[0] == 4  # 100 - 96 = 4

    def test_embed_chunks_preserves_order(self):
        """Results must be in same order as input texts."""
        texts = [f"text_{i}" for i in range(5)]
        embedder = BatchEmbedder(batch_size=2, max_workers=2)

        def mock_embed_batch(batch: list[str]) -> list[list[float]]:
            # Return a unique vector per text based on its index (offset by 1 to avoid zero vector)
            return [[float(t.split("_")[1]) + 1.0] * 384 for t in batch]

        embedder._embed_batch = mock_embed_batch  # type: ignore[method-assign]

        results, skipped = asyncio.run(embedder.embed_chunks(texts))

        assert len(results) == 5
        assert skipped == 0
        for i, vec in enumerate(results):
            assert vec[0] == float(i) + 1.0

    def test_embed_chunks_empty_input(self):
        """Empty input returns ([], 0) without calling Ollama."""
        embedder = BatchEmbedder()

        results, skipped = asyncio.run(embedder.embed_chunks([]))

        assert results == []
        assert skipped == 0

    def test_embed_batch_calls_ollama_api(self):
        """_embed_batch calls Ollama /api/embed with correct payload."""
        embedder = BatchEmbedder(model="test-model")
        batch = ["hello", "world"]

        mock_response = MagicMock()
        mock_response.json.return_value = {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
        mock_response.raise_for_status = MagicMock()

        with patch("backend.ingestion.embedder.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            result = embedder._embed_batch(batch)

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/api/embed" in call_args[0][0]
        assert call_args[1]["json"]["model"] == "test-model"
        assert call_args[1]["json"]["input"] == ["hello", "world"]
        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    def test_embed_batch_propagates_http_error(self):
        """HTTP errors from Ollama propagate as exceptions."""
        import httpx

        embedder = BatchEmbedder()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        with patch("backend.ingestion.embedder.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                embedder._embed_batch(["test"])

    def test_embed_batch_falls_back_to_legacy_embeddings_endpoint_on_404(self):
        """If /api/embed returns 404, _embed_batch falls back to /api/embeddings."""
        embedder = BatchEmbedder(model="test-model")

        primary_response = MagicMock()
        primary_response.status_code = 404

        fallback_response_1 = MagicMock()
        fallback_response_1.raise_for_status = MagicMock()
        fallback_response_1.json.return_value = {"embedding": [0.11, 0.22]}

        fallback_response_2 = MagicMock()
        fallback_response_2.raise_for_status = MagicMock()
        fallback_response_2.json.return_value = {"embedding": [0.33, 0.44]}

        with patch("backend.ingestion.embedder.httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = [
                primary_response,
                fallback_response_1,
                fallback_response_2,
            ]
            mock_client_cls.return_value = mock_client

            result = embedder._embed_batch(["hello", "world"])

        assert mock_client.post.call_count == 3
        first_call = mock_client.post.call_args_list[0]
        assert "/api/embed" in first_call[0][0]
        second_call = mock_client.post.call_args_list[1]
        assert "/api/embeddings" in second_call[0][0]
        assert second_call[1]["json"] == {"model": "test-model", "prompt": "hello"}
        third_call = mock_client.post.call_args_list[2]
        assert third_call[1]["json"] == {"model": "test-model", "prompt": "world"}
        assert result == [[0.11, 0.22], [0.33, 0.44]]

    def test_default_settings_used(self):
        """BatchEmbedder uses settings defaults when no args provided."""
        # spec-26: BUG-023 — max_workers raised 4→12 per audit §CPU CPU-002 (commit 8a1107e)
        embedder = BatchEmbedder()

        assert embedder.model == "nomic-embed-text"
        assert embedder.max_workers == 12
        assert embedder.batch_size == 16

    def test_custom_settings_override(self):
        """BatchEmbedder accepts custom model, max_workers, batch_size."""
        embedder = BatchEmbedder(model="custom-model", max_workers=8, batch_size=32)

        assert embedder.model == "custom-model"
        assert embedder.max_workers == 8
        assert embedder.batch_size == 32


class TestValidateEmbedding:
    """Tests for embedding validation checks."""

    def test_valid_embedding_passes(self):
        """Valid vector with correct dimensions and normal values passes."""
        vector = [0.1] * 384
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is True
        assert reason == ""

    def test_return_type_is_tuple_bool_str(self):
        """Return type is tuple[bool, str] in all cases."""
        # Valid case
        result = validate_embedding([0.1] * 384, 384)
        assert isinstance(result, tuple)
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

        # Invalid case
        result = validate_embedding([0.1] * 100, 384)
        assert isinstance(result, tuple)
        assert isinstance(result[0], bool)
        assert isinstance(result[1], str)

    def test_wrong_dimensions(self):
        """Wrong dimension count returns False with descriptive reason."""
        vector = [0.1] * 100
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert reason == "wrong dimensions: got 100, expected 384"

    def test_contains_nan_values(self):
        """NaN values in vector are detected."""
        vector = [0.1] * 383 + [float("nan")]
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert reason == "contains NaN values"

    def test_zero_vector(self):
        """All-zero vector is rejected."""
        vector = [0.0] * 384
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert reason == "zero vector"

    def test_magnitude_below_threshold(self):
        """Very small magnitude vector (near-zero but not exactly zero) is rejected."""
        # Create a vector with magnitude well below 1e-6
        tiny_val = 1e-8
        vector = [tiny_val] + [0.0] * 383
        magnitude = math.sqrt(tiny_val**2)
        assert magnitude < 1e-6  # Confirm it's below threshold

        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert "magnitude below threshold" in reason

    def test_valid_small_but_above_threshold(self):
        """Vector with small but sufficient magnitude passes."""
        # Create a vector with magnitude just above 1e-6
        val = 1e-3
        vector = [val] + [0.0] * 383
        magnitude = math.sqrt(val**2)
        assert magnitude >= 1e-6  # Confirm it's above threshold

        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is True
        assert reason == ""

    def test_checks_ordered_dimensions_first(self):
        """Dimension check runs before NaN/zero checks."""
        # Wrong dims AND contains NaN — should report dimensions
        vector = [float("nan")] * 100
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert "wrong dimensions" in reason

    def test_nan_check_before_zero_check(self):
        """NaN check runs before zero vector check."""
        # All NaN with correct dims — should report NaN, not zero
        vector = [float("nan")] * 384
        is_valid, reason = validate_embedding(vector, 384)

        assert is_valid is False
        assert reason == "contains NaN values"


class TestEmbedChunksSkipAndContinue:
    """Tests for FR-010: skip-and-continue in embed_chunks."""

    def test_invalid_embedding_skipped_rest_succeeds(self):
        """Invalid embedding returns None, rest of batch succeeds."""
        embedder = BatchEmbedder(batch_size=10, max_workers=1)

        def mock_embed_batch(batch: list[str]) -> list[list[float]]:
            results = []
            for i, _ in enumerate(batch):
                if i == 1:
                    # Return a zero vector (will fail validation)
                    results.append([0.0] * 384)
                else:
                    results.append([0.1] * 384)
            return results

        embedder._embed_batch = mock_embed_batch  # type: ignore[method-assign]

        results, skipped = asyncio.run(embedder.embed_chunks(["a", "b", "c"]))

        assert len(results) == 3
        assert skipped == 1
        assert results[0] is not None
        assert results[1] is None  # zero vector skipped
        assert results[2] is not None

    def test_all_valid_embeddings_no_skip(self):
        """All valid embeddings -> 0 skipped."""
        embedder = BatchEmbedder(batch_size=10, max_workers=1)

        def mock_embed_batch(batch: list[str]) -> list[list[float]]:
            return [[0.1] * 384 for _ in batch]

        embedder._embed_batch = mock_embed_batch  # type: ignore[method-assign]

        results, skipped = asyncio.run(embedder.embed_chunks(["a", "b"]))

        assert len(results) == 2
        assert skipped == 0
        assert all(r is not None for r in results)

    def test_nan_embedding_skipped(self):
        """NaN embedding is skipped via validation."""
        embedder = BatchEmbedder(batch_size=10, max_workers=1)

        def mock_embed_batch(batch: list[str]) -> list[list[float]]:
            return [[float("nan")] * 384 if i == 0 else [0.1] * 384 for i, _ in enumerate(batch)]

        embedder._embed_batch = mock_embed_batch  # type: ignore[method-assign]

        results, skipped = asyncio.run(embedder.embed_chunks(["a", "b"]))

        assert skipped == 1
        assert results[0] is None
        assert results[1] is not None
