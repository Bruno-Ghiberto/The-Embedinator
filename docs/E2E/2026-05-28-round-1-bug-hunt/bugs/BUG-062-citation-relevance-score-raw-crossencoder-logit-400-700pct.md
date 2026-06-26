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
