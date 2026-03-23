# backend/

Python backend for The Embedinator, built with FastAPI and LangGraph.

## Module Structure

| Directory     | Purpose                                                |
|---------------|--------------------------------------------------------|
| `agent/`      | 3-layer LangGraph agent (conversation, research, meta-reasoning) |
| `api/`        | FastAPI route handlers for all REST and streaming endpoints |
| `storage/`    | SQLite and Qdrant data persistence layer               |
| `providers/`  | Pluggable LLM provider system with encrypted key storage |
| `retrieval/`  | Hybrid search, cross-encoder reranking, score normalization |
| `ingestion/`  | Document processing pipeline with Rust worker orchestration |

## Key Files

- **`main.py`** -- App factory with `lifespan` context manager. Initializes
  SQLite, Qdrant, provider registry, LangGraph checkpointer, and compiles all
  three agent graphs (inside-out: MetaReasoning -> Research -> Conversation).
- **`config.py`** -- Centralized configuration via `pydantic-settings`. All
  environment variables are defined in the `Settings` class with sensible
  defaults.
- **`errors.py`** -- Custom exception hierarchy rooted at `EmbeddinatorError`.
  Includes `QdrantConnectionError`, `OllamaConnectionError`, `CircuitOpenError`,
  and others, each mapped to specific HTTP status codes.
- **`middleware.py`** -- Request middleware stack: `TraceIDMiddleware` (assigns
  trace IDs), `RequestLoggingMiddleware` (structured logging),
  `RateLimitMiddleware` (per-endpoint sliding window limits).

## Running

```bash
# Development (hot reload)
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or via Makefile
make dev-backend
```

The backend expects Qdrant on `localhost:6333` and Ollama on
`localhost:11434` by default. Start them with `make dev-infra`.

## Key Patterns

- **App factory** -- `create_app()` returns a configured FastAPI instance.
  All state (DB connections, graphs, tools) is attached to `app.state` during
  the async `lifespan` context manager.
- **Pydantic Settings** -- `backend.config.settings` is the single source of
  truth for configuration. All env vars, including `EMBEDINATOR_FERNET_KEY`
  (aliased), are defined there.
- **structlog JSON logging** -- All modules use `structlog.get_logger()` bound
  with `component=__name__`. Per-component log level overrides are supported
  via `LOG_LEVEL_OVERRIDES`.
- **Circuit breaker + retry** -- Qdrant and Ollama calls use a circuit breaker
  pattern with configurable failure threshold and cooldown. Transient failures
  are retried with exponential backoff (via tenacity).
