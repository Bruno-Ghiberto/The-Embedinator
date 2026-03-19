# Spec 13: Security Hardening -- Implementation Context

## MANDATORY: tmux Multi-Pane Agent Teams Execution

This implementation MUST be executed using Claude Code Agent Teams with tmux multi-pane spawning.
DO NOT attempt to implement this spec without Agent Teams orchestration.

Reference: https://code.claude.com/docs/en/agent-teams

### Spawning Protocol

1. Open tmux with enough panes for all agents (4 panes minimum)
2. Spawn each agent with: "Read your instruction file at `Docs/PROMPTS/spec-13-security/agents/<file>.md` FIRST, then execute all assigned tasks"
3. Use SendMessage to coordinate between waves
4. Each agent reads its briefing file BEFORE doing any work

Spawn command for every agent (no exceptions):

```
Agent(
  subagent_type="<type>",
  model="<model>",
  prompt="Read your instruction file at Docs/PROMPTS/spec-13-security/agents/<file>.md FIRST, then execute all assigned tasks"
)
```

---

## Scope Summary

Spec-13 closes four specific security gaps in the existing codebase. All changes are small, surgical additions to existing files.

- **4 production files modified** (chat.py, searcher.py, ingest.py, main.py)
- **5 test files created** (~21 tests total)
- **~30 lines of net-new production code**
- **0 new modules, 0 new pip dependencies** (stdlib `re` only)
- **4 FRs implemented** + FR-005 implicit + FR-007 verified + FR-008 regressed

---

## Already Built -- DO NOT Reimplement

The following were completed in earlier specs. Agents MUST NOT touch these files or recreate these components:

| Component | Spec | Location | Status |
|-----------|------|----------|--------|
| `KeyManager` (Fernet encryption) | spec-07 | `backend/providers/key_manager.py` | Complete -- DO NOT MODIFY |
| `RateLimitMiddleware` (per-IP, 4 buckets) | spec-08 | `backend/middleware.py` | Complete -- DO NOT MODIFY |
| `CORSMiddleware` registration | spec-08 | `backend/main.py` `create_app()` | Complete -- DO NOT MODIFY |
| Extension allowlist + size check | spec-08 | `backend/api/ingest.py` lines 16-19, 31-49 | Complete -- DO NOT MODIFY |
| Collection name regex validation | spec-08 | `backend/api/collections.py` | Complete -- DO NOT MODIFY |
| All rate limit + CORS settings fields | spec-08 | `backend/config.py` | Complete -- DO NOT MODIFY |
| `ProviderDetailResponse` with `has_key` | spec-10 | `backend/api/providers.py` | Complete -- VERIFY ONLY |
| `TraceIDMiddleware` + `RequestLoggingMiddleware` | spec-08 | `backend/middleware.py` | Complete -- DO NOT MODIFY |
| Error hierarchy (`EmbeddinatorError` etc.) | spec-12 | `backend/errors.py` | Complete -- DO NOT MODIFY |

The old `13-implement.md` described building `KeyManager`, `FileValidator`, `RateLimiter`, and CORS middleware from scratch. That was **completely wrong**. All of those already exist. This rewrite corrects the scope.

---

## FR Numbering Cross-Reference

Spec.md and plan.md use slightly different FR numbering. This table maps between them. **All documents in this spec use spec.md numbering (FR-001 through FR-008).**

| Spec FR | Plan FR | Description | File | Change Type |
|---------|---------|-------------|------|-------------|
| FR-001 | FR-001 | Chat message truncation | `backend/api/chat.py` | 1 assignment + 2 reference replacements |
| FR-002 | FR-002 | Filter key whitelist | `backend/retrieval/searcher.py` | 1 constant + 1 guard in loop |
| FR-003 | FR-003a | Filename sanitization | `backend/api/ingest.py` | 1 import, 1 constant, 1 function, 1 assignment change |
| FR-004 | FR-003b | PDF magic byte check | `backend/api/ingest.py` | 1 check block (6 lines) |
| FR-005 | *(implicit)* | No magic for non-PDF | `backend/api/ingest.py` | Implicit in FR-004 impl (PDF-only check) |
| FR-006 | FR-004 | Log field redaction | `backend/main.py` | 1 function + 1 processor chain insertion |
| FR-007 | *(n/a)* | No encrypted keys in responses | `backend/api/providers.py` | Verification test only -- already implemented |
| FR-008 | *(n/a)* | Preserve existing security | *(all files)* | Regression suite -- no production changes |

---

## Wave Execution Plan

### Wave 1 -- Pre-Flight Audit (Sequential)

| Field | Value |
|-------|-------|
| Agent | A1 |
| Type | `security-engineer` |
| Model | **Opus 4.6** (`model="opus"`) |
| Tasks | T001-T005 |
| Instruction file | `Docs/PROMPTS/spec-13-security/agents/A1-security-audit.md` |
| Output | `Docs/Tests/spec13-a1-audit.md` |

**Gate condition**: Audit report exists AND confirms all 4 target files are in pre-FR state (no partial implementation). Do not spawn Wave 2 until this gate passes.

### Wave 2 -- Implementation (Parallel)

Both A2 and A3 run simultaneously in separate tmux panes. They modify different files and cannot conflict.

#### A2 -- Chat + Search Hardening

| Field | Value |
|-------|-------|
| Agent | A2 |
| Type | `python-expert` |
| Model | **Sonnet 4.6** (`model="sonnet"`) |
| Tasks | T012-T018 |
| Instruction file | `Docs/PROMPTS/spec-13-security/agents/A2-chat-search.md` |
| Files modified | `backend/api/chat.py`, `backend/retrieval/searcher.py` |
| New test files | `tests/unit/api/test_chat_security.py`, `tests/unit/retrieval/test_searcher_security.py` |

#### A3 -- Ingest + Logs Hardening

| Field | Value |
|-------|-------|
| Agent | A3 |
| Type | `python-expert` |
| Model | **Sonnet 4.6** (`model="sonnet"`) |
| Tasks | T006-T011, T019-T023b |
| Instruction file | `Docs/PROMPTS/spec-13-security/agents/A3-ingest-logs.md` |
| Files modified | `backend/api/ingest.py`, `backend/main.py` |
| New test files | `tests/unit/api/test_ingest_security.py`, `tests/unit/test_main_security.py` |

**Wave 2 gate condition**: Both A2 and A3 complete all assigned tasks. Each agent's external test run returns PASSED. Pre-existing failure count does not increase from 39.

### Wave 3 -- Regression + AC Verification (Sequential)

| Field | Value |
|-------|-------|
| Agent | A4 |
| Type | `quality-engineer` |
| Model | **Sonnet 4.6** (`model="sonnet"`) |
| Tasks | T024-T027 |
| Instruction file | `Docs/PROMPTS/spec-13-security/agents/A4-regression.md` |
| Output | `Docs/Tests/spec13-a4-final.md` |

**Final gate condition**: All 11 ACs pass. Pre-existing failure count remains 39. Final report written.

---

## Exact Insertion Points (from Serena Code Audit)

This section documents the precise code context for each change, verified against the current codebase on branch `013-security-hardening`.

### FR-001 -- chat.py (lines 58-220)

**File**: `backend/api/chat.py`
**Function**: `generate()` (inner async generator, defined at line 58 inside `chat()`)
**Two `body.message` occurrences to replace**:

1. **Line 77** -- `HumanMessage(content=body.message)` inside `initial_state` dict
2. **Line 176** -- `query=body.message` inside `db.create_query_trace(...)` call

**Change**: Add `message = body.message[:10_000]` after the session event yield (line 74) and before `initial_state` construction (line 76). Replace both `body.message` references with `message`.

Current code (lines 72-77):
```python
        # 1. Session event (BEFORE astream)
        yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

        initial_state = {
            "session_id": session_id,
            "messages": [HumanMessage(content=body.message)],
```

After change:
```python
        # 1. Session event (BEFORE astream)
        yield json.dumps({"type": "session", "session_id": session_id}) + "\n"

        message = body.message[:10_000]  # FR-001: silent truncation

        initial_state = {
            "session_id": session_id,
            "messages": [HumanMessage(content=message)],
```

And at line ~176:
```python
                    query=message,  # was: query=body.message
```

**No new imports needed.** String slicing is a builtin operation.

### FR-002 -- searcher.py (lines 65-76)

**File**: `backend/retrieval/searcher.py`
**Method**: `HybridSearcher._build_filter()` at lines 65-76
**Current imports** (lines 13-20): Already imports `FieldCondition`, `Filter`, `MatchValue` from `qdrant_client.models`

**Change 1**: Add module-level constant after the imports block (after line 24, before class definition):
```python
ALLOWED_FILTER_KEYS = {"doc_type", "source_file", "page", "chunk_index"}
```

**Change 2**: Add guard inside the `for key, value` loop in `_build_filter()`:

Current code (lines 65-76):
```python
    def _build_filter(self, filters: dict | None) -> Filter | None:
        """Build Qdrant Filter from a dict of field conditions."""
        if not filters:
            return None

        conditions = []
        for key, value in filters.items():
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )

        return Filter(must=conditions) if conditions else None
```

After change:
```python
    def _build_filter(self, filters: dict | None) -> Filter | None:
        """Build Qdrant Filter from a dict of field conditions."""
        if not filters:
            return None

        conditions = []
        for key, value in filters.items():
            if key not in ALLOWED_FILTER_KEYS:
                continue  # FR-002: silently ignore unknown keys
            conditions.append(
                FieldCondition(key=key, match=MatchValue(value=value))
            )

        return Filter(must=conditions) if conditions else None
```

**No new imports needed.** The constant is a plain set literal.

### FR-003 -- ingest.py (filename sanitization)

**File**: `backend/api/ingest.py`
**Function**: `ingest_file()` at lines 21-144

**Change 1**: Add import at line 3 (after `import asyncio`, `import uuid`):
```python
import re as _re
```

**Change 2**: Add module-level constant and function after the `ALLOWED_EXTENSIONS` set (after line 19):
```python
_SAFE_FILENAME = _re.compile(r"[^a-zA-Z0-9._-]")


def _sanitize_filename(raw: str) -> str:
    """Strip path traversal sequences and unsafe characters from a filename."""
    name = raw.replace("\\", "/").split("/")[-1]
    name = name.replace("..", "")
    name = _SAFE_FILENAME.sub("_", name)
    return name or "upload"
```

**Change 3**: Replace the filename assignment at line 74 (currently inside step "4. Save file"):

Current:
```python
    filename = file.filename or f"document{suffix}"
```

After:
```python
    filename = _sanitize_filename(file.filename or f"document{suffix}")
```

### FR-004 -- ingest.py (PDF magic byte check)

**File**: `backend/api/ingest.py`
**Function**: `ingest_file()` at lines 21-144
**Insertion point**: After the size check block (which ends at line 49 with the `FILE_TOO_LARGE` HTTPException) and BEFORE the collection existence check (line 52, `collection = await db.get_collection(collection_id)`).

Insert this block between lines 50-51:
```python
    # PDF magic byte check (FR-004)
    if suffix == ".pdf" and content[:4] != b"%PDF":
        trace_id = getattr(request.state, "trace_id", "")
        raise HTTPException(status_code=400, detail={
            "error": {
                "code": "FILE_CONTENT_MISMATCH",
                "message": "File content does not match declared type",
                "details": {"expected_magic": "%PDF"},
            },
            "trace_id": trace_id,
        })
```

**Error pattern**: This matches the exact error envelope format used by the existing `FILE_FORMAT_NOT_SUPPORTED` and `FILE_TOO_LARGE` guards already in the function.

### FR-006 -- main.py (log redaction)

**File**: `backend/main.py`
**Function**: `_configure_logging()` at lines 29-46
**Current processor chain**: 6 processors ending with `structlog.processors.JSONRenderer()` at line 38

**Change 1**: Define `_strip_sensitive_fields` function at module level, above `_configure_logging()` (insert before line 29):
```python
_SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization"}


def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    """Redact sensitive field values in log records (FR-006)."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict
```

**Change 2**: Insert `_strip_sensitive_fields` into the processor list at position -2 (immediately before `JSONRenderer`):

Current (lines 31-39):
```python
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
```

After:
```python
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _strip_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
```

**No new imports needed.** The function uses only builtins (`list`, `dict.keys`, `str.lower`).

### FR-007 -- providers.py (verification only)

**File**: `backend/api/providers.py`
**Function**: `list_providers()` at lines 13-39
**Status**: Already correctly implemented. The function serializes via `ProviderDetailResponse.model_dump()`, which includes `has_key: bool` and does NOT include `api_key_encrypted`. The raw DB row (which contains `api_key_encrypted`) is never exposed.

**Action**: Write a verification test only. No production code changes.

---

## Error Response Patterns

All new error responses MUST match the existing envelope format used throughout `ingest.py`:

```json
{
  "error": {
    "code": "<ERROR_CODE>",
    "message": "<human-readable message>",
    "details": { ... }
  },
  "trace_id": "<uuid>"
}
```

The `trace_id` is obtained via `getattr(request.state, "trace_id", "")` -- this is the existing pattern in every guard block in `ingest_file()`.

New error code introduced by spec-13:
- `FILE_CONTENT_MISMATCH` -- HTTP 400 -- PDF magic byte check failure

Existing error codes preserved (FR-008):
- `FILE_FORMAT_NOT_SUPPORTED` -- HTTP 400 -- Extension not in allowlist
- `FILE_TOO_LARGE` -- HTTP 413 -- File exceeds max size
- `COLLECTION_NOT_FOUND` -- HTTP 404 -- Collection does not exist
- `DUPLICATE_DOCUMENT` -- HTTP 409 -- Identical content already ingested

---

## Ingest Operation Order (Post Spec-13)

The full operation order inside `ingest_file()` after all spec-13 changes are applied:

```
1.  Validate extension        --> 400 FILE_FORMAT_NOT_SUPPORTED     (existing, lines 31-42)
2.  Read content into memory  --> N/A                                (existing, line 44)
3.  Validate file size        --> 413 FILE_TOO_LARGE                 (existing, lines 45-49)
4.  PDF magic byte check      --> 400 FILE_CONTENT_MISMATCH          (NEW -- FR-004)
5.  Verify collection exists  --> 404 COLLECTION_NOT_FOUND           (existing, lines 52-60)
6.  Sanitize filename         --> N/A (no error, just transform)     (NEW -- FR-003)
7.  Save file to disk         --> N/A                                (existing, lines 74-77)
8.  Compute hash + dedup      --> 409 DUPLICATE_DOCUMENT             (existing, lines 79-91)
9.  Check for changed file    --> N/A                                (existing, lines 93-101)
10. Create document + job     --> N/A                                (existing, lines 103-113)
11. Launch background ingest  --> N/A                                (existing, lines 115-123)
```

---

## Testing Protocol

**NEVER run pytest directly inside Claude Code.** All testing uses the external runner:

```bash
# Run a target
zsh scripts/run-tests-external.sh -n <name> <target>

# Check status (poll)
cat Docs/Tests/<name>.status        # RUNNING | PASSED | FAILED | ERROR

# Read results
cat Docs/Tests/<name>.summary       # ~20 lines, token-efficient
cat Docs/Tests/<name>.log           # full pytest output if needed
```

**The external test runner accepts ONE target per invocation.** To test multiple directories, run separate invocations.

### External Test Run Schedule

| Agent | Run name | Target | When |
|-------|----------|--------|------|
| A1 | `spec13-baseline` | `tests/` | Phase 1 (document pre-existing baseline) |
| A2 | `spec13-a2` | `tests/unit/` | After T012-T013 complete |
| A3 | `spec13-a3` | `tests/unit/` | After T022 complete |
| A4 | `spec13-a4-full` | `tests/` | Wave 3 start (T024) |

### New Test File Locations

```
tests/
  unit/
    api/
      test_chat_security.py        # A2 -- FR-001 (~4 tests)
      test_ingest_security.py      # A3 -- FR-003, FR-004 (~7 tests)
      test_providers_security.py   # A4 -- AC-7 verification (~2 tests)
    retrieval/
      test_searcher_security.py    # A2 -- FR-002 (~4 tests)
    test_main_security.py          # A3 -- FR-006 (~4 tests)
```

### Pre-Existing Failure Baseline

**Expected: 39 pre-existing failures.** Any increase is a regression that MUST be investigated and resolved before proceeding to the next wave.

---

## Acceptance Criteria Verification Checklist

All 11 acceptance criteria from `specs/013-security-hardening/quickstart.md`. A4 must verify every one in Wave 3.

| AC | Description | Verification Method |
|----|-------------|---------------------|
| AC-1 | 15,000-char message processed; `query_traces.query` is 10,000 chars | Unit test in `test_chat_security.py` |
| AC-2 | `_build_filter({"arbitrary_field": "x"})` returns `None` | Unit test in `test_searcher_security.py` |
| AC-3 | Upload file named `../../etc/passwd.txt`; DB stores clean name | Unit test in `test_ingest_security.py` |
| AC-4 | Upload `.pdf` starting with `AAAA`; HTTP 400 `FILE_CONTENT_MISMATCH` | Unit test in `test_ingest_security.py` |
| AC-5 | Upload `.md` with any content; upload succeeds | Unit test in `test_ingest_security.py` |
| AC-6 | Log event with `api_key="real-key"`; JSON shows `[REDACTED]` | Unit test in `test_main_security.py` |
| AC-7 | `GET /api/providers` has `has_key`, no `api_key_encrypted` | Unit test in `test_providers_security.py` |
| AC-8 | Upload `.exe` returns HTTP 400 `FILE_FORMAT_NOT_SUPPORTED` | Existing test OR new test in `test_ingest_security.py` |
| AC-9 | Upload >100 MB returns HTTP 413 `FILE_TOO_LARGE` | Existing test (regression) |
| AC-10 | 31 chat requests/60s returns HTTP 429 on 31st | Existing test (regression) |
| AC-11 | `_strip_sensitive_fields` at index -2 in processor chain | Unit test in `test_main_security.py` |

---

## Wave Gates Summary

| Gate | Condition | Blocks |
|------|-----------|--------|
| Wave 1 -> Wave 2 | `Docs/Tests/spec13-a1-audit.md` exists; all 4 target files confirmed in pre-FR state; `providers.py` already returns `has_key` | Wave 2 spawn |
| Wave 2 -> Wave 3 | `spec13-a2.status = PASSED` AND `spec13-a3.status = PASSED`; no new failures above 39 baseline | Wave 3 spawn |
| Final | `spec13-a4-full.status = PASSED`; all 11 ACs verified; pre-existing failure count = 39; final report written | Spec-13 complete |

---

## Key Constraints

### No New Dependencies (SC-007)

All changes use Python stdlib only:
- `re` -- used in `ingest.py` for `_SAFE_FILENAME` regex (imported as `import re as _re`)
- No new imports needed in `chat.py`, `searcher.py`, or `main.py`

### Silent Truncation (FR-001)

The message truncation MUST be silent. Do not raise an exception, emit a log warning, or return an error. The truncated value is simply used downstream.

### Silent Filter Key Ignoring (FR-002)

Unknown filter keys MUST be silently ignored via `continue`. Do not raise an exception or log a warning. `ALLOWED_FILTER_KEYS` is a module-level constant (not a class attribute).

### Filename Sanitization Behavior (FR-003)

`_sanitize_filename` MUST: (1) replace backslashes with forward slashes and take the last segment, (2) remove all `..` substrings, (3) replace `[^a-zA-Z0-9._-]` with `_`, (4) return `"upload"` if result is empty. The sanitized name is used for both the on-disk path and the `filename` argument to `db.create_document()`.

### PDF Magic Check Placement (FR-004)

The check MUST be placed after the size check and BEFORE the collection existence check. The check is PDF-only. Do not add magic byte checks for any other extension.

### Structlog Processor Order (FR-006)

After spec-13, the processor chain has 7 entries. `_strip_sensitive_fields` is at position 6 (index -2, immediately before `JSONRenderer`). It replaces VALUES of sensitive keys with `"[REDACTED]"` but does NOT delete the keys. Top-level keys only -- no nested scanning.

### Constitution Compliance

All changes comply with the constitution (verified in plan.md):
- I. Local-First Privacy: No new network calls
- II. Three-Layer Agent Architecture: No LangGraph changes
- III. Retrieval Pipeline Integrity: Filter whitelist adds validation, does not alter search mechanics
- IV. Observability: Trace recording still occurs on every request
- V. Secure by Design: This spec directly implements remaining section V requirements
- VI. NDJSON Streaming Contract: No event types or frame schemas altered
- VII. Simplicity by Default: stdlib `re` only, no new abstractions

---

## Source Documents

Agents should read these files in priority order:

1. `Docs/PROMPTS/spec-13-security/13-implement.md` -- this file (implementation context)
2. `Docs/PROMPTS/spec-13-security/13-plan.md` -- Agent Teams orchestration plan
3. `specs/013-security-hardening/tasks.md` -- 28 tasks across 6 phases
4. `specs/013-security-hardening/quickstart.md` -- implementation guide + 11 ACs
5. `specs/013-security-hardening/spec.md` -- 4 user stories, 8 FRs, 7 SCs
6. `specs/013-security-hardening/data-model.md` -- entities and validation rules
7. `specs/013-security-hardening/contracts/chat-endpoint.md` -- FR-001 contract
8. `specs/013-security-hardening/contracts/ingest-endpoint.md` -- FR-003/FR-004 contract
9. `specs/013-security-hardening/research.md` -- R1-R6 decisions
10. `.specify/memory/constitution.md` -- project constitution (non-negotiable)
