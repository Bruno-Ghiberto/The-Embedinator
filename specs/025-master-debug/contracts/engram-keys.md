# Contract: Engram Topic Key Registry

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

All Spec-25 findings are persisted to Engram using structured topic keys. This registry defines every key, its content schema, and its lifecycle. Keys enable cross-session recovery and final report compilation.

## Topic Key Registry

| Topic Key | Phase | Content | Written By | When Updated |
|-----------|-------|---------|------------|--------------|
| `spec-25/p1-infrastructure` | P1 | Service health, GPU info, model availability, seed data, log findings | A1 + CEO | Phase 1 completion |
| `spec-25/p2-core-functionality` | P2 | Chat results, CRUD results, API endpoint status, session continuity, edge cases | A2 + CEO | Phase 2 completion |
| `spec-25/p3-model-matrix` | P3 | Per-combo scores, VRAM data, pull times, ranked scorecard, recommendation | A3 + CEO | Phase 3 completion (incremental during testing) |
| `spec-25/p4-data-quality` | P4 | Factual Q scores, OOD confidence, consistency results, calibration, groundedness | A4 | Phase 4 completion |
| `spec-25/p5-chaos-engineering` | P5 | Per-scenario results, recovery times, log excerpts, circuit breaker behavior | A1 + CEO | Phase 5 completion (incremental per scenario) |
| `spec-25/p6-security` | P6 | Per-probe results, payloads tested, response analysis, vulnerability findings | A5 | Phase 6 completion |
| `spec-25/p7-ux-journey` | P7 | Per-page findings, onboarding rating, click count, theme issues, a11y issues | A6 + CEO | Phase 7 completion |
| `spec-25/p8-regression` | P8 | 11-item checklist with PASS/FAIL and notes per item | A2 | Phase 8 completion |
| `spec-25/p9-performance` | P9 | Timing tables (TTFT, latency), GPU memory profiles, ingestion metrics, API latency | A3 | Phase 9 completion |
| `spec-25/p10-final-report` | P10 | Report file location, completion status, bug count summary | A7 + CEO | Phase 10 completion |
| `spec-25/bugs` | All | Running bug registry --- all bugs across all phases, sorted by severity | CEO | After every bug discovery |
| `spec-25/session-{N}` | N/A | Session snapshot: current phase, completed tests, pending, bugs, next action | CEO | Session end |

## Persistence Protocol

### Writing (mem_save)

```python
mem_save(
    title="Spec-25 P{N} {Phase Name} Results",
    type="discovery",
    scope="project",
    topic_key="spec-25/p{n}-{phase-name}",
    content="""
    **What**: Phase {N} testing completed with {pass}/{total} tests passing.
    **Why**: Spec-25 battle test Phase {N}.
    **Where**: Testing results for {list of FRs covered}.
    **Learned**: {key findings, anomalies, bugs discovered}.

    ## Results
    {structured phase summary content}
    """
)
```

### Reading (mem_search + mem_get_observation)

```python
# Step 1: Find the observation
results = mem_search(query="spec-25/p3-model-matrix", project="The-Embedinator")

# Step 2: Get full content (search results are truncated)
full_content = mem_get_observation(id=results[0].id)
```

### Session Recovery

```python
# At session start:
results = mem_search(query="spec-25/session", project="The-Embedinator")
# Get the most recent session snapshot
latest = mem_get_observation(id=results[0].id)
# Parse: current_phase, completed_tests, pending_tests, next_action
# Resume from next_action
```

## Update Policy

- **Phase keys** are written once at phase completion. If a phase is interrupted and resumed, the key is UPDATED (upsert via same topic_key), not duplicated.
- **Bug registry** is updated after every bug discovery (upsert with latest full registry).
- **Session keys** use incrementing suffixes: `spec-25/session-1`, `spec-25/session-2`, etc. These are append-only (never updated).
- **Incremental updates** during long phases (P3: model matrix): update the topic key after each combo is scored. The latest version always contains ALL completed combo data.

## Validation Rules

1. Every phase MUST have its Engram key written before transitioning to COMPLETED.
2. The bug registry key MUST reflect ALL bugs found so far (cumulative, not per-phase).
3. Session keys MUST be written before the CEO ends a testing session.
4. Topic keys are project-scoped (`project: "The-Embedinator"`).
