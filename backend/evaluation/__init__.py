"""Pure, network-free retrieval-evaluation core.

TREC qrels/run I/O, per-query ranking metrics (recall/hit/mrr/ndcg), paired
permutation significance testing, and golden-set labeling helpers (loading,
pool assembly, judge-response parsing, review-CSV -> qrels). Nothing in this
package makes a network call or touches a database.

The thin CLI that drives these functions against the live Qdrant/Ollama stack
(retrieve, pool, judge with a local LLM, convert to qrels, score two runs)
lives in scripts/retrieval_eval.py.
"""

from __future__ import annotations

from backend.evaluation.labeling import (
    REVIEW_FIELDS,
    GoldenQuestion,
    NeedsReview,
    ParsedJudgeGrade,
    PoolRow,
    build_pool,
    complete_review_rows,
    csv_rows_to_qrels,
    golden_questions_from_records,
    merge_chunk_metadata,
    parse_judge_response,
)
from backend.evaluation.metrics import (
    EvaluationResult,
    evaluate,
    hit_at_k,
    mrr_at_k,
    ndcg_at_k,
    recall_at_k,
)
from backend.evaluation.significance import PermutationTestResult, paired_permutation_test
from backend.evaluation.trec import Qrels, Run, RunEntry, read_qrels, read_run, write_qrels, write_run

__all__ = [
    "REVIEW_FIELDS",
    "GoldenQuestion",
    "NeedsReview",
    "ParsedJudgeGrade",
    "PoolRow",
    "build_pool",
    "complete_review_rows",
    "csv_rows_to_qrels",
    "golden_questions_from_records",
    "merge_chunk_metadata",
    "parse_judge_response",
    "EvaluationResult",
    "evaluate",
    "hit_at_k",
    "mrr_at_k",
    "ndcg_at_k",
    "recall_at_k",
    "PermutationTestResult",
    "paired_permutation_test",
    "Qrels",
    "Run",
    "RunEntry",
    "read_qrels",
    "read_run",
    "write_qrels",
    "write_run",
]
