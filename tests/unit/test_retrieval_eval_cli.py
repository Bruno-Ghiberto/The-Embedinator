"""Tests for scripts/retrieval_eval.py — the CLI that drives backend.evaluation.

The script is not an importable package, so it is loaded by path. Every test
here stays offline: the only function that talks to Ollama (`_judge_one`) is
monkeypatched, and `OLLAMA_BASE_URL` points at a dead port so an accidental
real call fails fast instead of reaching a live stack.
"""

from __future__ import annotations

import asyncio
import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from backend.evaluation import GoldenQuestion, csv_rows_to_qrels

SCRIPT_PATH = Path(__file__).parents[2] / "scripts" / "retrieval_eval.py"


def _load_cli() -> ModuleType:
    """Import scripts/retrieval_eval.py by path (it inserts the repo root into sys.path itself)."""
    spec = importlib.util.spec_from_file_location("retrieval_eval_cli", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pool_row(chunk_id: str) -> dict[str, Any]:
    return {
        "qid": "Q-001",
        "chunk_id": chunk_id,
        "source_file": "NAG-200.pdf",
        "page": 1,
        "text": f"texto de {chunk_id}",
        "question_es": "pregunta uno",
        "reference_answer_es": "respuesta uno",
        "source_doc": "NAG-200.pdf",
        "source_section": "§1.1",
    }


def _write_pool(tmp_path: Path) -> Path:
    pool = tmp_path / "pool.jsonl"
    pool.write_text(
        "".join(json.dumps(_pool_row(chunk_id), ensure_ascii=False) + "\n" for chunk_id in ("c1", "c2", "c3")),
        encoding="utf-8",
    )
    return pool


def _patch_judge(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the only function that talks to Ollama; returns the chunk ids it is asked to grade."""
    judged_chunk_ids: list[str] = []

    async def fake_judge_one(http: Any, ollama_url: str, model: str, row: dict[str, Any]) -> str:
        judged_chunk_ids.append(str(row["chunk_id"]))
        return json.dumps({"grade": 2, "reason": "ok"})

    monkeypatch.setattr(module, "_judge_one", fake_judge_one)
    return judged_chunk_ids


def _assert_resumed_cleanly(review: Path, module: ModuleType) -> None:
    with review.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    for row in rows:
        assert None not in row  # no overflow column from a glued line
        assert sorted(row) == sorted(module.REVIEW_FIELDS)
        assert all(value is not None for value in row.values())
    assert csv_rows_to_qrels(rows) == {"Q-001": {"c1": 1, "c2": 2, "c3": 2}}


def test_judge_resumes_over_a_partial_row_left_by_an_interrupted_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A judge run killed mid-write leaves a truncated last line in review.csv.

    Resuming must re-judge that pair and produce a well-formed CSV, never glue
    the next judgment onto the truncated line.
    """
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    module = _load_cli()
    pool = _write_pool(tmp_path)

    review = tmp_path / "review.csv"
    # Header, one complete row, then a row cut mid-reason: unterminated quote, no newline.
    review.write_text(
        "qid,chunk_id,grade,reason,source_file,page,snippet\n"
        "Q-001,c1,1,razon uno,NAG-200.pdf,1,texto de c1\n"
        'Q-001,c2,1,"partial reas',
        encoding="utf-8",
    )
    judged_chunk_ids = _patch_judge(module, monkeypatch)

    exit_code = module.main(["judge", "--pool", str(pool), "--out", str(review)])
    assert exit_code == 0

    # c1 is already judged; c2's row was truncated, so it must be judged again.
    assert judged_chunk_ids == ["c2", "c3"]
    _assert_resumed_cleanly(review, module)


def test_judge_resumes_when_the_kill_landed_inside_a_multi_byte_character(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The judge writes Spanish reasons, so a kill can cut a UTF-8 character in half.

    Reading such a file strictly raises UnicodeDecodeError before the partial
    row can be dropped, which would make every retry of the resume fail the
    same way.
    """
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:1")
    module = _load_cli()
    pool = _write_pool(tmp_path)

    review = tmp_path / "review.csv"
    # b"\xc3" is the first byte of "ó" in "razón": the second byte never reached the disk.
    review.write_bytes(
        b"qid,chunk_id,grade,reason,source_file,page,snippet\r\n"
        b"Q-001,c1,1,razon uno,NAG-200.pdf,1,texto de c1\r\n"
        b'Q-001,c2,1,"raz\xc3'
    )
    judged_chunk_ids = _patch_judge(module, monkeypatch)

    exit_code = module.main(["judge", "--pool", str(pool), "--out", str(review)])
    assert exit_code == 0
    assert judged_chunk_ids == ["c2", "c3"]
    _assert_resumed_cleanly(review, module)


# ---------------------------------------------------------------------------
# judge — the rubric the model is handed
# ---------------------------------------------------------------------------


class _RecordingResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"message": {"content": '{"grade": 0, "reason": "ok"}'}}


class _RecordingHttp:
    """Stands in for the httpx client so the request body can be inspected offline."""

    def __init__(self) -> None:
        self.payloads: list[dict[str, Any]] = []

    async def post(self, url: str, json: dict[str, Any]) -> _RecordingResponse:
        self.payloads.append(json)
        return _RecordingResponse()


def _judge_prompt(row: dict[str, Any]) -> str:
    """The exact prompt `_judge_one` sends to the judge model for one pooled pair."""
    http = _RecordingHttp()
    asyncio.run(_load_cli()._judge_one(http, "http://ollama.invalid", "judge-model", row))
    (payload,) = http.payloads
    return str(payload["messages"][0]["content"])


def test_judge_prompt_does_not_define_a_shared_topic_as_relevant() -> None:
    """Grade 1 as "same topic or section" graded every chunk of the right norm as relevant."""
    assert "same topic or section" not in _judge_prompt(_pool_row("c1"))


@pytest.mark.parametrize(
    "clause",
    [
        # Q-011/Q-012/Q-014: tables of contents and unrelated tests of the right norm graded 1.
        "A shared topic is NOT relevance.",
        # Q-004: "0,5 bar / 4 bar" repeated from the reference answer for a different concept.
        "uses it for a different concept, quantity or procedure",
        "a table of contents, a reference or standards list",
        # Q-002 -> NAG-240, Q-015 -> NAG-E209: another norm's analogous rule graded 2.
        "A different norm stating its own analogous rule about its own subject is 0.",
        # Cross-norm questions: no single chunk carries the whole reference answer.
        "A chunk that fully states one required element still earns 2.",
        # Q-004 / NAG-235 p23: the reason described content the snippet did not contain.
        "If you cannot quote such a phrase from the chunk above, the grade is 0.",
    ],
)
def test_judge_prompt_carries_the_clause_that_closes_an_observed_label_defect(clause: str) -> None:
    assert clause in _judge_prompt(_pool_row("c1"))


def test_judge_prompt_renders_the_pair_and_a_literal_json_example() -> None:
    """The rubric goes through `str.format`: an unescaped brace would raise or eat the example."""
    prompt = _judge_prompt(_pool_row("c1"))

    for rendered in ("pregunta uno", "respuesta uno", "NAG-200.pdf §1.1", "NAG-200.pdf, page 1", "texto de c1"):
        assert rendered in prompt
    assert '{"grade": 0, 1 or 2, "reason": "<one short sentence>"}' in prompt


# ---------------------------------------------------------------------------
# qrels / eval — consistency of the inputs the pipeline is handed
# ---------------------------------------------------------------------------


def _golden(qid: str) -> GoldenQuestion:
    return GoldenQuestion(
        id=qid,
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


def _write_review(path: Path, pairs: list[tuple[str, str, str]]) -> None:
    """Write a reviewed CSV holding one graded row per (qid, chunk_id, grade) triple."""
    rows = "".join(f"{qid},{chunk_id},{grade},razon,NAG-200.pdf,1,texto\n" for qid, chunk_id, grade in pairs)
    path.write_text("qid,chunk_id,grade,reason,source_file,page,snippet\n" + rows, encoding="utf-8")


def test_qrels_rejects_a_review_qid_that_is_not_in_the_golden_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A qid the golden set never defined cannot be scored; writing it would hide the mismatch."""
    module = _load_cli()
    monkeypatch.setattr(module, "_load_golden", lambda: [_golden("Q-001"), _golden("Q-002")])
    review = tmp_path / "review.csv"
    _write_review(review, [("Q-001", "c1", "2"), ("Q-003", "c9", "1")])
    out = tmp_path / "qrels.tsv"

    assert module.main(["qrels", "--review", str(review), "--out", str(out)]) == 1
    stderr = capsys.readouterr().err
    assert "Q-003" in stderr
    assert "not in the golden set" in stderr
    assert not out.exists()


def test_qrels_warns_about_golden_questions_with_no_judgments_but_still_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A partial review is legitimate while iterating — but it must not pass unremarked."""
    module = _load_cli()
    monkeypatch.setattr(module, "_load_golden", lambda: [_golden("Q-001"), _golden("Q-002")])
    review = tmp_path / "review.csv"
    _write_review(review, [("Q-001", "c1", "2")])
    out = tmp_path / "qrels.tsv"

    assert module.main(["qrels", "--review", str(review), "--out", str(out)]) == 0
    assert out.exists()
    stderr = capsys.readouterr().err
    assert "Q-002" in stderr
    assert "no judgments" in stderr


def test_eval_fails_instead_of_printing_a_table_of_nan(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Every qid excluded for having no relevant chunk means there is nothing to report."""
    module = _load_cli()
    qrels = tmp_path / "qrels.tsv"
    qrels.write_text("Q-001 0 c1 0\n", encoding="utf-8")
    run = tmp_path / "dense.trec"
    run.write_text("Q-001 Q0 c1 1 0.9 dense\n", encoding="utf-8")

    assert module.main(["eval", "--qrels", str(qrels), "--run", str(run)]) == 1
    captured = capsys.readouterr()
    assert "no query could be evaluated" in captured.err
    assert "nan" not in captured.out.lower()


def test_eval_reports_qids_a_run_has_no_entries_for(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Missing run qids score 0 on every metric and drag the mean down, so they must be named."""
    module = _load_cli()
    qrels = tmp_path / "qrels.tsv"
    qrels.write_text("Q-001 0 c1 2\nQ-002 0 c2 2\n", encoding="utf-8")
    run = tmp_path / "dense.trec"
    run.write_text("Q-001 Q0 c1 1 0.9 dense\n", encoding="utf-8")

    assert module.main(["eval", "--qrels", str(qrels), "--run", str(run)]) == 0
    stderr = capsys.readouterr().err
    assert "dense.trec" in stderr
    assert "Q-002" in stderr
    assert "no entries" in stderr
