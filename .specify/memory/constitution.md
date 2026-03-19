<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.1 → 1.1.0 (MINOR — new principle added)

Principles:
  I.   Local-First Privacy — unchanged
  II.  Three-Layer Agent Architecture (ADR-002) — unchanged
  III. Retrieval Pipeline Integrity (ADR-004, ADR-005) — unchanged
  IV.  Observability from Day One (ADR-006) — unchanged
  V.   Secure by Design (ADR-008) — unchanged
  VI.  NDJSON Streaming Contract (ADR-007) — unchanged
  VII. Simplicity by Default (ADR-001, ADR-003) — unchanged
  VIII. Cross-Platform Compatibility — NEW

Sections modified:
  - Core Principles: added Principle VIII
  - Governance: version bump, amended date

Templates reviewed:
  ✅ .specify/templates/plan-template.md
     "Constitution Check" is generic (dynamically evaluates all principles).
     "Target Platform" placeholder exists (line 24) — no update needed.
  ✅ .specify/templates/spec-template.md
     No constitution-specific content — aligned as-is.
  ✅ .specify/templates/tasks-template.md
     Generic task structure — no constitution-specific references.

Deferred items: none.
Cross-references updated in PRD:
  ✅ Docs/Project Blueprints/prd.md — C7 constraint added
  ✅ Docs/Project Blueprints/performance-budget.md — OS row updated
  ✅ Docs/PROMPTS/spec-14-performance/14-specify.md — OS row updated
-->

# The Embedinator Constitution

## Core Principles

### I. Local-First Privacy

The system MUST run entirely on the user's own hardware with zero mandatory
outbound network calls in its default configuration. Ollama is the default
inference and embedding provider. Cloud providers (OpenRouter, OpenAI,
Anthropic) are strictly opt-in, enabled only when the user explicitly
configures an API key. The web interface MUST NOT require user authentication;
access control is the user's responsibility at the network level (firewall,
VPN).

**Rules**:
- Default `docker compose up` MUST produce a fully operational system with no
  internet calls after the initial model download.
- No authentication/login system SHALL be introduced. The trusted-local-network
  model is a permanent design decision, not a deferred feature.
- Cloud provider queries MUST be gated behind explicit user opt-in. The system
  MUST fall back to Ollama if a configured cloud provider is unavailable.

**Rationale**: The primary value proposition is private, local document
intelligence. Adding mandatory cloud dependencies or authentication would
contradict the product's reason to exist for its target users (technical
professionals, researchers, and privacy-conscious individuals).

---

### II. Three-Layer Agent Architecture (ADR-002)

The agent MUST be implemented as three nested LangGraph state machines:
`ConversationGraph → ResearchGraph → MetaReasoningGraph`. This layering is
non-negotiable and MUST be preserved across all build phases.

**Rules**:
- ConversationGraph manages session lifecycle, intent classification, and
  fan-out query decomposition.
- ResearchGraph executes tool-based retrieval loops per sub-question with an
  iteration budget.
- MetaReasoningGraph (Phase 2+) diagnoses retrieval failures and autonomously
  switches strategy; its scaffold MUST be present even when not yet activated.
- Single-loop flattening or prompt-based retry MUST NOT replace the three-layer
  structure.
- Maximum 2 meta-reasoning attempts per query to prevent infinite loops.

**Rationale**: Single-loop agents fail silently on hard queries. MetaReasoning
provides quantitative diagnosis (cross-encoder score signals) enabling
autonomous strategy switching — the primary architectural differentiator over
comparable open-source systems.

---

### III. Retrieval Pipeline Integrity (ADR-004, ADR-005)

The retrieval pipeline MUST use parent/child chunking with breadcrumbs,
hybrid dense + BM25 search, and cross-encoder reranking. No component of this
pipeline MAY be removed or replaced without a new ADR.

**Rules**:
- Child chunks MUST be ~500 characters; embedded and stored in Qdrant.
- Parent chunks MUST be 2000–4000 characters; stored in SQLite. When a child
  chunk matches a query, its parent chunk MUST be fetched for LLM context.
- Breadcrumb paths (e.g., `"Chapter 3 > 3.2 Auth > Token Lifecycle"`) MUST be
  prepended to child chunk text before embedding.
- Hybrid search (dense + BM25 via RRF) MUST be used for all retrieval; neither
  component MAY be disabled.
- Cross-encoder reranking (ms-marco-MiniLM-L-6-v2) MUST be applied to the
  top-20 candidates after hybrid retrieval. Removing reranking for performance
  is not permitted; reduce the candidate set instead.
- Child chunk point IDs MUST be deterministic UUID5 values keyed on
  `doc_id:chunk_index` for idempotent upserts.
- Phase 1 parsing uses Python. Phase 2+ parsing MUST use the Rust ingestion
  worker (ADR-003). Python parsing MUST NOT be retained in Phase 2 as the
  primary path.

**Rationale**: Each layer adds measurable precision. Flat chunking loses
document structure; removing BM25 misses keyword-match retrieval; removing
reranking degrades ranking quality. Breadcrumbs ensure embeddings carry
structural context beyond raw text similarity.

---

### IV. Observability from Day One (ADR-006)

Every query MUST produce a trace record. Trace recording is non-optional and
MUST NOT be skipped for any reason including performance optimisation.

**Rules**:
- Every `POST /api/chat` request MUST write a row to `query_traces` in SQLite
  capturing: query text, collections searched, passages retrieved with
  cross-encoder scores, confidence score (0–100), reasoning steps, strategy
  switches, and total latency in ms.
- Confidence MUST be computed from retrieval signals (weighted average of
  passage scores), never from LLM self-assessment.
- The confidence score (0–100 integer) MUST be displayed to the user in the
  chat UI alongside every answer — not only in the trace detail view.
- When a source document is deleted, existing trace records MUST retain the
  passage text they captured at query time and display a `source_removed: true`
  indicator in place of the source link.
- The `/observability` page (Phase 2) MUST expose: trace table with filters,
  latency histogram, confidence distribution chart, and health dashboard.

**Rationale**: Users need to understand and trust AI-generated answers.
Observability is the mechanism for trust. Retroactively adding trace recording
to async agent code paths is significantly harder than building it in from the
start.

---

### V. Secure by Design (ADR-008)

All credentials and sensitive configuration MUST be encrypted at rest.
Security controls MUST be implemented at the system boundary, not deferred.

**Rules**:
- All LLM provider API keys MUST be encrypted with Fernet (Python
  `cryptography` library) before storage in SQLite. They MUST be decrypted
  in-memory only at the moment of use and garbage-collected immediately after.
- API keys MUST NOT appear in logs (structlog processors MUST strip them),
  MUST NOT be returned in any API response, and MUST NOT be committed to git.
- The Fernet encryption key MUST come from `EMBEDINATOR_FERNET_KEY` env var.
  If absent, the application raises `ValueError` during startup; `main.py`
  handles this by setting `app.state.key_manager = None`. Provider key
  endpoints MUST return HTTP 503 when `key_manager` is `None`. There is no
  dev fallback — this forces explicit operator configuration and is the
  intentionally safer default.
- All SQL queries MUST use parameterized statements (`?` placeholders). String
  interpolation in SQL is forbidden.
- File uploads MUST be validated: extension allowlist (pdf, md, txt), 100 MB
  size limit, MIME content-type check.
- Rate limits MUST be enforced: 10 uploads/min, 30 chat/min, 120 general/min.
- CORS MUST be configured to restrict origins (default: `localhost:3000`).
- Every request MUST receive a UUID trace ID injected into structlog context
  via `bind_contextvars(trace_id=...)` at the middleware boundary.

**Rationale**: The threat model includes malicious file uploads, API key
exposure, and SQL injection. Controls at system boundaries prevent these
without burdening internal code. Encryption at rest protects users who store
cloud API keys locally.

---

### VI. NDJSON Streaming Contract (ADR-007)

Chat responses MUST stream over HTTP as Newline-Delimited JSON
(`application/x-ndjson`). The protocol format is fixed; changes require a
new ADR.

**Rules**:
- Every `POST /api/chat` response MUST use `StreamingResponse` with
  `media_type="application/x-ndjson"`.
- Token frames MUST use the schema: `{"type": "chunk", "text": "..."}`.
- The final frame MUST be a metadata frame:
  `{"type": "metadata", "trace_id": "...", "confidence": 0–100,
  "citations": [...], "latency_ms": ...}`.
- Error frames MUST use: `{"type": "error", "message": "...", "code": "..."}`.
- First token MUST appear within 500ms of query submission under normal
  operating conditions (target; actual Phase 1 ~800ms).
- WebSockets and JSON batch responses MUST NOT be used for chat streaming.

**Rationale**: NDJSON provides simple line-by-line parsing without the
`data:` prefix overhead of SSE. The fixed schema ensures all clients
(browser, CLI, test suite) parse responses identically.

---

### VII. Simplicity by Default (ADR-001, ADR-003)

The system MUST favour zero-config, single-file, and embedded solutions over
networked services wherever the performance requirement is met. Complexity MUST
be justified by a concrete, current need — not a hypothetical future one.

**Rules**:
- SQLite with WAL mode MUST be the sole relational database. PostgreSQL, MySQL,
  or any networked RDBMS MUST NOT be introduced without a new ADR that
  demonstrates the need exceeds SQLite's capabilities.
- The system MUST deploy via `docker compose up` producing exactly 4 services:
  Qdrant, Ollama, backend, frontend. Adding a 5th service requires an ADR.
- Python ingestion MUST be the implementation for Phase 1. The Rust worker
  (ADR-003) is a Phase 2 performance optimisation, not an upfront complexity.
- YAGNI applies: do not add abstractions, helpers, or configurations for
  hypothetical future requirements. Three similar lines of code is preferable
  to a premature abstraction.
- Concurrent users: 1–5. The system MUST NOT be designed to scale beyond
  this without an explicit scope change.

**Rationale**: A self-hosted tool for 1–5 users does not need a database
daemon, connection pooling, or horizontal scaling. SQLite's backup is
`cp embedinator.db backup.db`. Every additional service adds operational
complexity for users who just want to query their documents.

---

### VIII. Cross-Platform Compatibility

The system MUST deploy and operate identically on Windows 11+, macOS 13+,
and major Linux distributions (Ubuntu, Fedora, Debian). Docker Compose is the
canonical deployment mechanism and provides the primary platform abstraction.
The codebase MUST NOT introduce platform-specific assumptions that break any
of the three target operating systems.

**Rules**:
- `docker compose up` MUST produce an identical working system on all three
  target platforms. If a Docker configuration behaves differently across
  platforms, the divergence MUST be resolved — not documented as a known issue.
- Python file operations MUST use `pathlib.Path` (never hardcoded `/` or `\\`
  separators, never `os.path.join` with string literals).
- The Rust ingestion worker binary MUST be compilable for all three target
  platforms (x86_64-unknown-linux-gnu, x86_64-pc-windows-msvc,
  aarch64-apple-darwin / x86_64-apple-darwin). Platform-conditional compilation
  (e.g., `.exe` extension on Windows) MUST be handled in the build system,
  not in Python code.
- Configuration defaults in `backend/config.py` (e.g., `rust_worker_path`)
  MUST work on Linux and macOS out of the box. Windows users MAY need to
  override via environment variables — this is acceptable as Docker is the
  primary deployment path.
- Shell scripts in `scripts/` target bash/zsh (available on Linux and macOS).
  Windows users are expected to use WSL, Git Bash, or Docker. Creating
  PowerShell equivalents is NOT required (Principle VII applies).
- No platform-specific system calls, file locking mechanisms, or process
  management APIs SHALL be introduced without a cross-platform fallback or
  an explicit ADR justifying the platform restriction.

**Rationale**: The system's target users (technical professionals, researchers,
privacy-conscious individuals) work across all major operating systems. Docker
Compose already abstracts most platform differences. This principle ensures no
future spec inadvertently introduces Windows-only or Linux-only assumptions
that would exclude a third of potential users. The rules are deliberately
pragmatic: Docker does the heavy lifting, bash scripts require WSL on Windows
(a standard developer tool), and only the Rust build matrix requires explicit
multi-platform attention.

---

## Technology Stack & Architecture Constraints

The technology stack is pinned. Changes to pinned versions or introduction of
new core dependencies require an ADR documenting the rationale and migration
path.

### Backend (Python 3.14+)

| Dependency | Version | Purpose |
|---|---|---|
| FastAPI | >= 0.135 | API framework + StreamingResponse |
| LangGraph | >= 1.0.10 | Agent graph orchestration |
| LangChain | >= 1.2.10 | LLM abstraction and tool binding |
| Qdrant Client | >= 1.17.0 | Vector storage + hybrid search |
| sentence-transformers | >= 5.2.3 | Cross-encoder reranking |
| Pydantic v2 | >= 2.12 | Schema validation + Settings |
| aiosqlite | >= 0.21 | Async SQLite |
| httpx | >= 0.28 | Async HTTP client |
| cryptography | >= 44.0 | Fernet encryption |
| structlog | >= 24.0 | Structured JSON logging |
| tenacity | >= 9.0 | Retry + circuit breaker |

### Frontend (Node.js / TypeScript 5.7)

| Dependency | Version | Purpose |
|---|---|---|
| Next.js | 16 | React framework (Pages Router) |
| React | 19 | UI library |
| Tailwind CSS | 4 | Styling |
| SWR | 2 | Data fetching |
| recharts | 2 | Observability charts |

### Infrastructure

| Component | Notes |
|---|---|
| Qdrant | Dense + BM25 vector search |
| Ollama | Default LLM + embedding (local) |
| SQLite 3.45+ | WAL mode; single file: `data/embedinator.db` |
| Rust 1.93.1 | Ingestion worker (Phase 2 only) |

### Architecture Constraints

- All LLM providers MUST implement `LLMProvider` ABC from
  `backend/providers/base.py`.
- The provider registry (`backend/providers/registry.py`) MUST resolve
  model name → provider instance at query time (not cached statically).
- All settings MUST live in `backend/config.py` as `Settings(BaseSettings)`.
- All custom exceptions MUST extend base classes in `backend/errors.py`.
- The app MUST be created via `create_app()` factory in `backend/main.py`
  with a lifespan context manager for startup/shutdown.

---

## Development Standards & Quality Gates

### Testing Requirements

- Backend line coverage MUST be >= 80% (enforced via `pytest-cov`).
- Frontend line coverage MUST be >= 70% (enforced via `vitest --coverage`).
- Unit tests MUST use `monkeypatch.setenv()` — never `os.environ[]` directly
  (prevents environment leakage between tests).
- Integration tests against Qdrant MUST use the `unique_name()` helper for
  collection names to prevent 409 conflicts between parallel test runs.
- Tests requiring Docker services MUST be placed in `tests/integration/`.
  Tests in `tests/unit/` MUST run without any external services.

### Code Style

**Python**:
- Type hints MUST be present on all function signatures.
- `async/await` MUST be used for all I/O-bound operations.
- Pydantic models MUST be used for all API request/response schemas.
- Naming: `snake_case` for functions/variables; `PascalCase` for classes;
  `snake_case.py` for files.

**TypeScript / React**:
- `strict: true` MUST be set in `tsconfig.json`.
- Only functional components with hooks — no class components.
- SWR MUST be used for all server data fetching.
- Naming: `camelCase` for functions/variables; `PascalCase` for
  components/types; `PascalCase.tsx` for component files.

### Git & Branching

- Conventional commits are REQUIRED: `feat:`, `fix:`, `refactor:`,
  `test:`, `chore:`, `docs:`.
- Feature branches: `NNN-description` (NNN = zero-padded spec number).
- Bug fixes: `fix/<description>`.
- `main` MUST be production-ready at all times.

### Reliability Standards

- Circuit breaker MUST wrap ALL Qdrant and Ollama call sites: 5 consecutive
  failures opens the circuit; stays open for 30s cooldown; half-open probe
  after cooldown. No time-decay window — only consecutive failure count.
- Retry policy: 3 attempts, 1s initial delay, 2× multiplier (via tenacity).
- Embeddings MUST be validated before upsert: reject NaN values, zero vectors,
  and dimension mismatches.
- The system MUST respond gracefully (user-facing message) rather than crash
  on any recoverable error.

### Performance Budgets

| Metric | Target |
|---|---|
| First token latency (chat) | < 500ms target; < 800ms Phase 1 actual |
| Full answer (simple query) | < 5 seconds |
| Full answer (complex query) | < 15 seconds |
| Qdrant search (100K vectors) | < 100ms |
| `GET /api/health` | < 50ms |
| UI cold load | < 2 seconds |
| Ingestion (Python, Phase 1) | >= 10 pages/sec |
| Ingestion (Rust, Phase 2) | >= 50 pages/sec |

---

## Governance

This constitution supersedes all other project practices. Any work that
conflicts with a principle in this document requires an amendment before
proceeding — not after.

**Amendment procedure**:
1. Open a discussion describing the principle to change and the rationale.
2. If the change involves a settled ADR decision, write a new ADR that
   explicitly supersedes the prior one.
3. Update this constitution with the amended text, increment the version
   following semantic versioning rules (see below), and update
   `LAST_AMENDED_DATE`.
4. Run `/speckit.constitution` to propagate the change to dependent templates
   and artifacts.

**Versioning policy**:
- MAJOR: A principle is removed, fundamentally redefined, or a settled ADR
  decision is reversed.
- MINOR: A new principle or section is added, or existing guidance is
  materially expanded.
- PATCH: Clarifications, wording improvements, typo fixes, or non-semantic
  additions (examples, rationale notes).

**Compliance review**:
- Every speckit plan (`/speckit.plan`) MUST include a Constitution Check
  section evaluating each principle against the feature's design.
- A gate failure (principle violation) MUST be resolved or explicitly
  justified in the Complexity Tracking table before implementation begins.
- All code reviews MUST verify that the submitted code does not introduce
  violations (e.g., unauthenticated endpoints, skipped trace recording,
  plaintext key storage, platform-specific assumptions).

**Guidance file**: `PROMPTS/speckit-constitution-context.md` contains the
extended context used to derive this constitution and serves as the canonical
input for regenerating it.

**Version**: 1.1.0 | **Ratified**: 2026-03-10 | **Last Amended**: 2026-03-18
