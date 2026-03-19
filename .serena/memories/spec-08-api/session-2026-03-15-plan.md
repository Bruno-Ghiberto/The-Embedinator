# Spec 08: API Reference — Plan Session (2026-03-15)

## Status
- speckit.specify: COMPLETE
- speckit.clarify: COMPLETE
- **speckit.plan: COMPLETE** — all Phase 0 + Phase 1 artifacts generated
- Next step: `/speckit.tasks`

## Artifacts Generated
- `specs/008-api-reference/plan.md` — complete implementation plan
- `specs/008-api-reference/research.md` — 8 research decisions (R1-R8)
- `specs/008-api-reference/data-model.md` — 8 entities, NDJSON types, error codes
- `specs/008-api-reference/contracts/api-endpoints.md` — full HTTP contract definitions
- `specs/008-api-reference/quickstart.md` — dev setup + testing guide
- `Docs/PROMPTS/spec-08-api/08-plan.md` — improved implementation context prompt (1049 lines)
- `CLAUDE.md` — updated with spec-08 tech stack entry

## Key Research Findings
- R1: 10 NDJSON events map to ConversationGraph astream + final_state
- R2: SQLiteDB missing 5 methods (list_traces, get_trace, get_active_provider, upsert_provider); chat.py should call create_query_trace() directly
- R3: Settings are key-value rows (db.get_setting/set_setting), assembled at read time
- R4: Model listing via direct Ollama httpx (no ProviderRegistry.list_models())
- R5: Switch providers.py to use app.state.key_manager
- R6: Constitution conflicts (event naming, rate limit) resolved by spec authority
- R7: Ingest consolidation — new ingest.py + remove legacy from documents.py
- R8: Collection create schema needs description/embedding_model/chunk_profile + regex

## Agent Team Structure (5 waves, 8 agents)
- Wave 1: A1 (Opus — schemas+config) + A2 (Sonnet — middleware)
- Wave 2: A3 (Opus — chat NDJSON) + A4 (Sonnet — ingest router)
- Wave 3: A5 (Sonnet — documents+collections) + A6 (Sonnet — models+providers+settings)
- Wave 4: A7 (Sonnet — traces+health+wiring)
- Wave 5: A8 (Sonnet — tests+integration+regression)

## Known Issues in Branch (9 total)
1. chat.py: 4 event types, calls missing db methods
2. documents.py: overlapping ingest endpoints
3. providers.py: missing PUT/DELETE /key
4. middleware.py: missing 4th rate limit category, general=100 not 120
5. health.py: missing latency_ms
6. traces.py: calls missing db methods
7. models.py, settings.py: don't exist
8. main.py: missing 3 router registrations
9. SQLiteDB: 5 missing methods
