# BUG-098: No embedder/collection compatibility check; query embedded with wrong model

- **Severity**: CRITICAL
- **Layer**: Backend
- **Discovered**: 2026-07-10T15:29:14Z in Phase 5 (P5-S4)
- **Phase scenario**: P5-S4
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Chat against a collection whose index was built by a different embedder than the app's default. Live repro: select `nag-corpus-bge-m3` (embedding_model=bge-m3, Qdrant dense dim 1024).
2. Ask any question.
3. The chat sends `embed_model: null`, so `chat.py:106` falls back to `settings.default_embed_model` = `nomic-embed-text` (768-dim).
4. Qdrant rejects every search: `Wrong input: Vector dimension error: expected dim: 1024, got 768` (verbatim, x4).
5. Trace `c9d5d6c5`: `retrieval_hybrid_search_complete` = 0, `retrieval_hybrid_search_failed` = 4.

## Expected
The system should validate that the query's embedder matches the collection's recorded embedder before searching, or select the correct embedder automatically.

## Actual
The retrieval path never checks embedder compatibility; it embeds with whatever the request/config specifies, and Qdrant rejects the resulting dimension mismatch.

## Artifacts
- Screenshot: screenshots/BUG-098-fifty-citations-zero-retrievals.png (gitignored)
- Log excerpt: logs/BUG-098-embedder-collection-mismatch.log (gitignored)
- Trace: null

## Root-cause hypothesis
The retrieval path never checks which embedder built the target collection. `collections.embedding_model` is recorded at ingest (`api/collections.py:77`) and, per a repo-wide `rg "embedding_model" backend/` (7 hits, all in collections.py/sqlite_db.py/schemas.py), is read by NOTHING at query time. `searcher.py`, `agent/tools.py`, and `agent/research_nodes.py` never reference it. The query is embedded with `body.embed_model or settings.default_embed_model` (`chat.py:106`) — whatever the request or config says, never what the collection requires. Fixing this needs new plumbing: thread the collection's recorded `embedding_model` through `ResearchState` and compare it to the request embedder before searching.

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: v1.0-fix
- **GitHub issue**: https://github.com/Bruno-Ghiberto/The-Embedinator/issues/160
- **Rationale**: collections.embedding_model is recorded at ingest and read by nothing at query time — retrieval returned zero chunks while fifty citations rendered, and two same-dimension different-model collections would silently search a semantically unrelated embedding space with no error at all.

## Notes
Why CRITICAL — this defeats the headline feature, and the reproduced case is the LUCKY one:
- The product's headline claim is "verifiable citations." In this repro it retrieved ZERO chunks and the user saw a confident-looking answer with FIFTY citations (see BUG-070 — accumulated from the prior turn on a different collection).
- The dimension mismatch reproduced here fails LOUDLY (to the logs; the user still gets a misleading answer). That is the safe failure. Two collections built with DIFFERENT embedders that happen to share a dimension (e.g. two different 768-dim models) would produce a query vector Qdrant accepts as structurally valid and searches WITHOUT ERROR — returning nearest neighbours from a semantically unrelated embedding space, with a normal-looking confident answer built on garbage retrieval, zero error, zero log signal, zero circuit-breaker trip. Confirmed possible by code absence (no embedder-identity check anywhere) but NOT reproduced live (no two same-dim/different-model collections available). Recorded as a code-confirmed worst case and a recommended targeted probe (this phase or Phase 6), NOT as reproduced fact. The reproduced dimension-mismatch case alone justifies CRITICAL; the silent-garbage case is why it is not merely MAJOR.

Blast radius: the phantom-citation display requires a prior successful turn in the same session (else `aggregate_answers()` dedups to 0 citations) — but the retrieval FAILURE and the misleading message (BUG-100) need no prior turn. And it does NOT require a collection switch: any transient search failure after one good turn shows the same phantom citations, which ties this to the general multi-turn accumulation family (BUG-070/BUG-078).

Dedup-check performed against all 74 existing bugs: `grep -ril "Vector dimension|expected dim|embedding_model"` at query time across bugs/ = ZERO. BUG-025 is a `:latest` tag STRING-match in `/api/health` (availability check), unrelated. BUG-039 is orphaned Qdrant COLLECTIONS from failed ingestion. No existing bug owns "query embedder never validated against collection embedder." New.
