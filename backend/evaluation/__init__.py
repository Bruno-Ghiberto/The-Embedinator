"""Pure, network-free retrieval-evaluation core.

TREC qrels/run I/O. Nothing in this package makes a network call or touches a
database.
"""

from __future__ import annotations

from backend.evaluation.trec import Qrels, Run, RunEntry, read_qrels, read_run, write_qrels, write_run

__all__ = [
    "Qrels",
    "Run",
    "RunEntry",
    "read_qrels",
    "read_run",
    "write_qrels",
    "write_run",
]
