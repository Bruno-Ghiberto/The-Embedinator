# Data Model: Error Handling (spec-12)

**Date**: 2026-03-17 | **Branch**: `012-error-handling`

## Overview

Spec-12 introduces no new database tables. All error handling state is either in-memory (circuit breakers, rate limit buckets) or manifested as JSON response bodies. This document captures the relevant entities and their schemas.

---

## Exception Hierarchy (Code Artifact)

### EmbeddinatorError Family (`backend/errors.py`)

Flat hierarchy — all subclasses extend `EmbeddinatorError` directly. No intermediate base classes.

```
EmbeddinatorError(Exception)
  ├─ QdrantConnectionError      Qdrant connection or communication failure
  ├─ OllamaConnectionError      Ollama connection or communication failure
  ├─ SQLiteError                SQLite operation failure
  ├─ LLMCallError               LLM inference call failure
  ├─ EmbeddingError             Embedding generation failure
  ├─ IngestionError             Document ingestion pipeline failure
  ├─ SessionLoadError           Failed to load session from SQLite
  ├─ StructuredOutputParseError Failed to parse structured LLM output
  ├─ RerankerError              Cross-encoder reranking failure
  └─ CircuitOpenError           Raised when circuit breaker is open
```

**Invariants**:
- `EmbeddinatorError` has no `__init__` override — contextual info passed as message string
- All subclasses are instantiable with a plain string: `QdrantConnectionError("msg")`
- No subclass adds `code`, `message`, or `details` attributes (those live in the response envelope)

### ProviderRateLimitError (`backend/providers/base.py`)

Separate from the `EmbeddinatorError` hierarchy by design (spec-10):

```python
ProviderRateLimitError(Exception)
  - provider: str   # name of the cloud provider that returned HTTP 429
```

**Invariants**:
- Extends `Exception` directly (NOT `EmbeddinatorError`)
- Constructor: `__init__(self, provider: str)`
- `str(exc)` returns `f"Rate limit exceeded for provider: {provider}"`

---

## REST Error Envelope

### JSON Schema

```json
{
  "error": {
    "code": "<UPPER_SNAKE_CASE>",
    "message": "<human-readable string>",
    "details": {}
  },
  "trace_id": "<UUID4 string>"
}
```

### Pydantic Backing Models (`backend/agent/schemas.py`)

```python
class ErrorDetail(BaseModel):
    code: str          # required, stable identifier
    message: str       # required, user-facing text
    details: dict = {} # optional structured context

class ErrorResponse(BaseModel):
    error: ErrorDetail
    # NOTE: trace_id is NOT a field — it is appended manually as a dict key
```

### Error Code Registry

All error codes are stable. Renaming is a breaking change.

| Code | HTTP Status | Source | Description |
|------|-------------|--------|-------------|
| `PROVIDER_RATE_LIMIT` | 429 | `main.py` exception handler | Cloud provider returned HTTP 429 |
| `INTERNAL_ERROR` | 500 | `main.py` exception handler | Any unhandled `EmbeddinatorError` |
| `QDRANT_UNAVAILABLE` | 503 | `main.py` exception handler | `QdrantConnectionError` escaped router |
| `OLLAMA_UNAVAILABLE` | 503 | `main.py` exception handler | `OllamaConnectionError` escaped router |
| `RATE_LIMIT_EXCEEDED` | 429 | `middleware.py` | Per-IP sliding window exceeded |
| `KEY_MANAGER_UNAVAILABLE` | 503 | `api/providers.py` | `EMBEDINATOR_FERNET_KEY` not configured |
| `SERVICE_UNAVAILABLE` | 503 | `api/models.py` | Ollama unreachable on models endpoint |
| `COLLECTION_NAME_INVALID` | 400 | `api/collections.py` | Name fails regex validation |
| `SETTINGS_VALIDATION_ERROR` | 400 | `api/settings.py` | Value out of configured range |
| `FILE_FORMAT_NOT_SUPPORTED` | 400 | `api/ingest.py` | Extension not in allowlist |
| `FILE_TOO_LARGE` | 413 | `api/ingest.py` | Exceeds `max_upload_size_mb` |
| `COLLECTION_NOT_FOUND` | 404 | `api/collections.py`, `api/ingest.py` | Collection does not exist |
| `DOCUMENT_NOT_FOUND` | 404 | `api/documents.py` | Document does not exist |
| `JOB_NOT_FOUND` | 404 | `api/ingest.py` | Ingestion job does not exist |
| `TRACE_NOT_FOUND` | 404 | `api/traces.py` | Query trace does not exist |
| `PROVIDER_NOT_FOUND` | 404 | `api/providers.py` | Provider does not exist |
| `COLLECTION_NAME_CONFLICT` | 409 | `api/collections.py` | Name already in use |
| `DUPLICATE_DOCUMENT` | 409 | `api/ingest.py` | Same file hash already ingested |

---

## NDJSON Stream Error Event

Emitted by `POST /api/chat` when an error occurs after the HTTP 200 response has started:

```json
{"type": "error", "message": "<user-facing string>", "code": "<CODE>", "trace_id": "<UUID4>"}
```

| Code | Trigger |
|------|---------|
| `NO_COLLECTIONS` | `body.collection_ids` is empty |
| `CIRCUIT_OPEN` | `CircuitOpenError` raised during graph execution |
| `SERVICE_UNAVAILABLE` | Any other unhandled `Exception` during graph execution |

**Note**: This format is intentionally different from the REST error envelope. Both are correct for their respective contexts.

---

## Circuit Breaker State (In-Memory)

Three independent circuit breakers. No persistence.

### QdrantClientWrapper and QdrantStorage (instance variables)

```python
_circuit_open: bool = False       # True when circuit is open
_failure_count: int = 0           # consecutive failure count
_last_failure_time: float | None  # time.monotonic() of last failure
_max_failures: int                # from settings.circuit_breaker_failure_threshold
_cooldown_secs: int               # from settings.circuit_breaker_cooldown_secs
```

### Inference Circuit Breaker (module-level globals in nodes.py)

```python
_inf_circuit_open: bool = False
_inf_failure_count: int = 0
_inf_last_failure_time: float | None = None
```

Config read from `settings` on every `_check_inference_circuit()` call.

---

## Rate Limit Bucket (In-Memory)

Keyed by `"{bucket_type}:{client_ip}"` string. Sliding window of request timestamps.

| Bucket Type | Endpoint Pattern | Config Field | Default |
|-------------|-----------------|--------------|---------|
| `chat` | `POST /api/chat` | `rate_limit_chat_per_minute` | 30 |
| `ingest` | `POST **/ingest` | `rate_limit_ingest_per_minute` | 10 |
| `provider_keys` | `PUT/DELETE /api/providers/*/key` | `rate_limit_provider_keys_per_minute` | 5 |
| `general` | All other endpoints | `rate_limit_general_per_minute` | 120 |
