# Spec 11: Component Interface Contracts — Session 2026-03-17 (Design Phase)

## Status: FULL PIPELINE COMPLETE — Ready for Implementation

## What Was Done (continuation of earlier session)
1. **11-plan.md rewrite** — Technical-writer (Opus) rewrote from 153 → 708 lines, corrected 15 factual errors
2. **speckit.plan** — Generated plan.md, research.md (5 decisions), data-model.md, contracts/test-patterns.md (7 patterns), quickstart.md
3. **speckit.tasks** — 56 tasks (T001-T056) across 8 phases, 4-wave Agent Teams
4. **speckit.analyze** — 0 CRITICAL, 0 HIGH, 3 MEDIUM (all remediated: T028 FR ref, UpsertBuffer gap, SC-008 validation note)
5. **11-implement.md rewrite** — Technical-writer (Opus) produced 308-line implementation guide + 5 agent instruction files

## Agent Teams Configuration
- **Wave 1**: A1 (quality-engineer, Opus) — validate 11-specify.md, T003-T012
- **Wave 2**: A2 + A3 (python-expert, Sonnet) — PARALLEL in tmux panes
  - A2: test_contracts_agent.py (T013-T022)
  - A3: test_contracts_storage.py + test_contracts_retrieval.py (T023-T029, T035-T038)
- **Wave 3**: A4 (python-expert, Sonnet) — test_contracts_providers.py + ingestion + cross_cutting (T030-T052)
- **Wave 4**: A5 (quality-engineer, Sonnet) — final gate + full regression (T053-T056)

## Agent Instruction Files
- `Docs/PROMPTS/spec-11-interfaces/agents/A1-validation.md` (146 lines)
- `Docs/PROMPTS/spec-11-interfaces/agents/A2-agent-contracts.md` (128 lines)
- `Docs/PROMPTS/spec-11-interfaces/agents/A3-storage-retrieval-contracts.md` (157 lines)
- `Docs/PROMPTS/spec-11-interfaces/agents/A4-remaining-contracts.md` (191 lines)
- `Docs/PROMPTS/spec-11-interfaces/agents/A5-final-gate.md` (102 lines)

## Model IDs
- Short names used in Agent tool: `opus` and `sonnet` (maps to claude-opus-4-6, claude-sonnet-4-6)
- Fixed from initial claude-*-4-5 to correct short names

## Key Constraint
- tmux multi-pane is MANDATORY for Agent Teams (stated at top of 11-implement.md)
- NEVER run pytest inside Claude Code — always use `zsh scripts/run-tests-external.sh`

## Next Step: `speckit.implement` or manual Agent Teams execution in tmux
