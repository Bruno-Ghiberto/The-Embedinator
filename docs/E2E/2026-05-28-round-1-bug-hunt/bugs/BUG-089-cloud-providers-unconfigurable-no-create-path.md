# BUG-089: Cloud providers unconfigurable — no create path; README claims are false

- **Severity**: CRITICAL
- **Layer**: Backend
- **Discovered**: 2026-07-10T14:20:28Z in Phase 5 (P5-S1)
- **Phase scenario**: P5-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Settings > Providers.
2. Observe exactly one card, "Ollama". No OpenAI card, no "Add provider" control.
3. `curl -X PUT http://localhost:8000/api/providers/openai/key -H 'Content-Type: application/json' -d '{"api_key":"probe-nonsecret-value"}'` -> HTTP 404, envelope `{"error":{"code":"PROVIDER_NOT_FOUND","message":"Provider 'openai' not found"},"trace_id":"399ad896-ad86-40c6-892b-74c3f45e96b5"}`.
4. `sqlite3 data/embedinator.db "SELECT name FROM providers"` -> `ollama` only, before and after.

## Expected
A user can configure a cloud provider (OpenAI, Anthropic, OpenRouter), per README.

## Actual
There is no path to do so — not in the UI, not in the API, not in env/config. Every cloud-provider surface is unreachable.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-089-cloud-provider-unreachable.log (gitignored)
- Trace: null
- Public evidence: public-evidence/BUG-089-cloud-provider-unreachable.log (tracked)

## Root-cause hypothesis
Day-one wiring gap between the storage contract and the API surface:
- `backend/api/providers.py` exposes only four routes: GET /api/providers (:15), PUT /api/providers/{name}/key (:49), GET /api/providers/health (:89), DELETE /api/providers/{name}/key (:152). There is NO POST/create route.
- The PUT guard at providers.py:68-78 (`provider = await db.get_provider(name); if not provider: raise 404`) fires BEFORE the encrypt call at providers.py:83. A key can only be set on a provider that already exists.
- `SQLiteDB.create_provider()` (sqlite_db.py:603) has ZERO production callers. Every caller is a test: tests/unit/test_contracts_storage.py:161-163, tests/unit/test_sqlite_db.py:551/566/579/585/586/592/599, tests/integration/test_storage_integration.py:467-542, tests/regression/test_regression.py:326/342/774.
- `ProviderRegistry.set_active_provider()` (providers/registry.py:140-146) calls `db.upsert_provider(...)` (INSERT OR REPLACE, sqlite_db.py:687-703) — which COULD create a cloud row — but has ZERO callers anywhere in backend/. A second dead creation surface.
- `ProviderRegistry.initialize()` (registry.py:29-44) is the only startup write to `providers`; it hardcodes `name="ollama"` gated by `if not active:` and cannot produce a cloud row under any input.
- No .sql file, migration, or Makefile target seeds a provider row. `backend/config.py` contains ZERO references to openai/anthropic/openrouter — no environment-variable escape hatch either.
- Consequently DEAD IN PRODUCTION: `backend/providers/openai.py`, `anthropic.py`, `openrouter.py`; the cloud dispatch branches in `provider_health()` (providers.py:125-145); and both `registry.py:56-67` (`get_active_llm`) and `registry.py:117-125` (`get_active_langchain_model`), each of which branches on `active["name"]` from `db.get_active_provider()`.
- Frontend corroboration (independent): `ProviderHub.tsx:151-225` is purely API-driven via `useSWR('/api/providers', getProviders)` with no static provider list; `frontend/app/settings/page.tsx:61-64,68-72` mounts only `<ProviderHub />` — no button, dialog, or select; `frontend/lib/api.ts` exports exactly three provider functions (getProviders :239, setProviderKey :246, deleteProviderKey :259), no create function. Repo-wide grep of frontend/ for `add.?provider|new.?provider|create.?provider|providerType|provider_type` returns ZERO hits.
- Never built, not regressed: `backend/api/providers.py` was created whole-cloth in commit `01b253e` (2026-03-18). `git log --all -p -- backend/api/providers.py | grep "@router\."` across ALL history returns only today's four decorators — no POST/create route ever existed. `create_provider()` was born in that same commit alongside its full test suite. The storage contract was built and unit-tested; the route layer was never given a POST to call it.
- Damning corroboration: `frontend/tests/e2e/settings.spec.ts:32` mocks a provider literally named `"openai"` with `model_count: 5` — the Settings E2E suite validates against a product state the backend cannot produce.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/157
- **Rationale**: The README advertises OpenAI/Anthropic/OpenRouter in three places while no POST/create route has ever existed in any version of providers.py — an advertised headline feature unreachable through every surface, falsifiable by a reader in under a minute.

## Notes
Why CRITICAL, not MAJOR: the README makes the claim in three places — line 29 ("Cloud providers (OpenAI, Anthropic, OpenRouter) are supported as optional alternatives."), line 65 ("**Multi-provider LLM support** -- Ollama (local), OpenAI, Anthropic, and OpenRouter **with encrypted API key storage**"), line 150 (tech table: "Cloud providers | OpenAI, Anthropic, OpenRouter (optional)"). An advertised headline feature is unreachable through every surface the product exposes, with no workaround available to any user. Three adapter modules, two registry dispatch paths, and two storage methods are dead code. This is a v1.0 launch-blocking credibility defect, falsifiable by a reader in under a minute.

Impact on this hunt: P5-S1 and P5-S2 have no UI path as written; P5-S5 has no cloud key to audit. Not a BLOCKER — the hunt can continue via an out-of-band seeded row, pending Pilot authorization.

Dedup-check performed against all 65 existing bugs: `grep -ril "openai\|anthropic\|openrouter"` -> zero hits, independently re-run by frontend-inspector -> zero hits. No existing bug owns "a provider cannot be created." Distinct from BUG-047 (frontend DEFAULT_LLM hardcoded, a sync issue on an existing provider) and from BUG-045 (LangGraph config injection). Genuinely new.

[2026-07-10T11:58:57-03:00] P5-S2 CORROBORATION — a THIRD dead surface on the cloud-provider path, found while testing decrypt-after-restart. `grep -rn "providers/health" frontend/` returns ZERO hits: `GET /api/providers/health` (backend/api/providers.py:89) is fully implemented, dispatches by name to OpenRouterLLMProvider/OpenAILLMProvider/AnthropicLLMProvider, works correctly when called by curl — and NOTHING IN THE PRODUCT EVER CALLS IT. This is the same disease as BUG-089 itself, running in the opposite direction: BUG-089 is a storage contract with no route to call it (`create_provider()`, `set_active_provider()`); this is a route with no client to call it. The cloud-provider path now shows SIX independent defects, every one of them a consequence of the path never having been walked end to end: (1) BUG-089 — no create route, so no cloud provider can exist. (2) BUG-091 — `get_active_llm()` reads `config_json["api_key"]` in plaintext, bypassing Fernet; dead, and ARMED by BUG-089's most natural fix. (3) BUG-093 — CSS `capitalize` will render "Openrouter"; dormant, unmasked by BUG-089's fix. (4) BUG-094 — `provider_health()` swallows every failure cause into one unlogged boolean. (5) `frontend/tests/e2e/settings.spec.ts:32` mocks a provider named "openai" with `model_count: 5`, a state the backend cannot produce — the suite validates a fiction. (6) `GET /api/providers/health` has no caller. Untested code is not neutral. It rots, and every defect above was invisible precisely because nothing ever exercised the path. Severity UNCHANGED (CRITICAL).

[2026-07-10T12:22:13-03:00] TEAM-LEAD CORRECTION OF THIS RECORD'S OWN COMMIT NARRATIVE. The "NEVER BUILT, NOT REGRESSED" paragraph above states that `backend/api/providers.py` "was created whole-cloth in commit 01b253e ... commit message says spec-15 observability but the diff is unmistakably spec-10-provider-architecture." THAT CHARACTERISATION IS WRONG and is hereby corrected. Flagged by log-analyst, then verified independently by team-lead: `git show --stat 01b253e` reports **679 files changed, 121,211 insertions, 11,138 deletions**, spanning 57 backend files, 646 non-backend files, and even `.claude/skills/gitnexus/*`. The diff is not "unmistakably spec-10" — it is essentially the ENTIRE repository. Further: `git cat-file -e 01b253e~1:backend/api/providers.py` fails and `git ls-tree 01b253e~1 backend/` is empty — **`backend/` did not exist at that commit's parent (5f1fbb1)**. The repo holds 189 commits, only 4 of them predating this one. So `01b253e` is not a squash of earlier git history; it is the commit where the entire backend — specs 01 through 15 — first entered version control, fully formed. CONSEQUENCES FOR THIS RECORD: (a) "born in the same commit as settings.py/create_provider()" is TRUE but VACUOUS — every backend file was born there, so co-location implies no shared authorship session and no causal link. Any inference that one developer introduced these defects together is unsupported. (b) `git log -S` on ANY backend symbol will always bottom out at this commit, because nothing before it exists; that weakens `git log -S` as an archaeology tool for this repo generally. (c) THE CORE FINDING IS UNAFFECTED AND NOW RESTS ON FIRMER GROUND: `backend/api/providers.py` has exactly THREE commits in its entire life — `01b253e` (birth), `8bb53b8` (ruff format), `3a5fe6b` (mypy fix) — and `git log --all -p -- backend/api/providers.py | grep "^+@router\."` yields exactly four unique decorators across all history: GET /api/providers, GET /api/providers/health, PUT /api/providers/{name}/key, DELETE /api/providers/{name}/key. No POST/create route has ever existed in any version of this file. NEVER BUILT, NOT REGRESSED — confirmed, and independent of the commit narrative. The orphaned contracts were present at the moment this backend first appeared in version control. Severity UNCHANGED (CRITICAL). Recorded under team-lead's name: this is the ELEVENTH team-lead accuracy error of Phase 5, and the first one that reached a permanent bug record rather than being caught in the session log.
