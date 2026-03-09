# Spec 10: Provider Architecture -- Implementation Context

## Implementation Scope

### Files to Create
```
backend/
  providers/
    __init__.py
    base.py             # LLMProvider ABC, EmbeddingProvider ABC, ModelInfo
    registry.py         # ProviderRegistry class
    ollama.py           # OllamaProvider
    openrouter.py       # OpenRouterProvider
    openai.py           # OpenAIProvider
    anthropic.py        # AnthropicProvider
    key_manager.py      # KeyManager with Fernet encryption
```

### Files to Modify
- `backend/config.py` -- Add provider-related configuration (Ollama URL, encryption secret)
- `backend/api/providers.py` -- Provider management API routes (may already exist from spec-08)

## Code Specifications

### Base Interfaces (`backend/providers/base.py`)

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional
from pydantic import BaseModel
from langchain_core.messages import BaseMessage


class ModelInfo(BaseModel):
    name: str
    provider: str               # "ollama", "openrouter", "openai", "anthropic"
    size: Optional[str] = None  # "7B", "13B", etc.
    quantization: Optional[str] = None  # "Q4_K_M", "Q8_0", etc.
    context_length: Optional[int] = None
    dims: Optional[int] = None  # embedding dimensions (embed models only)


class LLMProvider(ABC):
    @abstractmethod
    async def chat(
        self, messages: List[BaseMessage], model: str, **kwargs
    ) -> AsyncIterator[str]:
        """Stream chat completion tokens."""
        ...

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models from this provider."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is reachable."""
        ...


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        ...

    @abstractmethod
    async def get_dimensions(self, model: str) -> int:
        """Return the embedding dimensions for a model."""
        ...
```

### Key Manager (`backend/providers/key_manager.py`)

```python
import os
import hashlib
import base64
import structlog
from cryptography.fernet import Fernet, InvalidToken

logger = structlog.get_logger()


def get_fernet_key(secret: str) -> bytes:
    """Derive a Fernet key from the .env secret.
    Fernet requires exactly 32 url-safe base64-encoded bytes.
    """
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


class KeyManager:
    def __init__(self, secret: str):
        self.fernet = Fernet(get_fernet_key(secret))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string. Returns base64-encoded ciphertext."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string. Returns plaintext.
        Raises: ProviderAuthError if decryption fails.
        """
        try:
            return self.fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken:
            raise ProviderAuthError(
                message="Failed to decrypt API key -- encryption secret may have changed",
                code="KEY_DECRYPT_ERROR",
            )

    @staticmethod
    def ensure_secret(env_path: str = ".env") -> str:
        """Load or generate the encryption secret.
        If API_KEY_ENCRYPTION_SECRET is not set, generate one and append to .env.
        """
        secret = os.environ.get("API_KEY_ENCRYPTION_SECRET")
        if secret:
            return secret

        secret = base64.urlsafe_b64encode(os.urandom(32)).decode()
        logger.warning("Generated new API_KEY_ENCRYPTION_SECRET -- save this in .env")

        with open(env_path, "a") as f:
            f.write(f"\nAPI_KEY_ENCRYPTION_SECRET={secret}\n")

        os.environ["API_KEY_ENCRYPTION_SECRET"] = secret
        return secret
```

### Ollama Provider (`backend/providers/ollama.py`)

```python
from typing import AsyncIterator, List
from langchain_core.messages import BaseMessage
from langchain_community.chat_models import ChatOllama
import httpx

from backend.providers.base import LLMProvider, EmbeddingProvider, ModelInfo
from backend.errors import ProviderError


class OllamaProvider(LLMProvider, EmbeddingProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url

    async def chat(
        self, messages: List[BaseMessage], model: str, **kwargs
    ) -> AsyncIterator[str]:
        llm = ChatOllama(base_url=self.base_url, model=model, **kwargs)
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def list_models(self) -> List[ModelInfo]:
        async with httpx.AsyncClient() as client:
            res = await client.get(f"{self.base_url}/api/tags", timeout=10.0)
            res.raise_for_status()
            data = res.json()
        return [
            ModelInfo(
                name=m["name"],
                provider="ollama",
                size=m.get("details", {}).get("parameter_size"),
                quantization=m.get("details", {}).get("quantization_level"),
            )
            for m in data.get("models", [])
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"{self.base_url}/api/tags", timeout=5.0)
                return res.status_code == 200
        except Exception:
            return False

    async def embed(self, texts: List[str], model: str) -> List[List[float]]:
        embeddings = []
        async with httpx.AsyncClient() as client:
            for text in texts:
                res = await client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": model, "prompt": text},
                    timeout=30.0,
                )
                res.raise_for_status()
                embeddings.append(res.json()["embedding"])
        return embeddings

    async def get_dimensions(self, model: str) -> int:
        result = await self.embed(["dimension test"], model)
        return len(result[0])
```

### OpenRouter Provider (`backend/providers/openrouter.py`)

```python
from typing import AsyncIterator, List
from langchain_core.messages import BaseMessage
from langchain_openai import ChatOpenAI
import httpx

from backend.providers.base import LLMProvider, ModelInfo


class OpenRouterProvider(LLMProvider):
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def chat(
        self, messages: List[BaseMessage], model: str, **kwargs
    ) -> AsyncIterator[str]:
        llm = ChatOpenAI(
            base_url=self.BASE_URL,
            api_key=self.api_key,
            model=model,
            **kwargs,
        )
        async for chunk in llm.astream(messages):
            if chunk.content:
                yield chunk.content

    async def list_models(self) -> List[ModelInfo]:
        async with httpx.AsyncClient() as client:
            res = await client.get(
                f"{self.BASE_URL}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
            )
            res.raise_for_status()
            data = res.json()
        return [
            ModelInfo(
                name=m["id"],
                provider="openrouter",
                context_length=m.get("context_length"),
            )
            for m in data.get("data", [])
        ]

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"{self.BASE_URL}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5.0,
                )
                return res.status_code == 200
        except Exception:
            return False
```

### Provider Registry (`backend/providers/registry.py`)

```python
from typing import List, Optional
from backend.providers.base import LLMProvider, EmbeddingProvider, ModelInfo
from backend.providers.ollama import OllamaProvider
from backend.providers.openrouter import OpenRouterProvider
from backend.providers.openai import OpenAIProvider
from backend.providers.anthropic import AnthropicProvider
from backend.providers.key_manager import KeyManager
from backend.storage.sqlite_db import SQLiteDB
from backend.errors import (
    ProviderNotConfiguredError, ProviderAuthError, ModelNotFoundError,
)


class ProviderRegistry:
    """Resolves model name -> provider + credentials at runtime."""

    def __init__(self, db: SQLiteDB, key_manager: KeyManager, ollama_url: str):
        self.db = db
        self.key_manager = key_manager
        self.ollama = OllamaProvider(base_url=ollama_url)

    def _resolve_provider_type(self, model_name: str) -> str:
        """Determine provider from model name pattern."""
        if "/" in model_name:
            return "openrouter"
        if model_name.startswith("gpt-") or model_name.startswith("o1-") or model_name.startswith("o3-"):
            return "openai"
        if model_name.startswith("claude-"):
            return "anthropic"
        return "ollama"

    async def _load_and_decrypt_key(self, provider_name: str) -> str:
        provider_row = await self.db.get_provider(provider_name)
        if not provider_row or not provider_row.api_key_encrypted:
            raise ProviderNotConfiguredError(
                message=f"No API key configured for provider: {provider_name}",
                code="PROVIDER_NOT_CONFIGURED",
            )
        return self.key_manager.decrypt(provider_row.api_key_encrypted)

    async def get_provider(self, model_name: str) -> LLMProvider:
        provider_type = self._resolve_provider_type(model_name)
        if provider_type == "ollama":
            return self.ollama
        key = await self._load_and_decrypt_key(provider_type)
        if provider_type == "openrouter":
            return OpenRouterProvider(api_key=key)
        elif provider_type == "openai":
            return OpenAIProvider(api_key=key)
        elif provider_type == "anthropic":
            return AnthropicProvider(api_key=key)
        raise ModelNotFoundError(
            message=f"No provider found for model: {model_name}",
            code="MODEL_NOT_FOUND",
        )

    async def get_embedding_provider(self, model_name: str) -> EmbeddingProvider:
        provider_type = self._resolve_provider_type(model_name)
        if provider_type == "ollama":
            return self.ollama
        if provider_type == "openai":
            key = await self._load_and_decrypt_key("openai")
            return OpenAIProvider(api_key=key)
        raise ModelNotFoundError(
            message=f"No embedding provider for model: {model_name}",
            code="MODEL_NOT_FOUND",
        )

    async def list_all_models(self) -> List[ModelInfo]:
        models: List[ModelInfo] = []
        # Always include Ollama models
        try:
            models.extend(await self.ollama.list_models())
        except Exception:
            pass
        # Include cloud providers if keys are configured
        for provider_name, provider_cls in [
            ("openrouter", OpenRouterProvider),
            ("openai", OpenAIProvider),
            ("anthropic", AnthropicProvider),
        ]:
            try:
                key = await self._load_and_decrypt_key(provider_name)
                provider = provider_cls(api_key=key)
                models.extend(await provider.list_models())
            except (ProviderNotConfiguredError, Exception):
                continue
        return models
```

## Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_ENCRYPTION_SECRET` | (auto-generated) | Secret used to derive Fernet encryption key for API key storage |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |

### SQLite `providers` Table Schema
```sql
CREATE TABLE IF NOT EXISTS providers (
    name TEXT PRIMARY KEY,
    api_key_encrypted TEXT,
    base_url TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);
```

## Error Handling

- **`ProviderNotConfiguredError`**: Raised when requesting a cloud provider without a stored API key. HTTP 400.
- **`ProviderAuthError`**: Raised when API key decryption fails or provider rejects the key. HTTP 401.
- **`ProviderRateLimitError`**: Raised when provider returns 429 Too Many Requests. HTTP 429.
- **`ModelNotFoundError`**: Raised when model name cannot be mapped to any provider. HTTP 404.
- **Health check failures**: Caught and returned as `False`, never crash the application.
- **Key encryption errors**: Caught and wrapped in `ProviderAuthError` with a descriptive message.

All provider errors extend `ProviderError`, which extends `EmbdinatorError`. They include `message`, `code`, and optional `details` fields.

## Testing Requirements

### Unit Tests
- `KeyManager`: Roundtrip encrypt/decrypt produces original plaintext
- `KeyManager`: Decrypt with wrong secret raises `ProviderAuthError`
- `KeyManager.ensure_secret()`: Generates and persists secret when missing
- `ProviderRegistry._resolve_provider_type()`: Correct mapping for model name patterns (`llama3.2` -> ollama, `gpt-4` -> openai, `claude-3` -> anthropic, `meta-llama/llama-3` -> openrouter)
- `ProviderRegistry.get_provider()`: Returns correct provider type for each model pattern
- `ProviderRegistry.get_provider()`: Raises `ProviderNotConfiguredError` for cloud models without keys
- `OllamaProvider.list_models()`: Parses Ollama API response correctly
- `OpenRouterProvider.list_models()`: Parses OpenRouter API response correctly

### Integration Tests (require running services)
- `OllamaProvider.health_check()`: Returns `True` when Ollama is running
- `OllamaProvider.embed()`: Returns valid embeddings with correct dimensions
- `OllamaProvider.chat()`: Streams tokens for a simple prompt
- `ProviderRegistry` end-to-end: Store encrypted key, resolve provider, get models

## Done Criteria

1. `backend/providers/base.py` defines `LLMProvider` and `EmbeddingProvider` ABCs with all required abstract methods
2. `backend/providers/key_manager.py` implements Fernet encryption/decryption with secret auto-generation
3. `backend/providers/ollama.py` implements both `LLMProvider` and `EmbeddingProvider` with working `chat()`, `embed()`, `list_models()`, and `health_check()`
4. `backend/providers/openrouter.py` implements `LLMProvider` with `ChatOpenAI(base_url=openrouter)` instantiation
5. `backend/providers/openai.py` implements both `LLMProvider` and `EmbeddingProvider`
6. `backend/providers/anthropic.py` implements `LLMProvider` with `ChatAnthropic` instantiation
7. `backend/providers/registry.py` correctly resolves model names to providers and handles key decryption
8. All unit tests pass: key manager roundtrip, provider resolution, model listing parsing
9. API keys are never logged or exposed in any output
10. Provider health check failures are caught gracefully and return `False`
