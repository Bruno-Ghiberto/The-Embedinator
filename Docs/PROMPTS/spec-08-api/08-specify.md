# Spec 08: API Reference -- Feature Specification Context

## Feature Description

The API layer is a FastAPI application that exposes all backend functionality through a RESTful HTTP interface. It is the sole interface between the frontend (Next.js) and the backend systems (agent graphs, ingestion pipeline, storage, providers). The API is organized into six endpoint groups:

1. **Collections** -- CRUD operations for document collections (each maps to a Qdrant collection).
2. **Documents** -- Document listing, file upload (multipart, triggers ingestion pipeline), ingestion job status polling, and document deletion.
3. **Chat** -- The primary endpoint. Accepts a user message + collection IDs, invokes the agent graph, and streams the response as NDJSON (`application/x-ndjson`) with token-by-token output, citations, confidence scores, groundedness results, and trace IDs.
4. **Models** -- Proxy endpoints to list available LLM and embedding models from configured providers (primarily Ollama).
5. **Providers** -- Provider management: list providers, save/delete API keys (Fernet-encrypted), list models per provider.
6. **Observability** -- Query trace listing/detail, health check (Qdrant + Ollama + SQLite status), and system-wide statistics.

Additional cross-cutting concerns: Settings CRUD, rate limiting per endpoint category, CORS configuration, and trace ID injection middleware.

## Requirements

### Functional Requirements

- **Base URL**: `http://localhost:8000/api`
- **Collections CRUD**: GET /collections (list), POST /collections (create with name validation), DELETE /collections/{id}.
- **Document Management**: GET /collections/{id}/documents (list), POST /collections/{id}/ingest (multipart file upload), GET /collections/{id}/ingest/{job_id} (poll status), DELETE /collections/{id}/documents/{doc_id}.
- **Chat with NDJSON Streaming**: POST /chat accepts `ChatRequest`, returns an NDJSON stream (`application/x-ndjson`). Each line is a complete JSON object. Event types: session, status, chunk, citation, meta_reasoning, confidence, groundedness, done, clarification, error.
- **Model Listing**: GET /models/llm, GET /models/embed -- proxy to Ollama (and other providers).
- **Provider Management**: GET /providers (list), PUT /providers/{name}/key (save encrypted API key), DELETE /providers/{name}/key, GET /providers/{name}/models.
- **Settings**: GET /settings, PUT /settings (partial update).
- **Observability**: GET /traces (paginated), GET /traces/{id} (detail), GET /health (service status), GET /stats (system-wide metrics).
- **Rate Limiting**: Chat: 30/min, Ingest: 10/min, Provider key: 5/min, Default: 120/min.
- **CORS**: Allow origins from `cors_origins` config (default: localhost:3000).
- **File Validation**: Allowed extensions: .pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h. Max size: 100MB.

### Non-Functional Requirements

- NDJSON streaming must deliver tokens as they are generated (no buffering).
- All endpoints must return proper HTTP status codes and structured error responses.
- Rate limiting must apply per-endpoint-category, not globally.
- CORS must be configurable via environment variable.
- Health check must probe Qdrant, Ollama, and SQLite with latency measurements.

## Key Technical Details

### Pydantic Schemas

```python
# --- Collections ---

class CollectionCreateRequest(BaseModel):  # EXISTS: schemas.py, needs EXTENSION
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: str | None = Field(None, max_length=500)  # NEW field
    embedding_model: str = "nomic-embed-text"              # NEW field
    chunk_profile: str = "default"                         # NEW field
    # NOTE: current code has only name (min=1, max=255, no pattern). This extends it
    #       with description, embedding_model, chunk_profile, and adds regex validation.

class CollectionResponse(BaseModel):  # EXISTS: schemas.py, needs EXTENSION
    id: str
    name: str
    description: str | None           # NEW field
    embedding_model: str              # NEW field
    chunk_profile: str                # NEW field
    qdrant_collection_name: str       # NEW field
    document_count: int               # EXISTS
    total_chunks: int                 # NEW field
    created_at: str                   # EXISTS
    # NOTE: current code has 4 fields (id, name, document_count, created_at).
    #       This extends to 9 fields matching the SQLiteDB collections table.

# --- Documents ---

class DocumentResponse(BaseModel):  # EXISTS: schemas.py, needs REWRITE
    id: str
    collection_id: str               # NOTE: current code has collection_ids (list). DB has singular FK.
    filename: str                     # NOTE: current code has name. DB column is filename.
    file_hash: str                    # NEW field (exists in DB)
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int                  # NEW field (exists in DB)
    ingested_at: str | None           # NOTE: current code has upload_date. DB column is ingested_at.
    # NOTE: current code statuses are uploaded/parsing/indexing/indexed/failed/deleted.
    #       DB + blueprint use pending/ingesting/completed/failed/duplicate.

class IngestionResponse(BaseModel):  # NEW
    job_id: str
    document_id: str
    status: Literal["started", "duplicate"]

class IngestionJobResponse(BaseModel):  # NEW
    id: str
    document_id: str
    status: Literal["started", "streaming", "embedding", "completed", "failed", "paused"]
    started_at: str
    finished_at: str | None
    error_msg: str | None
    chunks_processed: int
    chunks_skipped: int

# --- Chat ---

class ChatRequest(BaseModel):  # EXISTS: schemas.py, needs EXTENSION
    message: str = Field(..., min_length=1, max_length=10000)
    collection_ids: list[str] = Field(..., min_length=1)
    llm_model: str = "qwen2.5:7b"
    embed_model: str = "nomic-embed-text"            # NEW field
    session_id: str | None = None                    # EXISTS
    # NOTE: current code has max_length=2000 (extend to 10000),
    #       collection_ids defaults to empty list (make required with min_length=1),
    #       embed_model does not exist (add it).

# --- Models ---

class ModelInfo(BaseModel):  # NEW
    name: str
    provider: str               # "ollama", "openrouter", etc.
    size: str | None            # "7B", "13B", etc.
    quantization: str | None    # "Q4_K_M", "Q8_0", etc.
    context_length: int | None
    dims: int | None            # embedding dimensions (embed models only)

# --- Providers ---

class ProviderResponse(BaseModel):  # EXISTS: schemas.py, needs REWRITE
    name: str
    is_active: bool
    has_key: bool              # True if encrypted key stored (never returns the key)
    base_url: str | None
    model_count: int           # number of available models
    # NOTE: current code has type, status, model fields. This replaces them
    #       with has_key, base_url, model_count (matching blueprint + DB schema).

class ProviderKeyRequest(BaseModel):  # EXISTS as ProviderConfigRequest, needs RENAME
    api_key: str
    # NOTE: current code class is named ProviderConfigRequest.

# --- Settings ---

class SettingsResponse(BaseModel):  # NEW (settings not currently a schema)
    default_llm_model: str
    default_embed_model: str
    default_provider: str
    parent_chunk_size: int
    child_chunk_size: int
    max_iterations: int
    max_tool_calls: int
    confidence_threshold: int          # 0-100 scale, INTEGER
    groundedness_check_enabled: bool
    citation_alignment_threshold: float
    # NOTE: confidence_threshold is int (0-100), NOT float (0.0-1.0).
    #       config.py uses int = 60. DB stores as key-value text.

class SettingsUpdateRequest(BaseModel):  # NEW
    """All fields optional for partial update."""
    default_llm_model: str | None = None
    default_embed_model: str | None = None
    default_provider: str | None = None
    parent_chunk_size: int | None = None
    child_chunk_size: int | None = None
    max_iterations: int | None = None
    max_tool_calls: int | None = None
    confidence_threshold: int | None = None  # 0-100 scale, INTEGER
    groundedness_check_enabled: bool | None = None
    citation_alignment_threshold: float | None = None

# --- Observability ---

class QueryTraceResponse(BaseModel):  # EXISTS as TraceResponse, needs EXTENSION
    id: str
    session_id: str
    query: str
    collections_searched: list[str]
    meta_reasoning_triggered: bool
    latency_ms: int
    llm_model: str
    confidence_score: int | None       # 0-100 scale, INTEGER
    created_at: str
    # NOTE: current TraceResponse has query_id (rename to session_id for clarity),
    #       confidence_score is already int in code. DB column is INTEGER.

class QueryTraceDetailResponse(QueryTraceResponse):  # NEW (extends list schema)
    sub_questions: list[str]
    chunks_retrieved: list[dict]  # [{chunk_id, score, collection, source_file}]
    embed_model: str
    reasoning_steps: list[dict] | None     # from reasoning_steps_json column
    strategy_switches: list[dict] | None   # from strategy_switches_json column (FR-005)
    # NOTE: strategy_switches_json was added by spec-07 FR-005 to query_traces table.

class HealthResponse(BaseModel):  # EXISTS: schemas.py, needs REWRITE
    qdrant: Literal["ok", "error"]
    ollama: Literal["ok", "error"]
    sqlite: Literal["ok", "error"]
    qdrant_latency_ms: int | None
    ollama_latency_ms: int | None
    timestamp: str
    # NOTE: current code has status + services dict (generic).
    #       This rewrites to per-service status with latency.

class SystemStatsResponse(BaseModel):  # NEW
    total_collections: int
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_latency_ms: float
    avg_confidence: float
    meta_reasoning_rate: float  # percentage of queries triggering meta-reasoning
```

### NDJSON Event Types (POST /api/chat)

The chat endpoint streams `application/x-ndjson`. Each line is a complete JSON object followed by a newline character. There is NO SSE framing (no `data:` prefix, no `text/event-stream`).

**Current implementation** (4 event types in `backend/api/chat.py`):
```jsonl
{"type": "chunk", "text": "The answer "}
{"type": "clarification", "question": "Could you clarify..."}
{"type": "metadata", "trace_id": "xyz", "confidence": 85, "groundedness": {...}, "citations": [...], "latency_ms": 1240}
{"type": "error", "message": "Inference service unavailable", "code": "OLLAMA_UNAVAILABLE"}
```

**Target implementation** (spec-08 expands to 10 event types, keeping NDJSON format):
```jsonl
{"type": "session", "session_id": "abc-123"}
{"type": "status", "node": "classify_intent"}
{"type": "status", "node": "rewrite_query", "sub_questions": ["q1", "q2"]}
{"type": "chunk", "text": "The "}
{"type": "chunk", "text": "answer"}
{"type": "citation", "index": 1, "chunk_id": "uuid", "source": "file.pdf", "page": 3, "breadcrumb": "Ch2 > 2.3"}
{"type": "meta_reasoning", "strategy": "widen_search", "attempt": 1}
{"type": "confidence", "score": 82, "level": "high"}
{"type": "groundedness", "supported": 4, "unsupported": 1, "contradicted": 0}
{"type": "done", "latency_ms": 1240, "trace_id": "xyz-456", "session_id": "abc-123"}
{"type": "clarification", "question": "Could you clarify which API version you mean?"}
{"type": "error", "message": "Inference service unavailable", "code": "OLLAMA_UNAVAILABLE"}
```

Key changes from current implementation:
- **session** (NEW) -- emitted first, provides session_id to the client.
- **status** (NEW) -- emitted per graph node transition for progress indication.
- **chunk** (EXISTS) -- unchanged, streams answer tokens.
- **citation** (NEW) -- emitted per citation instead of bundled in metadata.
- **meta_reasoning** (NEW) -- emitted when meta-reasoning triggers a retry strategy.
- **confidence** (NEW) -- emitted as a separate event. Score is int 0-100 (not float).
- **groundedness** (NEW) -- emitted as a separate event with claim counts.
- **done** (REPLACES metadata) -- final event, carries latency_ms and trace_id.
- **clarification** (EXISTS) -- unchanged, triggers when graph interrupts for user input.
- **error** (EXISTS) -- unchanged, emitted on failures.

### Endpoint Summary Table

| Method | Path | Body/Params | Response | Status Codes |
|--------|------|-------------|----------|-------------|
| GET | /collections | -- | list[CollectionResponse] | 200 |
| POST | /collections | CollectionCreateRequest | CollectionResponse | 201, 400, 409 |
| DELETE | /collections/{id} | -- | {"status": "deleted"} | 200, 404 |
| GET | /collections/{id}/documents | -- | list[DocumentResponse] | 200, 404 |
| POST | /collections/{id}/ingest | multipart file | IngestionResponse | 202, 400, 404, 413 |
| GET | /collections/{id}/ingest/{job_id} | -- | IngestionJobResponse | 200, 404 |
| DELETE | /collections/{id}/documents/{doc_id} | -- | {"status": "deleted"} | 200, 404 |
| POST | /chat | ChatRequest | NDJSON stream | 200, 400, 503 |
| GET | /models/llm | -- | list[ModelInfo] | 200, 503 |
| GET | /models/embed | -- | list[ModelInfo] | 200, 503 |
| GET | /providers | -- | list[ProviderResponse] | 200 |
| PUT | /providers/{name}/key | ProviderKeyRequest | {"status": "saved"} | 200, 400 |
| DELETE | /providers/{name}/key | -- | {"status": "deleted"} | 200, 404 |
| GET | /providers/{name}/models | -- | list[ModelInfo] | 200, 503 |
| GET | /settings | -- | SettingsResponse | 200 |
| PUT | /settings | SettingsUpdateRequest | SettingsResponse | 200, 400 |
| GET | /traces | ?page=1&limit=50&session_id= | Paginated list[QueryTraceResponse] | 200 |
| GET | /traces/{id} | -- | QueryTraceDetailResponse | 200, 404 |
| GET | /health | -- | HealthResponse | 200 |
| GET | /stats | -- | SystemStatsResponse | 200 |

### Error Response Format

All error responses use a structured format with error code and trace ID:
```json
{"detail": "Human-readable error description", "code": "ERROR_CODE", "trace_id": "req-abc-123"}
```

Specific error examples:
| Status | Condition | Body |
|--------|----------|------|
| 400 | Invalid collection name | {"detail": "Collection name must be lowercase alphanumeric with hyphens/underscores", "code": "VALIDATION_ERROR", "trace_id": "req-abc-123"} |
| 400 | Unsupported file type | {"detail": "Unsupported file type '.exe'. Allowed: .pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h", "code": "UNSUPPORTED_FILE_TYPE", "trace_id": "req-abc-124"} |
| 404 | Collection not found | {"detail": "Collection not found", "code": "NOT_FOUND", "trace_id": "req-abc-125"} |
| 409 | Duplicate collection name | {"detail": "Collection 'arca-specs' already exists", "code": "CONFLICT", "trace_id": "req-abc-126"} |
| 413 | File too large | {"detail": "File exceeds maximum size of 100MB", "code": "FILE_TOO_LARGE", "trace_id": "req-abc-127"} |
| 503 | Ollama unavailable | {"detail": "Inference service unavailable. Check Ollama status.", "code": "OLLAMA_UNAVAILABLE", "trace_id": "req-abc-128"} |

## Dependencies

- **Internal**: spec-02/03/04 (agent graphs invoked by chat endpoint), spec-05 (accuracy subsystems emit NDJSON events), spec-06 (ingestion pipeline called by ingest endpoint), spec-07 (storage layer for all CRUD)
- **Future**: spec-10 (provider registry) is not yet implemented. For now, provider and model listing functionality will be self-contained within spec-08.
- **Libraries**: `fastapi >=0.135`, `uvicorn >=0.34`, `python-multipart >=0.0.20` (file uploads), `pydantic >=2.12` (request/response schemas), `httpx >=0.28` (async HTTP for health checks)

## Acceptance Criteria

1. All 20 endpoints are implemented and return correct status codes.
2. POST /collections validates the name pattern (lowercase alphanumeric, hyphens, underscores).
3. POST /collections/{id}/ingest validates file type (.pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java, .c, .cpp, .h) and size (100MB), triggers ingestion pipeline, returns 202.
4. POST /chat streams NDJSON events (`application/x-ndjson`) with all 10 documented event types.
5. GET /health probes Qdrant, Ollama, and SQLite with per-service status and latency measurements.
6. GET /stats computes system-wide aggregates from query_traces.
7. Rate limiting applies per endpoint category (chat: 30/min, ingest: 10/min, provider key: 5/min, default: 120/min).
8. CORS allows configured origins.
9. All error responses use the structured format with detail, code, and trace_id.
10. Provider API keys are never returned in GET responses (only `has_key: bool`).

## Architecture Reference

- **Collections router**: `backend/api/collections.py` -- EXISTS, needs extension for new schema fields
- **Documents router**: `backend/api/documents.py` -- EXISTS, needs rewrite for new schema
- **Chat router**: `backend/api/chat.py` -- EXISTS, needs NDJSON event expansion
- **Ingest router**: `backend/api/ingest.py` -- NEW, extract ingestion endpoints from documents.py or create new
- **Models router**: `backend/api/models.py` -- NEW, proxy to Ollama/providers for model listing
- **Providers router**: `backend/api/providers.py` -- EXISTS, needs extension for key delete + model listing
- **Settings router**: `backend/api/settings.py` -- NEW, settings CRUD
- **Traces/health/stats router**: `backend/api/traces.py` + `backend/api/health.py` -- EXIST, need schema rewrite
- **Middleware**: `backend/middleware.py` -- NEW, rate limiting + trace ID injection (CORS currently in main.py)
- **Schemas**: `backend/agent/schemas.py` -- EXISTS, contains current request/response models
- **App factory**: `backend/main.py` -- EXISTS, router registration + lifespan
- **Configuration**: `backend/config.py` -- EXISTS, needs new fields: `rate_limit_default_per_minute`, `rate_limit_provider_key_per_minute`
