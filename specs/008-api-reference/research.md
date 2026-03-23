# Research: API Reference (Spec 08)

**Generated**: 2026-03-15 | **Phase**: 0 (Research)

## Research Questions & Resolutions

### R1: How do the 10 NDJSON event types map to ConversationGraph output?

**Decision**: Split the current 4-event stream (`chunk`, `clarification`, `metadata`, `error`) into 10 distinct typed events, extracting each signal from the LangGraph astream loop and final state.

**Findings**:
- `chat.py` currently uses `graph.astream(state, stream_mode="messages", config=config)`
- Each iteration yields `(chunk, metadata)` — chunk is an `AIMessageChunk`, metadata is a dict
- Node transitions are visible as `metadata["langgraph_node"]` (emit `status` event)
- Interrupt is signalled by `"__interrupt__" in metadata` (emit `clarification` event)
- Final state via `graph.get_state(config).values` contains: `confidence_score`, `citations`, `groundedness_result`, `final_response`, `attempted_strategies`

**Mapping**:
| Event | Source |
|-------|--------|
| `session` | Emitted first, before `astream()` call; `session_id` from `config["configurable"]["thread_id"]` |
| `status` | `metadata["langgraph_node"]` on each astream tick |
| `chunk` | `chunk.content` on `AIMessageChunk` with non-empty content |
| `citation` | `final_state["citations"]` after stream completes |
| `meta_reasoning` | `final_state["attempted_strategies"]` (set) if non-empty |
| `confidence` | `int(final_state["confidence_score"])` — always int 0–100 |
| `groundedness` | `final_state["groundedness_result"].verifications` count by verdict |
| `done` | Always last on success; carries `latency_ms` (monotonic) and `trace_id` |
| `clarification` | `metadata["__interrupt__"][0].value` — triggers early return |
| `error` | Any unhandled exception or `CircuitOpenError` |

**Alternatives Considered**: Server-Sent Events (SSE with `data:...\n\n`) — rejected by ADR-007 and coherence review.

---

### R2: What SQLiteDB methods are missing and need to be implemented?

**Decision**: Implement the missing convenience wrapper methods in SQLiteDB. They are straightforward wrappers around the existing `create_query_trace()` method.

**Findings** (from codebase analysis):
`chat.py` calls three methods that do not exist on SQLiteDB:
- `db.create_query()` — missing
- `db.create_trace()` — missing
- `db.create_answer()` — missing

`traces.py` calls two missing methods:
- `db.list_traces()` — missing (similar method `list_query_traces()` exists but has a different signature)
- `db.get_trace()` — missing

`ProviderRegistry` calls two missing methods:
- `db.get_active_provider()` — missing
- `db.upsert_provider()` — missing (provider_type and config_json columns also absent)

**Resolution**:
- `create_query()` / `create_trace()` / `create_answer()` → These are API layer convenience wrappers that should call the existing `create_query_trace()` method. Implement as thin adapters in chat.py (not as new SQLiteDB methods) to avoid breaking SQLiteDB's clean interface. Chat.py should directly call `db.create_query_trace()` with the correct parameters.
- `list_traces()` / `get_trace()` → Implement as new SQLiteDB methods with the correct signatures.
- `get_active_provider()` / `upsert_provider()` → Implement as new SQLiteDB methods for ProviderRegistry compatibility.

**Implementation approach for chat.py**: Replace the three missing method calls with a single `db.create_query_trace()` call after the stream completes.

---

### R3: How does settings storage work? (key-value vs. structured)

**Decision**: Settings are stored as individual key-value rows in SQLite, assembled into a typed `SettingsResponse` in the API layer.

**Findings**:
- `SQLiteDB` has `get_setting(key)`, `set_setting(key, value)`, `list_settings()` (key-value store)
- No single-row settings table; each setting is a separate row with a string key and string value
- Type coercion is required: int/bool/float settings stored as strings, parsed at read time
- Default values come from `backend/config.py` (`Settings(BaseSettings)`)

**Settings Keys and Types**:
| Key | Type | Default (config.py) |
|-----|------|---------------------|
| `default_llm_model` | str | `qwen2.5:7b` |
| `default_embed_model` | str | `nomic-embed-text` |
| `confidence_threshold` | int (0–100) | `60` |
| `groundedness_check_enabled` | bool | `True` |
| `citation_alignment_threshold` | float | `0.3` |
| `parent_chunk_size` | int | `2000` |
| `child_chunk_size` | int | `500` |

**API pattern**: `GET /settings` reads all keys via `db.list_settings()`, falls back to config defaults for missing keys, coerces types, returns `SettingsResponse`. `PUT /settings` validates each field, calls `db.set_setting(key, str(value))` for each changed field.

---

### R4: How does model listing work without a full ProviderRegistry.list_models()?

**Decision**: `GET /models/llm` and `GET /models/embed` query the Ollama API directly via `httpx` and read configured cloud providers from the DB. A full ProviderRegistry abstraction is out of scope for Spec 08 (deferred to Spec 10).

**Findings**:
- `ProviderRegistry` in `backend/providers/registry.py` has `get_active_llm()` and `get_embedding_provider()` but no `list_models()` method
- Ollama exposes `GET /api/tags` → returns list of downloaded model names with metadata
- Cloud providers (OpenRouter, OpenAI, Anthropic) have their own model listing APIs; for Spec 08, return an empty list if the provider API key is not configured
- `app.state.registry` is available in routers via `request.app.state.registry`

**Implementation approach**:
- `GET /models/llm`: Call `httpx.get(f"{settings.ollama_base_url}/api/tags")` for Ollama models, return 503 on failure. For cloud providers, read from DB, skip those without API keys.
- `GET /models/embed`: Similar, filter by model type (embedding models on Ollama have `:embed` or `:embedding` suffix, or known names like `nomic-embed-text`).

---

### R5: Does the providers router use KeyManager from spec-07?

**Decision**: Yes. `app.state.key_manager` is set during lifespan (gracefully optional if `EMBEDINATOR_FERNET_KEY` missing). All new `PUT /providers/{name}/key` calls must go through `key_manager.encrypt()`.

**Findings**:
- Current `providers.py` uses its own Fernet instantiation (inline), not `app.state.key_manager`
- `KeyManager` is on `app.state.key_manager` since spec-07 implementation
- For Spec 08, `providers.py` must switch to `request.app.state.key_manager` to be consistent with spec-07 architecture
- If `key_manager is None` (env var missing), return 503 with `KEY_MANAGER_UNAVAILABLE` error code

---

### R6: Constitution Compliance Conflicts

**Decision**: Two minor conflicts with the constitution were identified. Both are resolved by the spec, which is more authoritative as the spec postdates the constitution's NDJSON rule.

**Conflict 1 — Event naming**:
- Constitution VI says: `{"type": "metadata", ...}` for final frame
- Spec FR-014 says: 10 event types including `done` (no `metadata`)
- **Resolution**: Spec supersedes. The coherence review session (2026-03-14) confirmed this is a known discrepancy; `done` is the correct target type. No ADR amendment needed.

**Conflict 2 — General rate limit**:
- Constitution V says: 100 requests/min for general endpoints
- Spec FR-024 says: 120 requests/min for all other endpoints
- **Resolution**: Spec supersedes. 120/min is the target per blueprint; constitution's 100/min is the Phase 1 implemented value. No violation — this is an upward adjustment.

---

### R7: Ingestion endpoint consolidation

**Decision**: Create `backend/api/ingest.py` as a NEW dedicated router. Remove the overlapping `POST /api/documents` (Phase 1 stub) from `documents.py` in the same wave. Keep the `POST /api/collections/{id}/ingest` path in `ingest.py`.

**Findings**:
- `documents.py` has two ingest endpoints: old `POST /api/documents` (stub) and proper `POST /api/collections/{id}/ingest`
- The `POST /api/documents` stub uses `_process_document()` which is a legacy Phase 1 background task (pre-spec-06)
- Spec 08 assigns all ingest logic to `ingest.py` — this is a clean architectural separation
- The `GET /api/collections/{id}/ingest/{job_id}` polling endpoint is NEW (does not exist anywhere currently)

---

### R8: Collection creation schema alignment

**Decision**: Extend `CollectionCreateRequest` with `description`, `embedding_model`, `chunk_profile` (all optional). Add regex validator. The `create_collection()` SQLiteDB method already accepts these parameters.

**Findings**:
- `db.create_collection(id, name, embedding_model, chunk_profile, qdrant_collection_name, description)` — all fields exist in SQLiteDB
- Current `CollectionCreateRequest` only has `name` — missing 3 optional fields
- Regex pattern `^[a-z0-9][a-z0-9_-]*$` needs a `@field_validator("name")` in the schema
- `qdrant_collection_name` should be auto-generated from collection UUID (not in request)

---

## Summary of Research Decisions

| # | Question | Decision | Action |
|---|----------|----------|--------|
| R1 | NDJSON 10 event types | Map to ConversationGraph astream output | A3 implements in chat.py |
| R2 | Missing SQLiteDB methods | Adapter wrappers + new list/get trace methods | A7 adds to sqlite_db.py |
| R3 | Settings storage | Key-value store → typed SettingsResponse | A6 implements settings.py |
| R4 | Model listing | Direct Ollama httpx + DB for cloud | A6 implements models.py |
| R5 | KeyManager in providers | Switch to app.state.key_manager | A6 updates providers.py |
| R6 | Constitution conflicts | Spec supersedes; no violations | Document in plan |
| R7 | Ingest consolidation | New ingest.py + remove old stub | A4 creates, A5 cleans |
| R8 | Collection schema | Extend with optional fields + regex | A5 extends collections.py |
