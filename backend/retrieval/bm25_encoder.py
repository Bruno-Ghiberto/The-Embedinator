"""Lightweight BM25 sparse vector encoder for Qdrant hybrid retrieval.

Pairs with the `Modifier.IDF` configured on the `sparse` named vector at
collection creation: the encoder emits raw term-frequency counts and Qdrant
applies IDF re-weighting server-side using its corpus statistics. The same
encoder is used for both ingestion (chunk text → sparse vector) and query time
(user question → sparse vector); deterministic blake2b hashing makes the token
→ index mapping stable across processes without a persisted vocabulary.

Why custom (vs. fastembed / Qdrant Document inference): the corpus is small
(<10k chunks) and Spanish-tuned tokenization is the dominant signal; pulling
fastembed adds ~150 MB to the image for ONNX runtime that is overkill here.
This encoder is ~50 lines, dependency-free, and Spanish-aware.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

# Qdrant supports unsigned 32-bit indices for sparse vectors. Use 31 bits to
# keep values comfortably positive when interpreted as signed ints.
_INDEX_MASK = 0x7FFFFFFF

# Tokens shorter than this contain little IDF signal in Spanish technical text.
# (Most Spanish stop words are 2-3 chars — IDF will already downweight them,
# but excluding 1-char tokens removes a lot of noise from punctuation splits.)
_MIN_TOKEN_LEN = 2

# Split on anything that is not a word character (Unicode-aware).
_TOKEN_SPLIT_RE = re.compile(r"[^\w]+", flags=re.UNICODE)


@dataclass
class SparseVector:
    """Sparse vector payload for Qdrant `sparse` named vector with IDF modifier.

    `indices` are deterministic 31-bit hashes of normalized tokens.
    `values` are raw term frequencies; Qdrant applies IDF on the server.
    """

    indices: list[int]
    values: list[float]


def _normalize(text: str) -> str:
    """Lowercase + strip accent marks (NFD decomposition, drop combining marks)."""
    text = text.lower()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def _tokenize(text: str) -> list[str]:
    """Split on non-word boundaries; keep alphanumeric tokens of length >= 2.

    Digits are intentionally retained — the NAG corpus is full of technical
    references like "NAG-200", "§1.1", and "tabla 6.29" where numeric tokens
    carry significant signal. Pure stop words are not filtered explicitly;
    BM25 IDF naturally downweights them across the corpus.
    """
    normalized = _normalize(text)
    return [tok for tok in _TOKEN_SPLIT_RE.split(normalized) if len(tok) >= _MIN_TOKEN_LEN]


def _token_index(token: str) -> int:
    """Deterministic 31-bit token index via blake2b (stable across processes)."""
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=4).digest()
    return int.from_bytes(digest, "big") & _INDEX_MASK


def encode(text: str) -> SparseVector:
    """Encode text into a Qdrant-compatible BM25 sparse vector.

    Empty or all-stop-word inputs return an empty SparseVector, which Qdrant
    accepts (no points score against it). Callers that pass empty inputs should
    fall back to dense-only search at the query layer.
    """
    tokens = _tokenize(text)
    if not tokens:
        return SparseVector(indices=[], values=[])

    counts = Counter(tokens)
    indices: list[int] = []
    values: list[float] = []
    seen: dict[int, int] = {}

    # Two tokens could hash to the same index (rare but possible at 2^31).
    # Sum their TFs at the same position to avoid duplicate-index errors from
    # Qdrant.
    for token, count in counts.items():
        idx = _token_index(token)
        if idx in seen:
            values[seen[idx]] += float(count)
        else:
            seen[idx] = len(indices)
            indices.append(idx)
            values.append(float(count))

    return SparseVector(indices=indices, values=values)
