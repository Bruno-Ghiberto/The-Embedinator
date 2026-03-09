# Spec 08: API Reference -- Implementation Plan Context

## Component Overview

The API layer is the HTTP interface for The Embedinator. It is a FastAPI application that exposes collection management, document ingestion, chat with SSE streaming, provider configuration, settings, and observability endpoints. The frontend communicates exclusively through this API. The API delegates to the storage layer (spec-07), ingestion pipeline (spec-06), and agent graphs (specs-02/03/04) for actual business logic.

This spec covers the endpoint definitions, request/response schemas, SSE streaming protocol, middleware (CORS, rate limiting, trace ID injection), and the FastAPI app factory.

## Technical Approach

### Router Organization

Each endpoint group gets its own FastAPI router file:
- `collections.py` -- Collection CRUD (3 endpoints)
- `chat.py` -- Chat with SSE streaming (1 endpoint, but complex)
- `models.py` -- Ollama model listing proxy (2 endpoints)
- `settings.py` -- Settings CRUD (2 endpoints)
- `providers.py` -- Provider management (4 endpoints)
- `traces.py` -- Query traces, health check, system stats (4 endpoints)

### SSE Streaming (Chat)

The chat endpoint is the most complex. It:
1. Accepts a `ChatRequest` body
2. Creates or resumes a session
3. Invokes the ConversationGraph (which internally runs ResearchGraph and possibly MetaReasoningGraph)
4. Streams events back to the client as SSE using `EventSourceResponse` from `sse-starlette` or a raw `StreamingResponse` with proper content-type
5. Events include status updates (which node is running), token-by-token answer generation, citation references, confidence scores, groundedness results, and a final done event with latency and trace ID

### Middleware Stack

- **CORS**: FastAPI `CORSMiddleware` with configurable origins
- **Rate Limiting**: Per-endpoint-category limits using an in-memory token bucket (or a simple counter with time window)
- **Trace ID Injection**: Generate a UUID4 trace ID for each request, inject into response headers and pass to downstream services

### App Factory

`backend/main.py` creates the FastAPI app instance, registers all routers under the `/api` prefix, configures middleware, and manages the lifespan (startup: initialize SQLite, connect to Qdrant, verify Ollama; shutdown: close connections).

## File Structure

```
backend/
  api/
    collections.py       # Collection CRUD endpoints
    chat.py              # Chat endpoint + SSE streaming
    models.py            # Ollama model listing proxy
    settings.py          # Settings CRUD
    providers.py         # Provider management endpoints
    traces.py            # Query trace log + health + stats
  main.py                # FastAPI app factory, router registration, lifespan
  middleware.py          # CORS, rate limiting, trace ID injection
  config.py              # Rate limiting and CORS configuration fields
```

## Implementation Steps

1. **Create Pydantic schemas**: Define all request/response models in the appropriate router files or a shared schemas module. Include field validators (name pattern, min/max length, Literal types).

2. **Create `backend/api/collections.py`**: Implement GET /collections, POST /collections (with name validation, 409 on duplicate), DELETE /collections/{id} (with Qdrant collection deletion). Wire to SQLiteDB and QdrantStorage.

3. **Create `backend/api/chat.py`**: Implement POST /chat. Parse ChatRequest. Create/resume session. Invoke ConversationGraph. Implement SSE streaming with all event types (session, status, token, citation, meta_reasoning, confidence, groundedness, done, error). Handle 503 when Ollama is unavailable (circuit breaker open).

4. **Create `backend/api/models.py`**: Implement GET /models/llm and GET /models/embed. Proxy to Ollama /api/tags endpoint. Filter by model type. Handle 503 when Ollama is unreachable.

5. **Create `backend/api/providers.py`**: Implement GET /providers, PUT /providers/{name}/key (encrypt with KeyManager), DELETE /providers/{name}/key, GET /providers/{name}/models. Never return raw API keys.

6. **Create `backend/api/settings.py`**: Implement GET /settings (read from SQLite settings table + config defaults), PUT /settings (partial update, validate values).

7. **Create `backend/api/traces.py`**: Implement GET /traces (paginated query_traces), GET /traces/{id} (detail with sub_questions and chunks_retrieved), GET /health (probe Qdrant, Ollama, SQLite with timing), GET /stats (aggregate from query_traces).

8. **Create `backend/middleware.py`**: Implement CORS middleware configuration. Implement rate limiting middleware with per-category limits. Implement trace ID injection middleware.

9. **Create `backend/main.py`**: FastAPI app factory with lifespan. Register all routers. Apply middleware. Initialize storage on startup (SQLiteDB connect, QdrantStorage connect). Shutdown cleanup (close connections).

10. **Add ingest endpoint to collections router** (or a separate documents router): POST /collections/{id}/ingest (multipart file upload), GET /collections/{id}/ingest/{job_id} (job status), GET /collections/{id}/documents (list), DELETE /collections/{id}/documents/{doc_id}.

11. **Write tests**: Unit tests for schema validation. Integration tests for each endpoint. SSE streaming test.

## Integration Points

- **Storage** (spec-07): All CRUD operations go through `SQLiteDB` and `QdrantStorage`.
- **Ingestion** (spec-06): POST /ingest calls `ingest_document()` from `pipeline.py`.
- **Agent Graphs** (specs 02-04): POST /chat invokes `ConversationGraph` which orchestrates `ResearchGraph` and `MetaReasoningGraph`.
- **Accuracy** (spec-05): GAV and confidence results are emitted as SSE events by the chat endpoint.
- **Providers** (spec-10): Provider management endpoints use `KeyManager` and `ProviderRegistry`.
- **Frontend** (spec-09): The Next.js frontend consumes all these endpoints.

## Key Code Patterns

### FastAPI App Factory

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    db = SQLiteDB(settings.sqlite_path)
    await db.connect()
    qdrant = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
    app.state.db = db
    app.state.qdrant = qdrant
    yield
    # Shutdown
    await db.close()

def create_app() -> FastAPI:
    app = FastAPI(title="The Embedinator", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(collections_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(providers_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(traces_router, prefix="/api")

    return app
```

### SSE Streaming Pattern

```python
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
import json

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        # Emit session event
        yield f"data: {json.dumps({'type': 'session', 'session_id': session_id})}\n\n"

        # Run graph and stream events
        async for event in run_conversation_graph(request):
            yield f"data: {json.dumps(event)}\n\n"

        # Emit done event
        yield f"data: {json.dumps({'type': 'done', 'latency_ms': latency, 'trace_id': trace_id})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### Rate Limiting Pattern

```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self):
        self.requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, limit: int, window_secs: int = 60) -> bool:
        now = time.monotonic()
        self.requests[key] = [t for t in self.requests[key] if now - t < window_secs]
        if len(self.requests[key]) >= limit:
            return False
        self.requests[key].append(now)
        return True
```

### File Upload Validation

```python
ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".py", ".js", ".ts", ".rs", ".go", ".java"}
MAX_UPLOAD_SIZE = 100 * 1024 * 1024  # 100MB

async def validate_upload(file: UploadFile) -> None:
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
    # Size check done via request content-length or reading file
```

## Phase Assignment

- **Phase 1 (MVP)**: All collection and document endpoints. Chat endpoint with SSE streaming. Ollama model listing. Provider endpoints (Ollama + OpenRouter). Settings endpoints. Health check. Rate limiting. CORS.
- **Phase 2 (Performance and Resilience)**: Query traces endpoints (GET /traces, GET /traces/{id}). GET /stats with aggregated metrics. query_traces fully populated on every chat request.
- **Phase 3 (Ecosystem and Polish)**: Additional provider model listing. Per-document chunk profile configuration. Enhanced /documents/{id} page data.
