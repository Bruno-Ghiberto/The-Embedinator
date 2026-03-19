"""Provider management endpoints -- key storage and listing."""

import asyncio
import json

from fastapi import APIRouter, HTTPException, Request

from backend.agent.schemas import ProviderDetailResponse, ProviderHealthSchema, ProviderKeyRequest
from backend.config import settings

router = APIRouter()


@router.get("/api/providers")
async def list_providers(request: Request) -> dict:
    """List all configured providers with has_key indicator."""
    db = request.app.state.db
    providers = await db.list_providers()

    result = []
    for p in providers:
        result.append(ProviderDetailResponse(
            name=p["name"],
            is_active=bool(p["is_active"]),
            has_key=p.get("api_key_encrypted") is not None and p["api_key_encrypted"] != "",
            base_url=p.get("base_url"),
            model_count=0,
        ))

    # Always include Ollama even if not in DB
    if not any(p.name == "ollama" for p in result):
        result.insert(0, ProviderDetailResponse(
            name="ollama",
            is_active=True,
            has_key=False,
            base_url=None,
            model_count=0,
        ))

    return {"providers": [p.model_dump() for p in result]}


@router.put("/api/providers/{name}/key")
async def save_provider_key(name: str, body: ProviderKeyRequest, request: Request) -> dict:
    """Save or replace an encrypted API key for a provider."""
    db = request.app.state.db
    key_manager = request.app.state.key_manager
    trace_id = getattr(request.state, "trace_id", "")

    if key_manager is None:
        raise HTTPException(status_code=503, detail={
            "error": {
                "code": "KEY_MANAGER_UNAVAILABLE",
                "message": "Encryption key not configured. Set EMBEDINATOR_FERNET_KEY environment variable.",
                "details": {},
            },
            "trace_id": trace_id,
        })

    provider = await db.get_provider(name)
    if not provider:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "PROVIDER_NOT_FOUND",
                "message": f"Provider '{name}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    encrypted = key_manager.encrypt(body.api_key)
    await db.update_provider(name, api_key_encrypted=encrypted)

    return {"name": name, "has_key": True}


@router.get("/api/providers/health")
async def provider_health(request: Request) -> dict:
    """Check reachability of all configured providers concurrently."""
    db = request.app.state.db
    key_manager = request.app.state.key_manager
    providers = await db.list_providers()

    # Ensure Ollama always appears even if not in DB
    provider_names = {p["name"] for p in providers}
    if "ollama" not in provider_names:
        providers.insert(0, {"name": "ollama", "api_key_encrypted": None, "config_json": "{}"})

    async def check_one(p: dict) -> ProviderHealthSchema:
        name = p["name"]
        has_key = bool(p.get("api_key_encrypted"))

        if name == "ollama":
            try:
                from backend.providers.ollama import OllamaLLMProvider
                provider_instance = OllamaLLMProvider(
                    base_url=settings.ollama_base_url,
                    model=settings.default_llm_model,
                )
                reachable = await provider_instance.health_check()
            except Exception:
                reachable = False
            return ProviderHealthSchema(provider=name, reachable=reachable)

        if not has_key or key_manager is None:
            return ProviderHealthSchema(provider=name, reachable=False)

        try:
            key = key_manager.decrypt(p["api_key_encrypted"])
            config = json.loads(p.get("config_json") or "{}")
            model = config.get("model", "")

            if name == "openrouter":
                from backend.providers.openrouter import OpenRouterLLMProvider
                provider_instance = OpenRouterLLMProvider(api_key=key, model=model)
            elif name == "openai":
                from backend.providers.openai import OpenAILLMProvider
                provider_instance = OpenAILLMProvider(api_key=key, model=model)
            elif name == "anthropic":
                from backend.providers.anthropic import AnthropicLLMProvider
                provider_instance = AnthropicLLMProvider(api_key=key, model=model)
            else:
                return ProviderHealthSchema(provider=name, reachable=False)

            reachable = await provider_instance.health_check()
        except Exception:
            reachable = False

        return ProviderHealthSchema(provider=name, reachable=reachable)

    results = await asyncio.gather(*[check_one(p) for p in providers])
    return {"health": [r.model_dump() for r in results]}


@router.delete("/api/providers/{name}/key")
async def delete_provider_key(name: str, request: Request) -> dict:
    """Remove a stored API key."""
    db = request.app.state.db
    trace_id = getattr(request.state, "trace_id", "")

    provider = await db.get_provider(name)
    if not provider:
        raise HTTPException(status_code=404, detail={
            "error": {
                "code": "PROVIDER_NOT_FOUND",
                "message": f"Provider '{name}' not found",
                "details": {},
            },
            "trace_id": trace_id,
        })

    await db.update_provider(name, api_key_encrypted="")

    return {"name": name, "has_key": False}
