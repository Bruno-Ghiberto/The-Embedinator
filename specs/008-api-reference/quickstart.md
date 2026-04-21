# Developer Quickstart — Spec 08 (API Reference)

**Generated**: 2026-03-15

This guide covers how to develop and test the Spec 08 API layer locally.

---

## Prerequisites

- Docker Compose running: `docker compose -f docker-compose.dev.yml up -d`
- Backend services healthy: Qdrant (6333), Ollama (11434), SQLite (`data/embedinator.db`)
- `EMBEDINATOR_FERNET_KEY` set in `.env` (or use dev fallback — see warning below)
- Python 3.14+ and `zsh` available on host

---

## Environment Setup

```bash
# 1. Copy environment template
cp .env.example .env

# 2. Generate a Fernet key for local dev (optional — dev fallback exists)
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Add to .env: EMBEDINATOR_FERNET_KEY=<output>

# 3. Start services
docker compose -f docker-compose.dev.yml up -d

# 4. Verify health
curl http://localhost:8000/api/health | python3 -m json.tool
```

---

## Running Tests

> **CRITICAL**: Never run `pytest` directly inside Claude Code. Always use the external runner.

```bash
# Run all tests (background, token-efficient)
zsh scripts/run-tests-external.sh -n spec08-all tests/

# Run only unit tests
zsh scripts/run-tests-external.sh -n spec08-unit tests/unit/

# Run only integration tests
zsh scripts/run-tests-external.sh -n spec08-integration tests/integration/

# Run a specific test file
zsh scripts/run-tests-external.sh -n spec08-chat tests/unit/test_chat_ndjson.py

# Check status
cat Docs/Tests/spec08-all.status      # RUNNING | PASSED | FAILED | ERROR

# Read summary when done (~20 lines)
cat Docs/Tests/spec08-all.summary
```

**Test output files** (in `Docs/Tests/`):
- `<name>.status` — one line: RUNNING | PASSED | FAILED | ERROR
- `<name>.summary` — ~20 line summary with pass/fail counts
- `<name>.log` — full output (grep only, never cat)

---

## Testing Individual Endpoints

Use `curl` or `httpie` against the running backend (port 8000):

```bash
# Health check
curl http://localhost:8000/api/health

# List collections
curl http://localhost:8000/api/collections

# Create a collection
curl -X POST http://localhost:8000/api/collections \
  -H "Content-Type: application/json" \
  -d '{"name":"test-docs","description":"Quick test"}'

# Upload a document
curl -X POST http://localhost:8000/api/collections/<id>/ingest \
  -F "file=@/path/to/document.pdf"

# Poll ingestion job
curl http://localhost:8000/api/collections/<collection_id>/ingest/<job_id>

# Chat (streaming NDJSON)
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is this document about?","collection_ids":["<id>"]}'
# Each line in the response is a JSON object (type: session, status, chunk, ..., done)

# List providers
curl http://localhost:8000/api/providers

# Save a provider key
curl -X PUT http://localhost:8000/api/providers/openai/key \
  -H "Content-Type: application/json" \
  -d '{"api_key":"sk-test-key"}'

# Get settings
curl http://localhost:8000/api/settings

# Update settings
curl -X PUT http://localhost:8000/api/settings \
  -H "Content-Type: application/json" \
  -d '{"confidence_threshold":75}'
```

---

## File Structure for This Feature

```
specs/008-api-reference/          # This spec
  spec.md                          # Authoritative specification
  plan.md                          # This document
  research.md                      # Phase 0 decisions
  data-model.md                    # Entity definitions
  contracts/api-endpoints.md       # HTTP contract definitions
  quickstart.md                    # This file

backend/api/                       # API routers
  chat.py                          # EXISTS — extend NDJSON events
  collections.py                   # EXISTS — extend
  documents.py                     # EXISTS — rewrite
  ingest.py                        # NEW
  models.py                        # NEW
  providers.py                     # EXISTS — extend
  settings.py                      # NEW
  traces.py                        # EXISTS — extend
  health.py                        # EXISTS — rewrite schema

backend/agent/schemas.py           # EXISTS — extend
backend/main.py                    # EXISTS — register new routers
backend/middleware.py              # EXISTS — extend rate limits
backend/config.py                  # EXISTS — add rate limit fields

tests/unit/                        # Unit tests (no external services)
  test_schemas_api.py              # NEW — Pydantic schema validation
  test_middleware_rate_limit.py    # NEW — rate limiting
  test_chat_ndjson.py              # NEW — NDJSON format correctness
  test_ingest_router.py            # NEW — upload validation
  test_collections_router.py      # NEW — CRUD + cascade
  test_documents_router.py        # NEW — document CRUD
  test_models_router.py           # NEW — model listing
  test_providers_router.py        # NEW — provider key management
  test_settings_router.py         # NEW — settings CRUD
  test_traces_router.py           # NEW — traces + pagination
  test_health_router.py           # NEW — health check

tests/integration/                 # Integration tests (require services)
  test_api_integration.py         # NEW — full request cycle per endpoint group
  test_ndjson_streaming.py        # NEW — end-to-end chat stream
  test_rate_limiting.py           # NEW — burst tests per rate limit category
```

---

## Common Pitfalls

1. **NDJSON vs SSE**: The chat endpoint uses `application/x-ndjson`. Each line is `json.dumps(event) + "\n"`. Never use `data: ...\n\n` (SSE format).

2. **Confidence scores are int**: Always `int(final_state["confidence_score"])`. Never float. Validated with `Field(ge=0, le=100)`.

3. **Provider keys**: Never decrypt and return in any response. Return `has_key: bool` only.

4. **Collection name pattern**: Must match `^[a-z0-9][a-z0-9_-]*$`. Uppercase, spaces, or special chars → 400.

5. **12 file types, not 9**: `.c`, `.cpp`, `.h` are required in the extension allowlist.

6. **Settings are key-value**: Use `db.get_setting(key)` / `db.set_setting(key, value)` / `db.list_settings()`. Each setting is a separate DB row.

7. **Rate limits are per-IP**: Extract client IP from `request.client.host` (or `X-Forwarded-For` if behind proxy).

8. **Duplicate detection**: SHA-256 hash of file content. Return `duplicate` status without re-ingesting (FR-011).

9. **Collection cascade delete**: Cancel active jobs (→ `failed`) → delete documents → delete Qdrant collection — in that order (FR-005).

10. **Settings apply to new sessions only**: Active chat sessions continue with settings at session start (FR-020 clarification).
