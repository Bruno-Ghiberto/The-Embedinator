# Data Model: Frontend Application

**Phase**: 1 — Design
**Date**: 2026-03-16
**Source**: `backend/agent/schemas.py` (verified 2026-03-16)

All types mirror backend Pydantic schemas exactly. TypeScript definitions live in `frontend/lib/types.ts`.

---

## Core Entities

### Collection

```typescript
interface Collection {
  id: string;
  name: string;                    // validated: ^[a-z0-9][a-z0-9_-]*$
  description: string | null;
  embedding_model: string;         // default: "nomic-embed-text"
  chunk_profile: string;           // default: "default"
  document_count: number;          // aggregate, no per-collection chunk count in API
  created_at: string;              // ISO 8601
}

interface CollectionCreateRequest {
  name: string;                    // max_length: 100, pattern: ^[a-z0-9][a-z0-9_-]*$
  description?: string | null;
  embedding_model?: string | null;
  chunk_profile?: string | null;
}
```

**Validation rules**: Name slug `^[a-z0-9][a-z0-9_-]*$`, max 100 chars. Inline validation before submission. Conflict error `COLLECTION_NAME_CONFLICT` displayed without closing dialog.

---

### Document

```typescript
interface Document {
  id: string;
  collection_id: string;
  filename: string;
  status: DocumentStatus;
  chunk_count: number | null;
  created_at: string;
  updated_at: string | null;
}

type DocumentStatus = "pending" | "ingesting" | "completed" | "failed" | "duplicate";
```

**Note**: `DocumentStatus` has 5 values (document-level). Distinct from `IngestionJobStatus` (7 values, job-level).

---

### IngestionJob

```typescript
interface IngestionJob {
  job_id: string;
  document_id: string;
  status: IngestionJobStatus;
  chunks_processed: number;
  chunks_total: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

type IngestionJobStatus =
  | "pending" | "started" | "streaming" | "embedding"
  | "completed" | "failed" | "paused";

// Terminal states — stop polling when reached:
const TERMINAL_JOB_STATES: IngestionJobStatus[] = ["completed", "failed"];
```

---

### ChatMessage

```typescript
interface ChatMessage {
  id: string;                       // client-generated uuid
  role: "user" | "assistant";
  content: string;                  // accumulated from chunk events
  citations?: Citation[];
  confidence?: number;              // integer 0–100; undefined until done event
  groundedness?: GroundednessData;
  clarification?: string;           // set when clarification event received
  isStreaming: boolean;             // true while chunk events arriving
  traceId?: string;                 // set from done event
}
```

---

### Citation

```typescript
interface Citation {
  passage_id: string;
  document_id: string;
  document_name: string;
  start_offset: number;
  end_offset: number;
  text: string;
  relevance_score: number;          // 0.0–1.0 float
  source_removed: boolean;          // CONSTITUTION IV: must render "source removed" when true
  // Future: page?: number; breadcrumb?: string;
  // These exist in backend RetrievedChunk (searcher.py) and Qdrant payload
  // but are not yet exposed in the Citation schema (schemas.py).
}
```

**UI rule**: When `source_removed === true`, `CitationTooltip` renders a "source removed" badge instead of the source link. The `text` field contains the captured passage text; `document_name` provides the file name. Page number and breadcrumb are not in the current Citation schema — render `start_offset`/`end_offset` as a position indicator if desired.

---

### GroundednessData

```typescript
interface GroundednessData {
  overall_grounded: boolean;
  supported: number;
  unsupported: number;
  contradicted: number;
}
```

---

### Model

```typescript
interface ModelInfo {
  name: string;
  provider: string;
  model_type: "llm" | "embed";
  size_gb: number | null;
  quantization: string | null;
  context_length: number | null;
}
```

---

### Provider

```typescript
interface Provider {
  name: string;
  is_active: boolean;              // connectivity status (Ollama: no key needed)
  has_key: boolean;                // API key stored (NEVER return raw key)
  base_url: string | null;
  model_count: number;
}
```

**UI rule**: Display `has_key ? "••••••••" : "No key"` in key field. Raw key is never returned by backend. `is_active` and `has_key` are independent indicators.

---

### Settings

```typescript
interface Settings {
  default_llm_model: string;
  default_embed_model: string;
  confidence_threshold: number;      // integer 0–100
  groundedness_check_enabled: boolean;
  citation_alignment_threshold: number; // float
  parent_chunk_size: number;
  child_chunk_size: number;
}

interface SettingsUpdateRequest {
  default_llm_model?: string;
  default_embed_model?: string;
  confidence_threshold?: number;
  groundedness_check_enabled?: boolean;
  citation_alignment_threshold?: number;
  parent_chunk_size?: number;
  child_chunk_size?: number;
}
```

**Save pattern**: `PUT /api/settings` with partial body. Show `Toast` on success/error after API response. No optimistic UI.

---

### QueryTrace (list view)

```typescript
interface QueryTrace {
  id: string;
  session_id: string;
  query: string;
  collections_searched: string[];
  confidence_score: number | null;   // integer 0–100
  latency_ms: number;
  llm_model: string | null;
  meta_reasoning_triggered: boolean;
  created_at: string;
}
```

### QueryTraceDetail (expanded row)

```typescript
interface QueryTraceDetail extends QueryTrace {
  sub_questions: string[];
  chunks_retrieved: Record<string, unknown>[];
  reasoning_steps: Record<string, unknown>[];
  strategy_switches: Record<string, unknown>[];
}
```

---

### Health

```typescript
interface HealthStatus {
  status: "healthy" | "degraded";
  services: HealthService[];
}

interface HealthService {
  name: string;                      // "sqlite" | "qdrant" | "ollama"
  status: "ok" | "error";
  latency_ms: number | null;
  error_message: string | null;
}
```

---

### Stats (aggregate)

```typescript
interface SystemStats {
  total_collections: number;
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  avg_confidence: number;            // float
  avg_latency_ms: number;
  meta_reasoning_rate: number;       // float 0.0–1.0
}
```

**Note**: No per-collection chunk count available. `CollectionStats` displays `document_count` from each `Collection` and `total_chunks` from `SystemStats` as aggregate.

---

## NDJSON Stream Events

```typescript
type NdjsonEvent =
  | { type: "session";        session_id: string }
  | { type: "status";         node: string }
  | { type: "chunk";          text: string }           // field is "text", not "content"
  | { type: "clarification";  question: string }       // stream ends here; no done follows
  | { type: "citation";       citations: Citation[] }
  | { type: "meta_reasoning"; strategies_attempted: string[] }
  | { type: "confidence";     score: number }           // integer 0–100
  | { type: "groundedness";   overall_grounded: boolean; supported: number; unsupported: number; contradicted: number }
  | { type: "done";           latency_ms: number; trace_id: string }
  | { type: "error";          message: string; code: string; trace_id: string };
```

**isStreaming release**: Must be called in `done`, `error`, AND `clarification` handlers.

---

## Error Shape

```typescript
interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  trace_id: string;
}

// Common error codes:
// COLLECTION_NOT_FOUND, COLLECTION_NAME_INVALID, COLLECTION_NAME_CONFLICT
// DOCUMENT_NOT_FOUND, FILE_FORMAT_NOT_SUPPORTED, FILE_TOO_LARGE
// DUPLICATE_DOCUMENT, JOB_NOT_FOUND, PROVIDER_NOT_FOUND
// KEY_MANAGER_UNAVAILABLE, SETTINGS_VALIDATION_ERROR, TRACE_NOT_FOUND
// NO_COLLECTIONS, CIRCUIT_OPEN, SERVICE_UNAVAILABLE
```

---

## File Upload Constraints

```typescript
const UPLOAD_CONSTRAINTS = {
  maxSizeBytes: 50 * 1024 * 1024,                    // 50 MB (client-side guard)
  allowedExtensions: ['pdf', 'md', 'txt', 'rst'],    // constitution V allowlist
  accept: {                                           // react-dropzone accept prop
    'application/pdf': ['.pdf'],
    'text/markdown': ['.md'],
    'text/plain': ['.txt'],
    'text/x-rst': ['.rst'],
  },
} as const;
```

---

## Confidence Tier Mapping

```typescript
// confidence event: { type: "confidence", score: number } — score is integer 0–100
type ConfidenceTier = "green" | "yellow" | "red";

const getConfidenceTier = (score: number): ConfidenceTier => {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "red";
};
```
