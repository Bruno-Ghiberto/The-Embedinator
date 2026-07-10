# BUG-096: ChatRequest.llm_model hardcoded default makes the settings fallback dead

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:22:13Z in Phase 5 (P5-S3)
- **Phase scenario**: P5-S3
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Read `ChatRequest` (backend/agent/schemas.py:187-193).
2. Observe `llm_model: str = "qwen2.5:7b"` (:192) is non-optional with a hardcoded literal default.
3. Read `backend/api/chat.py:105` — `llm_model = body.llm_model or settings.default_llm_model`.
4. Confirm the fallback can only fire if a caller transmits an explicit empty string, which the UI never does.

## Expected
The backend's settings-based fallback for `llm_model` should be reachable whenever a client omits the field.

## Actual
Because `ChatRequest.llm_model` has a hardcoded non-optional default, Pydantic always populates it before the fallback logic runs. The fallback to `settings.default_llm_model` is unreachable dead code.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-096-chatrequest-hardcoded-model-default.log (gitignored)
- Trace: null

## Root-cause hypothesis
`backend/agent/schemas.py:192` `llm_model: str = "qwen2.5:7b"` inside `class ChatRequest` (declared :187) is non-optional with a hardcoded literal default. Pydantic therefore always populates it, so `backend/api/chat.py:105` `llm_model = body.llm_model or settings.default_llm_model` can only reach its fallback if a caller transmits an explicit empty string. From the UI this never happens.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
The asymmetry, and why it hides the defect: `embed_model: str | None = None` (schemas.py:193) IS Optional, so `chat.py:106`'s fallback DOES fire on every request — and reads `settings.default_embed_model` from the CONFIG singleton, never the DB row (BUG-095). Today both read `nomic-embed-text` by coincidence, which conceals it from casual testing. If the Pilot changed the embedding model in Settings, chat would keep using the old config value on every request, permanently.

Note the compounding: even a complete fix to BUG-095 would NOT make the Settings model selector work, because `body.llm_model` still wins. Three things must change together — this, BUG-095, and BUG-047. Three sources of truth, three different answers, and a frontend constant wins.

Severity MINOR: no data loss, no security exposure; on its own it is unreachable dead code. Registered because it is a required half of BUG-095's fix and would silently defeat it.

Dedup-check performed against all 71 existing bugs: distinct from BUG-095 (different file, different fix surface) and BUG-047 (frontend). New.
