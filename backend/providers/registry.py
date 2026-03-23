"""Provider registry for runtime provider resolution and switching."""

import json

import structlog

from backend.config import Settings
from backend.providers.base import LLMProvider, EmbeddingProvider
from backend.providers.ollama import OllamaLLMProvider, OllamaEmbeddingProvider
from backend.storage.sqlite_db import SQLiteDB

logger = structlog.get_logger().bind(component=__name__)


class ProviderRegistry:
    """Resolves provider names to instances. Reads active provider from DB on each call."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._ollama_llm = OllamaLLMProvider(
            base_url=settings.ollama_base_url,
            model=settings.default_llm_model,
        )
        self._ollama_embed = OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.default_embed_model,
        )

    async def initialize(self, db: SQLiteDB):
        """Ensure default Ollama provider is registered in DB."""
        active = await db.get_active_provider()
        if not active:
            await db.upsert_provider(
                name="ollama",
                provider_type="local",
                config_json=json.dumps({
                    "model": self.settings.default_llm_model,
                    "embed_model": self.settings.default_embed_model,
                }),
                is_active=True,
            )
            logger.info("provider_default_registered", name="ollama")

    async def get_active_llm(self, db: SQLiteDB) -> LLMProvider:
        """Get the currently active LLM provider instance."""
        active = await db.get_active_provider()
        if not active or active["name"] == "ollama":
            return self._ollama_llm

        # Cloud providers — lazy import to avoid dependency when not used
        config = json.loads(active["config_json"])
        provider_name = active["name"]

        if provider_name == "openrouter":
            from backend.providers.openrouter import OpenRouterLLMProvider
            return OpenRouterLLMProvider(api_key=config.get("api_key", ""), model=config.get("model", ""))
        elif provider_name == "openai":
            from backend.providers.openai import OpenAILLMProvider
            return OpenAILLMProvider(api_key=config.get("api_key", ""), model=config.get("model", ""))
        elif provider_name == "anthropic":
            from backend.providers.anthropic import AnthropicLLMProvider
            return AnthropicLLMProvider(api_key=config.get("api_key", ""), model=config.get("model", ""))

        # Fallback to Ollama
        logger.warning("provider_unknown_fallback", name=provider_name, error="UnknownProvider")
        return self._ollama_llm

    async def get_active_langchain_model(self, db: SQLiteDB):
        """Return a LangChain BaseChatModel for the active provider.

        Used by agent graph nodes (ainvoke, with_structured_output, bind_tools).
        Coexists with get_active_llm() which returns LLMProvider for httpx streaming.
        """
        active = await db.get_active_provider()
        if not active or active["name"] == "ollama":
            from langchain_ollama import ChatOllama
            # Prefer model from DB config_json over settings default
            ollama_config = json.loads(active["config_json"] or "{}") if active else {}
            ollama_model = ollama_config.get("model") or self.settings.default_llm_model
            return ChatOllama(
                base_url=self.settings.ollama_base_url,
                model=ollama_model,
            )

        config = json.loads(active["config_json"] or "{}")
        model = config.get("model", "")
        name = active["name"]

        # Decrypt API key (in-memory only, discarded after constructor call)
        key = None
        if active.get("api_key_encrypted"):
            try:
                from backend.providers.key_manager import KeyManager
                key_manager = KeyManager()
                key = key_manager.decrypt(active["api_key_encrypted"])
            except Exception:
                pass

        if not key:
            # No key available — fall back to Ollama
            from langchain_ollama import ChatOllama
            return ChatOllama(
                base_url=self.settings.ollama_base_url,
                model=self.settings.default_llm_model,
            )

        if name in ("openrouter", "openai"):
            from langchain_openai import ChatOpenAI
            base_url = (
                "https://openrouter.ai/api/v1" if name == "openrouter"
                else "https://api.openai.com/v1"
            )
            return ChatOpenAI(api_key=key, model=model, base_url=base_url)
        elif name == "anthropic":
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(api_key=key, model=model)

        # Unknown provider — fall back to Ollama
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=self.settings.ollama_base_url,
            model=self.settings.default_llm_model,
        )

    async def get_embedding_provider(self) -> EmbeddingProvider:
        """Get the embedding provider (always Ollama for Phase 1)."""
        return self._ollama_embed

    async def set_active_provider(
        self, db: SQLiteDB, name: str, config: dict | None = None
    ) -> bool:
        """Switch the active provider."""
        config_json = json.dumps(config or {})
        provider_type = "local" if name == "ollama" else "cloud"
        await db.upsert_provider(name, provider_type, config_json, is_active=True)
        logger.info("provider_set_active", name=name)
        return True
