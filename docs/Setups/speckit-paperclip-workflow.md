# Speckit + Paperclip: Complete Feature Execution Workflow

A production guide for senior developers running AI-assisted feature delivery using the two-layer model: Speckit for planning, Paperclip for execution.

---

## Table of Contents

1. [Overview: The Two-Layer Model](#overview-the-two-layer-model)
2. [Phase 1: Planning with Speckit](#phase-1-planning-with-speckit)
3. [Phase 2: The Handoff](#phase-2-the-handoff)
4. [Phase 3: Execution with Paperclip](#phase-3-execution-with-paperclip)
5. [Phase 4: Board Duties](#phase-4-board-duties)
6. [Phase 5: Verification and Archive](#phase-5-verification-and-archive)
7. [CEO Briefing Prompt Template](#ceo-briefing-prompt-template)
8. [Monitoring Cheatsheet](#monitoring-cheatsheet)
9. [Comparison: Agent Teams vs Paperclip](#comparison-agent-teams-vs-paperclip)
10. [Gotchas and Tips](#gotchas-and-tips)

---

## Overview: The Two-Layer Model

The core insight: **planning and execution are different problems that require different tools**.

Speckit is a spec-driven planning framework that runs inside Claude Code. It produces structured artifacts — specifications, architectural designs, task checklists — before a single line of code is written. It answers the question: *what needs to be built, why, and how?*

Paperclip is a self-hosted AI agent orchestration platform. It manages a persistent company of AI agents — each with a role, a model, a budget, and a heartbeat schedule. It answers the question: *who builds it, in what order, and are we on track?*

The boundary between them is `tasks.md`. Everything before it is Speckit's domain. Everything after it is Paperclip's.

```
┌─────────────────────────────────────────────────────────────────┐
│                        PLANNING LAYER                           │
│                          (Speckit)                              │
│                                                                 │
│  /speckit.specify → /speckit.plan → /speckit.design             │
│                         ↓                                       │
│                   /speckit.tasks                                │
│                         ↓                                       │
│                      tasks.md  ◄── HANDOFF POINT                │
└─────────────────────────────────────┬───────────────────────────┘
                                      │
                          /speckit.taskstoissues
                          or CEO reads tasks.md
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                       EXECUTION LAYER                           │
│                         (Paperclip)                             │
│                                                                 │
│  CEO creates issues → assigns agents → heartbeats run           │
│                                                                 │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ backend- │  │frontend- │  │ devops-  │  │quality-  │        │
│  │architect │  │architect │  │architect │  │engineer  │        │
│  │ (async)  │  │ (async)  │  │ (async)  │  │ (async)  │        │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘        │
│                                                                 │
│  Board (you) approves hires, unblocks decisions                 │
└─────────────────────────────────────┬───────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     VERIFICATION LAYER                          │
│                          (Speckit)                              │
│                                                                 │
│  /speckit.verify → /speckit.archive                             │
└─────────────────────────────────────────────────────────────────┘
```

**Why this split?** Speckit runs in your Claude Code session, which has full project context, your CLAUDE.md conventions, and your architecture memory. That context is exactly what you need for planning. Paperclip agents run independently and persistently — they survive session endings, can run in true parallel, and maintain their own memory. That independence is exactly what you need for execution.

---

## Phase 1: Planning with Speckit

Run all speckit commands inside Claude Code. Each command produces artifacts in `specs/<feature-name>/`.

### Step 1.1 — Write the Specification

```
/speckit.specify <feature-name>
```

**What it does**: Elicits and documents user stories, acceptance scenarios, bug registries, constraints, and out-of-scope items. Runs an interactive dialogue to surface ambiguities before they become implementation bugs.

**Produces**: `specs/<feature-name>/spec.md`

**Contents**:
- Feature summary and motivation
- User stories with numbered acceptance scenarios (Given/When/Then format)
- Non-functional requirements
- Explicit out-of-scope boundaries
- For bug-fix specs: a bug registry table with severity, layer, and summary

**When to move on**: The spec is complete when every user story has at least one acceptance scenario with a clear, independently testable criterion. If you cannot answer "how will I know this is done?", do not proceed.

**Real example** (`specs/024-chat-fix/spec.md`):
```
| ID      | Severity    | Layer    | Summary                                     |
|---------|-------------|----------|---------------------------------------------|
| BUG-013 | P0-CRITICAL | Frontend | Chat response text never renders            |
| BUG-014 | P1-HIGH     | Frontend | Sidebar "New Chat" button does not clear    |
| BUG-016 | P1-HIGH     | Backend  | Call limit callback using wrong defaults    |
```

---

### Step 1.2 — Create the Plan and Design

```
/speckit.plan
/speckit.design
```

**What it does**: Translates requirements into an architectural approach. `plan` produces the high-level approach and phased execution strategy. `design` produces detailed technical decisions, component contracts, and data models.

**Produces**:
- `specs/<feature-name>/plan.md` — execution approach, phases, agent assignments, risk areas
- `specs/<feature-name>/design.md` — component interfaces, data flow, implementation decisions
- `specs/<feature-name>/research.md` — if research was performed during planning
- `specs/<feature-name>/data-model.md` — schema changes, type definitions, state shapes
- `specs/<feature-name>/contracts/` — interface contracts between components

**When to move on**: Design is complete when you can answer: what files change, what interfaces are affected, and what can be done in parallel.

**Tip**: For complex features, review `data-model.md` and `contracts/` before generating tasks. Errors in contracts propagate into every downstream task.

---

### Step 1.3 — Generate the Task Checklist

```
/speckit.tasks
```

**What it does**: Reads `spec.md`, `plan.md`, `design.md`, and all contracts. Produces an ordered, dependency-mapped task checklist. Tasks are tagged with parallelism indicators `[P]`, agent assignments `[Agent]`, and story references `[US1]`.

**Produces**: `specs/<feature-name>/tasks.md`

**Key properties of well-formed tasks**:
- Each task has an ID (`T001`, `T002`, ...)
- Blocked tasks explicitly reference their dependency (`depends on T014`)
- Parallel tasks are marked `[P]` — these become concurrent Paperclip issues
- Agent assignments indicate which specialist should own the task
- File paths are explicit, not implied

**Real example** (`specs/024-chat-fix/tasks.md`):
```markdown
## Phase 1: Setup (Environment Verification)

- [x] T001 [Orchestrator] Verify all 4 Docker containers are healthy
- [x] T002 [Orchestrator] Verify backend health endpoint
- [ ] T006 [Navigator] Navigate to http://localhost:3000/chat and take screenshot

## Phase 3: User Story 1 — Chat Response Rendering

- [ ] T018 [P] [A1] Fix NDJSON stream reader in frontend/components/ChatHistory.tsx
- [ ] T019 [P] [A2] Fix call limit defaults in backend/agent/nodes.py
```

**When to move on**: Tasks.md is the contract between planning and execution. Review it carefully — every ambiguity here costs a blocked Paperclip issue later.

---

## Phase 2: The Handoff

This is where tasks.md becomes work items in Paperclip. You have two paths.

### Path A — Automated via `/speckit.taskstoissues`

```
/speckit.taskstoissues
```

This command reads `tasks.md` and converts each task into a Paperclip issue via the API. It preserves:
- Task IDs and descriptions
- Dependency chains (via `parentId`)
- Phase groupings (via labels or milestones)
- Parallel indicators (all `[P]` tasks get `backlog` status simultaneously)

Use this path when your tasks.md is clean and the task structure maps directly to work items without needing CEO-level strategy decomposition.

### Path B — CEO Briefing (recommended for complex features)

Skip `taskstoissues` and brief the CEO agent directly. The CEO reads `tasks.md`, understands the architecture, and creates issues with proper context. This is better when:

- Tasks require judgment about agent assignments
- Some tasks need to be split or merged before becoming issues
- You want the CEO to own the strategy and surface risks proactively

See the [CEO Briefing Prompt Template](#ceo-briefing-prompt-template) section for the exact format.

### After Either Path: Verify Issues Exist

```bash
npx paperclipai issue list -C d7b07693-6463-413a-9690-0ef8feec4005
```

Confirm:
- Issues exist for every task group (not necessarily 1:1 with tasks)
- Dependency chains are set (`parentId` populated)
- Agents are assigned to issues that have clear ownership
- Backlog vs todo status is correct (todo = ready to pick up, backlog = blocked)

---

## Phase 3: Execution with Paperclip

### Paperclip Concepts You Must Know

**Company**: The project. Every agent and issue belongs to a company.
- The Embedinator company ID: `d7b07693-6463-413a-9690-0ef8feec4005`

**CEO agent**: The top-level AI agent. Owns strategy, creates issues, assigns work, escalates to Board.
- CEO agent ID: `098ecb35-30a9-43fa-b76f-89ebd42a7833`
- Model: `claude-opus-4-6`

**Issue lifecycle**:
```
backlog → todo → in_progress → in_review → done
                              ↘ blocked
```

**Heartbeat**: How agents wake up and do work. Every agent runs a 9-step cycle:
1. Read identity and context
2. Check pending approvals
3. Get current assignments
4. Pick the highest-priority available issue
5. Atomic checkout (409 = already owned, STOP)
6. Understand the full context of the issue
7. Do the work
8. Update issue status and add comments
9. Delegate if needed

**Atomic checkout**: Only one agent can own an issue at a time. If `checkout` returns 409, that issue is already in progress. Never retry or force-checkout.

---

### Step 3.1 — Brief the CEO

Trigger a CEO heartbeat and provide the briefing:

```bash
npx paperclipai heartbeat run -a 098ecb35-30a9-43fa-b76f-89ebd42a7833
```

This streams live output. The CEO will read its context, check for pending items, and pick up your briefing. Use the template in Section 7.

---

### Step 3.2 — CEO Creates Issues and Assigns Agents

The CEO will:
1. Read `specs/<feature-name>/tasks.md`
2. Create issues for each logical work unit
3. Assign issues to appropriate specialist agents
4. Set dependencies (`parentId`) for sequential tasks
5. Move independent tasks to `todo` simultaneously (this triggers parallel execution)

You do not need to do any of this manually. Watch the CEO's heartbeat output to confirm it happened correctly.

---

### Step 3.3 — Approve Agent Hires (if needed)

Because `requireBoardApprovalForNewAgents=true`, the CEO cannot activate new agents without Board approval.

Check for pending approvals:

```bash
npx paperclipai approval list -C d7b07693-6463-413a-9690-0ef8feec4005
```

Review each approval request. It will include the proposed agent name, role, model, and budget. Approve:

```bash
npx paperclipai approval approve <approval-id>
```

All 20 agents for The Embedinator are already hired, so this step is only needed if the CEO proposes a new specialist.

---

### Step 3.4 — Trigger Parallel Agent Heartbeats

Once issues are assigned, trigger heartbeats for the agents that have active work:

```bash
# Trigger individual agents
npx paperclipai heartbeat run -a <agent-id>

# For parallel phases, run these in separate terminal windows
# Window 1:
npx paperclipai heartbeat run -a <backend-architect-id>

# Window 2:
npx paperclipai heartbeat run -a <frontend-architect-id>

# Window 3:
npx paperclipai heartbeat run -a <devops-architect-id>
```

Each `heartbeat run` streams that agent's live output. Unlike Agent Teams, there is no tmux required — you can open separate terminal tabs or let agents run on their own schedules.

**Note**: Agents with cron schedules wake up automatically every 30 seconds. For immediate work, use `heartbeat run` to force a cycle now.

---

### Step 3.5 — Monitor Progress

```bash
# Dashboard overview
npx paperclipai dashboard get -C d7b07693-6463-413a-9690-0ef8feec4005

# All issues and their current status
npx paperclipai issue list -C d7b07693-6463-413a-9690-0ef8feec4005

# Recent activity across all agents
npx paperclipai activity list -C d7b07693-6463-413a-9690-0ef8feec4005
```

The dashboard shows:
- Issues by status (backlog / todo / in_progress / in_review / done)
- Agent activity and cost burn
- Pending approvals
- Blocked items requiring intervention

---

### How Parallelism Works

This is the key difference from Agent Teams.

In Agent Teams, you manually spawned subprocesses in tmux panes and managed their lifecycle. When your Claude Code session ended, those agents died.

In Paperclip:
- Each agent is a persistent entity with its own identity, memory, and heartbeat schedule
- When the CEO moves multiple issues to `todo` simultaneously, any available agent can pick up work
- Agents run their heartbeat cycles independently — no coordination layer needed
- A `backend-architect` and `frontend-architect` can work in parallel on different issues without any tmux setup
- Dependencies are enforced by issue status: an agent cannot check out an issue whose `parentId` issue is still `in_progress`

```
CEO creates issues:
  Issue A (todo) ─── no parent ──► backend-architect picks up
  Issue B (todo) ─── no parent ──► frontend-architect picks up
  Issue C (backlog) ─ parentId=A ─► stays blocked until A is done
  Issue D (todo) ─── no parent ──► devops-architect picks up

All three run at the same time. Issue C unblocks when A moves to done.
```

---

## Phase 4: Board Duties

You are the Board. Your role is governance, not execution. Agents handle the work; you handle the decisions.

### When You Must Intervene

**1. Pending approvals**

Check regularly:
```bash
npx paperclipai approval list -C d7b07693-6463-413a-9690-0ef8feec4005
```

Approve or reject hire requests and strategy changes promptly. Agents that are waiting on Board approval will not make progress.

**2. Blocked issues**

When an issue has status `blocked`, an agent has determined it cannot proceed without input. Read the issue comments to understand what it needs:

```bash
npx paperclipai issue list -C d7b07693-6463-413a-9690-0ef8feec4005
# Filter for blocked status, then:
npx paperclipai issue comment <issue-id>
```

Unblock by adding a comment to the issue with the decision or information. An `@mention` in the comment triggers the assigned agent's heartbeat immediately.

**3. In-review issues**

When an agent moves an issue to `in_review`, it has completed the work and is asking for your sign-off. Review the changes (check the git diff or the agent's summary in the issue comment), then either:
- Comment with approval → agent moves to `done`
- Comment with requested changes → agent moves back to `in_progress`

**4. Budget alerts**

Check the cost summary periodically on long-running features:
```bash
npx paperclipai dashboard get -C d7b07693-6463-413a-9690-0ef8feec4005
```

If an agent is burning through its monthly budget unexpectedly, pause it and investigate:
- Is it stuck in a loop?
- Is it doing work that should belong to another agent?
- Is the task scoped correctly?

### What You Do NOT Need to Do

- Manually coordinate agents — the CEO handles this
- Manage tmux panes or terminal sessions
- Restart agents after your session ends — they continue on heartbeat schedules
- Track which agent is working on what — the dashboard shows this

---

## Phase 5: Verification and Archive

Once all Paperclip issues are `done`, return to Claude Code for the final two steps.

### Step 5.1 — Verify Implementation

```
/speckit.verify
```

This command reads your `spec.md` acceptance scenarios and systematically checks that each one passes. It can run automated checks (curl commands, test execution) and browser verification for UI scenarios.

**What it checks**:
- Each acceptance scenario from `spec.md`
- That no spec contracts were violated
- That the implementation matches the design from `plan.md` and `design.md`
- That performance budgets (if specified) are met

**Output**: A verification report in `specs/<feature-name>/` indicating which scenarios pass and which fail with specific evidence.

Do not archive until all P0 and P1 scenarios pass. P2/P3 failures can be documented as known gaps if there is a clear reason to defer them.

### Step 5.2 — Archive the Spec

```
/speckit.archive
```

This command:
- Marks the spec as complete
- Moves artifacts to an archive location
- Updates any cross-references in the project constitution
- Records the feature as shipped in the project memory

After archiving, run `npx gitnexus analyze` to update the code intelligence index with the new symbols introduced by the feature.

---

## CEO Briefing Prompt Template

Use this template whenever you trigger a CEO heartbeat to start a new feature. Paste it as a comment on the company's primary issue board, or deliver it directly via `heartbeat run`.

```
You are the CEO of The Embedinator (company ID: d7b07693-6463-413a-9690-0ef8feec4005).

A new feature spec is ready for execution. Your job is to read the planning artifacts,
create Paperclip issues, assign them to the right specialist agents, and manage execution.

## Feature
Name: <feature-name>
Branch: <git-branch-name>
Priority: <P0-CRITICAL | P1-HIGH | P2-MEDIUM>

## Planning Artifacts
All artifacts are in: specs/<feature-name>/
- spec.md        — user stories and acceptance scenarios (READ THIS FIRST)
- plan.md        — execution approach and agent assignments
- design.md      — technical decisions and component interfaces
- tasks.md       — ordered, dependency-mapped task checklist (THIS IS YOUR WORK ORDER)
- data-model.md  — schema and type changes (if present)
- contracts/     — interface contracts between components (if present)

## Your Tasks
1. Read spec.md to understand what success looks like
2. Read tasks.md to understand the work breakdown
3. Create Paperclip issues for each phase/task group
4. Set parentId dependencies for sequential tasks
5. Assign issues to appropriate agents based on the [Agent] tags in tasks.md
6. Move all unblocked issues (no parentId, or parentId is done) to todo status
7. Trigger heartbeats for assigned agents to start parallel work

## Agent Roster (all active, all claude_local)
- backend-architect, python-expert — backend Python/FastAPI/LangGraph work
- frontend-architect — Next.js/React/TypeScript/Tailwind work
- devops-architect — Docker, CI/CD, infrastructure
- quality-engineer — testing, verification, validation
- security-engineer — security review
- performance-engineer — performance analysis
- technical-writer — documentation
- deep-research-agent — research tasks requiring web search or library docs

## Constraints
- Do NOT modify the Makefile — it is frozen
- Do NOT create new Python dependencies without Board approval
- Run impact analysis (gitnexus_impact) before modifying any existing symbol
- The active git branch is <git-branch-name> — all work happens on this branch

## Board Contact
Add a comment mentioning @Board for any decision that blocks progress.
The Board reviews approvals and comments every 30 minutes during working hours.

Begin by reading specs/<feature-name>/spec.md.
```

---

## Monitoring Cheatsheet

All commands use the company ID: `d7b07693-6463-413a-9690-0ef8feec4005`

### Status Overview

```bash
# Full dashboard (issues, agents, costs, approvals at a glance)
npx paperclipai dashboard get -C d7b07693-6463-413a-9690-0ef8feec4005

# All issues with current status
npx paperclipai issue list -C d7b07693-6463-413a-9690-0ef8feec4005

# Recent activity log across all agents
npx paperclipai activity list -C d7b07693-6463-413a-9690-0ef8feec4005

# All agents and their current status
npx paperclipai agent list -C d7b07693-6463-413a-9690-0ef8feec4005
```

### Approvals

```bash
# Check for pending Board approvals
npx paperclipai approval list -C d7b07693-6463-413a-9690-0ef8feec4005

# Approve a specific request
npx paperclipai approval approve <approval-id>

# Reject a request with reason
npx paperclipai approval reject <approval-id>
```

### Agent Control

```bash
# Trigger a specific agent's heartbeat (streams live output)
npx paperclipai heartbeat run -a <agent-id>

# CEO heartbeat (use to deliver briefings or unblock strategy)
npx paperclipai heartbeat run -a 098ecb35-30a9-43fa-b76f-89ebd42a7833

# Get full agent details including current assignment
npx paperclipai agent get <agent-id>
```

### Issue Management

```bash
# Get a single issue with full details
npx paperclipai issue get <issue-id>

# Read comments on a blocked issue
npx paperclipai issue comment <issue-id>

# Update issue status manually (use sparingly — agents should own this)
npx paperclipai issue update <issue-id>

# Add a comment to unblock an agent (use @agent-name to trigger heartbeat)
npx paperclipai issue comment <issue-id> --message "Decision: use approach B. @backend-architect please proceed."
```

### Costs

```bash
# Summary cost view in the dashboard
npx paperclipai dashboard get -C d7b07693-6463-413a-9690-0ef8feec4005

# Per-agent cost breakdown via API
curl http://localhost:3100/api/companies/d7b07693-6463-413a-9690-0ef8feec4005/costs/by-agent
```

### Health

```bash
# Verify Paperclip is healthy
npx paperclipai doctor

# Verify server is responding
curl http://localhost:3100/api/health
```

---

## Comparison: Agent Teams vs Paperclip

| Dimension | Agent Teams (old) | Paperclip (new) |
|---|---|---|
| **Lifespan** | Dies when Claude Code session ends | Persistent — survives session end, machine restart |
| **Parallelism** | Manual: spawn N tmux panes | Automatic: agents pick up issues independently on heartbeat |
| **Coordination** | You manage pane-by-pane | CEO manages issue assignment |
| **Setup overhead** | High: TeamCreate, TaskCreate, tmux pane per agent | Low: issue list, heartbeat run |
| **Agent memory** | Ephemeral — dies with context | Persistent — each agent has its own identity and memory |
| **Blocking work** | You wait for each wave to complete | Agents run async; you check dashboard periodically |
| **Error recovery** | Rerun the failed agent manually | Agent marks issue blocked; Board unblocks via comment |
| **Dependency tracking** | Manual: next wave waits for previous | Automatic: parentId prevents checkout until parent is done |
| **Cost tracking** | None | Per-agent cost breakdown, monthly budgets |
| **Governance** | None | Board approvals for hires and strategy changes |
| **Task visibility** | Scattered across tmux panes | Centralized issue list with status history |
| **Interruption handling** | Session end = lost work | In-progress issues resume on next heartbeat |
| **Speckit integration** | /speckit.implement calls agents inline | /speckit.taskstoissues bridges to Paperclip |
| **Scaling** | 4–8 agents before tmux becomes unwieldy | 20+ agents, unlimited issues |

### When Agent Teams is still appropriate

Agent Teams may still be useful for:
- Single-shot, low-stakes tasks that finish in one session
- Research tasks where you want to watch every step in real time
- Debugging sessions where tight human supervision matters more than parallelism

For any feature delivery — spec execution, multi-file changes, or work that spans hours — use Paperclip.

---

## Gotchas and Tips

### Speckit Phase

**Do not rush tasks.md.** The quality of `tasks.md` directly determines how much rework agents do. A vague task description like "fix the chat component" generates questions and blocks. A specific description like "Fix NDJSON stream reader in `frontend/components/ChatHistory.tsx` — the `getReader()` loop is not appending to state correctly" generates a working fix on the first heartbeat.

**Contracts before tasks.** If your feature touches interfaces between components (API contracts, TypeScript types, state shapes), generate `contracts/` before running `/speckit.tasks`. Agents that work on different sides of an interface need to agree on the contract upfront, not discover it mid-implementation.

**Name phases, not just tasks.** Tasks.md phases become natural gate points. Name them clearly: `Phase 1: Setup`, `Phase 2: Investigation`, `Phase 3: Fix`. The CEO uses phase structure to sequence issue creation.

---

### Handoff Phase

**The CEO needs to read the right files.** The briefing template specifies exactly which files to read and in what order. Do not condense the spec into the briefing — let the CEO read the authoritative files. Inline summaries drift from the actual spec.

**Set the branch explicitly in the briefing.** Agents run Claude Code under the hood. If the working directory is on the wrong branch, every file edit goes to the wrong place. Always include the branch name in the CEO briefing.

**Check parentId after issue creation.** The most common issue with automated task-to-issue conversion is that dependencies are not set correctly. Run `issue list` and verify that tasks marked `[depends on T014]` in tasks.md have the corresponding `parentId` set in Paperclip.

---

### Execution Phase

**Atomic checkout is a hard constraint.** If an agent's heartbeat returns a 409 on checkout, that means another agent already owns the issue. Do not manually override the status. Do not re-trigger the agent. The original owner will complete the work and move status. The blocked agent will pick up its next available issue.

**Comments with @mention are how you unblock agents.** When an issue is `blocked`, the agent is waiting for you. Add a comment to the issue with your decision and `@agent-name`. This triggers an immediate heartbeat for that agent — you do not need to manually call `heartbeat run`.

**Run heartbeat in watch mode for live debugging.** If you are troubleshooting a specific agent (wrong output, unexpected behavior), run:
```bash
npx paperclipai heartbeat run -a <agent-id>
```
This streams the agent's entire thought process in real time. You can watch exactly what it reads, what it decides to do, and what tools it calls.

**Do not trigger heartbeats for agents with no active issues.** An agent with no assigned issues will do nothing useful on a heartbeat cycle but will still consume a small amount of budget. Only trigger heartbeats when you know the agent has work to do.

---

### Board Duties

**Check approvals first, every session.** Before looking at issue progress, run `approval list`. A pending approval can be blocking 5 agents. It takes 10 seconds to approve. Check it first.

**Do not move issues manually unless necessary.** Agents own their issue status. If you manually move an issue to `done` without the agent completing the work, the agent will pick up a new issue and the original work will be half-done. Only move issues manually to unblock a stuck agent that is not making progress.

**Budget review is a weekly task, not per-feature.** Agent costs per feature are typically small. Review the monthly budget dashboard weekly rather than per-feature. If a specific agent is burning unexpectedly high budget mid-feature, that signals a loop or a scoping problem worth investigating immediately.

---

### Verification Phase

**Run `/speckit.verify` before declaring done.** It is easy to look at all issues as `done` in Paperclip and declare the feature shipped. Do not. The issues track execution. `spec.md` tracks correctness. Run verify to confirm the acceptance scenarios actually pass against the live system.

**Re-index GitNexus after every feature.** New symbols introduced by agents do not appear in the code intelligence index until you re-run:
```bash
npx gitnexus analyze
```
The next feature's impact analysis depends on this being current.

**Archive immediately after verify passes.** Do not let completed specs accumulate in `specs/`. Archive removes them from speckit's active scope and prevents accidental confusion with the current feature.

---

## Quick Reference: Full Feature Lifecycle

```
1. /speckit.specify <name>         → specs/<name>/spec.md
2. /speckit.plan                   → specs/<name>/plan.md + design.md
3. /speckit.design                 → specs/<name>/contracts/
4. /speckit.tasks                  → specs/<name>/tasks.md
                                        ↓
5. /speckit.taskstoissues           → Paperclip issues created
   OR: brief CEO via heartbeat run
                                        ↓
6. npx paperclipai approval list   → approve agent hires if needed
7. npx paperclipai heartbeat run   → agents start parallel work
8. npx paperclipai dashboard get   → monitor progress
9. Review blocked issues, add comments with @mention to unblock
                                        ↓
10. All issues reach 'done'
                                        ↓
11. /speckit.verify                → acceptance scenarios checked
12. /speckit.archive               → spec marked complete
13. npx gitnexus analyze           → code index updated
```
