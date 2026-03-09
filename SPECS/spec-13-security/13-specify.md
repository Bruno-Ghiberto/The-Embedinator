# Spec 13: Security -- Feature Specification Context

## Feature Description

The Security layer for The Embedinator provides defense-in-depth protections for a self-hosted single-user RAG application. It covers five areas: API key encryption at rest using Fernet symmetric encryption, input sanitization across all user-facing endpoints, file upload validation with type/size/content checks, CORS configuration for frontend-backend communication, and rate limiting to prevent abuse. A first-run secret generation mechanism ensures encryption is available without manual configuration.

## Requirements

### Functional Requirements

1. **API Key Encryption**: All third-party API keys (OpenRouter, OpenAI, Anthropic) must be encrypted before storage in SQLite and decrypted only in-memory at call time. Plaintext keys must never be written to disk.
2. **Key Derivation**: Derive a Fernet-compatible key from the `API_KEY_ENCRYPTION_SECRET` environment variable using SHA-256 hashing and base64 encoding.
3. **Auto-Generated Secrets**: On first run, if `API_KEY_ENCRYPTION_SECRET` is empty in `.env`, generate a random 32-byte secret using `os.urandom(32)`, write it to `.env`, and log a warning.
4. **Key Rotation**: Support re-encrypting stored keys when a user submits a new API key via `PUT /api/providers/{name}/key`.
5. **File Upload Validation**: Validate file extension, file size (max 100 MB), MIME type consistency, filename sanitization, and magic number content sniffing for all uploads.
6. **Input Sanitization**: Sanitize chat messages (truncate to 10,000 chars), collection names (regex validation), Qdrant filter keys (whitelist), SQL parameters (parameterized queries), and SSE output (JSON-encode all event data).
7. **CORS Configuration**: Restrict allowed origins to `http://localhost:3000` and `http://127.0.0.1:3000` by default, overridable via `CORS_ORIGINS` environment variable.
8. **Rate Limiting**: Apply per-endpoint sliding window rate limits using in-memory counters via FastAPI dependency injection.

### Non-Functional Requirements

- Zero external dependencies for rate limiting (in-memory sliding window, no Redis).
- Key encryption/decryption latency must be negligible (sub-millisecond).
- Security measures must not impact development workflow (CORS defaults match dev setup).
- Virus scanning is out of scope for MVP but the ingestion pipeline must support a pre-processing hook where ClamAV integration can be inserted later.

## Key Technical Details

### API Key Encryption (KeyManager)

```python
import os
from cryptography.fernet import Fernet
import hashlib
import base64

def get_fernet_key(secret: str) -> bytes:
    """Derive a Fernet key from the .env secret."""
    # Fernet requires exactly 32 url-safe base64-encoded bytes
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)

class KeyManager:
    def __init__(self, secret: str):
        self.fernet = Fernet(get_fernet_key(secret))

    def encrypt(self, plaintext: str) -> str:
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.fernet.decrypt(ciphertext.encode()).decode()
```

### API Key Lifecycle

- **Storage**: `PUT /api/providers/{name}/key` -> `KeyManager.encrypt()` -> `UPDATE providers SET api_key_encrypted = ?`
- **Usage**: `SELECT api_key_encrypted FROM providers WHERE name = ?` -> `KeyManager.decrypt()` -> instantiate `ChatOpenAI(api_key=plaintext)` -> key garbage collected after use
- **Rotation**: New `PUT` overwrites the encrypted value. Old ciphertext is replaced.

### File Upload Validation Rules

| Check | Rule | Error Code | Error Message |
|-------|------|------------|---------------|
| File extension | Allow: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h` | 400 | "Unsupported file type" |
| File size | Maximum 100 MB | 413 | "File exceeds maximum size" |
| MIME type | Verify MIME matches extension (via `python-magic` or `mimetypes`) | 400 | "File type mismatch" |
| Filename | Strip path traversal (`../`, `..\\`), limit to alphanumeric + `._-` | 400 | "Invalid filename" |
| Content sniffing | Read first 4 bytes for magic number (PDF: `%PDF`, etc.) | 400 | "File content does not match declared type" |

### Input Sanitization Rules

| Input | Sanitization | Reason |
|-------|-------------|--------|
| Chat messages | Truncate to 10,000 chars max | Prevent context window abuse |
| Collection names | Regex: `^[a-z0-9][a-z0-9_-]*$`, max 100 chars | Prevent injection into Qdrant collection names |
| Qdrant payload filters | Whitelist allowed filter keys: `doc_type`, `source_file`, `page`, `chunk_index` | Prevent arbitrary payload query injection |
| SQL parameters | All queries use parameterized statements (`?` placeholders) | Prevent SQL injection |
| SSE output | JSON-encode all event data | Prevent XSS via event stream |

### CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Next.js dev
        "http://127.0.0.1:3000",   # alternate localhost
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

For Docker deployment, `CORS_ORIGINS` env var overrides defaults (comma-separated string).

### Rate Limiting

| Endpoint | Limit | Window | Purpose |
|----------|-------|--------|---------|
| `POST /api/chat` | 30 requests | per minute | Prevent runaway query loops |
| `POST /api/collections/{id}/ingest` | 10 requests | per minute | Prevent ingestion flooding |
| `PUT /api/providers/{name}/key` | 5 requests | per minute | Prevent brute-force key testing |
| All other endpoints | 120 requests | per minute | General protection |

Implementation uses a `RateLimiter` class injected as a FastAPI dependency.

## Dependencies

- **Libraries**: `cryptography>=44.0` (Fernet encryption), `python-magic` or `mimetypes` (MIME validation), `python-multipart>=0.0.20` (file upload parsing)
- **Internal**: `backend/config.py` (Settings class with `api_key_encryption_secret`, `max_upload_size_mb`, `cors_origins`, rate limit settings)
- **Other specs**: Spec 4 (Storage -- SQLite `providers` table), Spec 6 (Provider Hub -- `PUT /api/providers/{name}/key` endpoint), Spec 2 (API Layer -- FastAPI middleware registration)

## Acceptance Criteria

1. API keys stored in SQLite are encrypted; `SELECT api_key_encrypted FROM providers` returns Fernet ciphertext, never plaintext.
2. Decrypted keys are used only in-memory and never logged or written to disk.
3. First run with empty `API_KEY_ENCRYPTION_SECRET` auto-generates a secret, writes it to `.env`, and logs a warning.
4. Uploading a `.exe` file returns HTTP 400 with "Unsupported file type".
5. Uploading a file larger than 100 MB returns HTTP 413 with "File exceeds maximum size".
6. A file named `../../etc/passwd.txt` has its filename sanitized to `etcpasswd.txt` (or similar safe form).
7. A PDF file with the wrong extension (e.g., renamed `.txt`) is rejected by content sniffing.
8. Chat messages longer than 10,000 characters are truncated without error.
9. Collection names like `; DROP TABLE --` are rejected by regex validation.
10. CORS preflight from `http://evil.com` is rejected; from `http://localhost:3000` is accepted.
11. Sending 31 chat requests within 60 seconds returns HTTP 429 on the 31st request.
12. Rate limiter state resets after the sliding window expires.

## Architecture Reference

The security subsystem spans three files in the project structure:

- `backend/providers/key_manager.py` -- Fernet encryption/decryption for API keys
- `backend/middleware.py` -- CORS, rate limiting, trace ID injection
- File upload validation logic lives in the ingestion API endpoint (`backend/api/collections.py` or a dedicated validator module)

Settings fields in `backend/config.py`:

```python
api_key_encryption_secret: str = ""      # auto-generated on first run if empty
max_upload_size_mb: int = 100
cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
rate_limit_chat_per_minute: int = 30
rate_limit_ingest_per_minute: int = 10
rate_limit_default_per_minute: int = 120
```
