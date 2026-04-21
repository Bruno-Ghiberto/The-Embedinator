# Contract: Environment Configuration

**Spec**: 017-infra-setup
**FR**: FR-009, FR-010
**SC**: SC-005

---

## Overview

The `.env.example` file is the single-source documentation for all environment variables. Every field in `backend/config.py`'s `Settings` class MUST have a corresponding entry. The format is:

```
# Description. Expected: type (range). Default: value.
ENV_VAR_NAME=default_value
```

## Completeness Rule (SC-005)

Count of variables in `.env.example` MUST equal count of fields in `Settings`. Verified by A5 during validation wave.

## Critical Variables

| Env Var | Field | Required | Notes |
|---------|-------|----------|-------|
| `EMBEDINATOR_FERNET_KEY` | `api_key_encryption_secret` | On startup if provider keys used | Fernet key; 32-byte URL-safe base64; see Constitution V |
| `QDRANT_HOST` | `qdrant_host` | In Docker only | Set to `qdrant` (Docker service name) in compose |
| `OLLAMA_BASE_URL` | `ollama_base_url` | In Docker only | Set to `http://ollama:11434` in compose |
| `SQLITE_PATH` | `sqlite_path` | In Docker only | Set to `/data/embedinator.db` in compose |

## Docker Override Pattern

In `docker-compose.yml`, the backend service MUST override:
```yaml
environment:
  QDRANT_HOST: qdrant
  OLLAMA_BASE_URL: http://ollama:11434
  SQLITE_PATH: /data/embedinator.db
  UPLOAD_DIR: /data/uploads
```

These overrides replace the `localhost` defaults that work for native dev mode.
