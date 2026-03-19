# Spec 09: Frontend Architecture -- Implementation Context

---

## AGENT TEAMS ORCHESTRATION PROTOCOL — READ THIS FIRST

> **MAXIMUM PRIORITY.** The orchestrator MUST read and act on this entire section before doing anything else in this file. Do NOT proceed to implementation scope until all orchestration prerequisites below are confirmed.

**This spec MUST be implemented using Agent Teams.** Do not implement manually.

```
CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

All agents spawn in tmux panes. The lead orchestrator reads this file and the task list (`specs/009-next-frontend/tasks.md`), spawns agents per the wave table, enforces checkpoint gates, and never implements code directly.

**Spawn pattern for each agent:**
```
Read your instruction file at Docs/PROMPTS/spec-09-frontend/agents/A<N>-<name>.md FIRST. Also read `.claude/skills/vercel-react-best-practices/SKILL.md` and apply the relevant rules to every component and hook you write. Then execute all assigned tasks.
```

### Wave Table

| Wave | Agents | Tasks | Focus | Model |
|------|--------|-------|-------|-------|
| 1 | A1 (serial) | T001-T014 | Scaffold, types, API client, SWR hooks | Opus |
| 2 | A2 + A3 (parallel) | T015-T021 / T022-T025 | Chat page / Collections page | Opus + Sonnet |
| 3 | A4 + A5 (parallel) | T026-T028 / T029-T031 | Documents page / Settings + ProviderHub | Sonnet + Sonnet |
| 4 | A6 (serial) | T032-T037 | Observability page | Sonnet |
| 5 | A7 (serial) | T038-T046 | vitest, Playwright, TypeScript audit | Sonnet |

Phase 9 (T047-T052) is orchestrator-level work post Wave 5.

### Agent Instruction Files

| Agent | File | Agent Type | Responsibility |
|-------|------|------------|----------------|
| A1 | `agents/A1-foundation.md` | `system-architect` | Project scaffold, `lib/types.ts`, `lib/api.ts`, all 4 SWR hooks |
| A2 | `agents/A2-chat-page.md` | `frontend-architect` | Chat page: NDJSON streaming, multi-turn, citations, confidence |
| A3 | `agents/A3-collections-page.md` | `frontend-architect` | Collections CRUD: slug validation, Radix Dialog, conflict error |
| A4 | `agents/A4-documents-page.md` | `frontend-architect` | Documents: 50 MB guard, extension guard, job polling |
| A5 | `agents/A5-settings-page.md` | `frontend-architect` | Settings form, ProviderHub, Toast |
| A6 | `agents/A6-observability-page.md` | `performance-engineer` | Health cards, recharts, trace table |
| A7 | `agents/A7-quality-tests.md` | `quality-engineer` | vitest, Playwright, TypeScript strict audit |

### Checkpoint Gates

**Gate 1 (after Wave 1):** TypeScript compiles; `streamChat()` exports; all 10 NDJSON event types handled; all 4 SWR hooks export.
```bash
cd frontend && npx tsc --noEmit
# Must exit 0 before Wave 2 starts
```

**Gate 2 (after Wave 2):** Chat page renders with NDJSON streaming; send button locks; collections CRUD works with slug validation.
```bash
cd frontend && npx tsc --noEmit
```

**Gate 3 (after Wave 3):** Document upload enforces 50 MB guard; job polling cycles to terminal state; settings save shows toast.
```bash
cd frontend && npx tsc --noEmit
```

**Gate 4 (after Wave 4):** Observability page renders health cards, recharts histograms, paginated trace table.
```bash
cd frontend && npx tsc --noEmit
```

**Gate 5 (after Wave 5):** All vitest unit tests pass; Playwright E2E pass; zero TypeScript errors; no Python regressions.
```bash
cd frontend && npm run test -- --run
cd frontend && npx playwright test
zsh scripts/run-tests-external.sh -n spec09-regression tests/
cat Docs/Tests/spec09-regression.status  # must be PASSED
```

### Orchestration Rules

1. Never skip checkpoint gates -- a failed gate means the next wave builds on broken contracts.
2. Parallel agents in Wave 2 and Wave 3 touch disjoint files -- no merge conflicts.
3. All teammate prompts are minimal -- just point to the instruction file. All authoritative context lives in the instruction files.
4. If a teammate fails -- shut it down and spawn a replacement with the same instruction file.
5. Monitor via tmux -- each agent spawns in its own pane for real-time visibility.
6. No agent runs tests inline in Claude Code -- run in background or via npm scripts.

---

## Vercel React Best Practices — MANDATORY

**All agents implementing React components or Next.js pages MUST apply the Vercel React Best Practices skill.** Performance correctness is a first-class implementation requirement alongside functional correctness.

**Skill location:** `.claude/skills/vercel-react-best-practices/`
**Quick reference:** `.claude/skills/vercel-react-best-practices/SKILL.md`
**Full compiled rules:** `.claude/skills/vercel-react-best-practices/AGENTS.md`
**Individual rule files:** `.claude/skills/vercel-react-best-practices/rules/<rule-name>.md`

### High-Impact Rules for This Implementation

The following rules are **directly applicable** to this frontend and must be followed by all agents:

| Rule | Category | Impact | Applies To |
|------|----------|--------|------------|
| `bundle-dynamic-imports` | Bundle | CRITICAL | `LatencyChart`, `ConfidenceDistribution` — recharts MUST use `next/dynamic` with `ssr: false` |
| `bundle-barrel-imports` | Bundle | CRITICAL | Radix UI: import directly from `@radix-ui/react-tooltip` etc., never via barrel re-exports |
| `async-parallel` | Async | CRITICAL | Use `Promise.all` for independent concurrent fetches; never chain awaits for independent calls |
| `rerender-use-ref-transient-values` | Re-render | MEDIUM | `useStreamChat` — NDJSON buffer and `TextDecoder` are transient; store in `useRef`, not `useState` |
| `rerender-functional-setstate` | Re-render | MEDIUM | `useStreamChat` — accumulate tokens with `setContent(prev => prev + text)`, not closure over stale state |
| `rerender-memo` | Re-render | MEDIUM | `ChatMessage`, `CitationTooltip`, `CollectionCard` — wrap with `React.memo` to prevent list re-renders |
| `rerender-no-inline-components` | Re-render | MEDIUM | Never define components inside render functions or other components |
| `rerender-dependencies` | Re-render | MEDIUM | Use primitive values (string/number), not object refs, in `useEffect` dependency arrays |
| `rerender-derived-state-no-effect` | Re-render | MEDIUM | Derive confidence tier and streaming UI flags during render — do NOT use `useEffect` for derivation |
| `client-swr-dedup` | Client | MEDIUM-HIGH | Set `revalidateOnFocus: false` for slowly-changing data (models list, providers list) |
| `rendering-conditional-render` | Rendering | MEDIUM | Use ternary `condition ? <A/> : <B/>`, NOT `condition && <A/>` — avoids rendering `0` as text |

### Agent-Specific Rule Responsibilities

- **A1 (Foundation):** `bundle-barrel-imports` for Radix UI imports; `rerender-use-ref-transient-values` + `rerender-functional-setstate` in `useStreamChat`; `client-swr-dedup` with `revalidateOnFocus: false` in `useModels` and `useCollections`.
- **A2 (Chat Page):** `rerender-memo` on `ChatMessage` list items; `rerender-no-inline-components`; `rendering-conditional-render` throughout; `rerender-use-ref-transient-values` for any local streaming buffer state.
- **A3 (Collections Page):** `rerender-memo` on `CollectionCard`; `rerender-no-inline-components`; `rendering-conditional-render`.
- **A4 (Documents Page):** `rerender-functional-setstate` for job polling state updates; `rerender-dependencies` — use primitive `jobId` string in polling effect, not object references.
- **A5 (Settings Page):** `rerender-derived-state-no-effect` — form dirty/pristine state must be derived during render, not in a `useEffect`; `rendering-conditional-render`.
- **A6 (Observability Page):** `bundle-dynamic-imports` — `LatencyChart` and `ConfidenceDistribution` MUST use `next/dynamic` with `{ ssr: false }`; `async-parallel` — health, stats, and traces fetched with `Promise.all` where independent.
- **A7 (Quality Tests):** During TypeScript strict audit, verify all above rules are applied; flag any violations in the audit report before declaring Wave 5 complete.

---

## Implementation Scope

### Files to Create

```
frontend/
  app/
    layout.tsx                       # Root layout: Navigation, Inter font, Tailwind globals, metadata
    globals.css                      # Tailwind CSS v4 global styles import
    chat/
      page.tsx                       # Chat page (client component): NDJSON streaming, multi-turn
    collections/
      page.tsx                       # Collections grid page (client component): CRUD
    documents/
      [id]/page.tsx                  # Per-collection document list + uploader (client component)
    settings/
      page.tsx                       # Settings form + ProviderHub (client component)
    observability/
      page.tsx                       # Health dashboard, charts, trace table (client component)
  components/
    Navigation.tsx                   # Top nav bar: logo, 5 page links, active route via usePathname
    ChatPanel.tsx                    # Multi-turn message thread, NDJSON token accumulation, auto-scroll
    ChatInput.tsx                    # Textarea + send button (disabled while isStreaming)
    ChatSidebar.tsx                  # Collection multi-select + LLM/embed model selectors, URL params
    CitationTooltip.tsx              # Radix Tooltip: passage text, document_name, source_removed badge
    ConfidenceIndicator.tsx          # Integer 0-100 score: green/yellow/red dot, score on hover
    CollectionList.tsx               # Responsive card grid from useCollections, loading/empty states
    CollectionCard.tsx               # Card: name, description, doc count, delete with Radix Dialog confirm
    CreateCollectionDialog.tsx       # Radix Dialog: slug validation, conflict error without closing
    DocumentList.tsx                 # Table with 5-state status badges, delete button
    DocumentUploader.tsx             # react-dropzone: 50 MB + extension guard, job polling
    ModelSelector.tsx                # Radix Select: LLMModelSelector + EmbedModelSelector exports
    ProviderHub.tsx                  # Provider list: is_active badge, has_key masking, save/delete key
    Toast.tsx                        # Success/error banner: fixed bottom-right, auto-dismiss 3s
    TraceTable.tsx                   # Paginated traces, expandable detail rows, session filter
    LatencyChart.tsx                 # recharts BarChart: latency distribution (dynamic import, ssr:false)
    ConfidenceDistribution.tsx       # recharts BarChart: 3 confidence tier bars (dynamic import, ssr:false)
    HealthDashboard.tsx              # 3 service cards: sqlite/qdrant/ollama status + latency
    CollectionStats.tsx              # Per-collection doc count + aggregate stats from /api/stats
  lib/
    api.ts                           # 17+ typed async functions + streamChat NDJSON (NO "data:" prefix)
    types.ts                         # All TypeScript interfaces matching backend schemas exactly
  hooks/
    useStreamChat.ts                 # NDJSON hook: isStreaming released on done/error/clarification
    useCollections.ts                # SWR for collections list with optimistic delete
    useModels.ts                     # SWR for LLM + embed model lists
    useTraces.ts                     # SWR for paginated traces with params
  tests/
    unit/
      api.test.ts                    # streamChat NDJSON parsing, all 10 events, PUT settings
      components.test.ts             # ConfidenceIndicator tiers, CitationTooltip source_removed, etc.
      hooks.test.ts                  # useStreamChat isStreaming release on done/error/clarification
    e2e/
      chat.spec.ts                   # Full chat flow: streaming, citations, confidence
      collections.spec.ts            # CRUD: create, invalid name, duplicate, delete
      documents.spec.ts              # Upload: 50 MB guard, extension guard, polling
      settings.spec.ts               # Save + toast, provider key masking
      responsive.spec.ts             # 768px + 1024px viewport tests
      workflow.spec.ts               # End-to-end cross-page journey
  vitest.config.ts                   # jsdom, @vitejs/plugin-react, v8 coverage >= 70%
  playwright.config.ts               # baseURL localhost:3000, screenshots on failure
  next.config.ts                     # NEXT_PUBLIC_API_URL, optimizePackageImports
  package.json                       # All runtime + dev dependencies
  tailwind.config.ts                 # Tailwind CSS v4, responsive breakpoints md/lg
  tsconfig.json                      # strict: true, "@/*" path alias
```

---

## Code Specifications

### Shared Types (`lib/types.ts`)

All interfaces below are copied from the authoritative contract at `specs/009-next-frontend/contracts/api-client.ts`. Do NOT invent additional fields.

```typescript
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

export type DocumentStatus = "pending" | "ingesting" | "completed" | "failed" | "duplicate";

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
  | "pending" | "started" | "streaming" | "embedding"
  | "completed" | "failed" | "paused";

// Terminal states -- stop polling when reached:
export const TERMINAL_JOB_STATES: IngestionJobStatus[] = ["completed", "failed"];

export interface ChatMessage {
  id: string;                       // client-generated uuid
  role: "user" | "assistant";
  content: string;                  // accumulated from chunk events
  citations?: Citation[];
  confidence?: number;              // integer 0-100; undefined until confidence event
  groundedness?: GroundednessData;
  clarification?: string;           // set when clarification event received
  isStreaming: boolean;             // true while chunk events arriving
  traceId?: string;                 // set from done event
}

export interface Citation {
  passage_id: string;
  document_id: string;
  document_name: string;
  start_offset: number;
  end_offset: number;
  text: string;
  relevance_score: number;          // float 0.0-1.0
  source_removed: boolean;          // CONSTITUTION IV: render "source removed" badge when true
  // NOTE: page and breadcrumb exist in backend RetrievedChunk (searcher.py) and
  // Qdrant payload but are NOT included in the Citation schema (schemas.py).
  // CitationTooltip renders document_name + text only.
  // When backend extends Citation model, add: page?: number; breadcrumb?: string;
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
  has_key: boolean;                 // never display raw key; show masked when true
  base_url: string | null;
  model_count: number;
}

export interface Settings {
  default_llm_model: string;
  default_embed_model: string;
  confidence_threshold: number;          // integer 0-100
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
  confidence_score: number | null;       // integer 0-100
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
  services: HealthService[];
}

export interface HealthService {
  name: string;                          // "sqlite" | "qdrant" | "ollama"
  status: "ok" | "error";
  latency_ms: number | null;
  error_message: string | null;
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
  | { type: "session";        session_id: string }
  | { type: "status";         node: string }
  | { type: "chunk";          text: string }            // field is "text", NOT "content"
  | { type: "clarification";  question: string }        // stream ends here; no "done" follows
  | { type: "citation";       citations: Citation[] }
  | { type: "meta_reasoning"; strategies_attempted: string[] }
  | { type: "confidence";     score: number }           // INTEGER 0-100
  | { type: "groundedness";   overall_grounded: boolean; supported: number; unsupported: number; contradicted: number }
  | { type: "done";           latency_ms: number; trace_id: string }
  | { type: "error";          message: string; code: string; trace_id: string };

export interface StreamChatCallbacks {
  onSession?: (sessionId: string) => void;
  onStatus?: (node: string) => void;
  onToken: (text: string) => void;                      // called on "chunk" event with event.text
  onClarification?: (question: string) => void;         // releases isStreaming
  onCitation: (citations: Citation[]) => void;
  onMetaReasoning?: (strategiesAttempted: string[]) => void;
  onConfidence: (score: number) => void;                // integer 0-100
  onGroundedness?: (data: GroundednessData) => void;
  onDone: (latencyMs: number, traceId: string) => void; // releases isStreaming
  onError: (message: string, code: string, traceId?: string) => void; // releases isStreaming
}

export interface ChatRequest {
  message: string;                   // 1-2000 chars
  collection_ids: string[];          // required, non-empty
  llm_model?: string;               // default: "qwen2.5:7b"
  embed_model?: string | null;
  session_id?: string | null;
}

// ─── Upload Constraints ───────────────────────────────────────────────────

export const UPLOAD_CONSTRAINTS = {
  maxSizeBytes: 50 * 1024 * 1024,                      // 50 MB client-side guard
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
  if (score >= 70) return "green";     // integer 0-100
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

// Common error codes:
// COLLECTION_NOT_FOUND, COLLECTION_NAME_INVALID, COLLECTION_NAME_CONFLICT
// DOCUMENT_NOT_FOUND, FILE_FORMAT_NOT_SUPPORTED, FILE_TOO_LARGE
// DUPLICATE_DOCUMENT, JOB_NOT_FOUND, PROVIDER_NOT_FOUND
// KEY_MANAGER_UNAVAILABLE, SETTINGS_VALIDATION_ERROR, TRACE_NOT_FOUND
// NO_COLLECTIONS, CIRCUIT_OPEN, SERVICE_UNAVAILABLE
```

### API Client (`lib/api.ts`)

All functions below are copied from the authoritative contract at `specs/009-next-frontend/contracts/api-client.ts`. The `streamChat()` function uses NDJSON (raw JSON lines) -- there is NO `data:` prefix.

```typescript
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

// Helper: parse error response body and throw ApiError
async function throwApiError(res: Response): Promise<never> {
  const body = await res.json().catch(() => ({ error: { code: "UNKNOWN", message: res.statusText } }));
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
  // GET /api/collections -> { collections: Collection[] }
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
  // POST /api/collections -> Collection (201)
  // Throws ApiError with code COLLECTION_NAME_CONFLICT (409) on duplicate name
}

export async function deleteCollection(collectionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
  // DELETE /api/collections/{collection_id} -> 204
}

// ─── Documents ────────────────────────────────────────────────────────────

export async function getDocuments(collectionId: string): Promise<Document[]> {
  const res = await fetch(`${API_BASE}/api/documents?collection_id=${collectionId}`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.documents;
  // GET /api/documents?collection_id={collectionId} -> { documents: Document[] }
}

export async function deleteDocument(docId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/documents/${docId}`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
  // DELETE /api/documents/{doc_id} -> 204
}

// ─── Ingestion ────────────────────────────────────────────────────────────

export async function ingestFile(
  collectionId: string,
  file: File,
): Promise<IngestionJob> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/ingest`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
  // POST /api/collections/{collectionId}/ingest (multipart/form-data, field: "file")
  // -> IngestionJob (202)
  // Client-side validation MUST happen BEFORE calling this function:
  //   - file.size <= UPLOAD_CONSTRAINTS.maxSizeBytes
  //   - extension in UPLOAD_CONSTRAINTS.allowedExtensions
}

export async function getIngestionJob(
  collectionId: string,
  jobId: string,
): Promise<IngestionJob> {
  const res = await fetch(`${API_BASE}/api/collections/${collectionId}/ingest/${jobId}`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/collections/{collectionId}/ingest/{jobId}
  // Poll every 2s until status in ["completed", "failed"]
}

// ─── Chat Streaming (NDJSON) ──────────────────────────────────────────────
//
// CRITICAL: This is NDJSON (application/x-ndjson), NOT Server-Sent Events.
// Each line is a raw JSON object. There is NO "data:" prefix.
// The "clarification" event ENDS the stream -- no "done" event follows.
// isStreaming MUST be released on "done", "error", AND "clarification".
//

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
  }).then(async (res) => {
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
        const event: NdjsonEvent = JSON.parse(line); // Raw JSON -- NO "data:" prefix
        switch (event.type) {
          case "session":        callbacks.onSession?.(event.session_id); break;
          case "status":         callbacks.onStatus?.(event.node); break;
          case "chunk":          callbacks.onToken(event.text); break;          // field is "text"
          case "clarification":  callbacks.onClarification?.(event.question); break; // stream ends
          case "citation":       callbacks.onCitation(event.citations); break;
          case "meta_reasoning": callbacks.onMetaReasoning?.(event.strategies_attempted); break;
          case "confidence":     callbacks.onConfidence(event.score); break;    // integer 0-100
          case "groundedness":   callbacks.onGroundedness?.(event); break;
          case "done":           callbacks.onDone(event.latency_ms, event.trace_id); break;
          case "error":          callbacks.onError(event.message, event.code, event.trace_id); break;
        }
      }
    }
  }).catch((err) => {
    if (err.name !== "AbortError") {
      callbacks.onError("Connection error -- please check that the backend is running", "NETWORK_ERROR");
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
  // GET /api/models/llm -> { models: ModelInfo[] }
}

export async function getEmbedModels(): Promise<ModelInfo[]> {
  const res = await fetch(`${API_BASE}/api/models/embed`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.models;
  // GET /api/models/embed -> { models: ModelInfo[] }
}

// ─── Providers ────────────────────────────────────────────────────────────

export async function getProviders(): Promise<Provider[]> {
  const res = await fetch(`${API_BASE}/api/providers`);
  if (!res.ok) await throwApiError(res);
  const data = await res.json();
  return data.providers;
  // GET /api/providers -> { providers: Provider[] }
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
  // PUT /api/providers/{name}/key  body: { api_key: string }
}

export async function deleteProviderKey(
  providerName: string,
): Promise<{ name: string; has_key: false }> {
  const res = await fetch(`${API_BASE}/api/providers/${providerName}/key`, {
    method: "DELETE",
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
  // DELETE /api/providers/{name}/key
}

// ─── Settings ─────────────────────────────────────────────────────────────

export async function getSettings(): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/settings -> Settings
}

export async function updateSettings(
  data: Partial<Settings>,
): Promise<Settings> {
  const res = await fetch(`${API_BASE}/api/settings`, {
    method: "PUT",                   // PUT, NOT PATCH
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) await throwApiError(res);
  return res.json();
  // PUT /api/settings (NOT PATCH) with partial body -> Settings
  // Show Toast on success/error -- NO optimistic UI
}

// ─── Traces ───────────────────────────────────────────────────────────────

export async function getTraces(params?: {
  session_id?: string;
  collection_id?: string;
  min_confidence?: number;
  max_confidence?: number;
  limit?: number;      // default 20, max 100
  offset?: number;     // default 0
}): Promise<{ traces: QueryTrace[]; total: number; limit: number; offset: number }> {
  const searchParams = new URLSearchParams();
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) searchParams.set(key, String(value));
    }
  }
  const res = await fetch(`${API_BASE}/api/traces?${searchParams}`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/traces
}

export async function getTraceDetail(traceId: string): Promise<QueryTraceDetail> {
  const res = await fetch(`${API_BASE}/api/traces/${traceId}`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/traces/{trace_id}
}

// ─── Health & Stats ───────────────────────────────────────────────────────

export async function getHealth(): Promise<HealthStatus> {
  const res = await fetch(`${API_BASE}/api/health`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/health -> HealthStatus (200 healthy, 503 degraded)
}

export async function getStats(): Promise<SystemStats> {
  const res = await fetch(`${API_BASE}/api/stats`);
  if (!res.ok) await throwApiError(res);
  return res.json();
  // GET /api/stats -> SystemStats
}
```

### Component Props Interfaces

```typescript
// ChatPanel
interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
}

// ChatInput
interface ChatInputProps {
  isStreaming: boolean;
  selectedCollections: string[];     // send disabled when empty
  onSubmit: (message: string) => void;
}

// ChatSidebar
interface ChatSidebarProps {
  selectedCollections: string[];
  onCollectionsChange: (ids: string[]) => void;
  llmModel: string;
  onLLMModelChange: (model: string) => void;
  embedModel: string | null;
  onEmbedModelChange: (model: string | null) => void;
}

// ConfidenceIndicator
interface ConfidenceIndicatorProps {
  score: number;                     // integer 0-100
}

// CitationTooltip
interface CitationTooltipProps {
  citation: Citation;
  index: number;                     // display as [N]
}

// CollectionCard
interface CollectionCardProps {
  collection: Collection;
  onDelete: (id: string) => void;
}

// CreateCollectionDialog
interface CreateCollectionDialogProps {
  onCreated: () => void;             // calls mutate
}

// DocumentList
interface DocumentListProps {
  documents: Document[];
  onDelete: (id: string) => void;
}

// DocumentUploader
interface DocumentUploaderProps {
  collectionId: string;
  onUploadComplete: () => void;      // calls mutate
}

// ModelSelector
interface ModelSelectorProps {
  models: ModelInfo[];
  selectedModel: string;
  onSelect: (model: string) => void;
  placeholder?: string;
}

// ProviderHub (no props -- fetches own data)

// Toast
interface ToastProps {
  message: string;
  type: "success" | "error";
  onDismiss: () => void;
}

// TraceTable
interface TraceTableProps {
  traces: QueryTrace[];
  total: number;
  limit: number;
  offset: number;
  onPageChange: (offset: number) => void;
  sessionFilter?: string;
  onSessionFilterChange: (sessionId: string) => void;
}

// HealthDashboard (no props -- fetches own data via getHealth)

// LatencyChart
interface LatencyChartProps {
  traces: QueryTrace[];
}

// ConfidenceDistribution
interface ConfidenceDistributionProps {
  traces: QueryTrace[];
}

// CollectionStats (no props -- fetches own data via useCollections + getStats)
```

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |

### next.config.ts

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
  },
  experimental: {
    optimizePackageImports: [
      "@radix-ui/react-tooltip",
      "@radix-ui/react-dialog",
      "@radix-ui/react-select",
    ],
  },
};

export default nextConfig;
```

### Package Dependencies

```json
{
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "tailwindcss": "^4.0.0",
    "swr": "^2.0.0",
    "recharts": "^2.0.0",
    "react-dropzone": "^14.0.0",
    "@radix-ui/react-tooltip": "latest",
    "@radix-ui/react-dialog": "latest",
    "@radix-ui/react-select": "latest",
    "react-hook-form": "latest"
  },
  "devDependencies": {
    "typescript": "^5.7.0",
    "vitest": "^3.0.0",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "latest",
    "@playwright/test": "^1.50.0",
    "@vitejs/plugin-react": "latest",
    "jsdom": "latest",
    "@vitest/coverage-v8": "latest"
  }
}
```

---

## Error Handling

**Error response format** (from spec-08-api):

```typescript
// Non-streaming errors follow this shape:
interface ApiErrorResponse {
  error: {
    code: string;          // e.g., "COLLECTION_NAME_CONFLICT"
    message: string;       // human-readable message
    details?: Record<string, unknown>;
  };
  trace_id: string;
}
```

**Rules**:

1. All API functions in `lib/api.ts` throw `ApiError(status, code, message, traceId)` on non-OK responses.
2. Components catch `ApiError` and display `error.message` to the user. Use `error.code` for programmatic branching (e.g., `COLLECTION_NAME_CONFLICT` keeps dialog open).
3. NDJSON stream errors arrive as `{ type: "error", message, code, trace_id }` events and are dispatched to `callbacks.onError`.
4. Network failures (fetch rejection) show: "Connection error -- please check that the backend is running".
5. File upload errors display specific messages based on `error.code`: `FILE_FORMAT_NOT_SUPPORTED`, `FILE_TOO_LARGE`, `DUPLICATE_DOCUMENT`.
6. SWR hooks surface errors via `isError` for components to render error states.

---

## Testing Protocol

**NEVER run vitest, playwright, or npm test inline inside Claude Code.** All test execution is initiated via npm scripts and monitored externally.

```bash
# TypeScript compile check (before each wave gate)
cd frontend && npx tsc --noEmit

# Unit tests (vitest)
cd frontend && npm run test -- --run

# E2E tests (Playwright)
cd frontend && npx playwright test

# Coverage check
cd frontend && npm run test:coverage

# Python regression baseline (no backend changes in spec-09, but verify no regressions)
zsh scripts/run-tests-external.sh -n spec09-regression tests/
cat Docs/Tests/spec09-regression.status     # RUNNING | PASSED | FAILED | ERROR
cat Docs/Tests/spec09-regression.summary    # ~20 lines when done
```

**Rules for all agents:**
- Do not run `npm test` interactively inside a Claude Code session -- run in background or via script.
- Do not read `.log` files directly; read `.summary` files only.
- Wave gates must be PASSED before the next wave starts.
- `npx tsc --noEmit` must return zero errors before any agent reports DONE.

---

## Key Code Patterns

### NDJSON Stream Parsing (NOT Server-Sent Events)

The backend emits `application/x-ndjson` -- raw JSON lines with **NO** `data:` prefix. See `streamChat()` in the API Client section above. Key points:

- Use `ReadableStream` + `TextDecoder` + line-by-line `JSON.parse()`
- **Never** strip a `data:` prefix (there is none)
- All 10 event types must be handled: `session`, `status`, `chunk`, `clarification`, `citation`, `meta_reasoning`, `confidence`, `groundedness`, `done`, `error`
- The `chunk` event has field `text` (NOT `content`)
- The `clarification` event **ends** the stream -- no `done` event follows. `isStreaming` MUST be released on `clarification` in addition to `done` and `error`

### Send-Button Lock

```typescript
const [isStreaming, setIsStreaming] = useState(false);

// In useStreamChat: setIsStreaming(true) on submit,
// setIsStreaming(false) inside onDone, onError, AND onClarification callbacks

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
// confidence event: { type: "confidence", score: number } -- score is integer 0-100
const getConfidenceTier = (score: number): "green" | "yellow" | "red" => {
  if (score >= 70) return "green";
  if (score >= 40) return "yellow";
  return "red";
};

// ConfidenceIndicator renders a dot colored by tier, numeric score visible on Radix Tooltip hover
```

### 50 MB Upload Guard

```typescript
const handleDrop = (files: File[]) => {
  for (const file of files) {
    if (file.size > UPLOAD_CONSTRAINTS.maxSizeBytes) {
      setFileError(`${file.name} exceeds the 50 MB limit. Choose a smaller file.`);
      return; // Do NOT call ingestFile() -- no network request
    }
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (!ext || !(UPLOAD_CONSTRAINTS.allowedExtensions as readonly string[]).includes(ext)) {
      setFileError(`${file.name}: unsupported file type. Allowed: pdf, md, txt, rst`);
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
    await updateSettings(data);     // PUT /api/settings
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
const llmModel = searchParams.get("llm") ?? "qwen2.5:7b";
```

---

## Done Criteria

1. All five pages (`/chat`, `/collections`, `/documents/[id]`, `/settings`, `/observability`) render without errors.
2. `lib/api.ts` contains typed functions for every backend endpoint (17+ functions).
3. `lib/types.ts` contains all shared TypeScript interfaces matching backend schemas from `contracts/api-client.ts`.
4. Chat page streams tokens via **NDJSON** (NOT SSE) and accumulates them into the message thread.
5. All **10 NDJSON event types** are handled: session, status, chunk, clarification, citation, meta_reasoning, confidence, groundedness, done, error.
6. `isStreaming` is released on `done`, `error`, **AND** `clarification` events.
7. Citation markers render inline; `CitationTooltip` shows `text` + `document_name`; renders "source removed" badge when `source_removed === true`.
8. `ConfidenceIndicator` uses **integer 0-100**: green >= 70, yellow >= 40, red < 40.
9. Collection creation validates name against `^[a-z0-9][a-z0-9_-]*$`; conflict error displays **without closing dialog**.
10. File upload enforces 50 MB guard **and** extension allowlist BEFORE any network request.
11. Settings saves use `PUT /api/settings` (NOT PATCH); Toast shown on success/error; no optimistic UI.
12. `ProviderHub` never displays raw API keys -- shows `has_key: bool` only.
13. Observability: `HealthStatus` has `{ status, services[] }` structure (NOT flat fields).
14. Selected collections and models are persisted in URL query params.
15. All vitest unit tests pass; Playwright E2E pass; TypeScript strict compiles; no Python regressions.
