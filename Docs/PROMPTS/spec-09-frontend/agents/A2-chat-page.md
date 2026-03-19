# Agent A2: Chat Page Architect

**Agent Type**: `frontend-architect`
**Model**: Opus
**Wave**: 2 (parallel with A3)
**Tasks**: T015-T021

## Mission

Build the most complex page in the application: the multi-turn chat interface with NDJSON streaming, inline citation tooltips with source_removed awareness, confidence indicator using integer 0-100 scoring, send-button lock during streaming, and URL-persisted collection/model state.

## Authoritative Sources

Read these files FIRST before writing any code:

- `specs/009-next-frontend/contracts/api-client.ts` -- NDJSON event types, Citation interface, ChatRequest
- `specs/009-next-frontend/data-model.md` -- ChatMessage, Citation, GroundednessData, NdjsonEvent, confidence tiers
- `specs/009-next-frontend/tasks.md` -- Task list with exact descriptions for T015-T021
- `Docs/PROMPTS/spec-09-frontend/09-implement.md` -- Component props, code patterns, NDJSON stream parsing

## Tasks

1. **T015** [P] [US1] Create `frontend/components/ConfidenceIndicator.tsx` -- integer 0-100 score; `getConfidenceTier`: >= 70 green, >= 40 yellow, < 40 red; colored dot; numeric score visible on Radix Tooltip hover
2. **T016** [P] [US1] Create `frontend/components/CitationTooltip.tsx` -- Radix Tooltip wrapping inline `[N]` citation marker; renders `citation.text` (passage) and `citation.document_name` (file name); renders "source removed" badge when `citation.source_removed === true` (Constitution IV); do NOT fabricate `page` or `breadcrumb` fields
3. **T017** [P] [US1] Create `frontend/components/ChatInput.tsx` -- controlled textarea; send button `disabled={isStreaming || !message.trim() || selectedCollections.length === 0}`; Enter-to-submit (Shift+Enter for newline); `onSubmit(message)` callback; clears on submit
4. **T018** [P] [US1] Create `frontend/components/ModelSelector.tsx` -- Radix Select wrapping `ModelInfo[]`; separate exports `LLMModelSelector` and `EmbedModelSelector`; `selectedModel: string`, `onSelect: (model: string) => void` props
5. **T019** [US1] Create `frontend/components/ChatSidebar.tsx` -- collection multi-select checkboxes from `useCollections`; `LLMModelSelector` and `EmbedModelSelector`; reads/writes URL params via `useSearchParams` + `useRouter`; lazy `useState` init for URL param parsing
6. **T020** [US1] Create `frontend/components/ChatPanel.tsx` -- scrollable multi-turn message thread; new Q&A appended at bottom; token accumulation via functional `setState`; `CitationTooltip` rendered per citation in assistant message; `ConfidenceIndicator` shown after complete response; passive scroll event listener; auto-scroll to bottom on new message
7. **T021** [US1] Create `frontend/app/chat/page.tsx` -- `'use client'`; reads collections/llm/embed from URL params; wires `ChatPanel`, `ChatInput`, `ChatSidebar`; calls `useStreamChat`; passes `isStreaming` to `ChatInput`; session ID persisted across turns

## Key Constraints

- **NDJSON streaming**: The `useStreamChat` hook (created by A1) calls `streamChat()` which parses NDJSON. This is NOT Server-Sent Events. You consume the hook -- you do not re-implement stream parsing.
- **isStreaming release**: `setIsStreaming(false)` must happen on `done`, `error`, AND `clarification`. The `clarification` event ends the stream without a `done` event following.
- **Confidence is INTEGER 0-100**: Tiers: >= 70 green, >= 40 yellow, < 40 red. Use `getConfidenceTier()` from `lib/types.ts`.
- **Citation fields**: `passage_id`, `document_id`, `document_name`, `start_offset`, `end_offset`, `text`, `relevance_score`, `source_removed`. Do NOT use `page`, `breadcrumb`, `index`, `chunkId`, or `source` -- they do not exist in the Citation schema.
- **source_removed**: When `citation.source_removed === true`, render a "source removed" badge instead of the source link. This is Constitution IV.
- **URL state**: Collections and models persist in URL query params (`useSearchParams` + `useRouter`). This enables bookmarking and sharing.
- **Functional setState**: Use `setMessages(prev => [...prev, ...])` to avoid stale closures during rapid chunk events.
- **Abort on unmount**: Store `AbortController` in a ref; call `controller.abort()` on component unmount to prevent memory leaks.

## Testing Protocol

- NEVER run tests inside Claude Code
- TypeScript compile: `cd frontend && npx tsc --noEmit`
- Visual verification: Chat page renders at `/chat`; streaming works; send button locks during stream

## Done Criteria

- `/chat` page renders without errors
- NDJSON streaming displays tokens word-by-word (via `useStreamChat`)
- Send button is disabled during streaming and when no collections are selected
- `CitationTooltip` shows passage text and document name; shows "source removed" badge when `source_removed === true`
- `ConfidenceIndicator` uses integer 0-100 with correct color tiers
- URL params persist selected collections and models across page refresh
- `npx tsc --noEmit` exits 0
