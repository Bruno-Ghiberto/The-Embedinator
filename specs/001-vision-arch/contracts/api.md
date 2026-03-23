# API Contracts: Vision & System Architecture

**Date**: 2026-03-10 | **Branch**: `001-vision-arch` | **Phase**: 1 (Design)

This document specifies the backend REST API endpoints, request/response schemas, and error handling for Phase 1 MVP.

## Base URL

```
http://localhost:8000  (local development)
http://embedinator:8000  (Docker Compose)
```

## Authentication

**No authentication required** for Phase 1 (local network assumed trusted).

---

## Endpoints

### Collections

#### `GET /api/collections`

List all collections.

**Request**:
```http
GET /api/collections HTTP/1.1
```

**Response** (200 OK):
```json
{
  "collections": [
    {
      "id": "col-001",
      "name": "Project Files",
      "document_count": 5,
      "created_at": "2026-03-10T10:00:00Z"
    },
    {
      "id": "col-002",
      "name": "Legal Docs",
      "document_count": 3,
      "created_at": "2026-03-10T10:05:00Z"
    }
  ]
}
```

---

#### `POST /api/collections`

Create a new collection.

**Request**:
```json
{
  "name": "My Collection"
}
```

**Response** (201 Created):
```json
{
  "id": "col-abc123",
  "name": "My Collection",
  "created_at": "2026-03-10T10:15:00Z"
}
```

**Errors**:
- 400: Name empty or > 255 chars
- 409: Name already exists

---

#### `DELETE /api/collections/{id}`

Delete a collection.

**Request**:
```http
DELETE /api/collections/col-001 HTTP/1.1
```

**Response** (204 No Content):
```
```

**Errors**:
- 404: Collection not found

**Side effects**: Documents remain in other collections; orphaned documents are still queryable if they belong to other collections.

---

### Documents

#### `POST /api/documents`

Upload a document and add to collection(s).

**Request** (multipart/form-data):
```
POST /api/documents HTTP/1.1
Content-Type: multipart/form-data

----boundary
Content-Disposition: form-data; name="file"; filename="report.pdf"
Content-Type: application/pdf

[binary PDF content]
----boundary
Content-Disposition: form-data; name="collection_ids"

["col-001", "col-002"]
----boundary--
```

**Response** (202 Accepted — processing happens asynchronously):
```json
{
  "id": "doc-xyz789",
  "name": "report.pdf",
  "collection_ids": ["col-001", "col-002"],
  "status": "uploaded",
  "upload_date": "2026-03-10T10:20:00Z"
}
```

**Polling for completion** (check status):
```http
GET /api/documents/doc-xyz789 HTTP/1.1
```

Response shows status progression: `uploaded` → `parsing` → `indexing` → `indexed`

**Supported formats**: PDF, Markdown (.md), plain text (.txt)

**Errors**:
- 400: No file provided, or file format not supported
- 400: collection_ids empty
- 413: File too large (>100MB)

---

#### `GET /api/documents`

List documents (optionally filtered by collection).

**Request**:
```http
GET /api/documents?collection_id=col-001 HTTP/1.1
```

**Response** (200 OK):
```json
{
  "documents": [
    {
      "id": "doc-001",
      "name": "report.pdf",
      "collection_ids": ["col-001"],
      "status": "indexed",
      "upload_date": "2026-03-10T10:15:00Z"
    }
  ]
}
```

**Query params**:
- `collection_id` (optional): Filter by collection

---

#### `DELETE /api/documents/{id}`

Delete a document from all collections and mark as deleted.

**Request**:
```http
DELETE /api/documents/doc-001 HTTP/1.1
```

**Response** (204 No Content):
```
```

**Side effects**: Document marked as `deleted`; existing traces retain captured passage text with `source_removed: true`.

**Errors**:
- 404: Document not found

---

### Chat

#### `POST /api/chat`

Submit a query and stream answer response.

**Request** (application/json):
```json
{
  "query": "What are the main findings?",
  "collection_ids": ["col-001", "col-002"],
  "model_name": "qwen2.5:7b"
}
```

**Response** (200 OK, application/x-ndjson — newline-delimited JSON stream):
```
{"type": "chunk", "text": "The"}
{"type": "chunk", "text": " main"}
{"type": "chunk", "text": " findings"}
{"type": "chunk", "text": " are"}
...
{"type": "metadata", "trace_id": "trace-12345", "confidence_score": 87, "citations_count": 3}
```

**Stream protocol**:
1. Each line is a JSON object followed by newline
2. `type: "chunk"` sends answer text incrementally
3. `type: "metadata"` sends final metadata (trace_id, confidence, citation count)
4. Stream ends with EOF

**First words appear within 1 second** (SC-002)

**Errors**:
- 400: query empty, collection_ids empty
- 404: Collection not found
- 503: Ollama or Qdrant unavailable

---

### Traces

#### `GET /api/traces/{trace_id}`

Retrieve full trace for a query.

**Request**:
```http
GET /api/traces/trace-12345 HTTP/1.1
```

**Response** (200 OK):
```json
{
  "id": "trace-12345",
  "query_id": "query-001",
  "query_text": "What are the main findings?",
  "collections_searched": ["col-001", "col-002"],
  "passages_retrieved": [
    {
      "id": "passage-abc",
      "document_id": "doc-001",
      "document_name": "report.pdf",
      "text": "The key insight is...",
      "relevance_score": 0.94,
      "chunk_index": 42,
      "source_removed": false
    },
    {
      "id": "passage-def",
      "document_id": "doc-002",
      "document_name": "executive_summary.md",
      "text": "Summary: ...",
      "relevance_score": 0.78,
      "chunk_index": 5,
      "source_removed": false
    }
  ],
  "confidence_score": 87,
  "created_at": "2026-03-10T10:25:00Z"
}
```

**Errors**:
- 404: Trace not found

---

### Providers

#### `GET /api/providers`

List available providers and active status.

**Request**:
```http
GET /api/providers HTTP/1.1
```

**Response** (200 OK):
```json
{
  "providers": [
    {
      "name": "ollama",
      "type": "local",
      "is_active": true,
      "status": "ready",
      "model": "qwen2.5:7b"
    },
    {
      "name": "openrouter",
      "type": "cloud",
      "is_active": false,
      "status": "configured",
      "model": "qwen/qwen-2.5-7b"
    }
  ]
}
```

---

#### `POST /api/providers/{name}/activate`

Activate a provider for use in queries.

**Request**:
```json
{
  "name": "openrouter"
}
```

**Response** (200 OK):
```json
{
  "name": "openrouter",
  "is_active": true
}
```

**Errors**:
- 404: Provider not found
- 400: Provider not configured (no API key)

---

#### `POST /api/providers/{name}/config`

Configure or update a provider's API key.

**Request**:
```json
{
  "api_key": "sk-..."
}
```

**Response** (200 OK):
```json
{
  "name": "openrouter",
  "type": "cloud",
  "configured": true
}
```

**Security**: API key is encrypted in storage; never returned in responses.

**Errors**:
- 400: API key format invalid
- 404: Provider not found

---

### Health

#### `GET /api/health`

System health check.

**Request**:
```http
GET /api/health HTTP/1.1
```

**Response** (200 OK if healthy):
```json
{
  "status": "healthy",
  "services": {
    "sqlite": "ok",
    "qdrant": "ok",
    "ollama": "ok"
  }
}
```

**Response** (503 Service Unavailable if degraded):
```json
{
  "status": "degraded",
  "services": {
    "sqlite": "ok",
    "qdrant": "error: connection refused",
    "ollama": "ok"
  }
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": {
    "code": "COLLECTION_NOT_FOUND",
    "message": "Collection 'col-001' not found",
    "details": {}
  }
}
```

**Common error codes**:
- `COLLECTION_NOT_FOUND` (404)
- `DOCUMENT_NOT_FOUND` (404)
- `TRACE_NOT_FOUND` (404)
- `INVALID_REQUEST` (400)
- `FILE_FORMAT_NOT_SUPPORTED` (400)
- `SERVICE_UNAVAILABLE` (503)
- `INTERNAL_SERVER_ERROR` (500)

---

## Request/Response Headers

**Request**:
```
Content-Type: application/json
Accept: application/json
```

**Response**:
```
Content-Type: application/json
X-Trace-ID: [UUID for request tracing]
```

---

## Rate Limiting

**Phase 1**: No rate limiting (local, trusted network)

**Phase 2**: Planned per-endpoint rate limits:
- Chat endpoint: 100 requests/minute per session
- Upload endpoint: 10 requests/minute

---

## Streaming Response Format

For chat endpoint (SSE-like streaming via NDJSON):

**Format**: Each line is a complete JSON object

```
{"type": "chunk", "text": "The"}
{"type": "chunk", "text": " main"}
{"type": "chunk", "text": " findings"}
...
{"type": "metadata", "trace_id": "trace-abc", "confidence_score": 92, "citations": [{"document_name": "report.pdf", "passage_text": "..."}]}
```

**Client consumption** (JavaScript):
```javascript
const response = await fetch('/api/chat', {
  method: 'POST',
  body: JSON.stringify({ query, collection_ids, model_name })
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const line = decoder.decode(value);
  const data = JSON.parse(line);

  if (data.type === 'chunk') {
    // Display text chunk in UI
    displayText(data.text);
  } else if (data.type === 'metadata') {
    // Store trace, confidence, etc.
    storeMetadata(data);
  }
}
```

---

**Status**: API contracts complete. Ready for quickstart guide.
