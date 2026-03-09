# Feature Specification: Vision & System Architecture

**Feature Branch**: `001-vision-arch`
**Created**: 2026-03-04
**Status**: Draft
**Input**: User description: "The Embedinator — self-hosted agentic RAG system for private document intelligence with zero cloud dependencies, single-command launch, and a three-layer agent for multi-document querying."

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Private Document Q&A (Priority: P1)

A user has sensitive documents (PDFs, notes, reports) they want to query using AI but cannot send to the cloud. They install the system on their own computer, upload their documents, type a natural-language question, and receive an answer that cites the exact passages it drew from — all without any data leaving their machine.

**Why this priority**: This is the core value proposition of the system. Without local, private document querying, the product has no reason to exist. Every other story depends on this working first.

**Independent Test**: Can be fully tested by uploading a PDF, asking a factual question whose answer is in the PDF, and verifying the answer is correct and includes a citation to the source passage.

**Acceptance Scenarios**:

1. **Given** the system is running and a collection contains indexed documents, **When** the user asks a question in natural language, **Then** the system returns an answer that directly addresses the question and identifies the source documents and passages used.
2. **Given** a question whose answer spans multiple documents, **When** the user submits the question, **Then** the system synthesizes a coherent answer citing all relevant sources.
3. **Given** the user asks a question with no relevant content in any indexed document, **When** the system processes the query, **Then** it clearly indicates that no relevant information was found rather than fabricating an answer.

---

### User Story 2 — One-Command System Start (Priority: P2)

A non-technical user wants to start the entire system without reading a manual or configuring individual services. They run a single command and within a couple of minutes all components are online and accessible through a browser.

**Why this priority**: Ease of setup directly determines adoption. A complex multi-step installation will prevent most target users from ever experiencing the core value.

**Independent Test**: Can be fully tested by a fresh install on a compatible machine: running the single start command and verifying the web interface loads and accepts a test document upload.

**Acceptance Scenarios**:

1. **Given** the user has the system files and compatible hardware, **When** they run the single start command, **Then** all system components start automatically with no additional manual steps required.
2. **Given** all components are running, **When** the user opens a browser and navigates to the local address, **Then** the web interface loads and is ready to use.
3. **Given** the system is running for the first time with no prior configuration, **When** the user uploads a document and asks a question, **Then** the system responds using its built-in local AI with no API keys or external accounts required.

---

### User Story 3 — Streamed Real-Time Answers (Priority: P3)

A user submits a complex question and watches the answer appear word-by-word in the browser, giving immediate feedback that the system is working — similar to how they experience consumer AI chat tools.

**Why this priority**: Perceived responsiveness is critical to user trust. A long blank wait before a complete answer feels broken. Streaming makes the same underlying latency feel far more acceptable.

**Independent Test**: Can be fully tested by submitting a query and measuring time from submission to first visible text appearing in the response area.

**Acceptance Scenarios**:

1. **Given** the user submits a question, **When** the system begins generating an answer, **Then** the first words appear in the browser within one second of submission.
2. **Given** a streaming answer is in progress, **When** the user watches the response, **Then** text continues to appear progressively until the answer is complete.
3. **Given** a network interruption during streaming, **When** the connection drops, **Then** the system communicates the failure clearly rather than silently stopping.

---

### User Story 4 — Observability: Trace Every Answer (Priority: P4)

A user receives an answer and wants to understand exactly how the system reached it — which documents were searched, which passages were retrieved, what confidence the system had, and whether any fallback reasoning was triggered.

**Why this priority**: Trust in AI-generated answers requires transparency. Users need to verify answers are grounded in their actual documents, not hallucinated.

**Independent Test**: Can be fully tested by submitting a query, then navigating to the query trace view and confirming it shows the sources consulted, retrieval scores, and the reasoning path taken.

**Acceptance Scenarios**:

1. **Given** any completed query, **When** the user views the trace for that query, **Then** they can see which document collections were searched and which passages were retrieved.
2. **Given** a trace, **When** the user reviews it, **Then** each retrieved passage includes a relevance indicator and a direct link back to the source document.
3. **Given** a query where the system had to attempt additional reasoning strategies, **When** the user views the trace, **Then** those additional attempts are visible and explained.

---

### User Story 5 — Optional Cloud AI Provider (Priority: P5)

A power user wants to use a cloud-hosted AI model for higher-quality responses on certain queries. They enter their API credentials through the settings interface and switch the active provider without restarting the system.

**Why this priority**: While local-only is the default and primary use case, supporting cloud providers expands usefulness for users with access to cloud models without compromising the privacy-first default.

**Independent Test**: Can be fully tested by configuring a cloud provider API key through the UI, submitting a query, and confirming the response originates from the configured cloud provider.

**Acceptance Scenarios**:

1. **Given** the settings interface, **When** the user enters a cloud provider API key and saves, **Then** the key is stored securely and the provider becomes available for selection.
2. **Given** a configured cloud provider, **When** the user selects it and submits a question, **Then** the answer is generated using that provider.
3. **Given** a cloud provider is configured, **When** the user wishes to return to local inference, **Then** they can switch back without data loss or system restart.

---

### Edge Cases

- What happens when the user asks a question and the local AI is unavailable (e.g., not started, out of memory)?
- How does the system handle a document upload that fails mid-transfer or cannot be parsed?
- What happens when the user submits an extremely long question or document that exceeds processing capacity?
- How does the system behave when storage is full and a new document cannot be indexed?
- What happens when a question is ambiguous across multiple collections and the system is unsure which to prioritize?
- How does the system handle simultaneous queries from multiple browser tabs? Each tab maintains an independent query session; concurrent queries execute in parallel without sharing state or context.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST run entirely on user-owned hardware with no mandatory external network calls at runtime.
- **FR-002**: System MUST accept documents in PDF, Markdown, and plain text formats for indexing.
- **FR-002a**: Users MUST be able to delete a document from a collection; deletion removes the document from future retrieval. Existing traces that cited the deleted document MUST retain the passage text they captured at query time and display a "source removed" indicator in place of the source link.
- **FR-003**: Users MUST be able to type natural-language questions and receive answers grounded in their indexed documents.
- **FR-004**: Every answer MUST include citations identifying the source documents and passages used to generate it.
- **FR-005**: System MUST stream answer text to the browser progressively, with first visible content within one second of query submission.
- **FR-006**: System MUST decompose complex questions into sub-questions, retrieve evidence per sub-question, and synthesize a unified answer.
- **FR-007**: System MUST attempt alternative retrieval strategies when initial results fall below a confidence threshold, before responding to the user.
- **FR-008**: System MUST record a trace for every query capturing: documents searched, passages retrieved, confidence indicators, and any fallback reasoning steps.
- **FR-008a**: System MUST display a confidence indicator to the user alongside every answer in the main chat view, not only in the trace.
- **FR-009**: Users MUST be able to view query traces through the web interface.
- **FR-010**: System MUST organize documents into named collections that can be queried independently or in combination. A document MAY belong to multiple collections simultaneously; adding it to a second collection does not remove it from the first.
- **FR-011**: System MUST start all components with a single command requiring no manual per-service configuration.
- **FR-012**: System MUST provide a web interface accessible from any browser on the local network without installing client software or providing credentials.
- **FR-013**: Users MUST be able to configure optional cloud AI providers through the settings interface and switch between providers without restarting the system.
- **FR-014**: Cloud API credentials MUST be stored in encrypted form; the system MUST NOT transmit them to any unintended party.
- **FR-015**: System MUST clearly communicate when a question cannot be answered from the available documents rather than generating an unsupported answer.

### Key Entities

- **Document**: A file submitted by the user, associated with a collection, with indexable content and metadata (name, upload date, processing status). Documents may be deleted by the user; deletion removes the document from future retrieval but does not erase passage text already captured in existing traces.
- **Collection**: A named group of documents that can be queried as a unit or in combination with other collections. A document may belong to multiple collections simultaneously.
- **Query**: A natural-language question submitted by the user, associated with one or more target collections.
- **Answer**: A generated response to a query, including cited source passages and a confidence indicator displayed visibly to the user in the answer view.
- **Trace**: A record of the system's full reasoning path for a query: sources searched, passages retrieved with relevance scores, sub-questions explored, and fallback steps taken.
- **Provider**: A configured AI inference source (local or cloud) used for both answer generation and document indexing.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new user can upload a document and receive a correct, cited answer from it within 5 minutes of first starting the system.
- **SC-002**: The first words of an answer appear in the browser within 1 second of query submission under normal operating conditions.
- **SC-003**: No user document content or query text leaves the user's machine when the system is operating in its default local-only configuration.
- **SC-004**: The system starts successfully from a single command with no additional manual steps on hardware meeting the stated requirements.
- **SC-005**: Every statement in a generated answer can be traced back to a specific passage in a source document via the trace view.
- **SC-006**: When initial retrieval yields low-confidence results, the system automatically attempts at least one alternative strategy before responding.
- **SC-007**: Users can switch between the local AI provider and a configured cloud provider without restarting or reconfiguring the system.
- **SC-008**: The system correctly declines to answer (rather than fabricating a response) for at least 95% of queries on topics absent from the indexed documents.

## Assumptions

- The system targets a single power user or small team on a shared local network, not multi-tenant cloud deployment.
- "Compatible hardware" is defined elsewhere; this spec assumes sufficient compute for local AI inference exists.
- The default experience requires no paid accounts, no internet connectivity, and no pre-existing AI infrastructure.
- Document collections are user-managed (no automatic organization or tagging by the system).
- The web interface requires no authentication; any device on the local network can access it. Users are responsible for network-level access control (e.g., firewall rules, VPN).
- Multiple users can query the system concurrently; each browser tab or user gets an independent session with no shared conversational state.

## Clarifications

### Session 2026-03-04

- Q: Does the web interface require authentication (login)? → A: No — any device on the local network can open and use the interface without credentials.
- Q: How many users can simultaneously query the system? → A: Multiple concurrent sessions — each browser tab/user gets an independent query session with no shared state.
- Q: Can users delete documents after indexing, and what happens to existing traces? → A: Yes — documents are deletable; traces retain captured passage text but display a "source removed" indicator in place of the original source link.
- Q: Can a single document belong to more than one collection? → A: Yes — a document may be added to multiple collections simultaneously without duplication or reassignment.
- Q: Is the confidence indicator shown to users in the answer view, or used only internally? → A: Visible to users — a confidence indicator appears alongside every answer in the main chat UI.
