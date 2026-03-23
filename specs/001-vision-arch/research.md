# Phase 0 Research: Vision & System Architecture

**Date**: 2026-03-10 | **Branch**: `001-vision-arch`

This document consolidates research findings on 8 key technical unknowns identified in the planning phase. Each unknown has been researched and a decision recorded with rationale.

## 1. FastAPI + SSE Streaming Best Practices

**Unknown**: How to implement streaming responses in FastAPI with proper backpressure, error recovery, and browser consumption?

**Decision**: Use `StreamingResponse` with async generator that yields JSON-lines (newline-delimited JSON) for each response chunk.

**Rationale**:
- FastAPI's `StreamingResponse` is the standard pattern for SSE-style streaming
- Async generators provide natural backpressure (consumer pulls at own pace)
- JSON-lines format (one JSON object per line) is robust to partial/delayed delivery
- Frontend can parse with `response.body.getReader()` or EventSource API for true SSE

**Alternatives considered**:
- WebSocket: Overkill for one-way (server→client) answer streaming; SSE simpler
- Polling (`GET /api/chat/{job_id}/progress`): Higher latency and network overhead
- Server-sent Events (native EventSource): Limited to text/event-stream MIME type; JSON-lines more flexible

**Implementation pattern**:
```python
# Backend: FastAPI streaming endpoint
@app.post("/api/chat", response_class=StreamingResponse)
async def chat_stream(request: ChatRequest):
    async def generate():
        try:
            async for chunk in generate_answer_async(request.query):
                yield json.dumps({"type": "chunk", "text": chunk}).encode() + b"\n"
        except Exception as e:
            yield json.dumps({"type": "error", "message": str(e)}).encode() + b"\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")

# Frontend: React hook to consume stream
const [response, setResponse] = useState("");
const res = await fetch("/api/chat", { method: "POST", body: JSON.stringify(query) });
const reader = res.body.getReader();
while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const line = new TextDecoder().decode(value);
    const { type, text, message } = JSON.parse(line);
    if (type === "chunk") setResponse(prev => prev + text);
}
```

**References**: FastAPI docs (StreamingResponse), NDJSON spec, Anthropic API streaming patterns

---

## 2. Qdrant Vector Search Integration

**Unknown**: How to initialize Qdrant client, create collections, perform hybrid search (dense + BM25), and implement circuit breaker reliability?

**Decision**: Use `qdrant_client.QdrantClient` with async HTTP connection; implement circuit breaker with exponential backoff in wrapper class.

**Rationale**:
- `qdrant_client` is the official Python SDK with async support
- Qdrant HTTP API is more reliable than gRPC for local deployments
- Circuit breaker prevents cascading failures when Qdrant is temporarily unavailable
- Exponential backoff (100ms → 200ms → 400ms → max 10s) balances retry latency with resilience

**Alternatives considered**:
- gRPC client: Faster but less reliable in local development; harder to debug
- Direct HTTP calls: Possible but error-prone; better to use SDK
- No retry logic: Unacceptable for distributed system; single Qdrant restart breaks user experience

**Implementation pattern**:
```python
# Wrapper with circuit breaker
class QdrantClientWrapper:
    def __init__(self, host: str, port: int):
        self.client = QdrantClient(host=host, port=port, api_key_header=None)
        self.circuit_open = False
        self.failure_count = 0

    async def search(self, collection_name: str, query_vector: List[float], limit: int):
        if self.circuit_open:
            # Exponential backoff: retry after delay
            await asyncio.sleep(min(2 ** self.failure_count, 10))
            self.circuit_open = False

        try:
            result = await self.client.search(
                collection_name=collection_name,
                query_vector=query_vector,
                limit=limit
            )
            self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            if self.failure_count > 3:
                self.circuit_open = True
            raise QdrantConnectionError(str(e))
```

**Collection creation** (on app startup):
```python
await qdrant_client.recreate_collection(
    collection_name="embeddings",
    vectors_config=VectorParams(size=384, distance=Distance.COSINE),
    # Note: BM25 search is implemented at application level (SQLite FTS)
)
```

**References**: Qdrant docs, Circuit Breaker pattern (Martin Fowler), async Python best practices

---

## 3. Pydantic Settings for .env Configuration

**Unknown**: How to load configuration from `.env` file, support environment variable overrides, and provide sensible local defaults?

**Decision**: Use `pydantic_settings.BaseSettings` with `.env_file=".env"` and field validation.

**Rationale**:
- Pydantic `BaseSettings` is the standard pattern for Python configuration
- Automatically reads `.env` file; environment variables override `.env` values
- Type validation ensures config is correct at load time (fail fast)
- Sensible defaults (Ollama at `localhost:11434`, Qdrant at `localhost:6333`) enable local-only deployment

**Alternatives considered**:
- Plain `os.environ` + dict: No type safety, defaults scattered in code
- `python-dotenv` directly: Lower-level; less validation
- Config file (YAML/JSON): More complex for local dev; .env is simpler

**Implementation pattern**:
```python
# backend/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    sqlite_path: str = "./data/embedinator.db"

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"  # Default model

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

**Usage**:
```bash
# .env file (local-only defaults work without this)
QDRANT_HOST=qdrant
OLLAMA_BASE_URL=http://ollama:11434
SQLITE_PATH=/app/data/embedinator.db
```

**References**: Pydantic docs, 12-factor app methodology

---

## 4. SQLite WAL Mode + Async Access

**Unknown**: How to initialize SQLite with WAL mode, use async access with aiosqlite, and ensure thread-safe concurrent access?

**Decision**: Enable WAL mode on first connection; use `aiosqlite.connect()` with context manager; rely on SQLite's built-in locking for concurrent queries.

**Rationale**:
- WAL (Write-Ahead Logging) mode allows concurrent reads while writes are in progress
- `aiosqlite` provides async interface without thread pool (pure asyncio)
- SQLite's default locking (lock-free reads in WAL mode) is sufficient for small deployments (10s of concurrent users)
- Context manager ensures connections are properly closed

**Alternatives considered**:
- PostgreSQL: Overkill for single-user local deployment; adds Docker dependency
- Direct threading: Less efficient than WAL mode; harder to reason about
- No WAL mode: Serializes all writes; insufficient for multi-tab concurrent queries

**Implementation pattern**:
```python
# backend/storage/sqlite_db.py
import aiosqlite

class SQLiteDB:
    @staticmethod
    async def create(db_path: str) -> 'SQLiteDB':
        db = SQLiteDB(db_path)
        async with aiosqlite.connect(db_path) as conn:
            # Enable WAL mode
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA synchronous=NORMAL")  # Balance safety + speed
            # Create tables
            await db._create_tables(conn)
            await conn.commit()
        return db

    async def _create_tables(self, conn):
        schemas = [
            # Collections table
            """CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            # Documents table (supports many-to-many via JSON)
            """CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                collection_ids JSON NOT NULL,  -- ["col1", "col2"]
                file_path TEXT NOT NULL,
                status TEXT DEFAULT 'uploaded',  -- uploaded, indexing, indexed, failed, deleted
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            # Query traces table
            """CREATE TABLE IF NOT EXISTS query_traces (
                id TEXT PRIMARY KEY,
                query_text TEXT NOT NULL,
                collections_searched JSON NOT NULL,  -- ["col1"]
                passages_retrieved JSON NOT NULL,    -- [{id, text, score, source_doc_id}]
                confidence_score INT NOT NULL,        -- 0-100
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )""",
            # Providers table
            """CREATE TABLE IF NOT EXISTS providers (
                name TEXT PRIMARY KEY,
                type TEXT NOT NULL,  -- 'ollama', 'openrouter', 'openai', 'anthropic'
                config_json TEXT NOT NULL,  -- encrypted API key, model name, etc.
                is_active BOOLEAN DEFAULT 0
            )""",
        ]
        for schema in schemas:
            await conn.execute(schema)

    async def query(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as conn:
            async with conn.execute(sql, params) as cursor:
                return await cursor.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(sql, params)
            await conn.commit()
```

**Concurrent read example**:
```python
# Multiple browser tabs can read concurrently in WAL mode
results = await db.query("SELECT * FROM query_traces WHERE id = ?", (trace_id,))
```

**References**: SQLite WAL docs, aiosqlite docs, async Python best practices

---

## 5. Next.js 16 Dynamic Routes & Server Components

**Unknown**: How to structure Next.js 16 app with dynamic routes (`chat/[id]`), consume SSE streams from frontend, and handle streaming responses?

**Decision**: Use Next.js 16 Pages Router (not App Router) with dynamic routes; use `fetch()` with `response.body.getReader()` for stream consumption.

**Rationale**:
- Pages Router is more stable and easier to reason about than App Router (experimental in v16)
- Dynamic route syntax `[id]` is standard for resource-specific pages
- `getReader()` + `TextDecoder` is browser-native (no extra libraries)
- Server-side rendering can fetch initial data; streaming updates in browser

**Alternatives considered**:
- App Router: More modern but less stable; additional complexity not needed for MVP
- axios: Adds dependency; native fetch is sufficient
- Socket.io: Overkill for one-way streaming

**Implementation pattern**:
```typescript
// frontend/src/pages/chat/[id].tsx
import { useRouter } from "next/router";
import { useState, useEffect } from "react";

export default function ChatPage() {
  const router = useRouter();
  const { id: collectionId } = router.query;
  const [response, setResponse] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitQuery(query: string) {
    setLoading(true);
    setResponse("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query,
          collection_ids: [collectionId],
          model_name: "qwen2.5:7b"
        })
      });

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const line = new TextDecoder().decode(value);
        const data = JSON.parse(line);

        if (data.type === "chunk") {
          setResponse(prev => prev + data.text);  // Stream updates UI
        } else if (data.type === "metadata") {
          // Store trace_id, confidence, citations
          console.log("Trace:", data.trace_id, "Confidence:", data.confidence_score);
        }
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1>Chat: {collectionId}</h1>
      <input type="text" placeholder="Ask a question..." onSubmit={(e) => submitQuery(e.target.value)} />
      <div className="response">{response}</div>
    </div>
  );
}
```

**References**: Next.js 16 docs, Fetch API streaming, React hooks best practices

---

## 6. Docker Compose Multi-Service Orchestration

**Unknown**: How to structure Docker Compose for 4 services with dependencies, health checks, volume persistence, and environment variable loading?

**Decision**: Use `docker-compose.yml` with `depends_on`, `healthcheck`, volumes for persistence, `.env` file for configuration.

**Rationale**:
- `depends_on` with `condition: service_healthy` ensures services start in order and are ready
- Health checks prevent container readiness before service is truly listening
- Named volumes persist data across container restarts
- `.env` file centralizes configuration; env vars injected into containers

**Alternatives considered**:
- Kubernetes: Overkill for single-user local deployment
- Manual Docker commands: Error-prone; Compose is simpler
- No health checks: Containers may start before services are ready

**Implementation pattern**:
```yaml
# docker-compose.yml
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    container_name: qdrant
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/health"]
      interval: 5s
      timeout: 2s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    container_name: ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 5s
      timeout: 2s
      retries: 3

  backend:
    build: .
    container_name: embedinator-backend
    ports:
      - "8000:8000"
    environment:
      - QDRANT_HOST=qdrant
      - QDRANT_PORT=6333
      - OLLAMA_BASE_URL=http://ollama:11434
      - SQLITE_PATH=/app/data/embedinator.db
    volumes:
      - ./backend:/app/backend
      - ./data:/app/data
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:
        condition: service_healthy
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

  frontend:
    build: ./frontend
    container_name: embedinator-frontend
    ports:
      - "3000:3000"
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000
    depends_on:
      - backend
    command: npm run dev

volumes:
  qdrant_data:
  ollama_models:
```

**Dev overrides** (docker-compose.dev.yml):
```yaml
services:
  backend:
    command: uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
  frontend:
    command: npm run dev
```

**Usage**:
```bash
make dev  # Starts all services with hot reload
```

**References**: Docker Compose docs, health check best practices

---

## 7. Provider Registry Pattern

**Unknown**: How to switch between Ollama (local) and cloud providers (OpenRouter, OpenAI, Anthropic) at runtime without restarting?

**Decision**: Implement `ProviderRegistry` class that resolves provider names to instances; store active provider in SQLite; read on each query.

**Rationale**:
- Registry pattern decouples provider selection from query logic
- SQLite persistence allows user settings (via UI) to survive restarts
- Reading active provider on each query (not caching) ensures instant switches
- Encrypted API key storage in DB prevents accidental exposure

**Alternatives considered**:
- Global config variable: Can't switch without restart
- Per-request provider selection: Forces UI to choose; better to default + remember user's choice
- Hardcoded provider: Not extensible to cloud providers

**Implementation pattern**:
```python
# backend/providers/registry.py
class ProviderRegistry:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers = {
            "ollama": OllamaProvider(settings.ollama_base_url),
            "openrouter": OpenRouterProvider,  # Lazy init on demand
            "openai": OpenAIProvider,
            "anthropic": AnthropicProvider,
        }

    async def get_active_provider(self, db: SQLiteDB) -> LLMProvider:
        # Query DB for active provider
        rows = await db.query("SELECT name, config_json FROM providers WHERE is_active = 1")
        if not rows:
            # Default to Ollama
            return self.providers["ollama"]

        provider_name, config_json = rows[0]
        config = json.loads(config_json)

        if provider_name == "ollama":
            return self.providers["ollama"]
        elif provider_name == "openrouter":
            # Initialize with decrypted API key
            api_key = decrypt(config["api_key"])
            return OpenRouterProvider(api_key=api_key)
        # ... etc

    async def set_active_provider(self, db: SQLiteDB, name: str, api_key: Optional[str]):
        # Deactivate all, activate one
        await db.execute("UPDATE providers SET is_active = 0")
        config = {"api_key": encrypt(api_key)} if api_key else {}
        await db.execute(
            "INSERT OR REPLACE INTO providers (name, type, config_json, is_active) VALUES (?, ?, ?, 1)",
            (name, name, json.dumps(config))
        )

# Chat endpoint uses registry
@app.post("/api/chat")
async def chat(request: ChatRequest):
    provider = await registry.get_active_provider(db)
    async for chunk in provider.generate(request.query):
        yield json.dumps({"type": "chunk", "text": chunk}).encode() + b"\n"
```

**Encryption**: Use `cryptography.Fernet` for API key storage:
```python
from cryptography.fernet import Fernet

def encrypt(plaintext: str, key: bytes) -> str:
    cipher = Fernet(key)
    return cipher.encrypt(plaintext.encode()).decode()

def decrypt(ciphertext: str, key: bytes) -> str:
    cipher = Fernet(key)
    return cipher.decrypt(ciphertext.encode()).decode()
```

**References**: Registry pattern, Provider interface, API key security best practices

---

## 8. Trace Recording & Observability

**Unknown**: What data to capture in traces? How to structure for trace viewer UI?

**Decision**: Record query, collections searched, passages retrieved (with scores), sub-questions explored (if any), confidence score, and timestamps. Store as JSON in SQLite; expose via `/api/traces/{trace_id}` endpoint.

**Rationale**:
- Traces fulfill User Story 4 (observability): users verify answers are grounded
- Recording retrieval scores and passages enables debugging and grounding validation
- JSON format is flexible for future additions (reasoning steps, provider used, etc.)
- Trace viewer UI can display hierarchically (query → collections → passages)

**Trace data structure** (persisted in SQLite):
```json
{
  "id": "trace-12345",
  "query_text": "What is the capital of France?",
  "collections_searched": ["geography", "world-facts"],
  "retrieval_strategy": "dense_search",
  "passages_retrieved": [
    {
      "id": "passage-abc",
      "document_id": "doc-123",
      "document_name": "world_capitals.pdf",
      "text": "Paris is the capital of France...",
      "relevance_score": 0.95,
      "chunk_index": 42
    },
    {
      "id": "passage-def",
      "document_id": "doc-124",
      "document_name": "europe.md",
      "text": "France is located in Western Europe...",
      "relevance_score": 0.72,
      "chunk_index": 15
    }
  ],
  "reasoning_steps": [
    {
      "step": 1,
      "name": "Query Decomposition",
      "substeps": ["Identify entity: France", "Identify attribute: capital"]
    },
    {
      "step": 2,
      "name": "Retrieval",
      "passages_retrieved": 2,
      "avg_score": 0.835
    }
  ],
  "confidence_score": 92,  # 0-100%
  "fallback_used": false,
  "created_at": "2026-03-10T14:32:15Z"
}
```

**Trace endpoint**:
```python
@app.get("/api/traces/{trace_id}")
async def get_trace(trace_id: str, db: SQLiteDB):
    rows = await db.query("SELECT * FROM query_traces WHERE id = ?", (trace_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Trace not found")

    # Deserialize JSON columns
    trace_data = json.loads(rows[0]["passages_retrieved"])
    return {
        "id": trace_id,
        "query": rows[0]["query_text"],
        "passages": trace_data,
        "confidence": rows[0]["confidence_score"],
        "created_at": rows[0]["created_at"]
    }
```

**Frontend trace viewer** (React component):
```typescript
// frontend/src/components/TraceViewer.tsx
export function TraceViewer({ traceId }: { traceId: string }) {
  const [trace, setTrace] = useState(null);

  useEffect(() => {
    fetch(`/api/traces/${traceId}`)
      .then(r => r.json())
      .then(setTrace);
  }, [traceId]);

  if (!trace) return <div>Loading...</div>;

  return (
    <div className="trace-viewer">
      <h3>Query: {trace.query}</h3>
      <p>Confidence: {trace.confidence}%</p>
      <ul>
        {trace.passages.map(p => (
          <li key={p.id}>
            <strong>{p.document_name}</strong> (score: {p.relevance_score.toFixed(2)})
            <p>{p.text.slice(0, 100)}...</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
```

**References**: Anthropic API traces, RAG evaluation metrics, observability best practices

---

## Summary Table

| Unknown | Decision | Key Rationale |
|---------|----------|---------------|
| FastAPI SSE Streaming | JSON-lines + StreamingResponse | Robust, backpressure-aware, browser-friendly |
| Qdrant Integration | HTTP client + circuit breaker | Official SDK, exponential backoff resilience |
| Pydantic Settings | BaseSettings + .env file | Type-safe, env var overrides, sensible defaults |
| SQLite + Async | aiosqlite + WAL mode | Concurrent reads, async-native, single-user sufficient |
| Next.js 16 | Pages Router + getReader() | Stable, standard patterns, native fetch API |
| Docker Compose | Multi-service + health checks | Reliable service startup, persistence, configuration |
| Provider Registry | SQLiteDB-backed registry | Runtime switching, encrypted keys, extensible |
| Trace Recording | JSON in SQLite + viewer endpoint | Flexible, observable, grounds user trust |

All research complete. Ready for Phase 1 design artifacts.
