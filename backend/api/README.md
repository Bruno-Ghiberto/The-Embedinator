# backend/api/

FastAPI route handlers for all REST and streaming endpoints.

## Endpoints

| File             | Routes                                              |
|------------------|-----------------------------------------------------|
| `chat.py`        | `POST /api/chat` -- NDJSON streaming answers         |
| `collections.py` | CRUD for document collections                        |
| `documents.py`   | CRUD for documents within collections                |
| `ingest.py`      | `POST .../ingest` (file upload), `GET .../ingest/{job_id}` |
| `traces.py`      | Query traces, system stats, time-series metrics      |
| `providers.py`   | LLM provider key management and health checks        |
| `models.py`      | List available LLM and embedding models              |
| `settings.py`    | Read and update runtime settings                     |
| `health.py`      | `GET /api/health` -- probes SQLite, Qdrant, Ollama   |

## NDJSON Streaming (chat.py)

The chat endpoint returns a `StreamingResponse` with content type
`application/x-ndjson`. Each line is a JSON object followed by a newline.
The stream emits 10 event types in order:

1. `session` -- Session ID assignment
2. `status` -- Node transition notifications
3. `chunk` -- Streamed answer text fragments
4. `citation` -- Source citations with chunk references
5. `meta_reasoning` -- Strategies attempted (if meta-reasoning activated)
6. `confidence` -- Integer score 0-100
7. `groundedness` -- Claim verification summary
8. `done` -- Latency and trace ID
9. `clarification` -- Interrupt when clarification is needed
10. `error` -- Error with code and message

## Request/Response Models

All schemas are defined in `backend/agent/schemas.py` using Pydantic v2.
Key request models:

- `ChatRequest` -- message, session_id, collection_ids, llm_model, embed_model
- `CollectionCreateRequest` -- name, description
- `ProviderKeyRequest` -- api_key
- `SettingsUpdateRequest` -- key-value settings pairs

## Security

- Input sanitization: message truncated to 10,000 characters (FR-001)
- Collection names validated against `^[a-zA-Z0-9_-]+$` pattern
- File uploads restricted to `.pdf`, `.md`, `.txt` extensions
- Filename sanitization strips path traversal and special characters
- Per-endpoint rate limiting via `RateLimitMiddleware`

## Error Handling

All endpoints return structured error responses:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable description",
    "details": {}
  },
  "trace_id": "uuid"
}
```

HTTP status codes: 400 (validation), 404 (not found), 409 (conflict),
413 (file too large), 429 (rate limit), 503 (service unavailable).
