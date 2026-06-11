# BUG-047: Frontend DEFAULT_LLM hardcoded — never synced with backend settings

- **Severity**: MINOR
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
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
Chat page initializes model state from a local constant; useModels() populates the dropdown but not the initial selection; no settings fetch on mount.

## Triage (filled in Phase 8 for MAJOR+)

## Notes
Model confirmed NOT the cause of BUG-045 (both models installed; Ollama never reached).
