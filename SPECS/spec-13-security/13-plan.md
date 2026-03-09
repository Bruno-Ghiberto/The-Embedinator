# Spec 13: Security -- Implementation Plan Context

## Component Overview

The Security layer provides defense-in-depth protections for The Embedinator, a self-hosted single-user RAG application. It encompasses API key encryption at rest (Fernet), input sanitization across all user-facing endpoints, file upload validation, CORS middleware, and rate limiting. These protections are designed for a single-user deployment without requiring external infrastructure (no Redis, no separate auth service).

## Technical Approach

### API Key Encryption

- Use the `cryptography` library's Fernet symmetric encryption.
- Derive the Fernet key from the `API_KEY_ENCRYPTION_SECRET` env var via SHA-256 hashing + base64 encoding.
- Implement as a `KeyManager` class in `backend/providers/key_manager.py`.
- On first run, detect empty secret, generate 32 random bytes via `os.urandom(32)`, write hex-encoded value to `.env`, and log a warning via `structlog`.

### Input Sanitization

- Chat message truncation: apply in the chat endpoint handler before passing to the agent.
- Collection name validation: use a compiled regex pattern as a Pydantic field validator or a standalone validator function.
- Qdrant filter key whitelisting: validate in the searcher or tool layer before constructing Qdrant filter payloads.
- SQL injection prevention: enforce parameterized queries throughout `sqlite_db.py` (already a design constraint).
- SSE output encoding: JSON-encode all SSE event `data` fields in the streaming response.

### File Upload Validation

- Implement as a reusable validator function or class (e.g., `FileValidator`) that can be called from the ingestion endpoint.
- Check order: extension -> size -> MIME type -> filename sanitization -> magic number sniffing.
- Use `mimetypes` stdlib for MIME matching (fallback to `python-magic` if needed).
- Read first 4-8 bytes for magic number checks. Known signatures: `%PDF` for PDF.
- Include a no-op hook point for future virus scanning (ClamAV integration).

### CORS Configuration

- Use FastAPI's `CORSMiddleware` with defaults for `localhost:3000`.
- Parse `CORS_ORIGINS` env var (comma-separated) to override at runtime.
- Configure in the middleware setup within `backend/middleware.py` or `backend/main.py`.

### Rate Limiting

- Implement a `RateLimiter` class using an in-memory sliding window counter (dictionary of timestamp lists per client key).
- Inject as a FastAPI `Depends()` dependency on protected routes.
- Key by endpoint path (not by IP, since single-user deployment).
- Configurable limits via Settings class fields.

## File Structure

```
backend/
  providers/
    key_manager.py          # KeyManager class, get_fernet_key(), auto-secret generation
  middleware.py             # CORSMiddleware setup, RateLimiter class, TraceMiddleware
  api/
    collections.py          # File upload validation integrated into ingest endpoint
  config.py                 # Settings fields: api_key_encryption_secret, cors_origins, rate limits
  validators.py             # FileValidator class, input sanitization utilities (NEW FILE)
```

## Implementation Steps

1. **Create `backend/providers/key_manager.py`**: Implement `get_fernet_key()` and `KeyManager` class with `encrypt()` and `decrypt()` methods.
2. **Add auto-secret generation**: In the application startup (lifespan handler in `main.py`), check if `api_key_encryption_secret` is empty. If so, generate a random secret, write it to `.env`, update the Settings instance, and log a warning.
3. **Create `backend/validators.py`**: Implement `FileValidator` with methods for extension check, size check, MIME validation, filename sanitization, and magic number sniffing. Include a no-op `scan_for_virus()` hook.
4. **Add input sanitization utilities**: In `validators.py`, add `sanitize_chat_message()`, `validate_collection_name()`, and `validate_filter_keys()` functions.
5. **Implement `RateLimiter` class**: In `backend/middleware.py`, create a sliding window rate limiter class with configurable limits per endpoint pattern. Expose it as a FastAPI dependency.
6. **Configure CORS middleware**: In `backend/middleware.py` or `backend/main.py`, parse `CORS_ORIGINS` from settings and apply `CORSMiddleware`.
7. **Integrate validators into endpoints**: Wire `FileValidator` into the ingestion endpoint. Add `sanitize_chat_message()` to the chat endpoint. Add `validate_collection_name()` to collection creation.
8. **Wire rate limiter**: Add `Depends(RateLimiter(...))` to chat, ingest, and provider key endpoints with their respective limits.

## Integration Points

- **Provider Hub (Spec 6)**: The `PUT /api/providers/{name}/key` endpoint calls `KeyManager.encrypt()` before storing and `KeyManager.decrypt()` at LLM call time.
- **Storage Layer (Spec 4)**: The `providers` table stores `api_key_encrypted` column. All SQL queries use parameterized statements.
- **Ingestion Pipeline (Spec 5)**: The ingest endpoint calls `FileValidator` before accepting uploads.
- **Chat API (Spec 2)**: The chat endpoint applies message truncation and rate limiting.
- **Observability (Spec 15)**: Rate limit rejections and validation failures are logged with trace IDs.

## Key Code Patterns

### KeyManager Usage in Provider Flow

```python
# In PUT /api/providers/{name}/key
key_manager = KeyManager(settings.api_key_encryption_secret)
encrypted = key_manager.encrypt(request.api_key)
await db.update_provider_key(name, encrypted)

# At LLM call time
encrypted = await db.get_provider_key(provider_name)
key_manager = KeyManager(settings.api_key_encryption_secret)
plaintext = key_manager.decrypt(encrypted)
llm = ChatOpenAI(api_key=plaintext, ...)
# plaintext is garbage collected after use
```

### Rate Limiter as FastAPI Dependency

```python
from fastapi import Depends

rate_limiter = RateLimiter()

@router.post("/api/chat")
async def chat(
    request: ChatRequest,
    _rate_check: None = Depends(rate_limiter.check(limit=30, window=60))
):
    ...
```

### File Validation in Ingest Endpoint

```python
validator = FileValidator(max_size_mb=settings.max_upload_size_mb)
validator.validate(uploaded_file)  # raises HTTPException on failure
```

## Phase Assignment

- **Phase 1 (MVP)**: API key encryption (KeyManager), CORS configuration, basic input sanitization (collection names, SQL parameterization), file upload validation (extension + size checks), basic rate limiting.
- **Phase 2 (Performance and Resilience)**: Full file validation (MIME type, magic number sniffing), structured logging of security events, rate limiter refinements.
- **Phase 3 (Ecosystem and Polish)**: Virus scanning hook (ClamAV), advanced rate limiting (per-IP if multi-user considered), security audit and hardening.
