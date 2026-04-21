# Spec 02: ConversationGraph — Implementation Session 2026-03-10

## Status
- **All speckit artifacts**: Complete
- **02-implement.md**: Rewritten, coherent with spec, plan, research, contracts
- **Agent instruction files**: 10 files created in `Docs/PROMPTS/spec-02-conversation-graph/agents/`
- **External test runner**: Adapted from GRAVITEA, working with auto-venv
- **Branch**: `002-conversation-graph`
- **Next step**: Run `/speckit.implement` — orchestrator reads `02-implement.md` and spawns Agent-Scaffold

## Key Deliverables This Session

### 1. Rewritten 02-implement.md (428 lines)
- Corrected all SSE → NDJSON, astream_events → stream_mode="messages"
- Added ORCHESTRATOR: READ THIS FIRST section with anti-drift rules
- Added step-by-step Spawning Protocol with exact Agent() calls per wave
- Added Test Execution Policy (NEVER run pytest inside Claude Code)
- All 11 nodes, 3 edges, correct graph wiring from plan.md

### 2. Agent Instruction Files (10 files)
| Agent | Wave | subagent_type | Model |
|-------|------|---------------|-------|
| agent-scaffold.md | 1 | python-expert | opus |
| agent-session-history.md | 2 | python-expert | sonnet |
| agent-intent-analysis.md | 2 | python-expert | opus |
| agent-dispatch-aggregation.md | 2 | python-expert | sonnet |
| agent-interrupt-stubs.md | 2 | python-expert | sonnet |
| agent-integration.md | 3 | backend-architect | opus |
| agent-api.md | 4 | backend-architect | opus |
| agent-unit-tests.md | 5 | quality-engineer | sonnet |
| agent-integration-tests.md | 5 | quality-engineer | opus |
| agent-polish.md | 6 | self-review | opus |

### 3. External Test Runner (scripts/run-tests-external.sh)
- Adapted from GRAVITEA for Fedora Linux + zsh + tmux
- Auto-creates `.venv/` with fingerprint-based dep checking (sha256 of requirements*.txt)
- Modes: detached (agents), --visible (tmux window), --fg (interactive)
- Output: Docs/Tests/{name}.{status,summary,log}
- Added pytest-cov to requirements.txt
- Smoke tested: 50 passed, 1 pre-existing failure in test_config.py

### 4. tmux Setup (Docs/Setups/tmux.md)
- Fixed: detached mode (-d flag), proper set-option syntax, session name
