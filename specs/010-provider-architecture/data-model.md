# Data Model: Provider Architecture

**Phase**: 1 — Design
**Date**: 2026-03-16
**Feature**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

---

## Entity Overview

Spec-10 extends three existing entities and introduces one simple exception class. No new tables
are added to SQLite. The `query_traces` table gains one new nullable column.

---

## 1. LLMProvider (ABC, extended)

**File**: `backend/providers/base.py`
**Status**: EXISTS — interface unchanged

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: str = "") -> str: ...
    @abstractmethod
    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]: ...
    @abstractmethod
    async def health_check(self) -> bool: ...
    @abstractmethod
    def get_model_name(self) -> str: ...
```

**Spec-10 changes**: None. The interface is stable.

---

## 2. EmbeddingProvider (ABC, extended)

**File**: `backend/providers/base.py`
**Status**: EXISTS — add optional `model` parameter to `embed()` and `embed_single()`

```python
class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...
    @abstractmethod
    async def embed_single(self, text: str, model: str | None = None) -> list[float]: ...
    @abstractmethod
    def get_model_name(self) -> str: ...
    @abstractmethod
    def get_dimension(self) -> int: ...
```

**Spec-10 change**: `model: str | None = None` added to `embed()` and `embed_single()`.

**Validation rules**:
- `model` defaults to `None`; when `None`, each implementation uses its own `self.model`.
- All existing callers pass no `model` argument — they continue to work unchanged.
- `OllamaEmbeddingProvider` uses `model or self.model` in its API payload.

**State transitions**: None. Stateless method calls.

---

## 3. OllamaEmbeddingProvider (concrete, extended)

**File**: `backend/providers/ollama.py`
**Status**: EXISTS — update `embed()` and `embed_single()` to honour optional `model` param

```python
class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self, base_url: str, model: str): ...

    async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        return [await self.embed_single(t, model=model) for t in texts]

    async def embed_single(self, text: str, model: str | None = None) -> list[float]:
        effective_model = model or self.model
        # POST {base_url}/api/embeddings {"model": effective_model, "prompt": text}
        ...
```

**Validation rules**:
- `effective_model` must be a non-empty string.
- Response from Ollama: `{"embedding": [float, ...]}` — validate list is non-empty.

---

## 4. Cloud LLMProviders (extended: retry + 429)

**Files**: `backend/providers/openrouter.py`, `backend/providers/openai.py`, `backend/providers/anthropic.py`
**Status**: EXISTS — add retry-once and `ProviderRateLimitError` handling

Each cloud provider adds a `_call_with_retry()` helper (or inline retry loop) with these rules:

| HTTP Status | Action |
|-------------|--------|
| 429 | Raise `ProviderRateLimitError` immediately. No retry, no Ollama fallback. |
| 5xx | Retry once. On second 5xx, re-raise `httpx.HTTPStatusError`. |
| Timeout | Retry once. On second timeout, re-raise `httpx.TimeoutException`. |
| 4xx (not 429) | Re-raise immediately without retry. |

**Validation rules**:
- Retry is exactly once (`attempt in range(2)`).
- `ProviderRateLimitError` carries `provider` name for error messages.
- `OllamaLLMProvider` is EXCLUDED from this change.

---

## 5. ProviderRateLimitError (new exception)

**File**: `backend/providers/base.py` (until spec-12 formalizes error hierarchy)
**Status**: NEW — simple exception class

```python
class ProviderRateLimitError(Exception):
    """Raised when a cloud provider returns HTTP 429 (rate limit exceeded)."""
    def __init__(self, provider: str, message: str = "") -> None:
        self.provider = provider
        super().__init__(message or f"Rate limit exceeded for provider: {provider}")
```

**Validation rules**:
- `provider` field MUST be set (e.g., `"openrouter"`, `"openai"`, `"anthropic"`).
- The API layer (`chat.py` or FastAPI exception handler) catches this and returns HTTP 429 to client.

---

## 6. query_traces Table (extended)

**File**: `backend/storage/sqlite_db.py` + SQLite `data/embedinator.db`
**Status**: EXISTS — add `provider_name TEXT` column

### New column

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `provider_name` | TEXT | YES | NULL | Registry key of the LLM provider that handled the request: `"ollama"`, `"openrouter"`, `"openai"`, `"anthropic"` |

### Migration

Applied in `SQLiteDB.initialize()` via:
```sql
ALTER TABLE query_traces ADD COLUMN provider_name TEXT
```
Guarded by catching `aiosqlite.OperationalError` (SQLite error: "duplicate column name").

### Updated create_query_trace() signature

```python
async def create_query_trace(
    self,
    id: str,
    session_id: str,
    query: str,
    collections_searched: list[str],
    chunks_retrieved_json: str,
    latency_ms: int,
    llm_model: str | None = None,
    embed_model: str | None = None,
    confidence_score: int | None = None,
    sub_questions_json: str | None = None,
    reasoning_steps_json: str | None = None,
    strategy_switches_json: str | None = None,
    meta_reasoning_triggered: bool = False,
    provider_name: str | None = None,   # NEW
) -> None: ...
```

**Validation rules**:
- `provider_name` is nullable — traces from before spec-10 have `NULL` (not an error).
- Value must match one of: `"ollama"`, `"openrouter"`, `"openai"`, `"anthropic"` (not enforced by DB,
  but enforced by the registry resolution logic).

---

## 7. chat.py — Provider Name Propagation

**File**: `backend/api/chat.py`
**Status**: EXISTS — extract active provider name and pass to `create_query_trace`

```python
# After resolving provider:
provider = await app.state.registry.get_active_llm(db)
provider_name = _resolve_provider_name(app.state.registry, db)  # or extract from active row

# When writing trace:
await db.create_query_trace(
    ...,
    provider_name=provider_name,
)
```

**Validation rules**:
- `provider_name` is the registry key (e.g., `"ollama"`), NOT the model name string.
- If `app.state.registry` is None (startup failure), pass `provider_name=None`.

---

## 8. BatchEmbedder (extended)

**File**: `backend/ingestion/embedder.py`
**Status**: EXISTS — replace direct `OllamaEmbeddingProvider(...)` with registry injection

```python
class BatchEmbedder:
    def __init__(self, embedding_provider: EmbeddingProvider, ...): ...
    # Previously: OllamaEmbeddingProvider(base_url=..., model=...) instantiated internally
    # Now: provider passed in from caller via registry.get_embedding_provider()
```

**Validation rules**:
- Constructor accepts `EmbeddingProvider` (the ABC), not a concrete class — easier to mock in tests.
- Injection point: the ingestion pipeline entry in `backend/api/ingest.py` or wherever
  `BatchEmbedder` is constructed.

---

## 9. models.py — Enriched Model Listing

**File**: `backend/api/models.py`
**Status**: EXISTS — add cloud provider models when API key is stored

### ModelInfo schema (unchanged)

```python
class ModelInfo(BaseModel):
    name: str
    provider: str               # "ollama", "openrouter", "openai", "anthropic"
    size: Optional[str]         # "7B", "13B", etc.
    quantization: Optional[str] # "Q4_K_M", etc.
    context_length: Optional[int]
    dims: Optional[int]         # embedding dimensions (embed models only)
```

### Enrichment logic

For `GET /api/models/llm`:
1. Fetch Ollama LLM models via `_fetch_ollama_models()` (existing).
2. For each cloud provider row in DB: if `api_key_encrypted` is not null/empty, append
   `ModelInfo(name=config["model"], provider=provider_name)` if a model is configured.

For `GET /api/models/embed`:
- No cloud embedding providers yet. Return Ollama embedding models only (no change).

**Validation rules**:
- Cloud model entries are additive — existing Ollama entries are not removed.
- `model_count` in `GET /api/providers` response remains `0` (models are only in `/api/models/*`).

---

## Relationship Summary

```
ProviderRegistry
  ├── get_active_llm(db) → LLMProvider (one of: OllamaLLMProvider, OpenRouterLLMProvider,
  │                                               OpenAILLMProvider, AnthropicLLMProvider)
  └── get_embedding_provider() → EmbeddingProvider (always OllamaEmbeddingProvider)

LLMProvider ──(interface)── generate(), generate_stream(), health_check(), get_model_name()
                             Cloud providers: + _call_with_retry() helper

EmbeddingProvider ──(interface)── embed(texts, model?), embed_single(text, model?),
                                   get_model_name(), get_dimension()

KeyManager
  ├── encrypt(plaintext) → ciphertext (stored in providers.api_key_encrypted)
  └── decrypt(ciphertext) → plaintext (in-memory only, at instantiation time)

query_traces (SQLite)
  └── provider_name TEXT — set by chat.py after resolving active LLM provider

BatchEmbedder
  └── embedding_provider: EmbeddingProvider — injected from registry.get_embedding_provider()
```
