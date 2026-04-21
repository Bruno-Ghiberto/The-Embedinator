"""Anthropic cloud LLM provider — T070."""

import json
from typing import AsyncIterator

import httpx

from backend.providers.base import LLMProvider, ProviderRateLimitError


class AnthropicLLMProvider(LLMProvider):
    """Anthropic API provider (Claude models)."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.anthropic.com/v1"

    async def _call_with_retry(self, make_request_fn):
        """Retry once on 5xx or timeout; raise ProviderRateLimitError on 429."""
        for attempt in range(2):
            try:
                return await make_request_fn()
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    raise ProviderRateLimitError(provider=self.__class__.__name__) from exc
                if exc.response.status_code < 500:
                    raise  # 4xx other than 429: no retry
                if attempt == 1:
                    raise
            except httpx.TimeoutException:
                if attempt == 1:
                    raise

    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        payload: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_prompt:
            payload["system"] = system_prompt

        async def _request():
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]

        return await self._call_with_retry(_request)

    async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
        payload: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "stream": True,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async def _connect():
            client = httpx.AsyncClient(timeout=120)
            try:
                req = client.build_request(
                    "POST",
                    f"{self.base_url}/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp = await client.send(req, stream=True)
                if resp.status_code >= 400:
                    await resp.aread()
                    resp.raise_for_status()
                return client, resp
            except Exception:
                await client.aclose()
                raise

        client, resp = await self._call_with_retry(_connect)
        try:
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    try:
                        event = json.loads(line[6:])
                        if event.get("type") == "content_block_delta":
                            text = event["delta"].get("text", "")
                            if text:
                                yield text
                    except json.JSONDecodeError:
                        continue
        finally:
            await resp.aclose()
            await client.aclose()

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.base_url}/models",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                return resp.status_code == 200
        except Exception:
            return False

    def get_model_name(self) -> str:
        return self.model
