# Spec 09: Frontend Architecture -- Implementation Plan Context

## Component Overview

The frontend is a Next.js 16 App Router application providing the complete user interface for The Embedinator RAG system. It has five pages: chat (multi-turn RAG queries with NDJSON streaming), collections (CRUD with slug validation), documents (upload with 50 MB client-side guard and job polling), settings (agent behavior configuration with toast feedback and provider API key management), and observability (health cards, latency histogram, confidence distribution, paginated trace table). No authentication is required — all pages are publicly accessible. The frontend communicates with the FastAPI backend exclusively through a centralized typed API client. The sole backend dependency is `spec-08-api`.

## Technical Approach

### Framework and Tooling
- **Next.js 16** with App Router (server components for layout, client components for interactive pages)
- **React 19** for UI rendering
- **TypeScript 5.7** with strict mode across all files
- **Tailwind CSS v4** for utility-first styling
- **Radix UI** for accessible primitives (tooltip, dialog, select)
- **SWR v2** for data fetching with stale-while-revalidate caching
- **recharts v2** for charts on the observability page
- **react-dropzone v14** for drag-and-drop file upload
- **React Hook Form** for settings page form state
- **vitest v3** + **React Testing Library v16** for component unit tests
- **Playwright v1.50** for E2E tests

### Patterns
- **Centralized API client** (`lib/api.ts`): All backend calls go through typed async functions. No direct fetch calls in components.
- **NDJSON stream parsing**: `streamChat()` reads `application/x-ndjson` — each line is a raw JSON object with no `data:` prefix. Parsed via `ReadableStream` + `TextDecoder` + line-by-line `JSON.parse()`.
- **Custom SWR hooks** (`hooks/`): One hook per data domain (collections, models, traces).
- **URL query param state**: Selected collections and models stored in URL params via `useSearchParams` for shareability (FR-006).
- **Send-button lock**: `isStreaming` state disables the send button during a streaming response; re-enabled on `done` or `error` event (FR-001).
- **50 MB client-side upload guard**: File size checked before any network request; inline error shown on violation (FR-011).
- **Toast notifications**: Settings saves show a success or error banner after API response completes; no optimistic UI (FR-015).
- **Component composition**: Small, single-responsibility components composed at page level.

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
    Navigation.tsx                   # Top nav bar: logo, page links, active state
    ChatPanel.tsx                    # Multi-turn message thread with NDJSON accumulation
    ChatInput.tsx                    # Textarea + send button (disabled while isStreaming)
    ChatSidebar.tsx                  # Collection multi-select + model selectors
    CitationTooltip.tsx              # Radix Tooltip for inline citation markers
    ConfidenceIndicator.tsx          # Integer 0-100 score: green/yellow/red dot
    CollectionList.tsx               # Responsive grid of CollectionCards
    CollectionCard.tsx               # Individual collection card with delete button
    CreateCollectionDialog.tsx       # Radix Dialog for new collection (slug validation)
    DocumentList.tsx                 # Document table with pipeline status badges
    DocumentUploader.tsx             # react-dropzone with 50 MB guard + job polling
    ModelSelector.tsx                # LLM/embed model dropdown (Radix Select)
    ProviderHub.tsx                  # Provider list, masked key input, status indicator
    Toast.tsx                        # Success/error banner for settings saves
    TraceTable.tsx                   # Paginated trace list with expandable rows
    LatencyChart.tsx                 # recharts histogram
    ConfidenceDistribution.tsx       # recharts bar chart
    HealthDashboard.tsx              # Service status cards
    CollectionStats.tsx              # Per-collection document and chunk counts
  lib/
    api.ts                           # Centralized API client (fetch + NDJSON streaming)
    types.ts                         # Shared TypeScript interfaces
  hooks/
    useStreamChat.ts                 # Custom hook wrapping NDJSON-based streamChat()
    useCollections.ts                # SWR hook for collections data
    useModels.ts                     # SWR hook for LLM and embed model lists
    useTraces.ts                     # SWR hook for paginated traces
  next.config.ts                     # Next.js configuration
  package.json                       # Dependencies
  tailwind.config.ts                 # Tailwind configuration
  tsconfig.json                      # TypeScript configuration (strict mode)
```

## Testing Policy

**NEVER run vitest, playwright, or npm test inline inside Claude Code.** All frontend test execution is initiated via npm scripts and monitored externally.

```bash
# Frontend unit tests (vitest)
cd frontend && npm run test -- --run        # run once and exit
# or via run-tests-external.sh if script supports frontend targets

# Frontend E2E tests (Playwright)
cd frontend && npx playwright test

# TypeScript strict compile check (always run before marking a wave complete)
cd frontend && npx tsc --noEmit

# Python regression baseline (no backend changes in spec-09, but verify no regressions)
zsh scripts/run-tests-external.sh -n spec09-regression tests/
cat Docs/Tests/spec09-regression.status    # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec09-regression.summary   # ~20 lines when done
```

Rules for all agents:
- Do not run `npm test` interactively inside a Claude Code session — run in background or via script.
- Do not read `.log` files directly; read `.summary` files only.
- Wave gates must be PASSED before the next wave starts.
- `npx tsc --noEmit` must return zero errors before any agent reports DONE.

## Agent Teams Orchestration

**This spec MUST be implemented using Agent Teams.** Do not implement manually.

```
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

All agents spawn in tmux panes. The lead orchestrator reads this file and the task list, spawns agents per the wave table, enforces checkpoint gates, and never implements code directly.

**Spawn pattern for each agent:**
```
Read your instruction file at Docs/PROMPTS/spec-09-frontend/agents/A<N>-<name>.md FIRST, then execute all assigned tasks.
```

### Wave Table

| Wave | Agents | Work | Model |
|------|--------|------|-------|
| 1 | A1 (serial) | Scaffolding, types, API client, SWR hooks | Opus |
| 2 | A2 + A3 (parallel) | Chat page / Collections page | Opus + Sonnet |
| 3 | A4 + A5 (parallel) | Documents page / Settings page + ProviderHub | Sonnet + Sonnet |
| 4 | A6 (serial) | Observability page (charts, health, traces) | Sonnet |
| 5 | A7 (serial) | Quality: vitest unit tests, Playwright E2E, TypeScript audit | Sonnet |

**Model rationale**: A1 (Opus) — the API client with correct NDJSON parsing for all 10 event types is the foundation everything else depends on. A2 (Opus) — chat streaming with send-button lock, multi-turn thread, citations, and confidence is the most complex page. All others use Sonnet.

### Agent Instruction Files

| Agent | File | Responsibility |
|-------|------|----------------|
| A1 | `Docs/PROMPTS/spec-09-frontend/agents/A1-foundation.md` | Project scaffold, `lib/types.ts`, `lib/api.ts`, all four SWR hooks |
| A2 | `Docs/PROMPTS/spec-09-frontend/agents/A2-chat-page.md` | `app/chat/page.tsx`, ChatPanel, ChatInput, ChatSidebar, CitationTooltip, ConfidenceIndicator, useStreamChat |
| A3 | `Docs/PROMPTS/spec-09-frontend/agents/A3-collections-page.md` | `app/collections/page.tsx`, CollectionList, CollectionCard, CreateCollectionDialog |
| A4 | `Docs/PROMPTS/spec-09-frontend/agents/A4-documents-page.md` | `app/documents/[id]/page.tsx`, DocumentList, DocumentUploader (50 MB guard + polling) |
| A5 | `Docs/PROMPTS/spec-09-frontend/agents/A5-settings-page.md` | `app/settings/page.tsx`, ProviderHub, ModelSelector, Toast |
| A6 | `Docs/PROMPTS/spec-09-frontend/agents/A6-observability-page.md` | `app/observability/page.tsx`, HealthDashboard, LatencyChart, ConfidenceDistribution, TraceTable, CollectionStats |
| A7 | `Docs/PROMPTS/spec-09-frontend/agents/A7-quality-tests.md` | vitest unit tests for all components and API client, Playwright E2E, TypeScript strict audit, regression check |

### Checkpoint Gates

**Gate 1 (after Wave 1):** TypeScript compiles, API client exports all functions, all 10 NDJSON event types handled in `streamChat()`, SWR hooks created.
```bash
cd frontend && npx tsc --noEmit
# Must exit 0 before Wave 2 starts
```

**Gate 2 (after Wave 2):** Chat page renders with NDJSON streaming, send button locks on submit, collections CRUD works with slug validation.
```bash
cd frontend && npx tsc --noEmit
cd frontend && npm run test -- --run --reporter=verbose
```

**Gate 3 (after Wave 3):** Document upload enforces 50 MB limit with inline error, job polling cycles to terminal state, settings saves show toast notification.
```bash
cd frontend && npx tsc --noEmit
```

**Gate 4 (after Wave 4):** Observability page renders health cards, recharts histograms, paginated trace table without errors.
```bash
cd frontend && npx tsc --noEmit
```

**Gate 5 (after Wave 5):** All vitest unit tests pass, Playwright E2E pass, zero TypeScript errors, no Python regressions.
```bash
cd frontend && npm run test -- --run
cd frontend && npx playwright test
zsh scripts/run-tests-external.sh -n spec09-regression tests/
cat Docs/Tests/spec09-regression.status  # must be PASSED
```

### Orchestration Rules

1. Never skip checkpoint gates — a failed gate means the next wave builds on broken contracts.
2. Parallel waves in Wave 2 and Wave 3 touch disjoint files — no merge conflicts.
3. All teammate prompts are minimal — just point to the instruction file. All authoritative context lives in the instruction files.
4. If a teammate fails — shut it down and spawn a replacement with the same instruction file.
5. Monitor via tmux — each agent spawns in its own pane for real-time visibility.
6. No agent runs tests inline in Claude Code — run in background or via npm scripts.

## Implementation Steps

### Step 1: Project Scaffolding
1. Initialize Next.js 16 project with TypeScript and App Router inside `frontend/`
2. Install dependencies: tailwindcss v4, swr v2, recharts v2, react-dropzone v14, @radix-ui/react-tooltip, @radix-ui/react-dialog, @radix-ui/react-select, react-hook-form
3. Install dev dependencies: vitest v3, @playwright/test, @testing-library/react v16
4. Configure Tailwind CSS and `next.config.ts` with `NEXT_PUBLIC_API_URL` env variable
5. Create `tsconfig.json` with strict mode and path aliases (`@/*` -> `./src/*` or project root)

### Step 2: Shared Types and API Client
1. Create `lib/types.ts` with all TypeScript interfaces: ChatMessage, Citation, ChatRequest, Collection, Document, IngestionJob, ModelInfo, Provider, Settings, QueryTrace, QueryTraceDetail, HealthStatus, SystemStats, ApiError
2. Create `lib/api.ts` with all typed API functions: `getCollections`, `createCollection`, `deleteCollection`, `getDocuments`, `ingestFile`, `getIngestionJob`, `deleteDocument`, `streamChat`, `getLLMModels`, `getEmbedModels`, `getProviders`, `setProviderKey`, `deleteProviderKey`, `getSettings`, `updateSettings`, `getTraces`, `getHealth`, `getStats`
3. Implement `streamChat()` with NDJSON parsing: raw JSON lines, no `data:` prefix, handles all 10 event types, returns `AbortController`

### Step 3: Root Layout and Navigation
1. Create `app/layout.tsx` with root HTML structure, Tailwind imports, font loading
2. Create `components/Navigation.tsx` with logo, links to all five pages (Chat, Collections, Documents, Settings, Observability), active route highlighting via `usePathname`

### Step 4: SWR Custom Hooks
1. Create `hooks/useCollections.ts` wrapping `useSWR` for collections list with optimistic delete
2. Create `hooks/useModels.ts` wrapping `useSWR` for LLM and embed model lists
3. Create `hooks/useTraces.ts` wrapping `useSWR` for paginated traces with session filter
4. Create `hooks/useStreamChat.ts` wrapping `streamChat()` with React state: `messages`, `isStreaming`, `sessionId`; sets `isStreaming(false)` on `done` or `error` event

### Step 5: Chat Page
1. Create `app/chat/page.tsx` as client component with URL param state for collections and models
2. Implement `ChatPanel` as a scrollable multi-turn message thread; appends new Q&A at bottom; accumulates `chunk` event text incrementally during streaming
3. Implement `ChatInput` with textarea, send button disabled when `isStreaming || !message.trim() || selectedCollections.length === 0`, Enter key handling
4. Implement `ChatSidebar` with collection multi-select checkboxes and ModelSelector dropdowns
5. Implement `CitationTooltip` using Radix Tooltip; renders source chunk text, file name, page number, breadcrumb
6. Implement `ConfidenceIndicator` showing color-coded dot with integer score on hover: `score >= 70` green, `score >= 40` yellow, `score < 40` red

### Step 6: Collections Page
1. Create `app/collections/page.tsx` using `useCollections` hook
2. Implement `CollectionList` as a responsive card grid
3. Implement `CollectionCard` showing name, description, document count, embedding model, chunk profile; confirm-before-delete
4. Implement `CreateCollectionDialog` using Radix Dialog with name validation (`^[a-z0-9][a-z0-9_-]*$`), description input, embedding model picker; show inline error on `COLLECTION_NAME_CONFLICT` without closing dialog

### Step 7: Documents Page
1. Create `app/documents/[id]/page.tsx` with collection ID from URL params
2. Implement `DocumentList` as a table with color-coded status badges for all pipeline states: pending, started, streaming, embedding, completed, failed, paused
3. Implement `DocumentUploader` with react-dropzone, client-side 50 MB guard (inline error shown, no network request made), upload progress indicator, job status polling every 2 seconds until terminal state

### Step 8: Settings Page
1. Create `app/settings/page.tsx` with two sections: agent behavior form and provider hub
2. Implement settings form using React Hook Form for: default LLM model, default embed model, confidence threshold, groundedness check, citation alignment threshold, parent chunk size, child chunk size
3. On save: call `updateSettings()`, await response, then show `Toast` with success or error — no optimistic UI
4. Implement `ProviderHub` showing provider list with active status, masked API key input, save/delete key actions; never display raw key value (`has_key: bool` from backend)

### Step 9: Observability Page
1. Create `app/observability/page.tsx` composing all dashboard components
2. Implement `HealthDashboard` with service status cards from `/api/health` (vector store, LLM runtime, database); show latency_ms per service
3. Implement `LatencyChart` as recharts bar chart with 24-hour query latency distribution
4. Implement `ConfidenceDistribution` as recharts bar chart grouping traces by confidence tier
5. Implement `TraceTable` with pagination, expandable detail rows, optional session filter
6. Implement `CollectionStats` with per-collection document and chunk counts from `/api/stats`

### Step 10: Testing
1. Set up vitest with React Testing Library; configure `vitest.config.ts` with jsdom environment
2. Write unit tests for: `streamChat()` NDJSON parsing (all 10 event types), `ConfidenceIndicator` color tier mapping, `CollectionCard` render and delete callback, `DocumentUploader` 50 MB guard, `CreateCollectionDialog` slug validation, `ModelSelector` option rendering
3. Set up Playwright; write E2E tests for: full chat flow (submit, streaming tokens, confidence indicator), collection CRUD, file upload with polling, settings save with toast, all navigation links
4. TypeScript strict compile (`npx tsc --noEmit`) must exit 0

## Integration Points

- **Backend API (`spec-08-api`, REQUIRED)**: All data flows through `lib/api.ts`. Every endpoint defined in spec-08-api has a corresponding typed function. This is the only backend dependency.
- **NDJSON contract (`spec-08-api`)**: The chat stream emits `application/x-ndjson` — raw JSON lines with no `data:` prefix. The `streamChat()` function must handle exactly 10 event types in the order defined by spec-08-api: `session`, `status`, `chunk` (field: `text`), `citation` (field: `citations`), `meta_reasoning`, `confidence` (field: `score`, integer 0-100), `groundedness`, `clarification`, `done`, `error`.
- **Error response format (`spec-08-api`)**: Non-streaming errors follow `{"error": {"code": "...", "message": "..."}, "trace_id": "..."}`. The `ApiError` class in `lib/api.ts` wraps non-OK HTTP responses for components to surface user-facing messages.
- **Provider key contract (`spec-08-api`)**: The backend never returns a raw API key — only `has_key: bool`. `ProviderHub` must reflect this: display masked placeholder when `has_key` is true, "no key" indicator when false.

## Key Code Patterns

### NDJSON Stream Parsing

```typescript
// CORRECT: raw JSON lines, no "data:" prefix
export function streamChat(request: ChatRequest, callbacks: { ... }): AbortController {
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
        if (!line.trim()) continue;
        const event = JSON.parse(line); // No "data: " prefix -- raw JSON
        switch (event.type) {
          case "session":        callbacks.onSession?.(event.session_id); break;
          case "chunk":          callbacks.onToken(event.text); break; // field is "text"
          case "citation":       callbacks.onCitation(event.citations); break;
          case "status":         callbacks.onStatus(event.node); break;
          case "meta_reasoning": callbacks.onMetaReasoning?.(event.strategies_attempted); break;
          case "confidence":     callbacks.onConfidence(event.score); break; // int 0-100
          case "groundedness":   callbacks.onGroundedness?.(event); break;
          case "clarification":  callbacks.onClarification?.(event.question); break;
          case "done":           callbacks.onDone(event.latency_ms, event.trace_id); break;
          case "error":          callbacks.onError(event.message, event.code); break;
        }
      }
    }
  });
  return controller;
}
```

### Send-Button Lock

```typescript
const [isStreaming, setIsStreaming] = useState(false);

// In useStreamChat: setIsStreaming(true) on submit,
// setIsStreaming(false) inside onDone and onError callbacks

// In ChatInput:
<button
  disabled={isStreaming || !message.trim() || selectedCollections.length === 0}
  onClick={handleSubmit}
>
  Send
</button>
```

### Confidence Display (Integer 0-100)

```typescript
// confidence event: { type: "confidence", score: number } -- score is int 0-100
const getConfidenceTier = (score: number): "green" | "yellow" | "red" => {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "red";
};

// ConfidenceIndicator renders a dot colored by tier, score visible on hover
```

### 50 MB Upload Guard

```typescript
const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB

const handleDrop = (files: File[]) => {
  for (const file of files) {
    if (file.size > MAX_FILE_SIZE) {
      setFileError(`${file.name} exceeds the 50 MB limit. Choose a smaller file.`);
      return; // Do NOT call ingestFile() -- no network request
    }
  }
  // proceed with upload
};
```

### Toast Notification for Settings Saves

```typescript
const [toast, setToast] = useState<{ message: string; type: "success" | "error" } | null>(null);

const handleSave = async (data: Partial<Settings>) => {
  try {
    await updateSettings(data);
    setToast({ message: "Settings saved", type: "success" });
  } catch {
    setToast({ message: "Failed to save settings", type: "error" });
  }
};
// Toast auto-dismisses after 3 seconds; no optimistic UI used
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
const router = useRouter();
const selectedCollections = searchParams.get("collections")?.split(",").filter(Boolean) ?? [];
const llmModel = searchParams.get("llm") ?? "llama3.2";
```

## Phase Assignment

- **Phase 1 (MVP)**: `/chat` and `/collections` pages — streaming chat with NDJSON, multi-turn thread, citation tooltips, confidence indicator, collection CRUD with slug validation, ModelSelector with Ollama models.
- **Phase 2**: `/documents/[id]` page — file upload with 50 MB guard, progress polling, status badge table, document delete.
- **Phase 3**: `/settings` page — React Hook Form for agent settings, ProviderHub with masked key input and connection status, toast notifications.
- **Phase 4**: `/observability` page — health dashboard, latency histogram, confidence distribution chart, paginated trace table.
