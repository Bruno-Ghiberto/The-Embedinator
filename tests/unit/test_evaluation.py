"""Tests for backend.evaluation — TREC I/O, per-query retrieval metrics,
paired permutation significance testing, and golden-set labeling helpers.

Metric and significance-test fixtures are hand-computed (see inline comments)
so a failure points at a wrong formula, not a wrong assumption about the
fixture itself.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from backend.evaluation.labeling import (
    REVIEW_FIELDS,
    GoldenQuestion,
    NeedsReview,
    ParsedJudgeGrade,
    build_pool,
    complete_review_rows,
    csv_rows_to_qrels,
    golden_questions_from_records,
    merge_chunk_metadata,
    parse_judge_response,
)
from backend.evaluation.metrics import (
    evaluate,
    hit_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)
from backend.evaluation.significance import paired_permutation_test
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


def test_read_qrels_rejects_a_doc_id_judged_twice_for_one_qid(tmp_path: Path) -> None:
    """Keeping the last grade would let a re-judged pair silently overwrite the reviewed one."""
    path = tmp_path / "qrels.tsv"
    path.write_text("Q-001 0 c1 2\nQ-001 0 c2 1\nQ-001 0 c1 0\n")
    with pytest.raises(ValueError) as excinfo:
        read_qrels(path)
    message = str(excinfo.value)
    assert "c1" in message
    assert f"{path}:3" in message  # the offending line
    assert "line 1" in message  # and the one it collides with


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


def test_read_run_rejects_a_doc_id_repeated_within_one_qid(tmp_path: Path) -> None:
    """A document holds exactly one rank; two ranks for one doc id is a malformed run."""
    path = tmp_path / "run.trec"
    path.write_text("Q-001 Q0 chunk-a 1 0.9 hybrid\nQ-002 Q0 chunk-a 1 0.7 hybrid\nQ-001 Q0 chunk-a 2 0.5 hybrid\n")
    with pytest.raises(ValueError) as excinfo:
        read_run(path)
    message = str(excinfo.value)
    assert "chunk-a" in message
    assert "Q-001" in message  # the same doc id under a different qid is legitimate


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


def test_ndcg_at_k_counts_a_repeated_doc_id_once() -> None:
    """A chunk retrieved twice must not earn its gain twice — recall/hit/mrr already count it once.

    "a" (grade 2) is credited at rank 1 only; the rank-2 repeat adds nothing, and
    "b" (grade 0) at rank 3 adds nothing either:
      dcg  = 2/log2(2)                      = 2.0
      idcg = 2/log2(2)                      = 2.0   (ideal order: a)
    """
    qrels_row = {"a": 2}
    score = ndcg_at_k(qrels_row, ["a", "a", "b"], k=10)
    assert score <= 1.0
    assert score == pytest.approx(1.0)
    assert score == pytest.approx(ndcg_at_k(qrels_row, ["a", "b"], k=10))


def test_ndcg_at_k_repeat_still_occupies_its_rank_slot() -> None:
    """The duplicate earns no gain but does not promote what follows it.

    Retrieved ["b", "b", "a"]: "b" (grade 1) is credited at rank 1, the rank-2
    repeat adds nothing, and "a" (grade 2) stays at rank 3.
      dcg  = 1/log2(2) + 2/log2(4)  = 1.0 + 1.0     = 2.0
      idcg = 2/log2(2) + 1/log2(3)                  (ideal order: a, b)
    """
    qrels_row = {"a": 2, "b": 1}
    dcg = 1 / math.log2(2) + 2 / math.log2(4)
    idcg = 2 / math.log2(2) + 1 / math.log2(3)
    assert ndcg_at_k(qrels_row, ["b", "b", "a"], k=10) == pytest.approx(dcg / idcg)


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


# ---------------------------------------------------------------------------
# paired_permutation_test
# ---------------------------------------------------------------------------


def test_paired_permutation_test_identical_inputs_give_p_one() -> None:
    result = paired_permutation_test([0.5, 0.7, 0.9], [0.5, 0.7, 0.9], n_permutations=10000, seed=0)
    assert result.method == "exact"  # 2**3 = 8 <= 10000
    assert result.p_value == pytest.approx(1.0)


def test_paired_permutation_test_exact_branch_hand_computed() -> None:
    """a - b = [4, 2, 0]; observed |mean diff| = 2.0.

    Of the 8 sign-flip vectors over (i0, i1, i2), i2's diff is 0 so its sign
    never changes the sum — only the 4 (i0, i1) combinations matter, each
    counted twice:
      (+,+) -> mean=+2.0 -> extreme (x2, i2 either sign)
      (+,-) -> mean=+0.667 -> not extreme
      (-,+) -> mean=-0.667 -> not extreme
      (-,-) -> mean=-2.0 -> extreme (x2)
    4 of 8 sign vectors are extreme -> p = 0.5.
    """
    a = [5.0, 3.0, 1.0]
    b = [1.0, 1.0, 1.0]
    result = paired_permutation_test(a, b, n_permutations=10000, seed=0)
    assert result.method == "exact"
    assert result.p_value == pytest.approx(0.5)


def test_paired_permutation_test_monte_carlo_branch_is_seed_deterministic() -> None:
    a = [0.9, 0.4, 0.6, 0.8, 0.5, 0.7]
    b = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
    assert 2 ** len(a) > 32  # forces the Monte Carlo branch below
    first = paired_permutation_test(a, b, n_permutations=32, seed=42)
    second = paired_permutation_test(a, b, n_permutations=32, seed=42)
    assert first.method == "monte_carlo"
    assert first.p_value == second.p_value


def test_paired_permutation_test_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError):
        paired_permutation_test([1.0, 2.0], [1.0], n_permutations=100, seed=0)


def test_paired_permutation_test_rejects_empty_input() -> None:
    with pytest.raises(ValueError):
        paired_permutation_test([], [], n_permutations=100, seed=0)


# ---------------------------------------------------------------------------
# Labeling helpers
# ---------------------------------------------------------------------------


def test_golden_questions_from_records_excludes_null_source_doc() -> None:
    # Records as yaml.safe_load returns them for golden-qa.yaml (a top-level list).
    records = [
        {
            "id": "Q-001",
            "category": "factoid",
            "question_es": "pregunta uno",
            "reference_answer_es": "respuesta uno",
            "source_doc": "NAG-200.pdf, NAG-235.pdf",
            "source_section": "§1.1",
            "notes": "nota",
            "authored_by": "scaffold-reviewed",
            "follow_up_of": None,
            "expected_behavior": "answer",
        },
        {
            "id": "Q-018",
            "category": "out-of-scope",
            "question_es": "pregunta fuera de alcance",
            "reference_answer_es": "respuesta",
            "source_doc": None,
            "source_section": None,
            "notes": "nota",
            "authored_by": "user",
            "follow_up_of": None,
            "expected_behavior": "decline",
        },
    ]
    questions = golden_questions_from_records(records)
    assert [q.id for q in questions] == ["Q-001"]
    assert questions[0].source_doc == ["NAG-200.pdf", "NAG-235.pdf"]


def test_merge_chunk_metadata_keeps_first_seen_entry_per_chunk_id() -> None:
    first = {"c1": {"source_file": "NAG-200.pdf", "page": 1, "text": "from hybrid sidecar"}}
    second = {
        "c1": {"source_file": "NAG-200.pdf", "page": 1, "text": "from dense sidecar — must lose"},
        "c2": {"source_file": "NAG-235.pdf", "page": 3, "text": "only in dense sidecar"},
    }
    merged = merge_chunk_metadata([first, second])
    assert merged["c1"]["text"] == "from hybrid sidecar"
    assert merged["c2"]["text"] == "only in dense sidecar"


def _golden_question(**overrides: object) -> GoldenQuestion:
    defaults: dict[str, object] = dict(
        id="Q-001",
        category="factoid",
        question_es="pregunta",
        reference_answer_es="respuesta",
        source_doc=["NAG-200.pdf"],
        source_section="§1.1",
        notes="",
        authored_by="scaffold-reviewed",
        follow_up_of=None,
        expected_behavior="answer",
    )
    defaults.update(overrides)
    return GoldenQuestion(**defaults)  # type: ignore[arg-type]


def test_build_pool_unions_top_depth_ids_across_runs_without_duplicates() -> None:
    golden_by_id = {"Q-001": _golden_question()}
    runs = {
        "hybrid": {
            "Q-001": [
                RunEntry(doc_id="c1", rank=1, score=0.9, tag="hybrid"),
                RunEntry(doc_id="c2", rank=2, score=0.8, tag="hybrid"),
                RunEntry(doc_id="c3", rank=3, score=0.1, tag="hybrid"),  # beyond depth=2
            ]
        },
        "dense": {
            "Q-001": [
                RunEntry(doc_id="c2", rank=1, score=0.7, tag="dense"),  # already pooled from hybrid
                RunEntry(doc_id="c4", rank=2, score=0.6, tag="dense"),
            ]
        },
    }
    chunk_metadata = {
        "c1": {"source_file": "NAG-200.pdf", "page": 1, "text": "texto uno"},
        "c2": {"source_file": "NAG-200.pdf", "page": 2, "text": "texto dos"},
        "c4": {"source_file": "NAG-235.pdf", "page": 3, "text": "texto cuatro"},
    }
    pool = build_pool(runs, depth=2, chunk_metadata=chunk_metadata, golden_by_id=golden_by_id)
    ids = [row.chunk_id for row in pool]
    assert ids == ["c1", "c2", "c4"]  # c3 excluded by depth=2; c2 not duplicated
    assert all(row.qid == "Q-001" for row in pool)
    assert all(row.question_es == "pregunta" for row in pool)


def test_build_pool_rejects_pooled_chunks_without_usable_text() -> None:
    """A chunk with no text would be graded 0 by the judge, fabricating a true negative."""
    golden_by_id = {"Q-001": _golden_question()}
    runs = {
        "hybrid": {
            "Q-001": [
                RunEntry(doc_id="c1", rank=1, score=0.9, tag="hybrid"),
                RunEntry(doc_id="c2", rank=2, score=0.8, tag="hybrid"),
                RunEntry(doc_id="c3", rank=3, score=0.7, tag="hybrid"),
                RunEntry(doc_id="c4", rank=4, score=0.6, tag="hybrid"),
            ]
        }
    }
    chunk_metadata: dict[str, dict[str, object]] = {
        "c1": {"source_file": "NAG-200.pdf", "page": 1, "text": "texto uno"},  # the only healthy chunk
        "c2": {"source_file": "NAG-200.pdf", "page": 2, "text": None},
        "c3": {"source_file": "NAG-200.pdf", "page": 3},  # no "text" key at all
        "c4": {"source_file": "NAG-235.pdf", "page": 4, "text": "   "},
    }
    with pytest.raises(ValueError) as excinfo:
        build_pool(runs, depth=4, chunk_metadata=chunk_metadata, golden_by_id=golden_by_id)
    message = str(excinfo.value)
    assert "c2" in message
    assert "c3" in message
    assert "c4" in message
    assert "c1" not in message


def test_parse_judge_response_valid_json() -> None:
    parsed = parse_judge_response(json.dumps({"grade": 2, "reason": "matches the reference answer"}))
    assert isinstance(parsed, ParsedJudgeGrade)
    assert parsed.grade == 2
    assert parsed.reason == "matches the reference answer"


def test_parse_judge_response_needs_review_on_malformed_json() -> None:
    parsed = parse_judge_response("not json at all")
    assert isinstance(parsed, NeedsReview)


def test_parse_judge_response_needs_review_on_out_of_range_grade() -> None:
    parsed = parse_judge_response(json.dumps({"grade": 5, "reason": "x"}))
    assert isinstance(parsed, NeedsReview)


def test_parse_judge_response_needs_review_on_missing_reason() -> None:
    parsed = parse_judge_response(json.dumps({"grade": 1}))
    assert isinstance(parsed, NeedsReview)


def test_csv_rows_to_qrels_builds_grade_map() -> None:
    rows = [
        {"qid": "Q-001", "chunk_id": "c1", "grade": "2", "reason": "", "source_file": "", "page": "", "snippet": ""},
        {"qid": "Q-001", "chunk_id": "c2", "grade": "0", "reason": "", "source_file": "", "page": "", "snippet": ""},
    ]
    assert csv_rows_to_qrels(rows) == {"Q-001": {"c1": 2, "c2": 0}}


def test_csv_rows_to_qrels_rejects_a_repeated_qid_chunk_id_pair() -> None:
    """Two rows for one pair is an error even when the grades agree — one of them is stale."""
    rows = [
        {"qid": "Q-001", "chunk_id": "c1", "grade": "2", "reason": "", "source_file": "", "page": "", "snippet": ""},
        {"qid": "Q-001", "chunk_id": "c1", "grade": "2", "reason": "", "source_file": "", "page": "", "snippet": ""},
    ]
    with pytest.raises(ValueError) as excinfo:
        csv_rows_to_qrels(rows)
    assert "Q-001/c1" in str(excinfo.value)


def test_csv_rows_to_qrels_never_silently_drops_a_duplicate_beside_an_unresolved_grade() -> None:
    rows = [
        {"qid": "Q-001", "chunk_id": "c1", "grade": "2", "reason": "", "source_file": "", "page": "", "snippet": ""},
        {"qid": "Q-001", "chunk_id": "c1", "grade": "2", "reason": "", "source_file": "", "page": "", "snippet": ""},
        {"qid": "Q-001", "chunk_id": "c2", "grade": "?", "reason": "", "source_file": "", "page": "", "snippet": ""},
    ]
    with pytest.raises(ValueError) as excinfo:
        csv_rows_to_qrels(rows)
    message = str(excinfo.value)
    assert "Q-001/c1" in message or "Q-001/c2" in message


def test_csv_rows_to_qrels_raises_on_blank_or_needs_review_grade() -> None:
    rows = [
        {"qid": "Q-001", "chunk_id": "c1", "grade": "", "reason": "", "source_file": "", "page": "", "snippet": ""},
        {"qid": "Q-001", "chunk_id": "c2", "grade": "?", "reason": "", "source_file": "", "page": "", "snippet": ""},
    ]
    with pytest.raises(ValueError) as excinfo:
        csv_rows_to_qrels(rows)
    assert "c1" in str(excinfo.value)
    assert "c2" in str(excinfo.value)


# ---------------------------------------------------------------------------
# complete_review_rows — recovering a review CSV from an interrupted judge run
# ---------------------------------------------------------------------------

_REVIEW_HEADER = "qid,chunk_id,grade,reason,source_file,page,snippet\n"
_COMPLETE_ROW = "Q-001,c1,2,razon uno,NAG-200.pdf,1,texto uno\n"


def test_complete_review_rows_keeps_every_row_of_an_intact_file() -> None:
    rows, dropped = complete_review_rows(
        _REVIEW_HEADER + _COMPLETE_ROW + "Q-001,c2,0,razon dos,NAG-200.pdf,2,texto dos\n"
    )
    assert dropped == []
    assert [row["chunk_id"] for row in rows] == ["c1", "c2"]
    assert sorted(rows[0]) == sorted(REVIEW_FIELDS)


def test_complete_review_rows_drops_a_last_row_without_a_trailing_newline() -> None:
    rows, dropped = complete_review_rows(_REVIEW_HEADER + _COMPLETE_ROW + 'Q-001,c2,1,"partial reas')
    assert dropped == ["Q-001/c2"]
    assert [row["chunk_id"] for row in rows] == ["c1"]
    assert rows[0]["snippet"] == "texto uno"  # rows before the last are untouched


def test_complete_review_rows_drops_a_last_row_missing_fields_despite_a_newline() -> None:
    rows, dropped = complete_review_rows(_REVIEW_HEADER + _COMPLETE_ROW + "Q-001,c2,1,razon dos\n")
    assert dropped == ["Q-001/c2"]
    assert [row["chunk_id"] for row in rows] == ["c1"]


def test_complete_review_rows_drops_a_last_row_whose_open_quote_swallowed_the_newline() -> None:
    # The kill landed inside a quoted reason, so the record's own newline is part of the field.
    rows, dropped = complete_review_rows(_REVIEW_HEADER + _COMPLETE_ROW + 'Q-001,c2,1,"razon cortada\n')
    assert dropped == ["Q-001/c2"]
    assert [row["chunk_id"] for row in rows] == ["c1"]


def test_complete_review_rows_reports_an_unreadable_tail_without_qid_and_chunk_id() -> None:
    rows, dropped = complete_review_rows(_REVIEW_HEADER + _COMPLETE_ROW + "Q-0")
    assert dropped == ["unreadable tail"]
    assert [row["chunk_id"] for row in rows] == ["c1"]


def test_complete_review_rows_accepts_crlf_terminated_text() -> None:
    """`csv.DictWriter` writes CRLF, so a real review.csv reaches the helper CRLF-terminated."""
    rows, dropped = complete_review_rows(
        _REVIEW_HEADER.replace("\n", "\r\n") + _COMPLETE_ROW.replace("\n", "\r\n") + 'Q-001,c2,1,"razon cort'
    )
    assert dropped == ["Q-001/c2"]
    assert [row["chunk_id"] for row in rows] == ["c1"]
    assert rows[0]["snippet"] == "texto uno"


def test_complete_review_rows_reports_a_truncated_header() -> None:
    assert complete_review_rows(_REVIEW_HEADER.rstrip("\n")) == ([], ["partial header"])


def test_complete_review_rows_on_empty_text() -> None:
    assert complete_review_rows("") == ([], [])
