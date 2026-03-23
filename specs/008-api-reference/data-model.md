# Data Model: API Reference (Spec 08)

**Generated**: 2026-03-15 | **Phase**: 1 (Design)

This document captures the data model for the API Reference feature. All entities are either served from or persisted to the existing spec-07 storage layer (SQLiteDB + Qdrant). Spec 08 does not introduce new storage tables — it only exposes existing data through new or revised HTTP endpoints.

---

## 1. Core Entities (SQLite-backed)

### Collection

Stored in `collections` table (spec-07 schema).

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID string | NO | Primary key, UUID4 |
| `name` | string | NO | Unique; `^[a-z0-9][a-z0-9_-]*$`; max 100 chars |
| `description` | string | YES | Optional user note |
| `embedding_model` | string | NO | Default from `settings.default_embed_model` |
| `chunk_profile` | string | NO | Default `"default"` |
| `qdrant_collection_name` | string | NO | Auto-generated from UUID |
| `document_count` | int | NO | Derived: count of non-deleted documents |
| `created_at` | ISO-8601 timestamp | NO | Set at creation |

**Validation Rules**:
- `name`: must match `^[a-z0-9][a-z0-9_-]*$` (FR-002)
- `name`: unique across all collections (FR-003)

**API Shape** (`CollectionResponse`):
```python
class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    embedding_model: str
    chunk_profile: str
    document_count: int
    created_at: str
```

---

### Document

Stored in `documents` table (spec-07 schema).

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID string | NO | Primary key, UUID4 |
| `collection_id` | UUID string | NO | FK → collections.id |
| `filename` | string | NO | Original filename |
| `file_hash` | string | NO | SHA-256 hex digest (duplicate detection) |
| `file_path` | string | YES | Storage path |
| `status` | string | NO | Enum: see state machine |
| `chunk_count` | int | YES | Set after ingestion completes |
| `created_at` | ISO-8601 timestamp | NO | Upload time |
| `updated_at` | ISO-8601 timestamp | YES | Last status change |

**Status State Machine**:
```
pending → ingesting → completed
                   → failed
         → duplicate (terminal — content identical to existing)
```

**Validation Rules**:
- `filename`: extension must be in allowed set (FR-007)
- `file_size`: must not exceed 100 MB (FR-008)

**API Shape** (`DocumentResponse`):
```python
class DocumentResponse(BaseModel):
    id: str
    collection_id: str
    filename: str
    status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
    chunk_count: int | None
    created_at: str
    updated_at: str | None
```

---

### IngestionJob

Stored in `ingestion_jobs` table (spec-07 schema).

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID string | NO | Primary key, UUID4 |
| `document_id` | UUID string | NO | FK → documents.id |
| `status` | string | NO | Enum: see state machine |
| `chunks_processed` | int | YES | Processed so far |
| `chunks_skipped` | int | YES | Skipped (duplicates) |
| `started_at` | ISO-8601 timestamp | YES | Ingestion start |
| `finished_at` | ISO-8601 timestamp | YES | Completion or failure time |
| `error_msg` | string | YES | Error detail if failed |

**Status State Machine**:
```
pending → started → streaming → embedding → completed
                                           → failed
                                → paused (Qdrant outage) → resumed → embedding
```

**API Shape** (`IngestionJobResponse`):
```python
class IngestionJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: Literal["pending", "started", "streaming", "embedding", "completed", "failed", "paused"]
    chunks_processed: int
    chunks_total: int | None
    error_message: str | None
    started_at: str | None
    completed_at: str | None
```

---

### QueryTrace

Stored in `query_traces` table (spec-07 schema).

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `id` | UUID string | NO | Primary key |
| `session_id` | string | NO | LangGraph thread_id |
| `query` | string | NO | User's query text |
| `collections_searched` | JSON string | NO | List of collection IDs |
| `chunks_retrieved_json` | JSON string | NO | Retrieved passages with scores |
| `latency_ms` | int | NO | Total request latency |
| `llm_model` | string | YES | Model used |
| `embed_model` | string | YES | Embedding model |
| `confidence_score` | int | YES | 0–100 integer (FR-015) |
| `sub_questions_json` | JSON string | YES | Decomposed sub-queries |
| `reasoning_steps_json` | JSON string | YES | Step-by-step reasoning |
| `strategy_switches_json` | JSON string | YES | Meta-reasoning strategy changes |
| `meta_reasoning_triggered` | bool | NO | Whether MetaReasoningGraph ran |
| `created_at` | ISO-8601 timestamp | NO | Query time |

**Retention**: Indefinitely (never automatically purged — FR-021 clarification)

**API Shapes**:
```python
class QueryTraceResponse(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: list[str]
    confidence_score: int | None     # 0-100 integer
    latency_ms: int
    llm_model: str | None
    meta_reasoning_triggered: bool
    created_at: str

class QueryTraceDetailResponse(QueryTraceResponse):
    sub_questions: list[str]
    chunks_retrieved: list[dict]     # chunk_id, score, text
    reasoning_steps: list[dict]
    strategy_switches: list[dict]
```

---

### Provider

Stored in `providers` table (spec-07 schema, needs extension).

| Field | Type | Nullable | Notes |
|-------|------|----------|-------|
| `name` | string | NO | Primary key: `ollama`, `openai`, `openrouter`, `anthropic` |
| `api_key_encrypted` | string | YES | Fernet-encrypted API key (Constitution V) |
| `base_url` | string | YES | Override base URL |
| `is_active` | bool | NO | Whether this provider is currently active |
| `created_at` | ISO-8601 timestamp | NO | Registration time |

**Security Rules (Constitution V + FR-018)**:
- `api_key_encrypted` MUST NEVER be returned in any API response
- Only `has_key: bool` indicator returned (SC-005)
- Encryption: Fernet via `app.state.key_manager`

**API Shape** (`ProviderDetailResponse`):
```python
class ProviderDetailResponse(BaseModel):
    name: str
    is_active: bool
    has_key: bool       # True if api_key_encrypted is non-null
    base_url: str | None
    model_count: int    # Count of available models (from Ollama/API)
    # api_key_encrypted: NEVER included
```

---

### SystemSettings

Stored as key-value pairs in `settings` table (spec-07 schema). No single settings row — each setting is a separate DB row with key and string value.

| Setting Key | Value Type | Default | Notes |
|-------------|------------|---------|-------|
| `default_llm_model` | str | `qwen2.5:7b` | Model for chat |
| `default_embed_model` | str | `nomic-embed-text` | Embedding model |
| `confidence_threshold` | int (0–100) | `60` | Min confidence before uncertainty response |
| `groundedness_check_enabled` | bool | `True` | Run GAV check on answers |
| `citation_alignment_threshold` | float | `0.3` | Min citation relevance score |
| `parent_chunk_size` | int | `2000` | Parent chunk character limit |
| `child_chunk_size` | int | `500` | Child chunk character limit |

**API Shapes**:
```python
class SettingsResponse(BaseModel):
    default_llm_model: str
    default_embed_model: str
    confidence_threshold: int = Field(ge=0, le=100)
    groundedness_check_enabled: bool
    citation_alignment_threshold: float
    parent_chunk_size: int
    child_chunk_size: int

class SettingsUpdateRequest(BaseModel):
    default_llm_model: str | None = None
    default_embed_model: str | None = None
    confidence_threshold: int | None = Field(None, ge=0, le=100)
    groundedness_check_enabled: bool | None = None
    citation_alignment_threshold: float | None = None
    parent_chunk_size: int | None = None
    child_chunk_size: int | None = None
```

---

### ModelInfo

Transient — not persisted. Built on-demand by querying Ollama `/api/tags` and configured cloud providers.

```python
class ModelInfo(BaseModel):
    name: str                              # e.g., "llama3.2:3b", "gpt-4o"
    provider: str                          # e.g., "ollama", "openai"
    model_type: Literal["llm", "embed"]
    size_gb: float | None                  # Model size on disk
    quantization: str | None               # e.g., "Q4_K_M"
    context_length: int | None             # Context window in tokens
```

---

## 2. NDJSON Event Types (Chat Stream)

The chat endpoint streams newline-delimited JSON. Each line is a complete JSON object.

```python
# 1 — Session (first event, always emitted)
{"type": "session", "session_id": str}

# 2 — Status (on each graph node transition)
{"type": "status", "node": str}   # e.g., "query_rewrite", "research", "format_response"

# 3 — Chunk (token-by-token answer content)
{"type": "chunk", "text": str}

# 4 — Citation (after stream completes)
{"type": "citation", "citations": list[dict]}  # Citation objects from spec-02

# 5 — Meta-reasoning (if MetaReasoningGraph ran)
{"type": "meta_reasoning", "strategies_attempted": list[str]}

# 6 — Confidence (integer 0-100, FR-015)
{"type": "confidence", "score": int}   # ALWAYS int, never float

# 7 — Groundedness
{"type": "groundedness", "overall_grounded": bool, "supported": int, "unsupported": int, "contradicted": int}

# 8 — Done (last event on success)
{"type": "done", "latency_ms": int, "trace_id": str}

# 9 — Clarification (on LangGraph interrupt; triggers early return)
{"type": "clarification", "question": str}

# 10 — Error (on exception)
{"type": "error", "message": str, "code": str, "trace_id": str}
```

---

## 3. Error Response Schema

All non-streaming error responses (FR-026):

```python
class ErrorDetail(BaseModel):
    code: str       # Machine-readable: "COLLECTION_NOT_FOUND", "FILE_TOO_LARGE", etc.
    message: str    # Human-readable description
    details: dict   # Optional structured details

class ErrorResponse(BaseModel):
    error: ErrorDetail
    trace_id: str   # From request.state.trace_id (set by TraceIDMiddleware)
```

**Error Codes** (exhaustive):
| Code | HTTP | Description |
|------|------|-------------|
| `COLLECTION_NOT_FOUND` | 404 | Collection ID does not exist |
| `COLLECTION_NAME_CONFLICT` | 409 | Name already in use |
| `COLLECTION_NAME_INVALID` | 400 | Regex pattern violation |
| `DOCUMENT_NOT_FOUND` | 404 | Document ID does not exist |
| `FILE_FORMAT_NOT_SUPPORTED` | 400 | Extension not in allowlist |
| `FILE_TOO_LARGE` | 413 | File exceeds 100 MB |
| `DUPLICATE_DOCUMENT` | 409 | Same content hash already ingested |
| `JOB_NOT_FOUND` | 404 | Ingestion job ID does not exist |
| `PROVIDER_NOT_FOUND` | 404 | Provider name not registered |
| `KEY_MANAGER_UNAVAILABLE` | 503 | `EMBEDINATOR_FERNET_KEY` not set |
| `TRACE_NOT_FOUND` | 404 | Trace ID does not exist |
| `RATE_LIMIT_EXCEEDED` | 429 | Per-IP rate limit reached |
| `CIRCUIT_OPEN` | 503 | Qdrant/Ollama circuit breaker open |
| `SERVICE_UNAVAILABLE` | 503 | Upstream service unreachable |
| `INVALID_REQUEST` | 400 | Generic request validation failure |
| `SETTINGS_VALIDATION_ERROR` | 400 | Settings value out of valid range |

---

## 4. Relationships

```
Collection (1) ──────────────── (N) Document
Collection (1) ──── (cascade) ── (N) IngestionJob (via Document)
ChatSession ──────────────────── (N) QueryTrace
Provider (1) ──────────────────── (*) ModelInfo (transient)
Settings ──────────────────────── SystemConfig (merged at read time)
```

**Cascade Rules**:
- Deleting a Collection: cancel active IngestionJobs (→ `failed`) → delete Documents → delete Qdrant collection
- Deleting a Document: preserve QueryTraces with `source_removed: true` marker (Constitution IV)

---

## 5. Rate Limit Counters (In-Memory)

Not persisted. Per-IP, per-category, sliding window (60 seconds):

| Category | Limit | Bucket Key Pattern |
|----------|-------|-------------------|
| Chat | 30 req/min | `chat:{client_ip}` |
| Ingestion | 10 req/min | `ingest:{client_ip}` |
| Provider key management | 5 req/min | `provider_key:{client_ip}` |
| General | 120 req/min | `general:{client_ip}` |

Rate limit counters are `dict[str, list[float]]` (timestamps) held in middleware instance. Lost on process restart — acceptable for the 1-5 user target scale.
