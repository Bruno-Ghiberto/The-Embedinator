# A4 — Wave 3 — backend-architect (Sonnet)

## Role

You are the Wave 3 backend-architect. You run after both Wave 2 agents (A2 and A3) complete. Do not start until the orchestrator signals that Wave 2 gates passed.

You own foundational file verification, the Makefile rebuild, and docker-compose.yml environment overrides. Your task set is the largest in this spec.

## Read First

1. `specs/017-infra-setup/tasks.md` — canonical task list (T008–T018, T022–T029, T036–T039)
2. `Docs/PROMPTS/spec-17-infra/17-implement.md` — authoritative code specs (Makefile, docker-compose.yml sections)

## Assigned Tasks

T008–T018, T022–T029, T036–T039.

---

## T008 — Verify `requirements.txt`

Read the file. Confirm these package names:

| Correct | Wrong (stale) |
|---------|--------------|
| `langchain-core>=1.2.10` | `langchain>=1.2.10` |
| `langchain-ollama>=0.3` | `langchain-community>=1.2` |
| `langgraph-checkpoint-sqlite>=2.0` | (absent) |

If any corrections are needed, make them. If `langchain` or `langchain-community` appear as standalone entries (not part of a larger package name), replace them.

`langchain-openai`, `langchain-anthropic`, and `langgraph` should already be present and correct — verify but do not change.

## T009 — Verify `.gitignore`

Read the file. Confirm ALL of these patterns are present:

```
data/
.env
.venv/
node_modules/
.next/
target/
__pycache__/
*.pyc
```

If any are missing, add them in the appropriate section. Do not remove existing entries.

## T010 — Verify `ingestion-worker/Cargo.toml`

Read the file. Confirm all of these dependencies appear in `[dependencies]`:

```
serde
serde_json
pulldown-cmark
pdf-extract
clap
regex
```

If any are absent, this is a gap to document but do not modify the Cargo.toml — flag it for the orchestrator. Cargo.toml changes require a Rust build to validate.

## T011–T013 — Add Makefile targets: `setup`, `build-rust`, `pull-models`

Read the current Makefile. These targets may be absent or have wrong implementations.

Required implementations:

```makefile
setup:  ## Install all dependencies (Python pip, Node npm, Rust binary)
	pip install -r requirements.txt
	cd frontend && npm install
	$(MAKE) build-rust

build-rust:  ## Compile the Rust ingestion worker binary
	cd ingestion-worker && cargo build --release

pull-models:  ## Pull default Ollama models (qwen2.5:7b + nomic-embed-text)
	docker exec $$(docker compose ps -q ollama) ollama pull qwen2.5:7b
	docker exec $$(docker compose ps -q ollama) ollama pull nomic-embed-text
```

Note: `pull-models` uses `qwen2.5:7b`, not `llama3.2`. If the current file has `llama3.2`, correct it.
Note: `setup` installs from `requirements.txt` directly (no virtualenv activation) — `requirements-dev.txt` does NOT exist.

## T014–T017 — Add Makefile targets: `dev-infra`, `dev-backend`, `dev-frontend`, `dev`

```makefile
dev-infra:  ## Start Qdrant + Ollama in Docker (infrastructure only, for dev mode)
	docker compose -f docker-compose.dev.yml up -d

dev-backend:  ## Start Python backend with hot reload (uvicorn --reload)
	uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:  ## Start Next.js frontend with hot reload (next dev)
	cd frontend && npm run dev

dev: dev-infra  ## Start dev-infra then print instructions for backend + frontend
	@echo "Run in separate terminals: make dev-backend  /  make dev-frontend"
```

Note: the existing `dev` target in the current Makefile does something different (uses docker compose with two override files). Replace it entirely with the implementation above.

## T018 — Verify `docker-compose.dev.yml`

Read the file. **WARNING from A1 audit**: the current file has 2 services (`backend` + `frontend` overrides), NOT `qdrant` + `ollama`. This is a compose override file used for dev-mode hot reload, not a standalone dev infrastructure file.

The `dev-infra` target (T014) uses `docker compose -f docker-compose.dev.yml up -d` — but this file does not contain qdrant/ollama service definitions.

**Action**: Either (a) rewrite `docker-compose.dev.yml` to contain only Qdrant + Ollama standalone services for dev-infra mode, or (b) change the `dev-infra` target to filter services from the base compose file (e.g., `docker compose up -d qdrant ollama`). Option (b) is simpler and preserves the existing dev overlay.

If choosing option (b), update T014's `dev-infra` target to:
```makefile
dev-infra:  ## Start Qdrant + Ollama in Docker (infrastructure only, for dev mode)
	docker compose up -d qdrant ollama
```

Record your decision and the rationale.

## T022 — Verify/Add GPU Passthrough Block in `docker-compose.yml`

Read `docker-compose.yml`. In the `ollama` service, confirm this block exists:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

If it is absent, add it. If it is present, record: "GPU passthrough: VERIFIED."

## T023–T025 — Verify Healthchecks, Restart Policies, Named Volumes

Read `docker-compose.yml`. Confirm:

T023 — Healthchecks:
- `qdrant` service: `healthcheck.test` references `http://localhost:6333/healthz`
- `ollama` service: `healthcheck.test` references `http://localhost:11434/`
- `backend` service: `healthcheck.test` references `http://localhost:8000/api/health`

T024 — Restart policies:
- `qdrant`, `ollama`, `backend`, `frontend` all have `restart: unless-stopped`

T025 — Named volumes:
- `ollama_models` appears in the top-level `volumes:` block
- `ollama` service mounts it at `/root/.ollama`

Record findings. If any are missing, add them.

## T026 — Add/Verify Backend Service Environment Overrides

Read the `backend` service `environment` block in `docker-compose.yml`. It must contain all 6 of these entries:

```yaml
environment:
  QDRANT_HOST: qdrant
  OLLAMA_BASE_URL: http://ollama:11434
  SQLITE_PATH: /data/embedinator.db
  UPLOAD_DIR: /data/uploads
  LOG_LEVEL_OVERRIDES: ${LOG_LEVEL_OVERRIDES:-}
  RUST_WORKER_PATH: /app/ingestion-worker/target/release/embedinator-worker
```

The two new entries that are likely absent are `LOG_LEVEL_OVERRIDES` and `RUST_WORKER_PATH`. Add them if missing. Do not remove existing entries.

The `${LOG_LEVEL_OVERRIDES:-}` syntax passes the host env var through with an empty-string fallback — this is the correct Docker Compose variable substitution form.

## T027 — Rename `docker-up` to `up` in Makefile

The current Makefile has `docker-up`. The required target name is `up` (FR-011).

Replace the target definition:

Current:
```makefile
docker-up:
	docker compose up -d
```

Replace with:
```makefile
up:  ## Build and start all 4 production Docker services
	docker compose up --build -d
```

Update the `.PHONY` line to remove `docker-up` and add `up`.

## T028 — Rename `docker-down` to `down` in Makefile

The current Makefile has `docker-down`. The required target name is `down` (FR-011).

Replace:

Current:
```makefile
docker-down:
	docker compose down
```

Replace with:
```makefile
down:  ## Stop all Docker services
	docker compose down
```

Update the `.PHONY` line to remove `docker-down` and add `down`.

## T029 — Add Comment Header to `docker-compose.prod.yml`

Read `docker-compose.prod.yml`. Add a comment header at the top of the file if one is not present:

```yaml
# docker-compose.prod.yml — Production deployment override.
# Use with: docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
# Overrides: backend + frontend services only (no Qdrant/Ollama — use managed services in prod).
```

Make no other changes to this file.

## T036 — Add `test-cov` Target to Makefile

The `test-cov` target must delegate to `run-tests-external.sh` (never call pytest directly):

```makefile
test-cov:  ## Run backend tests with >=80% coverage gate (exits non-zero if below threshold)
	zsh scripts/run-tests-external.sh -n make-test-cov tests/
```

If a `test-cov` target already exists and calls pytest directly, replace it with the above.

## T037 — Verify/Add `test-frontend` Target

```makefile
test-frontend:  ## Run frontend tests (vitest)
	cd frontend && npm run test
```

If already present, verify the implementation matches. If absent, add it.

## T038 — Verify `clean` Target

Read the current `clean` target. The required implementation removes the `data/` directory:

```makefile
clean:  ## Remove runtime data (data/ directory contents)
	rm -rf data/
```

If the current `clean` target removes only specific files or subdirectories (e.g. `data/uploads/*` or `__pycache__` only), replace it with the simpler `rm -rf data/` version. The spec requires removing all runtime data, not just partial cleanup.

## T039 — Add `clean-all` Target

```makefile
clean-all: down  ## Full teardown: stop containers, remove volumes and build outputs
	docker compose down -v
	rm -rf data/ ingestion-worker/target/ frontend/.next/
```

If absent, add it. `clean-all` depends on `down` and runs `docker compose down -v` to remove named volumes.

## Makefile `.PHONY` Line

After all Makefile changes, ensure the `.PHONY` declaration at the top lists exactly these 15 names (14 required + `help`):

```makefile
.PHONY: help setup build-rust dev-infra dev-backend dev-frontend dev up down pull-models test test-cov test-frontend clean clean-all
```

Remove stale names (`docker-up`, `docker-down`, `build`, `test-unit`, `test-integration`, `lint`, `format`, `docker-clean`, `logs`, `logs-backend`, `logs-frontend`) from `.PHONY`. Removing from `.PHONY` does not remove the target body — you only need to remove it from the `.PHONY` declaration line.

The `test` target must also delegate to `run-tests-external.sh`:

```makefile
test:  ## Run backend tests (no coverage threshold)
	zsh scripts/run-tests-external.sh -n make-test --no-cov tests/
```

If the current `test` target calls pytest directly, replace it.

---

## Reporting

After completing all tasks, report to orchestrator:

"A4 complete. Completed T008–T018, T022–T029, T036–T039.
Makefile: X of 14 targets present (was Y). Renames: docker-up->up, docker-down->down.
docker-compose.yml: LOG_LEVEL_OVERRIDES + RUST_WORKER_PATH added. GPU passthrough: [PRESENT/ADDED].
requirements.txt: [changes made or VERIFIED].
.gitignore: [changes made or VERIFIED].
Wave 4 may proceed."

---

## Critical Gotchas

- NEVER run pytest directly. Makefile `test` and `test-cov` targets must delegate to `run-tests-external.sh`.
- `docker-up` and `docker-down` must be RENAMED, not kept alongside `up` and `down`. Having both would mean more than 14 `.PHONY` targets and would violate FR-011.
- `requirements-dev.txt` does not exist. The `setup` target installs from `requirements.txt` only.
- `pull-models` uses `qwen2.5:7b`, not `llama3.2`.
- All 14 (+ `help`) targets must have `## Short description` comments for SC-008 and for the `help` target to work correctly.
- The `${LOG_LEVEL_OVERRIDES:-}` syntax in docker-compose.yml uses a dash before the empty default — this is standard Compose variable substitution and must be exact.
- `docker-compose.prod.yml` receives only a comment header addition — no service-level changes.
