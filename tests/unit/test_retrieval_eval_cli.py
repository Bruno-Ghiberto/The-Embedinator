"""Tests for scripts/retrieval_eval.py — the CLI that drives backend.evaluation.

The script is not an importable package, so it is loaded by path. Every test
here stays offline: the only function that talks to Ollama (`_judge_one`) is
monkeypatched, and `OLLAMA_BASE_URL` points at a dead port so an accidental
real call fails fast instead of reaching a live stack.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from backend.evaluation import csv_rows_to_qrels

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
