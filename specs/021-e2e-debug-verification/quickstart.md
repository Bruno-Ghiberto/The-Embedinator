# Quickstart: Implementing Spec 21 (E2E Debug & Verification)

## Prerequisites

- Branch `021-e2e-debug-verification` checked out
- Docker Desktop installed and running (8GB RAM, 15GB free disk)
- No conflicting services on ports 3000, 6333, 8000, 11434
- Spec-20 changes committed (governance files, test annotations, docs reorg)

## Implementation Order

```
1. Read plan.md (this spec) and 21-plan.md (orchestration context)
2. Capture test baseline
3. Wave 1: A1 (Docker) + A2 (Backend) — parallel
4. Gate 1: Start services, verify health
5. Wave 2: A3 (Frontend) + A4 (Ingestion) — parallel
6. Gate 2: Verify pages, seed data
7. Wave 3: A5 (Chat + Smoke) + A6 (Docs) — parallel
8. Gate 3: Full SC validation
```

## Quick Validation Commands

```bash
# Test baseline (before any changes)
zsh scripts/run-tests-external.sh -n baseline-spec21 --no-cov tests/

# Docker validation
docker compose config > /dev/null && echo "OK"
docker compose build
docker compose up -d
docker compose ps

# Health endpoints
curl -sf http://localhost:8000/api/health | python -m json.tool
curl -sf http://localhost:3000/healthz

# Seed data
python scripts/seed_data.py

# Smoke test
python scripts/smoke_test.py

# Makefile check (every gate)
git diff -- Makefile | wc -l   # must be 0
```

## Key Artifacts

| Artifact | Path | Purpose |
|----------|------|---------|
| Feature spec | `specs/021-e2e-debug-verification/spec.md` | Requirements (26 FRs, 10 SCs) |
| Implementation plan | `specs/021-e2e-debug-verification/plan.md` | Technical plan + constitution check |
| Orchestration context | `Docs/PROMPTS/spec-21-debug/21-plan.md` | Agent team structure, wave execution, MCP tools |
| Research | `specs/021-e2e-debug-verification/research.md` | Resolved unknowns (6 decisions) |
| Smoke test contract | `specs/021-e2e-debug-verification/contracts/smoke-test.md` | 13 checks, exit codes, output format |
| Seed data contract | `specs/021-e2e-debug-verification/contracts/seed-data.md` | Idempotent seeding behavior |
| Agent instructions | `Docs/PROMPTS/spec-21-debug/agents/A1-A6-instructions.md` | Per-agent task details (to be created) |

## Critical Correction from Research

**Root Cause #1 is partially incorrect**: `BACKEND_URL` in `next.config.ts` rewrites is
read at **server startup** (runtime), NOT at build time. The `async rewrites()` function
evaluates when the Next.js process starts. Docker Compose's `environment: BACKEND_URL=...`
provides this at runtime correctly.

The frontend exit code 1 must be investigated from Docker logs — it's likely a build failure
or runtime error unrelated to BACKEND_URL. See `research.md` Decision 1 for details.

## Next Step

Run `/speckit.tasks` to generate the task breakdown, or create agent instruction files
at `Docs/PROMPTS/spec-21-debug/agents/` and proceed to `/speckit.implement`.
