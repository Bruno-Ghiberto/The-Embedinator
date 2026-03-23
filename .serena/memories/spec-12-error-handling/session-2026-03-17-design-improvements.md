# Spec 12: Error Handling — Agent Files Redesign (2026-03-17)

## Status
- 12-implement.md improved (tmux mandatory at top, spawn protocol updated, exact model IDs)
- All 4 agent instruction files rewritten with briefing protocol + MCP tool sections

## Key Changes Made

### 12-implement.md
1. `[!IMPORTANT]` tmux mandatory block moved to very top (first element after title)
2. Spawn prompt changed: `"...await further instructions."` (not "execute all assigned tasks")
3. Agent Teams docs reference: https://code.claude.com/docs/en/agent-teams
4. Exact model IDs: `claude-opus-4-6` / `claude-sonnet-4-6`

### Agent Instruction Files Pattern (new standard for all 4 agents)
1. `## This Is Your Briefing File` — explains spawn protocol, readiness signal, SendMessage handshake
2. `## Agent Configuration` — explicit subagent_type + model ID
3. `## MCP Tools Available` — scoped tool table per agent

### Readiness Signal Protocol (NEW)
Each agent reads its briefing file, then posts:
- A1: `"A1 ready -- briefing complete"`
- A2: `"A2 ready -- briefing complete"`
- A3: `"A3 ready -- briefing complete"`
- A4: `"A4 ready -- briefing complete"`
Orchestrator then sends tasks via `SendMessage`.

### Agent Assignments (confirmed)
| Agent | subagent_type | model |
|-------|--------------|-------|
| A1 (Audit) | `quality-engineer` | `claude-opus-4-6` |
| A2 (Handlers) | `python-expert` | `claude-sonnet-4-6` |
| A3 (Tests) | `python-expert` | `claude-sonnet-4-6` |
| A4 (Regression) | `quality-engineer` | `claude-sonnet-4-6` |

### MCP Tool Assignments (per agent)
- A1: serena (find_symbol, get_symbols_overview) + gitnexus (context, impact, query)
- A2: serena (symbol verify) + gitnexus (impact on create_app)
- A3: serena (find_symbol, overview) + sequential-thinking (test structure planning)
- A4: serena (final sanity check) + gitnexus (detect_changes before final report)

## Unchanged
- All task content (T001-T040) preserved exactly
- Handler code examples unchanged
- Test protocol unchanged (always zsh scripts/run-tests-external.sh)
- Gate checkpoint structure unchanged
