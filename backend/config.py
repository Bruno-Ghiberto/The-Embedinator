"""Application configuration via environment variables with sensible local-first defaults."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # Observability: per-component log level overrides (US3, FR-004)
    # Format: comma-separated module.path=LEVEL pairs
    # Example: backend.retrieval.reranker=DEBUG,backend.storage.sqlite_db=WARNING
    log_level_overrides: str = Field(default="", alias="LOG_LEVEL_OVERRIDES")

    # Frontend
    frontend_port: int = 3000

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = Field(default=6333, alias="EMBEDINATOR_PORT_QDRANT")

    # Providers
    ollama_base_url: str = "http://localhost:11434"
    default_provider: str = "ollama"
    default_llm_model: str = "qwen2.5:7b"  # spec-26: FR-004 Path B — revert to proven non-thinking model
    supported_llm_models: list[str] = [
        "qwen2.5:7b",
        "llama3.1:8b",
        "mistral:7b",
    ]  # spec-26: FR-004 — tested-and-recommended list; thinking models unsupported, see docs/performance.md
    default_embed_model: str = "nomic-embed-text"
    api_key_encryption_secret: str = Field(default="", alias="EMBEDINATOR_FERNET_KEY")  # Constitution V

    # SQLite
    sqlite_path: str = "data/embedinator.db"
    checkpoint_max_threads: int = 100  # spec-26 DISK-001: cap LangGraph checkpoints.db growth; prune oldest threads on startup. Set 0 to disable.

    # Ingestion
    upload_dir: str = "data/uploads"
    max_upload_size_mb: int = 100
    parent_chunk_size: int = 3000
    child_chunk_size: int = 500
    embed_batch_size: int = 16
    rust_worker_path: str = "ingestion-worker/target/release/embedinator-worker"
    embed_max_workers: int = 4
    qdrant_upsert_batch_size: int = 50

    # Agent
    max_iterations: int = 10
    max_tool_calls: int = 8
    max_loop_seconds: int = 300  # BUG-008: wall-clock deadline for research loop
    confidence_threshold: int = 60  # 0–100 scale
    compression_threshold: float = 0.75
    meta_reasoning_max_attempts: int = 2
    meta_relevance_threshold: float = 0.2  # R4: mean cross-encoder score threshold
    meta_variance_threshold: float = 0.15  # R4: stdev threshold for noisy results

    # Retrieval
    hybrid_dense_weight: float = 0.7
    hybrid_sparse_weight: float = 0.3
    top_k_retrieval: int = 20
    top_k_rerank: int = 5
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Accuracy & Robustness
    groundedness_check_enabled: bool = True
    citation_alignment_threshold: float = 0.3
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_cooldown_secs: int = 30
    retry_max_attempts: int = 3
    retry_backoff_initial_secs: float = 1.0

    # Rate Limiting
    rate_limit_chat_per_minute: int = 30
    rate_limit_ingest_per_minute: int = 10
    rate_limit_provider_keys_per_minute: int = 5
    rate_limit_general_per_minute: int = 120

    # CORS
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True, extra="ignore")


settings = Settings()
