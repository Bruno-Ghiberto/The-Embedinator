"""Custom exception hierarchy for The Embedinator."""


class EmbeddinatorError(Exception):
    """Base exception for all Embedinator errors."""


class QdrantConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Qdrant."""


class OllamaConnectionError(EmbeddinatorError):
    """Failed to connect to or communicate with Ollama."""


class SQLiteError(EmbeddinatorError):
    """SQLite operation failed."""


class LLMCallError(EmbeddinatorError):
    """LLM inference call failed."""


class EmbeddingError(EmbeddinatorError):
    """Embedding generation failed."""


class IngestionError(EmbeddinatorError):
    """Document ingestion pipeline failed."""


class SessionLoadError(EmbeddinatorError):
    """Failed to load session from SQLite."""


class StructuredOutputParseError(EmbeddinatorError):
    """Failed to parse structured output from LLM."""


class RerankerError(EmbeddinatorError):
    """Cross-encoder reranking failed."""


class CircuitOpenError(EmbeddinatorError):
    """Raised when a circuit breaker is open."""


class UnsupportedModelError(EmbeddinatorError):
    """Raised at startup when the configured LLM is not in supported_llm_models."""

    def __init__(self, model: str, supported: list[str]) -> None:
        self.model = model
        self.supported = supported
        super().__init__(
            f"Configured LLM {model!r} is not supported in this release. "
            f"Supported: {', '.join(supported)}. "
            f"Thinking models are explicitly unsupported — see docs/performance.md."
        )
