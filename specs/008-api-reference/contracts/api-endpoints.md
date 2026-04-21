# API Endpoint Contracts — Spec 08 (API Reference)

**Generated**: 2026-03-15 | **Base URL**: `/api` | **Format**: NDJSON (chat), JSON (all others)

All endpoints use the `/api` prefix. No version prefix (FR-001, clarification Q1).
All error responses include `error.code`, `error.message`, and `trace_id` at the top level (FR-026).

---

## Collections

### `GET /api/collections`

List all collections.

**Response `200`**:
```json
{
  "collections": [
    {
      "id": "uuid",
      "name": "my-docs",
      "description": null,
      "embedding_model": "nomic-embed-text",
      "chunk_profile": "default",
      "document_count": 5,
      "created_at": "2026-03-01T12:00:00Z"
    }
  ]
}
```

**FR**: FR-004

---

### `POST /api/collections`

Create a new collection.

**Request**:
```json
{
  "name": "my-docs",
  "description": "Optional description",
  "embedding_model": "nomic-embed-text",
  "chunk_profile": "default"
}
```

**Validation**:
- `name`: required, `^[a-z0-9][a-z0-9_-]*$`, max 100 chars (FR-002)
- `embedding_model`: optional, defaults to `settings.default_embed_model`
- `chunk_profile`: optional, defaults to `"default"`

**Response `201`**: `CollectionResponse`

**Response `409`**: `{"error": {"code": "COLLECTION_NAME_CONFLICT", "message": "...", "details": {}}, "trace_id": "..."}`

**Response `400`**: `{"error": {"code": "COLLECTION_NAME_INVALID", "message": "...", "details": {}}, "trace_id": "..."}`

**FR**: FR-002, FR-003

---

### `DELETE /api/collections/{collection_id}`

Delete a collection and all associated data.

**Path params**: `collection_id` (UUID)

**Behavior**:
1. Cancel active ingestion jobs (status → `failed`)
2. Delete all documents
3. Delete Qdrant collection (via `QdrantStorage.delete_collection()`)
4. Delete collection record

**Response `204`**: No content

**Response `404`**: `COLLECTION_NOT_FOUND`

**FR**: FR-005

---

## Documents

### `GET /api/documents`

List documents, optionally filtered by collection.

**Query params**: `collection_id` (optional UUID)

**Response `200`**:
```json
{
  "documents": [
    {
      "id": "uuid",
      "collection_id": "uuid",
      "filename": "report.pdf",
      "status": "completed",
      "chunk_count": 42,
      "created_at": "2026-03-01T12:00:00Z",
      "updated_at": "2026-03-01T12:05:00Z"
    }
  ]
}
```

**FR**: FR-006

---

### `GET /api/documents/{doc_id}`

Get document detail.

**Response `200`**: `DocumentResponse`

**Response `404`**: `DOCUMENT_NOT_FOUND`

---

### `DELETE /api/documents/{doc_id}`

Delete a document (soft delete). QueryTraces retain passage text with `source_removed: true`.

**Response `204`**: No content

**Response `404`**: `DOCUMENT_NOT_FOUND`

**FR**: FR-012

---

## Ingestion

### `POST /api/collections/{collection_id}/ingest`

Upload a file to a collection and trigger background ingestion.

**Request**: `multipart/form-data`
- `file`: uploaded file (UploadFile)

**Validation**:
- Extension must be in: `.pdf .md .txt .py .js .ts .rs .go .java .c .cpp .h` (FR-007)
- Size must be ≤ 100 MB (FR-008)
- Collection must exist (→ 404 if not)
- Duplicate detection: SHA-256 hash check (FR-011)

**Response `202`** (accepted, processing in background):
```json
{
  "document_id": "uuid",
  "job_id": "uuid",
  "status": "started",
  "filename": "report.pdf"
}
```

**Response `400`**: `FILE_FORMAT_NOT_SUPPORTED` or `INVALID_REQUEST`

**Response `409`**: `DUPLICATE_DOCUMENT` (content hash already ingested with `completed` status)

**Response `413`**: `FILE_TOO_LARGE`

**Response `404`**: `COLLECTION_NOT_FOUND`

**FR**: FR-007, FR-008, FR-009, FR-011

---

### `GET /api/collections/{collection_id}/ingest/{job_id}`

Poll ingestion job status.

**Response `200`** (`IngestionJobResponse`):
```json
{
  "job_id": "uuid",
  "document_id": "uuid",
  "status": "embedding",
  "chunks_processed": 15,
  "chunks_total": null,
  "error_message": null,
  "started_at": "2026-03-01T12:00:00Z",
  "completed_at": null
}
```

**Response `404`**: `JOB_NOT_FOUND`

**FR**: FR-010

---

## Chat

### `POST /api/chat`

Send a message and receive a streamed response.

**Request**:
```json
{
  "message": "What is the main finding in the report?",
  "collection_ids": ["uuid1", "uuid2"],
  "session_id": "optional-existing-session-id",
  "llm_model": "qwen2.5:7b"
}
```

**Validation**:
- `collection_ids`: required, non-empty list (→ 400 if empty)
- `message`: required, non-empty string
- `session_id`: optional; if omitted, a new UUID4 is generated

**Response `200`**: `StreamingResponse` with `Content-Type: application/x-ndjson`

Each line is a complete JSON object (no `data:` prefix):

```
{"type":"session","session_id":"..."}
{"type":"status","node":"query_rewrite"}
{"type":"status","node":"research"}
{"type":"chunk","text":"The main finding"}
{"type":"chunk","text":" is that..."}
{"type":"citation","citations":[{"chunk_id":"...","source":"report.pdf","text":"...","score":0.87}]}
{"type":"meta_reasoning","strategies_attempted":["WIDEN_SEARCH"]}
{"type":"confidence","score":82}
{"type":"groundedness","overall_grounded":true,"supported":3,"unsupported":0,"contradicted":0}
{"type":"done","latency_ms":1240,"trace_id":"uuid"}
```

**On clarification interrupt**:
```
{"type":"session","session_id":"..."}
{"type":"clarification","question":"Are you asking about Q1 or Q2 results?"}
```
(stream ends after clarification — client must resume with answer)

**On error**:
```
{"type":"error","message":"A required service is temporarily unavailable.","code":"CIRCUIT_OPEN","trace_id":"uuid"}
```

**Rate limit**: 30 requests/minute per IP (FR-024, SC-004)

**FR**: FR-013, FR-014, FR-015, FR-016

---

## Models

### `GET /api/models/llm`

List available language models from all configured providers.

**Response `200`**:
```json
{
  "models": [
    {
      "name": "qwen2.5:7b",
      "provider": "ollama",
      "model_type": "llm",
      "size_gb": 4.7,
      "quantization": "Q4_K_M",
      "context_length": 32768
    }
  ]
}
```

**Response `503`**: `SERVICE_UNAVAILABLE` (if Ollama is unreachable)

**FR**: FR-017

---

### `GET /api/models/embed`

List available embedding models.

**Response `200`**: Same structure as `/models/llm`, `model_type: "embed"`

**FR**: FR-017

---

## Providers

### `GET /api/providers`

List all configured providers.

**Response `200`**:
```json
{
  "providers": [
    {
      "name": "ollama",
      "is_active": true,
      "has_key": false,
      "base_url": "http://ollama:11434",
      "model_count": 3
    },
    {
      "name": "openai",
      "is_active": false,
      "has_key": true,
      "base_url": null,
      "model_count": 0
    }
  ]
}
```

**Security**: `has_key: bool` only — API key value NEVER returned (FR-018, SC-005)

---

### `PUT /api/providers/{name}/key`

Save or replace an encrypted API key for a cloud provider.

**Request**:
```json
{"api_key": "sk-..."}
```

**Response `200`**:
```json
{"name": "openai", "has_key": true}
```

**Response `404`**: `PROVIDER_NOT_FOUND`

**Response `503`**: `KEY_MANAGER_UNAVAILABLE` (if `EMBEDINATOR_FERNET_KEY` not set)

**Rate limit**: 5 requests/minute per IP (FR-024)

**FR**: FR-018

---

### `DELETE /api/providers/{name}/key`

Remove a stored API key.

**Response `200`**:
```json
{"name": "openai", "has_key": false}
```

**Response `404`**: `PROVIDER_NOT_FOUND`

**Rate limit**: 5 requests/minute per IP (FR-024)

**FR**: FR-019

---

### `GET /api/providers/{name}/models`

List models available from a specific provider.

**Response `200`**: `{"models": [ModelInfo, ...]}`

**Response `404`**: `PROVIDER_NOT_FOUND`

**Response `503`**: `SERVICE_UNAVAILABLE` (if provider is unreachable)

---

## Settings

### `GET /api/settings`

Get current system-wide settings (DB overrides merged with config defaults).

**Response `200`** (`SettingsResponse`):
```json
{
  "default_llm_model": "qwen2.5:7b",
  "default_embed_model": "nomic-embed-text",
  "confidence_threshold": 60,
  "groundedness_check_enabled": true,
  "citation_alignment_threshold": 0.3,
  "parent_chunk_size": 2000,
  "child_chunk_size": 500
}
```

**FR**: FR-020

---

### `PUT /api/settings`

Partially update settings. Only submitted fields change; all others retain current values.

**Request** (all fields optional):
```json
{
  "confidence_threshold": 75,
  "groundedness_check_enabled": false
}
```

**Validation**:
- `confidence_threshold`: int, must be 0–100 (→ 400 `SETTINGS_VALIDATION_ERROR` otherwise)

**Response `200`**: Full `SettingsResponse` after update

**Behavior**: Settings apply to new chat sessions only. Active sessions continue with the values in effect at session start (FR-020 clarification).

**FR**: FR-020

---

## Observability

### `GET /api/traces`

List query traces (paginated).

**Query params**:
- `session_id`: optional string filter
- `collection_id`: optional UUID filter
- `min_confidence`: optional int (0–100)
- `max_confidence`: optional int (0–100)
- `limit`: int (1–100, default 20)
- `offset`: int (default 0)

**Response `200`**:
```json
{
  "traces": [QueryTraceResponse, ...],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

**Note**: Empty filter matching → empty list (not 404).

**FR**: FR-021

---

### `GET /api/traces/{trace_id}`

Get full trace detail.

**Response `200`**: `QueryTraceDetailResponse` (includes sub_questions, chunks_retrieved, reasoning_steps, strategy_switches)

**Response `404`**: `TRACE_NOT_FOUND`

**FR**: FR-021

---

### `GET /api/stats`

Aggregate system statistics from historical query data.

**Response `200`**:
```json
{
  "total_collections": 3,
  "total_documents": 47,
  "total_chunks": 8920,
  "total_queries": 312,
  "avg_confidence": 74.2,
  "avg_latency_ms": 1840.5,
  "meta_reasoning_rate": 0.12
}
```

**FR**: FR-023

---

### `GET /api/health`

Probe all connected services independently with latency measurements.

**Response `200`** (all healthy):
```json
{
  "status": "healthy",
  "services": [
    {"name": "sqlite", "status": "ok", "latency_ms": 0.4, "error_message": null},
    {"name": "qdrant", "status": "ok", "latency_ms": 12.3, "error_message": null},
    {"name": "ollama", "status": "ok", "latency_ms": 45.1, "error_message": null}
  ]
}
```

**Response `503`** (any service down):
```json
{
  "status": "degraded",
  "services": [
    {"name": "sqlite", "status": "ok", "latency_ms": 0.3, "error_message": null},
    {"name": "qdrant", "status": "error", "latency_ms": null, "error_message": "Connection refused"},
    {"name": "ollama", "status": "ok", "latency_ms": 41.2, "error_message": null}
  ]
}
```

**Performance**: Must respond in < 1 second (SC-008). Target: < 50ms `GET /api/health` per constitution.

**FR**: FR-022

---

## Middleware

### Rate Limiting (FR-024)

All endpoints enforce per-IP rate limits (sliding window, 60 seconds):

| Category | Limit | Match Condition |
|----------|-------|-----------------|
| Chat | 30/min | `POST /api/chat` |
| Ingestion | 10/min | `POST /api/collections/*/ingest` |
| Provider key | 5/min | `PUT` or `DELETE /api/providers/*/key` |
| General | 120/min | everything else |

On limit exceeded → `429 Too Many Requests`:
```json
{
  "error": {"code": "RATE_LIMIT_EXCEEDED", "message": "...", "details": {"retry_after_seconds": 60}},
  "trace_id": "..."
}
```

Header: `Retry-After: 60`

### Trace ID Injection

Every request receives a UUID4 trace ID:
- Injected into structlog context: `bind_contextvars(trace_id=trace_id)`
- Returned in response header: `X-Trace-ID: <uuid>`
- Included in all error response bodies as `"trace_id": "..."`

### CORS (FR-025)

Configurable origins via `settings.cors_origins` (default: `http://localhost:3000`).
Methods: `*`, Headers: `*`, Credentials: not required (no auth).
