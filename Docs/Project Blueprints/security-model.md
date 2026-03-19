# The Embedinator — Security Model

**Version**: 1.0
**Date**: 2026-03-10
**Source**: `claudedocs/architecture-design.md` Section 16 (Security Specification)

---

## Threat Model

### System Context

The Embedinator is a **self-hosted, single-user** application running on a developer's local machine or private server. It is not designed for multi-tenant or internet-facing deployment without an additional authentication/authorization layer.

### Trust Boundaries

```
+-------------------------------------------------------------------+
| User's Machine / Private Network                                   |
|                                                                    |
|  Browser ←→ Next.js :3000 ←→ FastAPI :8000 ←→ Qdrant :6333       |
|                                                    ↕                |
|                                              Ollama :11434          |
|                                              SQLite (local file)   |
|                                                                    |
+----------------------------+--------------------------------------+
                             |
                    Trust Boundary (opt-in only)
                             |
                    Cloud Providers (OpenRouter, OpenAI, Anthropic)
```

**Inside trust boundary** (default): All services run on localhost. No data leaves the machine.
**Crosses trust boundary** (opt-in): When cloud LLM providers are configured, queries and document chunks are sent to external APIs.

### Threat Categories

| Threat | Risk Level | Mitigation |
|---|---|---|
| API key exposure in database | Medium | Fernet encryption at rest (see below) |
| API key in logs | Medium | structlog processors strip sensitive fields |
| Malicious file upload | Medium | Extension allowlist, size limits, MIME validation, content sniffing |
| SQL injection | Low | All queries use parameterized statements (`?` placeholders) |
| XSS via SSE stream | Low | All event data JSON-encoded before sending |
| Path traversal via filename | Low | Filename sanitization (strip `../`, limit to `[a-zA-Z0-9._-]`) |
| Qdrant payload injection | Low | Whitelist allowed filter keys (`doc_type`, `source_file`, `page`, `chunk_index`) |
| Context window abuse | Low | Chat messages truncated to 10,000 chars max |
| Brute-force API key testing | Low | Rate limiting on `PUT /api/providers/{name}/key` (5/min) |
| Denial of service | Low | Rate limiting on all endpoints; single-user system |

---

## API Key Encryption

### Lifecycle

```
User enters key in UI
  → Frontend sends to PUT /api/providers/{name}/key
    → Backend encrypts with Fernet
      → Encrypted ciphertext stored in SQLite providers.api_key_encrypted
        → On LLM call: decrypt in-memory, use, garbage collect
```

### Implementation

**Encryption scheme**: Fernet (symmetric, from Python `cryptography` library)
**Key derivation**: `SHA256(secret)` → base64-encode → 32-byte Fernet key
**Secret source**: `EMBEDINATOR_FERNET_KEY` environment variable in `.env`

```python
def get_fernet_key(secret: str) -> bytes:
    key_bytes = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(key_bytes)
```

**First-run behavior**: If `EMBEDINATOR_FERNET_KEY` is not set, a deterministic dev fallback key is generated from `hashlib.sha256(b"embedinator-dev-key")`. A warning is logged. For production, users must set their own key.

### Key Rotation

1. User enters new API key via Provider Hub UI
2. Frontend calls `PUT /api/providers/{name}/key` with new key
3. Backend encrypts new key, overwrites `api_key_encrypted` in SQLite
4. Old ciphertext is replaced — no versioning

**Fernet key rotation** (changing `EMBEDINATOR_FERNET_KEY`): Not supported in MVP. Would require re-encrypting all stored API keys.

---

## File Upload Validation

| Check | Rule | Error |
|---|---|---|
| File extension | Allowlist: `.pdf`, `.md`, `.txt`, `.py`, `.js`, `.ts`, `.rs`, `.go`, `.java`, `.c`, `.cpp`, `.h` | 400: "Unsupported file type" |
| File size | Maximum 100 MB | 413: "File exceeds maximum size" |
| MIME type | Verify MIME matches extension | 400: "File type mismatch" |
| Filename sanitization | Strip path traversal (`../`, `..\\`), limit to `[a-zA-Z0-9._-]` | 400: "Invalid filename" |
| Content sniffing | Read first 4 bytes for magic number (PDF: `%PDF`) | 400: "File content does not match type" |

**Virus scanning**: Not included in MVP. For production, ClamAV can be integrated via the ingestion pipeline pre-processing hook.

---

## Input Sanitization

| Input | Sanitization | Reason |
|---|---|---|
| Chat messages | Truncate to 10,000 chars max | Prevent context window abuse |
| Collection names | Regex: `^[a-z0-9][a-z0-9_-]*$`, max 100 chars | Prevent injection into Qdrant collection names |
| Qdrant payload filters | Whitelist: `doc_type`, `source_file`, `page`, `chunk_index` | Prevent arbitrary payload query injection |
| SQL parameters | Parameterized statements (`?` placeholders) | Prevent SQL injection |
| SSE output | JSON-encode all event data | Prevent XSS via event stream |

---

## CORS Configuration

```python
CORSMiddleware(
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

Configurable via `CORS_ORIGINS` environment variable for custom deployments.

---

## Rate Limiting

In-memory sliding window counter per client IP:

| Endpoint | Limit | Window | Purpose |
|---|---|---|---|
| `POST /api/chat` | 30 requests | per minute | Prevent runaway query loops |
| `POST /api/collections/{id}/ingest` | 10 requests | per minute | Prevent ingestion flooding |
| `PUT /api/providers/{name}/key` | 5 requests | per minute | Prevent brute-force key testing |
| All other endpoints | 120 requests | per minute | General protection |

When rate limited, response includes `Retry-After` header.

---

## Logging Security

- **structlog processors** strip fields matching: `api_key`, `password`, `secret`, `token`, `authorization`
- API keys are **never** returned in any GET response — `has_key: bool` is used instead
- Trace IDs are logged for all requests — enables correlation without exposing payload data
- Debug mode (`DEBUG=true`) exposes additional internal details in error responses — **must be disabled in production**

---

## Network Security

### Default (Local Only)
- All services bind to `localhost` or Docker internal network
- No ports exposed to the public internet
- Zero outbound API calls when using Ollama

### Production Deployment
- TLS should be handled by a reverse proxy (Caddy, nginx, Traefik)
- Backend runs plain HTTP behind the proxy
- Do NOT expose port 8000 directly in production
- See `docker-compose.prod.yml` for reverse proxy stubs

---

## Security Checklist for Deployment

- [ ] Set `EMBEDINATOR_FERNET_KEY` to a random 32+ character string in `.env`
- [ ] Set `DEBUG=false` in production
- [ ] Configure `CORS_ORIGINS` to match your domain
- [ ] Place a reverse proxy with TLS in front of the backend
- [ ] Do not expose ports 6333 (Qdrant) or 11434 (Ollama) publicly
- [ ] Review rate limit settings for your expected load
- [ ] Back up `.env` file securely (contains encryption key)

---

*Extracted from `claudedocs/architecture-design.md` Section 16 (Security Specification).*
