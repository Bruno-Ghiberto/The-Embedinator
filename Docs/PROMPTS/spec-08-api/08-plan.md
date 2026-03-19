# Spec 08: API Reference — Implementation Plan Context

> **READ THIS SECTION FIRST. Do not skip ahead to code specifications.**

## CRITICAL MANDATORY: EXTERNAL TESTING ONLY

**NO pytest execution inside Claude Code. PERIOD.**

Every single agent (A1-A8) and the lead orchestrator MUST use:

```bash
zsh scripts/run-tests-external.sh -n <run-name> <test-target>
```

**This is non-negotiable.** Violations = implementation failure.

**Why**: External runner provides:
- Isolated venv with fingerprinted dependencies (sha256 of requirements*.txt)
- Atomic status files (`Docs/Tests/<name>.status` = RUNNING|PASSED|FAILED|ERROR)
- Token-efficient summary output (~20 lines, not megabytes of pytest output)
- Checkpoint gates can poll asynchronously without blocking Claude Code session

**If any agent or orchestrator violates this rule — STOP and escalate.**

---

## Authoritative References

Before spawning ANY agent, all participants must be able to reference:

| Document | Purpose | Location |
|----------|---------|----------|
| **Feature Spec** | Source of truth: 26 FRs, 10 SCs, 5 user stories | `specs/008-api-reference/spec.md` |
| **Task List** | All tasks across phases with dependencies | `specs/008-api-reference/tasks.md` |
| **A1 Instructions** | Wave 1: schemas extension + config | `Docs/PROMPTS/spec-08-api/agents/A1-schemas-config.md` |
| **A2 Instructions** | Wave 1: middleware extension | `Docs/PROMPTS/spec-08-api/agents/A2-middleware.md` |
| **A3 Instructions** | Wave 2: chat.py NDJSON rewrite | `Docs/PROMPTS/spec-08-api/agents/A3-chat-ndjson.md` |
| **A4 Instructions** | Wave 2: ingest.py new router | `Docs/PROMPTS/spec-08-api/agents/A4-ingest-router.md` |
| **A5 Instructions** | Wave 3: documents.py + collections.py extensions | `Docs/PROMPTS/spec-08-api/agents/A5-documents-collections.md` |
| **A6 Instructions** | Wave 3: models.py + providers.py + settings.py | `Docs/PROMPTS/spec-08-api/agents/A6-models-providers-settings.md` |
| **A7 Instructions** | Wave 4: traces.py + health.py + main.py wiring | `Docs/PROMPTS/spec-08-api/agents/A7-traces-health-wiring.md` |
| **A8 Instructions** | Wave 5: tests + integration + regression | `Docs/PROMPTS/spec-08-api/agents/A8-quality-tests.md` |

---

## Testing Protocol (MANDATORY)

**ALL agents and orchestrator MUST follow this exactly.**

### Background Mode (Agents Use This)

```bash
# Start test run (returns immediately, runs in background)
zsh scripts/run-tests-external.sh -n spec08-wave1 tests/unit/test_schemas.py

# Poll status (1 line, returns immediately)
cat Docs/Tests/spec08-wave1.status

# When done (status = PASSED or FAILED), read summary
cat Docs/Tests/spec08-wave1.summary   # ~20 lines, token efficient
```

### Visible Mode (Orchestrator Uses at Checkpoints)

```bash
# Visible checkpoint run (shows progress in real-time)
zsh scripts/run-tests-external.sh --visible -n spec08-wave1 tests/unit/test_schemas.py
```

### Status File Meanings

| Status | Meaning | Action |
|--------|---------|--------|
| RUNNING | Tests in progress | Wait, poll again in 10s |
| PASSED | All tests passed | Proceed to next wave |
| FAILED | Tests failed | Review `Docs/Tests/<name>.summary`, ask agent to debug |
| ERROR | Test infrastructure failed | Check `scripts/run-tests-external.sh`, debug environment |

**Never parse full log directly.** Always use status + summary files.

---

## Agent Team Orchestration Protocol

> **MANDATORY**: Agent Teams is REQUIRED for this spec. You MUST be running
> inside tmux. Agent Teams auto-detects tmux and spawns each teammate in its
> own split pane (the default `"auto"` teammateMode).
>
> **Enable**: Set `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in `~/.claude/settings.json`:
> ```json
> {
>   "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" }
> }
> ```
>
> **tmux multi-pane spawning is REQUIRED.** Each agent gets its own tmux pane
> for real-time visibility. Do NOT run agents sequentially in a single pane.

### Architecture

The **lead session** (orchestrator) coordinates all work via Claude Code Agent Teams:

| Component | Role |
|-----------|------|
| **Lead** | Creates team, creates tasks with dependencies, spawns teammates, runs checkpoint gates, synthesizes results, runs final regression |
| **Teammates** | Independent Claude Code instances, each in its own tmux pane, executing assigned tasks |
| **Task List** | Shared task list with dependency tracking — teammates self-claim unblocked tasks |
| **Mailbox** | Inter-agent messaging for status updates and checkpoint coordination |

### Agent Team Composition

| Agent | Role | Model | Wave | Instruction File |
|-------|------|-------|------|-----------------|
| A1 | Schemas + Config | Opus 4.6 | 1 | A1-schemas-config.md |
| A2 | Middleware Extension | Sonnet 4.6 | 1 | A2-middleware.md |
| A3 | Chat NDJSON Rewrite | Opus 4.6 | 2 | A3-chat-ndjson.md |
| A4 | Ingest Router (New) | Sonnet 4.6 | 2 | A4-ingest-router.md |
| A5 | Documents + Collections | Sonnet 4.6 | 3 | A5-documents-collections.md |
| A6 | Models + Providers + Settings | Sonnet 4.6 | 3 | A6-models-providers-settings.md |
| A7 | Traces + Health + Wiring | Sonnet 4.6 | 4 | A7-traces-health-wiring.md |
| A8 | Tests + Quality + Regression | Sonnet 4.6 | 5 | A8-quality-tests.md |

**Model Selection Rationale**:
- A1 (Opus): Schema design requires careful judgment — new Pydantic models must satisfy all 26 FRs, proper field validators, exact integer constraint on confidence, NDJSON event type literals
- A3 (Opus): NDJSON streaming rewrite is the most complex task — 10 event types, correct media type, stateful graph integration, error handling
- All other agents (Sonnet): CRUD routers, middleware adjustment, wiring — straightforward I/O code

---

## Wave Execution Order

```
Wave 1 (A1 + A2):   Schemas + Config + Middleware foundation     → CHECKPOINT GATE
Wave 2 (A3 + A4):   Chat NDJSON rewrite + Ingest router          → CHECKPOINT GATE
Wave 3 (A5 + A6):   Documents/Collections + Models/Providers/Settings → CHECKPOINT GATE
Wave 4 (A7):        Traces + Health + main.py wiring             → CHECKPOINT GATE
Wave 5 (A8):        Full tests + regression + quality            → FINAL VALIDATION
```

**Key constraint**: Each wave is a hard dependency. Wave N+1 CANNOT start until Wave N passes checkpoint.

---

## Component Overview

The API layer is the unified HTTP interface for The Embedinator. It is a FastAPI application that exposes six endpoint groups: collections, documents/ingestion, chat, models, providers, and observability. The frontend communicates exclusively through this API. The API delegates all business logic to the storage layer (spec-07), ingestion pipeline (spec-06), and agent graphs (specs-02/03/04/05).

Spec 08 focuses on:
- Expanding NDJSON event types in `chat.py` to all 10 types required by FR-014
- Adding `ingest.py` as a dedicated router wrapping the spec-06 IngestionPipeline
- Rewriting `documents.py` to align with spec-07 SQLiteDB interface
- Adding new routers: `models.py`, `settings.py`
- Extending existing routers: `collections.py`, `providers.py`, `traces.py`, `health.py`
- Hardening middleware (rate limiting per FR-024 full spec, trace ID injection)
- Extending `backend/agent/schemas.py` with new Pydantic models
- Extending `backend/config.py` with rate-limiting and settings fields

All business logic already exists in specs 02-07. This spec is predominantly a surface layer.

---

## Technical Approach

### Router Organization

Each endpoint group gets its own FastAPI router file in `backend/api/`:

| Router | Endpoints | Status |
|--------|-----------|--------|
| `collections.py` | GET, POST `/api/collections`; DELETE `/api/collections/{id}` | EXISTS — extend with name validation regex (FR-002) and Qdrant cascade delete (FR-005) |
| `documents.py` | GET `/api/documents`, GET/DELETE `/api/documents/{id}` | EXISTS — rewrite to align with spec-07 SQLiteDB signatures |
| `ingest.py` | POST `/api/collections/{id}/ingest`, GET `/api/collections/{id}/ingest/{job_id}` | NEW — wraps spec-06 IngestionPipeline |
| `chat.py` | POST `/api/chat` | EXISTS — extend to all 10 NDJSON event types (FR-013, FR-014) |
| `models.py` | GET `/api/models/llm`, GET `/api/models/embed` | NEW — proxies ProviderRegistry |
| `providers.py` | GET `/api/providers`; PUT, DELETE `/api/providers/{name}/key`; GET `/api/providers/{name}/models` | EXISTS — extend to use KeyManager from app.state (FR-018, FR-019) |
| `settings.py` | GET `/api/settings`, PUT `/api/settings` | NEW — reads/writes settings table via SQLiteDB |
| `traces.py` | GET `/api/traces`, GET `/api/traces/{id}`, GET `/api/stats` | EXISTS — extend with session filter, stats endpoint, align schemas |
| `health.py` | GET `/api/health` | EXISTS — rewrite response schema to include per-service latency (FR-022) |

### NDJSON Streaming — Correct Protocol (FR-013, FR-014)

**Media type**: `application/x-ndjson`
**Format**: One JSON object per line, terminated with `\n`
**NOT SSE format** — do not use `data: ...\n\n` (SSE), do not use `text/event-stream`

The correct NDJSON format:

```python
yield json.dumps({"type": "session", "session_id": session_id}) + "\n"
yield json.dumps({"type": "status", "node": "query_rewrite"}) + "\n"
yield json.dumps({"type": "chunk", "text": "token content"}) + "\n"
yield json.dumps({"type": "citation", "citations": [...]}) + "\n"
yield json.dumps({"type": "meta_reasoning", "strategy": "WIDEN_SEARCH", "attempt": 1}) + "\n"
yield json.dumps({"type": "confidence", "score": 82}) + "\n"
yield json.dumps({"type": "groundedness", "overall_grounded": True, "supported": 3}) + "\n"
yield json.dumps({"type": "clarification", "question": "..."}) + "\n"
yield json.dumps({"type": "done", "latency_ms": 1240, "trace_id": trace_id}) + "\n"
yield json.dumps({"type": "error", "message": "...", "code": "...", "trace_id": trace_id}) + "\n"
```

**All 10 event types** (FR-014):
1. `session` — emitted first, carries `session_id`
2. `status` — node transitions, carries `node` name
3. `chunk` — token content, carries `text`
4. `citation` — after answer complete, carries `citations` list
5. `meta_reasoning` — emitted when MetaReasoningGraph changes strategy, carries `strategy` and `attempt`
6. `confidence` — carries integer `score` (0–100, FR-015)
7. `groundedness` — carries `overall_grounded`, `supported`, `unsupported`, `contradicted`
8. `done` — final event, carries `latency_ms` and `trace_id`
9. `clarification` — on LangGraph interrupt, carries `question`
10. `error` — on any exception, carries `message`, `code`, `trace_id`

**Confidence scores are always `int` 0–100** (FR-015). Never float. Validated in schemas with `Field(ge=0, le=100)`.

### Rate Limiting — Full Spec (FR-024)

Current `middleware.py` has partial limits. Spec requires four categories per client IP:

| Endpoint Category | Limit | Path/Method Match |
|-------------------|-------|-------------------|
| Chat | 30 req/min | POST `/api/chat` |
| Ingestion | 10 req/min | POST `/api/collections/*/ingest` |
| Provider key management | 5 req/min | PUT/DELETE `/api/providers/*/key` |
| All other endpoints | 120 req/min | everything else |

The middleware must update `_get_limit()` and `_get_bucket()` to cover all four categories.

### App Factory

`backend/main.py` already has the correct lifespan pattern. Spec 08 adds router registrations for `ingest`, `models`, and `settings` routers and ensures `key_manager` is wired to `providers.py` via `app.state.key_manager`.

---

## File Structure

```
backend/
  api/
    chat.py              # EXISTS — extend to 10 NDJSON event types, emit session + status + meta_reasoning
    collections.py       # EXISTS — extend: name regex validation, Qdrant cascade delete on collection remove
    documents.py         # EXISTS — rewrite: align GET/DELETE to spec-07 SQLiteDB method signatures
    ingest.py            # NEW — POST /collections/{id}/ingest, GET /collections/{id}/ingest/{job_id}
    models.py            # NEW — GET /models/llm, GET /models/embed (proxy ProviderRegistry)
    providers.py         # EXISTS — extend: use KeyManager from app.state; add PUT/DELETE /providers/{name}/key
    settings.py          # NEW — GET /settings, PUT /settings (partial update, validate)
    traces.py            # EXISTS — extend: add session filter, GET /stats endpoint, align schemas
    health.py            # EXISTS — rewrite: add per-service latency_ms to response schema
    __init__.py          # EXISTS — update to export new routers
  agent/
    schemas.py           # EXISTS — extend: new Pydantic models for all 10 NDJSON event types, ModelInfo,
                         #           IngestionJobResponse, SettingsResponse, ProviderKeyRequest,
                         #           HealthServiceStatus, StatsResponse
  main.py                # EXISTS — extend: register ingest, models, settings routers; wire key_manager
  middleware.py          # EXISTS — extend: add provider key management rate limit category (5 req/min);
                         #           update general limit from 100 to 120 req/min per spec
  config.py              # EXISTS — extend: add rate_limit_provider_keys_per_minute,
                         #           rate_limit_general_per_minute, settings_* fields

specs/008-api-reference/
  spec.md                # Authoritative spec (26 FRs, 10 SCs, 5 user stories)
  tasks.md               # Task list with phases and dependencies

tests/
  unit/
    test_schemas_api.py          # NEW — Pydantic schema validation, field validators, event type literals
    test_middleware_rate_limit.py # NEW — all 4 rate limit categories, sliding window, per-IP isolation
    test_chat_ndjson.py          # NEW — NDJSON format correctness, all 10 event types, error paths
    test_ingest_router.py        # NEW — upload validation, job status, duplicate detection
    test_collections_router.py   # NEW — name regex, 409 conflict, cascade delete
    test_documents_router.py     # NEW — list, get, delete document endpoints
    test_models_router.py        # NEW — LLM list, embed list, 503 on provider unavailable
    test_providers_router.py     # NEW — has_key response, key never returned, PUT/DELETE key
    test_settings_router.py      # NEW — GET defaults, partial PUT, validation errors
    test_traces_router.py        # NEW — paginated list, session filter, detail view, stats
    test_health_router.py        # NEW — all services ok, one service down, latency fields
  integration/
    test_api_integration.py      # NEW — full request cycle for each endpoint group
    test_ndjson_streaming.py     # NEW — end-to-end chat stream, all event types present
    test_rate_limiting.py        # NEW — burst test for each category, 429 on limit exceeded

Docs/PROMPTS/spec-08-api/agents/
  A1-schemas-config.md           # Wave 1 agent instruction
  A2-middleware.md               # Wave 1 agent instruction
  A3-chat-ndjson.md              # Wave 2 agent instruction
  A4-ingest-router.md            # Wave 2 agent instruction
  A5-documents-collections.md   # Wave 3 agent instruction
  A6-models-providers-settings.md # Wave 3 agent instruction
  A7-traces-health-wiring.md     # Wave 4 agent instruction
  A8-quality-tests.md            # Wave 5 agent instruction
```

---

## Integration Points

### Spec 02 — ConversationGraph

- **Import**: `from backend.agent.conversation_graph import build_conversation_graph`
- **Usage**: `chat.py` calls `graph.astream(initial_state, stream_mode="messages", config=config)`
- **Session ID**: passed as `config["configurable"]["thread_id"]`
- **Interrupt detection**: `"__interrupt__" in metadata` from `graph.astream` triggers `clarification` event
- **Final state**: `graph.get_state(config).values` after stream completes, contains `confidence_score` (int 0–100), `citations`, `groundedness_result`, `final_response`
- **Graph is cached on `app.state.conversation_graph`** — built during lifespan, not per request

### Spec 03 — ResearchGraph

- **Emits status events**: agents can emit `status` events by detecting node transitions in `graph.astream` metadata
- **No direct import in API layer** — wired inside ConversationGraph automatically

### Spec 04 — MetaReasoningGraph

- **meta_reasoning event**: when MetaReasoningGraph switches strategy, emit `{"type": "meta_reasoning", "strategy": "WIDEN_SEARCH"|"CHANGE_COLLECTION"|"RELAX_FILTERS", "attempt": n}`
- **Detection**: inspect `state.get("attempted_strategies")` in final state, or hook into node metadata
- **Controlled by**: `settings.meta_reasoning_max_attempts` — if 0, skip meta_reasoning event entirely

### Spec 05 — Accuracy/Robustness

- **confidence** event: `{"type": "confidence", "score": int}` — pulled from `final_state["confidence_score"]` which is int 0–100
- **groundedness** event: pulled from `final_state["groundedness_result"]` (GroundednessResult Pydantic model)
- **CircuitOpenError**: `from backend.errors import CircuitOpenError` — catch in chat endpoint, emit `error` event with code `"circuit_open"`

### Spec 06 — Ingestion Pipeline

- **IngestionPipeline**: `from backend.ingestion.pipeline import IngestionPipeline`
- **Ingest call**: `pipeline.ingest_file(file_path, filename, collection_id, document_id, job_id, file_hash)`
- **IncrementalChecker**: `from backend.ingestion.incremental import IncrementalChecker` — duplicate and change detection
- **Job phases**: `started`, `streaming`, `embedding`, `completed`, `failed`, `paused` — polled via `db.get_ingestion_job(job_id)`
- **Supported file types** (FR-007, 12 types): `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`
- **Max file size** (FR-008): 100 MB — enforced via `settings.max_upload_size_mb`
- **`ingest.py`** is a NEW separate router — it does NOT go into `collections.py` or `documents.py`

### Spec 07 — Storage Architecture

- **SQLiteDB** (on `app.state.db`): all CRUD for collections, documents, ingestion_jobs, query_traces, settings, providers
- **QdrantStorage** (on `app.state.qdrant_storage`): collection deletion cascade when removing a collection
- **KeyManager** (on `app.state.key_manager`): encrypt/decrypt API keys in `providers.py` — NEVER return decrypted key in any response
- **`has_key` indicator**: when listing providers, return `has_key: true/false` — never the key value (FR-018, SC-005)
- **Query traces**: written by `chat.py` via `db.create_query()` + `db.create_trace()` + `db.create_answer()`
- **Settings table**: `db.get_settings()` / `db.update_settings()` — used by new `settings.py` router

---

## Key Code Patterns

### NDJSON Streaming (Correct Pattern)

```python
from fastapi.responses import StreamingResponse
import json

@router.post("/api/chat")
async def chat(body: ChatRequest, request: Request):
    async def event_generator():
        # 1. Session event — always first
        yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

        try:
            async for chunk, metadata in graph.astream(
                initial_state, stream_mode="messages", config=config
            ):
                # 2. Status event on node transitions
                if "langgraph_node" in metadata:
                    yield json.dumps({"type": "status", "node": metadata["langgraph_node"]}) + "\n"

                # 3. Chunk events for token content
                if hasattr(chunk, "content") and chunk.content:
                    yield json.dumps({"type": "chunk", "text": chunk.content}) + "\n"

                # 9. Clarification interrupt
                if "__interrupt__" in metadata:
                    yield json.dumps({
                        "type": "clarification",
                        "question": metadata["__interrupt__"][0].value,
                    }) + "\n"
                    return

            final_state = graph.get_state(config).values

            # 4. Citation event
            if final_state.get("citations"):
                yield json.dumps({
                    "type": "citation",
                    "citations": [c.model_dump() for c in final_state["citations"]],
                }) + "\n"

            # 5. Meta-reasoning event (if strategies were attempted)
            strategies = final_state.get("attempted_strategies", set())
            if strategies:
                yield json.dumps({
                    "type": "meta_reasoning",
                    "strategies_attempted": list(strategies),
                }) + "\n"

            # 6. Confidence event (integer 0–100)
            yield json.dumps({
                "type": "confidence",
                "score": int(final_state.get("confidence_score", 0)),
            }) + "\n"

            # 7. Groundedness event
            gr = final_state.get("groundedness_result")
            if gr is not None:
                yield json.dumps({
                    "type": "groundedness",
                    "overall_grounded": gr.overall_grounded,
                    "supported": sum(1 for v in gr.verifications if v.verdict == "supported"),
                    "unsupported": sum(1 for v in gr.verifications if v.verdict == "unsupported"),
                    "contradicted": sum(1 for v in gr.verifications if v.verdict == "contradicted"),
                }) + "\n"

            # 8. Done event — always last on success
            yield json.dumps({
                "type": "done",
                "latency_ms": int((time.monotonic() - start_time) * 1000),
                "trace_id": trace_id,
            }) + "\n"

        except CircuitOpenError:
            # 10. Error event
            yield json.dumps({
                "type": "error",
                "message": "A required service is temporarily unavailable.",
                "code": "circuit_open",
                "trace_id": trace_id,
            }) + "\n"

    return StreamingResponse(event_generator(), media_type="application/x-ndjson")
```

### Collection Name Validation (FR-002, FR-003)

```python
import re
from pydantic import BaseModel, Field, field_validator

class CollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        if not re.match(r"^[a-z0-9][a-z0-9_-]*$", v):
            raise ValueError(
                "Collection name must be lowercase alphanumeric with hyphens/underscores only"
            )
        return v
```

### File Upload Validation (FR-007, FR-008)

```python
from pathlib import Path

ALLOWED_EXTENSIONS = {
    ".pdf", ".md", ".txt",
    ".py", ".js", ".ts", ".rs", ".go", ".java",
    ".c", ".cpp", ".h",   # 12 types total — .c, .cpp, .h are REQUIRED
}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100 MB

async def validate_upload(file: UploadFile) -> bytes:
    content = await file.read()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, detail={
            "error": {
                "code": "FILE_FORMAT_NOT_SUPPORTED",
                "message": f"Unsupported type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                "details": {},
            }
        })
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(413, detail={
            "error": {
                "code": "FILE_TOO_LARGE",
                "message": "File exceeds 100 MB limit",
                "details": {"max_bytes": MAX_UPLOAD_SIZE},
            }
        })
    return content
```

### Rate Limit Middleware (FR-024, Full Four Categories)

```python
def _get_limit(self, path: str, method: str) -> int:
    if method == "POST" and path == "/api/chat":
        return 30
    if method == "POST" and "/ingest" in path:
        return 10
    if method in ("PUT", "DELETE") and "/key" in path:
        return 5
    return 120  # general — updated from 100 to match spec

def _get_bucket(self, path: str, method: str, client_ip: str) -> str:
    if method == "POST" and path == "/api/chat":
        return f"chat:{client_ip}"
    if method == "POST" and "/ingest" in path:
        return f"ingest:{client_ip}"
    if method in ("PUT", "DELETE") and "/key" in path:
        return f"provider_key:{client_ip}"
    return f"general:{client_ip}"
```

### Error Response Schema (FR-026)

All error responses MUST include `code`, `message`, and `trace_id`. The trace ID comes from `request.state.trace_id` (set by TraceIDMiddleware). Pattern:

```python
raise HTTPException(status_code=404, detail={
    "error": {
        "code": "COLLECTION_NOT_FOUND",
        "message": f"Collection '{collection_id}' not found",
        "details": {},
    }
})
```

For non-HTTP exceptions in streaming responses (where HTTPException cannot be raised), yield an `error` event with `trace_id`.

### Provider Key Management — has_key Only (FR-018, SC-005)

```python
@router.put("/api/providers/{name}/key")
async def save_provider_key(name: str, body: ProviderKeyRequest, request: Request):
    key_manager = request.app.state.key_manager
    if key_manager is None:
        raise HTTPException(503, detail={"error": {"code": "KEY_MANAGER_UNAVAILABLE", ...}})
    encrypted = key_manager.encrypt(body.api_key)
    await db.upsert_provider_key(name, encrypted)
    return {"name": name, "has_key": True}  # NEVER return body.api_key

@router.get("/api/providers")
async def list_providers(request: Request):
    # Return has_key: True/False — NEVER decrypt and return key value
    providers = await db.list_providers()
    return {"providers": [
        {**p, "has_key": bool(p.get("encrypted_key")), "encrypted_key": None}
        for p in providers
    ]}
```

---

## Phase Assignment

### Phase 1 — MVP (Core Endpoints)

- `chat.py`: All 10 NDJSON event types (session, status, chunk, citation, meta_reasoning, confidence, groundedness, done, clarification, error)
- `collections.py`: Name validation regex, 409 conflict, Qdrant cascade on delete
- `documents.py`: Rewrite to spec-07 SQLiteDB signatures
- `ingest.py`: POST ingest endpoint with full pipeline integration; GET job status endpoint
- `providers.py`: has_key indicator, PUT/DELETE key via KeyManager, list providers
- `health.py`: Per-service latency_ms in response (FR-022)
- `middleware.py`: All four rate limit categories (FR-024)
- `schemas.py`: All new Pydantic models
- `config.py`: New rate limit fields
- `main.py`: Register ingest, models, settings routers

### Phase 2 — Feature Complete

- `models.py`: GET /models/llm, GET /models/embed via ProviderRegistry
- `settings.py`: GET /settings with defaults, PUT /settings partial update with validation (FR-020)
- `traces.py`: Session filter, GET /stats aggregate endpoint (FR-021, FR-023)
- `health.py`: Latency measurement for each probe (SC-008)

### Phase 3 — Polish

- Per-document chunk profile configuration
- Enhanced trace detail (sub-questions, strategy switches JSON)
- Provider model metadata (size, quantization, context length per FR-017)
- SC-010: concurrent stream connection validation

---

## Step-by-Step Orchestration

### Setup: Create the Team

```
Create an agent team called "spec08-api" to implement the API Reference
feature for The Embedinator.

Reference the authoritative documents:
- Feature spec: specs/008-api-reference/spec.md
- Task list: specs/008-api-reference/tasks.md
```

All teammates will appear in their own tmux panes automatically.

---

### Wave 1: Schemas + Config + Middleware Foundation (Agents A1 + A2, Parallel)

**Prerequisites**: None (Wave 1 has no dependencies)

**Agent A1 (Schemas + Config)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A1-schemas-config.md FIRST.

Then extend backend/agent/schemas.py and backend/config.py.

You are implementing:
1. New Pydantic models in backend/agent/schemas.py:
   - CollectionCreateRequest: add field_validator for lowercase-alphanumeric name regex
   - IngestionJobResponse: job_id, document_id, status, phase, chunks_processed, chunks_total, error_message, started_at, completed_at
   - ModelInfo: name, provider, model_type (Literal["llm","embed"]), size_gb, quantization, context_length
   - ProviderKeyRequest: api_key (str, min_length=1)
   - ProviderDetailResponse: name, provider_type, is_active, has_key (bool), base_url, model_count
   - SettingsResponse: default_llm_model, default_embed_model, confidence_threshold (int 0-100),
     groundedness_check_enabled (bool), citation_alignment_threshold (float), parent_chunk_size,
     child_chunk_size
   - SettingsUpdateRequest: all fields Optional, same validators as SettingsResponse
   - HealthServiceStatus: name, status (Literal["ok","error"]), latency_ms (float), error_message (str|None)
   - HealthResponse: status (Literal["healthy","degraded"]), services (list[HealthServiceStatus])
   - StatsResponse: total_collections, total_documents, total_chunks, total_queries,
     avg_confidence (float), avg_latency_ms (float), meta_reasoning_rate (float)
   - NDJSON event types as TypedDicts or dataclasses (SessionEvent, StatusEvent, ChunkEvent,
     CitationEvent, MetaReasoningEvent, ConfidenceEvent, GroundednessEvent, DoneEvent,
     ClarificationEvent, ErrorEvent)
2. CRITICAL: confidence scores are ALWAYS int 0-100. Use Field(ge=0, le=100) on all confidence fields.
3. New fields in backend/config.py:
   - rate_limit_provider_keys_per_minute: int = 5
   - rate_limit_general_per_minute: int = 120

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec08-wave1-schemas tests/unit/test_schemas_api.py
- Poll status: cat Docs/Tests/spec08-wave1-schemas.status
- When PASSED, send message to lead: "A1 complete: schemas and config ready"
```

**Agent A2 (Middleware Extension)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A2-middleware.md FIRST.

Then extend backend/middleware.py.

You are implementing:
1. Update RateLimitMiddleware._get_limit() and _get_bucket() to cover all 4 rate categories:
   - POST /api/chat → 30 req/min (bucket: chat:{ip})
   - POST **/ingest → 10 req/min (bucket: ingest:{ip})
   - PUT/DELETE **/key → 5 req/min (bucket: provider_key:{ip}) — NEW category
   - All other → 120 req/min (was 100, now 120) (bucket: general:{ip})
2. Read rate limits from settings: settings.rate_limit_chat_per_minute,
   settings.rate_limit_ingest_per_minute, settings.rate_limit_provider_keys_per_minute,
   settings.rate_limit_general_per_minute — do NOT hardcode integers
3. TraceIDMiddleware: ensure trace_id appears in error response bodies (not just headers)
   for 429 rate limit responses
4. RequestLoggingMiddleware: no changes needed

CRITICAL: Read backend/config.py to confirm new rate limit fields added by A1 before using them.

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec08-wave1-middleware tests/unit/test_middleware_rate_limit.py
- Poll status: cat Docs/Tests/spec08-wave1-middleware.status
- When PASSED, send message to lead: "A2 complete: middleware ready"
```

**Checkpoint Gate for Wave 1:**

```bash
# Lead orchestrator waits for both A1 and A2 messages ("complete")
# Then runs (visible mode):
zsh scripts/run-tests-external.sh --visible -n spec08-wave1-schemas tests/unit/test_schemas_api.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave1-middleware tests/unit/test_middleware_rate_limit.py

# Poll statuses:
cat Docs/Tests/spec08-wave1-schemas.status
cat Docs/Tests/spec08-wave1-middleware.status
```

**PASS Criteria**: Both statuses = PASSED.

**Action if FAIL**:
```
DO NOT PROCEED.
Send message to failing agent: "Wave 1 checkpoint failed.
Review Docs/Tests/spec08-wave1-{schemas|middleware}.summary.
Fix and re-run: zsh scripts/run-tests-external.sh -n spec08-wave1-{schemas|middleware} <target>"
```

---

### Wave 2: Chat NDJSON + Ingest Router (Agents A3 + A4, Parallel)

**Prerequisites**: Wave 1 MUST pass checkpoint

**Agent A3 (Chat NDJSON Rewrite)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A3-chat-ndjson.md FIRST.

Then rewrite backend/api/chat.py.

You are implementing:
1. Extend the event_generator() in POST /api/chat to emit all 10 event types:
   session, status, chunk, citation, meta_reasoning, confidence, groundedness,
   done, clarification, error
2. Emit "session" event FIRST, before graph.astream() call
3. Emit "status" events by checking metadata["langgraph_node"] on each astream tick
4. Emit "chunk" events for AIMessageChunk with non-empty content (existing, keep)
5. Emit "citation" event after stream completes, from final_state["citations"]
6. Emit "meta_reasoning" event if final_state["attempted_strategies"] is non-empty
7. Emit "confidence" event: score = int(final_state["confidence_score"]) — ALWAYS int 0-100
8. Emit "groundedness" event from final_state["groundedness_result"] if present
9. Emit "done" event with latency_ms (int) and trace_id — ALWAYS last on success
10. Emit "clarification" event on LangGraph interrupt (existing, keep)
11. Emit "error" event with trace_id on CircuitOpenError or any exception

CRITICAL CONSTRAINTS:
- Media type: "application/x-ndjson" (already correct, keep)
- Format: json.dumps(event) + "\n" — NOT "data: ...\n\n" (SSE format)
- confidence score: ALWAYS int(final_state.get("confidence_score", 0)) — never float
- trace_id: pull from request.state.trace_id (set by TraceIDMiddleware) for all events
- Do NOT add SSE, EventSource, or text/event-stream anywhere in this file

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec08-wave2-chat tests/unit/test_chat_ndjson.py
- Poll status: cat Docs/Tests/spec08-wave2-chat.status
- When PASSED, send message to lead: "A3 complete: chat NDJSON rewrite ready"
```

**Agent A4 (Ingest Router)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A4-ingest-router.md FIRST.

Then create backend/api/ingest.py as a NEW file.

You are implementing:
1. POST /api/collections/{collection_id}/ingest (status 202):
   - Validate file extension against 12 allowed types: .pdf, .md, .txt, .py, .js, .ts,
     .rs, .go, .java, .c, .cpp, .h — all 12 REQUIRED
   - Validate file size <= 100 MB (settings.max_upload_size_mb * 1024 * 1024)
   - Validate collection_id exists via db.get_collection(collection_id)
   - Save file to settings.upload_dir / collection_id / filename
   - Run IncrementalChecker to detect duplicates (409 if duplicate with "completed" status)
   - Create document via db.create_document() and job via db.create_ingestion_job()
   - Launch pipeline.ingest_file() as asyncio.create_task() background task
   - Return: {"document_id": ..., "job_id": ..., "status": "started", "filename": ...}
2. GET /api/collections/{collection_id}/ingest/{job_id} (status 200):
   - Fetch job from db.get_ingestion_job(job_id)
   - Return IngestionJobResponse with all phase/progress fields
   - 404 if job not found

NOTE: This endpoint currently lives partly in documents.py as ingest_document().
The lead will reconcile after Wave 3 — for now implement the clean new version in ingest.py
without modifying documents.py (A5 handles documents.py cleanup in Wave 3).

CRITICAL: Import IngestionPipeline from backend.ingestion.pipeline and
IncrementalChecker from backend.ingestion.incremental (spec-06 components).

TESTING:
- Run tests with: zsh scripts/run-tests-external.sh -n spec08-wave2-ingest tests/unit/test_ingest_router.py
- Poll status: cat Docs/Tests/spec08-wave2-ingest.status
- When PASSED, send message to lead: "A4 complete: ingest router ready"
```

**Checkpoint Gate for Wave 2:**

```bash
zsh scripts/run-tests-external.sh --visible -n spec08-wave2-chat tests/unit/test_chat_ndjson.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave2-ingest tests/unit/test_ingest_router.py

cat Docs/Tests/spec08-wave2-chat.status
cat Docs/Tests/spec08-wave2-ingest.status
```

**PASS Criteria**: Both statuses = PASSED.

---

### Wave 3: Documents + Collections + Models + Providers + Settings (Agents A5 + A6, Parallel)

**Prerequisites**: Wave 2 MUST pass checkpoint

**Agent A5 (Documents + Collections)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A5-documents-collections.md FIRST.

You are implementing:
1. REWRITE backend/api/documents.py:
   - Remove the ingest_document() function (now in ingest.py after Wave 2)
   - Keep and fix: GET /api/documents (list, optional collection_id filter)
   - Keep and fix: GET /api/documents/{doc_id} (get document status + metadata)
   - Keep and fix: DELETE /api/documents/{doc_id} (soft delete)
   - Align all db.* method calls to actual SQLiteDB method signatures (spec-07)
   - Remove dead code: _process_document(), imports for document_parser, chunker, indexing
2. EXTEND backend/api/collections.py:
   - Add name regex validation: ^[a-z0-9][a-z0-9_-]*$ (FR-002) using CollectionCreateRequest
     validator from updated schemas.py
   - Add Qdrant cascade on DELETE: call qdrant_storage.delete_collection(collection_id)
     after db.delete_collection(collection_id) (FR-005)
   - Cancel active jobs before delete: query db.list_ingestion_jobs(collection_id, status="active")
     and set each to "failed" before deletion proceeds
   - Wire to app.state.qdrant_storage (not app.state.qdrant)

TESTING:
- zsh scripts/run-tests-external.sh -n spec08-wave3-docs tests/unit/test_documents_router.py
- zsh scripts/run-tests-external.sh -n spec08-wave3-coll tests/unit/test_collections_router.py
- When both PASSED, send message to lead: "A5 complete: documents and collections ready"
```

**Agent A6 (Models + Providers + Settings)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A6-models-providers-settings.md FIRST.

You are implementing:

1. CREATE backend/api/models.py (NEW):
   - GET /api/models/llm: list LLM models from app.state.registry (ProviderRegistry)
   - GET /api/models/embed: list embedding models from app.state.registry
   - Return ModelInfo objects: name, provider, model_type, context_length
   - Return 503 with structured error if provider is unreachable
   - Ollama models: proxy to ProviderRegistry.list_models("ollama")

2. EXTEND backend/api/providers.py:
   - Add PUT /api/providers/{name}/key: accept ProviderKeyRequest, encrypt via
     app.state.key_manager.encrypt(body.api_key), store via db.upsert_provider_key()
     Return {"name": ..., "has_key": True} — NEVER return the key value
   - Add DELETE /api/providers/{name}/key: remove key from DB, return {"name": ..., "has_key": False}
   - Update GET /api/providers: add "has_key" boolean to each provider; NEVER include
     encrypted_key or decrypted key in response (SC-005)
   - Existing activate and configure endpoints: keep, but migrate configure to use KeyManager

3. CREATE backend/api/settings.py (NEW):
   - GET /api/settings: read from db.get_settings() + merge with config defaults
     Return SettingsResponse (all fields, including confidence_threshold as int 0-100)
   - PUT /api/settings: accept SettingsUpdateRequest (all Optional fields), validate,
     persist changed fields via db.update_settings(), return full SettingsResponse
   - Validation: confidence_threshold must be int 0-100; reject invalid values 400

CRITICAL: has_key field in provider responses is ALWAYS bool, NEVER the key string.

TESTING:
- zsh scripts/run-tests-external.sh -n spec08-wave3-models tests/unit/test_models_router.py
- zsh scripts/run-tests-external.sh -n spec08-wave3-providers tests/unit/test_providers_router.py
- zsh scripts/run-tests-external.sh -n spec08-wave3-settings tests/unit/test_settings_router.py
- When all PASSED, send message to lead: "A6 complete: models, providers, settings ready"
```

**Checkpoint Gate for Wave 3:**

```bash
zsh scripts/run-tests-external.sh --visible -n spec08-wave3-docs tests/unit/test_documents_router.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave3-coll tests/unit/test_collections_router.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave3-models tests/unit/test_models_router.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave3-providers tests/unit/test_providers_router.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave3-settings tests/unit/test_settings_router.py

# Check all 5:
for n in docs coll models providers settings; do
  cat Docs/Tests/spec08-wave3-$n.status
done
```

**PASS Criteria**: All five statuses = PASSED.

---

### Wave 4: Traces + Health + main.py Wiring (Agent A7)

**Prerequisites**: Wave 3 MUST pass checkpoint

**Agent A7 (Traces + Health + Wiring)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A7-traces-health-wiring.md FIRST.

You are implementing:

1. EXTEND backend/api/traces.py:
   - Add session_id filter to GET /api/traces: existing query supports collection_id;
     add optional session_id: str | None = Query(None) parameter (FR-021)
   - Add GET /api/stats endpoint:
     Return StatsResponse: total_collections, total_documents, total_chunks,
     total_queries, avg_confidence (float), avg_latency_ms (float), meta_reasoning_rate (float)
     Compute via db.get_stats() or separate aggregate queries
   - Fix schema: traces list response should use TraceResponse pydantic model
   - Traces are retained indefinitely — no purge endpoint (clarified in spec)

2. REWRITE backend/api/health.py:
   - Change response schema to HealthResponse with list[HealthServiceStatus]
   - Each service: {name, status: "ok"|"error", latency_ms: float, error_message: str|None}
   - Measure actual probe latency: time.monotonic() before/after each probe call
   - Services to probe: "sqlite", "qdrant", "ollama"
   - Return 200 if all ok, 503 if any service is "error" (SC-008)

3. UPDATE backend/main.py:
   - Import and register new routers: ingest, models, settings
   - from backend.api import ingest, models, settings
   - app.include_router(ingest.router, tags=["ingest"])
   - app.include_router(models.router, tags=["models"])
   - app.include_router(settings.router, tags=["settings"])
   - Verify app.state.key_manager is accessible in provider route (already set in lifespan)

TESTING:
- zsh scripts/run-tests-external.sh -n spec08-wave4-traces tests/unit/test_traces_router.py
- zsh scripts/run-tests-external.sh -n spec08-wave4-health tests/unit/test_health_router.py
- When both PASSED, send message to lead: "A7 complete: traces, health, wiring ready"
```

**Checkpoint Gate for Wave 4:**

```bash
zsh scripts/run-tests-external.sh --visible -n spec08-wave4-traces tests/unit/test_traces_router.py
zsh scripts/run-tests-external.sh --visible -n spec08-wave4-health tests/unit/test_health_router.py

cat Docs/Tests/spec08-wave4-traces.status
cat Docs/Tests/spec08-wave4-health.status
```

**PASS Criteria**: Both statuses = PASSED.

---

### Wave 5: Tests + Quality + Final Regression (Agent A8)

**Prerequisites**: Wave 4 MUST pass checkpoint

**Agent A8 (Quality + Tests)** — Spawn with this prompt:

```
Read your instruction file at Docs/PROMPTS/spec-08-api/agents/A8-quality-tests.md FIRST.

You are implementing:

1. INTEGRATION TESTS — tests/integration/test_api_integration.py:
   - Full request cycle per endpoint group using TestClient
   - Test each FR (FR-001 through FR-026) is satisfied
   - Verify 409 on duplicate collection name (FR-003)
   - Verify 400 on invalid name pattern (FR-002)
   - Verify 413 on oversized file, 400 on unsupported extension (FR-008)
   - Verify has_key never returns key value (FR-018, SC-005)
   - Verify confidence in all responses is int 0-100 (FR-015)

2. NDJSON STREAMING INTEGRATION — tests/integration/test_ndjson_streaming.py:
   - Parse each line of chat response as JSON
   - Assert first event type == "session"
   - Assert last event type == "done" or "error"
   - Assert no SSE prefix (no "data:" prefix on any line)
   - Assert media type == "application/x-ndjson"
   - Assert all 10 event types are exercised across test scenarios

3. RATE LIMITING INTEGRATION — tests/integration/test_rate_limiting.py:
   - Burst 31 chat requests → 30 succeed, 1 returns 429 (SC-004)
   - Burst 11 ingest requests → 10 succeed, 1 returns 429
   - Burst 6 provider key requests → 5 succeed, 1 returns 429
   - Verify Retry-After header present on 429

4. CODE QUALITY:
   - Run ruff check on all modified files
   - Verify type hints on all public router functions
   - Verify no API key value appears in any response schema or test fixture

5. FINAL FULL SUITE:
   - Run: zsh scripts/run-tests-external.sh -n spec08-full tests/
   - All previous tests must still pass (no regressions)

TESTING:
- Run integration tests: zsh scripts/run-tests-external.sh -n spec08-wave5-integration tests/integration/test_api_integration.py
- Run full suite: zsh scripts/run-tests-external.sh -n spec08-full tests/
- Poll: cat Docs/Tests/spec08-full.status
- When PASSED, send message to lead: "Wave 5 complete, all tests pass, API layer ready"
```

**Final Checkpoint (Lead Orchestrator):**

```bash
# Wait for A8 message ("complete")
# Then run final checkpoint (visible mode):
zsh scripts/run-tests-external.sh --visible -n spec08-full tests/

# Poll status:
cat Docs/Tests/spec08-full.status

# Read summary:
cat Docs/Tests/spec08-full.summary
```

**PASS Criteria**:
- Status = PASSED
- Summary shows: no regressions vs spec-07 baseline
- All NDJSON event type tests pass
- All rate limit category tests pass
- No API key value appears in any test response

**Action if PASS**:
```
IMPLEMENTATION COMPLETE

All 5 waves have passed their checkpoints.
API Reference layer is production-ready.

Next steps:
1. Merge branch into main
2. Proceed to Spec 09 (Frontend) which consumes all these endpoints
```

**Action if FAIL**:
```
DO NOT MERGE.
Send message to A8: "Final checkpoint failed.
Review Docs/Tests/spec08-full.summary and Docs/Tests/spec08-full.log.
Fix remaining issues and re-run:
zsh scripts/run-tests-external.sh -n spec08-full tests/"
```

---

## Known Issues in Current Implementation

These issues exist in the codebase on branch `008-api-reference` and MUST be corrected by the implementing agents:

1. **`chat.py` missing 4 event types**: Current implementation emits `chunk`, `clarification`, `metadata` (wrong name), and `error`. Spec requires `session`, `status`, `chunk`, `citation`, `meta_reasoning`, `confidence`, `groundedness`, `done`, `clarification`, `error`. The `metadata` event must be split into separate typed events.

2. **`documents.py` contains ingest logic**: The `ingest_document()` function at line 117 belongs in `ingest.py`. The `_process_document()` background function at line 93 is a legacy stub from pre-spec-06 and should be removed entirely.

3. **`providers.py` missing PUT/DELETE /key endpoints**: Current endpoints are `POST /providers/{name}/activate` and `POST /providers/{name}/config`. Spec requires `PUT /providers/{name}/key` and `DELETE /providers/{name}/key`.

4. **`middleware.py` missing provider key rate limit**: Current `_get_limit()` only has 3 cases (upload, chat, general). Provider key management (5 req/min) is missing. General limit is 100 not 120.

5. **`health.py` missing per-service latency**: Returns `{"status": ..., "services": {...}}` with string values. Spec requires per-service `latency_ms` float field (FR-022).

6. **`traces.py` missing session filter and `/stats` endpoint**: Current endpoint only supports `collection_id` filter. Session filter and aggregate stats endpoint are missing (FR-021, FR-023).

7. **`models.py` and `settings.py` do not exist**: These are NEW files to create.

8. **`main.py` missing router registrations**: Does not import or register `ingest`, `models`, `settings` routers.

---

## Important Reminders

- **EXTERNAL TESTING ONLY**: No pytest inside Claude Code. Ever. Use `scripts/run-tests-external.sh`.
- **NDJSON not SSE**: Media type is `application/x-ndjson`. Format is `json.dumps(event) + "\n"`. Never `data: ...\n\n`.
- **Confidence scores are int 0–100**: Never float. Validated by `Field(ge=0, le=100)` in all schemas.
- **12 file types, not 9**: `.c`, `.cpp`, `.h` are required additions to the allowed extensions set.
- **has_key only**: Provider listings return `has_key: bool`. Key value is never decrypted and returned.
- **ingest.py is a NEW separate router**: Not part of collections.py or documents.py.
- **Wave Gates Are Hard Stops**: Don't skip waves or proceed if checkpoint fails.
- **Agent Instructions Are Authoritative**: Each agent's instruction file is the detailed source of truth.
- **Checkpoint Polling**: Use `cat Docs/Tests/<name>.status` to poll, `cat Docs/Tests/<name>.summary` for results.
- **Rate Limit Categories**: Four distinct categories with four distinct limits — chat 30, ingest 10, provider key 5, general 120.
