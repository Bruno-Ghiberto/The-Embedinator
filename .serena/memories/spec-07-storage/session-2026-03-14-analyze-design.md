# Spec 07: Storage Architecture — Analyze + Design Session (2026-03-14)

## Status
- speckit.analyze: COMPLETE (13 findings, all fixed)
- 07-implement.md: FULLY REWRITTEN (707 lines)
- Agent instruction files: ALL 5 REWRITTEN
- Ready for: IMPLEMENTATION (Agent Teams with tmux)

## Key Fixes Applied
- CRITICAL: `EMBEDINATOR_SECRET_KEY` → `EMBEDINATOR_FERNET_KEY` across 6 files
- HIGH: query_traces missing `reasoning_steps_json`, `strategy_switches_json` fields
- HIGH: Child chunk size ~300 → ~500 chars (Constitution III)
- HIGH: FR-015 cross-ref to spec-06 for queue ownership
- MEDIUM: UUID5 constraint on Qdrant point IDs, ParentStore unit test task (T164), exports

## Files Modified
- `specs/007-storage-architecture/spec.md` — 5 edits (status, FR-005, SC-010, assumptions, FR-015)
- `specs/007-storage-architecture/plan.md` — 1 edit (complexity tracking cleanup)
- `specs/007-storage-architecture/tasks.md` — 11 edits + T164 new task (164 total)
- `specs/007-storage-architecture/contracts/key-manager-contract.md` — all SECRET_KEY → FERNET_KEY
- `Docs/PROMPTS/spec-07-storage/07-implement.md` — full rewrite
- `Docs/PROMPTS/spec-07-storage/agents/A1-foundation-schema.md` — rewrite
- `Docs/PROMPTS/spec-07-storage/agents/A2-qdrant-storage.md` — rewrite
- `Docs/PROMPTS/spec-07-storage/agents/A3-key-manager.md` — rewrite
- `Docs/PROMPTS/spec-07-storage/agents/A4-integration-wiring.md` — rewrite
- `Docs/PROMPTS/spec-07-storage/agents/A5-quality-polish.md` — rewrite

## Agent Team Configuration
| Agent | subagent_type | Model | Role |
|-------|---------------|-------|------|
| A1 | python-expert | Opus 4.6 | SQLiteDB foundation + schema (7 tables) |
| A2 | backend-architect | Sonnet 4.6 | QdrantStorage (vector DB client) |
| A3 | security-engineer | Sonnet 4.6 | KeyManager (Fernet encryption) |
| A4 | system-architect | Sonnet 4.6 | Integration wiring + lifespan |
| A5 | quality-engineer | Sonnet 4.6 | Regression tests + code review |

## Next Steps
1. Start implementation session with `/sc:load serena and engram`
2. Spawn Agent Teams via tmux multi-pane
3. Follow wave execution: Wave 1 (A1) → Gate → Wave 2 (A2∥A3) → Gate → Wave 3 (A4) → Gate → Wave 4 (A5)
