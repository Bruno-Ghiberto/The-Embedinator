"""Model listing endpoints -- proxies to Ollama and configured providers."""

import json

import httpx
from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import ModelInfo
from backend.config import settings

router = APIRouter()


_EMBED_PATTERNS = {"nomic-embed-text", "mxbai-embed-large"}


def _is_embed_model(name: str) -> bool:
    """Check if a model name is an embedding model."""
    base_name = name.split(":")[0] if ":" in name else name
    if base_name in _EMBED_PATTERNS:
        return True
    if name.endswith(":embed") or name.endswith(":embedding"):
        return True
    return False


async def _fetch_ollama_models(model_type: str) -> list[ModelInfo]:
    """Fetch models from Ollama /api/tags endpoint."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{settings.ollama_base_url}/api/tags")
            resp.raise_for_status()
    except (httpx.HTTPError, httpx.ConnectError, httpx.ConnectTimeout) as e:
        raise HTTPException(status_code=503, detail={
            "error": {
                "code": "SERVICE_UNAVAILABLE",
                "message": f"Ollama is unreachable: {e}",
                "details": {},
            },
            "trace_id": "",
        })

    data = resp.json()
    ollama_models = data.get("models", [])

    result = []
    for m in ollama_models:
        name = m.get("name", "")
        is_embed = _is_embed_model(name)

        if model_type == "embed" and not is_embed:
            continue
        if model_type == "llm" and is_embed:
            continue

        details = m.get("details", {})
        size_bytes = m.get("size", 0)
        size_gb = round(size_bytes / (1024 ** 3), 1) if size_bytes else None

        result.append(ModelInfo(
            name=name,
            provider="ollama",
            model_type="embed" if is_embed else "llm",
            size_gb=size_gb,
            quantization=details.get("quantization_level"),
            context_length=None,
        ))

    return result


@router.get("/api/models/llm")
async def list_llm_models(request: Request) -> dict:
    """List available language models from all providers."""
    models = await _fetch_ollama_models(model_type="llm")

    # Append cloud provider models where a key is stored
    db = getattr(request.app.state, "db", None)
    providers = await db.list_providers() if db is not None else []
    for p in providers:
        name = p["name"]
        if name == "ollama":
            continue
        if not p.get("api_key_encrypted"):
            continue
        config = json.loads(p.get("config_json") or "{}")
        model_name = config.get("model", "")
        if model_name:
            models.append(ModelInfo(
                name=model_name,
                provider=name,
                model_type="llm",
            ))

    return {"models": [m.model_dump() for m in models]}


@router.get("/api/models/embed")
async def list_embed_models(request: Request) -> dict:
    """List available embedding models."""
    models = await _fetch_ollama_models(model_type="embed")
    return {"models": [m.model_dump() for m in models]}
