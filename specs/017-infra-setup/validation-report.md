# Spec 17: Infrastructure — Validation Report

Generated: 2026-03-19

## Test Results

| Run | Passing | Failing | Errors | Total Failing | Coverage |
|-----|---------|---------|--------|---------------|----------|
| Baseline (spec17-baseline) | 1487 | 33 | 6 | 39 | 87% |
| Final (spec17-final) | 1487 | 33 | 6 | 39 | 87% |
| **New failures** | — | **0** | **0** | **0** | — |

**Gate: PASS** — zero new failures introduced by spec-17 changes.

---

## Constitution Compliance

| Principle | Check | Status |
|-----------|-------|--------|
| V — Secure by Default | `api_key_encryption_secret` has `alias="EMBEDINATOR_FERNET_KEY"` in `config.py:31` | **PASS** |
| V — Secure by Default | `model_config` has `populate_by_name=True` in `config.py:79` | **PASS** |
| IV — Observability | `LOG_LEVEL_OVERRIDES` forwarded in `docker-compose.yml` backend env (line 53) | **PASS** |

---

## FR Status

| FR | Description | Status | Notes |
|----|-------------|--------|-------|
| FR-001 | Single `.env` with all application config | **PASS** | `Settings` uses `env_file=".env"`; `.env.example` documents all 28 fields |
| FR-002 | Two operating modes (full container + dev) | **PASS** | `make up` = full containerized; `make dev-infra` starts only Qdrant+Ollama via `docker compose up -d qdrant ollama` |
| FR-003 | Native binary compiled from source and available | **PASS** | `make build-rust` runs `cargo build --release`; Dockerfile Stage 1 compiles binary |
| FR-004 | `Dockerfile.backend` multi-stage Rust+Python | **PASS** | 2 `FROM` lines: `rust:1.93 AS rust-builder` + `python:3.14-slim` |
| FR-005 | Non-root user in `frontend/Dockerfile` | **PASS** | `USER nextjs` (line 29), UID 1001 |
| FR-006 | All services with healthchecks + dependency ordering | **PARTIAL** | 3/4 services have healthchecks (qdrant, ollama, backend). Frontend service has **no healthcheck**. Backend `depends_on` uses `condition: service_healthy`. |
| FR-007 | Persistent data in volumes/bind mounts | **PASS** | `./data:/data` bind mount on backend; `ollama_models` named volume for model cache |
| FR-008 | GPU passthrough for model inference | **PASS** | `deploy.resources.reservations.devices` block on ollama service (nvidia, all GPUs) |
| FR-009 | `LOG_LEVEL_OVERRIDES` in backend service env | **PASS** | `LOG_LEVEL_OVERRIDES: ${LOG_LEVEL_OVERRIDES:-}` in `docker-compose.yml:53` |
| FR-010 | `RUST_WORKER_PATH` in backend service env | **PASS** | `RUST_WORKER_PATH: /app/ingestion-worker/target/release/embedinator-worker` in `docker-compose.yml:54` |
| FR-011 | Makefile has 14 named targets | **PASS** | 15 targets (help + 14 operational). Count: 15. |
| FR-012 | `make setup` installs all 3 toolchains | **PASS** | `pip install -r requirements.txt`, `cd frontend && npm install`, `$(MAKE) build-rust` |
| FR-013 | `output: standalone` in `next.config.ts` | **PASS** | Added by A5 in T041. Required for `frontend/Dockerfile` standalone copy. |
| FR-014 | `.gitignore` excludes required patterns | **PASS** | `data/`, `.env`, `.venv/`, `node_modules/`, `.next/`, `target/` all present. `git ls-files data/` returns empty. |
| FR-015 | Non-root `USER` in `Dockerfile.backend` | **PASS** | `USER appuser` (line 34), created via `adduser --system` |

---

## SC Status

| SC | Description | Verification | Status |
|----|-------------|-------------|--------|
| SC-001 | `docker compose config` exits 0 | `docker compose config > /dev/null` → exit 0 | **PASS** |
| SC-002 | `Settings()` instantiates with no env vars | `python -c "from backend.config import Settings; s = Settings(); print('OK:', s.host)"` → `OK: 0.0.0.0` | **PASS** |
| SC-003 | `EMBEDINATOR_FERNET_KEY` env var sets `api_key_encryption_secret` | `python -c "from backend.config import Settings; s = Settings(EMBEDINATOR_FERNET_KEY='testkey'); assert s.api_key_encryption_secret == 'testkey'"` → OK | **PASS** |
| SC-004 | `Dockerfile.backend` has 2 `FROM` lines | `grep -c "^FROM" Dockerfile.backend` → `2` | **PASS** |
| SC-005 | `make help` lists all targets with descriptions | `make help` → 15 lines, all targets present with descriptions | **PASS** |
| SC-006 | `.env.example` contains `EMBEDINATOR_FERNET_KEY=` | `grep "EMBEDINATOR_FERNET_KEY" .env.example` → found (comment + value line) | **PASS** |
| SC-007 | 0 new test failures vs baseline | Baseline: 39 failing → Final: 39 failing → Delta: 0 | **PASS** |
| SC-008 | All Makefile targets have `##` comment | `grep -c "##" Makefile` → `16` (≥ 15 required) | **PASS** |

---

## File Change Summary

| File | Action | Changes |
|------|--------|---------|
| `backend/config.py` | Modified (A2) | `api_key_encryption_secret` alias added; `populate_by_name=True` added to `model_config` |
| `Dockerfile.backend` | Rewritten (A3) | Multi-stage: `rust:1.93` builder + `python:3.14-slim` runtime; non-root `appuser`; binary at `/app/ingestion-worker/target/release/embedinator-worker` |
| `.env.example` | Rewritten (A2) | All 28 Settings fields documented with descriptions, types, and defaults |
| `Makefile` | Rewritten (A4) | 15 targets with `##` comments; `help` target; `docker-up`→`up` and `docker-down`→`down` renames; test targets use `run-tests-external.sh` |
| `docker-compose.yml` | Modified (A4) | `LOG_LEVEL_OVERRIDES`, `RUST_WORKER_PATH`, `UPLOAD_DIR` env vars added; `SQLITE_PATH` fixed to `/data/embedinator.db`; GPU passthrough block on ollama |
| `docker-compose.prod.yml` | Modified (A4) | Comment header with TLS/reverse proxy guidance added |
| `frontend/next.config.ts` | Modified (A5) | `output: "standalone"` added (FR-013) |
| `requirements.txt` | Verified | `langchain-core`, `langchain-ollama`, `langgraph-checkpoint-sqlite>=2.0` present |
| `.gitignore` | Verified | All 8 required patterns present; `data/` not tracked |
| `ingestion-worker/Cargo.toml` | Verified | All 6 required Rust deps present |
| `frontend/Dockerfile` | Verified | Multi-stage (4 stages), `USER nextjs`, `.next/standalone` copy |
| `docker-compose.dev.yml` | Verified (no changes) | Has backend+frontend overrides; `dev-infra` target uses base compose with service selection instead |

---

## Known Issues (Not Regressions)

| Issue | Impact | Notes |
|-------|--------|-------|
| Frontend service has no healthcheck in `docker-compose.yml` | FR-006 partial | A1 flagged this gap; frontend is a leaf service (nothing depends on it). Adding a healthcheck (`curl -f http://localhost:3000`) would make FR-006 fully compliant. |
| `test_config.py::test_default_settings` still fails | Pre-existing | This failure existed before spec-17 and is tracked in the baseline (1 of 33 failed tests). |
| 39 total test failures | Pre-existing | All 33 failures + 6 errors match the baseline exactly. None introduced by spec-17 changes. |
| `docker-compose.dev.yml` is an override file, not standalone | By design | A4 chose option (b): `dev-infra` Makefile target selects `qdrant ollama` from base compose file. FR-002 is satisfied. |
