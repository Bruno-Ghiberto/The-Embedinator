# BUG-091: get_active_llm reads plaintext api_key from config_json, bypassing decrypt

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T14:20:28Z in Phase 5 (P5-S1)
- **Phase scenario**: P5-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Read `ProviderRegistry.get_active_llm()` (backend/providers/registry.py:46-71).
2. Observe it constructs the cloud provider client with `api_key=config.get("api_key", "")`, read directly out of `config_json`.
3. Compare to its sibling `get_active_langchain_model()` (registry.py:96-105), which correctly calls `key_manager.decrypt(active["api_key_encrypted"])`.
4. Confirm current callers: `grep -rn "get_active_llm(" backend/` -> only a docstring self-reference at registry.py:77; zero production callers today.

## Expected
Every code path that resolves an active provider's API key MUST decrypt it via `KeyManager`, never read plaintext from `config_json`.

## Actual
`get_active_llm()` reads the key straight out of `config_json` in plaintext, with no `key_manager.decrypt()` call — a second, incorrect "get the active LLM" implementation exists alongside the correct one.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-091-plaintext-key-read-registry.log (gitignored)
- Trace: null

## Root-cause hypothesis
Two parallel "get the active LLM" methods were written; only one (`get_active_langchain_model`) was updated to respect the Fernet-encrypted storage contract. `get_active_llm()` was left reading the pre-encryption shape (`config.get("api_key", "")` from `config_json`).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
CURRENT STATUS — dead, not a live leak: the real chat path is `chat.py:176` -> `get_active_langchain_model()`, the encrypted one. `get_active_llm()` has zero production callers today.

WHY THIS IS REGISTERED ANYWAY, when team-lead declined to register the equally-dormant structlog exact-match redaction gap earlier this phase: the redaction gap requires someone to write new code that logs a key under a non-matching field name. THIS defect sits directly on the path of BUG-089's most obvious fix. `set_active_provider()` (registry.py:140-146) is the ONLY existing method that can create a cloud provider row, and it persists its `config` dict into `config_json`. A fixer wiring it up with `{"api_key": "<secret>"}` writes that key to config_json in PLAINTEXT, and `get_active_llm()` reads it straight back out unencrypted — bypassing the `providers.api_key_encrypted` Fernet column entirely. Fixing BUG-089 via the natural path arms BUG-091. That asymmetry — a dormant defect whose trigger is created by a required fix — is what distinguishes it from an untriggered latent gap. Spec-31 must fix these two together.

Dedup-check performed: distinct from the P5 pre-phase security-posture observation (that recorded the structlog redaction filter's exact-name matching, main.py:40/46 — a logging concern). This is a storage/read-path concern in registry.py. Distinct from BUG-083/084 (LLM output sanitization). New.
