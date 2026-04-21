# Contract: PaperclipAI Task Format

**Version**: 1.0 | **Spec**: 025-master-debug

## Purpose

Defines how the CEO agent creates and manages tasks in PaperclipAI for Spec-25. Each test task follows a consistent structure so agents can execute autonomously via heartbeat checkout.

## Task Creation Format

When the CEO creates a task in PaperclipAI:

```
Title: [T{NNN}] {Short descriptive title}
Description: |
  ## Context
  - Phase: P{N} ({Phase Name})
  - FR Coverage: {FR-NNN, FR-NNN}
  - Prerequisites: {what must be true before this task}

  ## Instructions
  {Detailed instructions for the assigned agent. Include:}
  - Exact commands to run (for infrastructure/API tasks)
  - Exact payloads to send (for security/edge case tasks)
  - What to observe and how to evaluate (for quality/UX tasks)
  - Expected results (what PASS looks like)

  ## Success Criteria
  - {Concrete, verifiable outcome 1}
  - {Concrete, verifiable outcome 2}

  ## Reporting
  Report results as a task comment with:
  - Status: PASS / FAIL / PARTIAL
  - Evidence: log excerpts, API responses, observations
  - Bugs: BUG-{NNN} entries if issues found (use bug-report template)
  - Notes: any anomalies or observations

Assignee: {Agent ID}
Priority: {LOW / MEDIUM / HIGH / URGENT}
Labels: [spec-25, phase-{N}, {agent-id}]
```

## Task Lifecycle

```
backlog/todo --> in_progress --> done
                            --> cancelled (with explanation in comment)
                            --> blocked (with blocker description)
```

| Conceptual State | PaperclipAI Status | Description |
|------------------|--------------------|-------------|
| OPEN | `backlog` or `todo` | Created by CEO, waiting for agent pickup |
| CHECKED_OUT | `in_progress` | Agent woke up via wakeOnDemand and claimed the task |
| COMPLETED | `done` | Agent finished and posted results as task comment |
| FAILED | `cancelled` | Agent could not complete — explanation in comment |
| BLOCKED | `blocked` | Agent identified an unsatisfied dependency |

- Agents use `wakeOnDemand` — PaperclipAI triggers them instantly on task assignment. No periodic polling.
- Each agent run allows up to **200 turns** (`maxTurnsPerRun`).
- 409 conflict on double-claim (only one agent can work a task at a time).

## Task Naming Convention

| Phase | Task Range | Pattern |
|-------|------------|---------|
| P1: Infrastructure | T001-T007 | `[T00N] Verify {service/component}` |
| P2: Core Functionality | T008-T017 | `[T0NN] Verify {feature} via {API/UI}` |
| P3: Model Matrix | T018-T022 | `[T0NN] {Model action}: {description}` |
| P4: Data Quality | T023-T028 | `[T0NN] Audit {quality dimension}` |
| P5: Chaos Engineering | T029-T034 | `[T0NN] Chaos: {scenario name}` |
| P6: Security | T035-T041 | `[T0NN] Security: {probe name}` |
| P7: UX Journey | T042-T046 | `[T0NN] UX: {audit area}` |
| P8: Regression | T047-T057 | `[T0NN] Regression: {check item}` |
| P9: Performance | T058-T061 | `[T0NN] Perf: {measurement type}` |
| P10: Final Report | T062 | `[T062] Compile final report` |

## Priority Assignment

| Priority | When to use |
|----------|-------------|
| URGENT | Gate-blocking tasks, P0 bug investigation |
| HIGH | Phase-critical tasks (first task in each phase) |
| MEDIUM | Standard test tasks within a phase |
| LOW | Supplementary tasks, detail collection |

## Agent Budget Allocation

| Agent | Budget Level | Rationale |
|-------|-------------|-----------|
| A2 (quality-engineer) | Medium | Most tasks: P2 (14 FRs) + P8 (11 regression items) |
| A3 (performance-engineer) | Medium | P3 (7 combos x 5 queries) + P9 (performance profiling) |
| A1 (DevOps Architect) | Low-Medium | P1 (7 checks) + P5 (6 chaos scenarios) |
| A4 (python-expert) | Low | P4 (6 data quality tasks) |
| A5 (security-engineer) | Low | P6 (7 security probes) |
| A6 (frontend-architect) | Low | P7 (5 UX audit items) |
| A7 (technical-writer) | Low | P10 (1 report compilation task) |
| S1 (Root Cause Analyst) | Minimal | On-demand for complex bugs only |
| S2 (Self Review) | Minimal | 4 gate checks only |
| S3 (CTO) | Minimal | Escalation only (P0/CRITICAL) |

## Agent Invocation Configuration

- **All agents (A1–A7, S1–S3)**: `wakeOnDemand=true` — triggered instantly on task assignment. `maxTurnsPerRun=200`.
- **CEO**: Always active during testing sessions — direct interactive orchestration, not heartbeat-driven.
- **Paused agents**: frontend-architect (A6) and CTO (S3) must be un-paused before execution begins.
