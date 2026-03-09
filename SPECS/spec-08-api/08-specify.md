# Spec 08: API Reference -- Feature Specification Context

## Feature Description

The API layer is a FastAPI application that exposes all backend functionality through a RESTful HTTP interface. It is the sole interface between the frontend (Next.js) and the backend systems (agent graphs, ingestion pipeline, storage, providers). The API is organized into six endpoint groups:

1. **Collections** -- CRUD operations for document collections (each maps to a Qdrant collection).
2. **Documents** -- Document listing, file upload (multipart, triggers ingestion pipeline), ingestion job status polling, and document deletion.
3. **Chat** -- The primary endpoint. Accepts a user message + collection IDs, invokes the agent graph, and streams the response as Server-Sent Events (SSE) with token-by-token output, citations, confidence scores, groundedness results, and trace IDs.
4. **Models** -- Proxy endpoints to list available LLM and embedding models from configured providers (primarily Ollama).
5. **Providers** -- Provider management: list providers, save/delete API keys (Fernet-encrypted), list models per provider.
6. **Observability** -- Query trace listing/detail, health check (Qdrant + Ollama + SQLite status), and system-wide statistics.

Additional cross-cutting concerns: Settings CRUD, rate limiting per endpoint category, CORS configuration, and trace ID injection middleware.

## Requirements

### Functional Requirements

- **Base URL**: `http://localhost:8000/api`
- **Collections CRUD**: GET /collections (list), POST /collections (create with name validation), DELETE /collections/{id}.
- **Document Management**: GET /collections/{id}/documents (list), POST /collections/{id}/ingest (multipart file upload), GET /collections/{id}/ingest/{job_id} (poll status), DELETE /collections/{id}/documents/{doc_id}.
- **Chat with SSE Streaming**: POST /chat accepts `ChatRequest`, returns an SSE stream. SSE events include: session, status, token, citation, meta_reasoning, confidence, groundedness, done, error.
- **Model Listing**: GET /models/llm, GET /models/embed -- proxy to Ollama (and other providers).
- **Provider Management**: GET /providers (list), PUT /providers/{name}/key (save encrypted API key), DELETE /providers/{name}/key, GET /providers/{name}/models.
- **Settings**: GET /settings, PUT /settings (partial update).
- **Observability**: GET /traces (paginated), GET /traces/{id} (detail), GET /health (service status), GET /stats (system-wide metrics).
- **Rate Limiting**: Chat: 30/min, Ingest: 10/min, Default: 120/min.
- **CORS**: Allow origins from `cors_origins` config (default: localhost:3000).
- **File Validation**: Allowed extensions: .pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java. Max size: 100MB.

### Non-Functional Requirements

- SSE streaming must deliver tokens as they are generated (no buffering).
- All endpoints must return proper HTTP status codes and structured error responses.
- Rate limiting must apply per-endpoint-category, not globally.
- CORS must be configurable via environment variable.
- Health check must probe Qdrant, Ollama, and SQLite with latency measurements.

## Key Technical Details

### Pydantic Schemas

```python
# --- Collections ---

class CreateCollectionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    description: Optional[str] = Field(None, max_length=500)
    embedding_model: str = "nomic-embed-text"
    chunk_profile: str = "default"

class CollectionSchema(BaseModel):
    id: str
    name: str
    description: Optional[str]
    embedding_model: str
    chunk_profile: str
    qdrant_collection_name: str
    document_count: int
    total_chunks: int
    created_at: str

# --- Documents ---

class DocumentSchema(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_hash: str
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int
    ingested_at: Optional[str]

class IngestionResponse(BaseModel):
    job_id: str
    document_id: str
    status: Literal["started", "duplicate"]

class IngestionJobSchema(BaseModel):
    id: str
    document_id: str
    status: Literal["started", "streaming", "embedding", "completed", "failed", "paused"]
    started_at: str
    finished_at: Optional[str]
    error_msg: Optional[str]
    chunks_processed: int
    chunks_skipped: int

# --- Chat ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    collection_ids: List[str] = Field(..., min_length=1)
    llm_model: str = "llama3.2"
    embed_model: str = "nomic-embed-text"
    session_id: Optional[str] = None  # auto-generated if omitted

# --- Models ---

class ModelInfo(BaseModel):
    name: str
    provider: str               # "ollama", "openrouter", etc.
    size: Optional[str]         # "7B", "13B", etc.
    quantization: Optional[str] # "Q4_K_M", "Q8_0", etc.
    context_length: Optional[int]
    dims: Optional[int]         # embedding dimensions (embed models only)

# --- Providers ---

class ProviderSchema(BaseModel):
    name: str
    is_active: bool
    has_key: bool         # True if encrypted key stored (never returns the key)
    base_url: Optional[str]
    model_count: int      # number of available models

# --- Settings ---

class SettingsSchema(BaseModel):
    default_llm_model: str
    default_embed_model: str
    default_provider: str
    parent_chunk_size: int
    child_chunk_size: int
    max_iterations: int
    max_tool_calls: int
    confidence_threshold: float
    groundedness_check_enabled: bool
    citation_alignment_threshold: float

# --- Observability ---

class QueryTraceSchema(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: List[str]
    meta_reasoning_triggered: bool
    latency_ms: int
    llm_model: str
    confidence_score: Optional[float]
    created_at: str

class QueryTraceDetailSchema(QueryTraceSchema):
    sub_questions: List[str]
    chunks_retrieved: List[dict]  # [{chunk_id, score, collection, source_file}]
    embed_model: str

class HealthResponse(BaseModel):
    qdrant: Literal["ok", "error"]
    ollama: Literal["ok", "error"]
    sqlite: Literal["ok", "error"]
    qdrant_latency_ms: Optional[int]
    ollama_latency_ms: Optional[int]
    timestamp: str

class SystemStatsSchema(BaseModel):
    total_collections: int
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_latency_ms: float
    avg_confidence: float
    meta_reasoning_rate: float  # percentage of queries triggering meta-reasoning
```

### SSE Event Types (POST /api/chat)

```
data: {"type": "session", "session_id": "abc-123"}
data: {"type": "status", "node": "classify_intent"}
data: {"type": "status", "node": "rewrite_query", "sub_questions": ["q1", "q2"]}
data: {"type": "token", "content": "The "}
data: {"type": "token", "content": "answer"}
data: {"type": "citation", "index": 1, "chunk_id": "uuid", "source": "file.pdf", "page": 3, "breadcrumb": "Ch2 > 2.3"}
data: {"type": "meta_reasoning", "strategy": "widen_search", "attempt": 1}
data: {"type": "confidence", "score": 0.82, "level": "high"}
data: {"type": "groundedness", "supported": 4, "unsupported": 1, "contradicted": 0}
data: {"type": "done", "latency_ms": 1240, "trace_id": "xyz-456"}
data: {"type": "error", "message": "Inference service unavailable", "code": "OLLAMA_UNAVAILABLE"}
```

### Endpoint Summary Table

| Method | Path | Body/Params | Response | Status Codes |
|--------|------|-------------|----------|-------------|
| GET | /collections | -- | List[CollectionSchema] | 200 |
| POST | /collections | CreateCollectionRequest | CollectionSchema | 201, 400, 409 |
| DELETE | /collections/{id} | -- | {status: "deleted"} | 200, 404 |
| GET | /collections/{id}/documents | -- | List[DocumentSchema] | 200, 404 |
| POST | /collections/{id}/ingest | multipart file | IngestionResponse | 202, 400, 404, 413 |
| GET | /collections/{id}/ingest/{job_id} | -- | IngestionJobSchema | 200, 404 |
| DELETE | /collections/{id}/documents/{doc_id} | -- | {status: "deleted"} | 200, 404 |
| POST | /chat | ChatRequest | SSE stream | 200, 400, 503 |
| GET | /models/llm | -- | List[ModelInfo] | 200, 503 |
| GET | /models/embed | -- | List[ModelInfo] | 200, 503 |
| GET | /providers | -- | List[ProviderSchema] | 200 |
| PUT | /providers/{name}/key | {"api_key": "sk-..."} | {status: "saved"} | 200, 400 |
| DELETE | /providers/{name}/key | -- | {status: "deleted"} | 200, 404 |
| GET | /providers/{name}/models | -- | List[ModelInfo] | 200, 503 |
| GET | /settings | -- | SettingsSchema | 200 |
| PUT | /settings | SettingsSchema (partial) | SettingsSchema | 200, 400 |
| GET | /traces | ?page=1&limit=50&session_id= | Paginated List[QueryTraceSchema] | 200 |
| GET | /traces/{id} | -- | QueryTraceDetailSchema | 200, 404 |
| GET | /health | -- | HealthResponse | 200 |
| GET | /stats | -- | SystemStatsSchema | 200 |

### Error Response Format

All error responses follow this structure:
```json
{"detail": "Human-readable error description"}
```

Specific error examples:
| Status | Condition | Body |
|--------|----------|------|
| 400 | Invalid collection name | {"detail": "Collection name must be lowercase alphanumeric with hyphens/underscores"} |
| 400 | Unsupported file type | {"detail": "Unsupported file type '.exe'. Allowed: .pdf, .md, .txt, .py, .js, .ts, .rs, .go, .java"} |
| 404 | Collection not found | {"detail": "Collection not found"} |
| 409 | Duplicate collection name | {"detail": "Collection 'arca-specs' already exists"} |
| 413 | File too large | {"detail": "File exceeds maximum size of 100MB"} |
| 503 | Ollama unavailable | {"detail": "Inference service unavailable. Check Ollama status."} |

## Dependencies

- **Internal**: spec-02/03/04 (agent graphs invoked by chat endpoint), spec-05 (accuracy subsystems emit SSE events), spec-06 (ingestion pipeline called by ingest endpoint), spec-07 (storage layer for all CRUD), spec-10 (provider registry for model listing and key management)
- **Libraries**: `fastapi >=0.135`, `uvicorn >=0.34`, `python-multipart >=0.0.20` (file uploads), `pydantic >=2.12` (request/response schemas), `httpx >=0.28` (async HTTP for health checks)

## Acceptance Criteria

1. All 20 endpoints are implemented and return correct status codes.
2. POST /collections validates the name pattern (lowercase alphanumeric, hyphens, underscores).
3. POST /collections/{id}/ingest validates file type and size, triggers ingestion pipeline, returns 202.
4. POST /chat streams SSE events with all documented event types.
5. GET /health probes Qdrant, Ollama, and SQLite with latency measurements.
6. GET /stats computes system-wide aggregates from query_traces.
7. Rate limiting applies per endpoint category (chat: 30/min, ingest: 10/min, default: 120/min).
8. CORS allows configured origins.
9. All error responses use the standard `{"detail": "..."}` format.
10. Provider API keys are never returned in GET responses (only `has_key: bool`).

## Architecture Reference

- **Collections router**: `backend/api/collections.py`
- **Chat router**: `backend/api/chat.py`
- **Models router**: `backend/api/models.py`
- **Settings router**: `backend/api/settings.py`
- **Providers router**: `backend/api/providers.py`
- **Traces/health/stats router**: `backend/api/traces.py`
- **App factory**: `backend/main.py` -- FastAPI app factory, router registration, lifespan
- **Middleware**: `backend/middleware.py` -- CORS, rate limiting, trace ID injection
- **Configuration**: `backend/config.py` -- `rate_limit_chat_per_minute`, `rate_limit_ingest_per_minute`, `rate_limit_default_per_minute`, `cors_origins`
