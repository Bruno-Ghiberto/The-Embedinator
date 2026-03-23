# Feature Specification: Provider Architecture

**Feature Branch**: `010-provider-architecture`
**Created**: 2026-03-16
**Status**: Draft
**Input**: User description: "Read Docs/PROMPTS/spec-10-providers/10-specify.md"

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Switch Active LLM Provider (Priority: P1)

As an operator, I want to switch the system from local Ollama to a cloud LLM provider (OpenRouter, OpenAI, or Anthropic) so that I can use more capable models without redeploying the application.

**Why this priority**: This is the core value of the feature. Key storage, health checks, and model listing all exist to enable this. Without provider switching the system is hard-wired to Ollama.

**Independent Test**: Can be fully tested by setting a cloud provider as active and confirming that subsequent chat requests are handled by that provider. Delivers immediate value by enabling cloud-model use.

**Acceptance Scenarios**:

1. **Given** Ollama is the current active provider, **When** an operator selects OpenRouter and saves a valid API key, **Then** subsequent chat requests are routed to OpenRouter and responses stream back correctly.
2. **Given** a cloud provider is active and its service is temporarily down, **When** a chat request is made, **Then** the system falls back to Ollama and continues serving requests without crashing.
3. **Given** an unknown provider name is stored as active, **When** the registry resolves the active provider, **Then** the system silently falls back to Ollama.

---

### User Story 2 — Store Cloud Provider API Keys Securely (Priority: P2)

As an operator, I want to enter API keys for cloud providers through the Settings UI and have them stored securely, so that credentials are never exposed in logs, API responses, or application code.

**Why this priority**: Cloud providers require API keys. Without secure key storage, provider switching (P1) cannot be offered safely.

**Independent Test**: Can be tested by submitting a key via the Provider Hub, then confirming the stored value is encrypted and the plaintext never appears in API responses, logs, or error messages.

**Acceptance Scenarios**:

1. **Given** no API key is stored for OpenAI, **When** an operator submits a valid key, **Then** the key is accepted, stored in encrypted form, and `has_key: true` is returned in the provider list.
2. **Given** an encrypted API key is stored, **When** the provider list is fetched, **Then** the response contains `has_key: true` but never the plaintext key value.
3. **Given** a stored encrypted key, **When** the operator deletes it, **Then** `has_key: false` is returned and the provider reverts to inactive.
4. **Given** the encryption configuration is absent from the environment, **When** a key-save request is made, **Then** the system returns a clear error and refuses to store the key.

---

### User Story 3 — Inspect Provider Health (Priority: P3)

As an operator, I want to see which LLM and embedding providers are reachable from the Observability dashboard, so that I can diagnose connectivity issues without examining server logs.

**Why this priority**: Once multiple providers are configured, health visibility is essential for operations. Undetected outages silently degrade system quality.

**Independent Test**: Can be tested by querying the health endpoint and confirming it returns reachability status for each configured provider within 5 seconds.

**Acceptance Scenarios**:

1. **Given** Ollama is running locally, **When** the health endpoint is queried, **Then** the response marks Ollama as reachable.
2. **Given** a cloud provider has an invalid or missing API key, **When** a health check is performed, **Then** the provider is marked unreachable without crashing the application.
3. **Given** a provider health check takes more than 5 seconds, **When** the check runs, **Then** the system times out and marks the provider as unreachable.

---

### User Story 4 — Browse Available Models (Priority: P4)

As an operator or end user, I want the model selector dropdowns in the Chat UI to reflect all models available from the currently configured providers, so that I can choose the right model for my task.

**Why this priority**: Model listing makes provider switching useful in practice. Without it, users cannot discover which models a newly configured provider offers.

**Independent Test**: Can be tested by querying the LLM and embedding model listing endpoints and confirming they return correctly labelled, non-overlapping lists.

**Acceptance Scenarios**:

1. **Given** Ollama has several models pulled locally, **When** the LLM model list is requested, **Then** all local Ollama models are returned with correct metadata.
2. **Given** no cloud providers are configured, **When** the embedding model list is requested, **Then** only Ollama embedding models are returned.
3. **Given** LLM and embedding lists are requested, **When** responses arrive, **Then** each list contains only models of the correct type with no cross-contamination.

---

### User Story 5 — Use Local Embeddings Without Configuration (Priority: P5)

As a developer setting up The Embedinator for the first time, I want embeddings to work out of the box using local Ollama, so that I can ingest and search documents immediately without any API key configuration.

**Why this priority**: Embedding is required for ingestion and search. Zero-configuration for the local case ensures the system is usable as a default deployment.

**Independent Test**: Can be tested by starting the application with no cloud credentials set and confirming that document ingestion and vector search succeed using the local embedding provider.

**Acceptance Scenarios**:

1. **Given** no provider API keys are configured, **When** a document is ingested, **Then** embeddings are generated using the local Ollama embedding model.
2. **Given** the local Ollama instance is unreachable, **When** embedding is attempted, **Then** the system returns a clear error rather than silently producing empty vectors.

---

### Edge Cases

- What happens when the active cloud provider is reachable but returns an authentication error mid-request?
- How does the system behave when both the active cloud provider and the Ollama fallback are unreachable simultaneously?
- What if a stored encrypted key cannot be decrypted (encryption secret was rotated or corrupted)?
- What happens when Ollama is running but has no models pulled (empty model list)?
- What if two concurrent requests arrive while the active provider is being switched?
- What if a provider health check takes exactly 5 seconds — does it pass or time out?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a single active LLM provider at any time, stored persistently so it survives application restarts.
- **FR-002**: The system MUST start with Ollama as the default active LLM provider requiring zero configuration.
- **FR-003**: The system MUST support four LLM provider types: local Ollama, OpenRouter (cloud, 200+ models with one API key), OpenAI (direct), and Anthropic (direct).
- **FR-004**: The system MUST provide a default embedding provider (Ollama) that requires no configuration.
- **FR-005**: The system MUST expose a uniform LLM provider interface: generate a complete response, stream response tokens, perform a reachability check, and report the active model name.
- **FR-006**: The system MUST expose a uniform embedding provider interface: generate embeddings for a batch of texts (with a caller-supplied model name), generate an embedding for a single text (with a caller-supplied model name), report the default model name, and report the vector dimension for a given model. A single provider instance handles all models — no per-model instantiation required.
- **FR-007**: The system MUST encrypt all cloud provider API keys before writing them to persistent storage, using symmetric encryption with a secret loaded from the environment.
- **FR-008**: The system MUST never return a plaintext API key in any API response, log entry, or error message.
- **FR-009**: The system MUST refuse key-save operations when the encryption secret is absent from the environment.
- **FR-010**: The system MUST decrypt stored API keys in memory only at the moment of provider instantiation, and discard the plaintext immediately after use.
- **FR-011**: The system MUST allow operators to delete a stored API key for any provider via an API call.
- **FR-012**: The system MUST return a list of configured providers with each provider's active/inactive status and a boolean indicating whether an API key is stored, without revealing the key itself.
- **FR-013**: The system MUST expose separate endpoints for listing available LLM models and available embedding models.
- **FR-014**: Provider health checks MUST complete or time out within 5 seconds.
- **FR-015**: The system MUST fall back to Ollama when the active cloud provider is unreachable or returns an authentication failure, without crashing or producing an unhandled exception.
- **FR-017**: On transient cloud provider errors (5xx responses, connection timeouts), the system MUST retry the request exactly once before falling back to Ollama.
- **FR-018**: On rate-limit errors (HTTP 429) from a cloud provider, the system MUST surface the error directly to the user without falling back to Ollama, so operators are aware the limit has been reached.
- **FR-016**: The system MUST validate that a stored token is a well-formed ciphertext before attempting decryption.
- **FR-019**: The system MUST record the active provider name in each query trace entry alongside the existing LLM model field, enabling per-provider cost tracking and failure diagnosis.

### Key Entities

- **Provider**: Represents a configured LLM or embedding source. Key attributes: unique name, active status, key-presence indicator (boolean, not the key itself), optional base URL for cloud providers, configuration parameters stored securely.
- **QueryTrace** *(extended)*: Each recorded query trace MUST include the provider name that handled the request alongside the existing LLM model field. This supports per-provider cost attribution and fallback diagnosis.
- **ModelInfo**: Represents a single model available from a provider. Attributes: model name, provider name, optional size (e.g., "7B"), optional quantization label, optional context window length, optional embedding dimension (embedding models only).
- **KeyManager**: Responsible for encrypting plaintext credentials before storage and decrypting them in-memory at call time. Plaintext never persisted to disk.

> **Note**: The embedding provider is model-agnostic — `embed()` and `embed_single()` accept the target model name as a parameter. A single provider instance serves all collections regardless of their configured embedding model.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Switching from local to a cloud LLM provider requires at most one operator action (entering an API key) with no application restart.
- **SC-002**: All provider health checks complete or time out within 5 seconds, measured end-to-end.
- **SC-003**: API key encryption and decryption each add less than 1 millisecond of latency to the request handling path.
- **SC-004**: A plaintext API key never appears in any system log, API response body, or error message — verifiable by full-text search of all output produced during a key-save and key-use cycle.
- **SC-005**: The application starts and serves all ingestion and search requests successfully with zero cloud provider credentials configured.
- **SC-006**: Provider failures (unreachable service, authentication error, timeout) are caught and surfaced as clear error messages without causing application crashes.
- **SC-009**: Every query trace record contains the provider name that handled the request — verifiable by querying the traces endpoint after a chat request with each provider type active.
- **SC-007**: LLM model list and embedding model list are returned as separate, correctly typed collections — no LLM models appear in the embedding list and vice versa.
- **SC-008**: All four provider types (Ollama, OpenRouter, OpenAI, Anthropic) complete a round-trip test: instantiate, send a minimal request, receive a valid response.

## Clarifications

### Session 2026-03-16

- Q: When a cloud provider returns a rate-limit (429) or transient server error (5xx/timeout), what should happen? → A: Retry once on transient errors (5xx/timeout), fall back to Ollama on persistent failure; surface rate-limit (429) errors directly to the user without fallback.
- Q: Is the embedding provider model-agnostic (caller passes model name per call) or model-specific (one provider instance per model)? → A: Model-agnostic — caller passes the target model name with each embed request; a single provider instance handles all models.
- Q: Should the active provider name be recorded in query traces for cost tracking and debugging? → A: Yes — add provider name to each query trace entry alongside the existing llm_model field.

## Assumptions

- The local Ollama instance URL is configured via an environment variable; Ollama installation is outside this spec's scope.
- The encryption key (`EMBEDINATOR_FERNET_KEY`) is a pre-generated valid symmetric key provided by the operator; auto-generation is not in scope.
- Only one LLM provider is active at a time; fan-out or load-balancing across providers is out of scope.
- The embedding provider is Ollama for this spec iteration; switching embedding providers to cloud services is out of scope.
- Cloud providers communicate over standard HTTP APIs; providers requiring local model weights (beyond Ollama) are out of scope.
- API key rotation (replacing an existing key) is handled by the delete-then-save flow already available via spec-08 endpoints.

## Dependencies

- **spec-07-storage** (COMPLETE): Provides the `providers` table in SQLite for persistent provider configuration and encrypted key storage.
- **spec-08-api** (COMPLETE): Implements the HTTP endpoints for provider management (`/api/providers/*`) and model listing (`/api/models/*`).
- **spec-09-frontend** (COMPLETE): The ProviderHub and ModelSelector components already consume the provider APIs implemented in spec-08.
- **spec-12-errors** (FUTURE): Provider-specific error types (`ProviderError`, `ProviderNotConfiguredError`, `ProviderAuthError`, `ProviderRateLimitError`, `ModelNotFoundError`) will be introduced in spec-12; this spec handles provider errors gracefully without them.
