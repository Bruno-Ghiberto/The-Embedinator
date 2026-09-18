# Retrieval benchmark results — 2026-09-18

The cross-encoder reranker is the only retrieval change this benchmark can prove: it lifts nDCG@10 from 0.30 to 0.60 (p = 0.0005). The three first-stage retrievers (dense, sparse BM25, hybrid RRF) cannot be told apart at n = 17. An earlier reading of the same runs claimed more than that; it rested on inflated labels and is withdrawn below.

Scope: the retriever alone, offline, against `golden-qa.yaml`. No agent, no answer generation. Driven by `scripts/retrieval_eval.py`; qrels in `retrieval-qrels.tsv` next to this file.

## Result

17 questions, top 20 per question, graded labels 0/1/2 (grade >= 1 counts as relevant for recall, hit and MRR; nDCG weights by grade).

| config | recall@10 | recall@20 | hit@10 | hit@20 | MRR@10 | nDCG@10 | nDCG@20 |
|---|---|---|---|---|---|---|---|
| dense | 0.4206 | 0.5814 | 0.5882 | 0.7647 | 0.3382 | 0.2894 | 0.3318 |
| sparse (BM25) | 0.4324 | 0.6922 | 0.7059 | 0.8824 | 0.2738 | 0.2641 | 0.3477 |
| hybrid (RRF) | 0.4500 | 0.7186 | 0.7059 | 0.8824 | 0.3706 | 0.2956 | 0.3769 |
| hybrid + rerank | 0.6990 | 0.7186 | 0.8824 | 0.8824 | 0.7451 | 0.6028 | 0.6094 |

Paired permutation tests, two-sided, exact (all 2^17 sign vectors), diff = B minus A:

| A -> B | metric | diff | p |
|---|---|---|---|
| hybrid -> hybrid + rerank | nDCG@10 | +0.3072 | 0.0005 |
| hybrid -> hybrid + rerank | MRR@10 | +0.3745 | 0.0059 |
| hybrid -> hybrid + rerank | recall@10 | +0.2490 | 0.0156 |
| hybrid -> hybrid + rerank | recall@20, hit@20 | +0.0000 | 1.0000 |
| hybrid -> dense | recall@20 | -0.1373 | 0.3438 |
| hybrid -> dense | nDCG@10 | -0.0062 | 0.8926 |
| hybrid -> sparse | MRR@10 | -0.0968 | 0.1211 |
| dense -> sparse | recall@20 | +0.1108 | 0.5288 |

For the three first-stage pairs the table shows the smallest p found; every other metric is weaker.

## What this supports, and what it does not

| Claim | Verdict |
|---|---|
| Reranking improves ranking quality in the top 10 | Supported. Large effect, p <= 0.006 on nDCG@10 and MRR@10, stable under every label variant below. |
| Reranking finds more relevant chunks | Not at depth 20. It reorders essentially the same 20 candidates (the sets differ by one chunk on two questions), so recall@20 and hit@20 cannot move. |
| Hybrid beats dense | Not supported. The direction favours hybrid (recall@20 0.72 vs 0.58) but p = 0.34. |
| Hybrid beats sparse, or sparse beats dense | Not supported. No metric reaches p < 0.12. |
| Every question is answered within the top 20 | False. hit@20 is 0.8824 for hybrid: Q-007 and Q-011 have no relevant chunk in its top 20. Dense misses four (Q-001, Q-003, Q-006, Q-020). |

With 17 questions only a large effect is detectable. "Not supported" means this benchmark cannot show it, not that the effect is absent.

## Label quality: why the first reading was withdrawn

The labels come from an LLM judge (`qwen3:14b`, temperature 0) over a pool of 671 (question, chunk) pairs: the union of the top 20 of all four runs, so every run's top 20 is fully judged (340/340 per config).

The first judge rubric defined grade 1 as "same topic or section" and grade 2 as containing "a key part of the reference answer" while that answer sat in the same prompt. A manual audit of its 37 grade-2 rows found 19 sound, 14 inflated and 4 wrong, plus a flood of grade-1 rows on the cross-norm questions (every chunk of the right norm, tables of contents included).

The rubric was rewritten (`JUDGE_PROMPT` in `scripts/retrieval_eval.py`; each clause is pinned by a test naming the defect it closes) and the full pool re-judged:

| grade | first rubric | current rubric |
|---|---|---|
| 0 | 511 | 617 |
| 1 | 123 | 35 |
| 2 | 37 | 19 |

Every change is a demotion: nothing was promoted, so the current relevant set is a strict subset of the old one.

### Hand corrections applied on top of the judge

Comparing the re-judge with the manual audit left six rows where the judge is wrong. They are corrected in the tracked qrels:

| qid | chunk | source | judge -> qrels | why |
|---|---|---|---|---|
| Q-002 | `5775e5cc` | NAG-240 p5 | 1 -> 0 | scope of another norm (multilayer pipe); shares "28 mbar / GN-GLP" only |
| Q-004 | `c96d6477` | NAG-235 p23 | 1 -> 0 | venting-valve test table, not the inlet pressure range |
| Q-015 | `dcf374d2` | NAG-E209 p84 | 1 -> 0 | scope of another norm (copper pipe) |
| Q-007 | `2a5e63f6` | NAG-204 p1 | 2 -> 1 | title page and table of contents |
| Q-017 | `50dd6104` | NAG-226 p7 | 2 -> 1 | portable leak-detector sweep, a different test than the one asked about |
| Q-013 | `9fda94cf` | NAG-200 p73 | 1 -> 2 | states "aprobados según la NAG-214", like its two grade-2 siblings |

### Q-014 is excluded

Its reference answer asserts that NAG-226 requires CO detection devices to comply with NAG-204. No NAG-226 chunk in the corpus says so; the link is the author's synthesis, so no retriever can be scored on it. The record stays in `golden-qa.yaml` with `retrieval_eval_excluded` carrying the reason, and the loader skips it. Q-018 and Q-019 (out-of-scope decline questions, `source_doc: null`) were never part of the retrieval eval.

## Sensitivity: do the conclusions depend on the labels?

| labels | n | rerank nDCG@10 gain | hybrid -> dense recall@20 | hybrid hit@20 |
|---|---|---|---|---|
| first rubric (withdrawn) | 18 | +0.2507, p < 0.0001 | -0.1430, p = 0.0256 | 1.0000 |
| current rubric, as judged | 17 | +0.3042, p = 0.0004 | -0.1490, p = 0.2461 | 0.8824 |
| current rubric + 6 corrections (tracked) | 17 | +0.3072, p = 0.0005 | -0.1373, p = 0.3438 | 0.8824 |
| current rubric, grade 2 only | 16 | +0.3031, p = 0.0039 | -0.2500, p = 0.2188 | 0.8125 |

The reranker result survives every variant. The hybrid-over-dense result and the perfect hit@20 existed only under the first rubric. The six corrections move numbers in the third decimal and change no conclusion. "Grade 2 only" drops Q-020, which has no grade-2 chunk.

## Known limits

- n = 17. Treat every non-significant row as "unknown", not "equal".
- Follow-up questions (Q-015 to Q-017) are retrieved standalone, without the conversation rewrite the agent applies, and the judge sees them without their parent question. They say only "esos reguladores" or "esa prueba", so the rubric's cross-norm and different-test rules cannot apply; two of the six corrections (Q-015, Q-017) are on these questions.
- Q-020 expects the agent to disambiguate, so "relevant" is not well defined for it. Its labels pick one reading.
- The run files do not record which embedding and reranker models produced them; they are whatever `Settings` resolved from `.env` on 2026-09-11 and 2026-09-12. Collection: `emb-61b0dd9f-05b9-4bed-a502-fae360bc65ed`, the only NAG collection with BM25 sparse vectors.

## Reproduce

Runs, pool and review CSVs live under `data/retrieval-eval/` (gitignored). From the repo root, with Qdrant and Ollama up:

```bash
for c in dense sparse hybrid hybrid_rerank; do .venv/bin/python scripts/retrieval_eval.py run --config $c; done
.venv/bin/python scripts/retrieval_eval.py pool --runs data/retrieval-eval/{dense,sparse,hybrid,hybrid_rerank}.trec
.venv/bin/python scripts/retrieval_eval.py judge --pool data/retrieval-eval/pool.jsonl --out data/retrieval-eval/review.csv
# review the CSV, then:
.venv/bin/python scripts/retrieval_eval.py qrels --review data/retrieval-eval/review.csv \
    --out docs/E2E/2026-04-24-bug-hunt/retrieval-qrels.tsv
.venv/bin/python scripts/retrieval_eval.py eval --qrels docs/E2E/2026-04-24-bug-hunt/retrieval-qrels.tsv \
    --run data/retrieval-eval/hybrid.trec --run data/retrieval-eval/hybrid_rerank.trec
```

`judge` resumes by (qid, chunk), so re-judging after a rubric change needs a fresh `--out`; pointing it at an existing review reports "0 pending" and keeps the old labels.

## Next step

More questions, not more metrics: the first-stage retrievers stay unresolved until the golden set grows. Passing the parent question to the judge for `follow_up_of` records would remove the largest remaining source of label error.
