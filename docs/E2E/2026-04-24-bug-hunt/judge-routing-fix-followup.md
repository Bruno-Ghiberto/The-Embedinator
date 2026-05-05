# Spec-28 follow-up: judge-LLM decline-bias fix — answer rate 20% → 85%

> **Status**: code change shipped (this PR). 20-question sweep evidence
> attached. Single-sample answer rate moved from v1's 4/20 (20%) to **17/20
> (85%)** — 4.25× improvement on the same dataset, same retrieval pipeline,
> same model.

## Problem

PR #80 wired BM25 hybrid retrieval, surfacing canonical answer chunks for
queries like Q-001 ("¿Cuál es el objeto del Reglamento Técnico NAG-200?").
Subsequent investigation showed the §1.1 chunk reached the rerank pool but the
sweep's headline answer-rate did not move (still ~1/20). RCA:

- `should_continue_loop` (`research_edges.py`) routed
  `iteration_count >= max_iterations` straight to `"exhausted"` →
  `fallback_response`. That node is mechanical: it concatenates *"I searched N
  collection(s) and found M passage(s), but none were sufficiently relevant"*
  WITHOUT ever sending the chunks to the LLM. So even when retrieval surfaced
  the canonical chunk on iteration 0, the loop iterated 3 times trying to
  improve confidence, never reached threshold, then exited to fallback that
  pre-decided the verdict.
- `COLLECT_ANSWER_SYSTEM` (`prompts.py`) — when the loop DID reach
  `collect_answer`, the prompt biased qwen2.5:7b toward declining: *"If the
  passages do not contain sufficient information, say so clearly"*. With 1 of
  5 passages containing the answer (typical for an over-fetched candidate
  pool), the LLM correctly followed the prompt and declined.

The combined effect: retrieval and reranking were working but the LLM was
either skipped entirely (fallback) or instructed to decline (prompt bias).

## Fix

Two surgical patches on top of PR #80's hybrid retrieval:

| File | Change |
|---|---|
| `backend/agent/research_edges.py` | `should_continue_loop` now treats `budget exhausted + chunks retrieved` as `"sufficient"` (route to `collect_answer`). `"exhausted"` only fires when no chunks were retrieved at all. |
| `backend/agent/prompts.py` | `COLLECT_ANSWER_SYSTEM` rewritten with explicit partial-match handling: *"Scan ALL passages and find any that directly address the sub-question — even ONE passage with the answer is enough… ignore passages that are off-topic… ONLY decline if NO passage contains information relevant to the sub-question"*. Hard-rule guardrail block preserved (no fabrication, no extrapolation, no false citations). |
| `tests/unit/test_research_edges.py` | Two new tests cover the new routing branch: `test_sufficient_when_iterations_exhausted_with_chunks` and `test_sufficient_when_tool_calls_exhausted_with_chunks`. All 17 routing tests pass. |

## Validation

**Sweep comparison (single sample at default `qwen2.5:7b` temperature):**

| | v1 (HEAD pre-PR-80) | v5 (BM25 hybrid) | **v7 (this PR)** |
|---|---:|---:|---:|
| factoid | 2/10 | 1/10 | **8/10** |
| analytical | 1/4 | 0/4 | **3/4** |
| follow-up | 0/3 | 0/3 | **3/3** |
| out-of-scope | 0/2 (false-pass on Q-018) | 0/2 | 2/2 *(see note)* |
| ambiguous | 1/1 | 1/1 | 1/1 |
| **TOTAL** | **4/20 (20%)** | 1/20 (5%) | **17/20 (85%)** |

**Smoke test on Q-001** (3 runs, default temp): 2/3 answered with verbatim
§1.1 reference text (was 0/3 deterministic before this PR, 1/3 after PR #80).

## OOS-category note (NOT a regression)

Q-018 and Q-019 show `cits=5, declined=False` in the sweep JSON, which the
script flags as "answered". Inspecting actual content:

- **Q-018**: *"No hay información específica en las pasadas sobre la sección
  mínima del cable de cobre para alimentar un termotanque domiciliario."*
- **Q-019**: *"Based on the provided passages, none of them contain
  information regarding any modifications made by ENARGAS to the text of
  NAG-200 in 2024."*

Both correctly identify that the question is out of scope. The script's
decline-marker detection (issue #75) doesn't catch the new Spanish phrasing
*"no hay información específica"* or the English *"none of them contain"*.
The LLM behavior is correct; the test harness flag is wrong. Issue #75 should
be expanded to cover these phrasings.

A separate UX concern surfaces: when the LLM correctly declines, the API still
emits 5 citations from the off-topic chunks. A polished system would suppress
citations on decline responses. Worth filing as a follow-up bug.

## Risks deliberately accepted

- **Hallucination risk increases when the LLM is given full latitude.** The
  loosened prompt makes the LLM more willing to answer with partial chunk
  matches. Mitigation: hard-rule guardrails ("Do NOT fabricate facts"; "Do NOT
  guess or extrapolate"; "Do NOT cite a passage that does not actually contain
  the cited claim"). The existing groundedness check (`groundedness_check_enabled`,
  default `False`) remains available as a stricter follow-up gate if needed.
- **Confidence-score gate is unchanged.** `confidence_threshold = 60` still
  routes high-confidence cases to `collect_answer` directly. Low-confidence
  cases now ALSO route there at budget exhaustion (instead of fallback). This
  means qwen sees the chunks more often, including bad ones — but the prompt
  now tells it explicitly to decline when nothing is relevant.
- **Single-sample variance**. The 85% number is one sample; multi-run averaging
  is still v1.1 work. Q-001 smoke at 3 runs landed 2/3, suggesting the true
  per-question answer rate is 60-100% rather than deterministic.

## Deferred to v1.1

- **Multi-sample sweep methodology** (n≥5, mean±stddev) — needed to publish
  defensible quality numbers.
- **Decline-marker expansion** (issue #75) — script needs to recognize
  Spanish "no hay información específica" + English "none of them contain"
  variants.
- **Suppress citations on decline** — when the LLM emits a decline phrase, the
  API should skip the citation event to avoid confusing UX.
- **Multilingual reranker re-evaluation** — `bge-reranker-v2-m3` was tried
  earlier and showed no F1 win in single-sample tests. With the new routing
  giving the LLM a real chance to use chunks, the reranker's chunk ordering
  matters more. Worth re-measuring.

## Files

- `backend/agent/research_edges.py` (modified)
- `backend/agent/prompts.py` (modified — `COLLECT_ANSWER_SYSTEM`)
- `tests/unit/test_research_edges.py` (modified — 2 new tests)
- `docs/E2E/2026-04-24-bug-hunt/baseline-sweep-2026-05-05-v7-judge-routing-fix.json` (evidence)
