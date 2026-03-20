// ─── Core Entities ────────────────────────────────────────────────────────

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
  status: DocumentStatus;
  chunk_count: number | null;
  created_at: string;
  updated_at: string | null;
}

export type DocumentStatus =
  | "pending"
  | "ingesting"
  | "completed"
  | "failed"
  | "duplicate";

export interface IngestionJob {
  job_id: string;
  document_id: string;
  status: IngestionJobStatus;
  chunks_processed: number;
  chunks_total: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export type IngestionJobStatus =
  | "pending"
  | "started"
  | "streaming"
  | "embedding"
  | "completed"
  | "failed"
  | "paused";

export const TERMINAL_JOB_STATES: IngestionJobStatus[] = [
  "completed",
  "failed",
];

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: number;
  groundedness?: GroundednessData;
  clarification?: string;
  isStreaming: boolean;
  traceId?: string;
}

export interface Citation {
  passage_id: string;
  document_id: string;
  document_name: string;
  start_offset: number;
  end_offset: number;
  text: string;
  relevance_score: number;
  source_removed: boolean;
}

export interface GroundednessData {
  overall_grounded: boolean;
  supported: number;
  unsupported: number;
  contradicted: number;
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
  has_key: boolean;
  base_url: string | null;
  model_count: number;
}

export interface Settings {
  default_llm_model: string;
  default_embed_model: string;
  confidence_threshold: number;
  groundedness_check_enabled: boolean;
  citation_alignment_threshold: number;
  parent_chunk_size: number;
  child_chunk_size: number;
}

export interface SettingsUpdateRequest {
  default_llm_model?: string;
  default_embed_model?: string;
  confidence_threshold?: number;
  groundedness_check_enabled?: boolean;
  citation_alignment_threshold?: number;
  parent_chunk_size?: number;
  child_chunk_size?: number;
}

export interface QueryTrace {
  id: string;
  session_id: string;
  query: string;
  collections_searched: string[];
  confidence_score: number | null;
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
  stage_timings?: Record<string, { duration_ms: number; failed?: boolean }>;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  services: HealthService[];
}

export interface HealthService {
  name: string;
  status: "ok" | "error";
  latency_ms: number | null;
  error_message: string | null;
}

// ─── Backend Status (FR-046) ──────────────────────────────────────────────

export type BackendStatus = "unreachable" | "degraded" | "ready";

export interface BackendHealthServiceStatus {
  name: string;
  status: "ok" | "error";
  latency_ms: number | null;
  error_message: string | null;
  models?: Record<string, boolean>;
}

export interface BackendHealthResponse {
  status: "healthy" | "degraded" | "starting";
  services: BackendHealthServiceStatus[];
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

// ─── NDJSON Stream Types ──────────────────────────────────────────────────

export type NdjsonEvent =
  | { type: "session"; session_id: string }
  | { type: "status"; node: string }
  | { type: "chunk"; text: string }
  | { type: "clarification"; question: string }
  | { type: "citation"; citations: Citation[] }
  | { type: "meta_reasoning"; strategies_attempted: string[] }
  | { type: "confidence"; score: number }
  | {
      type: "groundedness";
      overall_grounded: boolean;
      supported: number;
      unsupported: number;
      contradicted: number;
    }
  | { type: "done"; latency_ms: number; trace_id: string }
  | { type: "error"; message: string; code: string; trace_id: string };

export interface StreamChatCallbacks {
  onSession?: (sessionId: string) => void;
  onStatus?: (node: string) => void;
  onToken: (text: string) => void;
  onClarification?: (question: string) => void;
  onCitation: (citations: Citation[]) => void;
  onMetaReasoning?: (strategiesAttempted: string[]) => void;
  onConfidence: (score: number) => void;
  onGroundedness?: (data: GroundednessData) => void;
  onDone: (latencyMs: number, traceId: string) => void;
  onError: (message: string, code: string, traceId?: string) => void;
}

export interface ChatRequest {
  message: string;
  collection_ids: string[];
  llm_model?: string;
  embed_model?: string | null;
  session_id?: string | null;
}

// ─── Upload Constraints ───────────────────────────────────────────────────

export const UPLOAD_CONSTRAINTS = {
  maxSizeBytes: 50 * 1024 * 1024,
  allowedExtensions: ["pdf", "md", "txt", "rst"] as const,
  accept: {
    "application/pdf": [".pdf"],
    "text/markdown": [".md"],
    "text/plain": [".txt"],
    "text/x-rst": [".rst"],
  },
} as const;

// ─── Confidence Tier Mapping ──────────────────────────────────────────────

export type ConfidenceTier = "green" | "yellow" | "red";

export const getConfidenceTier = (score: number): ConfidenceTier => {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "red";
};

// ─── Error Types ──────────────────────────────────────────────────────────

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  trace_id: string;
}
