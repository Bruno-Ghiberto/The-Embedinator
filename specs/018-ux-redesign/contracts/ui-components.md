# UI Component Contracts: UX/UI Redesign

**Phase 1 output** | **Date**: 2026-03-19

## New Custom Components

### SidebarNav

**Purpose**: Replaces Navigation.tsx. Collapsible sidebar with app nav, theme toggle, and status indicator.
**File**: `components/SidebarNav.tsx`
**Props**: None (self-contained, reads pathname via `usePathname()`)
**Dependencies**: shadcn Sidebar (compound), ThemeToggle, lucide-react icons
**Behavior**:
- Renders 5 navigation links with icons
- Active link derived from current pathname
- Collapsed state: icon-only (~56px); expanded state: icons + labels (~240px)
- Footer: ThemeToggle + health status dot
- Mobile: handled by shadcn Sidebar's built-in Sheet overlay

---

### ThemeToggle

**Purpose**: Toggles dark/light mode.
**File**: `components/ThemeToggle.tsx`
**Props**: None
**Dependencies**: `next-themes` (useTheme hook), lucide-react (Sun, Moon)
**Behavior**:
- Displays Sun icon when in dark mode (click → light)
- Displays Moon icon when in light mode (click → dark)
- Uses `resolvedTheme` from `useTheme()` to determine current state
- Must be a client component (`'use client'`)

---

### CommandPalette

**Purpose**: Cmd+K searchable command palette.
**File**: `components/CommandPalette.tsx`
**Props**: None (rendered globally in layout.tsx)
**Dependencies**: shadcn Command, Dialog, lucide-react (Search)
**Behavior**:
- Opens on `Cmd+K` (macOS) or `Ctrl+K` (Windows/Linux)
- Searchable list of commands:
  - Navigate: Chat, Collections, Documents, Settings, Observability
  - Actions: Create Collection, Clear Chat, Toggle Dark Mode
- Selecting a command executes it (navigation via `useRouter()`, actions via callbacks)
- Closes on Escape or selection

---

### PageBreadcrumb

**Purpose**: Shows current navigation context at top of content area.
**File**: `components/PageBreadcrumb.tsx`
**Props**: `{ items?: { label: string; href?: string }[] }` (optional override)
**Dependencies**: shadcn Breadcrumb
**Behavior**:
- Default: derives breadcrumb from `usePathname()` (e.g., `/documents/abc` → "Documents / abc")
- Optional `items` prop for custom overrides (e.g., collection name instead of ID)

---

### useChatStorage (Hook)

**Purpose**: localStorage persistence for chat messages.
**File**: `hooks/useChatStorage.ts`
**Returns**: `{ storedMessages: ChatMessage[], sessionId: string | null, saveMessages: (msgs, sessionId) => void, clearChat: () => void }`
**Dependencies**: None (pure localStorage interaction)
**Behavior**:
- Reads from `localStorage.getItem("embedinator-chat-session")`
- Parses JSON into `StoredChat` shape: `{ sessionId, messages, updatedAt }`
- `saveMessages()`: writes current conversation (auto-evicts previous session if sessionId differs)
- `clearChat()`: removes the localStorage entry entirely
- Returns empty array + null sessionId if nothing stored

## Existing Component Contracts (Preserved)

The following interfaces from `lib/types.ts` are UNCHANGED — all 18 interfaces remain as-is:

- `ChatMessage`, `ChatRequest`, `StreamChatCallbacks`, `NdjsonEvent`
- `Citation`, `Collection`, `Document`, `IngestionJob`
- `ModelInfo`, `Provider`, `Settings`, `SettingsUpdateRequest`
- `QueryTrace`, `QueryTraceDetail`, `HealthStatus`, `HealthService`
- `SystemStats`, `GroundednessData`
- Type aliases: `ConfidenceTier`, `DocumentStatus`, `IngestionJobStatus`
- Constants: `getConfidenceTier`, `TERMINAL_JOB_STATES`, `UPLOAD_CONSTRAINTS`

## Existing Hook Contracts (Preserved)

All 5 hooks remain unchanged:
- `useStreamChat()` → `{ messages, isStreaming, sendMessage }`
- `useCollections()` → `{ collections, isLoading, mutate }`
- `useModels()` → `{ llmModels, embedModels, isLoading }`
- `useTraces(params)` → `{ traces, total, limit, isLoading, isError }`
- `useMetrics()` → `{ stats, isLoading }`

## API Client Contract (Preserved)

`lib/api.ts` — all functions unchanged. No new API endpoints. No modified signatures.
