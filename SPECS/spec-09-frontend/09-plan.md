# Spec 09: Frontend Architecture -- Implementation Plan Context

## Component Overview

The frontend is a Next.js 16 App Router application that serves as the complete user interface for The Embedinator RAG system. It provides five pages: chat (RAG queries with streaming), collections (CRUD), documents (upload and status), settings (configuration and provider management), and observability (health, traces, charts). The frontend communicates with the FastAPI backend via a centralized typed API client using fetch, SSE streaming, and SWR for data caching.

## Technical Approach

### Framework and Tooling
- **Next.js 16** with App Router (server components for layout, client components for interactive pages)
- **React 19** for UI rendering
- **TypeScript 5.7** for type safety across all files
- **Tailwind CSS v4** for utility-first styling
- **Radix UI** for accessible primitives (tooltip, dialog, select)
- **SWR v2** for data fetching with stale-while-revalidate caching
- **recharts v2** for charts on the observability page
- **react-dropzone v14** for drag-and-drop file upload

### Patterns
- **Centralized API client** (`lib/api.ts`): All backend calls go through typed async functions
- **Custom SWR hooks** (`hooks/`): One hook per data domain (collections, models, traces)
- **URL query param state**: Selected collections and models stored in URL params via `useSearchParams`
- **SSE via ReadableStream**: Custom `useStreamChat` hook wraps the `streamChat()` API function
- **React Hook Form** for the settings page form state
- **Component composition**: Small, single-responsibility components composed on page level

## File Structure

```
frontend/
  app/
    layout.tsx                       # Root layout with Navigation, theme, fonts
    chat/
      page.tsx                       # Chat page (client component)
    collections/
      page.tsx                       # Collections list page
    documents/
      [id]/page.tsx                  # Per-collection document list + uploader
    settings/
      page.tsx                       # Settings form + Provider Hub
    observability/
      page.tsx                       # Health dashboard, charts, trace table
  components/
    Navigation.tsx                   # Top nav bar: logo, page links, theme toggle
    ChatPanel.tsx                    # Message thread with SSE accumulation
    ChatInput.tsx                    # Text area + send button
    ChatSidebar.tsx                  # Collection multi-select + model selectors
    CitationTooltip.tsx              # Hover tooltip for inline citations
    ConfidenceIndicator.tsx          # Green/yellow/red confidence dot
    CollectionList.tsx               # Grid of CollectionCards
    CollectionCard.tsx               # Individual collection card
    CreateCollectionDialog.tsx       # Radix Dialog for new collection
    DocumentList.tsx                 # Document table with status badges
    DocumentUploader.tsx             # react-dropzone + progress polling
    ModelSelector.tsx                # LLM/embed model dropdown (Radix Select)
    ProviderHub.tsx                  # Provider list, API key input, status
    TraceTable.tsx                   # Paginated trace list with expandable rows
    LatencyChart.tsx                 # recharts histogram
    ConfidenceDistribution.tsx       # recharts bar chart
    HealthDashboard.tsx              # Service status cards
    CollectionStats.tsx              # Per-collection statistics
  lib/
    api.ts                           # Centralized API client (fetch + SSE)
    types.ts                         # Shared TypeScript interfaces
  hooks/
    useStreamChat.ts                 # Custom hook wrapping streamChat()
    useCollections.ts                # SWR hook for collections data
    useModels.ts                     # SWR hook for model lists
    useTraces.ts                     # SWR hook for traces
  next.config.ts                     # Next.js configuration
  package.json                       # Dependencies
  tailwind.config.ts                 # Tailwind configuration
  tsconfig.json                      # TypeScript configuration
```

## Implementation Steps

### Step 1: Project Scaffolding
1. Initialize Next.js 16 project with TypeScript and App Router
2. Install dependencies: tailwindcss v4, swr v2, recharts v2, react-dropzone v14, @radix-ui/react-tooltip, @radix-ui/react-dialog, @radix-ui/react-select
3. Configure Tailwind CSS
4. Set up `next.config.ts` with `NEXT_PUBLIC_API_URL` environment variable
5. Create `tsconfig.json` with strict mode and path aliases

### Step 2: Shared Types and API Client
1. Create `lib/types.ts` with all TypeScript interfaces (ChatMessage, Citation, Collection, Provider, QueryTrace, etc.)
2. Create `lib/api.ts` with all API functions: `getCollections()`, `createCollection()`, `deleteCollection()`, `getDocuments()`, `ingestFile()`, `getIngestionJob()`, `streamChat()`, `getModels()`, `getProviders()`, `setProviderKey()`, `getSettings()`, `updateSettings()`, `getTraces()`, `getHealth()`, `getStats()`
3. Implement `streamChat()` with ReadableStream SSE parsing and typed callbacks

### Step 3: Root Layout and Navigation
1. Create `app/layout.tsx` with root HTML structure, Tailwind imports, font loading
2. Create `components/Navigation.tsx` with logo, page links (Chat, Collections, Documents, Settings, Observability), active state highlighting

### Step 4: SWR Custom Hooks
1. Create `hooks/useCollections.ts` wrapping `useSWR("/api/collections", getCollections)`
2. Create `hooks/useModels.ts` wrapping `useSWR` for LLM and embed model lists
3. Create `hooks/useTraces.ts` wrapping `useSWR` for paginated traces
4. Create `hooks/useStreamChat.ts` wrapping the `streamChat()` API function with React state management

### Step 5: Chat Page
1. Create `app/chat/page.tsx` as client component with URL param state for collections and models
2. Implement `ChatPanel` with message list rendering, token accumulation during streaming, citation inline markers
3. Implement `ChatInput` with textarea, send button, and Enter key handling
4. Implement `ChatSidebar` with collection multi-select checkboxes and ModelSelector dropdowns
5. Implement `CitationTooltip` using Radix Tooltip with lazy chunk text fetch on hover
6. Implement `ConfidenceIndicator` with color-coded dot and score tooltip

### Step 6: Collections Page
1. Create `app/collections/page.tsx` using `useCollections` hook
2. Implement `CollectionList` as a responsive grid of `CollectionCard` components
3. Implement `CollectionCard` showing name, description, doc count, chunk count, embedding model, with delete button
4. Implement `CreateCollectionDialog` using Radix Dialog with name validation, description input, embedding model picker

### Step 7: Documents Page
1. Create `app/documents/[id]/page.tsx` with collection ID from URL params
2. Implement `DocumentList` as a table with status badges (color-coded by status)
3. Implement `DocumentUploader` using react-dropzone with drag-drop zone, file validation, upload progress bar, and job status polling

### Step 8: Settings Page
1. Create `app/settings/page.tsx` with two sections: settings form and provider hub
2. Implement `SettingsForm` using React Hook Form for agent limits, chunk sizes, thresholds
3. Implement `ProviderHub` showing provider list with status indicators, masked API key input, save/delete key actions

### Step 9: Observability Page
1. Create `app/observability/page.tsx` composing dashboard components
2. Implement `HealthDashboard` with service status cards fetching from `/api/health`
3. Implement `LatencyChart` using recharts histogram with time range selector
4. Implement `ConfidenceDistribution` using recharts bar chart
5. Implement `TraceTable` with pagination, expandable detail rows, session filter
6. Implement `CollectionStats` with per-collection document and chunk counts

### Step 10: Testing
1. Set up vitest with React Testing Library for component unit tests
2. Write tests for: API client functions, SSE parsing, component rendering, user interactions
3. Set up Playwright for E2E tests covering chat flow, collection CRUD, file upload

## Integration Points

- **Backend API** (`spec-08-api`): All data flows through the centralized API client in `lib/api.ts`. Every backend endpoint has a corresponding typed function.
- **Provider API** (`spec-10-providers`): The ProviderHub component and ModelSelector consume `/api/providers` and `/api/models/*` endpoints.
- **Error handling** (`spec-12-errors`): The API client catches errors and maps `ErrorResponse` objects to user-facing messages. The `ApiError` class in `api.ts` wraps HTTP errors.
- **SSE contract** (`spec-08-api`): The chat streaming depends on the exact SSE event format (`type`, `content`, `citation`, etc.) defined in the API spec.

## Key Code Patterns

### API Client Pattern
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function getCollections(): Promise<Collection[]> {
  const res = await fetch(`${API_BASE}/api/collections`);
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return res.json();
}
```

### SWR Hook Pattern
```typescript
export function useCollections() {
  const { data, error, mutate } = useSWR<Collection[]>("/api/collections", getCollections);
  return { collections: data, isLoading: !error && !data, isError: error, mutate };
}
```

### URL Param State Pattern
```typescript
const searchParams = useSearchParams();
const selectedCollections = searchParams.get("collections")?.split(",") ?? [];
const llmModel = searchParams.get("llm") ?? "llama3.2";
```

### SSE Stream Hook Pattern
```typescript
export function useStreamChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const controllerRef = useRef<AbortController | null>(null);
  // ... wraps streamChat() with React state updates
}
```

## Phase Assignment

- **Phase 1 (MVP)**: `/chat` and `/collections` pages with file upload and progress polling. Basic ModelSelector with Ollama models. ProviderHub with Ollama + OpenRouter support.
- **Phase 2**: `/observability` page with latency histogram, collection sizes, trace log, confidence distribution.
- **Phase 3**: `/documents/[id]` page enhancements (per-document chunk count, re-ingest button, status history). Citation highlighting with page coordinate mapping.
