# backend/providers/

Pluggable LLM provider system with encrypted API key storage.

## Provider Architecture

The system supports multiple LLM providers through a registry pattern.
Only one provider is active at a time, but keys for all providers can be
stored simultaneously.

```
ProviderRegistry
  |-- OllamaProvider (default, no API key needed)
  |-- OpenAIProvider
  |-- AnthropicProvider
  +-- OpenRouterProvider
```

## Key Components

| File             | Purpose                                              |
|------------------|------------------------------------------------------|
| `registry.py`    | `ProviderRegistry` -- provider discovery, activation, and LangChain model resolution |
| `base.py`        | Abstract `BaseProvider` interface and `ProviderRateLimitError` |
| `ollama.py`      | Ollama adapter (local inference, default provider)   |
| `openai.py`      | OpenAI adapter (GPT models)                          |
| `anthropic.py`   | Anthropic adapter (Claude models)                    |
| `openrouter.py`  | OpenRouter adapter (multi-model gateway)             |
| `key_manager.py` | `KeyManager` -- Fernet-encrypted API key storage/retrieval |

## How It Works

1. On startup, `ProviderRegistry.initialize(db)` loads provider records from
   SQLite and registers all known providers.
2. The active provider is stored in the `providers` table with
   `is_active=true`.
3. When a chat request arrives, `registry.get_active_langchain_model(db)`
   returns a LangChain chat model instance for the active provider.
4. Cloud provider API keys are encrypted with Fernet before storage.
   The encryption key is set via `EMBEDINATOR_FERNET_KEY`.

## Adding a New Provider

1. Create a new file in `providers/` (e.g., `my_provider.py`)
2. Implement the `BaseProvider` interface (model listing, health check,
   LangChain model factory)
3. Register the provider in `registry.py`

## Encrypted Key Storage

Cloud provider API keys are encrypted at rest using Fernet symmetric
encryption (via the `cryptography` library). The `KeyManager` class handles
encryption and decryption. To enable cloud providers:

```bash
# Generate a key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Set in .env
EMBEDINATOR_FERNET_KEY=<generated-key>
```

Without this key, cloud providers are gracefully disabled and only Ollama
is available.
