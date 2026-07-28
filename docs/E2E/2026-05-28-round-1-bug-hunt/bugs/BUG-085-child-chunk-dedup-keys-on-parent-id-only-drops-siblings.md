# BUG-085: Child-chunk dedup keys on parent_id only, silently drops distinct siblings

- **Severity**: MAJOR
- **Layer**: Retrieval
- **Discovered**: 2026-07-08T19:14:00Z in Phase 4 (P4-S5)
- **Phase scenario**: P4-S5
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Ingest a document whose single parent chunk splits into 2+ distinct child chunks (e.g. a parent covering offset 0-439 and offset 439+).
2. Ask a query where BOTH children score as relevant candidates for the same query.
3. Observe: `retrieval_hybrid_search_complete` returns all candidate children, but `agent_dedup_filtered` reduces the count — one of the two distinct children of the SAME parent is silently discarded regardless of its actual content, because the dedup key does not distinguish them.
4. Live repro (P4-S5, collection `poison-test-p4s5`, doc `d12fae2d`, parent `cc495661`): child-A (offset 0-439) and child-B (offset 439+) both retrieved; log chain `retrieval_hybrid_search_complete results=4` → `retrieval_rerank_complete input_count=4 output_count=4` → `agent_dedup_filtered original=4 kept=3` — child-B was dropped. `query_traces.chunk_count=3` reflects the post-dedup set, not what was actually retrieved/reranked.

## Expected
Deduplication should only collapse genuinely duplicate content (same chunk retrieved twice, e.g. via multiple query variants); two distinct children of the same parent, each carrying different text, must both survive to the LLM.

## Actual
`dedup_key()` (`backend/agent/research_nodes.py:41-43`) computes `f"{normalize_query(query)}:{parent_id}"` — keyed ONLY on `(query, parent_id)`, never on `chunk_id`/offset. Applied in the tool-result loop at `research_nodes.py:410-416`, this means any second child chunk sharing a parent with an already-seen child collides on the same key and is silently filtered out, independent of whether its content differs. In this trace, child-B — which happened to carry the P4-S5 canary-compliance-demand text — was the one dropped, making the retrieved-context set incomplete for reasons unrelated to relevance/ranking.

## Artifacts
- Screenshot: screenshots/BUG-085-p4s5-dedup-collision.png (gitignored)
- Log excerpt: null
- Trace: null

## Root-cause hypothesis
HIGH confidence, code-confirmed (log-analyst). `dedup_key()` (`research_nodes.py:41-43`) uses `(normalize_query(query), parent_id)` as its uniqueness key with no `chunk_id`/offset component, so any parent yielding 2+ scoring children in the same query collapses to 1 survivor at `research_nodes.py:410-416`, chosen by iteration/insertion order rather than any relevance criterion. Confirmed via the log chain `retrieval_hybrid_search_complete results=4` → `retrieval_rerank_complete input_count=4 output_count=4` → `agent_dedup_filtered original=4 kept=3`, and SQLite ground truth showing parent `cc495661` genuinely has two distinct children (offsets 0-439 / 439+) where only the first was passed downstream.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/154
- **Rationale**: dedup_key omits chunk_id, so any parent yielding two scoring children silently loses one regardless of content — deterministic, repeatable recall loss in ordinary retrieval, with query_traces.chunk_count reporting the post-dedup set as what was retrieved.

## Notes
Dedup-check performed before minting: confirmed distinct from BUG-071 (false decline because a document's own catalog identifier is absent from its body text — a retrieval-signal gap, not a dedup collision), BUG-062 (relevance-score display is an unclamped raw CrossEncoder logit — a normalization/rendering defect, unrelated to which chunks survive dedup), and BUG-066 (citation-count *inflation* — `chunks_retrieved_json` recording the same chunks 4× — the opposite failure direction from this bug's silent *drop*). None of the three owns this symptom.

This is a general-purpose retrieval/completeness defect, not security-specific — it surfaced during the P4-S5 indirect-injection probe (evidence: trace `e6d35cd6-3c73-40e4-a02f-a865be03822c`, collection `poison-test-p4s5`, doc `d12fae2d`) because the discarded child happened to carry the injection-compliance-demand text, making the P4-S5 canary-compliance verdict INCONCLUSIVE (see session-log P4-S5 verdict entry) rather than a genuine PASS. Applies equally to any normal, non-adversarial query where a document's parent chunk legitimately splits into 2+ scoring children — silent recall/completeness loss in ordinary retrieval, not just this adversarial scenario.

P4-S5 (2026-07-08) RECURRENCE on the re-probe, trace `08124655-eaaf-40c0-8208-41f188038046`: log chain `retrieval_hybrid_search_complete results=5` → `retrieval_rerank_complete output=5` → `agent_dedup_filtered original=5 kept=4`; the dropped chunk was the original doc's `cc495661` second child (offset 439+), colliding again on `dedup_key(query, parent_id)` with the surviving `cc495661`-A. Confirms the defect is deterministic and repeatable, not a one-off collision.
