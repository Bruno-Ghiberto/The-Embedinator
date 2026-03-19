"""FastAPI application factory with lifespan management."""

import logging
import logging as stdlib_logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import settings
from backend.providers.base import ProviderRateLimitError
from backend.errors import EmbeddinatorError, QdrantConnectionError, OllamaConnectionError
from backend.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
    TraceIDMiddleware,
)
from backend.storage.sqlite_db import SQLiteDB
from backend.storage.qdrant_client import QdrantClientWrapper
from backend.providers.registry import ProviderRegistry
from backend.api import collections, documents, chat, traces, providers, health
from backend.api import ingest as ingest_router
from backend.api import models as models_router
from backend.api import settings as api_settings


_SENSITIVE_KEYS = {"api_key", "password", "secret", "token", "authorization"}


def _strip_sensitive_fields(logger, method, event_dict: dict) -> dict:
    """Redact sensitive field values in log records (FR-006)."""
    for key in list(event_dict.keys()):
        if key.lower() in _SENSITIVE_KEYS:
            event_dict[key] = "[REDACTED]"
    return event_dict


def _configure_logging(log_level: str = "INFO", log_level_overrides: str = ""):
    """Configure structured JSON logging with structlog.

    Builds a per-component level filter from LOG_LEVEL_OVERRIDES and inserts it
    between merge_contextvars and add_log_level so that method_name is still
    the raw log-method string (T038–T039, US3, FR-004).
    """
    # --- Parse per-component override string (T038) ---
    override_map: dict[str, int] = {}
    _startup_warnings: list[tuple[str, dict]] = []

    for pair in log_level_overrides.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            _startup_warnings.append(("http_log_override_invalid_format", {"pair": pair}))
            continue
        module, level_str = pair.split("=", 1)
        level_int = stdlib_logging.getLevelName(level_str.strip().upper())
        if not isinstance(level_int, int):
            _startup_warnings.append(
                (
                    "http_log_override_invalid_level",
                    {"module": module.strip(), "level": level_str.strip()},
                )
            )
            continue
        override_map[module.strip()] = level_int

    # --- Per-component filter processor (T039) ---
    def _filter_by_component(logger, method_name: str, event_dict: dict) -> dict:
        """Drop events that fall below the per-component override level.

        Uses ``event_dict.get("component", "")`` because loggers are bound with
        ``.bind(component=__name__)`` (A1 migration). Reads ``method_name``
        directly instead of ``event_dict.get("level")`` because add_log_level
        has not run yet at this processor position.
        """
        component = event_dict.get("component", "")
        if not component:
            return event_dict  # no component key → pass through
        component_override = override_map.get(component)
        if component_override is None:
            return event_dict  # no override for this component → pass through
        event_level = stdlib_logging.getLevelName(method_name.upper())
        if isinstance(event_level, int) and event_level < component_override:
            raise structlog.DropEvent()
        return event_dict

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _filter_by_component,           # inserted between merge_contextvars and add_log_level
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            _strip_sensitive_fields,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Emit any deferred startup warnings AFTER structlog is configured (SC-007)
    if _startup_warnings:
        _warn_logger = structlog.get_logger(__name__)
        for event_name, kwargs in _startup_warnings:
            _warn_logger.warning(event_name, **kwargs)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init DB, Qdrant, providers, checkpointer. Shutdown: close connections."""
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    _configure_logging(settings.log_level, settings.log_level_overrides)
    logger = structlog.get_logger().bind(component=__name__)

    # Startup
    db = SQLiteDB(settings.sqlite_path)
    await db.connect()
    app.state.db = db
    logger.info("storage_sqlite_initialized", path=settings.sqlite_path)

    qdrant = QdrantClientWrapper(settings.qdrant_host, settings.qdrant_port)
    await qdrant.connect()
    app.state.qdrant = qdrant
    logger.info("storage_qdrant_initialized", host=settings.qdrant_host)

    # Spec 07: QdrantStorage (full-featured, coexists with QdrantClientWrapper)
    from backend.storage.qdrant_client import QdrantStorage
    qdrant_storage = QdrantStorage(settings.qdrant_host, settings.qdrant_port)
    app.state.qdrant_storage = qdrant_storage
    logger.info("storage_qdrant_storage_initialized")

    # Spec 07: KeyManager (optional -- graceful degradation if env var missing)
    from backend.providers.key_manager import KeyManager
    try:
        key_manager = KeyManager()
        app.state.key_manager = key_manager
        logger.info("storage_key_manager_initialized")
    except ValueError as e:
        logger.warning("storage_key_manager_skipped", reason=str(e))
        app.state.key_manager = None

    registry = ProviderRegistry(settings)
    await registry.initialize(db)
    app.state.registry = registry
    logger.info("provider_providers_initialized")

    # LangGraph checkpointer — separate DB for checkpoint state
    checkpoint_path = settings.sqlite_path.replace("embedinator.db", "checkpoints.db")
    checkpointer = AsyncSqliteSaver.from_conn_string(checkpoint_path)
    await checkpointer.setup()
    app.state.checkpointer = checkpointer
    logger.info("storage_checkpointer_initialized", path=checkpoint_path)

    # --- Spec 03: ResearchGraph infrastructure ---
    from backend.retrieval.searcher import HybridSearcher
    from backend.retrieval.reranker import Reranker
    from backend.storage.parent_store import ParentStore
    from backend.agent.tools import create_research_tools
    from backend.agent.research_graph import build_research_graph
    from backend.agent.conversation_graph import build_conversation_graph

    hybrid_searcher = HybridSearcher(qdrant.client, settings)
    app.state.hybrid_searcher = hybrid_searcher
    logger.info("retrieval_hybrid_searcher_initialized")

    reranker_instance = Reranker(settings)
    app.state.reranker = reranker_instance
    logger.info("retrieval_reranker_initialized", model=settings.reranker_model)

    parent_store = ParentStore(db)
    app.state.parent_store = parent_store
    logger.info("storage_parent_store_initialized")

    # Build tool list via closure-based factory (R6)
    research_tools = create_research_tools(hybrid_searcher, reranker_instance, parent_store)
    app.state.research_tools = research_tools
    logger.info("agent_research_tools_created", count=len(research_tools))

    # --- Spec 04: MetaReasoningGraph (Layer 3) ---
    from backend.agent.meta_reasoning_graph import build_meta_reasoning_graph

    # FR-011: skip meta-reasoning if max_attempts=0
    meta_reasoning_graph = None
    if settings.meta_reasoning_max_attempts > 0:
        meta_reasoning_graph = build_meta_reasoning_graph()
        logger.info("agent_meta_reasoning_graph_compiled")

    # Build graph chain inside-out: MetaReasoning -> Research -> Conversation
    research_graph = build_research_graph(
        tools=research_tools,
        meta_reasoning_graph=meta_reasoning_graph,
    )
    conversation_graph = build_conversation_graph(
        research_graph=research_graph,
        checkpointer=checkpointer,
    )
    app.state.conversation_graph = conversation_graph
    logger.info("agent_graphs_compiled", meta_reasoning_enabled=meta_reasoning_graph is not None)

    # FR-003: Observable startup warning — estimated in-process model memory (no psutil)
    # Approximate sizes for loaded sentence-transformer models.
    # LLM inference engine (Ollama/external) excluded — runs in a separate process.
    logger.warning(
        "agent_estimated_model_memory_footprint",
        reranker_model=settings.reranker_model,
        reranker_model_size_mb=400,
        embed_model=settings.default_embed_model,
        embed_model_size_mb=300,
        estimated_total_model_mb=700,
        budget_target_mb=600,
        note="SC-005: backend idle memory target <600 MB excluding inference engine",
    )

    yield

    # Shutdown
    await db.close()
    await qdrant.close()
    logger.info("storage_shutdown_complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="The Embedinator",
        description="Self-hosted agentic RAG system for private document intelligence",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Middleware (order matters — outermost first)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(TraceIDMiddleware)

    # CORS middleware — allow local network access (no auth, FR-012)
    origins = [o.strip() for o in settings.cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handler: rate limit errors from cloud providers → HTTP 429
    @app.exception_handler(ProviderRateLimitError)
    async def rate_limit_handler(request: Request, exc: ProviderRateLimitError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "PROVIDER_RATE_LIMIT",
                    "message": f"Rate limit exceeded for provider: {exc.provider}",
                    "details": {"provider": exc.provider},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: Qdrant connection errors → HTTP 503
    @app.exception_handler(QdrantConnectionError)
    async def qdrant_connection_error_handler(request: Request, exc: QdrantConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "QDRANT_UNAVAILABLE",
                    "message": "Vector database is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: Ollama connection errors → HTTP 503
    @app.exception_handler(OllamaConnectionError)
    async def ollama_connection_error_handler(request: Request, exc: OllamaConnectionError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "OLLAMA_UNAVAILABLE",
                    "message": "Inference service is temporarily unavailable",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Exception handler: global catch-all for any EmbeddinatorError → HTTP 500
    @app.exception_handler(EmbeddinatorError)
    async def embedinator_error_handler(request: Request, exc: EmbeddinatorError):
        trace_id = getattr(request.state, "trace_id", "")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred",
                    "details": {},
                },
                "trace_id": trace_id,
            },
        )

    # Register routers
    app.include_router(collections.router, tags=["collections"])
    app.include_router(documents.router, tags=["documents"])
    app.include_router(chat.router, tags=["chat"])
    app.include_router(traces.router, tags=["traces"])
    app.include_router(providers.router, tags=["providers"])
    app.include_router(health.router, tags=["health"])
    app.include_router(ingest_router.router, tags=["ingest"])
    app.include_router(models_router.router, tags=["models"])
    app.include_router(api_settings.router, tags=["settings"])

    return app


app = create_app()
