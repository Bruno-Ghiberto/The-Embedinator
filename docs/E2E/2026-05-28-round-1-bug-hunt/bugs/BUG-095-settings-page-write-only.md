# BUG-095: Settings page is write-only — no setting is ever read at runtime

- **Severity**: CRITICAL
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:22:13Z in Phase 5 (P5-S3)
- **Phase scenario**: P5-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Settings > Models, change chat model qwen2.5:7b -> qwen3:14b, Save.
2. Toast reads "Settings saved successfully".
3. `sqlite3 data/embedinator.db "SELECT value FROM settings WHERE key='default_llm_model'"` -> qwen3:14b.
4. `GET /api/settings` -> qwen3:14b.
5. Send one chat.
6. `SELECT llm_model FROM query_traces ORDER BY created_at DESC LIMIT 1` -> qwen2.5:7b. The old model ran.

## Expected
A saved setting should be read and applied by the runtime it governs.

## Actual
The setting persists to SQLite and reads back correctly from the API, but nothing at runtime ever consumes it. The old value keeps running indefinitely.

## Artifacts
- Screenshot: screenshots/BUG-095-settings-saved-no-effect.png (gitignored)
- Log excerpt: logs/BUG-095-settings-write-only.log (gitignored)
- Trace: null
- Public evidence: public-evidence/BUG-095-settings-write-only.log (tracked)

## Root-cause hypothesis
The DB `settings` table and the `backend.config.settings` Pydantic singleton are two disconnected systems with no bridge in either direction.
- `backend/config.py:104` `settings = Settings()` — the only instantiation anywhere, built at import time from env/defaults.
- `backend/api/settings.py:52` PUT persists ONLY via `await db.set_setting(key, str(value))` at :73-78. It never mutates the singleton.
- `grep -rn "get_setting(\|list_settings(" backend/ --include="*.py"` excluding `storage/sqlite_db.py` and `api/settings.py` returns ZERO hits. Nothing outside the settings router ever reads the table.
- `backend/main.py` contains ZERO settings-table calls. It neither seeds the DB from config at boot nor seeds config from the DB. A restart does not help.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/158
- **Rationale**: Nothing outside the settings router ever reads the settings table, so seven load-bearing knobs are inert — including groundedness_check_enabled, which a user believes disables an entire verification stage when it only writes a row; the deception is structural rather than a false string.

## Notes
All seven keys are load-bearing runtime consumers, not decoration — this raises severity rather than lowering it:
- `default_llm_model` — 10 read sites (main.py x2, providers/registry.py x5, api/providers.py, api/chat.py, api/health.py)
- `default_embed_model` — 7 read sites (main.py, ingestion/embedder.py, api/health.py, api/chat.py, api/collections.py, providers/registry.py x2)
- `confidence_threshold` — `agent/research_edges.py:36` `threshold = settings.confidence_threshold / 100`; gates the research-loop continue/decline decision
- `groundedness_check_enabled` — `agent/nodes.py:509` `if not settings.groundedness_check_enabled:`; on/off switch for an entire verification stage
- `citation_alignment_threshold` — `agent/nodes.py:669`
- `parent_chunk_size` / `child_chunk_size` — `ingestion/chunker.py:37-38`

Frontend (verified independently): all 7 keys have exactly one control each and no orphans in either direction — Models tab owns default_llm_model (settings/page.tsx:87-96) and default_embed_model (:105-114); Inference owns confidence_threshold (:145-162), groundedness_check_enabled (:171-177, a checkbox), citation_alignment_threshold (:184-201); System owns parent_chunk_size (:232-247) and child_chunk_size (:256-271). All three tabs share ONE `useForm<Settings>()` and ONE `onSubmit`, so every save round-trips the full 7-field object.

Why CRITICAL, and the framing matters: an initial framing ("the UI confirms a lie") was imprecise and was corrected. `settings/page.tsx:35-44` does `await updateSettings(data); toast.success('Settings saved successfully')`. That toast is TRUE: the write did succeed. There is no read-back inside `onSubmit` (zero `reset()`/`mutate()`/`getSettings()` calls there). But `useForm`'s `defaultValues: async () => getSettings()` (:30-32) runs at mount, so RELOADING Settings displays the saved value, read from the database. Save, see the toast, reload, see qwen3:14b. Every individual thing the user observes is accurate. Nothing they observe is connected to anything. The deception is structural, not a false string: persistence is presented as configuration. That is harder to catch than a control that visibly fails, not easier. Seven load-bearing knobs — one of which toggles an entire verification pipeline stage — are inert, with no workaround and no restart remedy. A user who disables `groundedness_check_enabled` believes they turned off a verification stage. They wrote a row.

Corroborating orphans (see the orphaned-contract audit session-log entry): `SQLiteDB.get_setting()` (sqlite_db.py:580) has ZERO production callers, not even from its own router, which uses the plural `list_settings()`. `SQLiteDB.delete_setting()` (sqlite_db.py:597) has zero production callers and no `DELETE /api/settings` route exists.

Never built, not regressed: `backend/api/settings.py` first appears in `01b253e`, the commit where the entire backend entered version control (679 files, +121,211/-11,138; `backend/` did not exist at its parent `5f1fbb1`). Only `8bb53b8` (ruff format) and `3a5fe6b` (mypy fix) have touched it since. No wiring was ever added and removed.

Dedup-check performed against all 71 existing bugs: BUG-047 is FRONTEND (`DEFAULT_LLM` hardcoded in chat/page.tsx; the chat page never fetches /api/settings) — a different layer, a different file, and its fix would NOT repair the other six settings. BUG-089 is providers, not settings. BUG-094 is provider_health's swallowed exceptions. No existing bug owns "the settings table is never read at runtime." New.

**CORROBORATION 2026-07-28 (P7-S1)**: a clean end-to-end demonstration of this record's thesis — the setting is stored, readable, and not honoured. `settings.default_llm_model` = **qwen3:14b**; `GET /api/settings` echoes qwen3:14b; backend startup logs `startup_model_validated model=qwen3:14b`. Yet three independent traces this phase record `llm_model=qwen2.5:7b`, and `ollama ps` plus the checkpoint blob both confirm **qwen2.5:7b** actually served the inference. The value survives the full write→read round-trip and is then ignored at the point of use.

**Attribution note (registrar)**: this evidence is genuinely dual-attributed and is recorded on BOTH records rather than being forced onto one. The PROXIMATE cause of the wrong model on these specific requests is BUG-047 — the P7-S1 POST body carries `"llm_model":"qwen2.5:7b"` explicitly, a frontend override that leaves the backend no fallback to consult. What THIS record contributes independently is that the persisted backend setting is never consulted at the point of use regardless of that override. Cross-ref BUG-047. No severity change; no new ID.
