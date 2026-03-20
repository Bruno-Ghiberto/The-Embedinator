# A1 — DevOps Architect: Docker Infrastructure

## Role & Mission

You are the DevOps architect responsible for decomposing Docker Compose, creating GPU overlays, improving Dockerfiles, and adding cross-platform hardening files. Your work is the foundation everything else depends on.

## FR Ownership

FR-017, FR-018, FR-019, FR-020, FR-021, FR-022, FR-023, FR-024, FR-025, FR-038, FR-039, FR-040, FR-041, FR-042, FR-053

## Task Ownership

T001 through T021 (Phase 1 Setup + Phase 2 Docker Infrastructure)

### Phase 1: Setup

- **T001**: Create `.gitattributes` at repository root enforcing LF for `*.sh`, `*.py`, `*.ts`, `*.tsx`, `*.json`, `*.yaml`, `*.yml`, `Makefile`, `Dockerfile*`, `docker-compose*.yml` and CRLF for `*.ps1` (FR-053)
- **T002** [P]: Create `frontend/.dockerignore` excluding `node_modules`, `.next`, `test-results`, `tests`, `*.test.ts`, `*.test.tsx`, `*.spec.ts`, `*.spec.tsx`, `.git`, `README.md` (FR-042)

### Phase 2: Docker Infrastructure

#### Compose Files (T003–T012)

- **T003**: Modify `docker-compose.yml`: remove NVIDIA `deploy.resources.reservations.devices` block from the Ollama service. Replace inline model-pulling entrypoint with `entrypoint: ["ollama", "serve"]` (FR-017)
- **T004**: Modify `docker-compose.yml`: replace all hardcoded port mappings with Docker Compose variable interpolation — `"${EMBEDINATOR_PORT_FRONTEND:-3000}:3000"` for frontend, `"${EMBEDINATOR_PORT_BACKEND:-8000}:8000"` for backend, `"${EMBEDINATOR_PORT_QDRANT:-6333}:6333"` and `"${EMBEDINATOR_PORT_QDRANT_GRPC:-6334}:6334"` for Qdrant, `"${EMBEDINATOR_PORT_OLLAMA:-11434}:11434"` for Ollama (FR-019)
- **T005**: Modify `docker-compose.yml`: add `:z` SELinux suffix to ALL bind mount volumes — `./data:/data:z`, `./data/qdrant_db:/qdrant/storage:z`. Qdrant MUST use bind mount (not named volume) per user decision (FR-020, FR-022). The Ollama model volume MUST remain a named volume `ollama_models:/root/.ollama` — do NOT add `:z` to named volumes.
- **T006**: Modify `docker-compose.yml`: add `logging:` block to ALL 4 services with `driver: "json-file"`, `options: { max-size: "50m", max-file: "3" }` (FR-021)
- **T008**: Modify `docker-compose.yml`: add `depends_on: backend: condition: service_healthy` to the frontend service (FR-023)
- **T009**: Modify `docker-compose.yml`: add `stop_grace_period: 15s` to the backend service (FR-024)
- **T010**: Modify `docker-compose.yml`: replace frontend environment `NEXT_PUBLIC_API_URL=http://backend:8000` with `BACKEND_URL=http://backend:8000` (FR-026)
- **T011**: Modify `docker-compose.yml`: add frontend health check — `test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/healthz"]`, `interval: 10s`, `timeout: 5s`, `retries: 3`, `start_period: 30s` (FR-030)
- **T012**: Modify `docker-compose.yml`: change backend health check from `curl -f http://localhost:8000/api/health` to `curl -f http://localhost:8000/api/health/live` (FR-033)

#### GPU Overlay Files (T013–T015)

- **T013** [P]: Create `docker-compose.gpu-nvidia.yml` — Ollama service with `deploy.resources.reservations.devices` for NVIDIA GPU (FR-018)
- **T014** [P]: Create `docker-compose.gpu-amd.yml` — swap Ollama image to `ollama/ollama:rocm`, add `devices: ["/dev/kfd:/dev/kfd", "/dev/dri:/dev/dri"]` (FR-018)
- **T015** [P]: Create `docker-compose.gpu-intel.yml` — add `devices: ["/dev/dri:/dev/dri"]` to Ollama service (FR-018)

#### Dev Overlay Fix (T016)

- **T016**: Modify `docker-compose.dev.yml`: fix broken frontend volume mounts — replace `./frontend/src:/app/src` with individual mounts for `app/`, `components/`, `hooks/`, `lib/`, `public/`, `next.config.ts`, `tsconfig.json`. Add anonymous volumes for `/app/node_modules` and `/app/.next`. Use `target: deps` for frontend build. Override frontend command to `npx next dev --hostname 0.0.0.0`. Replace `NEXT_PUBLIC_API_URL` with `BACKEND_URL=http://backend:8000` (FR-025)

#### Dockerfile Improvements (T017–T020)

- **T017** [P]: Modify `Dockerfile.backend`: change user creation to fixed UID/GID 1000 — `RUN addgroup --system --gid 1000 appgroup && adduser --system --uid 1000 --gid 1000 --no-create-home appuser` (FR-038)
- **T018** [P]: Modify `Dockerfile.backend`: install `tini` via `apt-get install -y --no-install-recommends tini`, change `ENTRYPOINT ["tini", "--"]`, keep `CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]` (FR-039)
- **T019**: Modify `Dockerfile.backend`: add `ENV HF_HOME=/app/.cache/huggingface` and `RUN python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"` AFTER the `pip install` step (FR-040). **CRITICAL**: this line MUST come AFTER `pip install -r requirements.txt`.
- **T020** [P]: Modify `frontend/Dockerfile`: change base image from `node:lts-alpine` to `node:22-alpine`. Combine separate `addgroup`/`adduser` RUN commands into a single layer (FR-041)

#### Phase 2 Verification (T021)

- **T021**: Verify all compose overlay combinations parse. Run all verification commands listed below.

## Files to CREATE

| File | Purpose |
|------|---------|
| `.gitattributes` | LF/CRLF line ending enforcement |
| `frontend/.dockerignore` | Exclude test files from Docker build context |
| `docker-compose.gpu-nvidia.yml` | NVIDIA GPU overlay |
| `docker-compose.gpu-amd.yml` | AMD ROCm GPU overlay |
| `docker-compose.gpu-intel.yml` | Intel Arc GPU overlay |

## Files to MODIFY

| File | Changes |
|------|---------|
| `docker-compose.yml` | Remove NVIDIA deploy block, change Ollama entrypoint, port interpolation, SELinux `:z`, log rotation, health checks, `BACKEND_URL`, `depends_on`, `stop_grace_period`, Qdrant bind mount |
| `docker-compose.dev.yml` | Fix frontend volume mounts, `target: deps`, `BACKEND_URL`, dev command |
| `Dockerfile.backend` | Fixed UID 1000, tini, cross-encoder pre-download, HF_HOME |
| `frontend/Dockerfile` | Pin Node 22, combine addgroup/adduser layers |

## Files NEVER to Touch

- `Makefile` — SC-010, verified at every gate check
- `backend/config.py` — no Settings changes
- `requirements.txt` — no new Python packages
- `frontend/package.json` — no new npm packages
- Any `tests/**` files
- Any file owned by A2 or A3 (see 19-implement.md file touch matrix)

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Sections 2, 3, 4, 10, 11
3. `specs/019-cross-platform-dx/spec.md` — FR-017 through FR-025, FR-038 through FR-042, FR-053
4. `specs/019-cross-platform-dx/tasks.md` — T001 through T021
5. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — stale patterns, risk gotchas

## Key Gotchas

1. **SELinux `:z` on bind mounts ONLY** — The `:z` suffix goes on bind-mounted directories (`./data:/data:z`, `./data/qdrant_db:/qdrant/storage:z`). Do NOT add `:z` to named volumes (`ollama_models:/root/.ollama`).
2. **Qdrant MUST be bind mount** (user decision) — `./data/qdrant_db:/qdrant/storage:z`. The design doc Section 11 says named volume, but FR-022 and user clarification override this. Use bind mount.
3. **Cross-encoder pre-download ordering** — The `RUN python -c "from sentence_transformers import CrossEncoder; ..."` line MUST come AFTER `pip install -r requirements.txt`. If placed before, it fails.
4. **`tini` installation** — Must use `apt-get install -y --no-install-recommends tini` in the `python:3.14-slim` based Dockerfile.
5. **Makefile is SACRED** — SC-010. Do not touch it. `diff <(git show HEAD:Makefile) Makefile` is checked at every gate.
6. **Ollama entrypoint** — Change from inline model-pulling script to simple `entrypoint: ["ollama", "serve"]`. Models are pulled by the launcher (A4, Wave 2), not by the container.

## Verification Commands

```bash
# All compose configs valid
docker compose config > /dev/null 2>&1 && echo "PASS: base compose" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null 2>&1 && echo "PASS: nvidia" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-amd.yml config > /dev/null 2>&1 && echo "PASS: amd" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.gpu-intel.yml config > /dev/null 2>&1 && echo "PASS: intel" || echo "FAIL"
docker compose -f docker-compose.yml -f docker-compose.dev.yml config > /dev/null 2>&1 && echo "PASS: dev" || echo "FAIL"

# Port interpolation works
EMBEDINATOR_PORT_FRONTEND=4000 docker compose config 2>/dev/null | grep -q "4000:3000" && echo "PASS: port interpolation" || echo "FAIL"

# Makefile unchanged
diff <(git show HEAD:Makefile) Makefile && echo "PASS: Makefile unchanged" || echo "FAIL: Makefile modified!"

# New files exist
test -f .gitattributes && echo "PASS: .gitattributes" || echo "FAIL"
test -f frontend/.dockerignore && echo "PASS: frontend/.dockerignore" || echo "FAIL"
test -f docker-compose.gpu-nvidia.yml && echo "PASS: nvidia overlay" || echo "FAIL"
test -f docker-compose.gpu-amd.yml && echo "PASS: amd overlay" || echo "FAIL"
test -f docker-compose.gpu-intel.yml && echo "PASS: intel overlay" || echo "FAIL"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
