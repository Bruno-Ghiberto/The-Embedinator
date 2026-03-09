# Spec 09: Frontend Architecture -- Implementation Context

## Implementation Scope

### Files to Create

```
frontend/
  app/
    layout.tsx
    chat/page.tsx
    collections/page.tsx
    documents/[id]/page.tsx
    settings/page.tsx
    observability/page.tsx
  components/
    Navigation.tsx
    ChatPanel.tsx
    ChatInput.tsx
    ChatSidebar.tsx
    CitationTooltip.tsx
    ConfidenceIndicator.tsx
    CollectionList.tsx
    CollectionCard.tsx
    CreateCollectionDialog.tsx
    DocumentList.tsx
    DocumentUploader.tsx
    ModelSelector.tsx
    ProviderHub.tsx
    TraceTable.tsx
    LatencyChart.tsx
    ConfidenceDistribution.tsx
    HealthDashboard.tsx
    CollectionStats.tsx
  lib/
    api.ts
    types.ts
  hooks/
    useStreamChat.ts
    useCollections.ts
    useModels.ts
    useTraces.ts
  next.config.ts
  package.json
  tailwind.config.ts
  tsconfig.json
```

## Code Specifications

### Shared Types (`lib/types.ts`)

```typescript
// --- Chat ---
export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: { score: number; level: "high" | "moderate" | "low" };
  groundedness?: { supported: number; unsupported: number; contradicted: number };
  isStreaming?: boolean;
}

export interface Citation {
  index: number;
  chunkId: string;
  source: string;
  page: number;
  breadcrumb: string;
  text?: string;
}

export interface ChatRequest {
  message: string;
  collection_ids: string[];
  llm_model: string;
  embed_model: string;
  session_id?: string;
}

// --- Collections ---
export interface Collection {
  id: string;
  name: string;
  description: string | null;
  embeddingModel: string;
  chunkProfile: string;
  documentCount: number;
  totalChunks: number;
  createdAt: string;
}

export interface CreateCollectionRequest {
  name: string;
  description?: string;
  embedding_model: string;
  chunk_profile?: string;
}

// --- Documents ---
export interface Document {
  id: string;
  collectionId: string;
  filename: string;
  fileHash: string;
  status: "pending" | "ingesting" | "completed" | "failed" | "duplicate";
  chunkCount: number;
  ingestedAt: string | null;
}

export type IngestionJobStatus = "started" | "streaming" | "embedding" | "completed" | "failed" | "paused";

export interface IngestionJob {
  id: string;
  documentId: string;
  status: IngestionJobStatus;
  startedAt: string;
  finishedAt: string | null;
  errorMsg: string | null;
  chunksProcessed: number;
  chunksSkipped: number;
}

export interface IngestionResponse {
  job_id: string;
  document_id: string;
  status: "started" | "duplicate";
}

// --- Models ---
export interface ModelInfo {
  name: string;
  provider: string;
  size: string | null;
  quantization: string | null;
  context_length: number | null;
  dims: number | null;
}

// --- Providers ---
export interface Provider {
  name: string;
  isActive: boolean;
  hasKey: boolean;
  baseUrl: string | null;
  modelCount: number;
}

// --- Observability ---
export interface QueryTrace {
  id: string;
  sessionId: string;
  query: string;
  collectionsSearched: string[];
  metaReasoningTriggered: boolean;
  latencyMs: number;
  llmModel: string;
  confidenceScore: number | null;
  createdAt: string;
}

export interface QueryTraceDetail extends QueryTrace {
  subQuestions: string[];
  chunksRetrieved: { chunkId: string; score: number; collection: string; sourceFile: string }[];
  embedModel: string;
}

export interface HealthStatus {
  qdrant: "ok" | "error";
  ollama: "ok" | "error";
  sqlite: "ok" | "error";
  qdrant_latency_ms: number | null;
  ollama_latency_ms: number | null;
  timestamp: string;
}

export interface SystemStats {
  total_collections: number;
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  avg_latency_ms: number;
  avg_confidence: number;
  meta_reasoning_rate: number;
}

// --- Settings ---
export interface Settings {
  default_llm_model: string;
  default_embed_model: string;
  default_provider: string;
  parent_chunk_size: number;
  child_chunk_size: number;
  max_iterations: number;
  max_tool_calls: number;
  confidence_threshold: number;
  groundedness_check_enabled: boolean;
  citation_alignment_threshold: number;
}

// --- Errors ---
export interface ApiErrorResponse {
  detail: string;
  code: string;
  trace_id?: string;
}

export class ApiError extends Error {
  constructor(public status: number, public body: string) {
    super(`API Error ${status}: ${body}`);
  }
}
```

### API Client (`lib/api.ts`)

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// --- Collections ---
export async function getCollections(): Promise<Collection[]> {
  const res = await fetch(`${API_BASE}/api/collections`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function createCollection(data: CreateCollectionRequest): Promise<Collection> {
  const res = await fetch(`${API_BASE}/api/collections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function deleteCollection(id: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/collections/${id}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}

// --- Documents ---
export async function getDocuments(collectionId: string): Promise<Document[]> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/documents`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function ingestFile(collectionId: string, file: File): Promise<IngestionResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/ingest`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function getIngestionJob(collectionId: string, jobId: string): Promise<IngestionJob> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/ingest/${jobId}`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function deleteDocument(collectionId: string, docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}

// --- Chat (SSE streaming) ---
export function streamChat(
  request: ChatRequest,
  callbacks: {
    onToken: (content: string) => void;
    onCitation: (citation: Citation) => void;
    onStatus: (node: string, data?: Record<string, unknown>) => void;
    onConfidence: (score: number, level: string) => void;
    onDone: (latencyMs: number, traceId: string) => void;
    onError: (message: string, code: string) => void;
  }
): AbortController {
  const controller = new AbortController();
  fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
    signal: controller.signal,
  }).then(async (res) => {
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
        if (!line.startsWith("data: ")) continue;
        const event = JSON.parse(line.slice(6));
        switch (event.type) {
          case "token": callbacks.onToken(event.content); break;
          case "citation": callbacks.onCitation(event); break;
          case "status": callbacks.onStatus(event.node, event); break;
          case "confidence": callbacks.onConfidence(event.score, event.level); break;
          case "done": callbacks.onDone(event.latency_ms, event.trace_id); break;
          case "error": callbacks.onError(event.message, event.code); break;
        }
      }
    }
  });
  return controller;
}

// --- Models ---
export async function getLLMModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/api/models/llm`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function getEmbedModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/api/models/embed`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

// --- Providers ---
export async function getProviders(): Promise<Provider[]> {
  const res = await fetch(`${API_BASE}/api/providers`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function setProviderKey(name: string, apiKey: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/providers/${name}/key`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ api_key: apiKey }),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}

export async function deleteProviderKey(name: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/providers/${name}/key`, { method: "DELETE" });
  if (!res.ok) throw new ApiError(res.status, await res.text());
}

// --- Settings ---
export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function updateSettings(settings: Partial<Settings>): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

// --- Observability ---
export async function getTraces(page: number, limit: number, sessionId?: string): Promise<{ traces: QueryTrace[]; total: number }> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) });
  if (sessionId) params.set("session_id", sessionId);
  const res = await fetch(`${API_BASE}/api/traces?${params}`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}

export async function getStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

### Component Props Interfaces

```typescript
// ChatPanel
interface ChatPanelProps {
  sessionId: string | null;
  selectedCollections: string[];
  llmModel: string;
  embedModel: string;
  onSessionCreated: (sessionId: string) => void;
}

// CollectionCard
interface CollectionCardProps {
  collection: Collection;
  onDelete: (id: string) => void;
  onNavigate: (id: string) => void;
}

// DocumentUploader
interface DocumentUploaderProps {
  collectionId: string;
  onUploadComplete: () => void;
}

// ModelSelector
interface ModelSelectorProps {
  type: "llm" | "embed";
  value: string;
  onChange: (model: string) => void;
}

// ProviderHub
interface ProviderHubProps {
  onProviderChange: () => void;
}

// TraceTable
interface TraceTableProps {
  page: number;
  limit: number;
  sessionFilter?: string;
  onPageChange: (page: number) => void;
}
```

## Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

### next.config.ts
```typescript
const nextConfig = {
  reactStrictMode: true,
  experimental: {
    turbopack: true,
  },
};
export default nextConfig;
```

### Package Dependencies (package.json)
```json
{
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "typescript": "^5.7.0",
    "tailwindcss": "^4.0.0",
    "recharts": "^2.0.0",
    "@radix-ui/react-tooltip": "^1.0.0",
    "@radix-ui/react-dialog": "^1.0.0",
    "@radix-ui/react-select": "^2.0.0",
    "swr": "^2.0.0",
    "react-dropzone": "^14.0.0"
  },
  "devDependencies": {
    "vitest": "^3.0.0",
    "@playwright/test": "^1.50.0",
    "@testing-library/react": "^16.0.0"
  }
}
```

## Error Handling

- All API functions in `lib/api.ts` throw `ApiError` on non-OK HTTP responses
- Components display user-facing error messages from the `detail` field of `ApiErrorResponse`
- SSE stream errors are handled via the `onError` callback, displaying the error message in the chat panel
- Network failures show a generic "Connection error -- please check that the backend is running" message
- File upload errors display specific messages: "Unsupported file type", "File too large", "File already ingested"
- SWR hooks surface errors via the `isError` state for components to render error states

## Testing Requirements

### Unit Tests (vitest + React Testing Library)
- `lib/api.ts`: Test each API function with mocked fetch responses
- `lib/api.ts`: Test SSE stream parsing with mock ReadableStream
- `components/ConfidenceIndicator`: Test color mapping for score ranges
- `components/CitationTooltip`: Test tooltip rendering with citation data
- `components/CollectionCard`: Test render with collection data, delete callback
- `components/DocumentUploader`: Test drag-drop interaction, upload flow
- `components/ModelSelector`: Test dropdown rendering and selection

### E2E Tests (Playwright)
- Chat flow: Send a message, verify streaming response appears, check citation tooltips
- Collection CRUD: Create collection, verify it appears in list, delete it
- File upload: Upload a file, verify progress polling, check document appears in list
- Settings: Change a setting, save, verify persistence
- Navigation: Verify all page links work correctly

## Done Criteria

1. All five pages (`/chat`, `/collections`, `/documents/[id]`, `/settings`, `/observability`) render without errors
2. `lib/api.ts` contains typed functions for every backend endpoint
3. `lib/types.ts` contains all shared TypeScript interfaces matching backend Pydantic schemas
4. Chat page streams tokens via SSE and accumulates them into the message thread in real time
5. Citation markers render inline and show Radix Tooltip on hover with chunk text, source, page, breadcrumb
6. ConfidenceIndicator renders correct color: green (0.7-1.0), yellow (0.4-0.69), red (0.0-0.39)
7. Collection creation validates name format (`^[a-z0-9][a-z0-9_-]*$`) before submission
8. File upload uses react-dropzone and polls job status every 2 seconds until terminal state
9. ModelSelector populates options from `/api/models/llm` and `/api/models/embed` via SWR
10. ProviderHub displays provider list, supports API key entry with masked display, shows connection status
11. Observability page renders latency histogram, confidence distribution, health cards, and paginated trace table
12. Selected collections and models are persisted in URL query params
13. All vitest unit tests pass
14. TypeScript compiles with zero errors in strict mode
