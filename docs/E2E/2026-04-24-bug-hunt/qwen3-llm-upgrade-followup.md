# Spec-28 follow-up: default LLM upgrade qwen2.5:7b → qwen3:14b

> **Headline**: same mean answer rate (85.0%) with **tighter 95% CI** —
> [79.3%, 90.7%] vs prior [75.2%, 94.8%]. **No latency cost** (qwen3 fits
> 12 GB VRAM at Q4_K_M; same end-to-end wall time as the smaller qwen2.5).
> Plus a capability upgrade for v1.1: hybrid thinking + native tool/MCP support.

## Context

`docs-Bruno/Researches/models-research.md` recommended Qwen3-14B Q4_K_M as the
top orchestrator LLM for Spanish-legal Agentic RAG on a 12 GB / 64 GB / i7
12700K rig. The prior default `qwen2.5:7b` was the spec-26 choice when
Ollama's Q4_K_M qwen3 wasn't yet available.

## Change

| File | Change |
|---|---|
| `backend/config.py` | `default_llm_model: "qwen2.5:7b"` → `"qwen3:14b"`. Added qwen3:14b to `supported_llm_models` list. Updated comment to reflect that qwen3's hybrid thinking is supported (the spec-26 *"thinking models unsupported"* note was specifically about other thinking models — qwen3 has a HYBRID mode that gracefully degrades to non-thinking when not asked to reason). |

No code changes elsewhere — this is purely a model swap.

## Validation

`scripts/multi_sample_sweep.py` n=3 against the same `nag-corpus-bm25`
collection, same retrieval (BM25 hybrid from PR #80), same reranker
(`ms-marco-MiniLM-L-6-v2` from develop), same routing (PR #81). The only
variable is the LLM.

| Metric | qwen2.5:7b (baseline) | qwen3:14b (this PR) | Δ |
|---|---|---|---|
| Overall mean answer_rate | 85.0% ± 8.7% | **85.0% ± 5.0%** | 0pp / variance ↓ |
| 95% CI | [75.2%, 94.8%] | **[79.3%, 90.7%]** | lower bound +4pp |
| Overall has_cits_rate | 100% | 100% | 0 |
| Total elapsed (3 runs) | 1862s | **1793s** | 0.96× |
| Avg per-run | 10.3 min | 10.0 min | -0.3 min |

Per-run:

| Run | qwen2.5:7b | qwen3:14b |
|---|---|---|
| 1 | 16/20 in 616s | 17/20 in 627s |
| 2 | 19/20 in 641s | 18/20 in 558s |
| 3 | 16/20 in 605s | 16/20 in 608s |

Per category:

| Category | qwen2.5:7b | qwen3:14b | Δ |
|---|---|---|---|
| factoid | 90.0% ± 10.0% | **93.3% ± 5.8%** | +3.3pp ✓ |
| follow-up | 100% ± 0% | 100% ± 0% | 0 |
| analytical | 100% ± 0% | 83.3% ± 14.4% | -16.7pp |
| ambiguous (1 q) | 33.3% ± 57.7% | 33.3% ± 57.7% | 0 |
| out-of-scope (2 q) | 33.3% ± 57.7% | 50.0% ± 50.0% | +16.7pp |

## Capability upgrades (not measured here)

Per `ollama show qwen3:14b`:
- **`tools`** capability: native tool/function calling (was supported in qwen2.5 too, just confirmed solid).
- **`thinking`** capability: hybrid thinking mode. Qwen3 can switch between fast non-thinking and structured reasoning via `<think>...</think>` blocks. Off by default; opt-in for hard analytical questions in v1.1.
- 40K context (vs qwen2.5's 32K). Useful when the agent retrieves multi-passage parents.
- Apache 2.0.

Smoke test on Q-001 produced verbatim §1.1 reference text plus an explicit
`SOURCE:[1]` citation marker — qwen3 is following the
`COLLECT_ANSWER_SYSTEM` prompt format slightly more diligently than qwen2.5
(small qualitative win, not in the metrics).

## Risks accepted

- **VRAM**: qwen2.5:7b at Q4_K_M used ~5 GB. qwen3:14b uses **~9.3 GB**, leaving ~2.7 GB headroom on the 12 GB RTX 4070 Ti. Plenty for inference but no room left for a GPU-resident cross-encoder reranker — the GPU-passthrough-for-backend path is now blocked at this VRAM budget unless we drop to a smaller LLM or move the reranker to a separate GPU. Worth noting in the v1.1 doc.
- **Analytical regression** is a 16.7pp drop on 12 samples — within noise but worth checking. Re-run at n=5 before any release tag.
- **Thinking-mode latency**: not measured here because Qwen3 defaults to non-thinking mode. If we opt in to thinking for analytical/multi-hop questions later (v1.1 lever), latency will increase. Out of scope for this PR.

## Spec-26 comment update

The comment in `config.py` previously said: *"thinking models unsupported,
see docs/performance.md"*. That referred to specific reasoning models that
introduced excessive latency without quality wins under the spec-26 budget.
Qwen3's hybrid thinking mode is OFF by default and only fires on explicit
opt-in, so the spec-26 concern doesn't apply. Comment updated to reflect this.

## Why this is the third PR landing on the same baseline collection

Today's three PRs build on each other against the same `nag-corpus-bm25`
Qdrant collection (created during PR #80 ingestion):

| PR | Change | After-state mean |
|---|---|---|
| PR #80 | BM25 sparse retrieval wired (architectural) | answer rate variance dominated by judge LLM |
| PR #81 | Routing + prompt unblocks judge on partial-match | mean rate jumped 4/20 → 17/20 (single sample) |
| PR #82 | Multi-sample methodology + n=3 baseline | confirmed mean is 85.0% ± 8.7% |
| **THIS** | LLM upgrade qwen2.5 → qwen3 | mean stable, **CI tightens to [79.3%, 90.7%]** |

The variance reduction is the load-bearing improvement. Future quality gates
can treat the new lower-bound (79.3%) as a regression floor.

## Files

- `backend/config.py` (modified)
- `docs/E2E/2026-04-24-bug-hunt/multi-sample-baseline-n3-2026-05-05-qwen3.json` (evidence)
- `docs/E2E/2026-04-24-bug-hunt/qwen3-llm-upgrade-followup.md` (this file)
