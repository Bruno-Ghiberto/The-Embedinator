# Speckit Workflow Orientation — Session 2026-03-10

## Status
- **Spec 02**: Implementation COMPLETE (52/52 tasks, 147 tests, done in other tmux terminal)
- **Specs 03-17**: Context prompts exist (specify, plan, implement .md files), not yet run through speckit
- **Workflow template**: Updated at `Docs/PROMPTS/workflow.txt` — now 9-step reusable template

## Workflow Improvements Applied
1. Templatized with `{NN}` / `{spec-name}` placeholders (was hardcoded to spec-02)
2. Added Step 7: `/speckit.analyze` — quality gate for cross-artifact consistency
3. Added Step 8: `/sc:design` — agent instruction file creation (was missing, critical for spec-02)
4. Organized into 5 phases: Specify → Plan → Quality Gate → Agent Design → Implement
5. Fixed wording: "agent teams" → "subagent teams" (using subagents, not experimental Agent Teams)
6. Added session guidance: load context first, one spec per session

## Agent Teams vs Subagents Decision
- **Agent Teams** (experimental): NOT recommended for speckit workflow — sequential pipeline with human checkpoints, /speckit.clarify needs direct interaction, coordination overhead exceeds benefit
- **Subagents** (stable): Already proven in spec-02 implementation — better control (subagent_type + model per agent), more reliable, well-designed instruction files
- Agent Teams better suited for: parallel code review, hypothesis-driven debugging, independent module implementation

## Recommended Execution Strategy
### Phase A — Specify+Plan All (while spec-02 implements)
- Batch 1 (agent core): 03, 04, 05
- Batch 2 (infrastructure): 06, 07, 10
- Batch 3 (foundations): 11, 12, 15, 17
- Batch 4 (integration): 08, 13, 16
- Batch 5 (final): 09, 14

### Phase B — Implement in Dependency Order
- Wave 1: 10, 11, 12, 15, 17 (foundations)
- Wave 2: 06, 07, 13 (infrastructure)
- Wave 3: 03 → 04 → 05 (agent layer, sequential)
- Wave 4: 08, 16 (integration)
- Wave 5: 09, 14 (frontend + performance)

## Key Risk: Prompt Drift
Late specs (14-17) context prompts will drift from codebase reality. Re-run /sc:improve step close to implementation time, not months in advance.
