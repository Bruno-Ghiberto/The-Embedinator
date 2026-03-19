# A6: Models + Providers + Settings

**Agent type:** `backend-architect`
**Model:** Sonnet 4.6
**Tasks:** T018, T019, T020, T021, T026, T027
**Wave:** 3 (parallel with A5)

---

## Assigned Tasks

### T018: Write tests/unit/test_providers_router.py
### T019: Write tests/unit/test_models_router.py
### T020: Extend backend/api/providers.py
### T021: Create backend/api/models.py
### T026: Write tests/unit/test_settings_router.py
### T027: Create backend/api/settings.py

---

## File Targets

| File | Action |
|------|--------|
| `backend/api/providers.py` | Rewrite |
| `backend/api/models.py` | Create new |
| `backend/api/settings.py` | Create new |
| `tests/unit/test_providers_router.py` | Create new |
| `tests/unit/test_models_router.py` | Create new |
| `tests/unit/test_settings_router.py` | Create new |

---

## Implementation: backend/api/providers.py (Rewrite)

Read the current file first. It has:
- `_get_fernet()`, `encrypt_api_key()`, `decrypt_api_key()` -- REMOVE (use KeyManager)
- `list_providers()` -- REWRITE (add has_key, remove type/status)
- `activate_provider()` -- REMOVE
- `configure_provider()` -- REMOVE
- Add: `PUT /api/providers/{name}/key`, `DELETE /api/providers/{name}/key`

**Rewritten file:**

```python
"""Provider management endpoints -- key storage and listing."""

from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import ProviderDetailResponse, ProviderKeyRequest

router = APIRouter()


@router.get("/api/providers")
async def list_providers(request: Request) -> dict:
    """List all configured providers with has_key indicator."""
    db = request.app.state.db
    providers = await db.list_providers()

    result = []
    for p in providers:
        result.append(ProviderDetailResponse(
            name=p["name"],
            is_active=bool(p["is_active"]),
            has_key=p.get("api_key_encrypted") is not None and p["api_key_encrypted"] != "",
            base_url=p.get("base_url"),
            model_count=0,  # populated lazily or by models endpoint
        ))

    # Always include Ollama even if not in DB
    if not any(p.name == "ollama" for p in result):
        result.insert(0, ProviderDetailResponse(
            name="ollama",
            is_active=True,
            has_key=False,
            base_url=None,
            model_count=0,
        ))

    return {"providers": [p.model_dump() for p in result]}


@router.put("/api/providers/{name}/key")
async def save_provider_key(name: str, body: ProviderKeyRequest, request: Request) -> dict:
    """Save or replace an encrypted API key for a provider."""
    db = request.app.state.db
    key_manager = request.app.state.key_manager
    trace_id = getattr(request.state, "trace_id", "")

    # KeyManager must be available
    if key_manager is None:
        raise HTTPException(status_code=503, detail={
            "error": {
                "code": "KEY_MANAGER_UNAVAILABLE",
                "message": "Encryption key not configured. Set EMBEDINATOR_FERNET_KEY environment variable.",
                "details": {},
            },
            "trace_id": trace_id,
        })

    # Verify provider exists
    provider = await db.get_provider(name)
    if not provider:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "PROVIDER_NOT_FOUND",
                "message": f"Provider '{name}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    # Encrypt and store
    encrypted = key_manager.encrypt(body.api_key)
    await db.update_provider(name, api_key_encrypted=encrypted)

    return {"name": name, "has_key": True}


@router.delete("/api/providers/{name}/key")
async def delete_provider_key(name: str, request: Request) -> dict:
    """Remove a stored API key."""
    db = request.app.state.db
    trace_id = getattr(request.state, "trace_id", "")

    provider = await db.get_provider(name)
    if not provider:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "PROVIDER_NOT_FOUND",
                "message": f"Provider '{name}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    # Clear the encrypted key
    # Note: update_provider with api_key_encrypted=None won't clear it
    # because the method skips None values. Use empty string or direct SQL.
    # Check the actual update_provider implementation for handling.
    await db.update_provider(name, api_key_encrypted="")

    return {"name": name, "has_key": False}
```

### Critical: KeyManager Usage

- `app.state.key_manager` is a `KeyManager` instance (from `backend/providers/key_manager.py`)
- It may be `None` if `EMBEDINATOR_FERNET_KEY` env var is not set
- Methods: `key_manager.encrypt(plaintext: str) -> str`, `key_manager.decrypt(ciphertext: str) -> str`
- Return 503 with code `KEY_MANAGER_UNAVAILABLE` when `key_manager is None`

### Critical: Provider Key Security (SC-005)

The `api_key_encrypted` field MUST NEVER appear in any response. The `list_providers()` endpoint reads it from the DB only to compute `has_key: bool`. The `ProviderDetailResponse` schema has NO api_key field.

### Critical: update_provider() and None Values

Read `SQLiteDB.update_provider()` (line 534-559 of sqlite_db.py). It skips `None` values -- only non-None kwargs are SET. To CLEAR the api_key_encrypted field, pass an empty string `""` instead of `None`. Then in `has_key` computation, check `is not None and != ""`.

---

## Implementation: backend/api/models.py (New)

```python
"""Model listing endpoints -- proxies to Ollama and configured providers."""

import httpx
from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import ModelInfo
from backend.config import settings

router = APIRouter()


@router.get("/api/models/llm")
async def list_llm_models(request: Request) -> dict:
    """List available language models from all providers."""
    models = await _fetch_ollama_models(model_type="llm")
    return {"models": [m.model_dump() for m in models]}


@router.get("/api/models/embed")
async def list_embed_models(request: Request) -> dict:
    """List available embedding models."""
    models = await _fetch_ollama_models(model_type="embed")
    return {"models": [m.model_dump() for m in models]}


_EMBED_PATTERNS = {"nomic-embed-text", "mxbai-embed-large"}


def _is_embed_model(name: str) -> bool:
    """Check if a model name is an embedding model."""
    base_name = name.split(":")[0] if ":" in name else name
    if base_name in _EMBED_PATTERNS:
        return True
    if name.endswith(":embed") or name.endswith(":embedding"):
        return True
    return False


async def _fetch_ollama_models(model_type: str) -> list[ModelInfo]:
    """Fetch models from Ollama /api/tags endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
    except (httpx.HTTPError, httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise HTTPException(status_code=503, detail={
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Ollama is unreachable: {e}",
                "details": {},
            },
            "trace_id": "",
        })

    data = resp.json()
    ollama_models = data.get("models", [])

    result = []
    for m in ollama_models:
        name = m.get("name", "")
        is_embed = _is_embed_model(name)

        if model_type == "embed" and not is_embed:
            continue
        if model_type == "llm" and is_embed:
            continue

        details = m.get("details", {})
        size_bytes = m.get("size", 0)
        size_gb = round(size_bytes / (1024 ** 3), 1) if size_bytes else None

        result.append(ModelInfo(
            name=name,
            provider="ollama",
            model_type="embed" if is_embed else "llm",
            size_gb=size_gb,
            quantization=details.get("quantization_level"),
            context_length=None,  # Ollama /api/tags doesn't expose this
        ))

    return result
```

---

## Implementation: backend/api/settings.py (New)

```python
"""System settings endpoints -- read and partial update."""

from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import SettingsResponse, SettingsUpdateRequest
from backend.config import settings as app_config

router = APIRouter()

# Map of setting keys to their config defaults and types
_SETTINGS_KEYS = {
    "default_llm_model": ("default_llm_model", str),
    "default_embed_model": ("default_embed_model", str),
    "confidence_threshold": ("confidence_threshold", int),
    "groundedness_check_enabled": ("groundedness_check_enabled", _parse_bool),
    "citation_alignment_threshold": ("citation_alignment_threshold", float),
    "parent_chunk_size": ("parent_chunk_size", int),
    "child_chunk_size": ("child_chunk_size", int),
}


def _parse_bool(value: str) -> bool:
    """Parse boolean from string stored in settings table."""
    return value.lower() in ("true", "1", "yes")


def _build_settings_response(db_settings: dict[str, str]) -> SettingsResponse:
    """Merge DB settings with config defaults, coerce types."""
    values = {}
    for key, (config_attr, type_fn) in _SETTINGS_KEYS.items():
        if key in db_settings:
            try:
                values[key] = type_fn(db_settings[key])
            except (ValueError, TypeError):
                values[key] = getattr(app_config, config_attr)
        else:
            values[key] = getattr(app_config, config_attr)
    return SettingsResponse(**values)


@router.get("/api/settings")
async def get_settings(request: Request):
    """Get current system-wide settings (DB overrides + config defaults)."""
    db = request.app.state.db
    db_settings = await db.list_settings()
    return _build_settings_response(db_settings)


@router.put("/api/settings")
async def update_settings(body: SettingsUpdateRequest, request: Request):
    """Partially update settings. Only non-None fields are changed."""
    db = request.app.state.db
    trace_id = getattr(request.state, "trace_id", "")

    # Validate confidence_threshold range (Pydantic handles this via Field,
    # but add explicit check for clear error code)
    if body.confidence_threshold is not None:
        if body.confidence_threshold < 0 or body.confidence_threshold > 100:
            raise HTTPException(status_code=400, detail={
                "error": {
                    "code": "SETTINGS_VALIDATION_ERROR",
                    "message": "confidence_threshold must be between 0 and 100",
                    "details": {"field": "confidence_threshold", "value": body.confidence_threshold},
                },
                "trace_id": trace_id,
            })

    # Persist each non-None field
    update_dict = body.model_dump(exclude_none=True)
    for key, value in update_dict.items():
        await db.set_setting(key, str(value))

    # Return full settings after update
    db_settings = await db.list_settings()
    return _build_settings_response(db_settings)
```

**Important**: The `_SETTINGS_KEYS` dict references `_parse_bool` before it is defined. Restructure the file so `_parse_bool` is defined BEFORE the dict. Alternatively, use a function instead of a module-level dict.

### SQLiteDB Settings Methods (Reference)

```python
await db.list_settings() -> dict[str, str]     # all key-value pairs
await db.get_setting(key) -> str | None         # single value
await db.set_setting(key, value: str)           # INSERT OR REPLACE
```

Values are always stored as strings. Type coercion happens in the router.

---

## Test Specifications

### test_providers_router.py

Mock `SQLiteDB` and `KeyManager`. Test:

1. **GET /providers**: Returns list with `has_key: true/false`, no key value in response
2. **Key value never returned**: Assert no response body contains `api_key_encrypted` or `api_key` fields (except request body for PUT)
3. **PUT /key**: Encrypts via KeyManager.encrypt(), stores, returns `{name, has_key: true}`
4. **DELETE /key**: Clears key, returns `{name, has_key: false}`
5. **503 when key_manager is None**: PUT /key returns `KEY_MANAGER_UNAVAILABLE`
6. **404 for unknown provider**: PUT and DELETE return `PROVIDER_NOT_FOUND`
7. **Ollama always listed**: Even if not in DB, Ollama appears in GET /providers

### test_models_router.py

Mock `httpx.AsyncClient`. Test:

1. **GET /models/llm**: Returns ModelInfo list with `model_type="llm"`
2. **GET /models/embed**: Returns only embed models
3. **503 when Ollama unreachable**: Returns `SERVICE_UNAVAILABLE`
4. **Empty response**: When Ollama returns no models, return empty list (not error)
5. **Embedding model detection**: `nomic-embed-text`, `model:embed` correctly filtered

### test_settings_router.py

Mock `SQLiteDB`. Test:

1. **GET /settings**: Returns all 7 fields with correct types and config defaults
2. **PUT partial update**: Only submitted fields change, others retain values
3. **PUT confidence_threshold=150**: Returns 400 `SETTINGS_VALIDATION_ERROR`
4. **PUT confidence_threshold=0**: Returns 200 (valid boundary)
5. **PUT confidence_threshold=100**: Returns 200 (valid boundary)
6. **Defaults**: When no DB settings exist, config defaults are returned

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-mps tests/unit/test_providers_router.py tests/unit/test_models_router.py tests/unit/test_settings_router.py
cat Docs/Tests/spec08-mps.status
cat Docs/Tests/spec08-mps.summary
```

---

## Key Constraints

- **NEVER return API keys**: Not in GET /providers, not in PUT /key response, not anywhere
- `KeyManager` is at `app.state.key_manager` -- may be None
- `ProviderKeyRequest` schema has a single field: `api_key: str`
- Settings are key-value strings in DB -- coerce to int/bool/float at the router level
- `confidence_threshold` is ALWAYS int 0-100, never float
- httpx timeout for Ollama model listing: 10 seconds
- If Ollama is unreachable, return 503, not 500
- Cloud provider model listing is out of scope for this spec -- return empty list if no cloud providers configured

---

## What NOT to Do

- Do NOT keep `_get_fernet()`, `encrypt_api_key()`, `decrypt_api_key()` in providers.py -- use KeyManager
- Do NOT keep `activate_provider()` or `configure_provider()` endpoints
- Do NOT import `Fernet` or `cryptography` in providers.py
- Do NOT return `api_key_encrypted` or the decrypted key in any response
- Do NOT add provider registry logic to models.py -- just use httpx directly to Ollama
- Do NOT add authentication to any endpoint
- Do NOT run pytest inside Claude Code -- use the external test runner
