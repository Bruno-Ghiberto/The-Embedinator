# BUG-081: Citations attached to every retrieved chunk, even on declines

- **Severity**: MINOR
- **Layer**: Backend
- **Discovered**: 2026-07-03T19:21:29Z in Phase 4 (P4-S1)
- **Phase scenario**: P4-S1
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ask an out-of-scope question that the system correctly declines to answer.
2. Observe: the decline still displays a non-empty "N sources" count (e.g. "5/10 sources").
3. Expand the sources panel: it shows real retrieved candidates that the answer never actually referenced.

## Expected
A decline should show no sources, or sources should be gated on the answer actually referencing them.

## Actual
`backend/agent/research_nodes.py:581-601`, `_build_citations`, attaches a `Citation` for every retrieved chunk (`chunks[:20]`) unconditionally; the function's own docstring assumes citations map to what the LLM references, but the code never checks `answer_text`. The disclosure itself is honest — the listed sources are real retrieved candidates, not fabricated (verified via the raw NDJSON citation events) — but it is misleading on a decline, since none of them were actually used.

## Artifacts
- Log excerpt: logs/BUG-079-p4s2-fresh-english.network-response (gitignored) — shows citation events emitted alongside a decline answer.
- Screenshot: null
- Trace: null

## Root-cause hypothesis
HIGH confidence (log-analyst + frontend-inspector). `_build_citations` unconditionally maps retrieved chunks to citation objects with no check against whether the generation step actually referenced them or declined outright.

## Triage (filled in Phase 8 for MAJOR+)
<!-- MINOR — triage optional -->

## Notes
Cross-ref: BUG-080 (same decline-blind failure class, applied to confidence instead of citations). BUG-070/BUG-078 (feed the same citation-count bloat problem from a different angle — across-turn accumulation rather than within-turn over-attachment). BUG-061/BUG-063 (the citation click-through dead-end — a downstream consequence of citations being shown when they shouldn't be).

P4-S4 (2026-07-07) fresh repro data point: on the BUG-083 prompt-injection-compliance trace, `_build_citations` attached 5 sources to the literal "pwned" non-answer produced by a successful prompt injection — the unconditional-attachment behavior does not distinguish a hijacked non-answer from a genuine grounded answer any more than it distinguishes a decline.

P4-S4 (2026-07-08) fresh repro data point: system-prompt-extraction probe, trace `effe246c-caec-4e8b-99b2-b2462856c55f` (session `8c2ed0a7…`, created_at 2026-07-08T18:42:37Z, latency 35.2s, intent=rag_query, confidence_score=37, llm_model=qwen2.5:7b). 5 citations stapled to a pure decline, ALL with negative relevance (-9.83/-10.40/-10.50/-10.61/-10.69 → NAG-240/200/215/235/E209), confidence Low 37%, response in English.
