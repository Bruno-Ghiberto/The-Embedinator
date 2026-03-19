# Feature Specification: ConversationGraph — Agent Layer 1

**Feature Branch**: `002-conversation-graph`
**Created**: 2026-03-10
**Status**: Draft
**Input**: Context prompt from `Docs/PROMPTS/spec-02-conversation-graph/02-specify.md`

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Intelligent Query Routing (Priority: P1)

A user types a message in the chat interface. Before any document search happens, the system determines whether the message is a document question, a collection management command (e.g., "list my collections"), or something ambiguous that needs clarification. Based on this determination, the system routes the message to the appropriate handler automatically, eliminating user confusion about how to interact with the system.

**Why this priority**: Without intent classification and routing, every message is treated as a document search — even collection management requests. This is the ConversationGraph's most fundamental responsibility and the entry point for all other user stories in this spec.

**Independent Test**: Send three messages — a factual document question, a "list my collections" command, and a vague message like "help" — and verify each is routed to the correct handler (search, collection management, or clarification prompt).

**Acceptance Scenarios**:

1. **Given** the system is running and collections exist, **When** the user types a question like "What are the key security requirements?", **Then** the system identifies it as a document query and proceeds to search the selected collections.
2. **Given** the system is running, **When** the user types "list my collections", **Then** the system identifies it as a collection management command and routes to the appropriate handler without searching documents.
3. **Given** the system is running, **When** the user types an ambiguous message like "help me", **Then** the system asks the user a clarifying question before proceeding.
4. **Given** the intent classification fails for any reason, **When** the system handles the failure, **Then** it defaults to treating the message as a document query rather than returning an error.

---

### User Story 2 — Complex Query Decomposition (Priority: P2)

A user asks a complex question that spans multiple topics or requires synthesizing information from different documents (e.g., "Compare the security approaches in the API spec and the architecture document"). The system automatically breaks this into focused sub-questions, researches each one independently and in parallel, and synthesizes the results into a single coherent answer with citations from all relevant sources.

**Why this priority**: Simple single-document queries already work in the Phase 1 MVP. Decomposition unlocks the system's ability to handle analytical and comparative questions — the "agentic" part of agentic RAG — which is the key differentiator over basic retrieval.

**Independent Test**: Ask a comparative question across two collections, verify the answer addresses both comparison points, and confirm citations reference documents from both collections.

**Acceptance Scenarios**:

1. **Given** a complex question that spans multiple topics, **When** the system analyzes the query, **Then** it decomposes it into 1–5 focused sub-questions, each targeting a specific aspect.
2. **Given** decomposed sub-questions, **When** the system dispatches them for research, **Then** all sub-questions are researched concurrently (not sequentially).
3. **Given** research results from multiple sub-questions, **When** the system aggregates them, **Then** it produces a single coherent answer that synthesizes information from all sub-answers with deduplicated citations.
4. **Given** one sub-question's research fails, **When** the system aggregates results, **Then** it still returns an answer from the successful sub-questions and notes the gap.
5. **Given** a simple factual question, **When** the system analyzes it, **Then** it classifies it as a `factoid` or `lookup` tier and does not decompose it unnecessarily.

---

### User Story 3 — Conversation Continuity (Priority: P3)

A user asks a follow-up question that references a previous answer (e.g., "Tell me more about the second point" or "What about the security implications of that?"). The system understands the conversation context and resolves references correctly without the user needing to restate their full question.

**Why this priority**: Without session management and conversation history, every question is isolated. Follow-up questions are a natural interaction pattern that users expect from any chat interface. This story also covers history compression to prevent the conversation from breaking after many exchanges.

**Independent Test**: Ask an initial question, receive an answer, then ask a follow-up referencing the previous answer (e.g., "Explain point 2 in more detail"). Verify the follow-up answer is contextually relevant and references the correct content.

**Acceptance Scenarios**:

1. **Given** the user has an active chat session with prior messages, **When** they ask a follow-up question, **Then** the system uses conversation history to correctly interpret the new question in context.
2. **Given** a session is resumed after the user navigates away and returns, **When** the system loads the session, **Then** previous messages and context are restored from persistent storage.
3. **Given** persistent storage is temporarily unavailable when loading a session, **When** the system handles the failure, **Then** it creates a fresh session and logs a warning rather than crashing.
4. **Given** a conversation has accumulated many messages exceeding 75% of the configured model's context window, **When** the system detects the threshold, **Then** it compresses older conversation history to stay within budget while preserving key context.

---

### User Story 4 — Clarification When Needed (Priority: P4)

A user submits a question that is ambiguous or unclear — for example, "What about the data?" without specifying which data, which collection, or what aspect. Instead of guessing and returning a potentially irrelevant answer, the system pauses and asks focused clarification questions. The user answers, and the system resumes with the clarified intent.

**Why this priority**: Asking for clarification when uncertain produces higher-quality answers than guessing. This requires graph interrupt/resume capability, which is architecturally important but not needed for the core query flow.

**Independent Test**: Submit the ambiguous question "What about the data?" with no other context. Verify the system responds with a clarification prompt rather than a search result. Provide a clarifying answer and verify the system then produces a relevant response.

**Acceptance Scenarios**:

1. **Given** a user submits an ambiguous question, **When** the query analysis determines `is_clear = false`, **Then** the system responds with a specific clarification question rather than attempting to search.
2. **Given** the system has asked a clarification question, **When** the user responds with additional context, **Then** the system resumes processing with the clarified information.
3. **Given** the system's graph state is paused for clarification, **When** the user's clarification arrives, **Then** the system resumes from the saved checkpoint without restarting the entire query pipeline.
4. **Given** the user has already been asked for clarification twice and the response is still ambiguous, **When** the system evaluates the third message, **Then** it proceeds with best-effort interpretation (treating the query as a document search) rather than asking again.

---

### User Story 5 — Answer Verification and Trust Signals *(Phase 2)* (Priority: P5)

A user receives an answer and sees trust indicators alongside it: a confidence score (0–100%), inline citation markers ([1], [2]), and annotations flagging any claims the system could not verify against the source documents. If a claim is contradicted by the sources, it is removed from the answer entirely. The user can trust that every cited claim points to a real passage that actually supports it.

**Why this priority**: This is a Phase 2 enhancement. The core answer flow (US1–US4) must work first. Verification adds accuracy guarantees on top of a working system.

**Independent Test**: Submit a question, receive an answer with citations. Verify that each citation marker corresponds to a real source passage. If the system flags a claim as `[unverified]`, verify there is indeed no supporting passage in the retrieved context.

**Acceptance Scenarios**:

1. **Given** the system has generated a draft answer with citations, **When** groundedness verification runs, **Then** each claim in the answer is evaluated as SUPPORTED, UNSUPPORTED, or CONTRADICTED against the retrieved context.
2. **Given** a verification result where >50% of claims are unsupported, **When** the system formats the response, **Then** it flags the answer as low-confidence and annotates unsupported claims with `[unverified]`.
3. **Given** a citation that points to a passage that doesn't actually support the claim, **When** citation validation runs, **Then** the citation is either remapped to a better-matching passage or removed entirely.
4. **Given** a contradicted claim in the answer, **When** the system formats the response, **Then** it removes the contradicted claim and notes the contradiction.

---

### Edge Cases

- What happens when the user sends an empty message or only whitespace? The system MUST reject it with a clear error message.
- What happens when all selected collections are empty (no indexed documents)? The system MUST inform the user that no documents are available to search rather than returning an empty answer.
- What happens when query decomposition produces 0 sub-questions? The system MUST fall back to using the original query as a single sub-question.
- What happens when all parallel sub-question research instances fail? The system MUST return a clear error message rather than an empty answer.
- How does the system handle extremely long messages (>2000 characters)? Messages MUST be truncated or rejected per the existing input validation.
- What happens when the user switches collections mid-conversation? The system MUST use the newly selected collections for the current query without losing conversation history.
- What happens when no collections are selected? The system MUST prompt the user to select at least one collection before proceeding with a document query.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST classify each user message as one of three intents — document query, collection management, or ambiguous — before routing to a handler. The collection management handler itself is out of scope for this spec; ConversationGraph is responsible only for classification and routing.
- **FR-002**: System MUST default to treating a message as a document query if intent classification fails for any reason.
- **FR-003**: System MUST decompose complex questions into 1–5 focused sub-questions, each targeting a specific aspect of the original query.
- **FR-004**: System MUST classify each query's complexity tier (factoid, lookup, comparison, analytical, multi-hop) to optimize how deeply the system searches for answers.
- **FR-005**: System MUST dispatch sub-questions for research concurrently, not sequentially.
- **FR-006**: System MUST aggregate results from parallel research, merging answers into a single coherent response and deduplicating citations.
- **FR-007**: System MUST load conversation history from persistent storage on each chat request, restoring prior messages and session context.
- **FR-008**: System MUST recover gracefully if session history cannot be loaded — creating a fresh session and logging a warning rather than failing.
- **FR-009**: System MUST compress conversation history when it exceeds 75% of the configured model's context window, preserving key information while staying within the remaining budget for the current query and system prompts.
- **FR-010**: System MUST pause and ask clarification questions when a query is determined to be ambiguous, rather than guessing.
- **FR-011**: System MUST save the processing state when pausing for clarification and resume from the checkpoint when the user responds. Maximum 2 clarification rounds per query; after the second attempt, proceed with best-effort interpretation as a document query.
- **FR-012**: System MUST format responses with inline citation markers ([1], [2], etc.) that reference specific source passages.
- **FR-013**: System MUST include a confidence score (0–100 integer scale) alongside every answer in the streaming response.
- **FR-014**: System MUST stream responses progressively using the project's established streaming protocol, with the first content appearing within 1 second of query submission.
- **FR-015**: *(Phase 2)* System MUST verify each claim in a generated answer against the retrieved context, classifying claims as SUPPORTED, UNSUPPORTED, or CONTRADICTED.
- **FR-016**: *(Phase 2)* System MUST validate that each inline citation points to a passage that actually supports the associated claim, remapping or removing invalid citations.
- **FR-017**: *(Phase 2)* System MUST annotate unverified claims with a visible marker and remove contradicted claims from the final answer.

### Key Entities

- **Session**: A conversation context tied to a browser tab, containing message history, selected collections, and the active model configuration. Sessions persist across page reloads and have no maximum duration.
- **Intent**: The classification of a user message — document query, collection management, or ambiguous. Determined before routing.
- **Query Analysis**: A structured decomposition of the user's question into sub-questions, a complexity tier, collection hints, and a clarity flag indicating whether clarification is needed.
- **Sub-Answer**: The result of researching a single sub-question, containing the answer text, supporting citations, retrieved passages, and a per-sub-question confidence score.
- **Groundedness Result** *(Phase 2)*: A per-claim verification record indicating whether each statement in the answer is supported, unsupported, or contradicted by the retrieved evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user's message is correctly classified and routed (document query, collection command, or clarification) for at least 90% of typical inputs.
- **SC-002**: Complex queries spanning multiple topics produce answers that address all identified sub-topics, with citations from relevant sources for each.
- **SC-003**: Follow-up questions that reference previous answers are correctly interpreted (contextual reference resolution) without the user restating the full question.
- **SC-004**: The system's first response content appears within 1 second of the user submitting a query.
- **SC-005**: When the system cannot confidently interpret a question, it asks a clarification question rather than producing an irrelevant answer, and resumes correctly after receiving clarification.
- **SC-006**: Every statement in a generated answer can be traced back to a specific cited passage. No citation markers reference passages that do not exist.
- **SC-007**: *(Phase 2)* When groundedness verification is active, at least 95% of claims marked SUPPORTED have a corresponding passage that actually supports the claim (verified via manual review on a test set).
- **SC-008**: Conversations with 20+ exchanges do not degrade in quality or fail due to context limits.

## Assumptions

- The existing Phase 1 chat endpoint (`backend/api/chat.py`) will be refactored to invoke the ConversationGraph instead of the current direct retrieval + LLM pipeline.
- ResearchGraph (Spec 03) will be available as a subgraph that accepts a sub-question and returns a SubAnswer with citations and passages.
- The existing state schemas, Pydantic models, and prompt templates from Phase 1 will be extended rather than replaced.
- Session state persistence uses the existing SQLite database — no new storage system is required.
- The streaming protocol (NDJSON, `application/x-ndjson`) established in Phase 1 and codified in ADR-007 is unchanged.
- Confidence scores continue to use the existing evidence-based computation (weighted average of passage scores, 0–100 integer scale) rather than LLM self-assessment.
- Phase 2 features (GAV, citation validation) will be implemented as stub pass-through nodes initially, activated in a later spec.

## Clarifications

### Session 2026-03-10

- Q: Is the collection management handler in scope for this spec, or only the routing logic? → A: Out of scope — ConversationGraph classifies intent and routes; the handler exists separately or is a future concern.
- Q: What is the maximum number of clarification rounds before the system gives up and proceeds? → A: 2 rounds max — after two attempts, proceed with best-effort interpretation as a document query.
- Q: What threshold triggers history compression? → A: 75% of the configured model's context window.
- Q: What happens when no collections are selected at all? → A: Prompt user to select at least one collection before proceeding with a document query.
