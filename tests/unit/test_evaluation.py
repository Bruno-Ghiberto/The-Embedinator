"""Tests for backend.evaluation.trec — TREC qrels and run file I/O."""

from __future__ import annotations

from pathlib import Path

import pytest

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
