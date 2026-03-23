# Tasks: Provider Architecture

**Input**: Design documents from `/specs/010-provider-architecture/`
**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅ | quickstart.md ✅

**Organization**: Tasks grouped by user story. All seven spec-10 implementation items are covered.
Tests are included — required by the A5 quality-engineer wave in the Agent Teams plan.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to

## Agent Teams Wave Map

| Wave | Agents | Tasks |
|------|--------|-------|
| Wave 1 | A1 (backend-architect, Opus) | T003–T007 |
| Wave 2 parallel | A2 (python-expert, Sonnet) + A3 (python-expert, Sonnet) | T008–T010 |
| Wave 3 | A4 (python-expert, Sonnet) | T011–T025 |
| Wave 4 | A5 (quality-engineer, Sonnet) | T026–T034 |

---

## Phase 1: Setup

**Purpose**: Establish baseline and confirm starting state.

- [x] T001 Run spec-09 baseline gate check: `zsh scripts/run-tests-external.sh -n spec10-baseline tests/` — poll until PASSED, read summary
- [x] T002 Read design artifacts: `specs/010-provider-architecture/plan.md`, `specs/010-provider-architecture/quickstart.md`, `specs/010-provider-architecture/contracts/provider-contract.md`, `specs/010-provider-architecture/contracts/schema-migration-contract.md`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core changes that all user stories depend on. Wave 1 (A1) is responsible for this phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T003 Add `class ProviderRateLimitError(Exception)` with `provider: str` attribute to `backend/providers/base.py`
- [x] T004 Update `EmbeddingProvider.embed()` signature to `embed(self, texts: list[str], model: str | None = None)` in `backend/providers/base.py`
- [x] T005 Update `EmbeddingProvider.embed_single()` signature to `embed_single(self, text: str, model: str | None = None)` in `backend/providers/base.py`
- [x] T006 Add `ALTER TABLE query_traces ADD COLUMN provider_name TEXT` migration (with OperationalError guard for idempotency) in `SQLiteDB.initialize()` in `backend/storage/sqlite_db.py`
- [x] T007 Update `SQLiteDB.create_query_trace()` to accept `provider_name: str | None = None` and include it in the INSERT statement in `backend/storage/sqlite_db.py`

**Checkpoint (Wave 1 gate)**: Run `zsh scripts/run-tests-external.sh -n spec10-gate-wave1 tests/` — must pass with 0 new failures before Wave 2 begins.

---

## Phase 3: User Story 1 — Switch Active LLM Provider (Priority: P1) 🎯 MVP

**Goal**: Enable operators to switch from Ollama to cloud LLM providers at runtime. Cloud providers handle transient errors with retry-once and surface rate-limit errors directly.

**Independent Test**: Set `openrouter` as active provider with a valid API key, send a chat request, confirm response streams from OpenRouter. Remove the key, confirm fallback to Ollama.

### Implementation — Wave 2 parallel (A2 handles T008, A3 handles T009–T010)

- [x] T008 [P] [US1] Update `OllamaEmbeddingProvider.embed_single()` to use `effective_model = model or self.model` when building API payload in `backend/providers/ollama.py`
- [x] T009 [P] [US1] Add `_call_with_retry()` helper and `ProviderRateLimitError` raising on HTTP 429 to **both** `OpenRouterLLMProvider.generate()` and `OpenRouterLLMProvider.generate_stream()` in `backend/providers/openrouter.py` — retry applies to all outbound calls, not only streaming (see contracts/provider-contract.md for retry table)
- [x] T010 [P] [US1] Add identical retry + 429 handling to **both** `generate()` and `generate_stream()` in `OpenAILLMProvider` (`backend/providers/openai.py`) and `AnthropicLLMProvider` (`backend/providers/anthropic.py`)

**Checkpoint (Wave 2 gate)**: Run `zsh scripts/run-tests-external.sh -n spec10-gate-wave2 tests/` — must pass with 0 new failures before Wave 3 begins.

### Implementation — Wave 3 (A4)

- [x] T011 [US1] Add `async def get_active_langchain_model(self, db: SQLiteDB) -> BaseChatModel` method to `ProviderRegistry` in `backend/providers/registry.py` — returns `ChatOllama`, `ChatOpenAI` (for openrouter/openai), or `ChatAnthropic` based on active provider row. Uses lazy imports (`from langchain_ollama import ChatOllama` etc.) to avoid module-level coupling. Decrypts API key via `self._key_manager.decrypt()`. Falls back to `ChatOllama` on unknown provider name.
- [x] T012 [US1] Add `langchain-ollama`, `langchain-openai`, `langchain-anthropic` to `requirements.txt` — these are required by the new `get_active_langchain_model()` method. Pin to ranges compatible with existing `langchain >= 1.2.10`.
- [x] T013 [US1] Update `backend/api/chat.py` to wire the full graph config: (1) call `active = await db.get_active_provider()` and capture `provider_name = active["name"]`; (2) call `langchain_llm = await registry.get_active_langchain_model(db)` to get the LangChain BaseChatModel; (3) build config dict with `{"configurable": {"thread_id": session_id, "llm": langchain_llm, "tools": app.state.research_tools}}`; (4) pass `provider_name=provider_name` to `db.create_query_trace()`. This wires the entire agent layer — nodes.py is NOT edited.
- [x] T014 [US1] Add FastAPI exception handler for `ProviderRateLimitError` in `backend/main.py` — return HTTP 429 with `{"type": "error", "message": "...", "code": "rate_limit"}` response

**Checkpoint (Wave 3 gate)**: Run `zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/` — must pass with 0 regressions in spec-02/03/04 conversation graph tests.

---

## Phase 4: User Story 2 — Store Cloud Provider API Keys Securely (Priority: P2)

**Goal**: Confirm that API keys are encrypted at rest, never leak in responses/logs, and `KeyManager` raises `ValueError` on missing env var.

**Independent Test**: Submit a key via `PUT /api/providers/openrouter/key`, confirm `has_key: true` in `GET /api/providers` but no plaintext key. Delete the key, confirm `has_key: false`.

> **Note**: `KeyManager` and the provider key endpoints are already implemented from spec-08. This phase verifies correctness and adds missing edge-case coverage.

- [x] T015 [US2] Verify `KeyManager.is_valid_key()` returns `True` for valid ciphertext and `False` for garbage in `backend/providers/key_manager.py` — fix if broken
- [x] T016 [US2] Verify `app.state.key_manager = None` graceful degradation when `EMBEDINATOR_FERNET_KEY` is absent — `PUT /api/providers/{name}/key` must return HTTP 503, not 500, in `backend/api/providers.py`
- [x] T017 [US2] Verify `structlog` context never binds a raw API key — scan `backend/api/providers.py` and `backend/providers/registry.py` log call sites; add key masking if any log statement could include a plaintext key

---

## Phase 5: User Story 3 — Inspect Provider Health (Priority: P3)

**Goal**: Operators can query provider reachability. Health checks complete within 5 seconds.

**Independent Test**: Call `GET /api/providers/health` (or equivalent health status field), confirm Ollama shows reachable when running and unreachable when stopped. Response arrives within 5 seconds.

- [x] T018 [US3] Verify all `health_check()` implementations have a `timeout=5.0` guard in `backend/providers/ollama.py`, `backend/providers/openrouter.py`, `backend/providers/openai.py`, `backend/providers/anthropic.py` — add `httpx.AsyncClient(timeout=5.0)` where missing
- [x] T019 [US3] Add `GET /api/providers/health` endpoint in `backend/api/providers.py` that calls `health_check()` on each configured provider and returns `{"provider": name, "reachable": bool}` list — use `asyncio.gather()` with 5-second individual timeouts
- [x] T020 [US3] Register the new health route in `backend/api/providers.py` router (already imported in `main.py` via `api_router.include_router(providers_router)`)

---

## Phase 6: User Story 4 — Browse Available Models (Priority: P4)

**Goal**: `GET /api/models/llm` returns cloud provider models alongside Ollama models when their API keys are stored.

**Independent Test**: Store an OpenRouter key, call `GET /api/models/llm`, confirm the configured model appears with `provider: "openrouter"`. Remove the key, confirm the entry disappears.

- [x] T021 [US4] Update `backend/api/models.py` to query provider DB rows after `_fetch_ollama_models()` — for each cloud provider row with non-null `api_key_encrypted`, append `ModelInfo(name=config["model"], provider=provider_name)` to the LLM model list
- [x] T022 [US4] Confirm `GET /api/models/embed` is unchanged (Ollama embedding models only, no cloud embedding providers in spec-10)

---

## Phase 7: User Story 5 — Use Local Embeddings Without Configuration (Priority: P5)

**Goal**: Out-of-the-box document ingestion and vector search work via local Ollama embeddings. The ingestion pipeline uses the registry to obtain its embedding provider.

**Independent Test**: Start with no cloud credentials. Ingest a document. Confirm embeddings are generated via `OllamaEmbeddingProvider`. Confirm `embed(texts, model="nomic-embed-text")` works as a model override.

- [x] T023 [US5] Update `BatchEmbedder.__init__()` in `backend/ingestion/embedder.py` to accept `embedding_provider: EmbeddingProvider` via constructor injection instead of instantiating `OllamaEmbeddingProvider` directly
- [x] T024 [US5] Update the `BatchEmbedder` construction site in `backend/api/ingest.py` (or wherever `BatchEmbedder` is instantiated) to pass `registry.get_embedding_provider()` from `app.state.registry`
- [x] T025 [US5] Verify `OllamaEmbeddingProvider.embed(texts, model="nomic-embed-text")` correctly uses the override model name in the API payload in `backend/providers/ollama.py`

---

## Phase 8: Testing & Validation (Wave 4 — A5)

**Purpose**: Comprehensive tests and regression gate for all spec-10 changes.

- [x] T026 [P] Write unit tests for retry-once (5xx triggers one retry, re-raises on second failure) and 429 raises `ProviderRateLimitError` for all three cloud providers in `tests/unit/test_providers.py`
- [x] T027 [P] Write unit tests for `EmbeddingProvider` model-agnostic parameter: `embed(texts)` uses `self.model`; `embed(texts, model="override")` uses override in `tests/unit/test_providers.py`
- [x] T028 [P] Write unit tests for `SQLiteDB.create_query_trace()` with `provider_name` parameter and verify the column exists post-migration in `tests/unit/test_sqlite_db.py`
- [x] T029 [P] Write unit tests for `GET /api/providers/health` endpoint: Ollama reachable, cloud provider unreachable (key absent), timeout returns unreachable in `tests/unit/test_providers_router.py`
- [x] T030 [P] Write unit tests for enriched `GET /api/models/llm`: cloud provider model appears when key stored, disappears when key absent in `tests/unit/test_providers_router.py`
- [x] T031 Write integration test for full ProviderRegistry flow: `initialize()` → `get_active_llm(db)` returns `OllamaLLMProvider` by default → `set_active_provider(db, "openrouter", config)` → `get_active_llm(db)` returns `OpenRouterLLMProvider` in `tests/integration/test_providers_integration.py`
- [x] T032 Write integration test for `BatchEmbedder` with injected `OllamaEmbeddingProvider`: ingest one document, confirm embeddings non-empty in `tests/integration/test_providers_integration.py`
- [x] T033 Run `gitnexus_detect_changes({scope: "all"})` — confirm changed symbols match expected scope (providers/, storage/sqlite_db.py, ingestion/embedder.py, agent/nodes.py, api/chat.py, api/models.py, api/providers.py)
- [x] T034 Run final gate: `zsh scripts/run-tests-external.sh -n spec10-gate-final tests/` — poll until PASSED; read `Docs/Tests/spec10-gate-final.summary`; confirm 0 new failures vs spec-09 baseline

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2; Wave 2 tasks T008–T010 can run in parallel; T011–T014 run after Wave 2 gate
- **Phase 4 (US2)**: Depends on Phase 2; can run in parallel with Phase 3
- **Phase 5 (US3)**: Depends on Phase 2; can run in parallel with Phases 3–4
- **Phase 6 (US4)**: Depends on Phase 2; T021 also reads from Phase 2's provider DB row logic
- **Phase 7 (US5)**: Depends on Phase 2 (T004–T005 extend base interface that T023–T025 depend on)
- **Phase 8 (Testing)**: Depends on all implementation phases; T026–T032 can run in parallel

### User Story Dependencies

- **US1 (P1)**: Requires T003 (`ProviderRateLimitError`), T006–T007 (query_traces) from Phase 2
- **US2 (P2)**: Requires T003 (`ProviderRateLimitError`) for 429 handling
- **US3 (P3)**: Requires Phase 2 foundation only
- **US4 (P4)**: Requires Phase 2 foundation only
- **US5 (P5)**: Requires T004–T005 (model-agnostic embed signature) from Phase 2

### Task-Level Dependencies Within US1

```
T003 (ProviderRateLimitError) → T009, T010
T004, T005 → T008
T006, T007 → T013
T011 (registry.py factory method) → T013 (chat.py wiring uses it)
T009, T010 complete → Wave 2 gate → T011, T012, T013, T014
```

### Parallel Opportunities

**Wave 2** (after Wave 1 gate):
- T008 (A2: OllamaEmbeddingProvider) runs in parallel with T009–T010 (A3: cloud providers)

**Phase 4–7** (after Phase 2):
- US2 (T015–T017), US3 (T018–T020), US4 (T021–T022), US5 (T023–T025) can all run in parallel

**Wave 4 tests** (after all implementation):
- T026, T027, T028, T029, T030 can all run in parallel (different files/concerns)

---

## Parallel Example: Wave 2

```
# A2 (separate tmux pane):
"Read instruction file at Docs/PROMPTS/spec-10-providers/agents/A2-python-expert-ollama.md FIRST, then execute T008"

# A3 (separate tmux pane):
"Read instruction file at Docs/PROMPTS/spec-10-providers/agents/A3-python-expert-cloud.md FIRST, then execute T009, T010"
```

## Parallel Example: User Stories after Phase 2

```
# Can run concurrently:
US3 tasks: T018 → T019 → T020
US4 tasks: T021 → T022
US5 tasks: T023 → T024 → T025
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Baseline verification
2. Complete Phase 2: Foundational changes (T003–T007) — **Wave 1**
3. Wave 2 gate check
4. Complete Phase 3: US1 tasks (T008–T014) — **Waves 2 and 3**
5. **STOP and VALIDATE**: Run `zsh scripts/run-tests-external.sh -n spec10-gate-us1 tests/`
6. Cloud provider switching is now operational end-to-end

### Incremental Delivery

1. Phase 1 + Phase 2 → foundation stable
2. Phase 3 (US1) → cloud LLM switching works → **MVP**
3. Phase 4 (US2) → key security verified
4. Phase 5 (US3) → health inspection operational
5. Phase 6 (US4) → model browsing enriched
6. Phase 7 (US5) → local embeddings zero-config via registry
7. Phase 8 → full test coverage, final gate

### Agent Teams Execution

Instruction files location: `Docs/PROMPTS/spec-10-providers/agents/`

| Agent | Instruction file | Wave | Tasks |
|-------|-----------------|------|-------|
| A1 | `A1-backend-architect.md` | 1 | T003–T007 |
| A2 | `A2-python-expert-ollama.md` | 2 | T008 |
| A3 | `A3-python-expert-cloud.md` | 2 | T009–T010 |
| A4 | `A4-python-expert-wiring.md` | 3 | T011–T025 |
| A5 | `A5-quality-engineer.md` | 4 | T026–T034 |

**Spawn rule**: Always pass `"Read your instruction file at <path> FIRST, then execute all assigned tasks"` as the spawn prompt.

---

## Testing Rules (MANDATORY — all agents)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log

Wave gate checks:
  zsh scripts/run-tests-external.sh -n spec10-gate-wave1 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-wave2 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-wave3 tests/
  zsh scripts/run-tests-external.sh -n spec10-gate-final tests/
```

Baseline: 946 tests passing, 39 known pre-existing failures unchanged from spec-09.

---

## Notes

- [P] tasks use different files — no state conflicts
- [Story] label maps each task to its user story for traceability
- T011 (GitNexus impact analysis) is a mandatory safety gate — do NOT skip
- `nodes.py` is UNTOUCHED — LLM is injected via `config["configurable"]["llm"]` in chat.py
- `registry.py` gains `get_active_langchain_model()` — two LLM access paths by design (LLMProvider for httpx, BaseChatModel for agent nodes)
- `ProviderRateLimitError` goes in `base.py` (spec-12 will formalize hierarchy later)
- Migration in T006 is idempotent — safe to re-deploy
- US2 tasks (T015–T017) validate existing spec-08 behavior; fix if broken
