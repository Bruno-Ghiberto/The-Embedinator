# A1 — Wave 1 — devops-architect (Sonnet)

## Role

You are the Wave 1 devops-architect. You run alone before any other agent. Your job is to establish the test baseline, conduct a thorough gap audit of all infrastructure files against FR-001–FR-015, document findings, and produce A2–A5 instruction files. Wave 2 does not start until you signal completion.

## Read First

1. `specs/017-infra-setup/tasks.md` — canonical task list (T001–T044)
2. `specs/017-infra-setup/plan.md` — wave structure, Constitution check
3. `specs/017-infra-setup/spec.md` — FR-001–FR-015, SC-001–SC-008
4. `specs/017-infra-setup/research.md` — audit gap findings
5. `Docs/PROMPTS/spec-17-infra/17-implement.md` — authoritative code specs

Do not begin any task until you have read all five files.

## Assigned Tasks

T001–T007.

## T001 — Run Baseline Test Suite

```
zsh scripts/run-tests-external.sh -n spec17-baseline --no-cov tests/
```

Poll `cat Docs/Tests/spec17-baseline.status` until the value is `done` or `error`.

Then read `cat Docs/Tests/spec17-baseline.summary`.

Record BOTH values:
- BASELINE_PASSING = total passing tests
- BASELINE_FAILING = total failing tests

These exact numbers are the gate for T043 (Wave 4). Write them into a comment at the top of `specs/017-infra-setup/validation-report.md` now so subsequent waves can reference them. Create the file if it does not exist.

If status is `error`, read `Docs/Tests/spec17-baseline.log` to diagnose, but do not abort — record the error state and proceed with the audit. The gate applies only to status == `done`.

## T002 — Audit `backend/config.py`

Read the file. Check each of the following:

| Check | Expected | Action if wrong |
|-------|----------|-----------------|
| `api_key_encryption_secret` field | Has `Field(default="", alias="EMBEDINATOR_FERNET_KEY")` | Flag as GAP (A2 will fix) |
| `model_config` | Includes `populate_by_name=True` | Flag as GAP (A2 will fix) |
| `confidence_threshold` | `int = 60` | Flag as GAP if `float = 0.6` |
| `default_llm_model` | `"qwen2.5:7b"` | Flag as GAP if `"llama3.2"` |
| `log_level_overrides` | Present with `alias="LOG_LEVEL_OVERRIDES"` | Flag as GAP if absent |
| `frontend_port` | Present, `int = 3000` | Flag as GAP if absent |
| `meta_relevance_threshold` | Present, `float = 0.2` | Flag as GAP if absent |
| `meta_variance_threshold` | Present, `float = 0.15` | Flag as GAP if absent |
| `rate_limit_provider_keys_per_minute` | Present, `int = 5` | Flag as GAP if absent |
| `rate_limit_general_per_minute` | Present, `int = 120` | Flag as GAP if `rate_limit_default_per_minute` |

## T003 — Audit `Dockerfile.backend`

Read the file. Check:

| Check | Expected | Action if wrong |
|-------|----------|-----------------|
| Stage count | 2 `FROM` lines | Flag as GAP (A3 will fix) |
| Rust stage base image | `FROM rust:1.93` | Flag as GAP |
| Python stage base image | `FROM python:3.14-slim` | Flag as GAP |
| Non-root user | `USER appuser` before `CMD` | Flag as GAP |
| Binary destination | `/app/ingestion-worker/target/release/embedinator-worker` | Flag as GAP if wrong path |

Also read `frontend/Dockerfile` and confirm `USER nextjs` is present. Record as VERIFIED (no change needed).

## T004 — Audit `Makefile`

Read the file. For each of the 14 required targets, record PRESENT or MISSING:

Required: `help`, `setup`, `build-rust`, `dev-infra`, `dev-backend`, `dev-frontend`, `dev`, `up`, `down`, `pull-models`, `test`, `test-cov`, `test-frontend`, `clean`, `clean-all`

Also check that each present target has a `## Short description` comment (SC-008).

Note: `docker-up` and `docker-down` exist in the current file but are not in the required set. A4 will rename them.

## T005 — Audit `docker-compose.yml`

Read the file. Check the backend service `environment` block for:

| Variable | Expected |
|----------|---------|
| `QDRANT_HOST` | `qdrant` |
| `OLLAMA_BASE_URL` | `http://ollama:11434` |
| `SQLITE_PATH` | `/data/embedinator.db` |
| `UPLOAD_DIR` | `/data/uploads` |
| `LOG_LEVEL_OVERRIDES` | `${LOG_LEVEL_OVERRIDES:-}` |
| `RUST_WORKER_PATH` | `/app/ingestion-worker/target/release/embedinator-worker` |

Also confirm the Ollama service has a `deploy.resources.reservations.devices` GPU passthrough block (FR-008).

Read `docker-compose.dev.yml` and confirm it has exactly 2 services.

Read `docker-compose.prod.yml` (if it exists) and note whether it has a comment header explaining it is a production override.

## T006 — Audit `.env.example`, `requirements.txt`, `.gitignore`, `ingestion-worker/Cargo.toml`

`.env.example`:
- Must contain `EMBEDINATOR_FERNET_KEY=` (not `API_KEY_ENCRYPTION_SECRET=`)
- Must contain `CONFIDENCE_THRESHOLD=60` (not `0.6`)
- Must contain `DEFAULT_LLM_MODEL=qwen2.5:7b` (not `llama3.2`)
- Must contain `RATE_LIMIT_GENERAL_PER_MINUTE=120` (not `RATE_LIMIT_DEFAULT_PER_MINUTE=120`)
- Must document all 28 Settings fields

`requirements.txt`:
- Must have `langchain-core` (not `langchain`)
- Must have `langchain-ollama` (not `langchain-community`)
- Must have `langgraph-checkpoint-sqlite>=2.0`

`.gitignore`:
- Must include: `data/`, `.env`, `.venv/`, `node_modules/`, `.next/`, `target/`, `__pycache__/`, `*.pyc`

`ingestion-worker/Cargo.toml`:
- Must list: `serde`, `serde_json`, `pulldown-cmark`, `pdf-extract`, `clap`, `regex`

## T007 — Write A2–A5 Instruction Files and Signal Gate

Create the directory `Docs/PROMPTS/spec-17-infra/agents/` if it does not already exist.

Write files:
- `A2-instructions.md` — python-expert, Wave 2, config.py + .env.example
- `A3-instructions.md` — python-expert, Wave 2, Dockerfile.backend
- `A4-instructions.md` — backend-architect, Wave 3, Makefile + compose + requirements
- `A5-instructions.md` — quality-engineer, Wave 4, polish + validation

After writing, notify the orchestrator: "Wave 1 complete. Baseline: BASELINE_PASSING passing, BASELINE_FAILING failing. Gaps found: [list]. A2–A5 instruction files written. Wave 2 may proceed."

---

## Critical Pre-existing Facts

- `frontend/Dockerfile` is ALREADY compliant — `USER nextjs` present, multi-stage build. Do not flag as a gap. Do not assign A3 to touch it.
- `docker-compose.prod.yml` is a 2-service production override (backend + frontend only). It is NOT a 5th service definition. A4 will add a comment header to it, nothing else.
- `docker-compose.dev.yml` already has exactly 2 services (Qdrant + Ollama). Verify only.
- The current `backend/config.py` already has `from pydantic import Field` on line 3 — A2 does not need to add this import, only fix the field definition.
- The current `confidence_threshold` in config.py is already `int = 60` — verify but no change needed for this field.
- The current `default_llm_model` in config.py is already `"qwen2.5:7b"` — verify but no change needed for this field.
- `requirements-dev.txt` does NOT exist in the repository. Do not reference it. Dev dependencies are in `requirements.txt`.

## Critical Gotchas

- NEVER run pytest directly. Always use `zsh scripts/run-tests-external.sh -n <name> <target>`.
- Do not run `docker compose build` or any Docker command. Audit is read-only until the relevant wave agent acts.
- Record baseline numbers precisely — they are the gate for the final validation in Wave 4.
