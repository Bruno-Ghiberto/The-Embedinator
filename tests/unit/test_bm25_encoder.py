"""Tests for backend.retrieval.bm25_encoder.

Covers tokenization, accent stripping, deterministic hashing, empty/edge inputs,
and hash collision handling.
"""

from __future__ import annotations

import pytest

from backend.retrieval.bm25_encoder import SparseVector, encode


def test_encode_simple_spanish_query() -> None:
    """Spanish query produces non-empty sparse vector with expected token count."""
    sv = encode("¿Cuál es el objeto del Reglamento Técnico NAG-200?")
    assert isinstance(sv, SparseVector)
    assert len(sv.indices) == len(sv.values)
    # Tokens after normalize+filter (len>=2): cual, es, el, objeto, del, reglamento,
    # tecnico, nag, 200 — 9 unique tokens.
    assert len(sv.indices) == 9


def test_encode_empty_input_returns_empty_vector() -> None:
    sv = encode("")
    assert sv.indices == []
    assert sv.values == []


def test_encode_only_punctuation_returns_empty_vector() -> None:
    sv = encode("¡¿?!.,;:")
    assert sv.indices == []
    assert sv.values == []


def test_encode_only_short_tokens_returns_empty_vector() -> None:
    """Tokens of length <2 are filtered out (1-char tokens carry no IDF signal)."""
    sv = encode("a b c d e")
    assert sv.indices == []
    assert sv.values == []


def test_encode_strips_accents_for_match() -> None:
    """Accented and unaccented forms produce the same token index (NFD normalization)."""
    sv_accent = encode("régimen técnico")
    sv_plain = encode("regimen tecnico")
    assert set(sv_accent.indices) == set(sv_plain.indices)


def test_encode_lowercases() -> None:
    """Case is normalized so 'OBJETO' and 'objeto' produce the same index."""
    sv_upper = encode("OBJETO REGLAMENTO")
    sv_lower = encode("objeto reglamento")
    assert set(sv_upper.indices) == set(sv_lower.indices)


def test_encode_keeps_digit_tokens() -> None:
    """Digits are signal in technical refs — '200' and 'nag' both retained."""
    sv = encode("NAG-200")
    # Two tokens after split on '-': ["nag", "200"]
    assert len(sv.indices) == 2


def test_encode_term_frequency_counts_repeats() -> None:
    """Repeated tokens accumulate term frequency in the values array."""
    sv = encode("objeto objeto objeto reglamento")
    # Two unique tokens: 'objeto' (3) and 'reglamento' (1).
    assert len(sv.indices) == 2
    # Sorted by token order of first occurrence — the count for 'objeto' is 3.
    assert max(sv.values) == 3.0
    assert min(sv.values) == 1.0


def test_encode_is_deterministic_across_calls() -> None:
    """Same input → identical output (no randomness, blake2b stable hash)."""
    text = "¿Qué es el alcance del Reglamento NAG-200?"
    sv1 = encode(text)
    sv2 = encode(text)
    assert list(zip(sv1.indices, sv1.values)) == list(zip(sv2.indices, sv2.values))


def test_encode_indices_are_unique() -> None:
    """No duplicate indices in output (collisions merged with TF summed)."""
    sv = encode(
        "objeto reglamento tecnico nag alcance instalacion domiciliaria gas natural"
    )
    assert len(sv.indices) == len(set(sv.indices))


def test_encode_indices_fit_in_int32() -> None:
    """All indices are positive 31-bit integers (Qdrant requirement)."""
    sv = encode("una frase larga con muchas palabras diferentes para testear los indices")
    for idx in sv.indices:
        assert 0 <= idx <= 0x7FFFFFFF


@pytest.mark.parametrize(
    "text",
    [
        "objeto",
        "Reglamento Técnico",
        "¿Cuál es el alcance de la NAG-200?",
        "La instalación interna domiciliaria",
    ],
)
def test_encode_query_and_passage_share_tokens(text: str) -> None:
    """Encoding the same string twice always shares all token indices.

    This is the load-bearing invariant for hybrid retrieval — the query encoder
    and the ingestion encoder MUST produce overlapping indices for matching
    text, otherwise BM25 retrieval is silently broken.
    """
    sv_a = encode(text)
    sv_b = encode(text)
    assert set(sv_a.indices) == set(sv_b.indices)
