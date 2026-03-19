import type {
  Collection,
  Document,
  IngestionJob,
  ChatRequest,
  StreamChatCallbacks,
  NdjsonEvent,
  ModelInfo,
  Provider,
  Settings,
  QueryTrace,
  QueryTraceDetail,
  HealthStatus,
  SystemStats,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── ApiError ─────────────────────────────────────────────────────────────

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

async function throwApiError(res: Response): Promise<never> {
  const body = await res
    .json()
    .catch(() => ({ error: { code: "UNKNOWN", message: res.statusText } }));
  throw new ApiError(
    res.status,
    body.error?.code || "UNKNOWN",
    body.error?.message || res.statusText,
    body.trace_id,
  );
}

// ─── Collections ──────────────────────────────────────────────────────────

export async function getCollections(): Promise<Collection[]> {
  const res = await fetch(`${API_BASE}/api/collections`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.collections;
}

export async function createCollection(data: {
  name: string;
  description?: string | null;
  embedding_model?: string | null;
  chunk_profile?: string | null;
}): Promise<Collection> {
  const res = await fetch(`${API_BASE}/api/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function deleteCollection(collectionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
}

// ─── Documents ────────────────────────────────────────────────────────────

export async function getDocuments(collectionId: string): Promise<Document[]> {
  const res = await fetch(
    `${API_BASE}/api/documents?collection_id=${collectionId}`,
  );
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.documents;
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
}

// ─── Ingestion ────────────────────────────────────────────────────────────

export async function ingestFile(
  collectionId: string,
  file: File,
): Promise<IngestionJob> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(
    `${API_BASE}/api/collections/${collectionId}/ingest`,
    {
      method: "POST",
      body: formData,
    },
  );
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function getIngestionJob(
  collectionId: string,
  jobId: string,
): Promise<IngestionJob> {
  const res = await fetch(
    `${API_BASE}/api/collections/${collectionId}/ingest/${jobId}`,
  );
  if (!res.ok) await throwApiError(res);
  return res.json();
}

// ─── Chat Streaming (NDJSON) ──────────────────────────────────────────────

export function streamChat(
  request: ChatRequest,
  callbacks: StreamChatCallbacks,
): AbortController {
  const controller = new AbortController();
  fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: controller.signal,
  })
    .then(async (res) => {
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        callbacks.onError(
          body.error?.message || res.statusText,
          body.error?.code || "UNKNOWN",
          body.trace_id,
        );
        return;
      }
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (!line.trim()) continue;
          const event: NdjsonEvent = JSON.parse(line);
          switch (event.type) {
            case "session":
              callbacks.onSession?.(event.session_id);
              break;
            case "status":
              callbacks.onStatus?.(event.node);
              break;
            case "chunk":
              callbacks.onToken(event.text);
              break;
            case "clarification":
              callbacks.onClarification?.(event.question);
              break;
            case "citation":
              callbacks.onCitation(event.citations);
              break;
            case "meta_reasoning":
              callbacks.onMetaReasoning?.(event.strategies_attempted);
              break;
            case "confidence":
              callbacks.onConfidence(event.score);
              break;
            case "groundedness":
              callbacks.onGroundedness?.(event);
              break;
            case "done":
              callbacks.onDone(event.latency_ms, event.trace_id);
              break;
            case "error":
              callbacks.onError(event.message, event.code, event.trace_id);
              break;
          }
        }
      }
    })
    .catch((err) => {
      if (err.name !== "AbortError") {
        callbacks.onError(
          "Connection error -- please check that the backend is running",
          "NETWORK_ERROR",
        );
      }
    });
  return controller;
}

// ─── Models ───────────────────────────────────────────────────────────────

export async function getLLMModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/api/models/llm`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.models;
}

export async function getEmbedModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/api/models/embed`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.models;
}

// ─── Providers ────────────────────────────────────────────────────────────

export async function getProviders(): Promise<Provider[]> {
  const res = await fetch(`${API_BASE}/api/providers`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.providers;
}

export async function setProviderKey(
  providerName: string,
  apiKey: string,
): Promise<{ name: string; has_key: true }> {
  const res = await fetch(`${API_BASE}/api/providers/${providerName}/key`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function deleteProviderKey(
  providerName: string,
): Promise<{ name: string; has_key: false }> {
  const res = await fetch(`${API_BASE}/api/providers/${providerName}/key`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

// ─── Settings ─────────────────────────────────────────────────────────────

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`);
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function updateSettings(
  data: Partial<Settings>,
): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
}

// ─── Traces ───────────────────────────────────────────────────────────────

export async function getTraces(params?: {
  session_id?: string;
  collection_id?: string;
  min_confidence?: number;
  max_confidence?: number;
  limit?: number;
  offset?: number;
}): Promise<{
  traces: QueryTrace[];
  total: number;
  limit: number;
  offset: number;
}> {
  const searchParams = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) searchParams.set(key, String(value));
    }
  }
  const res = await fetch(`${API_BASE}/api/traces?${searchParams}`);
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function getTraceDetail(
  traceId: string,
): Promise<QueryTraceDetail> {
  const res = await fetch(`${API_BASE}/api/traces/${traceId}`);
  if (!res.ok) await throwApiError(res);
  return res.json();
}

// ─── Health & Stats ───────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) await throwApiError(res);
  return res.json();
}

export async function getStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) await throwApiError(res);
  return res.json();
}
