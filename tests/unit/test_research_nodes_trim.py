"""Unit tests for count_message_tokens helper and trim_messages token-counting fix.

spec-26: FR-007 — Proper Token Counting in Message Trimming (BUG-019).
Tests validate that count_message_tokens returns accurate token counts and that
trim_messages(token_counter=...) correctly trims a 10 000-token conversation.
"""
from __future__ import annotations

import pytest
import tiktoken
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.messages import trim_messages

from backend.agent.nodes import count_message_tokens


class _StubModelWithCountTokens:
    """Minimal stub exposing count_tokens() backed by cl100k_base — avoids Ollama dependency."""

    def __init__(self):
        self._enc = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        return len(self._enc.encode(str(text)))


class _StubModelWithoutCountTokens:
    """Stub that does NOT expose count_tokens — triggers tiktoken fallback path."""
    pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_messages_approx_n_tokens(target_tokens: int, enc) -> list:
    """Build a list of HumanMessages whose total token count approximates target_tokens."""
    # Each message: ~50 tokens of content.  Repeat to reach the target.
    per_msg = 50
    word = "apple "  # ~1 token each
    content = (word * per_msg).strip()
    actual_per_msg = len(enc.encode(content))
    n_msgs = max(1, target_tokens // actual_per_msg)
    return [HumanMessage(content=content) for _ in range(n_msgs)]


# ---------------------------------------------------------------------------
# Tests: count_message_tokens
# ---------------------------------------------------------------------------

def test_count_message_tokens_uses_model_count_tokens():
    """When model.count_tokens() is available it should be used (provider-aware path)."""
    stub = _StubModelWithCountTokens()
    msgs = [HumanMessage(content="Hello world")]
    result = count_message_tokens(msgs, stub)
    # tiktoken cl100k_base on "Hello world" = 2 tokens
    expected = len(tiktoken.get_encoding("cl100k_base").encode("Hello world"))
    assert result == expected


def test_count_message_tokens_falls_back_to_tiktoken():
    """When model has no count_tokens(), tiktoken fallback must still return a positive count."""
    stub = _StubModelWithoutCountTokens()
    msgs = [HumanMessage(content="Hello world"), SystemMessage(content="You are helpful.")]
    result = count_message_tokens(msgs, stub)
    assert result > 0


def test_count_message_tokens_none_model_falls_back_to_tiktoken():
    """Passing model=None must not raise; tiktoken fallback handles it."""
    msgs = [HumanMessage(content="Some text here")]
    result = count_message_tokens(msgs, None)
    assert result > 0


def test_count_message_tokens_approximates_true_tokens():
    """Counter must stay within ±5% of the known tiktoken count for a 10 000-token corpus."""
    enc = tiktoken.get_encoding("cl100k_base")
    target_tokens = 10_000
    msgs = _build_messages_approx_n_tokens(target_tokens, enc)

    stub = _StubModelWithCountTokens()
    counted = count_message_tokens(msgs, stub)

    # Verify independently what tiktoken thinks the total is
    true_count = sum(len(enc.encode(str(m.content))) for m in msgs if getattr(m, "content", None))

    # The helper must agree with the independent count (same encoder used)
    assert counted == true_count, f"count_message_tokens={counted} but direct tiktoken={true_count}"
    # And the corpus should be close to 10 000 tokens (corpus construction sanity-check)
    assert 8_000 <= true_count <= 12_000, f"Corpus not near 10 000 tokens: {true_count}"


# ---------------------------------------------------------------------------
# Tests: trim_messages integration
# ---------------------------------------------------------------------------

def test_trim_messages_respects_max_tokens():
    """trim_messages with count_message_tokens must produce a list whose total is ≤ max_tokens."""
    enc = tiktoken.get_encoding("cl100k_base")
    target_tokens = 10_000
    msgs = _build_messages_approx_n_tokens(target_tokens, enc)

    stub = _StubModelWithCountTokens()
    max_tokens = 6_000

    trimmed = trim_messages(
        msgs,
        max_tokens=max_tokens,
        token_counter=lambda m: count_message_tokens(m, stub),
        strategy="last",
        include_system=True,
        allow_partial=False,
    )

    trimmed_count = count_message_tokens(trimmed, stub)
    assert trimmed_count <= max_tokens, (
        f"Trimmed message list has {trimmed_count} tokens, exceeds max_tokens={max_tokens}"
    )
    assert len(trimmed) < len(msgs), "trim_messages should have removed some messages"


def test_trim_messages_does_not_trim_short_conversation():
    """trim_messages must leave a short conversation unchanged."""
    msgs = [HumanMessage(content="hi"), SystemMessage(content="hello")]
    stub = _StubModelWithCountTokens()

    trimmed = trim_messages(
        msgs,
        max_tokens=6_000,
        token_counter=lambda m: count_message_tokens(m, stub),
        strategy="last",
        include_system=True,
        allow_partial=False,
    )

    assert len(trimmed) == len(msgs)
