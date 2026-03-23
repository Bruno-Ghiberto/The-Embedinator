# Contract: POST /api/chat

**Modified by**: spec-13 FR-001
**File**: `backend/api/chat.py`

## Request

```json
{
  "message": "string",
  "collection_ids": ["string"],
  "session_id": "string | null"
}
```

| Field | Type | Constraint | Change |
|-------|------|------------|--------|
| `message` | str | Required | Truncated at 10,000 chars **before** processing. Schema unchanged. |
| `collection_ids` | list[str] | Required | Unchanged |
| `session_id` | str \| null | Optional | Unchanged |

**Schema class**: `ChatRequest` in `backend/agent/schemas.py` — **not modified**.

## Behaviour Change (FR-001)

Inside `chat()` (or `generate()`), before building `initial_state`:

```python
message = body.message[:10_000]  # silent truncation
```

Both downstream usages must reference `message`, not `body.message`:
- `HumanMessage(content=message)`
- `db.create_query_trace(..., query=message, ...)`

The client **receives no indication** that truncation occurred. The response stream begins normally.

## Response

NDJSON streaming response — unchanged. See constitution §VI for the complete frame schema.

```
{"type": "session",   "session_id": "..."}
{"type": "chunk",     "text": "..."}
{"type": "metadata",  "trace_id": "...", "confidence": 0-100, "citations": [...], "latency_ms": ...}
```

Error frame (if applicable):
```
{"type": "error", "message": "...", "code": "..."}
```

## Rate Limiting

Unchanged: 30 requests/min per IP (spec-08 `RateLimitMiddleware`). HTTP 429 on breach.

## What Does NOT Change

- `ChatRequest` schema
- NDJSON event types or fields
- Rate limiting configuration
- Session handling
- LangGraph graph invocation
