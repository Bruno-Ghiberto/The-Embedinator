"""Golden-set loading, pool assembly, judge-response parsing, and review-CSV -> qrels.

All functions here are pure (no network, no Qdrant/Ollama calls, no file I/O).
Parsing golden-qa.yaml and the network calls (embeddings, hybrid search, the
LLM judge) live in scripts/retrieval_eval.py, which imports this module for
everything else.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from backend.evaluation.trec import Qrels, Run

_VALID_GRADES = frozenset({0, 1, 2})


@dataclass
class GoldenQuestion:
    """One labeled entry from docs/E2E/2026-04-24-bug-hunt/golden-qa.yaml.

    `source_doc` is the comma-separated `source_doc` YAML field split into a
    list (e.g. "NAG-235.pdf,NAG-200.pdf" -> ["NAG-235.pdf", "NAG-200.pdf"]).
    """

    id: str
    category: str
    question_es: str
    reference_answer_es: str
    source_doc: list[str]
    source_section: str
    notes: str
    authored_by: str
    follow_up_of: str | None
    expected_behavior: str


def golden_questions_from_records(records: Sequence[Mapping[str, Any]]) -> list[GoldenQuestion]:
    """Build `GoldenQuestion`s from parsed golden-qa.yaml records.

    The caller parses the YAML (scripts/retrieval_eval.py); keeping YAML out of
    this package keeps `mypy backend/` free of the untyped `yaml` import.
    Entries with `source_doc: null` (out-of-scope pairs, e.g. Q-018/Q-019) are
    excluded — they have no retrievable ground truth to grade against.
    """
    questions: list[GoldenQuestion] = []
    for record in records:
        source_doc = record.get("source_doc")
        if not source_doc:
            continue
        follow_up_of = record.get("follow_up_of")
        questions.append(
            GoldenQuestion(
                id=str(record["id"]),
                category=str(record.get("category") or ""),
                question_es=str(record["question_es"]).strip(),
                reference_answer_es=str(record.get("reference_answer_es") or "").strip(),
                source_doc=[doc.strip() for doc in str(source_doc).split(",") if doc.strip()],
                source_section=str(record.get("source_section") or ""),
                notes=str(record.get("notes") or "").strip(),
                authored_by=str(record.get("authored_by") or ""),
                follow_up_of=str(follow_up_of) if follow_up_of else None,
                expected_behavior=str(record.get("expected_behavior") or ""),
            )
        )
    return questions


@dataclass
class PoolRow:
    """One pooled (question, chunk) pair awaiting an LLM judge grade."""

    qid: str
    chunk_id: str
    source_file: str
    page: int | None
    text: str
    question_es: str
    reference_answer_es: str
    source_doc: str
    source_section: str


def merge_chunk_metadata(
    sidecars: Sequence[Mapping[str, Mapping[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """Merge several chunk_id -> metadata maps (one per run's sidecar), first sidecar wins.

    Used when the same chunk_id appears in more than one run's sidecar file —
    keeps the metadata from whichever sidecar is listed first, rather than
    letting a later sidecar silently overwrite it.
    """
    merged: dict[str, dict[str, Any]] = {}
    for sidecar in sidecars:
        for chunk_id, metadata in sidecar.items():
            merged.setdefault(chunk_id, dict(metadata))
    return merged


def build_pool(
    runs: Mapping[str, Run],
    depth: int,
    chunk_metadata: Mapping[str, Mapping[str, Any]],
    golden_by_id: Mapping[str, GoldenQuestion],
) -> list[PoolRow]:
    """Union the top-`depth` chunk ids per qid across several runs into pool rows.

    `runs` maps a run tag (e.g. "hybrid", "dense") to a parsed `Run`; runs are
    scanned in mapping-iteration order and, within each, entries in rank order
    up to `depth`. A chunk id already pooled for a qid (from an earlier run) is
    not added again — the pool is a de-duplicated union, one row per unique
    (qid, chunk_id). Metadata for each chunk id is looked up once in
    `chunk_metadata` (see `merge_chunk_metadata` for building that mapping from
    several sidecars). qids in `runs` with no matching `golden_by_id` entry are
    skipped. Result rows are returned grouped by qid (qids sorted), each row in
    first-seen order within its qid.

    Raises:
        ValueError: a pooled chunk id has no entry in `chunk_metadata` — the
            judge could not grade a chunk whose text is unknown.
    """
    pooled: dict[str, dict[str, None]] = {}  # qid -> insertion-ordered set of chunk ids
    for run in runs.values():
        for qid, entries in run.items():
            if qid not in golden_by_id:
                continue
            chunk_ids = pooled.setdefault(qid, {})
            for entry in sorted(entries, key=lambda entry: entry.rank)[:depth]:
                chunk_ids.setdefault(entry.doc_id, None)

    missing = sorted({chunk_id for ids in pooled.values() for chunk_id in ids if chunk_id not in chunk_metadata})
    if missing:
        raise ValueError(f"no chunk metadata for pooled chunk ids: {', '.join(missing)}")

    rows: list[PoolRow] = []
    for qid in sorted(pooled):
        question = golden_by_id[qid]
        for chunk_id in pooled[qid]:
            metadata = chunk_metadata[chunk_id]
            page = metadata.get("page")
            rows.append(
                PoolRow(
                    qid=qid,
                    chunk_id=chunk_id,
                    source_file=str(metadata.get("source_file") or ""),
                    page=page if isinstance(page, int) else None,
                    text=str(metadata.get("text") or ""),
                    question_es=question.question_es,
                    reference_answer_es=question.reference_answer_es,
                    source_doc=",".join(question.source_doc),
                    source_section=question.source_section,
                )
            )
    return rows


@dataclass
class ParsedJudgeGrade:
    """A successfully parsed and validated LLM judge response."""

    grade: int
    reason: str


@dataclass
class NeedsReview:
    """A judge response that failed to parse or validate — never silently graded 0."""

    raw_response: str
    error: str


def parse_judge_response(raw: str) -> ParsedJudgeGrade | NeedsReview:
    """Parse a strict-JSON judge response: `{"grade": 0|1|2, "reason": str}`.

    Returns `NeedsReview` (never a silent 0) when `raw` is not valid JSON, is
    not a JSON object, `grade` is missing/not an int/out of {0, 1, 2}, or
    `reason` is missing or not a string.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return NeedsReview(raw_response=raw, error=f"invalid JSON: {exc}")
    if not isinstance(data, dict):
        return NeedsReview(raw_response=raw, error="response is not a JSON object")
    grade = data.get("grade")
    # bool is a subclass of int; `true` must not pass as grade 1.
    if isinstance(grade, bool) or not isinstance(grade, int) or grade not in _VALID_GRADES:
        return NeedsReview(raw_response=raw, error=f"grade must be 0, 1 or 2, got {grade!r}")
    reason = data.get("reason")
    if not isinstance(reason, str):
        return NeedsReview(raw_response=raw, error="reason must be a string")
    return ParsedJudgeGrade(grade=grade, reason=reason)


def csv_rows_to_qrels(rows: Sequence[Mapping[str, str]]) -> Qrels:
    """Convert reviewed CSV rows (columns: qid, chunk_id, grade, reason, source_file,
    page, snippet) into TREC qrels.

    Raises:
        ValueError: any row's `grade` is blank or "?" (needs-review, never
            resolved) or not an integer in {0, 1, 2} — lists every offending
            (qid, chunk_id) pair in the message; such rows are never silently
            dropped.
    """
    qrels: Qrels = {}
    unresolved: list[str] = []
    for row in rows:
        raw_grade = (row.get("grade") or "").strip()
        try:
            grade = int(raw_grade)
        except ValueError:
            grade = -1
        if grade not in _VALID_GRADES:
            unresolved.append(f"{row.get('qid')}/{row.get('chunk_id')} (grade={raw_grade!r})")
            continue
        qrels.setdefault(row["qid"], {})[row["chunk_id"]] = grade
    if unresolved:
        raise ValueError(f"{len(unresolved)} review row(s) need a 0/1/2 grade: {', '.join(unresolved)}")
    return qrels
