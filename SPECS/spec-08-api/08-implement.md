# Spec 08: API Reference -- Implementation Context

## Implementation Scope

### Files to Create
- `backend/api/collections.py` -- Collection CRUD + Document management endpoints
- `backend/api/chat.py` -- Chat endpoint with SSE streaming
- `backend/api/models.py` -- Model listing proxy endpoints
- `backend/api/providers.py` -- Provider management endpoints
- `backend/api/settings.py` -- Settings CRUD endpoints
- `backend/api/traces.py` -- Query traces, health, stats endpoints
- `backend/main.py` -- FastAPI app factory, router registration, lifespan
- `backend/middleware.py` -- CORS, rate limiting, trace ID injection

### Files to Modify
- `backend/config.py` -- Add rate limiting and CORS configuration fields

## Code Specifications

### Collections Router (backend/api/collections.py)

```python
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field
from typing import Literal
import uuid
import shutil

router = APIRouter(tags=["collections"])

# --- Schemas ---

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

class DocumentSchema(BaseModel):
    id: str
    collection_id: str
    filename: str
    file_hash: str
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int
    ingested_at: Optional[str]

class IngestionResponse(BaseModel):
    job_id: Optional[str]
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

# --- Endpoints ---

ALLOWED_EXTENSIONS = {".pdf", ".md", ".txt", ".py", ".js", ".ts", ".rs", ".go", ".java"}

@router.get("/collections", response_model=List[CollectionSchema])
async def list_collections(db=Depends(get_db)):
    collections = await db.list_collections()
    result = []
    for c in collections:
        doc_count = len(await db.list_documents(c["id"]))
        total_chunks = sum(d["chunk_count"] for d in await db.list_documents(c["id"]))
        result.append(CollectionSchema(
            **c, document_count=doc_count, total_chunks=total_chunks
        ))
    return result

@router.post("/collections", response_model=CollectionSchema, status_code=201)
async def create_collection(req: CreateCollectionRequest, db=Depends(get_db), qdrant=Depends(get_qdrant)):
    # Check for duplicate name
    existing = await db.list_collections()
    if any(c["name"] == req.name for c in existing):
        raise HTTPException(409, f"Collection '{req.name}' already exists")

    # Determine dense vector dimension based on model
    dense_dim = get_embedding_dim(req.embedding_model)  # e.g., 768 for nomic-embed-text

    # Create in Qdrant
    await qdrant.create_collection(req.name, dense_dim)

    # Create in SQLite
    result = await db.create_collection(
        name=req.name,
        description=req.description,
        embedding_model=req.embedding_model,
        chunk_profile=req.chunk_profile,
        qdrant_collection_name=req.name,
    )

    return CollectionSchema(
        id=result["id"], name=req.name, description=req.description,
        embedding_model=req.embedding_model, chunk_profile=req.chunk_profile,
        qdrant_collection_name=req.name, document_count=0, total_chunks=0,
        created_at=result["created_at"],
    )

@router.delete("/collections/{collection_id}")
async def delete_collection(collection_id: str, db=Depends(get_db), qdrant=Depends(get_qdrant)):
    coll = await db.get_collection(collection_id)
    if not coll:
        raise HTTPException(404, "Collection not found")
    await qdrant.delete_collection(coll["qdrant_collection_name"])
    await db.delete_collection(collection_id)
    return {"status": "deleted"}

@router.get("/collections/{collection_id}/documents", response_model=List[DocumentSchema])
async def list_documents(collection_id: str, db=Depends(get_db)):
    coll = await db.get_collection(collection_id)
    if not coll:
        raise HTTPException(404, "Collection not found")
    return await db.list_documents(collection_id)

@router.post("/collections/{collection_id}/ingest", response_model=IngestionResponse, status_code=202)
async def ingest_document(
    collection_id: str,
    file: UploadFile = File(...),
    db=Depends(get_db),
    qdrant=Depends(get_qdrant),
):
    coll = await db.get_collection(collection_id)
    if not coll:
        raise HTTPException(404, "Collection not found")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # Save to upload directory
    upload_path = Path(settings.upload_dir) / str(uuid.uuid4()) / file.filename
    upload_path.parent.mkdir(parents=True, exist_ok=True)
    with open(upload_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Check file size
    file_size = upload_path.stat().st_size
    if file_size > settings.max_upload_size_mb * 1024 * 1024:
        upload_path.unlink()
        raise HTTPException(413, f"File exceeds maximum size of {settings.max_upload_size_mb}MB")

    # Run ingestion pipeline (async background task or inline)
    from backend.ingestion.pipeline import ingest_document as run_ingestion
    result = await run_ingestion(
        db=db, qdrant=qdrant,
        collection_id=collection_id,
        collection_name=coll["qdrant_collection_name"],
        file_path=str(upload_path),
        filename=file.filename,
        embedding_model=coll["embedding_model"],
        dense_dim=get_embedding_dim(coll["embedding_model"]),
    )
    return IngestionResponse(**result)

@router.get("/collections/{collection_id}/ingest/{job_id}", response_model=IngestionJobSchema)
async def get_ingestion_job(collection_id: str, job_id: str, db=Depends(get_db)):
    job = await db.get_ingestion_job(job_id)
    if not job:
        raise HTTPException(404, "Ingestion job not found")
    return IngestionJobSchema(**job)

@router.delete("/collections/{collection_id}/documents/{doc_id}")
async def delete_document(collection_id: str, doc_id: str, db=Depends(get_db)):
    # Delete Qdrant points for this document, then delete SQLite records
    ...
    return {"status": "deleted"}
```

### Chat Router (backend/api/chat.py)

```python
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import json
import time
import uuid

router = APIRouter(tags=["chat"])

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)
    collection_ids: List[str] = Field(..., min_length=1)
    llm_model: str = "llama3.2"
    embed_model: str = "nomic-embed-text"
    session_id: Optional[str] = None

@router.post("/chat")
async def chat(request: ChatRequest, db=Depends(get_db), qdrant=Depends(get_qdrant)):
    session_id = request.session_id or str(uuid.uuid4())
    start_time = time.monotonic()

    async def event_generator():
        # 1. Session event
        yield sse_event({"type": "session", "session_id": session_id})

        try:
            # 2. Run ConversationGraph and stream events
            async for event in run_conversation(request, session_id, db, qdrant):
                yield sse_event(event)

            # 3. Done event
            latency_ms = int((time.monotonic() - start_time) * 1000)
            trace_id = str(uuid.uuid4())
            yield sse_event({
                "type": "done",
                "latency_ms": latency_ms,
                "trace_id": trace_id,
            })

        except OllamaUnavailableError:
            yield sse_event({
                "type": "error",
                "message": "Inference service unavailable. Check Ollama status.",
                "code": "OLLAMA_UNAVAILABLE",
            })
        except Exception as e:
            yield sse_event({
                "type": "error",
                "message": str(e),
                "code": "INTERNAL_ERROR",
            })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

def sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
```

### Observability Router (backend/api/traces.py)

```python
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List, Literal
import time

router = APIRouter(tags=["observability"])

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
    chunks_retrieved: List[dict]
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
    meta_reasoning_rate: float

@router.get("/traces", response_model=List[QueryTraceSchema])
async def list_traces(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    session_id: Optional[str] = None,
    db=Depends(get_db),
):
    return await db.list_query_traces(page=page, limit=limit, session_id=session_id)

@router.get("/traces/{trace_id}", response_model=QueryTraceDetailSchema)
async def get_trace(trace_id: str, db=Depends(get_db)):
    trace = await db.get_query_trace(trace_id)
    if not trace:
        raise HTTPException(404, "Trace not found")
    return trace

@router.get("/health", response_model=HealthResponse)
async def health_check(db=Depends(get_db), qdrant=Depends(get_qdrant)):
    from datetime import datetime, timezone

    # Probe Qdrant
    qdrant_start = time.monotonic()
    qdrant_status = await qdrant.health_check()
    qdrant_latency = int((time.monotonic() - qdrant_start) * 1000)

    # Probe Ollama
    ollama_start = time.monotonic()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags", timeout=5)
            ollama_status = "ok" if resp.status_code == 200 else "error"
    except Exception:
        ollama_status = "error"
    ollama_latency = int((time.monotonic() - ollama_start) * 1000)

    # Probe SQLite
    try:
        await db.get_setting("__health_check__")
        sqlite_status = "ok"
    except Exception:
        sqlite_status = "error"

    return HealthResponse(
        qdrant=qdrant_status["status"],
        ollama=ollama_status,
        sqlite=sqlite_status,
        qdrant_latency_ms=qdrant_latency if qdrant_status["status"] == "ok" else None,
        ollama_latency_ms=ollama_latency if ollama_status == "ok" else None,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@router.get("/stats", response_model=SystemStatsSchema)
async def system_stats(db=Depends(get_db)):
    collections = await db.list_collections()
    documents = []
    for c in collections:
        documents.extend(await db.list_documents(c["id"]))
    traces = await db.list_query_traces(page=1, limit=10000)

    total_chunks = sum(d["chunk_count"] for d in documents if d.get("chunk_count"))
    total_queries = len(traces)
    avg_latency = sum(t.get("latency_ms", 0) for t in traces) / max(total_queries, 1)
    avg_confidence = sum(t.get("confidence_score", 0) or 0 for t in traces) / max(total_queries, 1)
    meta_count = sum(1 for t in traces if t.get("meta_reasoning_triggered"))
    meta_rate = meta_count / max(total_queries, 1)

    return SystemStatsSchema(
        total_collections=len(collections),
        total_documents=len(documents),
        total_chunks=total_chunks,
        total_queries=total_queries,
        avg_latency_ms=round(avg_latency, 1),
        avg_confidence=round(avg_confidence, 3),
        meta_reasoning_rate=round(meta_rate, 3),
    )
```

### Providers Router (backend/api/providers.py)

```python
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter(tags=["providers"])

class ProviderSchema(BaseModel):
    name: str
    is_active: bool
    has_key: bool
    base_url: Optional[str]
    model_count: int

class ModelInfo(BaseModel):
    name: str
    provider: str
    size: Optional[str]
    quantization: Optional[str]
    context_length: Optional[int]
    dims: Optional[int]

@router.get("/providers", response_model=List[ProviderSchema])
async def list_providers(db=Depends(get_db)):
    providers = await db.get_providers()
    return [
        ProviderSchema(
            name=p["name"],
            is_active=bool(p["is_active"]),
            has_key=p["api_key_encrypted"] is not None,
            base_url=p.get("base_url"),
            model_count=0,  # populated lazily
        )
        for p in providers
    ]

@router.put("/providers/{name}/key")
async def save_provider_key(name: str, body: dict, db=Depends(get_db), key_mgr=Depends(get_key_manager)):
    api_key = body.get("api_key")
    if not api_key:
        raise HTTPException(400, "api_key is required")
    encrypted = key_mgr.encrypt(api_key)
    await db.upsert_provider_key(name, encrypted)
    return {"status": "saved"}

@router.delete("/providers/{name}/key")
async def delete_provider_key(name: str, db=Depends(get_db)):
    deleted = await db.delete_provider_key(name)
    if not deleted:
        raise HTTPException(404, "Provider not found")
    return {"status": "deleted"}

@router.get("/providers/{name}/models", response_model=List[ModelInfo])
async def list_provider_models(name: str):
    # Proxy to provider's model listing API
    ...
```

### Settings Router (backend/api/settings.py)

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

router = APIRouter(tags=["settings"])

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

@router.get("/settings", response_model=SettingsSchema)
async def get_settings_endpoint(db=Depends(get_db)):
    # Read from SQLite settings table, fall back to config defaults
    ...

@router.put("/settings", response_model=SettingsSchema)
async def update_settings(updates: dict, db=Depends(get_db)):
    # Partial update of settings
    ...
```

### App Factory (backend/main.py)

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import QdrantStorage

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SQLiteDB(settings.sqlite_path)
    await db.connect()
    qdrant = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
    app.state.db = db
    app.state.qdrant = qdrant
    yield
    await db.close()

def create_app() -> FastAPI:
    app = FastAPI(title="The Embedinator", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    from backend.api.collections import router as collections_router
    from backend.api.chat import router as chat_router
    from backend.api.models import router as models_router
    from backend.api.providers import router as providers_router
    from backend.api.settings import router as settings_router
    from backend.api.traces import router as traces_router

    app.include_router(collections_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    app.include_router(models_router, prefix="/api")
    app.include_router(providers_router, prefix="/api")
    app.include_router(settings_router, prefix="/api")
    app.include_router(traces_router, prefix="/api")

    return app

app = create_app()
```

### Middleware (backend/middleware.py)

```python
import time
import uuid
from collections import defaultdict
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

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

rate_limiter = RateLimiter()

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        client_ip = request.client.host

        if "/chat" in path:
            limit = request.app.state.settings.rate_limit_chat_per_minute
        elif "/ingest" in path:
            limit = request.app.state.settings.rate_limit_ingest_per_minute
        else:
            limit = request.app.state.settings.rate_limit_default_per_minute

        key = f"{client_ip}:{path.split('/')[2] if len(path.split('/')) > 2 else 'default'}"
        if not rate_limiter.check(key, limit):
            raise HTTPException(429, "Rate limit exceeded")

        return await call_next(request)

class TraceIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response
```

## Configuration

Add to `backend/config.py` `Settings` class:

```python
# Rate Limiting
rate_limit_chat_per_minute: int = 30
rate_limit_ingest_per_minute: int = 10
rate_limit_default_per_minute: int = 120

# CORS
cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
```

## Error Handling

- **400 Bad Request**: Invalid request body, unsupported file type, invalid collection name format. Return `{"detail": "specific message"}`.
- **404 Not Found**: Collection, document, job, or trace not found. Return `{"detail": "Resource not found"}`.
- **409 Conflict**: Duplicate collection name. Return `{"detail": "Collection 'name' already exists"}`.
- **413 Payload Too Large**: File exceeds max upload size. Return `{"detail": "File exceeds maximum size of 100MB"}`.
- **429 Too Many Requests**: Rate limit exceeded. Return `{"detail": "Rate limit exceeded"}`.
- **503 Service Unavailable**: Ollama or Qdrant unreachable (circuit breaker open). Return `{"detail": "Service unavailable"}` or emit SSE error event.
- **500 Internal Server Error**: Unexpected exceptions. Log the full traceback, return generic error to client.

## Testing Requirements

### Unit Tests
- `test_create_collection_validation`: Verify name pattern regex rejects invalid names.
- `test_chat_request_validation`: Verify min/max length on message, min_length on collection_ids.
- `test_file_type_validation`: Verify allowed/disallowed extensions.
- `test_rate_limiter`: Verify requests are blocked after limit exceeded, allowed after window resets.
- `test_sse_event_format`: Verify SSE event string format.

### Integration Tests
- `test_collections_crud`: Create, list, delete collections via HTTP.
- `test_document_upload`: Upload a file, verify 202 response with job_id.
- `test_duplicate_upload`: Upload same file twice, verify second returns status=duplicate.
- `test_chat_streaming`: Send chat request, read SSE stream, verify event sequence (session -> status -> token -> done).
- `test_health_endpoint`: Verify health check probes all three services.
- `test_providers_crud`: Save key, list providers (verify has_key=true, key not exposed), delete key.
- `test_cors_headers`: Verify CORS headers on responses.
- `test_rate_limiting`: Send requests exceeding limit, verify 429 response.

## Done Criteria

- [ ] All 20 endpoints are implemented and reachable
- [ ] POST /collections validates name with regex `^[a-z0-9][a-z0-9_-]*$`
- [ ] POST /collections/{id}/ingest validates file type and size, returns 202
- [ ] POST /chat streams SSE events with types: session, status, token, citation, confidence, groundedness, done, error
- [ ] GET /health probes Qdrant, Ollama, SQLite with latency measurements
- [ ] GET /stats returns aggregated system metrics
- [ ] Rate limiting enforced per category (chat: 30/min, ingest: 10/min, default: 120/min)
- [ ] CORS configured for localhost:3000
- [ ] Provider API keys encrypted on save, never returned in GET responses
- [ ] All error responses use standard `{"detail": "..."}` format with correct HTTP status codes
- [ ] Trace ID injected into response headers for every request
- [ ] App startup initializes SQLite and Qdrant connections via lifespan
