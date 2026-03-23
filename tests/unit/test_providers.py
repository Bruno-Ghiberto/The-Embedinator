"""Unit tests for provider base classes and registry — T024, T026, T027."""

import httpx
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.providers.base import LLMProvider, EmbeddingProvider, ProviderRateLimitError
from backend.errors import EmbeddinatorError


def test_llm_provider_is_abstract():
    """Verify LLMProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        LLMProvider()


def test_embedding_provider_is_abstract():
    """Verify EmbeddingProvider cannot be instantiated directly."""
    with pytest.raises(TypeError):
        EmbeddingProvider()


def test_error_hierarchy():
    """Verify all custom exceptions inherit from EmbeddinatorError."""
    from backend.errors import (
        QdrantConnectionError,
        OllamaConnectionError,
        SQLiteError,
        LLMCallError,
        EmbeddingError,
        IngestionError,
        SessionLoadError,
        StructuredOutputParseError,
        RerankerError,
    )

    exceptions = [
        QdrantConnectionError,
        OllamaConnectionError,
        SQLiteError,
        LLMCallError,
        EmbeddingError,
        IngestionError,
        SessionLoadError,
        StructuredOutputParseError,
        RerankerError,
    ]
    for exc_class in exceptions:
        assert issubclass(exc_class, EmbeddinatorError), f"{exc_class.__name__} doesn't inherit from EmbeddinatorError"
        # Verify they can be instantiated
        instance = exc_class("test message")
        assert str(instance) == "test message"


# ── Helpers ───────────────────────────────────────────────────────


def _make_ctx_mock(post_side_effects):
    """Return (ctx, mock_client) for mocking httpx.AsyncClient as async context manager."""
    mock_client = AsyncMock()
    mock_client.post.side_effect = post_side_effects
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_client)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx, mock_client


def _make_stream_client_mock():
    """Return a mock httpx.AsyncClient for non-context-manager streaming usage."""
    mock_client = AsyncMock()
    mock_client.build_request = MagicMock(return_value=MagicMock())
    mock_client.aclose = AsyncMock()
    return mock_client


async def _empty_aiter():
    """Async generator that yields nothing — simulates an empty SSE stream."""
    return
    yield  # makes it an async generator function


# ── T026: Cloud Provider Retry and 429 Behavior ───────────────────


class TestCloudProviderRetryBehavior:
    """T026: 5xx retries once; 429 raises ProviderRateLimitError immediately."""

    # ── OpenRouter generate() ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_openrouter_generate_retries_once_on_5xx(self):
        from backend.providers.openrouter import OpenRouterLLMProvider

        mock_resp_503 = MagicMock()
        mock_resp_503.status_code = 503
        error_503 = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_resp_503)

        mock_resp_200 = MagicMock()
        mock_resp_200.raise_for_status = MagicMock()
        mock_resp_200.json.return_value = {"choices": [{"message": {"content": "ok"}}]}

        ctx, mock_client = _make_ctx_mock([error_503, mock_resp_200])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OpenRouterLLMProvider(api_key="sk-test", model="openai/gpt-4o-mini")
            result = await provider.generate("hello")

        assert result == "ok"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_openrouter_generate_429_raises_immediately_no_retry(self):
        from backend.providers.openrouter import OpenRouterLLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        error_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)

        ctx, mock_client = _make_ctx_mock([error_429])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OpenRouterLLMProvider(api_key="sk-test", model="openai/gpt-4o-mini")
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await provider.generate("hello")

        assert exc_info.value.provider == "OpenRouterLLMProvider"
        assert mock_client.post.call_count == 1  # no retry

    @pytest.mark.asyncio
    async def test_openrouter_generate_5xx_second_failure_reraises(self):
        from backend.providers.openrouter import OpenRouterLLMProvider

        mock_resp_503 = MagicMock()
        mock_resp_503.status_code = 503
        error_503 = httpx.HTTPStatusError("503", request=MagicMock(), response=mock_resp_503)

        ctx, mock_client = _make_ctx_mock([error_503, error_503])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OpenRouterLLMProvider(api_key="sk-test", model="openai/gpt-4o-mini")
            with pytest.raises(httpx.HTTPStatusError):
                await provider.generate("hello")

        assert mock_client.post.call_count == 2

    # ── OpenAI generate() ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_openai_generate_retries_once_on_5xx(self):
        from backend.providers.openai import OpenAILLMProvider

        mock_resp_500 = MagicMock()
        mock_resp_500.status_code = 500
        error_500 = httpx.HTTPStatusError("500", request=MagicMock(), response=mock_resp_500)

        mock_resp_200 = MagicMock()
        mock_resp_200.raise_for_status = MagicMock()
        mock_resp_200.json.return_value = {"choices": [{"message": {"content": "openai-ok"}}]}

        ctx, mock_client = _make_ctx_mock([error_500, mock_resp_200])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o-mini")
            result = await provider.generate("hello")

        assert result == "openai-ok"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_openai_generate_429_raises_immediately_no_retry(self):
        from backend.providers.openai import OpenAILLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        error_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)

        ctx, mock_client = _make_ctx_mock([error_429])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o-mini")
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await provider.generate("hello")

        assert exc_info.value.provider == "OpenAILLMProvider"
        assert mock_client.post.call_count == 1

    # ── Anthropic generate() ─────────────────────────────────────

    @pytest.mark.asyncio
    async def test_anthropic_generate_retries_once_on_5xx(self):
        from backend.providers.anthropic import AnthropicLLMProvider

        mock_resp_529 = MagicMock()
        mock_resp_529.status_code = 529
        error_529 = httpx.HTTPStatusError("529", request=MagicMock(), response=mock_resp_529)

        mock_resp_200 = MagicMock()
        mock_resp_200.raise_for_status = MagicMock()
        mock_resp_200.json.return_value = {"content": [{"text": "anthropic-ok"}]}

        ctx, mock_client = _make_ctx_mock([error_529, mock_resp_200])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = AnthropicLLMProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
            result = await provider.generate("hello")

        assert result == "anthropic-ok"
        assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_anthropic_generate_429_raises_immediately_no_retry(self):
        from backend.providers.anthropic import AnthropicLLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        error_429 = httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)

        ctx, mock_client = _make_ctx_mock([error_429])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = AnthropicLLMProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
            with pytest.raises(ProviderRateLimitError) as exc_info:
                await provider.generate("hello")

        assert exc_info.value.provider == "AnthropicLLMProvider"
        assert mock_client.post.call_count == 1

    # ── generate_stream() ────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_openrouter_generate_stream_429_raises_immediately_no_retry(self):
        from backend.providers.openrouter import OpenRouterLLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.aread = AsyncMock()
        mock_resp_429.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)
        )

        mock_client = _make_stream_client_mock()
        mock_client.send = AsyncMock(return_value=mock_resp_429)

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = mock_client
            provider = OpenRouterLLMProvider(api_key="sk-test", model="openai/gpt-4o-mini")
            with pytest.raises(ProviderRateLimitError):
                async for _ in provider.generate_stream("hello"):
                    pass

        assert mock_client.send.call_count == 1  # no retry

    @pytest.mark.asyncio
    async def test_openrouter_generate_stream_retries_once_on_5xx(self):
        from backend.providers.openrouter import OpenRouterLLMProvider

        mock_resp_503 = MagicMock()
        mock_resp_503.status_code = 503
        mock_resp_503.aread = AsyncMock()
        mock_resp_503.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("503", request=MagicMock(), response=mock_resp_503)
        )

        mock_resp_200 = MagicMock()
        mock_resp_200.status_code = 200
        mock_resp_200.aiter_lines = MagicMock(return_value=_empty_aiter())
        mock_resp_200.aclose = AsyncMock()

        mock_client = _make_stream_client_mock()
        mock_client.send = AsyncMock(side_effect=[mock_resp_503, mock_resp_200])

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = mock_client
            provider = OpenRouterLLMProvider(api_key="sk-test", model="openai/gpt-4o-mini")
            tokens = []
            async for token in provider.generate_stream("hello"):
                tokens.append(token)

        assert mock_client.send.call_count == 2

    @pytest.mark.asyncio
    async def test_openai_generate_stream_429_raises_immediately_no_retry(self):
        from backend.providers.openai import OpenAILLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.aread = AsyncMock()
        mock_resp_429.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)
        )

        mock_client = _make_stream_client_mock()
        mock_client.send = AsyncMock(return_value=mock_resp_429)

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = mock_client
            provider = OpenAILLMProvider(api_key="sk-test", model="gpt-4o-mini")
            with pytest.raises(ProviderRateLimitError):
                async for _ in provider.generate_stream("hello"):
                    pass

        assert mock_client.send.call_count == 1

    @pytest.mark.asyncio
    async def test_anthropic_generate_stream_429_raises_immediately_no_retry(self):
        from backend.providers.anthropic import AnthropicLLMProvider

        mock_resp_429 = MagicMock()
        mock_resp_429.status_code = 429
        mock_resp_429.aread = AsyncMock()
        mock_resp_429.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError("429", request=MagicMock(), response=mock_resp_429)
        )

        mock_client = _make_stream_client_mock()
        mock_client.send = AsyncMock(return_value=mock_resp_429)

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = mock_client
            provider = AnthropicLLMProvider(api_key="sk-ant-test", model="claude-sonnet-4-20250514")
            with pytest.raises(ProviderRateLimitError):
                async for _ in provider.generate_stream("hello"):
                    pass

        assert mock_client.send.call_count == 1


# ── T027: OllamaEmbeddingProvider Model-Agnostic Parameter ────────


class TestOllamaEmbedModelParam:
    """T027: embed()/embed_single() use self.model by default; override when specified."""

    def _make_embed_ctx(self, embedding_data: list[float]):
        """Return (ctx, mock_client) for mocking the embed httpx call."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"embeddings": [embedding_data]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_resp)

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx, mock_client

    @pytest.mark.asyncio
    async def test_embed_uses_self_model_when_no_model_arg(self):
        from backend.providers.ollama import OllamaEmbeddingProvider

        ctx, mock_client = self._make_embed_ctx([0.1, 0.2, 0.3])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="nomic-embed-text")
            await provider.embed(["hello world"])

        called_json = mock_client.post.call_args[1]["json"]
        assert called_json["model"] == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_embed_uses_override_model_when_specified(self):
        from backend.providers.ollama import OllamaEmbeddingProvider

        ctx, mock_client = self._make_embed_ctx([0.1, 0.2, 0.3])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="nomic-embed-text")
            await provider.embed(["hello world"], model="mxbai-embed-large")

        called_json = mock_client.post.call_args[1]["json"]
        assert called_json["model"] == "mxbai-embed-large"

    @pytest.mark.asyncio
    async def test_embed_single_uses_self_model_when_no_model_arg(self):
        from backend.providers.ollama import OllamaEmbeddingProvider

        ctx, mock_client = self._make_embed_ctx([0.4, 0.5, 0.6])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="nomic-embed-text")
            await provider.embed_single("test text")

        called_json = mock_client.post.call_args[1]["json"]
        assert called_json["model"] == "nomic-embed-text"

    @pytest.mark.asyncio
    async def test_embed_single_uses_override_model_when_specified(self):
        from backend.providers.ollama import OllamaEmbeddingProvider

        ctx, mock_client = self._make_embed_ctx([0.4, 0.5, 0.6])
        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="nomic-embed-text")
            await provider.embed_single("test text", model="all-MiniLM-L6-v2")

        called_json = mock_client.post.call_args[1]["json"]
        assert called_json["model"] == "all-MiniLM-L6-v2"

    @pytest.mark.asyncio
    async def test_embed_single_falls_back_to_legacy_embeddings_endpoint_on_404(self):
        from backend.providers.ollama import OllamaEmbeddingProvider

        primary_response = MagicMock()
        primary_response.status_code = 404

        fallback_response = MagicMock()
        fallback_response.raise_for_status = MagicMock()
        fallback_response.json.return_value = {"embedding": [0.9, 0.8, 0.7]}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[primary_response, fallback_response])

        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=mock_client)
        ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value = ctx
            provider = OllamaEmbeddingProvider(base_url="http://localhost:11434", model="nomic-embed-text")
            embedding = await provider.embed_single("test text")

        assert mock_client.post.call_count == 2
        first_call = mock_client.post.call_args_list[0]
        assert "/api/embed" in first_call[0][0]
        second_call = mock_client.post.call_args_list[1]
        assert "/api/embeddings" in second_call[0][0]
        assert second_call[1]["json"] == {"model": "nomic-embed-text", "prompt": "test text"}
        assert embedding == [0.9, 0.8, 0.7]
