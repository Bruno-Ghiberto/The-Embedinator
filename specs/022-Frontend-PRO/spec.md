# Feature Specification: Frontend PRO — Professional Agentic RAG Interface

**Feature ID**: 022-Frontend-PRO
**Branch**: `022-frontend-pro`
**Created**: 2026-03-21
**Status**: Draft

## Overview

Transform The Embedinator's frontend from an unstyled prototype into a professional-grade Agentic RAG chat interface. The backend API is complete and verified (22 bugs fixed in Spec 21). The frontend has correct component logic but fundamentally broken visual rendering — every component displays as unstyled HTML. This specification fixes the visual foundation, then adds the missing user experience layer that makes a RAG application feel like a serious product: rich text responses, interactive source citations, conversation history, real-time ingestion feedback, and a responsive mobile-friendly layout.

**Scope**: Frontend-only. Zero backend changes. All work consumes existing, verified API endpoints.

---

## Clarifications

### Session 2026-03-21

- Q: Should markdown rendering strip raw HTML for security (XSS prevention)? → A: Strip all raw HTML — only render safe markdown syntax (headings, code blocks, lists, links, tables, blockquotes). No raw HTML tags permitted in rendered output.

---

## User Scenarios & Testing

### US-1: First Impression — Styled Interface

**Persona**: New user visiting The Embedinator for the first time

**Scenario**: A user opens the application and sees a polished, professionally styled interface with a collapsible sidebar, themed navigation, inline command palette, and consistent visual design across all five pages. Every UI element (buttons, cards, badges, menus, breadcrumbs) renders with its intended design — no unstyled HTML fragments.

**Acceptance Tests**:
- Navigation sidebar renders with a themed background, proper width, and smooth collapse/expand animation
- Breadcrumbs render as styled inline text links (not as a numbered HTML `<ol>` list)
- Keyboard shortcut (`Cmd/Ctrl+K`) opens the command palette as a floating overlay dialog; the dialog is invisible when closed
- Switching between light and dark mode applies a consistent Obsidian Violet color scheme across all pages
- No JavaScript console errors on any of the five pages

### US-2: Chatting with Rich Responses

**Persona**: Knowledge worker querying their document collection

**Scenario**: A user selects a document collection, types a question, and receives a response that includes formatted headings, code blocks with syntax highlighting, bulleted lists, and inline citation badges. While the response streams in, the user sees dynamic progress labels ("Searching documents...", "Writing response...") and can stop generation mid-stream. After completion, a confidence indicator shows how well-grounded the answer is.

**Acceptance Tests**:
- Assistant messages containing markdown headings (`## Heading`) render as styled `<h2>` elements
- Code blocks with language identifiers render with syntax highlighting and a copy button
- Citation badges `[1]`, `[2]` appear inline within responses; hovering a badge shows a card with the source document name, excerpt, and relevance score
- Pipeline stage labels animate through stages ("Searching documents...", "Writing response...") during generation
- A stop button replaces the send button during streaming; clicking it halts generation immediately
- After completion, a confidence meter shows High/Medium/Low with a numeric score on hover
- Groundedness data (supported vs. unsupported claims) is displayed when available

### US-3: Browsing Conversation History

**Persona**: Returning user who wants to resume a past conversation

**Scenario**: A user returns to The Embedinator and sees their past chat sessions listed in the sidebar, grouped by date (Today, Yesterday, Previous 7 Days, Older). They click on a past conversation to reload it, pick up where they left off, or start a new chat. They can rename, delete, or search through sessions.

**Acceptance Tests**:
- Past chat sessions appear in the sidebar grouped by date
- Each session shows a title derived from the first user message, relative timestamp, and message count
- Clicking a session loads its messages into the chat view
- "New Chat" button clears the current conversation and starts fresh
- Sessions can be renamed, deleted (with confirmation), and searched
- Session data persists across browser refreshes via local storage

### US-4: Configuring Collections and Models

**Persona**: User who wants to search specific document collections with a particular model

**Scenario**: A user clicks a configuration icon in the chat toolbar to reveal a compact settings panel. They select which collections to search (multi-select with checkboxes) and which language model to use, then collapse the panel. The toolbar shows a one-line summary of the active configuration ("Searching: GraviTea Research | qwen2.5:7b") without consuming chat screen space.

**Acceptance Tests**:
- A slim toolbar above the chat area shows the active collection names as small badges and the model name as a pill
- Clicking the configuration icon expands a panel with collection checkboxes and model dropdowns
- The panel collapses smoothly when dismissed, restoring the full chat area
- Navigating to `/chat?collections=<id>` from a collection card pre-selects that collection

### US-5: Uploading Documents with Progress

**Persona**: User adding new documents to a collection

**Scenario**: A user drags files into the upload zone on the documents page. They see each file queued with an icon, name, and size. After upload starts, a progress bar updates every 2 seconds with real-time ingestion status (Pending, Processing, Embedding, Complete). On completion, the document list refreshes automatically. On failure, an error message and retry button appear.

**Acceptance Tests**:
- File type icons display based on extension (PDF, MD, TXT, RST)
- Multiple files can be uploaded with a visible queue and individual progress
- Progress bar updates every 2 seconds reflecting backend job status
- Status labels transition through: Pending, Processing, Embedding, Complete
- Successful ingestion auto-refreshes the document list and shows a success notification
- Failed ingestion shows an inline error with a retry button

### US-6: Onboarding and Empty States

**Persona**: Brand-new user with no collections or documents

**Scenario**: A first-time user sees a welcoming empty state that guides them through getting started: creating a collection, uploading documents, and asking their first question. The chat page shows different empty states depending on context — no collections, collections but none selected, or collection selected but no messages yet (with suggested prompts).

**Acceptance Tests**:
- Collections page empty state shows a welcoming message with a "Create your first collection" button
- Chat page with no collections shows an onboarding flow directing users to create a collection (chat input is hidden)
- Chat page with collections but none selected shows available collections as clickable cards
- Chat page with a selected collection shows 3-4 suggested prompts that can be clicked to send

### US-7: Mobile Experience

**Persona**: User accessing The Embedinator on a phone or tablet

**Scenario**: A user opens the app on a mobile device. The sidebar collapses to an off-canvas drawer accessible via a menu button. The chat configuration panel takes full width. Message bubbles use the full available width. The chat input sticks to the bottom of the viewport. Citation hover cards convert to tap-to-expand interactions. All interactive elements meet minimum touch target sizes.

**Acceptance Tests**:
- Sidebar collapses to off-canvas drawer on small screens
- Chat configuration panel takes full width on mobile
- Chat input remains fixed at the bottom of the viewport
- All interactive elements have a minimum touch target size of 44x44 pixels
- Citation information is accessible via tap instead of hover

---

## Functional Requirements

### Phase 1: Visual Foundation (Critical)

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-001 | All UI components render with their intended visual design across all five pages | Every styled component (sidebar, breadcrumbs, command palette, cards, buttons, badges, dialogs) displays with correct colors, spacing, borders, and animations. No unstyled HTML fragments visible. |
| FR-002 | A single consistent design token system governs the visual styling of the entire application | All component styles reference the same token vocabulary. No conflicting or redundant token definitions. Custom tokens limited to application-specific values (warning, success) that have no standard equivalent. |
| FR-003 | The chat interface fills the viewport correctly: scrollable message area, fixed input at bottom | Messages scroll without overflowing below the viewport. Input remains pinned at the bottom. Layout handles dynamic content (long messages, many messages) without breaking. Header, toolbar, and input bar all remain visible. |
| FR-004 | Breadcrumbs on all pages render as styled inline text links with proper hierarchy | Breadcrumb trail shows page hierarchy as styled, clickable text — not as an HTML numbered list. |

### Phase 2: Chat Experience

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-005 | Assistant messages display rich text formatting: headings, code blocks, lists, tables, links, blockquotes | Markdown content renders as proper HTML elements with appropriate styling. All raw HTML tags are stripped — only safe markdown syntax is rendered (XSS prevention). Code blocks include syntax highlighting and a copy-to-clipboard button. Incomplete markdown during streaming (e.g., unclosed code fences) displays gracefully as a placeholder until complete. |
| FR-006 | Collection and model selection uses a compact, collapsible configuration panel rather than a persistent sidebar | A slim toolbar above the chat area shows the active configuration. Clicking an icon reveals the settings panel. The panel collapses smoothly, returning full width to the chat area. |
| FR-007 | Inline citation badges appear within assistant responses, with hover previews showing source details | Numbered badges (`[1]`, `[2]`) appear next to cited claims. Hovering shows a card with: document name, collection name, passage excerpt (2-3 lines), and relevance score as a colored indicator. Clicking navigates to the source document. Below each response, a collapsible "N sources" section lists all citations. |
| FR-008 | During response generation, dynamic stage labels show the current pipeline stage | Progress labels transition through stages (understanding question, searching documents, writing response, verifying accuracy, etc.) with smooth animations. A spinner accompanies the current stage label. |
| FR-009 | Streaming UX: stop button replaces send during generation; auto-scroll with override; auto-resizing input | The send button becomes a stop button during streaming. Auto-scroll keeps latest content visible but pauses if the user scrolls up, with a "Scroll to bottom" floating button. The text input grows from 1 to 5 rows based on content and resets after sending. |
| FR-010 | After each completed response, a visual confidence indicator shows answer quality | A colored gauge shows High (green, >=70), Medium (yellow, 40-69), or Low (red, <40) confidence. Numeric score shows on hover. Groundedness data (supported/unsupported claims) displays when available. |

### Phase 3: Navigation & History

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-011 | Past chat sessions are listed in the sidebar, grouped by date, with search and management actions | Sessions grouped by: Today, Yesterday, Previous 7 Days, Older. Each entry shows: title (from first user message, truncated to ~40 chars), relative timestamp, message count. Actions: rename, delete (with confirmation), search. Active session is highlighted. Maximum 50 stored sessions. |
| FR-012 | Collection cards include a "Chat" action that navigates to the chat page with the collection pre-selected | A "Chat" button/action on each collection card navigates to `/chat?collections=<id>`. The documents page header also includes a "Chat with this collection" button. The chat page reads the URL parameter and pre-selects the collection. |
| FR-013 | The documents page shows the collection name as its title (not the UUID) and includes breadcrumb navigation | Page title displays the human-readable collection name. Breadcrumb shows: Collections > Collection Name > Documents. |

### Phase 4: Ingestion & Upload

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-014 | After file upload, a progress bar polls the backend every 2 seconds and displays real-time ingestion status | Progress bar updates with: status label (Pending, Processing, Embedding, Complete/Failed), chunk progress when available. On completion: document list auto-refreshes, success notification shown. On failure: error message with retry button. |
| FR-015 | File upload shows file details and supports queued multi-file uploads | Each file in the queue shows: file type icon (by extension), file name, file size. Multiple files can be queued and uploaded with individual progress tracking. |

### Phase 5: Empty States & Onboarding

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-016 | Chat page shows context-aware empty states depending on collection and message state | Three states: (1) No collections — onboarding flow with link to create collection, chat input hidden. (2) Collections exist but none selected — available collections as clickable cards. (3) Collection selected, no messages — 3-4 suggested prompts that send on click. |
| FR-017 | Collections page shows an inviting empty state when no collections exist | Centered display with icon, "No collections yet" heading, description text, and a button to create the first collection. |

### Phase 6: Polish & Quality

| ID | Requirement | Acceptance Criteria |
|----|-------------|-------------------|
| FR-018 | Keyboard shortcuts for common actions with discoverable hints | Shortcuts: `Cmd/Ctrl+K` (command palette), `Cmd/Ctrl+B` (toggle sidebar), `Enter` (send), `Shift+Enter` (newline), `Escape` (close dialog / stop streaming). "New Chat" is accessible via the button in the sidebar; a `Cmd/Ctrl+N` shortcut is intentionally omitted — it conflicts with the browser's native "Open New Window" action and cannot be reliably intercepted. Shortcuts shown in tooltips and command palette. |
| FR-019 | Errors display as inline system messages with retry capabilities | Network and generation errors appear as system message bubbles (not modal dialogs or page-level banners). Failed messages show a "Retry" button. User input is preserved on error. Backend status banner is dismissible once the backend comes online. |
| FR-020 | All data-fetching states show skeleton loading placeholders | Pages and components display skeleton placeholders while data loads. Chat streaming shows a shimmer/pulse animation on the assistant message placeholder. Route-level loading states cover page transitions. |
| FR-021 | The application is usable on mobile devices with appropriate responsive behavior | Sidebar collapses to off-canvas drawer on small screens. Configuration panel takes full width on mobile. Message bubbles use full available width. Chat input sticks to viewport bottom. Citation cards use tap-to-expand (not hover). All interactive elements have minimum 44x44px touch targets. |

---

## Success Criteria

| ID | Criterion | Verification |
|----|-----------|-------------|
| SC-001 | Navigation sidebar renders with styled background, themed width, smooth collapse/expand animation, and icon-only mode | Visual inspection in both light and dark themes |
| SC-002 | Chat page fills viewport correctly — input pinned at bottom, messages scrollable, no overflow below viewport | Test with 50+ messages, verify scroll behavior and input position |
| SC-003 | Breadcrumbs render as styled inline text links (not numbered HTML list) | Visual inspection on all five pages |
| SC-004 | `Cmd/Ctrl+K` opens command palette as a floating dialog; invisible when closed | Keyboard test; verify no layout shift |
| SC-005 | Assistant message containing markdown headings and code blocks renders as styled `<h2>` and syntax-highlighted code | Send a test message, inspect rendered HTML |
| SC-006 | Citation badges `[1]` `[2]` appear in responses; hovering shows source document name, excerpt, and relevance score | Test with a document-backed query |
| SC-007 | Pipeline stage indicator shows human-readable labels ("Searching documents...", "Writing response...") during streaming | Observe during a live chat query |
| SC-008 | After file upload, progress bar updates every 2 seconds until terminal status (Completed or Failed) | Upload a test document, observe progress |
| SC-009 | Sidebar shows past chat sessions grouped by date; clicking loads the conversation messages | Create multiple sessions, verify grouping and loading |
| SC-010 | Collection cards have a "Chat" action that navigates to `/chat?collections=:id` with the collection pre-selected | Click "Chat" on a collection card, verify navigation and selection |
| SC-011 | Documents page header shows collection name (not UUID), with breadcrumb navigation (Collections > Name > Documents) | Navigate to documents page, verify title and breadcrumb |
| SC-012 | All five pages load without JavaScript console errors | Open DevTools console, visit each page |
| SC-013 | All existing frontend tests still pass (baseline: 53 tests) | Run the frontend test suite |
| SC-014 | No conflicting or redundant custom CSS tokens remain — only the standard token system plus warning/success custom tokens | Grep the codebase for deprecated token patterns |
| SC-015 | Mobile: sidebar collapses to off-canvas drawer, chat input sticks to viewport bottom, all touch targets >= 44px | Test at 375px viewport width |

---

## Non-Functional Requirements

| ID | Requirement |
|----|------------|
| NFR-001 | First Contentful Paint under 1.5 seconds on desktop (measured by Lighthouse audit) |
| NFR-002 | Chat message rendering maintains 60fps during streaming — no visible jank or frame drops |
| NFR-003 | No individual new dependency exceeds 50KB gzipped in the client bundle |
| NFR-004 | WCAG 2.1 AA compliance: all interactive elements have accessible names, visible focus indicators, and color contrast ratio >= 4.5:1 |
| NFR-005 | Local storage schema is versioned to support forward-compatible data migration |

---

## Key Entities

### ChatSession
A conversation between the user and the system. Contains an ordered list of messages, a title derived from the first user message, timestamps, and the active configuration (selected collections and model).

### ChatMessage
A single message in a conversation. Has a role (user or assistant), content (plain text or markdown), optional citations, optional confidence score, optional groundedness data, and a timestamp.

### Citation
A reference to a source document chunk used in an assistant response. Contains the document name, collection name, passage excerpt, relevance score, and a link to the source.

### IngestionJob
A background process for ingesting an uploaded document. Has a status (pending, processing, embedding, completed, failed), progress metrics (chunks processed / total), and error information on failure.

---

## Dependencies

- **Backend API**: All endpoints verified working in Spec 21 (chat, collections, documents, ingestion, models, providers, settings, traces, health)
- **NDJSON Streaming**: Chat response stream with typed events (session, status, chunk, citation, confidence, groundedness, done, error)
- **Existing Frontend Hooks**: `useStreamChat`, `useCollections`, `useModels`, `useTraces`, `useMetrics`, `useChatStorage` — all functional
- **Existing API Client**: `lib/api.ts` with 18 API functions including streaming support

---

## Assumptions

- The Obsidian Violet color palette (purple accent, dark/light themes) is the permanent brand identity and will not change
- Local storage is an acceptable persistence layer for chat history (no server-side session storage needed)
- 50 stored chat sessions is a reasonable limit for local storage
- The existing 5-page structure (Chat, Collections, Documents, Settings, Observability) is final — no new pages will be added
- Suggested prompts in the empty state can be static/generic rather than dynamically generated
- Citation hover cards can use the existing `Citation` type data without additional backend fields
- File uploads will continue to be individual files (no folder/zip upload needed)

---

## Constraints

- **Zero backend changes** — all work is frontend-only, consuming existing API endpoints
- **Makefile SACRED** — the project Makefile must not be modified
- **Existing test baseline preserved** — all 53 frontend tests must continue to pass
- **No new pages** — enhance existing five pages, do not add new routes
- **Only three new dependencies** — `react-markdown`, `remark-gfm`, `rehype-highlight`

---

## Out of Scope

- Server-side chat session persistence (using local storage only)
- User authentication or multi-user support
- File preview or in-app document viewer
- Real-time collaborative editing
- Custom theme editor or user-configurable color schemes
- Backend API changes or new endpoints
- Internationalization / localization
- Automated end-to-end testing (manual verification per success criteria)
