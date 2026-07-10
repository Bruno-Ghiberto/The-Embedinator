# BUG-101: Chat embed_model tag drifts nomic-embed-text vs :latest by frontend state source

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:29:14Z in Phase 5 (P5-S4)
- **Phase scenario**: P5-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. In the same chat session, observe turn 1's `query_traces.embed_model` value.
2. Observe turn 2's `query_traces.embed_model` value in the same session.
3. Compare: turn 1 (`c741ce14`) records `nomic-embed-text` (bare); turn 2 (`c9d5d6c5`) records `nomic-embed-text:latest`.

## Expected
The embed_model tag recorded for a given embedder should be consistent within a session, regardless of which frontend state path populated it.

## Actual
The same session records two different string tags for what is functionally the same model, depending on which of two differently-tagged sources populated the frontend's `embedModel` state first.

## Artifacts
- Screenshot: null
- Log excerpt: logs/BUG-101-embed-model-tag-drift.log (gitignored)
- Trace: null

## Root-cause hypothesis
Turn 1 (`c741ce14`): `nomic-embed-text` (bare) — `body.embed_model` was null, so `chat.py:106` used `settings.default_embed_model` = `"nomic-embed-text"` (`config.py:44`, no tag). Turn 2 (`c9d5d6c5`): `nomic-embed-text:latest` — by then the frontend `embedModel` state carried an explicit value, sourced either from a restored session config (`chat/page.tsx:110-111`) or from `useModels()`'s `embedModels` list (`chat/page.tsx:9,43`), which comes from Ollama `/api/tags` and always carries `:latest`. So the embedder identity on a chat request depends on which of two differently-tagged sources populated frontend state first.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
Severity MINOR: both values are 768-dim, so this did NOT cause the P5-S4 dimension mismatch — confirmed. It is a latent inconsistency: `nomic-embed-text` and `nomic-embed-text:latest` are string-distinct, and any code that compares embedder identity by string (as BUG-025 does in `/api/health`) will treat them as different models.

Cross-reference BUG-025 (same Ollama tag-suffix family) but distinct site and trigger — BUG-025 is `/api/health` availability string-matching; this is chat-request-body construction. Same-family/different-trigger, registered separately per the hunt's consistent adjudication (cf. BUG-078 vs BUG-084).

Dedup-check performed: cross-ref BUG-025, not merged (different file, different trigger). New.
