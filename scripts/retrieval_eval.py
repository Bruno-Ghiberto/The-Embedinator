#!/usr/bin/env python3
"""Offline retrieval evaluation against the golden set (TREC-style qrels + runs).

Measures the retriever alone — no agent, no answer generation — so a retrieval
change can be judged by recall@k / hit@k / MRR / nDCG@k with a paired
permutation p-value instead of a qualitative sweep.

Workflow:
  1. run    Retrieve for every labeled golden question with one config and
            write a TREC run plus a chunk sidecar (<run>.chunks.jsonl).
            Configs: hybrid (HybridSearcher, RRF), hybrid_rerank (hybrid then
            the cross-encoder over the same candidates), dense, sparse (BM25).
  2. pool   Union the top-D chunks per question across several runs.
  3. judge  A local LLM grades each pooled (question, chunk) pair 0/1/2 into a
            review CSV. Unparseable verdicts get grade "?". Resumable.
  4. review A human spot-checks the CSV and resolves every "?" row.
  5. qrels  Convert the reviewed CSV into TREC qrels.
  6. eval   Score one run, or compare two with paired permutation p-values.

The reviewed qrels are meant to be tracked next to the golden set as
docs/E2E/2026-04-24-bug-hunt/retrieval-qrels.tsv. Generated runs, pools and
review CSVs default to data/retrieval-eval/ (gitignored).

run and judge need the live stack: Qdrant plus Ollama (query embeddings and
the judge model), at the addresses in backend.config.Settings (read from the
repo's .env). Follow-up questions are retrieved standalone, without the
conversation rewrite the agent applies, so they measure raw retrieval.

Examples (from the repo root):
  .venv/bin/python scripts/retrieval_eval.py run --config hybrid
  .venv/bin/python scripts/retrieval_eval.py run --config dense
  .venv/bin/python scripts/retrieval_eval.py pool --runs data/retrieval-eval/hybrid.trec data/retrieval-eval/dense.trec
  .venv/bin/python scripts/retrieval_eval.py judge --pool data/retrieval-eval/pool.jsonl
  .venv/bin/python scripts/retrieval_eval.py qrels --review data/retrieval-eval/review.csv \\
      --out docs/E2E/2026-04-24-bug-hunt/retrieval-qrels.tsv
  .venv/bin/python scripts/retrieval_eval.py eval --qrels docs/E2E/2026-04-24-bug-hunt/retrieval-qrels.tsv \\
      --run data/retrieval-eval/hybrid.trec --run data/retrieval-eval/hybrid_rerank.trec
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from collections import Counter
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Settings  # noqa: E402
from backend.evaluation import (  # noqa: E402
    REVIEW_FIELDS,
    GoldenQuestion,
    NeedsReview,
    Run,
    RunEntry,
    build_pool,
    complete_review_rows,
    csv_rows_to_qrels,
    evaluate,
    golden_questions_from_records,
    merge_chunk_metadata,
    paired_permutation_test,
    parse_judge_response,
    read_qrels,
    read_run,
    retrieval_eval_exclusions,
    write_qrels,
    write_run,
)

GOLDEN_PATH = REPO_ROOT / "docs" / "E2E" / "2026-04-24-bug-hunt" / "golden-qa.yaml"
DEFAULT_OUT_DIR = REPO_ROOT / "data" / "retrieval-eval"
# Golden corpus "nag-corpus-bm25" (2026-05-05): the NAG ingestion that carries BM25
# sparse vectors. The older "nag-corpus-spec28" collection (emb-22923ab5-..., the
# _DEFAULT_NAG_COLLECTION_ID in tests/quality/test_ragas_baseline.py) has none, so
# its "hybrid" results are dense-only.
DEFAULT_COLLECTION = "emb-61b0dd9f-05b9-4bed-a502-fae360bc65ed"
CONFIGS = ("hybrid", "hybrid_rerank", "dense", "sparse")
SNIPPET_CHARS = 300
# 2**18 enumerates every sign vector exactly for up to 18 queries (the current
# golden set); larger sets fall back to seeded Monte Carlo with this many draws.
DEFAULT_PERMUTATIONS = 2**18

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "grade": {"type": "integer", "enum": [0, 1, 2]},
        "reason": {"type": "string"},
    },
    "required": ["grade", "reason"],
}

JUDGE_PROMPT = """You grade search results for a retrieval benchmark over Argentine gas regulations (NAG documents, written in Spanish).

Question (Spanish): {question}
Reference answer (Spanish): {reference}
Expected source: {source_doc} {source_section}

Candidate chunk from {source_file}, page {page}:
<<<
{text}
>>>

Decide what this chunk does for a reader who has ONLY this chunk and must answer the question.

2 = the chunk states the answer, or states in full one of the named elements the reference answer is built from.

Many questions span two norms or several provisions, so no single chunk can carry the whole answer. A chunk that fully states one required element still earns 2. Do not withhold 2 merely because the chunk leaves the rest of the reference answer uncovered, and do not require the chunk to name every norm the question mentions.
1 = the chunk carries a real, usable piece of the answer but is not sufficient on its own.
0 = everything else.

Grade 0, not 1, in each of these cases:
- The chunk is merely about the same document, chapter or subject matter. A shared topic is NOT relevance.
- The chunk repeats a number, term or phrase that also appears in the reference answer, but uses it for a different concept, quantity or procedure.
- The chunk is front matter, a title page, a table of contents, a reference or standards list, a form, an annex template or an observations sheet.
- The chunk describes a different test, provision or requirement than the one the question asks about, even inside the correct norm.

When the question names a specific norm, a chunk from a DIFFERENT norm earns 2 only if it states the answer for the norm the question named. A different norm stating its own analogous rule about its own subject is 0.

In "reason", quote the exact phrase from the chunk that carries the answer. If you cannot quote such a phrase from the chunk above, the grade is 0.

Respond with JSON only: {{"grade": 0, 1 or 2, "reason": "<one short sentence>"}}"""


def _settings() -> Settings:
    # Read the repo's .env regardless of the caller's working directory.
    return Settings(_env_file=REPO_ROOT / ".env")


def _load_golden_records() -> list[Mapping[str, Any]]:
    import yaml  # untyped PyYAML stays out of backend/ so `mypy backend/` remains clean

    return yaml.safe_load(GOLDEN_PATH.read_text(encoding="utf-8"))


def _load_golden() -> list[GoldenQuestion]:
    return golden_questions_from_records(_load_golden_records())


def _load_exclusions() -> dict[str, str]:
    """qid -> reason for questions explicitly excluded from the retrieval eval (kept in the golden set)."""
    return retrieval_eval_exclusions(_load_golden_records())


def _sidecar_path(run_path: Path) -> Path:
    return run_path.with_name(f"{run_path.name}.chunks.jsonl")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


async def _retrieve(
    config: str,
    questions: list[GoldenQuestion],
    collection: str,
    top_k: int,
    ollama_url: str,
    settings: Settings,
) -> tuple[Run, dict[str, dict[str, Any]]]:
    """Retrieve top_k chunks per question with one config; read-only against Qdrant."""
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import SparseVector as QdrantSparseVector

    from backend.providers.ollama import OllamaEmbeddingProvider
    from backend.retrieval.bm25_encoder import encode as encode_bm25
    from backend.retrieval.reranker import Reranker
    from backend.retrieval.searcher import HybridSearcher

    client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    embedder = OllamaEmbeddingProvider(base_url=ollama_url, model=settings.default_embed_model)
    searcher = HybridSearcher(client, settings)
    reranker = Reranker(settings) if config == "hybrid_rerank" else None

    run: Run = {}
    sidecar: dict[str, dict[str, Any]] = {}
    try:
        for question in questions:
            query = question.question_es
            # (chunk_id, score, source_file, page, text) in rank order
            hits: list[tuple[str, float, str, int | None, str]] = []
            if config in ("hybrid", "hybrid_rerank"):
                chunks = await searcher.search(query, collection, top_k=top_k, embed_fn=embedder.embed_single)
                if reranker is not None and chunks:
                    chunks = reranker.rerank(query, chunks, top_k=len(chunks))
                    hits = [(c.chunk_id, float(c.rerank_score or 0.0), c.source_file, c.page, c.text) for c in chunks]
                else:
                    hits = [(c.chunk_id, float(c.dense_score), c.source_file, c.page, c.text) for c in chunks]
            else:
                if config == "dense":
                    response = await client.query_points(
                        collection_name=collection,
                        query=await embedder.embed_single(query),
                        using="dense",
                        limit=top_k,
                        with_payload=True,
                    )
                else:
                    sparse = encode_bm25(query)
                    if not sparse.indices:
                        print(f"  {question.id}: no BM25 tokens survive, empty sparse run", file=sys.stderr)
                        continue
                    response = await client.query_points(
                        collection_name=collection,
                        query=QdrantSparseVector(indices=sparse.indices, values=sparse.values),
                        using="sparse",
                        limit=top_k,
                        with_payload=True,
                    )
                for point in response.points:
                    payload = point.payload or {}
                    hits.append(
                        (
                            str(point.id),
                            float(point.score or 0.0),
                            str(payload.get("source_file", "")),
                            payload.get("page"),
                            str(payload.get("text", "")),
                        )
                    )

            run[question.id] = [
                RunEntry(doc_id=chunk_id, rank=rank, score=score, tag=config)
                for rank, (chunk_id, score, *_rest) in enumerate(hits, start=1)
            ]
            for chunk_id, _score, source_file, page, text in hits:
                sidecar.setdefault(chunk_id, {"source_file": source_file, "page": page, "text": text})
            print(f"  {question.id}: {len(hits)} chunks")
    finally:
        await client.close()
    return run, sidecar


def cmd_run(args: argparse.Namespace) -> int:
    settings = _settings()
    questions = _load_golden()
    out = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"{args.config}.trec"
    ollama_url = args.ollama_url or settings.ollama_base_url
    print(f"run: config={args.config} top_k={args.top_k} collection={args.collection} questions={len(questions)}")
    run, sidecar = asyncio.run(_retrieve(args.config, questions, args.collection, args.top_k, ollama_url, settings))
    out.parent.mkdir(parents=True, exist_ok=True)
    write_run(run, out)
    _write_jsonl([{"chunk_id": chunk_id, **meta} for chunk_id, meta in sidecar.items()], _sidecar_path(out))
    print(f"wrote {out} and {_sidecar_path(out).name}")
    return 0


# ---------------------------------------------------------------------------
# pool
# ---------------------------------------------------------------------------


def cmd_pool(args: argparse.Namespace) -> int:
    golden_by_id = {question.id: question for question in _load_golden()}
    runs: dict[str, Run] = {}
    sidecars: list[dict[str, dict[str, Any]]] = []
    for raw_path in args.runs:
        path = Path(raw_path)
        runs[str(path)] = read_run(path)
        sidecars.append({row.pop("chunk_id"): row for row in _read_jsonl(_sidecar_path(path))})
    rows = build_pool(runs, args.depth, merge_chunk_metadata(sidecars), golden_by_id)
    out = Path(args.out) if args.out else DEFAULT_OUT_DIR / "pool.jsonl"
    _write_jsonl([asdict(row) for row in rows], out)
    sizes = Counter(row.qid for row in rows)
    print(f"wrote {out}: {len(rows)} pairs over {len(sizes)} questions (depth={args.depth}, runs={len(runs)})")
    for qid in sorted(sizes):
        print(f"  {qid}: {sizes[qid]}")
    return 0


# ---------------------------------------------------------------------------
# judge
# ---------------------------------------------------------------------------


async def _judge_one(http: Any, ollama_url: str, model: str, row: dict[str, Any]) -> str:
    prompt = JUDGE_PROMPT.format(
        question=row["question_es"],
        reference=row["reference_answer_es"],
        source_doc=row["source_doc"],
        source_section=row["source_section"],
        source_file=row["source_file"],
        page=row["page"],
        text=row["text"],
    )
    response = await http.post(
        f"{ollama_url.rstrip('/')}/api/chat",
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "format": JUDGE_SCHEMA,
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
        },
    )
    response.raise_for_status()
    return str(response.json()["message"]["content"])


async def _judge(args: argparse.Namespace, rows: list[dict[str, Any]], out: Path, settings: Settings) -> int:
    import httpx

    ollama_url = args.ollama_url or settings.ollama_base_url
    model = args.model or settings.default_llm_model
    is_new = not out.exists() or out.stat().st_size == 0
    out.parent.mkdir(parents=True, exist_ok=True)
    judged = 0
    async with httpx.AsyncClient(timeout=settings.llm_call_timeout_seconds) as http:
        with out.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            if is_new:
                writer.writeheader()
            for index, row in enumerate(rows, start=1):
                try:
                    raw = await _judge_one(http, ollama_url, model, row)
                except httpx.HTTPError as exc:
                    print(f"judge call failed at {row['qid']}/{row['chunk_id']}: {exc!r}", file=sys.stderr)
                    print(f"progress saved in {out}; re-run the same command to resume", file=sys.stderr)
                    return 1
                verdict = parse_judge_response(raw)
                if isinstance(verdict, NeedsReview):
                    grade, reason = "?", f"NEEDS REVIEW: {verdict.error}"
                else:
                    grade, reason = str(verdict.grade), verdict.reason
                writer.writerow(
                    {
                        "qid": row["qid"],
                        "chunk_id": row["chunk_id"],
                        "grade": grade,
                        "reason": reason,
                        "source_file": row["source_file"],
                        "page": row["page"],
                        "snippet": " ".join(str(row["text"]).split())[:SNIPPET_CHARS],
                    }
                )
                handle.flush()
                judged += 1
                print(f"  [{index}/{len(rows)}] {row['qid']} {row['chunk_id'][:8]} -> {grade}")
    print(f"judged {judged} pair(s) with {model}; review {out} and resolve every '?' row before `qrels`")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:
    settings = _settings()
    out = Path(args.out) if args.out else DEFAULT_OUT_DIR / "review.csv"
    rows = _read_jsonl(Path(args.pool))
    if args.qid:
        wanted = set(args.qid)
        rows = [row for row in rows if row["qid"] in wanted]
    done: set[tuple[str, str]] = set()
    if out.exists() and out.stat().st_size > 0:
        # Bytes, not read_text: a kill can land inside a multi-byte character, and strict
        # decoding would crash before the partial row is dropped. The replacement char only
        # ever lands in that dropped tail. Reading bytes also preserves a CRLF the judge
        # wrote inside a quoted reason, which universal newlines would rewrite.
        complete, dropped = complete_review_rows(out.read_bytes().decode("utf-8", errors="replace"))
        if dropped:
            # Appending to a truncated file would glue the next judgment onto the
            # partial line; rewrite the file from its complete rows instead.
            print(
                f"judge: dropped partial row(s) left by an interrupted run: {', '.join(dropped)}; "
                "they will be re-judged",
                file=sys.stderr,
            )
            with out.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
                writer.writeheader()
                writer.writerows(complete)
        done = {(row["qid"], row["chunk_id"]) for row in complete}
    pending = [row for row in rows if (row["qid"], row["chunk_id"]) not in done]
    if args.limit is not None:
        pending = pending[: args.limit]
    print(f"judge: {len(pending)} pending, {len(done)} already in {out}")
    if not pending:
        return 0
    return asyncio.run(_judge(args, pending, out, settings))


# ---------------------------------------------------------------------------
# qrels
# ---------------------------------------------------------------------------


def cmd_qrels(args: argparse.Namespace) -> int:
    with Path(args.review).open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    exclusions = _load_exclusions()
    dropped_rows = [row for row in rows if row.get("qid") in exclusions]
    if dropped_rows:
        # Predates the exclusion: the pool and review files were built before a question was
        # explicitly excluded, so they still carry its rows. Drop them here rather than refusing
        # the whole review as "unknown qid" — the qid is known, just out of scope for this eval.
        dropped_qids = sorted({row["qid"] for row in dropped_rows})
        print(
            f"qrels: dropped {len(dropped_rows)} judgment(s) for question(s) excluded from the retrieval eval: "
            f"{', '.join(dropped_qids)}",
            file=sys.stderr,
        )
        rows = [row for row in rows if row.get("qid") not in exclusions]
    try:
        qrels = csv_rows_to_qrels(rows)
    except ValueError as exc:
        print(f"qrels: {exc}", file=sys.stderr)
        return 1
    golden_ids = {question.id for question in _load_golden()}
    unknown = sorted(set(qrels) - golden_ids)
    if unknown:
        print(
            f"qrels: {len(unknown)} qid(s) in the review are not in the golden set: {', '.join(unknown)}",
            file=sys.stderr,
        )
        return 1
    uncovered = sorted(golden_ids - set(qrels))
    if uncovered:
        # A partial review is legitimate while iterating, so this warns and still writes.
        print(
            f"qrels: WARNING {len(uncovered)} labeled golden question(s) have no judgments: {', '.join(uncovered)}",
            file=sys.stderr,
        )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_qrels(qrels, out)
    grades = Counter(grade for row in qrels.values() for grade in row.values())
    print(
        f"wrote {out}: {len(qrels)} questions, {sum(grades.values())} judgments, grades {dict(sorted(grades.items()))}"
    )
    return 0


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------


def cmd_eval(args: argparse.Namespace) -> int:
    if len(args.run) > 2:
        print("eval: pass one --run to score it, or two to compare them", file=sys.stderr)
        return 2
    qrels = read_qrels(args.qrels)
    labels = [Path(path).name for path in args.run]
    runs = [read_run(path) for path in args.run]
    for label, run in zip(labels, runs, strict=True):
        missing = sorted(set(qrels) - set(run))
        if missing:
            print(
                f"eval: {label} has no entries for {len(missing)} qid(s) ({', '.join(missing)}); "
                "they score 0 on every metric",
                file=sys.stderr,
            )
    results = [evaluate(qrels, run, args.k) for run in runs]
    first = results[0]
    if first.n_evaluated == 0:
        print(
            f"eval: no query could be evaluated: qrels has {len(qrels)} qid(s), "
            f"{len(first.excluded_qids)} excluded for having no relevant chunk",
            file=sys.stderr,
        )
        return 1
    included = [qid for qid in first.per_query if qid not in first.excluded_qids]
    print(
        f"qrels: {args.qrels}  evaluated queries n={first.n_evaluated}  excluded (no relevant chunk): {first.excluded_qids}"
    )

    header = f"{'metric':<10}" + "".join(f"{label:>22}" for label in labels)
    if len(results) == 2:
        header += f"{'diff (B-A)':>12}{'p':>10}"
    print(header)
    method = ""
    for key in first.mean:
        line = f"{key:<10}" + "".join(f"{result.mean[key]:>22.4f}" for result in results)
        if len(results) == 2 and included:
            test = paired_permutation_test(
                [results[1].per_query[qid][key] for qid in included],
                [first.per_query[qid][key] for qid in included],
                n_permutations=args.permutations,
                seed=args.seed,
            )
            method = test.method
            line += f"{test.observed_diff:>+12.4f}{test.p_value:>10.4f}"
        print(line)
    if method:
        print(f"paired permutation test: two-sided, {method}, n={len(included)}; diff = B minus A")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="retrieve for every labeled golden question with one config")
    run.add_argument("--config", choices=CONFIGS, required=True)
    run.add_argument("--top-k", type=int, default=20)
    run.add_argument("--collection", default=DEFAULT_COLLECTION, help="Qdrant collection name (emb-<uuid>)")
    run.add_argument("--ollama-url", help="override Settings.ollama_base_url for query embeddings")
    run.add_argument("--out", help=f"TREC run path (default: {DEFAULT_OUT_DIR}/<config>.trec)")
    run.set_defaults(func=cmd_run)

    pool = sub.add_parser("pool", help="union the top-D chunks per question across runs")
    pool.add_argument("--runs", nargs="+", required=True, help="TREC run files; each needs its .chunks.jsonl sidecar")
    pool.add_argument("--depth", type=int, default=20)
    pool.add_argument("--out", help=f"pool JSONL path (default: {DEFAULT_OUT_DIR}/pool.jsonl)")
    pool.set_defaults(func=cmd_pool)

    judge = sub.add_parser("judge", help="LLM-grade pooled pairs 0/1/2 into a review CSV (resumable)")
    judge.add_argument("--pool", required=True)
    judge.add_argument("--out", help=f"review CSV path (default: {DEFAULT_OUT_DIR}/review.csv)")
    judge.add_argument("--model", help="Ollama judge model (default: Settings.default_llm_model)")
    judge.add_argument("--ollama-url", help="override Settings.ollama_base_url")
    judge.add_argument("--qid", nargs="+", help="only judge these question ids")
    judge.add_argument("--limit", type=int, help="judge at most N pending pairs this invocation")
    judge.set_defaults(func=cmd_judge)

    qrels = sub.add_parser("qrels", help="convert a reviewed CSV into TREC qrels")
    qrels.add_argument("--review", required=True)
    qrels.add_argument("--out", required=True)
    qrels.set_defaults(func=cmd_qrels)

    ev = sub.add_parser("eval", help="score one run, or compare two with paired permutation p-values")
    ev.add_argument("--qrels", required=True)
    ev.add_argument("--run", action="append", required=True, help="TREC run; pass twice to compare A and B")
    ev.add_argument("--k", type=int, nargs="+", default=[5, 10, 20])
    ev.add_argument("--permutations", type=int, default=DEFAULT_PERMUTATIONS)
    ev.add_argument("--seed", type=int, default=0)
    ev.set_defaults(func=cmd_eval)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
