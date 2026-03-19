# Contract: Provider Architecture — Public Interfaces

**Date**: 2026-03-16
**Feature**: Provider Architecture (spec-10)
**Consumers**: agent nodes, ingestion pipeline, API layer, frontend (via HTTP)

---

## LLMProvider ABC Contract

**File**: `backend/providers/base.py`
**Status**: Stable — no breaking changes in spec-10

All implementations MUST satisfy:

| Method | Signature | Return | Behaviour |
|--------|-----------|--------|-----------|
| `generate` | `(prompt: str, system_prompt: str = "") -> str` | complete response string | Awaitable. Raises on failure. |
| `generate_stream` | `(prompt: str, system_prompt: str = "") -> AsyncIterator[str]` | token stream | Async generator. Raises `ProviderRateLimitError` on 429 (cloud). |
| `health_check` | `() -> bool` | `True` if reachable | Awaitable. Must complete or time out within 5 seconds. Returns `False` on timeout, never raises. |
| `get_model_name` | `() -> str` | model identifier string | Synchronous. Returns the model the provider was instantiated with. |

**Invariants**:
- `generate_stream()` yields non-empty strings only.
- `health_check()` MUST NOT propagate exceptions — catch and return `False`.
- Cloud providers retry once on 5xx/timeout before raising. HTTP 429 raises `ProviderRateLimitError` immediately.

---

## EmbeddingProvider ABC Contract

**File**: `backend/providers/base.py`
**Status**: BREAKING CHANGE (additive) — `model` parameter added to `embed()` and `embed_single()`

All implementations MUST satisfy:

| Method | Signature | Return | Behaviour |
|--------|-----------|--------|-----------|
| `embed` | `(texts: list[str], model: str \| None = None) -> list[list[float]]` | one vector per text | Awaitable. `model=None` uses `self.model`. |
| `embed_single` | `(text: str, model: str \| None = None) -> list[float]` | single embedding vector | Awaitable. `model=None` uses `self.model`. |
| `get_model_name` | `() -> str` | default model name | Synchronous. |
| `get_dimension` | `() -> int` | vector dimension | Synchronous. Returns dimension for `self.model` (not override). |

**Invariants**:
- `embed(texts)` length MUST equal `len(texts)`.
- No vector MUST be empty or all-zeros.
- Existing callers that pass no `model` argument continue to work unchanged (backward-compatible).

---

## ProviderRateLimitError Contract

**File**: `backend/providers/base.py`
**Status**: NEW in spec-10

```python
class ProviderRateLimitError(Exception):
    provider: str   # e.g. "openrouter", "openai", "anthropic"
```

**When raised**: Cloud providers raise this on HTTP 429. It MUST NOT be caught inside the provider
layer — it propagates to the API layer which returns HTTP 429 to the client.

**When NOT raised**: Ollama never raises this.

---

## HTTP API Contracts (unchanged from spec-08)

All paths below are relative to the backend base URL.

### Provider Management

| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| `GET` | `/api/providers` | — | `List[ProviderSchema]` | `has_key: bool` only — plaintext never returned |
| `PUT` | `/api/providers/{name}/key` | `{"api_key": "sk-..."}` | `{"status": "saved"}` | Returns 503 if `KeyManager` not configured |
| `DELETE` | `/api/providers/{name}/key` | — | `{"status": "deleted"}` | Returns 404 if provider not found |
| `GET` | `/api/providers/health` | — | `List[ProviderHealthSchema]` | Added in spec-10 (T019); completes within 5s |

```python
class ProviderHealthSchema(BaseModel):
    provider: str    # "ollama", "openrouter", "openai", "anthropic"
    reachable: bool  # False on timeout, missing key, or connection error
```

**Contract invariants for `/api/providers/health`**:
- All `health_check()` calls MUST run concurrently via `asyncio.gather()`.
- Each individual health check has a 5-second `httpx` timeout — the endpoint never blocks beyond 5s.
- Providers with no API key stored are included in the response with `reachable: False` (no attempt made).
- Returns HTTP 200 even when all providers are unreachable — `reachable: false` is a valid healthy response from the API layer's perspective.

```python
class ProviderSchema(BaseModel):
    name: str          # "ollama", "openrouter", "openai", "anthropic"
    is_active: bool
    has_key: bool      # True if encrypted key stored; plaintext never returned
    base_url: Optional[str]
    model_count: int   # Always 0 — models fetched via /api/models/*
```

### Model Listing (enriched in spec-10)

| Method | Path | Response | Notes |
|--------|------|----------|-------|
| `GET` | `/api/models/llm` | `List[ModelInfo]` | Now includes cloud provider models when key is stored |
| `GET` | `/api/models/embed` | `List[ModelInfo]` | Ollama only (no cloud embedding providers yet) |

```python
class ModelInfo(BaseModel):
    name: str
    provider: str               # "ollama", "openrouter", "openai", "anthropic"
    size: Optional[str]
    quantization: Optional[str]
    context_length: Optional[int]
    dims: Optional[int]         # embed models only
```

**Backward compatibility**: Cloud model entries are additive. Existing Ollama entries are unchanged.
Frontend model selector continues to work without changes.

---

## ProviderRegistry Contract

**File**: `backend/providers/registry.py`
**Status**: EXISTS — one new method added in spec-10

| Method | Signature | Behaviour |
|--------|-----------|-----------|
| `__init__` | `(settings: Settings)` | Creates `_ollama_llm` and `_ollama_embed` instances |
| `initialize` | `(db: SQLiteDB) -> None` | Ensures Ollama default row in DB; awaitable |
| `get_active_llm` | `(db: SQLiteDB) -> LLMProvider` | Returns httpx-based provider for NDJSON streaming, health checks, retry logic; awaitable |
| `get_active_langchain_model` | `(db: SQLiteDB) -> BaseChatModel` | **NEW in spec-10.** Returns LangChain-compatible model for agent graph nodes (`ainvoke`, `with_structured_output`, `bind_tools`); awaitable |
| `get_embedding_provider` | `() -> EmbeddingProvider` | Returns fixed `OllamaEmbeddingProvider`; synchronous |
| `set_active_provider` | `(db, name, config?) -> bool` | Upserts active provider row; awaitable |

**Two LLM access paths (by design)**:
- `get_active_llm()` → `LLMProvider` for chat.py NDJSON streaming, provider health checks, retry logic
- `get_active_langchain_model()` → `BaseChatModel` for agent graph nodes requiring `ainvoke`, `with_structured_output`, `bind_tools`

These serve different consumers with fundamentally different interface needs. Both use the same active-provider resolution logic and decrypt API keys identically.

**`get_active_langchain_model()` return mapping**:
| Active provider | Returns | Package |
|----------------|---------|---------|
| `"ollama"` (or unset) | `ChatOllama(base_url=..., model=...)` | `langchain-ollama` |
| `"openrouter"` | `ChatOpenAI(api_key=key, model=..., base_url="https://openrouter.ai/api/v1")` | `langchain-openai` |
| `"openai"` | `ChatOpenAI(api_key=key, model=...)` | `langchain-openai` |
| `"anthropic"` | `ChatAnthropic(api_key=key, model=...)` | `langchain-anthropic` |
| Unknown | `ChatOllama(...)` (fallback) | `langchain-ollama` |

**Invariants**:
- `get_active_llm()` MUST never raise — falls back to `OllamaLLMProvider` on unknown provider name.
- `get_active_langchain_model()` MUST never raise — falls back to `ChatOllama` on unknown provider name.
- `get_embedding_provider()` always returns the same `OllamaEmbeddingProvider` instance.
- API keys are decrypted in-memory at call time; plaintext goes out of scope immediately after use.
- LangChain imports are lazy (inside the method body) to avoid module-level coupling.
- When adding a new provider, **both** `get_active_llm()` and `get_active_langchain_model()` must be updated.

---

## KeyManager Contract

**File**: `backend/providers/key_manager.py`
**Status**: EXISTS — no changes in spec-10

| Method | Behaviour |
|--------|-----------|
| `encrypt(plaintext: str) -> str` | Returns Fernet ciphertext (URL-safe base64). Raises on empty input. |
| `decrypt(ciphertext: str) -> str` | Returns plaintext. Raises `cryptography.fernet.InvalidToken` on bad ciphertext. |
| `is_valid_key(ciphertext: str) -> bool` | Returns `True` if decryption succeeds without raising. |

**Contract invariant**: If `EMBEDINATOR_FERNET_KEY` is not set in environment, `KeyManager.__init__()`
raises `ValueError`. `main.py` sets `app.state.key_manager = None` and key endpoints return HTTP 503.
