"""Golden-set loading, pool assembly, judge-response parsing, and review-CSV -> qrels.

All functions here are pure (no network, no Qdrant/Ollama calls, no file I/O).
Parsing golden-qa.yaml and the network calls (embeddings, hybrid search, the
LLM judge) live in scripts/retrieval_eval.py, which imports this module for
everything else.
"""

from __future__ import annotations

import csv
import io
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
    excluded — they have no retrievable ground truth to grade against. Entries
    with a truthy `retrieval_eval_excluded` are also excluded — see
    `retrieval_eval_exclusions` for the recorded reason.
    """
    questions: list[GoldenQuestion] = []
    for record in records:
        source_doc = record.get("source_doc")
        if not source_doc:
            continue
        if record.get("retrieval_eval_excluded"):
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


def retrieval_eval_exclusions(records: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Map golden question id -> reason for records carrying a truthy `retrieval_eval_excluded`.

    A record with `retrieval_eval_excluded` absent, null, or whitespace-only is
    not an exclusion and is left out of the result. Every returned reason is
    stripped. Excluded questions stay in the golden set (see
    `golden_questions_from_records`) for documentation and downstream
    consumers other than the retrieval eval; only the retrieval eval itself
    skips them.
    """
    exclusions: dict[str, str] = {}
    for record in records:
        raw_reason = record.get("retrieval_eval_excluded")
        if not raw_reason:
            continue
        reason = str(raw_reason).strip()
        if not reason:
            continue
        exclusions[str(record["id"])] = reason
    return exclusions


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
        ValueError: a pooled chunk's metadata carries no usable text (the `text`
            key is missing, None, or whitespace-only) — the judge would grade
            the blank chunk 0 and fabricate a true negative in the qrels.
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

    blank = sorted(
        {
            chunk_id
            for ids in pooled.values()
            for chunk_id in ids
            if not str(chunk_metadata[chunk_id].get("text") or "").strip()
        }
    )
    if blank:
        raise ValueError(f"no text for pooled chunk ids: {', '.join(blank)}")

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


REVIEW_FIELDS: list[str] = ["qid", "chunk_id", "grade", "reason", "source_file", "page", "snippet"]


def _describe_partial_row(record: Mapping[Any, Any]) -> str:
    qid, chunk_id = record.get("qid"), record.get("chunk_id")
    if isinstance(qid, str) and qid and isinstance(chunk_id, str) and chunk_id:
        return f"{qid}/{chunk_id}"
    return "unreadable tail"


def complete_review_rows(text: str) -> tuple[list[dict[str, str]], list[str]]:
    """Split review-CSV text into its complete rows and the partial tail, if any.

    A judge run killed mid-write leaves the CSV ending in a truncated record:
    no trailing newline, a record short of `REVIEW_FIELDS`, or an unterminated
    quoted field that swallowed the record's own newline. Appending the next
    judgment to such a file glues two records together — one judgment is lost,
    one is corrupted, and `csv_rows_to_qrels` accepts both without complaint.
    This helper isolates that damage so the caller can rewrite the file and
    re-judge the affected pair.

    Only the LAST record is ever examined and dropped; earlier records are
    returned untouched. Returns `(rows, dropped)`, where `dropped` is empty or
    holds one short description of what was discarded: "<qid>/<chunk_id>" when
    the truncated record still carries both, "partial header" when the file
    stops inside its header line, "unreadable tail" otherwise.
    """
    if not text:
        return [], []
    records = list(csv.DictReader(io.StringIO(text)))
    ends_cleanly = text.endswith("\n")
    if not records:
        return [], [] if ends_cleanly else ["partial header"]
    last = records[-1]
    truncated = not ends_cleanly or None in last or any(value is None for value in last.values())
    if not truncated:
        return [{str(key): str(value) for key, value in record.items()} for record in records], []
    rows = [{str(key): str(value) for key, value in record.items()} for record in records[:-1]]
    return rows, [_describe_partial_row(last)]


def csv_rows_to_qrels(rows: Sequence[Mapping[str, str]]) -> Qrels:
    """Convert reviewed CSV rows (columns: qid, chunk_id, grade, reason, source_file,
    page, snippet) into TREC qrels.

    Raises:
        ValueError: two rows carry the same (qid, chunk_id) pair — one of them is
            stale, and keeping either would silently discard the other. This is
            an error even when both rows agree on the grade.
        ValueError: any row's `grade` is blank or "?" (needs-review, never
            resolved) or not an integer in {0, 1, 2} — lists every offending
            (qid, chunk_id) pair in the message; such rows are never silently
            dropped.
    """
    qrels: Qrels = {}
    unresolved: list[str] = []
    duplicates: list[str] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        # Tracked before the grade check so a duplicate is still caught on an unresolved row.
        pair = (row["qid"], row["chunk_id"])
        if pair in seen:
            duplicates.append(f"{pair[0]}/{pair[1]}")
        seen.add(pair)
        raw_grade = (row.get("grade") or "").strip()
        try:
            grade = int(raw_grade)
        except ValueError:
            grade = -1
        if grade not in _VALID_GRADES:
            unresolved.append(f"{row.get('qid')}/{row.get('chunk_id')} (grade={raw_grade!r})")
            continue
        qrels.setdefault(row["qid"], {})[row["chunk_id"]] = grade
    if duplicates:
        raise ValueError(f"{len(duplicates)} duplicate (qid, chunk_id) pair(s) in review rows: {', '.join(duplicates)}")
    if unresolved:
        raise ValueError(f"{len(unresolved)} review row(s) need a 0/1/2 grade: {', '.join(unresolved)}")
    return qrels
