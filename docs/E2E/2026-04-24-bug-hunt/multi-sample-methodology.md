# Multi-sample sweep methodology — spec-28 v1.1 quality measurement

> **Why**: single-sample sweeps mislabel ±15-20pp temperature variance as
> "answer rate". The headline 4/20 (20%) baseline in PR #72, the 17/20 (85%)
> in PR #81, and the 1/20 result in v5 were all valid — they just measured
> different rolls of the same noisy distribution. This document specifies a
> reproducible multi-sample protocol so post-v1.0 quality numbers are
> defensible against that noise.

## Problem with single-sample sweeps

`qwen2.5:7b` runs at Ollama's default temperature (~0.8) for both the
orchestrator decisions and the final answer synthesis. Across 20 binary trials
("does this question answer correctly?"), per-run rate has a binomial-style
spread of roughly `√(p·(1-p)/n) · z` per question — which on a noisy judge
compounds to ±10-20pp on the headline metric depending on which questions roll
"answer" vs "decline".

Empirical evidence from today's session:

| Run | Configuration | Answered |
|---|---|---:|
| v1 (PR #72) | dense-only retrieval, default temp | 4/20 |
| v4 (smoke) | same code as v2, default temp, 11h later | 1/20 |
| v5 | BM25 hybrid, default temp | 1/20 |
| v6 | BM25 hybrid, temp=0.1 | 0/20 |
| v7 (PR #81) | + judge-fix, default temp | 17/20 |

v1 and v4 share code; the spread is pure variance. v6 vs v7 share retrieval
but differ in temperature; the difference reveals the conservative-judge axis.
A single-sample number (whether published in a README or used as a CI gate)
cannot distinguish these axes.

## Methodology

`scripts/multi_sample_sweep.py` runs the full 20-question golden Q&A sweep
**N times serially** against a target collection and emits aggregate statistics.

### Inputs

- **Dataset**: `docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml` (20 pairs locked at FR-014/FR-019).
- **Target collection**: any Qdrant collection ID with the corpus ingested. For
  the v1.1 baseline, the BM25 hybrid collection (`nag-corpus-bm25`) is the canonical target.
- **N**: number of independent runs. Default 5 (sufficient for 95% CI under
  normal approximation). 3 for fast smoke, 10 for tight bounds.
- **Backend state**: docker stack must be running and healthy before invocation.

### Configuration

```bash
SWEEP_N=5 \
SWEEP_OUT=docs/E2E/2026-04-24-bug-hunt/multi-sample-baseline.json \
SWEEP_COLLECTION=<uuid> \
python3 scripts/multi_sample_sweep.py
```

If `SWEEP_COLLECTION` is unset, the script reads `/tmp/bm25_collection_id.txt`
(written by `scripts/multi_sample_sweep.py`'s sister ingestion script).

### Per-question metrics

For each of 20 questions, the script records:

| Field | Definition |
|---|---|
| `runs[]` | list of N per-run records: `{cits, declined, elapsed_s, error, answer_first_200}` |
| `answered_count` | number of runs where `cits>0` AND not `declined`-flagged |
| `has_citations_count` | number of runs where `cits>0` (less noisy than `declined` flag — see Issue #75) |
| `errored_count` | network or HTTP errors |
| `answer_rate` | `answered_count / N` — per-question consistency |
| `mean_elapsed_s` / `stddev_elapsed_s` | latency distribution |

### Aggregate metrics

| Field | Definition |
|---|---|
| `aggregate_per_run[]` | per-run `{answered, has_cits, total, rate, has_cits_rate, elapsed_s}` |
| `summary_by_category[c]` | per-category `mean_rate`, `stddev_rate`, `ci95_rate` over runs |
| `overall.mean_rate` | mean of per-run rates |
| `overall.stddev_rate` | sample stddev of per-run rates |
| `overall.ci95_rate` | 95% CI under normal approx (`mean ± 1.96·SEM`) |

### Two metrics, not one

The harness reports BOTH `mean_rate` and `mean_has_cits_rate` because the
existing decline-marker detection (Issue #75) has known false positives —
real answers that happen to contain phrases like *"no se especifica"* in
passing get flagged as declined.

- **`mean_rate`** matches the existing single-sample sweep's "answered"
  number. Use for direct comparison against PR #72 / PR #80 / PR #81.
- **`mean_has_cits_rate`** counts any run where the system attached
  citations as "responded with grounded content" — closer to true correctness
  for in-scope questions, ignores OOS hyper-correct declines that the
  decline-marker missed.

For a publishable headline, prefer `mean_has_cits_rate` for in-scope categories
(factoid, analytical, follow-up) and a manual classification for OOS.

### Reproducibility

- No fixed RNG seed. The harness intentionally captures temperature variance.
- Stack state must be warm (backend container up >= 1 min) so first-query
  cold-start doesn't bias per-run timing.
- Other agents on the LLM can introduce noise — run with no concurrent users.

### Estimated runtime

- 20 questions × ~30s mean elapsed × N runs ≈ 10·N minutes
- N=3: ~30 min; N=5: ~50 min; N=10: ~100 min
- Long-tail: questions hitting the ResearchGraph max-iterations loop (3 iter ×
  ~70s LLM round trip ≈ 210s timeout) extend runtime ±5 min per occurrence.

## Recommended cadence

- **CI**: do NOT run on every PR (60+ min on a CPU-only runner). Schedule
  weekly on `develop` HEAD or run manually before tagging a release.
- **Pre-release**: N=5 single sweep before each minor version tag. Compare
  against the previous tag's baseline. Regress if `mean_rate` drops by
  > 1.96·max(stddev_old, stddev_new) (hard 95%-CI overlap test).
- **Local iteration**: N=3 quick smoke after retrieval/prompt changes.

## File layout

- `scripts/multi_sample_sweep.py` — the harness (committed, reproducible).
- `docs/E2E/2026-04-24-bug-hunt/multi-sample-methodology.md` — this file.
- `docs/E2E/2026-04-24-bug-hunt/multi-sample-baseline.json` — first multi-sample
  run produced by this PR. Future runs save alongside with date stamps.
- `docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml` — input dataset (locked at
  FR-014).

## Deferred to later v1.1 work

- **Statistical regression test in CI**: gate that compares each new
  multi-sample run against the previous baseline with a CI-overlap check.
- **Per-question hard-floor**: separate CI gate that flags any single question
  whose `answer_rate` drops below a documented threshold (e.g., the curated
  demo questions Q-009/Q-013/Q-020 must keep `answer_rate >= 0.6`).
- **OOS-correct classification**: replace decline-marker substring matching
  with a small structured-output LLM call that classifies each response as
  `answer | partial | decline | hallucination` against the expected behavior.
- **Multi-LLM judge ensemble**: run the same chunks through `qwen2.5:7b`,
  `mistral:7b`, and `llama3.1:8b` in parallel and compare to estimate
  judge-LLM-induced variance separately from retrieval-induced variance.
