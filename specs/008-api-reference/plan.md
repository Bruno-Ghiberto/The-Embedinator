# Implementation Plan: API Reference — HTTP Interface Layer

**Branch**: `008-api-reference` | **Date**: 2026-03-15 | **Spec**: `specs/008-api-reference/spec.md`
**Input**: Feature specification from `specs/008-api-reference/spec.md`

---

## Summary

Spec 08 exposes The Embedinator's capabilities as a unified HTTP interface. It is a FastAPI surface layer — all business logic lives in specs 02–07. The work is:
1. Extend `chat.py` NDJSON events from 4 → 10 types
2. Create 3 new routers: `ingest.py`, `models.py`, `settings.py`
3. Rewrite `documents.py` (clean up legacy Phase 1 code, align to spec-07)
4. Extend `providers.py`, `traces.py`, `health.py`, `collections.py`
5. Extend `middleware.py` (add 4th rate limit category), `schemas.py`, `config.py`, `main.py`

---

## Technical Context

**Language/Version**: Python 3.14+, TypeScript 5.7 (frontend consumer, not in this spec)
**Primary Dependencies**: FastAPI >= 0.135, Pydantic v2 >= 2.12, aiosqlite >= 0.21, cryptography >= 44.0, httpx >= 0.28, structlog >= 24.0, LangGraph >= 1.0.10
**Storage**: SQLite WAL mode (`data/embedinator.db`) via spec-07 `SQLiteDB`; Qdrant via spec-07 `QdrantStorage`; in-memory rate limit counters (per-IP, sliding window)
**Testing**: pytest via `scripts/run-tests-external.sh` (NEVER run pytest inside Claude Code)
**Target Platform**: Linux server (Docker Compose, 4 services)
**Project Type**: Web service (FastAPI REST + NDJSON streaming)
**Performance Goals**: First token < 500ms (SC-002); health endpoint < 50ms (constitution); chat round-trip < 2s (SC-003); 10 concurrent streams without event loss (SC-010)
**Constraints**: No API version prefix; no authentication; rate limits per client IP; settings changes apply to new sessions only; traces retained indefinitely
**Scale/Scope**: 1–5 concurrent users (Constitution VII)

---

## Constitution Check

*Evaluated against `.specify/memory/constitution.md` v1.0.0*

| Principle | Status | Notes |
|-----------|--------|-------|
| **I. Local-First Privacy** | ✅ PASS | No authentication added. Cloud providers remain opt-in. No mandatory outbound calls. |
| **II. Three-Layer Agent Architecture** | ✅ PASS | `chat.py` delegates to `ConversationGraph` — the three-layer structure (ConversationGraph → ResearchGraph → MetaReasoningGraph) is preserved. API layer does not modify the graph. |
| **III. Retrieval Pipeline Integrity** | ✅ PASS | API layer is a surface only. No changes to chunking, BM25, reranking, or parent/child storage. |
| **IV. Observability from Day One** | ✅ PASS | Every `POST /api/chat` call writes to `query_traces` via `db.create_query_trace()`. Trace recording is mandatory and non-optional. |
| **V. Secure by Design** | ✅ PASS | Provider keys never returned (FR-018, SC-005). Fernet encryption via `app.state.key_manager`. Parameterized SQL throughout. Rate limits enforced. CORS configured. File upload validated. |
| **VI. NDJSON Streaming Contract** | ⚠️ MINOR CONFLICT | Constitution says final frame type is `metadata`; spec FR-014 says `done`. **Resolution**: Spec supersedes — coherence review confirmed `done` is the correct target type. No ADR amendment needed (this is a spec clarification, not an ADR reversal). |
| **VII. Simplicity by Default** | ✅ PASS | No new Docker services. Using existing SQLiteDB/QdrantStorage/KeyManager. In-memory rate limiter (no Redis). YAGNI applied throughout. |

**Constitution Gate**: PASS (one minor noted conflict, resolved by spec authority)

### Complexity Tracking

| Item | Status |
|------|--------|
| Rate limit: 120/min general (spec) vs 100/min (constitution) | Spec supersedes; 120 is the blueprint target. No violation. |
| Final NDJSON frame: `done` (spec) vs `metadata` (constitution) | Spec supersedes; coherence review (2026-03-14) established `done` as correct target. |

---

## Project Structure

### Documentation (this feature)

```text
specs/008-api-reference/
├── plan.md              # This file
├── research.md          # Phase 0 output — 8 research decisions
├── data-model.md        # Phase 1 output — 8 entities, NDJSON types, error codes
├── quickstart.md        # Phase 1 output — dev setup, testing, pitfalls
├── contracts/
│   └── api-endpoints.md # Phase 1 output — full HTTP contract definitions
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code

```text
backend/
  api/
    chat.py              # EXISTS — extend: 10 NDJSON event types
    collections.py       # EXISTS — extend: name regex, cascade delete
    documents.py         # EXISTS — rewrite: remove legacy ingest, align schemas
    ingest.py            # NEW — POST + GET ingestion endpoints
    models.py            # NEW — GET /models/llm + /models/embed
    providers.py         # EXISTS — extend: PUT/DELETE key, GET models
    settings.py          # NEW — GET + PUT /settings
    traces.py            # EXISTS — extend: session filter, /stats, pagination
    health.py            # EXISTS — rewrite: per-service latency_ms schema
    __init__.py          # EXISTS — update exports
  agent/
    schemas.py           # EXISTS — extend: 10+ new Pydantic models
  main.py                # EXISTS — extend: register new routers
  middleware.py          # EXISTS — extend: 4th rate limit category, 120 general
  config.py              # EXISTS — extend: rate limit fields

tests/
  unit/
    test_schemas_api.py             # NEW
    test_middleware_rate_limit.py   # NEW
    test_chat_ndjson.py             # NEW
    test_ingest_router.py           # NEW
    test_collections_router.py      # NEW (may exist — verify)
    test_documents_router.py        # NEW
    test_models_router.py           # NEW
    test_providers_router.py        # NEW
    test_settings_router.py         # NEW
    test_traces_router.py           # NEW
    test_health_router.py           # NEW
  integration/
    test_api_integration.py         # NEW
    test_ndjson_streaming.py        # NEW
    test_rate_limiting.py           # NEW

Docs/PROMPTS/spec-08-api/
  08-specify.md          # Context prompt used by /speckit.specify (coherence-reviewed)
  08-plan.md             # Implementation context prompt for agent teams
  agents/                # Agent instruction files (created by /speckit.tasks)
    A1-schemas-config.md
    A2-middleware.md
    A3-chat-ndjson.md
    A4-ingest-router.md
    A5-documents-collections.md
    A6-models-providers-settings.md
    A7-traces-health-wiring.md
    A8-quality-tests.md
```

**Structure Decision**: Web application backend. Uses existing `backend/api/` router directory. No new top-level directories needed.

---

## Key Design Decisions

### D1: No new SQLiteDB convenience methods for chat tracing

**Decision**: `chat.py` calls `db.create_query_trace()` directly instead of the non-existent `db.create_query()` / `db.create_trace()` / `db.create_answer()`.

**Rationale**: Those three methods are called in current chat.py but do not exist in SQLiteDB (research finding R2). Rather than adding 3 convenience wrappers to SQLiteDB that would duplicate fields, call `create_query_trace()` directly after the stream completes with all fields populated. This is simpler and matches the actual SQLiteDB interface.

### D2: Settings stored as key-value rows, assembled at read time

**Decision**: `GET /settings` calls `db.list_settings()` (key-value store), falls back to config defaults for missing keys, and assembles a typed `SettingsResponse`. `PUT /settings` validates + calls `db.set_setting(key, str(value))` per changed field.

**Rationale**: The spec-07 settings table is a key-value store, not a single row. API layer must handle this. Type coercion (str → int/bool/float) happens in the router, not in SQLiteDB.

### D3: Model listing via direct Ollama httpx + DB

**Decision**: `GET /models/llm` and `GET /models/embed` call `httpx.get("{ollama_base_url}/api/tags")` directly. No ProviderRegistry abstraction for model listing in this spec (deferred to Spec 10).

**Rationale**: `ProviderRegistry` has no `list_models()` method (research finding R4). Adding it now would require changes to spec-10 scope. Direct Ollama call is simpler and self-contained. Cloud provider model listing returns empty list if no API key configured.

### D4: Missing list/get trace methods added to SQLiteDB

**Decision**: Add `db.list_traces()` and `db.get_trace()` to `SQLiteDB` as new methods. These are minimal CRUD additions with filter/pagination support.

**Rationale**: Current `list_query_traces()` has an incompatible signature. Adding properly-named methods with the correct signature is cleaner than aliasing. The traces router depends on them.

### D5: Missing provider methods added to SQLiteDB

**Decision**: Add `db.get_active_provider()` and `db.upsert_provider()` to `SQLiteDB`. Update provider schema to add `provider_type` (VARCHAR) and `config_json` (TEXT) columns.

**Rationale**: `ProviderRegistry.initialize()` and `get_active_llm()` call these methods (research finding R2). Without them, the provider registry fails at startup. Schema migration needed for new columns.

---

## Integration Points

### ← spec-07 (Storage)
- `app.state.db: SQLiteDB` — all CRUD (collections, documents, jobs, traces, settings, providers)
- `app.state.qdrant_storage: QdrantStorage` — `delete_collection()` on collection removal
- `app.state.key_manager: KeyManager | None` — `encrypt()` / `decrypt()` for provider keys

### ← spec-06 (Ingestion)
- `backend.ingestion.pipeline.IngestionPipeline` — `ingest_file()` called as background task
- `backend.ingestion.incremental.IncrementalChecker` — SHA-256 hash duplicate detection
- Supported file types (12): `.pdf .md .txt .py .js .ts .rs .go .java .c .cpp .h`

### ← spec-02 (ConversationGraph)
- `app.state.conversation_graph` — pre-compiled, accessed per request
- `graph.astream(state, stream_mode="messages", config={"configurable": {"thread_id": session_id}})`
- Node detection: `metadata["langgraph_node"]` on each tick
- Interrupt: `"__interrupt__" in metadata` → clarification event, early return
- Final state: `graph.get_state(config).values` → confidence_score, citations, groundedness_result, attempted_strategies

### ← spec-03/04/05 (Research + MetaReasoning + Accuracy)
- `final_state["confidence_score"]` → int 0–100 (spec-07 confirmed)
- `final_state["groundedness_result"]` → `GroundednessResult` with `.verifications` list
- `final_state["attempted_strategies"]` → `set[str]` of strategy names

### → spec-09 (Frontend)
- The Next.js frontend consumes all endpoints defined in `contracts/api-endpoints.md`
- NDJSON chat streaming parsed line-by-line by the frontend

---

## Phase Assignment

### Phase 1 (MVP — All Core Endpoints)
- `schemas.py` extension: all new Pydantic models
- `config.py` extension: rate limit fields
- `middleware.py` extension: 4th rate limit category + 120 general
- `chat.py` extension: all 10 NDJSON event types
- `collections.py` extension: name regex + cascade delete
- `documents.py` rewrite: align to spec-07, remove legacy
- `ingest.py` NEW: POST upload + GET job status
- `providers.py` extension: PUT/DELETE key + GET models via has_key
- `health.py` rewrite: per-service latency_ms
- `main.py` extension: register new routers, wire key_manager

### Phase 2 (Feature Complete)
- `models.py` NEW: GET /models/llm + GET /models/embed
- `settings.py` NEW: GET/PUT /settings with validation
- `traces.py` extension: session filter + GET /stats + pagination
- SQLiteDB additions: `list_traces()`, `get_trace()`, `get_active_provider()`, `upsert_provider()`

### Phase 3 (Polish)
- Per-document chunk profile configuration
- Enhanced trace detail (full sub-questions + strategy switch JSON)
- Provider model metadata (size, quantization, context length via provider API)
- SC-010: Concurrent stream connection validation (10 simultaneous)

---

## Agent Team Orchestration

> See `Docs/PROMPTS/spec-08-api/08-plan.md` for the full step-by-step orchestration with agent spawn prompts, checkpoint gates, and testing commands.

**Structure**: 5-wave, 8-agent team

| Wave | Agents | Work |
|------|--------|------|
| 1 | A1 (Opus) + A2 (Sonnet) | Schemas + Config + Middleware |
| 2 | A3 (Opus) + A4 (Sonnet) | Chat NDJSON rewrite + Ingest router |
| 3 | A5 (Sonnet) + A6 (Sonnet) | Documents/Collections + Models/Providers/Settings |
| 4 | A7 (Sonnet) | Traces + Health + main.py wiring |
| 5 | A8 (Sonnet) | Tests + Integration + Regression |

**Testing**: ALL agents use `scripts/run-tests-external.sh`. No pytest inside Claude Code.

```bash
# Pattern for all agents:
zsh scripts/run-tests-external.sh -n spec08-<wave>-<name> <test-target>
cat Docs/Tests/spec08-<wave>-<name>.status
cat Docs/Tests/spec08-<wave>-<name>.summary
```

---

## Known Issues in Current Implementation

Issues on branch `008-api-reference` that agents must fix:

1. `chat.py` emits 4 event types (`chunk`, `clarification`, `metadata`, `error`); calls `db.create_query()` which does not exist
2. `documents.py` has overlapping ingest endpoints (Phase 1 stub + spec-06 proper)
3. `providers.py` missing `PUT /providers/{name}/key` and `DELETE /providers/{name}/key`
4. `middleware.py` missing 4th rate limit category (provider keys: 5/min); general limit is 100 not 120
5. `health.py` missing per-service `latency_ms` field
6. `traces.py` calls `db.list_traces()` and `db.get_trace()` which do not exist
7. `models.py` and `settings.py` do not exist
8. `main.py` does not register `ingest`, `models`, `settings` routers
9. `SQLiteDB` missing: `list_traces()`, `get_trace()`, `get_active_provider()`, `upsert_provider()`
