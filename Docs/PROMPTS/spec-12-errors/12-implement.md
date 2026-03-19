# Spec 12: Error Handling -- Implementation Context

**Branch**: `012-error-handling` | **Date**: 2026-03-17 | **Spec**: `specs/012-error-handling/spec.md`

---

> [!IMPORTANT]
> **tmux multi-pane spawning is MANDATORY for this spec.**
> You MUST be running inside a tmux session before proceeding. Each spawned agent
> gets its own tmux pane (auto-detected). Manual single-agent implementation is NOT
> acceptable. If you are not in tmux, run `tmux new-session -s spec12` first.

---

**Scope**: 1 production file modified (`backend/main.py`), 2 test files created, 0 new production dependencies, ~35-50 new tests.

Spec-12 is a hardening spec. The exception hierarchy, circuit breakers, retry logic, and rate limiting are already implemented and working across specs 02-11. This spec standardises error responses by fixing/adding 4 exception handlers in `backend/main.py` and locking the contracts with tests.

> **Agent Teams documentation**: https://code.claude.com/docs/en/agent-teams

---

## MANDATORY: Agent Teams with tmux Multi-Pane Spawning

This implementation MUST use Claude Code Agent Teams. Manual single-agent implementation is NOT acceptable.

The orchestrator MUST:
1. Run inside tmux
2. Use `TeamCreate` to create the team
3. Use `TaskCreate` to define tasks for each wave
4. Spawn agents using `Agent(team_name=..., subagent_type=..., model=...)`
5. Each agent gets its own tmux pane (auto-detected when running in tmux)
6. Wait for gate checkpoints between waves
7. Use `SendMessage` to coordinate between agents
8. Use `TeamDelete` when all waves complete

### Wave Schedule

| Wave | Agent | subagent_type | Model | Tasks | Primary Output |
|------|-------|---------------|-------|-------|----------------|
| 1 | A1 (Audit) | `quality-engineer` | `claude-opus-4-6` | T001-T009 | Audit report at `Docs/Tests/spec12-a1-audit.md` |
| 2 | A2 (Handlers) | `python-expert` | `claude-sonnet-4-6` | T010-T018 | `backend/main.py` with 4 handler changes |
| 3 | A3 (Tests) | `python-expert` | `claude-sonnet-4-6` | T019-T036 | `tests/unit/test_error_contracts.py` + `tests/integration/test_error_handlers.py` |
| 4 | A4 (Regression) | `quality-engineer` | `claude-sonnet-4-6` | T037-T040 | Full regression gate, final report at `Docs/Tests/spec12-final-report.md` |

### Spawning Protocol

Each agent's FIRST action MUST be to read its instruction file. After an agent reads its file, it signals readiness with a brief status message (e.g., "A1 ready -- briefing complete"). The orchestrator then sends specific task assignments via `SendMessage`. Spawn with minimal prompts:

```
Agent(
    team_name="spec12-errors",
    subagent_type="quality-engineer",  # or "python-expert"
    model="claude-opus-4-6",           # or "claude-sonnet-4-6"
    prompt="Read your instruction file at Docs/PROMPTS/spec-12-errors/agents/A1-audit.md FIRST, then await further instructions."
)
```

### Gate Checkpoints

- **Gate 1** (after Wave 1): A1 writes `Docs/Tests/spec12-a1-audit.md` with `Gate status: PASS`. If FAIL, stop all waves.
- **Gate 2** (after Wave 2): A2 runs smoke test, confirms `Docs/Tests/spec12-a2-smoke.status` = `PASSED`.
- **Gate 3** (after Wave 3): A3 confirms `Docs/Tests/spec12-us5-final.status` = `PASSED`.
- **Gate 4** (after Wave 4): A4 confirms `Docs/Tests/spec12-regression.status` = `PASSED`, writes final report.

### Agent Instruction Files

All instruction files live at `Docs/PROMPTS/spec-12-errors/agents/`:

| File | Agent | Purpose |
|------|-------|---------|
| `A1-audit.md` | A1 | Pre-implementation codebase audit |
| `A2-main-handlers.md` | A2 | Production code changes to `backend/main.py` |
| `A3-tests.md` | A3 | Create both test files with all test classes |
| `A4-regression.md` | A4 | Full regression suite and final report |

---

## Critical Constraints

These are non-negotiable. Violating any of these will produce a destructive implementation.

**NEVER create exception classes in `backend/errors.py`**. The hierarchy is frozen at exactly 11 classes (1 base + 10 subclasses). The 20+ invented classes in the old `12-implement.md` (StorageError, AgentError, ProviderError, DatabaseError, RustWorkerError, EmbeddingValidationError, etc.) do NOT exist and MUST NOT be created.

**NEVER create a `CircuitBreaker` class or `backend/circuit_breaker.py`**. Circuit breakers are already implemented as instance variables in `QdrantClientWrapper`, `QdrantStorage`, and module-level globals in `nodes.py`. Constitution VII (YAGNI) applies.

**NEVER wire `retry_max_attempts` or `retry_backoff_initial_secs` to tenacity**. These are dead config fields in `Settings`, reserved for a future spec. Retry attempt counts remain hardcoded at call sites (e.g., `stop_after_attempt(3)` in `qdrant_client.py`).

**NEVER modify `backend/api/chat.py`**. The NDJSON stream error codes (`NO_COLLECTIONS`, `CIRCUIT_OPEN`, `SERVICE_UNAVAILABLE`) are already correct. The stream format `{"type": "error", ...}` is intentionally different from the REST envelope.

**NEVER use `{"type": "error"}` format in REST exception handlers**. That is the NDJSON stream format. REST handlers use the nested envelope: `{"error": {"code": ..., "message": ..., "details": ...}, "trace_id": ...}`.

**NEVER run pytest inside Claude Code**. Always use `zsh scripts/run-tests-external.sh -n <name> <target>`.

---

## What Actually Changes

### Production Code (1 file modified)

**`backend/main.py`** -- 4 handler changes inside `create_app()`:

1. **FIX** existing `ProviderRateLimitError` handler body (lines ~173-178) -- change from flat NDJSON-style format to nested REST envelope with `PROVIDER_RATE_LIMIT` code and `trace_id`
2. **ADD** global `EmbeddinatorError` catch-all handler -- HTTP 500, `INTERNAL_ERROR`
3. **ADD** specific `QdrantConnectionError` handler -- HTTP 503, `QDRANT_UNAVAILABLE`
4. **ADD** specific `OllamaConnectionError` handler -- HTTP 503, `OLLAMA_UNAVAILABLE`

### Test Code (2 files created)

- `tests/unit/test_error_contracts.py` -- 7 test classes, ~25-35 methods (static contract tests, no server)
- `tests/integration/test_error_handlers.py` -- 4 test classes, ~20 methods (FastAPI TestClient)

### Nothing Else

- 0 new production files
- 0 new production dependencies
- 0 changes to `backend/errors.py`, `backend/api/chat.py`, `backend/middleware.py`, `backend/config.py`
- 0 database schema changes

---

## Codebase Ground Truth (Verified)

These facts were verified against the live codebase via serena symbol inspection. All handler code and test assertions MUST match these exactly.

### Exception Hierarchy (`backend/errors.py`) -- FROZEN

```
EmbeddinatorError(Exception)        # base, no __init__ override
  |- QdrantConnectionError          # Qdrant connection failure
  |- OllamaConnectionError          # Ollama connection failure
  |- SQLiteError                    # SQLite operation failure
  |- LLMCallError                   # LLM inference call failure
  |- EmbeddingError                 # Embedding generation failure
  |- IngestionError                 # Document ingestion pipeline failure
  |- SessionLoadError               # Failed to load session from SQLite
  |- StructuredOutputParseError     # Failed to parse structured LLM output
  |- RerankerError                  # Cross-encoder reranking failure
  |- CircuitOpenError               # Raised when circuit breaker is open
```

All 10 subclasses extend `EmbeddinatorError` directly. No intermediate base classes. All instantiable with a plain string: `QdrantConnectionError("msg")`.

### ProviderRateLimitError (`backend/providers/base.py`) -- Separate Hierarchy

```python
class ProviderRateLimitError(Exception):
    """Raised by cloud providers on HTTP 429 rate limit responses."""

    def __init__(self, provider: str) -> None:
        self.provider = provider
        super().__init__(f"Rate limit exceeded for provider: {provider}")
```

Extends `Exception` directly, NOT `EmbeddinatorError`. Has `self.provider` attribute.

### Pydantic Models (`backend/agent/schemas.py`)

```python
class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict = {}

class ErrorResponse(BaseModel):
    error: ErrorDetail
    # NOTE: NO trace_id field -- trace_id is added as a plain dict key in handlers
```

### Settings Config Fields (`backend/config.py`)

All 8 required fields exist:

```python
# Accuracy & Robustness
circuit_breaker_failure_threshold: int = 5
circuit_breaker_cooldown_secs: int = 30
retry_max_attempts: int = 3           # dead config -- DO NOT wire to tenacity
retry_backoff_initial_secs: float = 1.0  # dead config -- DO NOT wire to tenacity

# Rate Limiting
rate_limit_chat_per_minute: int = 30
rate_limit_ingest_per_minute: int = 10
rate_limit_provider_keys_per_minute: int = 5
rate_limit_general_per_minute: int = 120
```

### Current `backend/main.py` Handler State

`create_app()` is defined at line 149, ends at line 192. The existing `ProviderRateLimitError` handler is at lines 173-179 and currently returns the WRONG format:

```python
@app.exception_handler(ProviderRateLimitError)
async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
    return JSONResponse(
        status_code=429,
        content={"type": "error", "message": str(exc), "code": "rate_limit"},
    )
```

Problems: flat NDJSON-style format (should be nested envelope), lowercase `"rate_limit"` code (should be `"PROVIDER_RATE_LIMIT"`), missing `trace_id`.

No `EmbeddinatorError`, `QdrantConnectionError`, or `OllamaConnectionError` handlers exist.

### `create_app` Blast Radius

`create_app` is called by the following callers (verified via gitnexus context):
- `tests/integration/test_us4_traces.py::trace_app` (fixture)
- `tests/integration/test_us3_streaming.py::streaming_app` (fixture)
- `tests/integration/test_us1_e2e.py::test_app` (fixture)
- `tests/integration/test_app_startup.py::test_app_creates_successfully`
- `tests/integration/test_app_startup.py::test_app_startup_initializes_services`
- `backend/main.py` module level: `app = create_app()`

Risk assessment: **LOW**. We are adding handlers inside the function body without changing its signature or return type. All existing callers continue to work unchanged.

---

## Handler Code (Exact Implementations)

All four handlers are registered inside `create_app()` in `backend/main.py`. Copy these exactly.

### Import Addition

Add after the existing `ProviderRateLimitError` import:

```python
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
```

### Handler 1: Fix ProviderRateLimitError (Replace Body)

```python
@app.exception_handler(ProviderRateLimitError)
async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "PROVIDER_RATE_LIMIT",
                "message": f"Rate limit exceeded for provider: {exc.provider}",
                "details": {"provider": exc.provider},
            },
            "trace_id": trace_id,
        },
    )
```

### Handler 2: Add EmbeddinatorError (Global Catch-All)

```python
@app.exception_handler(EmbeddinatorError)
async def embedinator_error_handler(request: Request, exc: EmbeddinatorError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

### Handler 3: Add QdrantConnectionError (503)

```python
@app.exception_handler(QdrantConnectionError)
async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "QDRANT_UNAVAILABLE",
                "message": "Vector database is temporarily unavailable",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

### Handler 4: Add OllamaConnectionError (503)

```python
@app.exception_handler(OllamaConnectionError)
async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "OLLAMA_UNAVAILABLE",
                "message": "Inference service is temporarily unavailable",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

### Registration Order

Registration order does not affect resolution (FastAPI uses MRO lookup), but by convention register specific before generic:

1. `ProviderRateLimitError` (429) -- fixed body
2. `QdrantConnectionError` (503)
3. `OllamaConnectionError` (503)
4. `EmbeddinatorError` (500) -- global catch-all, last

### Handler Pattern Invariants

All four handlers follow this exact pattern:

```python
@app.exception_handler(SomeError)
async def handler(request: Request, exc: SomeError):
    trace_id = getattr(request.state, "trace_id", "")
    return JSONResponse(
        status_code=XXX,
        content={
            "error": {
                "code": "UPPER_SNAKE_CASE",
                "message": "User-facing text. No class names or stack traces.",
                "details": {},
            },
            "trace_id": trace_id,
        },
    )
```

- `code` MUST be `UPPER_SNAKE_CASE`
- `message` MUST NOT expose exception class names, file paths, or internal details
- `details` MUST be a dict (empty `{}` is fine)
- `trace_id` MUST use `getattr(request.state, "trace_id", "")` -- never generate a new UUID
- Return `JSONResponse`, not `Response`

### Error Code Reference (spec-12 handlers only)

| Handler | HTTP Status | Code |
|---------|-------------|------|
| `ProviderRateLimitError` | 429 | `PROVIDER_RATE_LIMIT` |
| `EmbeddinatorError` | 500 | `INTERNAL_ERROR` |
| `QdrantConnectionError` | 503 | `QDRANT_UNAVAILABLE` |
| `OllamaConnectionError` | 503 | `OLLAMA_UNAVAILABLE` |

### REST vs NDJSON -- Two Different Formats (Do Not Confuse)

**REST error envelope** (used by the 4 exception handlers and all REST routers):

```json
{
  "error": {
    "code": "UPPER_SNAKE_CASE",
    "message": "User-facing text",
    "details": {}
  },
  "trace_id": "uuid-string"
}
```

**NDJSON stream error** (used by `POST /api/chat` only -- DO NOT TOUCH):

```json
{"type": "error", "message": "...", "code": "...", "trace_id": "..."}
```

---

## Testing Protocol

**NEVER run pytest inside Claude Code.** Use the external runner exclusively.

### Running Tests

```bash
# Run specific test file
zsh scripts/run-tests-external.sh -n <name> <target>

# Poll status
cat Docs/Tests/<name>.status    # RUNNING | PASSED | FAILED | ERROR

# Read summary (~20 lines, token-efficient)
cat Docs/Tests/<name>.summary

# Read full log (if debugging failures)
cat Docs/Tests/<name>.log
```

### Test Run Names by Phase

| Phase | Run Name | Target |
|-------|----------|--------|
| Wave 2 smoke | `spec12-a2-smoke` | `tests/unit/test_schemas_api.py tests/unit/test_middleware_rate_limit.py` |
| US1 unit contracts | `spec12-unit-contracts` | `tests/unit/test_error_contracts.py` |
| US1 integration | `spec12-integration-handlers` | `tests/integration/test_error_handlers.py` |
| US1 combined gate | `spec12-us1` | `tests/unit/test_error_contracts.py tests/integration/test_error_handlers.py` |
| US2-US4 gate | `spec12-us2-us4` | `tests/unit/test_error_contracts.py` |
| US5 final | `spec12-us5-final` | `tests/unit/test_error_contracts.py` |
| Full regression | `spec12-regression` | `tests/` |
| Regression rerun | `spec12-regression-final` | `tests/` |

### Expected Final Counts

- Pre-spec-12 baseline: 1250 passing
- New spec-12 tests: ~35-50
- Total passing after spec-12: ~1285-1300
- Pre-existing failures (unchanged): 39
- New regressions: 0

---

## Reference Documents

All authoritative spec artifacts live in `specs/012-error-handling/`:

| Document | Purpose |
|----------|---------|
| `spec.md` | Feature specification -- 14 FRs, 7 SCs, 5 user stories |
| `plan.md` | Implementation plan with exact handler code |
| `tasks.md` | 40 tasks across 6 phases, 4 agent waves |
| `data-model.md` | Exception hierarchy, error codes, response schemas |
| `contracts/error-response.md` | REST and NDJSON error contracts |
| `quickstart.md` | Step-by-step implementation checklist |
| `research.md` | 4 research decisions (R1-R4) |
