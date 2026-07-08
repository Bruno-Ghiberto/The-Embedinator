# BUG-086: Model emits malformed citation marker [N:1] instead of [N], not chip-rendered

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-08T19:14:00Z in Phase 4 (P4-S5)
- **Phase scenario**: P4-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask a grounded question that the model answers successfully with citations.
2. Observe the answer's trailing citation marker: instead of the expected digit-only `[N]` form, the model occasionally emits a colon-indexed `[N:1]` form (e.g. "...en acometidas es de 25 mm. [N:1]").
3. Observe rendering: the malformed marker is NOT chip-rendered — it appears as literal plain text in the answer bubble.

## Expected
Every inline citation marker follows the documented `[N]` digit-only format and renders as a citation chip (per `COLLECT_ANSWER_SYSTEM`, `prompts.py:206,217`).

## Actual
`qwen2.5:7b` deviates from the explicit `[N]` citation instruction and emits a colon-indexed `[N:1]` marker; no such template exists anywhere in the codebase (grep = 0 hits; `FORMAT_RESPONSE_SYSTEM`, the one component that could normalize this, is an uninvoked Phase-2 stub — see BUG-084). The frontend citation parser, `ChatMessageBubble.tsx:37`, is digit-only (`/\[(\d+)\]/g`); `[N:1]` fails to match, hits the early-return at lines 38-40, and the whole message renders as plain markdown instead of routing through the chip component — so the malformed marker surfaces to the user as literal text.

## Artifacts
- Screenshot: screenshots/BUG-085-p4s5-dedup-collision.png (gitignored) — same P4-S5 answer screen, trailing "[N:1]" visible.
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
HIGH confidence (log-analyst, code-confirmed). Same family mechanism as BUG-083/BUG-084: zero validation or normalization of raw LLM output on the answer path. The model's citation-marker syntax is never checked or corrected before reaching the user; `ChatMessageBubble.tsx`'s digit-only parser is a reasonable, correctly-designed consumer contract that this malformed output simply violates — the frontend fallback (render as plain text rather than crash or drop content) is working as intended, NOT a frontend bug. Non-deterministic: the model sometimes emits the correct `[N]` form (see the many prior happy-path traces with working chips) and sometimes the malformed `[N:1]` form, matching the same free-form-output pattern documented in BUG-084's 5 decline-scaffolding variants.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Dedup-check performed before minting: confirmed distinct from BUG-060 (citation chip is non-semantic/non-focusable — an accessibility defect on a WELL-FORMED `[N]` marker, unrelated to marker syntax) and from BUG-084 (decline-scaffolding text leak — occurs on DECLINES; this defect occurs on a SUCCESSFUL, grounded answer). No other bug owns "model emits malformed inline citation-marker syntax on a successful answer."

Cross-ref: BUG-083/BUG-084 (shared root cause — no validation/normalization layer on raw LLM answer-path output; this is the citation-syntax-specific manifestation of that same gap). Evidence: trace `e6d35cd6-3c73-40e4-a02f-a865be03822c` (P4-S5 poison-test-p4s5 diameter answer, "...en acometidas es de 25 mm. [N:1]").
