# Data Model: Frontend PRO (Spec 022)

**Scope**: Frontend-only data model. All entities are client-side (React state + localStorage). Backend API entities are consumed as-is — no backend schema changes.

---

## Entity: ChatSession

**Storage**: localStorage (`embedinator-sessions:v1`)
**Lifecycle**: Created on first message → Updated on each message → Evicted when over 50 sessions (LRU by `updatedAt`)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `id` | `string` | UUID, unique | Session identifier |
| `title` | `string` | max 40 chars | Auto-derived from first user message, truncated |
| `messages` | `ChatMessage[]` | ordered by timestamp | All messages in the conversation |
| `config` | `SessionConfig` | required | Active configuration at time of chat |
| `createdAt` | `string` | ISO 8601 | When session was created |
| `updatedAt` | `string` | ISO 8601 | When last message was added |

**Relationships**:
- Has many `ChatMessage` (ordered)
- Has one `SessionConfig` (embedded)

**State Transitions**:
```
[New] --first message--> [Active] --user navigates away--> [Saved]
[Saved] --user clicks in sidebar--> [Active]
[Saved] --50 session limit reached, oldest updatedAt--> [Evicted]
[Active/Saved] --user clicks delete--> [Deleted]
```

---

## Entity: ChatMessage

**Storage**: Embedded within `ChatSession.messages[]`
**Lifecycle**: Created during conversation → Persisted with session → Deleted with session

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `role` | `"user" \| "assistant"` | required | Message author |
| `content` | `string` | required | Message text (may contain markdown for assistant) |
| `citations` | `Citation[]` | optional, assistant only | Source references from NDJSON `citation` event |
| `confidence` | `number` | 0-100, optional, assistant only | Confidence score from NDJSON `confidence` event |
| `groundedness` | `GroundednessData` | optional, assistant only | Claim verification from NDJSON `groundedness` event |
| `timestamp` | `string` | ISO 8601 | When message was created |
| `stageHistory` | `string[]` | optional, assistant only | Pipeline stages traversed (from `status` events) |

**Relationships**:
- Belongs to one `ChatSession`
- Has many `Citation` (optional, embedded)
- Has one `GroundednessData` (optional, embedded)

---

## Entity: SessionConfig

**Storage**: Embedded within `ChatSession.config`
**Lifecycle**: Set when session is created or config panel is changed

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `collectionIds` | `string[]` | at least 1 for chat to work | Selected collection UUIDs |
| `llmModel` | `string` | required | Active LLM model name |
| `embedModel` | `string` | required | Active embedding model name |

**Relationships**:
- Belongs to one `ChatSession`
- References `Collection` entities (by ID, from backend API)

---

## Entity: Citation

**Storage**: Embedded within `ChatMessage.citations[]`
**Source**: NDJSON `{ type: "citation", citations: Citation[] }` event

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `document_name` | `string` | required | Source document filename |
| `text` | `string` | required | Passage excerpt from the source |
| `relevance_score` | `number` | 0.0-1.0 | How relevant this citation is to the query |
| `passage_id` | `string` | required | Identifier for the specific chunk |

**Relationships**:
- Belongs to one `ChatMessage`
- References a `Document` in a `Collection` (via backend, not stored locally)

**Display Rules**:
- Relevance >= 0.7: green indicator
- Relevance 0.4-0.69: yellow indicator
- Relevance < 0.4: red indicator

---

## Entity: GroundednessData

**Storage**: Embedded within `ChatMessage.groundedness`
**Source**: NDJSON `{ type: "groundedness", ... }` event

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `overall_grounded` | `boolean` | required | Whether the response is grounded overall |
| `supported` | `number` | >= 0 | Number of claims supported by sources |
| `unsupported` | `number` | >= 0 | Number of claims not supported |
| `contradicted` | `number` | >= 0 | Number of claims contradicted by sources |

**Relationships**:
- Belongs to one `ChatMessage`

---

## Entity: IngestionJob (Read-only from API)

**Storage**: None (fetched from backend API, displayed in UI only)
**Source**: `GET /api/collections/:id/ingest/:jobId`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `job_id` | `string` | required | Job identifier |
| `status` | `string` | `pending \| processing \| embedding \| completed \| failed` | Current ingestion status |
| `chunks_processed` | `number` | optional | Number of chunks processed so far |
| `chunks_total` | `number` | optional | Total chunks expected |
| `error` | `string` | optional, only when `failed` | Error description |

**State Transitions**:
```
[pending] --> [processing] --> [embedding] --> [completed]
                    \                  \
                     --> [failed]       --> [failed]
```

**Polling Rules**:
- Poll every 2 seconds while status is non-terminal
- Stop polling when status is `completed` or `failed`
- On `completed`: refresh document list, show success toast
- On `failed`: show error inline with retry button

---

## localStorage Schema

**Version**: v1
**Key**: `embedinator-sessions:v1`
**Format**:
```typescript
interface SessionStore {
  version: 1;
  sessions: Record<string, ChatSessionData>;  // keyed by session ID
}
```

**Limits**:
- Maximum 50 sessions
- Eviction: oldest by `updatedAt` when limit reached
- All access wrapped in try-catch (private browsing fails silently)

**Migration**:
- On first load, check for old key `embedinator-chat-session`
- If found: extract messages, create a new v1 session, delete old key
- If not found: initialize empty `SessionStore`

**Other localStorage Keys** (existing, unchanged):
- `sidebar_state` cookie (managed by shadcn SidebarProvider, not localStorage)
- `theme` (managed by next-themes)
