# Quickstart: Spec 25 --- Master Debug Battle Test

## Prerequisites

Before starting the Spec-25 battle test, ensure:

1. **Docker Compose stack is running** with all 4 services healthy:
   ```bash
   cd /home/brunoghiberto/Documents/Projects/The-Embedinator
   docker compose up -d
   docker compose ps  # all 4 services should show "healthy" or "running"
   ```

2. **Baseline models are pulled** in Ollama:
   ```bash
   docker compose exec ollama ollama list
   # Must show: qwen2.5:7b and nomic-embed-text
   # If missing:
   docker compose exec ollama ollama pull qwen2.5:7b
   docker compose exec ollama ollama pull nomic-embed-text
   ```

3. **Seed data exists** (at least one collection with ingested documents):
   ```bash
   curl -sf http://localhost:8000/api/collections | python3 -m json.tool
   # Must show >= 1 collection with documents
   ```

4. **GPU is accessible** from the Ollama container:
   ```bash
   docker compose exec ollama nvidia-smi
   # Must show NVIDIA RTX 4070 Ti with ~12GB VRAM
   ```

5. **Browser ready** at http://localhost:3000 (frontend loads without errors).

6. **PaperclipAI configured** with:
   - Company: "The Embedinator QA"
   - Project: "Spec 25 --- Master Debug"
   - All 7 core agents (A1-A7) available
   - All 3 support agents (S1-S3) available
   - CEO agent with Docker MCP, Browser Tools, Playwright, Engram access

## How to Start

### Step 1: CEO Strategy Proposal

The CEO agent submits the following strategy to the Board (human) for approval:

> **Strategy**: 5-wave sequential execution with parallel phases within waves.
> Human-in-the-loop for all browser interactions. Gate checks between waves.
> Risk: phi4:14b may OOM on 12GB GPU (mitigation: mark "VRAM-exceeded").
> Deliverable: comprehensive quality report.
> Estimated sessions: 3-5.

**Board action**: Approve the strategy.

### Phase-to-Task Mapping

| Phase | Name | Tasks | Wave |
|-------|------|-------|------|
| Phase 1 | Setup (PaperclipAI Config) | T001-T007 | Pre-Wave |
| Phase 2 | Infrastructure Verification | T008-T015 | Wave 1 |
| Phase 3 | Core Functionality | T016-T038 | Wave 2 |
| Phase 4 | Model Experimentation | T039-T044 | Wave 2 |
| Phase 5 | Data Quality Audit | T045-T051 | Wave 3 |
| Phase 6 | Chaos Engineering | T052-T058 | Wave 3 |
| Phase 7 | Security Probing | T059-T066 | Wave 3 |
| Phase 8 | UX Journey Audit | T067-T072 | Wave 4 |
| Phase 9 | Regression Sweep | T073-T084 | Wave 4 |
| Phase 10 | Performance Profiling | T085-T089 | Wave 4 |
| Phase 11 | Final Report | T090-T094 | Wave 5 |
| Phase 12 | Polish | T095-T098 | Wave 5 |

> **Note**: Engram topic keys use P1-P10 numbering (testing phases only), offset by -1 from tasks.md phase numbers (which include Phase 1: Setup). Example: tasks.md "Phase 3" = Engram key "spec-25/p2-core-functionality".

### Step 2: Wave 1 --- Infrastructure (Phase 2)

CEO creates tasks T008-T015 for A1 (DevOps Architect):
- Verify all 4 services healthy, backend health, frontend pages
- Verify baseline models available, GPU acceleration
- Verify seed data exists, no startup errors
- Persist phase findings to Engram

CEO also directs human to open browser and verify frontend loads.

After Phase 2 completion: CEO runs Gate 1 with S2.

### Step 3: Wave 2 --- Core Testing (Phases 3 + 4 in parallel)

CEO creates tasks for A2 (quality-engineer) and A3 (performance-engineer):
- **Phase 3**: T016-T038 (core functionality via API + human browser actions + edge cases)
- **Phase 4**: T039-T044 (model pulling, switching, scoring, scorecard)

CEO directs human through chat tests, CRUD operations, settings, while simultaneously
coordinating model switching for A3's scoring work.

After Phases 3 + 4 completion: CEO runs Gate 2 with S2.

### Step 4: Wave 3 --- Stress and Security (Phases 5 + 6 + 7 in parallel)

- **Phase 5**: T045-T051 assigned to A4 (data quality audit)
- **Phase 6**: T052-T058 assigned to A1 + CEO (chaos engineering with human observation)
- **Phase 7**: T059-T066 assigned to A5 (security probing)

After Phases 5 + 6 + 7 completion: CEO runs Gate 3 with S2.

### Step 5: Wave 4 --- Coverage (Phases 8 + 9 + 10 in parallel)

- **Phase 8**: T067-T072 assigned to A6 + CEO (UX journey with human walkthrough)
- **Phase 9**: T073-T084 assigned to A2 (regression sweep)
- **Phase 10**: T085-T089 assigned to A3 (performance profiling)

After Phases 8 + 9 + 10 completion: CEO runs Gate 4 with S2.

### Step 6: Wave 5 --- Final Report and Polish (Phases 11 + 12)

CEO assigns T090-T094 to A7 (technical-writer) to compile the final report from all Engram data. Then CEO executes T095-T098 (Polish) for SC verification, Engram validation, artifact cleanup, and final session summary.

## Session Management

### Safe Stopping Points

You can safely stop after any gate check. All findings are persisted to Engram.

| Stop Point | Resume From |
|------------|-------------|
| After Gate 1 | Wave 2 start (P2 + P3) |
| After Gate 2 | Wave 3 start (P4 + P5 + P6) |
| After Gate 3 | Wave 4 start (P7 + P8 + P9) |
| After Gate 4 | Wave 5 start (P10) |

### Resuming a Session

1. CEO queries Engram: `mem_search(query: "spec-25/session", project: "The-Embedinator")`
2. CEO retrieves the latest session snapshot: `mem_get_observation(id: ...)`
3. CEO reads the `current_phase`, `completed_tests`, and `next_action` fields.
4. CEO resumes from the identified point.

### Ending a Session

CEO persists a session snapshot before ending:

```python
mem_save(
    title="Spec-25 Session {N} Summary",
    type="discovery",
    scope="project",
    topic_key="spec-25/session-{N}",
    content="""
    ## Session {N} Summary
    - Current Phase: P{X}
    - Completed: [list of completed phases and tasks]
    - Pending: [list of remaining work]
    - Bugs Found This Session: [count and IDs]
    - Next Action: [what to do when resuming]
    """
)
```

## Key References

| Document | Path | Purpose |
|----------|------|---------|
| Feature Spec | `specs/025-master-debug/spec.md` | Requirements (78 FRs, 8 NFRs, 12 SCs) |
| Implementation Plan | `specs/025-master-debug/plan.md` | Technical context, constitution check |
| Full Plan Design | `docs/PROMPTS/spec-25-Master-Debug/25-plan.md` | Detailed agent tasks, commands, protocols |
| Data Model | `specs/025-master-debug/data-model.md` | Entity definitions and state machines |
| Bug Report Template | `specs/025-master-debug/contracts/bug-report.md` | Bug report format and severity |
| Scorecard Format | `specs/025-master-debug/contracts/scorecard.md` | Model comparison scorecard structure |
| Phase Summary Template | `specs/025-master-debug/contracts/phase-summary.md` | Per-phase summary format |
| Final Report Structure | `specs/025-master-debug/contracts/final-report.md` | Report sections and requirements |
| PaperclipAI Task Format | `specs/025-master-debug/contracts/paperclipai-task.md` | Task creation and lifecycle |
| Human Protocol | `specs/025-master-debug/contracts/human-protocol.md` | ACTION/OBSERVE/LOG CHECK/EXPECTED |
| Engram Keys | `specs/025-master-debug/contracts/engram-keys.md` | Topic key registry and persistence |
| Gate Checks | `specs/025-master-debug/contracts/gate-checks.md` | Gate procedures (Gates 1-4) |

## Minimum Viable Completion

The core value is delivered when these SCs pass:
- SC-001 (infrastructure healthy)
- SC-002 (chat works E2E)
- SC-003 (model scorecard with >= 5/7 combos)
- SC-004 (chaos recovery)
- SC-011 (final report compiled)
- SC-012 (bug registry complete)

The remaining SCs (SC-005 through SC-010) improve comprehensiveness but are not required for minimum viable completion.
