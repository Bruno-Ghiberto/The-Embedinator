# NDJSON Streaming Contract: Chat Endpoint

**Date**: 2026-03-10 | **Branch**: `001-vision-arch` | **ADR**: ADR-007

This document specifies the NDJSON streaming protocol for the `POST /api/chat` endpoint.

---

## Transport

| Property | Value |
|---|---|
| Endpoint | `POST /api/chat` |
| Content-Type (request) | `application/json` |
| Content-Type (response) | `application/x-ndjson` |
| Transfer-Encoding | `chunked` |
| HTTP version | HTTP/1.1 |

---

## Request Schema

```json
{
  "query": "string (1–2000 chars, required)",
  "collection_ids": ["string (UUID, at least 1)", "..."],
  "model_name": "string (optional, defaults to active provider's default model)"
}
```

**Example**:
```json
{
  "query": "What are the key security requirements?",
  "collection_ids": ["col-abc123"],
  "model_name": "qwen2.5:7b"
}
```

---

## Response Stream Format

Each line in the response body is a complete JSON object terminated by `\n`. The client reads lines as they arrive.

### Frame Types

#### 1. `chunk` — Token frame (one or more per stream)

Emitted for each token or token group as the LLM generates the answer.

```json
{"type": "chunk", "text": "string"}
```

| Field | Type | Description |
|---|---|---|
| `type` | `"chunk"` | Literal discriminator |
| `text` | string | One or more tokens of the generated answer |

**Example sequence**:
```
{"type": "chunk", "text": "The"}
{"type": "chunk", "text": " key"}
{"type": "chunk", "text": " security"}
{"type": "chunk", "text": " requirements"}
{"type": "chunk", "text": " are:\n\n1."}
```

#### 2. `metadata` — Final frame (exactly one, always last)

Emitted after the final token. Contains the full answer metadata.

```json
{
  "type": "metadata",
  "trace_id": "string (UUID)",
  "confidence": "integer (0–100)",
  "citations": [
    {
      "passage_id": "string",
      "document_id": "string (UUID)",
      "document_name": "string",
      "text": "string (excerpt)",
      "relevance_score": "float (0.0–1.0)",
      "source_removed": "boolean"
    }
  ],
  "latency_ms": "integer"
}
```

| Field | Type | Description |
|---|---|---|
| `type` | `"metadata"` | Literal discriminator |
| `trace_id` | UUID string | ID of the query trace record in SQLite |
| `confidence` | int 0–100 | Evidence-based confidence score |
| `citations` | array | Source passages used; empty if no relevant content |
| `citations[].passage_id` | string | Unique passage identifier |
| `citations[].document_id` | UUID string | Document that contains this passage |
| `citations[].document_name` | string | Original filename (e.g., `report.pdf`) |
| `citations[].text` | string | Passage excerpt (≤ 300 chars) |
| `citations[].relevance_score` | float | Cross-encoder score 0.0–1.0 |
| `citations[].source_removed` | boolean | True if the source document was later deleted |
| `latency_ms` | int | Total query processing time in milliseconds |

**Example**:
```json
{"type": "metadata", "trace_id": "7f3a1c2d-...", "confidence": 87, "citations": [{"passage_id": "p-001", "document_id": "doc-abc", "document_name": "security-spec.pdf", "text": "All API keys must be encrypted at rest using Fernet...", "relevance_score": 0.94, "source_removed": false}], "latency_ms": 2340}
```

#### 3. `error` — Error frame (at most one, terminates stream)

Emitted if an unrecoverable error occurs during streaming. Stream ends after this frame.

```json
{"type": "error", "message": "string", "code": "string"}
```

| Field | Type | Description |
|---|---|---|
| `type` | `"error"` | Literal discriminator |
| `message` | string | Human-readable error description |
| `code` | string | Machine-readable error code (see below) |

**Error codes**:

| Code | Description |
|---|---|
| `provider_unavailable` | LLM provider (Ollama, cloud) unreachable |
| `collection_not_found` | One or more `collection_ids` do not exist |
| `no_documents_indexed` | Collection exists but has no indexed documents |
| `retrieval_failed` | Qdrant unreachable or search failed |
| `context_too_long` | Query + context exceeds LLM context window |
| `rate_limited` | Request rate limit exceeded (30 chat/min) |
| `internal_error` | Unexpected server error |

---

## Stream Lifecycle

```
Client                               Server
  |                                    |
  |-- POST /api/chat ----------------> |
  |                                    | [classify intent]
  |                                    | [embed query]
  |                                    | [hybrid search]
  |                                    | [rerank]
  |                                    | [fetch parent chunks]
  |                                    | [begin LLM generation]
  |<-- {"type":"chunk","text":"The"} --|
  |<-- {"type":"chunk","text":" main"}--|
  |         ... (N chunk frames) ...   |
  |<-- {"type":"metadata",...} --------|  (final frame)
  |                                    |
  |  (stream ends / connection closes) |
```

**Guaranteed ordering**:
1. Zero or more `chunk` frames
2. Exactly one `metadata` frame OR exactly one `error` frame
3. Stream closes

---

## Client Consumption Pattern

### TypeScript (React hook)

```typescript
async function streamChat(
  query: string,
  collectionIds: string[],
  onToken: (text: string) => void,
  onComplete: (metadata: ChatMetadata) => void,
  onError: (err: ChatError) => void
): Promise<void> {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, collection_ids: collectionIds }),
  });

  if (!response.ok) {
    onError({ code: "http_error", message: `HTTP ${response.status}` });
    return;
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? ""; // Keep incomplete line in buffer

    for (const line of lines) {
      if (!line.trim()) continue;
      const frame = JSON.parse(line);

      if (frame.type === "chunk") {
        onToken(frame.text);
      } else if (frame.type === "metadata") {
        onComplete(frame);
      } else if (frame.type === "error") {
        onError(frame);
        return;
      }
    }
  }
}
```

### Python (test client)

```python
import httpx
import json

async def stream_chat(query: str, collection_ids: list[str]):
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", "http://localhost:8000/api/chat",
            json={"query": query, "collection_ids": collection_ids},
            timeout=60.0,
        ) as response:
            async for line in response.aiter_lines():
                if not line:
                    continue
                frame = json.loads(line)
                if frame["type"] == "chunk":
                    print(frame["text"], end="", flush=True)
                elif frame["type"] == "metadata":
                    print(f"\n\nConfidence: {frame['confidence']}%")
                    return frame
                elif frame["type"] == "error":
                    raise RuntimeError(frame["message"])
```

---

## Error Handling Rules

1. If an error occurs **before** the first `chunk` frame, emit an `error` frame and return a non-200 HTTP status where possible.
2. If an error occurs **during** streaming (after at least one `chunk`), emit an `error` frame as the final frame. HTTP status is already 200.
3. The client **must** handle `error` frames even when HTTP status is 200.
4. Network interruption (no `metadata` or `error` frame before connection close) should be treated as `internal_error` by the client.

---

## Rate Limiting

- **Limit**: 30 chat requests per minute per IP
- **On limit exceeded**: HTTP 429 before stream starts (no NDJSON body)
- **Header**: `Retry-After: <seconds>` included in 429 response
