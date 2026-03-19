"""Unit tests for answer generator — T057."""

import pytest

from backend.agent.answer_generator import generate_answer_stream, generate_answer


class MockLLM:
    """Mock LLM provider that yields predefined tokens."""

    def __init__(self, tokens: list[str]):
        self._tokens = tokens

    async def generate_stream(self, prompt: str):
        for token in self._tokens:
            yield token

    async def generate(self, prompt: str) -> str:
        return "".join(self._tokens)


@pytest.mark.asyncio
async def test_stream_yields_tokens():
    """Verify streaming yields all tokens in order."""
    llm = MockLLM(["Hello", " ", "world", "!"])
    tokens = []
    async for token in generate_answer_stream(llm, "test prompt"):
        tokens.append(token)
    assert tokens == ["Hello", " ", "world", "!"]


@pytest.mark.asyncio
async def test_stream_empty():
    """Verify empty LLM response yields nothing."""
    llm = MockLLM([])
    tokens = []
    async for token in generate_answer_stream(llm, "test"):
        tokens.append(token)
    assert tokens == []


@pytest.mark.asyncio
async def test_generate_complete():
    """Verify non-streaming generation returns full text."""
    llm = MockLLM(["The", " answer", " is", " 42"])
    result = await generate_answer(llm, "test")
    assert result == "The answer is 42"
