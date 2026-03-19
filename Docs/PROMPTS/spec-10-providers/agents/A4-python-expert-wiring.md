# Agent A4: Python Expert — Wiring

## Agent: python-expert | Model: claude-sonnet-4-6 | Wave: 3

## Role

You are the Wave 3 wiring agent for spec-10. You connect the provider layer to the rest of
the application: LangChain factory method, chat endpoint config wiring, ingestion pipeline,
model listing, health endpoint, and security verification.

**Key architectural decision (R7)**: The agent nodes use LangChain `BaseChatModel` methods
(`ainvoke`, `with_structured_output`, `bind_tools`). A new `get_active_langchain_model(db)`
factory method on `ProviderRegistry` returns the appropriate LangChain model. The result is
passed into the graph via `config["configurable"]["llm"]` in `chat.py`. **nodes.py is NOT
edited** — the wiring happens entirely in `registry.py` and `chat.py`.

Wave 2 must be complete (gate passed) before you start.

---

## Assigned Tasks

### US1 — Switch Active LLM Provider

**T011** — Add `async def get_active_langchain_model(self, db: SQLiteDB) -> BaseChatModel`
to `ProviderRegistry` in `backend/providers/registry.py`. Implementation:

```python
async def get_active_langchain_model(self, db: SQLiteDB):
    """Return a LangChain BaseChatModel for the active provider.

    Used by agent graph nodes (ainvoke, with_structured_output, bind_tools).
    Coexists with get_active_llm() which returns LLMProvider for httpx streaming.
    """
    active = await db.get_active_provider()
    if not active or active["name"] == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=self._settings.ollama_base_url,
            model=self._settings.default_llm_model,
        )

    config = json.loads(active["config_json"])
    model = config.get("model", "")
    name = active["name"]

    # Decrypt API key (in-memory only, discarded after constructor call)
    if self._key_manager and active.get("api_key_encrypted"):
        key = self._key_manager.decrypt(active["api_key_encrypted"])
    else:
        # No key available — fall back to Ollama
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=self._settings.ollama_base_url,
            model=self._settings.default_llm_model,
        )

    if name in ("openrouter", "openai"):
        from langchain_openai import ChatOpenAI
        base_url = ("https://openrouter.ai/api/v1" if name == "openrouter"
                     else "https://api.openai.com/v1")
        return ChatOpenAI(api_key=key, model=model, base_url=base_url)
    elif name == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=key, model=model)

    # Unknown provider — fall back to Ollama
    from langchain_ollama import ChatOllama
    return ChatOllama(
        base_url=self._settings.ollama_base_url,
        model=self._settings.default_llm_model,
    )
```

**Important**: Use lazy imports (inside the method body) to avoid module-level LangChain coupling.
Read the existing `get_active_llm()` method first to understand the active provider resolution
pattern — mirror the same if/elif/else structure. Verify the attribute names (`self._settings`,
`self._key_manager`) by reading the `__init__` body.

**T012** — Add `langchain-ollama`, `langchain-openai`, `langchain-anthropic` to `requirements.txt`.
Pin to ranges compatible with the existing `langchain >= 1.2.10` constraint.

**T013** — Update `backend/api/chat.py` to wire the full graph config. In the `generate()`
function (or wherever `graph.astream()` is called):

```python
# 1. Resolve active provider name for query trace
active = await db.get_active_provider()
provider_name = active["name"] if active else "ollama"

# 2. Get LangChain model for agent nodes
registry = request.app.state.registry
langchain_llm = await registry.get_active_langchain_model(db)

# 3. Build full config dict (was only thread_id before)
config = {
    "configurable": {
        "thread_id": session_id,
        "llm": langchain_llm,
        "tools": request.app.state.research_tools,
    }
}

# 4. Pass to graph
async for event in conversation_graph.astream(input_state, config=config):
    ...

# 5. Record provider_name in trace
await db.create_query_trace(..., provider_name=provider_name)
```

Read the current `chat.py` to understand the existing flow. The key change is expanding the
config dict from `{"configurable": {"thread_id": ...}}` to include `llm` and `tools`.

**T014** — Add a FastAPI exception handler for `ProviderRateLimitError` in `backend/main.py`
returning HTTP 429 with `{"type": "error", "message": "...", "code": "rate_limit"}`.

### US2 — Verify Key Security

**T015** — Verify `KeyManager.is_valid_key()` correctness in `backend/providers/key_manager.py`.
Read the method body; fix only if genuinely broken. Most likely this is a read-only task.

**T016** — Verify `app.state.key_manager = None` gracefully degrades to HTTP 503 (not 500)
in `PUT /api/providers/{name}/key` in `backend/api/providers.py`. Fix only if the status code
is wrong.

**T017** — Scan log call sites in `backend/api/providers.py` and `backend/providers/registry.py`.
Verify no `structlog` calls bind a raw `api_key` value. If any do, add masking.

### US3 — Provider Health Endpoint

**T018** — Verify all four `health_check()` implementations use `httpx.AsyncClient(timeout=5.0)`:
`backend/providers/ollama.py`, `openrouter.py`, `openai.py`, `anthropic.py`. Add where missing.

**T019** — Add `GET /api/providers/health` endpoint in `backend/api/providers.py`. Use
`asyncio.gather()` to call all `health_check()` concurrently. Providers with no key stored
return `reachable: False` without calling `health_check()`. Never raise — catch all exceptions.
See `contracts/provider-contract.md` for the `ProviderHealthSchema` contract.

**T020** — Verify the health route is included in the providers.py router.

### US4 — Model Listing Enrichment

**T021** — Update `list_llm_models()` in `backend/api/models.py` to query cloud provider DB
rows. For each with non-null `api_key_encrypted`, append `ModelInfo(name=config["model"],
provider=provider_name)` to the response.

**T022** — Confirm `list_embed_models()` is unchanged (Ollama only). Read-only task.

### US5 — BatchEmbedder Wiring

**T023** — Update `BatchEmbedder.__init__()` in `backend/ingestion/embedder.py` to accept
`embedding_provider: EmbeddingProvider` via constructor injection.

**T024** — Update the `BatchEmbedder` construction site to pass
`registry.get_embedding_provider()` from `request.app.state.registry`.

**T025** — Verify `OllamaEmbeddingProvider.embed()` correctly uses the model override.
Read-only task — fix only if A2's implementation has a bug.

---

## File Scope

You may touch these files:
- `backend/providers/registry.py` (add `get_active_langchain_model()` — T011)
- `backend/api/chat.py` (wire config dict — T013)
- `backend/main.py` (exception handler — T014)
- `backend/providers/key_manager.py` (verify only — T015)
- `backend/api/providers.py` (verify + health endpoint — T016, T017, T019, T020)
- `backend/api/models.py` (enrich — T021, T022)
- `backend/ingestion/embedder.py` (constructor injection — T023)
- `backend/api/ingest.py` (injection site — T024)
- `requirements.txt` (add LangChain packages — T012)

**Do NOT touch**:
- `backend/agent/nodes.py` — the wiring is done via config["configurable"], not code changes
- `backend/agent/research_nodes.py` — already reads from config["configurable"]["llm"]
- `backend/providers/base.py` — A1 already completed
- `backend/providers/openrouter.py`, `openai.py`, `anthropic.py` — A3 already completed
- Any test files — A5 handles tests in Wave 4

---

## Critical Constraints

- **nodes.py is NOT edited** — LLM injection happens via config["configurable"]["llm"]
- Do NOT add `list_models()` to any provider class
- Do NOT change `ProviderRegistry.__init__()` or any existing methods
- Do NOT use env var `API_KEY_ENCRYPTION_SECRET` — the correct var is `EMBEDINATOR_FERNET_KEY`
- T015, T016, T017, T022, T025 are verify-only — make changes only if genuinely broken
- LangChain imports in `get_active_langchain_model()` MUST be lazy (inside method body)

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## Gate Check

After completing T011-T025, run the Wave 3 gate:

```bash
zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/
```

Poll `Docs/Tests/spec10-gate-wave3.status` until `PASSED` or `FAILED`.
The gate specifically checks for 0 regressions in spec-02/03/04 conversation graph tests.
If `FAILED`, read the summary, fix the regressions, and re-run before reporting done.

When the gate passes, notify the Orchestrator that Wave 3 is complete.
