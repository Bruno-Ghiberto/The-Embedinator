# Contributing to The Embedinator

---

## Development Environment Setup

### Prerequisites

- Python 3.14+
- Node.js 20+ (for frontend)
- Docker and Docker Compose
- Git

### Backend Setup

```bash
# Clone the repository
git clone <repo-url> the-embedinator
cd the-embedinator

# Create Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # pytest, etc.

# Copy environment config
cp .env.example .env

# Start infrastructure services
docker compose up -d qdrant ollama

# Run backend locally (for development)
uvicorn backend.main:app --reload --port 8000
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev  # Starts Next.js dev server on :3000
```

### Full Stack via Docker

```bash
docker compose up --build -d
```

---

## Project Structure

```
the-embedinator/
  backend/
    api/          # FastAPI route handlers
    agent/        # LangGraph agent modules (retrieval, citations, confidence)
    ingestion/    # Document parsing and embedding pipeline
    providers/    # LLM provider adapters (Ollama, OpenRouter, etc.)
    storage/      # Qdrant and SQLite clients
    config.py     # Centralized settings (Pydantic Settings)
    errors.py     # Error hierarchy
    main.py       # App factory and lifespan
    middleware.py  # Rate limiting, logging, trace ID
  frontend/
    app/          # Next.js App Router pages
    components/   # React components
    hooks/        # Custom hooks (useStreamChat, etc.)
    lib/          # API client and shared types
  tests/
    unit/         # Fast tests, mocked dependencies
    integration/  # Tests requiring Docker services
    e2e/          # Playwright browser tests
  claudedocs/     # Technical blueprint documents
  data/           # Runtime data (gitignored)
```

---

## Running Tests

```bash
# Unit tests (fast, no external services needed)
pytest tests/unit/ -v

# Unit tests with coverage
pytest tests/unit/ --cov=backend --cov-report=term-missing

# Integration tests (requires Docker services running)
docker compose up -d qdrant ollama
pytest tests/integration/ -v

# All tests
pytest -v

# Frontend tests
cd frontend && npx vitest run
```

---

## Code Style

### Python
- Follow existing code patterns in the codebase
- Use type hints for function signatures
- Use `async/await` for I/O-bound operations
- Pydantic models for request/response schemas
- Parameterized SQL queries (never string interpolation)

### TypeScript
- Strict TypeScript (`strict: true` in tsconfig)
- Functional components with hooks
- SWR for data fetching
- Tailwind CSS for styling

### Naming Conventions
- Python: `snake_case` for functions/variables, `PascalCase` for classes
- TypeScript: `camelCase` for functions/variables, `PascalCase` for components/types
- Files: `snake_case.py` for Python, `PascalCase.tsx` for React components
- Collection names: `lowercase-with-hyphens`

---

## Branch Naming

```
main              # Production-ready code
001-vision-arch   # Feature: Vision & Architecture (Phase 1)
002-*             # Feature: Phase 2 work
fix/<description> # Bug fixes
```

---

## Commit Messages

Follow conventional commit style:

```
feat: add streaming chat endpoint
fix: handle empty collection in search
refactor: extract retrieval module from chat.py
test: add integration tests for US1 flow
chore: update Docker health checks
docs: add API reference document
```

---

## Adding a New Provider

1. Create `backend/providers/<name>.py` implementing `LLMProvider` ABC from `backend/providers/base.py`
2. Register in `backend/providers/registry.py`
3. Add to `providers` table valid names
4. Add unit tests in `tests/unit/providers/`
5. Update frontend `ProviderHub` component if needed

---

## Adding a New API Endpoint

1. Create or update route handler in `backend/api/`
2. Define Pydantic request/response models
3. Register router in `backend/main.py` `create_app()`
4. Add error handling using exceptions from `backend/errors.py`
5. Add unit tests and integration tests
6. Update `claudedocs/api-reference.md`

---

## Key Technical Decisions

All major architecture decisions are documented as ADRs in `claudedocs/adr/`. Read these before proposing changes to core architecture:

- ADR-001: SQLite over PostgreSQL
- ADR-002: Three-layer LangGraph agent
- ADR-003: Rust ingestion worker
- ADR-004: Cross-encoder reranking
- ADR-005: Parent/child chunking with breadcrumbs
- ADR-006: Observability from day one
- ADR-007: SSE for streaming responses
- ADR-008: Multi-provider LLM architecture

---

*For full architecture details, see `claudedocs/architecture-design.md`. For the product requirements, see `claudedocs/prd.md`.*
