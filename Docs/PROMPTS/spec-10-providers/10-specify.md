# Spec 10: Provider Architecture -- Feature Specification Context

## Feature Description

The Provider Architecture is a multi-provider abstraction layer that allows The Embedinator to use LLMs and embedding models from multiple sources: Ollama (local, default), OpenRouter (200+ cloud models with one API key), OpenAI (direct), and Anthropic (direct). The system uses a `ProviderRegistry` that maintains a single active LLM provider at a time, loads encrypted API credentials from SQLite, and instantiates the appropriate custom provider instance.

The architecture supports both LLM providers (for chat completion) and embedding providers (for vector generation), with Ollama implementing both interfaces via two separate classes. API keys are encrypted at rest using Fernet symmetric encryption, with the encryption key loaded from the `EMBEDINATOR_FERNET_KEY` environment variable.

## Requirements

### Functional Requirements

1. **Provider Registry**: A `ProviderRegistry` class that manages the active LLM provider and returns the correct provider instance with decrypted credentials at runtime
2. **LLM Provider Interface**: Abstract base class `LLMProvider` with `generate()` (complete), `generate_stream()` (streaming), `health_check()`, and `get_model_name()` methods
3. **Embedding Provider Interface**: Abstract base class `EmbeddingProvider` with `embed()` (batch), `embed_single()`, `get_model_name()`, and `get_dimension()` methods
4. **OllamaLLMProvider**: Implements `LLMProvider`. No API key needed. Communicates with local Ollama instance. Default provider.
5. **OllamaEmbeddingProvider**: Implements `EmbeddingProvider`. No API key needed. Communicates with local Ollama instance.
6. **OpenRouterLLMProvider**: Implements `LLMProvider`. Uses OpenAI-compatible API with `base_url='https://openrouter.ai/api/v1'`. Requires API key.
7. **OpenAILLMProvider**: Implements `LLMProvider`. Direct OpenAI API. Requires API key. Embedding provider not yet implemented.
8. **AnthropicLLMProvider**: Implements `LLMProvider` only. Direct Anthropic API. Requires API key.
9. **API Key Encryption**: Keys stored in SQLite `providers` table with Fernet encryption. Never exposed in API responses. Only decrypted in-memory at LLM call time.
10. **Model Listing**: Available models are listed per-provider. The frontend model selector uses separate `/api/models/llm` and `/api/models/embed` endpoints (handled by `backend/api/models.py`).

### Non-Functional Requirements

- Provider health checks must complete within 5 seconds
- API key encryption/decryption must add less than 1ms overhead
- Provider resolution must be O(1) lookup
- Failed provider connections must not crash the application
- Keys must never appear in logs, API responses, or error messages

## Key Technical Details

### Provider Base Interfaces

```python
# backend/providers/base.py
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
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts."""

    @abstractmethod
    async def embed_single(self, text: str) -> list[float]:
        """Generate embedding for a single text."""

    @abstractmethod
    def get_model_name(self) -> str:
        """Return the embedding model identifier."""

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the embedding vector dimension."""
```

### Provider Implementations

```python
# backend/providers/ollama.py
class OllamaLLMProvider(LLMProvider): ...       # LLM: generate, generate_stream, health_check, get_model_name
class OllamaEmbeddingProvider(EmbeddingProvider): ...  # Embed: embed, embed_single, get_model_name, get_dimension

# backend/providers/openrouter.py
class OpenRouterLLMProvider(LLMProvider): ...   # LLM only

# backend/providers/openai.py
class OpenAILLMProvider(LLMProvider): ...       # LLM only — no OpenAI embedding provider yet

# backend/providers/anthropic.py
class AnthropicLLMProvider(LLMProvider): ...    # LLM only
```

### Provider Registry

```python
# backend/providers/registry.py
class ProviderRegistry:
    """Manages active LLM provider and embedding provider."""

    def __init__(self) -> None:
        # Stores settings, _ollama_llm (OllamaLLMProvider), _ollama_embed (OllamaEmbeddingProvider)

    async def initialize(self, db: SQLiteDB) -> None:
        """Ensure default Ollama provider is registered in DB."""

    async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
        """Get the currently active LLM provider instance.
        Returns OllamaLLMProvider if active provider is 'ollama' or not set.
        For cloud providers: loads config_json from DB, lazily instantiates the provider."""

    def get_embedding_provider(self) -> EmbeddingProvider:
        """Return the configured embedding provider (OllamaEmbeddingProvider)."""

    async def set_active_provider(self, db: SQLiteDB, name: str, ...) -> None:
        """Update the active provider in the database."""
```

The registry uses an **active-provider model**: one LLM provider is active at a time (stored in SQLite). Switching providers updates the DB record. There is no `get_provider(model_name)` lookup or `list_all_models()` aggregation — model listing is handled separately by `backend/api/models.py`.

### Active LLM Provider Resolution

`get_active_llm()` returns a custom `LLMProvider` instance based on the active provider name stored in SQLite:

```python
# get_active_llm() returns:
# - OllamaLLMProvider       when active provider is "ollama" or not set (default)
# - OpenRouterLLMProvider   when active provider is "openrouter"
# - OpenAILLMProvider       when active provider is "openai"
# - AnthropicLLMProvider    when active provider is "anthropic"
# Falls back to OllamaLLMProvider if unknown provider name
```

For cloud providers, the registry loads `config_json` from SQLite, decrypts the stored API key via `KeyManager`, and lazily instantiates the provider instance.

### API Key Encryption

```python
# backend/providers/key_manager.py
import os
from cryptography.fernet import Fernet

class KeyManager:
    """Fernet symmetric encryption for API keys.
    Loads EMBEDINATOR_FERNET_KEY from environment (must be a valid Fernet key).
    """

    def __init__(self) -> None:
        """Load encryption key from EMBEDINATOR_FERNET_KEY env var.
        Raises ValueError if EMBEDINATOR_FERNET_KEY is not set."""
        raw_key = os.environ.get("EMBEDINATOR_FERNET_KEY")
        if not raw_key:
            raise ValueError("EMBEDINATOR_FERNET_KEY environment variable is not set...")
        self._fernet = Fernet(raw_key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()

    def is_valid_key(self, ciphertext: str) -> bool:
        """Return True if ciphertext can be successfully decrypted."""
        ...
```

The `EMBEDINATOR_FERNET_KEY` must be a pre-generated valid Fernet key (e.g. from `Fernet.generate_key()`). There is no SHA256 derivation from a secret string and no auto-generation on first run — the application raises `ValueError` at startup if the variable is missing.

### Key Storage Flow
1. User enters API key in Frontend Provider Hub
2. Frontend sends `PUT /api/providers/{name}/key {"api_key": "sk-..."}`
3. Backend encrypts key with Fernet using `app.state.key_manager`
4. Encrypted key stored in SQLite `providers` table (`api_key_encrypted` column)
5. At LLM call time: encrypted key loaded from SQLite, decrypted in-memory, used to instantiate provider, garbage collected after use

### Model Info Schema

```python
class ModelInfo(BaseModel):
    name: str
    provider: str               # "ollama", "openrouter", "openai", "anthropic"
    size: Optional[str]         # "7B", "13B", etc.
    quantization: Optional[str] # "Q4_K_M", "Q8_0", etc.
    context_length: Optional[int]
    dims: Optional[int]         # embedding dimensions (embed models only)
```

### Provider API Endpoints

Provider management endpoints are handled by `backend/api/providers.py`. Model listing is handled separately by `backend/api/models.py`.

| Method | Path | Body | Response | Status Codes |
|--------|------|------|----------|-------------|
| `GET` | `/api/providers` | -- | `List[ProviderSchema]` | 200 |
| `PUT` | `/api/providers/{name}/key` | `{"api_key": "sk-..."}` | `{status: "saved"}` | 200, 400 |
| `DELETE` | `/api/providers/{name}/key` | -- | `{status: "deleted"}` | 200, 404 |

Model listing endpoints (handled by `backend/api/models.py`):

| Method | Path | Response |
|--------|------|----------|
| `GET` | `/api/models/llm` | List of available LLM models |
| `GET` | `/api/models/embed` | List of available embedding models |

```python
class ProviderSchema(BaseModel):
    name: str
    is_active: bool
    has_key: bool         # True if encrypted key stored (never returns the key)
    base_url: Optional[str]
    model_count: int      # always 0 — models are fetched via /api/models endpoints
```

### Provider Hardware Requirements (Local Ollama)

| Model Size | RAM Needed | GPU Recommended | Example Models |
|---|---|---|---|
| 7-8B params | 8 GB | Optional (CPU fine) | `llama3.2`, `mistral`, `qwen2.5:7b` |
| 13-14B params | 16 GB | 8 GB VRAM | `llama3.2:13b`, `qwen2.5:14b` |
| 32-34B params | 32 GB | 16 GB VRAM | `qwen2.5:32b`, `deepseek-coder:33b` |
| 70B+ params | 64 GB+ | 24 GB+ VRAM | `llama3.1:70b` |
| Embeddings | 2-4 GB | Not needed | `nomic-embed-text`, `all-minilm` |

## Dependencies

### Spec Dependencies
- **spec-07-storage**: SQLite `providers` table for encrypted key storage
- **spec-08-api**: Provider management endpoints (`/api/providers/*`, `/api/models/*`)
- **spec-09-frontend**: ProviderHub and ModelSelector components consume provider APIs
- **spec-12-errors**: Provider-specific error types (`ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ProviderRateLimitError`, `ModelNotFoundError`) do not exist yet in `backend/errors.py` — they will be added when spec-12 is implemented

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `langchain` | `>=1.2.10` | LLM abstraction, tool binding |
| `langchain-community` | `>=1.2` | Ollama integration |
| `langchain-openai` | `>=1.1.10` | OpenAI / OpenRouter integration |
| `langchain-anthropic` | `>=0.3` | Anthropic integration |
| `cryptography` | `>=44.0` | Fernet encryption for stored API keys |
| `httpx` | `>=0.28` | Async HTTP for provider API calls |

## Acceptance Criteria

1. `ProviderRegistry` returns `OllamaLLMProvider` as the default active provider when no provider is set
2. `ProviderRegistry.get_active_llm()` returns `OpenRouterLLMProvider` with decrypted key when active provider is "openrouter"
3. `ProviderRegistry.get_active_llm()` returns `OpenAILLMProvider` and `AnthropicLLMProvider` similarly for their respective active provider names
4. All providers implement the `LLMProvider` interface with `generate()`, `generate_stream()`, `health_check()`, and `get_model_name()`
5. `OllamaLLMProvider` and `OllamaEmbeddingProvider` are separate classes; `OllamaEmbeddingProvider` additionally implements `EmbeddingProvider` with `embed()`, `embed_single()`, `get_model_name()`, and `get_dimension()`
6. API keys are encrypted before storage and decrypted only in-memory at call time
7. API keys never appear in logs, error messages, or API responses -- only masked characters shown
8. Model listing is available via `GET /api/models/llm` and `GET /api/models/embed` (not embedded in provider responses)
9. Provider health check failures are caught and reported gracefully without crashing
10. The `KeyManager` correctly encrypts/decrypts roundtrip with the Fernet algorithm and exposes `is_valid_key()` for validation
11. Application raises `ValueError` at startup if `EMBEDINATOR_FERNET_KEY` is not set in the environment -- there is no auto-generation fallback

## Architecture Reference

### Provider Registry Flow (Mermaid)

```
UserRequest["Agent graph requests LLM provider"]
  --> GetActive["ProviderRegistry.get_active_llm(db)"]
  --> LoadActive["Load active provider name from SQLite"]
  --> CheckType{"Active provider?"}
    -->|ollama (default)| OllamaInst["Return OllamaLLMProvider instance"]
    -->|openrouter| LoadCreds --> Decrypt --> ORInst["Return OpenRouterLLMProvider(api_key)"]
    -->|openai| LoadCreds --> Decrypt --> OAIInst["Return OpenAILLMProvider(api_key)"]
    -->|anthropic| LoadCreds --> Decrypt --> AnthInst["Return AnthropicLLMProvider(api_key)"]
  --> Return["Provider instance used for generate() / generate_stream()"]
```

### Key Encryption Lifecycle

```
Key Storage: User -> Frontend -> FastAPI -> KeyManager.encrypt() -> SQLite (encrypted)
Key Usage:   SQLite -> KeyManager.decrypt() -> in-memory plaintext -> Provider(api_key=) -> garbage collected
Key Rotation: New key -> encrypt -> UPDATE providers -> old encrypted value overwritten
```
