# Data Model: Vision & System Architecture

**Date**: 2026-03-10 | **Branch**: `001-vision-arch` | **Phase**: 1 (Design)

This document defines the core entities, relationships, and validation rules for Phase 1 MVP.

## Entity Definitions

### Collection

A user-created group of documents that can be queried as a unit.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (UUID) | PRIMARY KEY | Generated on creation |
| `name` | TEXT | NOT NULL, UNIQUE | User-visible name (e.g., "Project Files", "Legal Docs") |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Audit trail |
| `updated_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Updated on modification |

**Lifecycle**:
- Created: User submits form via UI
- Queryable: Once documents added and indexed
- Deleted: Can be deleted; orphans documents (preserves document-collection relationship state)

**Validation**:
- `name`: 1–255 characters, no leading/trailing whitespace
- No duplicate names per user (future: support per-user collections)

---

### Document

A user-uploaded file (PDF, Markdown, plain text) that belongs to one or more collections.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (UUID) | PRIMARY KEY | Generated on creation |
| `name` | TEXT | NOT NULL | Original filename (e.g., "report.pdf") |
| `collection_ids` | JSON | NOT NULL | Array of collection UUIDs (supports many-to-many) |
| `file_path` | TEXT | NOT NULL | Local filesystem path (e.g., "./data/uploads/doc-123.pdf") |
| `status` | TEXT | DEFAULT 'uploaded' | Enum: uploaded, parsing, indexing, indexed, failed, deleted |
| `upload_date` | DATETIME | DEFAULT CURRENT_TIMESTAMP | When user uploaded |
| `file_size_bytes` | INT | | Optional: for quota tracking |
| `parse_error` | TEXT | | Optional: reason if status='failed' |

**Lifecycle**:
1. `uploaded`: User submits file via UI
2. `parsing`: Backend parses file content
3. `indexing`: Backend chunks text and sends to embedding service
4. `indexed`: Chunks stored in Qdrant; document queryable
5. `deleted`: User deletes; document removed from future retrieval but traces retain passage text

**Validation**:
- `name`: 1–255 characters
- `collection_ids`: At least one collection (mandatory)
- `file_path`: Absolute or relative to app root
- `status`: Must be one of the enum values above

**Many-to-many relationship** (supports document in multiple collections):
```json
{
  "id": "doc-456",
  "name": "report.pdf",
  "collection_ids": ["col-001", "col-002"],  // One document, two collections
  "status": "indexed"
}
```

---

### Query

A natural-language question submitted by a user in the chat interface.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (UUID) | PRIMARY KEY | Generated on creation |
| `session_id` | TEXT | NOT NULL | Browser session identifier |
| `query_text` | TEXT | NOT NULL | The user's question (e.g., "What are the main findings?") |
| `collection_ids` | JSON | NOT NULL | Collections searched (array of UUIDs) |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | When submitted |

**Lifecycle**:
- Created: User submits question → backend records query and starts retrieval
- Traced: Trace record created with search results, confidence, citations

**Validation**:
- `query_text`: 1–2000 characters (prevent absurdly long inputs)
- `collection_ids`: At least one collection (user selected in UI)

---

### Answer

The system-generated response to a query, including citations and confidence.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (UUID) | PRIMARY KEY | Generated at generation time |
| `query_id` | TEXT | NOT NULL, FK to Query | Link to originating query |
| `answer_text` | TEXT | NOT NULL | The full generated answer (may be long) |
| `citations` | JSON | NOT NULL | Array of citations (see Citation type) |
| `confidence_score` | INT | NOT NULL, 0–100 | Confidence that answer is grounded (0=min, 100=max) |
| `generated_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | When answer was finalized |

**Citation object** (element of `citations` array):
```json
{
  "passage_id": "passage-789",
  "document_id": "doc-123",
  "document_name": "report.pdf",
  "start_offset": 245,
  "end_offset": 387,
  "text": "The main finding was...",
  "relevance_score": 0.94
}
```

**Validation**:
- `answer_text`: Non-empty
- `confidence_score`: Integer 0–100 (clarified requirement)
- `citations`: At least one citation (unless "no relevant information" answer)

---

### Trace

Complete record of the system's reasoning for a query: retrieval results, scores, and any fallback steps.

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `id` | TEXT (UUID) | PRIMARY KEY | Generated on query completion |
| `query_id` | TEXT | NOT NULL, FK to Query | Link to originating query |
| `query_text` | TEXT | NOT NULL | Denormalized query text (for display without join) |
| `collections_searched` | JSON | NOT NULL | Array of collection UUIDs searched |
| `passages_retrieved` | JSON | NOT NULL | Array of Passage objects (see below) |
| `confidence_score` | INT | NOT NULL | Same 0–100 scale as Answer |
| `reasoning_steps` | JSON | | Optional: sub-questions explored, fallback attempts |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | When trace was recorded |

**Passage object** (element of `passages_retrieved` array):
```json
{
  "id": "passage-789",
  "document_id": "doc-456",
  "document_name": "report.pdf",
  "text": "The key insight is...",
  "relevance_score": 0.91,
  "chunk_index": 42,
  "source_removed": false  // Set to true if document later deleted
}
```

**Reasoning step object** (element of `reasoning_steps` array):
```json
{
  "step_num": 1,
  "strategy": "initial_retrieval",  // or "fallback_reranking", "query_decomposition", etc.
  "passages_found": 5,
  "avg_score": 0.78
}
```

**Lifecycle**:
- Created: Upon query completion, after answer generation
- Immutable: Never updated (audit trail)
- Retained on document deletion: Passages keep captured text, display "source removed"

**Validation**:
- `passages_retrieved`: At least one passage (or special "no results" marker)
- `confidence_score`: 0–100 integer

---

### Provider

Configured AI inference source (local Ollama or cloud API).

| Field | Type | Constraints | Notes |
|-------|------|-------------|-------|
| `name` | TEXT | PRIMARY KEY | Provider identifier (e.g., "ollama", "openrouter", "openai") |
| `type` | TEXT | NOT NULL | Provider category (e.g., "ollama", "cloud_api") |
| `config_json` | TEXT | NOT NULL | Encrypted JSON config (API key, model name, etc.) |
| `is_active` | BOOLEAN | DEFAULT 0 | True if this is the active provider for new queries |

**Supported providers** (Phase 1):
- `ollama`: Local, default. Config: `{ "model": "qwen2.5:7b" }`
- `openrouter`: Cloud API. Config: `{ "api_key": "...[encrypted]...", "model": "qwen/qwen-2.5-7b" }`

**Lifecycle**:
- Created: Via settings UI (provider endpoint)
- Activated: User selects in settings → backend updates `is_active` flag
- Config updated: API key changes → re-encrypt and store

**Validation**:
- `name`: Known provider type
- `config_json`: Valid JSON; API key required for cloud providers (encrypted)
- At most one provider has `is_active = 1`

---

## Relationships

```
Collection ←→ Document (many-to-many)
  Collection.id references Document.collection_ids (JSON array)
  Example: Collection "Legal" contains [Doc-A, Doc-B]
           Collection "Contracts" contains [Doc-B, Doc-C]  ← Doc-B in two collections

Document ←→ Query (one-to-many)
  Query.collection_ids references Document.collection_ids
  Each query targets one or more collections

Query → Answer (one-to-one)
  Answer.query_id = Query.id
  Each query results in exactly one answer

Query → Trace (one-to-one)
  Trace.query_id = Query.id
  Each query generates exactly one trace

Answer → Trace (implicit)
  Both record the same underlying retrieval results
  Trace is the detailed view; Answer is the user-facing summary
```

## State Transitions

### Document Status Lifecycle

```
    uploaded
       ↓
    parsing
       ↓
    indexing
       ↓
    indexed ← → failed (on error)
       ↓
    deleted (user action; preserves traces)
```

**Status meaning**:
- `uploaded`: File received; awaiting parse
- `parsing`: Extracting text from file
- `indexing`: Chunking and embedding text
- `indexed`: Ready for queries
- `failed`: Parse or indexing error; see `parse_error` field
- `deleted`: User removed; not searchable but traces retain text

### Provider Activation

```
ollama (default, auto-created on startup)
  ↓
user configures "openrouter" → openrouter activated
  ↓
user reconfigures "ollama" → ollama reactivated
```

**Invariant**: Exactly one provider has `is_active = 1` at all times.

## SQLite Schema

```sql
-- Collections
CREATE TABLE collections (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Documents (supports many-to-many via JSON)
CREATE TABLE documents (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  collection_ids JSON NOT NULL,  -- Array: ["col-001", "col-002"]
  file_path TEXT NOT NULL,
  status TEXT DEFAULT 'uploaded',
  upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
  file_size_bytes INT,
  parse_error TEXT
);
CREATE INDEX idx_documents_status ON documents(status);

-- Queries
CREATE TABLE queries (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  query_text TEXT NOT NULL,
  collection_ids JSON NOT NULL,  -- Array: ["col-001"]
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_queries_session_id ON queries(session_id);

-- Answers
CREATE TABLE answers (
  id TEXT PRIMARY KEY,
  query_id TEXT NOT NULL,
  answer_text TEXT NOT NULL,
  citations JSON NOT NULL,
  confidence_score INT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
  generated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (query_id) REFERENCES queries(id)
);

-- Traces (detailed reasoning logs)
CREATE TABLE traces (
  id TEXT PRIMARY KEY,
  query_id TEXT NOT NULL,
  query_text TEXT NOT NULL,
  collections_searched JSON NOT NULL,
  passages_retrieved JSON NOT NULL,
  confidence_score INT NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 100),
  reasoning_steps JSON,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (query_id) REFERENCES queries(id)
);
Create INDEX idx_traces_query_id ON traces(query_id);

-- Providers
CREATE TABLE providers (
  name TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  config_json TEXT NOT NULL,
  is_active BOOLEAN DEFAULT 0
);
```

## Type Definitions (Python Pydantic)

```python
# backend/agent/schemas.py

class Citation(BaseModel):
    passage_id: str
    document_id: str
    document_name: str
    start_offset: int
    end_offset: int
    text: str
    relevance_score: float  # 0.0–1.0

class Answer(BaseModel):
    id: str
    query_id: str
    answer_text: str
    citations: List[Citation]
    confidence_score: int  # 0–100
    generated_at: datetime

class Passage(BaseModel):
    id: str
    document_id: str
    document_name: str
    text: str
    relevance_score: float
    chunk_index: int
    source_removed: bool = False

class Trace(BaseModel):
    id: str
    query_id: str
    query_text: str
    collections_searched: List[str]
    passages_retrieved: List[Passage]
    confidence_score: int  # 0–100
    created_at: datetime

class Provider(BaseModel):
    name: str
    type: str
    is_active: bool
    # config_json is NOT exposed (encrypted in DB)
```

## Validation Rules

| Entity | Rule | Check |
|--------|------|-------|
| Collection | Name unique | Constraint: UNIQUE(name) |
| Document | At least one collection | `len(collection_ids) > 0` |
| Document | Valid status | `status` IN ('uploaded', 'parsing', 'indexing', 'indexed', 'failed', 'deleted') |
| Query | Confidence 0–100 | `confidence_score >= 0 AND confidence_score <= 100` |
| Answer | Non-empty answer | `len(answer_text) > 0` |
| Answer | At least one citation | `len(citations) > 0` OR special "no results" marker |
| Trace | At least one passage | `len(passages_retrieved) > 0` OR "no results" |
| Provider | One active | Exactly one row has `is_active = 1` |
| Provider | Valid type | `type` IN ('ollama', 'openrouter', 'openai', 'anthropic') |

---

**Status**: Data model complete. Ready for API contract design.
