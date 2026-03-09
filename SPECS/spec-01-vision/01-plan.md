# Spec 01: Vision & System Architecture -- Implementation Plan Context

## Component Overview

This spec establishes the foundational project structure, configuration system, Docker Compose orchestration, and FastAPI application factory. It is the skeleton upon which all other specs build. No agent logic, no retrieval, no frontend -- just the bare infrastructure that proves all six services can start and communicate.

## Technical Approach

- **FastAPI** with `lifespan` context manager for startup/shutdown of Qdrant client, SQLite connection, and Ollama health check.
- **Pydantic Settings** (`pydantic-settings`) for centralized configuration loaded from `.env` file with sensible defaults.
- **aiosqlite** for async SQLite access with WAL mode enabled on first connection.
- **Docker Compose** to orchestrate Qdrant, Ollama, FastAPI backend, and Next.js frontend containers.
- **Makefile** for common developer commands (`make dev`, `make build`, `make test`).
- **structlog** for structured JSON logging with trace ID propagation.

## File Structure

```
the-embedinator/
  backend/
    __init__.py
    main.py                # FastAPI app factory, router registration, lifespan
    config.py              # Pydantic Settings: all env vars, defaults
    errors.py              # Error hierarchy (all custom exceptions)
    middleware.py          # CORS, rate limiting, trace ID injection
    api/
      __init__.py
      collections.py       # Stub: Collection CRUD endpoints
      chat.py              # Stub: Chat endpoint + SSE streaming
      models.py            # Stub: Ollama model listing proxy
      settings.py          # Stub: Settings CRUD
      providers.py         # Stub: Provider management endpoints
      traces.py            # Stub: Query trace log + health + stats
    agent/
      __init__.py
      state.py             # TypedDict state schemas for all three graphs
      schemas.py           # Pydantic models: QueryAnalysis, SubAnswer, Citation, etc.
      prompts.py           # All system and user prompts as constants
    storage/
      __init__.py
      sqlite_db.py         # SQLite connection, table creation, WAL mode
      qdrant_client.py     # Qdrant connection, health check
    providers/
      __init__.py
      base.py              # LLMProvider ABC, EmbeddingProvider ABC
      registry.py          # ProviderRegistry: model name -> provider resolution
      ollama.py            # OllamaProvider (default)
  data/                    # gitignored -- runtime data
    uploads/
    qdrant_db/
  docker-compose.yml
  docker-compose.dev.yml
  .env.example
  Makefile
  requirements.txt
  .gitignore
```

## Implementation Steps

1. **Create `backend/config.py`**: Define `Settings` class with all environment variables and defaults from the architecture doc. This is the single source of truth for all configuration.

2. **Create `backend/errors.py`**: Define the custom exception hierarchy: `EmbeddinatorError` (base), `QdrantConnectionError`, `OllamaConnectionError`, `SQLiteError`, `LLMCallError`, `EmbeddingError`, `IngestionError`, `SessionLoadError`, `StructuredOutputParseError`, `RerankerError`.

3. **Create `backend/storage/sqlite_db.py`**: Implement `SQLiteDB` class with async context manager, WAL mode init, and table creation for `collections`, `documents`, `ingestion_jobs`, `parent_chunks`, `query_traces`, `providers`, `settings`, `sessions`.

4. **Create `backend/storage/qdrant_client.py`**: Implement Qdrant client wrapper with health check, connection pooling, and circuit breaker pattern.

5. **Create `backend/main.py`**: FastAPI application factory with `lifespan` async context manager that initializes SQLite, Qdrant client, and Ollama health check on startup. Register all API routers. Apply CORS middleware.

6. **Create `backend/middleware.py`**: CORS configuration, rate limiting (per-endpoint), trace ID injection via middleware.

7. **Create `backend/providers/base.py`**: Abstract base classes `LLMProvider` and `EmbeddingProvider`.

8. **Create `backend/providers/registry.py`**: `ProviderRegistry` class for model name to provider resolution.

9. **Create `backend/providers/ollama.py`**: Default `OllamaProvider` implementation.

10. **Create stub API routers**: Minimal routers in `backend/api/` that return placeholder responses. These will be filled in by later specs.

11. **Create `backend/agent/state.py`**: All three TypedDict state schemas.

12. **Create `backend/agent/schemas.py`**: All Pydantic models used across the agent.

13. **Create `docker-compose.yml`**: Define services for `qdrant`, `ollama`, `backend`, and `frontend` with volume mounts, port mappings, and health checks.

14. **Create `.env.example`**: Template with all environment variables and documentation comments.

15. **Create `Makefile`**: Targets for `dev`, `build`, `test`, `lint`, `docker-up`, `docker-down`.

16. **Create `requirements.txt`**: All Python dependencies with version constraints.

## Integration Points

- **All other specs depend on this one**: The config system, error hierarchy, state schemas, and Pydantic models are imported by every other module.
- **Docker Compose** is the deployment entry point. Later specs add functionality but do not modify the service topology.
- **`backend/main.py`** lifespan initializes shared resources (SQLite, Qdrant client, reranker model) that are injected into API handlers and agent nodes via FastAPI's dependency injection.

## Key Code Patterns

### FastAPI Lifespan Pattern
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app.state.db = await SQLiteDB.create(settings.sqlite_path)
    app.state.qdrant = QdrantClient(settings.qdrant_host, settings.qdrant_port)
    app.state.provider_registry = ProviderRegistry(settings)
    yield
    # Shutdown
    await app.state.db.close()
```

### Error Hierarchy Pattern
```python
class EmbeddinatorError(Exception):
    """Base exception for all Embedinator errors."""

class QdrantConnectionError(EmbeddinatorError): ...
class OllamaConnectionError(EmbeddinatorError): ...
class LLMCallError(EmbeddinatorError): ...
```

### State Schema Pattern
```python
from typing import TypedDict, List, Optional, Set
from langchain_core.messages import BaseMessage

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
```

## Phase Assignment

**Phase 1: Minimum Viable Product** -- This spec is entirely Phase 1. The project skeleton, configuration, Docker Compose, error hierarchy, state schemas, and Pydantic models must all exist before any feature work begins.
