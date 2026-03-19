# Implementation Guide: Provider Architecture (spec-10)

---

> **AGENT TEAMS — tmux IS REQUIRED**
>
> Wave 2 runs A2 and A3 in parallel. Each agent gets its own tmux pane. Without an active
> tmux session, parallel execution falls back to sequential (A2 finishes, then A3 starts),
> which is slower but still correct. Start implementation inside tmux:
> `tmux new-session -s spec10` or attach to your existing session.
>
> Spawn command for every agent (no exceptions):
> `"Read your instruction file at <path> FIRST, then execute all assigned tasks"`

---

## Component Overview

Spec-10 **extends** the existing provider scaffolding created in spec-08. It does NOT create
any new provider classes and does NOT recreate anything that already exists. The seven
concrete additions are:

1. `ProviderRateLimitError` exception class in `base.py` (FR-018)
2. `model: str | None = None` optional parameter on `EmbeddingProvider.embed()` and
   `embed_single()` in `base.py` (FR-006)
3. Retry-once on 5xx / timeout in `generate()` and `generate_stream()` for all three cloud
   providers; HTTP 429 raises `ProviderRateLimitError` immediately (FR-017)
4. `ALTER TABLE query_traces ADD COLUMN provider_name TEXT` schema migration with idempotency
   guard; `create_query_trace()` gains `provider_name: str | None = None` (FR-019)
5. Wire `registry.get_active_llm(db)` into LangGraph conversation node functions — currently
   nodes accept `llm: Any` via kwargs but receive `None` at runtime (no LLM bound)
6. `BatchEmbedder` constructor injection — accept `embedding_provider: EmbeddingProvider`
   instead of instantiating `OllamaEmbeddingProvider` internally
7. `GET /api/models/llm` appends cloud provider models when `api_key_encrypted` is non-null

---

## What Already Exists (do NOT recreate)

All provider classes below exist and work. Spec-10 only extends them.

### backend/providers/base.py — current signatures

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
    async def embed(self, texts: list[str]) -> list[list[float]]: ...      # model param MISSING — T004 adds it
    @abstractmethod
    async def embed_single(self, text: str) -> list[float]: ...            # model param MISSING — T005 adds it
    @abstractmethod
    def get_model_name(self) -> str: ...
    @abstractmethod
    def get_dimension(self) -> int: ...
```

There is NO `list_models()` abstract method. There is NO LangChain dependency in the provider
layer. All implementations use `httpx` directly. The interface method is `generate(prompt,
system_prompt)` and `generate_stream(prompt, system_prompt)` — NOT `chat(messages, model)`.

### backend/providers/ollama.py — two separate classes

- `OllamaLLMProvider(base_url, model)` — httpx POST `/api/generate`, SSE JSON lines
- `OllamaEmbeddingProvider(base_url, model)` — httpx POST `/api/embed`

These are TWO classes, not one. There is no `OllamaProvider` that merges both.

`OllamaEmbeddingProvider.embed_single()` currently builds `json={"model": self.model, "input": text}`.
T008 changes this to use `effective_model = model or self.model` in the API payload.

### backend/providers/openrouter.py

`OpenRouterLLMProvider(api_key, model)` — httpx POST `/chat/completions`.
`generate()` and `generate_stream()` currently have NO retry logic. T009 adds it.

### backend/providers/openai.py

`OpenAILLMProvider(api_key, model)` — same httpx SSE pattern as OpenRouter. T010 adds retry.

### backend/providers/anthropic.py

`AnthropicLLMProvider(api_key, model="claude-sonnet-4-20250514")`. T010 adds retry.

### backend/providers/registry.py — actual current interface

```python
class ProviderRegistry:
    def __init__(self, settings: Settings):       # creates _ollama_llm + _ollama_embed from settings
    async def initialize(self, db: SQLiteDB) -> None
    async def get_active_llm(self, db: SQLiteDB) -> LLMProvider
    def get_embedding_provider(self) -> EmbeddingProvider
    async def set_active_provider(self, db, name, config=None) -> bool
```

Constructor takes `Settings`, NOT `(db, key_manager, ollama_url)`. There is NO
`_resolve_provider_type()` method; registry uses an active-provider model, not model-name routing.
`get_active_llm(db)` reads the active provider row and lazy-instantiates cloud providers,
falling back to `_ollama_llm` on unknown names. It already calls `db.get_active_provider()` internally.

### backend/providers/key_manager.py — actual current interface

```python
class KeyManager:
    def __init__(self) -> None   # reads EMBEDINATOR_FERNET_KEY env var, raises ValueError if absent
    def encrypt(self, plaintext: str) -> str
    def decrypt(self, ciphertext: str) -> str
    def is_valid_key(self, ciphertext: str) -> bool
```

- Constructor takes NO arguments
- Env var is `EMBEDINATOR_FERNET_KEY` (NOT `API_KEY_ENCRYPTION_SECRET`)
- There is NO `get_fernet_key()` function, NO `ensure_secret()` method, NO SHA-256 derivation,
  NO auto-generation of secrets
- `main.py` sets `app.state.key_manager = None` on `ValueError` at startup

### backend/api/providers.py — existing routes

```
GET    /api/providers                    # list all providers
PUT    /api/providers/{name}/key         # encrypt + store API key; returns HTTP 503 if key_manager is None
DELETE /api/providers/{name}/key         # remove key
```

T016 verifies: `key_manager is None` → HTTP 503 (already implemented). T019-T020 add health route.

### backend/api/models.py — existing routes

```
GET /api/models/llm    # currently: Ollama LLM models only via _fetch_ollama_models()
GET /api/models/embed  # Ollama embed models; unchanged by spec-10
```

T021 enriches `GET /api/models/llm` to include cloud provider model entries when keys are stored.

### Agent Node Wiring — LangChain Factory (Architecture Decision R7)

**CRITICAL DISCOVERY**: Agent nodes across all 3 graph layers use LangChain `BaseChatModel`
methods — NOT the `LLMProvider` ABC from `base.py`:

| Method | Call sites | Cannot be replaced by |
|--------|-----------|----------------------|
| `llm.ainvoke(messages)` | 7 sites across nodes.py, research_nodes.py, meta_reasoning_nodes.py | `LLMProvider.generate()` — different message format |
| `llm.with_structured_output(PydanticModel)` | 2 sites: `rewrite_query` (QueryAnalysis), `verify_groundedness` (GroundednessResult) | Nothing — requires JSON mode + schema injection + retry |
| `llm.bind_tools(tools_list)` | 1 site: `orchestrator` in research_nodes.py | Nothing — requires tool-calling protocol |

**The solution (Option E)**: Add `get_active_langchain_model(db) -> BaseChatModel` to
`ProviderRegistry`. This factory method returns the appropriate LangChain model:

| Active provider | Returns | Package |
|----------------|---------|---------|
| `"ollama"` (default) | `ChatOllama(base_url=..., model=...)` | `langchain-ollama` |
| `"openrouter"` | `ChatOpenAI(api_key=key, base_url="https://openrouter.ai/api/v1")` | `langchain-openai` |
| `"openai"` | `ChatOpenAI(api_key=key, model=...)` | `langchain-openai` |
| `"anthropic"` | `ChatAnthropic(api_key=key, model=...)` | `langchain-anthropic` |

**Two LLM access paths coexist by design**:
- `get_active_llm(db) -> LLMProvider` — for `chat.py` NDJSON streaming, health checks, retry logic
- `get_active_langchain_model(db) -> BaseChatModel` — for agent graph nodes requiring `ainvoke`, `with_structured_output`, `bind_tools`

**Wiring in chat.py** (T013): The LangChain model is passed to the graph via `config["configurable"]`:
```python
langchain_llm = await registry.get_active_langchain_model(db)
config = {
    "configurable": {
        "thread_id": session_id,
        "llm": langchain_llm,          # agent nodes read this
        "tools": app.state.research_tools,
    }
}
async for event in conversation_graph.astream(input_state, config=config):
    ...
```

**nodes.py is NOT edited** — the `research_nodes.py` pattern (`config["configurable"]["llm"]`)
already works. Conversation nodes receive `llm` via `**kwargs` from the config propagation.
The wiring happens entirely in `registry.py` (new method) and `chat.py` (config dict expansion).

### backend/ingestion/embedder.py — BatchEmbedder current signature

```python
class BatchEmbedder:
    def __init__(
        self,
        model: str | None = None,
        max_workers: int | None = None,
        batch_size: int | None = None,
    ):
        self.model = model or settings.default_embed_model
        self.base_url = settings.ollama_base_url
        # instantiates OllamaEmbeddingProvider internally (currently hard-coded)
```

T023 replaces direct `OllamaEmbeddingProvider` instantiation with constructor injection:
accept `embedding_provider: EmbeddingProvider` and use it directly.

### backend/storage/sqlite_db.py — create_query_trace() current signature

```python
async def create_query_trace(
    self, id, session_id, query, collections_searched, chunks_retrieved_json,
    latency_ms, llm_model=None, embed_model=None, confidence_score=None,
    sub_questions_json=None, reasoning_steps_json=None, strategy_switches_json=None,
    meta_reasoning_triggered=False,
) -> None:
```

T007 adds `provider_name: str | None = None` to this signature and includes it in the INSERT.

The migration follows the same pattern as `_migrate_providers_columns()`:
```python
cursor = await self.db.execute("PRAGMA table_info(query_traces)")
columns = {row[1] for row in await cursor.fetchall()}
if "provider_name" not in columns:
    await self.db.execute("ALTER TABLE query_traces ADD COLUMN provider_name TEXT")
await self.db.commit()
```

Add a `_migrate_query_traces_columns()` method and call it from `_init_schema()` after
the existing `_migrate_providers_columns()` call.

---

## Technical Implementation Details

### ProviderRateLimitError (T003 — goes in base.py)

```python
class ProviderRateLimitError(Exception):
    """Raised by cloud providers on HTTP 429 rate limit responses."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

### Model-Agnostic Embed Signatures (T004, T005)

In `EmbeddingProvider` in `backend/providers/base.py`:

```python
@abstractmethod
async def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
    """Generate embeddings. model=None uses self.model."""

@abstractmethod
async def embed_single(self, text: str, model: str | None = None) -> list[float]:
    """Generate single embedding. model=None uses self.model."""
```

### OllamaEmbeddingProvider model override (T008 — ollama.py only)

In `OllamaEmbeddingProvider.embed_single()`:

```python
async def embed_single(self, text: str, model: str | None = None) -> list[float]:
    effective_model = model or self.model
    # Use effective_model in the API payload instead of self.model:
    json={"model": effective_model, "input": text}
```

Also update `embed()` signature to accept `model: str | None = None` and forward it to
`embed_single()`. The `embed()` method loops over texts and calls `embed_single()` for each.

### Retry-Once Pattern (T009 for OpenRouter, T010 for OpenAI + Anthropic)

Add `_call_with_retry()` as an instance method on each cloud provider class. Apply to BOTH
`generate()` AND `generate_stream()`. The pattern is identical for all three providers:

```python
async def _call_with_retry(self, make_request_fn):
    for attempt in range(2):
        try:
            return await make_request_fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderRateLimitError(provider=self.__class__.__name__) from exc
            if exc.response.status_code < 500:
                raise  # 4xx other than 429: no retry
            if attempt == 1:
                raise
        except httpx.TimeoutException:
            if attempt == 1:
                raise
```

Import `ProviderRateLimitError` from `backend.providers.base` in each cloud provider file.
For `generate_stream()`, wrap the entire httpx request setup (connection + response) inside
`_call_with_retry`, not individual chunk reads.

### provider_name capture in chat.py (T013)

`registry.get_active_llm(db)` does NOT return the provider name — it only returns the
`LLMProvider` instance. Extract the name separately using `db.get_active_provider()` BEFORE
calling `get_active_llm()`. Use the existing `db` handle already present in `chat()`:

```python
# In generate() before the graph astream call:
active = await db.get_active_provider()
provider_name = active["name"] if active else "ollama"

# Then in the create_query_trace() call:
await db.create_query_trace(
    ...
    provider_name=provider_name,
)
```

Do NOT add a new method to `ProviderRegistry`.

### ProviderRateLimitError FastAPI handler (T014 — goes in main.py)

Add after the middleware registrations inside `create_app()`:

```python
from fastapi.responses import JSONResponse
from backend.providers.base import ProviderRateLimitError

@app.exception_handler(ProviderRateLimitError)
async def rate_limit_handler(request, exc: ProviderRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"type": "error", "message": str(exc), "code": "rate_limit"},
    )
```

### Health Endpoint Contract (T018-T020 — providers.py)

`GET /api/providers/health` returns HTTP 200 with:

```python
# Response schema
{"providers": [{"provider": "ollama", "reachable": True}, ...]}
```

Rules:
- All `health_check()` calls MUST run concurrently via `asyncio.gather()`
- Providers with no API key stored: return `reachable: False` immediately, no `health_check()` call
- The endpoint NEVER raises — catch all exceptions, return `reachable: False`
- Each `health_check()` uses `httpx.AsyncClient(timeout=5.0)`

Verify T018 first: all four `health_check()` implementations (ollama.py, openrouter.py,
openai.py, anthropic.py) must use `httpx.AsyncClient(timeout=5.0)`, not the default timeout.
Add it where missing.

---

## Agent Teams Wave Structure

| Wave | Agent | Model | Tasks | Primary Files | Gate |
|------|-------|-------|-------|---------------|------|
| 1 | A1 backend-architect | Opus 4.6 | T003–T007 | base.py, sqlite_db.py | spec10-gate-wave1 |
| 2 parallel | A2 python-expert-ollama | Sonnet 4.6 | T008 | ollama.py | (orchestrator runs wave2 gate after both A2+A3 done) |
| 2 parallel | A3 python-expert-cloud | Sonnet 4.6 | T009–T010 | openrouter.py, openai.py, anthropic.py | spec10-gate-wave2 |
| 3 | A4 python-expert-wiring | Sonnet 4.6 | T011–T025 | registry.py, chat.py, main.py, requirements.txt, key_manager.py, providers.py, models.py, embedder.py, ingest.py | spec10-gate-wave3 |
| 4 | A5 quality-engineer | Sonnet 4.6 | T026–T034 | test_providers.py, test_sqlite_db.py, test_providers_router.py, test_providers_integration.py (new) | spec10-gate-final |

### Orchestrator Gate Commands

```bash
# After Wave 1 completes:
zsh scripts/run-tests-external.sh -n spec10-gate-wave1 tests/

# After BOTH A2 AND A3 (Wave 2) complete:
zsh scripts/run-tests-external.sh -n spec10-gate-wave2 tests/

# After Wave 3 completes:
zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/

# After Wave 4 (final):
zsh scripts/run-tests-external.sh -n spec10-gate-final tests/
```

Each gate must reach `PASSED` status before the next wave spawns.
Baseline: 946 tests passing, 39 known pre-existing failures unchanged from spec-09.

---

## Testing Protocol (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## GitNexus Requirements

A4 MUST run impact analysis before touching `backend/providers/registry.py` (to verify adding a method has no unexpected downstream effects):

```
gitnexus_impact({target: "nodes", direction: "upstream", repo: "The-Embedinator"})
```

Report the blast radius (direct callers, affected processes, risk level).
If risk is HIGH or CRITICAL, warn the user and await explicit acknowledgement before editing.

After all Wave 3 edits are complete:

```
gitnexus_detect_changes({scope: "staged", repo: "The-Embedinator"})
```

Verify that only the expected files changed.

---

## File Structure

```
backend/
  providers/
    base.py          [EXTEND] — add ProviderRateLimitError; add model param to embed signatures
    ollama.py        [EXTEND] — update OllamaEmbeddingProvider embed/embed_single for model param
    openrouter.py    [EXTEND] — add retry + 429 to generate() and generate_stream()
    openai.py        [EXTEND] — add retry + 429 to generate() and generate_stream()
    anthropic.py     [EXTEND] — add retry + 429 to generate() and generate_stream()
    registry.py      [NO CHANGE] — no interface change in spec-10
    key_manager.py   [VERIFY ONLY] — T015 checks is_valid_key() correctness; fix if broken
  storage/
    sqlite_db.py     [EXTEND] — add _migrate_query_traces_columns(); update create_query_trace()
  ingestion/
    embedder.py      [EXTEND] — BatchEmbedder constructor injection
    ingest.py        [EXTEND] — pass registry.get_embedding_provider() to BatchEmbedder
  agent/
    nodes.py         [UNTOUCHED] — LLM injection via config["configurable"]["llm"], no code changes needed
  api/
    chat.py          [EXTEND] — capture provider_name; pass to create_query_trace()
    main.py          [EXTEND] — add ProviderRateLimitError exception handler
    providers.py     [EXTEND] — add GET /api/providers/health endpoint (T019-T020)
    models.py        [EXTEND] — enrich GET /api/models/llm with cloud provider models (T021)

tests/
  unit/
    test_providers.py           [EXTEND] — retry + 429 + model-agnostic param tests (T026-T027)
    test_sqlite_db.py           [EXTEND] — provider_name column migration tests (T028)
    test_providers_router.py    [EXTEND] — health endpoint + enriched model listing tests (T029-T030)
  integration/
    test_providers_integration.py  [NEW] — registry flow + BatchEmbedder injection tests (T031-T032)
```

---

## Done Criteria

All of the following must be true before spec-10 is complete:

1. `zsh scripts/run-tests-external.sh -n spec10-gate-final tests/` reaches `PASSED` with 0 new failures
2. `ProviderRateLimitError` is raised by all three cloud providers on HTTP 429; Ollama never raises it
3. `OllamaEmbeddingProvider.embed(texts, model="nomic-embed-text")` uses `"nomic-embed-text"` in the API payload
4. `query_traces` table has a `provider_name` column; `create_query_trace(provider_name=...)` persists it
5. `GET /api/chat` traces written to DB include a non-null `provider_name` for the active provider
6. LangGraph conversation node functions receive a valid LangChain-compatible `llm` object at runtime (not `None`)
7. `BatchEmbedder` accepts `embedding_provider: EmbeddingProvider` in its constructor; no hard-coded instantiation
8. `GET /api/providers/health` returns within 5 seconds with `reachable: bool` per provider
9. `GET /api/models/llm` includes cloud provider model entries when `api_key_encrypted` is non-null
10. `gitnexus_detect_changes(scope="all")` confirms only expected files changed
