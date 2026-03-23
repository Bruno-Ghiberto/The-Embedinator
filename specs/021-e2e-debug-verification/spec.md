# Feature Specification: End-to-End Debug & Verification

**Feature Branch**: `021-e2e-debug-verification`
**Created**: 2026-03-20
**Status**: Draft
**Input**: User description: "Make The Embedinator actually work end-to-end for the first time. Debug startup failures, fix configuration issues, seed test data, verify every user flow, and establish a repeatable smoke test."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Application Starts Successfully (Priority: P1)

A developer clones the repository, runs the launcher script, and all four services (vector database, language model server, backend API, frontend UI) start and remain healthy. The developer sees a ready message with the application URL and can open it in a browser.

**Why this priority**: Nothing else works if the application cannot start. This is the absolute foundation — every other user story depends on all services being operational.

**Independent Test**: Can be fully tested by running the launcher script and verifying all four services report healthy status within the expected timeout window. Delivers value by proving the infrastructure layer is functional.

**Acceptance Scenarios**:

1. **Given** a fresh clone with no prior state, **When** the developer runs the launcher script, **Then** all four services start, pass their health checks, and the launcher reports success with the application URL.
2. **Given** the application was previously stopped, **When** the developer runs the launcher script again, **Then** all services resume within 60 seconds without rebuilding from scratch.
3. **Given** the application is running, **When** the developer navigates to the application URL in a browser, **Then** the frontend loads and displays the chat interface without errors.
4. **Given** the application is running, **When** the developer hits the backend health endpoint, **Then** the response indicates all subsystems (database, vector store, language model server) are reachable.

---

### User Story 2 - Create Collection and Ingest Document (Priority: P2)

A user opens the application, navigates to the collections page, creates a new collection, uploads a sample document (text or markdown), and sees the ingestion complete successfully with chunks indexed.

**Why this priority**: Without ingested data, the core RAG chat feature has nothing to search. This story seeds the knowledge base that makes the chat meaningful.

**Independent Test**: Can be tested by creating a collection, uploading a known document, and verifying the document status shows "complete" with a non-zero chunk count. Delivers value by proving the ingestion pipeline works from upload through chunking to vector indexing.

**Acceptance Scenarios**:

1. **Given** the application is running with no collections, **When** the user creates a collection named "Test Docs", **Then** the collection appears in the collections list and is queryable via the API.
2. **Given** a collection exists, **When** the user uploads a markdown file (at least 500 words), **Then** the ingestion job starts, progresses, and completes within 2 minutes.
3. **Given** an ingestion job has completed, **When** the user views the collection details, **Then** the document shows status "complete" and the chunk count is greater than zero.
4. **Given** a document was already ingested, **When** the user uploads the same file again, **Then** the system detects the duplicate and reports it without re-ingesting.

---

### User Story 3 - Chat with RAG and See Citations (Priority: P3)

A user opens the chat page, selects a collection with ingested documents, types a question related to the document content, and receives a streaming answer with relevant citations pointing back to the source document.

**Why this priority**: This is the core value proposition of the entire application — answering questions with grounded, cited responses from uploaded documents. It proves the 3-layer agent graph, retrieval pipeline, and streaming response all work together.

**Independent Test**: Can be tested by asking a factual question about a known ingested document and verifying the response includes relevant content and at least one citation. Delivers value by proving the complete RAG pipeline functions end-to-end.

**Acceptance Scenarios**:

1. **Given** a collection with an ingested document about a known topic, **When** the user asks a factual question about that topic, **Then** the response streams in progressively (not all at once) and contains relevant information from the document.
2. **Given** a streaming response is being received, **When** the response completes, **Then** at least one citation is displayed linking back to the source document.
3. **Given** a chat response has been received, **When** the user asks a follow-up question in the same session, **Then** the system maintains conversation context and provides a coherent continuation.
4. **Given** the user asks about a topic NOT covered by any ingested document, **When** the response is generated, **Then** the system indicates low confidence or states it cannot find relevant information, rather than hallucinating.

---

### User Story 4 - All Frontend Pages Render and Function (Priority: P4)

A user navigates through all five pages of the application (Chat, Collections, Settings, Observability, Documents) and each page loads correctly, displays relevant data, and interactive elements respond as expected.

**Why this priority**: Frontend functionality beyond the core chat/ingestion flow ensures the application feels complete and professional. Users need settings to configure providers, observability to understand system performance, and document management to maintain their knowledge base.

**Independent Test**: Can be tested by navigating to each page URL and verifying it renders without console errors and displays expected UI elements. Delivers value by proving the complete frontend is operational.

**Acceptance Scenarios**:

1. **Given** the application is running, **When** the user navigates to the chat page, **Then** the page renders with a message input, collection selector, and model selector.
2. **Given** the application is running, **When** the user navigates to the collections page, **Then** the page displays the list of collections with create and delete actions.
3. **Given** the application is running, **When** the user navigates to the settings page, **Then** the page shows provider configuration, model settings, and inference parameters.
4. **Given** the application is running and at least one query has been made, **When** the user navigates to the observability page, **Then** the health dashboard shows service statuses and the trace table displays query history.
5. **Given** the application is running, **When** the user navigates between all pages, **Then** no unhandled errors appear in the browser console and all navigation transitions complete within 2 seconds.

---

### User Story 5 - Repeatable Smoke Test Suite (Priority: P5)

A developer can run a single command that automatically verifies the application is working end-to-end: services healthy, API endpoints responding, a test document can be ingested, and a chat query returns a streaming response. This replaces manual verification with an automated check.

**Why this priority**: Without an automated verification mechanism, every future change risks silently breaking the application. A smoke test suite is the safety net that prevents regression to the "never worked" state.

**Independent Test**: Can be tested by running the smoke test command and verifying it exits with success (code 0) when the application is healthy, and fails (non-zero) when any service is down. Delivers value by providing confidence that the application works after any change.

**Acceptance Scenarios**:

1. **Given** all services are running and healthy, **When** the developer runs the smoke test command, **Then** all checks pass and the command exits with code 0.
2. **Given** the backend service is down, **When** the developer runs the smoke test command, **Then** the relevant check fails with a clear error message and the command exits with a non-zero code.
3. **Given** the smoke test has completed, **When** the developer examines the output, **Then** each check shows its name, pass/fail status, and elapsed time.

---

### User Story 6 - All Fixes Documented (Priority: P6)

Every bug found and fixed during the verification process is documented with the root cause, the fix applied, and the files changed. This creates a debugging knowledge base for future contributors and prevents the same issues from recurring.

**Why this priority**: Documentation is the final step that converts debugging effort into lasting value. Without it, the same issues will re-emerge in different guises.

**Independent Test**: Can be tested by reviewing the fixes log and verifying each entry has a root cause, fix description, and file list. Delivers value by providing a debugging reference for the project.

**Acceptance Scenarios**:

1. **Given** a bug was found and fixed during verification, **When** the fix is committed, **Then** the fixes log contains an entry with: symptom, root cause, fix applied, and files modified.
2. **Given** all verification is complete, **When** a reviewer reads the fixes log, **Then** they can understand every change without reading the code diff.

---

### Edge Cases

- What happens when the language model server has not finished downloading models and a chat request arrives?
- How does the system handle the backend starting before the vector database is fully ready?
- What happens when the frontend makes API calls and the backend returns 503 (service degraded)?
- How does the ingestion pipeline behave when the uploaded file is empty or contains only whitespace?
- What happens when the browser refreshes mid-stream during a chat response?
- How does the application behave when disk space is insufficient for model downloads?
- What happens when two concurrent ingestion jobs target the same collection?

## Requirements *(mandatory)*

### Functional Requirements

#### Service Startup & Health

- **FR-001**: System MUST start all four services (vector database, language model server, backend, frontend) via a single launcher command.
- **FR-002**: System MUST verify each service is healthy before declaring the application ready.
- **FR-003**: Backend health endpoint MUST probe all subsystems (database, vector store, language model server) and return aggregate status.
- **FR-004**: Frontend MUST be accessible at the configured URL once the application reports ready.
- **FR-005**: System MUST survive a stop-and-restart cycle without data loss or requiring full rebuild.

#### Configuration & Environment

- **FR-006**: System MUST generate all required secrets and configuration on first run without manual intervention.
- **FR-007**: System MUST use correct service addresses for inter-container communication (not localhost).
- **FR-008**: Frontend MUST route API calls to the backend correctly regardless of whether it runs inside or outside a container.

#### Data Ingestion

- **FR-009**: System MUST allow users to create named collections for organizing documents.
- **FR-010**: System MUST accept document uploads (at minimum: plain text and markdown) and process them into searchable chunks.
- **FR-011**: System MUST detect and reject duplicate document uploads within the same collection.
- **FR-012**: System MUST report ingestion progress and completion status to the user.

#### Chat & Retrieval

- **FR-013**: System MUST accept natural language questions and return streaming responses grounded in ingested documents.
- **FR-014**: System MUST include citations in responses that reference the source documents.
- **FR-015**: System MUST maintain conversation context within a session for follow-up questions.
- **FR-016**: System MUST indicate low confidence when no relevant documents are found, rather than fabricating answers.

#### Frontend Pages

- **FR-017**: Chat page MUST render a message input, collection selector, model selector, and streaming response display.
- **FR-018**: Collections page MUST display existing collections and support create/delete operations.
- **FR-019**: Settings page MUST allow configuration of provider keys, model selection, and inference parameters.
- **FR-020**: Observability page MUST display service health status and query trace history.
- **FR-021**: All pages MUST load without unhandled JavaScript errors in the browser console.

#### Smoke Test

- **FR-022**: System MUST provide a single command to run an automated smoke test covering service health, API responses, and basic workflows.
- **FR-023**: Smoke test MUST exit with code 0 on success and non-zero on any failure.
- **FR-024**: Smoke test MUST report individual check results with pass/fail status and timing.

#### Documentation

- **FR-025**: All bugs found and fixed MUST be documented with symptom, root cause, fix, and files changed.
- **FR-026**: Any remaining known issues MUST be documented with severity and workaround (if available).

#### Code Quality Verification (SonarQube)

- **FR-027**: The codebase MUST undergo a comprehensive static analysis using SonarQube Community Edition, executed via the SonarQube MCP server connected to a running SonarQube instance.
- **FR-028**: The analysis MUST cover four language targets: Python (backend), TypeScript (frontend), CSS including Tailwind directives (frontend styles), and Rust (ingestion worker) using the SonarQube instance's installed language plugins (community-rust plugin confirmed for Rust support).
- **FR-029**: The analysis MUST produce a quality report documenting per-language totals for: bugs, vulnerabilities, security hotspots, and code smells, with severity breakdown (BLOCKER, CRITICAL, MAJOR, MINOR, INFO).
- **FR-030**: All BLOCKER and CRITICAL severity issues identified MUST be triaged and documented in the known-issues log with a disposition: fix (in-scope per NFR-001), defer (out-of-scope), or false-positive.

### Non-Functional Requirements

- **NFR-001**: All fixes MUST be minimal and targeted — no refactoring, no feature additions beyond what is needed to make existing features work.
- **NFR-002**: The project Makefile MUST remain unchanged (preserved from prior specification).
- **NFR-003**: No regressions to existing passing tests — any test that passed before MUST still pass after.
- **NFR-004**: All changes MUST include clear rationale in commit messages or documentation.

### Key Entities

- **Service**: A containerized component of the application (vector database, language model server, backend API, frontend UI). Has a name, health status, port, and dependency list.
- **Collection**: A named group of documents that can be searched together. Has a name, description, and document count.
- **Document**: An uploaded file that has been processed into searchable chunks. Has a filename, status (pending/processing/complete/failed), and chunk count.
- **Smoke Check**: An individual verification step in the smoke test suite. Has a name, pass/fail result, and elapsed time.
- **Fix Entry**: A record of a bug found and resolved. Has a symptom description, root cause analysis, fix description, and list of modified files.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All four application services start and report healthy status within 5 minutes of running the launcher (excluding initial model downloads).
- **SC-002**: The application survives a stop-and-restart cycle, with all services returning to healthy state within 90 seconds.
- **SC-003**: A user can create a collection, upload a document, and see ingestion complete to "done" status with chunks indexed — all within 3 minutes of the application being ready.
- **SC-004**: A user can ask a question about an ingested document and receive a streaming response with at least one citation within 30 seconds.
- **SC-005**: All five frontend pages (chat, collections, settings, observability, documents) load and render without any unhandled browser console errors.
- **SC-006**: The automated smoke test suite passes with exit code 0 when all services are healthy.
- **SC-007**: Zero regressions — every test that passed before this spec MUST still pass after.
- **SC-008**: Every bug found and fixed is documented in the fixes log with root cause and resolution.
- **SC-009**: The application Makefile remains byte-for-byte identical to its state before this spec.
- **SC-010**: Frontend-to-backend API communication works correctly inside containers (no localhost fallback errors).
- **SC-011**: SonarQube analysis completes for all four language targets (Python, TypeScript, CSS/Tailwind, Rust) with results documented in the quality report, and all BLOCKER/CRITICAL issues triaged.

## Assumptions

- The host machine has Docker Desktop installed with at least 8GB RAM allocated and 15GB free disk space.
- An internet connection is available for initial model downloads (language model ~3.4GB, embedding model ~267MB).
- The host machine does not have conflicting services on ports 3000, 6333, 8000, or 11434.
- The existing codebase is architecturally sound — issues are configuration/integration bugs, not fundamental design flaws.
- The language model server may take 30+ minutes on first run to download models; this is expected behavior, not a bug.
- Pre-existing test failures (documented in prior specs) are not regressions and do not block this specification.

## Dependencies

- All prior specifications (001 through 020) have been implemented and their code is present on the current branch.
- Docker Desktop must be installed and running on the host machine.
- The launcher script exists and has execute permissions.
