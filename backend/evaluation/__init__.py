"""Pure, network-free retrieval-evaluation core.

TREC qrels/run I/O, per-query ranking metrics (recall/hit/mrr/ndcg), and paired
permutation significance testing. Nothing in this package makes a network call
or touches a database.
"""

from __future__ import annotations

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
