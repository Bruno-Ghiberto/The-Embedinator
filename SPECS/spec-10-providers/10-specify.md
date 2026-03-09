# Spec 10: Provider Architecture -- Feature Specification Context

## Feature Description

The Provider Architecture is a multi-provider abstraction layer that allows The Embedinator to use LLMs and embedding models from multiple sources: Ollama (local, default), OpenRouter (200+ cloud models with one API key), OpenAI (direct), and Anthropic (direct). The system uses a `ProviderRegistry` that resolves a model name to the correct provider at runtime, loads encrypted API credentials from SQLite, and instantiates the appropriate LangChain chat model or embedding client.

The architecture supports both LLM providers (for chat completion) and embedding providers (for vector generation), with Ollama uniquely implementing both interfaces. API keys are encrypted at rest using Fernet symmetric encryption with a machine-local secret derived from a `.env` variable.

## Requirements

### Functional Requirements

1. **Provider Registry**: A `ProviderRegistry` class that maps model names to providers and resolves the correct provider + credentials at runtime
2. **LLM Provider Interface**: Abstract base class `LLMProvider` with `chat()` (streaming), `list_models()`, and `health_check()` methods
3. **Embedding Provider Interface**: Abstract base class `EmbeddingProvider` with `embed()` (batch) and `get_dimensions()` methods
4. **OllamaProvider**: Implements both `LLMProvider` and `EmbeddingProvider`. No API key needed. Communicates with local Ollama instance. Default provider.
5. **OpenRouterProvider**: Implements `LLMProvider`. Uses OpenAI-compatible API with `base_url='https://openrouter.ai/api/v1'`. Requires API key.
6. **OpenAIProvider**: Implements both `LLMProvider` and `EmbeddingProvider`. Direct OpenAI API. Requires API key.
7. **AnthropicProvider**: Implements `LLMProvider` only. Direct Anthropic API. Requires API key.
8. **API Key Encryption**: Keys stored in SQLite `providers` table with Fernet encryption. Never exposed in API responses. Only decrypted in-memory at LLM call time.
9. **Model Listing**: Each provider can list its available models. The registry aggregates all models across providers for the frontend model selector dropdowns.
10. **LangChain Integration**: Providers instantiate LangChain chat models (`ChatOllama`, `ChatOpenAI`, `ChatAnthropic`) that implement the `BaseChatModel` interface for agent graph compatibility.

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
    @abstractmethod
    async def chat(self, messages: List[BaseMessage], model: str, **kwargs) -> AsyncIterator[str]:
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

### Provider Implementations

```python
# backend/providers/ollama.py
class OllamaProvider(LLMProvider, EmbeddingProvider): ...

# backend/providers/openrouter.py
class OpenRouterProvider(LLMProvider): ...

# backend/providers/openai.py
class OpenAIProvider(LLMProvider, EmbeddingProvider): ...

# backend/providers/anthropic.py
class AnthropicProvider(LLMProvider): ...
```

### Provider Registry

```python
# backend/providers/registry.py
class ProviderRegistry:
    """Resolves model name -> provider + credentials at runtime."""
    def get_provider(self, model_name: str) -> LLMProvider: ...
    def get_embedding_provider(self, model_name: str) -> EmbeddingProvider: ...
    def list_all_models(self) -> List[ModelInfo]: ...
```

### LangChain Model Instantiation

The registry creates LangChain-compatible model instances:
- **Ollama**: `ChatOllama(base_url=ollama_url, model=model_name)`
- **OpenRouter**: `ChatOpenAI(base_url='https://openrouter.ai/api/v1', api_key=decrypted_key, model=model_name)`
- **OpenAI**: `ChatOpenAI(api_key=decrypted_key, model=model_name)`
- **Anthropic**: `ChatAnthropic(api_key=decrypted_key, model=model_name)`

### API Key Encryption

```python
# backend/providers/key_manager.py
import hashlib
import base64
from cryptography.fernet import Fernet

def get_fernet_key(secret: str) -> bytes:
    """Derive a Fernet key from the .env secret."""
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

class KeyManager:
    def __init__(self, secret: str):
        self.fernet = Fernet(get_fernet_key(secret))

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

### Key Storage Flow
1. User enters API key in Frontend Provider Hub
2. Frontend sends `PUT /api/providers/{name}/key {"api_key": "sk-..."}`
3. Backend encrypts key with Fernet using `.env`-derived secret
4. Encrypted key stored in SQLite `providers` table (`api_key_encrypted` column)
5. At LLM call time: encrypted key loaded from SQLite, decrypted in-memory, used to instantiate model, garbage collected after use

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

| Method | Path | Body | Response | Status Codes |
|--------|------|------|----------|-------------|
| `GET` | `/providers` | -- | `List[ProviderSchema]` | 200 |
| `PUT` | `/providers/{name}/key` | `{"api_key": "sk-..."}` | `{status: "saved"}` | 200, 400 |
| `DELETE` | `/providers/{name}/key` | -- | `{status: "deleted"}` | 200, 404 |
| `GET` | `/providers/{name}/models` | -- | `List[ModelInfo]` | 200, 503 |

```python
class ProviderSchema(BaseModel):
    name: str
    is_active: bool
    has_key: bool         # True if encrypted key stored (never returns the key)
    base_url: Optional[str]
    model_count: int      # number of available models
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
- **spec-08-api**: Provider management endpoints (`/providers/*`, `/models/*`)
- **spec-09-frontend**: ProviderHub and ModelSelector components consume provider APIs
- **spec-12-errors**: `ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ProviderRateLimitError`, `ModelNotFoundError`

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `langchain` | `>=1.2.10` | LLM abstraction, tool binding |
| `langchain-community` | `>=1.2` | Ollama integration (`ChatOllama`) |
| `langchain-openai` | `>=1.1.10` | OpenAI / OpenRouter integration (`ChatOpenAI`) |
| `langchain-anthropic` | `>=0.3` | Anthropic integration (`ChatAnthropic`) |
| `cryptography` | `>=44.0` | Fernet encryption for stored API keys |
| `httpx` | `>=0.28` | Async HTTP for provider API calls |

## Acceptance Criteria

1. `ProviderRegistry` resolves any Ollama model name to `OllamaProvider` without requiring an API key
2. `ProviderRegistry` resolves OpenRouter model names to `OpenRouterProvider` with encrypted key decryption
3. `ProviderRegistry` resolves OpenAI and Anthropic model names similarly
4. All providers implement the `LLMProvider` interface with streaming `chat()`, `list_models()`, and `health_check()`
5. `OllamaProvider` and `OpenAIProvider` additionally implement the `EmbeddingProvider` interface
6. API keys are encrypted before storage and decrypted only in-memory at call time
7. API keys never appear in logs, error messages, or API responses -- only masked characters shown
8. `list_all_models()` aggregates models from all configured providers
9. Provider health check failures are caught and reported gracefully without crashing
10. The `KeyManager` correctly encrypts/decrypts roundtrip with the Fernet algorithm
11. Secret auto-generation occurs on first run if `API_KEY_ENCRYPTION_SECRET` is not set

## Architecture Reference

### Provider Registry Flow (Mermaid)

```
UserSelect["User selects model in ModelSelector dropdown"]
  --> GetProvider["ProviderRegistry.get_provider(model_name)"]
  --> CheckType{"Provider type?"}
    -->|ollama| OllamaChat["ChatOllama(base_url, model)"]
    -->|openrouter| LoadCreds --> Decrypt --> ORChat["ChatOpenAI(base_url=openrouter, api_key, model)"]
    -->|openai| LoadCreds --> Decrypt --> OAIChat["ChatOpenAI(api_key, model)"]
    -->|anthropic| LoadCreds --> Decrypt --> AnthChat["ChatAnthropic(api_key, model)"]
  --> Return["Return ChatModel to agent"]
```

### Key Encryption Lifecycle

```
Key Storage: User -> Frontend -> FastAPI -> KeyManager.encrypt() -> SQLite (encrypted)
Key Usage:   SQLite -> KeyManager.decrypt() -> in-memory plaintext -> ChatModel(api_key=) -> garbage collected
Key Rotation: New key -> encrypt -> UPDATE providers -> old encrypted value overwritten
```
