# Feature Specification: Chat & Agentic RAG Pipeline Fix

**Feature Branch**: `024-chat-fix`
**Created**: 2026-03-27
**Status**: Draft
**Input**: Bug-fix specification — resolve broken chat rendering, sidebar navigation, backend call limits, and duplicate citations

## Bug Registry

| ID       | Severity    | Layer    | Summary                                                                                    |
|----------|-------------|----------|--------------------------------------------------------------------------------------------|
| BUG-013  | P0-CRITICAL | Frontend | Chat response text never renders — skeleton bars shown indefinitely                        |
| BUG-014  | P1-HIGH     | Frontend | Sidebar "New Chat" button does not clear state — stale conversation persists               |
| BUG-015  | P1-HIGH     | Frontend | Conversation history entries show "New Chat 0" and may not load properly on click          |
| BUG-016  | P1-HIGH     | Backend  | Call limit callback instantiated with old limits (20/10) despite class defaults of (100/50) |
| BUG-017  | P2-MEDIUM   | Backend  | Citations duplicated 4x in response — no deduplication across fan-out sub-answers          |

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Chat Response Rendering (Priority: P1)

A user selects a document collection, types a question in the chat input, and sends it. The system processes the query through its retrieval-augmented generation pipeline. The user sees a streaming response appear in the chat panel as the answer is produced, followed by citation references, a confidence indicator, and groundedness data once the response completes.

**Why this priority**: This is the primary user-facing feature of the entire application. Without it, the product is non-functional. Every other user story depends on chat responses actually being visible.

**Independent Test**: Can be fully tested by sending a single chat message with a collection selected and observing that the assistant's answer text appears in the chat panel. Delivers the core value of the product — AI-powered answers grounded in user documents.

**Acceptance Scenarios**:

1. **Given** a user on the chat page with a collection selected, **When** they type a question and press Send, **Then** the assistant's response text appears in the chat panel as it streams from the backend.
2. **Given** the backend has started producing a response, **When** the first text chunk arrives at the frontend, **Then** the skeleton placeholder disappears and the response text becomes visible within 2 seconds.
3. **Given** a streaming response is in progress, **When** the user observes the chat panel, **Then** a blinking cursor indicates active streaming.
4. **Given** the backend has finished producing the response, **When** the done signal arrives, **Then** the streaming cursor disappears, the confidence meter appears, and citations become collapsible/expandable.
5. **Given** the backend returns an error during processing, **When** the error event arrives, **Then** the user sees an error message in the chat panel with a "Retry" button.

---

### User Story 2 — Start New Conversation (Priority: P2)

A user who has been chatting with the system wants to start a fresh conversation. They click the "New Chat" button in the sidebar. The current conversation is preserved in the conversation history, and the chat panel resets to its empty state so the user can begin a new topic.

**Why this priority**: Without the ability to start a new conversation, users are stuck in a single session indefinitely. This blocks multi-topic usage of the application.

**Independent Test**: Can be tested by having an active conversation, clicking "New Chat" in the sidebar, and verifying the chat panel clears to the empty state (collection selection or suggested prompts). The previous conversation should appear in the sidebar history.

**Acceptance Scenarios**:

1. **Given** a user on the chat page with an active conversation, **When** they click the sidebar "New Chat" button, **Then** the chat panel clears completely and shows the empty state.
2. **Given** a user already on the `/chat` path with messages visible, **When** they click the sidebar "New Chat" button, **Then** the same clearing behavior occurs (not ignored due to same-path navigation).
3. **Given** a user is viewing a loaded conversation via URL parameter, **When** they click the sidebar "New Chat" button, **Then** the URL parameter is removed and the chat panel resets.

---

### User Story 3 — Conversation History Navigation (Priority: P2)

A user has multiple past conversations in the sidebar. They click on a conversation entry to review it. The chat panel loads the messages from that conversation, the toolbar shows the collection and model that were used, and the conversation is highlighted as active in the sidebar.

**Why this priority**: Conversation history is the second most critical chat feature — it enables users to return to prior research and continue multi-turn conversations.

**Independent Test**: Can be tested by completing a chat conversation, clicking the sidebar entry, and verifying the messages load into the chat panel. The conversation title should reflect the first user message, and the message count badge should be accurate.

**Acceptance Scenarios**:

1. **Given** a user has completed a chat conversation, **When** they look at the sidebar, **Then** the conversation appears with the first user message as its title (not "New Chat") and the correct message count.
2. **Given** a user is on the chat page, **When** they click a conversation entry in the sidebar, **Then** the chat panel loads all messages from that conversation.
3. **Given** a conversation is loaded in the chat panel, **When** the user looks at the sidebar, **Then** the active conversation entry is visually highlighted.
4. **Given** a user is viewing a conversation, **When** they rename it via the dropdown menu, **Then** the new title appears in the sidebar immediately.
5. **Given** a user deletes a conversation via the dropdown menu, **When** the deletion completes, **Then** the conversation is removed from the sidebar and the chat panel resets.

---

### User Story 4 — Reliable Backend Processing for Complex Queries (Priority: P2)

A user asks a complex, multi-faceted question that requires the system to decompose it into sub-questions and research each one. The system completes the full research cycle without being prematurely cut off by internal processing limits. The final answer reflects the depth of research performed, and citations reference unique source passages without repetition.

**Why this priority**: Users asking complex questions are the power users of the system. Premature truncation of research produces incomplete or low-quality answers, undermining trust in the product.

**Independent Test**: Can be tested by sending a complex analytical question (e.g., "Explain the ARCA system architecture and how its components interact") and verifying the response completes without warnings in the backend logs about exceeded limits. Citations in the response should contain no duplicates.

**Acceptance Scenarios**:

1. **Given** a user sends a complex multi-part question, **When** the backend processes the query, **Then** the research pipeline runs to completion without being prematurely stopped by call limits.
2. **Given** the backend produces an answer with citations, **When** the citation data arrives at the frontend, **Then** each citation appears only once (no duplicates by source passage).
3. **Given** a complex query triggers multiple sub-question research loops, **When** processing completes, **Then** the backend logs show no "call limit exceeded" warnings.

---

### Edge Cases

- What happens when the user sends a second message while the first response is still streaming? The second message should be queued or the first stream should be aborted before starting the second.
- What happens when the user's browser has stale localStorage data from a previous version? The application should handle missing or malformed session data gracefully without crashing.
- What happens when the backend returns an empty `chunk` event (no text)? The frontend should not render an empty assistant bubble.
- What happens when the network connection drops mid-stream? The frontend should detect the disconnection and show an error state with a retry option.
- What happens when the user refreshes the page during an active streaming response? The streaming is lost, but the conversation history (if saved) should be recoverable from the sidebar.
- What happens when multiple browser tabs are open on the chat page? Session storage changes in one tab should not corrupt the state in another tab.

## Requirements *(mandatory)*

### Functional Requirements

**Chat Response Rendering (BUG-013)**

- **FR-001**: The system MUST display the assistant's response text in the chat panel as it arrives from the backend streaming endpoint.
- **FR-002**: The system MUST replace the skeleton placeholder with actual response text within 2 seconds of the first text chunk being received by the frontend.
- **FR-003**: The system MUST show a streaming indicator (blinking cursor) while the response is being produced.
- **FR-004**: The system MUST hide the streaming indicator and display the confidence meter when the response is complete.
- **FR-005**: The system MUST render error messages with a retry button when the backend reports an error during processing.

**Sidebar New Chat (BUG-014)**

- **FR-006**: The sidebar "New Chat" button MUST clear all messages from the chat panel and reset to the empty state.
- **FR-007**: The sidebar "New Chat" button MUST work when the user is already on the chat page (same-path navigation must not be ignored).
- **FR-008**: The sidebar "New Chat" button MUST clear URL session parameters, local storage for the current session, and all in-memory session references.

**Conversation History (BUG-015)**

- **FR-009**: The system MUST update the conversation title to the first user message text (truncated to 40 characters) after the first exchange completes.
- **FR-010**: The system MUST update the message count badge in the sidebar after each completed exchange.
- **FR-011**: Clicking a conversation entry in the sidebar MUST load all messages from that conversation into the chat panel.
- **FR-012**: The active conversation MUST be visually highlighted in the sidebar.
- **FR-013**: Conversation rename and delete actions from the dropdown menu MUST function correctly.

**Backend Call Limits (BUG-016)**

- **FR-014**: The backend call limit callback MUST use limits of at least 100 LLM calls and 50 tool calls per request.
- **FR-015**: The backend MUST NOT raise exceptions from call limit callbacks during parallel processing — warnings only.

**Citation Deduplication (BUG-017)**

- **FR-016**: The backend MUST deduplicate citations before emitting the citation event, using the citation source passage identifier as the unique key.
- **FR-017**: The citation count displayed in the frontend MUST match the number of unique source passages in the response.

### Key Entities

- **ChatMessage**: A single message in a conversation (user or assistant), with content text, optional citations, confidence score, groundedness data, streaming state, and error state.
- **ChatSession**: A conversation containing an ordered list of messages, associated collection and model configuration, a title derived from the first user message, and timestamps for creation and last update.
- **Citation**: A reference to a specific passage in a source document, identified by passage ID, with document name, text excerpt, and relevance score.
- **NDJSON Event**: A line in the streaming response from the backend. Event types: session, status, chunk, citation, confidence, groundedness, done, error, clarification.

## Scope

### In Scope

- Fix BUG-013 through BUG-017 (P0 through P2 severity)
- Verify fixes with manual browser testing and automated curl validation
- Ensure chat renders streamed responses in real-time
- Ensure sidebar "New Chat" properly resets all state
- Ensure conversation history loads correctly on click
- Deduplicate citations in backend NDJSON output
- Correct backend call limit callback instantiation

### Out of Scope

- New features, new UI components, or new API endpoints
- Performance optimization (latency tuning, caching)
- Mobile or responsive layout fixes
- P3 low-priority log noise (BUG-018 and BUG-019 — deferred)
- E2E test automation (Spec 023 scope — this spec fixes the app first)
- Observability, Settings, or Collections page bugs
- TUI installer testing
- Backend API contract changes (NDJSON event types and request/response schemas are correct)

### Assumptions

- The backend NDJSON streaming API produces correct output (verified via curl on 2026-03-27).
- The Next.js rewrite proxy correctly forwards streaming responses (verified via curl through port 3000).
- The bug is in the frontend rendering chain, not in the backend response production.
- Sidebar conversation history uses browser localStorage, which may contain stale or malformed data from previous application versions.
- The dual localStorage system (legacy single-session and multi-session history) may create conflicting state that should be resolved by consolidating on the multi-session system.

### Dependencies

- Existing backend chat API endpoint (`POST /api/chat`) must remain functional.
- Existing Qdrant vector database must contain at least one collection with ingested documents for testing.
- Docker Compose environment must be running (backend, frontend, qdrant, ollama) for manual verification.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can send a chat message and see the full response text rendered in the chat panel within 5 seconds of the backend completing response generation.
- **SC-002**: Clicking the sidebar "New Chat" button resets the chat panel to the empty state 100% of the time, regardless of current navigation state.
- **SC-003**: Completed conversations appear in the sidebar with an accurate title (first user message) and correct message count within 3 seconds of response completion.
- **SC-004**: Clicking a sidebar conversation entry loads all its messages into the chat panel 100% of the time.
- **SC-005**: Complex multi-part queries complete without premature research truncation — backend logs show zero "call limit exceeded" warnings for queries with fewer than 5 sub-questions.
- **SC-006**: Citation data in the response contains zero duplicate entries — each source passage appears exactly once.
- **SC-007**: All 5 bugs (BUG-013 through BUG-017) are resolved and verified through manual browser testing with a real backend and real data.
