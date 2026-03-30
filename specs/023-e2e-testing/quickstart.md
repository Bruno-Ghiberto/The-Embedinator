# Quickstart: E2E Testing

**Feature**: 023-e2e-testing
**Time estimate**: 3-5 hours (depends on bugs found)

## Prerequisites

Before starting, ensure you have:
- [ ] NVIDIA GPU with drivers installed (`nvidia-smi` works)
- [ ] Native Docker Engine (NOT Docker Desktop on Linux) with `nvidia-container-toolkit`
- [ ] `~/.docker/config.json` has `"credsStore": ""` (not `"desktop"`)
- [ ] Go 1.24+ installed (for building TUI binary)
- [ ] Chrome or Firefox browser
- [ ] Ports 3000, 8000, 6333, 11434 available

## How It Works

1. The orchestrator (Claude) runs automated checks and guides you through manual steps
2. At each phase gate, you explicitly confirm before advancing
3. When bugs are found, we pause, fix, verify, and resume
4. Everything is documented in real-time in `logs.md`

## Starting the E2E

Tell the orchestrator: **"Start Phase 0"** (or "empecemos con la Fase 0")

The orchestrator will:
1. Run environment pre-flight checks (Phase 0)
2. Guide you through TUI installation (Phase 1)
3. Verify all backend APIs (Phase 2)
4. Walk you through every page, feature, and integration (Phases 3-9)
5. Run final acceptance tests (Phase 10)
6. Generate the acceptance report

## Key Commands

| Action | What to say |
|--------|------------|
| Start testing | "Start Phase 0" |
| Confirm gate | "Proceed" or "Gate pass" |
| Report a bug | "I found a problem: [description]" |
| Skip a check | "Skip this check, reason: [why]" |
| Pause testing | "Pause -- let's resume later" |
| Resume testing | "Resume from Phase N" |

## Expected Duration

| Phase | Time |
|-------|------|
| 0: Pre-flight | ~5 min |
| 1: TUI Install | ~10 min |
| 2: Backend API | ~5 min |
| 3: Navigation | ~15 min |
| 4: Collections | ~10 min |
| 5: Ingestion | ~15 min |
| 6: Chat & RAG | ~20 min |
| 7: Settings | ~10 min |
| 8: Observability | ~10 min |
| 9: Edge Cases | ~10 min |
| 10: Acceptance | ~15 min |
| **Total** | **~2 hours** (without bugs) |

Add 15-30 minutes per bug found and fixed (impasse protocol).

## Deliverables

After testing completes, you will have:
- `e2e-guide.md` -- Reproducible step-by-step guide
- `logs.md` -- Complete execution log with all findings
- `acceptance-report.md` -- Final acceptance decision (ACCEPT / CONDITIONAL / REJECT)
