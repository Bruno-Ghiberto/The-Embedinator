"""Unit tests for confidence scoring."""

from backend.agent.confidence import compute_confidence


def test_no_passages_zero_confidence():
    assert compute_confidence([]) == 0


def test_perfect_scores():
    passages = [{"relevance_score": 1.0} for _ in range(5)]
    assert compute_confidence(passages) == 100


def test_zero_scores():
    passages = [{"relevance_score": 0.0} for _ in range(3)]
    assert compute_confidence(passages) == 0


def test_mixed_scores():
    passages = [
        {"relevance_score": 0.9},
        {"relevance_score": 0.7},
        {"relevance_score": 0.5},
    ]
    score = compute_confidence(passages)
    assert 0 < score < 100
    # Weighted average should favor higher-ranked (0.9 has most weight)
    assert score > 50


def test_confidence_clamped_to_100():
    passages = [{"relevance_score": 1.5}]  # Unrealistic but tests clamping
    assert compute_confidence(passages) == 100


def test_top_k_respected():
    passages = [{"relevance_score": 0.9} for _ in range(10)]
    score_k3 = compute_confidence(passages, top_k=3)
    score_k5 = compute_confidence(passages, top_k=5)
    # Same scores, so both should be 90
    assert score_k3 == score_k5 == 90
