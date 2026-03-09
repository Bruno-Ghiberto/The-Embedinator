# Spec 09: Frontend Architecture -- Feature Specification Context

## Feature Description

The Embedinator frontend is a Next.js 16 (App Router) single-page application that provides the complete user interface for the RAG system. It includes five primary pages: `/chat` for conversational RAG queries with SSE streaming, `/collections` for managing document collections, `/documents/[collectionId]` for per-collection document management, `/settings` for system configuration and provider API key management, and `/observability` for query trace analysis and system health monitoring.

The frontend communicates with the FastAPI backend exclusively through a centralized API client (`lib/api.ts`), using `fetch` for standard CRUD operations, SSE (`ReadableStream`) for streaming chat responses, and SWR for cached data fetching with auto-revalidation.

## Requirements

### Functional Requirements

1. **Chat Page (`/chat`)**:
   - Display a message thread with user and assistant message bubbles
   - Stream assistant responses token-by-token via SSE from `POST /api/chat`
   - Render inline citation markers `[1]`, `[2]`, etc., with hover tooltips showing chunk text, source file, page number, and breadcrumb
   - Display a confidence indicator (green/yellow/red dot) with score tooltip after each assistant message
   - Sidebar with multi-select collection picker and model selectors (LLM + embedding model dropdowns)
   - Text input area with send button and session controls
   - Selected collections and models stored in URL query params for shareability

2. **Collections Page (`/collections`)**:
   - Grid of collection cards showing name, description, doc count, chunk count, embedding model
   - Create collection dialog with name input (validated: `^[a-z0-9][a-z0-9_-]*$`), description, embedding model picker
   - Delete collection action with confirmation
   - Navigate to document view per collection

3. **Documents Page (`/documents/[collectionId]`)**:
   - Table of documents with status badges (pending, ingesting, completed, failed, duplicate)
   - Document upload via drag-drop zone (react-dropzone)
   - Upload progress bar with job status polling via `GET /api/collections/{id}/ingest/{job_id}`
   - Delete document action

4. **Settings Page (`/settings`)**:
   - Settings form for agent limits (max iterations, max tool calls), chunk sizes (parent/child), confidence threshold
   - Provider Hub component: list of providers, API key input (masked), connection status indicator
   - Uses React Hook Form with SWR cache integration

5. **Observability Page (`/observability`)**:
   - Service health dashboard: Qdrant, Ollama, SQLite status cards with latency gauges
   - Query latency histogram (last 24h) using recharts
   - Confidence distribution bar chart by score range
   - Paginated trace table with expandable detail rows showing tool call breakdown
   - Collection stats: per-collection doc + chunk counts

### Non-Functional Requirements

- Responsive design with Tailwind CSS v4
- Accessible UI primitives via Radix UI (tooltips, dialogs, selects)
- Type-safe with TypeScript 5.7
- First contentful paint under 1 second
- SSE first-token display within 200-500ms of query submission

## Key Technical Details

### TypeScript Component Interfaces

```typescript
// Chat components
interface ChatPanelProps {
  sessionId: string | null;
  selectedCollections: string[];
  llmModel: string;
  embedModel: string;
  onSessionCreated: (sessionId: string) => void;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  confidence?: { score: number; level: "high" | "moderate" | "low" };
  groundedness?: { supported: number; unsupported: number; contradicted: number };
  isStreaming?: boolean;
}

interface Citation {
  index: number;
  chunkId: string;
  source: string;
  page: number;
  breadcrumb: string;
  text?: string;  // populated on hover via lazy fetch
}

// Collection components
interface CollectionCardProps {
  collection: Collection;
  onDelete: (id: string) => void;
  onNavigate: (id: string) => void;
}

interface Collection {
  id: string;
  name: string;
  description: string | null;
  embeddingModel: string;
  chunkProfile: string;
  documentCount: number;
  totalChunks: number;
  createdAt: string;
}

// Document components
interface DocumentUploaderProps {
  collectionId: string;
  onUploadComplete: () => void;
}

interface DocumentUploaderState {
  file: File | null;
  uploading: boolean;
  jobId: string | null;
  jobStatus: IngestionJobStatus | null;
  error: string | null;
}

type IngestionJobStatus = "started" | "streaming" | "embedding" | "completed" | "failed" | "paused";

// Model selector
interface ModelSelectorProps {
  type: "llm" | "embed";
  value: string;
  onChange: (model: string) => void;
}

// Provider hub
interface ProviderHubProps {
  onProviderChange: () => void;
}

interface Provider {
  name: string;
  isActive: boolean;
  hasKey: boolean;
  baseUrl: string | null;
  modelCount: number;
}

// Observability
interface TraceTableProps {
  page: number;
  limit: number;
  sessionFilter?: string;
  onPageChange: (page: number) => void;
}

interface QueryTrace {
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
```

### State Management Strategy

| State Type | Mechanism | Scope |
|-----------|-----------|-------|
| Server data (collections, documents, models, traces) | SWR with `useSWR()` hooks | Cached, auto-revalidated |
| Chat session | React `useState` + `useRef` for SSE stream | Per-page, not persisted |
| Selected collections | URL query params (`?collections=a,b`) | Shareable, bookmarkable |
| Selected models | URL query params (`?llm=llama3.2&embed=nomic`) | Shareable, bookmarkable |
| Upload progress | React `useState` with polling interval | Per-upload lifecycle |
| Settings form | React Hook Form with SWR cache | Form-local, submitted on save |

### SSE Streaming Implementation

The `streamChat()` function in `lib/api.ts` uses `fetch` with `ReadableStream` to consume SSE events. It parses `data: {...}` lines and dispatches to typed callbacks:

```typescript
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
```

SSE event types from the backend:
- `session` -- session ID assignment
- `status` -- graph node execution updates
- `token` -- individual response tokens
- `citation` -- inline citation data
- `meta_reasoning` -- meta-reasoning strategy info
- `confidence` -- computed confidence score and level
- `groundedness` -- claim verification summary
- `done` -- completion with latency and trace ID
- `error` -- error with message and code

### Confidence Display Mapping

| Score Range | Color | Label | Icon |
|------------|-------|-------|------|
| 0.7 - 1.0 | Green | High confidence | Solid circle |
| 0.4 - 0.69 | Yellow | Moderate confidence | Half circle |
| 0.0 - 0.39 | Red | Low confidence | Empty circle |

## Dependencies

### Spec Dependencies
- **spec-08-api**: All backend API endpoints that the frontend consumes
- **spec-10-providers**: Provider listing and model APIs consumed by ModelSelector and ProviderHub
- **spec-12-errors**: Error response format for frontend error display

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `next` | `16` | React framework, App Router, Turbopack |
| `react` | `19` | UI component library |
| `typescript` | `5.7` | Type safety |
| `tailwindcss` | `4` | Utility-first CSS |
| `recharts` | `2` | Latency charts on observability page |
| `@radix-ui/react-tooltip` | `1` | Citation tooltip primitives |
| `@radix-ui/react-dialog` | `1` | Modal dialogs |
| `@radix-ui/react-select` | `2` | Dropdown selects |
| `swr` | `2` | Data fetching with cache for API calls |
| `react-dropzone` | `14` | File drag-drop upload |

### Dev/Test Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `vitest` | `>=3.0` | Frontend unit tests |
| `@playwright/test` | `>=1.50` | Frontend E2E tests |
| `@testing-library/react` | `>=16.0` | Component testing |

## Acceptance Criteria

1. All five pages render correctly and are navigable via the top navigation bar
2. Chat page streams tokens in real-time via SSE with visible first token within 500ms
3. Citations render as clickable inline markers with hover tooltips showing chunk text, source, page, breadcrumb
4. Confidence indicator displays correct color (green/yellow/red) based on score thresholds
5. Collection CRUD operations work end-to-end (create, list, delete)
6. File upload via drag-drop shows progress bar and polls job status until completion
7. Model selectors populate from `/api/models/llm` and `/api/models/embed` endpoints
8. Provider Hub shows provider status and allows API key entry (masked display)
9. Observability page displays latency histogram, confidence distribution, health status, and paginated trace table
10. Selected collections and models are persisted in URL query params
11. All SWR-backed data auto-revalidates on focus and interval
12. Responsive layout works on desktop (1024px+) and tablet (768px+)

## Architecture Reference

### Page Wireframes

**`/chat` Page:**
```
+------------------------------------------+------------------------------+
| [Logo] Chat | Collections | Docs | ...   |                              |
+------------------------------------------+                              |
|                                          | Collections:                 |
|  [ User message bubble ]                 |   [x] arca-specs             |
|                                          |   [ ] internal-docs          |
|  [ Assistant response bubble      ]      |   [ ] code-reference         |
|  [ with inline citations [1] [2] ]       |                              |
|  [ Confidence: green-dot 0.85    ]       | LLM Model:                   |
|                                          |   [llama3.2        v]        |
|  [ User message bubble ]                 |                              |
|                                          | Embed Model:                 |
|  [ Assistant streaming...         ]      |   [nomic-embed-text v]       |
|  [ cursor                         ]      |                              |
|                                          +------------------------------+
+------------------------------------------+
| [Type your message...          ] [Send]  |
+------------------------------------------+
```

**`/collections` Page:**
```
+------------------------------------------------------------------+
| [Logo] Chat | Collections | Docs | Settings | Observability       |
+------------------------------------------------------------------+
|  [+ Create Collection]                                            |
|                                                                   |
|  +--------------------+  +--------------------+  +-------------+  |
|  | arca-specs         |  | internal-docs      |  | code-ref    |  |
|  | API specifications |  | Internal guides    |  | Source code |  |
|  | 12 docs | 3,400 ch |  | 5 docs | 1,200 ch |  | 8 docs     |  |
|  | nomic-embed-text   |  | nomic-embed-text   |  | nomic-...  |  |
|  | [Upload] [Delete]  |  | [Upload] [Delete]  |  | [Upload]   |  |
|  +--------------------+  +--------------------+  +-------------+  |
+------------------------------------------------------------------+
```

### Component-to-File Mapping

| Component | File | Responsibility |
|-----------|------|---------------|
| `ChatPanel` | `components/ChatPanel.tsx` | Message thread, SSE token accumulation, inline citation rendering |
| `ChatInput` | `components/ChatInput.tsx` | Text area + send button |
| `ChatSidebar` | `components/ChatSidebar.tsx` | CollectionSelector + ModelSelector |
| `CollectionCard` | `components/CollectionCard.tsx` | Collection metadata display, delete action, document count |
| `CollectionList` | `components/CollectionList.tsx` | Grid of CollectionCards |
| `CreateCollectionDialog` | `components/CreateCollectionDialog.tsx` | Modal for collection creation |
| `DocumentUploader` | `components/DocumentUploader.tsx` | Drag-drop file upload, progress polling via `/ingest/{job_id}` |
| `DocumentList` | `components/DocumentList.tsx` | Table of documents with status badges |
| `ModelSelector` | `components/ModelSelector.tsx` | Dropdowns for LLM and embedding model |
| `CitationTooltip` | `components/CitationTooltip.tsx` | Hover tooltip showing chunk text, source file, page, breadcrumb |
| `ConfidenceIndicator` | `components/ConfidenceIndicator.tsx` | Visual confidence dot with score tooltip |
| `ProviderHub` | `components/ProviderHub.tsx` | Provider list, API key management, connection status |
| `TraceTable` | `components/TraceTable.tsx` | Paginated query trace list with expandable detail rows |
| `LatencyChart` | `components/LatencyChart.tsx` | Histogram of query latencies (recharts) |
| `ConfidenceDistribution` | `components/ConfidenceDistribution.tsx` | Bar chart by confidence score range |
| `HealthDashboard` | `components/HealthDashboard.tsx` | Service status cards + latency gauges |
| `CollectionStats` | `components/CollectionStats.tsx` | Per-collection doc + chunk counts |
| `Navigation` | `components/Navigation.tsx` | Top nav bar with logo and page links |
