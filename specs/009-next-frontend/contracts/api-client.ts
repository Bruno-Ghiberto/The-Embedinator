/**
 * API Client Contract — spec-09 Frontend
 *
 * This file defines the TypeScript signatures for all API functions in
 * frontend/lib/api.ts. It is a specification contract, not executable code.
 *
 * Backend source: spec-08-api (backend/agent/schemas.py + backend/api/*.py)
 * Verified: 2026-03-16
 *
 * IMPORTANT NOTES FOR IMPLEMENTORS:
 * - All HTTP is against NEXT_PUBLIC_API_URL (default: http://localhost:8000)
 * - Chat streaming uses application/x-ndjson — raw JSON lines, NO "data:" prefix
 * - Settings endpoint is PUT (not PATCH), body fields are all optional
 * - isStreaming must be released on "done", "error", AND "clarification" events
 * - Provider raw API keys are NEVER returned by backend (has_key: bool only)
 * - source_removed: bool in Citation must trigger "source removed" UI indicator
 */

// ─── Base ──────────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    message: string,
    public readonly traceId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// ─── Shared types ──────────────────────────────────────────────────────────

export interface Collection {
  id: string;
  name: string;
  description: string | null;
  embedding_model: string;
  chunk_profile: string;
  document_count: number;
  created_at: string;
}

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  status: "pending" | "ingesting" | "completed" | "failed" | "duplicate";
  chunk_count: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface IngestionJob {
  job_id: string;
  document_id: string;
  status: "pending" | "started" | "streaming" | "embedding" | "completed" | "failed" | "paused";
  chunks_processed: number;
  chunks_total: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Citation {
  passage_id: string;
  document_id: string;
  document_name: string;
  start_offset: number;
  end_offset: number;
  text: string;
  relevance_score: number;   // float 0.0–1.0
  source_removed: boolean;   // CONSTITUTION IV: render "source removed" badge when true
  // NOTE: `page: int | None` and `breadcrumb: str` exist in the backend RetrievedChunk
  // (searcher.py) and Qdrant payload but are NOT currently included in the Citation
  // model (schemas.py). CitationTooltip renders document_name + text only.
  // When the backend Citation schema is extended, add: page?: number; breadcrumb?: string;
}

export interface ModelInfo {
  name: string;
  provider: string;
  model_type: "llm" | "embed";
  size_gb: number | null;
  quantization: string | null;
  context_length: number | null;
}

export interface Provider {
  name: string;
  is_active: boolean;
  has_key: boolean;          // never display raw key; show "••••••••" when true
  base_url: string | null;
  model_count: number;
}

export interface Settings {
  default_llm_model: string;
  default_embed_model: string;
  confidence_threshold: number;          // integer 0–100
  groundedness_check_enabled: boolean;
  citation_alignment_threshold: number;
  parent_chunk_size: number;
  child_chunk_size: number;
}

export interface QueryTrace {
  id: string;
  session_id: string;
  query: string;
  collections_searched: string[];
  confidence_score: number | null;       // integer 0–100
  latency_ms: number;
  llm_model: string | null;
  meta_reasoning_triggered: boolean;
  created_at: string;
}

export interface QueryTraceDetail extends QueryTrace {
  sub_questions: string[];
  chunks_retrieved: Record<string, unknown>[];
  reasoning_steps: Record<string, unknown>[];
  strategy_switches: Record<string, unknown>[];
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  services: Array<{
    name: string;
    status: "ok" | "error";
    latency_ms: number | null;
    error_message: string | null;
  }>;
}

export interface SystemStats {
  total_collections: number;
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  avg_confidence: number;
  avg_latency_ms: number;
  meta_reasoning_rate: number;
}

// ─── NDJSON stream types ───────────────────────────────────────────────────

export type NdjsonEvent =
  | { type: "session";        session_id: string }
  | { type: "status";         node: string }
  | { type: "chunk";          text: string }            // field is "text", NOT "content"
  | { type: "clarification";  question: string }        // stream ends here; no "done" follows
  | { type: "citation";       citations: Citation[] }
  | { type: "meta_reasoning"; strategies_attempted: string[] }
  | { type: "confidence";     score: number }           // INTEGER 0–100
  | { type: "groundedness";   overall_grounded: boolean; supported: number; unsupported: number; contradicted: number }
  | { type: "done";           latency_ms: number; trace_id: string }
  | { type: "error";          message: string; code: string; trace_id: string };

export interface StreamChatCallbacks {
  onSession?: (sessionId: string) => void;
  onStatus?: (node: string) => void;
  onToken: (text: string) => void;
  onClarification?: (question: string) => void;        // releases isStreaming
  onCitation: (citations: Citation[]) => void;
  onMetaReasoning?: (strategiesAttempted: string[]) => void;
  onConfidence: (score: number) => void;
  onGroundedness?: (data: { overall_grounded: boolean; supported: number; unsupported: number; contradicted: number }) => void;
  onDone: (latencyMs: number, traceId: string) => void; // releases isStreaming
  onError: (message: string, code: string, traceId?: string) => void; // releases isStreaming
}

export interface ChatRequest {
  message: string;             // 1–2000 chars
  collection_ids: string[];    // required, non-empty
  llm_model?: string;          // default: "qwen2.5:7b"
  embed_model?: string | null;
  session_id?: string | null;
}

// ─── Upload constraints ────────────────────────────────────────────────────

export const UPLOAD_CONSTRAINTS = {
  maxSizeBytes: 50 * 1024 * 1024,                      // 50 MB client-side guard
  allowedExtensions: ["pdf", "md", "txt", "rst"] as const, // constitution V allowlist
} as const;

// ─── Collections ──────────────────────────────────────────────────────────

export declare function getCollections(): Promise<Collection[]>;
// GET /api/collections → { collections: Collection[] }

export declare function createCollection(data: {
  name: string;
  description?: string | null;
  embedding_model?: string | null;
  chunk_profile?: string | null;
}): Promise<Collection>;
// POST /api/collections → Collection (201)
// Throws ApiError with code COLLECTION_NAME_CONFLICT (409) on duplicate name

export declare function deleteCollection(collectionId: string): Promise<void>;
// DELETE /api/collections/{collection_id} → 204

// ─── Documents ────────────────────────────────────────────────────────────

export declare function getDocuments(collectionId: string): Promise<Document[]>;
// GET /api/documents?collection_id={collectionId} → { documents: Document[] }

export declare function deleteDocument(docId: string): Promise<void>;
// DELETE /api/documents/{doc_id} → 204

// ─── Ingestion ────────────────────────────────────────────────────────────

export declare function ingestFile(
  collectionId: string,
  file: File,
): Promise<IngestionJob>;
// POST /api/collections/{collectionId}/ingest (multipart/form-data, field: "file")
// → IngestionJob (202)
// Client-side validation MUST happen before calling this function:
//   - file.size <= UPLOAD_CONSTRAINTS.maxSizeBytes
//   - extension in UPLOAD_CONSTRAINTS.allowedExtensions

export declare function getIngestionJob(
  collectionId: string,
  jobId: string,
): Promise<IngestionJob>;
// GET /api/collections/{collectionId}/ingest/{jobId}
// Poll every 2s until status in ["completed", "failed"]

// ─── Chat streaming ───────────────────────────────────────────────────────

export declare function streamChat(
  request: ChatRequest,
  callbacks: StreamChatCallbacks,
): AbortController;
// POST /api/chat → application/x-ndjson StreamingResponse
//
// Implementation MUST:
// 1. Use ReadableStream + TextDecoder + line-by-line JSON.parse()
// 2. NOT strip any "data:" prefix (NDJSON has none)
// 3. Call callbacks.onClarification + release isStreaming on "clarification" event
//    (no "done" follows a clarification — isStreaming would permanently lock otherwise)
// 4. Return AbortController so caller can abort on page navigation

// ─── Models ───────────────────────────────────────────────────────────────

export declare function getLLMModels(): Promise<ModelInfo[]>;
// GET /api/models/llm → { models: ModelInfo[] }

export declare function getEmbedModels(): Promise<ModelInfo[]>;
// GET /api/models/embed → { models: ModelInfo[] }

// ─── Providers ────────────────────────────────────────────────────────────

export declare function getProviders(): Promise<Provider[]>;
// GET /api/providers → { providers: Provider[] }

export declare function setProviderKey(
  providerName: string,
  apiKey: string,
): Promise<{ name: string; has_key: true }>;
// PUT /api/providers/{name}/key  body: { api_key: string }

export declare function deleteProviderKey(
  providerName: string,
): Promise<{ name: string; has_key: false }>;
// DELETE /api/providers/{name}/key

// ─── Settings ─────────────────────────────────────────────────────────────

export declare function getSettings(): Promise<Settings>;
// GET /api/settings → Settings

export declare function updateSettings(
  data: Partial<Settings>,
): Promise<Settings>;
// PUT /api/settings (NOT PATCH) with partial body → Settings
// Show Toast on success/error — NO optimistic UI

// ─── Traces ───────────────────────────────────────────────────────────────

export declare function getTraces(params?: {
  session_id?: string;
  collection_id?: string;
  min_confidence?: number;
  max_confidence?: number;
  limit?: number;      // default 20, max 100
  offset?: number;     // default 0
}): Promise<{ traces: QueryTrace[]; total: number; limit: number; offset: number }>;
// GET /api/traces

export declare function getTraceDetail(traceId: string): Promise<QueryTraceDetail>;
// GET /api/traces/{trace_id}

// ─── Health & Stats ───────────────────────────────────────────────────────

export declare function getHealth(): Promise<HealthStatus>;
// GET /api/health → HealthStatus (200 healthy, 503 degraded)

export declare function getStats(): Promise<SystemStats>;
// GET /api/stats → SystemStats
