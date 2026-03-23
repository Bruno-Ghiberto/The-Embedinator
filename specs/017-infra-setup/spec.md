# Feature Specification: Project Infrastructure

**Feature Branch**: `017-infra-setup`
**Created**: 2026-03-19
**Status**: Draft
**Input**: Docs/PROMPTS/spec-17-infra/17-specify.md

---

## Clarifications

### Session 2026-03-19

- Q: Is automated CI/CD pipeline configuration (e.g., GitHub Actions workflows) in scope for this spec? → A: Out of scope. CI/CD pipeline files are a separate concern. The Makefile targets (`make test`, `make build-rust`) serve as the integration hooks any pipeline can call.
- Q: Should container images run as non-root users? → A: Yes, required. Both backend and frontend containers MUST run as non-root users (principle of least privilege, consistent with spec-13 security hardening).
- Q: Is the deployment target single-node or horizontally scalable? → A: Single-node only. Horizontal scaling is explicitly out of scope; the architecture (SQLite, in-process checkpointing) is not compatible with multi-replica deployments.
- Q: How are secrets injected into production containers? → A: Via `.env` file passed to Docker Compose at runtime. The `.env` file MUST be gitignored and never committed; `.env.example` documents all variables without real values.
- Q: Should key architectural tradeoffs be recorded in the spec as explicit constraints? → A: Yes. SQLite-over-PostgreSQL, Rust-for-parsing, and dev-mode-separation are load-bearing decisions that must be captured to prevent planning-phase misalignment.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - First-Time Developer Setup (Priority: P1)

A new developer joins the project and needs a working local environment from scratch. They run a single setup command that installs all language dependencies, compiles the native binary component, and downloads required models. Within minutes the entire development environment is ready.

**Why this priority**: Without a reliable, automated setup path no one can develop, run, or test the project. It is the prerequisite for every other user story.

**Independent Test**: Can be fully tested by a developer with no prior knowledge of the project — they clone the repo, run setup on a clean machine, and subsequently run the test suite successfully, with no manual steps in between.

**Acceptance Scenarios**:

1. **Given** a machine with Docker, Python 3.14, Node.js 22+, and Rust 1.93 installed, **When** the developer runs the setup make target, **Then** all Python packages, frontend packages, and the native binary are installed without errors.
2. **Given** setup is complete, **When** the developer runs the backend test suite, **Then** all tests pass with no environment-related failures.
3. **Given** setup is complete, **When** the developer starts dev mode, **Then** the application API and frontend are accessible locally.

---

### User Story 2 - Developer-Mode Iteration Without Rebuilds (Priority: P2)

A developer is actively writing code and wants changes to take effect immediately. Only the infrastructure services (vector database and model inference) run in containers; the application code (backend and frontend) runs natively with automatic reload on every save.

**Why this priority**: This is the daily workflow of every developer. Slow feedback loops block productivity for all 16 downstream specs.

**Independent Test**: Developer saves a code change; the running application reflects the change within 3 seconds, with no manual restart or container rebuild step.

**Acceptance Scenarios**:

1. **Given** dev mode is running, **When** a developer modifies a backend source file, **Then** the backend process reloads automatically and serves the updated code within 3 seconds.
2. **Given** dev mode is running, **When** a developer modifies a frontend source file, **Then** the browser reflects the change without a full page reload.
3. **Given** dev mode is running, **When** the application is stopped, **Then** only the infrastructure containers (vector DB and model inference) continue running — they are not stopped by the application shutdown.

---

### User Story 3 - Full Production Deployment (Priority: P3)

An operator deploying the application to a server runs a single command to build and start all services (vector database, model inference, backend API, frontend) in containers. Services perform health checks and dependent services only start after their dependencies are healthy.

**Why this priority**: This is the production deployment path — required for anyone to run the application outside of development.

**Independent Test**: Running the production deploy command on a clean machine results in all four services becoming healthy and the application being accessible, with no manual intervention required.

**Acceptance Scenarios**:

1. **Given** Docker Engine is installed, **When** the operator runs the production deploy command, **Then** all four services start and each reports a healthy status.
2. **Given** the backend service is starting, **When** its infrastructure dependencies are not yet healthy, **Then** the backend waits and does not attempt to serve requests until dependencies are healthy.
3. **Given** an operator machine with an NVIDIA GPU, **When** the model inference service starts, **Then** it automatically uses the GPU for inference.
4. **Given** the deployment has accumulated data, **When** the operator runs a full restart (stop then start), **Then** all persisted data (documents, vectors, conversation history) is preserved with zero data loss.

---

### User Story 4 - Environment Configuration (Priority: P4)

A developer or operator configures the application for their environment — changing the default model, supplying API keys for external providers, or adjusting storage paths. They start from the provided configuration template and the system validates all settings at startup.

**Why this priority**: Without clear configuration, operators cannot adapt the system to different environments or integrate external AI providers added in specs 10–15.

**Independent Test**: An operator who has never seen the codebase can configure the system correctly using only the `.env.example` file and its comments, without reading any source code.

**Acceptance Scenarios**:

1. **Given** a fresh checkout, **When** the operator opens the configuration template, **Then** every configuration variable has a comment explaining its purpose, expected values, and a working default.
2. **Given** an invalid or missing required configuration value, **When** the application starts, **Then** it fails immediately with an error that identifies the invalid setting by name.
3. **Given** a complete valid configuration, **When** the application starts, **Then** it reads and applies all configured values correctly, including per-component log levels and rate limits.

---

### User Story 5 - Test Execution and Coverage Reporting (Priority: P5)

A developer runs the full test suite and verifies code coverage meets the project minimum. They use a make target that executes all backend tests, enforces a minimum coverage threshold, and exits non-zero if the threshold is not met.

**Why this priority**: Required for CI/CD verification and for developers to confirm that changes do not introduce regressions or reduce test coverage below the agreed minimum.

**Independent Test**: Can be run at any time without any running services (using in-memory fixtures). Produces a coverage report and exits with a non-zero code if coverage falls below 80%.

**Acceptance Scenarios**:

1. **Given** the project is set up, **When** the developer runs the test make target, **Then** all backend tests execute and produce a coverage report.
2. **Given** code coverage is below 80%, **When** the coverage make target runs, **Then** it exits with a non-zero code.
3. **Given** the frontend test make target is invoked, **When** it runs, **Then** frontend component and integration tests execute and results are reported.

---

### Edge Cases

- What happens when required infrastructure services are unavailable when dev mode starts?
- How does the build behave if the native binary compilation fails partway through?
- What happens when a required environment variable has no default and is not set?
- How does volume management behave when data directories already exist from a previous version?
- What happens when the clean make target is run while services are still running?
- What if a GPU is not present but GPU passthrough is configured in the compose file?
- What happens when the `make setup` target is run a second time on an already-set-up environment?

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The build system MUST provide a single setup target that installs all project dependencies — Python packages, frontend packages, and compiles the native document-parsing binary — in the correct dependency order without requiring manual steps.
- **FR-002**: The project MUST support two operating modes: (a) full containerized mode where all services (infrastructure and application) run in containers, and (b) development mode where only infrastructure services run in containers and application code runs natively with hot reload.
- **FR-003**: The native binary for document parsing MUST be compiled from source as part of the build process, and the resulting binary MUST be available to the Python backend in both development and production environments.
- **FR-004**: The production backend container image MUST be built in at least two stages: one that compiles the native binary and one that constructs the Python runtime with the binary included.
- **FR-005**: The production frontend container image MUST be built in at least two stages: one that produces the optimized production bundle and one that runs a minimal standalone server.
- **FR-006**: All containerized services MUST declare health check configurations so that the orchestrator can determine when each service is ready, and dependent services MUST only start after their declared dependencies are healthy.
- **FR-007**: All persistent data (database files, vector indices, uploaded files) MUST be stored in named volumes or bind-mounted host directories that survive container stop, start, and upgrade operations.
- **FR-008**: The model inference service MUST support hardware-accelerated (GPU) operation when the runtime environment provides it, and MUST fall back gracefully to CPU-only operation when it does not.
- **FR-009**: The configuration system MUST load all settings from environment variables (or a `.env` file) with typed defaults, and MUST validate every setting at application startup, failing fast with a descriptive error on invalid input.
- **FR-010**: A configuration template file MUST document every configuration variable with: a description of its purpose, expected value type and range, and a working default value.
- **FR-011**: The build system MUST provide named targets for each of the following operations: initial setup, building the native binary, starting infrastructure-only services, starting the backend natively, starting the frontend natively, starting full dev mode, starting full production mode, stopping all services, downloading required models, running backend tests, running backend tests with coverage, running frontend tests, removing runtime data, and removing all generated artifacts including volumes.
- **FR-012**: The test coverage target MUST enforce a minimum threshold of 80% and MUST exit with a non-zero status code when coverage falls below this threshold.
- **FR-013**: The frontend production build MUST produce a self-contained standalone server output so it can run as a minimal process without a full Node.js installation of the framework's development tools.
- **FR-014**: The production service configuration MUST include restart policies so that services automatically recover from transient failures without operator intervention.
- **FR-015**: Both the backend and frontend container images MUST be configured to run their processes as a non-root user, consistent with the principle of least privilege established in spec-13 (Security Hardening).

### Key Entities

- **Build Artifact**: The compiled native binary for document parsing — produced from source and included in the backend container; its availability is required for the ingestion pipeline (spec-06) to function.
- **Service Configuration**: The typed, validated collection of settings controlling all application behavior — loaded from environment variables at startup, covering server, storage, model, agent, retrieval, security, and observability parameters.
- **Persistent Volume**: A named storage location attached to a service ensuring data survives container restarts and upgrades.
- **Health Probe**: A declarative check attached to a service that the orchestrator uses to determine service readiness before starting dependent services.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer with the required runtimes installed can go from a clean repository clone to a fully running development environment using a single setup command, with zero manual troubleshooting steps required.
- **SC-002**: Code changes in development mode are reflected in the running application within 3 seconds, with no manual restart, rebuild, or container operation required.
- **SC-003**: The full production deployment starts all four services and makes the application reachable using a single command, with no manual configuration steps beyond providing the `.env` file.
- **SC-004**: All four services report a healthy status within 120 seconds of the production deployment command completing.
- **SC-005**: The configuration template documents 100% of the settings that control application behavior — an operator needs to read no source code to configure a production deployment.
- **SC-006**: The backend test suite enforces a minimum 80% code coverage threshold and fails the build automatically when this threshold is not met.
- **SC-007**: Application data (documents, conversation history, vector indices) persists across full container restarts (stop followed by start) with zero data loss.
- **SC-008**: The build system targets are self-documenting — a developer unfamiliar with the project can understand the purpose of each target from its name alone.

---

## Constraints & Tradeoffs

- **SQLite over PostgreSQL**: The project uses a single-file embedded database (WAL mode for concurrent reads) rather than a server-based database. This keeps deployment to a single host with no additional service dependency. Horizontal scaling is explicitly out of scope (confirmed Q3).
- **Rust binary for document parsing**: The native binary provides 5–20× throughput improvement over a pure-Python parser for PDF and Markdown ingestion. The tradeoff is a required Rust toolchain at build time and a two-stage Docker build. A pure-Python fallback is not provided.
- **Dev-mode separation (infrastructure in Docker, application native)**: Running only the infrastructure services (Qdrant, Ollama) in Docker while the application code runs natively means code changes reflect in under 3 seconds without any container rebuild. The tradeoff is that developers must have Python 3.14 and Node.js 22+ installed locally.
- **`confidence_threshold` as integer (0–100)**: The setting is stored and validated as an integer on a 0–100 scale. The agent edge converts it to a float (divides by 100) when comparing against the 0.0–1.0 output of the confidence scoring function. Implementers MUST NOT use a float default of `0.6`.

## Out of Scope

- **CI/CD pipeline files**: Automated pipeline definitions (GitHub Actions, GitLab CI, etc.) are not part of this spec. The Makefile targets (`make test`, `make test-cov`, `make build-rust`) are the integration points any external pipeline can invoke.
- **Horizontal scaling**: This infrastructure targets a single-host deployment only. Multi-replica backend scaling is incompatible with the SQLite and in-process checkpointing architecture established in prior specs and is not a goal of this spec.

## Assumptions

- Developers have Docker Engine 24+, Docker Compose v2, Node.js 22+, Python 3.14, and Rust 1.93 installed before running the setup target.
- The NVIDIA Container Toolkit is optional — GPU passthrough is enabled when present; the system works on CPU-only machines without additional configuration.
- The default LLM and embedding models are available for download from the public model registry via the `pull-models` target.
- The `data/` directory and all runtime subdirectories are created automatically at application startup and are not committed to the repository.
- All secrets (API keys, Fernet encryption key) are supplied via environment variables from a `.env` file at Compose runtime. The `.env` file is gitignored and never committed; `.env.example` documents every variable with placeholder values and comments.
- The production backend Dockerfile builds both the native binary and the Python backend runtime in a single multi-stage file.
- Frontend configuration (Tailwind CSS, PostCSS) follows the conventions of the installed framework version and does not require a separate configuration file.
