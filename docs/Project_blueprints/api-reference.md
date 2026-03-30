# The Embedinator — API Reference

**Version**: 1.0
**Base URL**: `http://localhost:8000/api`
**Content-Type**: `application/json` (unless noted)

---

## Authentication

The Embedinator has no authentication layer in the MVP — it is a self-hosted single-user system. All endpoints are accessible without credentials. For production deployments, add a reverse proxy (Caddy/nginx) with basic auth or OAuth2 Proxy.

---

## Collections

### List Collections

```
GET /api/collections
```

**Response** `200`:
```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "arca-specs",
    "description": "ARCA web service API specifications",
    "embedding_model": "nomic-embed-text",
    "chunk_profile": "default",
    "qdrant_collection_name": "arca-specs",
    "document_count": 12,
    "total_chunks": 3400,
    "created_at": "2026-03-03T10:00:00Z"
  }
]
```

### Create Collection

```
POST /api/collections
Content-Type: application/json

{
  "name": "arca-specs",
  "description": "ARCA web service API specifications",
  "embedding_model": "nomic-embed-text"
}
```

**Request Body**:

| Field | Type | Required | Constraints | Default |
|---|---|---|---|---|
| `name` | string | Yes | `^[a-z0-9][a-z0-9_-]*$`, 1-100 chars | — |
| `description` | string | No | max 500 chars | `null` |
| `embedding_model` | string | No | Must be available in Ollama | `"nomic-embed-text"` |
| `chunk_profile` | string | No | `"default"` | `"default"` |

**Response** `201`:
```json
{
  "id": "a1b2c3d4-...",
  "name": "arca-specs",
  "description": "ARCA web service API specifications",
  "embedding_model": "nomic-embed-text",
  "chunk_profile": "default",
  "qdrant_collection_name": "arca-specs",
  "document_count": 0,
  "total_chunks": 0,
  "created_at": "2026-03-03T10:00:00Z"
}
```

**Errors**:

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Invalid name format |
| 409 | `CONFLICT` | Collection name already exists |

### Delete Collection

```
DELETE /api/collections/{id}
```

**Response** `200`:
```json
{"status": "deleted"}
```

**Errors**: `404` if collection not found.

---

## Documents

### List Documents

```
GET /api/collections/{collection_id}/documents
```

**Response** `200`:
```json
[
  {
    "id": "i9j0k1l2-...",
    "collection_id": "a1b2c3d4-...",
    "filename": "arca_api_spec_v2.pdf",
    "file_hash": "a3f5c2d8e...",
    "status": "completed",
    "chunk_count": 142,
    "ingested_at": "2026-03-03T10:05:00Z"
  }
]
```

**Document statuses**: `pending`, `ingesting`, `completed`, `failed`, `duplicate`

### Upload Document (Ingest)

```
POST /api/collections/{collection_id}/ingest
Content-Type: multipart/form-data

file: <binary>
```

**Accepted file types**: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h`
**Max file size**: 100 MB

**Response** `202`:
```json
{
  "job_id": "e5f6g7h8-...",
  "document_id": "i9j0k1l2-...",
  "status": "started"
}
```

**Errors**:

| Status | Code | Condition |
|---|---|---|
| 400 | `INVALID_FILE` | Unsupported file type |
| 404 | `NOT_FOUND` | Collection not found |
| 409 | `DUPLICATE_DOCUMENT` | File already ingested (same SHA256 hash) |
| 413 | — | File exceeds 100 MB |

### Get Ingestion Job Status

```
GET /api/collections/{collection_id}/ingest/{job_id}
```

**Response** `200`:
```json
{
  "id": "e5f6g7h8-...",
  "document_id": "i9j0k1l2-...",
  "status": "embedding",
  "started_at": "2026-03-03T10:04:00Z",
  "finished_at": null,
  "error_msg": null,
  "chunks_processed": 87,
  "chunks_skipped": 0
}
```

**Job statuses**: `started`, `streaming`, `embedding`, `completed`, `failed`, `paused`

### Delete Document

```
DELETE /api/collections/{collection_id}/documents/{document_id}
```

**Response** `200`:
```json
{"status": "deleted"}
```

---

## Chat

### Send Chat Message

```
POST /api/chat
Content-Type: application/json

{
  "message": "What authentication methods does the ARCA WSAA service support?",
  "collection_ids": ["a1b2c3d4-..."],
  "llm_model": "qwen2.5:7b",
  "embed_model": "nomic-embed-text",
  "session_id": null
}
```

**Request Body**:

| Field | Type | Required | Constraints | Default |
|---|---|---|---|---|
| `message` | string | Yes | 1-10,000 chars | — |
| `collection_ids` | string[] | Yes | At least 1 collection ID | — |
| `llm_model` | string | No | Must be available | `"qwen2.5:7b"` |
| `embed_model` | string | No | Must match collection's model | `"nomic-embed-text"` |
| `session_id` | string | No | UUID format | auto-generated |

**Response** `200` — NDJSON stream (`application/x-ndjson`):

Each line is a complete JSON object:

```jsonl
{"type": "chunk", "text": "The WSAA service supports "}
{"type": "chunk", "text": "certificate-based authentication"}
{"type": "chunk", "text": " using X.509 certificates [1]."}
{"type": "metadata", "trace_id": "trace-789", "confidence": 85, "citations": [...], "latency_ms": 2340}
```

**Event Types**:

| Type | Fields | Description |
|---|---|---|
| `chunk` | `text` | Streamed answer token(s) |
| `metadata` | `trace_id`, `confidence`, `citations[]`, `latency_ms` | Final metadata (last event) |

**Citation object in metadata**:
```json
{
  "index": 1,
  "document": "arca_api_spec_v2.pdf",
  "page": 12,
  "text": "The WSAA service uses certificate-based authentication..."
}
```

**Errors**:

| Status | Code | Condition |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing/invalid fields |
| 503 | `LLM_UNAVAILABLE` | Ollama or cloud provider unreachable |
| 503 | `QDRANT_UNAVAILABLE` | Qdrant connection failed |

---

## Models

### List LLM Models

```
GET /api/models/llm
```

**Response** `200`:
```json
[
  {
    "name": "qwen2.5:7b",
    "provider": "ollama",
    "size": "7B",
    "quantization": "Q4_K_M",
    "context_length": 32768,
    "dims": null
  }
]
```

### List Embedding Models

```
GET /api/models/embed
```

**Response** `200`:
```json
[
  {
    "name": "nomic-embed-text",
    "provider": "ollama",
    "size": null,
    "quantization": null,
    "context_length": 8192,
    "dims": 768
  }
]
```

---

## Providers

### List Providers

```
GET /api/providers
```

**Response** `200`:
```json
[
  {
    "name": "ollama",
    "is_active": true,
    "has_key": false,
    "base_url": "http://localhost:11434",
    "model_count": 3
  },
  {
    "name": "openrouter",
    "is_active": true,
    "has_key": true,
    "base_url": null,
    "model_count": 200
  }
]
```

### Save Provider API Key

```
PUT /api/providers/{name}/key
Content-Type: application/json

{
  "api_key": "sk-or-v1-..."
}
```

**Response** `200`:
```json
{"status": "saved"}
```

The API key is encrypted with Fernet before storage. It is **never** returned in any API response.

### Delete Provider API Key

```
DELETE /api/providers/{name}/key
```

**Response** `200`:
```json
{"status": "deleted"}
```

### List Provider Models

```
GET /api/providers/{name}/models
```

**Response** `200`: Same schema as `/api/models/llm`.

---

## Settings

### Get Settings

```
GET /api/settings
```

**Response** `200`:
```json
{
  "default_llm_model": "qwen2.5:7b",
  "default_embed_model": "nomic-embed-text",
  "default_provider": "ollama",
  "parent_chunk_size": 3000,
  "child_chunk_size": 500,
  "max_iterations": 10,
  "max_tool_calls": 8,
  "confidence_threshold": 0.6,
  "groundedness_check_enabled": true,
  "citation_alignment_threshold": 0.3
}
```

### Update Settings

```
PUT /api/settings
Content-Type: application/json

{
  "default_llm_model": "llama3.2",
  "max_iterations": 15
}
```

Partial updates are supported — only include fields to change.

**Response** `200`: Full settings object with updates applied.

---

## Observability

### List Traces

```
GET /api/traces?page=1&limit=50&session_id=&collection_id=&min_confidence=&max_confidence=
```

**Query Parameters**:

| Param | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `limit` | int | 50 | Results per page (max 100) |
| `session_id` | string | — | Filter by session |
| `collection_id` | string | — | Filter by collection searched |
| `min_confidence` | float | — | Minimum confidence score |
| `max_confidence` | float | — | Maximum confidence score |

**Response** `200`:
```json
[
  {
    "id": "trace-789",
    "session_id": "sess-xyz",
    "query": "What authentication methods does WSAA support?",
    "collections_searched": ["arca-specs"],
    "meta_reasoning_triggered": false,
    "latency_ms": 2340,
    "llm_model": "qwen2.5:7b",
    "confidence_score": 0.85,
    "created_at": "2026-03-03T10:32:15Z"
  }
]
```

### Get Trace Detail

```
GET /api/traces/{id}
```

**Response** `200`:
```json
{
  "id": "trace-789",
  "session_id": "sess-xyz",
  "query": "What authentication methods does WSAA support?",
  "sub_questions": ["What authentication methods does WSAA support?"],
  "collections_searched": ["arca-specs"],
  "chunks_retrieved": [
    {"chunk_id": "550e8400-...", "score": 0.92, "collection": "arca-specs", "source_file": "arca_api_spec_v2.pdf"}
  ],
  "meta_reasoning_triggered": false,
  "latency_ms": 2340,
  "llm_model": "qwen2.5:7b",
  "embed_model": "nomic-embed-text",
  "confidence_score": 0.85,
  "created_at": "2026-03-03T10:32:15Z"
}
```

### Health Check

```
GET /api/health
```

**Response** `200`:
```json
{
  "qdrant": "ok",
  "ollama": "ok",
  "sqlite": "ok",
  "qdrant_latency_ms": 3,
  "ollama_latency_ms": 12,
  "timestamp": "2026-03-03T10:32:15Z"
}
```

Returns `503` if any service is unreachable (with `"error"` status for that service).

### System Stats

```
GET /api/stats
```

**Response** `200`:
```json
{
  "total_collections": 3,
  "total_documents": 25,
  "total_chunks": 4600,
  "total_queries": 142,
  "avg_latency_ms": 2100.5,
  "avg_confidence": 0.78,
  "meta_reasoning_rate": 0.12
}
```

---

## Error Response Format

All errors follow a consistent format:

```json
{
  "detail": "Collection 'arca-specs' already exists",
  "code": "CONFLICT",
  "trace_id": "req-abc-123"
}
```

| Field | Type | Description |
|---|---|---|
| `detail` | string | User-facing error message |
| `code` | string | Machine-readable error code |
| `trace_id` | string | Request trace ID for debugging |

### Error Code Reference

| Code | HTTP Status | Description |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Invalid request body or parameters |
| `INVALID_FILE` | 400 | Unsupported file type or content |
| `PROVIDER_AUTH_ERROR` | 401 | Invalid API key for provider |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | Resource already exists |
| `DUPLICATE_DOCUMENT` | 409 | Document already ingested |
| `RATE_LIMITED` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Unexpected server error |
| `QDRANT_UNAVAILABLE` | 503 | Vector database unreachable |
| `LLM_UNAVAILABLE` | 503 | LLM inference service unreachable |
| `EMBEDDING_UNAVAILABLE` | 503 | Embedding service unreachable |

---

## Rate Limits

| Endpoint Pattern | Limit | Window |
|---|---|---|
| `POST /api/chat` | 30 requests | per minute |
| `POST /api/collections/*/ingest` | 10 requests | per minute |
| `PUT /api/providers/*/key` | 5 requests | per minute |
| All other endpoints | 120 requests | per minute |

Rate limiting is per-client-IP using a sliding window counter. When rate limited, the response is:

```
HTTP 429 Too Many Requests
Retry-After: <seconds>
```

---

*Extracted and expanded from `docs/architecture-design.md` Section 11 (API Reference). For Pydantic schema definitions and SSE event type details, see the architecture document.*
