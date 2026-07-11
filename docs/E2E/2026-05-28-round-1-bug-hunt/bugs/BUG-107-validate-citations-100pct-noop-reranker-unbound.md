# BUG-107: validate_citations is a 100% no-op — citation QA disabled (reranker unbound)

- **Severity**: MAJOR
- **Layer**: Backend
- **Discovered**: 2026-07-11T19:16:29Z in Phase 6 (P6-S1)
- **Phase scenario**: P6-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Code: `validate_citations` is added to the graph at `conversation_graph.py:65` with no reranker binding.
2. Runtime: every call hits `nodes.py:651` (`if not citations or not reranker:`) → early return; the cross-encoder alignment logic at `nodes.py:671-712` never runs.
3. Corroborated by BUG-103: `ranking` stage timing is 0.0 in 6/6 sampled traces.

## Expected
If `validate_citations` is meant to cross-encoder-validate/align citations, the reranker should be injected and the node should run its alignment logic.

## Actual
`reranker=None` on every invocation → the node is a 100% no-op → citation validation QA never happens on any request.

## Artifacts
- Screenshot: null
- Log excerpt: null
- Trace: traces/P6-S1-stage-timings-analysis.md (gitignored)

## Root-cause hypothesis
No partial application/closure binds the keyword-only `reranker` parameter when the node is registered on the graph (`conversation_graph.py:65`).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: TBD
- **GitHub issue**: TBD
- **Rationale**: TBD

## Notes
FLAG — by-design-vs-regression UNCONFIRMED, flagged for verify-gate adjudication. Pilot could not confirm whether the reranker was intentionally omitted (possible spec-26 perf decision) or whether this is a wiring regression. Related: BUG-103 (same root cause, timing-symptom side); spec-05 accuracy/citations context.
