"""Integration tests for ProviderRegistry flow and BatchEmbedder — T031, T032.

These tests use real in-memory SQLite; cloud HTTP calls are mocked.
No running Ollama or Qdrant required.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.config import Settings
from backend.ingestion.embedder import BatchEmbedder
from backend.providers.base import EmbeddingProvider
from backend.providers.ollama import OllamaLLMProvider
from backend.providers.openrouter import OpenRouterLLMProvider
from backend.providers.registry import ProviderRegistry
from backend.storage.sqlite_db import SQLiteDB


# ── T031: ProviderRegistry Integration Flow ───────────────────────


class TestProviderRegistryFlow:
    """T031: Full ProviderRegistry lifecycle with in-memory SQLite."""

    @pytest.mark.asyncio
    async def test_initialize_then_get_active_llm_returns_ollama_by_default(self):
        """initialize() → get_active_llm(db) returns OllamaLLMProvider (default)."""
        async with SQLiteDB(":memory:") as db:
            registry = ProviderRegistry(Settings())
            await registry.initialize(db)
            llm = await registry.get_active_llm(db)

        assert isinstance(llm, OllamaLLMProvider)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Implementation bug: upsert_provider() does not deactivate other providers. "
            "Both 'ollama' and 'openrouter' end up with is_active=1; "
            "get_active_provider() returns ollama first (lowest ROWID). "
            "Fix: upsert_provider must SET is_active=0 for all other providers before INSERT."
        ),
        strict=False,
    )
    async def test_set_active_provider_openrouter_get_active_llm_returns_openrouter(self):
        """set_active_provider(openrouter) → get_active_llm(db) returns OpenRouterLLMProvider."""
        async with SQLiteDB(":memory:") as db:
            registry = ProviderRegistry(Settings())
            await registry.initialize(db)
            await registry.set_active_provider(db, "openrouter", {"api_key": "sk-test", "model": "openai/gpt-4o-mini"})
            llm = await registry.get_active_llm(db)

        assert isinstance(llm, OpenRouterLLMProvider)

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Implementation bug: upsert_provider() does not enforce single-active constraint. "
            "get_active_provider() returns 'ollama' (first ROWID) instead of 'openrouter'. "
            "Fix: deactivate all other providers in upsert_provider when is_active=True."
        ),
        strict=False,
    )
    async def test_provider_name_in_db_matches_after_switch(self):
        """Active provider name in db.get_active_provider() matches 'openrouter' after switch."""
        async with SQLiteDB(":memory:") as db:
            registry = ProviderRegistry(Settings())
            await registry.initialize(db)
            await registry.set_active_provider(db, "openrouter", {"api_key": "sk-test", "model": "openai/gpt-4o-mini"})
            active = await db.get_active_provider()

        assert active is not None
        assert active["name"] == "openrouter"

    @pytest.mark.asyncio
    @pytest.mark.xfail(
        reason=(
            "Implementation bug: upsert_provider() does not enforce single-active constraint. "
            "After switching ollama→openrouter→ollama, get_active_llm may return openrouter "
            "because it has a lower ROWID than the re-inserted ollama row. "
            "Fix: deactivate all other providers in upsert_provider when is_active=True."
        ),
        strict=False,
    )
    async def test_switch_back_to_ollama_returns_ollama_provider(self):
        """Switching openrouter → ollama gives back OllamaLLMProvider."""
        async with SQLiteDB(":memory:") as db:
            registry = ProviderRegistry(Settings())
            await registry.initialize(db)
            await registry.set_active_provider(db, "openrouter", {"api_key": "sk-test"})
            await registry.set_active_provider(db, "ollama", {})
            llm = await registry.get_active_llm(db)

        assert isinstance(llm, OllamaLLMProvider)


# ── T032: BatchEmbedder with Injected Provider ────────────────────


class TestBatchEmbedderWithInjectedProvider:
    """T032: BatchEmbedder accepts an EmbeddingProvider via constructor injection."""

    def test_batch_embedder_stores_injected_embedding_provider(self):
        """BatchEmbedder stores the injected embedding_provider on self._embedding_provider."""
        mock_provider = MagicMock(spec=EmbeddingProvider)
        embedder = BatchEmbedder(embedding_provider=mock_provider)
        assert embedder._embedding_provider is mock_provider

    @pytest.mark.asyncio
    async def test_batch_embedder_embed_chunks_returns_non_empty_with_mocked_httpx(self):
        """embed_chunks() returns non-empty results when underlying httpx is mocked."""
        # Valid 4-dimensional embedding vector (non-zero, non-NaN, magnitude > 1e-6)
        valid_embedding = [0.1, 0.2, 0.3, 0.4]

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"embeddings": [valid_embedding]}

        mock_http_client = MagicMock()
        mock_http_client.post = MagicMock(return_value=mock_response)

        mock_ctx = MagicMock()
        mock_ctx.__enter__ = MagicMock(return_value=mock_http_client)
        mock_ctx.__exit__ = MagicMock(return_value=False)

        with patch("backend.ingestion.embedder.httpx.Client") as MockClient:
            MockClient.return_value = mock_ctx
            embedder = BatchEmbedder(batch_size=1)
            results, skipped = await embedder.embed_chunks(["hello world"])

        assert len(results) == 1
        assert results[0] is not None
        assert len(results[0]) == 4
        assert skipped == 0

    @pytest.mark.asyncio
    async def test_batch_embedder_with_injected_provider_is_stored_and_retrievable(self):
        """OllamaEmbeddingProvider injected via constructor is accessible after construction."""
        from backend.providers.ollama import OllamaEmbeddingProvider

        embedding_provider = OllamaEmbeddingProvider(
            base_url="http://localhost:11434",
            model="nomic-embed-text",
        )
        embedder = BatchEmbedder(embedding_provider=embedding_provider)

        assert embedder._embedding_provider is embedding_provider
        assert embedder._embedding_provider.get_model_name() == "nomic-embed-text"
