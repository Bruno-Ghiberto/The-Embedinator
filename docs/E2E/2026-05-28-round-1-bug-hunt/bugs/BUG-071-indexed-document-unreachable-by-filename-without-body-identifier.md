# BUG-071: Indexed document unreachable by its filename when body text omits the identifier

- **Severity**: MAJOR
- **Layer**: Retrieval
- **Discovered**: 2026-07-03T00:00:00Z in Phase 3 (P3-S6)
- **Phase scenario**: P3-S6
- **BLOCKER-PATCHED**: no
  <!-- after patching: yes — commit <SHA>, Pilot Y at <ISO-8601> -->

## Steps to Reproduce
1. Collection `nag-corpus-spec28` contains `NAG-E207.pdf`, correctly ingested (7 parent / 53 child chunks, status=completed, `document_id 684df090-2254-4607-af3c-7a241023b0c1`).
2. Ask: "¿De que trata la NAG-E207?"
3. Observe: the model declines — "None of the provided passages mention or reference a document called 'NAG-E207'. Therefore, I cannot answer the sub-question based on the given information as no relevant content was found to cite." Confidence Low 35%, cites [5]. The 5 retrieved sources are NAG-213/240/204/222/200.pdf — NAG-E207 is ABSENT from the results, and all 5 retrieved sources carry a negative `relevance_score` (-7.51 to -9.75).
4. Confirm via direct DB query on `document_id 684df090` that the document IS present, ingested, and indexed — the decline is a retrieval failure, not an ingestion gap.

## Expected
Naming an indexed, collection-visible document by its exact filename/identifier should surface that document's content (or at minimum retrieve it as a candidate), not produce a confident false "this document doesn't exist in the corpus."

## Actual
The model produces a confident decline for a document that IS indexed and visible in the collection, because retrieval structurally never surfaces it as a candidate for a query built around its own catalog identifier.

## Artifacts
- Screenshot: screenshots/BUG-071-nag204-vs-nag-e207-decline.png (gitignored) — two-turn chat: NAG-204 High 96% followed by the NAG-E207 decline Low 35%.
- Log excerpt: logs/BUG-071-nag-e207.log (gitignored)
- Trace: null

## Root-cause hypothesis
HIGH confidence, DB-verified — the document filename/catalog identifier is NOT part of the retrieval signal anywhere in the pipeline. A direct `parent_chunks` query for `document_id 684df090` shows "NAG-E207" / "E207" / "E-207" appears 0 times across all 7 parent chunks; the document self-identifies internally only as "ET-ENRG-GD-Nº 7 / Año 2000" (title: "ACCESORIOS ROSCADOS DE FUNDICIÓN ESFEROIDAL PARA USO EN CAÑERÍAS DE GAS"). BM25/sparse retrieval operates on body text only, so it cannot match the query term "NAG-E207" against a document that never contains that string; dense/semantic retrieval has no exploitable signal for a bare catalog code with no supporting body context either. The ingestion pipeline never injects the source filename/catalog identifier into indexed content, nor uses it as a retrieval boost or metadata filter. CONTROL (rules out a general indexing gap): `NAG-204.pdf`'s parent chunks contain the literal string "NAG-204" 22 times — which is exactly why the P3-S5 / Q-007 query succeeded. Self-identifying documents work correctly; NAG-E207 fails specifically because it is the anomaly (a document whose body never restates its own public-facing name).

## Triage (filled in Phase 8 for MAJOR+)
- **Decision**: <v1.0-fix | v1.1-defer>
- **GitHub issue**: <url>
- **Rationale**: <one sentence>

## Notes
Trigger/impact: CONDITIONAL, not universal — affects any correctly-ingested document whose body text does NOT echo its own filename/catalog identifier; many documents self-reference internally and are unaffected. But when it does hit, the user receives a confident "this document doesn't exist" for a document they can see in their own collection — a trust/correctness failure at the retrieval layer, not a rare edge case restricted to one file.

Scope note (per Lead): this is explicitly NOT an A-003 answer-quality issue — the model's decline is CORRECT given what retrieval actually returned (empty/irrelevant). The defect is that retrieval structurally cannot reach an indexed document by its own identifier (a false negative at the retrieval layer), which is distinct from relevance/ranking tuning.

Cross-refs: BUG-056 (rewrite_query also failed on this turn — OutputParserException → fallback passed the raw query — but this is NOT the root cause: even a working rewrite could not bridge "NAG-E207" → "ET-ENRG-GD-Nº 7", since no retrieval signal connects the two strings); BUG-062 (the 5 negative-score sources returned here are the same unclamped-CrossEncoder-logit display defect); BUG-064 (this turn ran on session `119b2304-9df8-42b6-822f-31e84f6ada37`, a fresh thread separate from the same-chat NAG-204 turn on session `2bfae3de-4b4e-446e-b569-cab94c60c6c1` — session-break corroboration for BUG-064, but a distinct bug from this one).

Session 119b2304-9df8-42b6-822f-31e84f6ada37; trace c33369b1-fa81-42a2-a4b8-4db03109c125. P3-S6 side-finding (surfaced during the mid-stream-navigation scenario, not the scenario's primary target). Lead+Pilot approved MAJOR/Retrieval.
