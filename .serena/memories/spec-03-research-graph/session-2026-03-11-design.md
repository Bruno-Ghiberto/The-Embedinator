# Spec 03: ResearchGraph — Full Speckit Pipeline + Design Session

## Status
- **Speckit pipeline**: COMPLETE (specify → clarify → plan → tasks → analyze → design)
- **Branch**: `003-research-graph`
- **Next step**: `/speckit.implement` (Step 9 of workflow)

## Artifacts Produced

| File | Lines | Purpose |
|------|-------|---------|
| `specs/003-research-graph/spec.md` | 180 | 6 user stories, 17 FRs, 8 SCs |
| `specs/003-research-graph/plan.md` | 179 | 5-wave subagent team, constitution check |
| `specs/003-research-graph/research.md` | 340 | 8 research decisions (R1-R8) |
| `specs/003-research-graph/data-model.md` | 174 | Entities, state transitions |
| `specs/003-research-graph/contracts/internal-contract.md` | 70 | I/O + tool contracts |
| `specs/003-research-graph/quickstart.md` | 77 | Dev onboarding |
| `specs/003-research-graph/tasks.md` | 297 | 57 tasks across 9 phases |
| `Docs/PROMPTS/spec-03-research-graph/03-implement.md` | ~1480 | Orchestrator implementation context (rewritten) |
| `Docs/PROMPTS/spec-03-research-graph/agents/*.md` | 8 files | Agent instruction files |

## /speckit.analyze Findings (Applied to 03-implement.md)

- **F1 (HIGH)**: Confidence must be checked FIRST in should_continue_loop, then budget. Fixed in implement.md.
- **F2 (HIGH)**: FR-016 retry-once had no explicit implementation task. Added to tools_node in implement.md.
- **C1 (MEDIUM)**: Circuit breaker required on HybridSearcher Qdrant calls. Added to implement.md.
- **F3 (MEDIUM)**: should_compress_context sets `_needs_compression` state flag. Documented.
- **F4 (MEDIUM)**: orchestrator sets `_no_new_tools` flag for tool exhaustion. Documented.
- **Confidence scale mismatch**: config.confidence_threshold=60 (int 0-100) vs state.confidence_score (float 0.0-1.0). Edge converts: `settings.confidence_threshold / 100`.

## Agent Team Design

| Agent | subagent_type | Model | Wave |
|-------|---------------|-------|------|
| agent-scaffold | python-expert | Opus 4.6 | 1 |
| agent-retrieval | python-expert | Opus 4.6 | 2 |
| agent-tools | python-expert | Sonnet 4.6 | 2 |
| agent-nodes | python-expert | Sonnet 4.6 | 2 |
| agent-integration | backend-architect | Opus 4.6 | 3 |
| agent-unit-tests | quality-engineer | Sonnet 4.6 | 4 |
| agent-integration-tests | quality-engineer | Opus 4.6 | 4 |
| agent-polish | self-review | Opus 4.6 | 5 |

## Orchestrator Protocol
- MUST run in tmux (Agent Teams auto-detects for multi-pane)
- Spawn prompt: "Read your instruction file at Docs/PROMPTS/spec-03-research-graph/agents/<name>.md FIRST, then execute all assigned tasks."
- Checkpoint gate between every wave — never proceed if checkpoint fails
- Parallel agents spawned in single message for concurrency

## Key Codebase Facts Discovered
- `config.py:40` — `confidence_threshold: int = 60` (0-100 scale, NOT float 0.6)
- `confidence.py` — Phase 1 placeholder returns int 0-100, must be replaced with float 0.0-1.0
- `mocks.py` — `build_mock_research_graph()` already exists, needs preservation
- `main.py` lifespan does NOT currently build graphs — needs HybridSearcher/Reranker/ParentStore init
- Serena only has bash configured — cannot use symbolic tools for Python files
