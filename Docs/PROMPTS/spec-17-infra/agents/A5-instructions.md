# A5 — Wave 4 — quality-engineer (Sonnet)

## Role

You are the Wave 4 quality-engineer. You run after Wave 3 (A4) completes. Do not start until the orchestrator signals that Wave 3 is done.

You own the final polish pass, the test validation run, and the written validation report. You are the last agent to run in this spec.

## Read First

1. `specs/017-infra-setup/tasks.md` — canonical task list (T040–T044)
2. `specs/017-infra-setup/spec.md` — SC-001–SC-008, FR-001–FR-015
3. `Docs/PROMPTS/spec-17-infra/17-implement.md` — authoritative specs for reference
4. `specs/017-infra-setup/validation-report.md` — baseline numbers written by A1 (read this now)

## Assigned Tasks

T040–T044.

---

## T040 — Add `help` Target and Verify ALL `##` Comments (SC-008)

Read the current Makefile.

### Add `help` target if absent

Place it as the first target in the file, immediately after the `.PHONY` line:

```makefile
help:  ## Show all available targets with descriptions
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'
```

Note: the indentation inside `help` uses a TAB character, not spaces. Makefile recipes must be tab-indented.

### Verify `##` comments on all 14 required targets

Each of these targets must have a `## Short description` comment on its definition line:

```
help setup build-rust dev-infra dev-backend dev-frontend dev
up down pull-models test test-cov test-frontend clean clean-all
```

Run `make help` mentally: each target should produce one output line. If any target is missing its `## comment`, add one.

SC-008 acceptance criterion: `grep -c "##" Makefile` returns at least 15 (15 targets with ## comments).

## T041 — Verify `frontend/next.config.ts` Has `output: "standalone"` (FR-013)

Read `frontend/next.config.ts`. Confirm `output: "standalone"` (or `output: 'standalone'`) is present in the Next.js config object.

This is required for the `frontend/Dockerfile` to work — it copies `.next/standalone` in its runner stage.

If absent, add it to the `nextConfig` object. If present, record: "next.config.ts: output: standalone VERIFIED."

## T042 — Verify `data/` is in `.gitignore` and Not Committed

Read `.gitignore`. Confirm `data/` appears as an entry.

Run:
```
git ls-files data/
```

If any files under `data/` are tracked by git, that is a violation. Record the finding. Do not run `git rm` without orchestrator approval — just flag it.

If `data/` is in `.gitignore` and `git ls-files data/` returns nothing, record: "data/ exclusion: VERIFIED."

## T043 — Run Final Test Suite and Compare to Baseline

```
zsh scripts/run-tests-external.sh -n spec17-final tests/
```

Poll `cat Docs/Tests/spec17-final.status` until `done` or `error`.

Read `cat Docs/Tests/spec17-final.summary`.

Record:
- FINAL_PASSING = total passing tests
- FINAL_FAILING = total failing tests
- FINAL_COVERAGE = coverage percentage (if reported)

Compare to baseline from `specs/017-infra-setup/validation-report.md`:
- New failures = FINAL_FAILING - BASELINE_FAILING
- Acceptance criterion: new failures must be 0

A non-zero exit from pytest is expected (39 pre-existing failures exist). The acceptance gate is "0 new failures", not "0 total failures."

If new failures > 0: read `Docs/Tests/spec17-final.log`, identify which tests newly failed, and determine if they are caused by spec-17 changes. Report findings to the orchestrator before writing the validation report.

## T044 — Write `specs/017-infra-setup/validation-report.md`

Write the complete validation report. Use the template below, filling in real values from the test runs and your verification work.

```markdown
# Spec 17: Infrastructure — Validation Report

Generated: 2026-03-19

## Test Results

| Run | Passing | Failing | Coverage |
|-----|---------|---------|---------|
| Baseline (spec17-baseline) | BASELINE_PASSING | BASELINE_FAILING | N/A |
| Final (spec17-final) | FINAL_PASSING | FINAL_FAILING | FINAL_COVERAGE% |
| New failures | — | NEW_FAILING | — |

## Constitution Compliance

| Principle | Check | Status |
|-----------|-------|--------|
| V — Secure by Default | `api_key_encryption_secret` has `alias="EMBEDINATOR_FERNET_KEY"` | PASS / FAIL |
| V — Secure by Default | `model_config` has `populate_by_name=True` | PASS / FAIL |
| IV — Observability | `LOG_LEVEL_OVERRIDES` forwarded in docker-compose.yml backend env | PASS / FAIL |

## FR Status

| FR | Description | Status | Notes |
|----|-------------|--------|-------|
| FR-001 | Single `.env` with all application config | PASS/FAIL | |
| FR-002 | `Settings()` instantiates with no env vars | PASS/FAIL | |
| FR-003 | `EMBEDINATOR_FERNET_KEY` sets `api_key_encryption_secret` | PASS/FAIL | |
| FR-004 | `Dockerfile.backend` multi-stage Rust+Python | PASS/FAIL | |
| FR-005 | Non-root user in `frontend/Dockerfile` | PASS/FAIL | |
| FR-006 | `docker-compose.yml` 4 services with healthchecks | PASS/FAIL | |
| FR-007 | `docker-compose.dev.yml` 2 services only | PASS/FAIL | |
| FR-008 | GPU passthrough block in docker-compose.yml | PASS/FAIL | |
| FR-009 | `LOG_LEVEL_OVERRIDES` in backend service env | PASS/FAIL | |
| FR-010 | `RUST_WORKER_PATH` in backend service env | PASS/FAIL | |
| FR-011 | Makefile has 14 named targets | PASS/FAIL | Count: X |
| FR-012 | `make setup` installs all 3 toolchains | PASS/FAIL | |
| FR-013 | `output: standalone` in next.config.ts | PASS/FAIL | |
| FR-014 | `.gitignore` excludes data/, .env, .venv/, node_modules/, .next/, target/ | PASS/FAIL | |
| FR-015 | Non-root USER in `Dockerfile.backend` | PASS/FAIL | |

## SC Status

| SC | Description | Verification | Status |
|----|-------------|-------------|--------|
| SC-001 | `docker compose config` exits 0 | `docker compose config > /dev/null` | PASS/FAIL/SKIP |
| SC-002 | `Settings()` instantiates with no env vars | Python import check | PASS/FAIL |
| SC-003 | `EMBEDINATOR_FERNET_KEY` env var sets `api_key_encryption_secret` | Python assertion | PASS/FAIL |
| SC-004 | `Dockerfile.backend` has 2 `FROM` lines | `grep -c "^FROM" Dockerfile.backend` == 2 | PASS/FAIL |
| SC-005 | `make help` output lists all 14 targets | `make help` | PASS/FAIL/SKIP |
| SC-006 | `.env.example` contains `EMBEDINATOR_FERNET_KEY=` | grep check | PASS/FAIL |
| SC-007 | 0 new test failures vs baseline | Compare final vs baseline | PASS/FAIL |
| SC-008 | All Makefile targets have `##` comment | `grep -c "##" Makefile` >= 15 | PASS/FAIL |

## File Change Summary

| File | Action | Changes |
|------|--------|---------|
| backend/config.py | Modified | api_key_encryption_secret alias, populate_by_name |
| Dockerfile.backend | Rewritten | Multi-stage Rust+Python, non-root user |
| .env.example | Rewritten | All 28 fields documented, correct key names |
| Makefile | Modified | X targets added/renamed, ## comments, help target |
| docker-compose.yml | Modified | LOG_LEVEL_OVERRIDES + RUST_WORKER_PATH env overrides |
| docker-compose.prod.yml | Modified | Comment header added |
| requirements.txt | Verified/Modified | langchain-core, langchain-ollama, langgraph-checkpoint-sqlite |
| .gitignore | Verified | All required patterns present |
| frontend/Dockerfile | Verified | No changes — USER nextjs already present |
| docker-compose.dev.yml | Verified | No changes — 2 services already correct |
| ingestion-worker/Cargo.toml | Verified | Rust deps present |
```

---

## Verification Commands to Run

Before writing the report, run these checks to confirm SC statuses:

```bash
# SC-002: Settings instantiates cleanly
python -c "from backend.config import Settings; s = Settings(); print('OK:', s.host)"

# SC-003: EMBEDINATOR_FERNET_KEY alias works
python -c "from backend.config import Settings; s = Settings(EMBEDINATOR_FERNET_KEY='testkey'); assert s.api_key_encryption_secret == 'testkey', 'FAIL'; print('OK')"

# SC-004: Dockerfile.backend has exactly 2 FROM lines
grep -c "^FROM" Dockerfile.backend

# SC-006: .env.example contains EMBEDINATOR_FERNET_KEY
grep "EMBEDINATOR_FERNET_KEY" .env.example

# SC-008: Makefile ## comment count
grep -c "##" Makefile
```

Record the actual output of each command in the report.

---

## Critical Gotchas

- NEVER run pytest directly. The final test run in T043 uses `zsh scripts/run-tests-external.sh`.
- The expected final failing count is approximately 39 (pre-existing). A non-zero exit is normal. The gate is new_failures == 0.
- Do not modify any source file in T040–T044 except to add the `help` target and `##` comments to the Makefile, and to fix `output: standalone` in next.config.ts if absent.
- `specs/017-infra-setup/validation-report.md` was partially created by A1 (baseline numbers). Append your full report content, do not discard A1's baseline comment.
- SC-001 (`docker compose config`) and SC-005 (`make help`) may be marked SKIP if Docker is not available in the agent environment — note this explicitly in the report rather than marking as FAIL.
