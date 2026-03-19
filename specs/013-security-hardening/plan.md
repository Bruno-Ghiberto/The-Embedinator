# Implementation Plan: Security Hardening

**Branch**: `013-security-hardening` | **Date**: 2026-03-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/013-security-hardening/spec.md`

**Note**: Agent Teams orchestration plan is at `Docs/PROMPTS/spec-13-security/13-plan.md`.

## Summary

Add four targeted security hardening changes to four existing backend files: (1) silently truncate chat messages at 10,000 chars before processing and trace storage, (2) whitelist Qdrant filter keys in the retrieval searcher, (3) sanitize uploaded filenames and add PDF magic-byte content verification in the ingest endpoint, (4) insert a structlog processor that redacts sensitive field values from all log output. No new dependencies, no new modules, ~30 lines of net-new code.

## Technical Context

**Language/Version**: Python 3.14+
**Primary Dependencies**: FastAPI >=0.135, structlog >=24.0, re (stdlib), Pydantic v2 >=2.12
**Storage**: SQLite WAL mode (`data/embedinator.db`) — existing, no schema changes
**Testing**: pytest via external runner (`zsh scripts/run-tests-external.sh -n <name> <target>`)
**Target Platform**: Linux server, Docker (self-hosted, single-user)
**Project Type**: web-service (backend micro-changes to 4 existing files)
**Performance Goals**: Sub-millisecond for all new checks; zero measurable latency impact on any endpoint
**Constraints**: No new pip dependencies; stdlib `re` only; no new source files outside test files
**Scale/Scope**: 4 files modified; 5 new test files created; ~30 lines of production code added

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Verdict | Notes |
|-----------|---------|-------|
| I. Local-First Privacy | ✅ PASS | No new network calls. All changes are local input validation and log processing. |
| II. Three-Layer Agent Architecture | ✅ PASS | Not affected — no LangGraph changes. `chat.py` modification is pre-graph (message variable). |
| III. Retrieval Pipeline Integrity | ✅ PASS | FR-002 adds `ALLOWED_FILTER_KEYS` to `_build_filter()` — silently skips unknown keys; does not alter search mechanics, scoring, or reranking. |
| IV. Observability from Day One | ✅ PASS | FR-001 truncation applies to both `HumanMessage(content=message)` and `db.create_query_trace(query=message)`. Every request still produces a complete trace row. |
| V. Secure by Design | ✅ PASS | This spec is a direct implementation of §V requirements: log key stripping (FR-006), file upload validation hardening (FR-003/FR-004), API response protection (FR-007). KeyManager and RateLimitMiddleware from §V are already complete (spec-07, spec-08). |
| VI. NDJSON Streaming Contract | ✅ PASS | The streaming `generate()` coroutine is unchanged except for the `message` variable substitution. No event types or frame schemas altered. |
| VII. Simplicity by Default | ✅ PASS | stdlib `re` only; no helper classes; no new abstractions; no new modules in `backend/`; YAGNI throughout. |

**Constitution Check result: PASS. No gate failures. Proceed to Phase 0.**

## Project Structure

### Documentation (this feature)

```text
specs/013-security-hardening/
├── plan.md              # This file (/speckit.plan output)
├── research.md          # Phase 0 output — no unknowns; design decisions documented
├── data-model.md        # Phase 1 output — key entities and validation rules
├── quickstart.md        # Phase 1 output — verification steps
├── contracts/           # Phase 1 output — API surface contracts
│   ├── chat-endpoint.md
│   └── ingest-endpoint.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created by /speckit.plan)
```

### Source Code (changes only)

```text
backend/
├── api/
│   ├── chat.py              # FR-001: message = body.message[:10_000]; replace both body.message refs
│   └── ingest.py            # FR-003a: _sanitize_filename(); FR-003b: PDF b"%PDF" magic check
├── retrieval/
│   └── searcher.py          # FR-002: ALLOWED_FILTER_KEYS constant + _build_filter() whitelist
└── main.py                  # FR-004: _strip_sensitive_fields processor before JSONRenderer

tests/
└── unit/
    ├── api/
    │   ├── test_chat_security.py       # FR-001 truncation tests
    │   ├── test_ingest_security.py     # FR-003a sanitization + FR-003b magic byte tests
    │   └── test_providers_security.py  # AC-7: verify has_key present, api_key_encrypted absent
    ├── retrieval/
    │   └── test_searcher_security.py   # FR-002 filter key whitelist tests
    └── test_main_security.py           # FR-004 log field redaction tests
```

**Structure Decision**: Single Python backend project. All changes are additions or in-place modifications to existing `backend/` files. No Rust or TypeScript changes required.

## Agent Teams Implementation

See `Docs/PROMPTS/spec-13-security/13-plan.md` for the full Agent Teams orchestration plan:

- **3 waves, 4 agents**, tmux mandatory
- **Wave 1**: A1 (quality-engineer/opus) — pre-flight audit, T001–T008
- **Wave 2 (parallel)**: A2 (python-expert/sonnet) for FR-001+FR-002 and A3 (python-expert/sonnet) for FR-003+FR-004
- **Wave 3**: A4 (quality-engineer/sonnet) — full regression + all 11 ACs verified
- **External test runner only**: `zsh scripts/run-tests-external.sh -n <name> <target>`
