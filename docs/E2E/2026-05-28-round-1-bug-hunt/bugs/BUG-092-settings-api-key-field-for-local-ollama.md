# BUG-092: Settings offers an API key field for local Ollama; schema omits provider_type

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T14:20:28Z in Phase 5 (P5-S1)
- **Phase scenario**: P5-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Open Settings > Providers.
2. Observe the Ollama card renders an "Enter ollama API key" input and a "Save key" button.
3. Note Ollama is a local provider requiring no key; its DB row has `api_key_encrypted NULL` and `provider_type='local'`.

## Expected
The UI should not present a key-entry affordance for a local provider that requires no key, or should clearly distinguish local vs. cloud providers.

## Actual
The key input renders unconditionally regardless of provider locality, inviting the user to enter a credential where none is needed or appropriate.

## Artifacts
- Screenshot: screenshots/BUG-092-ollama-api-key-field.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
A contract gap, not a missing `if`: `ProviderDetailResponse` (backend/agent/schemas.py:292-299) exposes only name/is_active/has_key/base_url/model_count. `provider_type` EXISTS in the `providers` table but is NOT in the response model. `frontend/lib/types.ts:94-100` mirrors it field-for-field. `ProviderHub.tsx` `ProviderRow` (:32-144) renders the key input at :93-121 unconditionally on `!provider.has_key`, with no branch on type or locality. The frontend was never given a slot to distinguish local from cloud; it cannot branch on what it cannot see. Fix surface: schemas.py:292-299 (expose provider_type) plus the corresponding UI branch.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Impact — not merely cosmetic. It actively invites a destructive action. During P5-S1, the Pilot, following the playbook and finding no OpenAI card, asked whether to paste the SC-012 placeholder into this field. Doing so would have Fernet-encrypted a bogus OpenAI-shaped credential onto the sole provider the entire stack runs on. The UI presented that as the obvious action. Pilot correctly stopped and did not do this.

Frontend exonerated — the component structurally cannot see `provider_type`, so it cannot branch on it.

Dedup-check performed against all 65 existing bugs: `grep -riE "add.?provider|providerhub"` -> zero hits (frontend-inspector, independent). Distinct from BUG-089 (cannot create cloud providers) — different symptom, different root cause, different fix surface. New.

[team-lead adjudication] LAYER = Backend. The fix SPANS BOTH LAYERS but is not symmetric. Backend is the root cause and the blocking dependency: `ProviderDetailResponse` (backend/agent/schemas.py:292-299) must first expose `provider_type`, which already exists on the `providers` table. Only then can the frontend act — `ProviderHub.tsx` `ProviderRow` (:32-144, key input at :93-121) must branch on it to suppress the API-key input for `provider_type == 'local'`. The frontend change is CONTINGENT and cannot be made first. Filed Backend per the BUG-086 precedent: layer names the root cause and the blocking dependency, not the surface where the symptom is visible. Spec-31 must land both halves; shipping only the schema field leaves the misleading input in place, and the frontend half is impossible alone.
