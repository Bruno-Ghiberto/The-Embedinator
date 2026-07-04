# BUG-079: No language-mirroring instruction — Spanish queries get English answers

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T19:27:52Z in Phase 4 (P4-S2)
- **Phase scenario**: P4-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask a Spanish-language question on a fresh chat (new `session_id`, no accumulated state).
2. Observe: the response language is effectively random per call — English or Spanish — regardless of the query's or the retrieved passages' language.
3. Proven standalone (isolated from any multi-turn accumulation) by P4-S2: trace `2439c409`, session `06a5074d` (genuinely fresh, `num_valid=1`, zero accumulation), Spanish query "¿Es seguro?" → English answer.

## Expected
The response mirrors the user's query language — the corpus and user base are Spanish-language.

## Actual
None of the 17 prompt constants in `backend/agent/prompts.py` contain any language-mirroring instruction. The only prose-producing LLM call on the happy path is `collect_answer` (`backend/agent/research_nodes.py:685-692`, using `COLLECT_ANSWER_SYSTEM`, `prompts.py:205-228`), which has no language constraint; `format_response` is pure Python and applies no correction. `qwen2.5:7b` freely chooses its output language on every generation. `REPORT_UNCERTAINTY_SYSTEM` (meta-reasoning path) has the identical gap.

## Artifacts
- Screenshot: screenshots/BUG-079-p4s2-english-decline.png (gitignored) — Spanish "¿Es seguro?" answered in English, fresh chat.
- Log excerpt: logs/BUG-079-p4s2-fresh-english.network-response (gitignored) — P4-S2 network response, trace `2439c409`.
- Trace: null

## Root-cause hypothesis
HIGH confidence (log-analyst, exhaustive prompt audit across all 17 constants in `prompts.py`). No system prompt on the answer-generation or uncertainty-reporting paths instructs the model to mirror the query's language; `qwen2.5:7b` has no default bias strong enough to guarantee consistent Spanish output. Fix: add "Always respond in the same language as the user's question" to `COLLECT_ANSWER_SYSTEM` and `REPORT_UNCERTAINTY_SYSTEM`.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Cross-ref: distinct from BUG-056 (topic drift across turns — a retrieval/routing defect, not a language defect). Amplified by BUG-047 (frontend hardcodes the wrong model, `qwen2.5:7b` instead of the backend's upgraded default `qwen3:14b`) — untested whether `qwen3:14b` exhibits the same drift, but the fix (explicit language-mirroring instruction) is model-independent and should be applied regardless.
