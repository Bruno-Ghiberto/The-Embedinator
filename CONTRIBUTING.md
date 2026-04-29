# Contributing to The Embedinator

Thank you for your interest in contributing! This guide will help you get started.

Please read our [Code of Conduct](CODE_OF_CONDUCT.md) before participating.

---

## First-Time Contributors

1. **Fork** the repository on GitHub
2. **Clone** your fork:
   ```bash
   git clone https://github.com/<your-username>/The-Embedinator.git
   cd The-Embedinator
   ```
3. **Create a branch** for your change:
   ```bash
   git checkout -b feat/your-feature-name
   ```
4. **Make your changes** (see development setup below)
5. **Run tests** to verify nothing is broken:
   ```bash
   make test
   ```
6. **Submit a pull request** against the `main` branch

---

## Development Setup

### Docker-Based (Recommended)

The fastest way to get running. Requires only [Docker Desktop](https://www.docker.com/products/docker-desktop/).

```bash
# macOS / Linux
./embedinator.sh

# Windows (PowerShell)
.\embedinator.ps1
```

This single command builds all services, downloads AI models, and opens the application in your browser.

### Native Development

For working on individual components with hot reload.

**Prerequisites**: Python 3.14+, Node.js 20+, Docker, Git

```bash
# Install all dependencies
make setup

# Start infrastructure (Qdrant + Ollama)
make dev-infra

# In separate terminals:
make dev-backend    # Python backend with hot reload on :8000
make dev-frontend   # Next.js frontend with hot reload on :3000
```

### Backend Source Changes Inside the Docker Stack

If you are using the Docker-based stack (`./embedinator.sh` or `make up`) and you
edit any Python source under `backend/`, you **must rebuild the backend image** to
pick up your changes:

```bash
./scripts/dev-rebuild-backend.sh
```

`docker compose restart backend` is **not** sufficient — `Dockerfile.backend` does
not bind-mount `backend/`, so the source code is baked into the image at build
time. Running `restart` recreates the container from the existing (stale) image
and silently keeps serving the old binaries. This cost a meaningful amount of
spec-28 debugging time before it was caught (see BUG-014 in
`docs/E2E/2026-04-24-bug-hunt/bugs-raw/`).

If you want true hot-reload while developing the backend, use the Native
Development path above (`make dev-backend` runs uvicorn outside Docker with
`--reload`).

### Useful Makefile Targets

| Target | Description |
|--------|-------------|
| `make setup` | Install Python, Node, and Rust dependencies |
| `make dev` | Start infrastructure and print dev instructions |
| `make up` | Build and start all 4 Docker services |
| `make down` | Stop all Docker services |
| `make test` | Run backend tests |
| `make test-cov` | Run backend tests with 80% coverage gate |
| `make test-frontend` | Run frontend tests (vitest) |
| `make pull-models` | Download default AI models |
| `make clean` | Remove runtime data |
| `make clean-all` | Full teardown: containers, volumes, build outputs |

---

## Running Tests

```bash
# Backend unit tests (fast, no Docker needed)
pytest tests/unit/ -v

# Backend tests with coverage
make test-cov

# Frontend tests
make test-frontend

# All backend tests (some require Docker services)
make dev-infra   # start Qdrant + Ollama first
make test
```

---

## Code Style

### Python

Linted with [ruff](https://docs.astral.sh/ruff/):

```bash
ruff check backend/ --config ruff.toml
ruff format backend/ --config ruff.toml
```

Pre-commit hooks run ruff automatically on staged files. Install them with:

```bash
pip install pre-commit
pre-commit install
```

### TypeScript

```bash
cd frontend && npm run lint
```

### Rust (Ingestion Worker)

```bash
cd ingestion-worker && cargo fmt
```

---

## Commit Conventions

We use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix | Use for |
|--------|---------|
| `feat:` | New features |
| `fix:` | Bug fixes |
| `docs:` | Documentation changes |
| `test:` | Adding or updating tests |
| `chore:` | Maintenance, dependencies |
| `refactor:` | Code restructuring (no behavior change) |
| `ci:` | CI/CD configuration |

Example:

```
feat: add streaming confidence indicator to chat
fix: handle empty collection in hybrid search
docs: update API reference with new endpoints
```

---

## Architecture Decision Records

Major design decisions are documented as ADRs. Read these before proposing changes to core architecture:

- [ADR-001: SQLite over PostgreSQL](docs/adr/001-sqlite-over-postgres.md)
- [ADR-002: Three-Layer Agent Architecture](docs/adr/002-three-layer-agent.md)
- [ADR-003: Rust Ingestion Worker](docs/adr/003-rust-ingestion-worker.md)
- [ADR-004: Cross-Encoder Reranking](docs/adr/004-cross-encoder-reranking.md)
- [ADR-005: Parent/Child Chunking](docs/adr/005-parent-child-chunking.md)
- [ADR-006: Observability from Day One](docs/adr/006-observability-from-day-one.md)
- [ADR-007: SSE Streaming](docs/adr/007-sse-streaming.md)
- [ADR-008: Multi-Provider Architecture](docs/adr/008-multi-provider-architecture.md)

---

## Pull Request Guidelines

- Keep PRs focused on a single concern
- Include tests for new functionality
- Update documentation if you change public APIs
- Ensure `make test` and `make test-frontend` pass before submitting
- Reference related issues in the PR description

---

## Getting Help

- Open a [GitHub Issue](https://github.com/Bruno-Ghiberto/The-Embedinator/issues) for bugs or feature requests
- Check `docs/architecture-design.md` for system design context
- Check `docs/api-reference.md` for endpoint documentation
