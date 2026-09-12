"""Per-query retrieval metrics and the `evaluate()` aggregate, trec_eval-compatible.

A chunk is "relevant" when its qrels grade is >= 1. All `*_at_k` functions take
one query's qrels row (`{doc_id: grade}`) and its ranked retrieved doc ids, and
return a single float; `evaluate()` runs all four metrics over a full qrels/run
pair for a list of cutoffs `ks`.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

from backend.evaluation.trec import Qrels, Run


def _is_relevant(qrels_row: Mapping[str, int], doc_id: str) -> bool:
    return qrels_row.get(doc_id, 0) >= 1


def recall_at_k(qrels_row: Mapping[str, int], ranked_ids: Sequence[str], k: int) -> float:
    """Fraction of relevant chunks (grade >= 1) present in the top-k retrieved ids.

    Returns 0.0 when `qrels_row` has no relevant chunks.
    """
    relevant = {doc_id for doc_id, grade in qrels_row.items() if grade >= 1}
    if not relevant:
        return 0.0
    return len(relevant.intersection(ranked_ids[:k])) / len(relevant)


def hit_at_k(qrels_row: Mapping[str, int], ranked_ids: Sequence[str], k: int) -> float:
    """1.0 if any relevant chunk appears in the top-k retrieved ids, else 0.0."""
    return 1.0 if any(_is_relevant(qrels_row, doc_id) for doc_id in ranked_ids[:k]) else 0.0


def mrr_at_k(qrels_row: Mapping[str, int], ranked_ids: Sequence[str], k: int) -> float:
    """Reciprocal rank (1-indexed) of the first relevant chunk within the top-k, else 0.0."""
    for rank, doc_id in enumerate(ranked_ids[:k], start=1):
        if _is_relevant(qrels_row, doc_id):
            return 1.0 / rank
    return 0.0


def ndcg_at_k(qrels_row: Mapping[str, int], ranked_ids: Sequence[str], k: int) -> float:
    """Normalized DCG@k, trec_eval convention: gain = grade, discount = log2(rank + 1).

    The ideal DCG is computed from the qrels row's own grades sorted descending
    (not limited to what was actually retrieved). Returns 0.0 when `qrels_row`
    has no relevant chunks (ideal DCG would be 0).
    """
    dcg = sum(
        max(qrels_row.get(doc_id, 0), 0) / math.log2(rank + 1) for rank, doc_id in enumerate(ranked_ids[:k], start=1)
    )
    ideal_grades = sorted((grade for grade in qrels_row.values() if grade > 0), reverse=True)[:k]
    idcg = sum(grade / math.log2(rank + 1) for rank, grade in enumerate(ideal_grades, start=1))
    return dcg / idcg if idcg > 0 else 0.0


_METRICS: tuple[tuple[str, Callable[[Mapping[str, int], Sequence[str], int], float]], ...] = (
    ("recall", recall_at_k),
    ("hit", hit_at_k),
    ("mrr", mrr_at_k),
    ("ndcg", ndcg_at_k),
)


@dataclass
class EvaluationResult:
    """Result of `evaluate()`: per-query metric scores plus means over included queries."""

    per_query: dict[str, dict[str, float]]
    mean: dict[str, float]
    excluded_qids: list[str]
    n_evaluated: int


def evaluate(qrels: Qrels, run: Run, ks: Sequence[int]) -> EvaluationResult:
    """Score `run` against `qrels` for every cutoff in `ks`.

    Semantics:
      - Every qid in `qrels` gets a `per_query` entry, computed against its
        run entries sorted by rank (or an empty ranking if the qid is absent
        from `run` entirely — trec_eval `-c` behavior: scores 0 on every metric).
      - A qid in `qrels` with zero relevant chunks (all grades == 0) is excluded
        from `mean` and listed in `excluded_qids`, but still appears in `per_query`.
      - qids present only in `run` (absent from `qrels`) are ignored entirely.

    Metric keys are named `f"{name}@{k}"` for name in (recall, hit, mrr, ndcg)
    and each k in `ks`. A mean over zero evaluated queries is NaN, not 0.0.
    """
    keys = [f"{name}@{k}" for name, _ in _METRICS for k in ks]
    per_query: dict[str, dict[str, float]] = {}
    excluded_qids: list[str] = []
    for qid in sorted(qrels):
        qrels_row = qrels[qid]
        ranked_ids = [entry.doc_id for entry in sorted(run.get(qid, []), key=lambda entry: entry.rank)]
        per_query[qid] = {f"{name}@{k}": metric(qrels_row, ranked_ids, k) for name, metric in _METRICS for k in ks}
        if not any(grade >= 1 for grade in qrels_row.values()):
            excluded_qids.append(qid)

    included = [qid for qid in per_query if qid not in excluded_qids]
    mean = {
        key: (sum(per_query[qid][key] for qid in included) / len(included) if included else math.nan) for key in keys
    }
    return EvaluationResult(per_query=per_query, mean=mean, excluded_qids=excluded_qids, n_evaluated=len(included))
