# Spec 08: API Reference -- Implementation Guide

> **This document is the authoritative implementation reference for spec-08.**
> It supersedes all prior versions. Agents MUST follow this exactly.

---

## MANDATORY: Agent Teams with tmux

**This spec MUST be implemented using Agent Teams.** Do not implement manually.

```
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

All agents spawn in tmux panes. The lead orchestrator:
1. Reads this file and `specs/008-api-reference/tasks.md`
2. Spawns agents per the Wave table below
3. Enforces checkpoint gates between waves
4. Never implements code directly -- only coordinates

**Spawn pattern for each agent:**
```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A<N>-<name>.md FIRST, then execute all assigned tasks.
```

---

## MANDATORY: External Test Runner

**NEVER run pytest inside Claude Code.** Every agent uses:

```bash
zsh scripts/run-tests-external.sh -n spec08-<name> <test-target>
cat Docs/Tests/spec08-<name>.status    # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec08-<name>.summary   # ~20 lines when done
```

Violations are implementation failures. No exceptions.

---

## Wave Orchestration

| Wave | Agents | Work | Model |
|------|--------|------|-------|
| 1 | A1 + A2 (parallel) | Schemas + Config / Middleware | Opus + Sonnet |
| 2 | A3 + A4 (parallel) | Chat NDJSON / Ingest Router | Opus + Sonnet |
| 3 | A5 + A6 (parallel) | Docs+Collections / Models+Providers+Settings | Sonnet + Sonnet |
| 4 | A7 (serial) | Traces + Health + main.py wiring | Sonnet |
| 5 | A8 (serial) | Quality + Integration tests + Regression | Sonnet |

### Checkpoint Gates

**Gate 1 (after Wave 1):** Schemas importable, config fields present, middleware has 4 categories.
```bash
zsh scripts/run-tests-external.sh -n spec08-gate1 tests/unit/test_schemas_api.py tests/unit/test_middleware_rate_limit.py
```
Must PASS before Wave 2 starts.

**Gate 2 (after Wave 2):** Chat streams 10 NDJSON event types, ingest router accepts 12 file types.
```bash
zsh scripts/run-tests-external.sh -n spec08-gate2 tests/unit/test_chat_ndjson.py tests/unit/test_ingest_router.py
```
Must PASS before Wave 3 starts.

**Gate 3 (after Wave 3):** Documents/collections CRUD works, providers never leak keys, settings validate.
```bash
zsh scripts/run-tests-external.sh -n spec08-gate3 tests/unit/test_collections_router.py tests/unit/test_documents_router.py tests/unit/test_providers_router.py tests/unit/test_models_router.py tests/unit/test_settings_router.py
```
Must PASS before Wave 4 starts.

**Gate 4 (after Wave 4):** Traces paginate, health reports latency_ms, new routers registered.
```bash
zsh scripts/run-tests-external.sh -n spec08-gate4 tests/unit/test_traces_router.py tests/unit/test_health_router.py
```
Must PASS before Wave 5 starts.

**Gate 5 (after Wave 5):** Full regression passes with zero regressions vs spec-07 baseline (238 tests).
```bash
zsh scripts/run-tests-external.sh -n spec08-full tests/
```

---

## Agent Instruction Files

| Agent | File | Tasks |
|-------|------|-------|
| A1 | `Docs/PROMPTS/spec-08-api/agents/A1-schemas-config.md` | T003, T004 |
| A2 | `Docs/PROMPTS/spec-08-api/agents/A2-middleware.md` | T005 |
| A3 | `Docs/PROMPTS/spec-08-api/agents/A3-chat-ndjson.md` | T008-T011 |
| A4 | `Docs/PROMPTS/spec-08-api/agents/A4-ingest-router.md` | T012-T014, T017 |
| A5 | `Docs/PROMPTS/spec-08-api/agents/A5-documents-collections.md` | T015-T016 |
| A6 | `Docs/PROMPTS/spec-08-api/agents/A6-models-providers-settings.md` | T018-T021, T026-T027 |
| A7 | `Docs/PROMPTS/spec-08-api/agents/A7-traces-health-wiring.md` | T022-T025, T028-T029 |
| A8 | `Docs/PROMPTS/spec-08-api/agents/A8-quality-tests.md` | T030-T034 |

---

## Authoritative References

| Document | Location |
|----------|----------|
| Feature Spec (26 FRs, 10 SCs) | `specs/008-api-reference/spec.md` |
| Task List (34 tasks) | `specs/008-api-reference/tasks.md` |
| Data Model (entities + NDJSON types) | `specs/008-api-reference/data-model.md` |
| HTTP Contracts (all endpoints) | `specs/008-api-reference/contracts/api-endpoints.md` |
| Implementation Plan | `specs/008-api-reference/plan.md` |
| Constitution | `.specify/memory/constitution.md` |

---

## Critical Rules (ALL Agents)

### 1. NDJSON not SSE

Every chat response line is `json.dumps(event) + "\n"`. No `data:` prefix. No `text/event-stream`.

```python
# CORRECT
yield json.dumps({"type": "chunk", "text": token}) + "\n"
# ...
return StreamingResponse(generate(), media_type="application/x-ndjson")

# WRONG -- do NOT use these
yield f"data: {json.dumps(event)}\n\n"          # SSE prefix
media_type="text/event-stream"                   # SSE media type
```

### 2. Ten NDJSON Event Types

Every chat stream produces a subset of these events. The order is:
`session` (always first) -> `status` (per node) -> `chunk` (tokens) -> `citation` -> `meta_reasoning` -> `confidence` -> `groundedness` -> `done` (always last on success).
On interrupt: `session` -> `clarification` (stream ends).
On error: `error` (stream ends).

```python
# 1. Session (always first)
{"type": "session", "session_id": str}

# 2. Status (per graph node transition)
{"type": "status", "node": str}

# 3. Chunk (token-by-token)
{"type": "chunk", "text": str}

# 4. Citation (after stream)
{"type": "citation", "citations": list[dict]}

# 5. Meta-reasoning (if triggered)
{"type": "meta_reasoning", "strategies_attempted": list[str]}

# 6. Confidence (ALWAYS int 0-100)
{"type": "confidence", "score": int}

# 7. Groundedness
{"type": "groundedness", "overall_grounded": bool, "supported": int, "unsupported": int, "contradicted": int}

# 8. Done (last on success)
{"type": "done", "latency_ms": int, "trace_id": str}

# 9. Clarification (on interrupt -- ends stream)
{"type": "clarification", "question": str}

# 10. Error (on exception -- ends stream)
{"type": "error", "message": str, "code": str, "trace_id": str}
```

### 3. Confidence is int 0-100

Never float. In schemas: `Field(ge=0, le=100)`. In events: `"score": int(confidence)`.

### 4. Error Response Format

All non-streaming errors use this structure (FR-026):

```python
{
    "error": {
        "code": "COLLECTION_NOT_FOUND",    # machine-readable
        "message": "Collection 'xyz' not found",  # human-readable
        "details": {}                       # optional structured data
    },
    "trace_id": "uuid"                      # from request.state.trace_id
}
```

Error codes: `COLLECTION_NOT_FOUND`, `COLLECTION_NAME_CONFLICT`, `COLLECTION_NAME_INVALID`, `DOCUMENT_NOT_FOUND`, `FILE_FORMAT_NOT_SUPPORTED`, `FILE_TOO_LARGE`, `DUPLICATE_DOCUMENT`, `JOB_NOT_FOUND`, `PROVIDER_NOT_FOUND`, `KEY_MANAGER_UNAVAILABLE`, `TRACE_NOT_FOUND`, `RATE_LIMIT_EXCEEDED`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`, `INVALID_REQUEST`, `SETTINGS_VALIDATION_ERROR`.

### 5. Provider Keys Never Returned

Only `has_key: bool` in any response. Never `api_key`, `api_key_encrypted`, or the decrypted value. Use `app.state.key_manager` (KeyManager from spec-07), not inline Fernet. Return 503 `KEY_MANAGER_UNAVAILABLE` if `app.state.key_manager is None`.

### 6. Twelve File Types

```python
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".py", ".js", ".ts", ".rs", ".go", ".java", ".c", ".cpp", ".h"}
```

### 7. Four Rate Limit Categories

| Category | Limit | Match | Bucket |
|----------|-------|-------|--------|
| Chat | 30/min | `POST /api/chat` | `chat:{ip}` |
| Ingestion | 10/min | `POST /api/collections/*/ingest` | `ingest:{ip}` |
| Provider key | 5/min | `PUT` or `DELETE /api/providers/*/key` | `provider_key:{ip}` |
| General | 120/min | everything else | `general:{ip}` |

All per-IP sliding window (60 seconds). On exceed: 429 with `Retry-After: 60` header and structured error body including `trace_id`.

### 8. Settings are Key-Value Rows

Settings live in the `settings` table as key-value pairs. The API layer assembles them:

```python
# Read: merge DB overrides with config defaults
db_settings = await db.list_settings()  # -> dict[str, str]
# Coerce types: str -> int/bool/float per field
# Return SettingsResponse

# Write: validate + persist per field
await db.set_setting("confidence_threshold", str(value))
```

Seven settings fields: `default_llm_model`, `default_embed_model`, `confidence_threshold` (int 0-100), `groundedness_check_enabled` (bool), `citation_alignment_threshold` (float), `parent_chunk_size` (int), `child_chunk_size` (int).

### 9. Ingest is a Separate Router

`backend/api/ingest.py` is a NEW file. It is NOT part of `collections.py` or `documents.py`. The legacy `ingest_document()` and `_process_document()` in `documents.py` must be removed by A5.

### 10. Trace Recording via db.create_query_trace()

The methods `db.create_query()`, `db.create_trace()`, and `db.create_answer()` DO NOT EXIST. Use:

```python
await db.create_query_trace(
    id=trace_id,
    session_id=session_id,
    query=body.message,
    collections_searched=json.dumps(body.collection_ids),
    chunks_retrieved_json=json.dumps([...]),
    latency_ms=latency_ms,
    llm_model=llm_model,
    embed_model=embed_model,
    confidence_score=int(final_state.get("confidence_score", 0)),
    sub_questions_json=json.dumps(sub_questions) if sub_questions else None,
    reasoning_steps_json=json.dumps(reasoning_steps) if reasoning_steps else None,
    strategy_switches_json=json.dumps(strategy_switches) if strategy_switches else None,
    meta_reasoning_triggered=bool(final_state.get("attempted_strategies")),
)
```

---

## File Targets by Agent

### A1: Schemas + Config (Wave 1)

**Files:** `backend/agent/schemas.py` (extend), `backend/config.py` (extend)

Extend `schemas.py` with:
- `CollectionCreateRequest`: add `description: str | None`, `embedding_model: str | None`, `chunk_profile: str | None`, regex `field_validator` for name: `^[a-z0-9][a-z0-9_-]*$`
- `CollectionResponse`: 7 fields (id, name, description, embedding_model, chunk_profile, document_count, created_at)
- `DocumentResponse`: correct status literals (`pending`, `ingesting`, `completed`, `failed`, `duplicate`)
- `IngestionJobResponse`: job_id, document_id, status (7 literals), chunks_processed, chunks_total, error_message, started_at, completed_at
- `ModelInfo`: name, provider, model_type (`llm`|`embed`), size_gb, quantization, context_length
- `ProviderKeyRequest`: api_key (str)
- `ProviderDetailResponse`: name, is_active, has_key (bool), base_url, model_count
- `SettingsResponse`: 7 fields, `confidence_threshold: int = Field(ge=0, le=100)`
- `SettingsUpdateRequest`: all Optional fields, `confidence_threshold: int | None = Field(None, ge=0, le=100)`
- `HealthServiceStatus`: name, status, latency_ms (float|None), error_message (str|None)
- `HealthResponse`: status (healthy|degraded), services: list[HealthServiceStatus]
- `StatsResponse`: 7 numeric fields
- `QueryTraceResponse`: 9 fields including `confidence_score: int | None`
- `QueryTraceDetailResponse(QueryTraceResponse)`: adds sub_questions, chunks_retrieved, reasoning_steps, strategy_switches
- 10 NDJSON event TypedDicts: `SessionEvent`, `StatusEvent`, `ChunkEvent`, `CitationEvent`, `MetaReasoningEvent`, `ConfidenceEvent`, `GroundednessEvent`, `DoneEvent`, `ClarificationEvent`, `ErrorEvent`

Extend `config.py` Settings class with:
- `rate_limit_provider_keys_per_minute: int = 5`
- `rate_limit_general_per_minute: int = 120`
- Fix `rate_limit_chat_per_minute` from 100 to 30

### A2: Middleware (Wave 1)

**Files:** `backend/middleware.py`

Update `RateLimitMiddleware`:
- Add 4th category: `PUT` or `DELETE` on paths matching `/api/providers/*/key` -> `provider_key:{ip}`, limit from `settings.rate_limit_provider_keys_per_minute`
- Update ingest detection: `POST` on paths matching `/api/collections/*/ingest`
- Change general limit from hardcoded 100 to `settings.rate_limit_general_per_minute` (120)
- Read chat limit from `settings.rate_limit_chat_per_minute` (30)
- Read ingest limit from `settings.rate_limit_ingest_per_minute` (10)
- Add `trace_id` to 429 response body (from `request.state.trace_id` via `getattr` with fallback)

### A3: Chat NDJSON (Wave 2)

**Files:** `backend/api/chat.py` (rewrite), `tests/unit/test_chat_ndjson.py` (new), `tests/integration/test_ndjson_streaming.py` (new)

Rewrite `event_generator()`:
1. Yield `session` event BEFORE `graph.astream()`
2. During `astream(stream_mode="messages")`: yield `status` events from `metadata["langgraph_node"]`, yield `chunk` events from `AIMessageChunk.content`
3. Detect `"__interrupt__"` in metadata -> yield `clarification` event, return early
4. After stream: get `final_state = graph.get_state(config).values`
5. Yield `citation` from `final_state["citations"]`
6. Yield `meta_reasoning` from `final_state["attempted_strategies"]` if non-empty
7. Yield `confidence` with `int(final_state.get("confidence_score", 0))`
8. Yield `groundedness` from `final_state["groundedness_result"]`
9. Write trace via `db.create_query_trace()` (NOT db.create_query/create_trace/create_answer)
10. Yield `done` with latency_ms and trace_id
11. On error: yield `error` event with trace_id

### A4: Ingest Router (Wave 2)

**Files:** `backend/api/ingest.py` (new), `tests/unit/test_ingest_router.py` (new)

Create `POST /api/collections/{collection_id}/ingest`:
- Validate extension (12 types), size (100 MB), collection exists
- SHA-256 via `IncrementalChecker.compute_file_hash()`
- Duplicate check via `IncrementalChecker.check_duplicate()`
- Save file, create document + job via db (caller generates UUIDs)
- Launch `IngestionPipeline.ingest_file()` via `asyncio.create_task()`
- Return 202 with `IngestionJobResponse`

Create `GET /api/collections/{collection_id}/ingest/{job_id}`:
- Fetch via `db.get_ingestion_job(job_id)`, return 404 if None

### A5: Documents + Collections (Wave 3)

**Files:** `backend/api/collections.py` (extend), `backend/api/documents.py` (rewrite), `tests/unit/test_collections_router.py` (new), `tests/unit/test_documents_router.py` (new)

Collections:
- Use `CollectionCreateRequest` with regex validation (already has `pattern` Field, add `field_validator` for clarity)
- Catch UNIQUE constraint for 409 with `COLLECTION_NAME_CONFLICT` code
- Cascade DELETE: list documents -> get jobs per document -> set jobs to failed -> delete qdrant collection via `app.state.qdrant_storage.delete_collection()` -> delete collection record

Documents:
- REMOVE `upload_document()` and `_process_document()` (legacy Phase 1)
- REMOVE `ingest_document()` (moved to ingest.py)
- Keep: `GET /api/documents` (list, optional collection_id filter), `GET /api/documents/{doc_id}`, `DELETE /api/documents/{doc_id}`
- Handle `list_documents()` requiring collection_id: if None, list all collections first and aggregate

### A6: Models + Providers + Settings (Wave 3)

**Files:** `backend/api/providers.py` (rewrite), `backend/api/models.py` (new), `backend/api/settings.py` (new), `tests/unit/test_providers_router.py` (new), `tests/unit/test_models_router.py` (new), `tests/unit/test_settings_router.py` (new)

Providers:
- Remove `activate_provider()` and `configure_provider()` endpoints
- Add `PUT /api/providers/{name}/key`: encrypt via `app.state.key_manager.encrypt()`, store via `db.update_provider(name, api_key_encrypted=encrypted)`, return `{"name": name, "has_key": true}`
- Add `DELETE /api/providers/{name}/key`: clear key via `db.update_provider(name, api_key_encrypted=None)`, return `{"name": name, "has_key": false}` (use empty string not None to clear, then check)
- Update `GET /api/providers`: include `has_key: bool` (True if `api_key_encrypted` is not None), NEVER include the key value
- Return 503 `KEY_MANAGER_UNAVAILABLE` if `app.state.key_manager is None`
- Remove inline Fernet code (`_get_fernet`, `encrypt_api_key`, `decrypt_api_key`)

Models:
- `GET /api/models/llm`: call `httpx.AsyncClient().get(f"{settings.ollama_base_url}/api/tags")`, parse into `list[ModelInfo]` with `model_type="llm"`, return 503 on failure
- `GET /api/models/embed`: same but filter for embedding model names (nomic-embed-text, mxbai-embed-large, patterns ending in `:embed` or `:embedding`)

Settings:
- `GET /api/settings`: call `db.list_settings()`, merge with config defaults, coerce types, return `SettingsResponse`
- `PUT /api/settings`: accept `SettingsUpdateRequest`, validate `confidence_threshold` 0-100, persist via `db.set_setting(key, str(value))` per non-None field, return full `SettingsResponse`

### A7: Traces + Health + Wiring (Wave 4)

**Files:** `backend/api/traces.py` (extend), `backend/api/health.py` (rewrite), `backend/main.py` (extend), `backend/api/__init__.py` (update), `tests/unit/test_traces_router.py` (new), `tests/unit/test_health_router.py` (new)

Traces:
- Add `session_id: str | None = Query(None)` filter
- Add `offset: int = Query(0)` for pagination
- Call `db.list_traces()` (T006 adds this method) with all filters
- Add `GET /api/stats`: compute aggregates from query data, return `StatsResponse`
- Empty filter -> empty list (NOT 404)

Health:
- Probe each service with `time.monotonic()` for latency
- Return `HealthResponse` with `services: list[HealthServiceStatus]`
- Each entry: `name`, `status` ("ok"/"error"), `latency_ms` (float|None), `error_message` (str|None)
- Return 200 if all ok, 503 if any error

Main:
- Import and register 3 new routers: `ingest`, `models`, `settings`
- `app.include_router(ingest.router, tags=["ingest"])`
- `app.include_router(models.router, tags=["models"])`
- `app.include_router(settings.router, tags=["settings"])`

### A8: Quality + Tests (Wave 5)

**Files:** `tests/integration/test_api_integration.py` (new), `tests/integration/test_rate_limiting.py` (new), `tests/integration/test_concurrent_streams.py` (new)

- Full request cycle per endpoint group (collections, documents, ingest, chat, providers, models, settings, traces, health)
- Burst rate limit tests (31 chat, 11 ingest, 6 provider key -> verify exactly 1 returns 429)
- 10 concurrent chat streams via `asyncio.gather()` (SC-010)
- `ruff check` on all modified/created files
- Full regression: spec-07 baseline (238 tests) must still pass

---

## SQLiteDB Method Reference

Methods agents will call (from `backend/storage/sqlite_db.py`):

```python
# Collections
await db.create_collection(id, name, embedding_model, chunk_profile, qdrant_collection_name, description=None)
await db.get_collection(collection_id) -> dict | None
await db.get_collection_by_name(name) -> dict | None
await db.list_collections() -> list[dict]
await db.delete_collection(collection_id)

# Documents
await db.create_document(id, collection_id, filename, file_hash, file_path=None, status="pending")
await db.get_document(doc_id) -> dict | None
await db.list_documents(collection_id) -> list[dict]  # NOTE: collection_id is REQUIRED
await db.delete_document(doc_id)
await db.update_document(doc_id, **kwargs)

# Ingestion Jobs
await db.create_ingestion_job(id, document_id, status="started")
await db.get_ingestion_job(job_id) -> dict | None
await db.list_ingestion_jobs(document_id) -> list[dict]  # by document_id, NOT collection_id
await db.update_ingestion_job(job_id, status=None, chunks_processed=None, ...)

# Query Traces
await db.create_query_trace(id, session_id, query, collections_searched, chunks_retrieved_json, latency_ms, ...)
await db.list_query_traces(session_id, limit=100) -> list[dict]  # requires session_id

# Settings
await db.get_setting(key) -> str | None
await db.set_setting(key, value)
await db.list_settings() -> dict[str, str]

# Providers
await db.get_provider(name) -> dict | None
await db.list_providers() -> list[dict]
await db.update_provider(name, is_active=None, api_key_encrypted=None, base_url=None)
await db.create_provider(name, api_key_encrypted=None, base_url=None, is_active=True)
```

**Missing methods that T006/T007 must add:**
- `db.list_traces(session_id=None, collection_id=None, min_confidence=None, max_confidence=None, limit=20, offset=0)` -> list[dict]
- `db.get_trace(trace_id)` -> dict | None

---

## Known Issues in Current Code

Agents will encounter these. This is expected -- fixing them is part of the work.

1. **chat.py** calls `db.create_query()`, `db.create_trace()`, `db.create_answer()` -- these do not exist. Replace with `db.create_query_trace()`.
2. **chat.py** emits 4 event types (`chunk`, `clarification`, `metadata`, `error`) -- must emit 10.
3. **chat.py** final event is `metadata` -- must be `done`.
4. **documents.py** has legacy `upload_document()` + `_process_document()` AND spec-06 `ingest_document()` -- remove all three, keep only GET/DELETE endpoints.
5. **providers.py** uses inline Fernet instead of `app.state.key_manager` -- rewrite to use KeyManager.
6. **providers.py** has `activate_provider()` and `configure_provider()` -- replace with PUT/DELETE key.
7. **middleware.py** has 3 rate limit categories, general=100 -- add 4th (provider_key:5), fix general to 120.
8. **config.py** has `rate_limit_chat_per_minute=100` -- must be 30.
9. **health.py** returns flat dict, no latency_ms per service -- rewrite with `HealthServiceStatus` list.
10. **traces.py** calls `db.get_trace()` and `db.list_traces()` which do not exist -- T006 adds them.
11. **traces.py** missing `session_id` filter, `offset` pagination, `/stats` endpoint.
12. **schemas.py** has `CollectionResponse` with 4 fields -- needs 7. Missing all NDJSON TypedDicts.
13. **main.py** missing `ingest`, `models`, `settings` router registrations.
14. **collections.py** missing name regex validation with `COLLECTION_NAME_INVALID` error code, missing cascade delete.
