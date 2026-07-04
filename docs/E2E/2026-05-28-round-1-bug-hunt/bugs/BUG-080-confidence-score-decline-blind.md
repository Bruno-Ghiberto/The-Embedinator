# BUG-080: Confidence score is decline-blind — shows confidence on explicit declines

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T19:21:29Z in Phase 4 (P4-S1)
- **Phase scenario**: P4-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask an out-of-scope question that the system correctly declines to answer ("no information found").
2. Observe the confidence pill on the decline: it shows a non-trivial score (e.g. Medium 54% on the copper-cable question, Low 37% on the Australia question) rather than reflecting that the model declined.

## Expected
An explicit decline should score near-zero / clearly-Low confidence, signaling to the user that no answer was found.

## Actual
`backend/agent/confidence.py:26-61`, `compute_confidence()`, takes only chunk and collection counts as input; it never inspects `answer_text` or any decline flag. The score reflects retrieval/rerank quality alone, regardless of whether the model actually answered or declined — so a well-retrieved-but-off-topic decline can still show a moderate confidence score.

## Artifacts
- Screenshot: screenshots/BUG-077-newchat-not-fresh.png (gitignored) — shows Medium 54% confidence on a decline.
- Screenshot: screenshots/BUG-078-subquestion-leak-samechat.png (gitignored) — same decline path, second view.
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
HIGH confidence (log-analyst, code-confirmed). `compute_confidence()`'s signature has no visibility into whether the generation step declined; confidence is purely a function of retrieval signal strength, decoupled from the actual answer content.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Cross-ref: BUG-081 (same decline-blind failure class, applied to citations instead of confidence — the two likely share a fix surface: gate both confidence and citation display on whether the answer is a decline).
