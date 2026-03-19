# Spec 10: Provider Architecture — Implementation Plan Context

## Component Overview

The Provider Architecture provides a unified abstraction over multiple LLM and embedding providers
(Ollama, OpenRouter, OpenAI, Anthropic). It enables users to switch between local inference (Ollama)
and cloud inference (OpenRouter, OpenAI, Anthropic) at runtime via an active-provider model stored in
SQLite. The `ProviderRegistry` reads the currently active provider from the database, lazy-instantiates
the correct concrete class, handles API key decryption via `KeyManager`, and exposes the result through
two access paths: `get_active_llm(db)` for LLM inference and `get_embedding_provider()` for embeddings.

All providers use `httpx` directly — there is no LangChain dependency in this layer. Agent graph nodes
receive token streams as `AsyncIterator[str]` and plain string completions via the `LLMProvider` ABC.

---

## What Already Exists (from spec-08 scaffolding)

The following modules were scaffolded during spec-08 and are already in the codebase. Spec-10 does NOT
recreate them — it extends them.

**`backend/providers/base.py`**

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

class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    async def embed_single(self, text: str) -> list[float]: ...
    @abstractmethod
    def get_model_name(self) -> str: ...
    @abstractmethod
    def get_dimension(self) -> int: ...
```

**`backend/providers/ollama.py`**
- `OllamaLLMProvider(base_url, model)` — httpx POST `/api/generate`, SSE JSON lines (`"response"` field)
- `OllamaEmbeddingProvider(base_url, model)` — httpx POST Ollama embed API; `embed()` loops over texts
  calling `embed_single()` for each

**`backend/providers/openrouter.py`**
- `OpenRouterLLMProvider(api_key, model)` — httpx POST `/chat/completions`, OpenAI SSE format
  (`data: ` prefix, `data: [DONE]` terminator, `choices[0].delta.content` extraction)

**`backend/providers/openai.py`**
- `OpenAILLMProvider(api_key, model)` — same httpx SSE pattern, `base_url = "https://api.openai.com/v1"`

**`backend/providers/anthropic.py`**
- `AnthropicLLMProvider(api_key, model)` — `base_url = "https://api.anthropic.com/v1"`,
  default `model = "claude-sonnet-4-20250514"`

**`backend/providers/registry.py`**
```python
class ProviderRegistry:
    def __init__(self, settings):  # takes Settings, NOT SQLiteDB
        # stores settings; holds _ollama_llm and _ollama_embed instances
    async def initialize(self, db: SQLiteDB) -> None:
        # ensures Ollama default row exists in DB providers table
    async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
        # reads active provider row, json.loads(active["config_json"]),
        # config.get("model", ""), lazy-instantiates correct class,
        # falls back to OllamaLLMProvider on unknown provider name
    def get_embedding_provider(self) -> EmbeddingProvider:
        # returns fixed OllamaEmbeddingProvider
    async def set_active_provider(self, db: SQLiteDB, name: str, config: dict | None = None) -> bool:
        # upserts provider row with config_json = json.dumps(config or {})
```

**`backend/providers/key_manager.py`**
```python
class KeyManager:
    def __init__(self) -> None:
        raw_key = os.environ.get("EMBEDINATOR_FERNET_KEY")
        if not raw_key:
            raise ValueError("EMBEDINATOR_FERNET_KEY environment variable is not set...")
        self._fernet = Fernet(raw_key.encode())
    def encrypt(self, plaintext: str) -> str: ...
    def decrypt(self, ciphertext: str) -> str: ...
    def is_valid_key(self, ciphertext: str) -> bool: ...
```
- Uses `EMBEDINATOR_FERNET_KEY` env var directly (must be a pre-generated valid Fernet key)
- No SHA-256 derivation, no `get_fernet_key()` function, no auto-generation
- Raises `ValueError` on missing env var; `main.py` catches this and sets `app.state.key_manager = None`

**`backend/main.py` lifespan (relevant excerpt)**
```python
registry = ProviderRegistry(settings)
await registry.initialize(db)
app.state.registry = registry
try:
    key_manager = KeyManager()
    app.state.key_manager = key_manager
except ValueError:
    app.state.key_manager = None  # graceful degradation
```

**API routes already live (spec-08)**
- `GET /api/providers` — list providers
- `PUT /api/providers/{name}/key` — save encrypted key
- `DELETE /api/providers/{name}/key` — delete key
- `GET /api/models/llm` — list LLM models
- `GET /api/models/embed` — list embedding models

**Existing tests**
- `tests/unit/test_providers.py` — 3 tests (abstract class contract only)
- `tests/unit/test_providers_router.py` — API layer tests for `/api/providers` endpoints

---

## What Spec-10 Adds

The following seven items are NOT yet implemented. Each is a distinct implementation task.

**1. Model-agnostic embedding signature** (FR-006)

Update `EmbeddingProvider.embed()` and `embed_single()` in `base.py` to accept an optional model
override parameter: `embed(texts: list[str], model: str | None = None)` and
`embed_single(text: str, model: str | None = None)`. Update `OllamaEmbeddingProvider` to use the
override when provided, falling back to `self.model`. All existing callers pass no `model` argument
and must continue to work unchanged.

**2. Retry logic on transient failures** (FR-017)

Each cloud provider's `generate_stream()` must retry exactly once on `httpx.HTTPStatusError` with a
5xx status code or `httpx.TimeoutException`. After one retry attempt the original exception is
re-raised. Ollama does not need this — its circuit breaker (spec-05) already handles retries.
Implementation: wrap the httpx call in a helper that catches the two error types, sleeps briefly,
and retries once.

**3. Rate-limit surfacing** (FR-018)

On HTTP 429 responses from any cloud provider, raise a distinct `ProviderRateLimitError` immediately
without retrying or falling back to Ollama. This lets the API layer return an appropriate 429 to the
frontend instead of silently degrading.

**4. query_traces schema migration** (FR-019)

Add `provider_name TEXT` column to the `query_traces` table via SQLite `ALTER TABLE ... ADD COLUMN`.
Update `SQLiteDB.create_query_trace()` to accept and persist `provider_name: str | None = None`.
Update `backend/api/chat.py` to resolve the active provider name from `app.state.registry` and pass
it to `create_query_trace`. The `query_traces` table currently has no `provider_name` column.

**5. Agent node wiring**

Update the LangGraph agent nodes in `backend/agent/nodes.py` to call
`ProviderRegistry.get_active_llm(db)` for LLM inference instead of their current hard-coded
ChatOllama configuration. This requires impact analysis via GitNexus before any edits. The
`ResearchGraph` and `ConversationGraph` do not currently use `ProviderRegistry` at all.

**6. BatchEmbedder wiring**

Update `backend/ingestion/embedder.py` to obtain its `EmbeddingProvider` via
`ProviderRegistry.get_embedding_provider()` instead of instantiating `OllamaEmbeddingProvider`
directly. The registry instance is available on `app.state.registry`.

**7. Model listing enrichment**

Update `backend/api/models.py` — specifically `_fetch_ollama_models()` or its caller — to also
include models from configured cloud providers when their API keys are present in the DB. This
populates the model selectors in the frontend ProviderHub component.

---

## Technical Approach

### Active-Provider Model

Provider selection is NOT based on model-name prefix matching. The active provider is a single row
in the SQLite `providers` table with `is_active = 1`. `ProviderRegistry.get_active_llm(db)` reads
that row, loads `config_json` to extract the `model` field, and instantiates the matching class.
Switching providers means updating which row has `is_active = 1` (via `set_active_provider`).

### httpx Streaming Pattern

All providers use `httpx.AsyncClient` directly. There is no LangChain dependency.

```python
# Ollama SSE — field name is "response"
async with httpx.AsyncClient() as client:
    async with client.stream("POST", url, json=payload, timeout=60.0) as resp:
        async for line in resp.aiter_lines():
            data = json.loads(line)
            if token := data.get("response"):
                yield token
            if data.get("done"):
                break

# OpenAI-compatible SSE (OpenRouter, OpenAI) — field name is choices[0].delta.content
async with httpx.AsyncClient() as client:
    async with client.stream("POST", url, json=payload, headers=headers, timeout=60.0) as resp:
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            payload_str = line[len("data: "):]
            if payload_str == "[DONE]":
                break
            data = json.loads(payload_str)
            if token := data["choices"][0]["delta"].get("content"):
                yield token
```

### Retry-Once Pattern (FR-017, cloud providers only)

```python
async def _call_with_retry(self, make_request_fn):
    for attempt in range(2):  # 0 = first try, 1 = one retry
        try:
            return await make_request_fn()
        except (httpx.HTTPStatusError, httpx.TimeoutException) as exc:
            if isinstance(exc, httpx.HTTPStatusError):
                if exc.response.status_code == 429:
                    raise ProviderRateLimitError(...) from exc  # FR-018: never retry 429
                if exc.response.status_code < 500:
                    raise  # 4xx other than 429: do not retry
            if attempt == 1:
                raise  # exhausted one retry
```

### Fernet Key Encryption

`KeyManager` reads `EMBEDINATOR_FERNET_KEY` from the environment. The value must be a valid
pre-generated Fernet key (URL-safe base64, 32 bytes). There is no SHA-256 derivation, no
auto-generation, and no fallback. Missing key raises `ValueError`; `main.py` handles this by
setting `app.state.key_manager = None` (graceful degradation — provider key endpoints return 503).

### Schema Migration

The `query_traces` column addition uses `ALTER TABLE ... ADD COLUMN`, which is safe in SQLite WAL
mode and does not require a copy-create-drop cycle. The migration runs at application startup in
`SQLiteDB.initialize()`.

---

## File Structure

```
backend/
  providers/
    base.py             # LLMProvider ABC, EmbeddingProvider ABC  [EXISTS — extend]
    registry.py         # ProviderRegistry: active-provider model [EXISTS — extend]
    ollama.py           # OllamaLLMProvider, OllamaEmbeddingProvider  [EXISTS — extend]
    openrouter.py       # OpenRouterLLMProvider  [EXISTS — extend: retry + 429]
    openai.py           # OpenAILLMProvider  [EXISTS — extend: retry + 429]
    anthropic.py        # AnthropicLLMProvider  [EXISTS — extend: retry + 429]
    key_manager.py      # KeyManager: Fernet encrypt/decrypt  [EXISTS — no changes]
  storage/
    sqlite_db.py        # SQLiteDB.create_query_trace() — add provider_name param  [EXTEND]
  ingestion/
    embedder.py         # BatchEmbedder — wire get_embedding_provider()  [EXTEND]
  agent/
    nodes.py            # LangGraph nodes — wire get_active_llm()  [EXTEND]
  api/
    chat.py             # Resolve + pass provider_name to create_query_trace  [EXTEND]
    models.py           # _fetch_ollama_models enrichment  [EXTEND]
tests/
  unit/
    test_providers.py         # Expand: retry, 429, model param  [EXTEND]
    test_providers_router.py  # Expand: enriched model listing  [EXTEND]
  integration/
    test_providers_integration.py  # New: end-to-end registry wiring tests
```

---

## Implementation Steps

### Step 1: Base Interface Extension (model-agnostic embedding)

1. Update `EmbeddingProvider.embed()` signature in `base.py`:
   `async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]`
2. Update `EmbeddingProvider.embed_single()` signature:
   `async def embed_single(self, text: str, model: str | None = None) -> list[float]`
3. Update `OllamaEmbeddingProvider.embed()` and `embed_single()` to use `model or self.model` when
   building the request payload.
4. Verify all existing callers pass no `model` argument and continue to type-check correctly.

### Step 2: Retry and Rate-Limit Handling (cloud providers)

1. Add `_call_with_retry()` helper (or inline retry logic) to `OpenRouterLLMProvider`,
   `OpenAILLMProvider`, and `AnthropicLLMProvider`.
2. On `httpx.HTTPStatusError` with status 429: raise `ProviderRateLimitError` immediately (FR-018).
3. On `httpx.HTTPStatusError` with 5xx or `httpx.TimeoutException`: retry once, then re-raise (FR-017).
4. On other 4xx errors: re-raise immediately without retry.
5. `OllamaLLMProvider` is excluded from this change — its error handling is governed by the
   circuit breaker from spec-05.

### Step 3: query_traces Schema Migration

1. Add `provider_name TEXT` column to `query_traces` table in `SQLiteDB.initialize()` using
   `ALTER TABLE query_traces ADD COLUMN provider_name TEXT`. Guard with `IF NOT EXISTS` pattern
   (catch `OperationalError: duplicate column name`).
2. Update `SQLiteDB.create_query_trace()` signature to accept `provider_name: str | None = None`.
3. Include `provider_name` in the `INSERT` statement for `query_traces`.

### Step 4: chat.py — Provider Name Propagation

1. In `backend/api/chat.py`, after resolving the active LLM via `app.state.registry.get_active_llm(db)`,
   call `provider.get_model_name()` and store the result.
2. Pass the provider name string to `db.create_query_trace(..., provider_name=provider_name)`.
3. The `provider_name` value should be the registry key (e.g., `"ollama"`, `"openrouter"`,
   `"openai"`, `"anthropic"`), not the model string.

### Step 5: Agent Node Wiring

1. Run `gitnexus_impact({target: "nodes", direction: "upstream"})` before touching `nodes.py`.
   Report blast radius to the user. Do not proceed if risk is CRITICAL without acknowledgement.
2. Update the LangGraph node functions in `backend/agent/nodes.py` that invoke the LLM to call
   `await registry.get_active_llm(db)` rather than constructing a hard-coded `ChatOllama` instance.
3. The `registry` and `db` must be threaded through the node config (`RunnableConfig`) or captured
   via the lifespan-injected `app.state`. Use the same pattern established in spec-08 for injecting
   `db` and `registry` into request-scoped code.
4. Run the full test suite after this step to confirm no regressions in spec-02, spec-03, spec-04
   conversation graph tests.

### Step 6: BatchEmbedder Wiring

1. Update `backend/ingestion/embedder.py`: replace the direct `OllamaEmbeddingProvider(...)`
   instantiation with a call to `registry.get_embedding_provider()`.
2. The `ProviderRegistry` instance must be passed into `BatchEmbedder` (constructor injection) or
   accessed via `app.state.registry` at the pipeline entry point.
3. Confirm the `embed()` call signature still works — no `model` argument is passed here; the
   optional parameter from Step 1 defaults to `None`.

### Step 7: Model Listing Enrichment

1. In `backend/api/models.py`, after calling `_fetch_ollama_models()`, check each cloud provider's
   DB row for a non-null `api_key_encrypted` value.
2. For providers with a key present, append their known/configured model to the response list with
   appropriate `provider` metadata so the frontend can group them.
3. The `GET /api/models/llm` response format must remain backward-compatible; new entries are additive.

---

## Key Code Patterns

### Active-Provider Registry Lookup

```python
# ProviderRegistry.get_active_llm — existing implementation shape
async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
    active = await db.get_active_provider()
    config = json.loads(active["config_json"])
    model = config.get("model", "")
    provider_name = active["name"]
    if provider_name == "openrouter":
        key = self._key_manager.decrypt(active["api_key_encrypted"])
        return OpenRouterLLMProvider(api_key=key, model=model)
    elif provider_name == "openai":
        key = self._key_manager.decrypt(active["api_key_encrypted"])
        return OpenAILLMProvider(api_key=key, model=model)
    elif provider_name == "anthropic":
        key = self._key_manager.decrypt(active["api_key_encrypted"])
        return AnthropicLLMProvider(api_key=key, model=model)
    return self._ollama_llm  # fallback
```

### httpx Streaming — Ollama

```python
# OllamaLLMProvider.generate_stream — SSE with "response" field
async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    url = f"{self.base_url}/api/generate"
    payload = {"model": self.model, "prompt": prompt, "system": system_prompt}
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, timeout=60.0) as resp:
            async for line in resp.aiter_lines():
                if not line:
                    continue
                data = json.loads(line)
                if token := data.get("response"):
                    yield token
                if data.get("done"):
                    break
```

### httpx Streaming — OpenAI-compatible SSE

```python
# OpenRouterLLMProvider / OpenAILLMProvider — "data: " prefix pattern
async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    url = f"{self.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
    payload = {
        "model": self.model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": prompt}],
        "stream": True,
    }
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, headers=headers, json=payload, timeout=60.0) as resp:
            if resp.status_code == 429:
                raise ProviderRateLimitError(provider=self.__class__.__name__)
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                body = line[len("data: "):]
                if body == "[DONE]":
                    break
                data = json.loads(body)
                if token := data["choices"][0]["delta"].get("content"):
                    yield token
```

### Key Security Pattern

```python
# Keys are NEVER:
# - Logged (use structlog's filter or mask keys in log contexts)
# - Returned in API responses (provider response schema exposes has_key: bool, not the key itself)
# - Stored in plaintext (Fernet encryption in SQLite api_key_encrypted column)
# - Held in memory longer than needed (decrypt -> use -> goes out of scope)
```

---

## Integration Points

- **Agent Graphs** (`backend/agent/nodes.py`): Agent node functions call
  `ProviderRegistry.get_active_llm(db)` for LLM inference. This is wired in spec-10 (Step 5).
  Before editing, run `gitnexus_impact({target: "nodes", direction: "upstream"})`.

- **Ingestion Pipeline** (`backend/ingestion/embedder.py`): `BatchEmbedder` calls
  `ProviderRegistry.get_embedding_provider()` to obtain the embedding provider. Wired in spec-10
  (Step 6).

- **Storage** (`backend/storage/sqlite_db.py`): `query_traces` table gains `provider_name TEXT`
  column. `SQLiteDB.create_query_trace()` gains `provider_name: str | None = None` parameter.

- **API Routes** (`backend/api/chat.py`, `backend/api/models.py`): `chat.py` extracts and persists
  `provider_name` on each query trace. `models.py` enriches the model list with cloud provider
  models when keys are present.

- **Frontend** (`spec-09`): The ProviderHub component and ModelSelector consume
  `GET /api/providers` and `GET /api/models/llm`. No frontend changes are needed in spec-10 — the
  API contract remains backward-compatible; new model entries are additive.

- **Error Handling**: `ProviderRateLimitError` is raised on HTTP 429 (FR-018). The API layer
  catches it and returns HTTP 429 to the client. Other provider errors follow the existing error
  hierarchy from spec-12.

---

## Agent Teams Workflow

Spec-10 uses the Agent Teams pattern. All agents read their instruction file first before executing
tasks. Instruction files live at `Docs/PROMPTS/spec-10-providers/agents/`.

### Wave Structure

| Wave | Agents | Mode | Focus | Model |
|------|--------|------|-------|-------|
| 1 | A1 | serial | Base interface extension + schema migration design | Opus (backend-architect) |
| 2 | A2, A3 | parallel | Ollama embedding update / Cloud provider retry+429 | Sonnet (python-expert) |
| 3 | A4 | serial | Integration wiring: nodes.py, embedder.py, chat.py, query_traces | Sonnet (python-expert) |
| 4 | A5 | serial | Tests, gate checks, regression verification | Sonnet (quality-engineer) |

**Gate rules**:
- Wave 2 cannot start until A1 has completed and the gate check `spec10-gate-wave1` passes.
- Wave 3 cannot start until both A2 and A3 have completed and gate check `spec10-gate-wave2` passes.
- Wave 4 cannot start until A4 has completed and gate check `spec10-gate-wave3` passes.

### Agent Assignments

| Agent | Role | Wave | Tasks |
|-------|------|------|-------|
| A1 | backend-architect (Opus) | 1 | Step 1 (base interface), Step 3 (schema migration) |
| A2 | python-expert (Sonnet) | 2 | Step 1 extension in OllamaEmbeddingProvider |
| A3 | python-expert (Sonnet) | 2 | Step 2 (retry + 429 for all cloud providers) |
| A4 | python-expert (Sonnet) | 3 | Steps 4–7 (wiring: chat.py, nodes.py, embedder.py, models.py) |
| A5 | quality-engineer (Sonnet) | 4 | All unit + integration tests, regression gate checks |

### Instruction File Locations

```
Docs/PROMPTS/spec-10-providers/agents/
  A1-backend-architect.md
  A2-python-expert-ollama.md
  A3-python-expert-cloud.md
  A4-python-expert-wiring.md
  A5-quality-engineer.md
```

### GitNexus Impact Analysis Requirement

A4 MUST run impact analysis before touching `nodes.py`:

```
gitnexus_impact({target: "nodes", direction: "upstream"})
```

Report the blast radius to the user. If risk level is HIGH or CRITICAL, warn the user and wait for
acknowledgement before proceeding. After all edits, run:

```
gitnexus_detect_changes({scope: "staged"})
```

to verify changes match expected scope.

---

## Testing Protocol (MANDATORY)

Every agent instruction file MUST include this rule verbatim. Violation of this rule breaks the
test infrastructure.

```
## Testing Rule (MANDATORY)
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll status: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read summary: cat Docs/Tests/<name>.summary   (~20 lines, token-efficient)
Full log: cat Docs/Tests/<name>.log

Wave gate checks (run before releasing the next wave):
  zsh scripts/run-tests-external.sh -n spec10-gate-wave1 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-wave2 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-final tests/
```

Acceptable baseline: 0 new failures relative to the spec-09 baseline (946 tests passing, 39
pre-existing known failures unchanged).

---

## Phase Assignment

- **Phase 1 (MVP)**: All seven spec-10 items are in scope. Retry logic, 429 handling, query_traces
  migration, agent wiring, embedder wiring, and model listing enrichment are all required before the
  frontend ProviderHub component (spec-09) can function correctly end-to-end.
- **Phase 2**: Additional embedding providers (OpenAI Embeddings, Anthropic future embedding APIs)
  may extend `EmbeddingProvider` further once the optional model parameter pattern from Step 1 is
  in place.
