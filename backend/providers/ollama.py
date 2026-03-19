"""Ollama LLM and embedding provider implementation."""

from typing import AsyncIterator

import httpx
import structlog

from backend.errors import LLMCallError, EmbeddingError, OllamaConnectionError
from backend.providers.base import LLMProvider, EmbeddingProvider

logger = structlog.get_logger().bind(component=__name__)


class OllamaLLMProvider(LLMProvider):
    """Ollama LLM provider using the HTTP API."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """Generate a complete response from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                return response.json()["response"]
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama at {self.base_url}: {e}") from e
        except Exception as e:
            raise LLMCallError(f"Ollama generate failed: {e}") from e

    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        """Stream tokens from Ollama."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    import json
                    async for line in response.aiter_lines():
                        if line:
                            data = json.loads(line)
                            if not data.get("done", False):
                                yield data.get("response", "")
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama at {self.base_url}: {e}") from e
        except Exception as e:
            raise LLMCallError(f"Ollama streaming failed: {e}") from e

    async def health_check(self) -> bool:
        """Check if Ollama is running and the model is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                tags = response.json()
                models = [m["name"] for m in tags.get("models", [])]
                return self.model in models or any(self.model in m for m in models)
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self.model


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Ollama embedding provider using the HTTP API."""

    def __init__(self, base_url: str, model: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._dimension: int | None = None

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        results = []
        for text in texts:
            embedding = await self.embed_single(text, model=model)
            results.append(embedding)
        return results

    async def embed_single(self, text: str, model: str | None = None) -> list[float]:
        """Generate embedding for a single text."""
        effective_model = model or self.model
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/embed",
                    json={"model": effective_model, "input": text},
                )
                response.raise_for_status()
                data = response.json()
                embedding = data["embeddings"][0]
                if self._dimension is None:
                    self._dimension = len(embedding)
                return embedding
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Cannot connect to Ollama: {e}") from e
        except Exception as e:
            raise EmbeddingError(f"Ollama embedding failed: {e}") from e

    def get_model_name(self) -> str:
        return self.model

    def get_dimension(self) -> int:
        return self._dimension or 384  # Default for nomic-embed-text
