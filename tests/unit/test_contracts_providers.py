"""Contract tests for provider layer: LLMProvider/EmbeddingProvider ABCs,
ProviderRegistry, KeyManager, concrete providers (FR-016, Pattern 5).
"""

import abc
import inspect

import pytest

from backend.providers.base import (
    LLMProvider,
    EmbeddingProvider,
    ProviderRateLimitError,
)
from backend.providers.registry import ProviderRegistry
from backend.providers.key_manager import KeyManager
from backend.providers.ollama import OllamaLLMProvider, OllamaEmbeddingProvider
from backend.providers.openrouter import OpenRouterLLMProvider
from backend.providers.openai import OpenAILLMProvider
from backend.providers.anthropic import AnthropicLLMProvider


class TestLLMProviderABC:
    """FR-016, Pattern 5: LLMProvider abstract base class contracts."""

    def test_llmprovider_is_abstract_base_class(self):
        """abc.ABC is in LLMProvider.__mro__."""
        assert abc.ABC in LLMProvider.__mro__

    def test_llmprovider_has_generate_abstract_method(self):
        """generate is an abstract method on LLMProvider."""
        method = getattr(LLMProvider, "generate", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_llmprovider_has_generate_stream_abstract_method(self):
        """generate_stream is an abstract method on LLMProvider."""
        method = getattr(LLMProvider, "generate_stream", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_llmprovider_has_health_check_abstract_method(self):
        """health_check is an abstract method on LLMProvider."""
        method = getattr(LLMProvider, "health_check", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_llmprovider_has_get_model_name_abstract_method(self):
        """get_model_name is an abstract method on LLMProvider."""
        method = getattr(LLMProvider, "get_model_name", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_llmprovider_has_exactly_4_abstract_methods(self):
        """LLMProvider has exactly 4 abstract methods."""
        abstract_methods = {
            name
            for name in dir(LLMProvider)
            if getattr(getattr(LLMProvider, name, None), "__isabstractmethod__", False)
        }
        assert abstract_methods == {
            "generate",
            "generate_stream",
            "health_check",
            "get_model_name",
        }

    def test_llmprovider_generate_has_prompt_param(self):
        """generate method has a prompt parameter."""
        sig = inspect.signature(LLMProvider.generate)
        assert "prompt" in sig.parameters

    def test_llmprovider_generate_has_system_prompt_param(self):
        """generate method has a system_prompt parameter."""
        sig = inspect.signature(LLMProvider.generate)
        assert "system_prompt" in sig.parameters

    def test_llmprovider_cannot_be_instantiated_directly(self):
        """Cannot instantiate LLMProvider directly (raises TypeError)."""
        with pytest.raises(TypeError):
            LLMProvider()


class TestEmbeddingProviderABC:
    """FR-016, Pattern 5: EmbeddingProvider abstract base class contracts."""

    def test_embeddingprovider_is_abstract_base_class(self):
        """abc.ABC is in EmbeddingProvider.__mro__."""
        assert abc.ABC in EmbeddingProvider.__mro__

    def test_embeddingprovider_has_embed_abstract_method(self):
        """embed is an abstract method on EmbeddingProvider."""
        method = getattr(EmbeddingProvider, "embed", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_embeddingprovider_has_embed_single_abstract_method(self):
        """embed_single is an abstract method on EmbeddingProvider."""
        method = getattr(EmbeddingProvider, "embed_single", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_embeddingprovider_has_get_model_name_abstract_method(self):
        """get_model_name is an abstract method on EmbeddingProvider."""
        method = getattr(EmbeddingProvider, "get_model_name", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_embeddingprovider_has_get_dimension_abstract_method(self):
        """get_dimension is an abstract method on EmbeddingProvider."""
        method = getattr(EmbeddingProvider, "get_dimension", None)
        assert method is not None
        assert getattr(method, "__isabstractmethod__", False)

    def test_embeddingprovider_has_exactly_4_abstract_methods(self):
        """EmbeddingProvider has exactly 4 abstract methods."""
        abstract_methods = {
            name
            for name in dir(EmbeddingProvider)
            if getattr(getattr(EmbeddingProvider, name, None), "__isabstractmethod__", False)
        }
        assert abstract_methods == {
            "embed",
            "embed_single",
            "get_model_name",
            "get_dimension",
        }

    def test_embeddingprovider_embed_has_optional_model_param(self):
        """embed method has an optional model parameter (spec-10 FR-006)."""
        sig = inspect.signature(EmbeddingProvider.embed)
        params = sig.parameters
        assert "model" in params
        # model must have a default value (making it optional)
        assert params["model"].default is not inspect.Parameter.empty

    def test_embeddingprovider_cannot_be_instantiated_directly(self):
        """Cannot instantiate EmbeddingProvider directly (raises TypeError)."""
        with pytest.raises(TypeError):
            EmbeddingProvider()


class TestProviderRegistry:
    """FR-016: ProviderRegistry contracts."""

    def test_registry_constructor_takes_settings_not_sqlitedb(self):
        """ProviderRegistry constructor takes settings (NOT SQLiteDB)."""
        sig = inspect.signature(ProviderRegistry.__init__)
        params = list(sig.parameters.keys())
        assert "settings" in params
        assert "db" not in params

    def test_registry_has_get_active_llm_method(self):
        """get_active_llm method exists on ProviderRegistry."""
        assert hasattr(ProviderRegistry, "get_active_llm")
        assert callable(ProviderRegistry.get_active_llm)

    def test_registry_has_get_active_langchain_model_method(self):
        """get_active_langchain_model method exists on ProviderRegistry."""
        assert hasattr(ProviderRegistry, "get_active_langchain_model")
        assert callable(ProviderRegistry.get_active_langchain_model)

    def test_registry_has_get_embedding_provider_method(self):
        """get_embedding_provider method exists on ProviderRegistry."""
        assert hasattr(ProviderRegistry, "get_embedding_provider")
        assert callable(ProviderRegistry.get_embedding_provider)

    def test_registry_has_set_active_provider_method(self):
        """set_active_provider method exists on ProviderRegistry."""
        assert hasattr(ProviderRegistry, "set_active_provider")
        assert callable(ProviderRegistry.set_active_provider)

    def test_get_embedding_provider_has_no_db_param(self):
        """get_embedding_provider takes NO db param (uses internal provider directly)."""
        sig = inspect.signature(ProviderRegistry.get_embedding_provider)
        params = list(sig.parameters.keys())
        assert "db" not in params


class TestKeyManagerAndConcreteProviders:
    """FR-016: KeyManager and concrete provider contracts."""

    def test_keymanager_has_encrypt_method(self):
        """KeyManager has encrypt method."""
        assert hasattr(KeyManager, "encrypt")
        assert callable(KeyManager.encrypt)

    def test_keymanager_has_decrypt_method(self):
        """KeyManager has decrypt method."""
        assert hasattr(KeyManager, "decrypt")
        assert callable(KeyManager.decrypt)

    def test_keymanager_has_is_valid_key_method(self):
        """KeyManager has is_valid_key method."""
        assert hasattr(KeyManager, "is_valid_key")
        assert callable(KeyManager.is_valid_key)

    def test_ollama_llm_provider_is_concrete_llmprovider_subclass(self):
        """OllamaLLMProvider is a concrete LLMProvider subclass."""
        assert issubclass(OllamaLLMProvider, LLMProvider)

    def test_openrouter_llm_provider_is_concrete_llmprovider_subclass(self):
        """OpenRouterLLMProvider is a concrete LLMProvider subclass."""
        assert issubclass(OpenRouterLLMProvider, LLMProvider)

    def test_openai_llm_provider_is_concrete_llmprovider_subclass(self):
        """OpenAILLMProvider is a concrete LLMProvider subclass."""
        assert issubclass(OpenAILLMProvider, LLMProvider)

    def test_anthropic_llm_provider_is_concrete_llmprovider_subclass(self):
        """AnthropicLLMProvider is a concrete LLMProvider subclass."""
        assert issubclass(AnthropicLLMProvider, LLMProvider)

    def test_ollama_embedding_provider_is_concrete_embeddingprovider_subclass(self):
        """OllamaEmbeddingProvider is a concrete EmbeddingProvider subclass."""
        assert issubclass(OllamaEmbeddingProvider, EmbeddingProvider)

    def test_provider_rate_limit_error_exists_in_base(self):
        """ProviderRateLimitError exists in backend/providers/base.py."""
        assert ProviderRateLimitError is not None

    def test_provider_rate_limit_error_is_exception_subclass(self):
        """ProviderRateLimitError is an Exception subclass."""
        assert issubclass(ProviderRateLimitError, Exception)
