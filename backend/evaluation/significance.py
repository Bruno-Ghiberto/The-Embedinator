"""Paired permutation (sign-flip) significance test for comparing two runs' per-query scores."""

from __future__ import annotations

import itertools
import random
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

# Tolerance so a permutation whose |mean diff| equals the observed one up to
# float rounding still counts as "at least as extreme".
_TIE_EPSILON = 1e-12


@dataclass
class PermutationTestResult:
    """Result of `paired_permutation_test`."""

    observed_diff: float
    p_value: float
    n: int
    method: Literal["exact", "monte_carlo"]


def paired_permutation_test(
    a: Sequence[float],
    b: Sequence[float],
    n_permutations: int = 10000,
    seed: int = 0,
) -> PermutationTestResult:
    """Two-sided paired sign-flip permutation test on `a[i] - b[i]`.

    If `2 ** len(a) <= n_permutations`, every sign vector is enumerated exactly
    and `p_value = extreme / total`. Otherwise `n_permutations` sign vectors are
    drawn from a `random.Random(seed)` generator (deterministic given `seed`)
    and `p_value = (extreme + 1) / (n_permutations + 1)`.

    A permutation's |mean diff| counts as "extreme" when it is >= the observed
    |mean diff| minus a small float-tie epsilon.

    Raises:
        ValueError: `len(a) != len(b)`, or both are empty.
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples must have equal length, got {len(a)} and {len(b)}")
    if not a:
        raise ValueError("paired samples must not be empty")

    diffs = [x - y for x, y in zip(a, b, strict=True)]
    n = len(diffs)
    observed = sum(diffs) / n
    threshold = abs(observed) - _TIE_EPSILON

    if 2**n <= n_permutations:
        extreme = 0
        total = 0
        for signs in itertools.product((1.0, -1.0), repeat=n):
            total += 1
            if abs(sum(sign * diff for sign, diff in zip(signs, diffs, strict=True))) / n >= threshold:
                extreme += 1
        return PermutationTestResult(observed_diff=observed, p_value=extreme / total, n=n, method="exact")

    rng = random.Random(seed)
    extreme = 0
    for _ in range(n_permutations):
        permuted_sum = sum(diff if rng.random() < 0.5 else -diff for diff in diffs)
        if abs(permuted_sum) / n >= threshold:
            extreme += 1
    return PermutationTestResult(
        observed_diff=observed,
        p_value=(extreme + 1) / (n_permutations + 1),
        n=n,
        method="monte_carlo",
    )
