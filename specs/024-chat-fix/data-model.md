# Data Model: Chat & Agentic RAG Pipeline Fix

**Feature**: 024-chat-fix | **Date**: 2026-03-27

## Entities

No new entities are created by this spec. This document records the existing entities relevant to the bug fixes and their state transitions.

### ChatMessage (Frontend — `lib/types.ts`)

| Field | Type | Notes |
|-------|------|-------|
| id | string (UUID) | Generated client-side via `crypto.randomUUID()` |
| role | "user" \| "assistant" | |
| content | string | Accumulates via `onToken` callback during streaming |
| citations | Citation[] \| undefined | Set by `onCitation` callback |
| confidence | number \| undefined | Set by `onConfidence` callback (0-100) |
| groundedness | GroundednessData \| undefined | Set by `onGroundedness` callback |
| clarification | string \| undefined | Set by `onClarification` callback |
| isStreaming | boolean | `true` during streaming, `false` after `onDone` or `onError` |
| isError | boolean \| undefined | `true` if `onError` fired |
| traceId | string \| undefined | Set by `onDone` callback |

**State transitions** (assistant message):
```
Created (content="", isStreaming=true)
  → onToken: content accumulates (content="...", isStreaming=true)
  → onCitation: citations set
  → onConfidence: confidence set
  → onGroundedness: groundedness set
  → onDone: isStreaming=false, traceId set
  OR
  → onError: content=error message, isStreaming=false, isError=true
```

**BUG-013 impact**: The `Created → onToken` transition is never reaching the render cycle. The `content` field stays empty, causing the skeleton placeholder to persist.

### ChatSession (Frontend — `hooks/useChatHistory.ts`)

| Field | Type | Notes |
|-------|------|-------|
| id | string (UUID) | Generated client-side |
| title | string | Initially "New Chat", updated to first user message (40 chars) after streaming completes |
| messageCount | number | Updated via `syncMessages` after streaming completes |
| messages | ChatMessage[] | Full message history |
| config | SessionConfig | { collectionIds, llmModel, embedModel } |
| createdAt | string (ISO) | |
| updatedAt | string (ISO) | |

**Storage**: `localStorage` key `embedinator-sessions:v1`, JSON object with `version: 1` and `sessions: Record<string, ChatSessionData>`. Max 50 sessions (LRU eviction).

**BUG-015 impact**: `title` stays "New Chat" and `messageCount` stays 0 because `syncMessages` only fires when `isStreaming` transitions from `true` to `false`. If BUG-013 prevents this transition from being detected, sessions are never updated.

### Citation (Backend — `agent/schemas.py`)

| Field | Type | Notes |
|-------|------|-------|
| passage_id | string | UUID — unique key for deduplication |
| document_id | string | UUID of source document |
| document_name | string | Filename |
| start_offset | int | Character offset in source |
| end_offset | int | Character offset in source |
| text | string | Passage excerpt |
| relevance_score | float | Cross-encoder score |
| source_removed | bool | True if source doc deleted |

**BUG-017 impact**: `passage_id` is the deduplication key. After `Send()` fan-out, the same citation may appear N times (once per sub-question that found it). Dedup at emission reduces the array to unique `passage_id` entries.

## Legacy Storage (Candidate for Removal)

### useChatStorage (Frontend — `hooks/useChatStorage.ts`)

| Field | Type | Notes |
|-------|------|-------|
| sessionId | string | |
| messages | ChatMessage[] | |
| updatedAt | number | Unix timestamp |

**Storage**: `localStorage` key `embedinator-chat-session`, single JSON object.

**BUG-013 impact**: This is the legacy single-session system. `ChatPageContent` hydrates from this on mount (line 124-129), potentially overwriting messages set by `useStreamChat.sendMessage`. **Recommended action**: Remove entirely — `useChatHistory` handles all persistence.
