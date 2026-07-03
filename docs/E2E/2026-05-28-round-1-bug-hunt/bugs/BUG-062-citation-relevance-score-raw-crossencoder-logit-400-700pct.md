# BUG-062: Citation relevance_score emits raw CrossEncoder logit; bar shows 400-700%

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-06-18T18:45:00Z in Phase 3 (P3-S2)
- **Phase scenario**: P3-S2
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask Q-001 in hunt-pdfs collection; wait for streamed response with citation chips.
2. Hover any inline citation chip ([1]-[4]) to open the CitationHoverCard tooltip.
3. Observe the relevance bar — reads >100%: [1] 614%, [2] 562%, [3] 540%, [4] 406%.

## Expected
Relevance bar shows a normalized percentage in [0%, 100%] reflecting the CrossEncoder reranker score, per schemas.py relevance_score: float # 0.0–1.0 contract.

## Actual
Raw CrossEncoder logit values (~[-10,+10]) are emitted directly as relevance_score: [1] 6.138→614%, [2] 5.623→562%, [3] 5.404→540%, [4] 4.059→406%. Color signal is also dead — CitationHoverCard.tsx:60-68 getRelevanceColor thresholds 0.7/0.4 → any positive logit always maps to bg-green-500 regardless of true relevance.

## Artifacts
- Screenshot: screenshots/BUG-062-relevance-tooltip.png (gitignored)
- Log excerpt: logs/BUG-062-score-payload.log (gitignored)
- Trace: null

## Root-cause hypothesis
reranker.py model.rank() lacks apply_function='sigmoid'; raw logit propagates through research_nodes.py:593/598 and nodes.py validate_citations:696 into the Citation schema without normalization. schemas.py:128 declares relevance_score: float # 0.0–1.0 but this contract is never enforced. Fix: apply sigmoid (1/(1+exp(-x))) or add apply_function='sigmoid' to model.rank() at the reranker; enforce normalization at ALL emission sites (nodes.py validate_citations + research_nodes.py). FE defensive band-aid: Math.min(Math.round(score*100), 100) in CitationHoverCard.tsx. No Next.js routing pattern implicated — pure backend contract violation.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Dedup check against 37 existing bugs: zero matches — no prior relevance/score bug registered. Raw score values from P3-S2 payload: [1] 6.138, [2] 5.623, [3] 5.404, [4] 4.059. Tooltip text and passage preview are CORRECT (BUG-061 is the click reachability failure; this bug is limited to score display). Session 931817be; backend trace 27bd5c78. Captures: /tmp/spec30-captures/p3-s2-frames/p3-s2-frame-hover-tooltip.png, frame_004.jpg; /tmp/spec30-captures/P3-S2-citation-payload-score.log.
P3-S3 NEGATIVE-score variant confirmed (analyst-correlated): Analytical trace 618fb649 raw CrossEncoder logits: +1.7839 / -0.1534 / -1.2169 / -1.5109 / -1.5400 → FE renders 178% / -15% / -122% / -151% / -154%. NEW visual failure mode beyond the original >100% overflow: negative percentage text. Frontend root: CitationHoverCard.tsx:62-68 renders Math.round(relevance_score*100)% with NO clamp on bar width OR text label. Backend root: raw logits not sigmoid-normalized. Both fix paths independent — frontend clamp Math.max(0, Math.min(1, score)) OR backend sigmoid; either alone stops the artifact.
P3-S4 T1 (2026-07-03) across-session re-confirmation on a factoid query — 5 sources render 334/215/150/142/-58%; the negative -58% renders as a red bar. Durable screenshots: screenshots/BUG-062-p3s4-t1-full-answer-94pct.png, screenshots/BUG-062-p3s4-t1-citation1-334pct.png, screenshots/BUG-062-p3s4-t1-citation2-215pct.png, screenshots/BUG-062-p3s4-t1-citation3-150pct.png, screenshots/BUG-062-p3s4-t1-citation4-142pct.png, screenshots/BUG-062-p3s4-t1-citation5-neg58pct-red.png.
P3-S4 T2 (2026-07-03) across-question evidence, same clean-probe session, follow-up "y para gas natural específicamente?": raw relevance_scores 4.750 / 3.840 / -1.248 → bars 475% / 384% / -125% (the -125% is another red NEGATIVE-bar data point, confirming the negative-score failure mode is not a one-off). Session 9c30b2ea, trace 30307482. Durable screenshots: screenshots/BUG-062-p3s4-t2-citation1-475pct.png, screenshots/BUG-062-p3s4-t2-citation2-384pct.png, screenshots/BUG-062-p3s4-t2-citation3-neg125pct-red.png (renamed from the held BUG-pending-p3s4-t2-* staging names). NOTE: citation1-475pct.png also dual-referenced from BUG-064 as topic-drift evidence — same physical file, two bug records, per Lead direction.
P3-S5 (2026-07-03) recurrence on a 3RD collection (nag-corpus-spec28, Q-007 NAG-204), confirming the defect is collection-independent: raw relevance_scores 5.817/5.494/5.137/4.697/4.620 → bars 582%/549%/514%/470%/462% (all positive — the WORST overflow observed across all P3 scenarios to date). Trace 80c47266.
