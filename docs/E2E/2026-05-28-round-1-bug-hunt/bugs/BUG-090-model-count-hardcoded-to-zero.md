# BUG-090: model_count hardcoded to 0 in list_providers; every card shows "0 models"

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T14:20:28Z in Phase 5 (P5-S1)
- **Phase scenario**: P5-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Settings > Providers.
2. Observe the Ollama card reads "0 models".
3. Cross-check `docker exec embedinator-ollama ollama list` -> 11 models installed, chat actively serving qwen2.5:7b.

## Expected
The provider card reflects the actual number of models available to that provider.

## Actual
`model_count` is a hardcoded literal `0`, never computed from anything, regardless of real model availability.

## Artifacts
- Screenshot: screenshots/BUG-090-model-count-zero.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
`model_count=0` is a literal at BOTH construction sites of `list_providers()` — `backend/api/providers.py:29` (the real-DB-rows loop) and `backend/api/providers.py:42` (the synthetic Ollama fallback insert). It is never computed. `schemas.py:299` `model_count: int = 0` is merely the Pydantic field default, not evidence of computation. `_fetch_ollama_models()` lives only in `backend/api/models.py` and is never imported or called from providers.py; `GET /api/models/llm` (models.py:77-99) is the only place a model list is actually built.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Frontend exonerated (same discipline as BUG-086): `ProviderHub.tsx:75` renders `{provider.model_count} model{...}` as a direct pass-through of the wire value, with no computation, default override, or client-side enumeration. `frontend/lib/types.ts:100` declares `model_count: number`. The zero originates entirely server-side.

`frontend/tests/e2e/settings.spec.ts:32` fixtures `model_count: 5` — the test data assumes a correct behavior the backend has never delivered.

TEAM-LEAD LINE-NUMBER CORRECTION: the `[2026-07-10T11:20:28-03:00] Pilot | observation` session-log entry cited `model_count` hardcoded at providers.py:27 and :40. Both are WRONG; the correct lines are providers.py:29 and :42, as reported by log-analyst and confirmed by `grep -n model_count backend/api/providers.py`. This bug record carries the correct line numbers. The erroneous session-log entry stands unedited; the correction supersedes it.

Dedup-check performed against all 65 existing bugs: `grep -ril "model_count\|0 models"` -> zero hits, independently re-run by frontend-inspector. New.

[2026-07-10T11:41:04-03:00] INDEPENDENT CORROBORATION from the P5-S1 out-of-band seed. After a dormant `openai` row was inserted, a single `GET /api/providers` response returned BOTH `{"name":"ollama",...,"model_count":0}` AND `{"name":"openai",...,"model_count":0}`. Ollama has 11 models installed (`docker exec embedinator-ollama ollama list`) and is actively serving qwen2.5:7b; the openai row was created seconds earlier and has never had a model. Identical zeros from opposite states. This confirms from a second direction that `model_count` is never computed — it is the literal `0` at backend/api/providers.py:29 (real-rows loop) and :42 (Ollama fallback). Severity UNCHANGED (MINOR).
