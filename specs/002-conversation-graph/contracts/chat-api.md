# Contract: Chat API Endpoint

**Date**: 2026-03-10
**Feature**: [spec.md](../spec.md)
**Protocol**: ADR-007 (NDJSON Streaming)

## Endpoint

```
POST /api/chat
Content-Type: application/json
```

## Request

```json
{
  "message": "string (required, 1-2000 chars)",
  "collection_ids": ["string (UUID)"],
  "llm_model": "string (model identifier)",
  "session_id": "string (UUID, optional — new session created if absent)"
}
```

**Validation**:
- `message`: Required, non-empty, max 2000 characters. Whitespace-only rejected.
- `collection_ids`: Required for `rag_query` intent. If empty, system prompts user to select.
- `llm_model`: Required. Resolved via `ProviderRegistry` at query time.
- `session_id`: Optional. If provided, session history is loaded from SQLite. If absent or load fails, fresh session created.

## Response

```
Content-Type: application/x-ndjson
Transfer-Encoding: chunked
```

Each line is a complete JSON object terminated by `\n`. No `data:` prefix.

### Frame Types

**Chunk frame** (streamed as LLM generates tokens):
```json
{"type": "chunk", "text": "The key finding is..."}
```

**Clarification frame** (when graph interrupts for clarification):
```json
{"type": "clarification", "question": "Which collection are you referring to?"}
```
When this frame is received, the client should display the question and submit the user's response as a new `POST /api/chat` with the same `session_id`. The graph resumes from checkpoint.

**Metadata frame** (final frame after all chunks):
```json
{
  "type": "metadata",
  "trace_id": "7f3a1c2d-...",
  "confidence": 87,
  "citations": [
    {
      "passage_id": "p-001",
      "document_id": "doc-abc",
      "document_name": "report.pdf",
      "text": "...",
      "relevance_score": 0.94,
      "source_removed": false
    }
  ],
  "latency_ms": 1240
}
```

**Error frame** (on failure):
```json
{"type": "error", "message": "No collections selected", "code": "NO_COLLECTIONS"}
```

### Error Codes

| Code | Meaning | HTTP Status |
|------|---------|-------------|
| `NO_COLLECTIONS` | No collections selected for document query | 200 (in stream) |
| `EMPTY_COLLECTIONS` | All selected collections have no indexed documents | 200 (in stream) |
| `EMPTY_MESSAGE` | Message is empty or whitespace-only | 400 |
| `MESSAGE_TOO_LONG` | Message exceeds 2000 character limit | 400 |
| `INTERNAL_ERROR` | Unexpected server error | 200 (in stream) |

## Clarification Flow

```
Client                          Server
  │                                │
  │─── POST /api/chat ───────────>│
  │    {message, session_id}       │
  │                                │── classify_intent
  │                                │── rewrite_query
  │                                │── is_clear=False
  │<── {"type":"clarification"} ──│
  │    {"question":"Which...?"}    │── interrupt + checkpoint
  │                                │
  │─── POST /api/chat ───────────>│
  │    {answer, same session_id}   │
  │                                │── Command(resume=answer)
  │                                │── rewrite_query (retry)
  │<── {"type":"chunk"} ─────────│
  │<── {"type":"metadata"} ──────│
```

Maximum 2 clarification rounds. After the 2nd, system proceeds with best-effort interpretation.

## Session Lifecycle

1. **New session**: Omit `session_id` → server creates UUID, returns in metadata `trace_id` context
2. **Resume session**: Include `session_id` → server loads history from SQLite
3. **Failed load**: If SQLite read fails → fresh session created, warning logged
4. **History compression**: When history exceeds 75% of model's context window → older messages summarized

## Rate Limits

Per Constitution Principle V:
- 30 chat requests per minute per client
- Rate limit response: HTTP 429 with `Retry-After` header
