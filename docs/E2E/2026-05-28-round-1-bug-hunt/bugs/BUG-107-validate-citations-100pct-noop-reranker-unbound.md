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
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/164
- **Rationale**: An unbound reranker param makes the node early-return on every request, so citation-alignment QA never runs on any answer — an entire verification stage silently absent while the graph presents it as wired, the same class the owner flagged in BUG-095.

## Notes
**ADJUDICATED 2026-07-28 (verify-gate conclusion — supersedes this record's earlier "by-design-vs-regression UNCONFIRMED" flag): BY-DESIGN STUB.** Git-confirmed, and registrar-verified independently rather than accepted on report: `build_conversation_graph` (`backend/agent/conversation_graph.py:32-36`) accepts only `research_graph`, `checkpointer` and `store` — it has never accepted a `reranker` parameter, and `git log --all -S'reranker' -- backend/agent/conversation_graph.py` returns ZERO commits, so the identifier has never appeared in that file in any revision. `validate_citations` (`nodes.py:633`) declares `*, reranker: Any = None`, a keyword-only parameter the graph therefore never supplies. The node was scaffolded into the graph and never wired. This is NOT a wiring regression: nothing was ever connected and subsequently broken.

**The finding STANDS — severity MAJOR and decision v1.0-fix are unchanged by this adjudication.** A by-design stub that silently disables citation-alignment QA on 100% of requests, while the graph presents the node as an active stage (it emits a `ranking` stage-timing key — see BUG-103), is a real defect: an entire verification stage is absent while appearing wired. "By design" describes how it got here, not whether it should be fixed. Related: BUG-103 (same root cause, timing-symptom side); spec-05 accuracy/citations context.
