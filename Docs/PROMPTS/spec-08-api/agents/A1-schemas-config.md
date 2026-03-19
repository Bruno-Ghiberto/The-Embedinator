# A1: Schemas + Config

**Agent type:** `python-expert`
**Model:** Opus 4.6
**Tasks:** T003, T004
**Wave:** 1 (parallel with A2)

---

## Assigned Tasks

### T003: Extend backend/agent/schemas.py

Add all spec-08 Pydantic models and NDJSON event TypedDicts. Do NOT remove existing models -- extend the file.

### T004: Extend backend/config.py

Add missing rate limit fields to the Settings class.

---

## File Targets

| File | Action |
|------|--------|
| `backend/agent/schemas.py` | Extend (add new models, keep all existing) |
| `backend/config.py` | Extend (add fields, fix one existing field) |

---

## Key Constraints

### schemas.py -- New Models to Add

Read the current file first. Keep ALL existing models (`QueryAnalysis`, `RetrievedChunk`, `ParentChunk`, `ClaimVerification`, `GroundednessResult`, `CollectionResponse`, `CollectionCreateRequest`, `DocumentResponse`, `Citation`, `SubAnswer`, `Passage`, `ReasoningStep`, `TraceResponse`, `AnswerResponse`, `ChatRequest`, `ProviderResponse`, `ProviderConfigRequest`, `HealthResponse`, `ErrorDetail`, `ErrorResponse`).

**Modify existing models:**

1. `CollectionCreateRequest` -- currently has `name: str = Field(min_length=1, max_length=255)`. Change to:
   ```python
   class CollectionCreateRequest(BaseModel):
       name: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9][a-z0-9_-]*$")
       description: str | None = None
       embedding_model: str | None = None
       chunk_profile: str | None = None
   ```

2. `CollectionResponse` -- currently has 4 fields. Replace with:
   ```python
   class CollectionResponse(BaseModel):
       id: str
       name: str
       description: str | None = None
       embedding_model: str = "nomic-embed-text"
       chunk_profile: str = "default"
       document_count: int = 0
       created_at: str
   ```

3. `DocumentResponse` -- currently has wrong status literals. Replace with:
   ```python
   class DocumentResponse(BaseModel):
       id: str
       collection_id: str
       filename: str
       status: Literal["pending", "ingesting", "completed", "failed", "duplicate"]
       chunk_count: int | None = None
       created_at: str
       updated_at: str | None = None
   ```

4. `ChatRequest` -- add `embed_model` field:
   ```python
   class ChatRequest(BaseModel):
       message: str = Field(min_length=1, max_length=2000)
       collection_ids: list[str] = Field(default_factory=list)
       llm_model: str = "qwen2.5:7b"
       embed_model: str | None = None
       session_id: str | None = None
   ```

5. `HealthResponse` -- replace flat dict with:
   ```python
   class HealthServiceStatus(BaseModel):
       name: str
       status: Literal["ok", "error"]
       latency_ms: float | None = None
       error_message: str | None = None

   class HealthResponse(BaseModel):
       status: Literal["healthy", "degraded"]
       services: list[HealthServiceStatus]
   ```

**Add new models:**

```python
class IngestionJobResponse(BaseModel):
    job_id: str
    document_id: str
    status: Literal["pending", "started", "streaming", "embedding", "completed", "failed", "paused"]
    chunks_processed: int = 0
    chunks_total: int | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None

class ModelInfo(BaseModel):
    name: str
    provider: str
    model_type: Literal["llm", "embed"]
    size_gb: float | None = None
    quantization: str | None = None
    context_length: int | None = None

class ProviderKeyRequest(BaseModel):
    api_key: str

class ProviderDetailResponse(BaseModel):
    name: str
    is_active: bool = False
    has_key: bool = False
    base_url: str | None = None
    model_count: int = 0

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

class StatsResponse(BaseModel):
    total_collections: int
    total_documents: int
    total_chunks: int
    total_queries: int
    avg_confidence: float
    avg_latency_ms: float
    meta_reasoning_rate: float

class QueryTraceResponse(BaseModel):
    id: str
    session_id: str
    query: str
    collections_searched: list[str]
    confidence_score: int | None = None
    latency_ms: int
    llm_model: str | None = None
    meta_reasoning_triggered: bool = False
    created_at: str

class QueryTraceDetailResponse(QueryTraceResponse):
    sub_questions: list[str] = []
    chunks_retrieved: list[dict] = []
    reasoning_steps: list[dict] = []
    strategy_switches: list[dict] = []
```

**Add 10 NDJSON event TypedDicts** (use `TypedDict` from `typing`):

```python
from typing import TypedDict

class SessionEvent(TypedDict):
    type: Literal["session"]
    session_id: str

class StatusEvent(TypedDict):
    type: Literal["status"]
    node: str

class ChunkEvent(TypedDict):
    type: Literal["chunk"]
    text: str

class CitationEvent(TypedDict):
    type: Literal["citation"]
    citations: list[dict]

class MetaReasoningEvent(TypedDict):
    type: Literal["meta_reasoning"]
    strategies_attempted: list[str]

class ConfidenceEvent(TypedDict):
    type: Literal["confidence"]
    score: int

class GroundednessEvent(TypedDict):
    type: Literal["groundedness"]
    overall_grounded: bool
    supported: int
    unsupported: int
    contradicted: int

class DoneEvent(TypedDict):
    type: Literal["done"]
    latency_ms: int
    trace_id: str

class ClarificationEvent(TypedDict):
    type: Literal["clarification"]
    question: str

class ErrorEvent(TypedDict):
    type: Literal["error"]
    message: str
    code: str
    trace_id: str
```

### config.py -- Changes

Read the current file. Make these changes:

1. **Fix** `rate_limit_chat_per_minute` from `100` to `30`
2. **Add** `rate_limit_provider_keys_per_minute: int = 5`
3. **Add** `rate_limit_general_per_minute: int = 120`

Place the new fields in the existing "Rate Limiting" section.

---

## Test Command

```bash
zsh scripts/run-tests-external.sh -n spec08-schemas tests/unit/test_schemas_api.py
cat Docs/Tests/spec08-schemas.status
cat Docs/Tests/spec08-schemas.summary
```

Note: `test_schemas_api.py` does not exist yet. If this test file needs to be created, write basic import/instantiation tests verifying:
- `CollectionCreateRequest` rejects names with uppercase or spaces
- `SettingsResponse` rejects `confidence_threshold=150`
- `SettingsUpdateRequest` accepts `confidence_threshold=None`
- All 10 NDJSON TypedDicts are importable

---

## What NOT to Do

- Do NOT remove any existing models from schemas.py -- only add and modify
- Do NOT change the `ErrorDetail` or `ErrorResponse` classes (they are already correct)
- Do NOT add `trace_id` to `ErrorResponse` as a field -- trace_id is added at the router level, not in the schema
- Do NOT use float for confidence_threshold -- it is ALWAYS int
- Do NOT create new files -- only modify the two listed files
- Do NOT run pytest inside Claude Code -- use the external test runner
- Do NOT change any unrelated fields in config.py (there are many settings for other specs)
