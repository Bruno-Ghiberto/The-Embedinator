# UI Component Contracts: Frontend PRO (Spec 022)

**Scope**: Props interfaces and behavioral contracts for all new components. These contracts define the public API that the implementation must satisfy.

---

## ChatToolbar

**File**: `components/ChatToolbar.tsx`
**Type**: Client Component (`'use client'`)
**Memo**: `React.memo` — re-renders only when config changes

```typescript
interface ChatToolbarProps {
  collections: Collection[]       // Active collections to display as badges
  model: string                   // Active LLM model name
  onNewChat: () => void           // Callback when "New Chat" button clicked
  onToggleConfig: () => void      // Callback when gear icon clicked
  isConfigOpen: boolean           // Whether config panel is expanded
}
```

**Behavior**:
- Renders as a 40px slim bar above the chat message area
- Shows collection names as `Badge variant="secondary"` pills
- Shows model name as `Badge variant="outline"` pill
- "New Chat" button uses `Button variant="ghost" size="icon"`
- Gear icon toggles `isConfigOpen` state via `onToggleConfig`
- When no collections selected: shows "Select a collection" hint text

---

## ChatConfigPanel

**File**: `components/ChatConfigPanel.tsx`
**Type**: Client Component (`'use client'`)

```typescript
interface ChatConfigPanelProps {
  isOpen: boolean                          // Controlled open state
  onOpenChange: (open: boolean) => void    // State change callback
  collections: Collection[]                // All available collections
  selectedCollectionIds: string[]          // Currently selected IDs
  onCollectionChange: (ids: string[]) => void  // Selection change
  llmModels: ModelInfo[]                   // Available LLM models
  embedModels: ModelInfo[]                 // Available embed models
  selectedLlmModel: string                // Current LLM model
  selectedEmbedModel: string              // Current embed model
  onLlmModelChange: (model: string) => void
  onEmbedModelChange: (model: string) => void
}
```

**Behavior**:
- Wrapped in shadcn `Collapsible` component
- Expands below the `ChatToolbar` when `isOpen` is true
- Contains: collection checkboxes (multi-select), LLM dropdown, embed dropdown
- Changes apply immediately (auto-apply on change, no "Apply" button)
- Collapses with smooth animation

---

## ChatMessageBubble

**File**: `components/ChatMessageBubble.tsx`
**Type**: Client Component (`'use client'`)
**Memo**: `React.memo` on `message.content` + `message.citations`

```typescript
interface ChatMessageBubbleProps {
  message: ChatMessage              // The message to render
  isStreaming?: boolean             // Whether this message is currently streaming
  currentStage?: string            // Current pipeline stage (for stage indicator)
  onCitationClick?: (citation: Citation) => void  // Navigate to source
}
```

**Behavior**:
- User messages: right-aligned, primary background
- Assistant messages: left-aligned, muted background, rendered through `MarkdownRenderer`
- During streaming: shows blinking cursor at end, PipelineStageIndicator below
- After completion: shows confidence indicator and citations section
- Applies `content-visibility: auto` CSS for virtualization in long lists

---

## MarkdownRenderer

**File**: `components/MarkdownRenderer.tsx`
**Type**: Client Component (`'use client'`)
**Loading**: Dynamic import with `next/dynamic`, `ssr: false`

```typescript
interface MarkdownRendererProps {
  content: string                   // Markdown text to render
  className?: string                // Additional CSS classes
  isStreaming?: boolean             // True if content is still arriving
}
```

**Behavior**:
- Renders markdown using `react-markdown` + `remark-gfm` + `rehype-highlight`
- Custom component map defined at MODULE level (not inside render)
- Strips all raw HTML by default (XSS safe)
- When `isStreaming` and incomplete code fence detected: shows skeleton for the incomplete block
- Code blocks include copy-to-clipboard button (absolute positioned top-right)

---

## CitationHoverCard

**File**: `components/CitationHoverCard.tsx`
**Type**: Client Component (`'use client'`)
**Memo**: `React.memo` on citation data

```typescript
interface CitationHoverCardProps {
  citationNumber: number            // Display number [1], [2], etc.
  citation: Citation                // Citation data
  collectionId?: string             // For navigation on click
  onClick?: () => void              // Navigate to source document
}
```

**Behavior**:
- Trigger: small rounded pill `[N]` with `bg-primary/10 text-primary`
- HoverCard `openDelay={200}`
- Content: document name (bold, truncated), collection name (muted), excerpt (2-3 lines, `line-clamp-3`), relevance score bar
- Click: calls `onClick` which navigates to `/documents/:collectionId`
- On mobile: tap to show (no hover available)

---

## PipelineStageIndicator

**File**: `components/PipelineStageIndicator.tsx`
**Type**: Client Component (`'use client'`)

```typescript
interface PipelineStageIndicatorProps {
  stage: string | null              // Current pipeline node name (from NDJSON status event)
  isVisible: boolean                // Show/hide the indicator
}
```

**Behavior**:
- Maps node names to labels via `lib/stage-labels.ts`
- Renders as animated pill with spinner icon
- Smooth text transition between stages (CSS transition on opacity)
- Hidden when `isVisible` is false or `stage` is null

---

## ScrollToBottom

**File**: `components/ScrollToBottom.tsx`
**Type**: Client Component (`'use client'`)

```typescript
interface ScrollToBottomProps {
  scrollContainerRef: React.RefObject<HTMLElement>  // The scrollable container
  isStreaming: boolean               // Whether streaming is active
}
```

**Behavior**:
- Shows when `scrollTop + clientHeight < scrollHeight - 100` (100px threshold)
- Hidden when user is at or near bottom
- Circular button with ArrowDown icon, fixed position above chat input
- Click: smooth scroll to bottom of container
- Uses `{ passive: true }` on scroll listener (Vercel best practice)

---

## ChatHistory

**File**: `components/ChatHistory.tsx`
**Type**: Client Component (`'use client'`)
**Loading**: Dynamic import (optional — not needed on initial sidebar paint)

```typescript
interface ChatHistoryProps {
  sessions: ChatSessionSummary[]    // All sessions, sorted by updatedAt desc
  activeSessionId: string | null    // Currently loaded session
  onSessionClick: (id: string) => void     // Load a session
  onSessionRename: (id: string, title: string) => void
  onSessionDelete: (id: string) => void
  searchQuery: string               // Current search filter
  onSearchChange: (query: string) => void
}

interface ChatSessionSummary {
  id: string
  title: string
  messageCount: number
  updatedAt: string                 // ISO 8601
}
```

**Behavior**:
- Groups sessions by: Today, Yesterday, Previous 7 Days, Older
- Each entry: title (truncated), relative timestamp ("2h ago"), message count badge
- Active session highlighted with `isActive` styling
- Hover actions: rename (inline edit), delete (with confirmation Dialog)
- Search bar at top filters sessions by title
- Renders inside `SidebarNav.tsx` as a `SidebarGroup`

---

## IngestionProgress

**File**: `components/IngestionProgress.tsx`
**Type**: Client Component (`'use client'`)

```typescript
interface IngestionProgressProps {
  collectionId: string              // Collection being ingested into
  jobId: string                     // Ingestion job ID to poll
  onComplete: () => void            // Called when job completes (refresh doc list)
  onRetry: () => void               // Called when user clicks retry after failure
}
```

**Behavior**:
- Polls `GET /api/collections/:id/ingest/:jobId` every 2 seconds
- Shows shadcn `Progress` with status label and chunk count
- Status labels: "Pending...", "Processing...", "Embedding...", "Complete!", "Failed"
- On `completed`: calls `onComplete`, shows success toast via Sonner
- On `failed`: shows error message inline with retry button
- Stops polling on terminal states

---

## hooks/useChatHistory

**File**: `hooks/useChatHistory.ts`

```typescript
interface UseChatHistoryReturn {
  sessions: ChatSessionSummary[]     // All sessions sorted by updatedAt desc
  activeSession: ChatSessionData | null  // Currently loaded session
  isLoading: boolean                 // True during initial load from localStorage
  createSession: (config: SessionConfig) => string  // Returns new session ID
  loadSession: (id: string) => void  // Load session messages into state
  saveMessage: (sessionId: string, message: ChatMessage) => void
  deleteSession: (id: string) => void
  renameSession: (id: string, title: string) => void
  searchSessions: (query: string) => ChatSessionSummary[]
}
```

**Storage Rules**:
- Key: `embedinator-sessions:v1`
- All access in try-catch (private browsing)
- Maximum 50 sessions (LRU eviction)
- Read in `useEffect` (hydration safe)
- Migration from old `embedinator-chat-session` key on first load

---

## lib/stage-labels.ts

```typescript
export const stageLabels: Record<string, string> = {
  intent_analysis: "Understanding your question...",
  research: "Searching documents...",
  tools_node: "Retrieving sources...",
  compress_check: "Analyzing relevance...",
  generate_response: "Writing response...",
  verify_groundedness: "Verifying accuracy...",
  evaluate_confidence: "Assessing confidence...",
}

export function getStageLabel(node: string): string
// Returns the human-readable label, or the raw node name if not mapped
```

---

## lib/markdown-components.tsx

```typescript
// Defined at MODULE level (Vercel rerender-no-inline-components rule)
export const markdownComponents: Components = {
  h1: /* text-2xl font-bold text-foreground mt-6 mb-3 */,
  h2: /* text-xl font-semibold text-foreground mt-5 mb-2 */,
  h3: /* text-lg font-medium text-foreground mt-4 mb-2 */,
  h4: /* text-base font-medium text-foreground mt-3 mb-1 */,
  code: /* inline: bg-muted rounded px-1.5 py-0.5 text-sm font-mono */,
  pre: /* relative group: contains code block + copy button */,
  a: /* text-primary underline hover:text-primary/80 target=_blank */,
  ul: /* list-disc pl-6 space-y-1 */,
  ol: /* list-decimal pl-6 space-y-1 */,
  table: /* border-collapse border-border w-full */,
  blockquote: /* border-l-4 border-primary/30 pl-4 italic text-muted-foreground */,
  img: /* max-w-full rounded */,
}
```

**Key Rule**: Must destructure `node` from props before spreading: `({ node, children, ...props }) => ...`
