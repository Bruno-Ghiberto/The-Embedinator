# Research: Provider Architecture

**Phase**: 0 — Outline & Research
**Date**: 2026-03-16
**Feature**: [spec.md](./spec.md)

## Scope

Spec-10 extends existing scaffolding from spec-08. All provider classes, interfaces, and the registry
already exist. Research focused on: (1) verifying actual codebase state vs spec assumptions,
(2) identifying integration risks, and (3) resolving all unknowns before design.

---

## R1: Actual Provider Interface vs Spec

**Decision**: `EmbeddingProvider.embed()` and `embed_single()` do NOT currently accept a model
parameter. Spec-10 adds `model: str | None = None` as an optional backward-compatible parameter.

**Finding**: `backend/providers/base.py` signatures confirmed:
```python
async def embed(self, texts: list[str]) -> list[list[float]]
async def embed_single(self, text: str) -> list[float]
```
No `model` parameter exists yet. Adding it as optional preserves all existing callers.

**Rationale**: Model-agnostic embedding (FR-006, clarification Q2) requires a single
`OllamaEmbeddingProvider` instance to handle all collections regardless of their configured model.
The caller passes `model=collection.embedding_model` at call time.

**Alternatives considered**:
- Per-model instantiation: Rejected — creates registry complexity and breaks the single-instance contract.
- Global default override: Rejected — implicit, hard to test.

---

## R2: ProviderRegistry — Active-Provider Model (not model-name routing)

**Decision**: `ProviderRegistry` is NOT a model-name router. It maintains a single active LLM
provider stored in the SQLite `providers` table. `get_active_llm(db)` reads which row has
`is_active = 1` and lazy-instantiates the correct class.

**Finding**: `backend/providers/registry.py` confirmed:
```python
async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
    active = await db.get_active_provider()
    config = json.loads(active["config_json"])
    provider_name = active["name"]
    if provider_name == "openrouter": ...
    elif provider_name == "openai": ...
    elif provider_name == "anthropic": ...
    return self._ollama_llm  # fallback
```
No `list_all_models()` or model-name prefix dispatch. Spec-10 adds no new dispatch logic here.

**Alternatives considered**:
- Model-name based routing: Rejected — complicates switching and violates FR-001 (single active provider).

---

## R3: httpx Streaming Patterns — Ollama vs OpenAI-compatible

**Decision**: Two distinct SSE parsing patterns are in use. No LangChain in the provider layer.

**Finding**: Confirmed via codebase inspection:
- **Ollama** (`/api/generate`): JSON lines, field name `"response"`, done signal via `data.get("done")`
- **OpenAI-compatible** (OpenRouter, OpenAI): SSE with `data: ` prefix, `[DONE]` terminator,
  token at `choices[0].delta.content`
- **Anthropic** (`/api/anthropic.com/v1`): SSE with `data: ` prefix, event type `"content_block_delta"`,
  token at `delta.text`

**Rationale**: Direct httpx streaming avoids LangChain version coupling and gives full control over
SSE parsing for retry logic injection.

---

## R4: Retry-Once Pattern — Where to Apply (FR-017)

**Decision**: Retry logic applies ONLY to cloud providers (OpenRouter, OpenAI, Anthropic) on
`httpx.HTTPStatusError` with 5xx status or `httpx.TimeoutException`. Exactly one retry.
Retry applies to **both** `generate()` and `generate_stream()` — FR-017 says "the request"
without limiting to streaming only.

**Finding**: `OllamaLLMProvider` already has circuit breaker behavior from spec-05
(`backend/agent/nodes.py` wraps Ollama calls). Applying retry to Ollama would conflict with
the existing circuit breaker protocol.

**Implementation pattern** (verified against spec-08 existing cloud providers):
```python
async def _call_with_retry(self, make_request_fn):
    for attempt in range(2):
        try:
            return await make_request_fn()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ProviderRateLimitError(...) from exc  # FR-018
            if exc.response.status_code < 500:
                raise  # 4xx other than 429: no retry
            if attempt == 1:
                raise  # exhausted retry
        except httpx.TimeoutException:
            if attempt == 1:
                raise
```

**Alternatives considered**:
- tenacity retry decorator: More verbose and couples retry config to provider class constructor.
  Inline loop is simpler and sufficient for exactly-once semantics.
- Apply to Ollama too: Rejected — conflicts with spec-05 circuit breaker.

---

## R5: ProviderRateLimitError — Location and Handling (FR-018)

**Decision**: `ProviderRateLimitError` is raised in the cloud provider `generate_stream()`
implementation on HTTP 429. The API layer (`chat.py`) catches it and returns HTTP 429 to the client.
It is NOT in `backend/errors.py` yet (spec-12 deferred); define it inline in `providers/base.py`
or as a simple exception class in `providers/` until spec-12 formalizes the hierarchy.

**Finding**: `backend/errors.py` confirmed — no `ProviderRateLimitError` exists. FR-018 and spec
note spec-12 as FUTURE. A simple `class ProviderRateLimitError(Exception): ...` in `base.py`
satisfies the requirement without premature hierarchy.

**Rationale**: Constitution Principle VII (Simplicity) — don't build the full error hierarchy
for a feature that doesn't need it yet.

---

## R6: query_traces Schema Migration (FR-019)

**Decision**: Use `ALTER TABLE query_traces ADD COLUMN provider_name TEXT` in `SQLiteDB.initialize()`.
Guard with try/except on `aiosqlite.OperationalError` (duplicate column name).

**Finding**: `backend/storage/sqlite_db.py` `create_query_trace()` confirmed — no `provider_name`
column exists. The `query_traces` table was established in spec-07. SQLite WAL mode supports
`ALTER TABLE ... ADD COLUMN` safely. The copy-create-drop migration pattern (used in spec-06 for
documents table) is NOT needed here — `ADD COLUMN` is sufficient for adding a nullable column.

**Alternatives considered**:
- Copy-create-drop cycle: More robust for complex migrations; overkill for a single nullable column.
- Schema versioning table: Would require new infrastructure; violation of Principle VII.

---

## R7: Agent Node Wiring — LangChain Factory on ProviderRegistry (Step 5)

**Decision**: Add `get_active_langchain_model(db) -> BaseChatModel` to `ProviderRegistry`. The
agent nodes (all 3 graph layers) require LangChain `BaseChatModel` methods (`ainvoke`,
`with_structured_output`, `bind_tools`) that `LLMProvider` does not expose.  The factory method
returns `ChatOllama`, `ChatOpenAI`, or `ChatAnthropic` depending on the active provider.
Wire the result into `chat.py`'s config dict: `config["configurable"]["llm"] = langchain_llm`.

**Risk**: LOW — nodes.py is NOT edited. Only `registry.py` (1 new method) and `chat.py`
(config dict update) change. All existing spec-02/03/04/05 tests pass unchanged because
test mocks already provide LangChain-compatible objects.

**Finding (critical discovery)**: Agent nodes in `nodes.py` use `llm.ainvoke()` (7 sites),
`llm.with_structured_output()` (2 sites: `QueryAnalysis`, `GroundednessResult`), and
`llm.bind_tools()` (1 site in `research_nodes.py:orchestrator`). These are LangChain
`BaseChatModel` methods — NOT replaceable by `LLMProvider.generate()` without hundreds
of lines of adapter code. Additionally, `chat.py` currently passes only
`{"configurable": {"thread_id": ...}}` — it never injects `llm`, `tools`, or `reranker`
into the graph config. The entire agent layer runs with `llm=None`.

**Implementation**:
```python
# registry.py — add one method
async def get_active_langchain_model(self, db: SQLiteDB) -> "BaseChatModel":
    active = await db.get_active_provider()
    if not active or active["name"] == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(base_url=..., model=...)
    config = json.loads(active["config_json"])
    key = self._key_manager.decrypt(active["api_key_encrypted"])
    if active["name"] in ("openrouter", "openai"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=key, model=config["model"], base_url=...)
    elif active["name"] == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=key, model=config["model"])
    from langchain_ollama import ChatOllama
    return ChatOllama(base_url=..., model=...)  # fallback

# chat.py — in generate(), pass langchain model to graph config
langchain_llm = await registry.get_active_langchain_model(db)
config = {
    "configurable": {
        "thread_id": session_id,
        "llm": langchain_llm,
        "tools": app.state.research_tools,
    }
}
```

**Alternatives evaluated (5 options)**:
- Option A (Dual-return): Functionally identical to Option E; E is clearer framing.
- Option B (LangChain Adapter wrapping LLMProvider): REJECTED — `with_structured_output()`
  and `bind_tools()` cannot be replicated without hundreds of lines of fragile adapter code.
  Violates Constitution Principle VII (Simplicity).
- Option C (Refactor nodes to use LLMProvider directly): REJECTED — blast radius: 21+ node
  functions, 335+ tests. Would require reimplementing structured output and tool calling
  from scratch. Belongs in a separate spec if ever pursued.
- Option D (Registry for selection only, agent layer builds LangChain models): REJECTED —
  splits provider resolution across two locations; harder to maintain.
- **Option E (LangChain factory on ProviderRegistry): SELECTED** — minimal blast radius,
  Constitution-compliant, established DI pattern, keeps registry as single source of truth.

**New packages**: `langchain-ollama`, `langchain-openai`, `langchain-anthropic` must be added
to `requirements.txt`. These are already implied by the constitutional tech stack pinning
(`LangChain >= 1.2.10`).

---

## R8: BatchEmbedder — OllamaEmbeddingProvider Direct vs Registry

**Decision**: `backend/ingestion/embedder.py` instantiates `OllamaEmbeddingProvider` directly.
Spec-10 replaces this with `registry.get_embedding_provider()`. The registry is available on
`app.state.registry`; it must be passed into the ingestion pipeline entry point.

**Finding**: The ingestion pipeline is triggered by `POST /api/ingest`. The `BatchEmbedder` is
instantiated with a fixed provider. Constructor injection is the cleanest path:
`BatchEmbedder(embedding_provider=registry.get_embedding_provider())`.

**Alternatives considered**:
- Access `app.state.registry` inside `embedder.py` directly: Requires passing the app reference;
  less testable than constructor injection.

---

## R9: Model Listing Enrichment (Step 7)

**Decision**: `backend/api/models.py` calls `_fetch_ollama_models()`. Spec-10 additionally queries
each cloud provider's DB row for non-null `api_key_encrypted`. When present, append the provider's
configured model to the `GET /api/models/llm` response. Use the `model` field from `config_json`.

**Finding**: The response is `list[ModelInfo]`. Cloud provider entries will have
`provider="openrouter"/"openai"/"anthropic"`, `name=config["model"]`, and optional `context_length`.
This is additive — no existing entries are removed.

**Alternatives considered**:
- Live API calls to cloud providers to enumerate models: Too slow (network round-trip), requires key.
  Use stored config_json model field instead.

---

## R10: No NEEDS CLARIFICATION Remaining

All technical unknowns are resolved:
- ✅ Embed model-agnostic param: `model: str | None = None` (R1)
- ✅ Retry-once scope: cloud providers only (R4)
- ✅ 429 handling: `ProviderRateLimitError` in `base.py`, no fallback (R5)
- ✅ Schema migration: `ALTER TABLE ... ADD COLUMN` (R6)
- ✅ Agent wiring: GitNexus impact analysis required (R7)
- ✅ Embedder wiring: constructor injection (R8)
