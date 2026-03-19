# Feature Specification: Frontend Application

**Feature Branch**: `009-next-frontend`
**Created**: 2026-03-15
**Status**: Draft
**Input**: User description: "Next.js 16 frontend for The Embedinator RAG system with five pages: chat with NDJSON streaming, collections management, document upload, settings and provider hub, and observability dashboard"

## Clarifications

### Session 2026-03-16

- Q: Does the frontend require user authentication (login page, protected routes)? → A: No — all pages open, localhost/internal access assumed.
- Q: Does the chat page display a scrollable conversation history (multiple Q&A pairs), or only the most recent exchange? → A: Multi-turn thread — all messages scroll vertically, new Q&A appended at bottom.
- Q: While a response is streaming, can the user submit a follow-up question? → A: No — send button is disabled while streaming; re-enabled on `done` or `error` event.
- Q: What maximum file size should the frontend enforce client-side for document uploads? → A: 50 MB.
- Q: When saving agent behavior settings, should the UI use a toast notification after API response or optimistic UI with rollback? → A: Toast notification — show success/error banner after API response completes.
- Analysis (2026-03-16): FR-002 `page` and `breadcrumb` removed — backend `Citation` schema (schemas.py) lacks these fields; they exist in `RetrievedChunk` and Qdrant payload but are not forwarded. CitationTooltip renders `text` + `document_name` only. Extend Citation model in a future spec-08 follow-up.
- Analysis (2026-03-16): FR-013 clarified — document table shows `DocumentResponse.status` (5 values: pending/ingesting/completed/failed/duplicate); uploader polling shows `IngestionJobResponse.status` (7 values including started/streaming/embedding).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Conversational RAG Query (Priority: P1)

A researcher types a question, selects one or more document collections to search, chooses an LLM model, and submits the query. The response appears word by word as it is generated, with inline numbered citation markers referencing the source documents. After the response completes, a confidence indicator (green, yellow, or red) shows how well the retrieved material supported the answer. The researcher can hover over a citation marker to read the source text, file name, and page number.

**Why this priority**: Chat is the primary user-facing capability of the entire system. Without it, no other feature delivers value.

**Independent Test**: Open the application in a browser, select a collection from the sidebar, type a question, and verify that streamed text appears with citations and a confidence indicator — without implementing any other page.

**Acceptance Scenarios**:

1. **Given** the user has selected at least one collection, **When** they submit a question, **Then** words appear on screen incrementally and the response finishes within a reasonable time.
2. **Given** the response includes retrieved chunks, **When** streaming completes, **Then** inline citation markers like `[1]`, `[2]` appear and hovering over one reveals the chunk text and document name. If `source_removed` is true, a "source removed" badge appears instead of the source link.
3. **Given** the response finishes, **When** a confidence score is available, **Then** a green dot appears for high confidence (≥ 70), yellow for moderate (40–69), and red for low (< 40), with the numeric score visible on hover.
4. **Given** the backend returns a clarification question instead of an answer, **When** the stream ends, **Then** the clarification question is displayed to the user instead of a response.
5. **Given** the user selects collections and a model, **When** they copy the URL and open it in another tab, **Then** the same collections and model are pre-selected.

---

### User Story 2 — Collection Management (Priority: P2)

An administrator creates document collections to organize knowledge by topic or team. They give each collection a short machine-friendly name, an optional description, and choose an embedding model. They can view all collections on a card grid, see how many documents each holds, and delete collections they no longer need.

**Why this priority**: Collections are the fundamental organizational unit. Documents and chat both depend on at least one collection existing.

**Independent Test**: Navigate to the collections page, create a collection, verify it appears in the grid with the correct metadata, then delete it — without any document upload or chat functionality.

**Acceptance Scenarios**:

1. **Given** the user opens the collections page, **When** collections exist, **Then** each is shown as a card with name, description, document count, embedding model, and chunk profile.
2. **Given** the user clicks "Create Collection," **When** they enter a valid name matching `^[a-z0-9][a-z0-9_-]*$`, **Then** the new collection appears in the grid.
3. **Given** the user enters an invalid name (e.g., starting with a dash or containing spaces), **When** they attempt to submit, **Then** an inline validation error is shown and the form cannot be submitted.
4. **Given** an existing collection, **When** the user clicks delete, **Then** a confirmation dialog appears and, upon confirmation, the collection is removed from the grid.

---

### User Story 3 — Document Upload and Ingestion Tracking (Priority: P3)

A user navigates to a collection's document page, drags one or more files onto the upload zone, and watches a progress bar advance as the document is processed. Once ingestion finishes, the document appears in the table with a "completed" status badge. If ingestion fails, the badge shows "failed" with an indication of the problem.

**Why this priority**: Documents must exist before meaningful RAG queries can be answered; upload is the gateway to all knowledge content.

**Independent Test**: Open the documents page for a collection, drag a file onto the upload zone, and verify the status badge cycles through intermediate states and eventually reaches "completed" or "failed" — without any chat page interaction.

**Acceptance Scenarios**:

1. **Given** the user is on the documents page, **When** they drag a file onto the upload zone, **Then** an upload progress bar appears and job status is polled until a terminal state is reached.
2. **Given** ingestion completes successfully, **When** the status is polled, **Then** the document appears in the table with a "completed" badge.
3. **Given** ingestion fails, **When** the status is polled, **Then** the document row shows a "failed" badge.
4. **Given** an existing document, **When** the user clicks delete, **Then** the document is removed from the table.

---

### User Story 4 — Settings and Provider API Key Management (Priority: P4)

A system operator opens the settings page to adjust agent behavior (iteration limits, tool call caps), chunk sizing parameters, and the confidence display threshold. A provider hub section lists all supported AI providers, lets the operator enter or update API keys (which are masked on display), and shows a connection status indicator per provider.

**Why this priority**: Settings control quality and cost trade-offs; provider keys are required for cloud-based LLM and embedding models. Less critical than chat and collections because defaults allow the system to run.

**Independent Test**: Open the settings page, update the confidence threshold, save, and verify the value persists on refresh. Then enter an API key for one provider and verify the connection status indicator updates.

**Acceptance Scenarios**:

1. **Given** the settings page is open, **When** the user changes the confidence threshold and saves, **Then** the new value persists on page refresh.
2. **Given** a provider row is shown, **When** the user enters an API key and saves, **Then** the key field is masked and the connection status updates.
3. **Given** the user has not entered a key for a provider, **When** viewing the provider list, **Then** the provider shows as inactive with a "no key" indicator.

---

### User Story 5 — Observability and System Health (Priority: P5)

A DevOps engineer opens the observability page to check backend health, review latency trends, inspect confidence distribution, and browse individual query traces. They see status cards for each service (vector store, LLM runtime, database), a latency histogram for the past 24 hours, a confidence score distribution bar chart, and a paginated table of query traces they can expand for detail.

**Why this priority**: Operational visibility is important for production reliability but does not block end-user workflows.

**Independent Test**: Open the observability page and verify health cards appear with status and latency values, charts render data, and the trace table is paginated and expandable — without any other page being functional.

**Acceptance Scenarios**:

1. **Given** the observability page is open, **When** the page loads, **Then** service status cards for the vector store, LLM runtime, and database are displayed with their health status and response latency.
2. **Given** traces exist, **When** the page loads, **Then** a latency histogram for the past 24 hours and a confidence distribution bar chart are rendered.
3. **Given** multiple traces exist, **When** the user navigates trace pages, **Then** each page shows the correct subset of records and expanding a row reveals tool call detail.
4. **Given** per-collection statistics exist, **When** the observability page loads, **Then** document and chunk counts are displayed per collection.

---

### Edge Cases

- What happens when the backend is unreachable and a query is submitted? → An error message replaces the streaming response.
- What happens if the user submits a query with no collections selected? → The send button is disabled or an inline warning prevents submission.
- What happens if a document upload is attempted with a file type the server does not accept? → An error badge appears immediately without starting a background ingestion job.
- What happens if the user navigates away from the chat page while a response is streaming? → The stream is aborted cleanly and no memory leak occurs.
- What happens if a collection name already exists? → The creation dialog shows a conflict error from the backend without closing the dialog.
- What happens if the observability page loads while a backend service is slow to respond? → Charts and health cards show a loading state and render incrementally as data arrives.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST display a multi-turn chat interface where all previous messages in the session are visible in a scrollable thread; users can submit new queries and receive streamed, word-by-word responses appended at the bottom of the thread. The send button MUST be disabled while a response is streaming and re-enabled upon receiving a `done` or `error` event.
- **FR-002**: The system MUST render inline citation markers within assistant responses, each expandable to show the source chunk text and document name. When `source_removed` is true, a "source removed" indicator MUST replace the source link. *(Note: `page` and `breadcrumb` fields are available in the backend retrieval layer but not currently exposed in the Citation API schema; add them when the Citation model is extended.)*
- **FR-003**: The system MUST display a confidence indicator — color-coded green (≥ 70), yellow (40–69), or red (< 40) — with the numeric score visible on hover after each completed response.
- **FR-004**: The system MUST display a clarification question when the backend requests one, halting further response streaming accordingly.
- **FR-005**: Users MUST be able to select one or more collections and choose LLM and embedding models before submitting a query.
- **FR-006**: Selected collections and model choices MUST be encoded in the page URL so the state can be shared or bookmarked.
- **FR-007**: The system MUST present a collection grid showing each collection's name, description, document count, embedding model, and chunk profile.
- **FR-008**: Users MUST be able to create a collection by providing a name (validated against `^[a-z0-9][a-z0-9_-]*$`), an optional description, and an embedding model selection.
- **FR-009**: Users MUST be able to delete a collection after confirming a prompt; confirmation must be required before deletion executes.
- **FR-010**: Users MUST be able to navigate from a collection card to the collection's document management page.
- **FR-011**: Users MUST be able to upload documents to a collection via a drag-and-drop file zone. The frontend MUST enforce a 50 MB per-file size limit client-side, displaying an inline error for oversized files before any network request is made.
- **FR-012**: The system MUST display upload progress and poll ingestion job status until the job reaches a terminal state (completed or failed).
- **FR-013**: Documents MUST be listed in a table with status badges reflecting document-level states: pending, ingesting, completed, failed, and duplicate (`DocumentResponse.status`). During active upload, the uploader shows granular ingestion-job states: pending, started, streaming, embedding, completed, failed, paused (`IngestionJobResponse.status`).
- **FR-014**: Users MUST be able to delete a document from a collection.
- **FR-015**: Users MUST be able to save agent behavior settings: maximum iterations, maximum tool calls, parent chunk size, child chunk size, and confidence display threshold. A toast notification MUST confirm success or display an error message after the API response completes; no optimistic UI is used for settings saves.
- **FR-016**: The system MUST list all supported AI providers with their active status, API key presence, base URL, and available model count.
- **FR-017**: Users MUST be able to enter, update, or delete an API key for each provider; stored keys MUST be masked in the display.
- **FR-018**: The observability page MUST show health and latency status for each backend service.
- **FR-019**: The observability page MUST display a query latency histogram for the past 24 hours and a confidence score distribution bar chart.
- **FR-020**: The observability page MUST display a paginated table of query traces, each expandable to show per-node detail.
- **FR-021**: The observability page MUST display per-collection document and chunk counts.
- **FR-022**: The system MUST provide a top navigation bar enabling one-click navigation to all five pages.
- **FR-023**: The UI MUST be usable on desktop (1024 px+) and tablet (768 px+) viewport widths.

### Key Entities

- **Collection**: A named, machine-addressable group of documents sharing an embedding model and chunk profile. Attributes: name (validated slug), optional description, document count, creation timestamp.
- **Document**: A file ingested into a collection, tracked through a processing lifecycle. Belongs to exactly one collection. Attributes: file name, ingestion status, creation timestamp.
- **Ingestion Job**: A background processing record created when a document is uploaded. Polled until it reaches a terminal state.
- **Chat Session**: A conversation thread identified by a session ID, scoped to chosen collections and models. Session settings persist in the URL.
- **Chat Message**: A user or assistant turn within a session. Assistant messages carry optional citations, a confidence indicator, and groundedness data.
- **Citation**: A reference to a retrieved source chunk. Contains source file, page number, breadcrumb, and optional preview text.
- **Query Trace**: A persisted record of a completed RAG query. Attributes: session ID, query text, collections searched, latency, model used, confidence score.
- **Provider**: An external AI service. Attributes: name, active status, API key presence flag, base URL, model count.
- **Model**: An LLM or embedding model available from a provider. Attributes: model ID, provider name, type (llm or embed).

### Non-Functional Requirements

- **NFR-SEC-001**: The application requires no user authentication. All pages are publicly accessible, assuming a trusted localhost or internal network deployment. No login flow, session tokens, or protected route guards are required or to be implemented.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users see the first word of a streamed response within 500 milliseconds of submitting a query under normal backend load.
- **SC-002**: All five pages are reachable via the top navigation bar without a full browser reload.
- **SC-003**: A user can complete the end-to-end workflow — create a collection, upload a document, and submit a chat query — in a single browser session without any page errors.
- **SC-004**: The confidence indicator correctly reflects the backend score for every completed assistant message, with no misclassification between color tiers.
- **SC-005**: Selected collections and model choices survive a browser refresh, confirming URL-based state persistence.
- **SC-006**: The observability page renders health cards, latency and confidence charts, and the trace table without error when backend data is available.
- **SC-007**: Heavy UI components (charts, file-drop zone) load asynchronously and do not delay the initial render of the page shell.
- **SC-008**: Collection name validation provides inline feedback before form submission, preventing invalid names from reaching the backend.
