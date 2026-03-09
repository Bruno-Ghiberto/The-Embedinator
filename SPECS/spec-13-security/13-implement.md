# Spec 13: Security -- Implementation Context

## Implementation Scope

### Files to Create

- `backend/providers/key_manager.py` -- Fernet encryption/decryption class and auto-secret generation
- `backend/validators.py` -- FileValidator class and input sanitization utilities

### Files to Modify

- `backend/middleware.py` -- Add CORS middleware setup, RateLimiter class
- `backend/main.py` -- Wire auto-secret generation in lifespan, register middleware
- `backend/config.py` -- Ensure security-related Settings fields exist
- `backend/api/collections.py` -- Integrate FileValidator into ingest endpoint
- `backend/api/chat.py` -- Integrate message sanitization and rate limiting
- `backend/api/providers.py` -- Use KeyManager for encrypt/decrypt on key endpoints

## Code Specifications

### backend/providers/key_manager.py

```python
import os
import hashlib
import base64
import structlog
from cryptography.fernet import Fernet

logger = structlog.get_logger(__name__)


def get_fernet_key(secret: str) -> bytes:
    """Derive a Fernet key from the .env secret.

    Fernet requires exactly 32 url-safe base64-encoded bytes.
    """
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)


class KeyManager:
    """Encrypts and decrypts API keys using Fernet symmetric encryption."""

    def __init__(self, secret: str):
        self.fernet = Fernet(get_fernet_key(secret))

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext API key. Returns base64-encoded ciphertext."""
        return self.fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a stored API key. Returns plaintext string."""
        return self.fernet.decrypt(ciphertext.encode()).decode()


def generate_secret_if_missing(env_path: str = ".env") -> str:
    """Generate API_KEY_ENCRYPTION_SECRET if not set. Writes to .env file.

    Returns the secret value (existing or newly generated).
    """
    current = os.environ.get("API_KEY_ENCRYPTION_SECRET", "")
    if current:
        return current

    secret = os.urandom(32).hex()
    logger.warning(
        "API_KEY_ENCRYPTION_SECRET was empty. Generated a random secret.",
        env_path=env_path,
    )

    # Append to .env file
    with open(env_path, "a") as f:
        f.write(f"\nAPI_KEY_ENCRYPTION_SECRET={secret}\n")

    os.environ["API_KEY_ENCRYPTION_SECRET"] = secret
    return secret
```

### backend/validators.py

```python
import re
import mimetypes
from pathlib import Path
from fastapi import HTTPException, UploadFile
import structlog

logger = structlog.get_logger(__name__)

ALLOWED_EXTENSIONS = {
    ".pdf", ".md", ".txt", ".py", ".js", ".ts",
    ".rs", ".go", ".java", ".c", ".cpp", ".h",
}

MAGIC_NUMBERS = {
    ".pdf": b"%PDF",
}

COLLECTION_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
MAX_COLLECTION_NAME_LENGTH = 100
MAX_CHAT_MESSAGE_LENGTH = 10_000

ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}


class FileValidator:
    """Validates uploaded files for extension, size, MIME type, filename safety,
    and magic number content sniffing."""

    def __init__(self, max_size_mb: int = 100):
        self.max_size_bytes = max_size_mb * 1024 * 1024

    async def validate(self, file: UploadFile) -> str:
        """Validate the uploaded file. Returns the sanitized filename.

        Raises HTTPException on validation failure.
        """
        filename = self._sanitize_filename(file.filename or "unknown")
        self._check_extension(filename)
        await self._check_size(file)
        self._check_mime_type(filename, file.content_type)
        await self._check_magic_number(file, filename)
        return filename

    def _sanitize_filename(self, filename: str) -> str:
        """Strip path traversal and dangerous characters."""
        # Remove path components
        name = Path(filename).name
        # Remove path traversal sequences
        name = name.replace("../", "").replace("..\\", "")
        # Keep only safe characters
        name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
        if not name:
            raise HTTPException(status_code=400, detail="Invalid filename")
        return name

    def _check_extension(self, filename: str) -> None:
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file type")

    async def _check_size(self, file: UploadFile) -> None:
        # Read to determine size, then seek back
        content = await file.read()
        await file.seek(0)
        if len(content) > self.max_size_bytes:
            raise HTTPException(status_code=413, detail="File exceeds maximum size")

    def _check_mime_type(self, filename: str, content_type: str | None) -> None:
        if not content_type:
            return
        guessed_type, _ = mimetypes.guess_type(filename)
        if guessed_type and content_type != guessed_type:
            logger.warning(
                "MIME type mismatch",
                filename=filename,
                declared=content_type,
                expected=guessed_type,
            )
            raise HTTPException(status_code=400, detail="File type mismatch")

    async def _check_magic_number(self, file: UploadFile, filename: str) -> None:
        ext = Path(filename).suffix.lower()
        expected_magic = MAGIC_NUMBERS.get(ext)
        if not expected_magic:
            return
        header = await file.read(len(expected_magic))
        await file.seek(0)
        if header != expected_magic:
            raise HTTPException(
                status_code=400,
                detail="File content does not match declared type",
            )

    async def scan_for_virus(self, file: UploadFile) -> None:
        """Hook for future ClamAV integration. No-op in MVP."""
        pass


def sanitize_chat_message(message: str) -> str:
    """Truncate chat message to maximum allowed length."""
    return message[:MAX_CHAT_MESSAGE_LENGTH]


def validate_collection_name(name: str) -> str:
    """Validate collection name against allowed pattern.

    Raises HTTPException if invalid.
    """
    if len(name) > MAX_COLLECTION_NAME_LENGTH:
        raise HTTPException(
            status_code=400, detail="Collection name too long (max 100 chars)"
        )
    if not COLLECTION_NAME_PATTERN.match(name):
        raise HTTPException(
            status_code=400,
            detail="Collection name must start with a letter or digit and contain only lowercase letters, digits, hyphens, and underscores",
        )
    return name


def validate_filter_keys(filters: dict) -> dict:
    """Whitelist Qdrant payload filter keys.

    Raises HTTPException if disallowed keys are present.
    """
    disallowed = set(filters.keys()) - ALLOWED_FILTER_KEYS
    if disallowed:
        raise HTTPException(
            status_code=400,
            detail=f"Disallowed filter keys: {disallowed}",
        )
    return filters
```

### RateLimiter in backend/middleware.py

```python
import time
from collections import defaultdict
from fastapi import HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

class RateLimiter:
    """In-memory sliding window rate limiter for single-user deployment."""

    def __init__(self):
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, limit: int, window: int = 60):
        """Return a FastAPI dependency that enforces rate limits.

        Args:
            limit: Maximum requests per window.
            window: Time window in seconds.
        """
        async def dependency(request: Request):
            key = f"{request.url.path}"
            now = time.time()
            cutoff = now - window

            # Remove expired entries
            self._requests[key] = [
                t for t in self._requests[key] if t > cutoff
            ]

            if len(self._requests[key]) >= limit:
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Max {limit} requests per {window}s.",
                )

            self._requests[key].append(now)

        return dependency


def setup_cors(app, origins: list[str]):
    """Configure CORS middleware from settings."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
```

### CORS Origins Parsing in main.py

```python
# In the app factory or lifespan
origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
setup_cors(app, origins)
```

## Configuration

### Environment Variables (from Settings class in config.py)

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY_ENCRYPTION_SECRET` | `""` (auto-generated) | Secret for Fernet key derivation |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum file upload size in megabytes |
| `CORS_ORIGINS` | `http://localhost:3000,http://127.0.0.1:3000` | Comma-separated allowed CORS origins |
| `RATE_LIMIT_CHAT_PER_MINUTE` | `30` | Rate limit for chat endpoint |
| `RATE_LIMIT_INGEST_PER_MINUTE` | `10` | Rate limit for ingestion endpoint |
| `RATE_LIMIT_DEFAULT_PER_MINUTE` | `120` | Rate limit for all other endpoints |

## Error Handling

- **Fernet decryption failure**: If the `API_KEY_ENCRYPTION_SECRET` changes after keys were stored, `Fernet.decrypt()` raises `InvalidToken`. Catch this and return a user-friendly error indicating the stored key is invalid and needs to be re-entered.
- **File validation failures**: Return specific HTTP error codes (400, 413) with descriptive messages. Log the failure with the trace ID.
- **Rate limit exceeded**: Return HTTP 429 with a message indicating the limit and window. Include `Retry-After` header if practical.
- **Missing secret on startup**: Log a warning (not an error) since auto-generation handles it. Only fail if `.env` is not writable.

## Testing Requirements

### Unit Tests (in `tests/unit/providers/test_key_manager.py`)

1. `test_encrypt_decrypt_roundtrip` -- encrypt a known string, decrypt it, verify match.
2. `test_different_secrets_produce_different_ciphertext` -- same plaintext with different secrets produces different output.
3. `test_decrypt_with_wrong_secret_fails` -- encrypting with one secret and decrypting with another raises `InvalidToken`.
4. `test_generate_secret_if_missing` -- when env var is empty, a secret is generated and written to file.
5. `test_generate_secret_preserves_existing` -- when env var is set, no new secret is generated.

### Unit Tests (in `tests/unit/test_validators.py`)

1. `test_valid_file_extensions` -- all allowed extensions pass validation.
2. `test_invalid_file_extension` -- `.exe`, `.bat`, `.sh` are rejected with 400.
3. `test_file_size_limit` -- file over 100 MB returns 413.
4. `test_filename_sanitization` -- path traversal sequences are stripped.
5. `test_magic_number_mismatch` -- PDF extension with non-PDF content is rejected.
6. `test_collection_name_valid` -- valid names pass.
7. `test_collection_name_injection` -- SQL injection attempts are rejected.
8. `test_chat_message_truncation` -- messages over 10,000 chars are truncated.
9. `test_filter_key_whitelist` -- disallowed keys raise 400.

### Unit Tests (in `tests/unit/test_middleware.py`)

1. `test_rate_limiter_allows_within_limit` -- requests within limit pass.
2. `test_rate_limiter_blocks_over_limit` -- request exceeding limit returns 429.
3. `test_rate_limiter_window_expiry` -- after window passes, requests are allowed again.

## Done Criteria

- [ ] `KeyManager` encrypts and decrypts API keys correctly with roundtrip verification
- [ ] Auto-secret generation works on first run with empty `API_KEY_ENCRYPTION_SECRET`
- [ ] File upload validation rejects invalid extensions, oversized files, MIME mismatches, path traversal filenames, and magic number mismatches
- [ ] Virus scanning hook exists as a no-op method on `FileValidator`
- [ ] Chat messages are truncated to 10,000 characters
- [ ] Collection names are validated against the regex pattern
- [ ] Qdrant filter keys are whitelisted
- [ ] All SQL queries use parameterized statements (verify by code review)
- [ ] SSE event data is JSON-encoded
- [ ] CORS middleware is configured with defaults and supports `CORS_ORIGINS` override
- [ ] Rate limiter enforces per-endpoint limits and returns 429 when exceeded
- [ ] All security unit tests pass
