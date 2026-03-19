# Agent A2: Python Expert — Ollama

## Agent: python-expert | Model: claude-sonnet-4-5 | Wave: 2 (parallel with A3)

## Role

You are one of two agents running in parallel during Wave 2. Your scope is exclusively the
Ollama embedding provider. While you work on `ollama.py`, A3 works independently on the three
cloud provider files. Your task is small and focused: update `OllamaEmbeddingProvider` to
accept and use an optional model override in both `embed()` and `embed_single()`.

Wave 1 must be complete before you start (base.py abstract signatures are already updated).

---

## Assigned Tasks

**T008** — Update `OllamaEmbeddingProvider.embed()` and `OllamaEmbeddingProvider.embed_single()`
in `backend/providers/ollama.py` to accept `model: str | None = None` and use
`effective_model = model or self.model` in the API payload.

---

## File Scope

You touch ONLY this one file:
- `/home/brunoghiberto/Documents/Projects/The-Embedinator/backend/providers/ollama.py`

Do NOT touch `OllamaLLMProvider`. Do NOT touch any cloud provider files.
Do NOT touch any test files.

---

## Implementation Notes

### Current embed_single() body (lines ~98-115)

```python
async def embed_single(self, text: str) -> list[float]:
    """Generate embedding for a single text."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": text},
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["embeddings"][0]
            if self._dimension is None:
                self._dimension = len(embedding)
            return embedding
    except httpx.ConnectError as e:
        raise OllamaConnectionError(f"Cannot connect to Ollama: {e}") from e
    except Exception as e:
        raise EmbeddingError(f"Ollama embedding failed: {e}") from e
```

### Required change

1. Add `model: str | None = None` parameter to `embed_single()`
2. Add `effective_model = model or self.model` before the `async with` block
3. Replace `"model": self.model` with `"model": effective_model` in the JSON payload

### Current embed() body (lines ~90-96)

```python
async def embed(self, texts: list[str]) -> list[list[float]]:
    """Generate embeddings for multiple texts."""
    results = []
    for text in texts:
        embedding = await self.embed_single(text)
        results.append(embedding)
    return results
```

### Required change

1. Add `model: str | None = None` parameter to `embed()`
2. Forward it to `embed_single(text, model=model)`

The class already stores `self.model` in `__init__`. No constructor changes are needed.
`get_model_name()` and `get_dimension()` are unchanged.

---

## Critical Constraints

- Do NOT modify `OllamaLLMProvider` — it is out of scope
- Do NOT change the httpx endpoint URL or timeout values
- The `model` parameter is optional — existing callers that pass no `model` must continue to work
- Do NOT change the error handling (OllamaConnectionError, EmbeddingError) — preserve as-is

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
A3 complete. You do not need to run the gate yourself. After finishing T008, notify the
Orchestrator that A2 (ollama.py) is complete.

Optional self-check before reporting done:
```bash
zsh scripts/run-tests-external.sh -n spec10-a2-check tests/unit/test_providers.py
```
This runs only the provider unit tests — faster than the full suite.
