"""TREC-format qrels and run I/O.

qrels lines: ``qid 0 docid grade`` (classic trec_eval qrels format; the
second column is a vestigial "iteration" field and is always written as 0).

Run lines: ``qid Q0 docid rank score tag`` (classic trec_eval run format).
`read_run` always returns entries ranked by the `rank` column within each
qid, regardless of the order lines appear on disk.

The `rank` column is authoritative here, a deliberate divergence from trec_eval,
which ignores `rank` and re-sorts each query by `score` descending. Every run
scripts/retrieval_eval.py writes keeps score monotone with rank, so trec_eval
would reproduce the same ranking — including `hybrid`, whose score column holds
Qdrant's RRF fused score (already ordered descending) rather than a dense
similarity, despite reaching the writer through a field named `dense_score`. The
divergence therefore only matters for run files produced elsewhere or with
hand-edited ranks, and for ties, which trec_eval breaks by doc id and this reader
by the `rank` column.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# qid -> {doc_id: grade}. grade >= 1 means relevant (see backend.evaluation.metrics).
Qrels = dict[str, dict[str, int]]


@dataclass
class RunEntry:
    """One ranked (doc_id, rank, score) triple for a single query in a TREC run."""

    doc_id: str
    rank: int
    score: float
    tag: str


# qid -> list[RunEntry], always sorted by rank ascending.
Run = dict[str, list[RunEntry]]


def _require_token(value: str, field: str) -> str:
    """Reject values that would split into extra whitespace-separated fields."""
    if not value or any(ch.isspace() for ch in value):
        raise ValueError(f"TREC {field} must be a non-empty token without whitespace, got {value!r}")
    return value


def read_qrels(path: str | Path) -> Qrels:
    """Read a TREC qrels file (`qid 0 docid grade` per line) into a `Qrels` mapping.

    Raises:
        ValueError: a non-blank line does not have exactly 4 whitespace-separated
            fields, or the grade field is not an integer.
    """
    qrels: Qrels = {}
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"{path}:{line_no}: expected 4 fields (qid iter docid grade), got {len(fields)}")
        qid, _iteration, doc_id, grade = fields
        try:
            parsed_grade = int(grade)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: grade {grade!r} is not an integer") from exc
        qrels.setdefault(qid, {})[doc_id] = parsed_grade
    return qrels


def write_qrels(qrels: Mapping[str, Mapping[str, int]], path: str | Path) -> None:
    """Write `qrels` to `path` in TREC qrels format, sorted by qid then doc_id."""
    lines = [
        f"{_require_token(qid, 'qid')} 0 {_require_token(doc_id, 'docid')} {int(grade)}\n"
        for qid in sorted(qrels)
        for doc_id, grade in sorted(qrels[qid].items())
    ]
    Path(path).write_text("".join(lines), encoding="utf-8")


def read_run(path: str | Path) -> Run:
    """Read a TREC run file (`qid Q0 docid rank score tag` per line) into a `Run` mapping.

    Entries for each qid are returned sorted by the `rank` column ascending,
    independent of on-disk line order. trec_eval instead ignores `rank` and sorts
    by `score` descending, which agrees with this ordering for every run the
    project's own CLI writes (see the module docstring).

    Raises:
        ValueError: a non-blank line does not have exactly 6 whitespace-separated
            fields, or the rank/score fields are not numeric.
        ValueError: the same doc id appears twice under one qid — a document
            holds exactly one rank, so such a run file is malformed. The same
            doc id under a different qid is legitimate.
    """
    run: Run = {}
    seen: set[tuple[str, str]] = set()
    for line_no, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 6:
            raise ValueError(f"{path}:{line_no}: expected 6 fields (qid Q0 docid rank score tag), got {len(fields)}")
        qid, _q0, doc_id, rank, score, tag = fields
        if (qid, doc_id) in seen:
            raise ValueError(f"{path}:{line_no}: duplicate doc id {doc_id!r} for qid {qid!r}")
        seen.add((qid, doc_id))
        try:
            entry = RunEntry(doc_id=doc_id, rank=int(rank), score=float(score), tag=tag)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: rank {rank!r} and score {score!r} must be numeric") from exc
        run.setdefault(qid, []).append(entry)
    for entries in run.values():
        entries.sort(key=lambda entry: entry.rank)
    return run


def write_run(run: Mapping[str, Sequence[RunEntry]], path: str | Path) -> None:
    """Write `run` to `path` in TREC run format, sorted by qid then rank ascending."""
    lines = [
        f"{_require_token(qid, 'qid')} Q0 {_require_token(entry.doc_id, 'docid')} "
        f"{entry.rank} {float(entry.score)!r} {_require_token(entry.tag, 'tag')}\n"
        for qid in sorted(run)
        for entry in sorted(run[qid], key=lambda entry: entry.rank)
    ]
    Path(path).write_text("".join(lines), encoding="utf-8")
