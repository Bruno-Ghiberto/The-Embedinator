# Spec 09: Frontend Architecture -- Feature Specification Context

## Feature Description

The Embedinator frontend is a Next.js 16 (App Router) single-page application that provides the complete user interface for the RAG system. It includes five primary pages: `/chat` for conversational RAG queries with NDJSON streaming, `/collections` for managing document collections, `/documents/[collectionId]` for per-collection document management, `/settings` for system configuration and provider API key management, and `/observability` for query trace analysis and system health monitoring.

The frontend communicates with the FastAPI backend exclusively through a centralized API client (`lib/api.ts`), using `fetch` for standard CRUD operations, NDJSON (`ReadableStream`) for streaming chat responses (media type `application/x-ndjson`), and SWR for cached data fetching with auto-revalidation.

## Requirements

### Functional Requirements

1. **Chat Page (`/chat`)**:
   - Display a message thread with user and assistant message bubbles
   - Stream assistant responses chunk-by-chunk via NDJSON from `POST /api/chat`
   - Render inline citation markers `[1]`, `[2]`, etc., with hover tooltips showing chunk text, source file, page number, and breadcrumb
   - Display a confidence indicator (green/yellow/red dot) with score tooltip after each assistant message
   - Sidebar with multi-select collection picker and model selectors (LLM + embedding model dropdowns)
   - Text input area with send button and session controls
   - Selected collections and models stored in URL query params for shareability

2. **Collections Page (`/collections`)**:
   - Grid of collection cards showing name, description, doc count, embedding model, chunk profile
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
- NDJSON first-chunk display within 200-500ms of query submission
- Heavy components (recharts, react-dropzone) loaded via `next/dynamic` to reduce initial bundle
- Radix UI packages imported via direct subpath or `optimizePackageImports` in `next.config.js` (not barrel imports)
- SWR used for all server data fetching (no raw `useEffect`+`fetch` patterns)
- No component definitions inside render functions (prevents remount on every parent render)

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
  // confidence.score is INTEGER 0-100 (matches backend ConfidenceEvent.score: int)
  confidence?: { score: number; level: "high" | "moderate" | "low" };
  groundedness?: { overallGrounded: boolean; supported: number; unsupported: number; contradicted: number };
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
  chunkProfile: string;   // maps to backend chunk_profile field
  documentCount: number;  // maps to backend document_count field
  createdAt: string;
  // NOTE: totalChunks is NOT returned by GET /api/collections — omit from this interface
  // Per-collection chunk totals are available via GET /api/stats (StatsResponse)
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

// All statuses used by backend IngestionPipeline and stored in ingestion_jobs table
// "pending" is the DB default; "streaming"/"embedding"/"paused" are mid-pipeline states
type IngestionJobStatus =
  | "pending"
  | "started"
  | "streaming"
  | "embedding"
  | "completed"
  | "failed"
  | "paused";

// Model selector
interface ModelSelectorProps {
  type: "llm" | "embed";
  value: string;
  onChange: (model: string) => void;
}

// Provider hub — maps to backend ProviderDetailResponse
interface ProviderHubProps {
  onProviderChange: () => void;
}

interface Provider {
  name: string;
  isActive: boolean;  // maps to is_active
  hasKey: boolean;    // maps to has_key
  baseUrl: string | null;  // maps to base_url
  modelCount: number;      // maps to model_count
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
  confidenceScore: number | null;  // INTEGER 0-100 from backend
  createdAt: string;
}
```

### State Management Strategy

| State Type | Mechanism | Scope |
|-----------|-----------|-------|
| Server data (collections, documents, models, traces) | SWR with `useSWR()` hooks | Cached, auto-revalidated |
| Chat session | React `useState` + `useRef` for NDJSON stream | Per-page, not persisted |
| Selected collections | URL query params (`?collections=a,b`) | Shareable, bookmarkable |
| Selected models | URL query params (`?llm=llama3.2&embed=nomic`) | Shareable, bookmarkable |
| Upload progress | React `useState` with polling interval | Per-upload lifecycle |
| Settings form | React Hook Form with SWR cache | Form-local, submitted on save |

### NDJSON Streaming Implementation

The `streamChat()` function in `lib/api.ts` uses `fetch` with `ReadableStream` to consume NDJSON events from `POST /api/chat`. The backend uses `media_type="application/x-ndjson"` — each line is a raw JSON object with NO `data: ` prefix. Do not apply SSE-style line parsing.

All 10 event types are defined in `backend/agent/schemas.py` as TypedDicts. The TypeScript callbacks must handle all of them:

```typescript
export function streamChat(
  request: ChatRequest,
  callbacks: {
    onSession: (sessionId: string) => void;
    onChunk: (text: string) => void;        // event.type === "chunk", field: text
    onCitations: (citations: Citation[]) => void;  // event.type === "citation", field: citations (array)
    onStatus: (node: string) => void;
    onMetaReasoning: (strategiesAttempted: string[]) => void;
    onConfidence: (score: number, level: "high" | "moderate" | "low") => void;
    onGroundedness: (overallGrounded: boolean, supported: number, unsupported: number, contradicted: number) => void;
    onClarification: (question: string) => void;
    onDone: (latencyMs: number, traceId: string) => void;
    onError: (message: string, code: string, traceId: string) => void;
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
        if (!line.trim()) continue;          // skip blank lines
        const event = JSON.parse(line);      // NDJSON: no "data: " prefix

        switch (event.type) {
          case "session":
            callbacks.onSession(event.session_id);
            break;
          case "chunk":
            // Use functional setState when accumulating: setContent(c => c + event.text)
            callbacks.onChunk(event.text);
            break;
          case "citation":
            // Backend emits one citation event with a list after streaming completes
            callbacks.onCitations(event.citations);
            break;
          case "status":
            callbacks.onStatus(event.node);
            break;
          case "meta_reasoning":
            callbacks.onMetaReasoning(event.strategies_attempted);
            break;
          case "confidence":
            // score is INTEGER 0-100; derive level in the component
            callbacks.onConfidence(event.score, event.score >= 70 ? "high" : event.score >= 40 ? "moderate" : "low");
            break;
          case "groundedness":
            callbacks.onGroundedness(event.overall_grounded, event.supported, event.unsupported, event.contradicted);
            break;
          case "clarification":
            callbacks.onClarification(event.question);
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
  });

  return controller;
}
```

### NDJSON Event Reference

All events emitted by `POST /api/chat` in order of emission:

| Event type | Fields | When emitted |
|-----------|--------|--------------|
| `session` | `session_id: string` | Immediately, before graph execution |
| `status` | `node: string` | On each LangGraph node transition |
| `chunk` | `text: string` | Each AI content token during streaming |
| `clarification` | `question: string` | On clarification interrupt (stream ends after this) |
| `citation` | `citations: list[dict]` | After stream completes, if chunks retrieved |
| `meta_reasoning` | `strategies_attempted: string[]` | After stream, if meta-reasoning ran |
| `confidence` | `score: int` | Always emitted after stream (int 0–100) |
| `groundedness` | `overall_grounded: bool`, `supported: int`, `unsupported: int`, `contradicted: int` | After stream, if groundedness check ran |
| `done` | `latency_ms: int`, `trace_id: string` | Last event on success |
| `error` | `message: string`, `code: string`, `trace_id: string` | On any error (replaces `done`) |

### Confidence Display Mapping

The backend emits `confidence_score` as an INTEGER in range 0–100 (stored as `INTEGER` in SQLite `query_traces` table, cast via `int(final_state.get("confidence_score", 0))` in `chat.py`). Display thresholds must use integer comparisons:

| Score Range | Color | Label | Icon |
|------------|-------|-------|------|
| 70 – 100 | Green | High confidence | Solid circle |
| 40 – 69 | Yellow | Moderate confidence | Half circle |
| 0 – 39 | Red | Low confidence | Empty circle |

### Vercel React Best Practices

Apply these rules specifically to this frontend:

**BP-1 Dynamic imports for heavy chart and upload components (CRITICAL)**
The observability page uses recharts (large bundle) and the documents page uses react-dropzone. Load them with `next/dynamic` and `ssr: false` so they do not inflate the initial bundle:
```typescript
const LatencyChart = dynamic(() => import('./LatencyChart'), { ssr: false });
const ConfidenceDistribution = dynamic(() => import('./ConfidenceDistribution'), { ssr: false });
const DocumentUploader = dynamic(() => import('./DocumentUploader'), { ssr: false });
```

**BP-2 Radix UI barrel import avoidance (CRITICAL)**
Import each Radix UI primitive from its own package path, not a shared barrel. Configure `next.config.js` to prevent full barrel loading:
```js
// next.config.js
module.exports = {
  experimental: {
    optimizePackageImports: ['@radix-ui/react-tooltip', '@radix-ui/react-dialog', '@radix-ui/react-select'],
  },
};
```

**BP-3 Functional setState for token accumulation (HIGH)**
When appending streamed text chunks in ChatPanel, use the functional update form to prevent stale closures:
```typescript
// Correct — no stale closure risk, no dependency on current content
setContent(curr => curr + event.text);
// Incorrect — requires content in useCallback deps, causes recreation on each chunk
setContent(content + event.text);
```

**BP-4 No component definitions inside render functions (HIGH)**
ChatPanel renders many sub-elements (MessageBubble, CitationMarker). Define all sub-components at module level, not inside ChatPanel's function body. Defining components inside render functions causes React to remount the sub-component on every parent render, resetting DOM state and re-running effects.

**BP-5 SWR for all server-state fetching (MEDIUM-HIGH)**
Use `useSWR` for every GET endpoint — never `useEffect` + `fetch`. Use `useSWRMutation` for POST/PUT/DELETE operations on collections, documents, and settings to get optimistic UI and cache invalidation:
```typescript
const { trigger: createCollection } = useSWRMutation('/api/collections', postFetcher);
```

**BP-6 Parallel SWR keys on multi-data pages (MEDIUM)**
The observability page needs collections, traces, and health data. Start all SWR keys together in the page component — SWR deduplicates and parallelizes automatically. Do not await one before starting the next.

**BP-7 Passive event listeners on chat scroll (MEDIUM)**
If ChatPanel auto-scrolls to the latest token, attach the scroll listener with `{ passive: true }` to avoid blocking the main thread during rapid streaming.

**BP-8 Lazy state initialization for URL param parsing (MEDIUM)**
On the chat page, initialize `selectedCollections` and model state from URL params using the lazy form of `useState` to avoid re-parsing the URL on every render:
```typescript
const [selectedCollections, setSelectedCollections] = useState(
  () => new URLSearchParams(window.location.search).get('collections')?.split(',') ?? []
);
```

## Dependencies

### Spec Dependencies
- **spec-08-api** (REQUIRED): All backend API endpoints consumed by the frontend. This includes collections, documents, ingest, chat, models, providers, settings, traces, and health endpoints — all implemented in spec-08. No dependency on spec-10 or spec-12 is needed; those planned specs are superseded by the comprehensive endpoint set in spec-08.

### Package Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `next` | `16` | React framework, App Router, Turbopack |
| `react` | `19` | UI component library |
| `typescript` | `5.7` | Type safety |
| `tailwindcss` | `4` | Utility-first CSS |
| `recharts` | `2` | Latency charts on observability page (dynamic import) |
| `@radix-ui/react-tooltip` | `1` | Citation tooltip primitives |
| `@radix-ui/react-dialog` | `1` | Modal dialogs |
| `@radix-ui/react-select` | `2` | Dropdown selects |
| `swr` | `2` | Data fetching with cache for API calls |
| `react-dropzone` | `14` | File drag-drop upload (dynamic import) |
| `react-hook-form` | `7` | Settings form state management (referenced in FR-4 and State Management table) |

### Dev/Test Dependencies
| Package | Version | Purpose |
|---------|---------|---------|
| `vitest` | `>=3.0` | Frontend unit tests |
| `@playwright/test` | `>=1.50` | Frontend E2E tests |
| `@testing-library/react` | `>=16.0` | Component testing |

## Acceptance Criteria

1. All five pages render correctly and are navigable via the top navigation bar
2. Chat page streams text chunks in real-time via NDJSON with visible first chunk within 500ms
3. Citations render as clickable inline markers with hover tooltips showing chunk text, source, page, breadcrumb (emitted as a list in the `citation` event after streaming)
4. Confidence indicator displays correct color (green for ≥70, yellow for 40–69, red for <40) based on INTEGER score from backend
5. Collection CRUD operations work end-to-end (create, list, delete)
6. File upload via drag-drop shows progress bar and polls job status until completion
7. Model selectors populate from `/api/models/llm` and `/api/models/embed` endpoints
8. Provider Hub shows provider status and allows API key entry (masked display), using `ProviderDetailResponse` fields
9. Observability page displays latency histogram, confidence distribution, health status, and paginated trace table
10. Selected collections and models are persisted in URL query params
11. All SWR-backed data auto-revalidates on focus and interval
12. Responsive layout works on desktop (1024px+) and tablet (768px+)
13. recharts and react-dropzone load via `next/dynamic` (`ssr: false`) and do not appear in the main bundle

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
|  [ Confidence: green-dot 85/100  ]       | LLM Model:                   |
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
|  | 12 docs            |  | 5 docs             |  | 8 docs     |  |
|  | nomic-embed-text   |  | nomic-embed-text   |  | nomic-...  |  |
|  | [Upload] [Delete]  |  | [Upload] [Delete]  |  | [Upload]   |  |
|  +--------------------+  +--------------------+  +-------------+  |
+------------------------------------------------------------------+
```

### Component-to-File Mapping

| Component | File | Responsibility |
|-----------|------|---------------|
| `ChatPanel` | `components/ChatPanel.tsx` | Message thread, NDJSON chunk accumulation, inline citation rendering |
| `ChatInput` | `components/ChatInput.tsx` | Text area + send button |
| `ChatSidebar` | `components/ChatSidebar.tsx` | CollectionSelector + ModelSelector |
| `CollectionCard` | `components/CollectionCard.tsx` | Collection metadata display, delete action, document count |
| `CollectionList` | `components/CollectionList.tsx` | Grid of CollectionCards |
| `CreateCollectionDialog` | `components/CreateCollectionDialog.tsx` | Modal for collection creation |
| `DocumentUploader` | `components/DocumentUploader.tsx` | Drag-drop file upload, progress polling via `/ingest/{job_id}` (dynamic import) |
| `DocumentList` | `components/DocumentList.tsx` | Table of documents with status badges |
| `ModelSelector` | `components/ModelSelector.tsx` | Dropdowns for LLM and embedding model |
| `CitationTooltip` | `components/CitationTooltip.tsx` | Hover tooltip showing chunk text, source file, page, breadcrumb |
| `ConfidenceIndicator` | `components/ConfidenceIndicator.tsx` | Visual confidence dot with score tooltip (integer 0-100 input) |
| `ProviderHub` | `components/ProviderHub.tsx` | Provider list, API key management, connection status |
| `TraceTable` | `components/TraceTable.tsx` | Paginated query trace list with expandable detail rows |
| `LatencyChart` | `components/LatencyChart.tsx` | Histogram of query latencies (recharts, dynamic import) |
| `ConfidenceDistribution` | `components/ConfidenceDistribution.tsx` | Bar chart by confidence score range (recharts, dynamic import) |
| `HealthDashboard` | `components/HealthDashboard.tsx` | Service status cards + latency gauges |
| `CollectionStats` | `components/CollectionStats.tsx` | Per-collection doc + chunk counts |
| `Navigation` | `components/Navigation.tsx` | Top nav bar with logo and page links |
