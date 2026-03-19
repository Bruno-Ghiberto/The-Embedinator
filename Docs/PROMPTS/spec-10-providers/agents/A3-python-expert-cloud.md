# Agent A3: Python Expert — Cloud Providers

## Agent: python-expert | Model: claude-sonnet-4-5 | Wave: 2 (parallel with A2)

## Role

You are one of two agents running in parallel during Wave 2. Your scope is the three cloud
provider files. While you work on `openrouter.py`, `openai.py`, and `anthropic.py`, A2 works
independently on `ollama.py`. Your task: add retry-once logic and `ProviderRateLimitError`
raising on HTTP 429 to all three cloud LLM providers.

Wave 1 must be complete before you start (`ProviderRateLimitError` is defined in `base.py`
by A1). Import it from `backend.providers.base`.

---

## Assigned Tasks

**T009** — Add `_call_with_retry()` helper and `ProviderRateLimitError` raising to BOTH
`OpenRouterLLMProvider.generate()` AND `OpenRouterLLMProvider.generate_stream()` in
`backend/providers/openrouter.py`

**T010** — Add identical retry + 429 handling to BOTH `generate()` AND `generate_stream()`
in `OpenAILLMProvider` (`backend/providers/openai.py`) and `AnthropicLLMProvider`
(`backend/providers/anthropic.py`)

---

## File Scope

You touch ONLY these three files:
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/providers/openrouter.py`
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/providers/openai.py`
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/providers/anthropic.py`

Do NOT touch `ollama.py`, `base.py`, `registry.py`, or any test files.

---

## Implementation Notes

### _call_with_retry() — add to every cloud provider class

Add this as an instance method on `OpenRouterLLMProvider`, `OpenAILLMProvider`, and
`AnthropicLLMProvider`. The body is identical for all three:

```python
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
```

### Applying to generate() — non-streaming

Wrap the core request inside `_call_with_retry()`:

```python
async def generate(self, prompt: str, system_prompt: str = "") -> str:
    async def _request():
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(...)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    return await self._call_with_retry(_request)
```

### Applying to generate_stream() — streaming

For streaming, the retry wraps the initial connection and first response headers, NOT
individual chunk reads (you cannot retry a partially-consumed stream). Wrap the `client.post`
or `client.stream()` setup call inside `_call_with_retry`. If the connection itself fails with
5xx/timeout, the retry fires. Once streaming has started successfully, chunks flow through
unchanged.

```python
async def generate_stream(self, prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    async def _connect():
        # build and return the initial response object (not the chunks)
        ...

    response = await self._call_with_retry(_connect)
    # then yield chunks from response
```

The exact implementation depends on whether the provider uses `client.stream()` or
`client.post()` for streaming. Read each file to understand the current pattern before
modifying.

### Imports to add in each cloud provider file

```python
import httpx
from backend.providers.base import ProviderRateLimitError
```

`httpx` may already be imported. Add `ProviderRateLimitError` to the existing
`from backend.providers.base import ...` line.

---

## Critical Constraints

- Apply retry to BOTH `generate()` AND `generate_stream()` — not just one of them
- HTTP 429 raises `ProviderRateLimitError` immediately — NO retry on 429
- HTTP 4xx (other than 429) re-raises immediately — NO retry
- HTTP 5xx and `httpx.TimeoutException` — retry once; re-raise after second failure
- Do NOT change provider constructors, `health_check()`, or `get_model_name()`
- Do NOT touch `OllamaLLMProvider` — it never raises `ProviderRateLimitError`

---

## Testing Rule (MANDATORY)

```
NEVER run pytest directly inside Claude Code. Use ONLY:
  zsh scripts/run-tests-external.sh -n <name> <target>

Poll: cat Docs/Tests/<name>.status     (RUNNING | PASSED | FAILED | ERROR)
Read: cat Docs/Tests/<name>.summary    (~20 lines, token-efficient)
Full: cat Docs/Tests/<name>.log
```

---

## Gate Check

Your change is tested as part of the Wave 2 gate, run by the Orchestrator after BOTH A2 and
A3 complete. You do not need to run the gate yourself. After finishing T009-T010, notify the
Orchestrator that A3 (cloud providers) is complete.

Optional self-check before reporting done:
```bash
zsh scripts/run-tests-external.sh -n spec10-a3-check tests/unit/test_providers.py
```
