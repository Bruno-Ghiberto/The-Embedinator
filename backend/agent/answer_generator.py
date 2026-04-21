"""Streaming answer generation — T053.

Wraps LLM streaming to yield text chunks progressively for NDJSON output.
"""

from typing import AsyncIterator

from backend.providers.base import LLMProvider


async def generate_answer_stream(
    llm: LLMProvider,
    prompt: str,
) -> AsyncIterator[str]:
    """Stream answer text from the LLM, yielding individual tokens/chunks.

    The caller is responsible for wrapping chunks in NDJSON format.
    """
    async for token in llm.generate_stream(prompt):
        yield token


async def generate_answer(
    llm: LLMProvider,
    prompt: str,
) -> str:
    """Generate a complete (non-streaming) answer from the LLM."""
    return await llm.generate(prompt)
