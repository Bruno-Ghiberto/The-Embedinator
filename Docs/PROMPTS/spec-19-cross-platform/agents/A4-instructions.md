# A4 — DevOps Architect: Launcher Scripts

## Role & Mission

You are the DevOps architect responsible for creating the `embedinator.sh` and `embedinator.ps1` launcher scripts — the single-command entry point that transforms The Embedinator from a multi-command setup into a one-command cross-platform application. This is the largest work item in the spec (19 FRs).

## FR Ownership

FR-001 through FR-016, FR-054, FR-055, FR-056

## Task Ownership

T037 through T060 (Phase 5: Launcher Scripts)

### embedinator.sh (bash/zsh) — T037 through T055

- **T037**: Create `embedinator.sh`: implement CLI argument parsing for all subcommands — `--dev`, `--stop`, `--restart`, `--logs [service]`, `--status`, `--open`, `--help`, `--frontend-port PORT`, `--backend-port PORT` (FR-001, FR-002, FR-003)
- **T038**: Implement `--help` subcommand: print usage with all flags and examples (FR-002)
- **T039**: Implement `--stop` subcommand: run `docker compose down` with the correct `-f` flags for the detected compose files (FR-002)
- **T040**: Implement `--restart` subcommand: stop then fall through to the start flow (FR-002)
- **T041**: Implement `--logs [service]` subcommand: run `docker compose logs -f [service]` (FR-002)
- **T042**: Implement `--status` subcommand: poll health endpoints using configured ports, print per-service status table (FR-002)
- **T043**: Implement preflight checks: (1) Docker daemon via `docker info`, (2) Docker Compose v2 via `docker compose version`, (3) port availability for all configured ports, (4) disk space warning < 15GB, (5) macOS Docker VM memory warning < 4GB, (6) Linux Docker group check (FR-054), (7) WSL2 `/mnt/c/` warning (FR-055), (8) macOS GPU info message (FR-056) (FR-004)
- **T044**: Implement GPU detection: priority order NVIDIA (`nvidia-smi` + `docker info | grep nvidia`) > AMD (`/dev/kfd` + `rocminfo`) > Intel (`/dev/dri/renderD*`) > CPU. `EMBEDINATOR_GPU` env var override. macOS always CPU with info message (FR-005, FR-006, FR-007)
- **T045**: Implement `.env` generation: copy `.env.example` to `.env` if not exists, generate Fernet key via `docker run --rm python:3.14-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`, inject into `.env` (FR-008). NO local Python required.
- **T046**: Implement port override logic: apply CLI `--frontend-port` / `--backend-port` flags to env vars, export for Docker Compose interpolation (FR-003)
- **T047**: Implement CORS auto-detection: detect LAN IP, write `CORS_ORIGINS=http://localhost:{port},http://127.0.0.1:{port},http://{lan_ip}:{port}` to `.env` (FR-009)
- **T048**: Implement data directory creation: `mkdir -p data/uploads data/qdrant_db` before compose up (FR-010)
- **T049**: Implement idempotency check: if `docker compose ps` shows running services, skip build and report status (FR-015)
- **T050**: Implement compose orchestration: select compose files based on GPU profile + `--dev` flag, run `docker compose -f ... up --build -d` (FR-001)
- **T051**: Implement health polling: poll Qdrant, Ollama, backend, frontend health endpoints using configured host ports. Print per-service status line with in-place overwrite. Timeout 300s first run, 60s subsequent (FR-011)
- **T052**: Implement model pull: after health checks pass, check `docker compose exec ollama ollama list` for each model in `OLLAMA_MODELS`. Pull missing models with progress passthrough (FR-012, FR-013)
- **T053**: Implement browser open: when `--open` flag is set, open `http://localhost:${FRONTEND_PORT}` via `open` (macOS) / `xdg-open` (Linux) (FR-014)
- **T054**: Implement port conflict detection: check configured ports before starting, identify conflicting process if possible, suggest `--frontend-port` / `--backend-port` as resolution (FR-016)
- **T055**: Implement ready message: print URL, `--logs` command, `--stop` command after all health checks and model pulls complete

### embedinator.ps1 (PowerShell) — T056 through T059

- **T056**: Create `embedinator.ps1`: implement identical logic with PowerShell-native syntax — `param()` block for CLI flags, `docker info 2>$null` for Docker check, `Test-NetConnection` for port checks, `Invoke-RestMethod` for health polling, `Start-Process` for browser open (FR-001)
- **T057**: Implement all subcommands: `-Help`, `-Stop`, `-Restart`, `-Logs [service]`, `-Status`, `-Open`, `-Dev`, `-FrontendPort PORT`, `-BackendPort PORT` (FR-002, FR-003)
- **T058**: Implement GPU detection: NVIDIA only via `nvidia-smi` in WSL2; AMD/Intel always fall back to CPU on Windows (FR-005, FR-006)
- **T059**: Implement `.env` generation, CORS auto-detection, data dir creation, health polling, model pull, and ready message — same logic as bash script with PowerShell equivalents (FR-008 through FR-016)

### Phase 5 Verification — T060

- **T060**: Verify `bash -n embedinator.sh` passes (syntax check). Verify `./embedinator.sh --help` prints usage.

## Files to CREATE

| File | Purpose |
|------|---------|
| `embedinator.sh` | Bash/zsh launcher for macOS and Linux — the primary launcher |
| `embedinator.ps1` | PowerShell launcher for Windows |

## Files to MODIFY

None — you only create new files.

## Files NEVER to Touch

- `Makefile` — SC-010
- `docker-compose.yml` — owned by A1 (Wave 1, already done)
- `docker-compose.dev.yml` — owned by A1
- `backend/**` — owned by A3 and A6
- `frontend/**` — owned by A2 and A5
- `requirements.txt` — no new packages
- `frontend/package.json` — no new packages
- Any `tests/**` files

## Must-Read Documents (in order)

1. This file (read first)
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — Sections 4 (GPU Auto-Detection), 8 (Launcher Script Design), 9 (Cross-Platform Considerations)
3. `specs/019-cross-platform-dx/spec.md` — FR-001 through FR-016, FR-054, FR-055, FR-056, plus User Stories 1-5
4. `specs/019-cross-platform-dx/tasks.md` — T037 through T060
5. `specs/019-cross-platform-dx/data-model.md` — Sections 1 (GPU Profile), 2 (Port Configuration), 5 (Launcher Subcommands)
6. `Docs/PROMPTS/spec-19-cross-platform/19-implement.md` — stale patterns, risk gotchas

## Key Gotchas

1. **Implement bash FIRST, then PowerShell** — `embedinator.sh` is the primary target. Get it fully working, then translate to PowerShell. PowerShell parity is the hardest deliverable.
2. **Fernet key via Docker, not local Python** — Use `docker run --rm python:3.14-slim python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. The host machine MUST NOT need Python installed.
3. **Health polling timeouts** — 300s for first run (model downloads take time), 60s for subsequent runs. Detect first run by checking if `.env` was just created OR if model images don't exist yet.
4. **Port conflict detection** — Check ALL configured ports (from `.env` + CLI overrides) BEFORE starting Docker Compose. Use `lsof -i :PORT` (Linux/macOS) or `Test-NetConnection` (PowerShell) to detect conflicts. Suggest `--frontend-port` / `--backend-port` in error messages.
5. **GPU detection priority** — NVIDIA > AMD > Intel > CPU. Only first match wins. `EMBEDINATOR_GPU` env var overrides auto-detection. macOS ALWAYS returns `none` (CPU) regardless of hardware.
6. **Compose file selection** — Base compose is always loaded. GPU overlay added based on detection. `--dev` flag adds dev overlay. Compose files combined with `-f` flags.
7. **CORS auto-detection** — Detect LAN IP via `hostname -I | awk '{print $1}'` (Linux) or `ipconfig getifaddr en0` (macOS). Write `CORS_ORIGINS` including localhost, 127.0.0.1, and LAN IP, all with the configured frontend port.
8. **Idempotency** — If `docker compose ps --format json` shows running services, skip build and just report status with health check.
9. **`OLLAMA_MODELS` default** — `qwen2.5:7b,nomic-embed-text` (comma-separated). Split and iterate to pull each model.
10. **Make the scripts executable** — `embedinator.sh` needs `chmod +x`. Start the file with `#!/usr/bin/env bash` and add `set -euo pipefail`.

## Verification Commands

```bash
# Syntax check (no execution)
bash -n embedinator.sh && echo "PASS: bash syntax" || echo "FAIL"

# Help output
./embedinator.sh --help 2>&1 | head -5 && echo "PASS: help output" || echo "FAIL"

# PowerShell syntax (if pwsh available)
pwsh -NoProfile -Command "& { Get-Help ./embedinator.ps1 }" 2>/dev/null && echo "PASS: ps1 syntax" || echo "SKIP: pwsh not available"
```

## Task Completion

After completing each task, mark it as `[X]` in `specs/019-cross-platform-dx/tasks.md`.
