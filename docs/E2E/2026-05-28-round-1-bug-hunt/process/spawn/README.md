# Spec-30 Hunt — Teammate Spawn Documents

Per-teammate boot contracts for team `spec30-hunt`. The Lead spawns each teammate with a minimal
prompt pointing at its spawn document; the document composes everything the teammate must read,
load, and pin before its first idle.

## Why these exist

The A1–A5 instruction files (`docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/`) are **role manuals**
written 2026-05-15 — they define workflow, tools allowlists, and output templates, and they remain
authoritative for that. But they predate the SDD redesign (2026-06-02) and Phase-1 execution, so
they know nothing about: the fixed `2026-05-28` session directory, the current bug-ID cursor,
Phase-2 baselines/errata, or the per-teammate engram contexts checkpointed at pause. Per the
official Agent Teams docs (https://code.claude.com/docs/en/agent-teams), team state
(`~/.claude/teams/`) is deleted when the session ends — teammates are ALWAYS respawned cold and
must be re-briefed from durable files + engram. These spawn documents are that briefing.

## Precedence (every teammate must apply this)

1. **Spawn document** (this directory) — current state, pins, overrides
2. **Engram team-context** (`sdd/single-round-bug-hunt/team-context/<name>`) — working methods + pause state
3. **Instruction file** (A1–A5) — role workflow, tools allowlist, output templates
4. `specs/030-e2e-test-v3/` spec + playbook + data-model + contracts — the hunt's law
5. `CLAUDE.md` — project standards (auto-loaded)

Conflicts resolve upward: a newer layer overrides an older one. Known overrides are listed
explicitly in each spawn doc (§ Overrides).

## Lead invocation pattern (Agent tool)

One `Agent` call per teammate, all three in ONE response (parallel spawn):

```
Agent(
  team_name: "spec30-hunt",
  name: "<teammate-name>",
  subagent_type: "<per roster>",
  model: "sonnet",
  prompt: "You are <name> on team spec30-hunt. Project root:
    <repo-root>.
    Read docs/E2E/2026-05-28-round-1-bug-hunt/process/spawn/spawn-<name>.md FIRST and follow it
    exactly — it is your boot contract. Do not act before completing its boot sequence."
)
```

Roster is LOCKED (R-005): 3 always-on + 2 on-demand. No additions, removals, or model swaps.

| Teammate | subagent_type | model | spawn doc |
|---|---|---|---|
| `log-analyst` | python-expert | sonnet | `spawn-log-analyst.md` |
| `frontend-inspector` | frontend-architect | sonnet | `spawn-frontend-inspector.md` |
| `bug-registrar` | technical-writer | sonnet | `spawn-bug-registrar.md` |
| `root-cause-investigator` (on-demand) | root-cause-analyst | **opus** | §below |
| `inline-fixer` (on-demand) | architect | sonnet | §below |

## On-demand teammates (spawned per episode, shut down after)

**`root-cause-investigator`** — spawned only when log-analyst AND frontend-inspector both report
"no evidence" or a finding is cross-layer. Spawn prompt: identity + read
`docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A4-root-cause-investigator-instructions.md` + the
specific BUG-ID/observation under investigation + the two teammates' findings verbatim + the state
pins from any always-on spawn doc §State Pins. Read-only. Shut down via `shutdown_request` after
its hypothesis is routed to bug-registrar.

**`inline-fixer`** — spawned only inside a BLOCKER-PATCHED gate episode (lead-prompt §5; all four
preconditions met, bug already registered). Spawn prompt: identity + read
`docs/E2E/2026-05-28-round-1-bug-hunt/process/agents/A5-inline-fixer-instructions.md` + the BUG-ID + **"Require
plan approval before making any changes."** Plan must state exact file, ≤20-line diff sketch,
MINOR|COSMETIC scope, ≤5 min, zero-risk argument. Shut down after the episode (Y or N).

## Maintenance

When a phase closes, the pause-state facts in these docs go stale. The Lead updates the
**§ State Pins** section of all three always-on docs at every overnight pause / phase boundary
(or regenerates them from the apply-progress checkpoint). Everything else is stable.
