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
