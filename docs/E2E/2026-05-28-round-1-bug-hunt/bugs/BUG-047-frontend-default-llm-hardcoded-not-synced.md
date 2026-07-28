# BUG-047: Frontend DEFAULT_LLM hardcoded — never synced with backend settings

- **Severity**: MAJOR
- **Layer**: Frontend
- **Discovered**: 2026-06-11T12:55:00Z in Phase 2 (P2-S2)
- **Phase scenario**: P2-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Read frontend/app/chat/page.tsx:19 — const DEFAULT_LLM = "qwen2.5:7b" (hardcoded literal).
2. Read :58-60 — initial model = URL ?llm= param ?? DEFAULT_LLM; /api/settings is never fetched by the chat page.
3. Change backend default_llm_model (Settings UI or env) → chat badge unchanged.

## Expected
Chat's default model sourced from backend settings (single source of truth).

## Actual
Frontend and backend defaults are independent constants; today they coincidentally match (backend persisted setting = qwen2.5:7b) while config.py code default is qwen3:14b — three values, three sources.

## Artifacts
- Screenshot: screenshots/BUG-047-model-badge.png (gitignored)
- Log excerpt: logs/BUG-047-p3s1-post-body.log (gitignored)
- Trace: null

## Root-cause hypothesis
Chat page initializes model state from a local constant; useModels() populates the dropdown but not the initial selection; no settings fetch on mount. More precisely: ChatRequest.llm_model defaults to "qwen2.5:7b" at schemas.py:192 — when frontend sends the explicit field, backend never falls back to config default_llm_model="qwen3:14b". All inference runs on the smaller model regardless of backend configuration.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/134
- **Rationale**: A hardcoded literal unconditionally overrides the backend on every request, so a user who saves qwen3:14b keeps running qwen2.5:7b — the same structural deception as BUG-095, via two independent bypasses (no settings fetch, plus frozen per-session llmModel restore).

## Notes
Model confirmed NOT the cause of BUG-045 (both models installed; Ollama never reached).

P3-S1 evidence (2026-06-18, escalation to MAJOR): frontend-inspector confirmed POST /api/chat body always contains llm_model="qwen2.5:7b" explicitly on every request — this is not display-only, it is an unconditional backend override. Log-analyst confirmed via query_traces.llm_model + Ollama runner log that qwen2.5:7b actually served inference (trace 2f4d0b4f), while backend startup validates qwen3:14b as default. Functional impact: smaller model handles all chat inference, degrading answer quality and increasing retry probability (see BUG-055, BUG-056). Capture: /tmp/spec30-captures/p3-s1-ndjson-stream.json.

**UPDATE 2026-07-03 (P4-S1/S2 root-cause confirmation)**: reconfirmed at Phase 4 — `frontend/app/chat/page.tsx:19` hardcodes `DEFAULT_LLM = "qwen2.5:7b"`, overriding the backend's upgraded default `qwen3:14b` (`config.py:37`). All P4-S1 and P4-S2 traces served `qwen2.5:7b`. This is the same root cause identified at P3-S1, now cross-referenced against the Phase 4 language-mirroring finding (BUG-079) — untested whether `qwen3:14b` would exhibit the same defects, but BUG-079's fix (explicit language instruction in the system prompt) is model-independent.

[2026-07-10T12:26:22-03:00] P5-S3 reconfirmation, plus a SECOND INDEPENDENT STALENESS PATH not previously recorded. Reconfirmed live by frontend-inspector on a clean Playwright profile AFTER the Pilot's real save to qwen3:14b: fresh `page.goto('http://localhost:3000/chat')`, rendered badge text `qwen2.5:7b`, `hasQwen3:14b` in body text = false. `grep getSettings` across chat/page.tsx = zero hits; the chat page never touches /api/settings. NEW MECHANISM: `frontend/app/chat/page.tsx:107-108` — `if (activeSession.config.llmModel) { setLlmModel(activeSession.config.llmModel); }`. A saved session in localStorage (`embedinator-sessions:v1`) carries `config.llmModel` FROZEN at that session's creation time. Reopening any saved conversation restores THAT session's model, overriding both the current default and any current Settings value. CONSEQUENCE FOR THE FIX: making chat/page.tsx fetch `getSettings()` on mount would NOT be sufficient — the session-restore path at :107-108 would silently override it the moment a user reopens a conversation. Two independent bypasses of live settings, not one. Severity UNCHANGED (MAJOR).

**UPDATE 2026-07-11 (P6-S1)**: Observability makes it globally visible — every trace's Model field (`TraceTable.tsx:131-133`, `trace.llm_model`) shows the same model (`qwen2.5:7b`) across the 1008-trace list; consistent with BUG-095 (settings write-only). Artifact: screenshots/P6-S1-observability-traces-list.png. Severity UNCHANGED (MAJOR).

**CORROBORATION 2026-07-28 (P7-S1)**: the live POST body captured by frontend-inspector is direct evidence of this record's mechanism — `{"message":"…","collection_ids":["22923ab5-…"],"llm_model":"qwen2.5:7b","embed_model":null,"session_id":null}`. The hardcoded `qwen2.5:7b` is sent explicitly on every request, unconditionally overriding the backend, while backend startup validates `qwen3:14b` and `GET /api/settings` returns qwen3:14b. `ollama ps` and the checkpoint blob confirm qwen2.5:7b actually served. The same POST body also carries `session_id: null`, a live re-confirmation of BUG-064. Cross-ref BUG-095 (the independent half: the persisted setting is never read at the point of use). No severity change; no new ID.
