# Implementation Plan: Cross-Platform Developer Experience

**Branch**: `019-cross-platform-dx` | **Date**: 2026-03-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/019-cross-platform-dx/spec.md`

## Summary

Spec-19 transforms The Embedinator from a multi-command, toolchain-dependent setup into a single-command, cross-platform application. Users run `./embedinator.sh` (macOS/Linux) or `.\embedinator.ps1` (Windows) and the entire stack builds, configures itself, downloads AI models, and reports readiness. Docker Desktop is the sole prerequisite. The implementation covers Docker Compose decomposition with GPU overlay files (NVIDIA/AMD/Intel), Next.js rewrite-based API routing (fixing a critical build-time baking bug), configurable ports, backend health enhancement with liveness/readiness separation, frontend degraded-state UI, graceful shutdown, and cross-platform hardening.

**Full implementation plan**: `Docs/PROMPTS/spec-19-cross-platform/19-plan.md` (758 lines, 7 phases, 7 agents, 3 waves)
**Design document**: `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` (700 lines, 13 sections)

## Technical Context

**Language/Version**: Python 3.14+ (backend), TypeScript 5.7 (frontend), Rust 1.93 (ingestion worker — compiled in Docker, unchanged), Bash/PowerShell (launcher scripts)
**Primary Dependencies**: FastAPI >= 0.135, Next.js 16, React 19, SWR 2, Docker Compose v2 — all existing, no new dependencies added
**Storage**: SQLite WAL mode (existing), Qdrant (existing) — no schema changes
**Testing**: pytest (backend, external runner), vitest (frontend), Playwright (E2E) — all existing
**Target Platform**: Windows 10/11 (Docker Desktop + WSL2), macOS 13+ (Docker Desktop), Linux (Docker Engine + Compose v2)
**Project Type**: Full-stack web application with Docker-based deployment
**Performance Goals**: First-run < 10 minutes (including model downloads); subsequent startup < 60 seconds; `/api/health` < 50ms; `/api/health/live` < 5ms
**Constraints**: Docker Desktop = sole prerequisite; zero local toolchain requirement; all 14 Makefile targets preserved unchanged; no new pip/npm packages
**Scale/Scope**: 56 FRs across 9 areas, 12 files to create, 15 files to modify, 7 user stories, 10 success criteria

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Assessment |
|-----------|--------|------------|
| **I. Local-First Privacy** | PASS | No new cloud dependencies. Docker Compose remains the deployment mechanism. Launcher auto-generates Fernet key locally. No authentication added (explicit out-of-scope). |
| **II. Three-Layer Agent Architecture** | PASS | No changes to the agent architecture. ConversationGraph → ResearchGraph → MetaReasoningGraph is untouched. |
| **III. Retrieval Pipeline Integrity** | PASS | No changes to retrieval pipeline. Hybrid search, cross-encoder reranking, parent/child chunking all unchanged. Cross-encoder model is pre-downloaded in Dockerfile (build optimization, not a pipeline change). |
| **IV. Observability from Day One** | PASS | Health endpoints enhanced (not removed). Liveness endpoint added. Health request logging suppressed for noise reduction only — security events and query traces are unaffected. |
| **V. Secure by Design** | PASS | Fernet key auto-generated via disposable Docker container (no weaker fallback). CORS origins auto-detected including LAN IP. Health log suppression excludes only `/api/health` and `/api/health/live`, not security-relevant endpoints. Shutdown sends proper NDJSON error frame (not connection drop). |
| **VI. NDJSON Streaming Contract** | PASS | NDJSON streaming preserved through Next.js rewrites (HTTP-level proxy, no buffering). Shutdown adds `{"type": "error", "code": "SHUTTING_DOWN"}` — a valid error frame per the contract. |
| **VII. Simplicity by Default** | PASS | Still exactly 4 Docker services (no 5th added). GPU overlays are additive compose files, not new services. Launcher scripts add 2 files but eliminate 9 manual setup steps. No new abstractions in backend or frontend code. |
| **VIII. Cross-Platform Compatibility** | PASS | This spec directly implements Principle VIII. Launcher scripts for all 3 OS. GPU detection for NVIDIA/AMD/Intel. SELinux `:z` for Fedora/RHEL. WSL2 warnings. macOS memory warnings. `.gitattributes` for line endings. |

**Result: All 8 principles PASS. No gate violations. No complexity tracking needed.**

## Project Structure

### Documentation (this feature)

```text
specs/019-cross-platform-dx/
├── plan.md              # This file
├── research.md          # Phase 0 output (all decisions pre-resolved via design doc)
├── data-model.md        # Phase 1 output (key entities and state machines)
├── quickstart.md        # Phase 1 output (developer quickstart for this feature)
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
# Files to CREATE (12)
embedinator.sh                                  # Bash/zsh launcher (macOS + Linux)
embedinator.ps1                                 # PowerShell launcher (Windows)
docker-compose.gpu-nvidia.yml                   # NVIDIA GPU overlay
docker-compose.gpu-amd.yml                      # AMD ROCm GPU overlay
docker-compose.gpu-intel.yml                    # Intel Arc GPU overlay
.gitattributes                                  # Line ending enforcement
frontend/.dockerignore                          # Build context exclusion
frontend/app/healthz/route.ts                   # Frontend health endpoint
frontend/app/page.tsx                           # Root redirect to /chat
frontend/components/BackendStatusProvider.tsx    # React context for backend health
frontend/components/StatusBanner.tsx             # Global degraded state banner
specs/019-cross-platform-dx/validation-report.md # SC validation report

# Files to MODIFY (15)
docker-compose.yml                              # Compose decomposition (GPU removal, ports, health, SELinux, logging)
docker-compose.dev.yml                          # Fix broken volume mounts
Dockerfile.backend                              # UID 1000, tini, cross-encoder pre-download
frontend/Dockerfile                             # Pin Node 22, combine layers
frontend/next.config.ts                         # Add rewrites() for API proxy
frontend/lib/api.ts                             # Change API_BASE to empty string
frontend/app/layout.tsx                         # Wrap with BackendStatusProvider
frontend/components/SidebarLayout.tsx            # Insert StatusBanner
frontend/components/ChatInput.tsx                # Backend status gating
frontend/components/ChatPanel.tsx                # First-run onboarding card
frontend/lib/types.ts                           # Add BackendStatus types
backend/api/health.py                           # Add liveness, enhance readiness
backend/agent/schemas.py                        # Extend health response types
backend/middleware.py                            # Suppress health request logs
backend/main.py                                 # Shutdown logic, upload dir, write-access
backend/api/chat.py                             # Shutdown rejection
.env.example                                    # Add port, GPU, model vars

# Files to PRESERVE (must not be modified)
Makefile                                        # SC-010: all 14 targets unchanged
backend/config.py                               # No Settings changes
tests/**                                        # No test file changes
```

**Structure Decision**: This feature modifies existing infrastructure files and adds new launcher/compose/component files. No new Python modules or npm packages. The backend and frontend directory structures are unchanged.
