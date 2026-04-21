# tests/

Test suite for The Embedinator backend. **1,487 tests** with **87% code
coverage**.

## Organization

```
tests/
|-- unit/              # Fast, isolated tests (~60 files)
|   |-- api/           # API endpoint security tests
|   +-- retrieval/     # Retrieval-specific tests
|-- integration/       # Tests requiring app context (~20 files)
|-- e2e/               # End-to-end API tests (4 files)
|-- regression/        # Regression suite for known issues
|-- fixtures/          # Sample files (PDF, Markdown, text)
|-- conftest.py        # Shared fixtures (4 project-wide fixtures)
+-- mocks.py           # Mock ResearchGraph + simple chat graph
```

### Unit Tests (`unit/`)

Fast tests that mock external dependencies. Cover individual functions,
classes, and modules. Key areas: config validation, schema contracts,
node functions, edge routing, confidence scoring, provider adapters,
middleware, and router handlers.

### Integration Tests (`integration/`)

Tests that exercise multiple components together. Require the app factory
or compiled graphs. Key areas: full graph compilation, NDJSON streaming,
rate limiting, circuit breaker behavior, concurrent reads, and storage
integration.

### E2E Tests (`e2e/`)

In-process ASGI tests using `httpx.AsyncClient` with `ASGITransport`.
Test complete request-response cycles through the full stack:

- `test_chat_e2e.py` -- Chat streaming flow
- `test_ingest_e2e.py` -- File upload and ingestion lifecycle
- `test_collection_e2e.py` -- Collection CRUD operations
- `test_observability_e2e.py` -- Traces and metrics endpoints

### Regression Tests (`regression/`)

Suite that guards against previously fixed bugs.

## Running Tests

```bash
# All tests (no coverage gate)
make test

# All tests with 80% coverage threshold
make test-cov

# Specific file or directory
pytest tests/unit/test_config.py
pytest tests/integration/ -v

# With markers
pytest -m "e2e" -v
pytest -m "not require_docker"
```

## Test Markers

| Marker           | Description                                      |
|------------------|--------------------------------------------------|
| `e2e`            | Backend E2E tests (in-process ASGI via httpx)    |
| `require_docker` | Tests requiring Qdrant on localhost:6333         |

## External Test Runner

For CI or automated workflows, see
[`../scripts/README.md`](../scripts/README.md) for the external test runner
that writes results to `Docs/Tests/` instead of stdout.

## Fixtures

Sample files in `fixtures/`: `sample.pdf`, `sample.md`, `sample.txt` --
used by ingestion pipeline, chunking, and E2E tests.

## Known Pre-existing Failures

There are 39 pre-existing test failures that are documented and tracked.
These are not regressions. Gate checks compare against this baseline.
