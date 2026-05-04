# Spec-033 — Learned Components (v1.1 portfolio sprint)

> **Status**: STUB / proposal placeholder.
> Full SDD artifacts (spec, plan, tasks) materialize after v1.0 ships and the prerequisites listed below land.
> Created: 2026-05-04 alongside spec-28 Wave 3 close-out (PR #72).

## Intent

Replace three v1.0 heuristics with learned models trained on data the v1.0 system either collected or can synthesize from its existing inputs. The narrative is the senior signal: ship strong heuristics in v1.0, instrument the system, then learn from production traffic.

## The README paragraph (target framing)

> *"v1.1 introduces three learned components, each replacing a v1.0.0 heuristic — query complexity routing (Adaptive-RAG, NAACL 2024), answer confidence calibration (TPA-style XGBoost ensemble + Wu et al. prior-contradiction score), and a domain-adapted bi-encoder fine-tuned on PROMPTGATOR-synthesized data from the v1.0.0 golden set. All three are trained on data the v1.0.0 system collected or can synthesize from its existing inputs."*

## Three components

### Component 1 — Adaptive query-routing classifier

Routes queries to (no retrieval | single-shot retrieval | multi-step research loop) based on complexity. The current system runs every query through the full 3-layer LangGraph; classifier-driven routing reduces compute by ~4× without accuracy loss (Soyeong Jeong et al., NAACL 2024).

| | |
|---|---|
| **Reference paper** | [Adaptive-RAG (Jeong et al., NAACL 2024)](https://arxiv.org/abs/2403.14403) |
| **Replaces** | "Every query → full 3-layer graph" (current behavior) |
| **Backbone** | DistilBERT fine-tune OR logistic regression over `nomic-embed-text` outputs |
| **Training data** | 300–500 hand-labeled queries; bootstrap from spec-28 golden set + production traces |
| **Compute** | Negligible — minutes on any GPU; CPU-feasible |
| **Quality target** | macro-F1 ≥ 0.79 (RAGRouter-Bench reported 0.79–0.93) |
| **Where it sits** | Conversation graph entry, before Research subgraph dispatch |
| **Source files to touch** | `backend/agent/conversation_graph.py`, new `backend/agent/router.py` |

### Component 2 — Learned confidence calibrator

XGBoost (or small MLP) trained on the 5 existing confidence signals + RAGAS faithfulness/answer-relevance + Wu et al. prior-contradiction score → human-rated correctness label.

| | |
|---|---|
| **Reference papers** | [TPA (arXiv:2512.07515)](https://arxiv.org/abs/2512.07515) — XGBoost ensemble for RAG hallucination detection; [Wu et al. 2024 (arXiv:2404.10198)](https://arxiv.org/abs/2404.10198) — prior-contradiction signal |
| **Replaces** | The 5-signal heuristic in `backend/agent/confidence.py` |
| **Why this is the strongest "senior" candidate** | Identifies a documented heuristic and replaces it with a learned model. Per Report 2 §3.4, this is "the canonical ML maturity move." |
| **Training data** | 500–2000 labeled answers. Spec-28 RAGAS dataset is the seed; expand from `query_traces` table populated post-launch |
| **New feature engineered** | Prior-contradiction score (per Wu et al.): grade the answer once with retrieval and once without; large divergence = hallucination risk. ~+1-3 pp calibration AUC |
| **Compute** | Trivial — XGBoost trains in seconds on CPU |
| **Source files to touch** | `backend/agent/confidence.py`, new `backend/agent/confidence_calibrator.py` |

### Component 3 — Domain-adapted bi-encoder fine-tune

Fine-tune the chosen embedding model on `(query, positive_doc)` pairs synthesized from the existing corpus + spec-28 seed via PROMPTGATOR.

| | |
|---|---|
| **Reference papers** | [PROMPTGATOR (Dai et al., arXiv:2209.11755)](https://arxiv.org/abs/2209.11755) — synthetic Q&A from k seed examples; sentence-transformers v3+ `MultipleNegativesRankingLoss` |
| **Replaces** | Off-the-shelf embedder (whichever wins F1 mitigation pre-launch) on in-domain queries |
| **Training data** | 1k–6k synthetic (query, doc) pairs generated via PROMPTGATOR from spec-28's 20-pair seed + `docs/Collection-Docs/` corpus. Cost: ~$1 of API spend. **Filter step required** (~50 LOC): drop pairs where embed-similarity(passage, generated_question) is below threshold, OR ask qwen2.5:7b "is this question answerable from this passage" yes/no |
| **Quality target** | +6–8 pp NDCG@10 on in-domain eval slice (Phil Schmid reports +7.4% on 6.3k samples) |
| **Compute** | ~30 min on RTX 3090 for 99k pairs; ~$1 cloud cost |
| **Why moved up from v1.2 to v1.1** | PROMPTGATOR removes the "needs production traces" dependency. Synthetic data from existing inputs is sufficient |
| **Source files to touch** | New `scripts/promptgator_synthesize.py`, new `scripts/finetune_embedder.py`, model artifact path config |

## Hard prerequisites

These MUST land before spec-33 implementation can begin:

1. **v1.0 must ship** — provides production query traces (~2 weeks min runtime) used as additional training data for the calibrator
2. **RAGAS execution unblocked** — issue [#73](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/73). Calibrator's labels come from RAGAS faithfulness scores; cannot proceed without them
3. **F1 mitigation completed** — pre-launch retrieval baseline must be stable so PROMPTGATOR generates high-quality synthetic data and the bi-encoder fine-tune has a meaningful starting point
4. **Citation propagation audit** — issue [#78](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/78). Need full `(doc_id, parent_chunk_id, child_chunk_id)` chain to evaluate the router and calibrator faithfulness

## Out of scope for spec-33

Per the four research reports, these are explicitly NOT spec-33:

- **Custom cross-encoder reranker training** — `mxbai-rerank-large-v2`, `jina-reranker-v3` were trained on hundreds of millions of mined hard negatives. Cannot beat them with our corpus
- **LoRA query rewriter** — prompt-replaceable; weak portfolio framing
- **Custom RAG-eval classifier** — RAGAS, ARES, Cleanlab TLM exist
- **GraphRAG / LightRAG** — defer until parent/child shown insufficient (consider for v1.2)
- **RAPTOR** — defer until long-document synthesis is shown to be the bottleneck

## Anti-goals

- Do not add ML for ML's sake — each component must replace a documented heuristic
- Do not bundle this with the launch — v1.0 ships first
- Do not over-engineer the synthetic data pipeline — PROMPTGATOR's quality bar is "20 examples randomly sampled to 2-8 per generation"; matching that is sufficient

## Estimated scope

- **Total**: ~1.5–2 weeks of focused work
- **Components in dependency order**: F1 mitigation (pre-launch) → adaptive router → confidence calibrator → bi-encoder fine-tune
- **Each component has its own RAGAS A/B comparison** measuring lift over v1.0

## Source documents

The full reasoning behind these picks lives in:

- `claudedocs/research_llm_wikis_vs_agentic_rag_2026-05-04.md` — architectural pattern comparison
- `claudedocs/research_pytorch_tf_roi_2026-05-04.md` — ROI analysis on training custom models
- `claudedocs/research_promptingguide_rag_pages_2026-05-04.md` — PROMPTGATOR + Wu et al. discoveries
- `claudedocs/Advanced Techniques for Professional-Grade Agentic RAG on Local LLMs.md` — production reference architecture

## Next steps

1. Run F1 mitigation experiment (pre-launch — separate branch, this week)
2. Ship v1.0 (specs 30 → 31 → 32)
3. Resolve issue [#73](https://github.com/Bruno-Ghiberto/The-Embedinator/issues/73) (RAGAS unblock)
4. ~2 weeks of v1.0 production traffic accumulates
5. Run `/sdd-new spec-033-learned-components` to expand this stub into full proposal → spec → design → tasks → implementation
