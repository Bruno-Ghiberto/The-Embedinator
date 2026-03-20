# A7 — Quality Engineer: Full Validation

## Role & Mission

You are the quality engineer responsible for validating all 10 success criteria, running regression tests (backend + frontend), verifying no new packages were added, and writing the final validation report.

## Task Ownership

T076 through T089 (Phase 8: Validation & Cross-Platform Testing)

### Tasks

- **T076**: Validate SC-001: verify `docker compose config` parses for base and all overlays. Verify all 4 service definitions present with correct health checks.
- **T077**: Validate SC-002: verify `embedinator.ps1` syntax with `pwsh -NoProfile -Command "& { Get-Help ./embedinator.ps1 }"` (or syntax check if pwsh not available). If pwsh is not installed, perform a manual code review of the script structure.
- **T078**: Validate SC-003: verify GPU detection logic in `embedinator.sh` — trace the NVIDIA/AMD/Intel/CPU code paths. Verify macOS always returns `none`.
- **T079**: Validate SC-004: verify Docker Compose variable interpolation — `EMBEDINATOR_PORT_FRONTEND=4000 docker compose config` shows `4000:3000` port mapping.
- **T080**: Validate SC-005: verify `frontend/next.config.ts` contains `rewrites()`, `frontend/lib/api.ts` has empty-string `API_BASE`, no `NEXT_PUBLIC_API_URL` in `docker-compose.yml`.
- **T081**: Validate SC-006: verify `backend/api/health.py` Ollama probe parses model list and reports availability in response. Read the code and trace the logic.
- **T082**: Validate SC-007: verify `BackendStatusProvider`, `StatusBanner`, and chat input gating are wired up — check imports in `layout.tsx`, `SidebarLayout.tsx`, `ChatInput.tsx`.
- **T083**: Validate SC-008: verify `embedinator.sh` generates Fernet key via Docker container without local Python — trace the key generation code path. Confirm it uses `docker run --rm python:3.14-slim`.
- **T084**: Validate SC-009: verify health polling timeout logic — 300s first run, 60s subsequent — in `embedinator.sh`. Search for the timeout values in the script.
- **T085**: Validate SC-010: `diff <(git show HEAD:Makefile) Makefile` MUST show zero changes. This is the most critical check.
- **T086**: Run frontend regression: `cd frontend && npm run build && npm run test` — all tests must pass (53/53 from spec-18 baseline).
- **T087**: Run backend regression: `zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/` — zero new failures vs 39 pre-existing baseline. **IMPORTANT**: NEVER run pytest directly — always use the external test runner. Poll with `cat Docs/Tests/spec19-final.status`, read summary with `cat Docs/Tests/spec19-final.summary`.
- **T088**: Verify no new npm/pip packages added: compare `frontend/package.json` and `requirements.txt` against HEAD using `git diff HEAD -- frontend/package.json requirements.txt`.
- **T089**: Create `specs/019-cross-platform-dx/validation-report.md` documenting all 10 SC results with PASS/FAIL status.

## Files to CREATE

| File | Purpose |
|------|---------|
| `specs/019-cross-platform-dx/validation-report.md` | Final validation report with all 10 SC results |

## Files to MODIFY

None — you only validate and create the report.

## Files NEVER to Touch

- `Makefile` — SC-010 (you verify this, not modify it)
- ALL source files — you are a validator, not an implementer
- If you find issues, report them in the validation report with FAIL status — do NOT fix them yourself

## Must-Read Documents (in order)

1. This file (read first)
2. `specs/019-cross-platform-dx/spec.md` — SC-001 through SC-010 (success criteria definitions)
3. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — verification commands, stale patterns
4. `specs/019-cross-platform-dx/tasks.md` — all tasks (to verify completion)
5. All source files being validated (read for verification, not modification)

## Validation Report Template

Create `specs/019-cross-platform-dx/validation-report.md` with this structure:

```markdown
# Spec-019 Cross-Platform DX — Validation Report

**Date**: 2026-03-19
**Validator**: A7 (Quality Engineer)
**Branch**: 019-cross-platform-dx

## Success Criteria Results

| SC | Description | Status | Evidence |
|----|-------------|--------|----------|
| SC-001 | Docker compose configs valid, 4 services | PASS/FAIL | (command output) |
| SC-002 | embedinator.ps1 syntax valid | PASS/FAIL | (command output) |
| SC-003 | GPU detection: NVIDIA=nvidia, macOS=none | PASS/FAIL | (code trace) |
| SC-004 | Port interpolation: 4000→4000:3000 | PASS/FAIL | (command output) |
| SC-005 | rewrites() in config, empty API_BASE | PASS/FAIL | (grep output) |
| SC-006 | Health Ollama probe includes models dict | PASS/FAIL | (code trace) |
| SC-007 | BackendStatusProvider+StatusBanner+gating | PASS/FAIL | (grep output) |
| SC-008 | Fernet key via Docker (no host Python) | PASS/FAIL | (code trace) |
| SC-009 | Health polling 300s/60s timeouts | PASS/FAIL | (code trace) |
| SC-010 | Makefile zero diff | PASS/FAIL | (diff output) |

## Regression Tests

### Frontend
- Build: PASS/FAIL
- Tests: X/53 passing

### Backend
- Status: PASS/FAIL
- New failures: X (vs 39 baseline)

## Package Verification
- `frontend/package.json`: No changes / Changes detected
- `requirements.txt`: No changes / Changes detected

## Overall Status: PASS / FAIL (X/10 SCs passing)
```

## Key Gotchas

1. **NEVER run pytest directly** — Use `zsh scripts/run-tests-external.sh -n spec19-final --no-cov tests/`. Poll status with `cat Docs/Tests/spec19-final.status`. Read summary with `cat Docs/Tests/spec19-final.summary`.
2. **Backend test baseline** — 39 pre-existing failures. The gate check is "zero NEW failures", not "zero total failures". Compare the failure count against this baseline.
3. **SC-010 is the most critical check** — If the Makefile was modified by any agent, this is a blocking failure. Run `diff <(git show HEAD:Makefile) Makefile` and verify zero output.
4. **Code trace for SC-003, SC-006, SC-008, SC-009** — Some SCs cannot be validated by running commands (they test runtime behavior). For these, read the source code and trace the logic paths. Document your findings in the evidence column.
5. **SC-002 PowerShell** — If `pwsh` is not installed on the system, do a manual code review of `embedinator.ps1` structure and note that runtime validation requires PowerShell.

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
