# Quickstart: Cross-Platform Developer Experience (Spec 019)

## For Implementers

### Prerequisites
- Docker Desktop (Windows/macOS) or Docker Engine + Compose v2 (Linux)
- Access to the codebase on branch `019-cross-platform-dx`

### Key Documents (read order)
1. `specs/019-cross-platform-dx/spec.md` — 56 FRs, 10 SCs, 7 user stories
2. `Docs/DESIGN-019-CROSS-PLATFORM-DX.md` — authoritative design decisions (700 lines)
3. `Docs/PROMPTS/spec-19-cross-platform/19-plan.md` — implementation plan (758 lines, 7 phases, 7 agents)

### Implementation Summary

This spec has 7 phases across 3 parallel waves:

**Wave 1 (parallel, zero file overlap)**:
- A1: Docker infrastructure (compose, overlays, Dockerfiles, .gitattributes)
- A2: Frontend API routing (rewrites, healthz, root redirect)
- A3: Backend health (liveness, readiness, log suppression)

**Gate Check 1**: Compose configs valid, frontend builds, health module imports

**Wave 2 (parallel, zero file overlap)**:
- A4: Launcher scripts (embedinator.sh + embedinator.ps1, 19 FRs)
- A5: Frontend degraded states (BackendStatusProvider, StatusBanner, chat gating)
- A6: Graceful shutdown + environment (.env.example, WAL checkpoint, shutdown flag)

**Gate Check 2**: Launcher syntax valid, frontend builds, main.py imports

**Wave 3**: A7 validates all 10 SCs

### Critical Constraints
- **Makefile MUST NOT be modified** (SC-010) — diff against HEAD to verify
- **No new pip/npm packages** — use only existing dependencies
- **No database schema changes** — SQLite and Qdrant schemas unchanged
- **NEVER run pytest directly** — use `zsh scripts/run-tests-external.sh -n <name> <target>`

### Verification Commands
```bash
# Compose overlays valid
docker compose config > /dev/null
docker compose -f docker-compose.yml -f docker-compose.gpu-nvidia.yml config > /dev/null

# Frontend builds and tests pass
cd frontend && npm run build && npm run test

# Backend health module loads
python -c "from backend.api.health import router"

# Launcher syntax valid
bash -n embedinator.sh

# Makefile unchanged
diff <(git show HEAD:Makefile) Makefile
```

## For End Users (post-implementation)

### First-Time Setup
```bash
git clone https://github.com/your-org/the-embedinator.git
cd the-embedinator
./embedinator.sh          # macOS/Linux
# or
.\embedinator.ps1         # Windows PowerShell
```

### Common Operations
```bash
./embedinator.sh                    # Start (production mode)
./embedinator.sh --dev              # Start with hot reload
./embedinator.sh --stop             # Stop all services
./embedinator.sh --restart          # Restart all services
./embedinator.sh --status           # Check service health
./embedinator.sh --logs backend     # Stream backend logs
./embedinator.sh --open             # Open browser after start
./embedinator.sh --help             # Show all options
```

### Custom Ports
```bash
# One-time override
./embedinator.sh --frontend-port 4000 --backend-port 9000

# Persistent (edit .env)
EMBEDINATOR_PORT_FRONTEND=4000
EMBEDINATOR_PORT_BACKEND=9000
```

### GPU Override
```bash
EMBEDINATOR_GPU=amd ./embedinator.sh    # Force AMD
EMBEDINATOR_GPU=none ./embedinator.sh   # Force CPU
```
