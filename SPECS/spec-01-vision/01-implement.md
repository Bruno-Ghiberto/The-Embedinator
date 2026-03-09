# Spec 01: Vision & System Architecture -- Implementation Context

## Implementation Scope

### Files to Create

| File | Purpose |
|------|---------|
| `backend/__init__.py` | Package marker |
| `backend/config.py` | Pydantic Settings with all env vars |
| `backend/errors.py` | Custom exception hierarchy |
| `backend/main.py` | FastAPI app factory with lifespan |
| `backend/middleware.py` | CORS, rate limiting, trace ID injection |
| `backend/api/__init__.py` | Package marker |
| `backend/api/collections.py` | Stub collection CRUD router |
| `backend/api/chat.py` | Stub chat endpoint router |
| `backend/api/models.py` | Stub model listing router |
| `backend/api/settings.py` | Stub settings router |
| `backend/api/providers.py` | Stub provider management router |
| `backend/api/traces.py` | Stub traces/health/stats router |
| `backend/agent/__init__.py` | Package marker |
| `backend/agent/state.py` | TypedDict state schemas for all three graphs |
| `backend/agent/schemas.py` | Pydantic models: QueryAnalysis, SubAnswer, Citation, etc. |
| `backend/agent/prompts.py` | All prompt templates as string constants |
| `backend/storage/__init__.py` | Package marker |
| `backend/storage/sqlite_db.py` | SQLite connection, WAL mode, table creation |
| `backend/storage/qdrant_client.py` | Qdrant client wrapper with health check |
| `backend/providers/__init__.py` | Package marker |
| `backend/providers/base.py` | LLMProvider ABC, EmbeddingProvider ABC |
| `backend/providers/registry.py` | ProviderRegistry class |
| `backend/providers/ollama.py` | OllamaProvider implementation |
| `docker-compose.yml` | Full service orchestration |
| `docker-compose.dev.yml` | Development overrides |
| `.env.example` | Environment variable template |
| `Makefile` | Developer command shortcuts |
| `requirements.txt` | Python dependencies |
| `.gitignore` | Ignore data/, __pycache__, .env, etc. |

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

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # Providers
    ollama_base_url: str = "http://localhost:11434"
    default_provider: str = "ollama"
    default_llm_model: str = "llama3.2"
    default_embed_model: str = "nomic-embed-text"
    api_key_encryption_secret: str = ""

    # SQLite
    sqlite_path: str = "data/embedinator.db"

    # Ingestion
    rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 100
    parent_chunk_size: int = 3000
    child_chunk_size: int = 500
    embed_batch_size: int = 16
    embed_max_workers: int = 4
    qdrant_upsert_batch_size: int = 50

    # Agent
    max_iterations: int = 10
    max_tool_calls: int = 8
    confidence_threshold: float = 0.6
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

    # Rate Limiting
    rate_limit_chat_per_minute: int = 30
    rate_limit_ingest_per_minute: int = 10
    rate_limit_default_per_minute: int = 120

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
    confidence_score: float
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
    confidence_score: float
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

```python
from pydantic import BaseModel
from typing import List, Optional, Literal

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

class Citation(BaseModel):
    index: int
    chunk_id: str
    source: str
    page: Optional[int]
    breadcrumb: str
    claim_text: str
    chunk: RetrievedChunk

class SubAnswer(BaseModel):
    sub_question: str
    answer: str
    citations: List[Citation]
    chunks: List[RetrievedChunk]
    confidence_score: float

class ClaimVerification(BaseModel):
    claim: str
    verdict: Literal["supported", "unsupported", "contradicted"]
    evidence_chunk_id: Optional[str]
    explanation: str

class GroundednessResult(BaseModel):
    verifications: List[ClaimVerification]
    overall_grounded: bool
    confidence_adjustment: float
```

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

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_models:/root/.ollama

  backend:
    build:
      context: .
      dockerfile: Dockerfile.backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - qdrant
      - ollama
    volumes:
      - ./data:/app/data

  frontend:
    build:
      context: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend

volumes:
  ollama_models:
```

## Configuration

### Environment Variables (.env.example)

```bash
# -- Ollama --
OLLAMA_BASE_URL=http://localhost:11434
DEFAULT_LLM_MODEL=llama3.2
DEFAULT_EMBED_MODEL=nomic-embed-text

# -- Qdrant --
QDRANT_HOST=localhost
QDRANT_PORT=6333

# -- Backend --
HOST=0.0.0.0
PORT=8000
SQLITE_PATH=data/embedinator.db
LOG_LEVEL=INFO
DEBUG=false

# -- Security --
API_KEY_ENCRYPTION_SECRET=

# -- Agent Limits --
MAX_ITERATIONS=10
MAX_TOOL_CALLS=8
CONFIDENCE_THRESHOLD=0.6

# -- Retrieval --
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

## Error Handling

- **Startup Failures**: If Qdrant or Ollama are unreachable at startup, log a warning but allow the backend to start. The health endpoint should report degraded status. This allows the UI to load and display connection status.
- **SQLite Init**: If `data/` directory does not exist, create it. If database file does not exist, create it with all tables. Enable WAL mode on first connection.
- **Graceful Shutdown**: Close SQLite connection and Qdrant client in lifespan shutdown.

## Testing Requirements

- **Unit**: `backend/config.py` loads defaults correctly; env var overrides work.
- **Unit**: `backend/errors.py` exception hierarchy is correct (all inherit from `EmbeddinatorError`).
- **Unit**: `backend/agent/schemas.py` Pydantic models validate and serialize correctly.
- **Unit**: `backend/agent/state.py` TypedDict definitions are importable and type-correct.
- **Integration**: `backend/main.py` starts without errors when Qdrant and Ollama are available.
- **Integration**: Health endpoint returns service status for Qdrant, Ollama, SQLite.

## Done Criteria

- [ ] `backend/config.py` exists with all Settings fields matching architecture doc
- [ ] `backend/errors.py` exists with complete exception hierarchy
- [ ] `backend/agent/state.py` exists with ConversationState, ResearchState, MetaReasoningState
- [ ] `backend/agent/schemas.py` exists with QueryAnalysis, SubAnswer, Citation, RetrievedChunk, ParentChunk, ClaimVerification, GroundednessResult
- [ ] `backend/main.py` creates FastAPI app with lifespan, registers routers
- [ ] `backend/storage/sqlite_db.py` creates database with WAL mode and all tables
- [ ] `backend/storage/qdrant_client.py` connects and performs health check
- [ ] `docker-compose.yml` defines qdrant, ollama, backend, frontend services
- [ ] `.env.example` documents all environment variables
- [ ] `requirements.txt` lists all Python dependencies with version constraints
- [ ] `make dev` starts the backend in development mode
- [ ] Health endpoint returns JSON with qdrant, ollama, sqlite status
