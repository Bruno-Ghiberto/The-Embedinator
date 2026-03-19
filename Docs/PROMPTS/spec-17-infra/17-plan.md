# Spec 17: Infrastructure -- Implementation Plan Context

## Component Overview

The Infrastructure spec establishes the entire project skeleton: directory structure, Docker deployment strategy, build automation, configuration management, and dependency pinning. It is the foundation that every other spec builds upon. Without this infrastructure, no other component can be built, tested, or deployed.

## Technical Approach

### Project Structure

- Create the full directory tree as specified in the architecture document.
- Every Python package directory gets an `__init__.py` file.
- The `data/` directory is gitignored and created at runtime.
- The `tests/` directory follows the structure defined in Spec 16.

### Docker Strategy

- **Full Docker** (`docker-compose.yml`): Four services -- Qdrant, Ollama, backend, frontend. The backend uses a multi-stage Dockerfile that compiles Rust in Stage 1 and runs Python in Stage 2. The frontend uses a multi-stage Dockerfile with Next.js standalone output.
- **Dev Mode** (`docker-compose.dev.yml`): Two services only -- Qdrant and Ollama. Backend and frontend run natively with hot reload.
- Health checks on all services ensure proper startup ordering via `depends_on: condition: service_healthy`.
- NVIDIA GPU passthrough for Ollama using Docker `deploy.resources.reservations.devices`.

### Configuration Management

- `backend/config.py` uses `pydantic-settings` `BaseSettings` with `SettingsConfigDict(env_file=".env")`.
- All settings have typed defaults. No setting requires manual configuration for local development.
- `.env.example` serves as documentation and template. Users copy it to `.env` on first setup.
- Docker Compose overrides specific settings (e.g., `QDRANT_HOST=qdrant` instead of `localhost`) via the `environment` section.

### Dependency Management

- `requirements.txt` for Python production dependencies.
- `requirements-dev.txt` for Python test/development dependencies.
- `frontend/package.json` for JavaScript dependencies.
- `ingestion-worker/Cargo.toml` for Rust dependencies.

### Build Automation

- Makefile with targets for every common operation: setup, build, dev, deploy, test, clean.
- Each target is self-contained and includes clear output messages.

## File Structure

```
the-embedinator/
  backend/
    __init__.py
    api/
      __init__.py
      collections.py
      chat.py
      models.py
      settings.py
      providers.py
      traces.py
    agent/
      __init__.py
      conversation_graph.py
      research_graph.py
      meta_reasoning_graph.py
      nodes.py
      edges.py
      tools.py
      prompts.py
      schemas.py
      state.py
    ingestion/
      __init__.py
      pipeline.py
      embedder.py
      chunker.py
      incremental.py
    retrieval/
      __init__.py
      searcher.py
      reranker.py
      router.py
      score_normalizer.py
    storage/
      __init__.py
      qdrant_client.py
      sqlite_db.py
      parent_store.py
    providers/
      __init__.py
      base.py
      registry.py
      ollama.py
      openrouter.py
      openai.py
      anthropic.py
      key_manager.py
    errors.py
    config.py
    main.py
    middleware.py
    logging_config.py
    timing.py
    validators.py
    Dockerfile
    requirements.txt
  ingestion-worker/
    src/
      main.rs
      pdf.rs
      markdown.rs
      text.rs
      heading_tracker.rs
      types.rs
    Cargo.toml
  frontend/
    app/
      layout.tsx
      chat/page.tsx
      collections/page.tsx
      documents/[id]/page.tsx
      settings/page.tsx
      observability/page.tsx
    components/ (18 component files)
    lib/
      api.ts
      types.ts
    hooks/ (4 hook files)
    next.config.ts
    package.json
    tailwind.config.ts
    tsconfig.json
    Dockerfile
  tests/ (see Spec 16)
  data/ (gitignored)
  docker-compose.yml
  docker-compose.dev.yml
  .env.example
  .gitignore
  Makefile
  requirements.txt
  requirements-dev.txt
  README.md
```

## Implementation Steps

1. **Create root project files**: `docker-compose.yml`, `docker-compose.dev.yml`, `.env.example`, `Makefile`, `.gitignore`, `requirements.txt`, `requirements-dev.txt`.
2. **Create backend directory skeleton**: All Python package directories with `__init__.py` files. Create placeholder files for every module listed in the architecture.
3. **Implement `backend/config.py`**: Full Pydantic Settings class with all typed fields and defaults.
4. **Create `backend/Dockerfile`**: Multi-stage build -- Rust compilation in Stage 1, Python runtime in Stage 2.
5. **Create `frontend/Dockerfile`**: Multi-stage build -- Next.js build in Stage 1, standalone runner in Stage 2.
6. **Create `docker-compose.yml`**: Full deployment with all four services, health checks, GPU passthrough, volume mounts, and environment overrides.
7. **Create `docker-compose.dev.yml`**: Dev mode with Qdrant and Ollama only.
8. **Create `Makefile`**: All automation targets (setup, build-rust, dev-infra, dev-backend, dev-frontend, dev, up, down, pull-models, test, test-cov, test-frontend, clean, clean-all).
9. **Create `.env.example`**: All variables with defaults, grouped by category, with comments.
10. **Create `.gitignore`**: Ignore `data/`, `__pycache__/`, `.venv/`, `node_modules/`, `.next/`, `target/`, `.env`.
11. **Initialize frontend**: Create `package.json` with all JS dependencies, `next.config.ts` with standalone output, `tailwind.config.ts`, `tsconfig.json`.
12. **Initialize Rust worker**: Create `Cargo.toml` with all Rust dependencies.
13. **Create `requirements.txt`**: All Python production dependencies with version constraints.
14. **Create `requirements-dev.txt`**: All Python test/development dependencies.

## Integration Points

- **All specs**: Every spec depends on this infrastructure for project structure and configuration.
- **Security (Spec 13)**: `.env` contains `API_KEY_ENCRYPTION_SECRET`. Docker Compose passes env vars to backend.
- **Testing (Spec 16)**: Makefile targets for running tests. Docker containers for integration tests.
- **Observability (Spec 15)**: `LOG_LEVEL` and `DEBUG` env vars control logging behavior.
- **Performance (Spec 14)**: Configuration defaults in Settings class are tuned for performance budgets.

## Key Code Patterns

### Settings Instantiation Pattern

```python
from functools import lru_cache
from backend.config import Settings

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### FastAPI Dependency Injection for Settings

```python
from fastapi import Depends

@router.get("/api/collections")
async def list_collections(settings: Settings = Depends(get_settings)):
    ...
```

### Docker Networking Override

```yaml
# In docker-compose.yml, backend service overrides localhost references:
environment:
  - QDRANT_HOST=qdrant            # Docker service name, not localhost
  - OLLAMA_BASE_URL=http://ollama:11434
```

### Frontend Build-Time vs Runtime Env Vars

```yaml
# NEXT_PUBLIC_* vars are baked into the JS bundle at build time
# They must point to where the BROWSER can reach the API
- NEXT_PUBLIC_API_URL=http://localhost:8000

# INTERNAL_API_URL is for server-side Next.js (SSR/API routes)
# It uses the Docker service name
- INTERNAL_API_URL=http://backend:8000
```

## Phase Assignment

- **Phase 1 (MVP)**: Full project directory structure, docker-compose files (full + dev), Makefile, .env configuration, requirements.txt, `backend/config.py` Settings class, frontend package.json, Cargo.toml placeholder, `.gitignore`, backend Dockerfile (Python-only, no Rust stage yet in Phase 1).
- **Phase 2 (Performance and Resilience)**: Multi-stage backend Dockerfile with Rust compilation, Rust Cargo.toml with real dependencies, `build-rust` Makefile target, structured logging configuration.
- **Phase 3 (Ecosystem and Polish)**: Docker Compose production optimization (resource limits, restart policies), frontend Dockerfile with standalone output, comprehensive Makefile with all targets, CI/CD pipeline configuration.
