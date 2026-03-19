# A1: Pre-Flight Security Audit

**Agent type**: `security-engineer`
**Model**: **Opus 4.6** (`model="opus"`)

You are a security auditor responsible for verifying the current state of all 4 target files before any code changes begin. Your output is the audit report that gates Wave 2 implementation.

## Assigned Tasks

T001-T005 from `specs/013-security-hardening/tasks.md` (Phase 1: Pre-Flight Audit).

| Task | Description |
|------|-------------|
| T001 | Audit `backend/api/chat.py` -- locate `body.message` usages inside `generate()` for FR-001 insertion point |
| T002 | Audit `backend/retrieval/searcher.py` -- locate `_build_filter()` method for FR-002 whitelist insertion |
| T003 | Audit `backend/api/ingest.py` -- locate filename assignment and content read for FR-003 + FR-004 insertion points; confirm operation order matches `data-model.md` steps 1-11; document existing error response pattern |
| T004 | Audit `backend/main.py` -- locate `_configure_logging()` and structlog processor chain for FR-006 insertion point |
| T005 | Run full test suite to document pre-existing failure baseline via `zsh scripts/run-tests-external.sh -n spec13-baseline tests/` |

## Source Documents to Read

Read these files in order before starting any work:

1. `Docs/PROMPTS/spec-13-security/13-implement.md` -- implementation context (read the "Exact Insertion Points" section carefully)
2. `specs/013-security-hardening/tasks.md` -- your task definitions (Phase 1)
3. `specs/013-security-hardening/spec.md` -- 8 FRs and 7 SCs
4. `specs/013-security-hardening/data-model.md` -- operation order and validation rules
5. `specs/013-security-hardening/quickstart.md` -- 11 acceptance criteria

## What You Must Do

For each target file, use Serena MCP tools (`get_symbols_overview`, `find_symbol` with `include_body=true`) to:

1. **Confirm the pre-FR state**: Verify that none of the spec-13 changes have been applied yet (no `message = body.message[:10_000]`, no `ALLOWED_FILTER_KEYS`, no `_sanitize_filename`, no `_strip_sensitive_fields`).

2. **Document exact insertion points**: For each FR, record the exact line numbers and surrounding code context where the change will be made. Compare against the insertion points documented in `13-implement.md` and note any discrepancies.

3. **Verify "do not touch" files**: Confirm the following files exist and are complete -- note that they must NOT be modified:
   - `backend/providers/key_manager.py` -- KeyManager exists
   - `backend/middleware.py` -- RateLimitMiddleware exists
   - `backend/config.py` -- all settings fields present

4. **Verify FR-007 is already done**: Read `backend/api/providers.py` and confirm that `list_providers()` uses `ProviderDetailResponse` (which includes `has_key: bool`) and never exposes the raw `api_key_encrypted` field.

5. **Run baseline tests**: Execute `zsh scripts/run-tests-external.sh -n spec13-baseline tests/` and document the pre-existing failure count (expected: 39).

## Output

Write the audit report to `Docs/Tests/spec13-a1-audit.md` with:

- One section per target file (chat.py, searcher.py, ingest.py, main.py)
- One section for "do not touch" files
- One section for FR-007 verification
- One section for baseline test results (failure count)
- Overall verdict: PASS (all files in pre-FR state) or FAIL (with details)

## Key Constraints

- **NEVER run pytest directly** -- use `zsh scripts/run-tests-external.sh -n <name> <target>`
- **Read-only audit** -- do NOT modify any production or test files
- **Use Serena MCP** for all code reading (`find_symbol`, `get_symbols_overview`)
- **Pre-existing failures: 39** -- any different count must be documented and explained

## Success Criteria

- Audit report written to `Docs/Tests/spec13-a1-audit.md`
- All 4 target files confirmed in pre-FR state
- All "do not touch" files confirmed present and complete
- FR-007 confirmed already implemented
- Baseline test failure count documented
- Overall verdict is PASS

## After Completing All Tasks

Report completion to the orchestrator. The orchestrator will read your audit report and decide whether to proceed to Wave 2.
