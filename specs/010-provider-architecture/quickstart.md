# Quickstart: Provider Architecture (spec-10)

**Date**: 2026-03-16
**For**: Developers implementing or reviewing this feature

---

## What This Feature Does

Spec-10 makes the existing provider scaffolding fully operational. After implementation:
- LangGraph agent nodes call `ProviderRegistry.get_active_llm(db)` instead of hard-coded ChatOllama.
- Cloud providers (OpenRouter, OpenAI, Anthropic) retry once on transient errors; HTTP 429 bubbles up.
- Every query trace records which provider handled the request.
- The embedding interface is model-agnostic — callers pass an optional model name per call.
- The ingestion pipeline gets its embedding provider from the registry, not a hard-coded class.

---

## Prerequisites

1. **Branch**: `010-provider-architecture` (already checked out)
2. **Environment variable**: `EMBEDINATOR_FERNET_KEY` — a valid pre-generated Fernet key
   ```bash
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Add this to `.env` (never commit to git). Without it, `KeyManager` raises `ValueError` at startup
   and `app.state.key_manager = None` (key endpoints return 503; Ollama works regardless).
3. **Services running**: `docker compose up qdrant ollama` (backend + frontend optional for unit tests)

---

## Implementation Sequence

Follow these steps in order. Each step has its own gate check.

### Step 1: Base Interface Extension (base.py + OllamaEmbeddingProvider)

**What to do**: Add `model: str | None = None` to `EmbeddingProvider.embed()` and `embed_single()`.
Update `OllamaEmbeddingProvider` to use `model or self.model` in its API payload.

**Files**: `backend/providers/base.py`, `backend/providers/ollama.py`

**Impact**: Low — existing callers pass no `model` argument; change is backward-compatible.

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step1 tests/unit/test_providers.py
```

---

### Step 2: Retry + Rate-Limit Handling (cloud providers)

**What to do**: Add `_call_with_retry()` or inline retry loop to `OpenRouterLLMProvider`,
`OpenAILLMProvider`, `AnthropicLLMProvider`. Raise `ProviderRateLimitError` on 429.
Define `ProviderRateLimitError` in `backend/providers/base.py`.

**Files**: `backend/providers/base.py`, `backend/providers/openrouter.py`,
`backend/providers/openai.py`, `backend/providers/anthropic.py`

**Retry logic summary**:
| Condition | Action |
|-----------|--------|
| HTTP 429 | Raise `ProviderRateLimitError` immediately |
| HTTP 5xx or Timeout | Retry once; re-raise after second failure |
| HTTP 4xx (not 429) | Re-raise immediately |

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step2 tests/unit/test_providers.py
```

---

### Step 3: query_traces Schema Migration

**What to do**: Add `provider_name TEXT` column to `query_traces` via
`ALTER TABLE ... ADD COLUMN` in `SQLiteDB.initialize()`. Update `create_query_trace()` signature.

**Files**: `backend/storage/sqlite_db.py`

**Migration is idempotent**: Running on an already-migrated DB silently passes.

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step3 tests/unit/test_sqlite_db.py
```

---

### Step 4: chat.py Provider Name Propagation

**What to do**: After resolving the active LLM via `app.state.registry.get_active_llm(db)`,
extract the active provider name (e.g., `"ollama"`) and pass it to `create_query_trace(...,
provider_name=provider_name)`.

**Files**: `backend/api/chat.py`

**Note**: The provider name is the registry key (e.g., `"ollama"`), not the model name string.

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step4 tests/unit/test_chat_api.py
```

---

### Step 5: Agent Node Wiring (HIGH RISK — GitNexus required)

**What to do**: Update LangGraph node functions in `backend/agent/nodes.py` to call
`await registry.get_active_llm(db)` instead of constructing a hard-coded `ChatOllama` instance.

**BEFORE TOUCHING nodes.py**:
```
gitnexus_impact({target: "nodes", direction: "upstream"})
```
Review the blast radius. If risk is HIGH or CRITICAL, report to user and wait for acknowledgement.

**Files**: `backend/agent/nodes.py`

**After editing**:
```
gitnexus_detect_changes({scope: "staged"})
```
Verify only expected files changed.

**Verify (full regression)**:
```bash
zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/
```
Expected: 0 new failures relative to spec-09 baseline (946 passing, 39 known pre-existing).

---

### Step 6: BatchEmbedder Wiring

**What to do**: Replace direct `OllamaEmbeddingProvider(...)` instantiation in
`backend/ingestion/embedder.py` with constructor injection of `EmbeddingProvider`.
Pass `registry.get_embedding_provider()` from the ingestion entry point.

**Files**: `backend/ingestion/embedder.py`, `backend/api/ingest.py` (injection point)

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step6 tests/unit/test_ingestion_pipeline.py
```

---

### Step 7: Model Listing Enrichment

**What to do**: In `backend/api/models.py`, after fetching Ollama models, query each cloud
provider's DB row. If `api_key_encrypted` is non-null, append a `ModelInfo` entry with
`name=config["model"]` and `provider=provider_name`.

**Files**: `backend/api/models.py`

**Verify**:
```bash
zsh scripts/run-tests-external.sh -n spec10-step7 tests/unit/test_providers_router.py
```

---

## Final Gate Check

After all steps are complete, run the full test suite:
```bash
zsh scripts/run-tests-external.sh -n spec10-gate-final tests/
```
Poll: `cat Docs/Tests/spec10-gate-final.status`
Read: `cat Docs/Tests/spec10-gate-final.summary`

**Pass criteria**: 0 new failures. 39 known pre-existing failures unchanged.

---

## Key Files Reference

| File | Role | Action |
|------|------|--------|
| `backend/providers/base.py` | ABCs + `ProviderRateLimitError` | Extend embed signatures; add exception |
| `backend/providers/ollama.py` | Ollama implementations | Update `embed()` + `embed_single()` |
| `backend/providers/openrouter.py` | OpenRouter | Add retry + 429 |
| `backend/providers/openai.py` | OpenAI | Add retry + 429 |
| `backend/providers/anthropic.py` | Anthropic | Add retry + 429 |
| `backend/storage/sqlite_db.py` | DB layer | Migration + `create_query_trace()` update |
| `backend/ingestion/embedder.py` | Ingestion | Constructor injection |
| `backend/agent/nodes.py` | LangGraph nodes | Wire `get_active_llm()` — GitNexus first |
| `backend/api/chat.py` | Chat endpoint | Pass `provider_name` to trace |
| `backend/api/models.py` | Model listing | Cloud provider enrichment |

---

## Testing Rules (MANDATORY)

**NEVER run pytest inside Claude Code.** Always use:
```bash
zsh scripts/run-tests-external.sh -n <name> <target>
```

| Output file | Meaning |
|-------------|---------|
| `Docs/Tests/<name>.status` | `RUNNING` / `PASSED` / `FAILED` / `ERROR` |
| `Docs/Tests/<name>.summary` | ~20 lines, token-efficient summary |
| `Docs/Tests/<name>.log` | Full pytest output |
