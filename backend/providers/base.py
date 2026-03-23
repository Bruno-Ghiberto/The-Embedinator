"""Abstract base classes for LLM and embedding providers."""

from abc import ABC, abstractmethod
from typing import AsyncIterator


class ProviderRateLimitError(Exception):
    """Raised by cloud providers on HTTP 429 rate limit responses."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")


class LLMProvider(ABC):
    """Abstract interface for LLM inference providers."""

    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a complete response."""

    @abstractmethod
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        """Generate a streaming response, yielding tokens."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable and ready."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the model identifier."""


class EmbeddingProvider(ABC):
    """Abstract interface for embedding generation."""

    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Args:
            texts: Input texts to embed.
            model: Override model identifier. If None, uses self.model.
        """

    @abstractmethod
    async def embed_single(self, text: str, model: str | None = None) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Input text to embed.
            model: Override model identifier. If None, uses self.model.
        """

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the embedding model identifier."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the embedding vector dimension."""
