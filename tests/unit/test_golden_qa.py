"""Content guards for the golden set (docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml).

A reference answer is the ground truth both the retrieval eval and the
answer-quality harness score against, so it may state only what the corpus
supports. These tests read the real file and stay offline.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

GOLDEN_QA_PATH = Path(__file__).parents[2] / "docs" / "E2E" / "2026-04-24-bug-hunt" / "golden-qa.yaml"


def _record(qid: str) -> dict[str, Any]:
    records = yaml.safe_load(GOLDEN_QA_PATH.read_text(encoding="utf-8"))
    return next(record for record in records if record["id"] == qid)


def _flat(text: str) -> str:
    """Collapse the whitespace a folded YAML scalar leaves behind."""
    return " ".join(text.split())


def test_q014_reference_answer_states_that_neither_norm_cites_the_other() -> None:
    """NAG-204 and NAG-226 never cite each other, so the answer must not invent the link.

    NAG-226 cites only NAG-200 and NAG-215. NAG-204 §1 covers continuously
    operating CO alarms for domestic premises; NAG-226 §8 has the inspector
    measure ambient CO with a calibrated detector. The earlier answer claimed
    the inspection device must meet NAG-204, which no page of either norm states.
    """
    record = _record("Q-014")
    answer = _flat(record["reference_answer_es"])

    assert "establecidos en NAG-204" not in answer
    assert "cadena normativa" not in answer
    assert "ninguna de las dos normas cita a la otra" in answer
    assert "uso doméstico" in answer  # NAG-204 §1 scope
    assert "calibración vigente" in answer  # NAG-226 §8 instrument
    assert "15 ppm" in answer and "30 ppm" in answer  # NAG-226 §8.1-§8.3 criteria


def test_q014_notes_do_not_cast_nag204_as_the_inspection_instrument() -> None:
    """The authoring note framed NAG-204 as the instrument NAG-226 §8 uses."""
    notes = _flat(_record("Q-014")["notes"])

    assert "NAG-204 (instrumento)" not in notes
