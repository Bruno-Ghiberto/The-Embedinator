"""Tests for backend.evaluation — TREC I/O and per-query retrieval metrics.

Metric fixtures are hand-computed (see inline comments) so a failure points at
a wrong formula, not a wrong assumption about the fixture itself.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.evaluation.metrics import (
    evaluate,
    hit_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)
from backend.evaluation.trec import RunEntry, read_qrels, read_run, write_qrels, write_run

# ---------------------------------------------------------------------------
# TREC I/O
# ---------------------------------------------------------------------------


def test_read_qrels_parses_qid_iter_docid_grade(tmp_path: Path) -> None:
    path = tmp_path / "qrels.tsv"
    path.write_text("Q-001 0 chunk-a 2\nQ-001 0 chunk-b 0\nQ-002 0 chunk-c 1\n")
    qrels = read_qrels(path)
    assert qrels == {"Q-001": {"chunk-a": 2, "chunk-b": 0}, "Q-002": {"chunk-c": 1}}


def test_write_qrels_round_trips_through_read_qrels(tmp_path: Path) -> None:
    path = tmp_path / "qrels.tsv"
    original = {"Q-002": {"chunk-c": 1}, "Q-001": {"chunk-b": 0, "chunk-a": 2}}
    write_qrels(original, path)
    assert read_qrels(path) == original


def test_read_qrels_rejects_malformed_line(tmp_path: Path) -> None:
    path = tmp_path / "qrels.tsv"
    path.write_text("Q-001 0 chunk-a\n")  # missing grade field
    with pytest.raises(ValueError):
        read_qrels(path)


def test_read_run_orders_entries_by_rank_within_qid(tmp_path: Path) -> None:
    path = tmp_path / "run.trec"
    # Deliberately out of rank order on disk — read_run must re-order per qid.
    path.write_text("Q-001 Q0 chunk-b 2 0.5 hybrid\nQ-001 Q0 chunk-a 1 0.9 hybrid\nQ-002 Q0 chunk-c 1 0.4 hybrid\n")
    run = read_run(path)
    assert [e.doc_id for e in run["Q-001"]] == ["chunk-a", "chunk-b"]
    assert run["Q-001"][0] == RunEntry(doc_id="chunk-a", rank=1, score=0.9, tag="hybrid")


def test_write_run_round_trips_through_read_run(tmp_path: Path) -> None:
    path = tmp_path / "run.trec"
    original = {
        "Q-001": [
            RunEntry(doc_id="chunk-a", rank=1, score=0.9, tag="hybrid"),
            RunEntry(doc_id="chunk-b", rank=2, score=0.5, tag="hybrid"),
        ]
    }
    write_run(original, path)
    assert read_run(path) == original


def test_read_run_rejects_malformed_line(tmp_path: Path) -> None:
    path = tmp_path / "run.trec"
    path.write_text("Q-001 Q0 chunk-a 1 notascore hybrid\n")
    with pytest.raises(ValueError):
        read_run(path)


# ---------------------------------------------------------------------------
# Per-query metrics — hand-computed fixtures
# ---------------------------------------------------------------------------


def test_recall_at_k_counts_grade_ge_1_as_relevant() -> None:
    # 3 relevant chunks total (grade >= 1); top-2 retrieved hits only 1 ("c").
    qrels_row = {"a": 2, "b": 0, "c": 1, "d": 1}
    ranked_ids = ["b", "c", "a", "d"]  # "b" (grade 0, irrelevant) ranked first
    assert recall_at_k(qrels_row, ranked_ids, k=2) == pytest.approx(1 / 3)


def test_hit_at_k_is_binary() -> None:
    qrels_row = {"a": 1, "b": 0}
    assert hit_at_k(qrels_row, ["b", "a"], k=1) == 0.0
    assert hit_at_k(qrels_row, ["b", "a"], k=2) == 1.0


def test_mrr_at_k_first_relevant_chunk_at_rank_3() -> None:
    qrels_row = {"a": 0, "b": 0, "c": 1}
    ranked_ids = ["a", "b", "c", "d"]
    assert mrr_at_k(qrels_row, ranked_ids, k=5) == pytest.approx(1 / 3)


def test_mrr_at_k_zero_when_relevant_chunk_is_beyond_cutoff() -> None:
    qrels_row = {"a": 0, "b": 0, "c": 1}
    ranked_ids = ["a", "b", "c"]
    assert mrr_at_k(qrels_row, ranked_ids, k=2) == 0.0


def test_ndcg_at_k_hand_computed() -> None:
    """Ideal order is [d1=2, d3=1, d2=0]; the run promotes d3 above d1.

    dcg  = 1/log2(2) + 2/log2(3) + 0/log2(4)   (retrieved order: d3, d1, d2)
    idcg = 2/log2(2) + 1/log2(3) + 0/log2(4)   (ideal order:     d1, d3, d2)
    ndcg = dcg / idcg
    """
    qrels_row = {"d1": 2, "d2": 0, "d3": 1}
    ranked_ids = ["d3", "d1", "d2"]
    dcg = 1 / math.log2(2) + 2 / math.log2(3) + 0 / math.log2(4)
    idcg = 2 / math.log2(2) + 1 / math.log2(3) + 0 / math.log2(4)
    assert ndcg_at_k(qrels_row, ranked_ids, k=3) == pytest.approx(dcg / idcg)


def test_ndcg_at_k_ideal_order_scores_one() -> None:
    qrels_row = {"a": 2, "b": 1, "c": 0}
    assert ndcg_at_k(qrels_row, ["a", "b", "c"], k=3) == pytest.approx(1.0)


def test_ndcg_at_k_zero_relevant_returns_zero() -> None:
    assert ndcg_at_k({"a": 0, "b": 0}, ["a", "b"], k=2) == 0.0


# ---------------------------------------------------------------------------
# evaluate() — aggregate semantics
# ---------------------------------------------------------------------------


def test_evaluate_scores_missing_run_qid_as_zero_and_counts_it_in_mean() -> None:
    qrels = {"Q-001": {"a": 1}, "Q-002": {"b": 1}}
    run = {"Q-002": [RunEntry(doc_id="b", rank=1, score=1.0, tag="t")]}
    result = evaluate(qrels, run, ks=[1])
    assert result.per_query["Q-001"]["recall@1"] == 0.0
    assert result.n_evaluated == 2
    assert result.mean["recall@1"] == pytest.approx(0.5)  # (0 + 1) / 2


def test_evaluate_excludes_zero_relevant_qid_from_mean() -> None:
    qrels = {"Q-001": {"a": 0}, "Q-002": {"b": 1}}
    run = {
        "Q-001": [RunEntry(doc_id="a", rank=1, score=1.0, tag="t")],
        "Q-002": [RunEntry(doc_id="b", rank=1, score=1.0, tag="t")],
    }
    result = evaluate(qrels, run, ks=[1])
    assert result.excluded_qids == ["Q-001"]
    assert result.n_evaluated == 1
    assert result.mean["recall@1"] == pytest.approx(1.0)  # only Q-002 counted


def test_evaluate_ignores_run_only_qids() -> None:
    qrels = {"Q-001": {"a": 1}}
    run = {
        "Q-001": [RunEntry(doc_id="a", rank=1, score=1.0, tag="t")],
        "Q-999": [RunEntry(doc_id="z", rank=1, score=1.0, tag="t")],
    }
    result = evaluate(qrels, run, ks=[1])
    assert "Q-999" not in result.per_query
