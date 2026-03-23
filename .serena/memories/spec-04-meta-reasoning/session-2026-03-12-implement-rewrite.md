# Session 2026-03-12: 04-implement.md Agent Teams Rewrite

## What Was Done
Rewrote the Agent Team Orchestration Protocol in `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` to use the official Claude Code Agent Teams API with tmux split-pane spawning.

## Key Changes
1. **Moved orchestration to top of file** — now the FIRST section after the title (lines 3-175), before Implementation Scope. Critical that the orchestrator reads this before any code specs.
2. **Replaced generic spawn commands** with full 5-step Agent Teams protocol:
   - Step 1: Create team (`"spec04-meta-reasoning"`)
   - Step 2: Create tasks with wave dependency chain in shared task list
   - Step 3: Spawn teammates per wave (each gets own tmux pane)
   - Step 4: Checkpoint gates (lead verifies after each wave)
   - Step 5: Shutdown and cleanup
3. **Added prerequisites**: tmux requirement + `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` enablement
4. **Added architecture table**: lead, teammates, task list, mailbox roles
5. **Added 8 orchestration rules**: checkpoint discipline, SendMessage steering, plan approval for A5, file-conflict avoidance, model selection (Opus for A2/A5, Sonnet for rest), tmux monitoring, failure recovery
6. **Plan approval for A5**: integration agent modifies existing files, so lead must review plan before edits

## File Location
- `Docs/PROMPTS/spec-04-meta-reasoning/04-implement.md` (912 → ~1010 lines after rewrite)

## Agent Teams API Reference
- Enable: `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in settings.json or env
- tmux auto-detection: `teammateMode: "auto"` (default) spawns split panes when already in tmux
- Teammates load CLAUDE.md automatically but NOT lead's conversation history
- Task dependencies: blocked tasks auto-unblock when dependencies complete
- File locking prevents race conditions on task claiming
- No nested teams (teammates cannot spawn their own teams)
