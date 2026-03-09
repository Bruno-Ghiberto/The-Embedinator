# Spec 10: Provider Architecture -- Implementation Plan Context

## Component Overview

The Provider Architecture provides a unified abstraction over multiple LLM and embedding providers (Ollama, OpenRouter, OpenAI, Anthropic). It enables users to switch between local inference (Ollama) and cloud inference (OpenRouter, OpenAI, Anthropic) seamlessly. The `ProviderRegistry` resolves model names to the correct provider at runtime, handles API key encryption/decryption, and instantiates LangChain-compatible chat and embedding models for use by the agent graphs.

## Technical Approach

### Design Patterns
- **Abstract Factory**: `LLMProvider` and `EmbeddingProvider` ABCs define the contract; concrete providers implement it
- **Registry Pattern**: `ProviderRegistry` maintains a lookup table mapping model name prefixes/patterns to providers
- **Strategy Pattern**: Provider selection is determined at runtime based on model name and available credentials
- **Dependency Injection**: Providers are injected into agent nodes and tools via the registry

### LangChain Integration
All providers instantiate LangChain model objects (`ChatOllama`, `ChatOpenAI`, `ChatAnthropic`) that implement `BaseChatModel`. This means the agent graph nodes receive a uniform interface regardless of which provider is backing the model. Streaming is done via LangChain's `astream()` method.

### Encryption Approach
API keys use Fernet symmetric encryption (`cryptography` library). The encryption key is derived from a secret in `.env` using SHA-256 + base64 encoding. Keys are only decrypted in-memory at the instant they are needed, then garbage collected.

## File Structure

```
backend/
  providers/
    base.py             # LLMProvider ABC, EmbeddingProvider ABC
    registry.py         # ProviderRegistry: model name -> provider resolution
    ollama.py           # OllamaProvider (default, no key needed)
    openrouter.py       # OpenRouterProvider (200+ models, one key)
    openai.py           # OpenAIProvider (direct)
    anthropic.py        # AnthropicProvider (direct)
    key_manager.py      # Fernet encryption/decryption for API keys
```

## Implementation Steps

### Step 1: Base Interfaces
1. Create `backend/providers/base.py` with `LLMProvider` and `EmbeddingProvider` ABCs
2. Define abstract methods: `chat()` (async generator yielding tokens), `list_models()`, `health_check()`, `embed()`, `get_dimensions()`
3. Define `ModelInfo` Pydantic model

### Step 2: Key Manager
1. Create `backend/providers/key_manager.py`
2. Implement `get_fernet_key(secret)` function deriving a Fernet-compatible key from the `.env` secret via SHA-256
3. Implement `KeyManager` class with `encrypt(plaintext) -> str` and `decrypt(ciphertext) -> str` methods
4. Add secret auto-generation logic: if `API_KEY_ENCRYPTION_SECRET` is missing from `.env`, generate a random 32-byte secret, write it to `.env`, and log a warning

### Step 3: Ollama Provider
1. Create `backend/providers/ollama.py` implementing both `LLMProvider` and `EmbeddingProvider`
2. `chat()`: Use `ChatOllama` from `langchain-community` with `astream()` for token streaming
3. `list_models()`: Call Ollama API `GET /api/tags` to list locally available models
4. `health_check()`: Call Ollama API `GET /api/tags` and verify response
5. `embed()`: Call Ollama API `POST /api/embeddings` for batch embedding
6. `get_dimensions()`: Embed a single test string and return vector length

### Step 4: OpenRouter Provider
1. Create `backend/providers/openrouter.py` implementing `LLMProvider`
2. `chat()`: Use `ChatOpenAI` with `base_url='https://openrouter.ai/api/v1'` and decrypted API key
3. `list_models()`: Call OpenRouter API `GET /api/v1/models` to list available models
4. `health_check()`: Verify OpenRouter API reachability

### Step 5: OpenAI Provider
1. Create `backend/providers/openai.py` implementing both `LLMProvider` and `EmbeddingProvider`
2. `chat()`: Use `ChatOpenAI` with direct OpenAI API key
3. `embed()`: Use `OpenAIEmbeddings` from `langchain-openai`
4. `list_models()`: Call OpenAI API to list available models

### Step 6: Anthropic Provider
1. Create `backend/providers/anthropic.py` implementing `LLMProvider`
2. `chat()`: Use `ChatAnthropic` with decrypted API key
3. `list_models()`: Return hardcoded list of known Anthropic models (Claude family)
4. `health_check()`: Verify Anthropic API reachability

### Step 7: Provider Registry
1. Create `backend/providers/registry.py` with `ProviderRegistry` class
2. Initialize with `SQLiteDB` (for key storage) and `KeyManager` (for decryption)
3. Implement `get_provider(model_name)`: Resolve model name to provider instance. Use model name prefix/pattern matching (e.g., `llama*` -> Ollama, `gpt-*` -> OpenAI, `claude-*` -> Anthropic, models containing `/` -> OpenRouter)
4. Implement `get_embedding_provider(model_name)`: Similar resolution for embedding providers
5. Implement `list_all_models()`: Aggregate models from all configured (active) providers

### Step 8: Testing
1. Unit tests for `KeyManager`: roundtrip encrypt/decrypt, invalid key handling
2. Unit tests for `ProviderRegistry`: model name resolution, provider selection
3. Integration tests for `OllamaProvider`: model listing, health check (requires Ollama running)
4. Mock tests for cloud providers: verify correct LangChain model instantiation

## Integration Points

- **Agent Graphs** (`spec-02`, `spec-03`, `spec-04`): Agent nodes receive `BaseChatModel` instances via `ProviderRegistry.get_provider()`. The registry is injected as a dependency.
- **Ingestion Pipeline** (`spec-06`): The `BatchEmbedder` uses `ProviderRegistry.get_embedding_provider()` to get the correct embedding provider.
- **Storage** (`spec-07`): The `providers` table in SQLite stores provider records with `name` and `api_key_encrypted` columns. `KeyManager` reads/writes encrypted keys.
- **API Routes** (`spec-08`): Provider management endpoints (`GET /providers`, `PUT /providers/{name}/key`, etc.) call registry and key manager methods.
- **Frontend** (`spec-09`): The ProviderHub component and ModelSelector consume provider API endpoints to display available providers and models.
- **Error Handling** (`spec-12`): Provider errors (`ProviderNotConfiguredError`, `ProviderAuthError`, `ProviderRateLimitError`, `ModelNotFoundError`) are defined in the error hierarchy.

## Key Code Patterns

### Provider Resolution Pattern
```python
class ProviderRegistry:
    def get_provider(self, model_name: str) -> LLMProvider:
        provider_type = self._resolve_provider_type(model_name)
        if provider_type == "ollama":
            return self._ollama_provider
        elif provider_type in ("openrouter", "openai", "anthropic"):
            key = self._load_and_decrypt_key(provider_type)
            return self._create_cloud_provider(provider_type, key)
        raise ModelNotFoundError(f"No provider found for model: {model_name}")
```

### LangChain Model Instantiation Pattern
```python
# Ollama (no key needed)
ChatOllama(base_url=self.ollama_url, model=model_name)

# OpenRouter (OpenAI-compatible)
ChatOpenAI(base_url="https://openrouter.ai/api/v1", api_key=decrypted_key, model=model_name)

# OpenAI (direct)
ChatOpenAI(api_key=decrypted_key, model=model_name)

# Anthropic (direct)
ChatAnthropic(api_key=decrypted_key, model=model_name)
```

### Key Security Pattern
```python
# Keys are NEVER:
# - Logged (use structlog filter)
# - Returned in API responses (ProviderSchema has has_key: bool, not the key itself)
# - Stored in plaintext (Fernet encryption in SQLite)
# - Held in memory longer than needed (decrypt -> use -> garbage collect)
```

## Phase Assignment

- **Phase 1 (MVP)**: Ollama as default provider for LLM and embeddings. OpenRouter support with encrypted API key storage. `ProviderRegistry` with model resolution. `KeyManager` with Fernet encryption. Provider Hub UI. `providers` SQLite table.
- **Phase 3**: Additional providers: OpenAI direct, Anthropic direct. These supplement OpenRouter (which already provides access to these models).
