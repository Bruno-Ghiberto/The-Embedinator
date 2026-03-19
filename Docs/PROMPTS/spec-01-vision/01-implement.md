# Spec 01: Vision & System Architecture -- Implementation Context

**Spec**: `specs/001-vision-arch/spec.md` | **Plan**: `specs/001-vision-arch/plan.md`
**Data Model**: `specs/001-vision-arch/data-model.md` | **API Contracts**: `specs/001-vision-arch/contracts/api.md`
**Tasks**: `specs/001-vision-arch/tasks.md` | **Research**: `specs/001-vision-arch/research.md`

## User Stories & Success Criteria

| Story | Priority | Goal | Key SC |
|-------|----------|------|--------|
| **US1** | P1 | Private Document Q&A — upload, query, cited answers | SC-001, SC-003, SC-005, SC-008 |
| **US2** | P2 | One-Command Start — `make dev` launches everything | SC-004 |
| **US3** | P3 | Streamed Real-Time Answers — word-by-word in browser | SC-002 |
| **US4** | P4 | Observability — trace every answer's reasoning path | SC-005, SC-006 |
| **US5** | P5 | Optional Cloud AI Provider — switch without restart | SC-007 |

| SC # | Criterion |
|------|-----------|
| SC-001 | Upload doc + get cited answer within 5 min of first start |
| SC-002 | First words of answer in browser within 1 second |
| SC-003 | No data leaves machine in default local-only mode |
| SC-004 | System starts from single command, no manual steps |
| SC-005 | Every answer statement traceable to source passage |
| SC-006 | Automatic fallback strategy on low-confidence retrieval |
| SC-007 | Switch providers without restart |
| SC-008 | Decline to answer off-topic queries ≥95% accuracy |

## Implementation Scope

### Files to Create

| File | Purpose | User Story |
|------|---------|------------|
| `backend/__init__.py` | Package marker | — |
| `backend/config.py` | Pydantic Settings with all env vars | US2 |
| `backend/errors.py` | Custom exception hierarchy | — |
| `backend/main.py` | FastAPI app factory with lifespan | US2 |
| `backend/middleware.py` | CORS, rate limiting, trace ID injection | — |
| `backend/api/__init__.py` | Package marker | — |
| `backend/api/collections.py` | Collection CRUD router | US1 |
| `backend/api/documents.py` | Document upload/delete/list router | US1 |
| `backend/api/chat.py` | Chat endpoint with NDJSON streaming | US1, US3 |
| `backend/api/traces.py` | Trace retrieval endpoints | US4 |
| `backend/api/providers.py` | Provider management endpoints | US5 |
| `backend/api/health.py` | System health check | US2 |
| `backend/agent/__init__.py` | Package marker | — |
| `backend/agent/state.py` | TypedDict state schemas for 3 LangGraph layers | US1 |
| `backend/agent/schemas.py` | Pydantic models for agent + API responses | US1, US4 |
| `backend/agent/prompts.py` | All prompt templates as string constants | US1 |
| `backend/storage/__init__.py` | Package marker | — |
| `backend/storage/sqlite_db.py` | SQLite connection, WAL mode, table creation | US1 |
| `backend/storage/qdrant_client.py` | Qdrant client wrapper with health check | US1 |
| `backend/storage/document_parser.py` | PDF/MD/TXT → text extraction | US1 |
| `backend/storage/chunker.py` | Parent/child chunking strategy | US1 |
| `backend/storage/indexing.py` | Embedding + Qdrant upsert pipeline | US1 |
| `backend/providers/__init__.py` | Package marker | — |
| `backend/providers/base.py` | LLMProvider ABC, EmbeddingProvider ABC | US1 |
| `backend/providers/registry.py` | ProviderRegistry class | US5 |
| `backend/providers/ollama.py` | OllamaProvider implementation | US1 |
| `frontend/src/pages/index.tsx` | Collections browser + document upload | US1, US2 |
| `frontend/src/pages/chat/[id].tsx` | Chat interface for a collection | US1, US3 |
| `frontend/src/pages/traces/[id].tsx` | Query trace viewer | US4 |
| `frontend/src/pages/settings.tsx` | Provider selection + API key management | US5 |
| `frontend/src/components/CollectionsList.tsx` | Collection list with edit/delete | US1 |
| `frontend/src/components/DocumentUpload.tsx` | File upload form | US1 |
| `frontend/src/components/ChatBox.tsx` | Streaming response display | US1, US3 |
| `frontend/src/components/CitationLink.tsx` | Clickable citation links | US1 |
| `frontend/src/components/ConfidenceIndicator.tsx` | 0–100% confidence badge | US1 |
| `frontend/src/components/TraceViewer.tsx` | Hierarchical trace display | US4 |
| `frontend/src/components/PassageDetail.tsx` | Expandable passage with scores | US4 |
| `frontend/src/components/ProviderConfig.tsx` | Provider API key form | US5 |
| `frontend/src/hooks/useStreamingChat.ts` | React hook for NDJSON stream consumption | US3 |
| `frontend/src/api/client.ts` | Fetch wrappers for backend API | — |
| `frontend/src/types/index.ts` | TypeScript interfaces | — |
| `docker-compose.yml` | Full service orchestration (4 services) | US2 |
| `docker-compose.dev.yml` | Development overrides | US2 |
| `.env.example` | Environment variable template | US2 |
| `Makefile` | Developer command shortcuts | US2 |
| `requirements.txt` | Python dependencies | — |
| `.gitignore` | Ignore data/, __pycache__, .env, etc. | — |

## Code Specifications

### backend/config.py

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # Frontend
    frontend_port: int = 3000

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Providers
    ollama_base_url: str = "http://localhost:11434"
    default_provider: str = "ollama"
    default_llm_model: str = "qwen2.5:7b"      # Spec default (was llama3.2)
    default_embed_model: str = "nomic-embed-text"
    api_key_encryption_secret: str = ""          # For Fernet encryption of cloud API keys

    # SQLite
    sqlite_path: str = "data/embedinator.db"

    # Ingestion (Phase 2: Rust worker; Phase 1: Python)
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 100
    parent_chunk_size: int = 3000
    child_chunk_size: int = 500
    embed_batch_size: int = 16

    # Agent
    max_iterations: int = 10
    max_tool_calls: int = 8
    confidence_threshold: int = 60   # 0–100 scale (internal threshold)
    meta_reasoning_max_attempts: int = 2

    # Retrieval
    hybrid_dense_weight: float = 0.7
    hybrid_sparse_weight: float = 0.3
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Accuracy & Robustness
    groundedness_check_enabled: bool = True
    citation_alignment_threshold: float = 0.3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_secs: int = 30
    retry_max_attempts: int = 3
    retry_backoff_initial_secs: float = 1.0

    # Rate Limiting (Phase 1: no enforcement; Phase 2: per-endpoint)
    rate_limit_chat_per_minute: int = 100
    rate_limit_ingest_per_minute: int = 10

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env")
```

### backend/errors.py

```python
class EmbeddinatorError(Exception):
    """Base exception for all Embedinator errors."""

class QdrantConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Qdrant."""

class OllamaConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Ollama."""

class SQLiteError(EmbeddinatorError):
    """SQLite operation failed."""

class LLMCallError(EmbeddinatorError):
    """LLM inference call failed."""

class EmbeddingError(EmbeddinatorError):
    """Embedding generation failed."""

class IngestionError(EmbeddinatorError):
    """Document ingestion pipeline failed."""

class SessionLoadError(EmbeddinatorError):
    """Failed to load session from SQLite."""

class StructuredOutputParseError(EmbeddinatorError):
    """Failed to parse structured output from LLM."""

class RerankerError(EmbeddinatorError):
    """Cross-encoder reranking failed."""
```

### backend/agent/state.py

```python
from typing import TypedDict, List, Optional, Set
from langchain_core.messages import BaseMessage
from backend.agent.schemas import (
    QueryAnalysis, SubAnswer, Citation,
    GroundednessResult, RetrievedChunk,
)

class ConversationState(TypedDict):
    session_id: str
    messages: List[BaseMessage]
    query_analysis: Optional[QueryAnalysis]
    sub_answers: List[SubAnswer]
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    final_response: Optional[str]
    citations: List[Citation]
    groundedness_result: Optional[GroundednessResult]
    confidence_score: int               # 0–100 scale (user-facing)
    iteration_count: int

class ResearchState(TypedDict):
    sub_question: str
    session_id: str
    selected_collections: List[str]
    llm_model: str
    embed_model: str
    retrieved_chunks: List[RetrievedChunk]
    retrieval_keys: Set[str]
    tool_call_count: int
    iteration_count: int
    confidence_score: float             # Internal computation (0.0–1.0)
    answer: Optional[str]
    citations: List[Citation]
    context_compressed: bool

class MetaReasoningState(TypedDict):
    sub_question: str
    retrieved_chunks: List[RetrievedChunk]
    alternative_queries: List[str]
    mean_relevance_score: float
    chunk_relevance_scores: List[float]
    meta_attempt_count: int
    recovery_strategy: Optional[str]
    modified_state: Optional[dict]
    answer: Optional[str]
    uncertainty_reason: Optional[str]
```

### backend/agent/schemas.py

Internal agent schemas + API response models. Must match `data-model.md` entity definitions.

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime

# --- Internal Agent Schemas ---

class QueryAnalysis(BaseModel):
    is_clear: bool
    sub_questions: List[str]
    clarification_needed: Optional[str]
    collections_hint: List[str]
    complexity_tier: Literal[
        "factoid", "lookup", "comparison", "analytical", "multi_hop"
    ]

class RetrievedChunk(BaseModel):
    chunk_id: str
    text: str
    source_file: str
    page: Optional[int]
    breadcrumb: str
    parent_id: str
    collection: str
    dense_score: float
    sparse_score: float
    rerank_score: Optional[float] = None

class ParentChunk(BaseModel):
    parent_id: str
    text: str
    source_file: str
    page: Optional[int]
    breadcrumb: str
    collection: str

class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str]
    explanation: str

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool
    confidence_adjustment: float

# --- API Response Schemas (match data-model.md) ---

class CollectionResponse(BaseModel):
    id: str
    name: str
    document_count: int = 0
    created_at: datetime

class DocumentResponse(BaseModel):
    id: str
    name: str
    collection_ids: List[str]
    status: Literal["uploaded", "parsing", "indexing", "indexed", "failed", "deleted"]
    upload_date: datetime

class Citation(BaseModel):
    """Citation in an answer. Matches data-model.md Citation object."""
    passage_id: str
    document_id: str
    document_name: str
    start_offset: int
    end_offset: int
    text: str
    relevance_score: float  # 0.0–1.0

class SubAnswer(BaseModel):
    sub_question: str
    answer: str
    citations: List[Citation]
    chunks: List[RetrievedChunk]
    confidence_score: int  # 0–100

class Passage(BaseModel):
    """Retrieved passage in a trace. Matches data-model.md Passage object."""
    id: str
    document_id: str
    document_name: str
    text: str
    relevance_score: float
    chunk_index: int
    source_removed: bool = False

class ReasoningStep(BaseModel):
    step_num: int
    strategy: str  # "initial_retrieval", "fallback_reranking", "query_decomposition"
    passages_found: int
    avg_score: float

class TraceResponse(BaseModel):
    """Full trace response. Matches data-model.md Trace entity."""
    id: str
    query_id: str
    query_text: str
    collections_searched: List[str]
    passages_retrieved: List[Passage]
    confidence_score: int = Field(ge=0, le=100)  # 0–100 integer
    reasoning_steps: Optional[List[ReasoningStep]] = None
    created_at: datetime

class AnswerResponse(BaseModel):
    id: str
    query_id: str
    answer_text: str
    citations: List[Citation]
    confidence_score: int = Field(ge=0, le=100)  # 0–100 integer
    generated_at: datetime

class ProviderResponse(BaseModel):
    name: str
    type: str
    is_active: bool
    status: str  # "ready", "configured", "unavailable"
    model: Optional[str] = None

class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded"]
    services: dict  # {"sqlite": "ok", "qdrant": "ok", "ollama": "ok"}
```

### backend/storage/sqlite_db.py

Async SQLite with WAL mode. DDL matches `data-model.md` exactly.

```python
import aiosqlite
from pathlib import Path

class SQLiteDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def connect(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path)
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()

    async def _create_tables(self):
        await self.db.executescript("""
            CREATE TABLE IF NOT EXISTS collections (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                collection_ids JSON NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT DEFAULT 'uploaded',
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                file_size_bytes INT,
                parse_error TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);

            CREATE TABLE IF NOT EXISTS queries (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                collection_ids JSON NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_queries_session_id ON queries(session_id);

            CREATE TABLE IF NOT EXISTS answers (
                id TEXT PRIMARY KEY,
                query_id TEXT NOT NULL,
                answer_text TEXT NOT NULL,
                citations JSON NOT NULL,
                confidence_score INT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
                generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_id) REFERENCES queries(id)
            );

            CREATE TABLE IF NOT EXISTS traces (
                id TEXT PRIMARY KEY,
                query_id TEXT NOT NULL,
                query_text TEXT NOT NULL,
                collections_searched JSON NOT NULL,
                passages_retrieved JSON NOT NULL,
                confidence_score INT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
                reasoning_steps JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (query_id) REFERENCES queries(id)
            );
            CREATE INDEX IF NOT EXISTS idx_traces_query_id ON traces(query_id);

            CREATE TABLE IF NOT EXISTS providers (
                name TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                config_json TEXT NOT NULL,
                is_active BOOLEAN DEFAULT 0
            );
        """)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()
```

### backend/api/chat.py (Streaming Endpoint)

NDJSON streaming protocol matching `contracts/api.md`.

```python
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List
import json

router = APIRouter()

class ChatRequest(BaseModel):
    query: str
    collection_ids: List[str]
    model_name: str = "qwen2.5:7b"

@router.post("/api/chat")
async def chat(request: ChatRequest, req: Request):
    """Stream answer as NDJSON. SC-002: first words within 1 second."""

    async def generate():
        # 1. Record query in SQLite
        # 2. Retrieve passages from Qdrant for each collection
        # 3. Call LLM with streaming; yield chunks as they arrive
        # 4. After completion, yield metadata with trace_id and confidence

        # Each line is a complete JSON object followed by newline:
        # {"type": "chunk", "text": "The"}
        # {"type": "chunk", "text": " main"}
        # ...
        # {"type": "metadata", "trace_id": "trace-xxx", "confidence_score": 87, "citations_count": 3}

        async for token in llm_stream:
            yield json.dumps({"type": "chunk", "text": token}) + "\n"

        yield json.dumps({
            "type": "metadata",
            "trace_id": trace_id,
            "confidence_score": confidence,  # int 0–100
            "citations": [
                {"document_name": c.document_name, "passage_text": c.text}
                for c in citations
            ]
        }) + "\n"

    return StreamingResponse(
        generate(),
        media_type="application/x-ndjson",
        headers={"X-Trace-ID": trace_id}
    )
```

### backend/api/health.py

```python
from fastapi import APIRouter
from backend.agent.schemas import HealthResponse

router = APIRouter()

@router.get("/api/health", response_model=HealthResponse)
async def health(request: Request):
    """Check SQLite, Qdrant, and Ollama connectivity."""
    services = {}
    status = "healthy"

    # Check each service; set to "error: <reason>" on failure
    # If any service is down, status = "degraded" and return 503

    return HealthResponse(status=status, services=services)
```

### frontend/src/types/index.ts

TypeScript interfaces matching `data-model.md` and `contracts/api.md`.

```typescript
export interface Collection {
  id: string;
  name: string;
  document_count: number;
  created_at: string;
}

export interface Document {
  id: string;
  name: string;
  collection_ids: string[];
  status: 'uploaded' | 'parsing' | 'indexing' | 'indexed' | 'failed' | 'deleted';
  upload_date: string;
}

export interface Passage {
  id: string;
  document_id: string;
  document_name: string;
  text: string;
  relevance_score: number;
  chunk_index: number;
  source_removed: boolean;
}

export interface Citation {
  passage_id: string;
  document_id: string;
  document_name: string;
  text: string;
  relevance_score: number;
}

export interface Trace {
  id: string;
  query_id: string;
  query_text: string;
  collections_searched: string[];
  passages_retrieved: Passage[];
  confidence_score: number;  // 0–100 integer
  reasoning_steps?: ReasoningStep[];
  created_at: string;
}

export interface ReasoningStep {
  step_num: number;
  strategy: string;
  passages_found: number;
  avg_score: number;
}

export interface Provider {
  name: string;
  type: 'local' | 'cloud';
  is_active: boolean;
  status: string;
  model?: string;
}

// NDJSON stream types for chat endpoint
export type StreamChunk =
  | { type: 'chunk'; text: string }
  | { type: 'metadata'; trace_id: string; confidence_score: number; citations: Citation[] };
```

### frontend/src/hooks/useStreamingChat.ts

React hook consuming NDJSON stream from `/api/chat`. Implements SC-002 (first words within 1 second).

```typescript
import { useState, useCallback } from 'react';
import type { StreamChunk, Citation } from '../types';

export function useStreamingChat() {
  const [text, setText] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [traceId, setTraceId] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [error, setError] = useState<string | null>(null);

  const sendQuery = useCallback(async (
    query: string,
    collectionIds: string[],
    modelName: string = 'qwen2.5:7b'
  ) => {
    setText('');
    setIsStreaming(true);
    setError(null);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, collection_ids: collectionIds, model_name: modelName }),
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value, { stream: true }).split('\n');
        for (const line of lines) {
          if (!line.trim()) continue;
          const chunk: StreamChunk = JSON.parse(line);

          if (chunk.type === 'chunk') {
            setText(prev => prev + chunk.text);
          } else if (chunk.type === 'metadata') {
            setTraceId(chunk.trace_id);
            setConfidence(chunk.confidence_score);
            setCitations(chunk.citations);
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Stream failed');
    } finally {
      setIsStreaming(false);
    }
  }, []);

  return { text, isStreaming, traceId, confidence, citations, error, sendQuery };
}
```

### frontend/src/components/ConfidenceIndicator.tsx

Displays confidence as 0–100% with color coding (FR-008a clarification).

```tsx
interface ConfidenceIndicatorProps {
  score: number;  // 0–100 integer
}

export function ConfidenceIndicator({ score }: ConfidenceIndicatorProps) {
  // Color coding: green 80–100, yellow 50–79, red 0–49
  const color = score >= 80 ? 'green' : score >= 50 ? 'yellow' : 'red';
  return <span className={`confidence-badge confidence-${color}`}>{score}% confident</span>;
}
```

## Configuration

### docker-compose.yml (reference structure)

```yaml
services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - ./data/qdrant_db:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/healthz"]
      interval: 10s
      timeout: 5s
      retries: 3

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama
    entrypoint: ["/bin/sh", "-c", "ollama serve & sleep 5 && ollama pull qwen2.5:7b && wait"]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:11434/api/tags"]
      interval: 15s
      timeout: 10s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      qdrant:
        condition: service_healthy
      ollama:
        condition: service_healthy
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/health"]
      interval: 10s
      timeout: 5s
      retries: 3

  frontend:
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000

volumes:
  ollama_models:
```

### Environment Variables (.env.example)

```bash
# -- Ollama --
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
DEFAULT_LLM_MODEL=qwen2.5:7b
DEFAULT_EMBED_MODEL=nomic-embed-text

# -- Qdrant --
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# -- Backend --
HOST=0.0.0.0
PORT=8000
SQLITE_PATH=./data/embedinator.db
LOG_LEVEL=INFO
DEBUG=false

# -- Frontend --
FRONTEND_PORT=3000

# -- Security --
API_KEY_ENCRYPTION_SECRET=       # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# -- Agent Limits --
MAX_ITERATIONS=10
MAX_TOOL_CALLS=8
CONFIDENCE_THRESHOLD=60          # 0–100 scale

# -- Retrieval --
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# -- CORS --
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
```

## Streaming Protocol (NDJSON)

The chat endpoint streams responses as **Newline-Delimited JSON** (application/x-ndjson):

```
{"type": "chunk", "text": "The"}
{"type": "chunk", "text": " main"}
{"type": "chunk", "text": " findings"}
...
{"type": "metadata", "trace_id": "trace-abc", "confidence_score": 92, "citations": [{"document_name": "report.pdf", "passage_text": "..."}]}
```

- Each line is a complete JSON object followed by `\n`
- `type: "chunk"` — incremental answer text
- `type: "metadata"` — final metadata sent after all chunks (trace_id, confidence 0–100, citations)
- Stream ends with EOF
- **SC-002**: First chunk must arrive within 1 second of query submission
- **Error recovery**: On connection drop, frontend displays failure message (US3 acceptance scenario 3)

## Error Handling

- **Startup Failures**: If Qdrant or Ollama are unreachable at startup, log a warning but allow the backend to start. The health endpoint reports degraded status. This allows the UI to load and display connection status.
- **SQLite Init**: If `data/` directory does not exist, create it. If database file does not exist, create it with all tables. Enable WAL mode on first connection.
- **Graceful Shutdown**: Close SQLite connection and Qdrant client in lifespan shutdown.
- **Document Deletion**: Mark status as `deleted`; traces retain captured passage text with `source_removed: true` (FR-002a).
- **Off-topic Queries**: When confidence < threshold, system declines to answer and communicates clearly (FR-015, SC-008).

### Error Response Format (from contracts/api.md)

All API errors follow this format:

```json
{
  "error": {
    "code": "COLLECTION_NOT_FOUND",
    "message": "Collection 'col-001' not found",
    "details": {}
  }
}
```

Error codes: `COLLECTION_NOT_FOUND` (404), `DOCUMENT_NOT_FOUND` (404), `TRACE_NOT_FOUND` (404), `INVALID_REQUEST` (400), `FILE_FORMAT_NOT_SUPPORTED` (400), `SERVICE_UNAVAILABLE` (503), `INTERNAL_SERVER_ERROR` (500).

## Testing Requirements

### Backend
- **Unit**: `backend/config.py` loads defaults correctly; env var overrides work
- **Unit**: `backend/errors.py` exception hierarchy is correct (all inherit from `EmbeddinatorError`)
- **Unit**: `backend/agent/schemas.py` Pydantic models validate and serialize correctly; confidence_score constrained 0–100
- **Unit**: `backend/agent/state.py` TypedDict definitions are importable and type-correct
- **Unit**: `backend/storage/sqlite_db.py` creates all tables with correct schema; WAL mode enabled
- **Unit**: `backend/providers/` provider registry resolves providers, Ollama health check works
- **Integration**: `backend/main.py` starts without errors when Qdrant and Ollama are available
- **Integration**: Health endpoint returns service status for Qdrant, Ollama, SQLite
- **Integration**: Upload document → parse → chunk → index → query → get cited answer (US1 end-to-end)
- **Integration**: Chat streaming returns NDJSON with first chunk < 1s (SC-002)

### Frontend
- **Unit**: TypeScript interfaces compile without errors
- **Unit**: `useStreamingChat` hook handles stream consumption and error states
- **Integration**: Collections browser loads and displays collections from API
- **Integration**: Chat interface sends query and renders streaming response
- **E2E**: Full workflow: create collection → upload document → ask question → see cited answer with confidence

## Done Criteria

### Backend Infrastructure
- [ ] `backend/config.py` exists with all Settings fields; default model is `qwen2.5:7b`
- [ ] `backend/errors.py` exists with complete exception hierarchy
- [ ] `backend/agent/state.py` exists with ConversationState (confidence: int 0–100), ResearchState, MetaReasoningState
- [ ] `backend/agent/schemas.py` exists with all internal + API response models; confidence constrained 0–100
- [ ] `backend/storage/sqlite_db.py` creates database with WAL mode and all 6 tables (collections, documents, queries, answers, traces, providers)
- [ ] `backend/storage/qdrant_client.py` connects and performs health check
- [ ] `backend/providers/` registry resolves Ollama by default; abstract base for LLM/Embedding providers

### API Endpoints
- [ ] `POST /api/collections` creates collection; `GET` lists; `DELETE` removes — **US1**
- [ ] `POST /api/documents` uploads file (PDF/MD/TXT) to collection(s); `DELETE` marks deleted — **US1**
- [ ] `POST /api/chat` streams NDJSON response with chunks + metadata — **US1, US3**
- [ ] `GET /api/traces/{trace_id}` returns full trace with passages and scores — **US4**
- [ ] `GET/POST /api/providers` lists and configures providers — **US5**
- [ ] `GET /api/health` returns status of SQLite, Qdrant, Ollama — **US2**

### Frontend
- [ ] Collections browser with document upload at `index.tsx` — **US1**
- [ ] Chat interface with streaming display at `chat/[id].tsx` — **US1, US3**
- [ ] Confidence indicator (0–100% badge) on every answer — **FR-008a**
- [ ] Trace viewer at `traces/[id].tsx` — **US4**
- [ ] Provider settings at `settings.tsx` — **US5**

### Deployment
- [ ] `docker-compose.yml` defines 4 services with health checks; Ollama auto-pulls `qwen2.5:7b`
- [ ] `.env.example` documents all environment variables
- [ ] `make dev` starts all services in development mode — **SC-004**
- [ ] `requirements.txt` lists all Python dependencies with version constraints

### Success Criteria Verification
- [ ] **SC-001**: New user uploads doc + gets cited answer within 5 minutes of `make dev`
- [ ] **SC-002**: First words of streaming answer appear in browser within 1 second
- [ ] **SC-003**: No data leaves machine in default config (Ollama only, no external calls)
- [ ] **SC-004**: `make dev` starts all 4 services with zero manual configuration
- [ ] **SC-005**: Every answer statement traceable to source passage via trace view
- [ ] **SC-006**: System attempts fallback strategy when initial retrieval confidence < threshold
- [ ] **SC-007**: User switches from Ollama to cloud provider without restart via settings UI
- [ ] **SC-008**: System declines to answer off-topic queries (confidence below threshold → "no relevant info" response)
