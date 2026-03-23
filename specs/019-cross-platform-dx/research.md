# Research: Cross-Platform Developer Experience

**Feature**: 019-cross-platform-dx
**Date**: 2026-03-19
**Status**: Complete — all decisions pre-resolved via 4-architect design session

## Note

All technical decisions for this spec were resolved during a dedicated design session using 4 specialized architect agents (system, devops, backend, frontend) before the speckit pipeline began. The authoritative design document is `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` (700 lines, 13 sections). This research.md documents the key decisions and rejected alternatives for traceability.

---

## Decision 1: Sole Prerequisite Strategy

**Decision**: Docker Desktop (or Docker Engine + Compose v2 on Linux) is the only prerequisite.
**Rationale**: The existing multi-stage Dockerfiles already compile Rust and run Python/Node inside containers. No local toolchain is needed for production mode. Docker Desktop is available on all 3 target platforms and handles networking, volume management, and process lifecycle.
**Alternatives considered**:
- Python CLI bootstrapper — rejected: requires Python pre-installed, pip/venv management is OS-dependent
- Go/Rust wrapper binary — rejected: requires distributing 6+ platform/arch binaries, premature for project stage
- `just`/`task` runner — rejected: adds a prerequisite users must install first

## Decision 2: Launcher Mechanism

**Decision**: `embedinator.sh` (bash/zsh) + `embedinator.ps1` (PowerShell) pair at repo root.
**Rationale**: Zero dependencies beyond the OS shell. bash/zsh exist on macOS and Linux. PowerShell exists on Windows 10/11. Scripts can detect GPU, generate .env, select compose overlays, poll health, and pull models — all using `docker` CLI commands guaranteed available with Docker Desktop.
**Alternatives considered**:
- Single cross-platform script — rejected: no shell language works natively on all 3 OS
- Makefile enhancements — rejected: `make` not available on Windows natively; Makefile is preserved for developers

## Decision 3: GPU Handling

**Decision**: Docker Compose overlay files selected by the launcher based on auto-detection. Priority: NVIDIA > AMD > Intel > CPU.
**Rationale**: The base compose file has no GPU block (always safe). GPU-specific configuration is additive. AMD requires a different Docker image (`ollama:rocm`), not just a deploy block, so overlays are more flexible than profiles.
**Alternatives considered**:
- Docker Compose profiles — rejected: profiles cannot swap the container image (needed for AMD ROCm)
- Single compose file with conditional GPU — rejected: YAML does not support conditionals; would require templating

## Decision 4: Frontend API Routing

**Decision**: Next.js `rewrites` in `next.config.ts` proxying `/api/:path*` to `BACKEND_URL`.
**Rationale**: Eliminates `NEXT_PUBLIC_API_URL` build-time baking. Browser uses relative paths, rewrite operates at HTTP level (no buffering, streaming works). Zero CORS issues. LAN access works automatically.
**Alternatives considered**:
- Build-time `NEXT_PUBLIC_API_URL=http://localhost:8000` — rejected: breaks LAN access from other devices
- Next.js API route proxy — rejected: adds latency, NDJSON streaming requires careful handling, increases Node CPU/memory
- Runtime env injection (sed on built JS) — rejected: fragile, depends on minification not mangling the string
- nginx reverse proxy — rejected: adds a 5th Docker service (violates Constitution VII)

## Decision 5: Port Configuration

**Decision**: 5 host ports configurable via `EMBEDINATOR_PORT_*` env vars in `.env`, with CLI flag overrides.
**Rationale**: Docker Compose variable interpolation (`${VAR:-default}:internal`) maps configurable host ports to fixed container ports. No code changes inside containers. Launcher reads ports from `.env` + CLI flags for health polling, CORS, and browser open.

## Decision 6: Backend Health Architecture

**Decision**: Two endpoints — `/api/health/live` (liveness, always 200) + `/api/health` (readiness, per-service status with model availability).
**Rationale**: Docker HEALTHCHECK targets liveness (prevents restarts during model downloads). Launcher and frontend target readiness (know when the system is fully functional). Ollama probe parses `/api/tags` to check model availability.

## Decision 7: Cross-Encoder Model Caching

**Decision**: Pre-download in Dockerfile (bake into image, +24MB).
**Rationale**: Eliminates runtime HuggingFace download. Works in air-gapped environments. 24MB is ~2% of total image size. Deterministic builds.
**Alternatives considered**:
- Named volume for HuggingFace cache — rejected: first-run still requires internet, model version drift
- Bind mount at `data/models/` — rejected: pollutes data directory, same first-run download issue

## Decision 8: Qdrant Volume Strategy

**Decision**: Keep as bind mount at `./data/qdrant_db:/qdrant/storage:z` (user decision from specify clarification Q2).
**Rationale**: User-visible data, survives `docker compose down -v`, consistent with SQLite data strategy.

## Decision 9: Browser Auto-Open

**Decision**: Require explicit `--open` flag (user decision from specify clarification Q5).
**Rationale**: Never surprising. Users who want auto-open use `./embedinator.sh --open`. Avoids annoyance on restarts.

## Decision 10: Model Pull Strategy

**Decision**: Launcher script pulls after Ollama is healthy (user decision from specify clarification Q4).
**Rationale**: Progress visible in terminal. Decoupled from container lifecycle. User sees download percentage. Easier to debug than an in-container init script.

## Decision 11: Graceful Shutdown

**Decision**: 15s stop_grace_period, `shutting_down` flag, WAL checkpoint on both SQLite DBs, explicit checkpointer close.
**Rationale**: Default 10s is insufficient for in-flight NDJSON streams. WAL checkpoint ensures consistent DB state on host. Checkpointer close prevents WAL leak.
**Source**: Design doc Section 6.3.

## Decision 12: Cross-Platform Hardening

**Decision**: `.gitattributes` (LF/CRLF), SELinux `:z` on bind mounts, platform-specific warnings in launcher.
**Rationale**: Addresses top failure modes on each OS. `.gitattributes` prevents shell script corruption on Windows. `:z` is a no-op on non-SELinux systems. Warnings are informational (not blocking).
